"""
core/video_code_manager.py — Gerenciador Central de Códigos Exclusivos de 11 Caracteres (Estilo YouTube)
Garante que cada vídeo base (projeto) e cada pequeno corte renderizado (instância de formato/minutagem)
possuam um código único de 11 caracteres (SHA-256 + Base64URL), com registro global anti-colisão
persistido em data/video_codes_registry.json.
"""

import os
import json
import hashlib
import base64
import threading
from datetime import datetime

_REGISTRY_LOCK = threading.Lock()
REGISTRY_FILENAME = "video_codes_registry.json"


def _get_data_dir() -> str:
    try:
        import core.library_manager as lm
        return getattr(lm, "DATA_DIR", "data") or "data"
    except Exception:
        return "data"


def get_registry_path(data_dir: str = None) -> str:
    base = data_dir or _get_data_dir()
    return os.path.join(base, REGISTRY_FILENAME)


def generate_youtube_style_id(text: str) -> str:
    """Gera um ID de 11 caracteres similar ao do YouTube a partir de uma string."""
    seed = str(text or "").strip()
    hash_bytes = hashlib.sha256(seed.encode("utf-8")).digest()
    base64url_hash = base64.urlsafe_b64encode(hash_bytes).decode("utf-8")
    return base64url_hash[:11]


def load_codes_registry(data_dir: str = None) -> dict:
    """Carrega o dicionário global de códigos emitidos ({code: info_dict})."""
    reg_path = get_registry_path(data_dir)
    if os.path.exists(reg_path):
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_codes_registry(registry: dict, data_dir: str = None):
    """Salva o dicionário global de códigos emitidos."""
    reg_path = get_registry_path(data_dir)
    os.makedirs(os.path.dirname(reg_path) or ".", exist_ok=True)
    try:
        with open(reg_path, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def allocate_unique_video_code(
    seed: str,
    owner_key: str,
    metadata: dict = None,
    preferred_code: str = None,
    data_dir: str = None
) -> str:
    """
    Aloca e registra um código de 11 caracteres garantidamente exclusivo para `owner_key`.
    - Se `owner_key` já possuir um código registrado no índice global, reutiliza-o (idempotente).
    - Se `preferred_code` (11 chars) for informado e estiver livre (ou já pertencer ao `owner_key`),
      registra e retorna `preferred_code`.
    - Caso o hash inicial colida com outro `owner_key`, aplica nonce incremental (`seed#1`, `seed#2`...)
      até obter um código de 11 caracteres 100% inédito.
    """
    clean_owner = str(owner_key or "").strip() or f"anon:{seed}"
    clean_seed = str(seed or "").strip() or clean_owner
    pref = str(preferred_code or "").strip()

    with _REGISTRY_LOCK:
        registry = load_codes_registry(data_dir)

        # 1. Verifica se este owner_key já tem um código registrado
        for existing_code, info in registry.items():
            if isinstance(info, dict) and info.get("owner_key") == clean_owner and len(existing_code) == 11:
                if metadata:
                    info.update(metadata)
                    save_codes_registry(registry, data_dir)
                return existing_code

        # 2. Se há um código preferido válido e sem conflito com outro owner_key, adota-o
        if len(pref) == 11:
            holder = registry.get(pref)
            if holder is None or (isinstance(holder, dict) and holder.get("owner_key") == clean_owner):
                entry = {"owner_key": clean_owner, "created_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
                if metadata:
                    entry.update(metadata)
                registry[pref] = entry
                save_codes_registry(registry, data_dir)
                return pref

        # 3. Gera a partir da semente e resolve eventual colisão com nonce incremental
        cand = generate_youtube_style_id(clean_seed)
        nonce = 1
        while cand in registry and registry[cand].get("owner_key") != clean_owner:
            cand = generate_youtube_style_id(f"{clean_seed}#{nonce}")
            nonce += 1

        entry = {"owner_key": clean_owner, "created_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
        if metadata:
            entry.update(metadata)
        registry[cand] = entry
        save_codes_registry(registry, data_dir)
        return cand


def build_project_seed(video_id: str, title: str = "", url: str = "") -> str:
    """
    Constrói a semente para vídeo base.
    Se o título for válido e personalizado, prioriza o título como base primária;
    caso haja outro projeto com o mesmo título, o registro global anti-colisão
    diferencia automaticamente via nonce sem jamais repetir o código.
    """
    t = str(title or "").strip()
    u = str(url or "").strip()
    vid = str(video_id or "").strip()
    if t and t != f"Vídeo {vid}":
        return t
    return f"{vid}|{u}" if u else vid


def allocate_project_code(
    video_id: str,
    title: str = "",
    url: str = "",
    preferred_code: str = None,
    data_dir: str = None
) -> str:
    """Aloca um código exclusivo de 11 caracteres para um vídeo base (projeto)."""
    vid = str(video_id or "").strip()
    owner_key = f"project:{vid}" if vid else f"project_anon:{title or url}"
    seed = build_project_seed(vid, title, url)
    meta = {
        "kind": "project",
        "video_id": vid,
        "title": str(title or "")[:120],
        "url": str(url or "")[:200],
    }
    return allocate_unique_video_code(
        seed=seed,
        owner_key=owner_key,
        metadata=meta,
        preferred_code=preferred_code,
        data_dir=data_dir,
    )


def allocate_cut_code(
    video_id: str,
    start_time: str,
    end_time: str,
    aspect_mode: str,
    title: str = "",
    folder_name: str = "",
    video_path: str = "",
    preferred_code: str = None,
    data_dir: str = None
) -> str:
    """
    Aloca um código exclusivo de 11 caracteres para um pequeno corte renderizado.
    Cada combinação (video_id, start_time, end_time, aspect_mode, folder_name) possui
    seu próprio owner_key e semente composta, garantindo que nem cortes de mesmo título
    nem formatos diferentes do mesmo trecho jamais repitam código.
    """
    vid = str(video_id or "").strip()
    st_s = str(start_time or "00:00:00.00").strip()
    et_s = str(end_time or "end").strip()
    asp = str(aspect_mode or "9:16").strip()
    fn = str(folder_name or "").strip()
    t = str(title or "").strip()

    owner_key = f"cut:{vid}:{st_s}_{et_s}:{asp}:{fn}" if fn else f"cut:{vid}:{st_s}_{et_s}:{asp}"
    seed = f"{vid}|{st_s}|{et_s}|{asp}|{t}|{fn}"
    meta = {
        "kind": "cut",
        "video_id": vid,
        "time_range": f"{st_s} -> {et_s}",
        "aspect_mode": asp,
        "title": t[:120],
        "folder_name": fn,
        "video_path": str(video_path or ""),
    }
    return allocate_unique_video_code(
        seed=seed,
        owner_key=owner_key,
        metadata=meta,
        preferred_code=preferred_code,
        data_dir=data_dir,
    )
