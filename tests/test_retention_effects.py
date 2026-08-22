import unittest
from core.retention_effects import (
    generate_zoom_punch_filter,
    attach_contextual_emojis_to_words,
    EMOJI_KEYWORDS
)


class TestRetentionEffects(unittest.TestCase):

    def test_generate_zoom_punch_filter(self):
        filter_str = generate_zoom_punch_filter(duration=30.0, interval=8.5, zoom_factor=1.07)
        self.assertIn("scale=1080:1920", filter_str)
        self.assertIn("crop=w='in_w/if(between(t", filter_str)

        # Se a duração for muito curta (< 5s), não gera filtro desnecessário
        short_filter = generate_zoom_punch_filter(duration=3.0)
        self.assertEqual(short_filter, "")

    def test_attach_contextual_emojis_to_words(self):
        words = [
            {"word": "O", "start": 0.0, "end": 0.3},
            {"word": "dinheiro", "start": 0.3, "end": 0.8},
            {"word": "acabou", "start": 0.8, "end": 1.2}
        ]
        enriched = attach_contextual_emojis_to_words(words)
        self.assertEqual(enriched[1]["word"], "dinheiro 💰")
        self.assertEqual(enriched[0]["word"], "O")


if __name__ == '__main__':
    unittest.main()
