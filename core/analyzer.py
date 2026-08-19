"""
analyzer.py — Inteligência Temática: Pautas, Compositor de Micro-Assuntos e Blocos

Estratégia de Inteligência Robusta:
1. Mapeamento Completo de Perguntas & Micro-Assuntos:
   - Identifica cada pergunta feita pelos jornalistas ao longo de toda a entrevista.
   - Suporta múltiplos formatos de resposta da IA (com timestamps, em markdown, ou lista pura).
   - Sistema Híbrido: Se a IA omitir timestamps em algum item, o algoritmo localiza
     automaticamente o minuto exato na transcrição através de casamento semântico de termos.

2. Compositor Interativo de Cortes:
   - Permite selecionar livremente múltiplos micro-assuntos e calcular o tempo total para 10+ min.

3. Agrupador de Séries Automáticas:
   - Monta séries encadeadas prontas de 10+ minutos para o YouTube.
"""

import ollama
import re


# ──────────────────────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────────────────────

SYS_MSG = (
    "You are an expert video editor and podcast producer. "
    "You identify every question and topic change in interviews and political debates. "
    "Respond ONLY with the numbered list. No intros, no conversational text."
)

PROMPT_MICRO_PAUTAS = """\
Analyze the Portuguese interview/debate transcript chunks below.
Different journalists ask multiple different questions throughout the video.

TASK:
Identify ALL distinct questions, topic changes, or debate points discussed in chronological order.
Aim to list between 5 to 15 individual topics covering the ENTIRE duration of the video.

For EACH question/topic:
1. Find the starting timestamp [HH:MM:SS] from the transcript chunk.
2. Provide a clear and concise title in Brazilian Portuguese describing what is being asked or discussed.

FORMAT RULES:
- One topic per line.
- Strict format: 1. [HH:MM:SS] Topic or Question Title in Portuguese
- Do NOT include markdown code blocks, intros, or summaries.

Example output:
1. [00:00:00] Pergunta sobre extinção da Justiça do Trabalho
2. [00:03:15] Escolha do superministro da reforma do Estado
3. [00:06:40] Denúncia sobre Banco Master e recursos cinematográficos
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
    # Remove aspas e markdown
    title = re.sub(r'[*_`"\'“”]', '', title).strip()
    # Remove números de lista no início (ex: '1.', '1 -', '01)')
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


def _find_best_chunk_start(topic_text: str, chunks_list: list) -> float:
    """
    Localiza o timestamp de início mais provável de um tópico na transcrição
    através de correspondência de termos-chave (busca semântica local).
    """
    if not chunks_list:
        return 0.0

    stop_words = {'para', 'sobre', 'com', 'que', 'dos', 'das', 'uma', 'como', 'mais', 'pelo', 'pela', 'qual', 'quando', 'pergunta', 'debate'}
    words = [w.lower() for w in re.findall(r'\b\w{4,}\b', topic_text) if w.lower() not in stop_words]
    
    if not words:
        return 0.0

    best_idx = 0
    best_score = 0

    for idx, c in enumerate(chunks_list):
        c_text = c['text'].lower()
        score = sum(1 for w in words if w in c_text)
        if score > best_score:
            best_score = score
            best_idx = idx

    return chunks_list[best_idx]['start']


def _extract_topics_resilient(raw_text: str, chunks_list: list) -> list[dict]:
    """
    Extrai lista de tópicos de forma resiliente a qualquer formato de resposta do LLM:
    1. Procura linhas com timestamps em qualquer parte da linha.
    2. Para linhas de lista sem timestamp, localiza o chunk pelo texto.
    """
    topics = []
    time_regex = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)')

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue

        # Ignora cabeçalhos óbvios
        if "example output" in line.lower() or "transcript" in line.lower():
            continue

        # Caso A: Linha possui timestamp explícito (ex: '1. [00:03:45] Título' ou '**00:03:45** Título')
        t_match = time_regex.search(line)
        if t_match:
            time_raw = t_match.group(1).strip()
            # Garante formato HH:MM:SS
            if len(time_raw.split(':')) == 2:
                time_raw = f"00:{time_raw}"

            # Remove o timestamp da linha para sobrar apenas o título
            title_part = re.sub(r'\[?\d{1,2}:\d{2}(?::\d{2})?\]?', '', line)
            title_clean = _clean_ai_title(title_part)

            if len(title_clean) > 3:
                topics.append({
                    "start_str": time_raw,
                    "start_s": parse_time_str_to_seconds(time_raw),
                    "title": title_clean
                })
        else:
            # Caso B: Linha é um item numerado ou com marcador de lista (ex: '1. Debate sobre STF')
            if re.match(r'^\s*(?:\d+[\.\)]|[\*\-\•])\s+', line):
                title_clean = _clean_ai_title(line)
                if len(title_clean) > 3:
                    # Encontra o minuto na transcrição
                    start_s = _find_best_chunk_start(title_clean, chunks_list)
                    time_raw = format_seconds_to_time(start_s)
                    topics.append({
                        "start_str": time_raw,
                        "start_s": start_s,
                        "title": title_clean
                    })

    # Ordena por timestamp
    topics = sorted(topics, key=lambda x: x["start_s"])

    # Remove itens com mesmo timestamp ou títulos duplicados
    unique_topics = []
    seen_starts = set()
    for t in topics:
        if t["start_str"] not in seen_starts:
            seen_starts.add(t["start_str"])
            unique_topics.append(t)

    return unique_topics


# ──────────────────────────────────────────────────────────────────────────────
# Estruturação de Micro-Pautas
# ──────────────────────────────────────────────────────────────────────────────

def build_micro_pautas(topics: list[dict], chunks_list: list) -> list[dict]:
    """
    Estrutura a lista de micro-assuntos com início, fim e duração exata de cada um.
    """
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']

    if not topics:
        # Fallback inteligente: se a IA não retornou nada, gera pautas a partir dos chunks de áudio
        pautas = []
        for i, c in enumerate(chunks_list):
            pautas.append({
                "id": i + 1,
                "start": format_seconds_to_time(c['start']),
                "end": format_seconds_to_time(c['end']),
                "start_s": c['start'],
                "end_s": c['end'],
                "duration_s": c['end'] - c['start'],
                "duration_label": format_duration_human(c['end'] - c['start']),
                "title": f"Trecho {i + 1}: {c['text'][:60]}..."
            })
        return pautas

    # Garante cobertura desde o início
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
        
        # Ignora pautas ultracurtas (< 15s) exceto se for a única
        if duration_s < 15 and i + 1 < len(topics):
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
    Executa a identificação de pautas ou ganchos no Ollama com parsing resiliente.
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

        # Extração resiliente de tópicos
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
