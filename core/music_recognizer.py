"""
music_recognizer.py — Motor de Reconhecimento Inteligente de Músicas e Trilhas Sonoras
Identifica o nome real do som (ex: "Iron Maiden - Fear of the Dark") a partir de metadados,
descrições, transcrição de letras (Whisper) e IA local (Ollama).
"""

import os
import re
import json
import urllib.request
import urllib.parse
from core.extractor import clean_music_title, detect_music_category_suggestion


GENERIC_TITLE_PATTERNS = [
    r'^video\s+by\s+[a-zA-Z0-9_.]+',
    r'^post\s+by\s+[a-zA-Z0-9_.]+',
    r'^reel\s+by\s+[a-zA-Z0-9_.]+',
    r'^tiktok\s+video\s+by\s+[a-zA-Z0-9_.]+',
    r'^instagram\s+post\s+by\s+[a-zA-Z0-9_.]+',
    r'^v[ií]deo\s+de\s+[a-zA-Z0-9_.]+',
    r'^publica[cç][aã]o\s+de\s+[a-zA-Z0-9_.]+',
    r'^clip\s+by\s+[a-zA-Z0-9_.]+',
    r'^audio\s+[a-zA-Z0-9_]+',
    r'^som\s+original\s*[-–—]?\s*[a-zA-Z0-9_.]*',
    r'^original\s+sound\s*[-–—]?\s*[a-zA-Z0-9_.]*',
]


def is_generic_video_title(title: str) -> bool:
    """Verifica se o título é um nome genérico de post/perfil de rede social."""
    if not title:
        return True
    t_clean = title.strip().lower()
    for pat in GENERIC_TITLE_PATTERNS:
        if re.match(pat, t_clean):
            return True
    return False


def extract_music_from_description(description: str) -> str:
    """Extrai nomes de músicas e artistas citados em legendas/descrições."""
    if not description:
        return None
    
    # Padrões comuns de créditos musicais
    patterns = [
        r'\b(?:m[uú]sica|music|song|track|sound|trilha|trilha sonora|áudio|audio)\s*[:=–—\-]\s*([^\n\r#|]+)',
        r'\b(?:tocando|playing|ouvindo|listen)\s*[:=–—\-]\s*([^\n\r#|]+)',
        r'🎵\s*([^\n\r#|]+)',
        r'🎶\s*([^\n\r#|]+)',
        r'🎧\s*([^\n\r#|]+)',
        r'🎸\s*([^\n\r#|]+)',
        r'\b(?:m[uú]sica|music|song|track)\s+([a-zA-Z0-9\s]{2,25}\s*[-–—]\s*[a-zA-Z0-9\s]{2,30})',
        r'([A-Z][a-zA-Z0-9\s]{1,24}\s*[-–—]\s*[A-Z][a-zA-Z0-9\s]{1,29})',  # Ex: Iron Maiden - Fear of the Dark
    ]

    for pat in patterns:
        m = re.search(pat, description, flags=re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            # Limpa palavras introdutórias residuais
            cand = re.sub(r'^(?:m[uú]sica|music|song|track|sound|áudio|audio)\s*[:=–—\-]?\s*', '', cand, flags=re.IGNORECASE)
            # Limpa hashtags ou tags coladas
            cand = re.sub(r'#\w+', '', cand).strip(' -_–—|[]()')
            if len(cand) >= 4 and not is_generic_video_title(cand):
                return clean_music_title(cand)
    return None


def recognize_music_via_ai(
    audio_path: str = None,
    raw_text_snippet: str = None,
    description: str = None,
    model: str = "llama3:latest"
) -> dict:
    """
    Utiliza o Ollama (IA local) para deduzir o nome exato da música e artista
    a partir de trechos de letras cantadas ou legendas do post.
    """
    context_text = ""
    if raw_text_snippet and len(raw_text_snippet.strip()) > 5:
        context_text += f"Trecho / Letra da Música: \"{raw_text_snippet.strip()}\"\n"
    if description and len(description.strip()) > 5:
        context_text += f"Texto do Post / Descrição: \"{description.strip()}\"\n"

    if not context_text.strip():
        return None

    prompt = f"""Você é um especialista em reconhecimento musical e cultura pop.
Analise as informações abaixo e identifique qual é a MÚSICA e o ARTISTA exatos.

{context_text}

Instruções:
- Identifique o Nome da Música e o Artista (ex: "Iron Maiden - Fear of the Dark", "Kordhell - Murder In My Mind", "Queen - Bohemian Rhapsody").
- Sugira a vibe/categoria: "Phonk / Superação", "Heavy Rock / Adrenalina", "Cômico / Meme", "Épico / Glória", "Lo-Fi Chill", "Tensão / Suspense".
- Retorne EXCLUSIVAMENTE um objeto JSON válido no seguinte formato:
{{
  "music_title": "Artista - Nome da Música",
  "category": "🎸 Heavy Rock / Adrenalina"
}}

Se não conseguir identificar com certeza, retorne null no campo music_title."""

    try:
        req_data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1}
        }
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            parsed = json.loads(res_json.get("response", "{}"))
            if parsed.get("music_title") and str(parsed["music_title"]).lower() != "null":
                return {
                    "music_title": parsed["music_title"].strip(),
                    "category": parsed.get("category", "🎵 Trilha Personalizada")
                }
    except Exception:
        pass

    return None


def identify_song_from_audio_and_meta(
    audio_path: str,
    meta: dict = None,
    ollama_model: str = "llama3:latest",
    use_ai: bool = True
) -> dict:
    """
    Função mestre de identificação:
    1. Avalia metadados oficiais do yt-dlp (track, artist, alt_title).
    2. Avalia a descrição do post procurando referências musicais.
    3. Se o título for genérico (ex: "Video by dosesdepsico"):
       - Transcreve 20 segundos do áudio com Whisper para capturar trechos de letras.
       - Envia para a IA do Ollama para identificar o nome da música e artista exato.
    """
    meta = meta or {}
    track = meta.get("track")
    artist = meta.get("artist")
    title = meta.get("title", "")
    description = meta.get("description", "") or meta.get("channel", "")

    # 1. Metadados oficiais yt-dlp
    if track and artist:
        full_title = f"{artist.strip()} - {track.strip()}"
        cat_lbl, cat_key = detect_music_category_suggestion(full_title)
        return {
            "music_title": full_title,
            "category_label": cat_lbl,
            "category_key": cat_key,
            "source": "Metadados Oficiais"
        }
    if track:
        cat_lbl, cat_key = detect_music_category_suggestion(track)
        return {
            "music_title": track.strip(),
            "category_label": cat_lbl,
            "category_key": cat_key,
            "source": "Metadados Oficiais"
        }

    # 2. Descrição do vídeo
    desc_music = extract_music_from_description(description)
    if desc_music and not is_generic_video_title(desc_music):
        cat_lbl, cat_key = detect_music_category_suggestion(desc_music)
        return {
            "music_title": desc_music,
            "category_label": cat_lbl,
            "category_key": cat_key,
            "source": "Descrição do Post"
        }

    # 3. Título não genérico
    if title and not is_generic_video_title(title):
        clean_t = clean_music_title(title, artist=artist)
        cat_lbl, cat_key = detect_music_category_suggestion(clean_t)
        return {
            "music_title": clean_t,
            "category_label": cat_lbl,
            "category_key": cat_key,
            "source": "Título do Vídeo"
        }

    # 4. Transcrição de Letras com Whisper + IA Ollama
    if use_ai and audio_path and os.path.exists(audio_path):
        lyrics_snippet = ""
        try:
            from core.transcriber import transcribe_audio
            t_res = transcribe_audio(audio_path, model_size="base", device="cuda")
            if not t_res.get("error") and t_res.get("full_text"):
                lyrics_snippet = t_res["full_text"][:250]
        except Exception:
            pass

        ai_res = recognize_music_via_ai(
            audio_path=audio_path,
            raw_text_snippet=lyrics_snippet,
            description=description,
            model=ollama_model
        )
        if ai_res and ai_res.get("music_title"):
            m_t = ai_res["music_title"]
            cat_lbl, cat_key = detect_music_category_suggestion(m_t)
            return {
                "music_title": m_t,
                "category_label": ai_res.get("category") or cat_lbl,
                "category_key": cat_key,
                "source": "IA (Reconhecimento Musical)"
            }

    # Fallback Limpo
    fallback_title = clean_music_title(title) if title and not is_generic_video_title(title) else "Trilha Sonora"
    cat_lbl, cat_key = detect_music_category_suggestion(fallback_title)
    return {
        "music_title": fallback_title,
        "category_label": cat_lbl,
        "category_key": cat_key,
        "source": "Título Limpo"
    }
