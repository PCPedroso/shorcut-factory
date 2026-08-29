"""
audio_processor.py — Motor de Equalização, De-Clipping e Nivelamento Dinâmico de Áudio (Pós-Corte)
Permite tratar áudios estourados em microfones, nivelar a voz com a torcida/som ambiente,
remover estridência e normalizar conforme padrões de transmissão e redes sociais.
"""

import os
import subprocess
import tempfile
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

AUDIO_EQUALIZER_PRESETS = {
    "anti_clipping_crowd": {
        "name": "🏆 Anti-Estouro & Destaque de Voz + Torcida/Ambiente (Recomendado)",
        "description": "Recupera microfones saturados/estourados sem perder a energia da torcida e do som ambiente nos momentos de vibração.",
        "highpass_hz": 75,
        "dynaudnorm_enabled": True,
        "dynaudnorm_framelen": 150,
        "dynaudnorm_maxgain": 15,
        "deharsh_eq_db": -3.5,
        "limiter_limit_db": -1.2,
        "volume_gain_db": 0.0,
        "denoise_enabled": False
    },
    "speech_clarity_podcast": {
        "name": "🎙️ Clareza de Voz & Podcast (Estúdio Broadcast)",
        "description": "Elimina ruídos de baixa frequência, realça a presença da voz e garante volume constante e cristalino.",
        "highpass_hz": 85,
        "dynaudnorm_enabled": True,
        "dynaudnorm_framelen": 200,
        "dynaudnorm_maxgain": 10,
        "deharsh_eq_db": -2.0,
        "limiter_limit_db": -1.0,
        "volume_gain_db": 0.0,
        "denoise_enabled": False
    },
    "declip_gentle": {
        "name": "🛡️ De-Clipper & Redutor de Saturação Suave",
        "description": "Foco cirúrgico em des-saturar o microfone e suavizar picos sem alterar a dinâmica do som original.",
        "highpass_hz": 60,
        "dynaudnorm_enabled": False,
        "dynaudnorm_framelen": 150,
        "dynaudnorm_maxgain": 10,
        "deharsh_eq_db": -4.0,
        "limiter_limit_db": -1.5,
        "volume_gain_db": 0.0,
        "denoise_enabled": False
    },
    "aggressive_leveler": {
        "name": "📢 Nivelador Dinâmico Agressivo (Volume Super Uniforme)",
        "description": "Equilíbrio total entre falas sussurradas e gritos no microfone. Ideal para gravações de rua com grande variação.",
        "highpass_hz": 80,
        "dynaudnorm_enabled": True,
        "dynaudnorm_framelen": 100,
        "dynaudnorm_maxgain": 22,
        "deharsh_eq_db": -3.0,
        "limiter_limit_db": -1.0,
        "volume_gain_db": 1.0,
        "denoise_enabled": False
    },
    "social_loudnorm": {
        "name": "📱 Normalização Padrão Redes Sociais (-14 LUFS / EBU R128)",
        "description": "Ajusta o volume percebido para a meta oficial do TikTok, Instagram Reels e YouTube Shorts.",
        "highpass_hz": 60,
        "dynaudnorm_enabled": False,
        "dynaudnorm_framelen": 150,
        "dynaudnorm_maxgain": 10,
        "deharsh_eq_db": 0.0,
        "limiter_limit_db": -1.0,
        "volume_gain_db": 0.0,
        "denoise_enabled": False,
        "use_loudnorm": True
    },
    "custom": {
        "name": "🎛️ Personalizado (Controle Manual Total)",
        "description": "Permite ajustar individualmente corte de graves, atenuação de agudos, nivelador e limiter.",
        "highpass_hz": 75,
        "dynaudnorm_enabled": True,
        "dynaudnorm_framelen": 150,
        "dynaudnorm_maxgain": 15,
        "deharsh_eq_db": -3.0,
        "limiter_limit_db": -1.2,
        "volume_gain_db": 0.0,
        "denoise_enabled": False
    }
}


def build_audio_filter_string(config: dict) -> str:
    """
    Constrói a cadeia de filtros de áudio do FFmpeg com base na configuração.
    """
    config = config or {}
    preset_key = config.get("preset_key", "anti_clipping_crowd")
    preset = AUDIO_EQUALIZER_PRESETS.get(preset_key, AUDIO_EQUALIZER_PRESETS["anti_clipping_crowd"])

    if preset.get("use_loudnorm") and preset_key != "custom":
        return "highpass=f=65,loudnorm=I=-14:TP=-1.5:LRA=11"

    highpass_hz = int(config.get("highpass_hz", preset.get("highpass_hz", 75)))
    dynaudnorm_enabled = bool(config.get("dynaudnorm_enabled", preset.get("dynaudnorm_enabled", True)))
    dynaudnorm_framelen = int(config.get("dynaudnorm_framelen", preset.get("dynaudnorm_framelen", 150)))
    dynaudnorm_maxgain = int(config.get("dynaudnorm_maxgain", preset.get("dynaudnorm_maxgain", 15)))
    deharsh_eq_db = float(config.get("deharsh_eq_db", preset.get("deharsh_eq_db", -3.5)))
    limiter_limit_db = float(config.get("limiter_limit_db", preset.get("limiter_limit_db", -1.2)))
    volume_gain_db = float(config.get("volume_gain_db", preset.get("volume_gain_db", 0.0)))
    denoise_enabled = bool(config.get("denoise_enabled", preset.get("denoise_enabled", False)))

    filters = []

    # 1. Filtro High-Pass (Corte de rumbles / ventos graves)
    if highpass_hz > 20:
        filters.append(f"highpass=f={highpass_hz}")

    # 2. Redução de Ruído de Fundo (se ativado)
    if denoise_enabled:
        filters.append("afftdn=nf=-25")

    # 3. Nivelador Dinâmico (Dynamic Audio Normalizer - eleva som de fundo/torcida e controla falas muito altas)
    if dynaudnorm_enabled:
        filters.append(f"dynaudnorm=f={dynaudnorm_framelen}:g={dynaudnorm_maxgain}:m=10:s=3")

    # 4. De-Harshing / Atenuação de Frequências Estridentes do Microfone (3.2 kHz)
    if abs(deharsh_eq_db) > 0.1:
        filters.append(f"equalizer=f=3200:t=q:w=1.2:g={deharsh_eq_db:.1f}")

    # 5. Ganho Geral de Volume
    if abs(volume_gain_db) > 0.1:
        filters.append(f"volume={volume_gain_db:+.1f}dB")

    # 6. Brickwall Peak Limiter / Anti-Clipping (Impede qualquer distorção no teto de saída)
    # limit em escala linear (ex: -1.2 dB = ~0.87)
    linear_limit = round(10.0 ** (limiter_limit_db / 20.0), 3)
    linear_limit = max(0.5, min(0.98, linear_limit))
    filters.append(f"alimiter=limit={linear_limit}:attack=5:release=50:asc=1")

    return ",".join(filters) if filters else "anull"


def equalize_video_audio(
    video_path: str,
    config: dict,
    output_path: str = None
) -> dict:
    """
    Equaliza e trata a faixa de áudio de um vídeo existente sem re-encodar o vídeo (Stream Copy em ~1s).
    """
    if not video_path or not os.path.exists(video_path):
        return {"path": None, "error": "Vídeo de origem não encontrado."}

    af_filter = build_audio_filter_string(config)

    target_out = output_path
    if not target_out:
        target_out = video_path

    tmp_out = target_out + ".eq_tmp.mp4"
    if os.path.exists(tmp_out):
        try:
            os.remove(tmp_out)
        except Exception:
            pass

    cmd = [
        FFMPEG_EXE, "-y",
        "-i", video_path,
        "-af", af_filter,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        tmp_out
    ]

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if res.returncode == 0 and os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 0:
        if os.path.exists(target_out):
            try:
                os.remove(target_out)
            except Exception:
                pass
        os.rename(tmp_out, target_out)
        return {"path": target_out, "error": None}
    else:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)
        err = res.stderr.decode("utf-8", errors="replace") if res.stderr else "Erro desconhecido"
        return {"path": None, "error": f"Falha na equalização de áudio:\n{err[-1200:]}"}


def generate_audio_preview_sample(
    video_path: str,
    config: dict,
    max_duration_s: float = 45.0
) -> str:
    """
    Gera uma amostra de áudio (AAC/MP3) com os filtros aplicados para prévia imediata no Streamlit.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    af_filter = build_audio_filter_string(config)
    v_dir = os.path.dirname(video_path) or tempfile.gettempdir()
    preview_audio_p = os.path.join(v_dir, f"preview_eq_{os.path.basename(video_path)}.m4a")

    if os.path.exists(preview_audio_p):
        try:
            os.remove(preview_audio_p)
        except Exception:
            pass

    cmd = [
        FFMPEG_EXE, "-y",
        "-t", str(float(max_duration_s)),
        "-i", video_path,
        "-af", af_filter,
        "-vn",
        "-c:a", "aac",
        "-b:a", "192k",
        preview_audio_p
    ]

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    if res.returncode == 0 and os.path.exists(preview_audio_p) and os.path.getsize(preview_audio_p) > 0:
        return preview_audio_p
    return None
