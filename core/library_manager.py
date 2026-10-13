"""
library_manager.py — Gerenciador de Biblioteca de Vídeos Processados
Registra título, data de lançamento, thumbnail, duração e histórico de vídeos para reutilização ou exclusão.
"""

import os
import json
import shutil
import re
from datetime import datetime

DATA_DIR = "data"
LIBRARY_FILE = os.path.join(DATA_DIR, "library.json")


def find_video_slices(base_vid: str) -> list:
    """
    Encontra todos os trechos/fatias e o vídeo base cadastrados ou existentes em data/ para um dado base_vid.
    Retorna uma lista ordenada com informações de cada fatia (video_id, título, start_sec, end_sec, arquivos existentes, etc.).
    """
    if not base_vid:
        return []

    # Se o ID passado já for um slice (ex: kick_..._t_120_240), recupera o base_vid limpo
    clean_base = re.sub(r'_t_\d+_(?:end|\d+)(?:_[a-zA-Z0-9_-]+)?$', '', base_vid)
    clean_base = re.sub(r'_(?:last\d+m|live_snapshot_[a-zA-Z0-9_-]+)$', '', clean_base)

    lib = get_library()
    slices = []
    seen_ids = set()

    # 1. Verifica itens cadastrados na biblioteca
    for item in lib:
        v_id = item.get("video_id") or ""
        if v_id == clean_base or v_id.startswith(f"{clean_base}_t_") or v_id.startswith(f"{clean_base}_"):
            seen_ids.add(v_id)
            v_dir = os.path.join(DATA_DIR, v_id)
            has_v = os.path.exists(os.path.join(v_dir, "video_full.mp4"))
            has_a = os.path.exists(os.path.join(v_dir, "audio.mp3"))
            has_tr = os.path.exists(os.path.join(v_dir, "transcript.json"))

            m = re.search(r'_t_(\d+)_([0-9a-zA-Z]+)', v_id)
            s_sec = int(m.group(1)) if m else None
            e_sec = int(m.group(2)) if (m and m.group(2).isdigit()) else None

            v_sz = 0.0
            if has_v:
                try:
                    v_sz = round(os.path.getsize(os.path.join(v_dir, "video_full.mp4")) / (1024 * 1024), 1)
                except Exception:
                    pass

            slices.append({
                "video_id": v_id,
                "title": item.get("title") or f"Trecho {v_id}",
                "is_base": (v_id == clean_base),
                "start_sec": s_sec,
                "end_sec": e_sec,
                "duration_sec": item.get("duration_sec"),
                "thumbnail": item.get("thumbnail"),
                "has_video": has_v,
                "has_audio": has_a,
                "has_transcript": has_tr,
                "video_size_mb": v_sz,
                "url": item.get("url"),
                "added_at": item.get("added_at")
            })

    # 2. Varre pastas em data/ caso não estejam cadastradas na biblioteca
    if os.path.exists(DATA_DIR):
        for entry in os.listdir(DATA_DIR):
            if entry in seen_ids:
                continue
            v_dir = os.path.join(DATA_DIR, entry)
            if not os.path.isdir(v_dir):
                continue
            if entry == clean_base or entry.startswith(f"{clean_base}_t_") or entry.startswith(f"{clean_base}_"):
                seen_ids.add(entry)
                has_v = os.path.exists(os.path.join(v_dir, "video_full.mp4"))
                has_a = os.path.exists(os.path.join(v_dir, "audio.mp3"))
                has_tr = os.path.exists(os.path.join(v_dir, "transcript.json"))
                meta_path = os.path.join(v_dir, "metadata.json")
                meta = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as mf:
                            meta = json.load(mf)
                    except Exception:
                        pass
                m = re.search(r'_t_(\d+)_([0-9a-zA-Z]+)', entry)
                s_sec = int(m.group(1)) if m else None
                e_sec = int(m.group(2)) if (m and m.group(2).isdigit()) else None

                v_sz = 0.0
                if has_v:
                    try:
                        v_sz = round(os.path.getsize(os.path.join(v_dir, "video_full.mp4")) / (1024 * 1024), 1)
                    except Exception:
                        pass

                slices.append({
                    "video_id": entry,
                    "title": meta.get("title") or f"Trecho {entry}",
                    "is_base": (entry == clean_base),
                    "start_sec": s_sec,
                    "end_sec": e_sec,
                    "duration_sec": meta.get("duration_sec") or meta.get("duration"),
                    "thumbnail": meta.get("thumbnail"),
                    "has_video": has_v,
                    "has_audio": has_a,
                    "has_transcript": has_tr,
                    "video_size_mb": v_sz,
                    "url": meta.get("url"),
                    "added_at": meta.get("added_at")
                })

    slices.sort(key=lambda s: (0 if s["is_base"] else 1, s["start_sec"] or 0))
    return slices


def format_upload_date(raw_date: str) -> str:
    """Formata YYYYMMDD para DD/MM/YYYY ou mantém se já for string formatada."""
    if not raw_date:
        return "Arquivo Local"
    s = str(raw_date).strip()
    if "/" in s or "-" in s and len(s) == 10:
        return s
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"
    return s


def get_library() -> list:
    """Retorna a lista de vídeos cadastrados na biblioteca, ordenada pelo mais recente."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    if os.path.exists(LIBRARY_FILE):
        try:
            with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                lib = json.load(f)
                if isinstance(lib, list):
                    return lib
        except Exception:
            pass

    # Se o arquivo não existir, faz varredura nas pastas de data/ para resgatar vídeos já existentes
    rescued_lib = []
    if os.path.exists(DATA_DIR):
        for entry in os.listdir(DATA_DIR):
            sub_dir = os.path.join(DATA_DIR, entry)
            if os.path.isdir(sub_dir):
                meta_path = os.path.join(sub_dir, "metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            rescued_lib.append(meta)
                    except Exception:
                        pass
                elif os.path.exists(os.path.join(sub_dir, "transcript.json")):
                    rescued_lib.append({
                        "video_id": entry,
                        "title": f"Vídeo ({entry})",
                        "upload_date": "Registrado",
                        "url": f"https://www.youtube.com/watch?v={entry}",
                        "added_at": datetime.now().strftime("%d/%m/%Y %H:%M")
                    })
                    
    save_library_list(rescued_lib)
    return rescued_lib


def save_library_list(lib_list: list):
    """Salva a lista completa da biblioteca no arquivo library.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(lib_list, f, ensure_ascii=False, indent=4)


def add_or_update_video_in_library(
    video_id: str,
    title: str,
    upload_date_raw: str,
    url: str,
    thumbnail_url: str = None,
    duration_sec: int = None,
    channel: str = None,
    is_live: bool = False
) -> dict:
    """Registra ou atualiza um vídeo no catálogo da biblioteca."""
    lib = get_library()
    
    formatted_date = format_upload_date(upload_date_raw)
    
    video_entry = {
        "video_id": video_id,
        "title": title or f"Vídeo {video_id}",
        "upload_date": formatted_date,
        "raw_upload_date": upload_date_raw,
        "url": url,
        "thumbnail": thumbnail_url,
        "duration_sec": duration_sec,
        "channel": channel or "Canal Desconhecido",
        "is_live": is_live,
        "added_at": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    # Atualiza se já existir ou adiciona no topo
    lib = [v for v in lib if v.get("video_id") != video_id]
    lib.insert(0, video_entry)
    save_library_list(lib)

    # Salva também dentro da pasta do próprio vídeo
    v_dir = os.path.join(DATA_DIR, video_id)
    os.makedirs(v_dir, exist_ok=True)
    with open(os.path.join(v_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(video_entry, f, ensure_ascii=False, indent=4)

    return video_entry


def remove_video_from_library(video_id: str, delete_folder: bool = True) -> bool:
    """Remove um vídeo da biblioteca e apaga seus dados locais."""
    lib = get_library()
    lib = [v for v in lib if v.get("video_id") != video_id]
    save_library_list(lib)

    if delete_folder:
        v_dir = os.path.join(DATA_DIR, video_id)
        if os.path.exists(v_dir):
            shutil.rmtree(v_dir, ignore_errors=True)

    return True


def update_video_thumbnail_in_library(video_id: str, thumbnail_path: str) -> bool:
    """Atualiza o caminho da thumbnail de um vídeo existente na biblioteca e em seu metadata.json."""
    if not video_id:
        return False
    lib = get_library()
    updated = False
    for item in lib:
        if item.get("video_id") == video_id:
            item["thumbnail"] = thumbnail_path
            updated = True
            break
    if updated:
        save_library_list(lib)

    v_dir = os.path.join(DATA_DIR, video_id)
    meta_path = os.path.join(v_dir, "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            meta["thumbnail"] = thumbnail_path
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
    return True


def create_project_from_cut_video(
    source_video_path: str,
    title: str,
    parent_video_id: str = None,
    start_time_str: str = None,
    end_time_str: str = None,
    parent_title: str = None,
    copy_transcript: bool = True
) -> dict:
    """
    Cria um novo projeto isolado no Shortcut Factory a partir de um vídeo de corte renderizado.
    1. Valida a existência do arquivo de vídeo de origem.
    2. Gera um video_id local único e cria seu diretório em data/<video_id>/.
    3. Copia o arquivo do corte para video_full.mp4 desse novo projeto.
    4. Extrai a duração real do novo vídeo.
    5. Copia ou gera uma thumbnail representativa.
    6. Se copy_transcript=True, fatia e sincroniza a transcrição existente (do projeto pai ou da pasta do corte).
    7. Cadastra o novo projeto na biblioteca (library.json) e salva seu metadata.json.
    """
    if not source_video_path or not os.path.exists(source_video_path):
        return {"error": f"Arquivo de corte não encontrado: {source_video_path}"}

    final_title = (title or "").strip() or f"Sub-projeto {os.path.splitext(os.path.basename(source_video_path))[0]}"

    try:
        from core.video_processor import generate_local_video_id, extract_thumbnail_from_video, parse_time_to_seconds
        from core.quick_editor import get_video_duration
    except Exception as e:
        return {"error": f"Falha ao importar dependências do processador de vídeo: {e}"}

    # 1. Gera ID local único para o projeto
    base_id = generate_local_video_id(final_title)
    new_video_id = base_id
    target_dir = os.path.join(DATA_DIR, new_video_id)
    counter = 1
    while os.path.exists(target_dir):
        new_video_id = f"{base_id}_{counter}"
        target_dir = os.path.join(DATA_DIR, new_video_id)
        counter += 1

    os.makedirs(target_dir, exist_ok=True)

    # 2. Copia o arquivo de vídeo do corte como video_full.mp4
    dest_video = os.path.join(target_dir, "video_full.mp4")
    try:
        shutil.copy2(source_video_path, dest_video)
    except Exception as e:
        return {"error": f"Falha ao copiar vídeo para o novo projeto: {e}"}

    # 3. Duração real do vídeo
    dur_sec = get_video_duration(dest_video)

    # 4. Thumbnail
    thumb_dest = os.path.join(target_dir, "thumbnail.jpg")
    cut_folder = os.path.dirname(os.path.abspath(source_video_path))
    cand_thumbs = [
        os.path.join(cut_folder, "thumbnail.jpg"),
        os.path.join(cut_folder, "thumbnail_1.jpg"),
        os.path.join(cut_folder, "thumbnail_2.jpg"),
        os.path.join(cut_folder, "thumbnail_3.jpg"),
    ]
    found_thumb = False
    for ct in cand_thumbs:
        if os.path.exists(ct) and os.path.getsize(ct) > 1000:
            try:
                shutil.copy2(ct, thumb_dest)
                found_thumb = True
                break
            except Exception:
                pass

    if not found_thumb:
        try:
            extract_thumbnail_from_video(dest_video, thumb_dest, timestamp_sec=min(2.0, max(0.0, dur_sec * 0.1)))
        except Exception:
            pass

    # 5. Herança / Fatiamento Inteligente de Transcrição
    has_transcript = False
    if copy_transcript:
        parent_dir = os.path.join(DATA_DIR, parent_video_id) if parent_video_id else None
        parent_tr_file = os.path.join(parent_dir, "transcript.json") if parent_dir else None
        cut_tr_file = os.path.join(cut_folder, "transcricao_corte.json")
        cut_srt_file = os.path.join(cut_folder, "legendas.srt")

        # 5.1 Fatiar do projeto pai com ajuste relativo de timestamps
        if parent_tr_file and os.path.exists(parent_tr_file) and start_time_str and end_time_str:
            try:
                s_sec = parse_time_to_seconds(start_time_str)
                e_sec = parse_time_to_seconds(end_time_str)
                with open(parent_tr_file, "r", encoding="utf-8") as f_p_tr:
                    p_tr_data = json.load(f_p_tr)

                orig_segs = p_tr_data.get("segments", [])
                sliced_segs = []
                for seg in orig_segs:
                    seg_start = float(seg.get("start", 0.0))
                    seg_end = float(seg.get("end", 0.0))
                    if seg_end <= s_sec or seg_start >= e_sec:
                        continue
                    new_s = max(0.0, round(seg_start - s_sec, 3))
                    new_e = max(0.0, round(seg_end - s_sec, 3))
                    new_seg = {
                        "start": new_s,
                        "end": new_e,
                        "text": seg.get("text", "")
                    }
                    if "words" in seg and isinstance(seg["words"], list):
                        new_words = []
                        for w in seg["words"]:
                            w_start = float(w.get("start", 0.0))
                            w_end = float(w.get("end", 0.0))
                            if w_end <= s_sec or w_start >= e_sec:
                                continue
                            new_words.append({
                                "word": w.get("word", ""),
                                "start": max(0.0, round(w_start - s_sec, 3)),
                                "end": max(0.0, round(w_end - s_sec, 3)),
                                "score": w.get("score", 1.0)
                            })
                        new_seg["words"] = new_words
                    sliced_segs.append(new_seg)

                if sliced_segs:
                    full_txt = " ".join(s["text"].strip() for s in sliced_segs if s.get("text"))
                    dest_tr = os.path.join(target_dir, "transcript.json")
                    with open(dest_tr, "w", encoding="utf-8") as f_d_tr:
                        json.dump({
                            "full_text": full_txt,
                            "segments": sliced_segs,
                            "source": f"Herdada do projeto pai ({parent_video_id})"
                        }, f_d_tr, ensure_ascii=False, indent=4)
                    has_transcript = True
            except Exception:
                pass

        # 5.2 Se não fatiou do pai, tenta transcricao_corte.json existente na pasta do corte
        if not has_transcript and os.path.exists(cut_tr_file) and os.path.getsize(cut_tr_file) > 10:
            try:
                shutil.copy2(cut_tr_file, os.path.join(target_dir, "transcript.json"))
                has_transcript = True
            except Exception:
                pass

        # 5.3 Se não tem json, mas tem legendas.srt na pasta do corte
        if not has_transcript and os.path.exists(cut_srt_file) and os.path.getsize(cut_srt_file) > 10:
            try:
                from core.subtitle_burner import parse_srt_to_transcript_dict
                srt_dict = parse_srt_to_transcript_dict(cut_srt_file)
                if srt_dict and srt_dict.get("segments"):
                    dest_tr = os.path.join(target_dir, "transcript.json")
                    with open(dest_tr, "w", encoding="utf-8") as f_d_tr:
                        json.dump(srt_dict, f_d_tr, ensure_ascii=False, indent=4)
                    has_transcript = True
            except Exception:
                pass

    # 6. Registra na biblioteca e em metadata.json
    channel_desc = f"Sub-projeto de {parent_title or parent_video_id or 'Corte'}"
    add_or_update_video_in_library(
        video_id=new_video_id,
        title=final_title,
        upload_date_raw=datetime.now().strftime("%d/%m/%Y"),
        url=f"local://{new_video_id}",
        thumbnail_url=thumb_dest if os.path.exists(thumb_dest) else None,
        duration_sec=int(dur_sec),
        channel=channel_desc,
        is_live=False
    )

    return {
        "success": True,
        "video_id": new_video_id,
        "title": final_title,
        "duration_sec": dur_sec,
        "has_transcript": has_transcript,
        "video_path": dest_video,
        "url": f"local://{new_video_id}"
    }

