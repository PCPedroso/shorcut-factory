"""
cuts_catalog.py — Catálogo & Cache Inteligente de Cortes por Minutagem e Formato
Rastreia e indexa todos os cortes gerados para cada vídeo em data/<video_id>/cuts_catalog.json.
Diferencia instâncias individuais para cada formato de vídeo (VLDSS, VRIRA, VFDBS, VCCFT, HOFHD).
"""

import os
import json
import shutil
import re
from datetime import datetime
from typing import Optional, Tuple
from core.export_kit import build_cut_folder_name
from core.video_code_manager import allocate_cut_code


def _get_catalog_path(video_id: str) -> str:
    return os.path.join("data", video_id, "cuts_catalog.json")


def _raw_load_cuts_catalog(video_id: str) -> dict:
    """Carrega o catálogo do arquivo cuts_catalog.json sem acionar sincronização."""
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


def ensure_catalog_cut_codes(video_id: str, catalog: dict = None) -> dict:
    """
    Garante que todos os pequenos cortes e instâncias de formato registrados em `cuts_catalog.json`
    possuam seu próprio `cut_code` exclusivo de 11 caracteres (retrocompatível para cortes antigos).
    """
    if not video_id:
        return catalog or {}
    cat = catalog if catalog is not None else _raw_load_cuts_catalog(video_id)
    if not isinstance(cat, dict) or not cat:
        return cat

    modified = False
    for time_key, c_data in cat.items():
        if not isinstance(c_data, dict):
            continue
        s_t = c_data.get("start_time", "")
        e_t = c_data.get("end_time", "")
        c_title = c_data.get("title", "")
        formats = c_data.get("formats", {})
        if not isinstance(formats, dict):
            continue
        for asp_mode, fmt_info in formats.items():
            if not isinstance(fmt_info, dict):
                continue
            existing = str(fmt_info.get("cut_code") or "").strip()
            code = allocate_cut_code(
                video_id=video_id,
                start_time=s_t,
                end_time=e_t,
                aspect_mode=asp_mode,
                title=c_title,
                folder_name=fmt_info.get("folder_name", ""),
                video_path=fmt_info.get("video_path", ""),
                preferred_code=existing if len(existing) == 11 else None,
            )
            if fmt_info.get("cut_code") != code:
                fmt_info["cut_code"] = code
                modified = True

    if modified:
        save_cuts_catalog(video_id, cat)
    return cat


def load_cuts_catalog(video_id: str, sync_carrossel: bool = True) -> dict:
    """Carrega o catálogo de cortes de um vídeo específico, sincronizando partes de carrossel e códigos exclusivos."""
    if not video_id:
        return {}
    if sync_carrossel:
        try:
            sync_carrossel_parts_to_catalog(video_id)
        except Exception:
            pass
    cat = _raw_load_cuts_catalog(video_id)
    return ensure_catalog_cut_codes(video_id, cat)


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


_syncing_carrossel_lock = set()


def sync_carrossel_parts_to_catalog(video_id: str) -> dict:
    """
    Sincroniza automaticamente partes processadas do carrossel (em data/<video_id>/carrossel/)
    com o catálogo cuts_catalog.json, garantindo que apareçam na Galeria de Cortes & Pós.
    """
    if not video_id or video_id in _syncing_carrossel_lock:
        return _raw_load_cuts_catalog(video_id)

    _syncing_carrossel_lock.add(video_id)
    try:
        carrossel_dir = os.path.join("data", video_id, "carrossel")
        if not os.path.isdir(carrossel_dir):
            return _raw_load_cuts_catalog(video_id)

        files = sorted(os.listdir(carrossel_dir))
        proc_files = []
        for f in files:
            if not f.endswith(".mp4") or f.endswith("_editado.mp4"):
                continue
            m = re.match(r"^parte_(\d+)_(.+)\.mp4$", f)
            if m:
                fp = os.path.join(carrossel_dir, f)
                if os.path.exists(fp) and os.path.getsize(fp) > 10240:
                    proc_files.append((int(m.group(1)), m.group(2), f, fp))

        if not proc_files:
            return _raw_load_cuts_catalog(video_id)

        # Carrega metadados do vídeo original para obter título
        meta_path = os.path.join("data", video_id, "metadata.json")
        orig_title = "Vídeo"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f_meta:
                    m_data = json.load(f_meta)
                    orig_title = m_data.get("title") or orig_title
            except Exception:
                pass

        # Carrega ou monta mapa de minutagens das partes
        split_info_file = os.path.join(carrossel_dir, "split_info.json")
        part_timings = {}
        if os.path.exists(split_info_file):
            try:
                with open(split_info_file, "r", encoding="utf-8") as f_sp:
                    sp_data = json.load(f_sp)
                    for p_item in sp_data.get("parts", []):
                        part_timings[int(p_item.get("index", 0))] = (float(p_item.get("start", 0.0)), float(p_item.get("end", 0.0)))
            except Exception:
                pass

        # Se não temos split_info.json, reconstrói acumulando durações a partir dos arquivos brutos ou processados
        if not part_timings:
            raw_files = [f for f in files if re.match(r"^parte_\d+\.mp4$", f)]
            from core.quick_editor import get_video_duration
            cur_t = 0.0
            parts_accum = []
            if raw_files:
                for rf in sorted(raw_files):
                    m_rf = re.match(r"^parte_(\d+)\.mp4$", rf)
                    if m_rf:
                        idx_rf = int(m_rf.group(1))
                        d_rf = get_video_duration(os.path.join(carrossel_dir, rf))
                        part_timings[idx_rf] = (cur_t, cur_t + d_rf)
                        parts_accum.append({"index": idx_rf, "start": cur_t, "end": cur_t + d_rf, "duration": d_rf})
                        cur_t += d_rf
            else:
                grouped_by_idx = {}
                for idx, tag, f, fp in proc_files:
                    if idx not in grouped_by_idx:
                        grouped_by_idx[idx] = fp
                for idx in sorted(grouped_by_idx.keys()):
                    d_p = get_video_duration(grouped_by_idx[idx])
                    part_timings[idx] = (cur_t, cur_t + d_p)
                    parts_accum.append({"index": idx, "start": cur_t, "end": cur_t + d_p, "duration": d_p})
                    cur_t += d_p

            if parts_accum:
                try:
                    with open(split_info_file, "w", encoding="utf-8") as f_out_sp:
                        json.dump({"parts": parts_accum, "total_duration": cur_t}, f_out_sp, indent=2, ensure_ascii=False)
                except Exception:
                    pass

        catalog = _raw_load_cuts_catalog(video_id)
        catalog_modified = False

        def _fmt_ts(s: float) -> str:
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:05.2f}"

        from core.video_processor import extract_thumbnail_from_video

        for idx, raw_aspect_tag, fname, fpath in proc_files:
            aspect_mode = raw_aspect_tag
            if aspect_mode.startswith("9-16"):
                aspect_mode = aspect_mode.replace("9-16", "9:16", 1)
            elif aspect_mode.startswith("16-9"):
                aspect_mode = aspect_mode.replace("16-9", "16:9", 1)

            t_start_sec, t_end_sec = part_timings.get(idx, (0.0, 0.0))
            if t_end_sec <= t_start_sec:
                from core.quick_editor import get_video_duration
                t_end_sec = t_start_sec + get_video_duration(fpath)

            start_time_str = _fmt_ts(t_start_sec)
            end_time_str = _fmt_ts(t_end_sec)
            time_key = make_time_key(start_time_str, end_time_str)

            # Se já estiver registrado com este formato e o vídeo existir, pula
            if time_key in catalog and aspect_mode in catalog[time_key].get("formats", {}):
                cur_fmt = catalog[time_key]["formats"][aspect_mode]
                if cur_fmt.get("video_path") and os.path.exists(cur_fmt.get("video_path")):
                    continue

            # Thumbnail do corte
            thumb_name = fname.replace(".mp4", "_thumb.jpg")
            thumb_path = os.path.join(carrossel_dir, thumb_name)
            if not os.path.exists(thumb_path):
                try:
                    extract_thumbnail_from_video(fpath, thumb_path, timestamp_sec=1.0)
                except Exception:
                    pass

            part_title = f"Parte {idx:02d}: {orig_title}"

            if time_key not in catalog:
                catalog[time_key] = {
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "title": part_title,
                    "description": f"{part_title}\n\nAssista ao episódio completo!",
                    "hashtags": ["#shorts", "#cortes", "#viral"],
                    "tags_seo": f"parte {idx}, cortes, podcast, viral",
                    "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "formats": {}
                }

            resolved_thumb_path = thumb_path if os.path.exists(thumb_path) else None
            part_cut_code = allocate_cut_code(
                video_id=video_id,
                start_time=start_time_str,
                end_time=end_time_str,
                aspect_mode=aspect_mode,
                title=part_title,
                folder_name=f"carrossel_parte_{idx}",
                video_path=fpath,
            )
            catalog[time_key]["formats"][aspect_mode] = {
                "cut_code": part_cut_code,
                "aspect_mode": aspect_mode,
                "folder_name": "carrossel",
                "folder_path": carrossel_dir,
                "video_path": fpath,
                "video_filename": fname,
                "thumbnail_path": resolved_thumb_path,
                "thumbnail_filename": os.path.basename(resolved_thumb_path) if resolved_thumb_path else None,
                "thumbnail_variations": [],
                "active_variation": 1,
                "subtitle_path": None,
                "subtitle_filename": None,
                "resolution": "1080p",
                "rendered_at": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            catalog_modified = True

        if catalog_modified:
            save_cuts_catalog(video_id, catalog)

        return catalog
    finally:
        _syncing_carrossel_lock.discard(video_id)


def make_time_key(start_time: str, end_time: str) -> str:
    """Normaliza o par start_time e end_time para chave de busca única."""
    s = (start_time or "").strip()
    e = (end_time or "").strip()
    return f"{s}_{e}"


def get_cut_entry(video_id: str, start_time: str, end_time: str) -> dict | None:
    """Retorna a entrada do corte se a minutagem exata já tiver sido processada."""
    if not video_id or not start_time or not end_time:
        return None
    catalog = _raw_load_cuts_catalog(video_id)
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
    catalog = _raw_load_cuts_catalog(video_id)
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

    # Registra a instância específica deste formato com código exclusivo de 11 caracteres
    prev_fmt = catalog[key]["formats"].get(aspect_mode, {}) if isinstance(catalog[key].get("formats"), dict) else {}
    prev_code = str(prev_fmt.get("cut_code") or "").strip()
    cut_code = allocate_cut_code(
        video_id=video_id,
        start_time=start_time,
        end_time=end_time,
        aspect_mode=aspect_mode,
        title=title,
        folder_name=folder_name,
        video_path=video_path,
        preferred_code=prev_code if len(prev_code) == 11 else None,
    )
    catalog[key]["formats"][aspect_mode] = {
        "cut_code": cut_code,
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
    catalog = _raw_load_cuts_catalog(video_id)
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
    catalog = _raw_load_cuts_catalog(video_id)
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
    catalog = _raw_load_cuts_catalog(video_id)
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

🏷️ TAGS / PALAVRAS-CHAVE SEO:
{tags_seo}

🎬 CRÉDITOS DO VÍDEO ORIGINAL:
- Vídeo: {orig_title}
- Canal: {orig_channel}
- Link Original: {orig_url}
- Data de Publicação: {orig_date}

════════════════════════════════════════════════════════════════
Pronto para publicação rápida nas redes sociais!
════════════════════════════════════════════════════════════════
"""
            with open(os.path.join(folder_path, "info_publicacao.txt"), "w", encoding="utf-8") as f:
                f.write(info_content)

            with open(os.path.join(folder_path, "descricao.txt"), "w", encoding="utf-8") as f:
                f.write(f"{description}\n\n{hashtags_str}\n")

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
    catalog = _raw_load_cuts_catalog(video_id)
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
            # Apaga a pasta inteira daquele formato (ou apenas arquivos de vídeo/thumb se for carrossel)
            inst = catalog[key]["formats"].pop(aspect_mode)
            f_path = inst.get("folder_path")
            if f_path and os.path.exists(f_path):
                if os.path.basename(os.path.normpath(f_path)).lower() == "carrossel":
                    v_p = inst.get("video_path")
                    if v_p and os.path.exists(v_p):
                        try:
                            os.remove(v_p)
                        except Exception:
                            pass
                    th_p = inst.get("thumbnail_path")
                    if th_p and os.path.exists(th_p):
                        try:
                            os.remove(th_p)
                        except Exception:
                            pass
                else:
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
    catalog = _raw_load_cuts_catalog(video_id)
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
                    if os.path.basename(os.path.normpath(f_path)).lower() == "carrossel":
                        v_p = inst.get("video_path")
                        if v_p and os.path.exists(v_p):
                            try:
                                os.remove(v_p)
                            except Exception:
                                pass
                        th_p = inst.get("thumbnail_path")
                        if th_p and os.path.exists(th_p):
                            try:
                                os.remove(th_p)
                            except Exception:
                                pass
                    else:
                        shutil.rmtree(f_path, ignore_errors=True)

        save_cuts_catalog(video_id, catalog)
        return True
    return False


def delete_entire_carrossel(
    video_id: str,
    delete_raw_splits: bool = True
) -> dict:
    """
    Remove um carrossel completo de um projeto/vídeo:
    - Se delete_raw_splits=True: remove toda a pasta data/<video_id>/carrossel/ e limpa as entradas no catálogo.
    - Se delete_raw_splits=False: remove apenas as partes processadas e thumbnails, mantendo os fatiamentos originais (parte_01.mp4, etc.) para reprocessamento.
    """
    if not video_id:
        return {"success": False, "error": "video_id não informado."}

    carrossel_dir = os.path.join("data", video_id, "carrossel")
    catalog = _raw_load_cuts_catalog(video_id)

    # Limpa do catálogo todas as instâncias e entradas relacionadas ao carrossel
    keys_to_remove = []
    for key, entry in list(catalog.items()):
        formats = entry.get("formats", {})
        for fmt_k, inst in list(formats.items()):
            folder_p = inst.get("folder_path", "")
            video_p = inst.get("video_path", "")
            f_norm = os.path.normpath(folder_p).lower().replace("\\", "/").split("/")
            v_norm = os.path.normpath(video_p).lower().replace("\\", "/").split("/")
            if inst.get("folder_name") == "carrossel" or "carrossel" in f_norm or "carrossel" in v_norm:
                formats.pop(fmt_k, None)
        if not formats:
            keys_to_remove.append(key)

    for k in keys_to_remove:
        catalog.pop(k, None)

    save_cuts_catalog(video_id, catalog)

    if os.path.isdir(carrossel_dir):
        if delete_raw_splits:
            shutil.rmtree(carrossel_dir, ignore_errors=True)
        else:
            for f in os.listdir(carrossel_dir):
                fp = os.path.join(carrossel_dir, f)
                if re.match(r"^parte_\d+\.mp4$", f) or f == "split_info.json":
                    continue
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                    elif os.path.isdir(fp):
                        shutil.rmtree(fp, ignore_errors=True)
                except Exception:
                    pass

    return {"success": True, "error": None}


# ---------------------------------------------------------------------------
# Importação e Parse de Cortes via JSON Externo
# ---------------------------------------------------------------------------

def parse_json_cuts(json_data: dict) -> dict:
    """
    Valida e normaliza o JSON de cortes externo para o formato estruturado do ViralCut.
    Ordena os cortes de acordo com a lista de 'ranking' (se presente).
    """
    if not isinstance(json_data, dict):
        return {
            "video_url": "",
            "video_id": "",
            "schema_version": "1.0",
            "resumo": "",
            "alertas_gerais": [],
            "ranking": [],
            "cortes": []
        }

    # Extrai informações do vídeo
    video_info = json_data.get("video") or {}
    video_url = ""
    if isinstance(video_info, dict):
        video_url = str(video_info.get("url") or "").strip()
    elif isinstance(video_info, str):
        video_url = video_info.strip()

    if not video_url:
        video_url = str(json_data.get("video_url") or "").strip()

    video_id = ""
    if video_url:
        try:
            from core.transcriber import extract_youtube_video_id
            video_id = extract_youtube_video_id(video_url)
        except Exception:
            pass
        if not video_id:
            # Fallback simples de regex para YouTube
            m = re.search(r"(?:v=|\/|youtu\.be\/|embed\/|live\/)([0-9A-Za-z_-]{11})", video_url)
            if m:
                video_id = m.group(1)

    schema_version = str(json_data.get("schema_version", "1.0"))
    resumo = str(json_data.get("resumo", "")).strip()
    alertas_gerais = json_data.get("alertas_gerais") or []
    if not isinstance(alertas_gerais, list):
        alertas_gerais = [str(alertas_gerais)]

    ranking = json_data.get("ranking") or []
    if not isinstance(ranking, list):
        ranking = []

    # Mapa de posição no ranking para ordenação rápida
    rank_pos_map = {}
    rank_desc_map = {}
    for r in ranking:
        if isinstance(r, dict):
            r_id = str(r.get("id", "")).strip()
            if r_id:
                rank_pos_map[r_id] = r.get("posicao", 999)
                rank_desc_map[r_id] = str(r.get("ponderacao", "")).strip()

    raw_cortes = json_data.get("cortes") or []
    if not isinstance(raw_cortes, list):
        raw_cortes = []

    parsed_cortes = []
    for idx, c in enumerate(raw_cortes):
        if not isinstance(c, dict):
            continue

        c_id = str(c.get("id") or f"C{idx + 1}").strip()
        start_time = str(c.get("inicio") or c.get("start_time") or "00:00:00.00").strip()
        end_time = str(c.get("fim") or c.get("end_time") or "00:00:00.00").strip()

        # Duração
        dur_sec = c.get("duracao_segundos")
        if dur_sec is not None:
            try:
                dur_sec = float(dur_sec)
            except Exception:
                dur_sec = 0.0
        dur_fmt = str(c.get("duracao_formatada") or "").strip()

        frase_inicio = str(c.get("frase_inicio") or "").strip()
        frase_fim = str(c.get("frase_fim") or "").strip()
        descricao_corte = str(c.get("descricao") or "").strip()
        gancho = str(c.get("gancho") or "").strip()

        # Potencial de viralização
        pot_raw = c.get("potencial_viralizacao") or {}
        if isinstance(pot_raw, dict):
            pot_nota = pot_raw.get("nota")
            pot_just = str(pot_raw.get("justificativa") or "").strip()
        elif isinstance(pot_raw, (int, float)):
            pot_nota = int(pot_raw)
            pot_just = ""
        else:
            pot_nota = None
            pot_just = ""

        depende_visual = bool(c.get("depende_visual", False))
        risco_contexto = str(c.get("risco_contexto") or "baixo").strip().lower()

        # Observações
        raw_obs = c.get("observacoes") or []
        observacoes = []
        if isinstance(raw_obs, list):
            for obs in raw_obs:
                if isinstance(obs, dict):
                    observacoes.append({
                        "tipo": str(obs.get("tipo", "geral")),
                        "texto": str(obs.get("texto", "")).strip()
                    })
                elif isinstance(obs, str):
                    observacoes.append({"tipo": "geral", "texto": obs.strip()})

        # Textos e títulos
        textos = c.get("textos") or {}
        if not isinstance(textos, dict):
            textos = {}

        raw_titulos = textos.get("titulos") or []
        title_list = []
        if isinstance(raw_titulos, list):
            for t in raw_titulos:
                if isinstance(t, dict):
                    txt_val = str(t.get("texto", "")).strip()
                    if txt_val:
                        title_list.append(txt_val)
                elif isinstance(t, str) and t.strip():
                    title_list.append(t.strip())

        primary_title = title_list[0] if title_list else (str(c.get("titulo") or c.get("title") or f"Corte {c_id}")).strip()
        alt_titles = title_list[1:] if len(title_list) > 1 else []

        # Descrição e hashtags
        desc_obj = textos.get("descricao") or {}
        if isinstance(desc_obj, dict):
            final_desc = str(desc_obj.get("texto") or descricao_corte).strip()
            raw_tags = desc_obj.get("hashtags") or []
            credito = str(desc_obj.get("credito") or "").strip()
        else:
            final_desc = str(desc_obj).strip() if str(desc_obj).strip() else descricao_corte
            raw_tags = textos.get("hashtags") or []
            credito = ""

        clean_hashtags = []
        if isinstance(raw_tags, list):
            for h in raw_tags:
                hs = str(h).strip()
                if hs:
                    if not hs.startswith("#"):
                        hs = f"#{hs}"
                    clean_hashtags.append(hs)

        # Textos âncora
        raw_ancora = textos.get("textos_ancora") or []
        textos_ancora = []
        if isinstance(raw_ancora, list):
            for a in raw_ancora:
                if isinstance(a, dict):
                    textos_ancora.append({
                        "texto": str(a.get("texto", "")).strip(),
                        "tipo": str(a.get("tipo", "padrao")).strip()
                    })
                elif isinstance(a, str) and a.strip():
                    textos_ancora.append({"texto": a.strip(), "tipo": "padrao"})

        # Enquete
        enquete = textos.get("enquete") or {}
        if not isinstance(enquete, dict):
            enquete = {}

        # Posição no ranking
        rank_pos = rank_pos_map.get(c_id, 999)
        rank_ponderacao = rank_desc_map.get(c_id, "")

        parsed_cortes.append({
            "id": c_id,
            "start_time": start_time,
            "end_time": end_time,
            "duracao_segundos": dur_sec,
            "duracao_formatada": dur_fmt,
            "title": primary_title,
            "alt_titles": alt_titles,
            "description": final_desc,
            "hashtags": clean_hashtags,
            "headline": gancho,
            "credito": credito,
            "textos_ancora": textos_ancora,
            "enquete": enquete,
            "observacoes": observacoes,
            "potencial_nota": pot_nota,
            "potencial_justificativa": pot_just,
            "risco_contexto": risco_contexto,
            "depende_visual": depende_visual,
            "frase_inicio": frase_inicio,
            "frase_fim": frase_fim,
            "ranking_posicao": rank_pos if rank_pos != 999 else None,
            "ranking_ponderacao": rank_ponderacao,
        })

    # Ordena pelo ranking se houver algum ranking configurado
    if rank_pos_map:
        parsed_cortes.sort(key=lambda item: (item["ranking_posicao"] if item["ranking_posicao"] is not None else 999))

    return {
        "video_url": video_url,
        "video_id": video_id,
        "schema_version": schema_version,
        "resumo": resumo,
        "alertas_gerais": alertas_gerais,
        "ranking": ranking,
        "cortes": parsed_cortes
    }


def register_cuts_from_parsed(video_id: str, parsed: dict) -> int:
    """
    Registra os metadados dos cortes importados no cuts_catalog.json do vídeo.
    Preserva instâncias de vídeo já renderizadas caso existam na mesma minutagem.
    Retorna a quantidade de cortes registrados/atualizados.
    """
    if not video_id or not parsed or not isinstance(parsed, dict):
        return 0

    cortes = parsed.get("cortes") or []
    if not cortes:
        return 0

    catalog = _raw_load_cuts_catalog(video_id)
    count = 0

    for cut in cortes:
        s_t = cut.get("start_time")
        e_t = cut.get("end_time")
        if not s_t or not e_t:
            continue

        key = make_time_key(s_t, e_t)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

        if key not in catalog:
            catalog[key] = {
                "start_time": s_t,
                "end_time": e_t,
                "title": cut.get("title", ""),
                "description": cut.get("description", ""),
                "hashtags": cut.get("hashtags", []),
                "tags_seo": "",
                "created_at": now_str,
                "updated_at": now_str,
                "formats": {}
            }
        else:
            if cut.get("title"):
                catalog[key]["title"] = cut.get("title")
            if cut.get("description"):
                catalog[key]["description"] = cut.get("description")
            if cut.get("hashtags"):
                catalog[key]["hashtags"] = cut.get("hashtags")
            catalog[key]["updated_at"] = now_str

        # Armazena metadados avançados do JSON de cortes no catálogo
        if cut.get("headline"):
            catalog[key]["headline"] = cut.get("headline")
        if cut.get("alt_titles"):
            catalog[key]["alt_titles"] = cut.get("alt_titles")
        if cut.get("textos_ancora"):
            catalog[key]["textos_ancora"] = cut.get("textos_ancora")
        if cut.get("enquete"):
            catalog[key]["enquete"] = cut.get("enquete")
        if cut.get("observacoes"):
            catalog[key]["observacoes"] = cut.get("observacoes")
        if cut.get("potencial_nota") is not None:
            catalog[key]["potencial_viralizacao"] = {
                "nota": cut.get("potencial_nota"),
                "justificativa": cut.get("potencial_justificativa", "")
            }
        if cut.get("risco_contexto"):
            catalog[key]["risco_contexto"] = cut.get("risco_contexto")
        if cut.get("depende_visual") is not None:
            catalog[key]["depende_visual"] = cut.get("depende_visual")
        if cut.get("id"):
            catalog[key]["json_cut_id"] = cut.get("id")
        if cut.get("ranking_posicao") is not None:
            catalog[key]["ranking_posicao"] = cut.get("ranking_posicao")
        if cut.get("ranking_ponderacao"):
            catalog[key]["ranking_ponderacao"] = cut.get("ranking_ponderacao")

        count += 1

    save_cuts_catalog(video_id, catalog)
    return count


def get_cut_license(video_id: str, cut_key: str) -> Optional[dict]:
    """Retorna a licença explícita definida na raiz do corte, ou None se herdada do vídeo."""
    if not video_id or not cut_key:
        return None
    from core.licensing import normalize_license
    catalog = _raw_load_cuts_catalog(video_id)
    entry = catalog.get(cut_key)
    if not entry or not isinstance(entry, dict):
        return None
    if "licenca" in entry and isinstance(entry["licenca"], dict):
        return normalize_license(entry["licenca"])
    return None


def set_cut_license(video_id: str, cut_key: str, license_dict: Optional[dict]) -> dict:
    """Define, atualiza ou remove a licença explícita de um corte no catálogo.

    Se license_dict for None, remove a chave 'licenca' da raiz do corte para que herde do vídeo.
    Se license_dict for um dicionário, grava na raiz do corte (fora de 'formats').
    Retorna o dicionário da entrada do corte atualizada.
    """
    if not video_id or not cut_key:
        return {}
    from core.licensing import normalize_license
    catalog = _raw_load_cuts_catalog(video_id)
    entry = catalog.get(cut_key)
    if not entry or not isinstance(entry, dict):
        return {}

    if license_dict is None:
        entry.pop("licenca", None)
    else:
        entry["licenca"] = normalize_license(license_dict)

    entry["updated_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    save_cuts_catalog(video_id, catalog)
    return entry


def get_effective_license_for_cut(video_id: str, cut_key: Optional[str]) -> Tuple[dict, str]:
    """Retorna a licença efetiva de um corte combinando corte e vídeo com regra de herança.

    Retorna:
        Tuple[licenca_normalizada (dict), origem ("corte" | "video" | "padrao")]
    """
    from core.licensing import resolve_effective_license
    from core.library_manager import get_video_license

    vid_lic = get_video_license(video_id) if video_id else None
    cut_lic = get_cut_license(video_id, cut_key) if (video_id and cut_key) else None
    return resolve_effective_license(vid_lic, cut_lic)



