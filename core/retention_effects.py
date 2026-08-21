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
