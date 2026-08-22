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


DANGLING_ENDINGS = {
    'E', 'DE', 'DO', 'DA', 'DOS', 'DAS', 'EM', 'NO', 'NA', 'NOS', 'NAS',
    'COM', 'POR', 'PARA', 'PRA', 'PELO', 'PELA', 'PELOS', 'PELAS',
    'QUE', 'SE', 'UM', 'UMA', 'UNS', 'UMAS', 'A', 'O', 'AS', 'OS',
    'AO', 'AOS', 'MAS', 'OU', 'NEM', 'POIS', 'PORQUE', 'SEU', 'SUA',
    'SEUS', 'SUAS', 'ESTE', 'ESTA', 'ESSE', 'ESSA', 'AQUELE', 'AQUELA'
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


def clean_and_condense_headline(text: str, max_chars: int = 42) -> str:
    """
    Higieniza e sintetiza frases longas para criar uma Headline de topo com pensamento 100% COMPLETO.
    Remove prefixos de orador, prioriza citações diretas e NUNCA deixa preposições ou conjunções cortadas no final.
    """
    if not text:
        return ""
    
    cleaned = text.strip().strip('"\'')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # 1. Se houver aspas com fala direta expressiva, prioriza a citação
    quote_match = re.search(r'["\']([^"\']{10,50})["\']', cleaned)
    if quote_match:
        cleaned = quote_match.group(1).strip()
    
    # 2. Remove prefixos de orador / pauta genérica que ocupam espaço inútil no topo
    cleaned = re.sub(
        r'^(?:[A-ZÀ-Úa-zà-ú\s]{2,25}\s+(?:diz|afirma|revela|prevê|alerta|explica|promete|fala|desafia|conta|dispara|comenta|lembra)\s*(?:que|sobre|o|a|os|as)?[:\s\-]*|\b(?:candidato|entrevistado|apresentador|ministro|senador|deputado|orador)\s+(?:diz|afirma|revela|prevê|alerta|explica|promete|fala|desafia|comenta)\s*(?:que|sobre|o|a|os|as)?[:\s\-]*|\b[A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)?\s*:\s*)',
        '',
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    # 3. Se ainda estiver longo, verifica se há pontuação forte ( ?, !, :, -, , ) para quebrar num pensamento completo
    if len(cleaned) > max_chars:
        for punct in ['?', '!', ':', '-']:
            if punct in cleaned:
                parts = cleaned.split(punct)
                if len(parts[0]) >= 10:
                    cleaned = parts[0] + (punct if punct in ['?', '!'] else '')
                    break

    # 4. Se ainda ultrapassar max_chars, corta de forma inteligente por palavras sem deixar preposições penduradas
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
            cleaned = " ".join(words[:4])

    cleaned = cleaned.strip(' ,;:-').upper()
    
    # Se terminar sem pontuação e parecer pergunta, adiciona ?
    if cleaned and not cleaned[-1] in '?!.':
        first_word = cleaned.split()[0]
        if first_word in {'QUEM', 'COMO', 'ONDE', 'QUANDO', 'QUAL', 'QUAIS', 'PORQUE', 'SERÁ', 'VAI', 'VALE', 'É'}:
            cleaned += '?'
            
    return cleaned


def format_headline_text(text: str, max_width_chars: int = 22, max_lines: int = 2) -> str:
    """
    Formata e quebra o texto da headline em até 2 linhas curtas e harmoniosas,
    garantindo que a frase seja concisa, em caixa alta e com pensamento 100% completo.
    No ASS, quebras de linha são feitas com \\N.
    """
    if not text:
        return ""
    
    condensed = clean_and_condense_headline(text, max_chars=44)
    if not condensed:
        condensed = text.strip().upper()[:40]
        
    total_len = len(condensed)
    target_width = max_width_chars
    if total_len <= 30:
        target_width = 16
    elif total_len <= 44:
        target_width = 22
    else:
        target_width = 24
        
    wrapped_lines = textwrap.wrap(condensed, width=target_width)
    if not wrapped_lines:
        return condensed
        
    # Limita ao número máximo de linhas configurado (padrão: 2 linhas)
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
