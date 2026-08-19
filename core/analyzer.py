"""
analyzer.py — Inteligência Temática: Pautas, Compositor de Micro-Assuntos e Blocos

Estratégia de Inteligência:
1. Detecção de Micro-Assuntos / Pautas:
   Em entrevistas e podcasts dinâmicos, repórteres mudam de assunto a cada 1-4 minutos.
   O modelo identifica o início exato de cada pergunta/pauta.

2. Compositor de Cortes:
   Permite calcular a duração de cada pauta individualmente e somar micro-assuntos
   selecionados para compor cortes customizados de 10+ minutos para o YouTube.

3. Agrupador Inteligente de Séries (10+ min):
   Agrupa automaticamente sequências de pautas atingindo a meta de 10+ minutos
   com ganchos de continuidade.
"""

import ollama
import re


# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

SYS_MSG = (
    "You are an expert video editor and podcast producer. "
    "You identify individual interview questions, topics, and debate segments accurately. "
    "Respond ONLY with the numbered list. No intros, no conversational text."
)

PROMPT_MICRO_PAUTAS = """\
Analyze the Portuguese interview/debate transcript chunks below.
Identify EVERY individual question, topic shift, or distinct point raised in the conversation.

For EACH question/topic:
1. Find the exact timestamp [HH:MM:SS] where this question or new topic begins.
2. Provide a clear, descriptive title in Brazilian Portuguese.

FORMAT RULES:
- One topic per line.
- Strict format: 1. [HH:MM:SS] Topic or Question Title in Portuguese
- Do NOT include markdown code blocks, intros, or extra explanations.

Example output:
1. [00:00:00] Pergunta sobre extinção da Justiça do Trabalho
2. [00:03:45] Escolha do superministro da reforma do Estado
3. [00:06:12] Denúncia sobre Banco Master e recursos cinematográficos
4. [00:09:20] Propostas para reforma tributária e split payment
5. [00:14:05] Discussão sobre Supremo Tribunal Federal e maioridade penal
6. [00:17:45] Análise da política externa e relação com governo Trump

Transcript:
{transcricao}
"""

PROMPT_TEMAS_GANCHOS = """\
Analyze the Portuguese transcript chunks below.
Find 3 to 6 high-impact moments (max 60 seconds each) suitable for YouTube Shorts or TikTok.
Look for controversial statements, strong quotes, heated exchanges, or punchlines.

FORMAT RULES:
- One hook per line.
- Strict format: 1. [HH:MM:SS] "Punchy quote or viral hook title in Portuguese"

Example output:
1. [00:02:15] Declaração contundente sobre o custo da Justiça
2. [00:08:40] "Não podemos tratar o Supremo como Deus ex-machina"
3. [00:17:45] Denúncia sobre os gastos do Banco Master

Transcript:
{transcricao}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários
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
    """Remove ruídos e introduções do título gerado pela IA."""
    title = title.strip()
    title = re.sub(r'^["\'“]+|["\'”]+$', '', title).strip()
    prefixes = [
        r'^Entendi[,\.\s]*',
        r'^Aqui vai[,\.\s]*',
        r'^Aqui est[aã]o?[,\.\s]*',
        r'^T[íi]tulo:\s*',
        r'^Assunto:\s*',
        r'^Tema:\s*',
        r'^Pauta:\s*'
    ]
    for p in prefixes:
        title = re.sub(p, '', title, flags=re.IGNORECASE).strip()
    return title


def _parse_topics_from_text(text: str) -> list[dict]:
    """Extrai lista de tópicos no formato: 1. [00:05:00] Título do assunto."""
    topics = []
    pattern = re.compile(
        r'(?:^\s*\d+[\.\)]\s*)?'
        r'[\[\(]?(\d{1,2}:\d{2}(?::\d{2})?)[\]\)]?'
        r'[\s:-]+'
        r'(.+)',
        re.MULTILINE
    )

    for match in pattern.finditer(text):
        time_raw = match.group(1).strip()
        title_raw = match.group(2).strip()

        parts = time_raw.split(':')
        if len(parts) == 2:
            time_raw = f"00:{time_raw}"

        title_cleaned = _clean_ai_title(title_raw)
        if title_cleaned and len(title_cleaned) > 2:
            if "Example output" in title_cleaned or "Transcript" in title_cleaned:
                continue
            topics.append({
                "start_str": time_raw,
                "start_s": parse_time_str_to_seconds(time_raw),
                "title": title_cleaned
            })

    return topics


# ──────────────────────────────────────────────────────────────────────────────
# Extração e Estruturação de Micro-Pautas
# ──────────────────────────────────────────────────────────────────────────────

def build_micro_pautas(topics: list[dict], chunks_list: list) -> list[dict]:
    """
    Estrutura a lista de micro-assuntos com start, end e duração calculada.
    """
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']

    if not topics:
        topics = [{"start_str": "00:00:00", "start_s": 0.0, "title": "Início da conversa"}]

    # Ordena por timestamp
    topics = sorted(topics, key=lambda x: x["start_s"])

    # Se o primeiro tópico não começar em 0, adiciona introdução
    if topics[0]["start_s"] > 30.0:
        topics.insert(0, {
            "start_str": "00:00:00",
            "start_s": 0.0,
            "title": "Abertura / Apresentação Inicial"
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
        
        # Ignora pautas com menos de 10s (ruído)
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


# ──────────────────────────────────────────────────────────────────────────────
# Agrupamento Automático em Séries (10+ min)
# ──────────────────────────────────────────────────────────────────────────────

def build_suggested_bundles(pautas: list[dict], min_minutes: int = 10) -> list[dict]:
    """
    Agrupa automaticamente as pautas sequenciais para sugerir vídeos completos de 10+ min.
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
            # O próximo vídeo pode recomeçar da última pauta como gancho ou da próxima
            current_pautas = []
            current_duration = 0.0

    # Sobra final
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
    Identifica pautas, sugere blocos ou extrai ganchos virais.
    """
    log = []

    try:
        prompt = PROMPT_MICRO_PAUTAS if mode in ("pautas", "blocos") else PROMPT_TEMAS_GANCHOS

        response = ollama.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': SYS_MSG},
                {'role': 'user', 'content': prompt.format(transcricao=chunked_transcript)},
            ]
        )

        raw_content = response['message']['content']
        log.append(f"=== RESPOSTA DO MODELO ({model}) ===\n{raw_content}")

        topics = _parse_topics_from_text(raw_content)

        if not topics:
            log.append("\n[Aviso] Aplicando extração flexível...")
            for line in raw_content.splitlines():
                t_match = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', line)
                if t_match:
                    time_raw = t_match.group(1)
                    title_clean = _clean_ai_title(re.sub(r'[\d\.\:\-\[\]\(\)]', ' ', line).strip())
                    if len(title_clean) > 3:
                        topics.append({
                            "start_str": time_raw,
                            "start_s": parse_time_str_to_seconds(time_raw),
                            "title": title_clean
                        })

        log.append(f"\n=== PAUTAS IDENTIFICADAS ({len(topics)}) ===")
        for t in topics:
            log.append(f"  • [{t['start_str']}] {t['title']}")

        # Estrutura as pautas individuais
        pautas = build_micro_pautas(topics, chunks_list or [])

        # Gera sugestões de blocos agrupados de 10+ min
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
