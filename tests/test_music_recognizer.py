import unittest
from core.music_recognizer import (
    is_generic_video_title,
    extract_music_from_description,
    identify_song_from_audio_and_meta
)


class TestMusicRecognizer(unittest.TestCase):

    def test_generic_title_detection(self):
        # Títulos genéricos de redes sociais devem ser filtrados
        self.assertTrue(is_generic_video_title("Video by dosesdepsico"))
        self.assertTrue(is_generic_video_title("post by usuario123"))
        self.assertTrue(is_generic_video_title("reel by perfil_oficial"))
        self.assertTrue(is_generic_video_title("TikTok Video by creator"))
        self.assertTrue(is_generic_video_title("som original - dosesdepsico"))
        self.assertTrue(is_generic_video_title("Vídeo de perfil"))
        self.assertTrue(is_generic_video_title(""))

        # Títulos reais de músicas NÃO devem ser filtrados
        self.assertFalse(is_generic_video_title("Iron Maiden - Fear of the Dark"))
        self.assertFalse(is_generic_video_title("Kordhell - Murder In My Mind"))
        self.assertFalse(is_generic_video_title("Metallica - Master of Puppets"))

    def test_extract_music_from_description(self):
        desc1 = "Confira este momento incrível! Música: Iron Maiden - Fear of the Dark #rock #metal"
        res1 = extract_music_from_description(desc1)
        self.assertEqual(res1, "Iron Maiden - Fear of the Dark")

        desc2 = "Treino insano de hoje 🎵 Kordhell - Murder In My Mind #gym #phonk"
        res2 = extract_music_from_description(desc2)
        self.assertEqual(res2, "Kordhell - Murder In My Mind")

        desc3 = "Apenas uma conversa sem trilha aqui."
        res3 = extract_music_from_description(desc3)
        self.assertIsNone(res3)

    def test_identify_song_with_official_metadata(self):
        meta = {
            "title": "Video by dosesdepsico",
            "track": "Fear of the Dark",
            "artist": "Iron Maiden"
        }
        res = identify_song_from_audio_and_meta(audio_path=None, meta=meta, use_ai=False)
        self.assertEqual(res["music_title"], "Iron Maiden - Fear of the Dark")
        self.assertEqual(res["source"], "Metadados Oficiais")

    def test_identify_song_with_description_fallback(self):
        meta = {
            "title": "Video by dosesdepsico",
            "description": "Edição insana com a música Iron Maiden - Fear of the Dark"
        }
        res = identify_song_from_audio_and_meta(audio_path=None, meta=meta, use_ai=False)
        self.assertEqual(res["music_title"], "Iron Maiden - Fear of the Dark")
        self.assertEqual(res["source"], "Descrição do Post")


if __name__ == '__main__':
    unittest.main()
