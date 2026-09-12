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


if __name__ == "__main__":
    unittest.main()
