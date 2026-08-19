"""
analyzer.py — Inteligência Temática via Ollama local

Estratégia de duas fases (mais confiável para modelos pequenos como llama3 8B):

  Fase 1 — Identificação de temas (resposta em texto livre, sem formatação obrigatória):
    Perguntamos ao modelo APENAS: "Quais são os principais temas do vídeo?"
    O modelo responde livremente em PT-BR.

  Fase 2 — Localização de timestamps (resposta ultra-simples, uma linha por tema):
    Para cada tema identificado, perguntamos:
    "Em que minuto começa e termina o tema X? Responda: START=HH:MM:SS END=HH:MM:SS"
    Fazemos regex em cima disso.

Se a fase 2 falhar para algum tema, usamos heurística sobre os chunks já conhecidos.
"""

import ollama
import re


# ──────────────────────────────────────────────────────────────────────────────
# Prompts — Mantidos em inglês para maximizar obediência do llama3
# ──────────────────────────────────────────────────────────────────────────────

SYS_TEMAS = (
    "You are an expert video editor. "
    "Answer concisely in Brazilian Portuguese."
)

PROMPT_TEMAS_BLOCOS = """\
Read the transcript below (Brazilian Portuguese political debate).
List the 3 to 5 main topics discussed, in chronological order.
Each topic is discussed for approximately 8 to 12 minutes.
Write ONLY a numbered list of topic names. No timestamps. No explanations.

Example format:
1. Reforma do sistema judiciário
2. Split payment e reforma tributária
3. Intervenção dos EUA nas eleições

Transcript:
{transcricao}
"""

PROMPT_TEMAS_GANCHOS = """\
Read the transcript below (Brazilian Portuguese political debate).
List the 4 to 6 most impactful and controversial moments (max 60 seconds each).
Write ONLY a numbered list of short, punchy names for each moment. No timestamps. No explanations.

Example format:
1. "Se resistiu, morreu" — declaração polêmica sobre segurança
2. STF como obstáculo à república
3. Crítica ao custo da Justiça do Trabalho

Transcript:
{transcricao}
"""

SYS_TEMPO = (
    "You are a precise timestamp extractor. "
    "Reply with exactly two tokens: START=HH:MM:SS END=HH:MM:SS. Nothing else."
)

PROMPT_TEMPO = """\
In the transcript below, find where the following topic starts and ends.
Topic: "{tema}"

Reply with ONLY: START=HH:MM:SS END=HH:MM:SS

Transcript (first and last lines shown):
{cabeca}
...
{cauda}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

TIME_RE = re.compile(r'\b(\d{1,2}:\d{2}:\d{2})\b')
LIST_RE = re.compile(r'^\s*\d+[\.\)]\s*(.+)', re.MULTILINE)


def _parse_tema_list(text: str) -> list[str]:
    """Extrai itens de uma lista numerada '1. Tema ...'"""
    matches = LIST_RE.findall(text)
    return [m.strip().strip('"').strip("'") for m in matches if m.strip()]


def _parse_start_end(text: str):
    """
    Extrai START e END de respostas como:
      'START=00:05:00 END=00:15:30'
    Retorna (start_str, end_str) ou (None, None).
    """
    s = re.search(r'START\s*=\s*(\d{1,2}:\d{2}:\d{2})', text, re.IGNORECASE)
    e = re.search(r'END\s*=\s*(\d{1,2}:\d{2}:\d{2})', text, re.IGNORECASE)
    if s and e:
        return s.group(1), e.group(1)

    # Fallback: pega os dois primeiros timestamps HH:MM:SS encontrados
    times = TIME_RE.findall(text)
    if len(times) >= 2:
        return times[0], times[1]

    return None, None


def _chunk_head_tail(chunked_transcript: str, head_lines=5, tail_lines=5) -> tuple[str, str]:
    """Retorna as primeiras e últimas linhas do transcript chunked."""
    lines = chunked_transcript.strip().split('\n')
    head = '\n'.join(lines[:head_lines])
    tail = '\n'.join(lines[-tail_lines:])
    return head, tail


def _heuristic_timestamps(tema_idx: int, total_temas: int,
                           chunks_list: list) -> tuple[str, str]:
    """
    Quando a IA não retorna timestamp, divide o vídeo uniformemente.
    chunks_list: lista de dicts {'start': float, 'end': float, 'text': str}
    """
    if not chunks_list:
        return "00:00:00", "00:10:00"

    total_chunks = len(chunks_list)
    per_block = max(1, total_chunks // total_temas)
    i_start = tema_idx * per_block
    i_end   = min(i_start + per_block - 1, total_chunks - 1)

    def fmt(secs):
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    return fmt(chunks_list[i_start]['start']), fmt(chunks_list[i_end]['end'])


# ──────────────────────────────────────────────────────────────────────────────
# Função principal
# ──────────────────────────────────────────────────────────────────────────────

def analyze_transcript(chunked_transcript: str, mode: str = "blocos",
                       model: str = "llama3",
                       chunks_list: list = None) -> dict:
    """
    Analisa a transcrição em duas fases:
      1. Identificar temas (texto livre)
      2. Localizar timestamps de cada tema

    Parâmetros:
      chunked_transcript : texto agrupado em blocos de 1 min '[HH:MM:SS - HH:MM:SS] ...'
      mode               : 'blocos' (8-12 min) ou 'ganchos' (< 60s)
      model              : nome do modelo Ollama
      chunks_list        : lista de dicts {start, end, text} — usada para heurística
    """
    log = []
    cortes = []

    try:
        # ── Fase 1: identificar temas ──────────────────────────────────────
        prompt_temas = (PROMPT_TEMAS_BLOCOS if mode == "blocos"
                        else PROMPT_TEMAS_GANCHOS)

        resp1 = ollama.chat(
            model=model,
            messages=[
                {'role': 'system', 'content': SYS_TEMAS},
                {'role': 'user',   'content': prompt_temas.format(
                    transcricao=chunked_transcript)},
            ]
        )
        raw_temas = resp1['message']['content']
        log.append(f"=== FASE 1 — Temas identificados ===\n{raw_temas}")

        temas = _parse_tema_list(raw_temas)
        if not temas:
            # Se não encontrou lista numerada, tenta dividir por linhas
            temas = [l.strip() for l in raw_temas.strip().splitlines()
                     if l.strip() and len(l.strip()) > 3][:6]

        if not temas:
            return {
                "cortes": [],
                "raw": log[-1],
                "error": "A IA não retornou lista de temas."
            }

        # ── Fase 2: localizar timestamps de cada tema ──────────────────────
        head, tail = _chunk_head_tail(chunked_transcript)

        for idx, tema in enumerate(temas):
            try:
                resp2 = ollama.chat(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': SYS_TEMPO},
                        {'role': 'user',   'content': PROMPT_TEMPO.format(
                            tema=tema,
                            cabeca=head,
                            cauda=tail
                        )},
                    ]
                )
                raw_tempo = resp2['message']['content']
                log.append(f"\n=== FASE 2 — Tema {idx+1}: {tema} ===\n{raw_tempo}")

                start, end = _parse_start_end(raw_tempo)

            except Exception as e2:
                start, end = None, None
                log.append(f"\n=== FASE 2 — Tema {idx+1} ERRO: {e2} ===")

            # Usa heurística se a IA não retornou timestamps válidos
            if not start or not end:
                start, end = _heuristic_timestamps(idx, len(temas), chunks_list or [])
                log.append(f"  → Heurística aplicada: {start} - {end}")

            cortes.append({'start': start, 'end': end, 'title': tema})

        return {"cortes": cortes, "raw": "\n".join(log), "error": None}

    except Exception as exc:
        return {"cortes": [], "raw": "\n".join(log), "error": str(exc)}
