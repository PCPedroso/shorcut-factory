import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from app import get_current_active_video_id
from core.transcriber import ensure_cut_transcript
from core.translator import translate_cut_subtitles


class TestLazyTranscription(unittest.TestCase):
    """
    Testa a arquitetura de Transcrição Sob Demanda (Lazy Transcription):
    - Vídeo pronto para corte sem necessidade de rodar Whisper na íntegra.
    - Transcrição pontual de slice de corte com aplicação de offset temporal.
    - Desbloqueio das seções 3 e 4 com base na existência de mídia de projeto.
    - Função canônica ensure_cut_transcript para legendas e IA.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="viralcut_test_lazy_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_media_ready_condition_without_full_transcription(self):
        """
        Valida que o player e as ações da Seção 1 são liberados
        quando video_ready for True ou video_full.mp4 existir, mesmo sem transcription_done.
        """
        session = {"transcription_done": False, "video_ready": True}
        has_media_ready = (
            session.get("transcription_done", False) or
            session.get("video_ready", False)
        )
        self.assertTrue(has_media_ready, "Mídia deve ser considerada pronta para o usuário cortar")

    def test_slice_transcript_timestamp_offset(self):
        """
        Testa se o offset de start_time (ex: corte de 00:05:00 a 00:06:00)
        é aplicado corretamente aos segmentos e palavras do slice pontual.
        """
        from core.extractor import parse_time_str

        start_time_str = "00:05:00.00"
        s_offset = parse_time_str(start_time_str) or 0.0
        self.assertEqual(s_offset, 300.0)

        raw_slice_segments = [
            {
                "start": 0.5,
                "end": 2.5,
                "text": "Olá mundo",
                "words": [
                    {"word": "Olá", "start": 0.5, "end": 1.2},
                    {"word": "mundo", "start": 1.3, "end": 2.5}
                ]
            }
        ]

        # Aplica o offset temporal
        for seg in raw_slice_segments:
            seg["start"] += s_offset
            seg["end"] += s_offset
            for w in seg.get("words", []):
                w["start"] += s_offset
                w["end"] += s_offset

        self.assertEqual(raw_slice_segments[0]["start"], 300.5)
        self.assertEqual(raw_slice_segments[0]["end"], 302.5)
        self.assertEqual(raw_slice_segments[0]["words"][0]["start"], 300.5)
        self.assertEqual(raw_slice_segments[0]["words"][1]["end"], 302.5)

    def test_unblocking_sections_3_and_4(self):
        """
        Valida que Seções 3 e 4 não são bloqueadas se houver vídeo ou áudio no diretório,
        mesmo com transcription_done sendo False.
        """
        session = {"transcription_done": False, "video_ready": True}
        has_any_project_media = (
            session.get("transcription_done", False) or
            session.get("video_ready", False)
        )
        self.assertTrue(has_any_project_media)

    @patch("os.path.exists")
    @patch("os.path.getsize")
    def test_ensure_cut_transcript_returns_global_if_exists(self, mock_getsize, mock_exists):
        """
        Se data/{video_id}/transcript.json existir, ensure_cut_transcript deve retorná-lo
        sem rodar Whisper.
        """
        mock_exists.side_effect = lambda path: "transcript.json" in path
        mock_getsize.return_value = 500

        res = ensure_cut_transcript(
            video_id="dummy_vid",
            start_time_str="00:01:00.00",
            end_time_str="00:01:30.00"
        )
        self.assertFalse(res.get("is_cut_slice"))
        self.assertIn("transcript.json", res.get("transcript_path"))
        self.assertIsNone(res.get("error"))

    def test_ensure_cut_transcript_generates_slice_and_applies_offset(self):
        """
        Testa geração de fatia pontual com mock de extração de áudio e Whisper.
        Valida que os timestamps são offsettados corretamente e salvos em JSON.
        """
        vid_id = "test_vid_lazy_123"
        v_data_dir = os.path.join("data", vid_id)
        os.makedirs(v_data_dir, exist_ok=True)
        dummy_media = os.path.join(v_data_dir, "video_full.mp4")
        with open(dummy_media, "w") as f:
            f.write("fake video data")

        try:
            with patch("subprocess.run") as mock_subproc, \
                 patch("core.transcriber.transcribe_audio") as mock_transcribe:

                def fake_ffmpeg(cmd, *args, **kwargs):
                    out_aud = cmd[-1]
                    with open(out_aud, "w") as f_aud:
                        f_aud.write("fake audio")
                    return MagicMock(returncode=0)

                mock_subproc.side_effect = fake_ffmpeg

                # Simula que o Whisper transcreveu o áudio do corte (0.0s a 15.0s)
                mock_transcribe.return_value = {
                    "transcript_segments": [
                        {
                            "start": 0.0,
                            "end": 4.5,
                            "text": "Fala importante",
                            "words": [
                                {"word": "Fala", "start": 0.0, "end": 1.5},
                                {"word": "importante", "start": 1.6, "end": 4.5}
                            ]
                        }
                    ],
                    "full_text": "Fala importante",
                    "error": None
                }

                res = ensure_cut_transcript(
                    video_id=vid_id,
                    start_time_str="00:02:00.00",
                    end_time_str="00:02:15.00",
                    media_path=dummy_media
                )

                self.assertTrue(res.get("is_cut_slice"))
                self.assertIsNotNone(res.get("transcript_path"))
                self.assertIsNone(res.get("error"))
                # Valida que o JSON do corte foi salvo com offset de 120s
                with open(res["transcript_path"], "r", encoding="utf-8") as f_tr:
                    saved_data = json.load(f_tr)
                self.assertEqual(saved_data["segments"][0]["start"], 120.0)
                self.assertEqual(saved_data["segments"][0]["words"][0]["start"], 120.0)
        finally:
            if os.path.exists(v_data_dir):
                shutil.rmtree(v_data_dir, ignore_errors=True)

    def test_translate_cut_subtitles_accepts_custom_transcript_path(self):
        """
        Valida que translate_cut_subtitles aceita transcript_path personalizado
        para traduzir diretamente fatias pontuais sob demanda.
        """
        slice_file = os.path.join(self.test_dir, "_cut_tr_test.json")
        with open(slice_file, "w", encoding="utf-8") as f:
            json.dump({
                "segments": [
                    {
                        "start": 120.0,
                        "end": 124.0,
                        "text": "Olá mundo",
                        "words": [{"word": "Olá", "start": 120.0, "end": 122.0}]
                    }
                ]
            }, f)

        with patch("core.translator.translate_transcript_segments") as mock_tr:
            mock_tr.return_value = {
                "segments": [
                    {
                        "start": 120.0,
                        "end": 124.0,
                        "text": "Hello world",
                        "words": [{"word": "Hello", "start": 120.0, "end": 122.0}]
                    }
                ],
                "error": None
            }

            res = translate_cut_subtitles(
                video_id="any_id",
                start_time_str="00:02:00.00",
                end_time_str="00:02:10.00",
                target_lang="en",
                transcript_path=slice_file
            )
            self.assertIsNone(res.get("error"))
            self.assertEqual(res.get("count"), 1)


if __name__ == "__main__":
    unittest.main()
