import os
import shutil
import unittest
from unittest.mock import patch, MagicMock

from core.cuts_catalog import load_cuts_catalog, sync_carrossel_parts_to_catalog


class TestBatchQuickEditor(unittest.TestCase):
    def setUp(self):
        self.test_vid_id = "test_vid_batch_quick_456"
        self.test_dir = os.path.join("data", self.test_vid_id)
        self.carrossel_dir = os.path.join(self.test_dir, "carrossel")
        os.makedirs(self.carrossel_dir, exist_ok=True)

        self.parts = [
            {"filename": "parte_01_9-16_blur.mp4", "path": os.path.join(self.carrossel_dir, "parte_01_9-16_blur.mp4")},
            {"filename": "parte_02_9-16_blur.mp4", "path": os.path.join(self.carrossel_dir, "parte_02_9-16_blur.mp4")},
        ]
        for p in self.parts:
            with open(p["path"], "wb") as f:
                f.write(b"0" * 20480)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("core.headline_drawer.apply_headline_to_video", return_value={"output_path": "fake.mp4", "error": None})
    @patch("core.quick_editor.record_quick_edit", return_value={})
    @patch("core.cuts_catalog.sync_carrossel_parts_to_catalog", return_value={})
    def test_batch_headline_application(self, mock_sync, mock_record, mock_apply_hl):
        """Valida que o headline em lote é aplicado em todas as partes com substituição dinâmica de {parte}."""
        from core.headline_drawer import apply_headline_to_video

        template_text = "Caso Especial • Parte {parte}"
        cfg = {"font_size": 50, "mode": "line_boxes"}

        applied_texts = []
        for idx, p in enumerate(self.parts, start=1):
            p_text = template_text.replace("{parte}", f"{idx:02d}").replace("{num}", str(idx))
            applied_texts.append(p_text)
            apply_headline_to_video(video_path=p["path"], text=p_text, config=cfg, start_offset_s=0.0)

        self.assertEqual(applied_texts, ["Caso Especial • Parte 01", "Caso Especial • Parte 02"])
        self.assertEqual(mock_apply_hl.call_count, 2)

    @patch("core.quick_editor.add_viral_hook_to_video", return_value={"output_path": "fake.mp4", "error": None})
    def test_batch_hook_application(self, mock_hook):
        """Valida que o gancho viral em lote é aplicado em todas as partes."""
        from core.quick_editor import add_viral_hook_to_video

        for p in self.parts:
            add_viral_hook_to_video(
                video_path=p["path"],
                hook_start_s=0.0,
                hook_end_s=3.0,
                hook_style="zoom_impact",
                badge_text="ASSISTA ATÉ O FINAL 😱",
                badge_style="fire_neon",
                badge_y_pct=28,
                transition_type="flash_white",
                hook_mode="teaser"
            )

        self.assertEqual(mock_hook.call_count, 2)

    @patch("core.quick_editor.change_video_speed", return_value={"output_path": "fake.mp4", "error": None})
    def test_batch_speed_application(self, mock_speed):
        """Valida que a aceleração em lote é aplicada em todas as partes com o fator correto."""
        from core.quick_editor import change_video_speed

        sel_speed = 1.15
        for p in self.parts:
            change_video_speed(p["path"], speed=sel_speed)

        self.assertEqual(mock_speed.call_count, 2)

    @patch("cv2.VideoCapture")
    def test_generate_headline_preview_timestamp_args(self, mock_cv):
        """Valida que generate_headline_preview aceita tanto timestamp_s quanto timestamp_sec sem erro."""
        from core.headline_drawer import generate_headline_preview
        import numpy as np

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0
        mock_frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv.return_value = mock_cap

        # Chamada com timestamp_s
        res_s = generate_headline_preview(self.parts[0]["path"], "Título Teste", {}, timestamp_s=1.5)
        self.assertIsNotNone(res_s)

        # Chamada com timestamp_sec (compatibilidade / alias)
        res_sec = generate_headline_preview(self.parts[0]["path"], "Título Teste", {}, timestamp_sec=1.5)
        self.assertIsNotNone(res_sec)

    @patch("cv2.VideoCapture")
    def test_headline_timing_and_transitions_in_preview(self, mock_cv):
        """Valida que a prévia da headline respeita início, término e interpolação de transições."""
        from core.headline_drawer import generate_headline_preview
        import numpy as np

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 30.0
        mock_frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv.return_value = mock_cap

        cfg = {
            "start_offset_s": 2.0,
            "end_offset_s": 6.0,
            "transition_type": "fade",
            "transition_dur_s": 0.5
        }

        # 1. Antes do início (1.0s) -> frame original sem texto
        prev_before = generate_headline_preview(self.parts[0]["path"], "Texto Teste", cfg, timestamp_s=1.0)
        self.assertIsNotNone(prev_before)

        # 2. Durante a transição de entrada (2.25s -> fade 50%)
        prev_fade_in = generate_headline_preview(self.parts[0]["path"], "Texto Teste", cfg, timestamp_s=2.25)
        self.assertIsNotNone(prev_fade_in)

        # 3. Durante o período estável (4.0s -> 100% visível)
        prev_stable = generate_headline_preview(self.parts[0]["path"], "Texto Teste", cfg, timestamp_s=4.0)
        self.assertIsNotNone(prev_stable)

        # 4. Durante a transição de saída (5.75s -> fade out)
        prev_fade_out = generate_headline_preview(self.parts[0]["path"], "Texto Teste", cfg, timestamp_s=5.75)
        self.assertIsNotNone(prev_fade_out)

        # 5. Após o término (7.0s -> oculto)
        prev_after = generate_headline_preview(self.parts[0]["path"], "Texto Teste", cfg, timestamp_s=7.0)
        self.assertIsNotNone(prev_after)

    @patch("core.headline_drawer.apply_headline_to_video", return_value={"output_path": "fake.mp4", "error": None})
    def test_apply_headline_duration_and_transition_params(self, mock_apply_hl):
        """Valida que apply_headline_to_video propaga parâmetros de duração e transição."""
        from core.headline_drawer import apply_headline_to_video

        cfg = {
            "start_offset_s": 3.0,
            "end_offset_s": 12.0,
            "transition_type": "slide_fade",
            "transition_dur_s": 0.8
        }
        res = apply_headline_to_video(
            video_path=self.parts[0]["path"],
            text="Headline Teste",
            config=cfg,
            start_offset_s=3.0,
            end_offset_s=12.0,
            transition_type="slide_fade",
            transition_dur_s=0.8
        )
        self.assertEqual(res["output_path"], "fake.mp4")
        mock_apply_hl.assert_called_once_with(
            video_path=self.parts[0]["path"],
            text="Headline Teste",
            config=cfg,
            start_offset_s=3.0,
            end_offset_s=12.0,
            transition_type="slide_fade",
            transition_dur_s=0.8
        )


if __name__ == "__main__":
    unittest.main()
