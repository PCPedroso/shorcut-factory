import os
import unittest
import numpy as np
from core.overlay_manager import (
    resize_image_mode,
    compose_banner_box,
    calculate_overlay_placement,
    generate_overlay_preview,
    OVERLAY_PRESETS
)


class TestOverlayManager(unittest.TestCase):

    def setUp(self):
        # Cria imagem RGBA de teste 200x100 (vermelho semi-transparente)
        self.sample_rgba = np.zeros((100, 200, 4), dtype=np.uint8)
        self.sample_rgba[:, :, 0] = 255  # R
        self.sample_rgba[:, :, 3] = 200  # Alpha

        # Cria logo de teste 50x50 (verde opaco)
        self.sample_logo = np.zeros((50, 50, 4), dtype=np.uint8)
        self.sample_logo[:, :, 1] = 255  # G
        self.sample_logo[:, :, 3] = 255  # Alpha

    def test_resize_mode_fill(self):
        res = resize_image_mode(self.sample_rgba, target_w=300, target_h=150, mode="fill")
        self.assertEqual(res.shape, (150, 300, 4))

    def test_resize_mode_fit(self):
        res = resize_image_mode(self.sample_rgba, target_w=400, target_h=400, mode="fit")
        self.assertEqual(res.shape, (400, 400, 4))
        # Verifica que o centro tem conteúdo e as bordas superior/inferior são transparentes
        self.assertEqual(res[0, 200, 3], 0)  # borda topo transparente
        self.assertGreater(res[200, 200, 3], 0)  # centro preenchido

    def test_resize_mode_cover(self):
        res = resize_image_mode(self.sample_rgba, target_w=100, target_h=100, mode="cover")
        self.assertEqual(res.shape, (100, 100, 4))

    def test_compose_banner_box_with_embedded_logo(self):
        box = compose_banner_box(
            banner_img_path_or_array=self.sample_rgba,
            target_w=400,
            target_h=100,
            scale_mode="fill",
            logo_path_or_array=self.sample_logo,
            logo_pos="left",
            logo_scale_pct=0.8,
            opacity=1.0
        )
        self.assertEqual(box.shape, (100, 400, 4))
        # O canto esquerdo deve conter verde do logo
        self.assertGreater(box[50, 30, 1], 200)

    def test_calculate_overlay_placement_bottom(self):
        config = {
            "width_pct": 100,
            "height_px": 300,
            "pos_x": "center",
            "pos_y": "bottom",
            "offset_y": 0
        }
        x, y, w, h = calculate_overlay_placement(1920, 1080, config)
        self.assertEqual(w, 1920)
        self.assertEqual(h, 300)
        self.assertEqual(x, 0)
        self.assertEqual(y, 780)

    def test_calculate_overlay_placement_watermark_top_right(self):
        config = {
            "width_pct": 20,
            "height_px": 100,
            "pos_x": "right",
            "pos_y": "top",
            "offset_x": 20,
            "offset_y": 20
        }
        x, y, w, h = calculate_overlay_placement(1920, 1080, config)
        self.assertEqual(w, 384)
        self.assertEqual(h, 100)
        self.assertEqual(x, 1920 - 384 - 20)
        self.assertEqual(y, 20)

    def test_generate_overlay_preview(self):
        base_frame = np.full((1080, 1920, 3), 50, dtype=np.uint8)
        preview = generate_overlay_preview(
            banner_path_or_array=self.sample_rgba,
            config=OVERLAY_PRESETS["gc_bottom_169"],
            base_frame=base_frame
        )
        self.assertEqual(preview.shape, (1080, 1920, 3))
        # O rodapé deve ter sido alterado pela sobreposição
        self.assertNotEqual(preview[900, 960, 0], 50)


if __name__ == '__main__':
    unittest.main()
