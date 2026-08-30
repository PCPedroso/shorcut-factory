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
    resolution: str = "1080p",
    thumbnail_path: str = None,
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

    # Verifica se a thumbnail e suas variações existem na pasta
    resolved_thumb_path = thumbnail_path
    if not resolved_thumb_path and folder_path:
        candidate_t = os.path.join(folder_path, "thumbnail.jpg")
        if os.path.exists(candidate_t):
            resolved_thumb_path = candidate_t

    # Mapeia variações de thumbnail disponíveis
    thumb_variations = []
    if folder_path:
        for v_i, v_name in [(1, "⚡ Impacto Neon (Glow)"), (2, "✨ Clean Focus (Sombra 3D)"), (3, "🎬 Moldura Dinâmica (HDR)")]:
            v_cand = os.path.join(folder_path, f"thumbnail_{v_i}.jpg")
            if os.path.exists(v_cand):
                thumb_variations.append({
                    "id": v_i,
                    "name": v_name,
                    "filename": f"thumbnail_{v_i}.jpg",
                    "path": v_cand
                })

    # Verifica se arquivos de legenda (.srt) existem na pasta
    resolved_sub_path = None
    if folder_path:
        cand_sub1 = os.path.join(folder_path, f"{folder_name}.srt")
        cand_sub2 = os.path.join(folder_path, "legendas.srt")
        if os.path.exists(cand_sub1):
            resolved_sub_path = cand_sub1
        elif os.path.exists(cand_sub2):
            resolved_sub_path = cand_sub2

    # Registra a instância específica deste formato
    catalog[key]["formats"][aspect_mode] = {
        "aspect_mode": aspect_mode,
        "folder_name": folder_name,
        "folder_path": folder_path,
        "video_path": video_path,
        "video_filename": os.path.basename(video_path) if video_path else f"{folder_name}.mp4",
        "thumbnail_path": resolved_thumb_path,
        "thumbnail_filename": "thumbnail.jpg" if resolved_thumb_path else None,
        "thumbnail_variations": thumb_variations,
        "active_variation": 1,
        "subtitle_path": resolved_sub_path,
        "subtitle_filename": os.path.basename(resolved_sub_path) if resolved_sub_path else None,
        "resolution": resolution,
        "rendered_at": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    save_cuts_catalog(video_id, catalog)
    return catalog[key]


def set_active_thumbnail_variation(
    video_id: str,
    start_time: str,
    end_time: str,
    aspect_mode: str,
    variation_id: int
) -> dict:
    """
    Define a variação selecionada (1, 2 ou 3) como a capa principal do corte (thumbnail.jpg).
    """
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)
    entry = catalog.get(key)
    if not entry:
        return {"error": "Corte não encontrado no catálogo."}

    inst = entry.get("formats", {}).get(aspect_mode)
    if not inst:
        return {"error": f"Formato {aspect_mode} não encontrado para este corte."}

    folder_path = inst.get("folder_path")
    if not folder_path or not os.path.exists(folder_path):
        return {"error": "Pasta do pacote do corte não encontrada no disco."}

    var_path = os.path.join(folder_path, f"thumbnail_{variation_id}.jpg")
    main_path = os.path.join(folder_path, "thumbnail.jpg")

    if not os.path.exists(var_path):
        return {"error": f"Variação {variation_id} não encontrada em {var_path}."}

    try:
        shutil.copy2(var_path, main_path)
        inst["active_variation"] = variation_id
        inst["thumbnail_path"] = main_path
        save_cuts_catalog(video_id, catalog)
        return {"success": True, "active_variation": variation_id, "thumbnail_path": main_path}
    except Exception as e:
        return {"error": f"Erro ao aplicar variação de capa: {str(e)}"}


def update_cut_thumbnail_in_catalog(
    video_id: str,
    start_time: str,
    end_time: str,
    aspect_mode: str,
    thumbnail_path: str,
    variations: list = None
) -> dict:
    """Atualiza a referência da thumbnail e variações no catálogo para um formato existente."""
    catalog = load_cuts_catalog(video_id)
    key = make_time_key(start_time, end_time)
    entry = catalog.get(key)
    if not entry:
        return {"error": "Minutagem não encontrada no catálogo."}

    inst = entry.get("formats", {}).get(aspect_mode)
    if not inst:
        return {"error": f"Formato {aspect_mode} não encontrado para este corte."}

    inst["thumbnail_path"] = thumbnail_path
    inst["thumbnail_filename"] = os.path.basename(thumbnail_path) if thumbnail_path else "thumbnail.jpg"
    if variations:
        inst["thumbnail_variations"] = variations
    inst["active_variation"] = 1
    inst["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    save_cuts_catalog(video_id, catalog)
    return {"success": True, "entry": entry}


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
