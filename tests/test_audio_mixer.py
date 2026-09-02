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
    def test_clean_music_title_and_category_detection(self):
        from core.extractor import clean_music_title, detect_music_category_suggestion

        raw1 = "KSLV - Override (Official Music Video) [4K] #shorts"
        clean1 = clean_music_title(raw1)
        self.assertEqual(clean1, "KSLV - Override")
        cat1_lbl, cat1_key = detect_music_category_suggestion(clean1)
        self.assertEqual(cat1_key, "custom")  # KSLV override

        raw2 = "Brazilian Phonk Extreme Gym Workout Music (Slowed + Reverb)"
        clean2 = clean_music_title(raw2)
        self.assertNotIn("Slowed", clean2)
        cat2_lbl, cat2_key = detect_music_category_suggestion(clean2)
        self.assertEqual(cat2_key, "phonk_power_override")

        raw3 = "Funny Comedy Meme Sound Effects Pack (Free Download)"
        clean3 = clean_music_title(raw3)
        cat3_lbl, cat3_key = detect_music_category_suggestion(clean3)
        self.assertEqual(cat3_key, "comedy_meme_funny")

    def test_register_custom_audio_track(self):
        from core.audio_mixer import register_custom_audio_track, ASSETS_AUDIO_DIR
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            tf.write(b"fake audio mp3 bytes for test")
            tf_path = tf.name

        try:
            res = register_custom_audio_track(
                source_path=tf_path,
                title="Meu Phonk Épico Teste",
                category_name="⚡ Phonk / Superação & Força",
                description="Trilha de teste"
            )
            self.assertIsNone(res.get("error"))
            self.assertIsNotNone(res.get("track"))
            track = res["track"]
            self.assertTrue(os.path.exists(track["path"]))
            self.assertEqual(track["title"], "Meu Phonk Épico Teste")

            # Verifica list_available_tracks
            tracks = list_available_tracks()
            found = any(t["id"] == track["id"] for t in tracks)
            self.assertTrue(found)
        finally:
            if os.path.exists(tf_path):
                try:
                    os.remove(tf_path)
                except Exception:
                    pass


if __name__ == '__main__':
    unittest.main()
