import unittest
from unittest.mock import patch, MagicMock
from core.integrations import send_to_webhook


class TestIntegrations(unittest.TestCase):

    @patch("requests.post")
    def test_send_to_webhook_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_post.return_value = mock_response

        res = send_to_webhook(
            webhook_url="https://example.com/webhook",
            payload={"event": "cut_ready", "title": "Teste"}
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("status_code"), 200)

    def test_send_to_webhook_invalid_url(self):
        res = send_to_webhook(
            webhook_url="invalid_url",
            payload={"test": 123}
        )
        self.assertFalse(res.get("success"))
        self.assertIn("URL de Webhook inválida", res.get("error"))

    def test_get_video_id_multi_platform(self):
        from core.extractor import get_video_id
        self.assertEqual(get_video_id("https://www.youtube.com/watch?v=aa-dLeL-Rf4"), "aa-dLeL-Rf4")
        self.assertEqual(get_video_id("https://youtu.be/aa-dLeL-Rf4"), "aa-dLeL-Rf4")
        self.assertEqual(get_video_id("https://www.youtube.com/shorts/12345678901"), "12345678901")
        self.assertEqual(get_video_id("https://www.instagram.com/reel/C8P0lMtp6Y4/"), "ig_C8P0lMtp6Y4")
        self.assertEqual(get_video_id("https://instagram.com/p/DFxyz123/"), "ig_DFxyz123")
        self.assertEqual(get_video_id("https://www.tiktok.com/@user/video/7381234567890"), "tt_7381234567890")
        self.assertEqual(get_video_id("https://x.com/user/status/180234567890"), "tw_180234567890")
        self.assertTrue(get_video_id("https://vimeo.com/12345678").startswith("web_"))


if __name__ == '__main__':
    unittest.main()
