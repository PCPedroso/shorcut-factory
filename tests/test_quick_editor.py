import os
import unittest
import numpy as np
import cv2
from core.quick_editor import (
    get_video_duration,
    extract_frame_at_timestamp,
    trim_video,
    remove_snippet_and_merge
)


class TestQuickEditor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = "tests/temp_quick_editor"
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.sample_video = os.path.join(cls.test_dir, "sample_test.mp4")

        # Gera um vídeo sintético de 6 segundos (1280x720 @ 30fps) com áudio silencioso via OpenCV/FFmpeg
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(cls.sample_video, fourcc, 30.0, (640, 360))
        for i in range(180): # 6 segundos * 30 fps
            # Frame colorido mudando com o tempo
            color = int((i / 180.0) * 255)
            frame = np.full((360, 640, 3), color, dtype=np.uint8)
            cv2.putText(frame, f"Frame {i}", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            out.write(frame)
        out.release()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            try:
                import shutil
                shutil.rmtree(cls.test_dir)
            except Exception:
                pass

    def test_get_video_duration(self):
        dur = get_video_duration(self.sample_video)
        self.assertAlmostEqual(dur, 6.0, delta=0.5)

    def test_extract_frame_at_timestamp(self):
        frame = extract_frame_at_timestamp(self.sample_video, 2.5)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (360, 640, 3))

    def test_trim_video(self):
        out_trim = os.path.join(self.test_dir, "trimmed.mp4")
        res = trim_video(self.sample_video, start_s=1.0, end_s=4.0, output_path=out_trim)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_trim))
        dur = get_video_duration(out_trim)
        self.assertAlmostEqual(dur, 3.0, delta=0.5)

    def test_remove_snippet_and_merge(self):
        out_snip = os.path.join(self.test_dir, "snipped.mp4")
        # Remove do segundo 2.0 ao 4.0 de um vídeo de 6.0s -> resultado ~4.0s
        res = remove_snippet_and_merge(self.sample_video, remove_start_s=2.0, remove_end_s=4.0, output_path=out_snip)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_snip))
        dur = get_video_duration(out_snip)
        self.assertAlmostEqual(dur, 4.0, delta=0.8)


if __name__ == '__main__':
    unittest.main()
