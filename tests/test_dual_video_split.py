import os
import cv2
import numpy as np
import pytest
from core.video_processor import (
    generate_local_dual_video_id,
    fit_frame_to_aspect_slot,
    generate_dual_split_preview,
    compose_dual_video_split_sequence,
    check_has_audio_stream
)
from core.quick_editor import get_video_duration

def test_generate_local_dual_video_id():
    vid_id = generate_local_dual_video_id("video_a.mp4", "video_b.mp4")
    assert vid_id.startswith("local_dual_video_a_e_video_b_")
    
    # Consistência para mesmos nomes
    vid_id2 = generate_local_dual_video_id("video_a.mp4", "video_b.mp4")
    assert vid_id == vid_id2

def test_fit_frame_to_aspect_slot():
    sample = np.zeros((480, 640, 3), dtype=np.uint8)
    sample[:, :] = (0, 255, 0)
    slot = fit_frame_to_aspect_slot(sample, target_w=1080, target_h=960)
    assert slot.shape == (960, 1080, 3)

def test_dual_split_preview_and_compose(tmp_path):
    # Cria dois vídeos sintéticos simples de 1 segundo cada
    v1_path = str(tmp_path / "vid1_red.mp4")
    v2_path = str(tmp_path / "vid2_blue.mp4")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out1 = cv2.VideoWriter(v1_path, fourcc, 10.0, (640, 360))
    for _ in range(10):
        frame1 = np.zeros((360, 640, 3), dtype=np.uint8)
        frame1[:, :] = (0, 0, 255) # Red
        out1.write(frame1)
    out1.release()

    out2 = cv2.VideoWriter(v2_path, fourcc, 10.0, (640, 360))
    for _ in range(10):
        frame2 = np.zeros((360, 640, 3), dtype=np.uint8)
        frame2[:, :] = (255, 100, 0) # Blue
        out2.write(frame2)
    out2.release()

    # 1. Teste de Prévia
    preview_path = str(tmp_path / "preview_dual.jpg")
    prev_res = generate_dual_split_preview(
        video1_path=v1_path,
        video2_path=v2_path,
        output_preview_path=preview_path,
        video1_ts=0.0,
        video2_ts=0.0,
        freeze_monochrome=True,
        aspect_ratio="9:16",
        divider_color="black",
        divider_width=4
    )
    assert prev_res.get("error") is None
    assert os.path.exists(preview_path)
    img = cv2.imread(preview_path)
    assert img.shape == (1920, 1080, 3)

    # 2. Teste de Composição Sequencial
    composed_path = str(tmp_path / "composed_output.mp4")
    comp_res = compose_dual_video_split_sequence(
        video1_path=v1_path,
        video2_path=v2_path,
        output_path=composed_path,
        freeze_timestamp_sec=0.0,
        freeze_monochrome=True,
        aspect_ratio="9:16",
        divider_width=4,
        divider_color="black"
    )
    assert comp_res.get("error") is None
    assert os.path.exists(composed_path)
    assert os.path.getsize(composed_path) > 0

    # Valida duração total composta
    dur = get_video_duration(composed_path)
    assert dur > 1.5 # ~2.0 segundos totais

def test_compose_error_handling(tmp_path):
    bad_res = compose_dual_video_split_sequence(
        video1_path=str(tmp_path / "nao_existe.mp4"),
        video2_path=str(tmp_path / "tambem_nao_existe.mp4"),
        output_path=str(tmp_path / "out.mp4")
    )
    assert bad_res.get("error") is not None
