import os
import unittest
import numpy as np
import cv2
from core.quick_editor import (
    get_video_duration,
    extract_frame_at_timestamp,
    trim_video,
    remove_snippet_and_merge,
    change_video_speed,
    apply_static_image_to_video,
    detect_cut_aspect_mode,
    build_static_image_filter
)


class TestQuickEditor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = "tests/temp_quick_editor"
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.sample_video = os.path.join(cls.test_dir, "sample_test.mp4")

        # Gera um vídeo sintético de 6 segundos (1280x720 @ 30fps) com áudio silencioso via OpenCV/FFmpeg
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(cls.sample_video, fourcc, 30.0, (640, 360))
        for i in range(180): # 6 segundos * 30 fps
            # Frame colorido mudando com o tempo
            color = int((i / 180.0) * 255)
            frame = np.full((360, 640, 3), color, dtype=np.uint8)
            cv2.putText(frame, f"Frame {i}", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            out.write(frame)
        out.release()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            try:
                import shutil
                shutil.rmtree(cls.test_dir)
            except Exception:
                pass

    def test_get_video_duration(self):
        dur = get_video_duration(self.sample_video)
        self.assertAlmostEqual(dur, 6.0, delta=0.5)

    def test_extract_frame_at_timestamp(self):
        frame = extract_frame_at_timestamp(self.sample_video, 2.5)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (360, 640, 3))

    def test_trim_video(self):
        out_trim = os.path.join(self.test_dir, "trimmed.mp4")
        res = trim_video(self.sample_video, start_s=1.0, end_s=4.0, output_path=out_trim)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_trim))
        dur = get_video_duration(out_trim)
        self.assertAlmostEqual(dur, 3.0, delta=0.5)

    def test_remove_snippet_and_merge(self):
        out_snip = os.path.join(self.test_dir, "snipped.mp4")
        # Remove do segundo 2.0 ao 4.0 de um vídeo de 6.0s -> resultado ~4.0s
        res = remove_snippet_and_merge(self.sample_video, remove_start_s=2.0, remove_end_s=4.0, output_path=out_snip)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_snip))
        dur = get_video_duration(out_snip)
        self.assertAlmostEqual(dur, 4.0, delta=0.8)

    def test_edit_history_logging(self):
        from core.quick_editor import get_edit_history_path, load_edit_history, record_quick_edit
        
        log_path = get_edit_history_path(self.sample_video)
        self.assertTrue(log_path.endswith("historico_edicoes.json"))

        entry1 = record_quick_edit(
            video_path=self.sample_video,
            action_name="✂️ Aparar (Trim)",
            details="Início: 1.0s | Fim: 4.0s (Duração: 3.0s)",
            output_path=None
        )
        self.assertEqual(entry1["action"], "✂️ Aparar (Trim)")
        self.assertEqual(entry1["mode"], "Substituição Direta")

        entry2 = record_quick_edit(
            video_path=self.sample_video,
            action_name="🏷️ Headline de Topo",
            details="Texto: 'TESTE HEADLINE'",
            output_path=os.path.join(self.test_dir, "sample_test_headline.mp4")
        )
        self.assertEqual(entry2["mode"], "Nova Versão")

        history = load_edit_history(self.sample_video)
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]["action"], "🏷️ Headline de Topo")
        self.assertEqual(history[1]["action"], "✂️ Aparar (Trim)")

    def test_change_video_speed(self):
        out_speed = os.path.join(self.test_dir, "sped_up.mp4")
        # Aumenta velocidade para 1.25x em vídeo de ~6.0s -> nova duração ~4.8s
        res = change_video_speed(self.sample_video, speed=1.25, output_path=out_speed)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_speed))
        dur = get_video_duration(out_speed)
        self.assertAlmostEqual(dur, 4.8, delta=0.8)

    def test_version_listing_and_deletion(self):
        from core.quick_editor import (
            list_edited_video_versions,
            delete_edited_video_version,
            cleanup_all_edited_versions,
            record_quick_edit,
            load_edit_history
        )

        # 1. Cria uma versão secundária editada
        ver_path = os.path.join(self.test_dir, "sample_test_speed_1.20x.mp4")
        res = change_video_speed(self.sample_video, speed=1.20, output_path=ver_path)
        self.assertTrue(os.path.exists(ver_path))

        record_quick_edit(
            video_path=self.sample_video,
            action_name="⚡ Aceleração",
            details="1.20x",
            output_path=ver_path
        )

        # 2. Lista versões
        versions = list_edited_video_versions(self.sample_video)
        filenames = [v["filename"] for v in versions]
        self.assertIn("sample_test_speed_1.20x.mp4", filenames)

        # 3. Deleta versão secundária individual
        del_res = delete_edited_video_version(ver_path)
        self.assertTrue(del_res["success"])
        self.assertFalse(os.path.exists(ver_path))

        # 4. Cria múltiplas versões secundárias e testa cleanup_all
        v2 = os.path.join(self.test_dir, "sample_test_editado.mp4")
        v3 = os.path.join(self.test_dir, "sample_test_com_banner.mp4")
        trim_video(self.sample_video, 1.0, 3.0, output_path=v2)
        trim_video(self.sample_video, 1.0, 3.0, output_path=v3)
        self.assertTrue(os.path.exists(v2))
        self.assertTrue(os.path.exists(v3))

        clean_res = cleanup_all_edited_versions(self.sample_video, keep_path=self.sample_video)
        self.assertTrue(clean_res["success"])
        self.assertFalse(os.path.exists(v2))
        self.assertFalse(os.path.exists(v3))
        self.assertTrue(os.path.exists(self.sample_video))

    def test_apply_static_image_to_video_new_file(self):
        img_path = os.path.join(self.test_dir, "sample_img.jpg")
        img = np.zeros((500, 500, 3), dtype=np.uint8)
        img[:, :] = (255, 120, 0)
        cv2.imwrite(img_path, img)

        out_static = os.path.join(self.test_dir, "sample_static.mp4")
        res = apply_static_image_to_video(self.sample_video, img_path, output_path=out_static)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_static))

        dur = get_video_duration(out_static)
        self.assertAlmostEqual(dur, 6.0, delta=0.5)

        cap = cv2.VideoCapture(out_static)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)

    def test_apply_static_image_to_video_in_place(self):
        import shutil
        temp_copy = os.path.join(self.test_dir, "sample_inplace.mp4")
        shutil.copy2(self.sample_video, temp_copy)

        img_path = os.path.join(self.test_dir, "sample_img_inplace.png")
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        img[:, :] = (0, 255, 100)
        cv2.imwrite(img_path, img)

        res = apply_static_image_to_video(temp_copy, img_path)
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(temp_copy))

        dur = get_video_duration(temp_copy)
        self.assertAlmostEqual(dur, 6.0, delta=0.5)

    def test_apply_static_image_missing_files(self):
        res1 = apply_static_image_to_video("inexistente.mp4", "img.jpg")
        self.assertIsNotNone(res1.get("error"))

        res2 = apply_static_image_to_video(self.sample_video, "inexistente.jpg")
        self.assertIsNotNone(res2.get("error"))

    def test_detect_cut_aspect_mode(self):
        self.assertEqual(detect_cut_aspect_mode("data/v1/VFDBS_Corte_1/VFDBS_Corte_1.mp4"), "9:16_blur")
        self.assertEqual(detect_cut_aspect_mode("data/v1/VCCFT_Corte_2/video.mp4"), "9:16_crop")
        self.assertEqual(detect_cut_aspect_mode("data/v1/VRIRA_Corte_3/VRIRA_Corte_3.mp4"), "9:16_smart_face")
        self.assertEqual(detect_cut_aspect_mode("data/v1/VLDSS_Corte_4/split.mp4"), "9:16_split")
        self.assertEqual(detect_cut_aspect_mode("data/v1/HOFHD_Corte_5/corte.mp4"), "16:9")

    def test_apply_static_image_with_format_blur_9_16(self):
        # Imagem horizontal (16:9) adaptada ao formato 9:16 Blur
        img_path = os.path.join(self.test_dir, "horizontal_img.jpg")
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        img[:, :] = (0, 180, 255)
        cv2.imwrite(img_path, img)

        out_blur = os.path.join(self.test_dir, "static_blur_916.mp4")
        res = apply_static_image_to_video(
            self.sample_video,
            img_path,
            output_path=out_blur,
            aspect_mode="9:16_blur"
        )
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_blur))
        self.assertEqual(res.get("aspect_mode"), "9:16_blur")

        cap = cv2.VideoCapture(out_blur)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self.assertEqual(w, 1080)
        self.assertEqual(h, 1920)

    def test_apply_static_image_with_format_16_9(self):
        img_path = os.path.join(self.test_dir, "any_img.jpg")
        img = np.zeros((500, 500, 3), dtype=np.uint8)
        img[:, :] = (100, 200, 50)
        cv2.imwrite(img_path, img)

        out_169 = os.path.join(self.test_dir, "static_169.mp4")
        res = apply_static_image_to_video(
            self.sample_video,
            img_path,
            output_path=out_169,
            aspect_mode="16:9"
        )
        self.assertIsNone(res.get("error"))
        self.assertTrue(os.path.exists(out_169))

        cap = cv2.VideoCapture(out_169)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self.assertEqual(w, 1920)
        self.assertEqual(h, 1080)


if __name__ == '__main__':
    unittest.main()


