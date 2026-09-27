import os
import shutil
import unittest
from core.headline_drawer import (
    load_user_headline_presets,
    save_user_headline_preset,
    delete_user_headline_preset,
    rename_user_headline_preset,
    HEADLINE_PRESETS
)


class TestHeadlinePresets(unittest.TestCase):

    def setUp(self):
        self.test_dir = os.path.join("tests", "temp_headline_presets")
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_presets_file = os.path.join(self.test_dir, "test_user_presets.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_save_and_load_headline_preset(self):
        preset_cfg = {
            "preset_style": "yellow_black",
            "preset_style_lbl": "🟡 Amarelo Vibrante (Texto Preto)",
            "container_mode": "outline_only",
            "margin_top": 320,
            "font_size": 56,
            "text_color": "#000000",
            "bg_color": "#FFDA29",
            "bg_alpha": 95,
            "alignment": "center",
            "padding_h": 30,
            "padding_v": 18,
            "line_spacing": 12,
            "corner_radius": 15,
            "max_width_pct": 90,
            "shadow": True,
            "duration_mode": "Intervalo Personalizado",
            "start_offset": 0.0,
            "end_offset": 10.0,
            "transition_type": "static_explode",
            "transition_dur": 1.0
        }

        # Salva preset
        success = save_user_headline_preset("Meu Amarelo Viral", preset_cfg, filepath=self.test_presets_file)
        self.assertTrue(success)

        # Carrega presets
        loaded = load_user_headline_presets(filepath=self.test_presets_file)
        self.assertIn("Meu Amarelo Viral", loaded)
        loaded_cfg = loaded["Meu Amarelo Viral"]
        self.assertEqual(loaded_cfg["container_mode"], "outline_only")
        self.assertEqual(loaded_cfg["margin_top"], 320)
        self.assertEqual(loaded_cfg["font_size"], 56)
        self.assertEqual(loaded_cfg["transition_type"], "static_explode")
        self.assertEqual(loaded_cfg["duration_mode"], "Intervalo Personalizado")
        self.assertEqual(loaded_cfg["end_offset"], 10.0)

    def test_edit_update_headline_preset(self):
        preset_cfg_v1 = {
            "preset_style": "yellow_black",
            "container_mode": "line_boxes",
            "margin_top": 240,
            "font_size": 70
        }
        save_user_headline_preset("Preset Editavel", preset_cfg_v1, filepath=self.test_presets_file)

        # Atualiza o mesmo preset com novos valores (Edição)
        preset_cfg_v2 = {
            "preset_style": "yellow_black",
            "container_mode": "outline_only",
            "margin_top": 350,
            "font_size": 60
        }
        save_user_headline_preset("Preset Editavel", preset_cfg_v2, filepath=self.test_presets_file)

        loaded = load_user_headline_presets(filepath=self.test_presets_file)
        self.assertEqual(loaded["Preset Editavel"]["margin_top"], 350)
        self.assertEqual(loaded["Preset Editavel"]["container_mode"], "outline_only")
        self.assertEqual(loaded["Preset Editavel"]["font_size"], 60)

    def test_rename_headline_preset(self):
        preset_cfg = {"margin_top": 300, "font_size": 50}
        save_user_headline_preset("Nome Antigo", preset_cfg, filepath=self.test_presets_file)

        # Renomeia
        ren_success = rename_user_headline_preset("Nome Antigo", "Nome Novo", filepath=self.test_presets_file)
        self.assertTrue(ren_success)

        loaded = load_user_headline_presets(filepath=self.test_presets_file)
        self.assertNotIn("Nome Antigo", loaded)
        self.assertIn("Nome Novo", loaded)
        self.assertEqual(loaded["Nome Novo"]["margin_top"], 300)

    def test_delete_headline_preset(self):
        preset_cfg = {"margin_top": 200}
        save_user_headline_preset("Para Deletar", preset_cfg, filepath=self.test_presets_file)
        self.assertIn("Para Deletar", load_user_headline_presets(filepath=self.test_presets_file))

        del_success = delete_user_headline_preset("Para Deletar", filepath=self.test_presets_file)
        self.assertTrue(del_success)

        loaded = load_user_headline_presets(filepath=self.test_presets_file)
        self.assertNotIn("Para Deletar", loaded)

    def test_default_preview_scale_is_50_in_app(self):
        # Verifica se o padrão do slider de prévia em app.py está em 50%
        with open("app.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('hl_post_prev_scale_{unique_key}", 50)', content)
        self.assertIn('batch_hl_prev_scale", 50)', content)


if __name__ == "__main__":
    unittest.main()
