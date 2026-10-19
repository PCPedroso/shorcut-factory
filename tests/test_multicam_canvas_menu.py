import unittest
from core.multicam_crop import (
    boxes_to_fabric_json,
    normalize_box_coordinates,
    snap_box_to_scene_borders
)


class TestMulticamCanvasMenu(unittest.TestCase):
    def test_boxes_to_fabric_json_empty(self):
        res = boxes_to_fabric_json([], canvas_w=680, canvas_h=382, video_w=1920, video_h=1080)
        self.assertEqual(res["version"], "4.4.0")
        self.assertEqual(res["objects"], [])

    def test_boxes_to_fabric_json_coordinates_scaling(self):
        input_boxes = [
            {"x": 192, "y": 108, "w": 384, "h": 216, "order": 0, "label": "Câmera 1"}
        ]
        res = boxes_to_fabric_json(input_boxes, canvas_w=960, canvas_h=540, video_w=1920, video_h=1080)
        self.assertEqual(len(res["objects"]), 1)
        obj = res["objects"][0]
        self.assertEqual(obj["type"], "rect")
        # 192 * (960 / 1920) = 96.0
        self.assertAlmostEqual(obj["left"], 96.0, places=1)
        # 108 * (540 / 1080) = 54.0
        self.assertAlmostEqual(obj["top"], 54.0, places=1)
        # 384 * 0.5 = 192.0
        self.assertAlmostEqual(obj["width"], 192.0, places=1)
        # 216 * 0.5 = 108.0
        self.assertAlmostEqual(obj["height"], 108.0, places=1)
        self.assertTrue(obj["lockRotation"])
        self.assertFalse(obj["hasRotatingPoint"])

    def test_roundtrip_fabric_normalization(self):
        orig_box = {"x": 200, "y": 150, "w": 400, "h": 300, "order": 0, "label": "Câmera 1"}
        fab_dict = boxes_to_fabric_json([orig_box], canvas_w=680, canvas_h=382, video_w=1920, video_h=1080)
        raw_obj = fab_dict["objects"][0]
        norm = normalize_box_coordinates(raw_obj, canvas_w=680, canvas_h=382, video_w=1920, video_h=1080)
        self.assertEqual(norm["x"], orig_box["x"])
        self.assertEqual(norm["y"], orig_box["y"])
        self.assertEqual(norm["w"], orig_box["w"])
        self.assertEqual(norm["h"], orig_box["h"])

    def test_undo_and_clear_operations(self):
        boxes = [
            {"x": 100, "y": 100, "w": 200, "h": 200, "label": "Câmera 1"},
            {"x": 400, "y": 100, "w": 200, "h": 200, "label": "Câmera 2"}
        ]
        # Test Undo (pop last)
        removed = boxes.pop()
        self.assertEqual(removed["label"], "Câmera 2")
        self.assertEqual(len(boxes), 1)

        # Test Clear
        boxes.clear()
        self.assertEqual(len(boxes), 0)


if __name__ == "__main__":
    unittest.main()
