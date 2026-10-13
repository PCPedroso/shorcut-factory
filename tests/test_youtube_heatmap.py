import os
import shutil
import unittest
from unittest.mock import patch, MagicMock

from core.youtube_heatmap import (
    extract_youtube_video_id,
    extract_initial_data_from_html,
    parse_heatmap_markers,
    fetch_youtube_heatmap,
    find_heatmap_hotspots,
    snap_hotspot_to_segments,
    get_text_for_range,
    intensity_label,
    build_heatmap_cut_items,
    HEATMAP_CACHE_FILENAME,
)


class TestYouTubeHeatmap(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join("tests", "temp_heatmap_test")
        os.makedirs(self.test_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_youtube_video_id(self):
        self.assertEqual(extract_youtube_video_id("dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(
            extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ?t=42"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(
            extract_youtube_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(extract_youtube_video_id("https://vimeo.com/12345678"), "")
        self.assertEqual(extract_youtube_video_id("invalid-string-too-long"), "")
        self.assertEqual(extract_youtube_video_id(""), "")

    def test_extract_initial_data_and_parse_markers_modern(self):
        mock_payload = {
            "frameworkUpdates": {
                "entityBatchUpdate": {
                    "mutations": [
                        {
                            "payload": {
                                "macroMarkersListEntity": {
                                    "markersList": {
                                        "markerType": "MARKER_TYPE_HEATMAP",
                                        "markers": [
                                            {"startMillis": "0", "durationMillis": "10000", "intensityScoreNormalized": 1.0},
                                            {"startMillis": "10000", "durationMillis": "10000", "intensityScoreNormalized": 0.3},
                                            {"startMillis": "20000", "durationMillis": "10000", "intensityScoreNormalized": 0.85},
                                            {"startMillis": "30000", "durationMillis": "10000", "intensityScoreNormalized": 0.90},
                                            {"startMillis": "40000", "durationMillis": "10000", "intensityScoreNormalized": 0.4},
                                        ],
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }
        import json
        html = f"<html><script>var ytInitialData = {json.dumps(mock_payload)};</script></html>"
        extracted = extract_initial_data_from_html(html)
        self.assertIn("frameworkUpdates", extracted)

        markers = parse_heatmap_markers(extracted)
        self.assertEqual(len(markers), 5)
        self.assertEqual(markers[0]["start_sec"], 0.0)
        self.assertEqual(markers[0]["duration_sec"], 10.0)
        self.assertEqual(markers[0]["intensity"], 1.0)
        self.assertEqual(markers[2]["intensity"], 0.85)
        self.assertEqual(markers[3]["start_sec"], 30.0)

    def test_fetch_youtube_heatmap_caching(self):
        mock_html = (
            '<html><script>var ytInitialData = {"frameworkUpdates": {"entityBatchUpdate": {"mutations": ['
            '{"payload": {"macroMarkersListEntity": {"markersList": {"markerType": "MARKER_TYPE_HEATMAP", "markers": ['
            '{"startMillis": "0", "durationMillis": "10000", "intensityScoreNormalized": 0.9}'
            ']}}}}]}}};</script></html>'
        )
        fake_fetcher = MagicMock(return_value=mock_html)

        # 1. Primeira chamada -> busca online
        res = fetch_youtube_heatmap(
            "dQw4w9WgXcQ",
            cache_dir=self.test_dir,
            html_fetcher=fake_fetcher,
        )
        self.assertTrue(res["has_heatmap"])
        self.assertEqual(res["source"], "youtube")
        self.assertEqual(fake_fetcher.call_count, 1)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, HEATMAP_CACHE_FILENAME)))

        # 2. Segunda chamada -> usa cache
        res2 = fetch_youtube_heatmap(
            "dQw4w9WgXcQ",
            cache_dir=self.test_dir,
            html_fetcher=fake_fetcher,
        )
        self.assertTrue(res2["has_heatmap"])
        self.assertEqual(res2["source"], "cache")
        self.assertEqual(fake_fetcher.call_count, 1)  # não chamou de novo!

    def test_find_heatmap_hotspots(self):
        markers = [
            {"start_sec": i * 10, "end_sec": (i + 1) * 10, "duration_sec": 10.0, "intensity": 0.1}
            for i in range(20)
        ]
        # Picos em 50s-70s (indices 5, 6, 7)
        markers[5]["intensity"] = 0.80
        markers[6]["intensity"] = 0.95
        markers[7]["intensity"] = 0.85

        hotspots = find_heatmap_hotspots(
            markers,
            min_duration=30.0,
            max_duration=60.0,
            min_intensity=0.40,
            skip_intro_sec=10.0,
            video_duration=200.0,
        )
        self.assertGreaterEqual(len(hotspots), 1)
        top = hotspots[0]
        self.assertEqual(top["rank"], 1)
        self.assertEqual(top["peak_intensity"], 0.95)
        self.assertGreaterEqual(top["duration_sec"], 30.0)
        self.assertLessEqual(top["duration_sec"], 60.0)
        self.assertLessEqual(top["start_sec"], 60.0)
        self.assertGreaterEqual(top["end_sec"], 70.0)

    def test_snap_hotspot_to_segments(self):
        hotspot = {
            "start_sec": 52.0,
            "end_sec": 84.0,
            "duration_sec": 32.0,
            "peak_sec": 65.0,
            "peak_intensity": 0.95,
        }
        segments = [
            {"start": 48.0, "end": 50.5, "text": "Antes da conversa."},
            {"start": 51.0, "end": 55.0, "text": "Aqui começou a frase chave."},
            {"start": 55.5, "end": 80.0, "text": "Meio do trecho super importante."},
            {"start": 80.5, "end": 85.5, "text": "E concluiu o raciocínio perfeitamente."},
            {"start": 86.0, "end": 90.0, "text": "Próximo assunto diferente."},
        ]
        snapped = snap_hotspot_to_segments(hotspot, segments, max_shift_s=6.0)
        self.assertEqual(snapped["start_sec"], 51.0)
        self.assertEqual(snapped["end_sec"], 85.5)
        self.assertTrue(snapped.get("snapped_to_transcript"))

    def test_get_text_for_range_and_intensity_label(self):
        segments = [
            {"start": 10.0, "end": 15.0, "text": "Olá mundo"},
            {"start": 16.0, "end": 20.0, "text": "este é um teste de legenda"},
        ]
        txt = get_text_for_range(segments, 9.0, 21.0)
        self.assertEqual(txt, "Olá mundo este é um teste de legenda")

        self.assertIn("Pico Máximo", intensity_label(0.92))
        self.assertIn("Muito Quente", intensity_label(0.70))
        self.assertIn("Quente", intensity_label(0.45))
        self.assertIn("Morno", intensity_label(0.20))

    def test_build_heatmap_cut_items(self):
        hotspots = [
            {
                "rank": 1,
                "start": "01:00",
                "end": "01:45",
                "start_sec": 60.0,
                "end_sec": 105.0,
                "duration_sec": 45.0,
                "peak_sec": 80.0,
                "peak_intensity": 0.95,
                "avg_intensity": 0.88,
            }
        ]
        segments = [
            {"start": 62.0, "end": 75.0, "text": "O segredo para criar cortes virais com retenção"},
        ]
        cuts = build_heatmap_cut_items(hotspots, segments)
        self.assertEqual(len(cuts), 1)
        c = cuts[0]
        self.assertEqual(c["source"], "youtube_heatmap")
        self.assertEqual(c["start"], "01:00")
        self.assertEqual(c["end"], "01:45")
        self.assertEqual(c["start_s"], 60.0)
        self.assertEqual(c["end_s"], 105.0)
        self.assertIn("95%", c["type"])
        self.assertIn("O segredo para criar cortes virais", c["snippet"])


if __name__ == "__main__":
    unittest.main()
