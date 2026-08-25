import unittest
from core.face_tracker import (
    is_dual_interlocutor_shot,
    select_target_face,
    CompositeBoundingBox,
    CompositeFaceDetection
)


class MockBoundingBox:
    def __init__(self, x, y, w, h):
        self.origin_x = x
        self.origin_y = y
        self.width = w
        self.height = h


class MockDetection:
    def __init__(self, x, y, w, h):
        self.bounding_box = MockBoundingBox(x, y, w, h)


class TestFaceTracker(unittest.TestCase):

    def test_is_dual_interlocutor_shot_true(self):
        # Dois oradores: um na esquerda (cx=400) e outro na direita (cx=1000) em frame 1920x1080
        d1 = MockDetection(250, 300, 300, 300)   # cx = 400, cy = 450
        d2 = MockDetection(850, 300, 300, 300)   # cx = 1000, cy = 450
        self.assertTrue(is_dual_interlocutor_shot([d1, d2], 1920, 1080))

    def test_is_dual_interlocutor_shot_single_face_false(self):
        d1 = MockDetection(800, 300, 320, 320)
        self.assertFalse(is_dual_interlocutor_shot([d1], 1920, 1080))

    def test_is_dual_interlocutor_shot_empty_false(self):
        self.assertFalse(is_dual_interlocutor_shot([], 1920, 1080))

    def test_select_target_face_both_speakers(self):
        d1 = MockDetection(200, 250, 250, 250)
        d2 = MockDetection(900, 250, 250, 250)
        target, center = select_target_face([d1, d2], 1920, 1080, person_preference="both")
        self.assertIsNotNone(target)
        # Bounding box composta deve cobrir de 200 até 1150 (largura 950)
        self.assertEqual(target.bounding_box.origin_x, 200)
        self.assertEqual(target.bounding_box.width, 950)
        # Centroide X deve ser (200 + 1150) / 2 = 675
        self.assertEqual(center[0], 675.0)


if __name__ == '__main__':
    unittest.main()
