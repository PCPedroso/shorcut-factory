import os
import unittest
import numpy as np
from PIL import Image
from core.thumbnail_generator import (
    format_frame_to_916,
    draw_headline_overlay_on_image,
    create_cut_thumbnail,
    _calculate_image_sharpness
)


class TestThumbnailGenerator(unittest.TestCase):

    def setUp(self):
        self.tmp_thumb_path = "tests/temp_test_thumbnail.jpg"

    def tearDown(self):
        if os.path.exists(self.tmp_thumb_path):
            try:
                os.remove(self.tmp_thumb_path)
            except Exception:
                pass

    def test_calculate_image_sharpness(self):
        # Frame uniforme (sem nitidez / bordas)
        flat_img = np.zeros((100, 100, 3), dtype=np.uint8)
        sharp_flat = _calculate_image_sharpness(flat_img)
        self.assertEqual(sharp_flat, 0.0)

        # Frame com gradiente / bordas
        noisy_img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        sharp_noisy = _calculate_image_sharpness(noisy_img)
        self.assertGreater(sharp_noisy, 0.0)

    def test_format_frame_to_916(self):
        # Entrada 16:9 (1920x1080)
        img_16_9 = np.ones((1080, 1920, 3), dtype=np.uint8) * 128
        res_916 = format_frame_to_916(img_16_9, face_box=(800, 400, 200, 200), aspect_mode="9:16_smart_face")

        self.assertEqual(res_916.shape[0], 1920)
        self.assertEqual(res_916.shape[1], 1080)
        self.assertEqual(res_916.shape[2], 3)

        # Entrada já 9:16
        img_vert = np.ones((1920, 1080, 3), dtype=np.uint8) * 200
        res_vert = format_frame_to_916(img_vert)
        self.assertEqual(res_vert.shape[:2], (1920, 1080))

    def test_draw_headline_overlay_on_image(self):
        base_img = Image.new("RGB", (1080, 1920), color=(50, 50, 50))
        headline = "O SEGREDO DO SUCESSO FINANCEIRO"
        out_img = draw_headline_overlay_on_image(
            base_img,
            headline_text=headline,
            preset="yellow_black"
        )
        self.assertEqual(out_img.size, (1080, 1920))
        self.assertEqual(out_img.mode, "RGB")

    def test_create_cut_thumbnail_from_frame(self):
        test_frame = np.ones((1080, 1920, 3), dtype=np.uint8) * 100
        res = create_cut_thumbnail(
            source_video_or_frame=test_frame,
            headline_text="NOVO RECORDE HISTÓRICO",
            output_path=self.tmp_thumb_path,
            preset="red_white"
        )
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(self.tmp_thumb_path))
        self.assertGreater(os.path.getsize(self.tmp_thumb_path), 500)


if __name__ == '__main__':
    unittest.main()
