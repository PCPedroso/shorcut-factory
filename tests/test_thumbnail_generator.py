import os
import unittest
import numpy as np
from PIL import Image
from core.thumbnail_generator import (
    format_frame_to_target,
    enhance_frame_clahe,
    create_cut_thumbnail,
    _calculate_image_sharpness
)


class TestThumbnailGenerator(unittest.TestCase):

    def setUp(self):
        self.tmp_thumb_path = "tests/temp_test_thumbnail.jpg"
        self.tmp_dir = "tests/temp_thumb_vars"
        os.makedirs(self.tmp_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.tmp_thumb_path):
            try:
                os.remove(self.tmp_thumb_path)
            except Exception:
                pass
        if os.path.exists(self.tmp_dir):
            try:
                import shutil
                shutil.rmtree(self.tmp_dir)
            except Exception:
                pass

    def test_calculate_image_sharpness(self):
        flat_img = np.zeros((100, 100, 3), dtype=np.uint8)
        sharp_flat = _calculate_image_sharpness(flat_img)
        self.assertEqual(sharp_flat, 0.0)

        noisy_img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        sharp_noisy = _calculate_image_sharpness(noisy_img)
        self.assertGreater(sharp_noisy, 0.0)

    def test_enhance_frame_clahe(self):
        test_img = np.ones((200, 200, 3), dtype=np.uint8) * 100
        enhanced = enhance_frame_clahe(test_img)
        self.assertEqual(enhanced.shape, (200, 200, 3))

    def test_format_frame_to_target_916_and_169(self):
        # Entrada 16:9 para 9:16
        img_16_9 = np.ones((1080, 1920, 3), dtype=np.uint8) * 128
        res_916 = format_frame_to_target(img_16_9, face_box=(800, 400, 200, 200), aspect_mode="9:16_smart_face")
        self.assertEqual(res_916.shape[0], 1920)
        self.assertEqual(res_916.shape[1], 1080)

        # Entrada 16:9 para 16:9
        res_169 = format_frame_to_target(img_16_9, aspect_mode="16:9")
        self.assertEqual(res_169.shape[0], 1080)
        self.assertEqual(res_169.shape[1], 1920)

    def test_create_cut_thumbnail_with_3_variations(self):
        test_frame = np.ones((1080, 1920, 3), dtype=np.uint8) * 100
        out_target = os.path.join(self.tmp_dir, "thumbnail.jpg")

        # Teste em 9:16
        res = create_cut_thumbnail(
            source_video_or_frame=test_frame,
            headline_text="NOVO RECORDE HISTÓRICO",
            output_path=out_target,
            preset="yellow_black",
            aspect_mode="9:16_smart_face"
        )
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_target))
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, "thumbnail_1.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, "thumbnail_2.jpg")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, "thumbnail_3.jpg")))
        self.assertEqual(len(res.get("variations", [])), 3)

        # Teste em 16:9
        out_target_169 = os.path.join(self.tmp_dir, "thumb_169", "thumbnail.jpg")
        res_169 = create_cut_thumbnail(
            source_video_or_frame=test_frame,
            headline_text="EPISÓDIO COMPLETO DO PODCAST",
            output_path=out_target_169,
            preset="red_white",
            aspect_mode="16:9"
        )
        self.assertIsNone(res_169.get("error"))
        self.assertTrue(os.path.exists(out_target_169))


if __name__ == '__main__':
    unittest.main()

