import os
import json
import tempfile
import unittest
from core.extractor import get_video_components_status
from core.transcriber import append_incremental_transcript


class TestIncrementalProcessing(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_get_video_components_status_partial_like_user_case(self):
        # Simula o cenário relatado pelo usuário:
        # data/<video_id> tem audio.mp3, metadata.json e transcript.json, mas NÃO tem video_full.mp4
        vid = "swd0rS-43q0_mock"
        v_dir = os.path.join(self.test_dir, vid)
        os.makedirs(v_dir, exist_ok=True)

        # 1. metadata.json
        with open(os.path.join(v_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump({
                "video_id": vid,
                "title": "ENCONTRO COM PRESIDENCIÁVEIS",
                "is_live": True,
                "duration": 3000.0
            }, f)

        # 2. audio.mp3 (> 10KB)
        with open(os.path.join(v_dir, "audio.mp3"), "wb") as f:
            f.write(b"0" * 20480)

        # 3. transcript.json
        with open(os.path.join(v_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump({
                "full_text": "Primeira fala da live. Segunda fala.",
                "segments": [
                    {"start": 0.0, "end": 10.0, "text": "Primeira fala da live."},
                    {"start": 10.5, "end": 2400.0, "text": "Segunda fala."}
                ]
            }, f)

        status = get_video_components_status(vid, data_dir=self.test_dir, remote_duration=3000.0)

        self.assertTrue(status["has_audio"])
        self.assertTrue(status["has_transcript"])
        self.assertFalse(status["has_video"])
        self.assertTrue(status["is_live"])
        self.assertEqual(status["segments_count"], 2)
        self.assertEqual(status["last_transcript_sec"], 2400.0)
        self.assertIn("video", status["missing_components"])
        self.assertIn("ai_analysis", status["missing_components"])
        # 3000 - 2400 = 600 segundos = 10 minutos novos
        self.assertEqual(status["new_minutes_available"], 10.0)
        self.assertIn("new_live_minutes", status["missing_components"])
        self.assertTrue(status["can_process_incrementally"])

    def test_get_video_components_status_missing_dir(self):
        status = get_video_components_status("video_inexistente", data_dir=self.test_dir)
        self.assertFalse(status["exists_dir"])
        self.assertFalse(status["has_audio"])
        self.assertFalse(status["has_transcript"])
        self.assertFalse(status["has_video"])
        self.assertFalse(status["can_process_incrementally"])

    def test_append_incremental_transcript(self):
        tr_file = os.path.join(self.test_dir, "transcript.json")
        # Cria transcrição existente de 0 a 100 segundos
        with open(tr_file, "w", encoding="utf-8") as f:
            json.dump({
                "full_text": "Trecho anterior gravado.",
                "segments": [
                    {"start": 0.0, "end": 100.0, "text": "Trecho anterior gravado."}
                ],
                "source": "Whisper"
            }, f)

        # Novos segmentos capturados a partir do segundo 100.0
        new_segs = [
            {"start": 0.0, "end": 15.5, "text": "Novo trecho que acabou de ser transmitido.", "words": [{"word": "Novo", "start": 0.0, "end": 1.0}]},
            {"start": 16.0, "end": 45.0, "text": "Conclusão final da fala.", "words": []}
        ]

        result = append_incremental_transcript(tr_file, new_segs, start_offset_sec=100.0)

        # Verifica mesclagem
        self.assertEqual(len(result["transcript_segments"]), 3)
        self.assertEqual(result["transcript_segments"][0]["start"], 0.0)
        self.assertEqual(result["transcript_segments"][0]["end"], 100.0)
        # O novo segmento deve ter o offset 100 somado
        self.assertEqual(result["transcript_segments"][1]["start"], 100.0)
        self.assertEqual(result["transcript_segments"][1]["end"], 115.5)
        self.assertEqual(result["transcript_segments"][1]["words"][0]["start"], 100.0)
        self.assertEqual(result["transcript_segments"][2]["start"], 116.0)
        self.assertEqual(result["transcript_segments"][2]["end"], 145.0)

        # Verifica texto consolidado
        self.assertIn("Trecho anterior gravado.", result["full_text"])
        self.assertIn("Novo trecho que acabou de ser transmitido.", result["full_text"])

        # Verifica persistência no arquivo JSON
        with open(tr_file, "r", encoding="utf-8") as f_check:
            saved_json = json.load(f_check)
            self.assertEqual(len(saved_json["segments"]), 3)
            self.assertTrue(saved_json.get("incremental_updated_at"))


if __name__ == '__main__':
    unittest.main()
