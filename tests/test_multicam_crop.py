"""
tests/test_multicam_crop.py — Testes Unitários para o Motor de Enquadramento Multicâmera
"""

import os
import pytest
import numpy as np
from core.multicam_crop import (
    normalize_box_coordinates,
    compute_slot_heights,
    crop_and_fit_image_slot,
    build_multicam_filtergraph
)


def test_compute_slot_heights():
    """Valida o cálculo das alturas verticais para 1, 2, 3 e 4 caixas."""
    assert compute_slot_heights(1, 1920) == [1920]
    assert compute_slot_heights(2, 1920) == [960, 960]
    assert compute_slot_heights(3, 1920) == [640, 640, 640]
    assert compute_slot_heights(4, 1920) == [480, 480, 480, 480]
    
    # Valida que a soma é sempre 1920
    for n in range(1, 6):
        heights = compute_slot_heights(n, 1920)
        assert sum(heights) == 1920
        # Todas as alturas devem ser pares
        for h in heights:
            assert h % 2 == 0


def test_normalize_box_coordinates():
    """Valida a conversão de coordenadas do canvas para resolução de vídeo real."""
    canvas_w, canvas_h = 800, 450
    video_w, video_h = 1920, 1080  # Proporção 16:9 exata (escala = 2.4)

    raw_box = {
        "left": 100,
        "top": 50,
        "width": 200,
        "height": 100,
        "scaleX": 1.5,
        "scaleY": 1.0,
        "order": 1,
        "label": "Camera 2"
    }

    norm = normalize_box_coordinates(raw_box, canvas_w, canvas_h, video_w, video_h)

    assert norm["order"] == 1
    assert norm["label"] == "Camera 2"
    # Largura e altura devem ser pares
    assert norm["w"] % 2 == 0
    assert norm["h"] % 2 == 0
    # Dentro dos limites do vídeo
    assert norm["x"] >= 0 and norm["x"] + norm["w"] <= video_w
    assert norm["y"] >= 0 and norm["y"] + norm["h"] <= video_h


def test_crop_and_fit_image_slot():
    """Valida que o recorte e ajuste proporcional preenche exatamente as dimensões do slot sem deformar."""
    # Cria uma imagem sintética 1920x1080 (gradiente)
    dummy_img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    dummy_img[:, :, 0] = 120  # Azul
    dummy_img[:, :, 1] = 200  # Verde

    box = {"x": 200, "y": 100, "w": 600, "h": 400}
    slot_w, slot_h = 1080, 640

    fitted = crop_and_fit_image_slot(dummy_img, box, target_w=slot_w, target_h=slot_h)

    assert fitted.shape == (slot_h, slot_w, 3)
    assert fitted.dtype == np.uint8


def test_build_multicam_filtergraph_single_box():
    """Valida o filtergraph gerado para 1 câmera (foco único)."""
    boxes = [{"x": 100, "y": 50, "w": 400, "h": 600, "order": 0}]
    fg = build_multicam_filtergraph(boxes, target_w=1080, target_h=1920)

    assert "crop=400:600:100:50" in fg
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in fg
    assert "setsar=1[v_multicam]" in fg


def test_build_multicam_filtergraph_three_boxes():
    """Valida o filtergraph gerado para 3 câmeras empilhadas verticalmente com linhas divisórias."""
    boxes = [
        {"x": 700, "y": 290, "w": 1120, "h": 520, "order": 0},
        {"x": 130, "y": 290, "w": 560, "h": 250, "order": 1},
        {"x": 130, "y": 555, "w": 560, "h": 260, "order": 2}
    ]
    fg = build_multicam_filtergraph(
        boxes,
        target_w=1080,
        target_h=1920,
        divider_color="black",
        divider_width=4
    )

    # 3 streams de entrada para as 3 câmeras
    assert "[0:v]crop=1120:520:700:290" in fg
    assert "scale=1080:640:force_original_aspect_ratio=increase" in fg
    assert "[cam_0][cam_1][cam_2]vstack=inputs=3" in fg
    # Linhas divisórias drawbox
    assert "drawbox=x=0" in fg
    assert "[v_multicam]" in fg


def test_render_multicam_cut_empty_scenes():
    """Valida retorno de erro quando não há cenas configuradas."""
    from core.multicam_crop import render_multicam_cut
    res = render_multicam_cut("dummy.mp4", [], "out.mp4")
    assert res.get("status") == "error"
    assert "Nenhuma cena" in res.get("error", "")


def test_cut_video_multicam_mode_integration(monkeypatch, tmp_path):
    """Valida o roteamento do modo 9:16_multicam dentro da função principal cut_video."""
    from core.video_processor import cut_video
    
    mock_called = {}

    def mock_render(input_video_path, scenes, output_video_path, fallback_start_time, fallback_end_time):
        mock_called["scenes"] = scenes
        mock_called["input"] = input_video_path
        # Cria arquivo fictício de saída
        with open(output_video_path, "wb") as f:
            f.write(b"dummy mp4 content")
        return {"status": "success", "path": output_video_path, "output_path": output_video_path}

    monkeypatch.setattr("core.multicam_crop.render_multicam_cut", mock_render)

    dummy_in = str(tmp_path / "in.mp4")
    dummy_out = str(tmp_path / "out.mp4")
    with open(dummy_in, "wb") as f:
        f.write(b"input data")

    scenes_input = [
        {"start_time": "00:00:00.00", "end_time": "00:00:10.00", "boxes": [{"x": 10, "y": 20, "w": 300, "h": 200, "order": 0}]}
    ]

    res = cut_video(
        input_path=dummy_in,
        start_time_str="00:00:00.00",
        end_time_str="00:00:10.00",
        output_path=dummy_out,
        aspect_ratio_mode="9:16_multicam",
        multicam_scenes=scenes_input,
        thumbnail_enabled=False
    )

    assert mock_called["scenes"] == scenes_input
    assert res.get("path") == dummy_out
