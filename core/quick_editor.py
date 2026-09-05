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
