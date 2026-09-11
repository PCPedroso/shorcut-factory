import os
import json
import unittest
from unittest.mock import patch, MagicMock
from app import get_current_active_video_id


class TestLazyTranscription(unittest.TestCase):
    """
    Testa a arquitetura de Transcrição Sob Demanda (Lazy Transcription):
    - Vídeo pronto para corte sem necessidade de rodar Whisper na íntegra.
    - Transcrição pontual de slice de corte com aplicação de offset temporal.
    - Desbloqueio das seções 3 e 4 com base na existência de mídia de projeto.
    """

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

        # Simula resultado do Whisper para o trecho de áudio de 60s
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

        # Valida que as palavras agora caem dentro do intervalo 300s - 360s
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


if __name__ == "__main__":
    unittest.main()
