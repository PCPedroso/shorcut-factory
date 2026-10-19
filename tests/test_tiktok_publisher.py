"""
Testes unitários para o módulo TikTokPublisher (TikTok Content Posting API v2).
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.publishing.base import Platform, AdaptedCaption
from core.publishing.credentials import CredentialVault
from core.publishing.tiktok import TikTokPublisher


class TestTikTokPublisher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "vault.enc")
        self.vault = CredentialVault(vault_path=self.vault_path)
        self.publisher = TikTokPublisher(vault=self.vault)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auth_status_unconfigured(self):
        status = self.publisher.get_auth_status()
        self.assertFalse(status.is_authenticated)
        self.assertIn("Nenhuma credencial", status.message)

    def test_auth_status_configured(self):
        self.vault.save_credential(Platform.TIKTOK, {
            "access_token": "act.tiktok_token_123",
            "open_id": "open_id_xyz",
            "display_name": "cortes_virais"
        })
        status = self.publisher.get_auth_status()
        self.assertTrue(status.is_authenticated)
        self.assertIn("@cortes_virais", status.account_name)

    @patch("core.publishing.tiktok.requests.post")
    def test_refresh_access_token(self, mock_post):
        self.vault.save_credential(Platform.TIKTOK, {
            "access_token": "old_tok",
            "refresh_token": "r_tok_456"
        })

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_tok_789",
            "refresh_token": "new_r_tok",
            "expires_in": 86400
        }
        mock_post.return_value = mock_resp

        res = self.publisher.refresh_access_token("client_k", "client_s")
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["token_expires_at"])

        updated = self.vault.get_credential(Platform.TIKTOK)
        self.assertEqual(updated["access_token"], "new_tok_789")

    @patch("core.publishing.tiktok.requests.put")
    @patch("core.publishing.tiktok.requests.post")
    def test_publish_chunked_success(self, mock_post, mock_put):
        video_file = os.path.join(self.temp_dir.name, "tiktok_corte.mp4")
        with open(video_file, "wb") as f:
            f.write(b"video chunk 1234567890")

        self.vault.save_credential(Platform.TIKTOK, {
            "access_token": "valid_tt_token",
            "open_id": "usr_99",
            "display_name": "tiktok_influencer"
        })

        # 1. Init response
        mock_init_resp = MagicMock()
        mock_init_resp.json.return_value = {
            "data": {
                "publish_id": "pub_tt_888",
                "upload_url": "https://upload.tiktok.com/chunk/888"
            },
            "error": {"code": "ok"}
        }

        # 2. Status response
        mock_status_resp = MagicMock()
        mock_status_resp.json.return_value = {
            "data": {
                "status": "PUBLISH_COMPLETE"
            }
        }

        mock_post.side_effect = [mock_init_resp, mock_status_resp]

        # Put chunk response
        mock_put_resp = MagicMock()
        mock_put_resp.status_code = 200
        mock_put.return_value = mock_put_resp

        caption = AdaptedCaption(
            platform=Platform.TIKTOK,
            title="Gancho viral TikTok",
            full_text="Gancho viral TikTok #foryou #viral"
        )

        res = self.publisher.publish(video_path=video_file, caption_data=caption)
        self.assertTrue(res.success)
        self.assertEqual(res.post_id, "pub_tt_888")
        self.assertIn("@tiktok_influencer", res.post_url)

    @patch("core.publishing.tiktok.requests.post")
    def test_publish_init_failure(self, mock_post):
        video_file = os.path.join(self.temp_dir.name, "tiktok_fail.mp4")
        with open(video_file, "wb") as f:
            f.write(b"data")

        self.vault.save_credential(Platform.TIKTOK, {
            "access_token": "invalid_tok"
        })

        mock_init_resp = MagicMock()
        mock_init_resp.json.return_value = {
            "error": {
                "code": "access_token_invalid",
                "message": "Token de acesso expirado ou inválido."
            }
        }
        mock_post.return_value = mock_init_resp

        res = self.publisher.publish(video_path=video_file, caption_data={"title": "Teste"})
        self.assertFalse(res.success)
        self.assertIn("access_token_invalid", res.error)


if __name__ == "__main__":
    unittest.main()
