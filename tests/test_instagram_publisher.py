"""
Testes unitários para o módulo InstagramPublisher (Instagram Reels via Meta Graph API).
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.publishing.base import Platform, AdaptedCaption
from core.publishing.credentials import CredentialVault
from core.publishing.instagram import InstagramPublisher


class TestInstagramPublisher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "vault.enc")
        self.vault = CredentialVault(vault_path=self.vault_path)
        self.publisher = InstagramPublisher(vault=self.vault)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auth_status_unconfigured(self):
        status = self.publisher.get_auth_status()
        self.assertFalse(status.is_authenticated)
        self.assertIn("Nenhuma credencial", status.message)

    def test_auth_status_configured(self):
        self.vault.save_credential(Platform.INSTAGRAM, {
            "access_token": "EAAG...",
            "ig_user_id": "17841400000000",
            "username": "canal_cortes"
        })
        status = self.publisher.get_auth_status()
        self.assertTrue(status.is_authenticated)
        self.assertIn("@canal_cortes", status.account_name)

    @patch("core.publishing.instagram.requests.get")
    def test_refresh_long_lived_token(self, mock_get):
        self.vault.save_credential(Platform.INSTAGRAM, {
            "access_token": "short_lived_tok",
            "ig_user_id": "17841400000000"
        })

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "access_token": "new_long_lived_token",
            "token_type": "bearer",
            "expires_in": 5184000
        }
        mock_get.return_value = mock_resp

        res = self.publisher.refresh_long_lived_token("app_id", "app_secret")
        self.assertTrue(res["success"])
        self.assertIsNotNone(res["token_expires_at"])

        # Verifica se o cofre foi atualizado com o novo token
        updated = self.vault.get_credential(Platform.INSTAGRAM)
        self.assertEqual(updated["access_token"], "new_long_lived_token")

    @patch("core.publishing.instagram.requests.post")
    @patch("core.publishing.instagram.requests.get")
    def test_publish_reels_success(self, mock_get, mock_post):
        video_file = os.path.join(self.temp_dir.name, "reels_test.mp4")
        with open(video_file, "wb") as f:
            f.write(b"video mp4 bytes")

        self.vault.save_credential(Platform.INSTAGRAM, {
            "access_token": "EAAG_TEST",
            "ig_user_id": "178414012345"
        })

        # Mock das chamadas POST:
        # 1. Criação do container
        mock_init_resp = MagicMock()
        mock_init_resp.json.return_value = {"id": "container_111", "uri": "https://rupload.facebook.com/ig/111"}

        # 2. Upload binário
        mock_upload_resp = MagicMock()
        mock_upload_resp.ok = True
        mock_upload_resp.json.return_value = {"success": True}

        # 4. Media publish
        mock_publish_resp = MagicMock()
        mock_publish_resp.json.return_value = {"id": "ig_media_888"}

        mock_post.side_effect = [mock_init_resp, mock_upload_resp, mock_publish_resp]

        # Mock das chamadas GET:
        # 3. Status do container
        mock_status_resp = MagicMock()
        mock_status_resp.json.return_value = {"status_code": "FINISHED", "id": "container_111"}

        # 5. Permalink do Reels
        mock_info_resp = MagicMock()
        mock_info_resp.json.return_value = {"permalink": "https://www.instagram.com/reel/Cx987654321/"}

        mock_get.side_effect = [mock_status_resp, mock_info_resp]

        caption = AdaptedCaption(
            platform=Platform.INSTAGRAM,
            title="Gancho Incrível",
            description="Legenda para reels",
            hashtags=["#cortes", "#viral"],
            full_text="Gancho Incrível\n\nLegenda para reels\n\n#cortes #viral"
        )

        res = self.publisher.publish(
            video_path=video_file,
            caption_data=caption
        )

        self.assertTrue(res.success)
        self.assertEqual(res.post_id, "ig_media_888")
        self.assertEqual(res.post_url, "https://www.instagram.com/reel/Cx987654321/")
        self.assertEqual(res.platform, Platform.INSTAGRAM)

    @patch("core.publishing.instagram.requests.post")
    def test_publish_init_failure(self, mock_post):
        video_file = os.path.join(self.temp_dir.name, "reels_fail.mp4")
        with open(video_file, "wb") as f:
            f.write(b"data")

        self.vault.save_credential(Platform.INSTAGRAM, {
            "access_token": "INVALID_TOKEN",
            "ig_user_id": "178414012345"
        })

        mock_init_resp = MagicMock()
        mock_init_resp.json.return_value = {
            "error": {"message": "Invalid OAuth access token.", "code": 190}
        }
        mock_post.return_value = mock_init_resp

        res = self.publisher.publish(video_file, {"caption": "Test"})
        self.assertFalse(res.success)
        self.assertIn("Invalid OAuth", res.error)


if __name__ == "__main__":
    unittest.main()
