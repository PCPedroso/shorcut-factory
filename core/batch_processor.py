import os
import json
from datetime import datetime
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
    force_rerender: bool = False,
    progress_callback: Callable[[int, int, str], None] = None,
    log_callback: Callable[[str], None] = None
) -> List[Dict]:
    """
    Processa uma lista de cortes em lote com rastreamento e logs detalhados:
    cut_items: [
        {"start": "00:02:45", "end": "00:03:45", "title": "...", "type": "Shorts"},
        ...
    ]
    """
    collected_logs = []

    def _log(msg: str):
        t_str = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{t_str}] {msg}"
        collected_logs.append(log_line)
        print(log_line, flush=True)
        if log_callback:
            try:
                log_callback(log_line)
            except Exception:
                pass

    _log(f"=== INÍCIO DO PROCESSAMENTO EM LOTE ===")
    _log(f"Vídeo ID: {video_id} | URL Ativa: {active_url}")
    _log(f"Total de cortes selecionados: {len(cut_items) if cut_items else 0}")
    _log(f"Formato de enquadramento: {aspect_ratio_mode}")
    _log(f"Legendas dinâmicas: {subtitle_enabled} (Tam: {subtitle_font_size}px, Destaque: {subtitle_highlight_color})")
    _log(f"Forçar re-renderização (force_rerender): {force_rerender}")

    if not video_id or not cut_items:
        _log("ERRO: Video ID ou lista de cortes vazia. Abortando lote.")
        return []

    data_dir = os.path.join("data", video_id)
    os.makedirs(data_dir, exist_ok=True)
    video_full_path = os.path.join(data_dir, "video_full.mp4")
    transcript_path = os.path.join(data_dir, "transcript.json")

    # 1. Garante que o vídeo original Full HD está baixado
    _log(f"Verificando vídeo original em: {video_full_path}")
    if not os.path.exists(video_full_path) or os.path.getsize(video_full_path) == 0:
        if progress_callback:
            progress_callback(0, len(cut_items), "Baixando vídeo original em 1080p Full HD...")
        _meta_file = os.path.join(data_dir, "metadata.json")
        _is_live = False
        if os.path.exists(_meta_file):
            try:
                with open(_meta_file, "r", encoding="utf-8") as _mf:
                    _is_live = bool(json.load(_mf).get("is_live"))
            except Exception:
                pass
        dl_res = core.video_processor.download_full_video(active_url, video_full_path, is_live=_is_live)
        if dl_res.get("error"):
            err_msg = f"Erro no download do vídeo completo: {dl_res['error']}"
            _log(f"FALHA CRÍTICA: {err_msg}")
            return [{"error": err_msg, "logs": collected_logs}]
        _log(f"Download concluído com sucesso. Tamanho: {os.path.getsize(video_full_path)} bytes")
    else:
        _log(f"Vídeo original já presente no disco ({os.path.getsize(video_full_path)} bytes).")

    # 2. Carrega metadados do vídeo original
    meta_file = os.path.join(data_dir, "metadata.json")
    orig_info = {}
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as mf:
                orig_info = json.load(mf)
            _log(f"Metadados originais carregados: '{orig_info.get('title', 'N/D')}' por '{orig_info.get('channel', 'N/D')}'")
        except Exception as e:
            _log(f"Aviso ao ler metadata.json: {e}")
    if not orig_info:
        orig_info = {
            "title": f"Vídeo {video_id}",
            "channel": "Canal Oficial",
            "upload_date": "N/D",
            "url": active_url
        }

    params = aspect_params or {}
    _log(f"Parâmetros da Fase 3: Headline={params.get('headline_enabled')}, Emojis={params.get('emojis_enabled')}, ZoomPunch={params.get('zoom_punch_enabled')}, BGM={params.get('bg_music_enabled')}")

    results = []
    total = len(cut_items)

    for idx, item in enumerate(cut_items):
        start_t = item.get("start", "")
        end_t = item.get("end", "")
        base_title = item.get("title", f"Corte {idx+1}")

        _log(f"\n--- Processando Corte [{idx+1}/{total}] | Intervalo: [{start_t} -> {end_t}] | '{base_title}' ---")

        # Verificação se o corte já foi gerado neste formato
        if not force_rerender:
            existing_inst = core.cuts_catalog.get_format_instance(video_id, start_t, end_t, aspect_ratio_mode)
            if existing_inst and os.path.exists(existing_inst.get("video_path", "")):
                _log(f"Corte já existente no catálogo ({existing_inst.get('folder_name')}). POUPOU RENDERIZAÇÃO (Smart Skip ativado).")
                _log(f"Arquivo existente em: {existing_inst.get('video_path')}")
                if progress_callback:
                    progress_callback(idx + 1, total, f"[{idx+1}/{total}] ⚡ Já gerado: '{existing_inst.get('video_filename')}' (Ignorado)")
                results.append({
                    "item": item,
                    "title": base_title,
                    "start": start_t,
                    "end": end_t,
                    "folder_name": existing_inst.get("folder_name"),
                    "video_path": existing_inst.get("video_path"),
                    "video_filename": existing_inst.get("video_filename"),
                    "package_dir": existing_inst.get("folder_path"),
                    "resolution": existing_inst.get("resolution", "1080p"),
                    "skipped": True,
                    "success": True,
                    "error": None
                })
                continue
            else:
                _log("Nenhum corte pré-renderizado encontrado neste formato. Prosseguindo com renderização.")
        else:
            _log("Forçar re-renderização ativo: processando novamente mesmo se já existir.")

        if progress_callback:
            progress_callback(idx, total, f"[{idx+1}/{total}] Analisando trecho [{start_t} → {end_t}]...")

        # 3. Geração de Metadados com IA
        words_meta = core.subtitle_burner.extract_words_in_range(transcript_path, start_t, end_t)
        if len(words_meta) > 180:
            snippet_text = " ".join(w["word"] for w in words_meta[:180]) + "..."
        else:
            snippet_text = " ".join(w["word"] for w in words_meta)

        _log(f"Trecho da transcrição extraído: {len(words_meta)} palavras ({len(snippet_text)} caracteres)")

        if snippet_text:
            _log(f"Solicitando metadados de IA via Ollama (modelo: {ollama_model})...")
            try:
                meta_res = core.analyzer.generate_viral_cut_metadata(snippet_text, model=ollama_model)
                cut_title = meta_res.get("titulo_principal") or base_title
                cut_headline = meta_res.get("headline_topo") or cut_title
                cut_desc = meta_res.get("descricao") or "Confira este momento imperdível! Curta e comente."
                cut_hashtags = meta_res.get("hashtags", ["#shorts", "#viral", "#cortes", "#reels"])
                cut_tags_seo = meta_res.get("tags_seo", "cortes, viral, shorts, podcast")
                _log(f"Título IA gerado: '{cut_title}'")
                _log(f"Headline Concisa do Topo: '{cut_headline}'")
            except Exception as ex_ia:
                _log(f"Aviso na geração de IA: {ex_ia}. Usando título base.")
                cut_title = base_title
                cut_headline = base_title
                cut_desc = f"Confira este trecho: {base_title}"
                cut_hashtags = ["#shorts", "#viral", "#cortes"]
                cut_tags_seo = "shorts, cortes, viral"
        else:
            _log("Transcrição vazia para este intervalo. Usando metadados padrão.")
            cut_title = base_title
            cut_headline = base_title
            cut_desc = f"Confira este trecho: {base_title}"
            cut_hashtags = ["#shorts", "#viral", "#cortes"]
            cut_tags_seo = "shorts, cortes, viral"

        # 4. Renderização do Vídeo
        safe_aspect = aspect_ratio_mode.replace(":", "-")
        temp_corte_path = os.path.join(data_dir, f"temp_batch_{idx}_{safe_aspect}.mp4")

        _log(f"Iniciando recorte e renderização via core.video_processor.cut_video...")
        _log(f"Destino temporário: {temp_corte_path}")

        if progress_callback:
            progress_callback(idx, total, f"[{idx+1}/{total}] Renderizando '{cut_title[:30]}...' em {aspect_ratio_mode}...")

        resolved_music_path = params.get("bg_music_track_path")
        if not resolved_music_path and params.get("bg_music_track_id"):
            from core.audio_mixer import get_track_path_by_id
            resolved_music_path = get_track_path_by_id(params.get("bg_music_track_id"))
            _log(f"Trilha sonora resolvida: ID={params.get('bg_music_track_id')} -> Path={resolved_music_path}")

        # Restrição para vídeos longos / 16:9
        is_series_or_169 = (aspect_ratio_mode == "16:9")
        eff_headline = False if is_series_or_169 else params.get("headline_enabled", False)
        eff_zoom_punch = False if is_series_or_169 else params.get("zoom_punch_enabled", False)
        eff_climax_zoom = False if is_series_or_169 else params.get("climax_zoom_enabled", False)
        eff_progress_bar = False if is_series_or_169 else params.get("progress_bar_enabled", False)
        eff_callout = False if is_series_or_169 else params.get("callout_enabled", False)

        # Resolve parâmetros de blur garantindo cálculo dinâmico por corte
        eff_blur_zoom = params.get("blur_zoom")
        eff_blur_pan = params.get("blur_pan")

        if (eff_blur_zoom is None or eff_blur_pan is None) and aspect_ratio_mode == "9:16_blur":
            try:
                from core.face_tracker import calculate_auto_blur_params
                pref = params.get("person_preference", "both")
                margin = params.get("face_margin_ratio", 1.55)
                auto_p = calculate_auto_blur_params(video_full_path, start_t, pref, margin)
                if auto_p.get("face_detected"):
                    eff_blur_zoom = auto_p["zoom"]
                    eff_blur_pan = auto_p["pan"]
                    _log(f"Auto-Blur dinâmico calculado para [{start_t}]: Zoom={eff_blur_zoom:.2f}x, Pan={eff_blur_pan:+.2f} (Dual Shot={auto_p.get('dual_shot')})")
            except Exception as e:
                _log(f"Aviso ao calcular auto-blur para [{start_t}]: {e}")

        if eff_blur_zoom is None:
            eff_blur_zoom = params.get("blur_zoom_custom", 1.35)
        if eff_blur_pan is None:
            eff_blur_pan = params.get("blur_pan_custom", 0.0)

        cut_res = core.video_processor.cut_video(
            video_full_path,
            start_t,
            end_t,
            temp_corte_path,
            aspect_ratio_mode=aspect_ratio_mode,
            horizontal_zoom=params.get("horizontal_zoom", 1.0),
            blur_zoom=eff_blur_zoom,
            blur_pan=eff_blur_pan,
            blur_intensity=params.get("blur_intensity", 25),
            blur_auto_tracking=params.get("blur_auto_tracking", True),
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
            # Fase 3 & 4: Retenção & Áudio Ducking
            headline_enabled=eff_headline,
            headline_text=cut_headline,
            headline_preset=params.get("headline_preset", "yellow_black"),
            headline_text_color=params.get("headline_text_color", "#000000"),
            headline_bg_color=params.get("headline_bg_color", "#FFE600"),
            headline_font_size=params.get("headline_font_size", 46),
            headline_margin_top=params.get("headline_margin_top", 120),
            emojis_enabled=params.get("emojis_enabled", False) if not is_series_or_169 else False,
            zoom_punch_enabled=eff_zoom_punch,
            bg_music_enabled=params.get("bg_music_enabled", False),
            bg_music_track_path=resolved_music_path,
            bg_music_volume=params.get("bg_music_volume", 0.15),
            ducking_preset=params.get("ducking_preset", "medio"),
            # Fase 4: Retenção Dinâmica & Thumbnails
            progress_bar_enabled=eff_progress_bar,
            progress_bar_color=params.get("progress_bar_color", "#FF0000"),
            progress_bar_height=params.get("progress_bar_height", 8),
            callout_enabled=eff_callout,
            callout_text=params.get("callout_text", ""),
            callout_duration=params.get("callout_duration", 4.5),
            climax_zoom_enabled=eff_climax_zoom,
            thumbnail_enabled=params.get("thumbnail_enabled", True),
        )

        _log(f"Retorno de cut_video: {cut_res}")

        if cut_res.get("error"):
            _log(f"ERRO NO CORTE {idx+1}: {cut_res['error']}")
            results.append({
                "item": item,
                "title": cut_title,
                "error": cut_res["error"],
                "success": False
            })
            continue

        if not os.path.exists(temp_corte_path) or os.path.getsize(temp_corte_path) == 0:
            err_not_found = f"Vídeo temporário renderizado não encontrado em {temp_corte_path}"
            _log(f"ERRO: {err_not_found}")
            results.append({
                "item": item,
                "title": cut_title,
                "error": err_not_found,
                "success": False
            })
            continue

        _log(f"Vídeo renderizado com sucesso ({os.path.getsize(temp_corte_path)} bytes). Criando pacote de publicação...")

        # 5. Criação do Pacote Estruturado (incluindo thumbnail)
        pkg_res = core.export_kit.create_viral_package(
            video_path=temp_corte_path,
            title=cut_title,
            description=cut_desc,
            hashtags=cut_hashtags,
            tags_seo=cut_tags_seo,
            aspect_mode=aspect_ratio_mode,
            output_base_dir=data_dir,
            orig_video_info=orig_info,
            thumbnail_path=cut_res.get("thumbnail_path")
        )
        _log(f"Pacote criado em: {pkg_res.get('package_dir')}")
        _log(f"Arquivo final: {pkg_res.get('video_filename')}")

        # Remove arquivo temporário se a cópia final foi criada
        if os.path.exists(temp_corte_path):
            try:
                os.remove(temp_corte_path)
            except Exception:
                pass

        # 6. Registra no Catálogo de Cortes
        out_res = core.video_processor.get_video_resolution(pkg_res["video_dest_path"])
        _log(f"Resolução identificada: {out_res}. Registrando no cuts_catalog.json...")

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
            resolution=out_res,
            thumbnail_path=pkg_res.get("thumbnail_dest_path")
        )

        _log(f"SUCESSO: Corte [{idx+1}/{total}] concluído e registrado no catálogo!")

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

    _log(f"\n=== FINALIZADO: {len([r for r in results if r.get('success')])} sucessos, {len([r for r in results if r.get('error')])} erros, {len([r for r in results if r.get('skipped')])} ignorados ===")

    if progress_callback:
        progress_callback(total, total, f"Concluído! {len(results)} cortes processados.")

    return results
