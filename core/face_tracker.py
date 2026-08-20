"""
face_tracker.py — Rastreamento Inteligente de Rosto e Auto-Reframing Vertical (9:16)
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


def crop_video_with_smart_face_tracking(
    input_video_path: str,
    start_time_str: str,
    end_time_str: str,
    output_video_path: str = "corte_smart_916.mp4",
    smoothing_alpha: float = 0.12,
    sample_detection_interval: int = 2  # Detecta a cada 2 frames para máxima velocidade
) -> dict:
    """
    Recorta o vídeo no formato 9:16 (1080x1920) acompanhando o orador principal.
    Aplica interpolação suave (Cinematic Panning) para movimentos naturais de câmera.
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

        # Calcula a janela de corte 9:16 com base na altura
        crop_w = int(height * 9.0 / 16.0)
        if crop_w % 2 != 0:
            crop_w += 1
        max_x = width - crop_w

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

        current_x = (width - crop_w) / 2.0
        smoothed_x = current_x
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

                if results.detections:
                    # Escolhe a face principal (maior área no quadro)
                    main_face = max(results.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
                    bx = main_face.bounding_box
                    face_center_x = bx.origin_x + bx.width / 2.0
                    target_x = face_center_x - crop_w / 2.0
                    current_x = max(0.0, min(float(max_x), float(target_x)))

            # Aplica suavização exponencial (Cinematic Panning)
            smoothed_x = smoothing_alpha * current_x + (1.0 - smoothing_alpha) * smoothed_x
            x_int = int(round(smoothed_x))
            x_int = max(0, min(max_x, x_int))

            # Recorta a janela 9:16 e redimensiona para 1080x1920
            cropped_frame = frame[:, x_int : x_int + crop_w]
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
