"""
frame_capturer.py — Motor de Captura de Frames e Gerenciamento de Thumbnails
Permite extrair frames de alta resolução em pontos exatos de vídeos/cortes (com precisão de milissegundos),
gerar downloads instantâneos e definir frames capturados diretamente como Thumbnails (Capas) oficiais.
"""

import os
import re
import base64
import cv2
import numpy as np
from PIL import Image
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def parse_time_str_to_seconds(time_str: str) -> float:
    """
    Converte strings de tempo nos formatos HH:MM:SS.ms, MM:SS.ms, SS.ms ou segundos numéricos para float.
    Exemplos:
      '00:01:23.45' -> 83.45
      '01:23' -> 83.0
      '14.5' -> 14.5
    """
    if time_str is None:
        return 0.0
    if isinstance(time_str, (int, float)):
        return max(0.0, float(time_str))

    s = str(time_str).strip().replace(',', '.')
    if not s:
        return 0.0

    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 3:
                h, m, sec = parts
                return max(0.0, float(h) * 3600.0 + float(m) * 60.0 + float(sec))
            elif len(parts) == 2:
                m, sec = parts
                return max(0.0, float(m) * 60.0 + float(sec))
        return max(0.0, float(s))
    except Exception:
        return 0.0


def format_seconds_to_time_str(seconds: float, include_ms: bool = True) -> str:
    """Formata segundos em string legível HH:MM:SS.ms."""
    sec = max(0.0, float(seconds or 0.0))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if include_ms:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    return f"{h:02d}:{m:02d}:{int(s):02d}"


def extract_frame_at_timestamp(
    video_path: str,
    timestamp_s: float
) -> dict:
    """
    Extrai o frame de um vídeo no segundo exato com OpenCV (e fallback FFmpeg).
    Retorna dict com:
      - 'frame': np.ndarray BGR (ou None)
      - 'timestamp_s': float
      - 'time_str': str (HH:MM:SS.ms)
      - 'resolution': (largura, altura)
      - 'error': str (ou None)
    """
    if not video_path or not os.path.exists(video_path):
        return {"frame": None, "error": f"Arquivo de vídeo não encontrado: {video_path}"}

    t = max(0.0, float(timestamp_s or 0.0))

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"frame": None, "error": f"Não foi possível abrir o vídeo: {video_path}"}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        dur_s = float(total_frames / fps) if (fps > 0 and total_frames > 0) else 0.0

        if dur_s > 0 and t > dur_s:
            t = max(0.0, dur_s - 0.1)

        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None and frame.size > 0:
            h, w = frame.shape[:2]
            return {
                "frame": frame,
                "timestamp_s": t,
                "time_str": format_seconds_to_time_str(t),
                "resolution": (w, h),
                "error": None
            }
    except Exception as exc:
        pass

    # Fallback FFmpeg
    try:
        import subprocess
        import tempfile
        tmp_img = os.path.join(tempfile.gettempdir(), f"frame_snap_{os.getpid()}_{int(t*1000)}.jpg")
        if os.path.exists(tmp_img):
            try:
                os.remove(tmp_img)
            except Exception:
                pass

        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", f"{t:.3f}",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            tmp_img
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(tmp_img) and os.path.getsize(tmp_img) > 0:
            frame = cv2.imread(tmp_img)
            try:
                os.remove(tmp_img)
            except Exception:
                pass
            if frame is not None:
                h, w = frame.shape[:2]
                return {
                    "frame": frame,
                    "timestamp_s": t,
                    "time_str": format_seconds_to_time_str(t),
                    "resolution": (w, h),
                    "error": None
                }
    except Exception as exc_ff:
        return {"frame": None, "error": f"Erro ao extrair frame via FFmpeg: {str(exc_ff)}"}

    return {"frame": None, "error": f"Não foi possível extrair o frame aos {t:.2f}s."}


def save_captured_frame_as_thumbnail(
    source_video_or_frame,
    output_thumbnail_path: str,
    timestamp_s: float = 0.0,
    video_id: str = None,
    start_time: str = None,
    end_time: str = None,
    aspect_mode: str = "9:16_smart_face",
    generate_ai_variations: bool = False,
    headline_text: str = ""
) -> dict:
    """
    Salva um frame capturado como Thumbnail (Capa) do corte:
    - Se generate_ai_variations=False: salva o frame exato diretamente em output_thumbnail_path (e thumbnail_1.jpg).
    - Se generate_ai_variations=True: invoca create_cut_thumbnail utilizando o frame como base para as 3 variações.
    - Se video_id, start_time, end_time e aspect_mode forem informados, atualiza cuts_catalog.json.
    """
    # 1. Obtém o frame bruto em formato np.ndarray BGR
    if isinstance(source_video_or_frame, np.ndarray):
        raw_bgr = source_video_or_frame
    elif isinstance(source_video_or_frame, str) and os.path.exists(source_video_or_frame):
        ext_res = extract_frame_at_timestamp(source_video_or_frame, timestamp_s)
        if ext_res.get("error") or ext_res.get("frame") is None:
            return {"success": False, "error": ext_res.get("error", "Erro ao extrair frame")}
        raw_bgr = ext_res["frame"]
    else:
        return {"success": False, "error": "Fonte de frame inválida ou não encontrada."}

    out_dir = os.path.dirname(output_thumbnail_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    variations_list = []

    if generate_ai_variations:
        try:
            from core.thumbnail_generator import create_cut_thumbnail
            ai_res = create_cut_thumbnail(
                source_video_or_frame=raw_bgr,
                headline_text=headline_text or "CORTE VIRAL",
                output_path=output_thumbnail_path,
                start_time_str=start_time or "00:00:00",
                end_time_str=end_time or "00:01:00",
                aspect_mode=aspect_mode
            )
            if ai_res.get("error"):
                return {"success": False, "error": ai_res["error"]}
            variations_list = ai_res.get("variations", [])
        except Exception as exc:
            return {"success": False, "error": f"Falha ao gerar variações com IA: {str(exc)}"}
    else:
        # Salva o frame exato como thumbnail.jpg e thumbnail_1.jpg com alta fidelidade
        frame_rgb = cv2.cvtColor(raw_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)
        pil_img.save(output_thumbnail_path, "JPEG", quality=95, optimize=True)

        t1_path = os.path.join(out_dir, "thumbnail_1.jpg") if out_dir else "thumbnail_1.jpg"
        pil_img.save(t1_path, "JPEG", quality=95, optimize=True)

        variations_list = [
            {"id": 1, "name": "📸 Frame Capturado (Original)", "path": t1_path, "filename": "thumbnail_1.jpg"}
        ]

    # Atualiza cuts_catalog.json se os metadados do corte foram passados
    catalog_updated = False
    if video_id and start_time and end_time and aspect_mode:
        try:
            from core.cuts_catalog import update_cut_thumbnail_in_catalog
            cat_res = update_cut_thumbnail_in_catalog(
                video_id=video_id,
                start_time=start_time,
                end_time=end_time,
                aspect_mode=aspect_mode,
                thumbnail_path=output_thumbnail_path,
                variations=variations_list
            )
            catalog_updated = cat_res.get("success", False)
        except Exception:
            pass

    return {
        "success": True,
        "thumbnail_path": output_thumbnail_path,
        "variations": variations_list,
        "catalog_updated": catalog_updated,
        "error": None
    }


def save_base64_data_as_image(base64_str: str, output_path: str) -> dict:
    """Decodifica string base64 de imagem (data:image/jpeg;base64,...) e grava em disco."""
    try:
        clean_b64 = re.sub(r"^data:image\/[a-zA-Z]+;base64,", "", base64_str.strip())
        img_bytes = base64.b64decode(clean_b64)
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "wb") as f_out:
            f_out.write(img_bytes)
        return {"success": True, "path": output_path, "error": None}
    except Exception as exc:
        return {"success": False, "error": f"Erro ao decodificar imagem base64: {str(exc)}"}
