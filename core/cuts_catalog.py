"""
cuts_catalog.py — Catálogo & Cache Inteligente de Cortes por Minutagem e Formato
Rastreia e indexa todos os cortes gerados para cada vídeo em data/<video_id>/cuts_catalog.json.
Diferencia instâncias individuais para cada formato de vídeo (VLDSS, VRIRA, VFDBS, VCCFT, HOFHD).
"""

import os
import json
import shutil
from datetime import datetime
from core.export_kit import build_cut_folder_name


def _get_catalog_path(video_id: str) -> str:
    return os.path.join("data", video_id, "cuts_catalog.json")


def load_cuts_catalog(video_id: str) -> dict:
    """Carrega o catálogo de cortes de um vídeo específico."""
    if not video_id:
        return {}
    cat_path = _get_catalog_path(video_id)
    if os.path.exists(cat_path):
        try:
            with open(cat_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cuts_catalog(video_id: str, catalog: dict):
    """Salva o catálogo de cortes no disco."""
    if not video_id:
        return
    cat_path = _get_catalog_path(video_id)
    os.makedirs(os.path.dirname(cat_path), exist_ok=True)
    try:
        with open(cat_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def make_time_key(start_time: str, end_time: str) -> str:
    """Normaliza o par start_time e end_time para chave de busca única."""
    s = (start_time or "").strip()
    e = (end_time or "").strip()
    return f"{s}_{e}"


def get_cut_entry(video_id: str, start_time: str, end_time: str) -> dict | None:
    """Retorna a entrada do corte se a minutagem exata já tiver sido processada."""
    if not video_id or not start_time or not end_time:
        return None
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)
    return catalog.get(key)


def get_format_instance(video_id: str, start_time: str, end_time: str, aspect_mode: str) -> dict | None:
    """
    Retorna os dados da instância de formato específico (ex: 9:16_smart_face)
    se o arquivo de vídeo ainda existir no disco.
    """
    entry = get_cut_entry(video_id, start_time, end_time)
    if not entry:
        return None
    formats = entry.get("formats", {})
    inst = formats.get(aspect_mode)
    if inst:
        v_path = inst.get("video_path")
        if v_path and os.path.exists(v_path):
            return inst
    return None


def register_cut_instance(
    video_id: str,
    start_time: str,
    end_time: str,
    title: str,
    description: str,
    hashtags: list,
    tags_seo: str,
    aspect_mode: str,
    folder_name: str,
    folder_path: str,
    video_path: str,
    resolution: str = "1080p"
) -> dict:
    """
    Registra uma nova instância de corte gerada ou atualiza uma existente no catálogo.
    """
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)

    if key not in catalog:
        catalog[key] = {
            "start_time": start_time,
            "end_time": end_time,
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "tags_seo": tags_seo,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "formats": {}
        }
    else:
        # Atualiza metadados mais recentes
        catalog[key]["title"] = title
        catalog[key]["description"] = description
        catalog[key]["hashtags"] = hashtags
        catalog[key]["tags_seo"] = tags_seo
        catalog[key]["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Registra a instância específica deste formato
    catalog[key]["formats"][aspect_mode] = {
        "aspect_mode": aspect_mode,
        "folder_name": folder_name,
        "folder_path": folder_path,
        "video_path": video_path,
        "video_filename": os.path.basename(video_path),
        "resolution": resolution,
        "rendered_at": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    save_cuts_catalog(video_id, catalog)
    return catalog[key]


def update_cut_texts_only(
    video_id: str,
    start_time: str,
    end_time: str,
    title: str,
    description: str,
    hashtags: list,
    tags_seo: str,
    orig_video_info: dict = None
) -> dict:
    """
    Atualiza apenas os textos e metadados de todas as instâncias existentes daquela minutagem
    sem necessidade de re-renderizar nenhum vídeo (.mp4).
    Atualiza info_publicacao.txt, descricao.txt e tags.txt em cada pasta já gerada.
    """
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)
    entry = catalog.get(key)
    if not entry:
        return {"error": "Minutagem não encontrada no catálogo."}

    entry["title"] = title
    entry["description"] = description
    entry["hashtags"] = hashtags
    entry["tags_seo"] = tags_seo
    entry["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    hashtags_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags) if hashtags else "#shorts #viral #cortes"

    orig_info = orig_video_info or {}
    orig_title = orig_info.get("title", "Título Desconhecido")
    orig_channel = orig_info.get("channel", "Canal Desconhecido")
    orig_date = orig_info.get("upload_date", "Data N/D")
    orig_url = orig_info.get("url", "")

    # Atualiza arquivos em todas as pastas de formatos já renderizadas
    for aspect_mode, inst in entry.get("formats", {}).items():
        folder_path = inst.get("folder_path")
        folder_name = inst.get("folder_name", "")
        if folder_path and os.path.exists(folder_path):
            # info_publicacao.txt
            info_content = f"""════════════════════════════════════════════════════════════════
🚀 PACOTE DE PUBLICAÇÃO VIRAL
📁 CÓDIGO DO CORTE: {folder_name}
════════════════════════════════════════════════════════════════

📌 TÍTULO DO CORTE:
{title}

📝 DESCRIÇÃO / LEGENDA (Instagram Reels, TikTok, YouTube Shorts):
{description}

{hashtags_str}

🏷️ TAGS SEO (separadas por vírgula):
{tags_seo}

🎬 ARQUIVO DE VÍDEO GERADO:
{inst.get('video_filename')}

════════════════════════════════════════════════════════════════
📺 INFORMAÇÕES DO VÍDEO ORIGINAL
════════════════════════════════════════════════════════════════
• Título Original: {orig_title}
• Canal do YouTube: {orig_channel}
• Data de Lançamento: {orig_date}
• Link do Vídeo: {orig_url}
"""
            with open(os.path.join(folder_path, "info_publicacao.txt"), "w", encoding="utf-8") as f:
                f.write(info_content)

            with open(os.path.join(folder_path, "descricao.txt"), "w", encoding="utf-8") as f:
                f.write(f"{description}\n\n{hashtags_str}")

            with open(os.path.join(folder_path, "tags.txt"), "w", encoding="utf-8") as f:
                f.write(f"HASHTAGS:\n{hashtags_str}\n\nTAGS SEO:\n{tags_seo}\n")

    save_cuts_catalog(video_id, catalog)
    return {"entry": entry, "error": None}


def delete_format_instance(
    video_id: str,
    start_time: str,
    end_time: str,
    aspect_mode: str,
    delete_publication_kit: bool = True
) -> bool:
    """
    Remove uma instância de formato específica.
    Se delete_publication_kit=False: apaga APENAS o arquivo .mp4, mantendo a pasta e o kit de publicação (.txt).
    Se delete_publication_kit=True: apaga a pasta completa e remove o formato do catálogo.
    """
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)
    if key in catalog and aspect_mode in catalog[key].get("formats", {}):
        inst = catalog[key]["formats"].get(aspect_mode)
        if not delete_publication_kit:
            # Apaga apenas o arquivo de vídeo (.mp4)
            v_path = inst.get("video_path")
            if v_path and os.path.exists(v_path):
                try:
                    os.remove(v_path)
                except Exception:
                    pass
            # Marca no catálogo que o vídeo foi removido mas o kit permanece
            inst["video_path"] = ""
            inst["video_deleted"] = True
        else:
            # Apaga a pasta inteira daquele formato
            inst = catalog[key]["formats"].pop(aspect_mode)
            f_path = inst.get("folder_path")
            if f_path and os.path.exists(f_path):
                shutil.rmtree(f_path, ignore_errors=True)
            if not catalog[key]["formats"]:
                catalog.pop(key, None)

        save_cuts_catalog(video_id, catalog)
        return True
    return False


def delete_entire_cut(
    video_id: str,
    start_time: str,
    end_time: str,
    delete_publication_kit: bool = True
) -> bool:
    """
    Remove todos os formatos daquela minutagem.
    Se delete_publication_kit=False: apaga APENAS os arquivos .mp4 de todos os formatos, preservando os textos.
    Se delete_publication_kit=True: apaga todas as pastas do disco e limpa o catálogo.
    """
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)
    if key in catalog:
        entry = catalog[key]
        if not delete_publication_kit:
            for inst in entry.get("formats", {}).values():
                v_path = inst.get("video_path")
                if v_path and os.path.exists(v_path):
                    try:
                        os.remove(v_path)
                    except Exception:
                        pass
                inst["video_path"] = ""
                inst["video_deleted"] = True
        else:
            catalog.pop(key, None)
            for inst in entry.get("formats", {}).values():
                f_path = inst.get("folder_path")
                if f_path and os.path.exists(f_path):
                    shutil.rmtree(f_path, ignore_errors=True)

        save_cuts_catalog(video_id, catalog)
        return True
    return False
