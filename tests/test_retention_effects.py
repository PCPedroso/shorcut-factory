import unittest
from core.retention_effects import (
    generate_zoom_punch_filter,
    attach_contextual_emojis_to_words,
    generate_progress_bar_filter,
    generate_climax_zoom_filter,
    generate_engagement_callout_ass_dialogue,
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

    def test_generate_progress_bar_filter(self):
        pb_filter = generate_progress_bar_filter(duration=45.0, color_hex="#FF0000", height_px=8)
        self.assertIn("drawbox=x=0:y=ih-8:w=iw:h=8:color=0x000000", pb_filter)
        self.assertIn("drawbox=x=0:y=ih-8:w='min(iw,iw*(t/45.0))':h=8:color=0xFF0000@1:t=fill", pb_filter)

        # Se duração for menor ou igual a 1s, retorna vazio
        empty_pb = generate_progress_bar_filter(duration=0.5)
        self.assertEqual(empty_pb, "")

    def test_generate_climax_zoom_filter(self):
        climax_f = generate_climax_zoom_filter(duration=30.0, climax_duration=3.5, zoom_factor=1.14)
        self.assertIn("between(t,26.5,30.0)", climax_f)
        self.assertIn("1.14", climax_f)
        self.assertIn("scale=1080:1920", climax_f)

        # Duração curta (< 5s) não aplica
        empty_climax = generate_climax_zoom_filter(duration=4.0)
        self.assertEqual(empty_climax, "")

    def test_generate_engagement_callout_ass_dialogue(self):
        dialogue = generate_engagement_callout_ass_dialogue(
            duration=30.0,
            callout_text="💬 O que você acha? Comente!",
            callout_duration=4.0
        )
        self.assertIn("Dialogue: 0,", dialogue)
        self.assertIn("CalloutStyle", dialogue)
        self.assertIn(r"{\fad(300,300)}💬 O que você acha? Comente!", dialogue)

        # Texto vazio ou duração muito curta
        self.assertEqual(generate_engagement_callout_ass_dialogue(duration=20.0, callout_text=""), "")
        self.assertEqual(generate_engagement_callout_ass_dialogue(duration=2.0, callout_text="Teste"), "")


if __name__ == '__main__':
    unittest.main()

