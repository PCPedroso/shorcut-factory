"""
batch_processor.py — Processador de Renderização em Lote (Batch Pipeline)
Executa a renderização sequencial de múltiplos cortes, geração automática de metadados virais,
queima de legendas dinâmicas e empacotamento estruturado no catálogo.
"""

import os
import json
from typing import Callable, List, Dict
import core.video_processor
import core.analyzer
import core.subtitle_burner
import core.export_kit
import core.cuts_catalog


def process_batch_cuts(
    video_id: str,
    active_url: str,
    cut_items: List[Dict],
    aspect_ratio_mode: str,
    subtitle_enabled: bool,
    subtitle_highlight_color: str,
    subtitle_base_color: str,
    subtitle_font_size: int,
    ollama_model: str,
    aspect_params: Dict = None,
    progress_callback: Callable[[int, int, str], None] = None
) -> List[Dict]:
    """
    Processa uma lista de cortes em lote:
    cut_items: [
        {"start": "00:02:45", "end": "00:03:45", "title": "...", "type": "Shorts"},
        ...
    ]
    """
    if not video_id or not cut_items:
        return []

    data_dir = os.path.join("data", video_id)
    os.makedirs(data_dir, exist_ok=True)
    video_full_path = os.path.join(data_dir, "video_full.mp4")
    transcript_path = os.path.join(data_dir, "transcript.json")

    # 1. Garante que o vídeo original Full HD está baixado
    if not os.path.exists(video_full_path):
        if progress_callback:
            progress_callback(0, len(cut_items), "Baixando vídeo original em 1080p Full HD...")
        dl_res = core.video_processor.download_full_video(active_url, video_full_path)
        if dl_res.get("error"):
            return [{"error": f"Erro no download do vídeo completo: {dl_res['error']}"}]

    # 2. Carrega metadados do vídeo original
    meta_file = os.path.join(data_dir, "metadata.json")
    orig_info = {}
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as mf:
                orig_info = json.load(mf)
        except Exception:
            pass
    if not orig_info:
        orig_info = {
            "title": f"Vídeo {video_id}",
            "channel": "Canal Oficial",
            "upload_date": "N/D",
            "url": active_url
        }

    params = aspect_params or {}
    results = []
    total = len(cut_items)

    for idx, item in enumerate(cut_items):
        start_t = item.get("start", "")
        end_t = item.get("end", "")
        base_title = item.get("title", f"Corte {idx+1}")

        if progress_callback:
            progress_callback(idx, total, f"[{idx+1}/{total}] Analisando trecho [{start_t} → {end_t}]...")

        # 3. Geração de Metadados com IA
        words_meta = core.subtitle_burner.extract_words_in_range(transcript_path, start_t, end_t)
        snippet_text = " ".join(w["word"] for w in words_meta)

        if snippet_text:
            meta_res = core.analyzer.generate_viral_cut_metadata(snippet_text, model=ollama_model)
            cut_title = meta_res.get("titulo_principal") or base_title
            cut_desc = meta_res.get("descricao") or "Confira este momento imperdível! Curta e comente."
            cut_hashtags = meta_res.get("hashtags", ["#shorts", "#viral", "#cortes", "#reels"])
            cut_tags_seo = meta_res.get("tags_seo", "cortes, viral, shorts, podcast")
        else:
            cut_title = base_title
            cut_desc = f"Confira este trecho: {base_title}"
            cut_hashtags = ["#shorts", "#viral", "#cortes"]
            cut_tags_seo = "shorts, cortes, viral"

        # 4. Renderização do Vídeo
        safe_aspect = aspect_ratio_mode.replace(":", "-")
        temp_corte_path = os.path.join(data_dir, f"temp_batch_{idx}_{safe_aspect}.mp4")

        if progress_callback:
            progress_callback(idx, total, f"[{idx+1}/{total}] Renderizando '{cut_title[:30]}...' em {aspect_ratio_mode}...")

        cut_res = core.video_processor.cut_video(
            video_full_path,
            start_t,
            end_t,
            temp_corte_path,
            aspect_ratio_mode=aspect_ratio_mode,
            blur_zoom=params.get("blur_zoom", 1.35),
            blur_pan=params.get("blur_pan", 0.0),
            blur_intensity=params.get("blur_intensity", 25),
            face_auto_zoom=params.get("face_auto_zoom", True),
            face_margin_ratio=params.get("face_margin_ratio", 1.55),
            person_preference=params.get("person_preference", "auto"),
            split_top_pan=params.get("split_top_pan", -0.65),
            split_bottom_pan=params.get("split_bottom_pan", 0.65),
            split_zoom=params.get("split_zoom", 1.15),
            split_divider_color=params.get("split_divider_color", "black"),
            split_divider_width=params.get("split_divider_width", 4),
            split_auto_switch=params.get("split_auto_switch", True),
            # Legendas Dinâmicas
            subtitle_enabled=subtitle_enabled,
            subtitle_transcript_path=transcript_path,
            subtitle_highlight_color=subtitle_highlight_color,
            subtitle_base_color=subtitle_base_color,
            subtitle_font_size=subtitle_font_size,
        )

        if cut_res.get("error"):
            results.append({
                "item": item,
                "title": cut_title,
                "error": cut_res["error"],
                "success": False
            })
            continue

        # 5. Criação do Pacote Estruturado
        pkg_res = core.export_kit.create_viral_package(
            video_path=temp_corte_path,
            title=cut_title,
            description=cut_desc,
            hashtags=cut_hashtags,
            tags_seo=cut_tags_seo,
            aspect_mode=aspect_ratio_mode,
            output_base_dir=data_dir,
            orig_video_info=orig_info
        )

        # Remove arquivo temporário se a cópia final foi criada
        if os.path.exists(temp_corte_path):
            try:
                os.remove(temp_corte_path)
            except Exception:
                pass

        # 6. Registra no Catálogo de Cortes
        out_res = core.video_processor.get_video_resolution(pkg_res["video_dest_path"])
        core.cuts_catalog.register_cut_instance(
            video_id=video_id,
            start_time=start_t,
            end_time=end_t,
            title=cut_title,
            description=cut_desc,
            hashtags=cut_hashtags,
            tags_seo=cut_tags_seo,
            aspect_mode=aspect_ratio_mode,
            folder_name=pkg_res["folder_name"],
            folder_path=pkg_res["package_dir"],
            video_path=pkg_res["video_dest_path"],
            resolution=out_res
        )

        results.append({
            "item": item,
            "title": cut_title,
            "start": start_t,
            "end": end_t,
            "folder_name": pkg_res["folder_name"],
            "video_path": pkg_res["video_dest_path"],
            "video_filename": pkg_res["video_filename"],
            "package_dir": pkg_res["package_dir"],
            "resolution": out_res,
            "success": True,
            "error": None
        })

    if progress_callback:
        progress_callback(total, total, f"Concluído! {len(results)} cortes processados.")

    return results
