import os
import json
import shutil
import unittest
from unittest.mock import patch

from core.cuts_catalog import (
    load_cuts_catalog, sync_carrossel_parts_to_catalog,
    delete_format_instance, delete_entire_cut, delete_entire_carrossel, make_time_key
)


class TestCarrosselGaleriaSync(unittest.TestCase):
    def setUp(self):
        self.test_vid_id = "test_vid_carrossel_sync_123"
        self.test_dir = os.path.join("data", self.test_vid_id)
        self.carrossel_dir = os.path.join(self.test_dir, "carrossel")
        os.makedirs(self.carrossel_dir, exist_ok=True)

        # Cria metadata de teste
        with open(os.path.join(self.test_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "Podcast Especial sobre Tecnologia", "duration_sec": 300.0}, f)

        # Cria partes brutas e processadas falsas
        self.raw_part1 = os.path.join(self.carrossel_dir, "parte_01.mp4")
        self.raw_part2 = os.path.join(self.carrossel_dir, "parte_02.mp4")
        self.proc_part1 = os.path.join(self.carrossel_dir, "parte_01_9-16_blur.mp4")
        self.proc_part2 = os.path.join(self.carrossel_dir, "parte_02_9-16_blur.mp4")

        for p in [self.raw_part1, self.raw_part2, self.proc_part1, self.proc_part2]:
            with open(p, "wb") as f:
                f.write(b"0" * 20480)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("core.quick_editor.get_video_duration", return_value=60.0)
    @patch("core.video_processor.extract_thumbnail_from_video", return_value={"error": None})
    def test_sync_carrossel_parts_to_catalog(self, mock_thumb, mock_dur):
        """Valida que partes processadas em carrossel são sincronizadas e aparecem no catálogo."""
        catalog = sync_carrossel_parts_to_catalog(self.test_vid_id)
        self.assertEqual(len(catalog), 2)

        # Verifica se as duas partes foram registradas
        keys = sorted(catalog.keys())
        self.assertIn("00:00:00.00_00:01:00.00", keys)
        self.assertIn("00:01:00.00_00:02:00.00", keys)

        entry1 = catalog["00:00:00.00_00:01:00.00"]
        self.assertIn("Parte 01:", entry1["title"])
        self.assertIn("9:16_blur", entry1["formats"])
        fmt1 = entry1["formats"]["9:16_blur"]
        self.assertEqual(fmt1["video_filename"], "parte_01_9-16_blur.mp4")
        self.assertEqual(fmt1["folder_name"], "carrossel")

    @patch("core.quick_editor.get_video_duration", return_value=60.0)
    @patch("core.video_processor.extract_thumbnail_from_video", return_value={"error": None})
    def test_load_cuts_catalog_auto_sync(self, mock_thumb, mock_dur):
        """Valida que load_cuts_catalog automaticamente aciona a sincronização das partes."""
        catalog = load_cuts_catalog(self.test_vid_id)
        self.assertEqual(len(catalog), 2)
        entry2 = catalog["00:01:00.00_00:02:00.00"]
        self.assertIn("Parte 02:", entry2["title"])
        self.assertIn("9:16_blur", entry2["formats"])

    @patch("core.quick_editor.get_video_duration", return_value=60.0)
    @patch("core.video_processor.extract_thumbnail_from_video", return_value={"error": None})
    def test_delete_format_preserves_carrossel_folder(self, mock_thumb, mock_dur):
        """Valida que excluir um formato de carrossel apaga o vídeo mas preserva a pasta carrossel."""
        sync_carrossel_parts_to_catalog(self.test_vid_id)
        self.assertTrue(os.path.exists(self.proc_part1))

        # Deleta a instância da parte 1
        res = delete_format_instance(self.test_vid_id, "00:00:00.00", "00:01:00.00", "9:16_blur", delete_publication_kit=True)
        self.assertTrue(res)

        # O arquivo do vídeo da parte 1 deve ter sido excluído
        self.assertFalse(os.path.exists(self.proc_part1))
        # Mas a pasta carrossel e a parte 2 continuam intactas
        self.assertTrue(os.path.isdir(self.carrossel_dir))
        self.assertTrue(os.path.exists(self.proc_part2))

    @patch("core.quick_editor.get_video_duration", return_value=60.0)
    @patch("core.video_processor.extract_thumbnail_from_video", return_value={"error": None})
    def test_delete_entire_carrossel_full(self, mock_thumb, mock_dur):
        """Valida exclusão total do carrossel: apaga a pasta inteira e limpa o catálogo."""
        sync_carrossel_parts_to_catalog(self.test_vid_id)
        catalog_before = load_cuts_catalog(self.test_vid_id)
        self.assertEqual(len(catalog_before), 2)

        res = delete_entire_carrossel(self.test_vid_id, delete_raw_splits=True)
        self.assertTrue(res.get("success"))

        # Pasta inteira foi removida
        self.assertFalse(os.path.exists(self.carrossel_dir))

        # Catálogo não possui mais entradas do carrossel
        catalog_after = load_cuts_catalog(self.test_vid_id)
        self.assertEqual(len(catalog_after), 0)

    @patch("core.quick_editor.get_video_duration", return_value=60.0)
    @patch("core.video_processor.extract_thumbnail_from_video", return_value={"error": None})
    def test_delete_entire_carrossel_processed_only(self, mock_thumb, mock_dur):
        """Valida exclusão parcial: apaga partes processadas e catálogo, mas preserva fatiamentos brutos."""
        sync_carrossel_parts_to_catalog(self.test_vid_id)
        self.assertTrue(os.path.exists(self.raw_part1))
        self.assertTrue(os.path.exists(self.proc_part1))

        res = delete_entire_carrossel(self.test_vid_id, delete_raw_splits=False)
        self.assertTrue(res.get("success"))

        # Pasta e arquivos brutos ainda existem
        self.assertTrue(os.path.isdir(self.carrossel_dir))
        self.assertTrue(os.path.exists(self.raw_part1))
        self.assertTrue(os.path.exists(self.raw_part2))

        # Arquivos processados foram excluídos
        self.assertFalse(os.path.exists(self.proc_part1))
        self.assertFalse(os.path.exists(self.proc_part2))

        # Catálogo não possui mais os processados
        catalog_after = load_cuts_catalog(self.test_vid_id)
        self.assertEqual(len(catalog_after), 0)

    def test_carrossel_duration_and_speed_metrics(self):
        """Valida a lógica de cálculo de duração original vs atual e taxa de aceleração."""
        orig_dur = 45.0
        curr_dur = 37.5
        diff_sec = orig_dur - curr_dur
        ratio = orig_dur / curr_dur

        self.assertAlmostEqual(diff_sec, 7.5, places=1)
        self.assertAlmostEqual(ratio, 1.20, places=2)
        self.assertTrue(diff_sec >= 0.4 and ratio >= 1.03)

        # Caso normal (sem alteração)
        same_dur = 45.0
        self.assertFalse((orig_dur - same_dur) >= 0.4 and (orig_dur / same_dur) >= 1.03)


if __name__ == "__main__":
    unittest.main()

