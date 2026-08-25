"""
overlay_manager.py — Motor de Sobreposição e Formatação de Banners, Tarjas (GC) e Logos em Vídeo
Permite compor banners com modos de escala (fill, fit, cover), logos embutidos,
geração de prévia instantânea em frame e renderização via FFmpeg acelerada por GPU.
"""

import os
import subprocess
import cv2
import numpy as np
import imageio_ffmpeg
from PIL import Image

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

OVERLAY_PRESETS = {
    "gc_bottom_169": {
        "name": "📰 Tarja Inferior Completa (Cobertura de GC / Notícias 16:9)",
        "width_pct": 100,
        "height_px": 320,
        "pos_x": "center",
        "pos_y": "bottom",
        "offset_y": 0,
        "scale_mode": "fill",
        "opacity": 1.0
    },
    "card_bottom": {
        "name": "🏷️ Card Flutuante no Rodapé (Margem Lateral)",
        "width_pct": 92,
        "height_px": 240,
        "pos_x": "center",
        "pos_y": "bottom",
        "offset_y": 40,
        "scale_mode": "fit",
        "opacity": 1.0
    },
    "watermark_top_right": {
        "name": "💧 Marca d'Água / Logo (Canto Superior Direito)",
        "width_pct": 25,
        "height_px": 140,
        "pos_x": "right",
        "pos_y": "top",
        "offset_x": 30,
        "offset_y": 30,
        "scale_mode": "fit",
        "opacity": 0.9
    },
    "watermark_top_left": {
        "name": "💧 Marca d'Água / Logo (Canto Superior Esquerdo)",
        "width_pct": 25,
        "height_px": 140,
        "pos_x": "left",
        "pos_y": "top",
        "offset_x": 30,
        "offset_y": 30,
        "scale_mode": "fit",
        "opacity": 0.9
    },
    "custom": {
        "name": "🎛️ Personalizado (Controle Manual Total)",
        "width_pct": 100,
        "height_px": 280,
        "pos_x": "center",
        "pos_y": "bottom",
        "offset_x": 0,
        "offset_y": 0,
        "scale_mode": "fill",
        "opacity": 1.0
    }
}


def load_image_rgba(image_path_or_array) -> np.ndarray:
    """
    Carrega uma imagem em formato RGBA (4 canais).
    Aceita caminho de arquivo ou array numpy (RGB/RGBA/BGR).
    """
    if isinstance(image_path_or_array, str):
        if not os.path.exists(image_path_or_array):
            return None
        img_pil = Image.open(image_path_or_array).convert("RGBA")
        return np.array(img_pil)
    elif isinstance(image_path_or_array, np.ndarray):
        if image_path_or_array.ndim == 2:
            return cv2.cvtColor(image_path_or_array, cv2.COLOR_GRAY2RGBA)
        elif image_path_or_array.shape[2] == 3:
            return cv2.cvtColor(image_path_or_array, cv2.COLOR_RGB2RGBA)
        elif image_path_or_array.shape[2] == 4:
            return image_path_or_array.copy()
    return None


def resize_image_mode(img_rgba: np.ndarray, target_w: int, target_h: int, mode: str = "fill") -> np.ndarray:
    """
    Redimensiona uma imagem RGBA para a caixa (target_w, target_h) segundo o modo:
    - 'fill': Estica a imagem para preencher exatamente target_w x target_h.
    - 'fit': Mantém a proporção original, centralizando dentro da caixa com fundo transparente.
    - 'cover': Amplia proporcionalmente até cobrir toda a caixa e corta as sobras centralizadamente.
    """
    if img_rgba is None or target_w <= 0 or target_h <= 0:
        return np.zeros((max(1, target_h), max(1, target_w), 4), dtype=np.uint8)

    src_h, src_w = img_rgba.shape[:2]
    if src_w == 0 or src_h == 0:
        return np.zeros((target_h, target_w, 4), dtype=np.uint8)

    if mode == "fill":
        return cv2.resize(img_rgba, (target_w, target_h), interpolation=cv2.INTER_AREA if (target_w < src_w) else cv2.INTER_CUBIC)

    elif mode == "fit":
        # Proporcional dentro da caixa com transparência ao redor
        scale = min(float(target_w) / src_w, float(target_h) / src_h)
        nw, nh = max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))
        resized = cv2.resize(img_rgba, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
        
        result = np.zeros((target_h, target_w, 4), dtype=np.uint8)
        ox = (target_w - nw) // 2
        oy = (target_h - nh) // 2
        result[oy:oy+nh, ox:ox+nw] = resized
        return result

    elif mode == "cover":
        # Proporcional preenchendo toda a caixa com corte centralizado
        scale = max(float(target_w) / src_w, float(target_h) / src_h)
        nw, nh = max(1, int(round(src_w * scale))), max(1, int(round(src_h * scale)))
        resized = cv2.resize(img_rgba, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)

        cx = (nw - target_w) // 2
        cy = (nh - target_h) // 2
        result = resized[cy:cy+target_h, cx:cx+target_w]
        return result

    # Default fallback
    return cv2.resize(img_rgba, (target_w, target_h))


def compose_banner_box(
    banner_img_path_or_array,
    target_w: int,
    target_h: int,
    scale_mode: str = "fill",
    logo_path_or_array = None,
    logo_pos: str = "left",
    logo_scale_pct: float = 0.75,
    logo_margin_x: int = 15,
    logo_margin_y: int = 10,
    opacity: float = 1.0
) -> np.ndarray:
    """
    Compõe a camada de banner final no tamanho target_w x target_h,
    aplicando o modo de escala, opacidade e embutindo o logo/imagem secundária se fornecido.
    Retorna imagem RGBA (H, W, 4).
    """
    banner_rgba = load_image_rgba(banner_img_path_or_array)
    if banner_rgba is None:
        return np.zeros((target_h, target_w, 4), dtype=np.uint8)

    # 1. Redimensiona o banner principal
    base_banner = resize_image_mode(banner_rgba, target_w, target_h, mode=scale_mode)

    # 2. Se houver imagem secundária (logo/selo), embute na composição
    if logo_path_or_array is not None:
        logo_rgba = load_image_rgba(logo_path_or_array)
        if logo_rgba is not None:
            lh, lw = logo_rgba.shape[:2]
            target_lh = max(10, int(target_h * max(0.1, min(1.0, logo_scale_pct))))
            scale_l = target_lh / float(lh)
            target_lw = max(10, int(round(lw * scale_l)))
            
            resized_logo = cv2.resize(
                logo_rgba, (target_lw, target_lh),
                interpolation=cv2.INTER_AREA if scale_l < 1.0 else cv2.INTER_CUBIC
            )
            
            # Posição do logo dentro do banner
            if logo_pos == "left":
                lx = logo_margin_x
            elif logo_pos == "right":
                lx = target_w - target_lw - logo_margin_x
            elif logo_pos == "center":
                lx = (target_w - target_lw) // 2
            else:
                lx = logo_margin_x
            
            ly = max(0, (target_h - target_lh) // 2)

            # Garante limites válidos
            lx = max(0, min(target_w - target_lw, lx))
            ly = max(0, min(target_h - target_lh, ly))

            # Alpha blend do logo sobre o banner
            alpha_logo = (resized_logo[:, :, 3] / 255.0)[:, :, np.newaxis]
            alpha_base = (base_banner[ly:ly+target_lh, lx:lx+target_lw, 3] / 255.0)[:, :, np.newaxis]

            for c in range(3):
                base_banner[ly:ly+target_lh, lx:lx+target_lw, c] = (
                    alpha_logo[:, :, 0] * resized_logo[:, :, c] +
                    (1.0 - alpha_logo[:, :, 0]) * base_banner[ly:ly+target_lh, lx:lx+target_lw, c]
                ).astype(np.uint8)

            base_banner[ly:ly+target_lh, lx:lx+target_lw, 3] = np.clip(
                (alpha_logo[:, :, 0] + alpha_base[:, :, 0] * (1.0 - alpha_logo[:, :, 0])) * 255, 0, 255
            ).astype(np.uint8)

    # 3. Ajuste de Opacidade Geral
    if opacity < 1.0:
        base_banner[:, :, 3] = (base_banner[:, :, 3] * max(0.0, min(1.0, opacity))).astype(np.uint8)

    return base_banner


def calculate_overlay_placement(frame_w: int, frame_h: int, config: dict) -> tuple:
    """
    Calcula as dimensões finais e a posição (x, y, w, h) do overlay no frame.
    """
    width_pct = float(config.get("width_pct", 100))
    target_w = max(10, int(frame_w * (width_pct / 100.0)))

    target_h = int(config.get("height_px", 300))
    target_h = max(10, min(frame_h, target_h))

    pos_x = str(config.get("pos_x", "center")).lower()
    offset_x = int(config.get("offset_x", 0))

    if pos_x == "left":
        x = offset_x
    elif pos_x == "right":
        x = frame_w - target_w - offset_x
    else:  # center
        x = (frame_w - target_w) // 2 + offset_x

    pos_y = str(config.get("pos_y", "bottom")).lower()
    offset_y = int(config.get("offset_y", 0))

    if pos_y == "top":
        y = offset_y
    elif pos_y == "center":
        y = (frame_h - target_h) // 2 + offset_y
    else:  # bottom
        y = frame_h - target_h - offset_y

    x = max(0, min(frame_w - target_w, x))
    y = max(0, min(frame_h - target_h, y))

    return x, y, target_w, target_h


def generate_overlay_preview(
    video_path: str = None,
    banner_path_or_array = None,
    config: dict = None,
    timestamp_s: float = 0.0,
    base_frame: np.ndarray = None,
    logo_path_or_array = None
) -> np.ndarray:
    """
    Gera uma prévia RGB (frame completo com o banner sobreposto) em alta fidelidade.
    Retorna numpy array RGB (H, W, 3).
    """
    if config is None:
        config = OVERLAY_PRESETS["gc_bottom_169"]

    frame_rgb = None
    if base_frame is not None:
        frame_rgb = base_frame.copy()
    elif video_path and os.path.exists(video_path):
        from core.quick_editor import extract_frame_at_timestamp
        frame_rgb = extract_frame_at_timestamp(video_path, timestamp_s)

    if frame_rgb is None:
        # Frame de fundo padrão 1920x1080 cinza escuro
        frame_rgb = np.full((1080, 1920, 3), 30, dtype=np.uint8)

    fh, fw = frame_rgb.shape[:2]

    if banner_path_or_array is None:
        return frame_rgb

    x, y, w, h = calculate_overlay_placement(fw, fh, config)

    # Compõe o banner
    scale_mode = config.get("scale_mode", "fill")
    opacity = float(config.get("opacity", 1.0))
    logo_pos = config.get("logo_pos", "left")
    logo_scale = float(config.get("logo_scale_pct", 0.75))

    banner_box_rgba = compose_banner_box(
        banner_img_path_or_array=banner_path_or_array,
        target_w=w,
        target_h=h,
        scale_mode=scale_mode,
        logo_path_or_array=logo_path_or_array,
        logo_pos=logo_pos,
        logo_scale_pct=logo_scale,
        opacity=opacity
    )

    # Aplica sobre o frame RGB
    alpha = (banner_box_rgba[:, :, 3] / 255.0)[:, :, np.newaxis]
    banner_rgb = banner_box_rgba[:, :, :3]

    for c in range(3):
        frame_rgb[y:y+h, x:x+w, c] = (
            alpha[:, :, 0] * banner_rgb[:, :, c] +
            (1.0 - alpha[:, :, 0]) * frame_rgb[y:y+h, x:x+w, c]
        ).astype(np.uint8)

    return frame_rgb


def apply_overlay_to_video(
    video_path: str,
    banner_path: str,
    config: dict,
    output_path: str = None,
    logo_path: str = None
) -> dict:
    """
    Aplica a sobreposição de imagem sobre o vídeo via FFmpeg com aceleração NVENC (GPU).
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Vídeo original não encontrado."}

    if not banner_path or not os.path.exists(banner_path):
        return {"path": None, "error": "Imagem do banner não encontrada."}

    # 1. Obtém a resolução do vídeo
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"path": None, "error": "Não foi possível abrir o arquivo de vídeo."}
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fw <= 0 or fh <= 0:
        fw, fh = 1920, 1080

    # 2. Calcula dimensões e posição
    x, y, w, h = calculate_overlay_placement(fw, fh, config)

    # 3. Compõe a imagem PNG temporária do banner com logo e escala
    scale_mode = config.get("scale_mode", "fill")
    opacity = float(config.get("opacity", 1.0))
    logo_pos = config.get("logo_pos", "left")
    logo_scale = float(config.get("logo_scale_pct", 0.75))

    banner_rgba = compose_banner_box(
        banner_img_path_or_array=banner_path,
        target_w=w,
        target_h=h,
        scale_mode=scale_mode,
        logo_path_or_array=logo_path,
        logo_pos=logo_pos,
        logo_scale_pct=logo_scale,
        opacity=opacity
    )

    temp_dir = os.path.dirname(video_path) or "data"
    temp_overlay_png = os.path.join(temp_dir, "temp_banner_overlay.png")
    
    # Salva imagem RGBA em PNG
    Image.fromarray(banner_rgba).save(temp_overlay_png, format="PNG")

    target_out = output_path
    is_in_place = False
    if not target_out:
        target_out = video_path
        is_in_place = True

    tmp_out = target_out + ".overlay_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    # 4. Executa o FFmpeg com aceleração por GPU
    filter_complex = f"[0:v][1:v]overlay={x}:{y}[outv]"

    cmd_gpu = [
        FFMPEG_EXE, "-y",
        "-i", video_path,
        "-i", temp_overlay_png,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-b:v", "8M",
        "-c:a", "copy",
        "-movflags", "+faststart",
        tmp_out
    ]

    res = subprocess.run(cmd_gpu, capture_output=True, text=True)

    # Fallback para libx264 se a GPU não estiver disponível
    if res.returncode != 0 or not os.path.exists(tmp_out) or os.path.getsize(tmp_out) == 0:
        cmd_cpu = [
            FFMPEG_EXE, "-y",
            "-i", video_path,
            "-i", temp_overlay_png,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "copy",
            "-movflags", "+faststart",
            tmp_out
        ]
        res = subprocess.run(cmd_cpu, capture_output=True, text=True)

    # Remove o PNG temporário
    if os.path.exists(temp_overlay_png):
        try:
            os.remove(temp_overlay_png)
        except Exception:
            pass

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if is_in_place and os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.replace(tmp_out, target_out)
        return {"path": target_out, "error": None}
    else:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
        err_msg = res.stderr[-1000:] if res.stderr else "Erro desconhecido no FFmpeg ao aplicar sobreposição."
        return {"path": None, "error": err_msg}
