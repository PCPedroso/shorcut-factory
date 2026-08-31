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
    Obtém a transcrição oficial do YouTube com prioridade absoluta para Português (pt-BR, pt, pt-PT).
    Detecta todas as linguagens disponíveis no vídeo e sinaliza suporte a multilinguagem.
    """
    if preferred_languages is None:
        preferred_languages = ['pt-BR', 'pt', 'pt-PT', 'pt-br', 'pt-pt', 'en', 'es']

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        clean_id = extract_youtube_video_id(video_id)
        ytt = YouTubeTranscriptApi()

        # 1. Mapeia todas as faixas de legenda disponíveis no vídeo
        available_languages = []
        selected_lang_name = "Português"
        try:
            t_list = ytt.list(clean_id)
            for t in t_list:
                available_languages.append({
                    "code": t.language_code,
                    "name": t.language,
                    "is_generated": getattr(t, "is_generated", False),
                    "is_translatable": getattr(t, "is_translatable", False)
                })
        except Exception:
            pass

        # 2. Busca estritamente com a ordem de preferência (Português prioritário)
        fetched = ytt.fetch(clean_id, languages=preferred_languages)

        # Identifica a linguagem selecionada
        if available_languages:
            for pref in preferred_languages:
                matching = [l for l in available_languages if l["code"].lower() == pref.lower()]
                if matching:
                    selected_lang_name = matching[0]["name"]
                    break

        transcript_data = []
        full_text_list = []
        for seg in fetched:
            t = seg.text.strip().replace('\n', ' ')
            if not t:
                continue
            transcript_data.append({
                "start": round(seg.start, 2),
                "end": round(seg.start + seg.duration, 2),
                "text": t
            })
            full_text_list.append(t)

        return {
            "transcript_segments": transcript_data,
            "full_text": " ".join(full_text_list),
            "source": f"YouTube Oficial ({selected_lang_name})",
            "available_languages": available_languages,
            "selected_language": selected_lang_name,
            "error": None
        }
    except Exception as e:
        return {
            "transcript_segments": None,
            "full_text": None,
            "source": None,
            "available_languages": [],
            "selected_language": None,
            "error": str(e)
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



