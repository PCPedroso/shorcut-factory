"""
thumbnail_generator.py — Gerador Avançado de Capas / Thumbnails Multicamadas
Gera automaticamente miniaturas profissionais para YouTube (16:9 Full HD) e Shorts/Reels (9:16 Vertical)
com isolamento de sujeito por IA (Rembg), realce facial (OpenCV CLAHE), vinhetas dinâmicas e 3 variações estilizadas.
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import core.face_tracker
from core.face_tracker import ensure_face_model, MODEL_PATH, parse_time_to_seconds
from core.headline_drawer import clean_and_condense_headline, HEADLINE_PRESETS

# Rembg cache de sessão
try:
    import rembg
    _REMBG_AVAILABLE = True
    _REMBG_SESSION = rembg.new_session("u2net")
except Exception:
    _REMBG_AVAILABLE = False
    _REMBG_SESSION = None

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
PRIMARY_FONT_PATH = os.path.join(FONTS_DIR, "Montserrat-ExtraBold.ttf")


def _calculate_image_sharpness(bgr_img: np.ndarray) -> float:
    """Calcula a variância do operador Laplaciano para medir nitidez e descartar frames borrados."""
    if bgr_img is None or bgr_img.size == 0:
        return 0.0
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def enhance_frame_clahe(bgr_img: np.ndarray) -> np.ndarray:
    """Aplica contraste adaptativo local (CLAHE) e máscara de nitidez suave no frame."""
    if bgr_img is None or bgr_img.size == 0:
        return bgr_img
    try:
        lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        enhanced_lab = cv2.merge((cl, a, b))
        enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        # Unsharp Mask suave
        gaussian = cv2.GaussianBlur(enhanced_bgr, (0, 0), 2.0)
        unsharp = cv2.addWeighted(enhanced_bgr, 1.25, gaussian, -0.25, 0)
        return unsharp
    except Exception:
        return bgr_img


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
    curr_t = start_s + min(1.0, duration * 0.1)
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
                    best_det = max(detection_result.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                    face_confidence = float(best_det.categories[0].score) if best_det.categories else 0.8
                    bb = best_det.bounding_box
                    target_box = (bb.origin_x, bb.origin_y, bb.width, bb.height)
                    face_area = float(bb.width * bb.height)
                    face_size_ratio = min(1.0, face_area / float(w * h * 0.15))
            except Exception:
                pass

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


def format_frame_to_target(frame_bgr: np.ndarray, face_box=None, aspect_mode: str = "9:16_smart_face") -> np.ndarray:
    """
    Converte qualquer frame para a resolução alvo exata:
    - 16:9 -> 1920x1080 (YouTube Padrão / Séries)
    - 9:16 -> 1080x1920 (Shorts / Reels / TikTok)
    """
    if frame_bgr is None:
        return np.zeros((1080, 1920, 3) if aspect_mode == "16:9" else (1920, 1080, 3), dtype=np.uint8)

    in_h, in_w = frame_bgr.shape[:2]

    if aspect_mode == "16:9":
        target_w, target_h = 1920, 1080
        curr_aspect = in_w / in_h
        target_aspect = target_w / target_h # 1.777

        if abs(curr_aspect - target_aspect) < 0.05:
            return cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

        # Se for um frame vertical 9:16 colocado em 16:9
        bg = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        bg = cv2.GaussianBlur(bg, (51, 51), 0)
        fg_h = target_h
        fg_w = int(in_w * (target_h / in_h))
        fg = cv2.resize(frame_bgr, (fg_w, fg_h), interpolation=cv2.INTER_LANCZOS4)
        x_offset = (target_w - fg_w) // 2
        bg[0:target_h, x_offset:x_offset+fg_w] = fg
        return bg

    # Modo 9:16 Vertical (1080x1920)
    target_w, target_h = 1080, 1920
    target_aspect = target_w / target_h

    curr_aspect = in_w / in_h
    if abs(curr_aspect - target_aspect) < 0.05:
        return cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

    if "blur" in aspect_mode:
        bg = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        bg = cv2.GaussianBlur(bg, (51, 51), 0)
        fg_w = target_w
        fg_h = int(in_h * (target_w / in_w))
        fg = cv2.resize(frame_bgr, (fg_w, fg_h), interpolation=cv2.INTER_LANCZOS4)
        y_offset = (target_h - fg_h) // 2
        bg[y_offset:y_offset+fg_h, 0:target_w] = fg
        return bg

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


def extract_subject_cutout(pil_img: Image.Image) -> Image.Image:
    """Extrai o recorte do orador com canal alfa transparente usando Rembg."""
    if not _REMBG_AVAILABLE:
        return None
    try:
        if _REMBG_SESSION is not None:
            return rembg.remove(pil_img, session=_REMBG_SESSION)
        return rembg.remove(pil_img)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 🎨 MOTORES DE VARIAÇÕES VISUAIS DE THUMBNAILS (1, 2 e 3)
# ─────────────────────────────────────────────────────────────────────────────

def _render_variation_1_glow(
    base_pil: Image.Image,
    cutout_pil: Image.Image,
    headline_text: str,
    is_169: bool,
    preset: str = "yellow_black"
) -> Image.Image:
    """
    Variação 1: Impacto Neon / Glow de Estúdio
    - Fundo com desfoque gaussiano + vinheta radial de escurecimento.
    - Orador recortado com Glow/Borda luminosa Amarelo/Branco.
    - Headline com caixas de alto contraste e cantos arredondados.
    """
    w, h = base_pil.size

    # 1. Fundo Desfocado com vinheta escura
    bg = base_pil.filter(ImageFilter.GaussianBlur(18 if is_169 else 24))
    # Vinheta de escurecimento
    dark_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 90))
    bg_comp = Image.alpha_composite(bg.convert("RGBA"), dark_overlay)

    # 2. Glow no Orador
    if cutout_pil is not None:
        alpha = cutout_pil.split()[-1]
        glow_mask = alpha.filter(ImageFilter.GaussianBlur(14))
        glow_layer = Image.new("RGBA", (w, h), (255, 230, 0, 0)) # Amarelo Neon
        glow_layer.putalpha(glow_mask)
        bg_comp.alpha_composite(glow_layer)
        bg_comp.alpha_composite(cutout_pil)

    # 3. Headline
    return _draw_boxed_headline(bg_comp, headline_text, is_169, preset=preset, box_style="solid")


def _render_variation_2_clean(
    base_pil: Image.Image,
    cutout_pil: Image.Image,
    headline_text: str,
    is_169: bool,
    preset: str = "yellow_black"
) -> Image.Image:
    """
    Variação 2: Clean Focus / Sombra 3D Projetada
    - Fundo com desfoque suave (bokeh leve).
    - Orador com sombra projetada suave.
    - Tipografia pesada com contorno duplo preto de 8px e sombra 3D, sem caixas sólidas.
    """
    w, h = base_pil.size

    bg = base_pil.filter(ImageFilter.GaussianBlur(6 if is_169 else 10))
    dark_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 60))
    bg_comp = Image.alpha_composite(bg.convert("RGBA"), dark_overlay)

    if cutout_pil is not None:
        alpha = cutout_pil.split()[-1]
        shadow_mask = alpha.filter(ImageFilter.GaussianBlur(10))
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow_layer.putalpha(shadow_mask)
        bg_comp.alpha_composite(shadow_layer)
        bg_comp.alpha_composite(cutout_pil)

    return _draw_3d_stroke_headline(bg_comp, headline_text, is_169, preset=preset)


def _render_variation_3_hdr_pop(
    base_pil: Image.Image,
    headline_text: str,
    is_169: bool,
    preset: str = "yellow_black"
) -> Image.Image:
    """
    Variação 3: Moldura Dinâmica / HDR Pop
    - Fundo original com realce de saturação e contraste (pop visual).
    - Headline com tarja moderna translúcida e badge de destaque no topo.
    """
    w, h = base_pil.size

    # Realce de cor e contraste
    enhancer_col = ImageEnhance.Color(base_pil)
    pop_img = enhancer_col.enhance(1.3)
    enhancer_con = ImageEnhance.Contrast(pop_img)
    pop_img = enhancer_con.enhance(1.2)

    # Vinheta superior e inferior
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    vig_h = int(h * 0.35)
    for y in range(vig_h):
        a = int(140 * (1.0 - (y / float(vig_h))))
        v_draw.line([(0, y), (w, y)], fill=(0, 0, 0, a))
        v_draw.line([(0, h - y), (w, h - y)], fill=(0, 0, 0, a // 2))

    bg_comp = Image.alpha_composite(pop_img.convert("RGBA"), vignette)
    return _draw_boxed_headline(bg_comp, headline_text, is_169, preset=preset, box_style="translucent", add_badge=True)


# ─────────────────────────────────────────────────────────────────────────────
# ✍️ TIPOGRAFIA & SOBREPOSIÇÃO DE TEXTOS
# ─────────────────────────────────────────────────────────────────────────────

def _draw_boxed_headline(
    bg_comp: Image.Image,
    headline_text: str,
    is_169: bool,
    preset: str = "yellow_black",
    box_style: str = "solid",
    add_badge: bool = False
) -> Image.Image:
    """Desenha headline em caixas arredondadas (sólidas ou translúcidas)."""
    if not headline_text:
        return bg_comp.convert("RGB")

    w, h = bg_comp.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    preset_data = HEADLINE_PRESETS.get(preset, HEADLINE_PRESETS["yellow_black"])
    text_color_rgb = _hex_to_rgb(preset_data["text_color"])
    bg_color_rgb = _hex_to_rgb(preset_data["bg_color"])

    clean_hl = clean_and_condense_headline(headline_text, max_chars=40).upper()
    words = clean_hl.split()
    if not words:
        return bg_comp.convert("RGB")

    if len(words) >= 4:
        half = len(words) // 2
        lines = [" ".join(words[:half]), " ".join(words[half:])]
    else:
        lines = [clean_hl]

    if is_169:
        font_size = 64 if len(lines) == 1 else 52
        pad_x, pad_y = 30, 16
        curr_y = int(h * 0.12)
    else:
        font_size = 52 if len(lines) == 1 else 46
        pad_x, pad_y = 24, 14
        curr_y = int(h * 0.08)

    font = _load_montserrat_font(font_size)

    # Badge de destaque se solicitado
    if add_badge:
        badge_font = _load_montserrat_font(int(font_size * 0.45))
        badge_text = "🔥 MOMENTO IMPERDÍVEL" if not is_169 else "🎬 DESTAQUE"
        b_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        bw, bh = b_bbox[2] - b_bbox[0], b_bbox[3] - b_bbox[1]
        bx = (w - (bw + 24)) // 2
        by = curr_y - bh - 18
        draw.rounded_rectangle([bx, by, bx + bw + 24, by + bh + 10], radius=8, fill=(255, 0, 0, 230))
        draw.text((bx + 12 - b_bbox[0], by + 5 - b_bbox[1]), badge_text, fill=(255, 255, 255, 255), font=badge_font)

    bg_alpha = 255 if box_style == "solid" else 200

    for l_text in lines:
        bbox = draw.textbbox((0, 0), l_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_w = text_w + (pad_x * 2)
        box_h = text_h + (pad_y * 2)
        box_x = (w - box_w) // 2
        box_y = curr_y

        # Sombra da caixa
        draw.rounded_rectangle(
            [box_x + 5, box_y + 5, box_x + box_w + 5, box_y + box_h + 5],
            radius=14,
            fill=(0, 0, 0, 120)
        )
        # Caixa de fundo
        draw.rounded_rectangle(
            [box_x, box_y, box_x + box_w, box_y + box_h],
            radius=14,
            fill=(*bg_color_rgb, bg_alpha)
        )
        # Texto
        text_x = box_x + pad_x - bbox[0]
        text_y = box_y + pad_y - bbox[1]
        draw.text((text_x, text_y), l_text, fill=(*text_color_rgb, 255), font=font)

        curr_y += box_h + 14

    final_img = Image.alpha_composite(bg_comp, overlay)
    return final_img.convert("RGB")


def _draw_3d_stroke_headline(
    bg_comp: Image.Image,
    headline_text: str,
    is_169: bool,
    preset: str = "yellow_black"
) -> Image.Image:
    """Desenha texto sem caixa com contorno grosso (stroke) de 8px e sombra 3D projetada."""
    if not headline_text:
        return bg_comp.convert("RGB")

    w, h = bg_comp.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    clean_hl = clean_and_condense_headline(headline_text, max_chars=36).upper()
    words = clean_hl.split()
    if not words:
        return bg_comp.convert("RGB")

    lines = [" ".join(words[:len(words)//2]), " ".join(words[len(words)//2:])] if len(words) >= 4 else [clean_hl]

    font_size = 68 if is_169 else 56
    font = _load_montserrat_font(font_size)
    curr_y = int(h * 0.12) if is_169 else int(h * 0.09)

    text_color = (255, 230, 0, 255) # Amarelo Solar
    stroke_color = (0, 0, 0, 255)

    for l_text in lines:
        bbox = draw.textbbox((0, 0), l_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = (w - text_w) // 2 - bbox[0]
        text_y = curr_y - bbox[1]

        # Sombra 3D projetada
        for s_offset in range(4, 12, 2):
            draw.text((text_x + s_offset, text_y + s_offset), l_text, fill=(0, 0, 0, 180), font=font, stroke_width=6, stroke_fill=(0, 0, 0, 180))

        # Texto principal com contorno
        draw.text((text_x, text_y), l_text, fill=text_color, font=font, stroke_width=8, stroke_fill=stroke_color)
        curr_y += text_h + 32

    final_img = Image.alpha_composite(bg_comp, overlay)
    return final_img.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# 🚀 PIPELINE MESTRE DE CRIAÇÃO E VARIAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

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
    Gera as 3 variações estilizadas de Thumbnail e salva:
    - thumbnail_1.jpg (Impacto Neon / Glow) -> Copiada como thumbnail.jpg padrão
    - thumbnail_2.jpg (Clean Focus / Sombra 3D)
    - thumbnail_3.jpg (Moldura Dinâmica / HDR Pop)
    """
    try:
        face_box = None
        best_t = 0.0
        best_score = 0.0

        if isinstance(source_video_or_frame, str):
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

        # 1. Realce de Nitidez e Contraste via OpenCV CLAHE
        enhanced_bgr = enhance_frame_clahe(raw_frame)

        # 2. Formata para a proporção alvo (16:9 ou 9:16)
        formatted_bgr = format_frame_to_target(enhanced_bgr, face_box=face_box, aspect_mode=aspect_mode)
        is_169 = (aspect_mode == "16:9")

        # 3. Converte para PIL e extrai recorte do sujeito via Rembg
        frame_rgb = cv2.cvtColor(formatted_bgr, cv2.COLOR_BGR2RGB)
        base_pil = Image.fromarray(frame_rgb)
        cutout_pil = extract_subject_cutout(base_pil)

        # 4. Renderiza as 3 variações estilizadas
        v1_img = _render_variation_1_glow(base_pil, cutout_pil, headline_text, is_169=is_169, preset=preset)
        v2_img = _render_variation_2_clean(base_pil, cutout_pil, headline_text, is_169=is_169, preset=preset)
        v3_img = _render_variation_3_hdr_pop(base_pil, headline_text, is_169=is_169, preset=preset)

        # 5. Salva todas as variações no disco
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        thumb_1_path = os.path.join(out_dir, "thumbnail_1.jpg") if out_dir else "thumbnail_1.jpg"
        thumb_2_path = os.path.join(out_dir, "thumbnail_2.jpg") if out_dir else "thumbnail_2.jpg"
        thumb_3_path = os.path.join(out_dir, "thumbnail_3.jpg") if out_dir else "thumbnail_3.jpg"

        v1_img.save(thumb_1_path, "JPEG", quality=94, optimize=True)
        v2_img.save(thumb_2_path, "JPEG", quality=94, optimize=True)
        v3_img.save(thumb_3_path, "JPEG", quality=94, optimize=True)

        # A Variação 1 é salva também como thumbnail.jpg principal
        v1_img.save(output_path, "JPEG", quality=94, optimize=True)

        return {
            "path": output_path,
            "variations": [
                {"id": 1, "name": "⚡ Impacto Neon (Glow)", "path": thumb_1_path, "filename": "thumbnail_1.jpg"},
                {"id": 2, "name": "✨ Clean Focus (Sombra 3D)", "path": thumb_2_path, "filename": "thumbnail_2.jpg"},
                {"id": 3, "name": "🎬 Moldura Dinâmica (HDR)", "path": thumb_3_path, "filename": "thumbnail_3.jpg"}
            ],
            "timestamp_s": best_t,
            "score": best_score,
            "error": None
        }

    except Exception as exc:
        return {"path": None, "error": str(exc)}
