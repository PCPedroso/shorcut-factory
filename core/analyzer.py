"""
analyzer.py — Inteligência Temática Multi-Estratégia:
1. 🎙️ Modo Entrevista / Sabatina (Detecção Semântica Exata de Perguntas e Respostas [INÍCIO -> FIM])
2. 🧠 Modo Temático / Monólogo / Aula (Detecção de Mudança Semântica de Assunto)
3. 🔥 Modo Ganchos Virais (Shorts/Reels 30s-60s)
"""

import os
import re
import json
import ollama


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
    """Retorna duração amigável como '1m 27s' ou '12m 10s'."""
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


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 1: 🎙️ Entrevistas & Sabatinas (Q&A Turn Boundary Detection)
# ──────────────────────────────────────────────────────────────────────────────

def detect_qa_pautas(segments: list, model: str = "llama3") -> list:
    """
    Detecta perguntas de jornalistas/apresentadores e respostas completas de entrevistados.
    Gera pautas com limites precisos de INÍCIO e FIM no segundo exato.
    """
    if not segments:
        return []

    question_starts = []
    # 1. Início do vídeo (Abertura)
    question_starts.append({"start_s": 0.0, "is_opening": True})

    for i, s in enumerate(segments):
        txt = s.get("text", "").strip()
        t = s.get("start", 0.0)

        is_new_speaker = ">>" in txt
        is_q_pattern = bool(re.search(
            r"(candidato|jornalista|primeira pergunta|gostaria de|o senhor disse|como defender|que que é|já que o senhor|dá tempo da gente|muitíssimo obrigado|boa noite)",
            txt,
            re.IGNORECASE
        ))

        # Detecta a 1ª pergunta formal do entrevistador (geralmente após a vinheta/apresentação ~60s-90s)
        if is_new_speaker and t >= 60.0 and len(question_starts) == 1:
            question_starts.append({"start_s": t, "is_opening": False})
            continue

        # Perguntas subsequentes (com distância mínima de 30 segundos)
        if is_new_speaker and is_q_pattern and (t - question_starts[-1]["start_s"] >= 30.0):
            question_starts.append({"start_s": t, "is_opening": False})

    total_dur = segments[-1]["end"]
    pautas = []

    for idx, q in enumerate(question_starts):
        st_s = q["start_s"]
        if idx + 1 < len(question_starts):
            next_st = question_starts[idx + 1]["start_s"]
            prev_seg = next((s for s in reversed(segments) if s["end"] <= next_st + 1.0), None)
            end_s = prev_seg["end"] if prev_seg else next_st
        else:
            end_s = total_dur

        dur_s = max(0, end_s - st_s)
        p_texts = [s["text"].replace(">>", "").strip() for s in segments if st_s <= s["start"] <= end_s]
        p_text = " ".join(p_texts)

        # Determina título base
        if q.get("is_opening"):
            title = "Abertura e Apresentação da Sabatina"
        elif "muitíssimo obrigado" in p_text.lower() and dur_s < 30:
            title = "Encerramento e Agradecimentos Finais"
        else:
            # Pega a frase da pergunta
            first_sentence = p_text.split('.')[0] if '.' in p_text else p_text[:90]
            title = first_sentence[:80].strip()

        pautas.append({
            "id": len(pautas) + 1,
            "start": format_seconds_to_time(st_s),
            "end": format_seconds_to_time(end_s),
            "start_s": st_s,
            "end_s": end_s,
            "duration_s": dur_s,
            "duration_label": format_duration_human(dur_s),
            "title": title,
            "text_snippet": p_text[:160]
        })

    # Otimiza títulos com IA via Ollama em lote rápido (se disponível)
    pautas = _refine_pauta_titles_with_ai(pautas, model=model)
    return pautas


def _refine_pauta_titles_with_ai(pautas: list, model: str = "llama3") -> list:
    """Refina os títulos das pautas usando a IA para deixá-los curtos, jornalísticos e atrativos."""
    if not pautas or len(pautas) <= 2:
        return pautas

    try:
        items_to_title = []
        for p in pautas:
            if "Abertura" not in p["title"] and "Encerramento" not in p["title"]:
                items_to_title.append(f"Pauta {p['id']}: {p['text_snippet']}")

        if not items_to_title:
            return pautas

        prompt = f"""Você é um editor sênior de jornalismo.
Crie um título curto, objetivo e jornalístico (4 a 8 palavras) para cada pauta da entrevista abaixo.

PAUTAS:
{chr(10).join(items_to_title)}

REGRAS:
1. Responda ESTRITAMENTE no formato: Pauta X: Título do assunto
2. Não adicione explicações ou notas.
"""
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2}
        )
        content = response["message"]["content"]

        for line in content.splitlines():
            line = line.strip()
            match = re.match(r'Pauta\s*(\d+)[\s:]+(.+)', line, re.IGNORECASE)
            if match:
                p_id = int(match.group(1))
                new_title = _clean_ai_title(match.group(2))
                for p in pautas:
                    if p["id"] == p_id and len(new_title) > 4:
                        p["title"] = new_title
                        break
    except Exception:
        pass

    return pautas


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia 2: 🧠 Modo Temático / Monólogos / Aulas (Mudança Semântica)
# ──────────────────────────────────────────────────────────────────────────────

def detect_semantic_topics(chunks_list: list, model: str = "llama3") -> list:
    """
    Identifica tópicos e mudanças semânticas de raciocínio para vídeos com 1 orador único.
    """
    if not chunks_list:
        return []

    lines = []
    for c in chunks_list:
        t_str = format_seconds_to_time(c['start'])
        snippet = c['text'].strip()[:200].replace('\n', ' ')
        lines.append(f"[{t_str}] {snippet}...")

    concise_text = "\n".join(lines)

    prompt = f"""Analise os trechos do vídeo abaixo.
Identifique os principais blocos temáticos ou mudanças de assunto.

TRANSCRIÇÃO:
{concise_text}

REGRAS:
1. Responda em Português no formato: 1. [HH:MM:SS] Título do assunto
2. Apenas a lista numerada.
"""
    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2}
        )
        raw_text = response['message']['content']
        topics = _extract_topics_resilient(raw_text, chunks_list)
        return build_micro_pautas(topics, chunks_list)
    except Exception:
        return []


def _extract_topics_resilient(raw_text: str, chunks_list: list) -> list:
    topics = []
    time_regex = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)')

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or len(line) < 4:
            continue
        if any(h in line.lower() for h in ["example", "transcript", "aqui estão", "observações"]):
            continue

        is_numbered = bool(re.match(r'^\s*\d+[\.\)\-:]\s+', line))
        t_match = time_regex.search(line)

        if is_numbered or t_match:
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
    unique = []
    seen = set()
    for t in topics:
        if t["start_str"] not in seen:
            seen.add(t["start_str"])
            unique.append(t)
    return unique


def build_micro_pautas(topics: list, chunks_list: list) -> list:
    if not chunks_list:
        return []

    total_video_duration = chunks_list[-1]['end']
    if not topics:
        return []

    if topics[0]["start_s"] > 30.0:
        topics.insert(0, {
            "start_str": "00:00:00",
            "start_s": 0.0,
            "title": "Abertura e Introdução"
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


# ──────────────────────────────────────────────────────────────────────────────
# Sugestões de Séries (10+ min) e Ganchos Virais (Shorts)
# ──────────────────────────────────────────────────────────────────────────────

def build_suggested_bundles(pautas: list, min_minutes: int = 10) -> list:
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


def build_golden_rule_micro_cuts(pautas: list, segments: list) -> list:
    """
    Gera micro-cortes para Shorts/Reels/TikTok aplicando as 6 Regras de Ouro Editoriais:
    1. Clean Entry: Ponto de entrada limpo no início da fala/pergunta com respiro de áudio.
    2. Clean Exit: Fechamento completo da oração com respiro, sem vazamento da próxima pauta.
    3. Autonomia Semântica: Compreensão autônoma no feed sem necessidade de contexto externo.
    4. Tipologia Clara: Classifica em Q&A Completo, Declaração/Punchline ou Debate/Réplica.
    5. Anti-Vazamento: Isolamento rígido dos limites de assunto.
    6. Retenção Ótima: Janela temporal calibrada entre 20s e 75s.
    """
    if not pautas:
        return []

    micro_cuts = []

    for p in pautas:
        # Pula vinhetas de abertura e encerramento
        if "Abertura" in p["title"] or "Encerramento" in p["title"]:
            continue

        dur = p["duration_s"]

        # Tipo A: Pergunta & Resposta Completa (Q&A Unit) [20s a 80s]
        if 20.0 <= dur <= 85.0:
            micro_cuts.append({
                "type": "🏷️ [Q&A] Pergunta & Resposta Completa",
                "start": p["start"],
                "end": p["end"],
                "start_s": p["start_s"],
                "end_s": p["end_s"],
                "duration_s": dur,
                "duration_label": format_duration_human(dur),
                "title": p["title"],
                "notes": "Pergunta do entrevistador e resposta integral do entrevistado com raciocínio 100% fechado.",
                "snippet": p.get("text_snippet", "")
            })

        # Tipo B: Declaração / Tese de Impacto (Punchline) para pautas longas (> 85s)
        elif dur > 85.0 and segments:
            p_segs = [s for s in segments if p["start_s"] <= s.get("start", 0) <= p["end_s"]]
            if len(p_segs) >= 4:
                # Procura a resposta do entrevistado (após a pergunta inicial)
                ans_start_seg = next((s for s in p_segs if ">>" in s.get("text", "") and s["start"] > p["start_s"] + 8), None)
                cut_start = ans_start_seg["start"] if ans_start_seg else p["start_s"] + 15.0

                # Busca o melhor fechamento de oração entre 30s e 70s
                potential_ends = [s for s in p_segs if cut_start + 25.0 <= s["end"] <= cut_start + 70.0 and s.get("text", "").strip().endswith(('.', '!'))]
                if potential_ends:
                    cut_end = potential_ends[-1]["end"]
                else:
                    cut_end = min(p["end_s"], cut_start + 55.0)

                cut_dur = cut_end - cut_start
                if cut_dur >= 20.0:
                    micro_cuts.append({
                        "type": "🏷️ [Punchline] Declaração / Tese de Impacto",
                        "start": format_seconds_to_time(cut_start),
                        "end": format_seconds_to_time(cut_end),
                        "start_s": cut_start,
                        "end_s": cut_end,
                        "duration_s": cut_dur,
                        "duration_label": format_duration_human(cut_dur),
                        "title": f"Tese: {p['title']}",
                        "notes": "Declaração contundente e autônoma do entrevistado com início e fim de raciocínio.",
                        "snippet": " ".join(s.get("text", "").replace(">>", "").strip() for s in p_segs if cut_start <= s["start"] <= cut_end)[:140]
                    })

    # Fallback caso não haja pautas de Q&A específicas
    if not micro_cuts:
        for p in pautas:
            if "Abertura" not in p["title"] and "Encerramento" not in p["title"]:
                dur = min(p["duration_s"], 55.0)
                end_s = p["start_s"] + dur
                micro_cuts.append({
                    "type": "🏷️ [Short] Momento de Destaque",
                    "start": p["start"],
                    "end": format_seconds_to_time(end_s),
                    "start_s": p["start_s"],
                    "end_s": end_s,
                    "duration_s": dur,
                    "duration_label": format_duration_human(dur),
                    "title": p["title"],
                    "notes": "Trecho destacado com duração otimizada para Shorts/Reels.",
                    "snippet": p.get("text_snippet", "")
                })

    return micro_cuts


# ──────────────────────────────────────────────────────────────────────────────
# API Principal
# ──────────────────────────────────────────────────────────────────────────────

def analyze_transcript(
    chunked_transcript: str = "",
    mode: str = "pautas",
    model: str = "llama3",
    chunks_list: list = None,
    segments: list = None,
    strategy: str = "qa_interview"
) -> dict:
    """
    Executa a identificação de pautas ou ganchos adaptando-se ao tipo de vídeo.
    
    Estratégias:
    - 'qa_interview': Entrevistas, Sabatinas e Podcasts (Perguntas & Respostas Exatas).
    - 'semantic_topics': Aulas, Monólogos e Vlogs (Mudança de Assunto).
    """
    try:
        if strategy == "qa_interview" and segments:
            pautas = detect_qa_pautas(segments, model=model)
        else:
            pautas = detect_semantic_topics(chunks_list, model=model)

        bundles = build_suggested_bundles(pautas, min_minutes=10)
        micro_cuts = build_golden_rule_micro_cuts(pautas, segments)

        return {
            "pautas": pautas,
            "bundles": bundles,
            "micro_cuts": micro_cuts,
            "cortes": bundles if mode == "blocos" else (micro_cuts if mode == "ganchos" else pautas),
            "raw": f"Mapeadas {len(pautas)} pautas e {len(micro_cuts)} micro-cortes sob as 6 Regras de Ouro.",
            "error": None
        }

    except Exception as exc:
        return {
            "pautas": [],
            "bundles": [],
            "micro_cuts": [],
            "cortes": [],
            "raw": str(exc),
            "error": str(exc)
        }


# ──────────────────────────────────────────────────────────────────────────────
# Geração de Metadados Virais para Cortes Individuais (Kit de Publicação)
# ──────────────────────────────────────────────────────────────────────────────

def generate_viral_cut_metadata(transcript_snippet: str, model: str = "llama3") -> dict:
    """
    Analisa a transcrição real do trecho do corte e gera um kit de publicação contextual e não-genérico:
    - Título principal magnético com alto CTR citando o fato real
    - 2 títulos alternativos (foco na declaração forte / foco na pergunta ou confronto)
    - Descrição persuasiva detalhada contextualizando o que foi dito com CTA
    - Hashtags e tags de SEO específicas ao tema abordado
    """
    snippet_clean = transcript_snippet.strip()
    if not snippet_clean:
        return {
            "titulo_principal": "Declaração em Destaque",
            "titulos_alternativos": [],
            "descricao": "Confira o trecho desta entrevista e compartilhe sua opinião nos comentários!",
            "hashtags": ["#shorts", "#viral", "#reels", "#tiktok", "#cortes"],
            "tags_seo": "cortes, viral, shorts, podcast, entrevista",
            "error": "Texto da transcrição vazio."
        }

    # Limita o tamanho do texto para o prompt se o corte for muito longo
    snippet_prompt = snippet_clean[:3500]

    prompt = f"""Você é um editor-chefe e estrategista de conteúdo viral de canais de cortes de notícias, podcasts e debates.
Analise a transcrição real abaixo e crie um pacote de publicação de alto impacto e jornalisticamente atraente em Português.

Transcrição do trecho do vídeo:
\"\"\"
{snippet_prompt}
\"\"\"

DIRETRIZES OBRIGATÓRIAS:
1. NUNCA use títulos genéricos como 'Corte Viral', 'Momento Imperdível' ou 'Declaração Forte'. O título DEVE citar o fato, pergunta ou declaração central real que aconteceu no trecho (ex: 'Como convencer eleitores de 60 anos? Candidato responde com franqueza').
2. Crie 1 título principal e 2 títulos alternativos com abordagens distintas (uma focada na declaração mais contundente, outra na pergunta/confronto).
3. A descrição deve contextualizar exatamente o que o entrevistado/personagem disse no trecho, citando o tema abordado e provocando o público com uma pergunta no final para gerar debate nos comentários.
4. As hashtags devem ser específicas ao tema abordado no vídeo (política, eleições, debate, nomes próprios citados) além de hashtags de formato (#shorts, #reels).

Responda ESTRITAMENTE em formato JSON com as seguintes chaves (sem texto introdutório ou markdown antes/depois):
{{
  "titulo_principal": "Título magnético baseado no fato real (máx 65 caracteres)",
  "titulos_alternativos": [
    "Opção 1 focada na resposta/frase de impacto",
    "Opção 2 focada na polêmica/pergunta"
  ],
  "descricao": "Texto de legenda persuasivo contextualizando o debate/declaração e chamando o público a opinar nos comentários.",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6"],
  "tags_seo": "palavra-chave 1, palavra-chave 2, palavra-chave 3, palavra-chave 4"
}}
"""

    # Resolve modelo (compatibilidade com tags :latest)
    try:
        models_res = ollama.list()
        avail = [m.model if hasattr(m, 'model') else m.get('name', '') for m in (models_res.models if hasattr(models_res, 'models') else models_res.get('models', []))]
        matched_model = model
        for a in avail:
            if a.startswith(model) or model.startswith(a.split(':')[0]):
                matched_model = a
                break
    except Exception:
        matched_model = model

    try:
        res = ollama.chat(
            model=matched_model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7}
        )
        raw_out = res.get("message", {}).get("content", "")

        # Tenta extrair JSON
        match = re.search(r'\{[\s\S]*\}', raw_out)
        if match:
            parsed = json.loads(match.group(0))
            return {
                "titulo_principal": _clean_ai_title(parsed.get("titulo_principal", "Momento em Destaque")),
                "titulos_alternativos": [_clean_ai_title(t) for t in parsed.get("titulos_alternativos", []) if t],
                "descricao": parsed.get("descricao", "Confira a declaração e participe do debate nos comentários."),
                "hashtags": parsed.get("hashtags", ["#shorts", "#viral", "#cortes", "#reels"]),
                "tags_seo": parsed.get("tags_seo", "shorts, cortes, viral, debate"),
                "error": None
            }
        else:
            first_line = raw_out.strip().split('\n')[0]
            return {
                "titulo_principal": _clean_ai_title(first_line[:65]) if first_line else "Momento em Destaque",
                "titulos_alternativos": [],
                "descricao": raw_out[:350],
                "hashtags": ["#shorts", "#viral", "#cortes", "#reels"],
                "tags_seo": "shorts, cortes, viral",
                "error": None
            }

    except Exception as exc:
        # Fallback inteligente se o Ollama estiver offline: extrai as primeiras palavras significativas da fala
        words_preview = snippet_clean.split()
        fallback_title = " ".join(words_preview[:7]) if words_preview else "Declaração em Destaque"
        return {
            "titulo_principal": fallback_title[:60],
            "titulos_alternativos": [],
            "descricao": f"Confira este trecho: '{fallback_title}...'. O que você acha? Deixe sua opinião!",
            "hashtags": ["#shorts", "#viral", "#cortes", "#reels"],
            "tags_seo": "shorts, cortes, viral",
            "error": str(exc)
        }
