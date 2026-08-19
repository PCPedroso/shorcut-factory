import os
from moviepy.video.io.VideoFileClip import VideoFileClip
import yt_dlp
import imageio_ffmpeg

def download_full_video(url: str, output_path: str = "temp_video.mp4") -> dict:
    """
    Baixa o vídeo completo na máxima resolução disponível (1080p, 2K, 4K ou 720p).
    Usa FFmpeg para mesclar a melhor faixa de vídeo com a melhor faixa de áudio em MP4.
    """
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'ffmpeg_location': ffmpeg_path,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return {"path": output_path, "error": None}
        except Exception as e:
            return {"path": None, "error": str(e)}


def get_video_resolution(video_path: str) -> str:
    """Retorna a resolução do vídeo (ex: '1920x1080') usando FFprobe ou MoviePy."""
    try:
        with VideoFileClip(video_path) as clip:
            w, h = clip.size
            return f"{w}x{h}"
    except Exception:
        return "Desconhecida"



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
    Corta o vídeo. Tenta FFmpeg direto primeiro (mais rápido, sem recodificação),
    com fallback para MoviePy se necessário.
    """
    try:
        import subprocess
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        # FFmpeg direto com -ss e -to: muito mais rápido (copia sem recodificar)
        cmd = [
            ffmpeg_exe,
            "-y",                    # sobrescreve sem perguntar
            "-ss", start_time_str,   # seek no input (mais rápido)
            "-i", input_path,
            "-to", end_time_str,
            "-c", "copy",            # copia stream sem recodificar
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return {"path": output_path, "error": None}
        
        # Fallback: MoviePy (recodifica, mais lento mas mais compatível)
        start_s = parse_time_to_seconds(start_time_str)
        end_s   = parse_time_to_seconds(end_time_str)
        
        with VideoFileClip(input_path) as video:
            # moviepy 2.x usa subclipped(); 1.x usa subclip()
            try:
                clip = video.subclipped(start_s, end_s)
            except AttributeError:
                clip = video.subclip(start_s, end_s)
            
            clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                logger=None
            )
        
        return {"path": output_path, "error": None}
    except Exception as e:
        return {"path": None, "error": str(e)}

