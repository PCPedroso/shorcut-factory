import unittest
from unittest.mock import patch, MagicMock
import os
import streamlit as st
from core.config_manager import DEFAULT_SETTINGS, load_settings, save_setting
from app import clear_current_project, get_current_active_video_id


class TestClearProjectAndStartup(unittest.TestCase):
    def test_default_settings_contains_startup_keys(self):
        self.assertIn("auto_load_last_project", DEFAULT_SETTINGS)
        self.assertIn("last_active_video_id", DEFAULT_SETTINGS)
        self.assertFalse(DEFAULT_SETTINGS["auto_load_last_project"])
        self.assertEqual(DEFAULT_SETTINGS["last_active_video_id"], "")

    def test_clear_current_project_resets_session_and_config(self):
        st.session_state["active_video_id"] = "StiuPmUgneE"
        st.session_state["video_url"] = "https://youtube.com/watch?v=StiuPmUgneE"
        st.session_state["input_yt_url"] = "https://youtube.com/watch?v=StiuPmUgneE"
        st.session_state["transcription_done"] = True
        st.session_state["video_ready"] = True
        st.session_state["full_text"] = "Olá mundo"
        st.session_state["segments"] = [{"text": "Olá"}]
        st.session_state["pautas"] = [{"title": "Pauta 1"}]

        with patch("app.save_setting") as mock_save:
            clear_current_project()

            self.assertEqual(st.session_state.get("active_video_id"), "")
            self.assertEqual(st.session_state.get("video_url"), "")
            self.assertEqual(st.session_state.get("input_yt_url"), "")
            self.assertFalse(st.session_state.get("transcription_done"))
            self.assertFalse(st.session_state.get("video_ready"))
            self.assertEqual(st.session_state.get("full_text"), "")
            self.assertEqual(st.session_state.get("segments"), [])
            self.assertEqual(st.session_state.get("pautas"), [])
            self.assertTrue(st.session_state.get("_project_cleared_by_user"))

            mock_save.assert_any_call("last_active_video_id", "")
            mock_save.assert_any_call("last_video_url", "")

    def test_get_current_active_video_id_when_auto_load_disabled(self):
        st.session_state.clear()
        with patch.dict("app._cfg", {"auto_load_last_project": False, "last_active_video_id": "StiuPmUgneE"}):
            vid = get_current_active_video_id("")
            self.assertEqual(vid, "")


if __name__ == "__main__":
    unittest.main()
