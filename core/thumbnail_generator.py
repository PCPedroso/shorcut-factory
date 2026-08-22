"""
thumbnail_generator.py — Gerador Automático de Capas / Thumbnails 9:16 para Cortes
Seleciona o frame mais nítido e expressivo do corte via MediaPipe BlazeFace e nitidez OpenCV (Laplacian),
compondo automaticamente com a Headline de topo em resolução vertical 1080x1920.
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import core.face_tracker
from core.face_tracker import ensure_face_model, MODEL_PATH, parse_time_to_seconds
from core.headline_drawer import clean_and_condense_headline, HEADLINE_PRESETS

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
PRIMARY_FONT_PATH = os.path.join(FONTS_DIR, "Montserrat-ExtraBold.ttf")


def _calculate_image_sharpness(bgr_img: np.ndarray) -> float:
    """Calcula a variância do operador Laplaciano para medir nitidez e descartar frames borrados."""
    if bgr_img is None or bgr_img.size == 0:
        return 0.0
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def extract_best_frame(
    video_path: str,
    start_time_str: str,
    end_time_str: str,
    sample_interval: float = 0.8,
    max_samples: int = 25
) -> dict:
    """
    Varre o trecho do vídeo [start_time -> end_time] e extrai o frame com maior pontuação:
    Combina nitidez da imagem (anti-blur) + expressividade facial (tamanho e confiança do rosto via MediaPipe).
    """
    if not video_path or not os.path.exists(video_path):
        return {"frame": None, "timestamp_s": 0.0, "error": f"Vídeo não encontrado: {video_path}"}

    start_s = parse_time_to_seconds(start_time_str)
    end_s = parse_time_to_seconds(end_time_str)
    duration = max(0.5, end_s - start_s)

    # Garante modelo BlazeFace
    try:
        ensure_face_model()
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.5)
        detector = vision.FaceDetector.create_from_options(options)
    except Exception:
        detector = None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"frame": None, "timestamp_s": 0.0, "error": "Falha ao abrir vídeo para extração de frames."}

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Calcula timestamps de amostragem distribuídos pelo corte
    step = max(0.4, min(sample_interval, duration / max(1, max_samples)))
    candidate_timestamps = []
    curr_t = start_s + min(1.0, duration * 0.1)  # Pequeno respiro inicial
    while curr_t < end_s - 0.2 and len(candidate_timestamps) < max_samples:
        candidate_timestamps.append(curr_t)
        curr_t += step

    if not candidate_timestamps:
        candidate_timestamps = [start_s + duration / 2.0]

    best_frame = None
    best_score = -1.0
    best_timestamp = candidate_timestamps[0]
    best_face_box = None

    for t in candidate_timestamps:
        frame_num = int(t * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        h, w = frame.shape[:2]
        sharpness = _calculate_image_sharpness(frame)

        face_confidence = 0.0
        face_size_ratio = 0.0
        target_box = None

        if detector is not None:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                detection_result = detector.detect(mp_image)

                if detection_result and detection_result.detections:
                    # Encontra o rosto com maior dominância/área
                    best_det = max(detection_result.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                    face_confidence = float(best_det.categories[0].score) if best_det.categories else 0.8
                    bb = best_det.bounding_box
                    target_box = (bb.origin_x, bb.origin_y, bb.width, bb.height)
                    face_area = float(bb.width * bb.height)
                    face_size_ratio = min(1.0, face_area / float(w * h * 0.15))
            except Exception:
                pass

        # Score ponderado: Nitidez (normalizada ~250) + Confiança Facial + Tamanho do Rosto
        norm_sharpness = min(1.0, sharpness / 350.0)
        score = (norm_sharpness * 35.0) + (face_confidence * 40.0) + (face_size_ratio * 25.0)

        if score > best_score:
            best_score = score
            best_frame = frame.copy()
            best_timestamp = t
            best_face_box = target_box

    cap.release()

    if best_frame is None:
        return {"frame": None, "timestamp_s": 0.0, "error": "Nenhum frame válido capturado."}

    return {
        "frame": best_frame,
        "timestamp_s": best_timestamp,
        "score": best_score,
        "face_box": best_face_box,
        "error": None
    }


def format_frame_to_916(frame_bgr: np.ndarray, face_box=None, aspect_mode: str = "9:16_smart_face") -> np.ndarray:
    """
    Converte qualquer frame (16:9 ou 9:16) para a proporção vertical exata 1080x1920.
    Centraliza no rosto ou aplica desfoque/crop inteligente conforme o formato.
    """
    if frame_bgr is None:
        return np.zeros((1920, 1080, 3), dtype=np.uint8)

    in_h, in_w = frame_bgr.shape[:2]
    target_w, target_h = 1080, 1920
    target_aspect = target_w / target_h  # 9/16 = 0.5625

    # Se já estiver em 9:16 (ou muito próximo)
    curr_aspect = in_w / in_h
    if abs(curr_aspect - target_aspect) < 0.05:
        return cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

    # Se a fonte for 16:9 Horizontal (e.g. 1920x1080)
    if "blur" in aspect_mode:
        # Fundo desfocado 1080x1920 + centro nítido
        bg = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        bg = cv2.GaussianBlur(bg, (51, 51), 0)
        # Escala o centro nítido mantendo aspect ratio
        fg_w = target_w
        fg_h = int(in_h * (target_w / in_w))
        fg = cv2.resize(frame_bgr, (fg_w, fg_h), interpolation=cv2.INTER_LANCZOS4)
        y_offset = (target_h - fg_h) // 2
        bg[y_offset:y_offset+fg_h, 0:target_w] = fg
        return bg

    # Enquadramento focado em rosto / Smart Face ou Center Crop
    crop_w = int(in_h * target_aspect)
    if crop_w > in_w:
        crop_w = in_w
        crop_h = int(in_w / target_aspect)
        y1 = (in_h - crop_h) // 2
        cropped = frame_bgr[y1:y1+crop_h, 0:in_w]
    else:
        if face_box is not None:
            fx, fy, fw, fh = face_box
            face_center_x = fx + fw / 2.0
            x1 = int(face_center_x - crop_w / 2.0)
            x1 = max(0, min(in_w - crop_w, x1))
        else:
            x1 = (in_w - crop_w) // 2
        cropped = frame_bgr[0:in_h, x1:x1+crop_w]

    return cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)


def _load_montserrat_font(size: int) -> ImageFont.FreeTypeFont:
    """Carrega Montserrat-ExtraBold ou fontes do sistema como fallback garantido."""
    if os.path.exists(PRIMARY_FONT_PATH):
        try:
            return ImageFont.truetype(PRIMARY_FONT_PATH, size)
        except Exception:
            pass

    system_fonts = [
        "arialbd.ttf", "impact.ttf", "segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf"
    ]
    for sf in system_fonts:
        try:
            return ImageFont.truetype(sf, size)
        except Exception:
            continue

    return ImageFont.load_default()


def _hex_to_rgb(hex_str: str) -> tuple:
    """Converte '#RRGGBB' para (R, G, B)."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        return tuple(int(clean[i:i+2], 16) for i in (0, 2, 4))
    return (255, 230, 0)


def draw_headline_overlay_on_image(
    image_pil: Image.Image,
    headline_text: str,
    preset: str = "yellow_black",
    custom_text_color: str = "#000000",
    custom_bg_color: str = "#FFE600",
    margin_top_px: int = 150
) -> Image.Image:
    """
    Desenha a caixa magnética de topo com a Headline formatada em 2 linhas harmônicas,
    cantos arredondados modernos e sombra suave para máxima retenção de clique.
    """
    if not headline_text:
        return image_pil

    img = image_pil.convert("RGBA")
    w, h = img.size

    # Obtém configurações de cores do preset
    preset_data = HEADLINE_PRESETS.get(preset, HEADLINE_PRESETS["yellow_black"])
    if preset == "custom":
        text_color_rgb = _hex_to_rgb(custom_text_color)
        bg_color_rgb = _hex_to_rgb(custom_bg_color)
    else:
        text_color_rgb = _hex_to_rgb(preset_data["text_color"])
        bg_color_rgb = _hex_to_rgb(preset_data["bg_color"])

    clean_hl = clean_and_condense_headline(headline_text, max_chars=40).upper()
    words = clean_hl.split()
    if not words:
        return image_pil

    # Quebra inteligente em 2 linhas
    if len(words) >= 4:
        half = len(words) // 2
        line1 = " ".join(words[:half])
        line2 = " ".join(words[half:])
    else:
        line1 = clean_hl
        line2 = ""

    lines = [line1] if not line2 else [line1, line2]

    # Tamanho da fonte dinâmico para encaixar na largura vertical (1080px)
    max_line_len = max(len(l) for l in lines)
    if max_line_len <= 14:
        font_size = 54
    elif max_line_len <= 20:
        font_size = 46
    else:
        font_size = 40

    font = _load_montserrat_font(font_size)

    # Cria overlay para desenhar caixas e textos
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 1. Adiciona um degradê de vinheta escuro sutil no topo para contraste profissional
    vignette = Image.new("RGBA", (w, 420), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for y in range(420):
        alpha = int(140 * (1.0 - (y / 420.0)))
        v_draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    img.alpha_composite(vignette, (0, 0))

    # Calcula caixas para cada linha de texto
    pad_x = 24
    pad_y = 12
    line_spacing = 14
    curr_y = margin_top_px

    for l_text in lines:
        # Bounding box do texto
        bbox = draw.textbbox((0, 0), l_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_w = text_w + (pad_x * 2)
        box_h = text_h + (pad_y * 2)
        box_x = (w - box_w) // 2
        box_y = curr_y

        # Sombra suave da caixa
        shadow_offset = 5
        draw.rounded_rectangle(
            [box_x + shadow_offset, box_y + shadow_offset, box_x + box_w + shadow_offset, box_y + box_h + shadow_offset],
            radius=12,
            fill=(0, 0, 0, 110)
        )

        # Caixa colorida de fundo
        draw.rounded_rectangle(
            [box_x, box_y, box_x + box_w, box_y + box_h],
            radius=12,
            fill=(*bg_color_rgb, 255)
        )

        # Texto renderizado perfeitamente centralizado
        text_x = box_x + pad_x - bbox[0]
        text_y = box_y + pad_y - bbox[1]
        draw.text((text_x, text_y), l_text, fill=(*text_color_rgb, 255), font=font)

        curr_y += box_h + line_spacing

    final_img = Image.alpha_composite(img, overlay)
    return final_img.convert("RGB")


def create_cut_thumbnail(
    source_video_or_frame,
    headline_text: str,
    output_path: str,
    start_time_str: str = "00:00:00",
    end_time_str: str = "00:01:00",
    preset: str = "yellow_black",
    custom_text_color: str = "#000000",
    custom_bg_color: str = "#FFE600",
    aspect_mode: str = "9:16_smart_face"
) -> dict:
    """
    Pipeline mestre para geração automática de thumbnail 9:16:
    1. Extrai o frame mais nítido e expressivo (se receber caminho de vídeo) ou usa o frame direto.
    2. Formata para proporção 9:16 (1080x1920) com enquadramento facial ou blur.
    3. Sobrepõe a Headline magnética de topo.
    4. Salva `thumbnail.jpg` em alta qualidade.
    """
    try:
        face_box = None
        best_t = 0.0
        best_score = 0.0

        if isinstance(source_video_or_frame, str):
            # É caminho de vídeo
            frame_res = extract_best_frame(source_video_or_frame, start_time_str, end_time_str)
            if frame_res.get("error") or frame_res.get("frame") is None:
                return {"path": None, "error": frame_res.get("error", "Erro ao extrair frame.")}
            raw_frame = frame_res["frame"]
            face_box = frame_res.get("face_box")
            best_t = frame_res.get("timestamp_s", 0.0)
            best_score = frame_res.get("score", 0.0)
        elif isinstance(source_video_or_frame, np.ndarray):
            raw_frame = source_video_or_frame
        else:
            return {"path": None, "error": "Fonte de frame inválida."}

        # 2. Formata para proporção 9:16 1080x1920
        frame_916 = format_frame_to_916(raw_frame, face_box=face_box, aspect_mode=aspect_mode)

        # 3. Converte para PIL e aplica overlay da Headline
        frame_rgb = cv2.cvtColor(frame_916, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)

        final_pil = draw_headline_overlay_on_image(
            pil_img,
            headline_text=headline_text,
            preset=preset,
            custom_text_color=custom_text_color,
            custom_bg_color=custom_bg_color,
            margin_top_px=140
        )

        # 4. Salva thumbnail.jpg com alta qualidade
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        final_pil.save(output_path, "JPEG", quality=92, optimize=True)

        return {
            "path": output_path,
            "timestamp_s": best_t,
            "score": best_score,
            "error": None
        }

    except Exception as exc:
        return {"path": None, "error": str(exc)}
