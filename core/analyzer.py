"""
analyzer.py — Inteligência Temática Semântica & Encadeamento de Blocos

Estratégia de Inteligência:
1. Extração Semântica Ancorada:
   A IA local (Llama 3 / Mistral / Qwen) analisa a transcrição e identifica
   os momentos reais onde cada assunto/pergunta começa no vídeo.

2. Regra de Negócio de Blocos para YouTube (>= 10 min) + Encadeamento com Gancho:
   - Se um assunto durar >= 10 min, o corte conclui no fechamento natural do assunto.
   - Se um assunto durar < 10 min (ex: 6 min), o corte "invade" o início do próximo
     assunto até completar no mínimo 10 minutos. O trecho final serve como GANCHO/CLIFFHANGER
     para o próximo vídeo, criando uma esteira de múltiplos vídeos interligados (Parte 1, Parte 2, etc.).

3. Ganchos Virais (< 60s) para Shorts/TikTok:
   - Extrai declarações de alto impacto ancoradas no timestamp real da fala.
"""

import ollama
import re


# ──────────────────────────────────────────────────────────────────────────────
# Prompts Otimizados (Instruções em Inglês para Alta Obediência do Llama 3)
# ──────────────────────────────────────────────────────────────────────────────

SYS_MSG = (
    "You are an expert video editor and producer for YouTube podcasts. "
    "You identify semantic topic transitions accurately. "
    "Respond with NO intro, NO outro, ONLY the numbered list."
)

PROMPT_TEMAS_BLOCOS = """\
Analyze the Portuguese transcript chunks below.
Each line has a timestamp prefix like [00:00:00 - 00:01:00].

TASK:
Identify the main topics/themes discussed in the conversation in chronological order.
For EACH topic:
1. Find the starting timestamp [HH:MM:SS] from the transcript where the discussion of that topic begins.
2. Provide a clear, descriptive title in Brazilian Portuguese.

FORMAT RULES:
- One topic per line.
- Strict format: 1. [HH:MM:SS] Topic title in Portuguese
- Do NOT include markdown code blocks, intros, or conversational text.

Example output:
1. [00:00:00] Debate sobre Justiça do Trabalho e Reforma do Estado
2. [00:06:12] Caso Banco Master e verbas para cinema
3. [00:14:05] Crise no Supremo Tribunal Federal e Maioridade Penal

Transcript:
{transcricao}
"""

PROMPT_TEMAS_GANCHOS = """\
Analyze the Portuguese transcript chunks below.
Each line has a timestamp prefix like [00:00:00 - 00:01:00].

TASK:
Find 3 to 6 high-impact moments (max 60 seconds each) suitable for YouTube Shorts or TikTok.
Look for controversial statements, strong quotes, heated exchanges, or punchlines.

FORMAT RULES:
- One hook per line.
- Strict format: 1. [HH:MM:SS] "Punchy quote or viral hook title in Portuguese"
- Do NOT include intros or conversational text.

Example output:
1. [00:02:15] Declaração contundente sobre o custo da Justiça
2. [00:08:40] "Não podemos tratar o Supremo como Deus ex-machina"
3. [00:17:45] Denúncia sobre os gastos do Banco Master

Transcript:
{transcricao}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Utilitários de Tempo e Parsing
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


def _clean_ai_title(title: str) -> str:
    """Remove ruídos e introduções do título gerado pela IA."""
    title = title.strip()
    # Remove aspas extras
    title = re.sub(r'^["\'“]+|["\'”]+$', '', title).strip()
    # Remove prefixos conversacionais caso a IA tenha incluído
    prefixes = [
        r'^Entendi[,\.\s]*',
        r'^Aqui vai[,\.\s]*',
        r'^Aqui est[aã]o?[,\.\s]*',
        r'^T[íi]tulo:\s*',
        r'^Assunto:\s*',
        r'^Tema:\s*'
    ]
    for p in prefixes:
        title = re.sub(p, '', title, flags=re.IGNORECASE).strip()
    return title


def _parse_topics_from_text(text: str) -> list[dict]:
    """
    Extrai lista de tópicos no formato:
      1. [00:05:00] Título do assunto
    """
    topics = []
    # Regex flexível para capturar [HH:MM:SS] ou HH:MM:SS seguido do título
    pattern = re.compile(
        r'(?:^\s*\d+[\.\)]\s*)?'                    # '1.' opcional
        r'[\[\(]?(\d{1,2}:\d{2}(?::\d{2})?)[\]\)]?' # Timestamp [00:00:00] ou 00:00:00
        r'[\s:-]+'                                  # Separador
        r'(.+)',                                    # Título
        re.MULTILINE
    )

    for match in pattern.finditer(text):
        time_raw = match.group(1).strip()
        title_raw = match.group(2).strip()

        # Garante HH:MM:SS
        parts = time_raw.split(':')
        if len(parts) == 2:
            time_raw = f"00:{time_raw}"

        title_cleaned = _clean_ai_title(title_raw)
        if title_cleaned and len(title_cleaned) > 2:
            # Ignora linhas que são claramente instrução do prompt
            if "Example format" in title_cleaned or "Transcript" in title_cleaned:
                continue
            topics.append({
                "start_str": time_raw,
                "start_s": parse_time_str_to_seconds(time_raw),
                "title": title_cleaned
            })

    return topics


# ──────────────────────────────────────────────────────────────────────────────
# Lógica de Encadeamento Semântico e Multi-Vídeos (>= 10 min)
# ──────────────────────────────────────────────────────────────────────────────

def _build_semantic_blocks(topics: list[dict], chunks_list: list,
                           min_minutes: int = 10) -> list[dict]:
    """
    Constrói blocos de no mínimo `min_minutes` (10 min).
    Se o tópico por si só durar menos que 10 min, invade o próximo tópico,
    criando um gancho temático e gerando uma série de vídeos interligados.
    """
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']
    min_duration_s = min_minutes * 60  # 600 segundos

    # Se a IA não achou tópicos específicos, usamos o início como tópico base
    if not topics:
        topics = [{"start_str": "00:00:00", "start_s": 0.0, "title": "Debate Principal"}]

    # Ordena tópicos por timestamp
    topics = sorted(topics, key=lambda x: x["start_s"])

    blocks = []
    num_topics = len(topics)

    for i, topic in enumerate(topics):
        start_s = topic["start_s"]
        
        # Garante que o start não seja além do vídeo
        if start_s >= total_video_duration:
            break

        # O próximo tópico teoricamente começa em:
        if i + 1 < num_topics:
            next_topic_start = topics[i + 1]["start_s"]
            next_topic_title = topics[i + 1]["title"]
        else:
            next_topic_start = total_video_duration
            next_topic_title = None

        topic_natural_duration = next_topic_start - start_s

        # Regra de 10 min:
        if topic_natural_duration >= min_duration_s:
            # Assunto longo: termina naturalmente no final do assunto
            end_s = min(next_topic_start, total_video_duration)
            title = f"{topic['title']}"
            has_hook = False
            notes = f"Duração: {(end_s - start_s)/60:.1f} min. Cobre integralmente o tema '{topic['title']}'."
        else:
            # Assunto curto (< 10 min): "Invade" o próximo assunto para alcançar >= 10 min
            target_end_s = start_s + min_duration_s
            end_s = min(target_end_s, total_video_duration)
            
            # Se invadiu o próximo assunto, adicionamos a indicação de gancho
            if next_topic_title and end_s > next_topic_start:
                has_hook = True
                title = f"{topic['title']} (com Gancho p/ {next_topic_title})"
                notes = (
                    f"Duração: {(end_s - start_s)/60:.1f} min. "
                    f"Cobre o tema '{topic['title']}' e introduz o início de '{next_topic_title}' como Gancho."
                )
            else:
                has_hook = False
                title = f"{topic['title']}"
                notes = f"Duração: {(end_s - start_s)/60:.1f} min."

        # Garante que não crie blocos duplicados de tempo idêntico
        start_fmt = format_seconds_to_time(start_s)
        end_fmt = format_seconds_to_time(end_s)

        if not blocks or blocks[-1]["start"] != start_fmt:
            blocks.append({
                "start": start_fmt,
                "end": end_fmt,
                "title": title,
                "has_hook": has_hook,
                "notes": notes,
                "series_label": f"Vídeo {len(blocks) + 1}"
            })

    # Caso especial: se o vídeo inteiro tiver menos que 10 min, gera um bloco único completo
    if not blocks:
        blocks.append({
            "start": "00:00:00",
            "end": format_seconds_to_time(total_video_duration),
            "title": topics[0]["title"] if topics else "Corte Completo",
            "has_hook": False,
            "notes": f"Duração total: {total_video_duration/60:.1f} min.",
            "series_label": "Vídeo 1"
        })

    return blocks


def _build_viral_hooks(topics: list[dict], chunks_list: list) -> list[dict]:
    """
    Constrói cortes virais curtos (30s a 60s) para Shorts/TikTok.
    """
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']
    hooks = []

    for i, item in enumerate(topics):
        start_s = item["start_s"]
        if start_s >= total_video_duration:
            continue

        # Duração ideal para Shorts: 45 a 60 segundos
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
# Função Principal (API da Inteligência Temática)
# ──────────────────────────────────────────────────────────────────────────────

def analyze_transcript(chunked_transcript: str, mode: str = "blocos",
                       model: str = "llama3",
                       chunks_list: list = None) -> dict:
    """
    Executa a análise temática no Ollama e aplica a regra de encadeamento semântico.
    """
    log = []

    try:
        prompt = PROMPT_TEMAS_BLOCOS if mode == "blocos" else PROMPT_TEMAS_GANCHOS

        response = ollama.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': SYS_MSG},
                {'role': 'user', 'content': prompt.format(transcricao=chunked_transcript)},
            ]
        )

        raw_content = response['message']['content']
        log.append(f"=== RESPOSTA BRUTA DO MODELO ({model}) ===\n{raw_content}")

        # Extrai tópicos ancorados nos timestamps
        topics = _parse_topics_from_text(raw_content)

        if not topics:
            log.append("\n[Aviso] Nenhum formato numerado explícito encontrado. Aplicando extração flexível...")
            # Tenta pegar qualquer timestamp no texto
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

        log.append(f"\n=== TÓPICOS IDENTIFICADOS ({len(topics)}) ===")
        for t in topics:
            log.append(f"  • [{t['start_str']}] {t['title']}")

        # Aplica a inteligência de montagem dos cortes:
        if mode == "blocos":
            cortes = _build_semantic_blocks(topics, chunks_list or [], min_minutes=10)
        else:
            cortes = _build_viral_hooks(topics, chunks_list or [])

        log.append(f"\n=== CORTES SEMÂNTICOS GERADOS ({len(cortes)}) ===")
        for c in cortes:
            log.append(f"  • {c.get('series_label', '')}: [{c['start']} - {c['end']}] {c['title']}")

        return {
            "cortes": cortes,
            "raw": "\n".join(log),
            "error": None
        }

    except Exception as exc:
        return {
            "cortes": [],
            "raw": "\n".join(log) if log else str(exc),
            "error": str(exc)
        }
