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

    def test_set_initial_and_final_time_from_player(self):
        # Testa a lógica de transferir o momento pausado do player para a Seção 3
        from core.analyzer import normalize_time_mask

        session = {}
        # Simula o momento pausado no player em 01:23.45 (1 minuto, 23 segundos, 45 ms)
        session["player_synced_time"] = "00:01:23.45"

        # 1. Simula clique em "Setar Tempo Inicial"
        cur_t = normalize_time_mask(session["player_synced_time"])
        session["final_start_time"] = cur_t
        self.assertEqual(session["final_start_time"], "00:01:23.45")

        # 2. Simula avançar o player e pausar em 02:40.00
        session["player_synced_time"] = "00:02:40.00"
        cur_t2 = normalize_time_mask(session["player_synced_time"])
        session["final_end_time"] = cur_t2
        self.assertEqual(session["final_end_time"], "00:02:40.00")

        # 3. Intervalo resultante para corte na Seção 3
        self.assertTrue(session["final_start_time"] < session["final_end_time"])

    def test_open_in_file_explorer_directory_and_file(self):
        from app import open_in_file_explorer

        with patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True), \
             patch("os.startfile") as mock_startfile:
            res = open_in_file_explorer("data/test_vid")
            self.assertTrue(res)
            mock_startfile.assert_called_once()

    def test_navigate_to_section3_syncs_stepper_radio(self):
        from core.ui_theme import navigate_to_step
        import streamlit as st

        mock_state = {"active_workflow_step": "1. 📥 Ingestão & Transcrição", "workflow_stepper_radio": "1. 📥 Ingestão & Transcrição"}
        with patch.object(st, "session_state", mock_state):
            nav_ok = navigate_to_step("3")
            self.assertTrue(nav_ok)
            self.assertEqual(mock_state["active_workflow_step"], "3. ✂️ Fábrica de Enquadramento 9:16")
            self.assertEqual(mock_state["workflow_stepper_radio"], "3. ✂️ Fábrica de Enquadramento 9:16")


if __name__ == "__main__":
    unittest.main()

