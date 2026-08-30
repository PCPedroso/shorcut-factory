import os
import shutil
import tempfile
import unittest
import json
from core.export_kit import build_cut_folder_name, create_viral_package


class TestExportKit(unittest.TestCase):

    def test_build_cut_folder_name_constraints(self):
        folder_blur = build_cut_folder_name("9:16_blur", "Candidato Desafia a Crise Econômica e Política")
        self.assertTrue(folder_blur.startswith("VFDBS_"))
        suffix = folder_blur.replace("VFDBS_", "")
        self.assertLessEqual(len(suffix), 25)
        self.assertNotIn(" ", folder_blur)

        folder_split = build_cut_folder_name("9:16_split", "Entrevista com Renan Santos")
        self.assertTrue(folder_split.startswith("VLDSS_"))

        folder_face = build_cut_folder_name("9:16_smart_face", "Momento Inacreditável")
        self.assertTrue(folder_face.startswith("VRIRA_"))

        folder_crop = build_cut_folder_name("9:16_crop", "Corte Central Fixo")
        self.assertTrue(folder_crop.startswith("VCCFT_"))

        folder_horiz = build_cut_folder_name("16:9", "Original Full HD")
        self.assertTrue(folder_horiz.startswith("HOFHD_"))

    def test_create_viral_package(self):
        temp_dir = tempfile.mkdtemp()
        try:
            src_video = os.path.join(temp_dir, "fake_cut.mp4")
            with open(src_video, "wb") as f:
                f.write(b"\x00" * 1024)

            pkg = create_viral_package(
                video_path=src_video,
                title="Renan Santos sobre combate ao crime",
                description="Confira o debate e comente sua opinião!",
                hashtags=["#shorts", "#viral", "#debate"],
                tags_seo="cortes, viral, podcast",
                aspect_mode="9:16_blur",
                output_base_dir=temp_dir,
                orig_video_info={
                    "title": "Entrevista Completa 2026",
                    "channel": "Canal Oficial",
                    "upload_date": "2026-08-20",
                    "url": "https://www.youtube.com/watch?v=sample123"
                }
            )

            self.assertTrue(os.path.exists(pkg["package_dir"]))
            self.assertTrue(os.path.exists(pkg["video_dest_path"]))

            info_path = os.path.join(pkg["package_dir"], "info_publicacao.txt")
            desc_path = os.path.join(pkg["package_dir"], "descricao.txt")
            tags_path = os.path.join(pkg["package_dir"], "tags.txt")

            self.assertTrue(os.path.exists(info_path))
            self.assertTrue(os.path.exists(desc_path))
            self.assertTrue(os.path.exists(tags_path))

            with open(info_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("PACOTE DE PUBLICAÇÃO VIRAL", content)
                self.assertIn("Canal Oficial", content)
                self.assertIn("https://www.youtube.com/watch?v=sample123", content)
                self.assertIn("#shorts", content)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_viral_package_with_subtitles(self):
        temp_dir = tempfile.mkdtemp()
        try:
            src_video = os.path.join(temp_dir, "fake_cut.mp4")
            with open(src_video, "wb") as f:
                f.write(b"\x00" * 1024)

            # Cria transcript sintético
            transcript_file = os.path.join(temp_dir, "transcript.json")
            with open(transcript_file, "w", encoding="utf-8") as f:
                json.dump({
                    "segments": [
                        {
                            "start": 10.0,
                            "end": 15.0,
                            "text": "Esta é a primeira frase do corte viral.",
                            "words": [
                                {"word": "Esta", "start": 10.0, "end": 10.8},
                                {"word": "é", "start": 10.8, "end": 11.2},
                                {"word": "a", "start": 11.2, "end": 11.5},
                                {"word": "primeira", "start": 11.5, "end": 12.5},
                                {"word": "frase", "start": 12.5, "end": 13.2},
                                {"word": "do", "start": 13.2, "end": 13.5},
                                {"word": "corte", "start": 13.5, "end": 14.2},
                                {"word": "viral.", "start": 14.2, "end": 15.0}
                            ]
                        }
                    ]
                }, f)

            pkg = create_viral_package(
                video_path=src_video,
                title="Fala de Impacto sobre Economia",
                description="Entenda os pontos principais do projeto.",
                hashtags=["#shorts", "#economia"],
                tags_seo="economia, cortes",
                aspect_mode="9:16_smart_face",
                output_base_dir=temp_dir,
                orig_video_info={"title": "Vídeo Completo", "channel": "Canal", "url": "https://youtube.com/watch?v=123"},
                transcript_path=transcript_file,
                start_time_str="00:10",
                end_time_str="00:15"
            )

            self.assertIsNotNone(pkg.get("subtitle_srt_path"))
            self.assertTrue(os.path.exists(pkg["subtitle_srt_path"]))
            self.assertTrue(pkg["subtitle_srt_path"].endswith(".srt"))

            # Verifica se o arquivo de legenda genérico legendas.srt também existe
            alt_srt = os.path.join(pkg["package_dir"], "legendas.srt")
            self.assertTrue(os.path.exists(alt_srt))

            # Verifica se a transcrição de texto puro foi criada
            txt_path = os.path.join(pkg["package_dir"], "transcricao_corte.txt")
            self.assertTrue(os.path.exists(txt_path))
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("primeira frase", content)

            # Verifica se foi listado no info_publicacao.txt
            info_path = os.path.join(pkg["package_dir"], "info_publicacao.txt")
            with open(info_path, "r", encoding="utf-8") as f:
                info_text = f.read()
                self.assertIn(".SRT", info_text)

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
