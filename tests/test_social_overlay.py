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

        # Ícone do TikTok
        icon_tk = load_social_icon("tiktok", target_height=38, monochrome=False)
        self.assertEqual(icon_tk.height, 38)
        self.assertGreater(icon_tk.width, 10)

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

    def test_tiktok_fallback_drawing(self):
        from core.social_overlay import _draw_fallback_icon
        fb = _draw_fallback_icon("tiktok", 40)
        self.assertIsInstance(fb, Image.Image)
        self.assertEqual(fb.size, (40, 40))
        self.assertEqual(fb.mode, "RGBA")

    def test_get_active_social_items(self):
        cfg = {
            "enabled": True,
            "networks": {
                "youtube": {"enabled": True, "handle": "@CanalOficial"},
                "instagram": {"enabled": False, "handle": "@Insta"},
                "tiktok": {"enabled": True, "handle": "@TikTokCortes"},
                "x": {"enabled": True, "handle": "@TwitterHandle"}
            }
        }
        items = get_active_social_items(cfg)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["key"], "youtube")
        self.assertEqual(items[0]["handle"], "@CanalOficial")
        self.assertEqual(items[1]["key"], "tiktok")
        self.assertEqual(items[1]["handle"], "@TikTokCortes")
        self.assertEqual(items[2]["key"], "x")
        self.assertEqual(items[2]["handle"], "@TwitterHandle")

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

    def test_render_social_overlay_auto_scaling(self):
        # Muito texto com fonte grande deve auto-ajustar para não ultrapassar a tela
        cfg = {
            "enabled": True,
            "position": "bottom",
            "offset_y": 0,
            "font_size": 48,
            "style": "pill_glass",
            "icon_style": "official",
            "text_color": "#FFFFFF",
            "networks": {
                "youtube": {"enabled": True, "handle": "@CanalMuitoLongoComNomeExtensoDemais"},
                "x": {"enabled": True, "handle": "@OutroCanalMuitoLongoTambem"}
            }
        }
        img = render_social_overlay_image(1080, 1920, cfg)
        self.assertIsInstance(img, Image.Image)
        arr = np.array(img)
        visible_xs = np.where(arr[:, :, 3] > 0)[1]
        self.assertGreater(len(visible_xs), 0)
        # O início e fim devem respeitar as bordas da tela
        self.assertGreaterEqual(visible_xs.min(), 5)
        self.assertLessEqual(visible_xs.max(), 1075)

    def test_get_formatted_preview_frame(self):
        from core.social_overlay import get_formatted_preview_frame
        # Se vídeo não existir, retorna canvas padrão neutro
        frame = get_formatted_preview_frame("non_existent.mp4", "00:00:01", aspect_mode="9:16_blur")
        self.assertEqual(frame.shape, (1920, 1080, 3))


    def test_render_social_overlay_extended_margin_range(self):
        # Garante que margens extremas entre -450 e 450 px renderizam sem erro
        for off in [-450, -300, 300, 450]:
            for pos in ["bottom", "top"]:
                cfg = {
                    "enabled": True,
                    "position": pos,
                    "offset_y": off,
                    "font_size": 32,
                    "style": "pill_glass",
                    "icon_style": "official",
                    "text_color": "#FFFFFF",
                    "networks": {
                        "youtube": {"enabled": True, "handle": "@canal"}
                    }
                }
                img = render_social_overlay_image(1080, 1920, cfg)
                self.assertIsInstance(img, Image.Image)
                arr = np.array(img)
                self.assertGreater(np.sum(arr[:, :, 3] > 0), 0)


    def test_social_preview_scale_config(self):
        from core.config_manager import DEFAULT_SETTINGS
        self.assertIn("social_preview_scale", DEFAULT_SETTINGS)
        self.assertEqual(DEFAULT_SETTINGS["social_preview_scale"], 50)

    def test_render_social_overlay_small_font(self):
        cfg = {
            "enabled": True,
            "position": "bottom",
            "offset_y": 0,
            "font_size": 14,
            "style": "pill_glass",
            "icon_style": "official",
            "text_color": "#FFFFFF",
            "networks": {
                "youtube": {"enabled": True, "handle": "@mini_yt"},
                "tiktok": {"enabled": True, "handle": "@mini_tk"}
            }
        }
        img = render_social_overlay_image(1080, 1920, cfg)
        self.assertIsInstance(img, Image.Image)
        arr = np.array(img)
        self.assertGreater(np.sum(arr[:, :, 3] > 0), 100)


    def test_social_profiles_lifecycle(self):
        import tempfile
        from core.social_overlay import (
            load_social_profiles, save_social_profile, delete_social_profile,
            rename_social_profile, set_active_social_profile_name, get_active_social_profile
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            tmp_path = tf.name

        try:
            # 1. Inicialização limpa
            data = load_social_profiles(tmp_path)
            self.assertIn("active_profile", data)
            self.assertIn("profiles", data)
            self.assertGreaterEqual(len(data["profiles"]), 1)
            initial_name = data["active_profile"]

            # 2. Cadastro de um novo perfil para outro canal (ex: Canal Finanças)
            financas_cfg = {
                "social_overlay_enabled": True,
                "social_overlay_position": "Superior (Top)",
                "social_overlay_offset_y": 100,
                "social_overlay_font_size": 36,
                "social_preview_scale": 60,
                "social_overlay_style": "Pílula Glassmorphism (Recomendado)",
                "social_overlay_icon_style": "Cores Oficiais da Marca",
                "social_youtube_enabled": True,
                "social_youtube_handle": "@FinancasExpert",
                "social_instagram_enabled": True,
                "social_instagram_handle": "@financas.expert",
                "social_tiktok_enabled": True,
                "social_tiktok_handle": "@financas_tiktok",
                "social_x_enabled": False,
                "social_x_handle": ""
            }
            ok = save_social_profile("Canal Finanças", financas_cfg, set_as_active=True, filepath=tmp_path)
            self.assertTrue(ok)

            act_name, act_cfg = get_active_social_profile(tmp_path)
            self.assertEqual(act_name, "Canal Finanças")
            self.assertEqual(act_cfg["social_youtube_handle"], "@FinancasExpert")
            self.assertEqual(act_cfg["social_instagram_handle"], "@financas.expert")

            # 3. Alternar entre perfis
            set_active_social_profile_name(initial_name, filepath=tmp_path)
            act_name2, act_cfg2 = get_active_social_profile(tmp_path)
            self.assertEqual(act_name2, initial_name)

            # 4. Renomear perfil
            ren_ok = rename_social_profile("Canal Finanças", "Finanças & Investimentos", filepath=tmp_path)
            self.assertTrue(ren_ok)
            data_after_ren = load_social_profiles(tmp_path)
            self.assertIn("Finanças & Investimentos", data_after_ren["profiles"])
            self.assertNotIn("Canal Finanças", data_after_ren["profiles"])

            # 5. Excluir perfil
            del_ok = delete_social_profile("Finanças & Investimentos", filepath=tmp_path)
            self.assertTrue(del_ok)
            data_after_del = load_social_profiles(tmp_path)
            self.assertNotIn("Finanças & Investimentos", data_after_del["profiles"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == '__main__':
    unittest.main()


