"""
library_manager.py — Gerenciador de Biblioteca de Vídeos Processados
Registra título, data de lançamento, thumbnail, duração e histórico de vídeos para reutilização ou exclusão.
"""

import os
import json
import shutil
from datetime import datetime

DATA_DIR = "data"
LIBRARY_FILE = os.path.join(DATA_DIR, "library.json")


def format_upload_date(raw_date: str) -> str:
    """Formata YYYYMMDD para DD/MM/YYYY."""
    if not raw_date or len(str(raw_date)) != 8:
        return "Data desconhecida"
    s = str(raw_date)
    return f"{s[6:8]}/{s[4:6]}/{s[0:4]}"


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
    channel: str = None
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
