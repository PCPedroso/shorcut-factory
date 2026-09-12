import os
import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from PIL import Image

from core.quick_editor import (
    create_hook_badge_image,
    apply_hook_style_to_frame,
    overlay_badge_on_frame,
    add_viral_hook_to_video,
    record_quick_edit,
    load_edit_history,
    HOOK_STYLES,
    HOOK_BADGE_PRESETS,
    HOOK_TRANSITIONS
)


class TestViralHook(unittest.TestCase):
    """
    Testes unitários para o recurso de Gancho Viral (Hook / Teaser / Cold Open).
    """

    def setUp(self):
        self.test_dir = os.path.join("tests", "temp_viral_hook")
        os.makedirs(self.test_dir, exist_ok=True)
        self.dummy_video = os.path.join(self.test_dir, "dummy_cut.mp4")
        with open(self.dummy_video, "wb") as f:
            f.write(b"\x00" * 2048)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_hook_constants_definition(self):
        self.assertIn("noir", HOOK_STYLES)
        self.assertIn("vignette_zoom", HOOK_STYLES)
        self.assertIn("retro", HOOK_STYLES)
        self.assertIn("flash_forward", HOOK_STYLES)
        self.assertIn("clean", HOOK_STYLES)
        self.assertGreaterEqual(len(HOOK_BADGE_PRESETS), 3)
        self.assertIn("flash_white", HOOK_TRANSITIONS)
        self.assertIn("dip_black", HOOK_TRANSITIONS)
        self.assertIn("jump_cut", HOOK_TRANSITIONS)

    def test_create_hook_badge_image(self):
        out_badge = os.path.join(self.test_dir, "test_badge.png")
        res_path = create_hook_badge_image(
            badge_text="🔥 TESTE GANCHO VIRAL",
            badge_style="red_alert",
            video_width=1080,
            video_height=1920,
            output_png_path=out_badge
        )
        self.assertIsNotNone(res_path)
        self.assertTrue(os.path.exists(res_path))
        self.assertTrue(os.path.getsize(res_path) > 0)

        # Valida que é uma imagem RGBA válida
        img = Image.open(res_path)
        self.assertEqual(img.mode, "RGBA")
        self.assertGreater(img.width, 100)
        self.assertGreater(img.height, 20)

    def test_apply_hook_style_to_frame(self):
        dummy_frame = np.full((120, 120, 3), 150, dtype=np.uint8)

        # 1. Noir (Grayscale RGB)
        f_noir = apply_hook_style_to_frame(dummy_frame, hook_style="noir")
        self.assertEqual(f_noir.shape, (120, 120, 3))
        self.assertEqual(f_noir[60, 60, 0], f_noir[60, 60, 1])
        self.assertEqual(f_noir[60, 60, 1], f_noir[60, 60, 2])

        # 2. Retrô / Sépia
        f_retro = apply_hook_style_to_frame(dummy_frame, hook_style="retro")
        self.assertEqual(f_retro.shape, (120, 120, 3))

        # 3. Flash-Forward
        f_ff = apply_hook_style_to_frame(dummy_frame, hook_style="flash_forward")
        self.assertEqual(f_ff.shape, (120, 120, 3))

        # 4. Vinheta / Zoom
        f_vig = apply_hook_style_to_frame(dummy_frame, hook_style="vignette_zoom")
        self.assertEqual(f_vig.shape, (120, 120, 3))

        # 5. Clean (Original)
        f_clean = apply_hook_style_to_frame(dummy_frame, hook_style="clean")
        np.testing.assert_array_equal(dummy_frame, f_clean)

    def test_add_viral_hook_validation_errors(self):
        # 1. Vídeo inexistente
        res_none = add_viral_hook_to_video("video_inexistente_999.mp4", 1.0, 4.0)
        self.assertIn("não encontrado", res_none.get("error", ""))

        # 2. Start >= End
        with patch("core.quick_editor.get_video_duration", return_value=30.0):
            res_inv_time = add_viral_hook_to_video(self.dummy_video, 5.0, 3.0)
            self.assertIn("deve ser menor", res_inv_time.get("error", ""))

        # 3. Duração < 0.5s
        with patch("core.quick_editor.get_video_duration", return_value=30.0):
            res_short = add_viral_hook_to_video(self.dummy_video, 5.0, 5.2)
            self.assertIn("pelo menos 0.5 segundos", res_short.get("error", ""))

    @patch("subprocess.run")
    @patch("core.quick_editor.get_video_duration")
    @patch("core.quick_editor.has_audio_stream")
    def test_add_viral_hook_teaser_mode_mocked(self, mock_audio, mock_dur, mock_run):
        mock_audio.return_value = True
        mock_dur.side_effect = [30.0, 34.0]  # Orig: 30s -> Teaser de 4s resulta em 34s
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        out_path = os.path.join(self.test_dir, "output_hook.mp4")

        # Simula criação do arquivo temporário gerado pelo ffmpeg
        def fake_ffmpeg(cmd, **kwargs):
            tmp_target = cmd[-1]
            with open(tmp_target, "wb") as f:
                f.write(b"\x00" * 4096)
            return MagicMock(returncode=0, stderr="")

        mock_run.side_effect = fake_ffmpeg

        res = add_viral_hook_to_video(
            video_path=self.dummy_video,
            hook_start_s=10.0,
            hook_end_s=14.0,
            hook_style="noir",
            badge_text="🔥 ASSISTA ATÉ O FINAL",
            transition_type="flash_white",
            hook_mode="teaser",
            output_path=out_path
        )

        self.assertIsNone(res.get("error"))
        self.assertEqual(res.get("new_duration"), 34.0)
        self.assertEqual(res.get("hook_duration"), 4.0)
        self.assertEqual(res.get("style"), "noir")
        self.assertEqual(res.get("mode"), "teaser")
        self.assertEqual(res.get("badge_y_pct"), 12.0)
        self.assertTrue(os.path.exists(out_path))

        first_call_cmd = mock_run.call_args_list[0][0][0]
        self.assertIn("-ss", first_call_cmd)
        self.assertIn("-t", first_call_cmd)

    def test_overlay_badge_on_frame(self):
        dummy_frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
        overlaid = overlay_badge_on_frame(
            frame_rgb=dummy_frame,
            badge_text="🔥 VEJA O QUE ELE DISSE...",
            badge_style="gold_viral",
            badge_y_pct=25.0
        )
        self.assertIsNotNone(overlaid)
        self.assertEqual(overlaid.shape, (720, 1280, 3))
        # O frame sobreposto deve ter sido modificado na região do badge
        self.assertFalse(np.array_equal(dummy_frame, overlaid))

    def test_create_hook_badge_with_all_presets(self):
        for idx, preset_text in enumerate(HOOK_BADGE_PRESETS):
            out_p = os.path.join(self.test_dir, f"badge_preset_{idx}.png")
            res = create_hook_badge_image(
                badge_text=preset_text,
                badge_style="gold_viral",
                video_width=1080,
                video_height=1920,
                output_png_path=out_p
            )
            self.assertIsNotNone(res)
            self.assertTrue(os.path.exists(res))
            self.assertTrue(os.path.getsize(res) > 0)

    def test_record_hook_edit_in_history(self):
        target_out = os.path.join(self.test_dir, "corte_com_gancho.mp4")
        with open(target_out, "wb") as f:
            f.write(b"\x00" * 1024)

        entry = record_quick_edit(
            video_path=self.dummy_video,
            action_name="🎣 Gancho Viral (Hook / Teaser)",
            details="Trecho: 10.0s a 14.0s (4.0s) | Estilo: Noir | Modo: Teaser",
            output_path=target_out,
            extra_info={"hook_duration": 4.0, "badge_y_pct": 14.0}
        )

        self.assertEqual(entry["action"], "🎣 Gancho Viral (Hook / Teaser)")
        self.assertEqual(entry["extra_info"]["hook_duration"], 4.0)
        self.assertEqual(entry["extra_info"]["badge_y_pct"], 14.0)
        history = load_edit_history(self.dummy_video)
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "🎣 Gancho Viral (Hook / Teaser)")


if __name__ == "__main__":
    unittest.main()

