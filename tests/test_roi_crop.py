"""
test_roi_crop.py — Testes Unitários para a Ferramenta de Enquadramento Manual & Remoção de Propagandas (ROI)
"""

import os
import shutil
import tempfile
import unittest
import numpy as np
import cv2

from core.video_processor import (
    CROP_MARGIN_PRESETS,
    sanitize_crop_margins,
    has_active_crop_margins,
    build_roi_crop_filter
)
from core.frame_capturer import (
    generate_roi_preview_image,
    generate_cropped_preview_image
)


class TestRoiCrop(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_roi_crop_")

    def tearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_presets_exist_and_calibrated(self):
        """Verifica se os presets homologados estão cadastrados com as proporções corretas."""
        self.assertIn("none", CROP_MARGIN_PRESETS)
        self.assertIn("l_banner_sponsor", CROP_MARGIN_PRESETS)
        self.assertIn("superchat_footer", CROP_MARGIN_PRESETS)
        self.assertIn("letterbox_cleanup", CROP_MARGIN_PRESETS)
        self.assertIn("custom", CROP_MARGIN_PRESETS)

        # Calibração Iron Talks (Banner L: Direita 28%, Rodapé 24%)
        iron_talks = CROP_MARGIN_PRESETS["l_banner_sponsor"]["margins"]
        self.assertAlmostEqual(iron_talks["right"], 0.28, places=2)
        self.assertAlmostEqual(iron_talks["bottom"], 0.24, places=2)
        self.assertEqual(iron_talks["left"], 0.0)
        self.assertEqual(iron_talks["top"], 0.0)

        # Superchat (Rodapé 20%)
        superchat = CROP_MARGIN_PRESETS["superchat_footer"]["margins"]
        self.assertAlmostEqual(superchat["bottom"], 0.20, places=2)
        self.assertEqual(superchat["right"], 0.0)

    def test_sanitize_crop_margins(self):
        """Valida a sanitização e clamping de segurança das margens."""
        # Caso 1: Entrada nula ou vazia
        self.assertEqual(sanitize_crop_margins(None), {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0})
        self.assertEqual(sanitize_crop_margins({}), {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0})

        # Caso 2: Margens válidas normais
        valid = {"top": 0.05, "bottom": 0.20, "left": 0.0, "right": 0.25}
        san = sanitize_crop_margins(valid)
        self.assertAlmostEqual(san["top"], 0.05)
        self.assertAlmostEqual(san["bottom"], 0.20)
        self.assertAlmostEqual(san["left"], 0.0)
        self.assertAlmostEqual(san["right"], 0.25)

        # Caso 3: Valores acima do teto de 45% por borda
        extreme = {"top": 0.80, "bottom": 0.60, "left": 0.0, "right": 0.0}
        san_ext = sanitize_crop_margins(extreme)
        self.assertLessEqual(san_ext["top"] + san_ext["bottom"], 0.90)

    def test_has_active_crop_margins(self):
        """Verifica detecção de cortes ativos."""
        self.assertFalse(has_active_crop_margins(None))
        self.assertFalse(has_active_crop_margins({"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0}))
        self.assertTrue(has_active_crop_margins({"top": 0.0, "bottom": 0.24, "left": 0.0, "right": 0.28}))
        self.assertTrue(has_active_crop_margins({"top": 0.05, "bottom": 0.0, "left": 0.0, "right": 0.0}))

    def test_build_roi_crop_filter(self):
        """Valida que o filtro FFmpeg gerado possui arredondamentos e coordenadas válidas."""
        margins = {"top": 0.0, "bottom": 0.24, "left": 0.0, "right": 0.28}
        f_str = build_roi_crop_filter(margins, "0:v", "roi")
        self.assertIn("[0:v]crop=", f_str)
        self.assertIn("[roi]", f_str)
        # Largura útil: 1.0 - 0.28 = 0.7200
        self.assertIn("0.7200", f_str)
        # Altura útil: 1.0 - 0.24 = 0.7600
        self.assertIn("0.7600", f_str)
        # Paridade par
        self.assertIn("/2)*2", f_str)

    def test_generate_roi_preview_image_with_synthetic_frame(self):
        """Gera imagem de prévia com máscara sobre um frame sintético Full HD 1920x1080."""
        # Cria frame sintético representando podcast com propaganda na lateral e rodapé
        frame = np.full((1080, 1920, 3), (60, 60, 60), dtype=np.uint8)
        # Propaganda na lateral direita (Verde / Patrocínio)
        frame[:, int(1920 * 0.72):] = (0, 180, 0)
        # Ticker inferior (Azul escuro)
        frame[int(1080 * 0.76):, :] = (150, 0, 0)

        out_path = os.path.join(self.tmp_dir, "roi_preview.jpg")
        margins = {"top": 0.0, "bottom": 0.24, "left": 0.0, "right": 0.28}

        res = generate_roi_preview_image(frame, output_path=out_path, crop_margins=margins)

        self.assertIsNone(res.get("error"))
        self.assertTrue(res["has_crop"])
        self.assertEqual(res["path"], out_path)
        self.assertTrue(os.path.exists(out_path))

        # Verifica dimensões da imagem gerada (deve manter 1920x1080 na prévia da máscara)
        img = cv2.imread(out_path)
        self.assertEqual(img.shape[:2], (1080, 1920))

        # Dimensões da ROI preservada: ~1382x821
        x1, y1, x2, y2 = res["roi"]
        self.assertEqual(x1, 0)
        self.assertEqual(y1, 0)
        self.assertEqual(x2, int(round(1920 * 0.72)))
        self.assertEqual(y2, int(round(1080 * 0.76)))

    def test_generate_cropped_preview_image_169(self):
        """Valida que o resultado renderizado 16:9 ajusta a ROI limpa para 1920x1080 Full HD."""
        frame = np.full((1080, 1920, 3), (80, 80, 80), dtype=np.uint8)
        frame[:, int(1920 * 0.72):] = (0, 200, 0)
        frame[int(1080 * 0.76):, :] = (200, 0, 0)

        out_path = os.path.join(self.tmp_dir, "cropped_169.jpg")
        margins = {"top": 0.0, "bottom": 0.24, "left": 0.0, "right": 0.28}

        res = generate_cropped_preview_image(frame, output_path=out_path, crop_margins=margins, target_aspect="16:9")

        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_path))

        img = cv2.imread(out_path)
        self.assertEqual(img.shape[:2], (1080, 1920))

    def test_generate_cropped_preview_image_916_blur(self):
        """Valida que o resultado renderizado 9:16 Blur cria o fundo desfocado e primeiro plano em 1080x1920."""
        frame = np.full((1080, 1920, 3), (100, 100, 100), dtype=np.uint8)
        out_path = os.path.join(self.tmp_dir, "cropped_916_blur.jpg")
        margins = {"top": 0.0, "bottom": 0.20, "left": 0.0, "right": 0.0}

        res = generate_cropped_preview_image(frame, output_path=out_path, crop_margins=margins, target_aspect="9:16_blur")

        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_path))

        img = cv2.imread(out_path)
        self.assertEqual(img.shape[:2], (1920, 1080))


if __name__ == "__main__":
    unittest.main()
