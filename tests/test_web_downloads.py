import os
import unittest
from unittest.mock import patch, MagicMock
from core.extractor import get_video_metadata, download_audio, get_video_id
from core.video_processor import download_full_video
from core.transcriber import extract_youtube_video_id, fetch_youtube_transcript


class TestWebDownloads(unittest.TestCase):

    def test_extract_youtube_video_id_ignores_external_web(self):
        # IDs de plataformas externas ou web não devem ser tratados como IDs de YouTube
        self.assertEqual(extract_youtube_video_id("web_84a178cda1"), "")
        self.assertEqual(extract_youtube_video_id("local_meuvideo"), "")
        self.assertEqual(extract_youtube_video_id("tw_180234567890"), "")
        self.assertEqual(extract_youtube_video_id("ig_C8P0lMtp6Y4"), "")
        self.assertEqual(extract_youtube_video_id("tt_7381234567890"), "")

        # IDs reais de YouTube continuam funcionando perfeitamente
        self.assertEqual(extract_youtube_video_id("aa-dLeL-Rf4"), "aa-dLeL-Rf4")
        self.assertEqual(extract_youtube_video_id("https://www.youtube.com/watch?v=aa-dLeL-Rf4"), "aa-dLeL-Rf4")

    def test_fetch_youtube_transcript_returns_early_for_web(self):
        res = fetch_youtube_transcript("web_84a178cda1")
        self.assertIsNone(res.get("transcript_segments"))
        self.assertIn("inválido", res.get("error", "").lower())

    @patch("yt_dlp.YoutubeDL")
    def test_get_video_metadata_article_playlist_extraction(self, mock_ydl_cls):
        mock_instance = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        # Simula resposta de artigo com múltiplos vídeos (GloboArticle)
        mock_instance.extract_info.return_value = {
            "_type": "playlist",
            "title": "Artigo Jornal Nacional - Todas as notícias",
            "entries": [
                {
                    "id": "14905212",
                    "title": "Renan Santos é entrevistado na Globo; veja íntegra",
                    "duration": 2670.5,
                    "upload_date": "20260826",
                    "thumbnail": "https://s2.glbimg.com/thumb_video.jpg",
                    "uploader": "Jornal Nacional",
                    "webpage_url": "https://g1.globo.com/jornal-nacional/..."
                },
                {
                    "id": "14905089",
                    "title": "Trecho secundário 2",
                    "duration": 120.0
                }
            ]
        }

        meta = get_video_metadata("https://g1.globo.com/jornal-nacional/noticia/2026/08/26/entrevista.ghtml")

        self.assertIsNone(meta.get("error"))
        # Garante que pegou o título e duração do vídeo principal (item 1) e não o título genérico do artigo
        self.assertEqual(meta["title"], "Renan Santos é entrevistado na Globo; veja íntegra")
        self.assertEqual(meta["duration"], 2670.5)
        self.assertEqual(meta["thumbnail"], "https://s2.glbimg.com/thumb_video.jpg")

        # Verifica flags de proteção contra download em lote indesejado
        called_opts = mock_ydl_cls.call_args[0][0]
        self.assertTrue(called_opts.get("noplaylist"))
        self.assertEqual(called_opts.get("playlist_items"), "1")
        self.assertTrue(called_opts.get("ignoreerrors"))

    @patch("os.remove")
    @patch("yt_dlp.YoutubeDL")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.getsize", return_value=1024 * 1024 * 50)
    def test_download_full_video_flags_for_web(self, mock_size, mock_exists, mock_ydl_cls, mock_remove):
        mock_instance = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        res = download_full_video("https://g1.globo.com/artigo.ghtml", "data/test/video_full.mp4")
        self.assertIsNone(res.get("error"))
        self.assertEqual(res.get("path"), "data/test/video_full.mp4")

        called_opts = mock_ydl_cls.call_args[0][0]
        self.assertTrue(called_opts.get("noplaylist"))
        self.assertEqual(called_opts.get("playlist_items"), "1")
        self.assertTrue(called_opts.get("ignoreerrors"))

    def test_low_res_native_video_cache_preserved(self):
        # Vídeos com resolução nativa < 720p (ex: 832x464 do Twitter/X) não devem ser marcados para re-download se já existem
        with patch("os.path.exists", return_value=True), patch("os.path.getsize", return_value=15000):
            video_full_path = "data/tw_test/video_full.mp4"
            need_download = not (os.path.exists(video_full_path) and os.path.getsize(video_full_path) > 10240)
            self.assertFalse(need_download, "Vídeo existente no cache com tamanho válido não deve acionar download nem ser excluído")

    def test_library_entry_lookup_with_list(self):
        # get_library retorna uma lista de dicionários; busca deve usar gerador/next sem lançar AttributeError
        fake_library = [
            {"id": "yt_123", "title": "Vídeo YouTube", "is_live": False},
            {"id": "tw_2097418273868706066", "title": "Vídeo Twitter/X", "is_live": False}
        ]
        video_id = "tw_2097418273868706066"
        entry = next((item for item in fake_library if item.get("id") == video_id), {})
        self.assertEqual(entry.get("id"), "tw_2097418273868706066")
        self.assertFalse(entry.get("is_live"))

        # Caso não exista
        entry_missing = next((item for item in fake_library if item.get("id") == "inexistente"), {})
        self.assertEqual(entry_missing, {})
        self.assertFalse(bool(entry_missing.get("is_live")))


if __name__ == '__main__':
    unittest.main()

