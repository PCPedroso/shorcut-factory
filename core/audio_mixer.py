"""
audio_mixer.py — Gerenciamento de Trilhas Sonoras de Fundo & Audio Ducking Inteligente via FFmpeg
Ajusta dinamicamente o volume da música de fundo para diminuir suavemente quando a pessoa fala
e subir com presença nos silêncios/pausas.
"""

import os
import re
import json
import shutil
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
# Categorias de Trilhas Padrão
MUSIC_CATEGORIES = {
    "phonk_power_override": {
        "title": "⚡ Phonk Agressivo / Sigma (Superação & Força)",
        "filename": "phonk_power_override.wav",
        "description": "Grave 808 pesado, cowbells distorcidos e batida acelerada para extrema força e foco",
        "base_bpm": 135,
    },
    "heavy_rock_overdrive": {
        "title": "🎸 Heavy Rock / Overdrive (Adrenalina & Atitude)",
        "filename": "heavy_rock_overdrive.wav",
        "description": "Riffs pesados com distorção de guitarra e ritmo agressivo para impacto forte",
        "base_bpm": 130,
    },
    "comedy_meme_funny": {
        "title": "🎭 Cômico / Meme & Humor (Gafes & Situações Engraçadas)",
        "filename": "comedy_meme_funny.wav",
        "description": "Melodia saltitante, efeitos cartoon e clima divertido para momentos hilários",
        "base_bpm": 115,
    },
    "epic_hype_glory": {
        "title": "🏆 Épico / Glória & Vitória (Conquista & Inspiração)",
        "filename": "epic_hype_glory.wav",
        "description": "Orquestra imponente e percussão de cinema para discursos grandiosos",
        "base_bpm": 95,
    },
    "lofi_chill": {
        "title": "🧘 Lo-Fi Chill / Relax",
        "filename": "lofi_chill.wav",
        "description": "Ideal para conversas reflexivas, estudos e tecnologia",
        "base_bpm": 80,
    },
    "dynamic_pulse": {
        "title": "⚡ Dinâmica / Ritmo Moderno",
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
        "title": "✨ Inspiracional / Motivacional Suave",
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
    
    samples = []
    
    if style == "phonk_power_override":
        # ⚡ PHONK AGRESSIVO: 808 pesado + Cowbell Memphis + Hi-Hats rápidos
        cowbell_melody = [739.99, 880.00, 830.61, 659.25, 739.99, 1108.73, 987.77, 739.99]
        step_len = 0.222  # ~135 BPM 8th notes
        for i in range(total_samples):
            t = i / sample_rate
            step_idx = int((t / step_len) % len(cowbell_melody))
            note_f = cowbell_melody[step_idx]
            dt = t % step_len
            
            # Cowbell metálico com decay rápido
            cb_env = math.exp(-dt * 14.0)
            cb_val = (math.sin(2.0 * math.pi * note_f * t) + 0.45 * math.sin(2.0 * math.pi * note_f * 2.4 * t)) * cb_env * 0.35
            
            # Sub-Bass 808 potente (46.25 Hz em F#) com leve saturação
            bass_env = 0.85 + 0.15 * math.sin(2.0 * math.pi * 0.5 * t)
            bass_val = math.sin(2.0 * math.pi * 46.25 * t) * 0.42 * bass_env
            # Adiciona punch no início de cada compasso (0.888s)
            punch_t = t % 0.888
            punch_env = math.exp(-punch_t * 9.0) * 0.30
            bass_val += math.sin(2.0 * math.pi * 58.0 * t) * punch_env
            
            # Hi-hat rápido (ruído com decay curto)
            hh_t = t % 0.111
            hh_env = math.exp(-hh_t * 45.0)
            hh_val = math.sin(2.0 * math.pi * 8500.0 * t) * hh_env * 0.08
            
            raw_v = cb_val + bass_val + hh_val
            # Distorção harmônica suave (clip phonk)
            val = math.tanh(raw_v * 1.6) * 0.90
            samples.append(int(val * 32767.0))

    elif style == "heavy_rock_overdrive":
        # 🎸 HEAVY ROCK / OVERDRIVE: Power chords distorcidos (E5, G5, A5) + Bateria agressiva
        riffs = [
            [82.41, 123.47, 164.81],   # E5
            [98.00, 146.83, 196.00],   # G5
            [110.00, 164.81, 220.00],  # A5
            [82.41, 123.47, 164.81],   # E5
        ]
        riff_len = 1.846  # ~130 BPM
        for i in range(total_samples):
            t = i / sample_rate
            riff_idx = int((t / riff_len) % len(riffs))
            chord = riffs[riff_idx]
            
            # Guitarra com Drive / Overdrive
            g_raw = 0.0
            for nf in chord:
                g_raw += math.sin(2.0 * math.pi * nf * t) * 0.22
                g_raw += math.sin(2.0 * math.pi * (nf * 2.0) * t) * 0.12
                g_raw += math.sin(2.0 * math.pi * (nf * 3.0) * t) * 0.06
            # Distorção de amplificador overdrive
            g_dist = math.tanh(g_raw * 2.8) * 0.55
            
            # Bateria Rock: Bumbo no tempo 1 e 3, Caixa no tempo 2 e 4
            beat_cycle = t % (60.0 / 130.0 * 2.0) # Ciclo de 2 tempos (~0.923s)
            # Kick (bumbo forte)
            kick_t = beat_cycle % 0.4615
            if beat_cycle < 0.4615:
                kick_env = math.exp(-kick_t * 12.0) * 0.35
                drum_val = math.sin(2.0 * math.pi * 55.0 * t) * kick_env
            else:
                # Snare (caixa estalada)
                snare_t = kick_t
                snare_env = math.exp(-snare_t * 18.0) * 0.28
                drum_val = (math.sin(2.0 * math.pi * 180.0 * t) + math.sin(2.0 * math.pi * 3200.0 * t) * 0.5) * snare_env
            
            raw_v = g_dist + drum_val
            val = max(-0.95, min(0.95, raw_v))
            samples.append(int(val * 32767.0))

    elif style == "comedy_meme_funny":
        # 🎭 CÔMICO / MEME: Ragtime staccato saltitante + Efeitos cômicos
        notes = [523.25, 659.25, 783.99, 880.00, 783.99, 659.25, 587.33, 493.88] # C5, E5, G5, A5...
        step_len = 0.260 # ~115 BPM
        for i in range(total_samples):
            t = i / sample_rate
            idx = int((t / step_len) % len(notes))
            freq = notes[idx]
            dt = t % step_len
            
            # Nota staccato com decay rápido (som de xilofone / desenho animado)
            env = math.exp(-dt * 16.0) if dt < 0.20 else 0.0
            melody = (math.sin(2.0 * math.pi * freq * t) + 0.3 * math.sin(2.0 * math.pi * (freq * 2) * t)) * env * 0.38
            
            # Baixo saltitante (Tuba / Baixo acústico)
            bass_f = 130.81 if (idx % 2 == 0) else 196.00 # C3 ou G3
            bass_env = math.exp(-dt * 8.0)
            bass = math.sin(2.0 * math.pi * bass_f * t) * bass_env * 0.30
            
            raw_v = melody + bass
            val = max(-0.95, min(0.95, raw_v))
            samples.append(int(val * 32767.0))

    elif style == "epic_hype_glory":
        # 🏆 ÉPICO / GLÓRIA: Metais cinematográficos + Tímpanos de impacto
        chords = [
            [146.83, 220.00, 293.66, 349.23, 440.00], # Dm
            [116.54, 174.61, 233.08, 349.23, 466.16], # Bb
            [130.81, 196.00, 261.63, 329.63, 523.25], # C
            [146.83, 220.00, 293.66, 370.00, 440.00], # D
        ]
        chord_len = 2.526 # ~95 BPM
        for i in range(total_samples):
            t = i / sample_rate
            chord_idx = int((t / chord_len) % len(chords))
            current_chord = chords[chord_idx]
            
            val = 0.0
            for note_f in current_chord:
                val += math.sin(2.0 * math.pi * note_f * t) * 0.16
                val += math.sin(2.0 * math.pi * (note_f * 0.5) * t) * 0.10
            
            # Tímpano de impacto a cada novo acorde
            timp_t = t % chord_len
            timp_env = math.exp(-timp_t * 4.0) * 0.32
            val += math.sin(2.0 * math.pi * 50.0 * t) * timp_env
            
            val = max(-0.95, min(0.95, val))
            samples.append(int(val * 32767.0))

    elif style == "lofi_chill":
        chords = [
            [261.63, 329.63, 392.00, 493.88],  # Cmaj7
            [220.00, 261.63, 329.63, 392.00],  # Am7
            [293.66, 349.23, 440.00, 523.25],  # Dm7
            [196.00, 246.94, 293.66, 349.23],  # G7
        ]
        chord_len = 3.0
        for i in range(total_samples):
            t = i / sample_rate
            chord_idx = int((t / chord_len) % len(chords))
            current_chord = chords[chord_idx]
            val = 0.0
            for note_f in current_chord:
                val += math.sin(2.0 * math.pi * note_f * t) * 0.18
                val += math.sin(math.pi * note_f * t) * 0.12
            beat_t = t % 0.5
            beat_env = math.exp(-beat_t * 8.0) * 0.15
            val += math.sin(2.0 * math.pi * 65.0 * t) * beat_env
            val = max(-0.95, min(0.95, val))
            samples.append(int(val * 32767.0))

    elif style == "tension_suspense":
        chords = [
            [130.81, 155.56, 196.00, 277.18],
            [123.47, 146.83, 185.00, 261.63],
            [116.54, 138.59, 174.61, 246.94],
            [130.81, 155.56, 196.00, 261.63],
        ]
        chord_len = 3.5
        for i in range(total_samples):
            t = i / sample_rate
            chord_idx = int((t / chord_len) % len(chords))
            current_chord = chords[chord_idx]
            val = 0.0
            for note_f in current_chord:
                val += math.sin(2.0 * math.pi * note_f * t) * 0.18
                val += math.sin(math.pi * note_f * t) * 0.12
            beat_t = t % 0.5
            beat_env = math.exp(-beat_t * 8.0) * 0.15
            val += math.sin(2.0 * math.pi * 65.0 * t) * beat_env
            val = max(-0.95, min(0.95, val))
            samples.append(int(val * 32767.0))

    elif style == "inspirational_epic":
        chords = [
            [174.61, 220.00, 261.63, 349.23],
            [196.00, 246.94, 293.66, 392.00],
            [220.00, 261.63, 329.63, 440.00],
            [164.81, 196.00, 246.94, 329.63],
        ]
        chord_len = 2.5
        for i in range(total_samples):
            t = i / sample_rate
            chord_idx = int((t / chord_len) % len(chords))
            current_chord = chords[chord_idx]
            val = 0.0
            for note_f in current_chord:
                val += math.sin(2.0 * math.pi * note_f * t) * 0.18
                val += math.sin(math.pi * note_f * t) * 0.12
            beat_t = t % 0.5
            beat_env = math.exp(-beat_t * 8.0) * 0.15
            val += math.sin(2.0 * math.pi * 65.0 * t) * beat_env
            val = max(-0.95, min(0.95, val))
            samples.append(int(val * 32767.0))

    else:  # dynamic_pulse
        chords = [
            [146.83, 220.00, 293.66, 349.23],
            [174.61, 261.63, 349.23, 440.00],
            [196.00, 293.66, 392.00, 493.88],
            [146.83, 220.00, 293.66, 440.00],
        ]
        chord_len = 2.0
        for i in range(total_samples):
            t = i / sample_rate
            chord_idx = int((t / chord_len) % len(chords))
            current_chord = chords[chord_idx]
            val = 0.0
            for note_f in current_chord:
                val += math.sin(2.0 * math.pi * note_f * t) * 0.18
                val += math.sin(math.pi * note_f * t) * 0.12
            beat_t = t % 0.5
            beat_env = math.exp(-beat_t * 8.0) * 0.15
            val += math.sin(2.0 * math.pi * 65.0 * t) * beat_env
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


CUSTOM_TRACKS_FILE = os.path.join(ASSETS_AUDIO_DIR, "custom_tracks.json")


def load_custom_tracks_metadata() -> dict:
    """Carrega o catálogo de metadados das trilhas customizadas."""
    if os.path.exists(CUSTOM_TRACKS_FILE):
        try:
            with open(CUSTOM_TRACKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_custom_tracks_metadata(data: dict):
    """Salva o catálogo de metadados das trilhas customizadas."""
    os.makedirs(ASSETS_AUDIO_DIR, exist_ok=True)
    with open(CUSTOM_TRACKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def register_custom_audio_track(
    source_path: str,
    title: str,
    category_name: str = "🎵 Trilha Personalizada",
    description: str = ""
) -> dict:
    """
    Registra um arquivo de áudio extraído/importado diretamente na biblioteca permanente de trilhas.
    """
    os.makedirs(ASSETS_AUDIO_DIR, exist_ok=True)
    if not os.path.exists(source_path):
        return {"error": f"Arquivo fonte não encontrado: {source_path}", "track": None}

    # Gera nome de arquivo limpo e seguro
    clean_title_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', title).strip('_').lower()[:35] or "track"
    ext = os.path.splitext(source_path)[1].lower() or ".mp3"
    dest_filename = f"{clean_title_slug}{ext}"
    dest_path = os.path.join(ASSETS_AUDIO_DIR, dest_filename)

    # Evita sobrescrever se for arquivo diferente
    counter = 1
    while os.path.exists(dest_path) and os.path.abspath(source_path) != os.path.abspath(dest_path):
        dest_filename = f"{clean_title_slug}_{counter}{ext}"
        dest_path = os.path.join(ASSETS_AUDIO_DIR, dest_filename)
        counter += 1

    if os.path.abspath(source_path) != os.path.abspath(dest_path):
        shutil.copy2(source_path, dest_path)

    track_id = dest_filename
    meta_db = load_custom_tracks_metadata()
    track_info = {
        "id": track_id,
        "filename": dest_filename,
        "title": title.strip() or f"🎵 {dest_filename}",
        "category": category_name,
        "description": description.strip() or f"Extraído para cortes ({category_name})",
        "path": dest_path,
        "is_builtin": False
    }
    meta_db[track_id] = track_info
    save_custom_tracks_metadata(meta_db)

    return {"error": None, "track": track_info}


def list_available_tracks() -> list:
    """
    Retorna lista de todas as trilhas disponíveis (embutidas + customizadas com metadados).
    """
    ensure_default_tracks()
    tracks = []
    
    # 1. Adiciona as categorias mapeadas nativas
    for key, info in MUSIC_CATEGORIES.items():
        fpath = os.path.join(ASSETS_AUDIO_DIR, info["filename"])
        tracks.append({
            "id": key,
            "title": info["title"],
            "description": info["description"],
            "path": fpath,
            "is_builtin": True
        })
        
    # 2. Adiciona metadados de trilhas customizadas salvas
    custom_meta = load_custom_tracks_metadata()

    # 3. Adiciona quaisquer arquivos MP3/WAV extras adicionados pelo usuário na pasta
    if os.path.exists(ASSETS_AUDIO_DIR):
        for f in os.listdir(ASSETS_AUDIO_DIR):
            ext = os.path.splitext(f)[1].lower()
            if ext in [".mp3", ".wav", ".m4a", ".aac"]:
                # Verifica se não é um dos built-in
                if not any(f == info["filename"] for info in MUSIC_CATEGORIES.values()):
                    fpath = os.path.join(ASSETS_AUDIO_DIR, f)
                    if f in custom_meta:
                        c_info = custom_meta[f]
                        tracks.append({
                            "id": f,
                            "title": c_info.get("title", f"🎵 {f}"),
                            "description": c_info.get("description", c_info.get("category", "Trilha personalizada")),
                            "path": fpath,
                            "is_builtin": False
                        })
                    else:
                        tracks.append({
                            "id": f,
                            "title": f"🎵 {f}",
                            "description": "Trilha personalizada do usuário",
                            "path": fpath,
                            "is_builtin": False
                        })
                    
    return tracks


def get_track_path_by_id(track_id: str) -> str:
    """Retorna o caminho absoluto do arquivo de áudio dado o seu identificador."""
    if not track_id:
        return ""
    all_tracks = list_available_tracks()
    for t in all_tracks:
        if t["id"] == track_id or t.get("filename") == track_id:
            return t["path"]
    # Fallback para caminho direto se existir
    if os.path.exists(track_id):
        return track_id
    default_f = os.path.join(ASSETS_AUDIO_DIR, "lofi_chill.wav")
    return default_f if os.path.exists(default_f) else ""


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
        # 1. Ajuste de volume base da música de fundo (com -stream_loop nativo no input)
        # 2. Sidechaincompress na música usando a faixa de voz [0:a] como trigger
        # 3. Mixagem do áudio da voz limpo com a música ducked
        filter_complex = (
            f"[1:a]volume={music_volume}[bg];"
            f"[bg][0:a]sidechaincompress=threshold={threshold}:ratio={ratio}:attack={attack}:release={release}[ducked_bg];"
            f"[0:a][ducked_bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", input_video_path,
            "-stream_loop", "-1", "-i", music_track_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
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
