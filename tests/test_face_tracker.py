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
    def test_filter_prominent_faces_ignores_libras(self):
        from core.face_tracker import filter_prominent_faces
        # Orador 1 (Renan): 300x300 (área 90.000)
        d1 = MockDetection(250, 300, 300, 300)
        # Orador 2 (Curi): 300x300 (área 90.000)
        d2 = MockDetection(850, 300, 300, 300)
        # Intérprete LIBRAS no canto direito: 70x70 (área 4.900 -> 5.4% do maior orador)
        d_libras = MockDetection(1650, 600, 70, 70)

        prominent = filter_prominent_faces([d1, d2, d_libras], 1920, 1080)
        self.assertEqual(len(prominent), 2)
        self.assertIn(d1, prominent)
        self.assertIn(d2, prominent)
        self.assertNotIn(d_libras, prominent)

    def test_select_target_face_right_ignores_libras(self):
        # Orador esquerda: x=250, cx=400
        d_left = MockDetection(250, 300, 300, 300)
        # Orador direita (entrevistado principal): x=850, cx=1000
        d_right = MockDetection(850, 300, 300, 300)
        # Intérprete LIBRAS na extrema direita: x=1650, cx=1685 (pequeno)
        d_libras = MockDetection(1650, 600, 70, 70)

        target, center = select_target_face([d_left, d_right, d_libras], 1920, 1080, person_preference="right")
        # Deve selecionar d_right (Curi), NÃO d_libras
        self.assertEqual(target, d_right)
        self.assertEqual(center[0], 1000.0)


if __name__ == '__main__':
    unittest.main()
