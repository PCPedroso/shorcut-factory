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


def capture_single_frame_rgb(video_path: str, timestamp_s_or_str=0.0) -> np.ndarray:
    """
    Extrai um único frame de vídeo em formato RGB (H, W, 3) como array NumPy.
    Aceita timestamp em segundos (float) ou string de tempo ('HH:MM:SS.ms').
    """
    t_sec = parse_time_str_to_seconds(timestamp_s_or_str)
    res = extract_frame_at_timestamp(video_path, t_sec)
    if res.get("frame") is not None:
        try:
            return cv2.cvtColor(res["frame"], cv2.COLOR_BGR2RGB)
        except Exception:
            return res["frame"]
    return None


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


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários de Prévia Visual da Região de Interesse (ROI) e Enquadramento Manual
# ──────────────────────────────────────────────────────────────────────────────

def _draw_text_badge(img, text: str, origin: tuple, bg_color=(15, 15, 15), text_color=(255, 255, 255), font_scale=0.6, thickness=2, padding=6):
    """Desenha texto com fundo escuro sólido para máxima legibilidade."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = origin
    x = max(padding, min(img.shape[1] - tw - padding, x))
    y = max(th + padding, min(img.shape[0] - baseline - padding, y))
    cv2.rectangle(img, (x - padding, y - th - padding), (x + tw + padding, y + baseline + padding), bg_color, -1)
    cv2.putText(img, text, (x, y), font, font_scale, text_color, thickness, cv2.LINE_AA)


def generate_roi_preview_image(
    source_video_or_frame,
    timestamp_s_or_str = 0.0,
    output_path: str = "preview_roi.jpg",
    crop_margins: dict = None
) -> dict:
    """
    Gera uma imagem de prévia com máscara visual da Região de Interesse (ROI):
    - Pinta as bordas a serem cortadas (anúncios, patrocínios em L, rodapés) com máscara vermelha semi-transparente.
    - Destaca a área limpa que será aproveitada com moldura verde neon estilo viewfinder.
    - Exibe métricas de dimensões e percentual de recorte de cada margem.
    """
    try:
        from core.video_processor import sanitize_crop_margins, has_active_crop_margins

        if isinstance(source_video_or_frame, np.ndarray):
            raw_bgr = source_video_or_frame.copy()
        elif isinstance(source_video_or_frame, str) and os.path.exists(source_video_or_frame):
            t_sec = parse_time_str_to_seconds(timestamp_s_or_str)
            ext_res = extract_frame_at_timestamp(source_video_or_frame, t_sec)
            if ext_res.get("error") or ext_res.get("frame") is None:
                return {"path": None, "error": ext_res.get("error", "Não foi possível extrair o frame para prévia ROI.")}
            raw_bgr = ext_res["frame"].copy()
        else:
            return {"path": None, "error": "Fonte de vídeo/frame inválida para prévia ROI."}

        h, w = raw_bgr.shape[:2]
        m = sanitize_crop_margins(crop_margins)
        has_crop = has_active_crop_margins(crop_margins)

        x1 = max(0, min(w - 1, int(round(w * m["left"]))))
        x2 = max(x1 + 1, min(w, int(round(w * (1.0 - m["right"])))))
        y1 = max(0, min(h - 1, int(round(h * m["top"]))))
        y2 = max(y1 + 1, min(h, int(round(h * (1.0 - m["bottom"])))))

        roi_w = x2 - x1
        roi_h = y2 - y1
        roi_area_pct = ((roi_w * roi_h) / float(w * h)) * 100.0

        canvas = raw_bgr.copy()

        if has_crop:
            # Cria camada de máscara vermelha semi-transparente sobre as bordas descartadas
            overlay = raw_bgr.copy()
            red_color = (35, 35, 215)  # BGR

            # Top margin
            if y1 > 0:
                overlay[0:y1, :] = red_color
            # Bottom margin
            if y2 < h:
                overlay[y2:h, :] = red_color
            # Left margin
            if x1 > 0:
                overlay[y1:y2, 0:x1] = red_color
            # Right margin
            if x2 < w:
                overlay[y1:y2, x2:w] = red_color

            cv2.addWeighted(overlay, 0.48, canvas, 0.52, 0, canvas)

            # Moldura verde neon contornando a ROI
            neon_green = (0, 255, 80)
            cv2.rectangle(canvas, (x1, y1), (x2, y2), neon_green, thickness=3)

            # Cantoneiras reforçadas estilo viewfinder (câmera cinema)
            bracket_len = min(40, roi_w // 4, roi_h // 4)
            b_thick = 5
            # Top-left
            cv2.line(canvas, (x1, y1), (x1 + bracket_len, y1), neon_green, b_thick)
            cv2.line(canvas, (x1, y1), (x1, y1 + bracket_len), neon_green, b_thick)
            # Top-right
            cv2.line(canvas, (x2, y1), (x2 - bracket_len, y1), neon_green, b_thick)
            cv2.line(canvas, (x2, y1), (x2, y1 + bracket_len), neon_green, b_thick)
            # Bottom-left
            cv2.line(canvas, (x1, y2), (x1 + bracket_len, y2), neon_green, b_thick)
            cv2.line(canvas, (x1, y2), (x1, y2 - bracket_len), neon_green, b_thick)
            # Bottom-right
            cv2.line(canvas, (x2, y2), (x2 - bracket_len, y2), neon_green, b_thick)
            cv2.line(canvas, (x2, y2), (x2, y2 - bracket_len), neon_green, b_thick)

            # Badges com percentuais de corte nas bordas descartadas
            if m["right"] > 0.001:
                cx_tag = x2 + (w - x2) // 2
                cy_tag = y1 + roi_h // 2
                _draw_text_badge(canvas, f"CORTE DIR: {m['right']*100:.1f}%", (cx_tag - 80, cy_tag), bg_color=(20, 20, 180), text_color=(255, 255, 255), font_scale=0.55)

            if m["bottom"] > 0.001:
                cx_tag = x1 + roi_w // 2
                cy_tag = y2 + (h - y2) // 2
                _draw_text_badge(canvas, f"CORTE INF (RODAPE): {m['bottom']*100:.1f}%", (cx_tag - 120, cy_tag + 6), bg_color=(20, 20, 180), text_color=(255, 255, 255), font_scale=0.55)

            if m["left"] > 0.001:
                cx_tag = x1 // 2
                cy_tag = y1 + roi_h // 2
                _draw_text_badge(canvas, f"CORTE ESQ: {m['left']*100:.1f}%", (cx_tag - 70, cy_tag), bg_color=(20, 20, 180), text_color=(255, 255, 255), font_scale=0.55)

            if m["top"] > 0.001:
                cx_tag = x1 + roi_w // 2
                cy_tag = y1 // 2
                _draw_text_badge(canvas, f"CORTE SUP: {m['top']*100:.1f}%", (cx_tag - 70, cy_tag), bg_color=(20, 20, 180), text_color=(255, 255, 255), font_scale=0.55)

            # Badge principal da ROI preservada
            badge_text = f"AREA PRESERVADA: {roi_w}x{roi_h} px ({roi_area_pct:.1f}% util)"
            _draw_text_badge(canvas, badge_text, (x1 + 14, y1 + 32), bg_color=(10, 10, 10), text_color=neon_green, font_scale=0.65, thickness=2)
        else:
            # Sem cortes ativos: exibe badge de 100% integral
            badge_text = f"ENQUADRAMENTO 100% ORIGINAL: {w}x{h} px"
            _draw_text_badge(canvas, badge_text, (24, 40), bg_color=(10, 10, 10), text_color=(0, 255, 255), font_scale=0.65, thickness=2)

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cv2.imwrite(output_path, canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        return {
            "path": output_path,
            "roi": (x1, y1, x2, y2),
            "dimensions": (roi_w, roi_h),
            "has_crop": has_crop,
            "error": None
        }
    except Exception as exc:
        return {"path": None, "error": str(exc)}


def generate_cropped_preview_image(
    source_video_or_frame,
    timestamp_s_or_str = 0.0,
    output_path: str = "preview_cropped.jpg",
    crop_margins: dict = None,
    target_aspect: str = "16:9",
    horizontal_zoom: float = 1.0
) -> dict:
    """
    Gera a prévia exata do resultado renderizado final com a ROI aplicada e sem distorção anamórfica:
    - target_aspect='16:9': Redimensiona e ajusta a ROI limpa para 1920x1080 Full HD (com zoom opcional).
    - target_aspect='9:16_crop': Recorta a fatia vertical central 9:16 da ROI para 1080x1920.
    - target_aspect='9:16_blur': Cria fundo desfocado a partir da ROI limpa com foreground 9:16 centralizado.
    """
    try:
        from core.video_processor import sanitize_crop_margins, has_active_crop_margins

        if isinstance(source_video_or_frame, np.ndarray):
            raw_bgr = source_video_or_frame.copy()
        elif isinstance(source_video_or_frame, str) and os.path.exists(source_video_or_frame):
            t_sec = parse_time_str_to_seconds(timestamp_s_or_str)
            ext_res = extract_frame_at_timestamp(source_video_or_frame, t_sec)
            if ext_res.get("error") or ext_res.get("frame") is None:
                return {"path": None, "error": ext_res.get("error", "Não foi possível extrair o frame.")}
            raw_bgr = ext_res["frame"].copy()
        else:
            return {"path": None, "error": "Fonte de vídeo/frame inválida."}

        h, w = raw_bgr.shape[:2]
        m = sanitize_crop_margins(crop_margins)
        has_crop = has_active_crop_margins(crop_margins)

        if has_crop:
            x1 = max(0, min(w - 1, int(round(w * m["left"]))))
            x2 = max(x1 + 1, min(w, int(round(w * (1.0 - m["right"])))))
            y1 = max(0, min(h - 1, int(round(h * m["top"]))))
            y2 = max(y1 + 1, min(h, int(round(h * (1.0 - m["bottom"])))))
            roi_frame = raw_bgr[y1:y2, x1:x2].copy()
        else:
            roi_frame = raw_bgr.copy()

        rh, rw = roi_frame.shape[:2]

        if target_aspect == "16:9":
            # Ajuste de proporção para 16:9 (1.7778)
            target_ratio = 16.0 / 9.0
            roi_ratio = rw / float(rh)

            if roi_ratio > target_ratio:
                # ROI mais larga que 16:9: apara laterais
                fit_w = int(round(rh * target_ratio))
                off_x = (rw - fit_w) // 2
                cropped_169 = roi_frame[:, off_x : off_x + fit_w]
            else:
                # ROI mais alta que 16:9: apara topo/base
                fit_h = int(round(rw / target_ratio))
                off_y = (rh - fit_h) // 2
                cropped_169 = roi_frame[off_y : off_y + fit_h, :]

            # Aplica zoom horizontal adicional se configurado
            eff_zoom = max(1.0, float(horizontal_zoom or 1.0))
            if eff_zoom > 1.001:
                ch, cw = cropped_169.shape[:2]
                zw = int(round(cw / eff_zoom))
                zh = int(round(ch / eff_zoom))
                zx = max(0, (cw - zw) // 2)
                zy = max(0, (ch - zh) // 2)
                cropped_169 = cropped_169[zy : zy + zh, zx : zx + zw]

            final_out = cv2.resize(cropped_169, (1920, 1080), interpolation=cv2.INTER_LINEAR)

        elif target_aspect == "9:16_crop":
            # 9:16 Vertical corte central (9/16 = 0.5625)
            target_ratio = 9.0 / 16.0
            roi_ratio = rw / float(rh)

            if roi_ratio > target_ratio:
                fit_w = int(round(rh * target_ratio))
                off_x = (rw - fit_w) // 2
                cropped_916 = roi_frame[:, off_x : off_x + fit_w]
            else:
                fit_h = int(round(rw / target_ratio))
                off_y = (rh - fit_h) // 2
                cropped_916 = roi_frame[off_y : off_y + fit_h, :]

            final_out = cv2.resize(cropped_916, (1080, 1920), interpolation=cv2.INTER_LINEAR)

        elif target_aspect == "9:16_blur":
            # Fundo desfocado 1080x1920 gerado exclusivamente da ROI limpa
            bg = cv2.resize(roi_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
            bg = cv2.GaussianBlur(bg, (99, 99), 30)
            # Escurece levemente o fundo (-10%)
            bg = np.clip(bg.astype(np.float32) * 0.90, 0, 255).astype(np.uint8)

            # Foreground proporcional centralizado
            scale = 1080.0 / float(rw)
            fg_h = int(round(rh * scale))
            fg = cv2.resize(roi_frame, (1080, fg_h), interpolation=cv2.INTER_LINEAR)

            off_y = max(0, (1920 - fg_h) // 2)
            clip_fg_h = min(fg_h, 1920)
            bg[off_y : off_y + clip_fg_h, :] = fg[:clip_fg_h, :]
            final_out = bg

        else:
            final_out = roi_frame

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cv2.imwrite(output_path, final_out, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        return {"path": output_path, "error": None}
    except Exception as exc:
        return {"path": None, "error": str(exc)}

