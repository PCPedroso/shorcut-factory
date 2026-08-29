"""
face_tracker.py — Rastreamento Inteligente de Rosto, Trava de Alvo (Target Lock) e Auto-Reframing Vertical (9:16)
Detecta o orador principal com Google MediaPipe BlazeFace e realiza movimento suave de câmera (Cinematic Panning).
"""

import os
import cv2
import urllib.request
import subprocess
import imageio_ffmpeg
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "blaze_face_short_range.tflite")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"


def ensure_face_model():
    """Garante que o modelo BlazeFace de 220KB esteja baixado."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) < 1000:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)


def parse_time_to_seconds(time_str: str) -> float:
    """Converte HH:MM:SS ou MM:SS para segundos."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return float(time_str)


def filter_prominent_faces(detections, frame_width: int, frame_height: int, min_relative_area: float = 0.28) -> list:
    """
    Filtra rostos secundários/irrelevantes (como intérprete de LIBRAS em miniatura no canto,
    plateia ao fundo ou inserções menores na transmissão).
    Critérios:
    - Descarta rostos cuja área seja inferior a 'min_relative_area' (ex: < 28%) da área do maior rosto em cena.
    - Descarta rostos com área absoluta insignificante (< 0.2% da tela).
    """
    if not detections:
        return []

    min_abs_area = frame_width * frame_height * 0.002
    candidates = [d for d in detections if (d.bounding_box.width * d.bounding_box.height) >= min_abs_area]
    if not candidates:
        return detections

    max_area = max(d.bounding_box.width * d.bounding_box.height for d in candidates)
    prominent = [d for d in candidates if (d.bounding_box.width * d.bounding_box.height) >= (max_area * min_relative_area)]
    return prominent if prominent else candidates


def get_tv_broadcast_split_bounds(frame, frame_width: int, frame_height: int):
    """
    Detecta as bordas exatas (colunas esquerda e direita) do quadro de split-screen de TV.
    Retorna uma tupla (box_left, box_right) em pixels ou None se não for detectado.
    """
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 120)
        col_densities = np.mean(edges > 0, axis=0)

        # Divisória central (entre 30% e 70% da largura)
        center_band = col_densities[int(frame_width * 0.30):int(frame_width * 0.70)]
        if np.max(center_band) < 0.20:
            return None

        # Borda esquerda da moldura (entre 2% e 25% da largura)
        left_region = col_densities[int(frame_width * 0.02):int(frame_width * 0.25)]
        left_peaks = np.where(left_region > 0.15)[0]
        box_left = int(frame_width * 0.02) + int(left_peaks[0]) if len(left_peaks) > 0 else 0

        # Borda direita da moldura (entre 65% e 90% da largura, excluindo a área de Libras)
        right_region = col_densities[int(frame_width * 0.65):int(frame_width * 0.90)]
        right_peaks = np.where(right_region > 0.15)[0]
        box_right = int(frame_width * 0.65) + int(right_peaks[-1]) if len(right_peaks) > 0 else frame_width

        return box_left, box_right
    except Exception:
        return None


def detect_tv_broadcast_split_screen(frame, frame_width: int, frame_height: int) -> bool:
    """
    Detecta se o frame possui layout de split-screen de transmissão de TV (debate/sabatina).
    """
    bounds = get_tv_broadcast_split_bounds(frame, frame_width, frame_height)
    return bounds is not None


def is_dual_interlocutor_shot(detections, frame_width: int, frame_height: int) -> bool:
    """
    Detecta se o enquadramento atual possui 2 interlocutores (plano conjunto ou split-screen de debate/sabatina).
    Critérios:
    - Pelo menos 2 rostos proeminentes detectados (filtrando LIBRAS/fundo).
    - Ambos os rostos com separação horizontal clara (distância >= 18% da largura).
    - Alinhamento vertical coerente (diferença de altura <= 28% da tela).
    """
    prominent_dets = filter_prominent_faces(detections, frame_width, frame_height, min_relative_area=0.28)
    if not prominent_dets or len(prominent_dets) < 2:
        return False

    valid_faces = []
    for d in prominent_dets:
        bx = d.bounding_box
        cx = bx.origin_x + bx.width / 2.0
        cy = bx.origin_y + bx.height / 2.0
        valid_faces.append((cx, cy, bx.width, bx.height, d))

    if len(valid_faces) < 2:
        return False

    valid_faces.sort(key=lambda x: x[2] * x[3], reverse=True)
    f1, f2 = valid_faces[0], valid_faces[1]

    cx_dist = abs(f1[0] - f2[0]) / float(frame_width)
    cy_diff = abs(f1[1] - f2[1]) / float(frame_height)

    return cx_dist >= 0.18 and cy_diff <= 0.28


def detect_dual_with_fallback(frame, detections, frame_width: int, frame_height: int) -> tuple:
    """
    Detecção robusta de Dual Shot combinando análise facial (BlazeFace) e
    análise estrutural do frame (split-screen de broadcast).

    Camada 1 — Análise Facial:
      Verifica se há ≥2 rostos proeminentes com separação horizontal adequada.
      Thresholds adaptativos: mais permissivos em contexto de broadcast.

    Camada 2 — Fallback Estrutural:
      Se split-screen de broadcast for detectado mas apenas 1 rosto visível
      (ex: 2º candidato com cabeça inclinada para baixo), ainda confirma Dual Shot.

    Retorna:
        (is_dual: bool, is_broadcast_split: bool)
    """
    is_broadcast = detect_tv_broadcast_split_screen(frame, frame_width, frame_height)

    # Thresholds adaptativos: broadcast permite rostos parcialmente de perfil
    min_rel_area = 0.15 if is_broadcast else 0.28
    min_horiz_sep = 0.12 if is_broadcast else 0.18

    prominent = filter_prominent_faces(detections, frame_width, frame_height,
                                       min_relative_area=min_rel_area)

    # Critério 1: 2+ rostos proeminentes com separação horizontal e alinhamento vertical ok
    if len(prominent) >= 2:
        sorted_faces = sorted(
            prominent,
            key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0
        )
        f1, f2 = sorted_faces[0], sorted_faces[-1]
        cx1 = f1.bounding_box.origin_x + f1.bounding_box.width / 2.0
        cx2 = f2.bounding_box.origin_x + f2.bounding_box.width / 2.0
        cy1 = f1.bounding_box.origin_y + f1.bounding_box.height / 2.0
        cy2 = f2.bounding_box.origin_y + f2.bounding_box.height / 2.0

        cx_dist = abs(cx1 - cx2) / float(frame_width)
        cy_diff = abs(cy1 - cy2) / float(frame_height)

        if cx_dist >= min_horiz_sep and cy_diff <= 0.35:
            return True, is_broadcast

    # Critério 2 — Fallback Estrutural: split-screen confirmado + pelo menos 1 rosto detectado
    # (o 2º personagem pode estar com a cabeça inclinada, fora do campo frontal do BlazeFace)
    if is_broadcast and len(detections) >= 1:
        return True, True

    return False, is_broadcast


class CompositeBoundingBox:
    def __init__(self, origin_x: int, origin_y: int, width: int, height: int):
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.width = width
        self.height = height


class CompositeFaceDetection:
    def __init__(self, bbox: CompositeBoundingBox):
        self.bounding_box = bbox


def select_target_face(detections, frame_width: int, frame_height: int, last_tracked_center=None, person_preference: str = "auto"):
    """
    Seleciona o rosto alvo respeitando a preferência do usuário e mantendo a
    Trava de Continuidade Espacial (Target Lock) para nunca pular para outra pessoa na cena.
    Filtra automaticamente rostos desproporcionalmente pequenos (ex: intérpretes de LIBRAS).
    Suporta modo 'both' para enquadrar ambos os interlocutores em plano conjunto simultaneamente.
    """
    if not detections:
        return None, last_tracked_center

    # Filtra rostos irrelevantes/LIBRAS
    prominent_dets = filter_prominent_faces(detections, frame_width, frame_height, min_relative_area=0.28)
    if not prominent_dets:
        prominent_dets = detections

    # Modo 'both' (Ambos os Interlocutores em Plano Conjunto / Split-Screen)
    if person_preference == "both":
        if len(prominent_dets) >= 2:
            min_x = min(d.bounding_box.origin_x for d in prominent_dets)
            max_x = max(d.bounding_box.origin_x + d.bounding_box.width for d in prominent_dets)
            min_y = min(d.bounding_box.origin_y for d in prominent_dets)
            max_y = max(d.bounding_box.origin_y + d.bounding_box.height for d in prominent_dets)

            comp_bbox = CompositeBoundingBox(min_x, min_y, max(1, max_x - min_x), max(1, max_y - min_y))
            comp_face = CompositeFaceDetection(comp_bbox)
            cx = min_x + comp_bbox.width / 2.0
            cy = min_y + comp_bbox.height / 2.0
            return comp_face, (cx, cy)
        else:
            best_face = prominent_dets[0]
            bx = best_face.bounding_box
            return best_face, (bx.origin_x + bx.width / 2.0, bx.origin_y + bx.height / 2.0)

    # Se já temos um alvo rastreado anteriormente, usamos a menor distância euclidiana (Target Lock)
    if last_tracked_center is not None:
        last_cx, last_cy = last_tracked_center
        best_face = None
        min_dist = float('inf')
        for d in prominent_dets:
            bx = d.bounding_box
            cx = bx.origin_x + bx.width / 2.0
            cy = bx.origin_y + bx.height / 2.0
            dist = ((cx - last_cx) ** 2 + (cy - last_cy) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                best_face = d

        if best_face is not None:
            bx = best_face.bounding_box
            return best_face, (bx.origin_x + bx.width / 2.0, bx.origin_y + bx.height / 2.0)

    # Primeira seleção (baseada na preferência escolhida)
    if person_preference == "right":
        # Pessoa principal mais à direita da tela (excluindo LIBRAS)
        best_face = max(prominent_dets, key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0)
    elif person_preference == "left":
        # Pessoa principal mais à esquerda da tela
        best_face = min(prominent_dets, key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0)
    elif person_preference == "center":
        # Pessoa principal mais próxima do centro da tela
        center_x = frame_width / 2.0
        best_face = min(prominent_dets, key=lambda d: abs((d.bounding_box.origin_x + d.bounding_box.width / 2.0) - center_x))
    else:
        # Modo 'auto': maior área / dominância inicial
        best_face = max(prominent_dets, key=lambda d: d.bounding_box.width * d.bounding_box.height)

    bx = best_face.bounding_box
    return best_face, (bx.origin_x + bx.width / 2.0, bx.origin_y + bx.height / 2.0)


def generate_face_preview_image(
    input_video_path: str,
    timestamp_str: str,
    output_preview_path: str = "temp_face_preview.jpg",
    person_preference: str = "auto",
    auto_zoom: bool = True,
    margin_ratio: float = 1.55,
    max_zoom_factor: float = 1.85
) -> dict:
    """
    Gera uma imagem de prévia mostrando as pessoas detectadas, quem foi travado como alvo
    e a moldura do enquadramento vertical 9:16.
    """
    try:
        ensure_face_model()
        t_sec = parse_time_to_seconds(timestamp_str)

        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            return {"path": None, "error": "Não foi possível abrir o vídeo para prévia."}

        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"path": None, "error": "Falha ao capturar o frame de prévia."}

        height, width, _ = frame.shape
        base_crop_w = int(height * 9.0 / 16.0)
        if base_crop_w % 2 != 0:
            base_crop_w += 1
        min_crop_w = int(base_crop_w / max_zoom_factor) if auto_zoom else base_crop_w

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options)
        detector = vision.FaceDetector.create_from_options(options)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = detector.detect(mp_img)
        detector.close()

        detections = results.detections if results.detections else []

        # ── Detecção de Dual Shot (Debate TV / Split-Screen) ──────────────────────────
        is_dual, is_broadcast = detect_dual_with_fallback(frame, detections, width, height)
        use_dual_preview = is_dual and person_preference in ("auto", "both")

        target_face, _ = select_target_face(detections, width, height, None, person_preference)

        preview_img = frame.copy()

        prominent_dets = filter_prominent_faces(
            detections, width, height,
            min_relative_area=0.15 if is_broadcast else 0.28
        )

        # Desenha as caixas dos rostos detectados
        for d in detections:
            is_target = (d == target_face) and not use_dual_preview
            is_prominent = (d in prominent_dets)
            bx = d.bounding_box
            if is_target:
                color = (0, 255, 0)    # Verde
                label = "ALVO PRINCIPAL"
            elif is_prominent:
                color = (0, 165, 255)  # Laranja
                label = "INTERLOCUTOR"
            else:
                color = (120, 120, 120)  # Cinza
                label = "SECUNDARIO / LIBRAS"

            cv2.rectangle(preview_img, (bx.origin_x, bx.origin_y),
                          (bx.origin_x + bx.width, bx.origin_y + bx.height),
                          color, 3 if is_target else 2)
            cv2.putText(preview_img, label,
                        (bx.origin_x, max(24, bx.origin_y - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # ── Calcula e desenha o enquadramento 9:16 ─────────────────────────────────────
        if use_dual_preview:
            # Modo Dual Shot: bounding box composta entre os dois interlocutores
            if len(prominent_dets) >= 2:
                sorted_p = sorted(prominent_dets[:2], key=lambda d: d.bounding_box.origin_x)
                d_min_bb = sorted_p[0].bounding_box
                d_max_bb = sorted_p[-1].bounding_box
                comp_min_x = d_min_bb.origin_x
                comp_max_x = d_max_bb.origin_x + d_max_bb.width
                comp_min_y = min(d_min_bb.origin_y, d_max_bb.origin_y)
                comp_max_y = max(d_min_bb.origin_y + d_min_bb.height,
                                 d_max_bb.origin_y + d_max_bb.height)
            elif is_broadcast and len(prominent_dets) == 1:
                # 1 rosto detectado + split-screen confirmado: estende para metade oposta
                bx_s = prominent_dets[0].bounding_box
                face_cx_s = bx_s.origin_x + bx_s.width / 2.0
                if face_cx_s < width * 0.5:
                    comp_min_x = max(0, int(bx_s.origin_x - bx_s.width * 0.4))
                    comp_max_x = int(width * 0.90)
                else:
                    comp_min_x = int(width * 0.05)
                    comp_max_x = min(width, int(bx_s.origin_x + bx_s.width + bx_s.width * 0.4))
                comp_min_y = max(0, bx_s.origin_y - int(bx_s.height * 0.3))
                comp_max_y = min(height, bx_s.origin_y + bx_s.height + int(bx_s.height * 0.3))
            else:
                use_dual_preview = False

        if use_dual_preview:
            # Bounding Box Composta em azul — envelope dos dois interlocutores
            cv2.rectangle(preview_img,
                          (comp_min_x, comp_min_y), (comp_max_x, comp_max_y),
                          (255, 80, 0), 3)  # Azul BGR
            dual_label = "DUAL SHOT [BROADCAST TV]" if is_broadcast else "DUAL SHOT"
            cv2.putText(preview_img, dual_label,
                        (comp_min_x + 10, comp_min_y + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 80, 0), 2)

            # Enquadramento 9:16 centrado entre os dois interlocutores (zoom=1.0)
            comp_face_cx = (comp_min_x + comp_max_x) / 2.0
            target_w_d = base_crop_w
            target_x_d = comp_face_cx - (base_crop_w / 2.0)
            x1 = max(0, min(width - target_w_d, int(target_x_d)))
            y1 = 0
            x2 = x1 + target_w_d
            y2 = height
            cv2.rectangle(preview_img, (x1, y1), (x2, y2), (255, 255, 0), 4)
            cv2.putText(preview_img, "ENQUADRAMENTO 9:16 DUAL",
                        (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        elif target_face is not None:
            # Modo individual: enquadramento 9:16 no rosto alvo
            bx = target_face.bounding_box
            face_cx = bx.origin_x + bx.width / 2.0
            face_cy = bx.origin_y + bx.height * 0.45

            if auto_zoom:
                body_width = bx.width * 2.0
                target_w = int(body_width * margin_ratio)
                target_w = max(min_crop_w, min(base_crop_w, target_w))
                target_h = int(target_w * 16.0 / 9.0)
                target_x = face_cx - (target_w / 2.0)
                target_y = face_cy - (target_h * 0.35)
            else:
                target_w = base_crop_w
                target_h = height
                target_x = face_cx - (base_crop_w / 2.0)
                target_y = 0.0

            x1 = max(0, min(width - target_w, int(target_x)))
            y1 = max(0, min(height - target_h, int(target_y)))
            x2 = x1 + target_w
            y2 = y1 + target_h
            cv2.rectangle(preview_img, (x1, y1), (x2, y2), (255, 255, 0), 4)
            cv2.putText(preview_img, "ENQUADRAMENTO 9:16",
                        (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.imwrite(output_preview_path, preview_img)
        return {
            "path": output_preview_path,
            "detected_count": len(detections),
            "dual_shot": use_dual_preview,
            "broadcast_split": is_broadcast,
            "error": None
        }

    except Exception as exc:
        return {"path": None, "error": str(exc)}


def calculate_auto_blur_params(
    input_video_path: str,
    timestamp_str: str,
    person_preference: str = "auto",
    margin_ratio: float = 1.55
) -> dict:
    """
    Calcula automaticamente o melhor nível de Zoom e Pan horizontal para o modo Fundo Desfocado,
    enquadrando o orador com a margem de segurança configurada.
    """
    try:
        ensure_face_model()
        t_sec = parse_time_to_seconds(timestamp_str)

        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            return {"zoom": 1.35, "pan": 0.0, "face_detected": False}

        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"zoom": 1.35, "pan": 0.0, "face_detected": False}

        height, width, _ = frame.shape
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options)
        detector = vision.FaceDetector.create_from_options(options)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = detector.detect(mp_img)
        detector.close()

        detections = results.detections if results.detections else []

        # Detecção de Dual Shot com análise estrutural de broadcast (Canny + facial)
        is_dual, is_broadcast = detect_dual_with_fallback(frame, detections, width, height)
        prominent = filter_prominent_faces(detections, width, height,
                                          min_relative_area=0.15 if is_broadcast else 0.28)

        # Caso 1: Preferência explícita por 'both' ou 'auto' com Dual Shot detectado
        if person_preference == "both" or (person_preference == "auto" and is_dual):
            # Tenta obter as bordas exatas da moldura de TV via detecção de bordas
            bounds = get_tv_broadcast_split_bounds(frame, width, height) if is_broadcast else None

            if bounds is not None:
                box_left, box_right = bounds
                crop_box_w = max(1080.0, min(float(width), float(box_right - box_left)))
                calc_zoom = min(1.85, max(1.0, float(width) / crop_box_w))
                w_fg = int(1080 * calc_zoom)
                max_crop_x = max(1, w_fg - 1080)
                x_scaled_left = float(box_left) * (w_fg / float(width))
                calc_pan = max(-1.0, min(1.0, 2.0 * (x_scaled_left / max_crop_x) - 1.0))

                return {
                    "zoom": round(calc_zoom, 2),
                    "pan": round(calc_pan, 2),
                    "face_detected": True,
                    "dual_shot": True,
                    "broadcast_split": True,
                    "notes": "Enquadramento automático pixel-perfect baseado nas bordas estruturais do debate de TV."
                }

            elif len(prominent) >= 2:
                # Ordena os 2 oradores principais da esquerda para a direita
                sorted_dual = sorted(prominent[:2], key=lambda d: d.bounding_box.origin_x)
                d_left, d_right = sorted_dual[0], sorted_dual[1]

                cx_left = d_left.bounding_box.origin_x + d_left.bounding_box.width / 2.0
                cx_right = d_right.bounding_box.origin_x + d_right.bounding_box.width / 2.0
                face_avg_w = (d_left.bounding_box.width + d_right.bounding_box.width) / 2.0

                box_left = max(0.0, cx_left - face_avg_w * 1.35)
                box_right = min(float(width), cx_right + face_avg_w * 1.55)
                crop_box_w = max(1080.0, min(float(width), box_right - box_left))

                calc_zoom = min(1.85, max(1.0, float(width) / crop_box_w))
                w_fg = int(1080 * calc_zoom)
                max_crop_x = max(1, w_fg - 1080)
                x_scaled_left = box_left * (w_fg / float(width))
                calc_pan = max(-1.0, min(1.0, 2.0 * (x_scaled_left / max_crop_x) - 1.0))

                return {
                    "zoom": round(calc_zoom, 2),
                    "pan": round(calc_pan, 2),
                    "face_detected": True,
                    "dual_shot": True,
                    "broadcast_split": is_broadcast,
                    "notes": "Enquadramento ajustado para englobar ambos os interlocutores com recorte das bordas irrelevantes."
                }
            elif is_broadcast and len(prominent) == 1:
                # Fallback Broadcast: split-screen confirmado mas 2º rosto não detectado
                bx_s = prominent[0].bounding_box
                face_cx_s = bx_s.origin_x + bx_s.width / 2.0
                face_w_s = bx_s.width
                if face_cx_s < width * 0.5:
                    box_left = max(0.0, face_cx_s - face_w_s * 1.35)
                    box_right = min(float(width), max(width * 0.74, face_cx_s + face_w_s * 1.35 + (width * 0.45)))
                else:
                    box_left = max(0.0, min(width * 0.04, face_cx_s - face_w_s * 1.35 - (width * 0.45)))
                    box_right = min(float(width), face_cx_s + face_w_s * 1.55)
                crop_box_w = max(1080.0, min(float(width), box_right - box_left))
                calc_zoom = min(1.85, max(1.0, float(width) / crop_box_w))
                w_fg = int(1080 * calc_zoom)
                max_crop_x = max(1, w_fg - 1080)
                x_scaled_left = box_left * (w_fg / float(width))
                calc_pan = max(-1.0, min(1.0, 2.0 * (x_scaled_left / max_crop_x) - 1.0))
                return {
                    "zoom": round(calc_zoom, 2),
                    "pan": round(calc_pan, 2),
                    "face_detected": True,
                    "dual_shot": True,
                    "broadcast_split": True,
                    "notes": "Split-screen de broadcast detectado (1 rosto visível). Enquadramento ajustado para cobrir ambos os interlocutores."
                }
            elif len(prominent) == 1:
                target_face = prominent[0]
            else:
                return {"zoom": 1.35, "pan": 0.0, "face_detected": False, "dual_shot": False}
        else:
            target_face, _ = select_target_face(detections, width, height, None, person_preference)

        if target_face is None:
            return {"zoom": 1.35, "pan": 0.0, "face_detected": False, "dual_shot": False}

        bx = target_face.bounding_box
        face_cx = bx.origin_x + bx.width / 2.0

        # Calcula a largura desejada com a margem de segurança
        desired_w = bx.width * 2.0 * margin_ratio
        calc_zoom = min(2.5, max(1.0, float(width) / desired_w))

        face_norm = face_cx / float(width)
        calc_pan = max(-1.0, min(1.0, (face_norm - 0.5) * 2.0))

        return {
            "zoom": round(calc_zoom, 2),
            "pan": round(calc_pan, 2),
            "face_detected": True,
            "dual_shot": False
        }
    except Exception:
        return {"zoom": 1.35, "pan": 0.0, "face_detected": False, "dual_shot": False}


def generate_blur_preview_image(
    input_video_path: str,
    timestamp_str: str,
    output_preview_path: str = "temp_blur_preview.jpg",
    zoom: float = 1.35,
    pan: float = 0.0,
    blur_intensity: int = 25
) -> dict:
    """
    Gera uma imagem de prévia realista do modo Fundo Desfocado (Blur) com o zoom e enquadramento exatos.
    """
    try:
        t_sec = parse_time_to_seconds(timestamp_str)
        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            return {"path": None, "error": "Não foi possível abrir o vídeo para prévia."}

        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"path": None, "error": "Falha ao capturar o frame."}

        h, w, _ = frame.shape
        import numpy as np

        # 1. Background (1080x1920 desfocado)
        bg = cv2.resize(frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        ksize = int(blur_intensity * 2 + 1)
        if ksize % 2 == 0:
            ksize += 1
        bg = cv2.GaussianBlur(bg, (ksize, ksize), blur_intensity)
        bg = (bg * 0.88).astype(np.uint8)

        # 2. Foreground (com zoom e pan)
        w_fg = int(1080 * zoom)
        if w_fg % 2 != 0:
            w_fg += 1
        h_fg = int(h * (w_fg / w))

        scaled_fg = cv2.resize(frame, (w_fg, h_fg), interpolation=cv2.INTER_LINEAR)

        if w_fg > 1080:
            max_crop = w_fg - 1080
            crop_x = int(max_crop * (pan + 1.0) / 2.0)
            crop_x = max(0, min(max_crop, crop_x))
            cropped_fg = scaled_fg[:, crop_x : crop_x + 1080]
        else:
            cropped_fg = scaled_fg

        # Centraliza verticalmente
        y_start = max(0, (1920 - h_fg) // 2)
        y_end = min(1920, y_start + h_fg)

        bg[y_start:y_end, 0:1080] = cropped_fg[: y_end - y_start, :1080]

        cv2.imwrite(output_preview_path, bg)
        return {"path": output_preview_path, "error": None}
    except Exception as exc:
        return {"path": None, "error": str(exc)}



def crop_video_with_smart_face_tracking(
    input_video_path: str,
    start_time_str: str,
    end_time_str: str,
    output_video_path: str = "corte_smart_916.mp4",
    smoothing_alpha: float = 0.10,
    sample_detection_interval: int = 2,  # Detecta a cada 2 frames para máxima performance
    auto_zoom: bool = True,
    margin_ratio: float = 1.55,          # Margem de segurança nas laterais do interlocutor
    max_zoom_factor: float = 1.85,       # Zoom máximo permitido
    person_preference: str = "auto"      # 'auto', 'right', 'left', 'center'
) -> dict:
    """
    Recorta o vídeo no formato 9:16 (1080x1920) acompanhando o orador principal.
    Aplica Trava de Consistência Espacial (Target Lock) e Auto-Zoom inteligente com Cinematic Panning.
    """
    try:
        ensure_face_model()

        if os.path.exists(output_video_path):
            os.remove(output_video_path)

        out_dir = os.path.dirname(output_video_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        start_sec = parse_time_to_seconds(start_time_str)
        end_sec = parse_time_to_seconds(end_time_str)
        duration = end_sec - start_sec

        if duration <= 0:
            return {"path": None, "error": "Tempo final deve ser maior que o tempo inicial."}

        cap = cv2.VideoCapture(input_video_path)
        if not cap.isOpened():
            return {"path": None, "error": "Não foi possível abrir o arquivo de vídeo original."}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Dimensões base para 9:16
        base_crop_w = int(height * 9.0 / 16.0)
        if base_crop_w % 2 != 0:
            base_crop_w += 1
        
        min_crop_w = int(base_crop_w / max_zoom_factor) if auto_zoom else base_crop_w

        # Inicializa detector BlazeFace
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options)
        detector = vision.FaceDetector.create_from_options(options)

        # Configura o FFmpeg process pipe para renderização em 1080x1920 com áudio original
        temp_audio_cut = output_video_path + ".temp_audio.m4a"
        cmd_extract_audio = [
            FFMPEG_EXE, "-y",
            "-ss", start_time_str,
            "-to", end_time_str,
            "-i", input_video_path,
            "-vn", "-c:a", "aac", "-b:a", "192k",
            temp_audio_cut
        ]
        subprocess.run(cmd_extract_audio, capture_output=True)

        temp_video_no_audio = output_video_path + ".temp_video.mp4"
        cmd_ffmpeg_in = [
            FFMPEG_EXE, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"1080x1920",
            "-pix_fmt", "bgr24",
            "-r", f"{fps:.2f}",
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            temp_video_no_audio
        ]
        ffmpeg_proc = subprocess.Popen(cmd_ffmpeg_in, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

        # Posiciona no frame inicial
        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)
        total_cut_frames = max(1, end_frame - start_frame)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        current_w = float(base_crop_w)
        current_x = (width - base_crop_w) / 2.0
        current_y = 0.0

        smoothed_x = current_x
        smoothed_y = current_y
        smoothed_w = current_w
        last_tracked_center = None
        recent_dual_counts = []   # Histerese para estabilizar transições dual/individual
        frame_idx = 0

        while frame_idx < total_cut_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            # Executa detecção a cada N frames para economizar CPU
            if frame_idx % sample_detection_interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = detector.detect(mp_img)
                detections = results.detections if results.detections else []

                # ── Detecção de Dual Shot (Debate TV / Split-Screen) ────────────────
                is_broadcast = False
                use_dual_mode = False

                if person_preference in ("auto", "both"):
                    is_dual, is_broadcast = detect_dual_with_fallback(frame, detections, width, height)
                    # 'both' força o modo dual; 'auto' usa histerese para transições suaves
                    effective_dual = is_dual or (person_preference == "both")
                    recent_dual_counts.append(1 if effective_dual else 0)
                    if len(recent_dual_counts) > 6:
                        recent_dual_counts.pop(0)
                    avg_dual = sum(recent_dual_counts) / max(1, len(recent_dual_counts))
                    use_dual_mode = avg_dual >= 0.5

                if use_dual_mode:
                    # ── Bounding Box Composta: engloba AMBOS os interlocutores ────
                    prominent = filter_prominent_faces(
                        detections, width, height,
                        min_relative_area=0.15 if is_broadcast else 0.28
                    )
                    if len(prominent) >= 2:
                        min_bx = min(d.bounding_box.origin_x for d in prominent[:2])
                        max_bx = max(d.bounding_box.origin_x + d.bounding_box.width for d in prominent[:2])
                        min_by = min(d.bounding_box.origin_y for d in prominent[:2])
                        max_by = max(d.bounding_box.origin_y + d.bounding_box.height for d in prominent[:2])
                    elif is_broadcast and len(prominent) == 1:
                        # Split-screen confirmado mas 2º rosto não detectado (cabeça inclinada):
                        # estende o bbox para cobrir a metade oposta da tela automaticamente
                        bx_s = prominent[0].bounding_box
                        face_cx_s = bx_s.origin_x + bx_s.width / 2.0
                        if face_cx_s < width * 0.5:
                            min_bx = max(0, int(bx_s.origin_x - bx_s.width * 0.4))
                            max_bx = int(width * 0.90)
                        else:
                            min_bx = int(width * 0.05)
                            max_bx = min(width, int(bx_s.origin_x + bx_s.width + bx_s.width * 0.4))
                        min_by = max(0, bx_s.origin_y - int(bx_s.height * 0.3))
                        max_by = min(height, bx_s.origin_y + bx_s.height + int(bx_s.height * 0.3))
                    else:
                        use_dual_mode = False  # Fallback: rosto único

                    if use_dual_mode:
                        comp_bbox = CompositeBoundingBox(
                            min_bx, min_by,
                            max(1, max_bx - min_bx),
                            max(1, max_by - min_by)
                        )
                        target_face = CompositeFaceDetection(comp_bbox)
                        last_tracked_center = (min_bx + (max_bx - min_bx) / 2.0,
                                               min_by + (max_by - min_by) / 2.0)

                if not use_dual_mode:
                    # Seleciona com Trava de Continuidade Espacial (Target Lock)
                    target_face, last_tracked_center = select_target_face(
                        detections, width, height, last_tracked_center, person_preference
                    )

                if target_face is not None:
                    bx = target_face.bounding_box
                    face_cx = bx.origin_x + bx.width / 2.0
                    face_cy = bx.origin_y + bx.height * 0.45

                    if use_dual_mode:
                        # Dual Shot: zoom=1.0, centraliza entre os dois interlocutores
                        target_w = base_crop_w
                        target_h = height
                        target_x = face_cx - (base_crop_w / 2.0)
                        target_y = 0.0
                    elif auto_zoom:
                        # Modo individual: zoom automático com a margem configurável
                        body_width = bx.width * 2.0
                        target_w = int(body_width * margin_ratio)
                        target_w = max(min_crop_w, min(base_crop_w, target_w))
                        target_h = int(target_w * 16.0 / 9.0)
                        target_x = face_cx - (target_w / 2.0)
                        target_y = face_cy - (target_h * 0.35)
                    else:
                        target_w = base_crop_w
                        target_h = height
                        target_x = face_cx - (base_crop_w / 2.0)
                        target_y = 0.0

                    current_x = max(0.0, min(float(width - target_w), float(target_x)))
                    current_y = max(0.0, min(float(height - target_h), float(target_y)))
                    current_w = float(target_w)

            # Aplica suavização exponencial (Cinematic Panning & Smooth Zoom)
            smoothed_x = smoothing_alpha * current_x + (1.0 - smoothing_alpha) * smoothed_x
            smoothed_y = smoothing_alpha * current_y + (1.0 - smoothing_alpha) * smoothed_y
            smoothed_w = smoothing_alpha * current_w + (1.0 - smoothing_alpha) * smoothed_w

            sh = int(round(smoothed_w * 16.0 / 9.0))
            sw = int(round(smoothed_w))
            sx = max(0, min(width - sw, int(round(smoothed_x))))
            sy = max(0, min(height - sh, int(round(smoothed_y))))

            # Recorta a janela dinâmica 9:16 e redimensiona para 1080x1920
            cropped_frame = frame[sy : sy + sh, sx : sx + sw]
            resized_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)

            # Envia frame para o FFmpeg
            ffmpeg_proc.stdin.write(resized_frame.tobytes())
            frame_idx += 1

        cap.release()
        detector.close()
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()

        # Mescla vídeo renderizado com a faixa de áudio recortada
        if os.path.exists(temp_audio_cut) and os.path.getsize(temp_audio_cut) > 0:
            cmd_merge = [
                FFMPEG_EXE, "-y",
                "-i", temp_video_no_audio,
                "-i", temp_audio_cut,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_video_path
            ]
        else:
            cmd_merge = [
                FFMPEG_EXE, "-y",
                "-i", temp_video_no_audio,
                "-c:v", "copy",
                output_video_path
            ]
        subprocess.run(cmd_merge, capture_output=True)

        # Limpa arquivos temporários de forma segura
        for tmp_f in [temp_video_no_audio, temp_audio_cut]:
            if tmp_f and os.path.exists(tmp_f):
                try:
                    os.remove(tmp_f)
                except Exception:
                    pass

        if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
            return {"path": output_video_path, "error": None}
        else:
            return {"path": None, "error": "Falha ao gerar o corte vertical com rastreamento."}

    except Exception as exc:
        return {"path": None, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# Layout Dividido (Split Screen 9:16 - Topo: Entrevistador(es) / Base: Entrevistado)
# ──────────────────────────────────────────────────────────────────────────────

def detect_split_screen_params(
    video_path: str,
    timestamp_str: str,
    top_preference: str = "left",
    bottom_preference: str = "right"
) -> dict:
    """
    Detecta automaticamente as posições dos interlocutores para o Split Screen 9:16.
    Retorna os fatores normalizados de enquadramento (-1.0 a +1.0) para Topo e Base.
    """
    try:
        ensure_face_model()
        t_sec = parse_time_to_seconds(timestamp_str)
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"top_pan": -0.65, "bottom_pan": 0.65, "zoom": 1.15}

        h, w = frame.shape[:2]

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
        detector = vision.FaceDetector.create_from_options(options)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        results = detector.detect(mp_image)
        detector.close()

        if not results.detections or len(results.detections) < 2:
            return {"top_pan": -0.65, "bottom_pan": 0.65, "zoom": 1.15}

        detections = results.detections
        sorted_faces = sorted(detections, key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0)

        left_cx = sorted_faces[0].bounding_box.origin_x + sorted_faces[0].bounding_box.width / 2.0
        right_cx = sorted_faces[-1].bounding_box.origin_x + sorted_faces[-1].bounding_box.width / 2.0

        left_pan = max(-0.85, min(0.85, (left_cx / (w / 2.0)) - 1.0))
        right_pan = max(-0.85, min(0.85, (right_cx / (w / 2.0)) - 1.0))

        top_pan = left_pan if top_preference == "left" else right_pan
        bottom_pan = right_pan if bottom_preference == "right" else left_pan

        return {"top_pan": round(top_pan, 2), "bottom_pan": round(bottom_pan, 2), "zoom": 1.20}

    except Exception:
        return {"top_pan": -0.65, "bottom_pan": 0.65, "zoom": 1.15}


def fit_frame_to_slot(img: np.ndarray, target_w: int = 1080, target_h: int = 960) -> np.ndarray:
    """
    Redimensiona e recorta centralizadamente a imagem/frame para preencher
    exatamente o slot (target_w x target_h) sem distorção (Aspect Fill / Center Crop).
    """
    if img is None:
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)
    ih, iw = img.shape[:2]
    if ih == 0 or iw == 0:
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)
    
    scale = max(float(target_w) / float(iw), float(target_h) / float(ih))
    new_w = int(round(iw * scale))
    new_h = int(round(ih * scale))
    
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(img, (new_w, new_h), interpolation=interp)
    
    x1 = max(0, (new_w - target_w) // 2)
    y1 = max(0, (new_h - target_h) // 2)
    cropped = resized[y1 : y1 + target_h, x1 : x1 + target_w]
    
    if cropped.shape[0] != target_h or cropped.shape[1] != target_w:
        cropped = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    return cropped


def load_images_for_slideshow(image_paths: list, target_w: int = 1080, target_h: int = 960) -> list:
    """
    Carrega e formata uma lista de imagens para exibição em slideshow 1080x960.
    Suporta caminhos do Windows e caracteres especiais (cv2.imdecode).
    """
    loaded = []
    if not image_paths:
        return loaded
    for img_p in image_paths:
        if not img_p or not os.path.exists(img_p):
            continue
        try:
            with open(img_p, "rb") as f_in:
                bytes_data = np.frombuffer(f_in.read(), dtype=np.uint8)
                img = cv2.imdecode(bytes_data, cv2.IMREAD_COLOR)
                if img is not None:
                    loaded.append(fit_frame_to_slot(img, target_w, target_h))
        except Exception:
            continue
    return loaded


def generate_split_preview_image(
    input_video_path: str,
    timestamp_str: str,
    output_preview_path: str = "temp_split_preview.jpg",
    top_pan: float = -0.65,
    bottom_pan: float = 0.65,
    zoom: float = 1.15,
    divider_color: str = "black",
    divider_width: int = 4,
    split_source_type: str = "main_video",
    split_video_path: str = None,
    split_image_paths: list = None,
    split_media_position: str = "bottom",
    split_blur_margin_pct: float = 5.0
) -> dict:
    """
    Gera uma imagem de prévia instantânea do Layout Dividido (Split Screen 9:16),
    com suporte a vídeo principal duplo, vídeo secundário em looping, slideshow de imagens
    e margens com fundo desfocado no topo e na base.
    """
    try:
        t_sec = parse_time_to_seconds(timestamp_str)
        cap = cv2.VideoCapture(input_video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"path": None, "error": "Não foi possível extrair o frame do vídeo para a prévia."}

        h, w = frame.shape[:2]

        # Cálculo das margens com blur (topo & base)
        margin_pct = max(0.0, min(25.0, float(split_blur_margin_pct)))
        if margin_pct > 0.0:
            margin_px = int(round(1920.0 * (margin_pct / 100.0)))
            slot_h = max(200, (1920 - 2 * margin_px) // 2)
            content_h = 2 * slot_h
            actual_top_margin = (1920 - content_h) // 2
        else:
            slot_h = 960
            content_h = 1920
            actual_top_margin = 0

        base_w = int(h * 1.125 / zoom)
        base_h = int(h / zoom)

        max_x = max(0, w - base_w)
        max_y = max(0, h - base_h)

        # Coordenadas Topo
        top_x = int(max(0, min(max_x, (max_x / 2.0) + (top_pan * (max_x / 2.0)))))
        top_y = int(max(0, min(max_y, max_y / 2.0)))

        # Coordenadas Base
        bot_x = int(max(0, min(max_x, (max_x / 2.0) + (bottom_pan * (max_x / 2.0)))))
        bot_y = top_y

        # Recorta frames do vídeo principal
        top_crop = frame[top_y : top_y + base_h, top_x : top_x + base_w]
        bot_crop = frame[bot_y : bot_y + base_h, bot_x : bot_x + base_w]

        top_resized = cv2.resize(top_crop, (1080, slot_h), interpolation=cv2.INTER_LINEAR)
        bot_resized = cv2.resize(bot_crop, (1080, slot_h), interpolation=cv2.INTER_LINEAR)

        # Processa Mídia Secundária caso selecionada
        sec_res = None
        if split_source_type == "video" and split_video_path and os.path.exists(split_video_path):
            try:
                sec_cap = cv2.VideoCapture(split_video_path)
                sec_fps = sec_cap.get(cv2.CAP_PROP_FPS) or 30.0
                sec_frames = int(sec_cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
                sec_dur = max(0.1, sec_frames / float(sec_fps))
                sec_t = (t_sec % sec_dur)
                sec_cap.set(cv2.CAP_PROP_POS_MSEC, sec_t * 1000.0)
                ret_s, f_s = sec_cap.read()
                sec_cap.release()
                if ret_s and f_s is not None:
                    sec_res = fit_frame_to_slot(f_s, 1080, slot_h)
            except Exception:
                sec_res = None

        elif split_source_type == "images" and split_image_paths:
            imgs = load_images_for_slideshow(split_image_paths, 1080, slot_h)
            if imgs:
                sec_res = imgs[0]

        # Monta conteúdo ativo
        if sec_res is not None:
            if split_media_position == "top":
                active_content = cv2.vconcat([sec_res, top_resized])
            else:
                active_content = cv2.vconcat([top_resized, sec_res])
        else:
            active_content = cv2.vconcat([top_resized, bot_resized])

        # Aplica margens com fundo desfocado se margin_pct > 0
        if actual_top_margin > 0:
            bg_scale = max(1080.0 / float(w), 1920.0 / float(h))
            bg_w = int(round(w * bg_scale))
            bg_h = int(round(h * bg_scale))
            bg_resized = cv2.resize(frame, (bg_w, bg_h), interpolation=cv2.INTER_LINEAR)
            bg_x = max(0, (bg_w - 1080) // 2)
            bg_y = max(0, (bg_h - 1920) // 2)
            bg_cropped = bg_resized[bg_y : bg_y + 1920, bg_x : bg_x + 1080]

            bg_small = cv2.resize(bg_cropped, (108, 192), interpolation=cv2.INTER_LINEAR)
            bg_blur_small = cv2.GaussianBlur(bg_small, (21, 21), 0)
            bg_blur = cv2.resize(bg_blur_small, (1080, 1920), interpolation=cv2.INTER_LINEAR)
            bg_blur = cv2.convertScaleAbs(bg_blur, alpha=0.85, beta=0)

            canvas = bg_blur
            canvas[actual_top_margin : actual_top_margin + content_h, 0:1080] = active_content
        else:
            canvas = active_content

        # Desenha linha divisória elegante
        if divider_width > 0:
            div_c = (0, 0, 0) if divider_color == "black" else ((255, 255, 255) if divider_color == "white" else (180, 180, 180))
            y_mid = actual_top_margin + slot_h
            y1 = max(0, y_mid - divider_width // 2)
            y2 = min(1920, y_mid + divider_width // 2)
            canvas[y1:y2, :] = div_c

        cv2.imwrite(output_preview_path, canvas)
        return {"path": output_preview_path, "error": None}

    except Exception as exc:
        return {"path": None, "error": str(exc)}


def crop_video_with_dynamic_auto_switch(
    input_video_path: str,
    start_time_str: str,
    end_time_str: str,
    output_video_path: str = "corte_dynamic_switch.mp4",
    split_zoom: float = 1.15,
    top_pan: float = -0.65,
    bottom_pan: float = 0.65,
    divider_color: str = "black",
    divider_width: int = 4,
    auto_switch_enabled: bool = True,
    split_source_type: str = "main_video",
    split_video_path: str = None,
    split_image_paths: list = None,
    split_media_position: str = "bottom",
    split_blur_margin_pct: float = 5.0
) -> dict:
    """
    Renderiza vídeo 9:16 em Layout Dividido (Split Screen):
    - Modo Padrão: Quando houver >= 2 pessoas, aplica Split Screen (Topo e Base).
    - Modo Vídeo Secundário: Insere vídeo local em looping contínuo na base (ou topo).
    - Modo Slideshow de Imagens: Apresenta imagens proporcionalmente ao tempo do vídeo.
    - Margens com Fundo Desfocado: Adiciona margens com blur cinematográfico no topo e na base.
    - Se auto_switch_enabled e sem mídia secundária: transiciona suavemente para 9:16 Full Screen em close-ups.
    """
    sec_cap = None
    try:
        ensure_face_model()
        start_s = parse_time_to_seconds(start_time_str)
        end_s = parse_time_to_seconds(end_time_str)

        cap = cv2.VideoCapture(input_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        start_frame = int(start_s * fps)
        end_frame = int(end_s * fps)
        total_cut_frames = max(1, end_frame - start_frame)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        out_dir = os.path.dirname(output_video_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        temp_audio_cut = os.path.join(out_dir, "temp_dyn_audio.m4a") if out_dir else "temp_dyn_audio.m4a"
        temp_video_raw = os.path.join(out_dir, "temp_dyn_raw.mp4") if out_dir else "temp_dyn_raw.mp4"

        # Extrai áudio sincronizado do vídeo principal
        cmd_audio = [
            FFMPEG_EXE, "-y",
            "-ss", start_time_str,
            "-to", end_time_str,
            "-i", input_video_path,
            "-vn", "-c:a", "aac", "-b:a", "192k",
            temp_audio_cut
        ]
        subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        # Cálculo das margens com blur (topo & base)
        margin_pct = max(0.0, min(25.0, float(split_blur_margin_pct)))
        if margin_pct > 0.0:
            margin_px = int(round(1920.0 * (margin_pct / 100.0)))
            slot_h = max(200, (1920 - 2 * margin_px) // 2)
            content_h = 2 * slot_h
            actual_top_margin = (1920 - content_h) // 2
        else:
            slot_h = 960
            content_h = 1920
            actual_top_margin = 0

        # Prepara Mídia Secundária (Vídeo em Looping ou Slideshow de Imagens)
        use_custom_secondary = split_source_type in ["video", "images"]
        slideshow_frames = []

        if split_source_type == "video" and split_video_path and os.path.exists(split_video_path):
            sec_cap = cv2.VideoCapture(split_video_path)
        elif split_source_type == "images" and split_image_paths:
            slideshow_frames = load_images_for_slideshow(split_image_paths, 1080, slot_h)

        # Inicia processo FFmpeg para receber os frames 1080x1920 via stdin
        cmd_ffmpeg = [
            FFMPEG_EXE, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", "1080x1920",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            temp_video_raw
        ]
        ffmpeg_proc = subprocess.Popen(cmd_ffmpeg, stdin=subprocess.PIPE)

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
        detector = vision.FaceDetector.create_from_options(options)

        current_mode = "split"
        recent_face_counts = []
        current_single_cx = 960.0

        frame_idx = 0
        while frame_idx < total_cut_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            h, w = frame.shape[:2]

            # Auto-switch só se aplica quando NÃO estiver usando mídia secundária personalizada
            if auto_switch_enabled and not use_custom_secondary:
                if frame_idx % 2 == 0 or frame_idx == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    results = detector.detect(mp_image)
                    num_faces = len(results.detections) if results.detections else 0
                    recent_face_counts.append(num_faces)
                    if len(recent_face_counts) > 8:
                        recent_face_counts.pop(0)

                    avg_faces = sum(recent_face_counts) / len(recent_face_counts)
                    if avg_faces >= 1.4:
                        current_mode = "split"
                    elif avg_faces <= 1.1 and num_faces == 1:
                        current_mode = "single"

                    if current_mode == "single" and results.detections:
                        target_f = max(results.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                        bx = target_f.bounding_box
                        raw_cx = bx.origin_x + bx.width / 2.0
                        current_single_cx = current_single_cx * 0.80 + raw_cx * 0.20
            else:
                current_mode = "split"

            if current_mode == "split":
                base_w = int(h * 1.125 / split_zoom)
                base_h = int(h / split_zoom)
                max_x = max(0, w - base_w)
                max_y = max(0, h - base_h)
                top_x = int(max(0, min(max_x, (max_x / 2.0) + (top_pan * (max_x / 2.0)))))
                top_y = int(max(0, min(max_y, max_y / 2.0)))
                bot_x = int(max(0, min(max_x, (max_x / 2.0) + (bottom_pan * (max_x / 2.0)))))
                bot_y = top_y

                top_crop = frame[top_y : top_y + base_h, top_x : top_x + base_w]
                top_res = cv2.resize(top_crop, (1080, slot_h), interpolation=cv2.INTER_LINEAR)

                # Processa slot secundário
                sec_slot_res = None
                if split_source_type == "video" and sec_cap is not None and sec_cap.isOpened():
                    ret_s, f_s = sec_cap.read()
                    if not ret_s or f_s is None:
                        # Looping contínuo caso o vídeo secundário seja menor que o principal
                        sec_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret_s, f_s = sec_cap.read()
                    if ret_s and f_s is not None:
                        sec_slot_res = fit_frame_to_slot(f_s, 1080, slot_h)
                    else:
                        sec_slot_res = np.zeros((slot_h, 1080, 3), dtype=np.uint8)

                elif split_source_type == "images" and slideshow_frames:
                    n_imgs = len(slideshow_frames)
                    idx_img = min(int((float(frame_idx) / max(1.0, float(total_cut_frames))) * n_imgs), n_imgs - 1)
                    sec_slot_res = slideshow_frames[idx_img]

                if sec_slot_res is not None:
                    if split_media_position == "top":
                        active_content = cv2.vconcat([sec_slot_res, top_res])
                    else:
                        active_content = cv2.vconcat([top_res, sec_slot_res])
                else:
                    bot_crop = frame[bot_y : bot_y + base_h, bot_x : bot_x + base_w]
                    bot_res = cv2.resize(bot_crop, (1080, slot_h), interpolation=cv2.INTER_LINEAR)
                    active_content = cv2.vconcat([top_res, bot_res])

                # Aplica margens com fundo desfocado se margin_pct > 0
                if actual_top_margin > 0:
                    bg_scale = max(1080.0 / float(w), 1920.0 / float(h))
                    bg_w = int(round(w * bg_scale))
                    bg_h = int(round(h * bg_scale))
                    bg_resized = cv2.resize(frame, (bg_w, bg_h), interpolation=cv2.INTER_LINEAR)
                    bg_x = max(0, (bg_w - 1080) // 2)
                    bg_y = max(0, (bg_h - 1920) // 2)
                    bg_cropped = bg_resized[bg_y : bg_y + 1920, bg_x : bg_x + 1080]

                    bg_small = cv2.resize(bg_cropped, (108, 192), interpolation=cv2.INTER_LINEAR)
                    bg_blur_small = cv2.GaussianBlur(bg_small, (21, 21), 0)
                    bg_blur = cv2.resize(bg_blur_small, (1080, 1920), interpolation=cv2.INTER_LINEAR)
                    bg_blur = cv2.convertScaleAbs(bg_blur, alpha=0.85, beta=0)

                    out_frame = bg_blur
                    out_frame[actual_top_margin : actual_top_margin + content_h, 0:1080] = active_content
                else:
                    out_frame = active_content

                if divider_width > 0:
                    div_c = (0, 0, 0) if divider_color == "black" else ((255, 255, 255) if divider_color == "white" else (180, 180, 180))
                    y_mid = actual_top_margin + slot_h
                    y1 = max(0, y_mid - divider_width // 2)
                    y2 = min(1920, y_mid + divider_width // 2)
                    out_frame[y1:y2, :] = div_c
            else:
                # Single person 9:16 full-screen crop
                crop_w = int(h * (9.0 / 16.0))
                crop_h = h
                max_cx = w - crop_w // 2
                min_cx = crop_w // 2
                clamped_cx = max(min_cx, min(max_cx, int(current_single_cx)))
                x1 = clamped_cx - crop_w // 2
                x2 = x1 + crop_w
                single_crop = frame[0:crop_h, x1:x2]
                out_frame = cv2.resize(single_crop, (1080, 1920), interpolation=cv2.INTER_LINEAR)

            ffmpeg_proc.stdin.write(out_frame.tobytes())
            frame_idx += 1

        cap.release()
        if sec_cap is not None and sec_cap.isOpened():
            sec_cap.release()
        detector.close()
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()

        # Mescla áudio e vídeo
        if os.path.exists(temp_audio_cut) and os.path.getsize(temp_audio_cut) > 0:
            cmd_merge = [
                FFMPEG_EXE, "-y",
                "-i", temp_video_raw,
                "-i", temp_audio_cut,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_video_path
            ]
        else:
            cmd_merge = [
                FFMPEG_EXE, "-y",
                "-i", temp_video_raw,
                "-c:v", "copy",
                output_video_path
            ]
        subprocess.run(cmd_merge, capture_output=True)

        # Limpa arquivos temporários de forma segura
        for tmp_f in [temp_video_raw, temp_audio_cut]:
            if tmp_f and os.path.exists(tmp_f):
                try:
                    os.remove(tmp_f)
                except Exception:
                    pass

        if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
            return {"path": output_video_path, "error": None}
        else:
            return {"path": None, "error": "Falha ao gerar o corte dinâmico."}

    except Exception as exc:
        return {"path": None, "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline 9:16 Fundo Desfocado com Rastreamento Inteligente de Personagem
# (Dynamic Auto-Reframing com Blur no Background)
# ──────────────────────────────────────────────────────────────────────────────

def crop_video_with_smart_blur_tracking(
    input_video_path: str,
    start_time_str: str,
    end_time_str: str,
    output_video_path: str,
    blur_zoom: float = 1.35,
    person_preference: str = "auto",
    face_margin_ratio: float = 1.55,
    auto_tracking: bool = True
) -> dict:
    """
    Renderiza vídeo vertical 9:16 (1080x1920) com fundo desfocado dinâmico e
    Auto-Reframing contínuo no foreground, mantendo o personagem principal (ou ambos em Dual Shot)
    perfeitamente enquadrado e centralizado com movimento cinematográfico suave (sem tremulações).
    """
    try:
        ensure_face_model()

        start_sec = parse_time_to_seconds(start_time_str)
        end_sec = parse_time_to_seconds(end_time_str)
        duration_sec = max(0.5, end_sec - start_sec)

        cap = cv2.VideoCapture(input_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 30.0

        total_input_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        start_frame = int(start_sec * fps)
        total_cut_frames = int(duration_sec * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        out_dir = os.path.dirname(output_video_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        temp_audio_cut = os.path.join(out_dir, "temp_blur_audio.m4a") if out_dir else "temp_blur_audio.m4a"
        temp_video_raw = os.path.join(out_dir, "temp_blur_raw.mp4") if out_dir else "temp_blur_raw.mp4"

        # Extrai áudio sincronizado do corte
        cmd_audio = [
            FFMPEG_EXE, "-y",
            "-ss", start_time_str,
            "-to", end_time_str,
            "-i", input_video_path,
            "-vn", "-c:a", "aac", "-b:a", "192k",
            temp_audio_cut
        ]
        subprocess.run(cmd_audio, capture_output=True)

        # Inicia processo FFmpeg para receber os frames 1080x1920 via stdin
        cmd_ffmpeg = [
            FFMPEG_EXE, "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", "1080x1920",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            temp_video_raw
        ]
        ffmpeg_proc = subprocess.Popen(cmd_ffmpeg, stdin=subprocess.PIPE)

        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceDetectorOptions(base_options=base_options, min_detection_confidence=0.35)
        detector = vision.FaceDetector.create_from_options(options)

        # Inicialização do Rastreamento com Zona Morta (Deadband Anchor) e Trava de Estabilidade
        anchor_crop_x = None
        smoothed_crop_x = None
        last_tracked_center = None
        recent_dual_counts = []
        deadband_px = 90  # Zona de conforto: 90px no foreground onde a câmera fica 100% estática

        smoothing_alpha = 0.025  # Transição imperceptivelmente suave e cinematográfica

        frame_idx = 0
        while frame_idx < total_cut_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            height, width = frame.shape[:2]

            # Dimensões do foreground ampliado
            effective_zoom = max(1.0, blur_zoom)
            w_fg = int(round(1080 * effective_zoom))
            if w_fg % 2 != 0:
                w_fg += 1
            h_fg = int(round(w_fg * (height / float(width))))
            if h_fg % 2 != 0:
                h_fg += 1
            max_crop_x = max(0, w_fg - 1080)

            # Rastreamento a cada 2 frames para máxima performance e estabilidade
            if auto_tracking and (frame_idx % 2 == 0 or anchor_crop_x is None):
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = detector.detect(mp_img)
                detections = results.detections if results.detections else []

                # Detecção de Dual Shot com histerese estrita (mínimo de 10 amostras confirmadas)
                is_broadcast = False
                use_dual_mode = False
                if person_preference in ("auto", "both"):
                    is_dual, is_broadcast = detect_dual_with_fallback(frame, detections, width, height)
                    effective_dual = is_dual or (person_preference == "both")
                    recent_dual_counts.append(1 if effective_dual else 0)
                    if len(recent_dual_counts) > 12:
                        recent_dual_counts.pop(0)
                    avg_dual = sum(recent_dual_counts) / max(1, len(recent_dual_counts))
                    use_dual_mode = avg_dual >= 0.70  # Exige 70% de consistência para alternar modo

                target_face = None
                if use_dual_mode:
                    prominent = filter_prominent_faces(
                        detections, width, height,
                        min_relative_area=0.15 if is_broadcast else 0.28
                    )
                    if len(prominent) >= 2:
                        min_bx = min(d.bounding_box.origin_x for d in prominent[:2])
                        max_bx = max(d.bounding_box.origin_x + d.bounding_box.width for d in prominent[:2])
                        min_by = min(d.bounding_box.origin_y for d in prominent[:2])
                        max_by = max(d.bounding_box.origin_y + d.bounding_box.height for d in prominent[:2])
                    elif is_broadcast and len(prominent) == 1:
                        bx_s = prominent[0].bounding_box
                        face_cx_s = bx_s.origin_x + bx_s.width / 2.0
                        if face_cx_s < width * 0.5:
                            min_bx = max(0, int(bx_s.origin_x - bx_s.width * 0.4))
                            max_bx = int(width * 0.90)
                        else:
                            min_bx = int(width * 0.05)
                            max_bx = min(width, int(bx_s.origin_x + bx_s.width + bx_s.width * 0.4))
                        min_by = max(0, bx_s.origin_y - int(bx_s.height * 0.3))
                        max_by = min(height, bx_s.origin_y + bx_s.height + int(bx_s.height * 0.3))
                    else:
                        use_dual_mode = False

                    if use_dual_mode:
                        comp_bbox = CompositeBoundingBox(
                            min_bx, min_by,
                            max(1, max_bx - min_bx),
                            max(1, max_by - min_by)
                        )
                        target_face = CompositeFaceDetection(comp_bbox)
                        last_tracked_center = (min_bx + (max_bx - min_bx) / 2.0,
                                               min_by + (max_by - min_by) / 2.0)

                if not use_dual_mode:
                    target_face, last_tracked_center = select_target_face(
                        detections, width, height, last_tracked_center, person_preference
                    )

                if target_face is not None:
                    bx = target_face.bounding_box
                    face_cx = bx.origin_x + bx.width / 2.0
                    raw_target_x = int(round((face_cx / float(width)) * w_fg - 540.0))
                    raw_target_x = max(0, min(max_crop_x, raw_target_x))

                    if anchor_crop_x is None:
                        anchor_crop_x = raw_target_x
                    else:
                        # Corte de Cena (Shot Transition): se pular mais de 45% da tela, reposiciona imediatamente
                        if abs(raw_target_x - anchor_crop_x) > (max_crop_x * 0.45):
                            anchor_crop_x = raw_target_x
                            smoothed_crop_x = float(raw_target_x)
                        else:
                            # Zona Morta (Deadband): se o orador estiver dentro da zona de conforto, a câmera NÃO se move!
                            diff = abs(raw_target_x - anchor_crop_x)
                            if diff > deadband_px:
                                if raw_target_x > anchor_crop_x:
                                    anchor_crop_x = raw_target_x - deadband_px
                                else:
                                    anchor_crop_x = raw_target_x + deadband_px
                else:
                    # Rosto temporariamente não detectado (olhando para baixo / b-roll): MANTÉM a posição anterior travada!
                    if anchor_crop_x is None:
                        anchor_crop_x = max_crop_x // 2

            if anchor_crop_x is None:
                anchor_crop_x = max_crop_x // 2
            if smoothed_crop_x is None:
                smoothed_crop_x = float(anchor_crop_x)

            # Suavização imperceptível e livre de micro-tremores
            smoothed_crop_x = smoothing_alpha * anchor_crop_x + (1.0 - smoothing_alpha) * smoothed_crop_x
            sx = max(0, min(max_crop_x, int(round(smoothed_crop_x))))


            # ── 1. GERAÇÃO DO FUNDO DESFOCADO (1080x1920) ────────────────────
            bg_scale = max(1080.0 / float(width), 1920.0 / float(height))
            bg_w = int(round(width * bg_scale))
            bg_h = int(round(height * bg_scale))
            bg_resized = cv2.resize(frame, (bg_w, bg_h), interpolation=cv2.INTER_LINEAR)
            bg_x = max(0, (bg_w - 1080) // 2)
            bg_y = max(0, (bg_h - 1920) // 2)
            bg_cropped = bg_resized[bg_y : bg_y + 1920, bg_x : bg_x + 1080]

            # Fast Bokeh Blur (Downscale + Blur + Upscale) + leve escurecimento de contraste
            bg_small = cv2.resize(bg_cropped, (108, 192), interpolation=cv2.INTER_LINEAR)
            bg_blur = cv2.GaussianBlur(bg_small, (15, 15), 0)
            bg_full = cv2.resize(bg_blur, (1080, 1920), interpolation=cv2.INTER_LINEAR)
            bg_full = cv2.convertScaleAbs(bg_full, alpha=0.88, beta=-10)

            # ── 2. GERAÇÃO DO FOREGROUND NÍTIDO ENQUADRADO ───────────────────
            fg_scaled = cv2.resize(frame, (w_fg, h_fg), interpolation=cv2.INTER_LINEAR)
            fg_cropped = fg_scaled[0 : h_fg, sx : sx + 1080]

            # ── 3. COMPOSIÇÃO: FOREGROUND SOBREPOSTO NO CENTRO DO BACKGROUND ──
            y_offset = max(0, (1920 - h_fg) // 2)
            bg_full[y_offset : y_offset + h_fg, 0 : 1080] = fg_cropped

            ffmpeg_proc.stdin.write(bg_full.tobytes())
            frame_idx += 1

        cap.release()
        detector.close()
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()

        # Mescla vídeo renderizado com a faixa de áudio sincronizada
        if os.path.exists(temp_audio_cut) and os.path.getsize(temp_audio_cut) > 0:
            cmd_merge = [
                FFMPEG_EXE, "-y",
                "-i", temp_video_raw,
                "-i", temp_audio_cut,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_video_path
            ]
        else:
            cmd_merge = [
                FFMPEG_EXE, "-y",
                "-i", temp_video_raw,
                "-c:v", "copy",
                output_video_path
            ]
        subprocess.run(cmd_merge, capture_output=True)

        # Limpeza segura de arquivos temporários
        for tmp_f in [temp_video_raw, temp_audio_cut]:
            if tmp_f and os.path.exists(tmp_f):
                try:
                    os.remove(tmp_f)
                except Exception:
                    pass

        if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
            return {"path": output_video_path, "error": None}
        else:
            return {"path": None, "error": "Falha ao gerar o corte vertical com fundo desfocado e rastreamento."}

    except Exception as exc:
        return {"path": None, "error": str(exc)}


def generate_169_preview_image(
    video_path: str,
    timestamp_str: str,
    output_path: str,
    zoom_factor: float = 1.0
) -> dict:
    """
    Gera uma prévia visual instantânea do enquadramento horizontal 16:9 com zoom/aproximação.
    """
    try:
        t_sec = parse_time_to_seconds(timestamp_str)
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return {"path": None, "error": "Não foi possível capturar o frame para a prévia 16:9."}

        h, w = frame.shape[:2]
        effective_zoom = max(1.0, float(zoom_factor))
        if effective_zoom > 1.001:
            crop_w = int(round(w / effective_zoom))
            crop_h = int(round(h / effective_zoom))
            x1 = max(0, (w - crop_w) // 2)
            y1 = max(0, (h - crop_h) // 2)
            cropped = frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
            resized = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            resized = frame

        cv2.imwrite(output_path, resized, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        return {"path": output_path, "error": None}
    except Exception as exc:
        return {"path": None, "error": str(exc)}

