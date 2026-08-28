import unittest
from core.headline_drawer import (
    clean_and_condense_headline,
    format_headline_text,
    hex_to_ass_color,
    build_ass_headline_style,
    HEADLINE_PRESETS,
    DANGLING_ENDINGS
)


class TestHeadlineDrawer(unittest.TestCase):

    def test_hex_to_ass_color(self):
        # Hex #FFE600 (Yellow) -> ASS format &H0000E6FF& (&HAABBGGRR&)
        ass_col = hex_to_ass_color("#FFE600", alpha=0.0)
        self.assertEqual(ass_col, "&H0000E6FF&")

        # Hex #000000 (Black)
        ass_black = hex_to_ass_color("#000000", alpha=0.0)
        self.assertEqual(ass_black, "&H00000000&")

        # Hex #FFFFFF (White)
        ass_white = hex_to_ass_color("#FFFFFF", alpha=0.0)
        self.assertEqual(ass_white, "&H00FFFFFF&")

    def test_clean_and_condense_headline_removes_speaker_prefixes(self):
        raw = "Candidato desafia a crise econômica vou pegar o país quebrado e resolver tudo"
        cleaned = clean_and_condense_headline(raw, max_chars=75)
        self.assertFalse(cleaned.startswith("CANDIDATO"))
        self.assertIn("PAÍS QUEBRADO", cleaned)

    def test_clean_and_condense_headline_no_dangling_endings(self):
        raw = "Renan Santos nós estamos destruídos por esses caras, tomados pelo"
        cleaned = clean_and_condense_headline(raw, max_chars=40)
        last_word = cleaned.split()[-1].rstrip('.,!?:')
        self.assertNotIn(last_word, DANGLING_ENDINGS)
        self.assertNotEqual(last_word, "PELO")
        self.assertNotEqual(last_word, "E")
        self.assertNotEqual(last_word, "DA")

    def test_clean_and_condense_headline_preserves_questions(self):
        raw = "Como convencer eleitores de 60 anos? Candidato responde com franqueza"
        cleaned = clean_and_condense_headline(raw, max_chars=75)
        self.assertTrue(cleaned.endswith("?") or "ELEITORES" in cleaned)

    def test_format_headline_text_two_lines_and_uppercase(self):
        raw = "Vou pegar o país quebrado e resolver tudo"
        formatted = format_headline_text(raw, max_width_chars=24, max_lines=3)
        lines = formatted.split(r"\N")
        self.assertLessEqual(len(lines), 3)
        self.assertEqual(formatted, formatted.upper())
        for line in lines:
            self.assertFalse(line.split()[-1].rstrip('.,!?:') in DANGLING_ENDINGS)

    def test_build_ass_headline_style(self):
        style = build_ass_headline_style(preset_key="yellow_black", font_size=46, margin_top=120)
        self.assertIn("Style: Headline", style)
        self.assertIn("Montserrat ExtraBold", style)
        self.assertIn("46", style)
        self.assertIn("120", style)

    def test_custom_headline_style(self):
        style = build_ass_headline_style(
            preset_key="custom",
            custom_text_color="#FF0000",
            custom_bg_color="#00FF00",
            font_size=50,
            margin_top=100
        )
        self.assertIn("Style: Headline", style)
        self.assertIn("50", style)


if __name__ == '__main__':
    unittest.main()
