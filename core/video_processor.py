import os
from moviepy.video.io.VideoFileClip import VideoFileClip
import yt_dlp
import imageio_ffmpeg

def download_full_video(url: str, output_path: str = "temp_video.mp4") -> dict:
    """
    Baixa o vídeo completo usando yt-dlp.
    """
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return {"path": output_path, "error": None}
        except Exception as e:
            return {"path": None, "error": str(e)}

def parse_time_to_seconds(time_str: str) -> int:
    """Converte formato HH:MM:SS ou MM:SS para segundos inteiros."""
    parts = time_str.strip().split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return int(time_str)

def cut_video(input_path: str, start_time_str: str, end_time_str: str, output_path: str = "corte_final.mp4") -> dict:
    """
    Corta o vídeo usando moviepy com base no tempo inicial e final (em formato de texto).
    """
    try:
        start_s = parse_time_to_seconds(start_time_str)
        end_s = parse_time_to_seconds(end_time_str)
        
        with VideoFileClip(input_path) as video:
            new_video = video.subclip(start_s, end_s)
            new_video.write_videofile(
                output_path, 
                codec="libx264", 
                audio_codec="aac",
                logger=None  # Desativa os logs no terminal para não travar o Streamlit
            )
            
        return {"path": output_path, "error": None}
    except Exception as e:
        return {"path": None, "error": str(e)}
