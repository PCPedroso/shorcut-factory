import yt_dlp
import os
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_EXE)
current_path = os.environ.get("PATH", "")
if FFMPEG_DIR and os.path.exists(FFMPEG_DIR) and FFMPEG_DIR not in current_path:
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + current_path

def get_video_metadata(url: str):
    """
    Extrai metadados, heatmaps e status de transmissão ao vivo (live stream / post_live) do vídeo usando yt-dlp.
    Retorna o título, heatmap, duração, status de live e canal com fallback automático para transmissões recém-encerradas.
    """
    options_list = [
        {'quiet': True, 'no_warnings': True},
        {'quiet': True, 'no_warnings': True, 'live_from_start': True},
        {'quiet': True, 'no_warnings': True, 'extractor_args': {'youtube': {'player_client': ['android', 'web']}}}
    ]

    last_error = None
    for ydl_opts in options_list:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                heatmap = info.get('heatmap')
                title = info.get('title')
                duration = info.get('duration')
                upload_date = info.get('upload_date')
                thumbnail = info.get('thumbnail')
                uploader = info.get('uploader') or info.get('channel') or "Canal Desconhecido"
                webpage_url = info.get('webpage_url') or url
                
                # Detecção de Live Stream / Transmissão ao Vivo (em andamento ou recém-encerrada / post_live)
                live_status = info.get('live_status') or ('is_live' if info.get('is_live') else 'not_live')
                is_live = bool(info.get('is_live') or (live_status == 'is_live'))
                was_live = bool(info.get('was_live') or (live_status in ('was_live', 'post_live')))

                return {
                    "title": title,
                    "heatmap": heatmap,
                    "duration": duration,
                    "upload_date": upload_date,
                    "thumbnail": thumbnail,
                    "channel": uploader,
                    "url": webpage_url,
                    "is_live": is_live,
                    "was_live": was_live,
                    "live_status": live_status,
                    "error": None
                }
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "title": None,
        "heatmap": None,
        "duration": None,
        "upload_date": None,
        "thumbnail": None,
        "channel": None,
        "url": url,
        "is_live": False,
        "was_live": False,
        "live_status": "not_live",
        "error": last_error or "Erro ao extrair metadados do vídeo"
    }


def download_audio(url: str, output_path: str = "temp_audio.mp3", is_live: bool = False):
    """
    Baixa o áudio de um vídeo do YouTube com aceleração multi-thread (concurrent fragments).
    Suporta transmissões ao vivo em andamento e recém-encerradas (post_live).
    """
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    base_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[protocol=https]/bestaudio/best',
        'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
        'ffmpeg_location': ffmpeg_path,
        'concurrent_fragment_downloads': 16,
        'http_chunk_size': 10485760,  # 10MB chunk size
        'buffersize': 1048576,        # 1MB buffer
        'retries': 10,
        'fragment_retries': 10,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    attempts = [
        dict(base_opts),
        dict(base_opts, live_from_start=True, hls_use_mpegts=True)
    ]
    if is_live:
        attempts.reverse()

    last_err = None
    for ydl_opts in attempts:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return {"path": output_path, "error": None}
        except Exception as e:
            last_err = str(e)
            continue

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return {"path": output_path, "error": None}
    return {"path": None, "error": last_err or "Falha ao baixar áudio"}
