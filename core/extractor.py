import yt_dlp
import os

def get_video_metadata(url: str):
    """
    Extrai metadados e heatmaps do vídeo usando yt-dlp.
    Retorna o título, heatmap e a duração do vídeo.
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
            return {
                "title": title,
                "heatmap": heatmap,
                "duration": duration,
                "upload_date": upload_date,
                "thumbnail": thumbnail,
                "channel": uploader,
                "url": webpage_url,
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
                "error": str(e)
            }

def download_audio(url: str, output_path: str = "temp_audio.mp3"):
    """
    Baixa o áudio de um vídeo do YouTube.
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
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return {"path": output_path, "error": None}
        except Exception as e:
            return {"path": None, "error": str(e)}
