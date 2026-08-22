import unittest
from core.analyzer import (
    parse_time_str_to_seconds,
    format_seconds_to_time,
    format_duration_human,
    _clean_ai_title
)


class TestAnalyzerUtils(unittest.TestCase):

    def test_parse_time_str_to_seconds(self):
        self.assertEqual(parse_time_str_to_seconds("00:01:30"), 90.0)
        self.assertEqual(parse_time_str_to_seconds("01:00:00"), 3600.0)
        self.assertEqual(parse_time_str_to_seconds("02:15"), 135.0)
        self.assertEqual(parse_time_str_to_seconds("45"), 45.0)

    def test_format_seconds_to_time(self):
        self.assertEqual(format_seconds_to_time(90), "00:01:30")
        self.assertEqual(format_seconds_to_time(3665), "01:01:05")
        self.assertEqual(format_seconds_to_time(0), "00:00:00")

    def test_format_duration_human(self):
        self.assertEqual(format_duration_human(90), "1m 30s")
        self.assertEqual(format_duration_human(45), "45s")
        self.assertEqual(format_duration_human(3600), "60m 00s")

    def test_clean_ai_title(self):
        raw1 = '1. "Título: O Brasil vai entrar em recessão?"'
        clean1 = _clean_ai_title(raw1)
        self.assertNotIn("Título:", clean1)
        self.assertNotIn('"', clean1)
        self.assertFalse(clean1.startswith("1."))

        raw2 = "Aqui estão os cortes: Renan Santos desafia o sistema"
        clean2 = _clean_ai_title(raw2)
        self.assertNotIn("Aqui estão", clean2)


if __name__ == '__main__':
    unittest.main()
