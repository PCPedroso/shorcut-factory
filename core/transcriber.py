from faster_whisper import WhisperModel
import os
import sys

# Tenta adicionar as DLLs do CUDA (baixadas via pip) no PATH do Windows
try:
    site_packages = next(p for p in sys.path if 'site-packages' in p)
    cublas_path = os.path.join(site_packages, "nvidia", "cublas", "bin")
    cudnn_path = os.path.join(site_packages, "nvidia", "cudnn", "bin")
    if os.path.exists(cublas_path) and os.path.exists(cudnn_path):
        os.environ["PATH"] = f"{cublas_path};{cudnn_path};" + os.environ.get("PATH", "")
except:
    pass

def extract_youtube_video_id(url_or_id: str) -> str:
    """Extrai o ID de 11 caracteres do YouTube a partir de ID puro ou URL completa."""
    if not url_or_id:
        return ""
    clean = str(url_or_id).strip()
    if len(clean) == 11 and "/" not in clean and "?" not in clean and "&" not in clean:
        return clean
    import re
    m = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|live\/)([0-9A-Za-z_-]{11})", clean)
    if m:
        return m.group(1)
    return clean


def fetch_youtube_transcript(video_id: str, preferred_languages: list = None) -> dict:
    """
    Obtém a transcrição oficial do YouTube com prioridade absoluta para Português (pt-BR, pt, pt-PT, pt-orig).
    Utiliza motor duplo:
      1. YouTubeTranscriptApi (com varredura de legendas manuais e geradas automaticamente)
      2. Fallback via yt-dlp (extração direta dos streams json3 de automatic_captions/subtitles)
    """
    if preferred_languages is None:
        preferred_languages = ['pt', 'pt-BR', 'pt-PT', 'pt-orig', 'a.pt', 'en', 'es']

    clean_id = extract_youtube_video_id(video_id)
    if not clean_id:
        return {
            "transcript_segments": None,
            "full_text": None,
            "source": None,
            "available_languages": [],
            "selected_language": None,
            "error": "ID do YouTube inválido."
        }

    available_languages = []
    selected_lang_name = "Português"
    last_err = None

    # -- MOTOR 1: YouTubeTranscriptApi --
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()

        # Mapeia todas as faixas disponíveis
        try:
            t_list = ytt.list(clean_id)
            for t in t_list:
                available_languages.append({
                    "code": t.language_code,
                    "name": t.language,
                    "is_generated": getattr(t, "is_generated", False),
                    "is_translatable": getattr(t, "is_translatable", False)
                })

            # Busca faixa preferencial (manual ou automática)
            tr = None
            try:
                tr = t_list.find_transcript(preferred_languages)
            except Exception:
                try:
                    tr = t_list.find_generated_transcript(preferred_languages)
                except Exception:
                    pass

            if tr is not None:
                fetched = tr.fetch()
                selected_lang_name = tr.language
            else:
                fetched = ytt.fetch(clean_id, languages=preferred_languages)
        except Exception:
            fetched = ytt.fetch(clean_id, languages=preferred_languages)

        if fetched:
            transcript_data = []
            full_text_list = []
            for seg in fetched:
                # Trata objeto ou dict
                text = getattr(seg, "text", None) or (seg.get("text") if isinstance(seg, dict) else "")
                start = getattr(seg, "start", None) or (seg.get("start") if isinstance(seg, dict) else 0.0)
                dur = getattr(seg, "duration", None) or (seg.get("duration") if isinstance(seg, dict) else 0.0)

                t_clean = str(text).strip().replace('\n', ' ')
                if not t_clean:
                    continue
                transcript_data.append({
                    "start": round(float(start), 2),
                    "end": round(float(start) + float(dur), 2),
                    "text": t_clean
                })
                full_text_list.append(t_clean)

            if transcript_data:
                return {
                    "transcript_segments": transcript_data,
                    "full_text": " ".join(full_text_list),
                    "source": f"YouTube Oficial ({selected_lang_name})",
                    "available_languages": available_languages,
                    "selected_language": selected_lang_name,
                    "error": None
                }
    except Exception as e1:
        last_err = str(e1)

    # -- MOTOR 2: Fallback via yt-dlp Subtitle Stream (json3) --
    try:
        import yt_dlp
        import urllib.request
        from core.extractor import get_cookie_file

        url = f"https://www.youtube.com/watch?v={clean_id}"
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        cookie_file = get_cookie_file()
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            auto_captions = info.get('automatic_captions') or {}
            manual_subtitles = info.get('subtitles') or {}

            # Prioridade de busca
            target_formats = None
            found_lang_key = "pt"
            for lang_k in preferred_languages + ['pt', 'pt-BR', 'pt-PT', 'pt-orig']:
                if lang_k in manual_subtitles:
                    target_formats = manual_subtitles[lang_k]
                    found_lang_key = lang_k
                    break
                if lang_k in auto_captions:
                    target_formats = auto_captions[lang_k]
                    found_lang_key = lang_k
                    break

            if target_formats:
                json_url = next((f['url'] for f in target_formats if f.get('ext') == 'json3'), None)
                if json_url:
                    req = urllib.request.Request(json_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        events = data.get('events', [])
                        transcript_data = []
                        full_text_list = []
                        for ev in events:
                            if 'segs' in ev and 'tStartMs' in ev:
                                start = round(float(ev['tStartMs']) / 1000.0, 2)
                                dur = round(float(ev.get('dDurationMs', 0)) / 1000.0, 2)
                                txt = ''.join([s.get('utf8', '') for s in ev['segs']]).strip().replace('\n', ' ')
                                if txt:
                                    transcript_data.append({
                                        'start': start,
                                        'end': round(start + dur, 2),
                                        'text': txt
                                    })
                                    full_text_list.append(txt)

                        if transcript_data:
                            return {
                                "transcript_segments": transcript_data,
                                "full_text": " ".join(full_text_list),
                                "source": f"YouTube Oficial ({found_lang_key})",
                                "available_languages": available_languages,
                                "selected_language": found_lang_key,
                                "error": None
                            }
    except Exception as e2:
        last_err = f"{last_err} | yt-dlp: {e2}"

    return {
        "transcript_segments": None,
        "full_text": None,
        "source": None,
        "available_languages": available_languages,
        "selected_language": None,
        "error": last_err or "Legendas não encontradas no YouTube."
    }


def transcribe_audio(audio_path: str, model_size: str = "small", device: str = "cuda", language: str = "pt"):
    """
    Transcreve o áudio usando Faster-Whisper (usado como fallback se não houver legendas no YouTube).
    Por padrão força language="pt" para garantir transcrição em português-BR mesmo com vinhetas ou ruídos iniciais.
    """
    if not os.path.exists(audio_path):
        return {"transcript_segments": None, "full_text": None, "source": None, "error": "Arquivo de áudio não encontrado."}

    try:
        compute_type = "float32" if device == "cuda" else "int8"
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        # Força language='pt' (ou linguagem informada) para evitar falsos positivos de detecção de inglês
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            word_timestamps=True
        )

        detected_lang = getattr(info, 'language', language) or language
        transcript_data = []
        full_text = ""
        for segment in segments:
            # Extrai lista de palavras com timestamps individuais
            words_data = []
            if segment.words:
                for w in segment.words:
                    words_data.append({
                        "word": w.word,
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                    })
            transcript_data.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": words_data,
            })
            full_text += segment.text + " "

        return {
            "transcript_segments": transcript_data,
            "full_text": full_text.strip(),
            "source": f"Whisper ({model_size} - {detected_lang.upper()})",
            "available_languages": [{"code": detected_lang, "name": "Português (Whisper AI)"}],
            "selected_language": detected_lang,
            "error": None
        }
    except Exception as e:
        return {"transcript_segments": None, "full_text": None, "source": None, "error": str(e)}


def format_badge_time(seconds: float) -> str:
    """Formata segundos no padrão do badge do YouTube (ex: '0:00', '0:06', '1:24', '1:02:15')."""
    total_sec = int(seconds)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"



def build_youtube_transcript_blocks(segments: list, min_duration: float = 5.8, target_duration: float = None, **kwargs) -> list:
    """
    Agrupa snippets de transcrição em blocos visuais de parágrafo no estilo exato do YouTube,
    respeitando as pausas e quebras de interlocutor [0:00, 0:06, 0:12, 0:19, 0:27...].
    """
    if target_duration is not None:
        min_duration = target_duration

    blocks = []
    if not segments:
        return blocks

    curr_start = segments[0]['start']
    curr_end = segments[0].get('end', curr_start)
    curr_texts = []

    for seg in segments:
        text = seg.get('text', '').strip().replace('\n', ' ')
        if not text:
            continue
        cleaned = text.replace('>>', '').strip()
        
        delta = seg['start'] - curr_start
        should_break = False
        if curr_texts:
            if delta >= 6.5:
                should_break = True
            elif delta >= min_duration and ('>>' in text or curr_texts[-1].endswith(('.', '?', '!'))):
                should_break = True

        if should_break:
            blocks.append({
                'start': round(curr_start, 2),
                'end': round(curr_end, 2),
                'time_label': format_badge_time(curr_start),
                'time_full': f"{int(curr_start//3600):02d}:{int((curr_start%3600)//60):02d}:{int(curr_start%60):02d}",
                'text': ' '.join(curr_texts)
            })
            curr_start = seg['start']
            curr_texts = []

        curr_texts.append(cleaned)
        curr_end = seg.get('end', seg['start'] + 2.0)

    if curr_texts:
        blocks.append({
            'start': round(curr_start, 2),
            'end': round(curr_end, 2),
            'time_label': format_badge_time(curr_start),
            'time_full': f"{int(curr_start//3600):02d}:{int((curr_start%3600)//60):02d}:{int(curr_start%60):02d}",
            'text': ' '.join(curr_texts)
        })
    return blocks



