import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from core.publishing.base import Platform, AdaptedCaption
from core.publishing.youtube import YouTubePublisher
from core.publishing.credentials import CredentialVault


class TestYouTubePublisher(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "vault.enc")
        self.vault = CredentialVault(vault_path=self.vault_path)
        self.publisher = YouTubePublisher(vault=self.vault)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_auth_status_unconfigured(self):
        status = self.publisher.get_auth_status()
        self.assertFalse(status.is_authenticated)
        self.assertIn("Nenhuma credencial", status.message)

    @patch("core.publishing.youtube.build")
    def test_publish_chunked_success(self, mock_build):
        # Cria arquivo temporário de vídeo
        video_file = os.path.join(self.temp_dir.name, "corte.mp4")
        with open(video_file, "wb") as f:
            f.write(b"fake video content")

        import datetime
        future_expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Mock de credenciais no vault
        self.vault.save_credential(Platform.YOUTUBE, {
            "token": "valid_token",
            "refresh_token": "valid_refresh",
            "client_id": "test_id",
            "client_secret": "test_secret",
            "expiry": future_expiry
        })

        # Mock do serviço do YouTube
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_xyz123"})
        mock_youtube.videos().insert.return_value = mock_insert

        res = self.publisher.publish(
            video_path=video_file,
            caption_data=AdaptedCaption(
                platform=Platform.YOUTUBE,
                title="Gancho Viral #Shorts",
                description="Descrição completa",
                tags_seo=["viral", "cortes"]
            ),
            options={"privacy_status": "unlisted"}
        )

        self.assertTrue(res.success)
        self.assertEqual(res.post_id, "vid_xyz123")
        self.assertEqual(res.post_url, "https://youtube.com/shorts/vid_xyz123")
        self.assertIsNone(res.error)

    @patch("core.publishing.youtube.build")
    def test_publish_scheduled_at(self, mock_build):
        import datetime
        future_expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        video_file = os.path.join(self.temp_dir.name, "corte_sched.mp4")
        with open(video_file, "wb") as f:
            f.write(b"fake video")

        self.vault.save_credential(Platform.YOUTUBE, {
            "token": "tok", "refresh_token": "ref", "client_id": "c", "client_secret": "s", "expiry": future_expiry
        })

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_sched_456"})
        mock_youtube.videos().insert.return_value = mock_insert

        target_time = "2026-10-25T18:00:00Z"
        res = self.publisher.publish(
            video_path=video_file,
            caption_data={"title": "Agendado #Shorts", "description": "Desc"},
            options={"scheduled_at": target_time}
        )

        self.assertTrue(res.success)
        self.assertEqual(res.post_id, "vid_sched_456")

        # Verifica se insert foi chamado com privacyStatus='private' e publishAt
        call_kwargs = mock_youtube.videos().insert.call_args[1]
        body = call_kwargs["body"]
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(body["status"]["publishAt"], target_time)


if __name__ == "__main__":
    unittest.main()
