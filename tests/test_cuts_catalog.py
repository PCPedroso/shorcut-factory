import os
import shutil
import tempfile
import unittest
import core.cuts_catalog as catalog


class TestCutsCatalog(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.video_id = "test_video_123"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        v_data = os.path.join("data", self.video_id)
        if os.path.exists(v_data):
            shutil.rmtree(v_data, ignore_errors=True)

    def test_register_and_retrieve_cut_instance(self):
        # Registra instância formato Blur
        entry_blur = catalog.register_cut_instance(
            video_id=self.video_id,
            start_time="00:01:00",
            end_time="00:01:45",
            title="Momento Revelador",
            description="Descrição do corte",
            hashtags=["#shorts", "#viral"],
            tags_seo="cortes, viral",
            aspect_mode="9:16_blur",
            folder_name="VFDBS_Momento_Revelador",
            folder_path=f"data/{self.video_id}/VFDBS_Momento_Revelador",
            video_path=f"data/{self.video_id}/VFDBS_Momento_Revelador/VFDBS_Momento_Revelador.mp4",
            resolution="1080x1920"
        )
        self.assertIn("9:16_blur", entry_blur["formats"])
        self.assertEqual(entry_blur["formats"]["9:16_blur"]["folder_name"], "VFDBS_Momento_Revelador")

        # Recupera entrada pelo catálogo
        entry = catalog.get_cut_entry(self.video_id, "00:01:00", "00:01:45")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "Momento Revelador")

        # Registra segundo formato para a mesma minutagem (Smart Face)
        catalog.register_cut_instance(
            video_id=self.video_id,
            start_time="00:01:00",
            end_time="00:01:45",
            title="Momento Revelador",
            description="Descrição do corte",
            hashtags=["#shorts", "#viral"],
            tags_seo="cortes, viral",
            aspect_mode="9:16_smart_face",
            folder_name="VRIRA_Momento_Revelador",
            folder_path=f"data/{self.video_id}/VRIRA_Momento_Revelador",
            video_path=f"data/{self.video_id}/VRIRA_Momento_Revelador/VRIRA_Momento_Revelador.mp4",
            resolution="1080x1920"
        )

        entry_both = catalog.get_cut_entry(self.video_id, "00:01:00", "00:01:45")
        self.assertIsNotNone(entry_both)
        self.assertIn("9:16_blur", entry_both["formats"])
        self.assertIn("9:16_smart_face", entry_both["formats"])

    def test_delete_format_instance(self):
        catalog.register_cut_instance(
            video_id=self.video_id,
            start_time="00:02:00",
            end_time="00:02:30",
            title="Corte Teste Delete",
            description="Desc",
            hashtags=["#shorts"],
            tags_seo="cortes",
            aspect_mode="9:16_crop",
            folder_name="VCCFT_Corte_Teste",
            folder_path=f"data/{self.video_id}/VCCFT_Corte_Teste",
            video_path=f"data/{self.video_id}/VCCFT_Corte_Teste/VCCFT_Corte_Teste.mp4",
            resolution="1080x1920"
        )

        del_res = catalog.delete_format_instance(self.video_id, "00:02:00", "00:02:30", "9:16_crop", delete_publication_kit=True)
        self.assertTrue(del_res)

        entry_after = catalog.get_cut_entry(self.video_id, "00:02:00", "00:02:30")
        self.assertIsNone(entry_after)


if __name__ == '__main__':
    unittest.main()
