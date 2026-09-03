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
    Constrói um prompt estrito para o Ollama traduzir uma lista de legendas mantendo o índice exato.
    """
    src_clause = f"from {source_language_name} " if source_language_name else ""
    return f"""You are an expert subtitle translator and localizer.
Translate the following subtitle lines {src_clause}to {target_language_name}.

STRICT RULES:
1. Maintain colloquial rhythm, tone, slang and punctuation appropriate for video subtitles.
2. Translate naturally (e.g. into Brazilian Portuguese if target is Portuguese).
3. Do NOT add extra explanations or change the line count.
4. You MUST return ONLY a valid JSON array of objects with the exact same keys and number of items:
[
  {{"id": 0, "text": "translated text here"}},
  ...
]

Input subtitle lines to translate:
{json.dumps(items, ensure_ascii=False, indent=2)}
"""


def _call_ollama_json(prompt: str, model: str = "llama3") -> list | None:
    """
    Chama o Ollama solicitando saída formatada em JSON com fallback de extração regex.
    """
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
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
                    for k in ["translations", "subtitles", "items", "lines", "data", "result"]:
                        if k in parsed and isinstance(parsed[k], list):
                            return parsed[k]
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
    batch_size: int = 20,
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
    return os.path.exists(os.path.join("data", video_id, "transcript_original.json"))
