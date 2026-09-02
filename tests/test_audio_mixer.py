import os
import unittest
from core.audio_mixer import (
    list_available_tracks,
    get_track_path_by_id,
    DUCKING_PRESETS,
    MUSIC_CATEGORIES
)


class TestAudioMixer(unittest.TestCase):

    def test_builtin_tracks_exist_in_assets(self):
        tracks = list_available_tracks()
        self.assertGreaterEqual(len(tracks), 8)

        track_ids = [t["id"] for t in tracks]
        self.assertIn("phonk_power_override", track_ids)
        self.assertIn("heavy_rock_overdrive", track_ids)
        self.assertIn("comedy_meme_funny", track_ids)
        self.assertIn("epic_hype_glory", track_ids)
        self.assertIn("lofi_chill", track_ids)
        self.assertIn("dynamic_pulse", track_ids)
        self.assertIn("tension_suspense", track_ids)
        self.assertIn("inspirational_epic", track_ids)

    def test_get_track_path_by_id(self):
        lofi_path = get_track_path_by_id("lofi_chill")
        self.assertIsNotNone(lofi_path)
        self.assertTrue(os.path.exists(lofi_path))

        # ID inválido deve acionar fallback seguro para a primeira trilha válida
        fallback_path = get_track_path_by_id("invalid_track_xyz")
        self.assertIsNotNone(fallback_path)
        self.assertTrue(os.path.exists(fallback_path))

    def test_ducking_presets_structure(self):
        for preset_name in ["suave", "medio", "intenso"]:
            self.assertIn(preset_name, DUCKING_PRESETS)
            preset = DUCKING_PRESETS[preset_name]
            self.assertIn("threshold", preset)
            self.assertIn("ratio", preset)
            self.assertIn("attack", preset)
            self.assertIn("release", preset)


if __name__ == '__main__':
    unittest.main()
