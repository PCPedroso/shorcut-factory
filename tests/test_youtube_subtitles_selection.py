import unittest
from unittest.mock import MagicMock, patch
from core.transcriber import (
    format_language_label,
    list_available_youtube_transcripts,
    fetch_youtube_transcript,
    _YT_TRANSCRIPTS_CACHE
)


class TestYouTubeSubtitlesSelection(unittest.TestCase):
    """
    Testes unitários para a seleção e download de diferentes faixas de legendas do YouTube
    na primeira aba (Ingestão & Transcrição).
    """

    def setUp(self):
        # Limpa o cache entre testes
        _YT_TRANSCRIPTS_CACHE.clear()

    def test_format_language_label(self):
        """Valida a formação amigável de rótulos com bandeiras e identificadores."""
        pt_label = format_language_label("pt", "Portuguese", is_generated=True)
        self.assertIn("🇧🇷", pt_label)
        self.assertIn("Portuguese [pt]", pt_label)
        self.assertIn("(Automática)", pt_label)

        en_label = format_language_label("en", "English", is_generated=False)
        self.assertIn("🇺🇸", en_label)
        self.assertIn("English [en]", en_label)
        self.assertIn("(Oficial)", en_label)

        es_label = format_language_label("es", "Spanish", is_generated=False)
        self.assertIn("🇪🇸", es_label)

        other_label = format_language_label("nl", "Dutch", is_generated=True)
        self.assertIn("🌐", other_label)

    @patch("youtube_transcript_api.YouTubeTranscriptApi.list")
    def test_list_available_youtube_transcripts_sorting(self, mock_list):
        """Valida que o português é sempre priorizado no topo da lista."""
        mock_t_en = MagicMock()
        mock_t_en.language_code = "en"
        mock_t_en.language = "English (auto-generated)"
        mock_t_en.is_generated = True
        mock_t_en.is_translatable = True

        mock_t_pt = MagicMock()
        mock_t_pt.language_code = "pt"
        mock_t_pt.language = "Portuguese (auto-generated)"
        mock_t_pt.is_generated = True
        mock_t_pt.is_translatable = True

        mock_t_ar = MagicMock()
        mock_t_ar.language_code = "ar"
        mock_t_ar.language = "Arabic"
        mock_t_ar.is_generated = False
        mock_t_ar.is_translatable = False

        mock_list.return_value = [mock_t_ar, mock_t_en, mock_t_pt]

        subs = list_available_youtube_transcripts("12345678901")
        self.assertEqual(len(subs), 3)
        # Primeiro item deve ser Português
        self.assertEqual(subs[0]["code"], "pt")
        # Segundo item deve ser Inglês
        self.assertEqual(subs[1]["code"], "en")
        # Terceiro item deve ser Árabe
        self.assertEqual(subs[2]["code"], "ar")

    @patch("youtube_transcript_api.YouTubeTranscriptApi.list")
    def test_fetch_youtube_transcript_with_selected_language(self, mock_list):
        """Valida a busca direcionada com selected_language='pt'."""
        mock_tr = MagicMock()
        mock_tr.language_code = "pt"
        mock_tr.language = "Portuguese (auto-generated)"
        mock_tr.fetch.return_value = [
            {"start": 1.5, "duration": 3.0, "text": "Olá a todos e bem-vindos."},
            {"start": 4.5, "duration": 2.5, "text": "Hoje vamos discutir o projeto."}
        ]

        mock_tl = MagicMock()
        mock_tl.find_transcript.return_value = mock_tr
        mock_list.return_value = mock_tl

        res = fetch_youtube_transcript("a8Tfy8OmK18", selected_language="pt")
        self.assertIsNone(res.get("error"))
        self.assertEqual(len(res.get("transcript_segments", [])), 2)
        self.assertEqual(res["selected_language"], "Portuguese (auto-generated)")
        self.assertEqual(res["selected_language_code"], "pt")
        self.assertEqual(res["transcript_segments"][0]["start"], 1.5)
        self.assertEqual(res["transcript_segments"][0]["end"], 4.5)
        self.assertEqual(res["transcript_segments"][0]["text"], "Olá a todos e bem-vindos.")

    @patch("youtube_transcript_api.YouTubeTranscriptApi.list")
    def test_fetch_youtube_transcript_fallback_translation(self, mock_list):
        """Valida o fallback de tradução quando uma faixa específica não existe diretamente mas é translatable."""
        mock_en_track = MagicMock()
        mock_en_track.language_code = "en"
        mock_en_track.language = "English"
        mock_en_track.is_translatable = True

        mock_pt_translated = MagicMock()
        mock_pt_translated.language_code = "pt"
        mock_pt_translated.language = "Portuguese"
        mock_pt_translated.fetch.return_value = [
            {"start": 0.0, "duration": 2.0, "text": "Texto traduzido"}
        ]
        mock_en_track.translate.return_value = mock_pt_translated

        mock_tl = MagicMock()
        mock_tl.__iter__.return_value = [mock_en_track]
        mock_tl.find_transcript.side_effect = Exception("Not found")
        mock_tl.find_generated_transcript.side_effect = Exception("Not found")
        mock_tl.find_manually_created_transcript.side_effect = Exception("Not found")
        mock_list.return_value = mock_tl

        res = fetch_youtube_transcript("12345678901", selected_language="pt")
        self.assertIsNone(res.get("error"))
        self.assertEqual(len(res.get("transcript_segments", [])), 1)
        self.assertEqual(res["transcript_segments"][0]["text"], "Texto traduzido")


if __name__ == "__main__":
    unittest.main()
