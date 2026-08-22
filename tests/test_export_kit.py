import os
import shutil
import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main()
