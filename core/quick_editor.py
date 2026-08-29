"""
quick_editor.py — Ferramenta de Edição Rápida, Ajuste Fino (Trim) e Remoção de Trechos com FFmpeg
"""

import os
import subprocess
import cv2
import numpy as np
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def get_video_duration(video_path: str) -> float:
    """
    Retorna a duração exata do vídeo em segundos via OpenCV / FFprobe.
    """
    if not video_path or not os.path.exists(video_path):
        return 0.0

    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0 and frame_count > 0:
                return float(frame_count / fps)
    except Exception:
        pass

    # Fallback via ffprobe se OpenCV falhar
    try:
        cmd = [
            FFMPEG_EXE, "-i", video_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if m:
            hours, mins, secs = m.groups()
            return int(hours) * 3600 + int(mins) * 60 + float(secs)
    except Exception:
        pass

    return 0.0


def extract_frame_at_timestamp(video_path: str, timestamp_s: float) -> np.ndarray:
    """
    Extrai um frame RGB no segundo exato para prévia visual na interface.
    """
    if not video_path or not os.path.exists(video_path):
        return None

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        target_frame = int(max(0.0, timestamp_s) * fps) if fps > 0 else 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame_bgr = cap.read()
        cap.release()

        if ret and frame_bgr is not None:
            return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        pass

    return None


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

    return entry
