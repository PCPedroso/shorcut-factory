"""
quick_editor.py — Ferramenta de Edição Rápida, Ajuste Fino (Trim) e Remoção de Trechos com FFmpeg
"""

import os
import subprocess
import cv2
import numpy as np
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


_DUR_CACHE = {}
_FRAME_CACHE = {}
_VERSIONS_CACHE = {}


def get_video_duration(video_path: str) -> float:
    """
    Retorna a duração exata do vídeo em segundos via OpenCV / FFprobe com cache em memória.
    """
    if not video_path or not os.path.exists(video_path):
        return 0.0

    mtime = 0
    try:
        mtime = os.path.getmtime(video_path)
        if video_path in _DUR_CACHE:
            cached_mtime, cached_dur = _DUR_CACHE[video_path]
            if cached_mtime == mtime:
                return cached_dur
    except Exception:
        pass

    dur = 0.0
    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0 and frame_count > 0:
                dur = float(frame_count / fps)
    except Exception:
        pass

    # Fallback via ffprobe se OpenCV falhar
    if dur <= 0.0:
        try:
            cmd = [
                FFMPEG_EXE, "-i", video_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            import re
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
            if m:
                hours, mins, secs = m.groups()
                dur = int(hours) * 3600 + int(mins) * 60 + float(secs)
        except Exception:
            pass

    if dur > 0:
        _DUR_CACHE[video_path] = (mtime, dur)
    return dur


def extract_frame_at_timestamp(video_path: str, timestamp_s: float) -> np.ndarray:
    """
    Extrai um frame RGB no segundo exato para prévia visual na interface com cache em memória.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    norm_ts = round(float(timestamp_s), 2)
    cache_key = None
    try:
        mtime = os.path.getmtime(video_path)
        cache_key = (video_path, mtime, norm_ts)
        if cache_key in _FRAME_CACHE:
            return _FRAME_CACHE[cache_key]
    except Exception:
        pass

    frame_rgb = None
    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            target_frame = int(max(0.0, norm_ts) * fps) if fps > 0 else 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame_bgr = cap.read()
            cap.release()
            if ret and frame_bgr is not None:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        pass

    if frame_rgb is not None and cache_key is not None:
        if len(_FRAME_CACHE) > 60:
            _FRAME_CACHE.clear()
        _FRAME_CACHE[cache_key] = frame_rgb

    return frame_rgb


def trim_video(video_path: str, start_s: float, end_s: float, output_path: str = None) -> dict:
    """
    Apara o início e o fim de um vídeo com precisão de milissegundos via FFmpeg.
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Arquivo de vídeo de origem não encontrado."}

    total_dur = get_video_duration(video_path)
    start_s = max(0.0, float(start_s))
    if end_s is None or end_s <= 0 or (total_dur > 0 and end_s > total_dur):
        end_s = total_dur if total_dur > 0 else start_s + 10.0

    if start_s >= end_s:
        return {"path": None, "error": "O tempo de início deve ser menor que o tempo final."}

    duration = end_s - start_s
    if duration < 0.5:
        return {"path": None, "error": "A duração mínima do corte deve ser de pelo menos 0.5 segundos."}

    target_out = output_path
    is_in_place = False
    if not target_out:
        target_out = video_path
        is_in_place = True

    tmp_out = target_out + ".trimmed_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    cmd = [
        FFMPEG_EXE, "-y",
        "-ss", f"{start_s:.3f}",
        "-t", f"{duration:.3f}",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        tmp_out
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if is_in_place and os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.replace(tmp_out, target_out)
        new_dur = get_video_duration(target_out)
        return {"path": target_out, "error": None, "new_duration": new_dur}
    else:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
        err_msg = res.stderr[-1000:] if res.stderr else "Erro desconhecido no FFmpeg ao aparar vídeo."
        return {"path": None, "error": err_msg}


def has_audio_stream(video_path: str) -> bool:
    """Verifica se o vídeo possui faixa de áudio."""
    try:
        cmd = [FFMPEG_EXE, "-i", video_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return "Audio:" in (res.stderr or "")
    except Exception:
        return False


def remove_snippet_and_merge(
    video_path: str,
    remove_start_s: float,
    remove_end_s: float,
    output_path: str = None
) -> dict:
    """
    Remove um trecho do meio do vídeo (ex: gafe, tosse, silêncio longo)
    e junta a Parte 1 e a Parte 2 de forma contínua com sincronia perfeita de áudio.
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Arquivo de vídeo de origem não encontrado."}

    total_dur = get_video_duration(video_path)
    if total_dur <= 1.0:
        return {"path": None, "error": "Vídeo muito curto para remoção de trecho."}

    remove_start_s = max(0.0, float(remove_start_s))
    remove_end_s = min(total_dur, float(remove_end_s))

    if remove_start_s >= remove_end_s:
        return {"path": None, "error": "O início do trecho a remover deve ser menor que o fim."}

    if remove_start_s <= 0.1 and remove_end_s >= total_dur - 0.1:
        return {"path": None, "error": "Não é possível remover a totalidade do vídeo."}

    if remove_start_s <= 0.1:
        return trim_video(video_path, start_s=remove_end_s, end_s=total_dur, output_path=output_path)

    if remove_end_s >= total_dur - 0.1:
        return trim_video(video_path, start_s=0.0, end_s=remove_start_s, output_path=output_path)

    target_out = output_path
    is_in_place = False
    if not target_out:
        target_out = video_path
        is_in_place = True

    tmp_out = target_out + ".merged_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    has_audio = has_audio_stream(video_path)

    if has_audio:
        filter_complex = (
            f"[0:v]trim=start=0:end={remove_start_s:.3f},setpts=PTS-STARTPTS[v1];"
            f"[0:a]atrim=start=0:end={remove_start_s:.3f},asetpts=PTS-STARTPTS[a1];"
            f"[0:v]trim=start={remove_end_s:.3f}:end={total_dur:.3f},setpts=PTS-STARTPTS[v2];"
            f"[0:a]atrim=start={remove_end_s:.3f}:end={total_dur:.3f},asetpts=PTS-STARTPTS[a2];"
            f"[v1][a1][v2][a2]concat=n=2:v=1:a=1[vout][aout]"
        )
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", video_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            tmp_out
        ]
    else:
        filter_complex = (
            f"[0:v]trim=start=0:end={remove_start_s:.3f},setpts=PTS-STARTPTS[v1];"
            f"[0:v]trim=start={remove_end_s:.3f}:end={total_dur:.3f},setpts=PTS-STARTPTS[v2];"
            f"[v1][v2]concat=n=2:v=1:a=0[vout]"
        )
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", video_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            tmp_out
        ]

    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if is_in_place and os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.replace(tmp_out, target_out)
        new_dur = get_video_duration(target_out)
        return {"path": target_out, "error": None, "new_duration": new_dur}
    else:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
        err_msg = res.stderr[-1000:] if res.stderr else "Erro desconhecido no FFmpeg ao remover trecho."
        return {"path": None, "error": err_msg}


def change_video_speed(
    video_path: str,
    speed: float = 1.0,
    output_path: str = None
) -> dict:
    """
    Altera a velocidade de reprodução do vídeo e do áudio de forma proporcional e sincronizada.
    - speed: multiplicador de velocidade (ex: 1.00x a 1.50x, em incrementos de 0.05x).
    - Utiliza o filtro setpts=(1/speed)*PTS para o vídeo e atempo=speed para o áudio (preserva o pitch/tom da voz).
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Arquivo de vídeo de origem não encontrado."}

    try:
        speed = float(speed)
    except (ValueError, TypeError):
        speed = 1.0

    if speed <= 0.05:
        return {"path": None, "error": "A velocidade deve ser maior que 0.05x."}

    total_dur = get_video_duration(video_path)
    if total_dur <= 0.1:
        return {"path": None, "error": "Vídeo inválido ou duração nula."}

    target_out = output_path if output_path else video_path
    is_in_place = not bool(output_path)

    tmp_out = target_out + ".speed_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    has_audio = has_audio_stream(video_path)
    pts_factor = 1.0 / speed

    if has_audio:
        filter_complex = f"[0:v]setpts={pts_factor:.6f}*PTS[v];[0:a]atempo={speed:.4f}[a]"
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", video_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            tmp_out
        ]
    else:
        filter_complex = f"[0:v]setpts={pts_factor:.6f}*PTS[v]"
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", video_path,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            tmp_out
        ]

    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if is_in_place and os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.replace(tmp_out, target_out)
        new_dur = get_video_duration(target_out)
        return {"path": target_out, "error": None, "new_duration": new_dur, "speed": speed}
    else:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
        err_msg = res.stderr[-1000:] if res.stderr else "Erro desconhecido no FFmpeg ao alterar velocidade do vídeo."
        return {"path": None, "error": err_msg}


# ──────────────────────────────────────────────────────────────────────────────
# 🎣 Gancho Viral (Hook / Teaser / Cold Open)
# ──────────────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.join(_SCRIPT_DIR, "fonts")
_FONT_BOLD_PATH = os.path.join(_FONTS_DIR, "Montserrat-ExtraBold.ttf")

HOOK_STYLES = {
    "noir": "🖤 Preto e Branco (Noir Clássico)",
    "vignette_zoom": "🎯 Vinheta Escura + Auto-Zoom (1.10x)",
    "retro": "🎞️ Retrô / Sépia Vintage",
    "flash_forward": "✨ Flash-Forward (Dessaturação 50%)",
    "clean": "🎨 Cores Originais (Sem Filtro)"
}

HOOK_BADGE_PRESETS = [
    "🔥 VEJA O QUE ELE DISSE...",
    "👀 ASSISTA ATÉ O FINAL",
    "⚡ SPOILER / MOMENTO CHAVE",
    "🎙️ MOMENTO TENSO",
    "💥 VEJA O QUE ACONTECEU..."
]

HOOK_TRANSITIONS = {
    "flash_white": "⚡ Flash Branco Cinematográfico",
    "dip_black": "🌑 Fade para Preto",
    "jump_cut": "✂️ Corte Seco (Instantâneo)"
}


def create_hook_badge_image(
    badge_text: str,
    badge_style: str = "red_alert",
    video_width: int = 1080,
    video_height: int = 1920,
    output_png_path: str = None
) -> str:
    """
    Gera uma imagem de badge PNG transparente com texto estilizado de retenção viral.
    Possui suporte a renderização de emojis coloridos via fontes do sistema (ex: Segoe UI Emoji no Windows).
    """
    if not badge_text or not badge_text.strip():
        return None

    import unicodedata
    from PIL import Image, ImageDraw, ImageFont

    clean_text = badge_text.strip()
    font_size = max(18, int(video_width * 0.036))

    font = None
    if os.path.exists(_FONT_BOLD_PATH):
        try:
            font = ImageFont.truetype(_FONT_BOLD_PATH, font_size)
        except Exception:
            pass
    if font is None:
        for fb_f in ["arialbd.ttf", "arial.ttf"]:
            try:
                font = ImageFont.truetype(fb_f, font_size)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    # Procura fonte de emojis do sistema para evitar glifos vazios / [?]
    emoji_font = None
    system_emoji_fonts = [
        "C:/Windows/Fonts/seguiemj.ttf",
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
    ]
    for ef in system_emoji_fonts:
        if os.path.exists(ef):
            try:
                emoji_font = ImageFont.truetype(ef, font_size)
                break
            except Exception:
                pass

    # Medição precisa dividindo caracteres comuns de emojis
    segments = []
    total_w = 0
    max_text_h = font_size
    for ch in clean_text:
        is_em = bool(emoji_font and (ord(ch) >= 0x1F000 or (0x2300 <= ord(ch) <= 0x27BF) or unicodedata.category(ch) in ('So', 'Sk')))
        f = emoji_font if is_em else font
        try:
            bbox = f.getbbox(ch)
            cw = (bbox[2] - bbox[0]) if bbox else int(font_size * 0.5)
            ch_h = (bbox[3] - bbox[1]) if bbox else font_size
        except Exception:
            cw = int(font_size * 0.5)
            ch_h = font_size
        segments.append((ch, is_em, f, cw))
        total_w += cw
        if ch_h > max_text_h:
            max_text_h = ch_h

    pad_x = max(16, int(font_size * 0.75))
    pad_y = max(10, int(font_size * 0.45))

    badge_w = int(total_w + pad_x * 2)
    badge_h = int(max_text_h + pad_y * 2)

    if badge_style == "gold_viral":
        bg_color = (255, 218, 41, 240)
        text_color = (15, 23, 42, 255)
        border_color = (0, 0, 0, 160)
    elif badge_style == "dark_pill":
        bg_color = (15, 23, 42, 230)
        text_color = (255, 255, 255, 255)
        border_color = (139, 92, 246, 220)
    elif badge_style == "neon_cyan":
        bg_color = (6, 182, 212, 235)
        text_color = (15, 23, 42, 255)
        border_color = (255, 255, 255, 200)
    else:  # red_alert
        bg_color = (225, 29, 72, 235)
        text_color = (255, 255, 255, 255)
        border_color = (255, 255, 255, 180)

    badge_img = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge_img)

    radius = max(8, int(badge_h * 0.35))
    draw.rounded_rectangle(
        [0, 0, badge_w - 1, badge_h - 1],
        radius=radius,
        fill=bg_color,
        outline=border_color,
        width=max(1, int(video_width * 0.0025))
    )

    cur_x = pad_x
    cur_y = pad_y - int(font_size * 0.1)
    for ch, is_em, f, cw in segments:
        if is_em:
            try:
                draw.text((cur_x, cur_y), ch, font=f, embedded_color=True)
            except Exception:
                draw.text((cur_x, cur_y), ch, font=f, fill=text_color)
        else:
            draw.text((cur_x, cur_y), ch, font=f, fill=text_color)
        cur_x += cw

    out_file = output_png_path
    if not out_file:
        import tempfile
        t_fd, out_file = tempfile.mkstemp(suffix="_hook_badge.png")
        os.close(t_fd)

    badge_img.save(out_file, format="PNG")
    return out_file


def overlay_badge_on_frame(
    frame_rgb: np.ndarray,
    badge_text: str,
    badge_style: str = "red_alert",
    badge_y_pct: float = 12.0
) -> np.ndarray:
    """
    Sobrepõe o badge estilizado diretamente no frame RGB para pré-visualização instantânea na interface.
    """
    if frame_rgb is None or not badge_text or not badge_text.strip():
        return frame_rgb

    h, w = frame_rgb.shape[:2]
    tmp_png = None
    try:
        import tempfile
        from PIL import Image
        t_fd, tmp_png = tempfile.mkstemp(suffix="_prev_badge.png")
        os.close(t_fd)

        create_hook_badge_image(
            badge_text=badge_text.strip(),
            badge_style=badge_style,
            video_width=w,
            video_height=h,
            output_png_path=tmp_png
        )

        if os.path.exists(tmp_png) and os.path.getsize(tmp_png) > 0:
            badge_pil = Image.open(tmp_png).convert("RGBA")
            bw, bh = badge_pil.size
            bx = max(0, (w - bw) // 2)
            by = max(10, min(h - bh - 10, int(h * (badge_y_pct / 100.0))))

            frame_pil = Image.fromarray(frame_rgb).convert("RGBA")
            frame_pil.paste(badge_pil, (bx, by), mask=badge_pil)
            return np.array(frame_pil.convert("RGB"))
    except Exception:
        pass
    finally:
        if tmp_png and os.path.exists(tmp_png):
            try:
                os.remove(tmp_png)
            except Exception:
                pass

    return frame_rgb


def apply_hook_style_to_frame(frame_rgb: np.ndarray, hook_style: str = "noir") -> np.ndarray:
    """
    Aplica o estilo visual do gancho a um frame isolado para pré-visualização instantânea na UI.
    """
    if frame_rgb is None or not isinstance(frame_rgb, np.ndarray):
        return None

    frame = frame_rgb.copy()
    h, w = frame.shape[:2]

    if hook_style == "noir":
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    elif hook_style == "retro":
        kernel = np.array([
            [0.272, 0.534, 0.131],
            [0.349, 0.686, 0.168],
            [0.393, 0.769, 0.189]
        ])
        sepia = cv2.transform(frame, kernel)
        return np.clip(sepia, 0, 255).astype(np.uint8)

    elif hook_style == "flash_forward":
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[..., 1] *= 0.45
        hsv[..., 2] = np.clip(hsv[..., 2] * 1.15, 0, 255)
        res = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
        return res

    elif hook_style == "vignette_zoom":
        crop_h = int(h / 1.10)
        crop_w = int(w / 1.10)
        y1 = (h - crop_h) // 2
        x1 = (w - crop_w) // 2
        cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        X = cv2.getGaussianKernel(w, w / 2.2)
        Y = cv2.getGaussianKernel(h, h / 2.2)
        kernel = Y * X.T
        mask = kernel / kernel.max()
        vignette = zoomed.astype(np.float32) * mask[..., np.newaxis]
        return np.clip(vignette, 0, 255).astype(np.uint8)

    return frame


def add_viral_hook_to_video(
    video_path: str,
    hook_start_s: float,
    hook_end_s: float,
    hook_style: str = "noir",
    badge_text: str = "",
    badge_style: str = "red_alert",
    badge_y_pct: float = 12.0,
    transition_type: str = "flash_white",
    hook_mode: str = "teaser",
    output_path: str = None
) -> dict:
    """
    Cria e acopla um Gancho Viral (Hook / Teaser) no início do vídeo com estilização visual e badge.
    - hook_mode == 'teaser': (Padrão) O trecho selecionado é duplicado no início como teaser,
      seguido pelo vídeo completo original. Duração total = hook_dur + original_dur.
    - hook_mode == 'move': O trecho selecionado é movido para o início e excluído de sua posição original.
      Duração total = original_dur.
    - badge_y_pct: Posição vertical percentual do topo onde a etiqueta flutuante é renderizada.
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Arquivo de vídeo de origem não encontrado."}

    total_dur = get_video_duration(video_path)
    if total_dur < 1.0:
        return {"path": None, "error": "Vídeo muito curto para criação de gancho."}

    hook_start_s = max(0.0, float(hook_start_s))
    hook_end_s = min(total_dur, float(hook_end_s))

    if hook_start_s >= hook_end_s:
        return {"path": None, "error": "O ponto inicial do gancho deve ser menor que o ponto final."}

    hook_dur = hook_end_s - hook_start_s
    if hook_dur < 0.5:
        return {"path": None, "error": "O gancho viral deve ter pelo menos 0.5 segundos de duração."}

    target_out = output_path if output_path else video_path
    is_in_place = not bool(output_path)

    tmp_out = target_out + ".hook_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    v_w = 1080
    v_h = 1920
    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            cw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            ch = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if cw > 0 and ch > 0:
                v_w, v_h = cw, ch
            cap.release()
    except Exception:
        pass

    badge_png = None
    if badge_text and badge_text.strip():
        badge_png = os.path.join(os.path.dirname(os.path.abspath(target_out)), f"_tmp_hook_badge_{os.getpid()}.png")
        create_hook_badge_image(
            badge_text=badge_text.strip(),
            badge_style=badge_style,
            video_width=v_w,
            video_height=v_h,
            output_png_path=badge_png
        )

    has_audio = has_audio_stream(video_path)

    hook_vf_list = [f"trim=start={hook_start_s:.3f}:end={hook_end_s:.3f}", "setpts=PTS-STARTPTS"]

    if hook_style == "noir":
        hook_vf_list.append("hue=s=0")
    elif hook_style == "vignette_zoom":
        scale_w = int(v_w * 1.10)
        scale_h = int(v_h * 1.10)
        if scale_w % 2 != 0: scale_w += 1
        if scale_h % 2 != 0: scale_h += 1
        hook_vf_list.append(f"scale={scale_w}:{scale_h}")
        hook_vf_list.append(f"crop={v_w}:{v_h}")
        hook_vf_list.append("vignette=PI/4")
    elif hook_style == "retro":
        hook_vf_list.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
    elif hook_style == "flash_forward":
        hook_vf_list.append("eq=saturation=0.45:contrast=1.2:brightness=0.03")

    if transition_type == "flash_white":
        fade_d = min(0.24, max(0.12, hook_dur * 0.08))
        fade_st = max(0.0, hook_dur - fade_d)
        hook_vf_list.append(f"fade=t=out:st={fade_st:.3f}:d={fade_d:.3f}:color=white")
    elif transition_type == "dip_black":
        fade_d = min(0.20, max(0.10, hook_dur * 0.08))
        fade_st = max(0.0, hook_dur - fade_d)
        hook_vf_list.append(f"fade=t=out:st={fade_st:.3f}:d={fade_d:.3f}:color=black")

    hook_vf_str = ",".join(hook_vf_list)
    filter_parts = []

    if badge_png and os.path.exists(badge_png):
        filter_parts.append(f"[0:v]{hook_vf_str}[v_hook_raw]")
        badge_y = max(20, min(v_h - 60, int(v_h * (float(badge_y_pct) / 100.0))))
        filter_parts.append(f"[v_hook_raw][1:v]overlay=(W-w)/2:{badge_y}:enable='between(t,0,{hook_dur:.3f})'[v_hook]")
    else:
        filter_parts.append(f"[0:v]{hook_vf_str}[v_hook]")

    if has_audio:
        aud_fade_d = min(0.05, hook_dur * 0.05)
        aud_fade_st = max(0.0, hook_dur - aud_fade_d)
        filter_parts.append(f"[0:a]atrim=start={hook_start_s:.3f}:end={hook_end_s:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={aud_fade_st:.3f}:d={aud_fade_d:.3f}[a_hook]")

    if hook_mode == "move":
        p1_dur = hook_start_s
        p2_dur = total_dur - hook_end_s

        concat_v_tags = ["[v_hook]"]
        concat_a_tags = ["[a_hook]"] if has_audio else []
        concat_n = 1

        if p1_dur > 0.1:
            filter_parts.append(f"[0:v]trim=start=0:end={hook_start_s:.3f},setpts=PTS-STARTPTS[v_p1]")
            concat_v_tags.append("[v_p1]")
            if has_audio:
                filter_parts.append(f"[0:a]atrim=start=0:end={hook_start_s:.3f},asetpts=PTS-STARTPTS[a_p1]")
                concat_a_tags.append("[a_p1]")
            concat_n += 1

        if p2_dur > 0.1:
            filter_parts.append(f"[0:v]trim=start={hook_end_s:.3f}:end={total_dur:.3f},setpts=PTS-STARTPTS[v_p2]")
            concat_v_tags.append("[v_p2]")
            if has_audio:
                filter_parts.append(f"[0:a]atrim=start={hook_end_s:.3f}:end={total_dur:.3f},asetpts=PTS-STARTPTS[a_p2]")
                concat_a_tags.append("[a_p2]")
            concat_n += 1

        if has_audio:
            concat_inputs = "".join([f"{v}{a}" for v, a in zip(concat_v_tags, concat_a_tags)])
            filter_parts.append(f"{concat_inputs}concat=n={concat_n}:v=1:a=1[vout][aout]")
        else:
            concat_inputs = "".join(concat_v_tags)
            filter_parts.append(f"{concat_inputs}concat=n={concat_n}:v=1:a=0[vout]")

    else:
        # Modo Teaser (Duplica trecho no início)
        filter_parts.append(f"[0:v]trim=start=0:end={total_dur:.3f},setpts=PTS-STARTPTS[v_main]")
        if has_audio:
            filter_parts.append(f"[0:a]atrim=start=0:end={total_dur:.3f},asetpts=PTS-STARTPTS[a_main]")
            filter_parts.append("[v_hook][a_hook][v_main][a_main]concat=n=2:v=1:a=1[vout][aout]")
        else:
            filter_parts.append("[v_hook][v_main]concat=n=2:v=1:a=0[vout]")

    full_filter_complex = ";".join(filter_parts)

    cmd = [
        FFMPEG_EXE, "-y",
        "-i", video_path
    ]
    if badge_png and os.path.exists(badge_png):
        cmd.extend(["-i", badge_png])

    cmd.extend([
        "-filter_complex", full_filter_complex,
        "-map", "[vout]"
    ])
    if has_audio:
        cmd.extend([
            "-map", "[aout]",
            "-c:a", "aac",
            "-b:a", "192k"
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        tmp_out
    ])

    res = subprocess.run(cmd, capture_output=True, text=True)

    if badge_png and os.path.exists(badge_png):
        try:
            os.remove(badge_png)
        except Exception:
            pass

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if is_in_place and os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.replace(tmp_out, target_out)
        new_dur = get_video_duration(target_out)
        return {
            "path": target_out,
            "error": None,
            "new_duration": new_dur,
            "hook_duration": hook_dur,
            "hook_start": hook_start_s,
            "hook_end": hook_end_s,
            "style": hook_style,
            "mode": hook_mode,
            "badge_y_pct": badge_y_pct
        }
    else:
        if os.path.exists(tmp_out):
            try:
                os.remove(tmp_out)
            except Exception:
                pass
        err_msg = res.stderr[-1200:] if res.stderr else "Erro desconhecido no FFmpeg ao aplicar gancho viral."
        return {"path": None, "error": err_msg}


# ──────────────────────────────────────────────────────────────────────────────
# Histórico de Ajustes e Sinalização de Conclusão da Edição Rápida
# ──────────────────────────────────────────────────────────────────────────────

EDIT_LOG_FILENAME = "historico_edicoes.json"


def get_edit_history_path(video_path: str) -> str:
    """
    Retorna o caminho do arquivo de histórico de edições do vídeo.
    Salva no mesmo diretório do arquivo de vídeo.
    """
    if not video_path:
        return None
    v_dir = os.path.dirname(video_path)
    if not v_dir:
        v_dir = "."
    return os.path.join(v_dir, EDIT_LOG_FILENAME)


def load_edit_history(video_path: str) -> list:
    """
    Carrega a lista de edições já realizadas neste vídeo.
    """
    log_p = get_edit_history_path(video_path)
    if log_p and os.path.exists(log_p):
        try:
            import json
            with open(log_p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def record_quick_edit(
    video_path: str,
    action_name: str,
    details: str,
    output_path: str = None,
    extra_info: dict = None
) -> dict:
    """
    Registra um novo ajuste de edição rápida no histórico persistente do vídeo.
    Retorna a entrada registrada.
    """
    log_p = get_edit_history_path(video_path)
    if not log_p:
        return {}

    import datetime
    import json

    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    target_out = output_path if output_path else video_path
    is_new_version = bool(output_path and os.path.abspath(output_path) != os.path.abspath(video_path))

    entry = {
        "timestamp": now_str,
        "action": action_name,
        "details": details,
        "source_file": os.path.basename(video_path),
        "output_file": os.path.basename(target_out),
        "output_path": target_out,
        "mode": "Nova Versão" if is_new_version else "Substituição Direta",
        "extra_info": extra_info or {}
    }

    history = load_edit_history(video_path)
    history.insert(0, entry)  # Mais recente no topo

    try:
        os.makedirs(os.path.dirname(log_p), exist_ok=True)
        with open(log_p, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    _VERSIONS_CACHE.clear()
    return entry


def list_edited_video_versions(video_path: str) -> list:
    """
    Lista todos os arquivos de vídeo (.mp4) no diretório do corte,
    diferenciando o arquivo principal de versões editadas secundárias.
    """
    if not video_path:
        return []

    v_dir = os.path.dirname(video_path)
    if not v_dir or not os.path.exists(v_dir):
        return []

    dir_mtime = 0
    cache_key = None
    try:
        dir_mtime = os.path.getmtime(v_dir)
        cache_key = (os.path.abspath(v_dir), os.path.basename(video_path), dir_mtime)
        if cache_key in _VERSIONS_CACHE:
            return _VERSIONS_CACHE[cache_key]
    except Exception:
        pass

    base_name = os.path.basename(video_path)
    # Tenta identificar o nome do vídeo principal (sem sufixos de edição rápida)
    main_name = base_name
    for suf in ["_speed_", "_editado", "_com_banner", "_com_headline", "_audio_equalizado", "_trimmed", "_snipped"]:
        if suf in main_name:
            # Encontra o prefixo antes do sufixo
            prefix = main_name.split(suf)[0]
            if prefix:
                possible_main = f"{prefix}.mp4"
                if os.path.exists(os.path.join(v_dir, possible_main)):
                    main_name = possible_main
                    break

    versions = []
    try:
        import datetime
        for f in os.listdir(v_dir):
            if f.lower().endswith(".mp4") and not f.endswith("_tmp.mp4") and not f.startswith("temp"):
                f_path = os.path.join(v_dir, f)
                if os.path.isfile(f_path):
                    sz_mb = round(os.path.getsize(f_path) / (1024 * 1024), 2)
                    dur = get_video_duration(f_path)
                    mtime = os.path.getmtime(f_path)
                    mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
                    is_main = (f == main_name) or (f == "corte_1080p.mp4") or (f == base_name and not any(s in f for s in ["_speed_", "_editado", "_com_banner", "_com_headline", "_audio_equalizado"]))
                    versions.append({
                        "filename": f,
                        "path": f_path,
                        "size_mb": sz_mb,
                        "duration": dur,
                        "is_main": is_main,
                        "timestamp": mtime_str
                    })
    except Exception:
        pass

    if cache_key is not None:
        if len(_VERSIONS_CACHE) > 100:
            _VERSIONS_CACHE.clear()
        _VERSIONS_CACHE[cache_key] = versions

    return versions


def delete_edited_video_version(file_path: str, base_video_path: str = None) -> dict:
    """
    Deleta com segurança um arquivo de vídeo editado do disco e limpa
    suas referências no histórico de edições (historico_edicoes.json).
    """
    if not file_path:
        return {"success": False, "error": "Caminho do arquivo não fornecido."}

    v_path = os.path.abspath(file_path)
    ref_dir = os.path.dirname(v_path)
    filename = os.path.basename(v_path)

    # 1. Remove arquivo do disco
    if os.path.exists(v_path):
        try:
            os.remove(v_path)
        except Exception as e:
            return {"success": False, "error": f"Não foi possível remover o arquivo: {str(e)}"}
    else:
        return {"success": False, "error": "Arquivo não encontrado no disco."}

    # 2. Limpa caches em memória
    if file_path in _DUR_CACHE:
        _DUR_CACHE.pop(file_path, None)
    if v_path in _DUR_CACHE:
        _DUR_CACHE.pop(v_path, None)
    _VERSIONS_CACHE.clear()

    # 3. Limpa do historico_edicoes.json
    log_p = os.path.join(ref_dir, EDIT_LOG_FILENAME)
    if os.path.exists(log_p):
        try:
            with open(log_p, "r", encoding="utf-8") as f:
                history = json.load(f)
            if isinstance(history, list):
                # Remove entradas referentes a este arquivo
                filtered_h = [h for h in history if h.get("output_file") != filename and h.get("output_path") != file_path and h.get("output_path") != v_path]
                if len(filtered_h) != len(history):
                    with open(log_p, "w", encoding="utf-8") as f:
                        json.dump(filtered_h, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {"success": True, "error": None, "deleted_file": filename}


def cleanup_all_edited_versions(video_path: str, keep_path: str = None) -> dict:
    """
    Remove todas as versões editadas secundárias de uma pasta, mantendo apenas
    o arquivo em `keep_path` ou o vídeo principal original.
    """
    if not video_path:
        return {"success": False, "error": "Caminho não fornecido.", "deleted_count": 0}

    v_dir = os.path.dirname(video_path)
    if not v_dir or not os.path.exists(v_dir):
        return {"success": False, "error": "Diretório não encontrado.", "deleted_count": 0}

    keep_abs = os.path.abspath(keep_path) if keep_path else None
    versions = list_edited_video_versions(video_path)
    deleted_files = []

    for v in versions:
        f_abs = os.path.abspath(v["path"])
        # Se for o arquivo a manter ou o vídeo principal canônico (quando não há keep_path), não deleta
        if keep_abs and f_abs == keep_abs:
            continue
        if not keep_abs and v.get("is_main"):
            continue
        if v.get("is_main") and keep_abs and f_abs != keep_abs:
            # Não deleta o principal a menos que seja explicitamente solicitado
            continue

        res = delete_edited_video_version(f_abs)
        if res.get("success"):
            deleted_files.append(v["filename"])

    return {
        "success": True,
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files
    }
