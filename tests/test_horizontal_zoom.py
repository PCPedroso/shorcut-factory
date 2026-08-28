import os
import cv2
import numpy as np
import pytest
from core.video_processor import cut_video, get_video_resolution
from core.face_tracker import generate_169_preview_image


def create_dummy_169_video(video_path: str, width: int = 1920, height: int = 1080, fps: int = 24, duration_sec: int = 2):
    os.makedirs(os.path.dirname(os.path.abspath(video_path)), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    total_frames = fps * duration_sec

    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)
        cv2.rectangle(frame, (width // 4, height // 4), (3 * width // 4, 3 * height // 4), (0, 255, 0), -1)
        cv2.rectangle(frame, (10, 10), (width - 10, height - 10), (0, 0, 255), 4)
        out.write(frame)

    out.release()


def test_generate_169_preview_image(tmp_path):
    dummy_vid = str(tmp_path / "dummy_169.mp4")
    create_dummy_169_video(dummy_vid)

    preview_path = str(tmp_path / "prev_169.jpg")
    res = generate_169_preview_image(dummy_vid, "00:00:01", preview_path, zoom_factor=1.15)
    
    assert res.get("error") is None
    assert res.get("path") == preview_path
    assert os.path.exists(preview_path)
    
    img = cv2.imread(preview_path)
    assert img is not None
    assert img.shape[0] == 1080
    assert img.shape[1] == 1920


def test_cut_video_with_horizontal_zoom(tmp_path):
    dummy_vid = str(tmp_path / "dummy_169_cut.mp4")
    create_dummy_169_video(dummy_vid)

    out_vid = str(tmp_path / "corte_169_zoomed.mp4")
    res = cut_video(
        dummy_vid,
        "00:00:00",
        "00:00:01",
        output_path=out_vid,
        aspect_ratio_mode="16:9",
        horizontal_zoom=1.20,
        thumbnail_enabled=False
    )

    assert res.get("error") is None
    assert os.path.exists(out_vid)
    assert os.path.getsize(out_vid) > 0
    assert get_video_resolution(out_vid) == "1920x1080"
