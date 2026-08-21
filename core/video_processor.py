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
    # --- Parâmetros da Fase 3: Retenção & Áudio ---
    headline_enabled: bool = False,
    headline_text: str = "",
    headline_preset: str = "yellow_black",
    headline_text_color: str = "#000000",
    headline_bg_color: str = "#FFE600",
    headline_font_size: int = 46,
    headline_margin_top: int = 120,
    emojis_enabled: bool = False,
    zoom_punch_enabled: bool = False,
    bg_music_enabled: bool = False,
    bg_music_track_path: str = None,
    bg_music_volume: float = 0.15,
    ducking_preset: str = "medio",
) -> dict:
    """
    Corta e formata o vídeo com alta precisão e esteira completa de pós-produção via FFmpeg.
    
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
            return _apply_all_post_processing(
                result, output_path, start_time_str, end_time_str,
                subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
                headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
                emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset
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
            return _apply_all_post_processing(
                result, output_path, start_time_str, end_time_str,
                subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
                headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
                emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset
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
            return _apply_all_post_processing(
                {"path": output_path, "error": None}, output_path, start_time_str, end_time_str,
                subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
                headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
                emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset
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

        return _apply_all_post_processing(
            {"path": output_path, "error": None}, output_path, start_time_str, end_time_str,
            subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
            headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
            emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset
        )
    except Exception as e:
        return {"path": None, "error": str(e)}


def _apply_all_post_processing(
    result: dict,
    output_path: str,
    start_time_str: str,
    end_time_str: str,
    subtitle_enabled: bool,
    subtitle_transcript_path: str,
    subtitle_highlight_color: str,
    subtitle_base_color: str,
    subtitle_font_size: int,
    headline_enabled: bool,
    headline_text: str,
    headline_preset: str,
    headline_text_color: str,
    headline_bg_color: str,
    headline_font_size: int,
    headline_margin_top: int,
    emojis_enabled: bool,
    zoom_punch_enabled: bool,
    bg_music_enabled: bool,
    bg_music_track_path: str,
    bg_music_volume: float,
    ducking_preset: str,
) -> dict:
    """
    Esteira unificada de pós-processamento:
    1. Aplica Zoom Punch dinâmico (se ativado e corte vertical).
    2. Aplica Legendas Dinâmicas e/ou Headline fixa no topo via ASS.
    3. Aplica Trilha Sonora de fundo com Audio Ducking inteligente via FFmpeg.
    """
    if result.get("error") or not result.get("path"):
        return result

    curr_path = result["path"]
    start_s = parse_time_to_seconds(start_time_str)
    end_s = parse_time_to_seconds(end_time_str)
    duration_s = max(1.0, float(end_s - start_s))

    # --- 1. Zoom Punch de Retenção Visual ---
    if zoom_punch_enabled and duration_s >= 7.0:
        try:
            from core.retention_effects import generate_zoom_punch_filter
            punch_filter = generate_zoom_punch_filter(duration=duration_s, interval=8.5, zoom_factor=1.07)
            if punch_filter:
                tmp_punch = output_path.replace(".mp4", "_punch_tmp.mp4")
                if tmp_punch == output_path:
                    tmp_punch = output_path + ".p_tmp.mp4"
                
                cmd = [
                    FFMPEG_EXE, "-y",
                    "-i", curr_path,
                    "-vf", punch_filter,
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-c:a", "copy",
                    tmp_punch
                ]
                p_res = subprocess.run(cmd, capture_output=True, text=True)
                if p_res.returncode == 0 and os.path.exists(tmp_punch) and os.path.getsize(tmp_punch) > 0:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(tmp_punch, output_path)
                    curr_path = output_path
                else:
                    if os.path.exists(tmp_punch):
                        os.remove(tmp_punch)
        except Exception:
            pass

    # --- 2. Legendas Dinâmicas & Headline de Topo ---
    if subtitle_enabled or (headline_enabled and headline_text):
        from core.subtitle_burner import burn_subtitles
        sub_result = burn_subtitles(
            input_video_path=curr_path,
            output_video_path=output_path,
            transcript_path=subtitle_transcript_path,
            start_time_str=start_time_str,
            end_time_str=end_time_str,
            highlight_color=subtitle_highlight_color,
            base_color=subtitle_base_color,
            font_size=subtitle_font_size,
            headline_enabled=headline_enabled,
            headline_text=headline_text,
            headline_preset=headline_preset,
            headline_text_color=headline_text_color,
            headline_bg_color=headline_bg_color,
            headline_font_size=headline_font_size,
            headline_margin_top=headline_margin_top,
            emojis_enabled=emojis_enabled,
        )
        if sub_result.get("error"):
            result["subtitle_error"] = sub_result["error"]
        elif sub_result.get("warning"):
            result["subtitle_warning"] = sub_result["warning"]
        else:
            curr_path = sub_result["path"]
            result["path"] = curr_path

    # --- 3. Trilha Sonora de Fundo & Audio Ducking Inteligente ---
    if bg_music_enabled and bg_music_track_path and os.path.exists(bg_music_track_path):
        from core.audio_mixer import apply_audio_ducking
        duck_result = apply_audio_ducking(
            input_video_path=curr_path,
            output_video_path=output_path,
            music_track_path=bg_music_track_path,
            music_volume=bg_music_volume,
            ducking_preset=ducking_preset,
        )
        if duck_result.get("warning"):
            result["audio_warning"] = duck_result["warning"]
        elif duck_result.get("path"):
            curr_path = duck_result["path"]
            result["path"] = curr_path

    return result

