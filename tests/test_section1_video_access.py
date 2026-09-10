import os
import unittest
from unittest.mock import patch, MagicMock
from app import safe_display_video, get_current_active_video_id


class TestSection1VideoAccess(unittest.TestCase):
    """
    Testa o acesso e reprodução do vídeo processado na Seção 1 (primeira fase).
    """

    @patch("streamlit.video")
    def test_safe_display_video_with_valid_file(self, mock_st_video):
        # Simula arquivo de vídeo existente
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024 * 1024 * 15):
            safe_display_video("data/test_video/video_full.mp4")
            mock_st_video.assert_called_once()

    @patch("streamlit.warning")
    def test_safe_display_video_with_missing_file(self, mock_st_warning):
        with patch("os.path.exists", return_value=False):
            safe_display_video("data/inexistente/video_full.mp4")
            mock_st_warning.assert_called_once()

    def test_get_current_active_video_id_retrieval(self):
        # Garante que get_current_active_video_id resolve o ID correto para a Seção 1
        with patch("streamlit.session_state", {"active_video_id": "test_active_123"}), \
             patch("os.path.exists", return_value=True):
            vid = get_current_active_video_id()
            self.assertEqual(vid, "test_active_123")


if __name__ == "__main__":
    unittest.main()
