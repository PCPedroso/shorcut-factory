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
    person_preference: str = "auto",
    split_top_pan: float = -0.65,
    split_bottom_pan: float = 0.65,
    split_zoom: float = 1.15,
    split_divider_color: str = "black",
    split_divider_width: int = 4,
    split_auto_switch: bool = True,
    # --- Parâmetros de Legendas Dinâmicas (Fase 2) ---
    subtitle_enabled: bool = False,
    subtitle_transcript_path: str = None,
    subtitle_highlight_color: str = "#FFFF00",
    subtitle_base_color: str = "#FFFFFF",
    subtitle_font_size: int = 55,
) -> dict:
    """
    Corta e formata o vídeo com alta precisão e velocidade via FFmpeg.
    
    Parâmetros:
    - aspect_ratio_mode:
        - '16:9': Horizontal original (1080p Full HD)
        - '9:16_blur': Vertical 1080x1920 com fundo ampliado e desfocado
        - '9:16_crop': Vertical 1080x1920 com corte central preenchendo 100% da tela
        - '9:16_smart_face': Vertical 1080x1920 com rastreamento inteligente de rosto
        - '9:16_split': Vertical 1080x1920 Dividido (Topo: Entrevistador / Base: Entrevistado - Estilo Podcasts/Flow)
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
            result = crop_video_with_smart_face_tracking(
                input_video_path=input_path,
                start_time_str=start_time_str,
                end_time_str=end_time_str,
                output_video_path=output_path,
                auto_zoom=face_auto_zoom,
                margin_ratio=face_margin_ratio,
                person_preference=person_preference
            )
            return _apply_subtitles_if_needed(
                result, output_path, subtitle_enabled, subtitle_transcript_path,
                start_time_str, end_time_str, subtitle_highlight_color, subtitle_base_color, subtitle_font_size
            )

        elif aspect_ratio_mode == "9:16_split":
            # Pipeline 9:16 Split Screen com Transição Dinâmica Inteligente
            from core.face_tracker import crop_video_with_dynamic_auto_switch
            result = crop_video_with_dynamic_auto_switch(
                input_video_path=input_path,
                start_time_str=start_time_str,
                end_time_str=end_time_str,
                output_video_path=output_path,
                split_zoom=split_zoom,
                top_pan=split_top_pan,
                bottom_pan=split_bottom_pan,
                divider_color=split_divider_color,
                divider_width=split_divider_width,
                auto_switch_enabled=split_auto_switch
            )
            return _apply_subtitles_if_needed(
                result, output_path, subtitle_enabled, subtitle_transcript_path,
                start_time_str, end_time_str, subtitle_highlight_color, subtitle_base_color, subtitle_font_size
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
            return _apply_subtitles_if_needed(
                {"path": output_path, "error": None}, output_path,
                subtitle_enabled, subtitle_transcript_path,
                start_time_str, end_time_str, subtitle_highlight_color, subtitle_base_color, subtitle_font_size
            )

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

        return _apply_subtitles_if_needed(
            {"path": output_path, "error": None}, output_path,
            subtitle_enabled, subtitle_transcript_path,
            start_time_str, end_time_str, subtitle_highlight_color, subtitle_base_color, subtitle_font_size
        )
    except Exception as e:
        return {"path": None, "error": str(e)}


def _apply_subtitles_if_needed(
    result: dict,
    output_path: str,
    subtitle_enabled: bool,
    subtitle_transcript_path: str,
    start_time_str: str,
    end_time_str: str,
    subtitle_highlight_color: str,
    subtitle_base_color: str,
    subtitle_font_size: int,
) -> dict:
    """
    Helper interno: aplica legendas dinâmicas como pass-2 se habilitado.
    Recebe o resultado do pipeline de vídeo e, se bem-sucedido e legendas ativadas,
    chama burn_subtitles() sobre o arquivo gerado.
    """
    if not subtitle_enabled:
        return result
    if result.get("error") or not result.get("path"):
        return result
    if not subtitle_transcript_path or not os.path.exists(subtitle_transcript_path):
        result["subtitle_warning"] = "transcript.json não encontrado — legendas ignoradas."
        return result

    import importlib
    import core.subtitle_burner
    importlib.reload(core.subtitle_burner)
    from core.subtitle_burner import burn_subtitles
    sub_result = burn_subtitles(
        input_video_path=result["path"],
        output_video_path=output_path,
        transcript_path=subtitle_transcript_path,
        start_time_str=start_time_str,
        end_time_str=end_time_str,
        highlight_color=subtitle_highlight_color,
        base_color=subtitle_base_color,
        font_size=subtitle_font_size,
    )
    if sub_result.get("error"):
        result["subtitle_error"] = sub_result["error"]
    elif sub_result.get("warning"):
        result["subtitle_warning"] = sub_result["warning"]
    else:
        result["path"] = sub_result["path"]
    return result
