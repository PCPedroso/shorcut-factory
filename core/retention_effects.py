"""
retention_effects.py — Efeitos Visuais de Retenção (Zoom Punch & Emojis Contextuais)
Aumenta a retenção de tela em vídeos verticais 9:16 para Reels, TikTok e YouTube Shorts.
"""

import re

# Dicionário de termos emocionais e seus emojis correspondentes
EMOJI_KEYWORDS = {
    r"\b(dinheiro|grana|lucro|milh[oõ]es|vendas?|rico|faturamento|d[oó]lar|reais|investir|investimento)\b": "💰",
    r"\b(fogo|viral|explodi[uo]|bomba|hype|foguete)\b": "🔥",
    r"\b(aten[cç][aã]o|cuidado|perigo|erro|pare|urgente|alerta)\b": "⚠️",
    r"\b(segredo|hack|truque|revelado|chave|mist[eé]rio)\b": "🤫",
    r"\b(meta|foco|sucesso|objetivo|topo|crescer|avan[cç]ar)\b": "🚀",
    r"\b(mente|c[eé]rebro|ideia|pensamento|estrat[eé]gia|inteligente)\b": "🧠",
    r"\b(incr[ií]vel|maravilhoso|perfeito|sensacional|top)\b": "⭐",
    r"\b(amor|corac[aã]o|paix[aã]o)\b": "❤️",
    r"\b(tempo|r[aá]pido|hora|urg[eê]ncia|demora|minutos?)\b": "⏳",
    r"\b(falou|conversa|disse|pergunta|resposta|entrevista)\b": "🗣️",
    r"\b(medo|terror|pavor|susto|chocante)\b": "😱",
    r"\b(engra[cç]ado|rir|piada|kkk|risos?)\b": "😂",
}


def attach_contextual_emojis_to_words(words: list, max_emojis: int = 6) -> list:
    """
    Identifica palavras de alto impacto na lista de palavras e anexa emojis visuais
    para destacar na legenda dinâmica.
    """
    if not words:
        return words

    enriched_words = []
    emojis_used_count = 0

    for item in words:
        w_dict = dict(item)
        w_text = w_dict.get("word", "")
        
        if emojis_used_count < max_emojis:
            for pattern, emoji in EMOJI_KEYWORDS.items():
                if re.search(pattern, w_text, re.IGNORECASE):
                    # Adiciona o emoji se ainda não estiver presente
                    if emoji not in w_text:
                        w_dict["word"] = f"{w_text} {emoji}"
                        emojis_used_count += 1
                        break
        
        enriched_words.append(w_dict)

    return enriched_words


def generate_zoom_punch_filter(
    duration: float,
    interval: float = 9.0,
    punch_duration: float = 0.45,
    zoom_factor: float = 1.08,
) -> str:
    """
    Gera expressão de filtro FFmpeg para aplicar Zoom Punchs sutis e dinâmicos
    a cada intervalo de segundos, quebrando a monotonia visual sem cortar elementos da cena.
    
    Exemplo: em t=8.0 a 8.45s, dá um leve punch de zoom 1.08x e volta suavemente.
    """
    if duration <= 6.0:
        return ""

    conditions = []
    t = interval
    while t + punch_duration < duration - 1.5:
        t_start = round(t, 2)
        t_end = round(t + punch_duration, 2)
        conditions.append(f"between(t,{t_start},{t_end})")
        t += interval

    if not conditions:
        return ""

    combined_cond = "+".join(conditions)
    # FFmpeg filter: scale dinâmico ou crop com zoom suave
    # Multiplica dimensões e recentraliza
    crop_w = f"in_w/if({combined_cond},{zoom_factor},1.0)"
    crop_h = f"in_h/if({combined_cond},{zoom_factor},1.0)"
    
    vf = f"crop=w='{crop_w}':h='{crop_h}':x='(in_w-out_w)/2':y='(in_h-out_h)/2',scale=1080:1920:flags=lanczos"
    return vf


# ─────────────────────────────────────────────────────────────────────────────
# ⏳ BARRA DE PROGRESSO ANIMADA DE RETENÇÃO (FFmpeg drawbox)
# ─────────────────────────────────────────────────────────────────────────────

PROGRESS_BAR_COLORS = {
    "red": {"name": "🔴 Vermelho Shorts / YouTube", "color": "#FF0000", "ffmpeg": "0xFF0000"},
    "yellow": {"name": "🟡 Amarelo Viral", "color": "#FFE600", "ffmpeg": "0xFFE600"},
    "cyan": {"name": "💎 Ciano Neon", "color": "#00E5FF", "ffmpeg": "0x00E5FF"},
    "white": {"name": "⚪ Branco Clean", "color": "#FFFFFF", "ffmpeg": "0xFFFFFF"},
    "green": {"name": "🟢 Verde Sucesso", "color": "#00E676", "ffmpeg": "0x00E676"},
}


def _hex_to_ffmpeg_color(hex_str: str) -> str:
    """Normaliza cores hex (#RRGGBB) para sintaxe aceita no drawbox do FFmpeg (0xRRGGBB)."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 6:
        return f"0x{clean.upper()}"
    elif len(clean) == 3:
        return f"0x{clean[0]*2}{clean[1]*2}{clean[2]*2}".upper()
    return "0xFF0000"


def generate_progress_bar_filter(
    duration: float,
    color_hex: str = "#FF0000",
    height_px: int = 8,
    bg_alpha: float = 0.45
) -> str:
    """
    Gera expressão de filtro FFmpeg para desenhar uma barra de progresso fluida e minimalista
    no rodapé exato do vídeo (y = ih - height_px), preenchendo proporcionalmente ao tempo `t`.
    """
    if duration <= 1.0:
        return ""

    fg_col = _hex_to_ffmpeg_color(color_hex)
    dur_f = max(0.1, round(float(duration), 3))
    h = max(2, min(30, int(height_px)))

    # 1. Trilha de fundo escura semitransparente
    bg_layer = f"drawbox=x=0:y=ih-{h}:w=iw:h={h}:color=0x000000@{bg_alpha:.2f}:t=fill"
    # 2. Barra de progresso preenchendo de 0 a 100% da largura (iw) conforme t avança
    fg_layer = f"drawbox=x=0:y=ih-{h}:w='min(iw,iw*(t/{dur_f}))':h={h}:color={fg_col}@1:t=fill"

    return f"{bg_layer},{fg_layer}"


# ─────────────────────────────────────────────────────────────────────────────
# 🎯 ZOOM DE ÊNFASE NO CLÍMAX (Climax Punchline Zoom)
# ─────────────────────────────────────────────────────────────────────────────

def generate_climax_zoom_filter(
    duration: float,
    climax_duration: float = 3.5,
    zoom_factor: float = 1.14
) -> str:
    """
    Gera expressão de filtro FFmpeg para aproximar a cena dramaticamente no rosto do orador
    durante os últimos segundos da frase de impacto / conclusão (punchline final).
    """
    if duration <= 5.0:
        return ""

    climax_start = max(0.5, round(duration - climax_duration, 2))
    climax_end = round(duration, 2)
    factor = round(max(1.02, min(1.30, float(zoom_factor))), 2)

    cond = f"between(t,{climax_start},{climax_end})"
    crop_w = f"in_w/if({cond},{factor},1.0)"
    crop_h = f"in_h/if({cond},{factor},1.0)"

    vf = f"crop=w='{crop_w}':h='{crop_h}':x='(in_w-out_w)/2':y='(in_h-out_h)/2',scale=1080:1920:flags=lanczos"
    return vf


# ─────────────────────────────────────────────────────────────────────────────
# 📌 BANNER DE CHAMADA / LOWER THIRD DINÂMICO (Engagement Callout)
# ─────────────────────────────────────────────────────────────────────────────

ENGAGEMENT_CALLOUT_PRESETS = {
    "comment": {
        "name": "💬 Pergunta & Comentário",
        "text": "💬 O que você acha? Comente abaixo!",
    },
    "follow": {
        "name": "🔔 Seguir Canal / Perfil",
        "text": "🔔 Siga para mais cortes diários!",
    },
    "share": {
        "name": "🔥 Compartilhar com Amigos",
        "text": "🔥 Compartilhe com quem precisa ver isso!",
    },
    "save": {
        "name": "📌 Salvar para Depois",
        "text": "📌 Salve este corte para não esquecer!",
    },
    "custom": {
        "name": "✍️ Texto Personalizado",
        "text": "",
    }
}


def format_seconds_to_ass_time(sec: float) -> str:
    """Converte segundos float para o formato de timestamp do ASS: H:MM:SS.cs"""
    sec = max(0.0, sec)
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    seconds = int(sec % 60)
    centiseconds = int(round((sec - int(sec)) * 100))
    if centiseconds >= 100:
        centiseconds = 99
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def generate_engagement_callout_ass_dialogue(
    duration: float,
    callout_text: str,
    callout_duration: float = 4.5
) -> str:
    """
    Gera a linha Dialogue do ASS para exibir um Lower Third elegante de engajamento
    com fade-in de 300ms e fade-out de 300ms nos últimos segundos do vídeo.
    Posicionado na parte inferior centralizada com safe zone (Margem vertical segura).
    """
    if not callout_text or duration <= 3.0:
        return ""

    callout_duration = min(duration - 0.5, max(2.0, float(callout_duration)))
    start_s = max(0.2, duration - callout_duration)
    end_s = max(start_s + 1.0, duration - 0.2)

    start_ass = format_seconds_to_ass_time(start_s)
    end_ass = format_seconds_to_ass_time(end_s)

    clean_text = callout_text.strip().replace("\n", " ")
    # Efeito ASS: \fad(300, 300) = Fade in 300ms, Fade out 300ms
    # Estilo CalloutStyle usa caixa de fundo opaca ou contorno nítido
    dialogue_line = f"Dialogue: 0,{start_ass},{end_ass},CalloutStyle,,0,0,0,,{{\\fad(300,300)}}{clean_text}"
    return dialogue_line

