import unittest
from core.config_manager import (
    load_settings,
    save_setting,
    save_all_settings,
    DEFAULT_SETTINGS
)


class TestConfigManager(unittest.TestCase):

    def test_load_settings_contains_defaults(self):
        settings = load_settings()
        self.assertIsInstance(settings, dict)
        for k in DEFAULT_SETTINGS:
            self.assertIn(k, settings)

    def test_save_setting(self):
        save_setting("subtitle_font_size", 85)
        current = load_settings()
        self.assertEqual(current["subtitle_font_size"], 85)

        # Restaura
        save_setting("subtitle_font_size", 80)
        current = load_settings()
        self.assertEqual(current["subtitle_font_size"], 80)


if __name__ == '__main__':
    unittest.main()
