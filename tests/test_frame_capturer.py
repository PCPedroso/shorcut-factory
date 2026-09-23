import os
import shutil
import tempfile
import unittest
import numpy as np
import cv2
from PIL import Image

from core.frame_capturer import (
    parse_time_str_to_seconds,
    format_seconds_to_time_str,
    extract_frame_at_timestamp,
    save_captured_frame_as_thumbnail,
    save_base64_data_as_image
)


class TestFrameCapturer(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_frame_cap_")

    def tearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_parse_time_str_to_seconds(self):
        self.assertEqual(parse_time_str_to_seconds("00:01:23.45"), 83.45)
        self.assertEqual(parse_time_str_to_seconds("01:23"), 83.0)
        self.assertEqual(parse_time_str_to_seconds("14.5"), 14.5)
        self.assertEqual(parse_time_str_to_seconds(10), 10.0)
        self.assertEqual(parse_time_str_to_seconds(""), 0.0)
        self.assertEqual(parse_time_str_to_seconds(None), 0.0)
        self.assertEqual(parse_time_str_to_seconds("00:00:05,50"), 5.50)

    def test_format_seconds_to_time_str(self):
        self.assertEqual(format_seconds_to_time_str(83.45), "00:01:23.45")
        self.assertEqual(format_seconds_to_time_str(83.45, include_ms=False), "00:01:23")
        self.assertEqual(format_seconds_to_time_str(0), "00:00:00.00")

    def test_extract_frame_at_timestamp(self):
        # Cria vídeo sintético de 2 segundos com 1080x1920
        v_path = os.path.join(self.tmp_dir, "dummy_video.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(v_path, fourcc, 10.0, (720, 1280))
        for i in range(20):
            # Frame colorido variável
            frame = np.full((1280, 720, 3), (i * 10, 100, 200), dtype=np.uint8)
            out.write(frame)
        out.release()

        res = extract_frame_at_timestamp(v_path, 1.0)
        self.assertIsNone(res.get("error"))
        self.assertIsNotNone(res.get("frame"))
        self.assertEqual(res["resolution"], (720, 1280))
        self.assertAlmostEqual(res["timestamp_s"], 1.0, places=1)

    def test_save_captured_frame_as_thumbnail_direct(self):
        dummy_frame = np.full((1920, 1080, 3), (255, 128, 0), dtype=np.uint8)
        out_thumb = os.path.join(self.tmp_dir, "thumbnail.jpg")

        res = save_captured_frame_as_thumbnail(
            source_video_or_frame=dummy_frame,
            output_thumbnail_path=out_thumb,
            generate_ai_variations=False
        )

        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(out_thumb))
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, "thumbnail_1.jpg")))
        self.assertEqual(len(res["variations"]), 1)

    def test_save_base64_data_as_image(self):
        # Gera imagem vermelha 100x100 e converte em base64
        import base64
        import io
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

        out_img = os.path.join(self.tmp_dir, "decoded.jpg")
        res = save_base64_data_as_image(b64, out_img)

        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(out_img))
        read_img = Image.open(out_img)
        self.assertEqual(read_img.size, (100, 100))


if __name__ == '__main__':
    unittest.main()
