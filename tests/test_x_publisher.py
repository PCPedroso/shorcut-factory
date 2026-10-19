"""
Testes unitários para o módulo XPublisher (X / Twitter API v1.1 Media + v2 Tweets).
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.publishing.base import Platform, AdaptedCaption
from core.publishing.credentials import CredentialVault
from core.publishing.x_publisher import XPublisher


class TestXPublisher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "vault.enc")
        self.vault = CredentialVault(vault_path=self.vault_path)
        self.publisher = XPublisher(vault=self.vault)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auth_status_unconfigured(self):
        status = self.publisher.get_auth_status()
        self.assertFalse(status.is_authenticated)
        self.assertIn("Nenhuma credencial", status.message)

    def test_auth_status_oauth1_configured(self):
        self.vault.save_credential(Platform.X, {
            "api_key": "k",
            "api_secret": "s",
            "access_token": "at",
            "access_token_secret": "ats",
            "screen_name": "viral_x"
        })
        status = self.publisher.get_auth_status()
        self.assertTrue(status.is_authenticated)
        self.assertEqual(status.account_name, "@viral_x")

    def test_auth_status_bearer_configured(self):
        self.vault.save_credential(Platform.X, {
            "bearer_token": "AAAAAAAA...",
            "screen_name": "bot_cortes"
        })
        status = self.publisher.get_auth_status()
        self.assertTrue(status.is_authenticated)
        self.assertEqual(status.account_name, "@bot_cortes")

    @patch("core.publishing.x_publisher.requests.post")
    def test_publish_video_and_tweet_success(self, mock_post):
        video_file = os.path.join(self.temp_dir.name, "tweet_vid.mp4")
        with open(video_file, "wb") as f:
            f.write(b"x video bytes content")

        self.vault.save_credential(Platform.X, {
            "api_key": "k",
            "api_secret": "s",
            "access_token": "at",
            "access_token_secret": "ats",
            "screen_name": "viral_x"
        })

        # Mock das 4 chamadas POST do upload e tweet:
        # 1. INIT
        mock_init = MagicMock()
        mock_init.json.return_value = {"media_id_string": "1789000111222"}

        # 2. APPEND
        mock_append = MagicMock()
        mock_append.status_code = 204

        # 3. FINALIZE (sem processamento assíncrono pendente)
        mock_finalize = MagicMock()
        mock_finalize.json.return_value = {"media_id_string": "1789000111222"}

        # 4. POST /2/tweets
        mock_tweet = MagicMock()
        mock_tweet.status_code = 201
        mock_tweet.json.return_value = {
            "data": {
                "id": "1800999888777",
                "text": "Gancho viral no X"
            }
        }

        mock_post.side_effect = [mock_init, mock_append, mock_finalize, mock_tweet]

        caption = AdaptedCaption(
            platform=Platform.X,
            title="Gancho viral no X",
            full_text="Gancho viral no X #cortes"
        )

        res = self.publisher.publish(video_path=video_file, caption_data=caption)
        self.assertTrue(res.success)
        self.assertEqual(res.post_id, "1800999888777")
        self.assertEqual(res.post_url, "https://x.com/i/status/1800999888777")

    @patch("core.publishing.x_publisher.requests.post")
    def test_publish_init_failure(self, mock_post):
        video_file = os.path.join(self.temp_dir.name, "tweet_vid_err.mp4")
        with open(video_file, "wb") as f:
            f.write(b"video bytes")

        self.vault.save_credential(Platform.X, {
            "bearer_token": "bad_token"
        })

        mock_init = MagicMock()
        mock_init.json.return_value = {"error": "Could not authenticate you"}
        mock_post.return_value = mock_init

        res = self.publisher.publish(video_path=video_file, caption_data={"text": "Fail test"})
        self.assertFalse(res.success)
        self.assertIn("Could not authenticate you", res.error)


if __name__ == "__main__":
    unittest.main()
