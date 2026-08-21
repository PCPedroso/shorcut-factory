"""
headline_drawer.py — Headline / Título Fixo de Retenção no Topo (9:16)
Gera caixas de texto magnéticas de topo com estilos pré-definidos (Amarelo, Vermelho, Dark, Custom),
com quebra de linha inteligente e suporte a ASS v4+ com caixa opaca ou contorno de alto contraste.
"""

import re
import textwrap

HEADLINE_PRESETS = {
    "yellow_black": {
        "name": "🟡 Amarelo Vibrante (Texto Preto)",
        "text_color": "#000000",
        "bg_color": "#FFE600",
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
}


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


def format_headline_text(text: str, max_width_chars: int = 24) -> str:
    """
    Formata e quebra o texto do título em até 2 ou 3 linhas curtas,
    colocando em caixa alta com formatação ideal para leitura rápida em tela vertical.
    No ASS, quebras de linha são feitas com \\N.
    """
    if not text:
        return ""
    
    # Remove aspas extras ou marcadores
    cleaned = text.strip().strip('"\'').upper()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Quebra em linhas de até max_width_chars caracteres sem quebrar palavras
    wrapped_lines = textwrap.wrap(cleaned, width=max_width_chars)
    if not wrapped_lines:
        return cleaned
    
    # Limita a no máximo 3 linhas
    wrapped_lines = wrapped_lines[:3]
    return r"\N".join(wrapped_lines)


def build_ass_headline_style(
    preset_key: str = "yellow_black",
    custom_text_color: str = "#FFFFFF",
    custom_bg_color: str = "#000000",
    font_size: int = 46,
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
    
    margin_lr = int(video_width * 0.06)
    margin_v = margin_top  # Distância do topo
    
    # Style: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,
    # Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,
    # Alignment, MarginL, MarginR, MarginV, Encoding
    style_line = (
        f"Style: Headline,Montserrat ExtraBold,{font_size},{ass_primary},&H000000FF&,"
        f"{ass_outline},{ass_back},-1,0,0,0,100,100,1,0,{border_style},{outline_width},2,"
        f"8,{margin_lr},{margin_lr},{margin_v},1"
    )
    
    return style_line
