"""
headline_drawer.py — Headline / Título Fixo de Retenção no Topo (9:16) & Pós-Corte
Gera caixas de texto magnéticas de topo com estilos pré-definidos (Amarelo, Vermelho, Dark, Custom),
quebra de linha inteligente, suporte a ASS v4+ e motor de renderização / prévia instantânea
com sobreposição de caixas individuais (line boxes), bloco único (single card) ou flutuante (outline).
"""

import os
import re
import textwrap
import subprocess
import cv2
import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# Diretório de fontes bundled
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.join(_SCRIPT_DIR, "fonts")
_FONT_BOLD_PATH = os.path.join(_FONTS_DIR, "Montserrat-ExtraBold.ttf")

HEADLINE_PRESETS = {
    "yellow_black": {
        "name": "🟡 Amarelo Vibrante (Texto Preto)",
        "text_color": "#000000",
        "bg_color": "#FFDA29",
        "outline_color": "#000000",
        "border_style": 3,  # Opaque box no ASS
        "box_padding": 8,
    },
    "red_white": {
        "name": "🔴 Alerta Vermelho (Texto Branco)",
        "text_color": "#FFFFFF",
        "bg_color": "#E50914",
        "outline_color": "#B20710",
        "border_style": 3,
        "box_padding": 8,
    },
    "dark_minimal": {
        "name": "⚫ Dark Box (Texto Branco)",
        "text_color": "#FFFFFF",
        "bg_color": "#111111",
        "outline_color": "#333333",
        "border_style": 3,
        "box_padding": 8,
    },
    "white_black": {
        "name": "⚪ Box Branco (Texto Preto)",
        "text_color": "#000000",
        "bg_color": "#FFFFFF",
        "outline_color": "#000000",
        "border_style": 3,
        "box_padding": 8,
    },
    "floating_bold": {
        "name": "✨ Flutuante Bold (Sem Caixa, Contorno Pesado)",
        "text_color": "#FFFFFF",
        "bg_color": "#000000",
        "outline_color": "#000000",
        "border_style": 1,  # Outline normal
        "box_padding": 6,
    },
    "custom": {
        "name": "🎨 Personalizado (Cores e Margens Livres)",
        "text_color": "#000000",
        "bg_color": "#FFDA29",
        "outline_color": "#000000",
        "border_style": 3,
        "box_padding": 8,
    }
}


DANGLING_ENDINGS = {
    'E', 'DE', 'DO', 'DA', 'DOS', 'DAS', 'EM', 'NO', 'NA', 'NOS', 'NAS',
    'COM', 'POR', 'PARA', 'PRA', 'PELO', 'PELA', 'PELOS', 'PELAS',
    'QUE', 'SE', 'UM', 'UMA', 'UNS', 'UMAS', 'A', 'O', 'AS', 'OS',
    'AO', 'AOS', 'MAS', 'OU', 'NEM', 'POIS', 'PORQUE', 'SEU', 'SUA',
    'SEUS', 'SUAS', 'ESTE', 'ESTA', 'ESSE', 'ESSA', 'AQUELE', 'AQUELA'
}


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple:
    """Converte cor hexadecimal (#RRGGBB) para tupla RGBA (r, g, b, a_255)."""
    if not hex_color:
        return (255, 255, 255, 255)
    hex_clean = hex_color.lstrip("#")
    if len(hex_clean) == 6:
        r, g, b = int(hex_clean[0:2], 16), int(hex_clean[2:4], 16), int(hex_clean[4:6], 16)
    elif len(hex_clean) == 3:
        r, g, b = int(hex_clean[0]*2, 16), int(hex_clean[1]*2, 16), int(hex_clean[2]*2, 16)
    else:
        r, g, b = 255, 255, 255
    a = max(0, min(255, int(alpha * 255)))
    return (r, g, b, a)


def hex_to_ass_color(hex_color: str, alpha: float = 0.0) -> str:
    """
    Converte cor hexadecimal (#RRGGBB) para o formato ASS (&HAABBGGRR&).
    Alpha: 0.0 = 100% opaco, 1.0 = 100% transparente.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    elif len(hex_color) == 3:
        r, g, b = hex_color[0]*2, hex_color[1]*2, hex_color[2]*2
    else:
        r, g, b = "FF", "FF", "FF"
    a_val = max(0, min(255, int(alpha * 255)))
    a_hex = format(a_val, "02X")
    return f"&H{a_hex}{b.upper()}{g.upper()}{r.upper()}&"


def clean_and_condense_headline(text: str, max_chars: int = 75) -> str:
    """
    Higieniza e sintetiza frases para criar uma Headline de topo com pensamento 100% COMPLETO.
    Remove prefixos de orador, prioriza citações diretas e NUNCA deixa preposições ou conjunções cortadas no final.
    """
    if not text:
        return ""
    
    cleaned = text.strip().strip('"\'')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # 1. Se houver aspas com fala direta expressiva, prioriza a citação
    quote_match = re.search(r'["\']([^"\']{10,75})["\']', cleaned)
    if quote_match:
        cleaned = quote_match.group(1).strip()
    
    # 2. Remove prefixos de orador / pauta genérica que ocupam espaço inútil no topo
    cleaned = re.sub(
        r'^(?:[A-ZÀ-Úa-zà-ú\s]{2,25}\s+(?:diz|afirma|revela|prevê|alerta|explica|promete|fala|desafia|conta|dispara|comenta|lembra)\s*(?:que|sobre|o|a|os|as)?[:\s\-]*|\b(?:candidato|entrevistado|apresentador|ministro|senador|deputado|orador)\s+(?:diz|afirma|revela|prevê|alerta|explica|promete|fala|desafia|comenta)\s*(?:que|sobre|o|a|os|as)?[:\s\-]*|\b[A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)?\s*:\s*)',
        '',
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    # 3. Se ainda ultrapassar max_chars, corta de forma inteligente por palavras sem deixar preposições penduradas
    if len(cleaned) > max_chars:
        # Se houver pontuação forte ( ?, !, :, -, , ) para quebrar num pensamento completo
        for punct in ['?', '!', ':', '-']:
            if punct in cleaned:
                parts = cleaned.split(punct)
                if len(parts[0]) >= 15 and len(parts[0]) <= max_chars:
                    cleaned = parts[0] + (punct if punct in ['?', '!'] else '')
                    break

    if len(cleaned) > max_chars:
        words = cleaned.split()
        cur_phrase = []
        for w in words:
            if len(" ".join(cur_phrase + [w])) <= max_chars:
                cur_phrase.append(w)
            else:
                break
        
        # Remove palavras penduradas do final (preposições, conjunções, artigos)
        while cur_phrase and (cur_phrase[-1].upper().rstrip('.,;!?:') in DANGLING_ENDINGS or len(cur_phrase[-1]) <= 1):
            cur_phrase.pop()
            
        if cur_phrase:
            cleaned = " ".join(cur_phrase)
        else:
            cleaned = " ".join(words[:6])

    cleaned = cleaned.strip(' ,;:-').upper()
    return cleaned


def format_headline_text(text: str, max_width_chars: int = 27, max_lines: int = 3) -> str:
    """
    Formata e quebra o texto da headline em linhas largas e harmoniosas,
    ocupando bem o espaço horizontal superior do corte vertical 9:16 (sem margens laterais vazias excessivas).
    No ASS, quebras de linha são feitas com \\N.
    """
    if not text:
        return ""
    
    condensed = clean_and_condense_headline(text, max_chars=75)
    if not condensed:
        condensed = text.strip().upper()[:75]
        
    total_len = len(condensed)
    
    # Distribui a largura por linha para ocupar bem a tela horizontal (24 a 28 caracteres por linha)
    if total_len <= 26:
        target_width = 26
    elif total_len <= 54:
        target_width = max(24, (total_len // 2) + 2)
    else:
        target_width = max(25, (total_len // 3) + 2)
        
    wrapped_lines = textwrap.wrap(condensed, width=target_width)
    if not wrapped_lines:
        return condensed
        
    # Limita ao número máximo de linhas configurado (padrão: 3 linhas)
    if len(wrapped_lines) > max_lines:
        wrapped_lines = wrapped_lines[:max_lines]
        # Garante que a última linha não termina com preposição/conjunção cortada
        last_words = wrapped_lines[-1].split()
        while last_words and last_words[-1].upper().rstrip('.,;!?:') in DANGLING_ENDINGS:
            last_words.pop()
        if last_words:
            wrapped_lines[-1] = " ".join(last_words)

    return r"\N".join(wrapped_lines)


def build_ass_headline_style(
    preset_key: str = "yellow_black",
    custom_text_color: str = "#FFFFFF",
    custom_bg_color: str = "#000000",
    font_size: int = 48,
    video_width: int = 1080,
    video_height: int = 1920,
    margin_top: int = 120,
) -> str:
    """
    Retorna a linha de definição de Style ASS para a Headline.
    Alinhamento 8 = Top Center.
    """
    preset = HEADLINE_PRESETS.get(preset_key, HEADLINE_PRESETS["yellow_black"])
    
    if preset_key == "custom":
        text_color = custom_text_color
        bg_color = custom_bg_color
        border_style = 3
        outline_width = 8
    else:
        text_color = preset["text_color"]
        bg_color = preset["bg_color"]
        border_style = preset["border_style"]
        outline_width = preset["box_padding"]
        
    ass_primary = hex_to_ass_color(text_color, alpha=0.0)
    ass_outline = hex_to_ass_color(bg_color if border_style == 3 else preset.get("outline_color", "#000000"), alpha=0.0)
    ass_back = hex_to_ass_color(bg_color, alpha=0.05 if border_style == 3 else 0.5)
    
    margin_lr = int(video_width * 0.04)  # Margens laterais compactas (4% = ~43px)
    margin_v = margin_top  # Distância do topo
    
    style_line = (
        f"Style: Headline,Montserrat ExtraBold,{font_size},{ass_primary},&H000000FF&,"
        f"{ass_outline},{ass_back},-1,0,0,0,100,100,1,0,{border_style},{outline_width},2,"
        f"8,{margin_lr},{margin_lr},{margin_v},1"
    )
    
    return style_line


# ──────────────────────────────────────────────────────────────────────────────
# Motor de Renderização de Headline em Alta Fidelidade (Pós-Corte & Prévia)
# ──────────────────────────────────────────────────────────────────────────────

def _get_pil_font(font_size: int):
    """Carrega fonte Montserrat-ExtraBold ou fallback seguro."""
    if os.path.exists(_FONT_BOLD_PATH):
        try:
            return ImageFont.truetype(_FONT_BOLD_PATH, max(12, int(font_size)))
        except Exception:
            pass
    try:
        return ImageFont.truetype("arialbd.ttf", max(12, int(font_size)))
    except Exception:
        return ImageFont.load_default()


def render_headline_overlay(
    video_width: int,
    video_height: int,
    text: str,
    config: dict = None
) -> np.ndarray:
    """
    Renderiza a camada gráfica transparente (RGBA) da Headline de Topo para overlay instantâneo.
    Suporta estilos de Caixas por Linha (TikTok/Reels), Bloco Único (Card) e Flutuante (Outline).
    """
    config = config or {}
    preset_key = config.get("preset_key", "yellow_black")
    preset = HEADLINE_PRESETS.get(preset_key, HEADLINE_PRESETS["yellow_black"])

    # Cores
    if preset_key == "custom":
        text_color_hex = config.get("text_color", "#000000")
        bg_color_hex = config.get("bg_color", "#FFDA29")
    else:
        text_color_hex = config.get("text_color") or preset["text_color"]
        bg_color_hex = config.get("bg_color") or preset["bg_color"]

    bg_opacity = float(config.get("bg_opacity", 1.0))
    text_rgba = hex_to_rgba(text_color_hex, alpha=1.0)
    bg_rgba = hex_to_rgba(bg_color_hex, alpha=bg_opacity)

    # Parâmetros de Layout
    font_size = int(config.get("font_size", 70))
    margin_top = int(config.get("margin_top", 240))
    container_mode = config.get("container_mode", "line_boxes")  # 'line_boxes', 'single_card', 'outline_only'
    container_width_pct = float(config.get("container_width_pct", 92.0))
    box_padding_x = int(config.get("box_padding_x", 28))
    box_padding_y = int(config.get("box_padding_y", 16))
    line_spacing = int(config.get("line_spacing", 14))
    corner_radius = int(config.get("corner_radius", 14))
    alignment = config.get("alignment", "center")  # 'center', 'left', 'right'
    shadow_enabled = bool(config.get("shadow_enabled", True))
    shadow_offset_y = int(config.get("shadow_offset_y", 6))
    stroke_width = int(config.get("stroke_width", 0))
    stroke_color_hex = config.get("stroke_color", "#000000")
    stroke_rgba = hex_to_rgba(stroke_color_hex, alpha=1.0)

    if preset_key == "floating_bold" or container_mode == "outline_only":
        container_mode = "outline_only"
        if stroke_width <= 0:
            stroke_width = max(3, int(font_size * 0.08))

    img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _get_pil_font(font_size)

    # Tratamento e quebra de texto
    clean_text = text.strip() if text else "SEU TÍTULO AQUI"
    if "\n" in clean_text:
        raw_lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
    else:
        # Calcula largura máxima permitida para o texto
        max_content_w = max(200, int(video_width * (container_width_pct / 100.0)) - (box_padding_x * 2))
        
        # Estima caracteres por linha
        sample_w = font.getbbox("ABCDEFGHIJKLMNOPQRSTUVWXYZ")[2] / 26.0
        chars_per_line = max(10, int(max_content_w / max(1.0, sample_w)))
        
        raw_lines = textwrap.wrap(clean_text, width=chars_per_line)
        if not raw_lines:
            raw_lines = [clean_text]

    # Mede dimensões exatas de cada linha
    line_metrics = []
    max_line_w = 0
    total_text_h = 0

    for l_text in raw_lines:
        bbox = font.getbbox(l_text)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        line_metrics.append({
            "text": l_text,
            "w": lw,
            "h": lh,
            "offset_x": bbox[0],
            "offset_y": bbox[1]
        })
        if lw > max_line_w:
            max_line_w = lw

    n_lines = len(line_metrics)
    total_h = sum(m["h"] + (box_padding_y * 2) for m in line_metrics) + (line_spacing * (n_lines - 1))

    # Desenho dos elementos
    cur_y = margin_top

    if container_mode == "single_card":
        card_w = max_line_w + (box_padding_x * 2)
        card_h = total_h

        if alignment == "left":
            card_x0 = int(video_width * ((100.0 - container_width_pct) / 200.0))
        elif alignment == "right":
            card_x0 = int(video_width - (video_width * ((100.0 - container_width_pct) / 200.0)) - card_w)
        else:
            card_x0 = (video_width - card_w) // 2

        card_x1 = card_x0 + card_w
        card_y0 = cur_y
        card_y1 = card_y0 + card_h

        if shadow_enabled and bg_opacity > 0.1:
            s_rgba = (0, 0, 0, int(90 * bg_opacity))
            draw.rounded_rectangle(
                [card_x0, card_y0 + shadow_offset_y, card_x1, card_y1 + shadow_offset_y],
                radius=corner_radius,
                fill=s_rgba
            )

        if bg_opacity > 0.01:
            draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=corner_radius, fill=bg_rgba)

        # Desenha cada linha de texto dentro do card
        text_y = card_y0 + box_padding_y
        for m in line_metrics:
            lw = m["w"]
            if alignment == "left":
                tx = card_x0 + box_padding_x - m["offset_x"]
            elif alignment == "right":
                tx = card_x1 - box_padding_x - lw - m["offset_x"]
            else:
                tx = (video_width - lw) // 2 - m["offset_x"]

            ty = text_y - m["offset_y"]
            
            if stroke_width > 0:
                draw.text((tx, ty), m["text"], font=font, fill=text_rgba, stroke_width=stroke_width, stroke_fill=stroke_rgba)
            else:
                draw.text((tx, ty), m["text"], font=font, fill=text_rgba)
            
            text_y += m["h"] + (box_padding_y * 2) + line_spacing - (box_padding_y * 2)

    elif container_mode == "line_boxes":
        # Cada linha recebe sua própria caixa arredondada
        for m in line_metrics:
            lw = m["w"]
            lh = m["h"]
            box_w = lw + (box_padding_x * 2)
            box_h = lh + (box_padding_y * 2)

            if alignment == "left":
                bx0 = int(video_width * ((100.0 - container_width_pct) / 200.0))
            elif alignment == "right":
                bx0 = int(video_width - (video_width * ((100.0 - container_width_pct) / 200.0)) - box_w)
            else:
                bx0 = (video_width - box_w) // 2

            bx1 = bx0 + box_w
            by0 = cur_y
            by1 = by0 + box_h

            if shadow_enabled and bg_opacity > 0.1:
                s_rgba = (0, 0, 0, int(90 * bg_opacity))
                draw.rounded_rectangle(
                    [bx0, by0 + shadow_offset_y, bx1, by1 + shadow_offset_y],
                    radius=corner_radius,
                    fill=s_rgba
                )

            if bg_opacity > 0.01:
                draw.rounded_rectangle([bx0, by0, bx1, by1], radius=corner_radius, fill=bg_rgba)

            # Texto centrado dentro de cada caixa
            tx = bx0 + box_padding_x - m["offset_x"]
            ty = by0 + box_padding_y - m["offset_y"]

            if stroke_width > 0:
                draw.text((tx, ty), m["text"], font=font, fill=text_rgba, stroke_width=stroke_width, stroke_fill=stroke_rgba)
            else:
                draw.text((tx, ty), m["text"], font=font, fill=text_rgba)

            cur_y += box_h + line_spacing

    elif container_mode == "outline_only":
        # Texto puro com contorno e sombra sem caixa de fundo
        for m in line_metrics:
            lw = m["w"]
            lh = m["h"]

            if alignment == "left":
                tx = int(video_width * ((100.0 - container_width_pct) / 200.0)) - m["offset_x"]
            elif alignment == "right":
                tx = int(video_width - (video_width * ((100.0 - container_width_pct) / 200.0)) - lw) - m["offset_x"]
            else:
                tx = (video_width - lw) // 2 - m["offset_x"]

            ty = cur_y - m["offset_y"]

            if shadow_enabled:
                draw.text(
                    (tx + 4, ty + shadow_offset_y),
                    m["text"],
                    font=font,
                    fill=(0, 0, 0, 180),
                    stroke_width=stroke_width,
                    stroke_fill=(0, 0, 0, 180)
                )

            draw.text((tx, ty), m["text"], font=font, fill=text_rgba, stroke_width=stroke_width, stroke_fill=stroke_rgba)
            cur_y += lh + line_spacing + 10

    return np.array(img)


def draw_headline_on_frame(
    frame_bgr: np.ndarray,
    text: str,
    config: dict = None
) -> np.ndarray:
    """
    Aplica a camada de Headline diretamente sobre um frame BGR (OpenCV) e retorna a imagem RGB.
    """
    if frame_bgr is None:
        return None

    h, w = frame_bgr.shape[:2]
    overlay_rgba = render_headline_overlay(w, h, text, config)

    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    alpha = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
    overlay_rgb = overlay_rgba[:, :, :3].astype(np.float32)

    composited = (overlay_rgb * alpha + frame_rgb.astype(np.float32) * (1.0 - alpha)).astype(np.uint8)
    return composited


def generate_headline_preview(
    video_path: str,
    text: str,
    config: dict = None,
    timestamp_s: float = 0.0
) -> np.ndarray:
    """
    Gera uma prévia visual instantânea (RGB) da Headline sobreposta no frame exato do vídeo.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_no = int(timestamp_s * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return None

    return draw_headline_on_frame(frame, text, config)


def apply_headline_to_video(
    video_path: str,
    text: str,
    config: dict = None,
    output_path: str = None
) -> dict:
    """
    Renderiza e queima a Headline diretamente no arquivo de vídeo com aceleração por GPU (NVENC).
    Pós-corte instantâneo sem necessitar de reprocessamento do vídeo do zero.
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Vídeo original não encontrado."}

    if not text or not text.strip():
        return {"path": None, "error": "Texto da Headline está vazio."}

    # 1. Obtém resolução do vídeo
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"path": None, "error": "Não foi possível abrir o arquivo de vídeo."}
    vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if vw <= 0 or vh <= 0:
        vw, vh = 1080, 1920

    # 2. Renderiza imagem RGBA transparente completa do overlay
    overlay_rgba = render_headline_overlay(vw, vh, text, config)

    temp_dir = os.path.dirname(video_path) or "data"
    temp_overlay_png = os.path.join(temp_dir, f"temp_hl_{os.path.basename(video_path)}.png")

    Image.fromarray(overlay_rgba).save(temp_overlay_png, format="PNG")

    target_out = output_path
    if not target_out:
        target_out = video_path

    tmp_out = target_out + ".hl_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    # 3. Executa FFmpeg com GPU NVENC e fallback CPU
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

    res = subprocess.run(cmd_gpu, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # Fallback para CPU libx264 se GPU falhar
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
        res = subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    # Limpeza do PNG temporário
    if os.path.exists(temp_overlay_png):
        try:
            os.remove(temp_overlay_png)
        except Exception:
            pass

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.rename(tmp_out, target_out)
        return {"path": target_out, "error": None}
    else:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        err_msg = res.stderr.decode("utf-8", errors="replace") if res.stderr else "Erro desconhecido"
        return {"path": None, "error": f"FFmpeg falhou ao aplicar Headline:\n{err_msg[-1500:]}"}
