import unittest
import os
import shutil
import json
import io
from unittest.mock import patch, MagicMock
from PIL import Image

from core.extractor import download_video_thumbnail, get_video_components_status
from core.library_manager import (
    add_or_update_video_in_library,
    update_video_thumbnail_in_library,
    get_library,
    LIBRARY_FILE
)


class TestYouTubeThumbnail(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath("test_thumb_data")
        os.makedirs(self.test_dir, exist_ok=True)
        self.orig_lib = None
        if os.path.exists(LIBRARY_FILE):
            try:
                with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                    self.orig_lib = f.read()
            except Exception:
                pass

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        if self.orig_lib is not None:
            try:
                with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                    f.write(self.orig_lib)
            except Exception:
                pass

    def _create_dummy_image_bytes(self, width=640, height=360, color=(255, 0, 0)) -> bytes:
        img = Image.new("RGB", (width, height), color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    def test_download_thumbnail_via_direct_url(self):
        fake_bytes = self._create_dummy_image_bytes()
        out_path = os.path.join(self.test_dir, "thumb_direct.jpg")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_bytes

        with patch("requests.get", return_value=mock_resp) as mock_get:
            res = download_video_thumbnail(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_path=out_path,
                thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
            )
            self.assertTrue(res["success"])
            self.assertTrue(os.path.exists(out_path))
            self.assertGreater(os.path.getsize(out_path), 1000)

            # Valida formato de imagem JPEG
            with Image.open(out_path) as im:
                self.assertEqual(im.format, "JPEG")
                self.assertEqual(im.size, (640, 360))

    def test_download_thumbnail_youtube_cdn_fallback(self):
        fake_bytes = self._create_dummy_image_bytes(color=(0, 255, 0))
        out_path = os.path.join(self.test_dir, "thumb_fallback.jpg")

        def side_effect(url, **kwargs):
            mock = MagicMock()
            if "maxresdefault.jpg" in url:
                mock.status_code = 404
                mock.content = b"Not found"
            elif "hqdefault.jpg" in url:
                mock.status_code = 200
                mock.content = fake_bytes
            else:
                mock.status_code = 404
                mock.content = b""
            return mock

        with patch("requests.get", side_effect=side_effect):
            res = download_video_thumbnail(
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                output_path=out_path,
                thumbnail_url=None
            )
            self.assertTrue(res["success"])
            self.assertTrue(os.path.exists(out_path))

    def test_redownload_restores_modified_or_deleted_thumbnail(self):
        out_path = os.path.join(self.test_dir, "thumb_restore.jpg")
        fake_bytes_v1 = self._create_dummy_image_bytes(color=(255, 0, 0))
        fake_bytes_v2 = self._create_dummy_image_bytes(color=(0, 0, 255))

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_bytes_v1

        with patch("requests.get", return_value=mock_resp):
            res1 = download_video_thumbnail("https://youtu.be/dQw4w9WgXcQ", out_path)
            self.assertTrue(res1["success"])
            self.assertTrue(os.path.exists(out_path))

        # 1. Simula usuário deletando o arquivo
        os.remove(out_path)
        self.assertFalse(os.path.exists(out_path))

        # 2. Rebaixa / restaura novamente
        mock_resp.content = fake_bytes_v2
        with patch("requests.get", return_value=mock_resp):
            res2 = download_video_thumbnail("https://youtu.be/dQw4w9WgXcQ", out_path)
            self.assertTrue(res2["success"])
            self.assertTrue(os.path.exists(out_path))
            self.assertGreater(os.path.getsize(out_path), 1000)

    def test_get_video_components_status_with_thumbnail(self):
        vid = "vid_test_thumb"
        v_dir = os.path.join(self.test_dir, vid)
        os.makedirs(v_dir, exist_ok=True)

        # Sem thumbnail
        status_empty = get_video_components_status(vid, data_dir=self.test_dir)
        self.assertFalse(status_empty["has_thumbnail"])
        self.assertIsNone(status_empty["thumbnail_path"])
        self.assertIn("thumbnail", status_empty["missing_components"])

        # Cria thumbnail válida
        t_path = os.path.join(v_dir, "thumbnail.jpg")
        with open(t_path, "wb") as f:
            f.write(self._create_dummy_image_bytes())

        status_full = get_video_components_status(vid, data_dir=self.test_dir)
        self.assertTrue(status_full["has_thumbnail"])
        self.assertEqual(os.path.abspath(status_full["thumbnail_path"]), os.path.abspath(t_path))
        self.assertNotIn("thumbnail", status_full["missing_components"])

    def test_update_video_thumbnail_in_library(self):
        vid = "vid_lib_thumb_test"
        v_dir = os.path.join(self.test_dir, vid)
        os.makedirs(v_dir, exist_ok=True)

        # Mock DATA_DIR na biblioteca apontando para self.test_dir
        with patch("core.library_manager.DATA_DIR", self.test_dir):
            add_or_update_video_in_library(
                video_id=vid,
                title="Vídeo com Thumbnail",
                upload_date_raw="01/01/2026",
                url="https://youtube.com/watch?v=123",
                thumbnail_url=None
            )

            # Atualiza thumbnail
            thumb_path = os.path.join(v_dir, "thumbnail.jpg")
            ok = update_video_thumbnail_in_library(vid, thumb_path)
            self.assertTrue(ok)

            lib = get_library()
            item = next((v for v in lib if v.get("video_id") == vid), None)
            self.assertIsNotNone(item)
            self.assertEqual(item["thumbnail"], thumb_path)


if __name__ == "__main__":
    unittest.main()
