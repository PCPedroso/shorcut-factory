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

def fetch_youtube_transcript(video_id: str) -> dict:
    """
    Obtém a transcrição oficial do YouTube (legendas automáticas ou manuais em PT-BR/PT).
    É instantâneo (< 1s) e muito mais preciso que modelos pequenos de Whisper.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id, languages=['pt', 'pt-BR', 'en'])
        
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
            "source": "YouTube Oficial (ASR)",
            "error": None
        }
    except Exception as e:
        return {
            "transcript_segments": None,
            "full_text": None,
            "source": None,
            "error": str(e)
        }


def transcribe_audio(audio_path: str, model_size: str = "small", device: str = "cuda"):
    """
    Transcreve o áudio usando Faster-Whisper (usado como fallback se não houver legendas no YouTube).
    """
    if not os.path.exists(audio_path):
        return {"transcript_segments": None, "full_text": None, "source": None, "error": "Arquivo de áudio não encontrado."}
        
    try:
        compute_type = "float32" if device == "cuda" else "int8"
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        transcript_data = []
        full_text = ""
        for segment in segments:
            transcript_data.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text
            })
            full_text += segment.text + " "
            
        return {
            "transcript_segments": transcript_data,
            "full_text": full_text.strip(),
            "source": f"Whisper ({model_size})",
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



def build_youtube_transcript_blocks(segments: list, target_duration: float = 6.0) -> list:
    """
    Agrupa snippets de transcrição em blocos visuais de parágrafo no estilo exato do YouTube (~6s por bloco),
    com badges de tempo [0:00], [0:06], [0:12], [0:19] e texto fluido.
    """
    blocks = []
    if not segments:
        return blocks

    curr_start = segments[0]['start']
    curr_end = segments[0]['end']
    curr_texts = []

    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue
        cleaned = text.replace('>>', '').strip()
        curr_texts.append(cleaned)
        curr_end = seg.get('end', curr_start)

        # Fecha o bloco quando acumular ~target_duration segundos
        if (curr_end - curr_start) >= target_duration:
            blocks.append({
                'start': round(curr_start, 2),
                'end': round(curr_end, 2),
                'time_label': format_badge_time(curr_start),
                'time_full': f"{int(curr_start//3600):02d}:{int((curr_start%3600)//60):02d}:{int(curr_start%60):02d}",
                'text': ' '.join(curr_texts)
            })
            curr_start = seg.get('end', curr_start)
            curr_texts = []

    if curr_texts:
        blocks.append({
            'start': round(curr_start, 2),
            'end': round(curr_end, 2),
            'time_label': format_badge_time(curr_start),
            'time_full': f"{int(curr_start//3600):02d}:{int((curr_start%3600)//60):02d}:{int(curr_start%60):02d}",
            'text': ' '.join(curr_texts)
        })
    return blocks


