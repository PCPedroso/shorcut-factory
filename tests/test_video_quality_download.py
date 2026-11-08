"""
tests/test_video_quality_download.py
Validação automatizada da política de qualidade máxima no download de vídeos:
- Garantia de que a especificação de formatos prioriza Full HD (1080p) e HD (720p).
- Garantia de que o solver EJS remoto (ejs:github) está configurado para decifrar os fluxos do YouTube com Deno.
- Validação da função validate_downloaded_video_quality contra rebaixamentos para 360p/480p.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from core.runtime_env import get_yt_dlp_remote_components
from core.video_processor import (
    get_optimal_video_format,
    validate_downloaded_video_quality,
    download_full_video,
)


class TestVideoQualityDownload(unittest.TestCase):

    def test_get_yt_dlp_remote_components_returns_ejs_github(self):
        """Garante que a lista de componentes remotos inclui ejs:github para o solver JS."""
        components = get_yt_dlp_remote_components()
        self.assertIsInstance(components, list)
        self.assertIn("ejs:github", components)

    def test_get_optimal_video_format_prioritizes_hd(self):
        """Garante que o formato para YouTube prioriza Full HD e não contém best[ext=mp4] antes de bestvideo+bestaudio."""
        fmt_youtube = get_optimal_video_format("https://www.youtube.com/watch?v=g9JtkxxZTqA")
        
        # Não deve conter 'best[ext=mp4]' na string do YouTube (que causava o download do format 18 de 360p)
        self.assertNotIn("best[ext=mp4]", fmt_youtube)
        
        # Deve priorizar bestvideo de até 1920 e conter fallback para bestvideo+bestaudio
        self.assertIn("bestvideo", fmt_youtube)
        self.assertIn("bestaudio", fmt_youtube)
        self.assertIn("best[height>=720]", fmt_youtube)

    @patch("os.remove")
    @patch("yt_dlp.YoutubeDL")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.getsize", return_value=1024 * 1024 * 50)
    @patch("core.video_processor.validate_downloaded_video_quality", return_value={"valid": True, "is_high_quality": True, "width": 1920, "height": 1080})
    def test_download_full_video_uses_remote_components_and_js_runtimes(
        self, mock_val, mock_size, mock_exists, mock_ydl_cls, mock_remove
    ):
        """Garante que download_full_video configura remote_components e js_runtimes no YoutubeDL."""
        mock_instance = MagicMock()
        mock_instance.download.return_value = 0
        mock_ydl_cls.return_value.__enter__.return_value = mock_instance

        res = download_full_video("https://www.youtube.com/watch?v=g9JtkxxZTqA", "data/test/video_full.mp4")
        self.assertIsNone(res.get("error"))
        self.assertEqual(res.get("path"), "data/test/video_full.mp4")

        called_opts = mock_ydl_cls.call_args[0][0]
        self.assertIn("remote_components", called_opts)
        self.assertIn("ejs:github", called_opts["remote_components"])
        self.assertIn("js_runtimes", called_opts)

    @patch("cv2.VideoCapture")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.getsize", return_value=1024 * 1024 * 50)
    def test_validate_downloaded_video_quality_1080p_success(self, mock_size, mock_exists, mock_cv2_cap):
        """Vídeo 1920x1080 (Full HD horizontal) é reconhecido como alta qualidade."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda prop: {
            3: 1920,   # cv2.CAP_PROP_FRAME_WIDTH
            4: 1080,   # cv2.CAP_PROP_FRAME_HEIGHT
            5: 30.0,   # cv2.CAP_PROP_FPS
        }.get(prop, 0)
        mock_cv2_cap.return_value = mock_cap_instance

        res = validate_downloaded_video_quality("data/test/video_1080p.mp4", min_height=720)
        self.assertTrue(res["valid"])
        self.assertTrue(res["is_high_quality"])
        self.assertEqual(res["width"], 1920)
        self.assertEqual(res["height"], 1080)
        self.assertIsNone(res["warning"])

    @patch("cv2.VideoCapture")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.getsize", return_value=1024 * 1024 * 50)
    def test_validate_downloaded_video_quality_vertical_shorts_success(self, mock_size, mock_exists, mock_cv2_cap):
        """Vídeo 1080x1920 (Full HD vertical 9:16 Shorts) é reconhecido como alta qualidade."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda prop: {
            3: 1080,   # cv2.CAP_PROP_FRAME_WIDTH
            4: 1920,   # cv2.CAP_PROP_FRAME_HEIGHT
            5: 30.0,   # cv2.CAP_PROP_FPS
        }.get(prop, 0)
        mock_cv2_cap.return_value = mock_cap_instance

        res = validate_downloaded_video_quality("data/test/video_shorts.mp4", min_height=720)
        self.assertTrue(res["valid"])
        self.assertTrue(res["is_high_quality"])
        self.assertIsNone(res["warning"])

    @patch("cv2.VideoCapture")
    @patch("os.path.exists", return_value=True)
    @patch("os.path.getsize", return_value=1024 * 1024 * 10)
    def test_validate_downloaded_video_quality_360p_detects_warning(self, mock_size, mock_exists, mock_cv2_cap):
        """Vídeo 640x360 (360p de baixa qualidade) dispara is_high_quality=False e aviso descritivo."""
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = True
        mock_cap_instance.get.side_effect = lambda prop: {
            3: 640,    # cv2.CAP_PROP_FRAME_WIDTH
            4: 360,    # cv2.CAP_PROP_FRAME_HEIGHT
            5: 24.0,   # cv2.CAP_PROP_FPS
        }.get(prop, 0)
        mock_cv2_cap.return_value = mock_cap_instance

        res = validate_downloaded_video_quality("data/test/video_360p.mp4", min_height=720)
        self.assertTrue(res["valid"])
        self.assertFalse(res["is_high_quality"])
        self.assertIsNotNone(res["warning"])
        self.assertIn("640x360", res["warning"])
        self.assertIn("720p", res["warning"])

    def test_validate_downloaded_video_quality_missing_file(self):
        """Arquivo inexistente retorna valid=False."""
        res = validate_downloaded_video_quality("caminho/completamente/inexistente.mp4")
        self.assertFalse(res["valid"])
        self.assertFalse(res["is_high_quality"])


if __name__ == "__main__":
    unittest.main()
