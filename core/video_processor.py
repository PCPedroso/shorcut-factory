"""
video_processor.py — Download em Alta Definição (1080p Full HD / 720p) e Corte Preciso via FFmpeg
"""

import os
import subprocess
import yt_dlp
import imageio_ffmpeg
from moviepy.video.io.VideoFileClip import VideoFileClip

# Garante que o Deno e o FFmpeg estejam no PATH do processo
DENO_DIR = os.path.expanduser(r"~/.deno/bin")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_EXE)

current_path = os.environ.get("PATH", "")
paths_to_add = [p for p in [DENO_DIR, FFMPEG_DIR] if os.path.exists(p) and p not in current_path]
if paths_to_add:
    os.environ["PATH"] = os.pathsep.join(paths_to_add) + os.pathsep + current_path


def download_full_video(url: str, output_path: str = "temp_video.mp4") -> dict:
    """
    Baixa o vídeo na máxima resolução disponível (1080p Full HD / 720p HD).
    Usa o runtime Deno e o solver EJS para decifrar os fluxos 1080p do YouTube,
    mesclando a melhor faixa de vídeo e áudio em MP4 via FFmpeg.
    """
    try:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if os.path.exists(output_path):
            os.remove(output_path)

        deno_exe = os.path.join(DENO_DIR, "deno.exe")
        js_runtimes_cfg = {}
        if os.path.exists(deno_exe):
            js_runtimes_cfg['deno'] = {'path': deno_exe}
        elif os.path.exists(r"C:\Program Files\nodejs\node.exe"):
            js_runtimes_cfg['node'] = {'path': r"C:\Program Files\nodejs\node.exe"}

        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best',
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
            'ffmpeg_location': FFMPEG_DIR,
            'quiet': False,
            'no_warnings': True,
            'js_runtimes': js_runtimes_cfg
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {"path": output_path, "error": None}
        else:
            return {"path": None, "error": "Falha ao gerar o arquivo de vídeo final."}

    except Exception as exc:
        return {"path": None, "error": str(exc)}


def get_video_resolution(video_path: str) -> str:
    """Retorna a resolução do vídeo (ex: '1920x1080') usando MoviePy."""
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


def cut_video(
    input_path: str,
    start_time_str: str,
    end_time_str: str,
    output_path: str = "corte_final.mp4",
    aspect_ratio_mode: str = "16:9",
    blur_zoom: float = 1.0,
    blur_pan: float = 0.0,
    blur_intensity: int = 25,
    face_auto_zoom: bool = True,
    face_margin_ratio: float = 1.55,
    person_preference: str = "auto"
) -> dict:
    """
    Corta e formata o vídeo com alta precisão e velocidade via FFmpeg.
    
    Parâmetros:
    - aspect_ratio_mode:
        - '16:9': Horizontal original (1080p Full HD)
        - '9:16_blur': Vertical 1080x1920 com fundo ampliado e desfocado
        - '9:16_crop': Vertical 1080x1920 com corte central preenchendo 100% da tela
        - '9:16_smart_face': Vertical 1080x1920 com rastreamento inteligente de rosto
    - blur_zoom: Nível de aproximação do vídeo principal no modo blur (1.0x a 2.5x).
    - blur_pan: Posição horizontal do vídeo principal (-1.0 à esquerda até +1.0 à direita).
    - blur_intensity: Intensidade do desfoque de fundo (10 a 50).
    - face_auto_zoom: Ativa o auto-zoom dinâmico no orador com corte de bordas vazias.
    - face_margin_ratio: Margem de segurança lateral do interlocutor (1.2x a 2.0x).
    - person_preference: 'auto', 'right', 'left', 'center' (Trava no orador desejado).
    """
    try:
        if os.path.exists(output_path):
            os.remove(output_path)

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if aspect_ratio_mode == "9:16_smart_face":
            # Pipeline 9:16 com Rastreamento Inteligente de Rosto (MediaPipe BlazeFace + Target Lock + Cinematic Panning)
            from core.face_tracker import crop_video_with_smart_face_tracking
            return crop_video_with_smart_face_tracking(
                input_video_path=input_path,
                start_time_str=start_time_str,
                end_time_str=end_time_str,
                output_video_path=output_path,
                auto_zoom=face_auto_zoom,
                margin_ratio=face_margin_ratio,
                person_preference=person_preference
            )

        elif aspect_ratio_mode == "9:16_blur":
            # Pipeline 9:16 Fundo Desfocado com Zoom e Pan configuráveis
            w_fg = int(1080 * blur_zoom)
            if w_fg % 2 != 0:
                w_fg += 1

            if w_fg > 1080:
                max_crop_x = w_fg - 1080
                crop_x = int(max_crop_x * (blur_pan + 1.0) / 2.0)
                fg_filter = f"[0:v]scale={w_fg}:-2,crop=1080:ih:{crop_x}:0[fg]"
                overlay_filter = "[bg][fg]overlay=0:(H-h)/2[v]"
            else:
                fg_filter = f"[0:v]scale={w_fg}:-2[fg]"
                overlay_filter = "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"

            filter_complex = (
                f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur={blur_intensity}:5,eq=brightness=-0.10[bg];"
                f"{fg_filter};"
                f"{overlay_filter}"
            )
            cmd = [
                FFMPEG_EXE, "-y",
                "-ss", start_time_str,
                "-to", end_time_str,
                "-i", input_path,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output_path
            ]
        elif aspect_ratio_mode == "9:16_crop":
            # Pipeline 9:16 Corte Central (1080x1920 preenchendo 100% da tela)
            filter_complex = "[0:v]crop=ih*(9/16):ih:(iw-ow)/2:0,scale=1080:1920[v]"
            cmd = [
                FFMPEG_EXE, "-y",
                "-ss", start_time_str,
                "-to", end_time_str,
                "-i", input_path,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output_path
            ]
        else:
            # Padrão 16:9 Horizontal (Cópia rápida com recodificação precisa)
            cmd = [
                FFMPEG_EXE, "-y",
                "-ss", start_time_str,
                "-to", end_time_str,
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                output_path
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {"path": output_path, "error": None}

        # Fallback MoviePy se FFmpeg direto retornar erro
        start_s = parse_time_to_seconds(start_time_str)
        end_s = parse_time_to_seconds(end_time_str)

        with VideoFileClip(input_path) as video:
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

