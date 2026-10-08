import os
import unittest
import numpy as np
from PIL import Image

from core.social_overlay import (
    load_social_icon,
    get_active_social_items,
    render_social_overlay_image,
    render_social_overlay_on_frame,
    apply_social_overlay_to_video,
    DEFAULT_SOCIAL_CONFIG
)


class TestSocialOverlay(unittest.TestCase):

    def test_load_social_icon_scaling_and_aspect(self):
        # Ícone do YouTube deve ter a altura requisitada
        icon_yt = load_social_icon("youtube", target_height=36, monochrome=False)
        self.assertIsInstance(icon_yt, Image.Image)
        self.assertEqual(icon_yt.mode, "RGBA")
        self.assertEqual(icon_yt.height, 36)
        self.assertGreater(icon_yt.width, 10)

        # Ícone do Instagram
        icon_ig = load_social_icon("instagram", target_height=42, monochrome=False)
        self.assertEqual(icon_ig.height, 42)

        # Ícone do X
        icon_x = load_social_icon("x", target_height=30, monochrome=False)
        self.assertEqual(icon_x.height, 30)

    def test_load_social_icon_monochrome(self):
        icon_mono = load_social_icon("youtube", target_height=32, monochrome=True)
        self.assertEqual(icon_mono.mode, "RGBA")
        # Modo monocromático converte canais RGB para branco (255, 255, 255)
        arr = np.array(icon_mono)
        visible_mask = arr[:, :, 3] > 100
        if np.any(visible_mask):
            self.assertTrue(np.all(arr[visible_mask, 0] == 255))
            self.assertTrue(np.all(arr[visible_mask, 1] == 255))
            self.assertTrue(np.all(arr[visible_mask, 2] == 255))

    def test_load_fallback_icon(self):
        # Rede desconhecida deve renderizar fallback procedimental sem crashar
        fallback = load_social_icon("unknown_network_xyz", target_height=28)
        self.assertIsInstance(fallback, Image.Image)
        self.assertEqual(fallback.height, 28)

    def test_get_active_social_items(self):
        cfg = {
            "enabled": True,
            "networks": {
                "youtube": {"enabled": True, "handle": "@CanalOficial"},
                "instagram": {"enabled": False, "handle": "@Insta"},
                "x": {"enabled": True, "handle": "@TwitterHandle"}
            }
        }
        items = get_active_social_items(cfg)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["key"], "youtube")
        self.assertEqual(items[0]["handle"], "@CanalOficial")
        self.assertEqual(items[1]["key"], "x")
        self.assertEqual(items[1]["handle"], "@TwitterHandle")

        # Se master enabled for False, lista deve ser vazia
        cfg_disabled = dict(cfg)
        cfg_disabled["enabled"] = False
        self.assertEqual(get_active_social_items(cfg_disabled), [])

    def test_render_social_overlay_image(self):
        cfg = {
            "enabled": True,
            "position": "bottom",
            "offset_y": 20,
            "font_size": 34,
            "style": "pill_glass",
            "icon_style": "official",
            "text_color": "#FFFFFF",
            "networks": {
                "youtube": {"enabled": True, "handle": "@meucanal"},
                "instagram": {"enabled": True, "handle": "@meuinsta"}
            }
        }
        img = render_social_overlay_image(1080, 1920, cfg)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (1080, 1920))
        self.assertEqual(img.mode, "RGBA")

        # Deve haver pixels visíveis (alpha > 0)
        arr = np.array(img)
        self.assertGreater(np.sum(arr[:, :, 3] > 0), 1000)

    def test_render_social_overlay_on_frame(self):
        frame = np.full((1920, 1080, 3), 50, dtype=np.uint8)
        cfg = {
            "enabled": True,
            "position": "bottom",
            "offset_y": 0,
            "font_size": 30,
            "style": "pill_individual",
            "icon_style": "official",
            "text_color": "#FFFFFF",
            "networks": {
                "youtube": {"enabled": True, "handle": "@teste"}
            }
        }
        res_frame = render_social_overlay_on_frame(frame, cfg)
        self.assertEqual(res_frame.shape, (1920, 1080, 3))
        # O frame com overlay deve ter diferenças em relação ao frame original
        self.assertFalse(np.array_equal(frame, res_frame))

        # Se desabilitado, deve retornar exatamente o mesmo array
        cfg_off = {"enabled": False}
        res_frame_off = render_social_overlay_on_frame(frame, cfg_off)
        np.testing.assert_array_equal(frame, res_frame_off)

    def test_apply_social_overlay_to_video_disabled(self):
        # Quando desabilitado, deve retornar o próprio path sem executar ffmpeg
        res = apply_social_overlay_to_video("fake_path.mp4", "out.mp4", {"enabled": False})
        self.assertEqual(res["path"], "fake_path.mp4")
        self.assertIsNone(res["error"])

    def test_apply_social_overlay_to_video_execution(self):
        import cv2
        tmp_in = "tests/temp_social_in.mp4"
        tmp_out = "tests/temp_social_out.mp4"
        try:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(tmp_in, fourcc, 24, (1080, 1920))
            for _ in range(24):
                f = np.full((1920, 1080, 3), 40, dtype=np.uint8)
                out.write(f)
            out.release()

            cfg = {
                "enabled": True,
                "position": "bottom",
                "offset_y": 10,
                "font_size": 32,
                "style": "pill_glass",
                "icon_style": "official",
                "text_color": "#FFFFFF",
                "networks": {
                    "youtube": {"enabled": True, "handle": "@CanalTeste"},
                    "instagram": {"enabled": True, "handle": "@InstaTeste"}
                }
            }
            res = apply_social_overlay_to_video(tmp_in, tmp_out, cfg)
            self.assertIsNone(res.get("error"))
            self.assertTrue(os.path.exists(tmp_out))
            self.assertGreater(os.path.getsize(tmp_out), 1000)
        finally:
            if os.path.exists(tmp_in):
                try: os.remove(tmp_in)
                except Exception: pass
            if os.path.exists(tmp_out):
                try: os.remove(tmp_out)
                except Exception: pass


if __name__ == '__main__':
    unittest.main()

