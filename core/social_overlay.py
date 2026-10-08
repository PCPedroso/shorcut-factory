"""
core/social_overlay.py — Motor de Assinatura e Badges de Redes Sociais nos Cortes
Permite exibir identificadores de YouTube, Instagram e X (Twitter) com ícones oficiais
proporcionais à tipografia, estilos em pílula (Glassmorphism / Minimalista) e safe zones.
"""

import os
import subprocess
import cv2
import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_ICONS_DIR = os.path.join(_PROJECT_DIR, "assets", "icons", "social")
_FONTS_DIR = os.path.join(_SCRIPT_DIR, "fonts")
_FONT_PATH = os.path.join(_FONTS_DIR, "Montserrat-ExtraBold.ttf")

DEFAULT_SOCIAL_CONFIG = {
    "enabled": False,
    "position": "bottom",       # 'bottom' ou 'top'
    "offset_y": 0,              # Ajuste fino em pixels (+/- 250px)
    "font_size": 32,            # Tamanho da fonte (20 a 54px)
    "style": "pill_glass",      # 'pill_glass', 'pill_individual', 'floating'
    "icon_style": "official",   # 'official' ou 'monochrome'
    "text_color": "#FFFFFF",
    "networks": {
        "youtube": {"enabled": True, "handle": "@meucanal"},
        "instagram": {"enabled": True, "handle": "@meuperfil"},
        "x": {"enabled": False, "handle": "@meuperfil"}
    }
}


def _get_font(font_size: int) -> ImageFont.ImageFont:
    """Carrega a fonte Montserrat ExtraBold ou fallback padrão."""
    try:
        if os.path.exists(_FONT_PATH):
            return ImageFont.truetype(_FONT_PATH, font_size)
    except Exception:
        pass
    try:
        return ImageFont.truetype("arialbd.ttf", font_size)
    except Exception:
        return ImageFont.load_default()


def _find_icon_file(network_key: str) -> str:
    """Busca o arquivo de ícone correspondente na pasta assets/icons/social/."""
    aliases = {
        "youtube": ["youtube.png", "yt.png", "youtube.webp"],
        "instagram": ["instagram.png", "insta.png", "ig.png", "instagram.webp"],
        "x": ["x.png", "twitter.png", "x_logo.png", "x.webp"]
    }
    candidates = aliases.get(network_key.lower(), [f"{network_key}.png"])
    for cand in candidates:
        full_path = os.path.join(_ICONS_DIR, cand)
        if os.path.exists(full_path):
            return full_path
    return None


def _draw_fallback_icon(network_key: str, size: int) -> Image.Image:
    """Gera proceduralmente um ícone vetorial de alta nitidez se não houver arquivo no disco."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = network_key.lower()

    if k == "youtube":
        pad = int(size * 0.12)
        d.rounded_rectangle([pad, pad + int(size * 0.1), size - pad, size - pad - int(size * 0.1)], radius=int(size * 0.22), fill=(255, 0, 0, 255))
        # Play triangle
        pw = int(size * 0.25)
        cx, cy = size // 2, size // 2
        d.polygon([(cx - pw // 2, cy - pw // 2), (cx - pw // 2, cy + pw // 2), (cx + pw // 2, cy)], fill=(255, 255, 255, 255))

    elif k == "instagram":
        pad = int(size * 0.1)
        d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=int(size * 0.25), fill=(225, 48, 108, 255))
        w = max(2, int(size * 0.07))
        c_pad = int(size * 0.22)
        d.rounded_rectangle([c_pad, c_pad, size - c_pad, size - c_pad], radius=int(size * 0.18), outline=(255, 255, 255, 255), width=w)
        l_pad = int(size * 0.35)
        d.ellipse([l_pad, l_pad, size - l_pad, size - l_pad], outline=(255, 255, 255, 255), width=w)
        f_x = int(size * 0.68)
        f_y = int(size * 0.32)
        fr = max(1, int(size * 0.04))
        d.ellipse([f_x - fr, f_y - fr, f_x + fr, f_y + fr], fill=(255, 255, 255, 255))

    elif k == "x":
        pad = int(size * 0.1)
        d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=int(size * 0.22), fill=(15, 20, 25, 255))
        w1 = max(2, int(size * 0.10))
        w2 = max(2, int(size * 0.07))
        d.line([(int(size * 0.26), int(size * 0.26)), (int(size * 0.74), int(size * 0.74))], fill=(255, 255, 255, 255), width=w1)
        d.line([(int(size * 0.74), int(size * 0.26)), (int(size * 0.26), int(size * 0.74))], fill=(255, 255, 255, 255), width=w2)

    else:
        d.ellipse([0, 0, size, size], fill=(100, 100, 100, 255))

    return img


def load_social_icon(network_key: str, target_height: int, monochrome: bool = False) -> Image.Image:
    """
    Carrega e redimensiona proporcionalmente o ícone da rede social para target_height.
    Suporta modo monocromático branco.
    """
    target_h = max(12, int(target_height))
    icon_path = _find_icon_file(network_key)

    if icon_path and os.path.exists(icon_path):
        try:
            raw_icon = Image.open(icon_path).convert("RGBA")
            iw, ih = raw_icon.size
            ratio = float(iw) / max(1, ih)
            target_w = max(12, int(round(target_h * ratio)))
            resized = raw_icon.resize((target_w, target_h), Image.Resampling.LANCZOS)
        except Exception:
            raw_icon = _draw_fallback_icon(network_key, target_h)
            resized = raw_icon
    else:
        raw_icon = _draw_fallback_icon(network_key, target_h)
        resized = raw_icon

    if monochrome:
        # Converte pixels coloridos em branco puro, preservando a transparência alpha original
        r, g, b, a = resized.split()
        white = Image.new("L", resized.size, 255)
        resized = Image.merge("RGBA", (white, white, white, a))

    return resized


def get_active_social_items(config: dict) -> list:
    """
    Retorna a lista de itens ativos a serem exibidos.
    [{'key': 'youtube', 'name': 'YouTube', 'handle': '@canal'}]
    """
    if not config or not config.get("enabled", True):
        return []

    networks = config.get("networks", {})
    order = ["youtube", "instagram", "x"]
    items = []

    for net_key in order:
        net_data = networks.get(net_key, {})
        if net_data.get("enabled", False):
            raw_handle = str(net_data.get("handle", "")).strip()
            if raw_handle:
                items.append({
                    "key": net_key,
                    "name": net_key.capitalize(),
                    "handle": raw_handle
                })

    return items


def render_social_overlay_image(video_width: int, video_height: int, config: dict) -> Image.Image:
    """
    Gera uma imagem RGBA transparente com a camada de assinatura de redes sociais
    posicionada exatamente no frame nas coordenadas calculadas.
    """
    img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    items = get_active_social_items(config)
    if not items:
        return img

    font_size = max(16, min(72, int(config.get("font_size", 32))))
    font = _get_font(font_size)
    monochrome = (config.get("icon_style", "official") == "monochrome")
    style_mode = config.get("style", "pill_glass")  # pill_glass, pill_individual, floating
    text_color = config.get("text_color", "#FFFFFF")

    # Escala proporcional do ícone: 1.05x o tamanho da fonte
    icon_h = max(16, int(round(font_size * 1.08)))

    # Mede dimensões de cada item
    rendered_items = []
    gap_icon_text = max(6, int(font_size * 0.28))

    for it in items:
        icon_img = load_social_icon(it["key"], icon_h, monochrome=monochrome)
        txt = it["handle"]
        bbox = font.getbbox(txt)
        txt_w = bbox[2] - bbox[0]
        txt_h = bbox[3] - bbox[1]

        item_content_w = icon_img.width + gap_icon_text + txt_w
        item_content_h = max(icon_img.height, txt_h)

        rendered_items.append({
            "key": it["key"],
            "handle": txt,
            "icon": icon_img,
            "txt_w": txt_w,
            "txt_h": txt_h,
            "txt_offset_y": bbox[1],
            "content_w": item_content_w,
            "content_h": item_content_h
        })

    # Espaçamento entre as redes sociais
    inter_network_gap = max(14, int(font_size * 0.70))
    padding_x = max(14, int(font_size * 0.55))
    padding_y = max(8, int(font_size * 0.32))

    # Posição Vertical (Safe Zones para 9:16)
    pos_type = str(config.get("position", "bottom")).lower()
    offset_y = int(config.get("offset_y", 0))

    if pos_type == "top":
        # Safe zone topo (abaixo de status bar do mobile / headline)
        base_y = max(40, int(video_height * 0.075))
        final_y = base_y + offset_y
    else:
        # Safe zone rodapé (acima de legenda nativa e botões do Reels/TikTok)
        base_y = max(100, int(video_height * 0.84))
        final_y = base_y - offset_y

    draw = ImageDraw.Draw(img)

    if style_mode == "pill_glass":
        # Container ÚNICO para todas as redes sociais ativas
        total_content_w = sum(ri["content_w"] for ri in rendered_items) + (inter_network_gap * (len(rendered_items) - 1))
        container_w = total_content_w + (padding_x * 2)
        container_h = max(ri["content_h"] for ri in rendered_items) + (padding_y * 2)

        start_x = max(10, (video_width - container_w) // 2)
        start_y = max(10, min(video_height - container_h - 10, final_y))

        # Fundo Glassmorphism Dark com cantos totalmente arredondados (pílula)
        pill_radius = container_h // 2
        bg_color = (12, 16, 24, 185)       # Slate dark translúcido 72%
        border_color = (255, 255, 255, 45) # Borda sutil de vidro

        draw.rounded_rectangle(
            [start_x, start_y, start_x + container_w, start_y + container_h],
            radius=pill_radius,
            fill=bg_color,
            outline=border_color,
            width=2
        )

        cur_x = start_x + padding_x
        center_y = start_y + (container_h // 2)

        for ri in rendered_items:
            # 1. Ícone
            ic = ri["icon"]
            ic_y = center_y - (ic.height // 2)
            img.paste(ic, (cur_x, ic_y), ic)

            # 2. Texto
            txt_x = cur_x + ic.width + gap_icon_text
            txt_y = center_y - (ri["txt_h"] // 2) - ri["txt_offset_y"]
            draw.text((txt_x, txt_y), ri["handle"], font=font, fill=text_color)

            cur_x += ri["content_w"] + inter_network_gap

    elif style_mode == "pill_individual":
        # Pílulas separadas para cada rede
        total_pills_w = sum(ri["content_w"] + (padding_x * 2) for ri in rendered_items) + (inter_network_gap * (len(rendered_items) - 1))
        start_x = max(10, (video_width - total_pills_w) // 2)
        cur_x = start_x

        for ri in rendered_items:
            p_w = ri["content_w"] + (padding_x * 2)
            p_h = ri["content_h"] + (padding_y * 2)
            p_y = max(10, min(video_height - p_h - 10, final_y))
            p_radius = p_h // 2

            draw.rounded_rectangle(
                [cur_x, p_y, cur_x + p_w, p_y + p_h],
                radius=p_radius,
                fill=(12, 16, 24, 195),
                outline=(255, 255, 255, 45),
                width=2
            )

            center_y = p_y + (p_h // 2)
            ic = ri["icon"]
            ic_x = cur_x + padding_x
            ic_y = center_y - (ic.height // 2)
            img.paste(ic, (ic_x, ic_y), ic)

            txt_x = ic_x + ic.width + gap_icon_text
            txt_y = center_y - (ri["txt_h"] // 2) - ri["txt_offset_y"]
            draw.text((txt_x, txt_y), ri["handle"], font=font, fill=text_color)

            cur_x += p_w + inter_network_gap

    else:
        # Modo 'floating' (Sem caixa de fundo, apenas sombra projetada suave)
        total_content_w = sum(ri["content_w"] for ri in rendered_items) + (inter_network_gap * (len(rendered_items) - 1))
        max_h = max(ri["content_h"] for ri in rendered_items)
        start_x = max(10, (video_width - total_content_w) // 2)
        start_y = max(10, min(video_height - max_h - 10, final_y))
        cur_x = start_x
        center_y = start_y + (max_h // 2)

        for ri in rendered_items:
            ic = ri["icon"]
            ic_y = center_y - (ic.height // 2)

            # Sombra suave sob o ícone
            shadow_offset = max(2, int(font_size * 0.08))
            img.paste(ic, (cur_x, ic_y), ic)

            # Texto com sombra projetada e contorno
            txt_x = cur_x + ic.width + gap_icon_text
            txt_y = center_y - (ri["txt_h"] // 2) - ri["txt_offset_y"]

            # Drop shadow
            draw.text((txt_x + shadow_offset, txt_y + shadow_offset), ri["handle"], font=font, fill=(0, 0, 0, 180))
            # Texto principal
            draw.text((txt_x, txt_y), ri["handle"], font=font, fill=text_color)

            cur_x += ri["content_w"] + inter_network_gap

    return img


def render_social_overlay_on_frame(base_frame_rgb: np.ndarray, config: dict) -> np.ndarray:
    """
    Aplica a sobreposição de redes sociais diretamente sobre um frame RGB (H, W, 3)
    para exibição instantânea na interface do Streamlit.
    """
    if base_frame_rgb is None:
        return None

    if not config or not config.get("enabled", False):
        return base_frame_rgb

    items = get_active_social_items(config)
    if not items:
        return base_frame_rgb

    fh, fw = base_frame_rgb.shape[:2]
    overlay_img = render_social_overlay_image(fw, fh, config)

    # Converte overlay PIL RGBA para numpy array
    overlay_arr = np.array(overlay_img)
    alpha = (overlay_arr[:, :, 3] / 255.0)[:, :, np.newaxis]
    over_rgb = overlay_arr[:, :, :3]

    result_rgb = base_frame_rgb.copy()
    for c in range(3):
        result_rgb[:, :, c] = (
            alpha[:, :, 0] * over_rgb[:, :, c] +
            (1.0 - alpha[:, :, 0]) * result_rgb[:, :, c]
        ).astype(np.uint8)

    return result_rgb


def apply_social_overlay_to_video(
    video_path: str,
    output_path: str,
    config: dict
) -> dict:
    """
    Aplica a barra de redes sociais sobre o arquivo de vídeo via FFmpeg
    com aceleração por hardware GPU NVENC e fallback automático para CPU.
    """
    if not config or not config.get("enabled", False):
        # Se desabilitado, apenas copia ou retorna o caminho original
        return {"path": video_path, "error": None}

    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Vídeo de entrada não encontrado."}

    items = get_active_social_items(config)
    if not items:
        return {"path": video_path, "error": None}

    # 1. Obtém a resolução do vídeo
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"path": None, "error": "Não foi possível abrir o vídeo."}
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if fw <= 0 or fh <= 0:
        fw, fh = 1080, 1920

    # 2. Gera a imagem PNG transparente do overlay
    overlay_img = render_social_overlay_image(fw, fh, config)
    temp_dir = os.path.dirname(output_path) or "data"
    os.makedirs(temp_dir, exist_ok=True)
    temp_overlay_png = os.path.join(temp_dir, "temp_social_overlay.png")
    overlay_img.save(temp_overlay_png, format="PNG")

    target_out = output_path
    is_in_place = (os.path.abspath(target_out) == os.path.abspath(video_path))
    tmp_out = target_out + ".social_tmp.mp4"

    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    # 3. Executa o FFmpeg com aceleração NVENC (GPU)
    filter_complex = "[0:v][1:v]overlay=0:0[outv]"
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

    # Fallback para libx264 se GPU falhar
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
            "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            tmp_out
        ]
        res = subprocess.run(cmd_cpu, capture_output=True, text=True)

    # Limpeza do PNG temporário
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
        err_msg = res.stderr[-1000:] if res.stderr else "Erro no FFmpeg ao aplicar assinatura de redes sociais."
        return {"path": None, "error": err_msg}
