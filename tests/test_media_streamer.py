import os
import unittest
import urllib.request
from core.media_streamer import (
    start_media_streamer_if_needed,
    get_media_stream_url,
    is_large_media,
    LARGE_MEDIA_THRESHOLD_BYTES
)


class TestMediaStreamer(unittest.TestCase):
    def test_start_media_streamer_returns_valid_port(self):
        port = start_media_streamer_if_needed()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)

    def test_get_media_stream_url_format(self):
        url = get_media_stream_url("tests/test_dummy_video.mp4")
        self.assertTrue(url.startswith("http://127.0.0.1:"))
        self.assertIn("/stream?file=", url)

    def test_is_large_media_detection(self):
        self.assertFalse(is_large_media("arquivo_inexistente_123.mp4"))

    def test_range_request_partial_content(self):
        # Cria um arquivo de teste temporário pequeno
        tmp_file = "temp_stream_test.txt"
        test_content = b"0123456789abcdefghijklmnopqrstuvwxyz" * 100
        with open(tmp_file, "wb") as f:
            f.write(test_content)

        try:
            url = get_media_stream_url(tmp_file)
            req = urllib.request.Request(url, headers={"Range": "bytes=10-25"})
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 206)
                self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")
                self.assertIn("bytes 10-25/", resp.headers.get("Content-Range", ""))
                data = resp.read()
                self.assertEqual(data, test_content[10:26])
        finally:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)


if __name__ == "__main__":
    unittest.main()
