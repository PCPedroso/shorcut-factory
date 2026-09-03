"""
translator.py — Motor de Tradução de Transcrições & Legendas Dinâmicas (PT-BR ⇄ EN ⇄ ES)
Permite traduzir trechos ou transcrições completas sob demanda via IA local (Ollama / Llama 3),
preservando 100% da sincronização milimétrica dos timestamps (start/end) para queima de legendas e exportação.
"""

import os
import re
import json
import requests


OLLAMA_API_URL = "http://localhost:11434/api/generate"


LANGUAGE_NAMES = {
    "pt": "Português (Brasil)",
    "pt-BR": "Português (Brasil)",
    "en": "Inglês (English)",
    "es": "Espanhol (Español)",
}


def format_translation_prompt(items: list, target_language_name: str, source_language_name: str = None) -> str:
    """
    Constrói um prompt estrito para o Ollama traduzir uma lista de legendas mantendo o índice exato
    e retornando um objeto JSON com chave 'translations'.
    """
    src_clause = f"from {source_language_name} " if source_language_name else ""
    return f"""You are an expert video subtitle translator and localizer.
Translate ALL {len(items)} subtitle lines {src_clause}to {target_language_name}.

STRICT RULES:
1. Maintain colloquial rhythm, tone, slang, emotion, and punctuation appropriate for video subtitles.
2. Translate naturally into {target_language_name} (e.g. natural Brazilian Portuguese).
3. Translate EVERY single item from id 0 to id {len(items)-1}. Do NOT omit or merge any items.
4. You MUST return ONLY a valid JSON object with the "translations" array:
{{
  "translations": [
    {{"id": 0, "text": "translated line 0"}},
    {{"id": 1, "text": "translated line 1"}}
  ]
}}

Input subtitle lines to translate:
{json.dumps(items, ensure_ascii=False, indent=2)}
"""


def _call_ollama_json(prompt: str, model: str = "llama3") -> list | None:
    """
    Chama o Ollama solicitando saída formatada em JSON com fallback robusto de extração.
    """
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }
        res = requests.post(OLLAMA_API_URL, json=payload, timeout=90)
        if res.status_code == 200:
            resp_json = res.json()
            raw_response = resp_json.get("response", "").strip()

            # Tenta decodificar direto
            try:
                parsed = json.loads(raw_response)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict):
                    for k in ["translations", "subtitles", "items", "lines", "data", "result", "results"]:
                        if k in parsed and isinstance(parsed[k], list):
                            return parsed[k]
                    # Se for um dicionário de ids {"0": "...", "1": "..."}
                    items_list = []
                    for k, v in parsed.items():
                        if isinstance(v, dict) and "text" in v:
                            v_copy = dict(v)
                            if "id" not in v_copy:
                                v_copy["id"] = k
                            items_list.append(v_copy)
                        elif isinstance(v, str):
                            items_list.append({"id": k, "text": v})
                    if items_list:
                        return items_list
            except Exception:
                pass

            # Fallback regex para array JSON
            match = re.search(r'\[\s*\{.*?\}\s*\]', raw_response, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass

    except Exception:
        pass
    return None


def translate_transcript_segments(
    segments: list,
    target_lang: str = "pt-BR",
    source_lang: str = None,
    model: str = "llama3",
    batch_size: int = 15,
    progress_callback=None
) -> dict:
    """
    Traduz uma lista de segmentos de transcrição em lotes com IA local (Ollama).
    Preserva rigorosamente start, end e a ordem de cada frase.
    
    Retorna:
      {
        "segments": [...],
        "full_text": "...",
        "translated_count": int,
        "target_lang": str,
        "error": str | None
      }
    """
    if not segments:
        return {
            "segments": [],
            "full_text": "",
            "translated_count": 0,
            "target_lang": target_lang,
            "error": "Nenhum segmento fornecido para tradução."
        }

    target_lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    source_lang_name = LANGUAGE_NAMES.get(source_lang, source_lang) if source_lang else None

    total_segments = len(segments)
    translated_segments = []
    translated_texts_all = []

    # Processa em lotes de batch_size
    for b_idx in range(0, total_segments, batch_size):
        batch = segments[b_idx:b_idx + batch_size]
        items_payload = [{"id": idx, "text": seg.get("text", "")} for idx, seg in enumerate(batch)]

        if progress_callback:
            progress_callback(min(1.0, b_idx / total_segments), f"Traduzindo frases {b_idx + 1} a {min(total_segments, b_idx + len(batch))} de {total_segments}...")

        prompt = format_translation_prompt(items_payload, target_lang_name, source_lang_name)
        translated_items = _call_ollama_json(prompt, model=model)

        # Mapeia as traduções recebidas
        trans_map = {}
        if translated_items and isinstance(translated_items, list):
            for it in translated_items:
                if isinstance(it, dict) and "id" in it and "text" in it:
                    trans_map[int(it["id"])] = str(it["text"]).strip()
                elif isinstance(it, dict) and "text" in it:
                    # Se não vier o id, usa a ordem da lista
                    idx_implicit = len(trans_map)
                    trans_map[idx_implicit] = str(it["text"]).strip()

        # Reconstrói os segmentos do lote com timestamps preservados
        for idx, seg in enumerate(batch):
            original_text = seg.get("text", "").strip()
            translated_text = trans_map.get(idx, original_text)

            new_seg = dict(seg)
            new_seg["text"] = translated_text
            new_seg["original_text"] = original_text
            # Remove palavras em inglês para que o subtitle_burner faça interpolação limpa com o novo texto traduzido
            if "words" in new_seg:
                del new_seg["words"]

            translated_segments.append(new_seg)
            translated_texts_all.append(translated_text)

    if progress_callback:
        progress_callback(1.0, "Tradução concluída!")

    full_text_translated = " ".join([t for t in translated_texts_all if t])

    return {
        "segments": translated_segments,
        "full_text": full_text_translated,
        "translated_count": len(translated_segments),
        "target_lang": target_lang_name,
        "error": None
    }


def save_translated_transcript(video_id: str, translated_data: dict, target_lang: str) -> bool:
    """
    Salva a transcrição traduzida em data/<video_id>/transcript.json
    e cria automaticamente um backup em data/<video_id>/transcript_original.json se ainda não existir.
    """
    if not video_id or not translated_data or not translated_data.get("segments"):
        return False

    v_dir = os.path.join("data", video_id)
    os.makedirs(v_dir, exist_ok=True)
    orig_path = os.path.join(v_dir, "transcript_original.json")
    active_path = os.path.join(v_dir, "transcript.json")

    # 1. Faz backup do original se não existir
    if os.path.exists(active_path) and not os.path.exists(orig_path):
        try:
            with open(active_path, "r", encoding="utf-8") as f_in, open(orig_path, "w", encoding="utf-8") as f_out:
                f_out.write(f_in.read())
        except Exception:
            pass

    # 2. Salva a nova transcrição traduzida
    try:
        out_payload = {
            "text": translated_data.get("full_text", ""),
            "segments": translated_data.get("segments", []),
            "language": target_lang,
            "is_translated": True,
            "source": f"IA Tradução ({LANGUAGE_NAMES.get(target_lang, target_lang)})"
        }
        with open(active_path, "w", encoding="utf-8") as f:
            json.dump(out_payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def restore_original_transcript(video_id: str) -> dict | None:
    """
    Restaura a transcrição original a partir de data/<video_id>/transcript_original.json.
    """
    if not video_id:
        return None

    v_dir = os.path.join("data", video_id)
    orig_path = os.path.join(v_dir, "transcript_original.json")
    active_path = os.path.join(v_dir, "transcript.json")

    if not os.path.exists(orig_path):
        return None

    try:
        with open(orig_path, "r", encoding="utf-8") as f_orig:
            orig_data = json.load(f_orig)

        with open(active_path, "w", encoding="utf-8") as f_active:
            json.dump(orig_data, f_active, ensure_ascii=False, indent=2)

        return orig_data
    except Exception:
        return None


def has_original_backup(video_id: str) -> bool:
    """Verifica se existe backup da transcrição original para restauração."""
    if not video_id:
        return False
    # Verifica em data/<video_id> ou data/<video_id_t_...>
    v_dir = os.path.join("data", video_id)
    if os.path.exists(os.path.join(v_dir, "transcript_original.json")):
        return True
    if os.path.exists("data"):
        for d in os.listdir("data"):
            if d.startswith(video_id) and os.path.exists(os.path.join("data", d, "transcript_original.json")):
                return True
    return False


def translate_cut_subtitles(
    video_id: str,
    start_time_str: str,
    end_time_str: str,
    target_lang: str = "pt-BR",
    model: str = "llama3"
) -> dict:
    """
    Traduz especificamente as frases de um trecho/corte delimitado por start_time e end_time,
    substituindo o texto no transcript.json e mantendo 100% da sincronia de timestamps.
    """
    from core.extractor import parse_time_str
    
    # Localiza o arquivo transcript.json correto (mesmo com sufixo _t_...)
    t_path = os.path.join("data", video_id, "transcript.json")
    target_vid_dir = os.path.join("data", video_id)
    if not os.path.exists(t_path):
        if os.path.exists("data"):
            for d in os.listdir("data"):
                if d.startswith(video_id) and os.path.exists(os.path.join("data", d, "transcript.json")):
                    t_path = os.path.join("data", d, "transcript.json")
                    target_vid_dir = os.path.join("data", d)
                    video_id = d
                    break

    if not os.path.exists(t_path):
        return {"translated_segments": [], "translated_snippet": "", "count": 0, "error": "Arquivo transcript.json não encontrado."}

    try:
        with open(t_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return {"translated_segments": [], "translated_snippet": "", "count": 0, "error": str(e)}

    segments = data.get("segments", [])
    if not segments:
        return {"translated_segments": [], "translated_snippet": "", "count": 0, "error": "Nenhum segmento encontrado no transcript.json."}

    s_sec = parse_time_str(start_time_str) or 0.0
    e_sec = parse_time_str(end_time_str) or float('inf')

    # Identifica os índices dos segmentos dentro do intervalo do corte
    target_indices = []
    target_sub_segments = []
    for idx, seg in enumerate(segments):
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", 0.0)
        # Sobreposição temporal estrita com o corte
        if seg_end > s_sec and seg_start < e_sec:
            target_indices.append(idx)
            target_sub_segments.append(seg)

    if not target_sub_segments:
        return {"translated_segments": [], "translated_snippet": "", "count": 0, "error": "Nenhuma frase encontrada dentro do intervalo selecionado."}

    # Traduz as frases do corte
    trans_res = translate_transcript_segments(
        segments=target_sub_segments,
        target_lang=target_lang,
        model=model,
        batch_size=20
    )

    if trans_res.get("error"):
        return {"translated_segments": [], "translated_snippet": "", "count": 0, "error": trans_res["error"]}

    # Backup do original no disco se ainda não existir
    orig_path = os.path.join(target_vid_dir, "transcript_original.json")
    if not os.path.exists(orig_path):
        try:
            with open(orig_path, "w", encoding="utf-8") as f_out:
                json.dump(data, f_out, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Atualiza os segmentos originais com as frases traduzidas
    translated_segs = trans_res.get("segments", [])
    for idx, new_seg in zip(target_indices, translated_segs):
        segments[idx] = new_seg

    # Salva transcript.json atualizado
    data["segments"] = segments
    data["full_text"] = " ".join([s.get("text", "") for s in segments if s.get("text")])
    data["is_translated"] = True
    data["language"] = target_lang

    try:
        with open(t_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"translated_segments": [], "translated_snippet": "", "count": 0, "error": str(e)}

    cut_snippet = " ".join([s.get("text", "") for s in translated_segs if s.get("text")])

    return {
        "translated_segments": translated_segs,
        "translated_snippet": cut_snippet,
        "count": len(translated_segs),
        "video_id": video_id,
        "error": None
    }
