import os
import shutil
import tempfile
import unittest
import json
from unittest.mock import patch

from core.library_manager import (
    create_project_from_cut_video,
    get_library,
    remove_video_from_library,
    DATA_DIR,
    LIBRARY_FILE
)


class TestCreateProjectFromCut(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Cria um arquivo de vídeo falso
        self.sample_cut_path = os.path.join(self.test_dir, "meu_corte_teste.mp4")
        with open(self.sample_cut_path, "wb") as f:
            f.write(b"fake mp4 video content for test purposes only")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("core.quick_editor.get_video_duration", return_value=7200.0)
    @patch("core.video_processor.extract_thumbnail_from_video")
    def test_create_project_from_cut_success(self, mock_thumb, mock_dur):
        res = create_project_from_cut_video(
            source_video_path=self.sample_cut_path,
            title="Grande Corte Podcast 2h",
            parent_video_id="IMkWfZssXx4",
            start_time_str="01:00:00",
            end_time_str="03:00:00",
            parent_title="Live Mestre",
            copy_transcript=False
        )

        self.assertTrue(res.get("success"))
        new_vid = res.get("video_id")
        self.assertIsNotNone(new_vid)
        self.assertTrue(str(new_vid).startswith("local_"))

        # Verifica arquivos criados na pasta data/<new_video_id>
        target_dir = os.path.join(DATA_DIR, new_vid)
        self.assertTrue(os.path.exists(target_dir))
        v_full = os.path.join(target_dir, "video_full.mp4")
        self.assertTrue(os.path.exists(v_full))
        self.assertEqual(os.path.getsize(v_full), os.path.getsize(self.sample_cut_path))

        # Verifica metadata.json
        meta_p = os.path.join(target_dir, "metadata.json")
        self.assertTrue(os.path.exists(meta_p))
        with open(meta_p, "r", encoding="utf-8") as f_m:
            meta = json.load(f_m)
            self.assertEqual(meta.get("title"), "Grande Corte Podcast 2h")
            self.assertEqual(meta.get("duration_sec"), 7200)

        # Limpeza do projeto criado no teste
        remove_video_from_library(new_vid, delete_folder=True)

    @patch("core.quick_editor.get_video_duration", return_value=3600.0)
    @patch("core.video_processor.extract_thumbnail_from_video")
    def test_create_project_with_transcript_slicing(self, mock_thumb, mock_dur):
        # Cria um projeto pai falso com transcript.json
        parent_id = "fake_parent_test_123"
        parent_dir = os.path.join(DATA_DIR, parent_id)
        os.makedirs(parent_dir, exist_ok=True)
        try:
            parent_tr_file = os.path.join(parent_dir, "transcript.json")
            with open(parent_tr_file, "w", encoding="utf-8") as f_tr:
                json.dump({
                    "full_text": "Texto completo antes do corte. Fala principal do corte. Depois do corte.",
                    "segments": [
                        {
                            "start": 500.0,
                            "end": 550.0,
                            "text": "Texto antes",
                            "words": [{"word": "Texto", "start": 500.0, "end": 510.0}]
                        },
                        {
                            "start": 3610.0,
                            "end": 3650.0,
                            "text": "Fala principal do corte",
                            "words": [
                                {"word": "Fala", "start": 3610.0, "end": 3620.0},
                                {"word": "principal", "start": 3620.0, "end": 3635.0},
                                {"word": "do", "start": 3635.0, "end": 3640.0},
                                {"word": "corte", "start": 3640.0, "end": 3650.0}
                            ]
                        },
                        {
                            "start": 8000.0,
                            "end": 8050.0,
                            "text": "Depois do corte",
                            "words": [{"word": "Depois", "start": 8000.0, "end": 8010.0}]
                        }
                    ]
                }, f_tr)

            # Executa a criação do projeto a partir do corte (01:00:00 = 3600s até 02:00:00 = 7200s)
            res = create_project_from_cut_video(
                source_video_path=self.sample_cut_path,
                title="Corte Fatiado com Transcricao",
                parent_video_id=parent_id,
                start_time_str="01:00:00",
                end_time_str="02:00:00",
                copy_transcript=True
            )

            self.assertTrue(res.get("success"))
            self.assertTrue(res.get("has_transcript"))
            new_vid = res.get("video_id")

            # Verifica transcript.json fatiado
            dest_tr = os.path.join(DATA_DIR, new_vid, "transcript.json")
            self.assertTrue(os.path.exists(dest_tr))
            with open(dest_tr, "r", encoding="utf-8") as f_d_tr:
                d_tr = json.load(f_d_tr)
                self.assertIn("Fala principal", d_tr["full_text"])
                self.assertNotIn("Texto antes", d_tr["full_text"])
                self.assertNotIn("Depois do corte", d_tr["full_text"])
                # Timestamps devem ter sido reajustados relativos ao início do corte (3600s)
                # 3610.0 - 3600.0 = 10.0s
                seg = d_tr["segments"][0]
                self.assertAlmostEqual(seg["start"], 10.0)
                self.assertAlmostEqual(seg["end"], 50.0)
                self.assertAlmostEqual(seg["words"][0]["start"], 10.0)

            remove_video_from_library(new_vid, delete_folder=True)
        finally:
            shutil.rmtree(parent_dir, ignore_errors=True)

    def test_create_project_nonexistent_file(self):
        res = create_project_from_cut_video(
            source_video_path="caminho_inexistente_12345.mp4",
            title="Corte Fantasma"
        )
        self.assertIn("error", res)
        self.assertFalse(res.get("success", False))


if __name__ == '__main__':
    unittest.main()
