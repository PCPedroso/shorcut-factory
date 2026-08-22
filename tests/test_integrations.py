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


if __name__ == '__main__':
    unittest.main()
