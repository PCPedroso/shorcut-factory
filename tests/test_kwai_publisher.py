"""
Testes unitários para o módulo KwaiPublisher (Exportação Assistida Kwai Creator).
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.publishing.base import Platform, AdaptedCaption
from core.publishing.kwai import KwaiPublisher


class TestKwaiPublisher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.publisher = KwaiPublisher()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auth_status_always_ready(self):
        status = self.publisher.get_auth_status()
        self.assertTrue(status.is_authenticated)
        self.assertIn("Exportação Assistida", status.message)

    @patch("core.publishing.kwai.webbrowser.open")
    @patch.object(KwaiPublisher, "_reveal_in_windows_explorer")
    @patch.object(KwaiPublisher, "_copy_to_windows_clipboard")
    def test_publish_assisted_success(self, mock_clip, mock_reveal, mock_browser):
        mock_clip.return_value = True

        video_file = os.path.join(self.temp_dir.name, "kwai_video.mp4")
        with open(video_file, "wb") as f:
            f.write(b"video kwai")

        caption = AdaptedCaption(
            platform=Platform.KWAI,
            title="Vídeo Incrível",
            full_text="Vídeo Incrível #kwai #viral"
        )

        res = self.publisher.publish(video_path=video_file, caption_data=caption, options={"open_browser": True})

        self.assertTrue(res.success)
        self.assertTrue(res.requires_manual_step)
        self.assertIsNotNone(res.manual_instructions)
        self.assertEqual(res.post_url, "https://creator.kwai.com/")

        mock_clip.assert_called_once_with("Vídeo Incrível #kwai #viral")
        mock_reveal.assert_called_once_with(video_file)
        mock_browser.assert_called_once_with("https://creator.kwai.com/")

    def test_publish_missing_video(self):
        res = self.publisher.publish("caminho_inexistente_123.mp4", {"title": "X"})
        self.assertFalse(res.success)
        self.assertIn("não encontrado", res.error)


if __name__ == "__main__":
    unittest.main()
