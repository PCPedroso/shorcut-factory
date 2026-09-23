import unittest
from core.headline_drawer import (
    clean_and_condense_headline,
    format_headline_text,
    hex_to_ass_color,
    build_ass_headline_style,
    HEADLINE_PRESETS,
    DANGLING_ENDINGS
)


class TestHeadlineDrawer(unittest.TestCase):

    def test_hex_to_ass_color(self):
        # Hex #FFE600 (Yellow) -> ASS format &H0000E6FF& (&HAABBGGRR&)
        ass_col = hex_to_ass_color("#FFE600", alpha=0.0)
        self.assertEqual(ass_col, "&H0000E6FF&")

        # Hex #000000 (Black)
        ass_black = hex_to_ass_color("#000000", alpha=0.0)
        self.assertEqual(ass_black, "&H00000000&")

        # Hex #FFFFFF (White)
        ass_white = hex_to_ass_color("#FFFFFF", alpha=0.0)
        self.assertEqual(ass_white, "&H00FFFFFF&")

    def test_clean_and_condense_headline_removes_speaker_prefixes(self):
        raw = "Candidato desafia a crise econômica vou pegar o país quebrado e resolver tudo"
        cleaned = clean_and_condense_headline(raw, max_chars=75)
        self.assertFalse(cleaned.startswith("CANDIDATO"))
        self.assertIn("PAÍS QUEBRADO", cleaned)

    def test_clean_and_condense_headline_no_dangling_endings(self):
        raw = "Renan Santos nós estamos destruídos por esses caras, tomados pelo"
        cleaned = clean_and_condense_headline(raw, max_chars=40)
        last_word = cleaned.split()[-1].rstrip('.,!?:')
        self.assertNotIn(last_word, DANGLING_ENDINGS)
        self.assertNotEqual(last_word, "PELO")
        self.assertNotEqual(last_word, "E")
        self.assertNotEqual(last_word, "DA")

    def test_clean_and_condense_headline_preserves_questions(self):
        raw = "Como convencer eleitores de 60 anos? Candidato responde com franqueza"
        cleaned = clean_and_condense_headline(raw, max_chars=75)
        self.assertTrue(cleaned.endswith("?") or "ELEITORES" in cleaned)

    def test_format_headline_text_two_lines_and_uppercase(self):
        raw = "Vou pegar o país quebrado e resolver tudo"
        formatted = format_headline_text(raw, max_width_chars=24, max_lines=3)
        lines = formatted.split(r"\N")
        self.assertLessEqual(len(lines), 3)
        self.assertEqual(formatted, formatted.upper())
        for line in lines:
            self.assertFalse(line.split()[-1].rstrip('.,!?:') in DANGLING_ENDINGS)

    def test_build_ass_headline_style(self):
        style = build_ass_headline_style(preset_key="yellow_black", font_size=46, margin_top=120)
        self.assertIn("Style: Headline", style)
        self.assertIn("Montserrat ExtraBold", style)
        self.assertIn("46", style)
        self.assertIn("120", style)

    def test_render_headline_overlay(self):
        from core.headline_drawer import render_headline_overlay
        overlay = render_headline_overlay(
            video_width=1080,
            video_height=1920,
            text="PREPARO DE RENAN SANTOS\nESTA MUITO ACIMA DO NORMAL",
            config={"preset_key": "yellow_black", "margin_top": 240, "font_size": 70}
        )
        self.assertEqual(overlay.shape, (1920, 1080, 4))
        # Ensure some non-transparent pixels exist
        self.assertTrue(overlay[:, :, 3].max() > 0)

    def test_generate_headline_preview(self):
        import cv2
        import numpy as np
        import tempfile
        import os
        from core.headline_drawer import generate_headline_preview

        # Create dummy 1-second video
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_video = os.path.join(tmp_dir, "dummy_prev.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(dummy_video, fourcc, 10.0, (1080, 1920))
            for _ in range(10):
                out.write(np.zeros((1920, 1080, 3), dtype=np.uint8))
            out.release()

            prev = generate_headline_preview(
                video_path=dummy_video,
                text="TESTE DE HEADLINE",
                config={"preset_key": "red_white", "margin_top": 200},
                timestamp_s=0.5
            )
            self.assertIsNotNone(prev)
            self.assertEqual(prev.shape, (1920, 1080, 3))

    def test_custom_headline_style(self):
        style = build_ass_headline_style(
            preset_key="custom",
            custom_text_color="#FF0000",
            custom_bg_color="#00FF00",
            font_size=50,
            margin_top=100
        )
        self.assertIn("Style: Headline", style)
        self.assertIn("50", style)

    def test_render_headline_overlay_preset_colors_red_white(self):
        from core.headline_drawer import render_headline_overlay
        overlay = render_headline_overlay(
            video_width=1080,
            video_height=1920,
            text="ALERTA URGENTE",
            config={
                "preset_key": "red_white",
                "text_color": "#FFFFFF",
                "bg_color": "#E50914"
            }
        )
        # Check non-transparent pixels have red-dominant background
        alpha = overlay[:, :, 3]
        mask = alpha > 128
        red_channel = overlay[:, :, 0][mask]
        blue_channel = overlay[:, :, 2][mask]
        # Red channel should be higher than blue for #E50914 background
        self.assertTrue(len(red_channel) > 0)
        self.assertTrue(red_channel.mean() > blue_channel.mean())

    def test_render_headline_overlay_synonym_keys(self):
        from core.headline_drawer import render_headline_overlay
        overlay = render_headline_overlay(
            video_width=1080,
            video_height=1920,
            text="CARD UNICO TESTE",
            config={
                "mode": "single_card",
                "bg_alpha": 0.85,
                "padding_h": 35,
                "padding_v": 20,
                "max_width_pct": 0.9,
                "shadow": True,
                "preset_key": "yellow_black"
            }
        )
        self.assertEqual(overlay.shape, (1920, 1080, 4))
        self.assertTrue(overlay[:, :, 3].max() > 0)

    def test_apply_headline_with_start_offset(self):
        from core.headline_drawer import apply_headline_to_video
        from unittest.mock import patch, MagicMock
        with patch("subprocess.run") as mock_run, \
             patch("cv2.VideoCapture") as mock_vc, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.rename"):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = [1080, 1920, 30.0, 300]
            mock_vc.return_value = mock_cap
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")

            res = apply_headline_to_video(
                video_path="dummy.mp4",
                text="TESTE DELAY",
                start_offset_s=4.5,
                output_path="dummy_out.mp4"
            )
            self.assertIsNone(res.get("error"))
            self.assertEqual(res.get("start_offset_s"), 4.5)
            # Check filter_complex contains enable='gte(t,4.500)'
            called_cmd = mock_run.call_args[0][0]
            fc_arg = called_cmd[called_cmd.index("-filter_complex") + 1]
            self.assertIn("enable='gte(t,4.500)'", fc_arg)

    def test_particle_explosion_helpers(self):
        """Valida que a extração de partículas e renderização de frames de explosão funcionam."""
        from core.headline_drawer import render_headline_overlay, extract_particles_from_overlay, render_particle_explosion_frame
        import numpy as np

        overlay = render_headline_overlay(1080, 1920, "TEXTO EXPLOSIVO", {})
        particles = extract_particles_from_overlay(overlay, block_size=6, max_particles=500)
        self.assertTrue(len(particles) > 0)

        # Frame no início da explosão (t=0.1)
        f_start = render_particle_explosion_frame(particles, 0.1, 1080, 1920)
        self.assertEqual(f_start.shape, (1920, 1080, 4))
        self.assertTrue(f_start[:, :, 3].max() > 0)

        # Frame no fim da explosão (t=1.0) -> completamente limpo
        f_end = render_particle_explosion_frame(particles, 1.0, 1080, 1920)
        self.assertEqual(f_end[:, :, 3].max(), 0)

    def test_slide_explode_preview(self):
        """Valida a prévia da headline com efeito de slide e explosão em partículas."""
        from core.headline_drawer import generate_headline_preview
        from unittest.mock import patch, MagicMock
        import numpy as np

        with patch("cv2.VideoCapture") as mock_vc, \
             patch("os.path.exists", return_value=True):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = [30.0, 300]
            mock_cap.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
            mock_vc.return_value = mock_cap

            cfg = {
                "start_offset_s": 1.0,
                "end_offset_s": 5.0,
                "transition_type": "slide_explode",
                "transition_dur_s": 0.8
            }

            # Durante a explosão (4.5s -> entre 4.2s e 5.0s)
            prev_expl = generate_headline_preview("dummy.mp4", "EXPLOSÃO", cfg, timestamp_s=4.5)
            self.assertIsNotNone(prev_expl)
            self.assertEqual(prev_expl.shape, (1920, 1080, 3))

    def test_apply_headline_slide_explode(self):
        """Valida que apply_headline_to_video monta os inputs de partículas para slide_explode."""
        from core.headline_drawer import apply_headline_to_video
        from unittest.mock import patch, MagicMock
        with patch("subprocess.run") as mock_run, \
             patch("cv2.VideoCapture") as mock_vc, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.rename"):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = [1080, 1920, 30.0, 300]
            mock_vc.return_value = mock_cap
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")

            res = apply_headline_to_video(
                video_path="dummy.mp4",
                text="TESTE EXPLOSÃO",
                start_offset_s=1.0,
                end_offset_s=5.0,
                transition_type="slide_explode",
                transition_dur_s=0.8,
                output_path="dummy_out.mp4"
            )
            self.assertIsNone(res.get("error"))
            self.assertEqual(res.get("transition_type"), "slide_explode")
            called_cmd = mock_run.call_args[0][0]
            fc_arg = called_cmd[called_cmd.index("-filter_complex") + 1]
            self.assertIn("eof_action=pass", fc_arg)

    def test_static_explode_preview(self):
        """Valida que static_explode exibe texto estático sem slide no início e partículas na explosão."""
        from core.headline_drawer import generate_headline_preview
        from unittest.mock import patch, MagicMock
        import numpy as np

        with patch("cv2.VideoCapture") as mock_vc, \
             patch("os.path.exists", return_value=True):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: 300 if prop == 7 else 30.0
            mock_cap.read.return_value = (True, np.zeros((1920, 1080, 3), dtype=np.uint8))
            mock_vc.return_value = mock_cap

            cfg = {
                "start_offset_s": 0.0,
                "end_offset_s": 5.0,
                "transition_type": "static_explode",
                "transition_dur_s": 0.8
            }

            # Durante o período fixo/estático (t=1.0s)
            prev_static = generate_headline_preview("dummy.mp4", "ESTÁTICO", cfg, timestamp_s=1.0)
            self.assertIsNotNone(prev_static)
            self.assertEqual(prev_static.shape, (1920, 1080, 3))

            # Durante a explosão final (t=4.6s -> entre 4.2s e 5.0s)
            prev_expl = generate_headline_preview("dummy.mp4", "ESTÁTICO", cfg, timestamp_s=4.6)
            self.assertIsNotNone(prev_expl)
            self.assertEqual(prev_expl.shape, (1920, 1080, 3))

    def test_apply_headline_static_explode(self):
        """Valida que apply_headline_to_video monta overlay fixo x=0:y=0 e partículas para static_explode."""
        from core.headline_drawer import apply_headline_to_video
        from unittest.mock import patch, MagicMock
        with patch("subprocess.run") as mock_run, \
             patch("cv2.VideoCapture") as mock_vc, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.rename"):
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = [1080, 1920, 30.0, 300]
            mock_vc.return_value = mock_cap
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")

            res = apply_headline_to_video(
                video_path="dummy.mp4",
                text="TESTE ESTÁTICO EXPLOSÃO",
                start_offset_s=0.0,
                end_offset_s=5.0,
                transition_type="static_explode",
                transition_dur_s=0.8,
                output_path="dummy_out.mp4"
            )
            self.assertIsNone(res.get("error"))
            self.assertEqual(res.get("transition_type"), "static_explode")
            called_cmd = mock_run.call_args[0][0]
            fc_arg = called_cmd[called_cmd.index("-filter_complex") + 1]
            self.assertIn("overlay=x=0:y=0", fc_arg)
            self.assertIn("eof_action=pass", fc_arg)


if __name__ == '__main__':
    unittest.main()


