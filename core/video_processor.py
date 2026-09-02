"""
video_processor.py — Download em Alta Definição (1080p Full HD / 720p) e Corte Preciso via FFmpeg
"""

import os
import subprocess
import yt_dlp
import imageio_ffmpeg
from moviepy.video.io.VideoFileClip import VideoFileClip

import re
import hashlib
import cv2
import numpy as np

# Garante que o Deno e o FFmpeg estejam no PATH do processo
DENO_DIR = os.path.expanduser(r"~/.deno/bin")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_EXE)

# Garante que exista um executável chamado ffmpeg.exe na pasta para ferramentas que buscam pelo nome padrão
ffmpeg_alias = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
if not os.path.exists(ffmpeg_alias) and os.path.exists(FFMPEG_EXE):
    try:
        import shutil
        shutil.copy2(FFMPEG_EXE, ffmpeg_alias)
    except Exception:
        pass

current_path = os.environ.get("PATH", "")
paths_to_add = [p for p in [DENO_DIR, FFMPEG_DIR] if os.path.exists(p) and p not in current_path]
if paths_to_add:
    os.environ["PATH"] = os.pathsep.join(paths_to_add) + os.pathsep + current_path


def generate_local_video_id(filename_or_path: str) -> str:
    """
    Gera um identificador único e seguro para vídeos locais do computador.
    Exemplo: 'Entrevista Podcast.mp4' -> 'local_entrevista_podcast_a1b2c3d4'
    """
    base_name = os.path.splitext(os.path.basename(filename_or_path))[0]
    # Sanitiza o nome para caracteres alfanuméricos e underscores
    slug = re.sub(r'[^a-zA-Z0-9_]+', '_', base_name).strip('_').lower()
    if not slug:
        slug = "video"
    if len(slug) > 35:
        slug = slug[:35]

    # Gera hash curto de 8 caracteres baseado no nome
    hash_str = hashlib.md5(filename_or_path.encode('utf-8')).hexdigest()[:8]
    return f"local_{slug}_{hash_str}"


def generate_local_dual_video_id(filename1: str, filename2: str) -> str:
    """
    Gera um identificador único para composição de dois vídeos locais.
    Exemplo: 'Entrevista.mp4' e 'Reacao.mp4' -> 'local_dual_entrevista_e_reacao_a1b2c3d4'
    """
    base1 = os.path.splitext(os.path.basename(filename1))[0]
    base2 = os.path.splitext(os.path.basename(filename2))[0]
    slug1 = re.sub(r'[^a-zA-Z0-9_]+', '_', base1).strip('_').lower()[:18] or "vid1"
    slug2 = re.sub(r'[^a-zA-Z0-9_]+', '_', base2).strip('_').lower()[:18] or "vid2"
    combo_str = f"{filename1}__AND__{filename2}"
    hash_str = hashlib.md5(combo_str.encode('utf-8')).hexdigest()[:8]
    return f"local_dual_{slug1}_e_{slug2}_{hash_str}"


def extract_audio_from_local_video(video_path: str, output_path: str = "temp_audio.mp3") -> dict:
    """
    Extrai a faixa de áudio em MP3 a partir de um arquivo de vídeo local usando FFmpeg.
    """
    try:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = [
            FFMPEG_EXE, "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", "192k",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {"path": output_path, "error": None}
        else:
            err_txt = res.stderr.decode('utf-8', errors='replace')[-200:] if res.stderr else 'Erro desconhecido'
            return {"path": None, "error": f"Falha ao extrair áudio: {err_txt}"}
    except Exception as exc:
        return {"path": None, "error": str(exc)}


def extract_thumbnail_from_video(video_path: str, output_path: str = "temp_thumb.jpg", timestamp_sec: float = 2.0) -> dict:
    """
    Captura e salva um frame do vídeo local em formato JPG para servir de thumbnail.
    """
    try:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = [
            FFMPEG_EXE, "-y",
            "-ss", str(max(0.0, float(timestamp_sec))),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {"path": output_path, "error": None}
        else:
            return {"path": None, "error": "Falha ao gerar thumbnail."}
    except Exception as exc:
        return {"path": None, "error": str(exc)}


def download_full_video(url: str, output_path: str = "temp_video.mp4", is_live: bool = False) -> dict:
    """
    Baixa o vídeo na máxima resolução disponível (1080p Full HD / 720p HD).
    Usa o runtime Deno e o solver EJS para decifrar os fluxos 1080p do YouTube,
    mesclando a melhor faixa de vídeo e áudio em MP4 via FFmpeg.
    Suporta transmissões ao vivo em andamento (live_from_start).
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

        from core.extractor import get_cookie_file
        cookie_file = get_cookie_file()

        base_opts = {
            'format': 'bestvideo[height<=1080][protocol=https]+bestaudio[protocol=https]/bestvideo[height<=1080]+bestaudio/bestvideo+bestaudio/best',
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
            'ffmpeg_location': FFMPEG_EXE,
            'concurrent_fragment_downloads': 16,
            'http_chunk_size': 10485760,  # 10MB chunk size to avoid YouTube throttling
            'buffersize': 1048576,        # 1MB RAM buffer
            'retries': 10,
            'fragment_retries': 10,
            'quiet': False,
            'no_warnings': True,
            'js_runtimes': js_runtimes_cfg
        }

        if cookie_file:
            base_opts['cookiefile'] = cookie_file

        attempts = [
            dict(base_opts),
            dict(base_opts, format='bestvideo+bestaudio/best', live_from_start=True, hls_use_mpegts=True),
            dict(base_opts, live_from_start=True, hls_use_mpegts=True)
        ]
        if is_live:
            attempts = [attempts[1], attempts[2], attempts[0]]

        last_err = None
        for ydl_opts in attempts:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return {"path": output_path, "error": None}
            except Exception as exc_attempt:
                last_err = str(exc_attempt)
                continue

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return {"path": output_path, "error": None}
        else:
            return {"path": None, "error": last_err or "Falha ao gerar o arquivo de vídeo final."}

    except Exception as exc:
        return {"path": None, "error": str(exc)}


def get_video_resolution(video_path: str) -> str:
    """Retorna a resolução do vídeo (ex: '1080x1920') instantaneamente."""
    if not video_path or not os.path.exists(video_path):
        return "1080x1920"
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if w > 0 and h > 0:
                return f"{w}x{h}"
    except Exception:
        pass
    try:
        with VideoFileClip(video_path) as clip:
            w, h = clip.size
            return f"{w}x{h}"
    except Exception:
        return "1080x1920"


def parse_time_to_seconds(time_str: str) -> float:
    """Converte formato HH:MM:SS, HH:MM:SS.ms ou MM:SS para segundos (float)."""
    if not time_str:
        return 0.0
    clean = str(time_str).strip().replace(',', '.')
    parts = clean.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    try:
        return float(clean)
    except Exception:
        return 0.0


def cut_video(
    input_path: str,
    start_time_str: str,
    end_time_str: str,
    output_path: str = "corte_final.mp4",
    aspect_ratio_mode: str = "16:9",
    horizontal_zoom: float = 1.0,
    blur_zoom: float = 1.0,
    blur_pan: float = 0.0,
    blur_intensity: int = 25,
    blur_auto_tracking: bool = True,
    face_auto_zoom: bool = True,
    face_margin_ratio: float = 1.55,
    person_preference: str = "auto",
    split_top_pan: float = -0.65,
    split_bottom_pan: float = 0.65,
    split_zoom: float = 1.15,
    split_divider_color: str = "black",
    split_divider_width: int = 4,
    split_auto_switch: bool = True,
    split_source_type: str = "main_video",
    split_video_path: str = None,
    split_image_paths: list = None,
    split_media_position: str = "bottom",
    split_blur_margin_pct: float = 5.0,
    # --- Parâmetros de Legendas Dinâmicas (Fase 2) ---
    subtitle_enabled: bool = False,
    subtitle_transcript_path: str = None,
    subtitle_highlight_color: str = "#FFFF00",
    subtitle_base_color: str = "#FFFFFF",
    subtitle_font_size: int = 55,
    # --- Parâmetros da Fase 3 & 4: Retenção, Capas & Áudio ---
    headline_enabled: bool = False,
    headline_text: str = "",
    headline_preset: str = "yellow_black",
    headline_text_color: str = "#000000",
    headline_bg_color: str = "#FFDA29",
    headline_font_size: int = 46,
    headline_margin_top: int = 120,
    emojis_enabled: bool = False,
    zoom_punch_enabled: bool = False,
    bg_music_enabled: bool = False,
    bg_music_track_path: str = None,
    bg_music_volume: float = 0.15,
    ducking_preset: str = "medio",
    # --- Parâmetros da Fase 4: Retenção Dinâmica & Thumbnails ---
    progress_bar_enabled: bool = False,
    progress_bar_color: str = "#FF0000",
    progress_bar_height: int = 8,
    callout_enabled: bool = False,
    callout_text: str = "",
    callout_duration: float = 4.5,
    climax_zoom_enabled: bool = False,
    climax_zoom_factor: float = 1.14,
    thumbnail_enabled: bool = True,
    thumbnail_output_path: str = None,
) -> dict:
    """
    Corta e formata o vídeo com alta precisão e esteira completa de pós-produção via FFmpeg.
    
    Parâmetros:
    - aspect_ratio_mode:
        - '16:9': Horizontal original (1080p Full HD com suporte a zoom/aproximação geral)
        - '9:16_blur': Vertical 1080x1920 com fundo ampliado e desfocado (Auto-Reframing dinâmico ou manual)
        - '9:16_crop': Vertical 1080x1920 com corte central preenchendo 100% da tela
        - '9:16_smart_face': Vertical 1080x1920 com rastreamento inteligente de rosto
        - '9:16_split': Vertical 1080x1920 Dividido (Topo e Base: Oradores, Vídeo Secundário em Looping ou Slideshow de Imagens)
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
                emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset,
                progress_bar_enabled, progress_bar_color, progress_bar_height,
                callout_enabled, callout_text, callout_duration,
                climax_zoom_enabled, climax_zoom_factor,
                thumbnail_enabled, thumbnail_output_path, aspect_ratio_mode, input_path
            )

        elif aspect_ratio_mode == "9:16_split":
            # Pipeline 9:16 Split Screen com Transição Dinâmica e Mídia Secundária
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
                auto_switch_enabled=split_auto_switch,
                split_source_type=split_source_type,
                split_video_path=split_video_path,
                split_image_paths=split_image_paths,
                split_media_position=split_media_position,
                split_blur_margin_pct=split_blur_margin_pct
            )
            return _apply_all_post_processing(
                result, output_path, start_time_str, end_time_str,
                subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
                headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
                emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset,
                progress_bar_enabled, progress_bar_color, progress_bar_height,
                callout_enabled, callout_text, callout_duration,
                climax_zoom_enabled, climax_zoom_factor,
                thumbnail_enabled, thumbnail_output_path, aspect_ratio_mode, input_path
            )

        elif aspect_ratio_mode == "9:16_blur":
            # Pipeline 9:16 Fundo Desfocado
            if blur_auto_tracking:
                # Modo Inteligente: Dynamic Auto-Reframing com rastreamento de rosto no foreground
                from core.face_tracker import crop_video_with_smart_blur_tracking
                result = crop_video_with_smart_blur_tracking(
                    input_video_path=input_path,
                    start_time_str=start_time_str,
                    end_time_str=end_time_str,
                    output_video_path=output_path,
                    blur_zoom=blur_zoom,
                    person_preference=person_preference,
                    face_margin_ratio=face_margin_ratio,
                    auto_tracking=True
                )
                return _apply_all_post_processing(
                    result, output_path, start_time_str, end_time_str,
                    subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
                    headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
                    emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset,
                    progress_bar_enabled, progress_bar_color, progress_bar_height,
                    callout_enabled, callout_text, callout_duration,
                    climax_zoom_enabled, climax_zoom_factor,
                    thumbnail_enabled, thumbnail_output_path, aspect_ratio_mode, input_path
                )
            else:
                # Modo Manual Estático
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
                "-movflags", "+faststart",
                output_path
            ]
        else:
            # Padrão 16:9 Horizontal (Com suporte a aproximação / zoom geral)
            effective_hz_zoom = max(1.0, float(horizontal_zoom))
            if effective_hz_zoom > 1.001:
                filter_complex = f"[0:v]crop=iw/{effective_hz_zoom}:ih/{effective_hz_zoom}:(in_w-out_w)/2:(in_h-out_h)/2,scale=1920:1080[v]"
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
                    "-movflags", "+faststart",
                    output_path
                ]
            else:
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
                    "-movflags", "+faststart",
                    output_path
                ]


        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        _stderr_txt = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''

        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return _apply_all_post_processing(
                {"path": output_path, "error": None}, output_path, start_time_str, end_time_str,
                subtitle_enabled, subtitle_transcript_path, subtitle_highlight_color, subtitle_base_color, subtitle_font_size,
                headline_enabled, headline_text, headline_preset, headline_text_color, headline_bg_color, headline_font_size, headline_margin_top,
                emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset,
                progress_bar_enabled, progress_bar_color, progress_bar_height,
                callout_enabled, callout_text, callout_duration,
                climax_zoom_enabled, climax_zoom_factor,
                thumbnail_enabled, thumbnail_output_path, aspect_ratio_mode, input_path
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
            emojis_enabled, zoom_punch_enabled, bg_music_enabled, bg_music_track_path, bg_music_volume, ducking_preset,
            progress_bar_enabled, progress_bar_color, progress_bar_height,
            callout_enabled, callout_text, callout_duration,
            climax_zoom_enabled, climax_zoom_factor,
            thumbnail_enabled, thumbnail_output_path, aspect_ratio_mode, input_path
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
    # --- Parâmetros da Fase 4 ---
    progress_bar_enabled: bool = False,
    progress_bar_color: str = "#FF0000",
    progress_bar_height: int = 8,
    callout_enabled: bool = False,
    callout_text: str = "",
    callout_duration: float = 4.5,
    climax_zoom_enabled: bool = False,
    climax_zoom_factor: float = 1.14,
    thumbnail_enabled: bool = True,
    thumbnail_output_path: str = None,
    aspect_mode: str = "9:16_smart_face",
    source_video_path: str = None
) -> dict:
    """
    Esteira unificada de pós-produção (Fases 2, 3 e 4):
    1. Aplica Zoom Punch dinâmico e/ou Climax Punchline Zoom.
    2. Aplica Barra de Progresso Animada no rodapé via FFmpeg drawbox.
    3. Aplica Legendas Dinâmicas, Headline fixa e Lower Third de Engajamento via ASS libass.
    4. Aplica Trilha Sonora de fundo com Audio Ducking inteligente.
    5. Gera automaticamente a Capa / Thumbnail 9:16 de alta conversão.
    """
    if result.get("error") or not result.get("path"):
        return result

    curr_path = result["path"]
    start_s = parse_time_to_seconds(start_time_str)
    end_s = parse_time_to_seconds(end_time_str)
    duration_s = max(1.0, float(end_s - start_s))

    # ── RESTRIÇÕES PARA FORMATO HORIZONTAL (16:9) ──
    # Em vídeos horizontais widescreen normais, efeitos automáticos de Shorts (como zoom punch e barras verticais)
    # são desativados para preservar a experiência tradicional de YouTube, a menos que o usuário tenha solicitado.
    if aspect_mode == "16:9":
        zoom_punch_enabled = False
        climax_zoom_enabled = False
        progress_bar_enabled = False
        callout_enabled = False

    # --- 1. Zoom Punch de Retenção & Climax Punchline Zoom ---
    curr_res_str = get_video_resolution(curr_path)
    v_w, v_h = 1080, 1920
    if "x" in curr_res_str:
        try:
            parts = curr_res_str.split("x")
            v_w = int(parts[0])
            v_h = int(parts[1])
        except Exception:
            pass

    zoom_filters = []
    if zoom_punch_enabled and duration_s >= 7.0:
        try:
            from core.retention_effects import generate_zoom_punch_filter
            punch_f = generate_zoom_punch_filter(
                duration=duration_s,
                interval=8.5,
                zoom_factor=1.08,
                video_width=v_w,
                video_height=v_h
            )
            if punch_f:
                zoom_filters.append(punch_f)
        except Exception:
            pass

    if climax_zoom_enabled and duration_s >= 5.0:
        try:
            from core.retention_effects import generate_climax_zoom_filter
            climax_f = generate_climax_zoom_filter(
                duration=duration_s,
                climax_duration=3.5,
                zoom_factor=climax_zoom_factor,
                video_width=v_w,
                video_height=v_h
            )
            if climax_f:
                zoom_filters.append(climax_f)
        except Exception:
            pass

    for zf in zoom_filters:
        try:
            tmp_z = output_path.replace(".mp4", "_zoom_tmp.mp4")
            if tmp_z == output_path:
                tmp_z = output_path + ".z_tmp.mp4"

            cmd = [
                FFMPEG_EXE, "-y",
                "-i", curr_path,
                "-filter_complex", zf,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "copy",
                "-movflags", "+faststart",
                tmp_z
            ]
            z_res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if z_res.returncode == 0 and os.path.exists(tmp_z) and os.path.getsize(tmp_z) > 0:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(tmp_z, output_path)
                curr_path = output_path
            else:
                if os.path.exists(tmp_z):
                    os.remove(tmp_z)
        except Exception:
            pass

    # --- 2. Barra de Progresso Animada de Retenção (Fase 4) ---
    if progress_bar_enabled and duration_s >= 2.0:
        try:
            from core.retention_effects import generate_progress_bar_filter
            curr_res_str = get_video_resolution(curr_path)
            v_w = 1080
            if "x" in curr_res_str:
                try:
                    v_w = int(curr_res_str.split("x")[0])
                except Exception:
                    pass

            pb_filter = generate_progress_bar_filter(
                duration=duration_s,
                color_hex=progress_bar_color,
                height_px=progress_bar_height,
                video_width=v_w
            )
            if pb_filter:
                tmp_pb = output_path.replace(".mp4", "_pb_tmp.mp4")
                if tmp_pb == output_path:
                    tmp_pb = output_path + ".pb_tmp.mp4"

                cmd = [
                    FFMPEG_EXE, "-y",
                    "-i", curr_path,
                    "-filter_complex", pb_filter,
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    tmp_pb
                ]
                pb_res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if pb_res.returncode == 0 and os.path.exists(tmp_pb) and os.path.getsize(tmp_pb) > 0:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(tmp_pb, output_path)
                    curr_path = output_path
                else:
                    if os.path.exists(tmp_pb):
                        os.remove(tmp_pb)
        except Exception:
            pass

    # --- 3. Legendas Dinâmicas, Headline de Topo & Callout de Engajamento ---
    if subtitle_enabled or (headline_enabled and headline_text) or (callout_enabled and callout_text):
        from core.subtitle_burner import burn_subtitles
        sub_result = burn_subtitles(
            input_video_path=curr_path,
            output_video_path=output_path,
            transcript_path=subtitle_transcript_path if subtitle_enabled else None,
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
            callout_enabled=callout_enabled,
            callout_text=callout_text,
            callout_duration=callout_duration,
        )
        if sub_result.get("error"):
            result["subtitle_error"] = sub_result["error"]
        elif sub_result.get("warning"):
            result["subtitle_warning"] = sub_result["warning"]
        else:
            curr_path = sub_result["path"]
            result["path"] = curr_path

    # --- 4. Trilha Sonora de Fundo & Audio Ducking Inteligente ---
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

    # --- 5. Geração Automática de Thumbnail / Capa 9:16 (Fase 4) ---
    if thumbnail_enabled:
        try:
            from core.thumbnail_generator import create_cut_thumbnail
            thumb_target = thumbnail_output_path
            if not thumb_target:
                out_dir = os.path.dirname(output_path)
                thumb_target = os.path.join(out_dir, "thumbnail.jpg")

            thumb_src = source_video_path if (source_video_path and os.path.exists(source_video_path)) else curr_path
            thumb_res = create_cut_thumbnail(
                source_video_or_frame=thumb_src,
                headline_text=headline_text or "",
                output_path=thumb_target,
                start_time_str=start_time_str,
                end_time_str=end_time_str,
                preset=headline_preset,
                custom_text_color=headline_text_color,
                custom_bg_color=headline_bg_color,
                aspect_mode=aspect_mode
            )
            if thumb_res.get("path") and os.path.exists(thumb_res["path"]):
                result["thumbnail_path"] = thumb_res["path"]
                result["thumbnail_variations"] = thumb_res.get("variations", [])
        except Exception:
            pass

    return result


def ensure_faststart(video_path: str) -> str:
    """
    Garante que o arquivo MP4 possua o moov atom no início do arquivo (+faststart)
    permitindo streaming e reprodução instantânea no navegador sem travamentos.
    """
    if not video_path or not os.path.exists(video_path):
        return video_path
    try:
        tmp_fast = video_path + ".fast.mp4"
        cmd = [FFMPEG_EXE, "-y", "-i", video_path, "-c", "copy", "-movflags", "+faststart", tmp_fast]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if res.returncode == 0 and os.path.exists(tmp_fast) and os.path.getsize(tmp_fast) > 0:
            os.replace(tmp_fast, video_path)
    except Exception:
        pass
    return video_path


def check_has_audio_stream(video_path: str) -> bool:
    """Verifica se o arquivo de vídeo possui uma faixa de áudio utilizável."""
    if not video_path or not os.path.exists(video_path):
        return False
    try:
        cmd = [FFMPEG_EXE, "-i", video_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err_txt = res.stderr.decode('utf-8', errors='replace')
        return "Audio:" in err_txt
    except Exception:
        return False


def fit_frame_to_aspect_slot(img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Redimensiona e recorta centralizadamente o frame para preencher o slot (target_w x target_h)."""
    if img is None:
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)
    ih, iw = img.shape[:2]
    if ih == 0 or iw == 0:
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)
    
    scale = max(float(target_w) / float(iw), float(target_h) / float(ih))
    new_w = int(round(iw * scale))
    new_h = int(round(ih * scale))
    
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(img, (new_w, new_h), interpolation=interp)
    
    x1 = max(0, (new_w - target_w) // 2)
    y1 = max(0, (new_h - target_h) // 2)
    cropped = resized[y1 : y1 + target_h, x1 : x1 + target_w]
    if cropped.shape[0] != target_h or cropped.shape[1] != target_w:
        cropped = cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    return cropped


def generate_dual_split_preview(
    video1_path: str,
    video2_path: str,
    output_preview_path: str = "temp_dual_split_preview.jpg",
    video1_ts: float = 0.0,
    video2_ts: float = 0.0,
    freeze_monochrome: bool = True,
    aspect_ratio: str = "9:16",
    divider_color: str = "black",
    divider_width: int = 4
) -> dict:
    """
    Gera imagem JPG de prévia da composição inicial dividida:
    - Topo: Frame do Vídeo 1 no timestamp video1_ts
    - Base: Frame do Vídeo 2 no timestamp video2_ts (monocromático se freeze_monochrome=True)
    - Linha divisória configurável
    """
    try:
        target_w, target_h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
        slot_h = target_h // 2
        
        # Frame do Vídeo 1 (Topo)
        cap1 = cv2.VideoCapture(video1_path)
        cap1.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(video1_ts)) * 1000.0)
        ret1, frame1 = cap1.read()
        cap1.release()
        if not ret1 or frame1 is None:
            top_res = np.zeros((slot_h, target_w, 3), dtype=np.uint8)
        else:
            top_res = fit_frame_to_aspect_slot(frame1, target_w, slot_h)

        # Frame do Vídeo 2 (Base)
        cap2 = cv2.VideoCapture(video2_path)
        cap2.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(video2_ts)) * 1000.0)
        ret2, frame2 = cap2.read()
        cap2.release()
        if not ret2 or frame2 is None:
            bot_res = np.zeros((slot_h, target_w, 3), dtype=np.uint8)
        else:
            bot_res = fit_frame_to_aspect_slot(frame2, target_w, slot_h)
            if freeze_monochrome:
                gray = cv2.cvtColor(bot_res, cv2.COLOR_BGR2GRAY)
                bot_res = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        # Junta topo e base
        canvas = cv2.vconcat([top_res, bot_res])

        # Divisor
        if divider_width > 0 and divider_color != "none":
            div_c = (0, 0, 0) if divider_color == "black" else ((255, 255, 255) if divider_color == "white" else (128, 128, 128))
            y_mid = slot_h
            y1 = max(0, y_mid - divider_width // 2)
            y2 = min(target_h, y_mid + divider_width // 2)
            canvas[y1:y2, :] = div_c

        out_dir = os.path.dirname(output_preview_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        cv2.imwrite(output_preview_path, canvas)
        return {"path": output_preview_path, "error": None}
    except Exception as exc:
        return {"path": None, "error": str(exc)}


def compose_dual_video_split_sequence(
    video1_path: str,
    video2_path: str,
    output_path: str = "video_composed_full.mp4",
    freeze_timestamp_sec: float = 0.0,
    freeze_monochrome: bool = True,
    aspect_ratio: str = "9:16",
    divider_width: int = 4,
    divider_color: str = "black",
    video1_audio_track: str = None,
    video1_audio_volume: float = 0.20,
    video2_audio_track: str = None,
    video2_audio_volume: float = 0.25,
    audio_ducking_enabled: bool = True
) -> dict:
    """
    Renderiza composição sequencial inteligente de 2 vídeos:
    1. Parte 1 (duração = Vídeo 1):
       - Topo: Vídeo 1 reproduzindo normalmente com seu áudio.
       - Base: Frame estático do Vídeo 2 (em freeze_timestamp_sec), opcionalmente monocromático (preto e branco).
       - Trilha Sonora 1: Música de fundo específica para a Parte 1 (com Audio Ducking).
    2. Parte 2 (duração = Vídeo 2):
       - O Vídeo 2 assume tela cheia (1080x1920 ou 1920x1080) e toca até o final com seu áudio.
       - Trilha Sonora 2: Música de fundo específica para a Parte 2 (com Audio Ducking).
    """
    temp_frozen_png = None
    try:
        from core.quick_editor import get_video_duration
        from core.audio_mixer import get_track_path_by_id

        if not os.path.exists(video1_path):
            return {"path": None, "error": f"Arquivo do Vídeo 1 não encontrado: {video1_path}"}
        if not os.path.exists(video2_path):
            return {"path": None, "error": f"Arquivo do Vídeo 2 não encontrado: {video2_path}"}

        dur1 = get_video_duration(video1_path)
        dur2 = get_video_duration(video2_path)

        if dur1 <= 0.0:
            return {"path": None, "error": "Não foi possível obter a duração do Vídeo 1."}
        if dur2 <= 0.0:
            return {"path": None, "error": "Não foi possível obter a duração do Vídeo 2."}

        target_w, target_h = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
        slot_h = target_h // 2

        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass

        # 1. Extrai frame estático do Vídeo 2
        temp_frozen_png = os.path.join(out_dir, "temp_freeze_bottom.png") if out_dir else "temp_freeze_bottom.png"
        cap2 = cv2.VideoCapture(video2_path)
        cap2.set(cv2.CAP_PROP_POS_MSEC, max(0.0, min(float(freeze_timestamp_sec), max(0.0, dur2 - 0.1))) * 1000.0)
        ret2, frame2 = cap2.read()
        cap2.release()

        if not ret2 or frame2 is None:
            # Fallback para primeiro frame
            cap2 = cv2.VideoCapture(video2_path)
            ret2, frame2 = cap2.read()
            cap2.release()

        if not ret2 or frame2 is None:
            bot_frame = np.zeros((slot_h, target_w, 3), dtype=np.uint8)
        else:
            bot_frame = fit_frame_to_aspect_slot(frame2, target_w, slot_h)
            if freeze_monochrome:
                gray = cv2.cvtColor(bot_frame, cv2.COLOR_BGR2GRAY)
                bot_frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        cv2.imwrite(temp_frozen_png, bot_frame)

        # 2. Resolução de Trilhas Musicais
        v1_music_path = None
        if video1_audio_track and video1_audio_track not in ["none", "nenhum", ""]:
            v1_music_path = get_track_path_by_id(video1_audio_track)
            if not v1_music_path or not os.path.exists(v1_music_path):
                v1_music_path = None

        v2_music_path = None
        if video2_audio_track and video2_audio_track not in ["none", "nenhum", ""]:
            v2_music_path = get_track_path_by_id(video2_audio_track)
            if not v2_music_path or not os.path.exists(v2_music_path):
                v2_music_path = None

        # 3. Mapeamento de Entradas FFmpeg
        base_cmd = [
            FFMPEG_EXE, "-y",
            "-i", video1_path,                               # Input 0
            "-loop", "1", "-t", f"{dur1:.3f}", "-i", temp_frozen_png, # Input 1
            "-i", video2_path                                # Input 2
        ]

        curr_input_idx = 3
        v1_music_idx = None
        if v1_music_path:
            v1_music_idx = curr_input_idx
            base_cmd.extend(["-stream_loop", "-1", "-i", v1_music_path])
            curr_input_idx += 1

        v2_music_idx = None
        if v2_music_path:
            v2_music_idx = curr_input_idx
            base_cmd.extend(["-stream_loop", "-1", "-i", v2_music_path])
            curr_input_idx += 1

        has_a1 = check_has_audio_stream(video1_path)
        has_a2 = check_has_audio_stream(video2_path)

        # 4. Grafo de Filtros Complexos
        filter_parts = []

        # -- Vídeo Parte 1 (Split Top / Base Congelada) --
        filter_parts.append(
            f"[0:v]scale={target_w}:{slot_h}:force_original_aspect_ratio=increase,crop={target_w}:{slot_h},setsar=1,fps=30[v1_top]"
        )
        filter_parts.append(
            f"[1:v]scale={target_w}:{slot_h}:force_original_aspect_ratio=increase,crop={target_w}:{slot_h},setsar=1,fps=30[v2_bot]"
        )
        filter_parts.append(
            "[v1_top][v2_bot]vstack=inputs=2[seg1_raw]"
        )

        if divider_width > 0 and divider_color != "none":
            div_col = "black" if divider_color == "black" else ("white" if divider_color == "white" else "gray")
            filter_parts.append(
                f"[seg1_raw]drawbox=x=0:y={slot_h - divider_width // 2}:w={target_w}:h={divider_width}:color={div_col}@1:t=fill[seg1_v]"
            )
        else:
            filter_parts.append(
                "[seg1_raw]null[seg1_v]"
            )

        # -- Áudio Parte 1 (Voz 1 + Música 1) --
        if has_a1:
            filter_parts.append(
                f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{dur1:.3f},asetpts=PTS-STARTPTS[v1_voice]"
            )
        else:
            filter_parts.append(
                f"anullsrc=r=48000:cl=stereo,atrim=duration={dur1:.3f}[v1_voice]"
            )

        if v1_music_idx is not None:
            filter_parts.append(
                f"[{v1_music_idx}:a]atrim=0:{dur1:.3f},asetpts=PTS-STARTPTS,volume={video1_audio_volume:.2f},aformat=sample_rates=48000:channel_layouts=stereo[m1_raw]"
            )
            if audio_ducking_enabled and has_a1:
                filter_parts.append(
                    f"[m1_raw][v1_voice]sidechaincompress=threshold=0.08:ratio=5:attack=30:release=300[m1_ducked]"
                )
                filter_parts.append(
                    f"[v1_voice][m1_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[seg1_a]"
                )
            else:
                filter_parts.append(
                    f"[v1_voice][m1_raw]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[seg1_a]"
                )
        else:
            filter_parts.append(
                "[v1_voice]aformat=sample_rates=48000:channel_layouts=stereo[seg1_a]"
            )

        # -- Vídeo Parte 2 (Tela Cheia Vídeo 2) --
        filter_parts.append(
            f"[2:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps=30[seg2_v]"
        )

        # -- Áudio Parte 2 (Voz 2 + Música 2) --
        if has_a2:
            filter_parts.append(
                f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{dur2:.3f},asetpts=PTS-STARTPTS[v2_voice]"
            )
        else:
            filter_parts.append(
                f"anullsrc=r=48000:cl=stereo,atrim=duration={dur2:.3f}[v2_voice]"
            )

        if v2_music_idx is not None:
            filter_parts.append(
                f"[{v2_music_idx}:a]atrim=0:{dur2:.3f},asetpts=PTS-STARTPTS,volume={video2_audio_volume:.2f},aformat=sample_rates=48000:channel_layouts=stereo[m2_raw]"
            )
            if audio_ducking_enabled and has_a2:
                filter_parts.append(
                    f"[m2_raw][v2_voice]sidechaincompress=threshold=0.08:ratio=5:attack=30:release=300[m2_ducked]"
                )
                filter_parts.append(
                    f"[v2_voice][m2_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[seg2_a]"
                )
            else:
                filter_parts.append(
                    f"[v2_voice][m2_raw]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[seg2_a]"
                )
        else:
            filter_parts.append(
                "[v2_voice]aformat=sample_rates=48000:channel_layouts=stereo[seg2_a]"
            )

        # -- Concatenação Final Sequencial --
        filter_parts.append(
            "[seg1_v][seg1_a][seg2_v][seg2_a]concat=n=2:v=1:a=1[out_v][out_a]"
        )

        filter_complex = ";".join(filter_parts)

        # 5. Execução FFmpeg com aceleração NVENC e fallback CPU
        full_base_cmd = base_cmd + [
            "-filter_complex", filter_complex,
            "-map", "[out_v]",
            "-map", "[out_a]"
        ]

        nvenc_cmd = full_base_cmd + [
            "-c:v", "h264_nvenc",
            "-preset", "p4",
            "-b:v", "8M",
            "-maxrate", "10M",
            "-bufsize", "16M",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path
        ]

        res = subprocess.run(nvenc_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            cpu_cmd = full_base_cmd + [
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path
            ]
            res_cpu = subprocess.run(cpu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if res_cpu.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                err_txt = res_cpu.stderr.decode('utf-8', errors='replace')[-300:] if res_cpu.stderr else "Erro desconhecido"
                return {"path": None, "error": f"Falha ao renderizar composição dupla: {err_txt}"}

        ensure_faststart(output_path)
        return {
            "path": output_path,
            "error": None,
            "total_duration": dur1 + dur2,
            "video1_duration": dur1,
            "video2_duration": dur2
        }

    except Exception as exc:
        return {"path": None, "error": str(exc)}
    finally:
        if temp_frozen_png and os.path.exists(temp_frozen_png):
            try:
                os.remove(temp_frozen_png)
            except Exception:
                pass

