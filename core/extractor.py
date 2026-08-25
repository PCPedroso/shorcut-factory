import yt_dlp
import os

def get_video_metadata(url: str):
    """
    Extrai metadados, heatmaps e status de transmissão ao vivo (live stream) do vídeo usando yt-dlp.
    Retorna o título, heatmap, duração, status de live e canal.
    """
    ydl_opts = {
        'quiet': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            heatmap = info.get('heatmap')
            title = info.get('title')
            duration = info.get('duration')
            upload_date = info.get('upload_date')
            thumbnail = info.get('thumbnail')
            uploader = info.get('uploader') or info.get('channel') or "Canal Desconhecido"
            webpage_url = info.get('webpage_url') or url
            
            # Detecção de Live Stream / Transmissão ao Vivo em andamento
            live_status = info.get('live_status') or ('is_live' if info.get('is_live') else 'not_live')
            is_live = bool(info.get('is_live') or (live_status == 'is_live'))
            was_live = bool(info.get('was_live') or (live_status == 'was_live'))

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
                "error": str(e)
            }

def download_audio(url: str, output_path: str = "temp_audio.mp3", is_live: bool = False):
    """
    Baixa o áudio de um vídeo do YouTube. Suporta transmissões ao vivo em andamento (live_from_start).
    """
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
        'ffmpeg_location': ffmpeg_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }

    if is_live:
        ydl_opts['live_from_start'] = True
        ydl_opts['hls_use_mpegts'] = True

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return {"path": output_path, "error": None}
        except Exception as e:
            return {"path": None, "error": str(e)}
