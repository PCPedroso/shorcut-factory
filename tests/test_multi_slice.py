import unittest
import os
import shutil
import tempfile
import json
import re
from unittest.mock import patch, MagicMock

from core.library_manager import find_video_slices, add_or_update_video_in_library, remove_video_from_library

class TestMultiSliceSupport(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_data_dir = "data"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_clean_base_video_id(self):
        base_id = "kick_01a12bc9-9a78-7443-b6df-0f453895b31a"
        sliced_id1 = f"{base_id}_t_120_240"
        sliced_id2 = f"{base_id}_t_28838_32438"
        sliced_id3 = f"{base_id}_t_100_200_gol"
        sliced_id4 = f"{base_id}_last15m"

        clean_fn = lambda vid: re.sub(r'_(?:last\d+m|live_snapshot_[a-zA-Z0-9_-]+)$', '', re.sub(r'_t_\d+_(?:end|\d+)(?:_[a-zA-Z0-9_-]+)?$', '', vid))

        self.assertEqual(clean_fn(sliced_id1), base_id)
        self.assertEqual(clean_fn(sliced_id2), base_id)
        self.assertEqual(clean_fn(sliced_id3), base_id)
        self.assertEqual(clean_fn(sliced_id4), base_id)
        self.assertEqual(clean_fn(base_id), base_id)

    def test_find_video_slices_detection(self):
        base_id = "test_stream_abc123"
        slice1 = f"{base_id}_t_60_120"
        slice2 = f"{base_id}_t_300_450"

        with patch("core.library_manager.DATA_DIR", self.test_dir), \
             patch("core.library_manager.get_library") as mock_lib:

            # Create directories on disk
            os.makedirs(os.path.join(self.test_dir, slice1), exist_ok=True)
            with open(os.path.join(self.test_dir, slice1, "video_full.mp4"), "wb") as f:
                f.write(b"0" * 2048)
            with open(os.path.join(self.test_dir, slice1, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump({"title": "Trecho 1 (00:01:00 - 00:02:00)", "duration_sec": 60}, f)

            os.makedirs(os.path.join(self.test_dir, slice2), exist_ok=True)
            with open(os.path.join(self.test_dir, slice2, "video_full.mp4"), "wb") as f:
                f.write(b"0" * 4096)
            with open(os.path.join(self.test_dir, slice2, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump({"title": "Trecho 2 (00:05:00 - 00:07:30)", "duration_sec": 150}, f)

            mock_lib.return_value = [
                {"video_id": slice1, "title": "Trecho 1", "duration_sec": 60},
                {"video_id": slice2, "title": "Trecho 2", "duration_sec": 150}
            ]

            slices = find_video_slices(base_id)
            self.assertEqual(len(slices), 2)
            self.assertEqual(slices[0]["video_id"], slice1)
            self.assertEqual(slices[0]["start_sec"], 60)
            self.assertEqual(slices[0]["end_sec"], 120)
            self.assertTrue(slices[0]["has_video"])

            self.assertEqual(slices[1]["video_id"], slice2)
            self.assertEqual(slices[1]["start_sec"], 300)
            self.assertEqual(slices[1]["end_sec"], 450)
            self.assertTrue(slices[1]["has_video"])

    def test_find_video_slices_when_given_slice_id(self):
        base_id = "test_vod_xyz"
        slice1 = f"{base_id}_t_100_200"
        slice2 = f"{base_id}_t_500_600"

        with patch("core.library_manager.DATA_DIR", self.test_dir), \
             patch("core.library_manager.get_library") as mock_lib:

            mock_lib.return_value = [
                {"video_id": slice1, "title": "Momento 1"},
                {"video_id": slice2, "title": "Momento 2"}
            ]

            # Searching with slice1 ID should still find both slices of base_id!
            slices = find_video_slices(slice1)
            self.assertEqual(len(slices), 2)
            ids = [s["video_id"] for s in slices]
            self.assertIn(slice1, ids)
            self.assertIn(slice2, ids)

if __name__ == '__main__':
    unittest.main()
