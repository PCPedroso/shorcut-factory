import os
import shutil
import tempfile
import unittest
import json

from core.subtitle_burner import (
    parse_srt_to_transcript_dict,
    resolve_preserved_cut_transcript,
    extract_words_in_range,
    apply_edited_transcript_to_json
)
from core.export_kit import create_viral_package


class TestPreserveCutTranscript(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_srt_to_transcript_dict(self):
        srt_content = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "Eu quero que você entenda\n\n"
            "2\n"
            "00:00:04,500 --> 00:00:08,000\n"
            "este assunto perfeitamente\n"
        )
        srt_path = os.path.join(self.test_dir, "legendas.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        data = parse_srt_to_transcript_dict(srt_path)
        self.assertIn("segments", data)
        self.assertEqual(len(data["segments"]), 2)
        self.assertEqual(data["segments"][0]["start"], 1.0)
        self.assertEqual(data["segments"][0]["end"], 4.0)
        self.assertEqual(data["segments"][0]["text"], "Eu quero que você entenda")
        self.assertEqual(len(data["segments"][0]["words"]), 5)
        self.assertIn("você", data["full_text"])

    def test_resolve_with_edited_txt(self):
        # Cria pasta do corte existente
        cut_folder = os.path.join(self.test_dir, "VFDBS_Corte_Teste")
        os.makedirs(cut_folder, exist_ok=True)

        txt_path = os.path.join(cut_folder, "transcricao_corte.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Eu quero que você compreenda este assunto perfeitamente")

        # Base JSON
        base_json = os.path.join(self.test_dir, "base_tr.json")
        with open(base_json, "w", encoding="utf-8") as f:
            json.dump({
                "segments": [
                    {
                        "start": 0.0,
                        "end": 8.0,
                        "text": "Eu quero que você entenda este assunto perfeitamente",
                        "words": [
                            {"word": "Eu", "start": 0.0, "end": 0.5},
                            {"word": "quero", "start": 0.5, "end": 1.2},
                            {"word": "que", "start": 1.2, "end": 1.5},
                            {"word": "você", "start": 1.5, "end": 2.2},
                            {"word": "entenda", "start": 2.2, "end": 3.5},
                            {"word": "este", "start": 3.5, "end": 4.2},
                            {"word": "assunto", "start": 4.2, "end": 5.5},
                            {"word": "perfeitamente", "start": 5.5, "end": 7.5}
                        ]
                    }
                ]
            }, f)

        res_path = resolve_preserved_cut_transcript(
            cut_folder_path=cut_folder,
            base_transcript_path=base_json,
            start_time_str="00:00:00",
            end_time_str="00:00:08"
        )
        self.assertIsNotNone(res_path)
        self.assertTrue(os.path.exists(res_path))

        with open(res_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("compreenda", data["full_text"])

    def test_resolve_with_only_srt(self):
        cut_folder = os.path.join(self.test_dir, "HOFHD_Corte_SRT")
        os.makedirs(cut_folder, exist_ok=True)

        srt_path = os.path.join(cut_folder, "legendas.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,500 --> 00:00:03,000\nFala importante do corte\n")

        res_path = resolve_preserved_cut_transcript(cut_folder)
        self.assertIsNotNone(res_path)
        self.assertTrue(os.path.exists(res_path))

        txt_created = os.path.join(cut_folder, "transcricao_corte.txt")
        self.assertTrue(os.path.exists(txt_created))
        with open(txt_created, "r", encoding="utf-8") as f:
            self.assertIn("Fala importante", f.read())

    def test_extract_words_in_range_already_relative(self):
        # Transcript que já é local/relativo (0s a 10s)
        local_json = os.path.join(self.test_dir, "local_tr.json")
        with open(local_json, "w", encoding="utf-8") as f:
            json.dump({
                "segments": [
                    {
                        "start": 0.5,
                        "end": 4.0,
                        "words": [
                            {"word": "Olá", "start": 0.5, "end": 1.5},
                            {"word": "mundo", "start": 1.5, "end": 3.0}
                        ]
                    }
                ]
            }, f)

        # Trecho original no vídeo full era 01:00 (60s) a 01:10 (70s)
        words = extract_words_in_range(local_json, "00:01:00", "00:01:10")
        self.assertEqual(len(words), 2)
        self.assertEqual(words[0]["word"], "Olá")
        self.assertEqual(words[1]["word"], "mundo")

    def test_create_viral_package_preserves_existing_transcript(self):
        src_video = os.path.join(self.test_dir, "fake_cut.mp4")
        with open(src_video, "wb") as f:
            f.write(b"\x00" * 512)

        # Pasta de corte anterior com transcrição editada
        old_folder = os.path.join(self.test_dir, "VFDBS_Corte_Old")
        os.makedirs(old_folder, exist_ok=True)
        old_txt = os.path.join(old_folder, "transcricao_corte.txt")
        with open(old_txt, "w", encoding="utf-8") as f:
            f.write("Texto editado manualmente pelo usuário que deve ser preservado")

        pkg = create_viral_package(
            video_path=src_video,
            title="Corte Re-renderizado",
            description="Desc",
            hashtags=["#shorts"],
            tags_seo="seo",
            aspect_mode="16:9",
            output_base_dir=self.test_dir,
            preserve_existing_transcript=True,
            existing_folder_path=old_folder
        )

        pkg_dir = pkg["package_dir"]
        pkg_txt = os.path.join(pkg_dir, "transcricao_corte.txt")
        self.assertTrue(os.path.exists(pkg_txt))
        with open(pkg_txt, "r", encoding="utf-8") as f:
            saved_content = f.read()
        self.assertIn("Texto editado manualmente pelo usuário que deve ser preservado", saved_content)


if __name__ == "__main__":
    unittest.main()
