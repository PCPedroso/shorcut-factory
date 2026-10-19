"""
Testes unitários para o módulo core/publishing/ui_tab.py (Central de Publicação Streamlit).
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import streamlit as st
from core.publishing.base import Platform, JobStatus
from core.publishing.credentials import CredentialVault
from core.publishing.publish_queue import PublishQueue
from core.publishing.ui_tab import (
    get_or_start_worker,
    render_publishing_tab
)


class TestPublishingUI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "vault.enc")
        self.vault = CredentialVault(vault_path=self.vault_path)
        self.queue_db = os.path.join(self.temp_dir.name, "queue.db")
        self.queue = PublishQueue(db_path=self.queue_db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_or_start_worker_lifecycle(self):
        worker = get_or_start_worker()
        self.assertIsNotNone(worker)
        self.assertTrue(worker.is_running)

    @patch("core.publishing.ui_tab.st")
    def test_render_publishing_tab_smoke(self, mock_st):
        # Configura mocks para tabs, columns e expanders do Streamlit
        mock_st.columns.side_effect = lambda spec: [MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]
        mock_st.tabs.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_st.text_input.return_value = ""
        mock_st.selectbox.return_value = 0
        mock_st.checkbox.return_value = False
        mock_st.radio.return_value = "Publicar Imediatamente (Na Fila)"
        mock_st.button.return_value = False
        mock_st.session_state = {}

        # Insere um job na fila de teste
        self.queue.enqueue(
            cut_folder="test_cut.mp4",
            platform=Platform.YOUTUBE,
            cut_title="Shorts Test",
            payload={"caption_data": {"title": "Shorts Test"}}
        )

        # Não deve lançar exceções durante renderização
        try:
            render_publishing_tab(vault=self.vault, queue=self.queue)
            rendered = True
        except Exception as e:
            rendered = False
            print(f"Erro ao renderizar aba: {e}")

        self.assertTrue(rendered)


if __name__ == "__main__":
    unittest.main()
