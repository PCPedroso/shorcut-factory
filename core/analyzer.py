"""
analyzer.py — Inteligência Temática: Pautas, Compositor de Micro-Assuntos e Blocos

Estratégia Otimizada:
1. Condensação Inteligente da Transcrição:
   - Em vez de enviar milhares de palavras de ruído/pausa, envia os trechos de cada minuto
     de forma concisa com timestamps claros [HH:MM:SS].
2. Prompt Direto e Específico:
   - Força Llama 3 / Qwen / Mistral a retornar estritamente a lista numerada de 8 a 15 pautas.
3. Compositor de Pautas Interativo:
   - Transforma as pautas em blocos temporais reais para composição e corte.
"""

import ollama
import re


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários de Tempo e Texto
# ──────────────────────────────────────────────────────────────────────────────

def parse_time_str_to_seconds(t_str: str) -> float:
    """Converte 'HH:MM:SS' ou 'MM:SS' para segundos float."""
    parts = t_str.strip().split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(t_str)


def format_seconds_to_time(secs: float) -> str:
    """Converte segundos para 'HH:MM:SS'."""
    secs = max(0, int(secs))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration_human(secs: float) -> str:
    """Retorna duração amigável como '3m 45s' ou '12m 10s'."""
    m = int(secs // 60)
    s = int(secs % 60)
    if m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _clean_ai_title(title: str) -> str:
    """Remove ruídos, formatação markdown e introduções do título gerado pela IA."""
    title = title.strip()
    title = re.sub(r'[*_`"\'“”:]', '', title).strip()
    title = re.sub(r'^\s*\d+[\.\)\-:]\s*', '', title).strip()
    prefixes = [
        r'^Entendi[,\.\s]*',
        r'^Aqui vai[,\.\s]*',
        r'^Aqui est[aã]o?[,\.\s]*',
        r'^T[íi]tulo:\s*',
        r'^Assunto:\s*',
        r'^Tema:\s*',
        r'^Pauta:\s*',
        r'^Pergunta:\s*'
    ]
    for p in prefixes:
        title = re.sub(p, '', title, flags=re.IGNORECASE).strip()
    return title


def _build_concise_transcript(chunks_list: list, chars_per_chunk: int = 140) -> str:
    """
    Condensa os chunks de 1 minuto em linhas objetivas com timestamp,
    reduzindo o consumo de tokens e melhorando a atenção do LLM.
    """
    lines = []
    for c in chunks_list:
        t_str = format_seconds_to_time(c['start'])
        snippet = c['text'].strip()[:chars_per_chunk].replace('\n', ' ')
        lines.append(f"[{t_str}] {snippet}...")
    return "\n".join(lines)


def _extract_topics_resilient(raw_text: str, chunks_list: list) -> list[dict]:
    """
    Extrai lista de tópicos no formato: 1. [00:05:00] Título do assunto.
    """
    topics = []
    time_regex = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)')

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue

        if any(h in line.lower() for h in ["example", "transcript", "aqui estão", "observações", "principais pontos"]):
            continue

        is_numbered_main = bool(re.match(r'^\s*\d+[\.\)\-:]\s+', line))
        t_match = time_regex.search(line)

        if is_numbered_main or t_match:
            if t_match:
                time_raw = t_match.group(1).strip()
                if len(time_raw.split(':')) == 2:
                    time_raw = f"00:{time_raw}"
                title_part = re.sub(r'\[?\d{1,2}:\d{2}(?::\d{2})?\]?', '', line)
                title_clean = _clean_ai_title(title_part)
                start_s = parse_time_str_to_seconds(time_raw)
            else:
                title_clean = _clean_ai_title(line)
                start_s = 0.0
                time_raw = format_seconds_to_time(start_s)

            if len(title_clean) > 3:
                topics.append({
                    "start_str": time_raw,
                    "start_s": start_s,
                    "title": title_clean
                })

    topics = sorted(topics, key=lambda x: x["start_s"])
    unique_topics = []
    seen_starts = set()
    for t in topics:
        if t["start_str"] not in seen_starts:
            seen_starts.add(t["start_str"])
            unique_topics.append(t)

    return unique_topics


def build_micro_pautas(topics: list[dict], chunks_list: list) -> list[dict]:
    """
    Estrutura a lista de micro-assuntos com início, fim e duração exata de cada um.
    """
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']

    if not topics:
        return []

    if topics[0]["start_s"] > 30.0:
        topics.insert(0, {
            "start_str": "00:00:00",
            "start_s": 0.0,
            "title": "Abertura e Apresentação Inicial"
        })

    pautas = []
    for i, t in enumerate(topics):
        start_s = t["start_s"]
        if start_s >= total_video_duration:
            break

        if i + 1 < len(topics):
            end_s = min(topics[i + 1]["start_s"], total_video_duration)
        else:
            end_s = total_video_duration

        duration_s = max(0, end_s - start_s)
        
        if duration_s < 10 and i + 1 < len(topics):
            continue

        pautas.append({
            "id": len(pautas) + 1,
            "start": format_seconds_to_time(start_s),
            "end": format_seconds_to_time(end_s),
            "start_s": start_s,
            "end_s": end_s,
            "duration_s": duration_s,
            "duration_label": format_duration_human(duration_s),
            "title": t["title"]
        })

    return pautas


def build_suggested_bundles(pautas: list[dict], min_minutes: int = 10) -> list[dict]:
    """
    Agrupa pautas sequenciais automaticamente formando vídeos de 10+ minutos.
    """
    if not pautas:
        return []

    min_duration_s = min_minutes * 60
    bundles = []
    current_pautas = []
    current_duration = 0.0
    bundle_num = 1

    for p in pautas:
        current_pautas.append(p)
        current_duration += p["duration_s"]

        if current_duration >= min_duration_s:
            start_fmt = current_pautas[0]["start"]
            end_fmt = current_pautas[-1]["end"]
            main_title = current_pautas[0]["title"]
            topics_included = [x["title"] for x in current_pautas]

            bundles.append({
                "series_label": f"Vídeo {bundle_num}",
                "start": start_fmt,
                "end": end_fmt,
                "start_s": current_pautas[0]["start_s"],
                "end_s": current_pautas[-1]["end_s"],
                "duration_s": current_duration,
                "duration_label": format_duration_human(current_duration),
                "title": f"{main_title} (+ {len(current_pautas)-1} pautas)",
                "pautas_incluidas": topics_included,
                "has_hook": len(current_pautas) > 1,
                "notes": f"Reúne {len(current_pautas)} pautas totalizando {format_duration_human(current_duration)}."
            })
            bundle_num += 1
            current_pautas = []
            current_duration = 0.0

    if current_pautas:
        start_fmt = current_pautas[0]["start"]
        end_fmt = current_pautas[-1]["end"]
        main_title = current_pautas[0]["title"]
        topics_included = [x["title"] for x in current_pautas]
        bundles.append({
            "series_label": f"Vídeo {bundle_num} (Parte Final)",
            "start": start_fmt,
            "end": end_fmt,
            "start_s": current_pautas[0]["start_s"],
            "end_s": current_pautas[-1]["end_s"],
            "duration_s": current_duration,
            "duration_label": format_duration_human(current_duration),
            "title": f"{main_title} (Final)",
            "pautas_incluidas": topics_included,
            "has_hook": False,
            "notes": f"Pautas finais totalizando {format_duration_human(current_duration)}."
        })

    return bundles


def _build_viral_hooks(topics: list[dict], chunks_list: list) -> list[dict]:
    """Cortes virais curtos (30s a 60s) para Shorts/TikTok."""
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']
    hooks = []

    for i, item in enumerate(topics):
        start_s = item["start_s"]
        if start_s >= total_video_duration:
            continue

        end_s = min(start_s + 55, total_video_duration)
        start_fmt = format_seconds_to_time(start_s)
        end_fmt = format_seconds_to_time(end_s)

        hooks.append({
            "start": start_fmt,
            "end": end_fmt,
            "title": f"🔥 {item['title']}",
            "has_hook": False,
            "notes": f"Corte Viral para Shorts/TikTok ({(end_s - start_s):.0f}s).",
            "series_label": f"Short {i + 1}"
        })

    return hooks


# ──────────────────────────────────────────────────────────────────────────────
# API Principal
# ──────────────────────────────────────────────────────────────────────────────

def analyze_transcript(chunked_transcript: str, mode: str = "pautas",
                       model: str = "llama3",
                       chunks_list: list = None) -> dict:
    """
    Executa a identificação de pautas ou ganchos no Ollama com prompting otimizado.
    """
    log = []

    try:
        # Usa representação concisa dos chunks para máxima atenção da IA
        if chunks_list:
            concise_text = _build_concise_transcript(chunks_list)
        else:
            concise_text = chunked_transcript

        if mode in ("pautas", "blocos"):
            prompt = f"""Analise a lista de trechos da entrevista abaixo.
Extraia uma lista numerada contendo apenas as perguntas ou assuntos novos abordados.

Regras:
- Responda OBRIGATORIAMENTE em português.
- Use estritamente o formato: 1. [HH:MM:SS] Título do assunto
- Não escreva introduções, resumos ou conclusões.

Exemplo de formato:
1. [00:00:00] Pergunta sobre reforma do Estado e nomes de ministros
2. [00:01:00] Modelo da Justiça do Trabalho e contratações
3. [00:06:00] Recursos do Banco Master e produção cinematográfica
4. [00:14:00] Redução da maioridade penal e novos presídios

Transcrição da entrevista:
{concise_text}"""
        else:
            prompt = f"""Analise os trechos abaixo e encontre de 3 a 6 momentos de alto impacto (máximo 60 segundos cada) para YouTube Shorts ou TikTok.
Formato estrito:
1. [00:02:15] "Declaração contundente sobre o assunto"
2. [00:08:40] "Outra frase de alto impacto"

Transcrição:
{concise_text}"""

        response = ollama.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': 'Responda estritamente no formato de lista solicitado. Não converse nem explique.'},
                {'role': 'user', 'content': prompt},
            ]
        )

        raw_content = response['message']['content']
        log.append(f"=== RESPOSTA DO MODELO ({model}) ===\n{raw_content}")

        # Extração de tópicos
        topics = _extract_topics_resilient(raw_content, chunks_list or [])

        log.append(f"\n=== TÓPICOS/PAUTAS PROCESSADOS ({len(topics)}) ===")
        for t in topics:
            log.append(f"  • [{t['start_str']}] {t['title']}")

        # Estrutura as pautas individuais
        pautas = build_micro_pautas(topics, chunks_list or [])

        # Gera sugestões de séries (10+ min)
        bundles = build_suggested_bundles(pautas, min_minutes=10)

        # Gera ganchos virais
        hooks = _build_viral_hooks(topics, chunks_list or [])

        return {
            "pautas": pautas,
            "bundles": bundles,
            "cortes": bundles if mode == "blocos" else (hooks if mode == "ganchos" else pautas),
            "raw": "\n".join(log),
            "error": None
        }

    except Exception as exc:
        return {
            "pautas": [],
            "bundles": [],
            "cortes": [],
            "raw": "\n".join(log) if log else str(exc),
            "error": str(exc)
        }
