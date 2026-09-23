import os
import shutil
import tempfile
import subprocess
import pytest
import numpy as np
import cv2
import imageio_ffmpeg

from core.video_processor import (
    replace_video_with_static_image,
    restore_original_video_from_backup,
    has_original_video_backup,
    check_has_audio_stream
)

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


class TestStaticImageVideo:

    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    def _create_synthetic_video_with_audio(self, duration_s=2.0, width=320, height=240):
        video_path = os.path.join(self.temp_dir, "test_video.mp4")
        cmd = [
            FFMPEG_EXE, "-y",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_s}",
            "-f", "lavfi", "-i", f"testsrc=duration={duration_s}:size={width}x{height}:rate=30",
            "-c:v", "libx264", "-c:a", "aac",
            video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"FFmpeg failed: {res.stderr}"
        return video_path

    def _create_synthetic_image(self, width=401, height=401):
        image_path = os.path.join(self.temp_dir, "test_image.jpg")
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:, :] = (0, 165, 255)  # Laranja BGR
        cv2.imwrite(image_path, img)
        return image_path

    def test_replace_video_with_static_image_success(self):
        v_path = self._create_synthetic_video_with_audio(duration_s=2.0)
        img_path = self._create_synthetic_image(width=401, height=401)  # dimensões ímpares

        res = replace_video_with_static_image(v_path, img_path, backup=True)
        assert res["success"] is True
        assert res["error"] is None
        assert os.path.exists(v_path)
        assert res["backup_path"] is not None
        assert os.path.exists(res["backup_path"])

        # Verifica dimensões ajustadas para pares (400x400)
        cap = cv2.VideoCapture(v_path)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        assert w % 2 == 0
        assert h % 2 == 0
        assert w == 400
        assert h == 400

        # Verifica preservação de áudio
        assert check_has_audio_stream(v_path) is True
        assert has_original_video_backup(v_path) is True

    def test_restore_original_video_from_backup(self):
        v_path = self._create_synthetic_video_with_audio(duration_s=2.0, width=320, height=240)
        img_path = self._create_synthetic_image(width=600, height=600)

        # Substitui
        res_replace = replace_video_with_static_image(v_path, img_path, backup=True)
        assert res_replace["success"] is True

        cap = cv2.VideoCapture(v_path)
        assert int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) == 600
        cap.release()

        # Restaura
        res_restore = restore_original_video_from_backup(v_path)
        assert res_restore["success"] is True
        assert res_restore["error"] is None

        # Confere que voltou a 320x240
        cap2 = cv2.VideoCapture(v_path)
        assert int(cap2.get(cv2.CAP_PROP_FRAME_WIDTH)) == 320
        assert int(cap2.get(cv2.CAP_PROP_FRAME_HEIGHT)) == 240
        cap2.release()

    def test_replace_video_missing_file_errors(self):
        res1 = replace_video_with_static_image("arquivo_inexistente.mp4", "img.jpg")
        assert res1["success"] is False
        assert "não encontrado" in res1["error"]

        v_path = self._create_synthetic_video_with_audio(duration_s=1.0)
        res2 = replace_video_with_static_image(v_path, "img_inexistente.jpg")
        assert res2["success"] is False
        assert "não encontrado" in res2["error"]
