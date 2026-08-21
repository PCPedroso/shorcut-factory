"""
audio_mixer.py — Gerenciamento de Trilhas Sonoras de Fundo & Audio Ducking Inteligente via FFmpeg
Ajusta dinamicamente o volume da música de fundo para diminuir suavemente quando a pessoa fala
e subir com presença nos silêncios/pausas.
"""

import os
import math
import wave
import struct
import subprocess
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_AUDIO_DIR = os.path.join(PROJECT_ROOT, "assets", "audio")

# Categorias de Trilhas Padrão
MUSIC_CATEGORIES = {
    "lofi_chill": {
        "title": "🧘 Lo-Fi Chill / Relax",
        "filename": "lofi_chill.wav",
        "description": "Ideal para conversas reflexivas, estudos e tecnologia",
        "base_bpm": 80,
    },
    "dynamic_pulse": {
        "title": "⚡ Dinâmica / Ritmo",
        "filename": "dynamic_pulse.wav",
        "description": "Batida moderna e acelerada para dicas rápidas e vendas",
        "base_bpm": 120,
    },
    "tension_suspense": {
        "title": "🔥 Tensão / Suspense",
        "filename": "tension_suspense.wav",
        "description": "Clima de mistério, curiosidade e revelações",
        "base_bpm": 70,
    },
    "inspirational_epic": {
        "title": "✨ Inspiracional / Motivacional",
        "filename": "inspirational_epic.wav",
        "description": "Harmonia expansiva para discursos, superação e negócios",
        "base_bpm": 90,
    },
}

DUCKING_PRESETS = {
    "suave": {
        "name": "Suave (-12dB)",
        "threshold": "0.12",
        "ratio": "3",
        "attack": "40",
        "release": "400",
    },
    "medio": {
        "name": "Médio / Padrão (-18dB)",
        "threshold": "0.08",
        "ratio": "5",
        "attack": "30",
        "release": "300",
    },
    "intenso": {
        "name": "Intenso (-24dB)",
        "threshold": "0.04",
        "ratio": "8",
        "attack": "20",
        "release": "200",
    },
}


def _generate_synthetic_track(filepath: str, style: str, duration_sec: int = 45):
    """
    Gera trilhas musicais harmônicas sintetizadas em PCM WAV caso o usuário
    não tenha adicionado seus próprios arquivos MP3/WAV.
    Cria progressões de acordes agradáveis e batidas rítmicas royalty-free.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 5000:
        return

    sample_rate = 44100
    total_samples = int(sample_rate * duration_sec)
    
    # Progressões de acordes (Frequências em Hz)
    if style == "lofi_chill":
        # Acordes Cmaj7 -> Am7 -> Dm7 -> G7
        chords = [
            [261.63, 329.63, 392.00, 493.88],  # Cmaj7
            [220.00, 261.63, 329.63, 392.00],  # Am7
            [293.66, 349.23, 440.00, 523.25],  # Dm7
            [196.00, 246.94, 293.66, 349.23],  # G7
        ]
        chord_len = 3.0
    elif style == "tension_suspense":
        # Dó menor tenso com intervalo de trítono
        chords = [
            [130.81, 155.56, 196.00, 277.18],
            [123.47, 146.83, 185.00, 261.63],
            [116.54, 138.59, 174.61, 246.94],
            [130.81, 155.56, 196.00, 261.63],
        ]
        chord_len = 3.5
    elif style == "inspirational_epic":
        # Progressão Épica: F -> G -> Am -> Em
        chords = [
            [174.61, 220.00, 261.63, 349.23],
            [196.00, 246.94, 293.66, 392.00],
            [220.00, 261.63, 329.63, 440.00],
            [164.81, 196.00, 246.94, 329.63],
        ]
        chord_len = 2.5
    else:  # dynamic_pulse
        # Ritmo pulsante em Ré Menor
        chords = [
            [146.83, 220.00, 293.66, 349.23],
            [174.61, 261.63, 349.23, 440.00],
            [196.00, 293.66, 392.00, 493.88],
            [146.83, 220.00, 293.66, 440.00],
        ]
        chord_len = 2.0

    samples = []
    for i in range(total_samples):
        t = i / sample_rate
        chord_idx = int((t / chord_len) % len(chords))
        current_chord = chords[chord_idx]
        
        # Síntese aditiva suave com envelope harmônico
        val = 0.0
        for note_f in current_chord:
            val += math.sin(2.0 * math.pi * note_f * t) * 0.18
            # Sub-harmônico suave (baixo quente)
            val += math.sin(math.pi * note_f * t) * 0.12

        # Pulso rítmico suave (beat sutil a cada 0.5s)
        beat_t = t % 0.5
        beat_env = math.exp(-beat_t * 8.0) * 0.15
        val += math.sin(2.0 * math.pi * 65.0 * t) * beat_env
        
        # Limiter suave
        val = max(-0.95, min(0.95, val))
        samples.append(int(val * 32767.0))

    with wave.open(filepath, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono para leveza
        wav_file.setsampwidth(2)  # 16 bits
        wav_file.setframerate(sample_rate)
        packed_data = struct.pack(f"<{len(samples)}h", *samples)
        wav_file.writeframes(packed_data)


def ensure_default_tracks():
    """Garante que todas as trilhas pré-configuradas existam no diretório de assets."""
    os.makedirs(ASSETS_AUDIO_DIR, exist_ok=True)
    for key, info in MUSIC_CATEGORIES.items():
        track_path = os.path.join(ASSETS_AUDIO_DIR, info["filename"])
        if not os.path.exists(track_path):
            try:
                _generate_synthetic_track(track_path, key, duration_sec=45)
            except Exception:
                pass


def list_available_tracks() -> list:
    """
    Retorna lista de todas as trilhas disponíveis (embutidas + arquivos customizados na pasta).
    """
    ensure_default_tracks()
    tracks = []
    
    # 1. Adiciona as categorias mapeadas
    for key, info in MUSIC_CATEGORIES.items():
        fpath = os.path.join(ASSETS_AUDIO_DIR, info["filename"])
        tracks.append({
            "id": key,
            "title": info["title"],
            "description": info["description"],
            "path": fpath,
            "is_builtin": True
        })
        
    # 2. Adiciona quaisquer arquivos MP3/WAV extras adicionados pelo usuário
    if os.path.exists(ASSETS_AUDIO_DIR):
        for f in os.listdir(ASSETS_AUDIO_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in [".mp3", ".wav", ".m4a", ".aac"]:
                # Verifica se não é um dos built-in
                if not any(f == info["filename"] for info in MUSIC_CATEGORIES.values()):
                    fpath = os.path.join(ASSETS_AUDIO_DIR, f)
                    tracks.append({
                        "id": f,
                        "title": f"🎵 {f}",
                        "description": "Trilha personalizada do usuário",
                        "path": fpath,
                        "is_builtin": False
                    })
                    
    return tracks


def apply_audio_ducking(
    input_video_path: str,
    output_video_path: str,
    music_track_path: str,
    music_volume: float = 0.15,
    ducking_preset: str = "medio",
) -> dict:
    """
    Aplica trilha sonora de fundo com Audio Ducking profissional via FFmpeg.
    A música é atenuada dinamicamente com sidechaincompress quando a voz do vídeo está ativa.
    """
    if not os.path.exists(input_video_path):
        return {"path": None, "error": f"Vídeo de entrada não encontrado: {input_video_path}"}
    
    if not os.path.exists(music_track_path):
        return {"path": input_video_path, "error": None, "warning": "Trilha de áudio não encontrada. Áudio original mantido."}
    
    preset = DUCKING_PRESETS.get(ducking_preset, DUCKING_PRESETS["medio"])
    threshold = preset["threshold"]
    ratio = preset["ratio"]
    attack = preset["attack"]
    release = preset["release"]
    
    # Prepara caminhos temporários
    tmp_output = output_video_path.replace(".mp4", "_ducking_tmp.mp4")
    if tmp_output == output_video_path:
        tmp_output = output_video_path + ".tmp.mp4"
        
    try:
        # Monta filtro de áudio:
        # 1. Loop infinito da música de fundo + ajuste de volume base
        # 2. Sidechaincompress na música usando a faixa de voz [0:a] como trigger
        # 3. Mixagem do áudio da voz limpo com a música ducked
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e+09,volume={music_volume}[bg];"
            f"[bg][0:a]sidechaincompress=threshold={threshold}:ratio={ratio}:attack={attack}:release={release}[ducked_bg];"
            f"[0:a][ducked_bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", input_video_path,
            "-i", music_track_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            tmp_output
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(tmp_output) and os.path.getsize(tmp_output) > 0:
            if os.path.exists(output_video_path):
                os.remove(output_video_path)
            os.rename(tmp_output, output_video_path)
            return {"path": output_video_path, "error": None}
        else:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            err = result.stderr[-1000:] if result.stderr else "Erro desconhecido no ducking FFmpeg"
            return {"path": input_video_path, "error": None, "warning": f"Audio ducking falhou, vídeo original mantido: {err}"}
            
    except Exception as exc:
        if os.path.exists(tmp_output):
            os.remove(tmp_output)
        return {"path": input_video_path, "error": None, "warning": str(exc)}
