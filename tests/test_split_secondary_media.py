import os
import numpy as np
import cv2
import pytest
from core.face_tracker import fit_frame_to_slot, load_images_for_slideshow, generate_split_preview_image

def test_fit_frame_to_slot():
    # Test aspect fill resize and center crop
    sample = np.zeros((720, 1280, 3), dtype=np.uint8)
    sample[:, :] = (255, 0, 0)
    slot = fit_frame_to_slot(sample, target_w=1080, target_h=960)
    assert slot.shape == (960, 1080, 3)

def test_load_images_for_slideshow(tmp_path):
    img1_path = str(tmp_path / "img1.jpg")
    img2_path = str(tmp_path / "img2.png")
    
    cv2.imwrite(img1_path, np.zeros((400, 400, 3), dtype=np.uint8))
    cv2.imwrite(img2_path, np.ones((500, 800, 3), dtype=np.uint8) * 128)
    
    frames = load_images_for_slideshow([img1_path, img2_path], target_w=1080, target_h=960)
    assert len(frames) == 2
    assert frames[0].shape == (960, 1080, 3)
    assert frames[1].shape == (960, 1080, 3)

def test_generate_split_preview_with_slideshow(tmp_path):
    video_path = str(tmp_path / "dummy_main.mp4")
    # Cria vídeo dummy curto de 1 segundo
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 10.0, (640, 360))
    for _ in range(10):
        out.write(np.ones((360, 640, 3), dtype=np.uint8) * 100)
    out.release()

    img_path = str(tmp_path / "slide1.jpg")
    cv2.imwrite(img_path, np.ones((300, 300, 3), dtype=np.uint8) * 200)

    preview_path = str(tmp_path / "preview.jpg")
    res = generate_split_preview_image(
        input_video_path=video_path,
        timestamp_str="00:00:00",
        output_preview_path=preview_path,
        split_source_type="images",
        split_image_paths=[img_path],
        split_media_position="bottom",
        split_blur_margin_pct=5.0
    )
    assert res.get("error") is None
    assert os.path.exists(preview_path)
    img_res = cv2.imread(preview_path)
    assert img_res.shape == (1920, 1080, 3)

def test_generate_split_preview_with_blur_margin(tmp_path):
    video_path = str(tmp_path / "dummy_main_margin.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 10.0, (640, 360))
    for _ in range(10):
        out.write(np.ones((360, 640, 3), dtype=np.uint8) * 150)
    out.release()

    preview_path = str(tmp_path / "preview_margin.jpg")
    res = generate_split_preview_image(
        input_video_path=video_path,
        timestamp_str="00:00:00",
        output_preview_path=preview_path,
        split_source_type="main_video",
        split_blur_margin_pct=8.0
    )
    assert res.get("error") is None
    assert os.path.exists(preview_path)
    img_res = cv2.imread(preview_path)
    assert img_res.shape == (1920, 1080, 3)

def test_extract_proportional_crop_no_anamorphic_distortion():
    from core.face_tracker import extract_proportional_crop
    # Cria uma imagem 1920x1080 com um círculo perfeitamente simétrico no centro
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    cv2.circle(frame, (960, 540), 200, (255, 255, 255), -1)

    # Simula o slot do usuário com margem de 20% (target_w=1080, slot_h=576) e zoom=1.5x
    cropped = extract_proportional_crop(frame, target_w=1080, target_h=576, zoom=1.50, pan_x=0.0, pan_y=0.0)
    assert cropped.shape == (576, 1080, 3)

    # Mede a proporção do círculo na imagem resultante
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    white_pts = np.where(gray > 200)
    assert len(white_pts[0]) > 0

    h_radius = (white_pts[1].max() - white_pts[1].min()) / 2.0
    v_radius = (white_pts[0].max() - white_pts[0].min()) / 2.0
    aspect_ratio_circle = h_radius / max(1.0, v_radius)

    # A proporção deve ser aproximadamente 1.0 (círculo não esticado), com tolerância de interpolação < 3%
    assert abs(aspect_ratio_circle - 1.0) < 0.03

def test_generate_split_preview_with_user_20pct_margin_and_zoom(tmp_path):
    video_path = str(tmp_path / "dummy_main_20pct.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 10.0, (1920, 1080))
    for _ in range(10):
        out.write(np.ones((1080, 1920, 3), dtype=np.uint8) * 180)
    out.release()

    img_path = str(tmp_path / "slide_news.webp")
    cv2.imwrite(img_path, np.ones((720, 1280, 3), dtype=np.uint8) * 90)

    preview_path = str(tmp_path / "preview_user_config.jpg")
    res = generate_split_preview_image(
        input_video_path=video_path,
        timestamp_str="00:00:00",
        output_preview_path=preview_path,
        split_source_type="images",
        split_image_paths=[img_path],
        split_media_position="bottom",
        zoom=1.50,
        top_pan=0.0,
        split_blur_margin_pct=20.0
    )
    assert res.get("error") is None
    assert os.path.exists(preview_path)
    img_res = cv2.imread(preview_path)
    assert img_res.shape == (1920, 1080, 3)

