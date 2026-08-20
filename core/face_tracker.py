"""
face_tracker.py — Rastreamento Inteligente de Rosto, Trava de Alvo (Target Lock) e Auto-Reframing Vertical (9:16)
Detecta o orador principal com Google MediaPipe BlazeFace e realiza movimento suave de câmera (Cinematic Panning).
"""

import os
import cv2
import urllib.request
import subprocess
import imageio_ffmpeg
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


def select_target_face(detections, frame_width: int, frame_height: int, last_tracked_center=None, person_preference: str = "auto"):
    """
    Seleciona o rosto alvo respeitando a preferência do usuário e mantendo a
    Trava de Continuidade Espacial (Target Lock) para nunca pular para outra pessoa na cena.
    """
    if not detections:
        return None, last_tracked_center

    # Se já temos um alvo rastreado anteriormente, usamos a menor distância euclidiana (Target Lock)
    if last_tracked_center is not None:
        last_cx, last_cy = last_tracked_center
        best_face = None
        min_dist = float('inf')
        for d in detections:
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
        # Pessoa mais à direita da tela
        best_face = max(detections, key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0)
    elif person_preference == "left":
        # Pessoa mais à esquerda da tela
        best_face = min(detections, key=lambda d: d.bounding_box.origin_x + d.bounding_box.width / 2.0)
    elif person_preference == "center":
        # Pessoa mais próxima do centro da tela
        center_x = frame_width / 2.0
        best_face = min(detections, key=lambda d: abs((d.bounding_box.origin_x + d.bounding_box.width / 2.0) - center_x))
    else:
        # Modo 'auto': maior área / dominância inicial
        best_face = max(detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)

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
        target_face, _ = select_target_face(detections, width, height, None, person_preference)

        preview_img = frame.copy()

        # Desenha as caixas dos rostos
        for d in detections:
            is_target = (d == target_face)
            bx = d.bounding_box
            color = (0, 255, 0) if is_target else (220, 120, 50)  # Verde para alvo, Laranja para outros
            cv2.rectangle(preview_img, (bx.origin_x, bx.origin_y), (bx.origin_x + bx.width, bx.origin_y + bx.height), color, 3)

            label = "ALVO PRINCIPAL" if is_target else "OUTRO"
            cv2.putText(preview_img, label, (bx.origin_x, max(24, bx.origin_y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Desenha a janela do enquadramento vertical 9:16
        if target_face is not None:
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

            # Desenha moldura de corte 9:16 em ciano
            cv2.rectangle(preview_img, (x1, y1), (x2, y2), (255, 255, 0), 4)
            cv2.putText(preview_img, "ENQUADRAMENTO 9:16", (x1 + 10, y1 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.imwrite(output_preview_path, preview_img)
        return {"path": output_preview_path, "detected_count": len(detections), "error": None}

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
        target_face, _ = select_target_face(detections, width, height, None, person_preference)

        if target_face is None:
            return {"zoom": 1.35, "pan": 0.0, "face_detected": False}

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
            "face_detected": True
        }
    except Exception:
        return {"zoom": 1.35, "pan": 0.0, "face_detected": False}


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
        temp_audio_cut = output_video_path + ".temp_audio.aac"
        cmd_extract_audio = [
            FFMPEG_EXE, "-y",
            "-ss", start_time_str,
            "-to", end_time_str,
            "-i", input_video_path,
            "-vn", "-c:a", "copy",
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

        # Posiciona no início
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000.0)

        current_w = float(base_crop_w)
        current_x = (width - base_crop_w) / 2.0
        current_y = 0.0

        smoothed_x = current_x
        smoothed_y = current_y
        smoothed_w = current_w
        last_tracked_center = None
        frame_idx = 0

        while cap.isOpened():
            pos_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if pos_sec > end_sec + 0.05:
                break

            ret, frame = cap.read()
            if not ret:
                break

            # Executa detecção a cada N frames para economizar CPU
            if frame_idx % sample_detection_interval == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                results = detector.detect(mp_img)
                detections = results.detections if results.detections else []

                # Seleciona com Trava de Continuidade Espacial (Target Lock)
                target_face, last_tracked_center = select_target_face(
                    detections, width, height, last_tracked_center, person_preference
                )

                if target_face is not None:
                    bx = target_face.bounding_box
                    face_cx = bx.origin_x + bx.width / 2.0
                    face_cy = bx.origin_y + bx.height * 0.45

                    if auto_zoom:
                        # Estima a largura dos ombros/busto com a margem configurável
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

        # Limpa arquivos temporários
        if os.path.exists(temp_video_no_audio):
            os.remove(temp_video_no_audio)
        if os.path.exists(temp_audio_cut):
            os.remove(temp_audio_cut)

        if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
            return {"path": output_video_path, "error": None}
        else:
            return {"path": None, "error": "Falha ao gerar o corte vertical com rastreamento."}

    except Exception as exc:
        return {"path": None, "error": str(exc)}
