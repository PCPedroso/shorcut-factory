import streamlit as st
import os
import re
import json
import importlib
import numpy as np
from urllib.parse import urlparse, parse_qs
from datetime import datetime

import core.extractor
import core.transcriber
import core.analyzer
import core.video_processor
import core.face_tracker
import core.library_manager
import core.config_manager
import core.export_kit
import core.cuts_catalog
import core.batch_processor
import core.headline_drawer
import core.audio_mixer
import core.retention_effects
import core.integrations
import core.thumbnail_generator
import core.quick_editor
import core.overlay_manager

importlib.reload(core.extractor)
importlib.reload(core.transcriber)
importlib.reload(core.analyzer)
importlib.reload(core.video_processor)
importlib.reload(core.face_tracker)
importlib.reload(core.library_manager)
importlib.reload(core.config_manager)
importlib.reload(core.export_kit)
importlib.reload(core.cuts_catalog)
importlib.reload(core.batch_processor)
importlib.reload(core.headline_drawer)
importlib.reload(core.audio_mixer)
importlib.reload(core.retention_effects)
importlib.reload(core.integrations)
importlib.reload(core.thumbnail_generator)
importlib.reload(core.quick_editor)
importlib.reload(core.overlay_manager)

from core.extractor import (
    download_audio, get_video_metadata, get_video_id,
    clean_music_title, detect_music_category_suggestion,
    parse_time_str, format_time_sec
)
from core.transcriber import transcribe_audio, fetch_youtube_transcript
from core.analyzer import analyze_transcript, build_suggested_bundles, build_golden_rule_micro_cuts, normalize_time_mask
from core.video_processor import (
    download_full_video, cut_video, get_video_resolution,
    extract_audio_from_local_video, extract_thumbnail_from_video, generate_local_video_id,
    generate_local_dual_video_id, generate_dual_split_preview, compose_dual_video_split_sequence
)
from core.library_manager import get_library, add_or_update_video_in_library, remove_video_from_library
from core.config_manager import load_settings, save_all_settings, save_setting
from core.export_kit import build_cut_folder_name, create_viral_package
from core.cuts_catalog import get_cut_entry, get_format_instance, register_cut_instance, update_cut_texts_only, delete_entire_cut, delete_format_instance, load_cuts_catalog, set_active_thumbnail_variation, update_cut_thumbnail_in_catalog
from core.batch_processor import process_batch_cuts
from core.headline_drawer import (
    HEADLINE_PRESETS, generate_headline_preview, apply_headline_to_video,
    clean_and_condense_headline, format_headline_text
)
from core.audio_mixer import list_available_tracks, DUCKING_PRESETS, register_custom_audio_track
from core.music_recognizer import identify_song_from_audio_and_meta
from core.retention_effects import PROGRESS_BAR_COLORS, ENGAGEMENT_CALLOUT_PRESETS
from core.thumbnail_generator import create_cut_thumbnail
from core.integrations import (
    get_youtube_auth_status, authenticate_youtube_oauth, upload_to_youtube_shorts, send_to_webhook
)
from core.quick_editor import (
    get_video_duration, extract_frame_at_timestamp, trim_video, remove_snippet_and_merge,
    load_edit_history, record_quick_edit
)
from core.overlay_manager import apply_overlay_to_video, generate_overlay_preview, OVERLAY_PRESETS
from core.audio_processor import (
    AUDIO_EQUALIZER_PRESETS, equalize_video_audio, generate_audio_preview_sample
)

# Carrega todas as configurações persistentes salvas
_cfg = load_settings()

st.set_page_config(page_title="Fábrica de Cortes", layout="wide")

st.title("✂️ ViralCut - Fábrica de Cortes")

def inject_time_mask_js():
    """Injeta JavaScript no navegador para aplicar máscara interativa HH:MM:SS.ms (com milissegundos de 2 dígitos) aos inputs de tempo."""
    import streamlit.components.v1 as components
    mask_script = """
    <script>
    (function() {
        function formatDigits(val) {
            let clean = val.replace(',', '.');
            let hasDot = clean.includes('.');
            let parts = clean.split('.');
            let mainDigits = parts[0].replace(/\\D/g, '').slice(0, 6);
            let msDigits = parts.length > 1 ? parts[1].replace(/\\D/g, '').slice(0, 2) : '';

            if (!hasDot && clean.replace(/\\D/g, '').length > 6) {
                let fullDigits = clean.replace(/\\D/g, '').slice(0, 8);
                mainDigits = fullDigits.slice(0, 6);
                msDigits = fullDigits.slice(6, 8);
            }

            let base = '';
            if (!mainDigits) {
                base = '';
            } else if (mainDigits.length <= 2) {
                base = mainDigits;
            } else if (mainDigits.length <= 4) {
                base = mainDigits.slice(0, 2) + ':' + mainDigits.slice(2);
            } else {
                base = mainDigits.slice(0, 2) + ':' + mainDigits.slice(2, 4) + ':' + mainDigits.slice(4);
            }

            if (hasDot || msDigits) {
                return base + '.' + msDigits;
            }
            return base;
        }

        function attachMask(input) {
            if (input.dataset.timeMaskAttached) return;
            input.dataset.timeMaskAttached = "true";

            input.addEventListener('input', function(e) {
                const oldVal = input.value;
                const masked = formatDigits(oldVal);
                if (oldVal !== masked) {
                    input.value = masked;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });

            input.addEventListener('blur', function() {
                let val = input.value.trim().replace(',', '.');
                if (!val) return;
                let parts = val.split('.');
                let mainDigits = parts[0].replace(/\\D/g, '');
                let msDigits = parts.length > 1 ? parts[1].replace(/\\D/g, '') : '00';

                if (msDigits.length === 1) msDigits = msDigits + '0';
                else if (msDigits.length > 2) msDigits = msDigits.slice(0, 2);
                else if (!msDigits) msDigits = '00';

                while (mainDigits.length < 6) {
                    if (mainDigits.length <= 2) mainDigits = mainDigits.padStart(6, '0');
                    else if (mainDigits.length === 3 || mainDigits.length === 4) mainDigits = '00' + mainDigits;
                    else if (mainDigits.length === 5) mainDigits = '0' + mainDigits;
                }
                const finalVal = mainDigits.slice(0, 2) + ':' + mainDigits.slice(2, 4) + ':' + mainDigits.slice(4, 6) + '.' + msDigits;
                if (input.value !== finalVal) {
                    input.value = finalVal;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }

        function scanTimeInputs() {
            try {
                const parentDoc = window.parent.document;
                const inputs = parentDoc.querySelectorAll('input[type="text"]');
                inputs.forEach(inp => {
                    const label = (inp.getAttribute('aria-label') || '').toLowerCase();
                    const ph = (inp.getAttribute('placeholder') || '').toLowerCase();
                    if (label.includes('(hh:mm:ss') || label.includes('tempo inicial') || label.includes('tempo final') || ph.includes('00:00:00') || ph.includes('00:10:00')) {
                        attachMask(inp);
                    }
                });
            } catch (e) {}
        }

        setInterval(scanTimeInputs, 400);
        scanTimeInputs();
    })();
    </script>
    """
    components.html(mask_script, height=0, width=0)

inject_time_mask_js()

def safe_display_image(img_source, caption=None, use_container_width=True):
    """
    Exibe imagens no Streamlit lendo diretamente os bytes em memória
    para garantir 100% de estabilidade de renderização no Windows/Chrome.
    """
    if img_source is None:
        return False
    if isinstance(img_source, np.ndarray):
        if img_source.size > 0:
            st.image(img_source, caption=caption, use_container_width=use_container_width)
            return True
        return False
    if isinstance(img_source, str) and os.path.exists(img_source):
        try:
            with open(img_source, "rb") as f:
                data = f.read()
            if data:
                st.image(data, caption=caption, use_container_width=use_container_width)
                return True
        except Exception:
            pass
    elif isinstance(img_source, (bytes, bytearray)):
        st.image(img_source, caption=caption, use_container_width=use_container_width)
        return True
    elif hasattr(img_source, "save") or hasattr(img_source, "convert"):
        st.image(img_source, caption=caption, use_container_width=use_container_width)
        return True
    return False

def safe_display_video(video_path: str):
    """Garante reprodução e streaming instantâneo de vídeo MP4 sem erros de storage."""
    if not video_path:
        st.warning("Arquivo de vídeo não encontrado.")
        return
    abs_p = os.path.abspath(video_path)
    if not os.path.exists(abs_p) or os.path.getsize(abs_p) == 0:
        st.warning(f"Arquivo de vídeo não encontrado ou vazio: {video_path}")
        return
    try:
        with open(abs_p, "rb") as f_v:
            st.video(f_v.read())
    except Exception:
        try:
            st.video(abs_p)
        except Exception as e_vid:
            st.error(f"Erro ao reproduzir vídeo: {e_vid}")

def open_in_file_explorer(target_path: str) -> bool:
    """
    Abre a pasta diretamente no Explorador de Arquivos do Windows (ou seleciona o arquivo).
    """
    if not target_path or not os.path.exists(target_path):
        return False
    try:
        norm_p = os.path.normpath(target_path)
        if os.path.isfile(norm_p):
            subprocess.Popen(f'explorer /select,"{norm_p}"', shell=True)
        else:
            os.startfile(norm_p)
        return True
    except Exception:
        return False

def render_quick_editor_component(video_path: str, unique_key: str):
    """
    Componente interativo de edição rápida / ajuste fino para cortar pequenos trechos do vídeo.
    """
    if not video_path or not os.path.exists(video_path):
        return

    dur = get_video_duration(video_path)
    if dur < 0.5:
        return

    # Carrega histórico de edições persistente do vídeo
    edit_history = load_edit_history(video_path)
    latest_edit = edit_history[0] if edit_history else st.session_state.get(f"last_edit_status_{unique_key}")

    # Título dinâmico do Expander sinalizando se houve edição
    expander_label = f"✂️ Edição Rápida / Ajuste Fino de Trechos (Duração: {dur:.1f}s)"
    if latest_edit:
        expander_label += f" — 🟢 Último Ajuste: {latest_edit['action']} ({latest_edit['timestamp']})"

    should_expand = bool(st.session_state.get(f"just_edited_{unique_key}", False))

    with st.expander(expander_label, expanded=should_expand):
        st.caption("Ajuste o vídeo diretamente sem precisar abrir softwares externos:")

        # ── SINALIZAÇÃO CLARA E PERSISTENTE DA ÚLTIMA EDIÇÃO ─────────────────
        if latest_edit:
            st.success(
                f"✅ **Edição Rápida Concluída com Sucesso!**\n\n"
                f"• **Ação Realizada:** `{latest_edit['action']}` ({latest_edit['mode']})\n\n"
                f"• **Detalhes do Ajuste:** {latest_edit['details']}\n\n"
                f"• **Arquivo Afetado:** `{latest_edit['output_file']}` — *Concluído em {latest_edit['timestamp']}*"
            )

        # ── HISTÓRICO DE EDIÇÕES DESTE VÍDEO ─────────────────────────────────
        if edit_history:
            with st.expander(f"📜 Histórico de Edições Deste Vídeo ({len(edit_history)} registro{'s' if len(edit_history) > 1 else ''})", expanded=False):
                st.markdown("Veja abaixo todos os ajustes e edições aplicados a este corte:")
                for idx_h, item_h in enumerate(edit_history):
                    st.markdown(
                        f"**{idx_h + 1}. {item_h['action']}** — `{item_h['timestamp']}` (`{item_h['mode']}`)\n\n"
                        f"↳ **Detalhes:** {item_h['details']}  |  **Arquivo:** `{item_h['output_file']}`"
                    )
                    if idx_h < len(edit_history) - 1:
                        st.markdown("---")

        col_mode, col_suf = st.columns([1.5, 1.0])
        with col_mode:
            save_mode = st.radio(
                "Destino do vídeo editado:",
                ["🔄 Substituir o vídeo atual", "✨ Salvar como um novo vídeo"],
                index=0,
                horizontal=True,
                key=f"edit_save_mode_{unique_key}"
            )
        with col_suf:
            custom_suffix = ""
            if "Salvar como um novo vídeo" in save_mode:
                custom_suffix = st.text_input(
                    "Sufixo da nova versão:",
                    value="_editado",
                    key=f"edit_suffix_{unique_key}"
                ).strip()
                if not custom_suffix.startswith("_"):
                    custom_suffix = f"_{custom_suffix}"

        tab_trim, tab_snip, tab_overlay, tab_headline, tab_audio = st.tabs([
            "✂️ Aparar (Trim)", 
            "🗑️ Remover Trecho",
            "🎨 Banner (Overlay)",
            "🏷️ Headline de Topo",
            "🎙️ Equalizador & Áudio"
        ])

        with tab_trim:
            st.markdown("##### ✂️ Aparar Vídeo")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                start_trim = st.number_input(
                    "Ponto Inicial (segundos):",
                    min_value=0.0,
                    max_value=max(0.0, float(dur - 0.5)),
                    value=0.0,
                    step=0.1,
                    key=f"trim_start_{unique_key}"
                )
            with col_t2:
                end_trim = st.number_input(
                    "Ponto Final (segundos):",
                    min_value=min(float(dur), start_trim + 0.5),
                    max_value=float(dur),
                    value=float(dur),
                    step=0.1,
                    key=f"trim_end_{unique_key}"
                )

            # Prévia visual dos frames de entrada e saída
            col_pf1, col_pf2 = st.columns(2)
            with col_pf1:
                st.caption(f"📍 Frame de Início ({start_trim:.1f}s):")
                f_start = extract_frame_at_timestamp(video_path, start_trim)
                if f_start is not None:
                    safe_display_image(f_start, use_container_width=True)
            with col_pf2:
                st.caption(f"🏁 Frame Final ({end_trim:.1f}s):")
                f_end = extract_frame_at_timestamp(video_path, max(0.0, end_trim - 0.1))
                if f_end is not None:
                    safe_display_image(f_end, use_container_width=True)

            dur_result = end_trim - start_trim
            st.info(f"⏱️ Nova duração resultante: **{dur_result:.1f} segundos** (removendo {start_trim:.1f}s no início e {dur - end_trim:.1f}s no final).")

            btn_label_trim = "✂️ Salvar como Novo Vídeo Aparado" if "Salvar como um novo vídeo" in save_mode else "✂️ Aplicar Corte no Vídeo Atual"
            if st.button(btn_label_trim, key=f"btn_apply_trim_{unique_key}", type="primary", use_container_width=True):
                with st.spinner("Aparando vídeo via FFmpeg..."):
                    out_target = None
                    if "Salvar como um novo vídeo" in save_mode:
                        v_dir = os.path.dirname(video_path)
                        b_name, ext = os.path.splitext(os.path.basename(video_path))
                        out_target = os.path.join(v_dir, f"{b_name}{custom_suffix}{ext}")

                    trim_res = trim_video(video_path, start_trim, end_trim, output_path=out_target)
                    if trim_res.get("error"):
                        st.error(f"Erro ao aparar vídeo: {trim_res['error']}")
                    else:
                        entry = record_quick_edit(
                            video_path=video_path,
                            action_name="✂️ Aparar (Trim)",
                            details=f"Início: {start_trim:.1f}s | Fim: {end_trim:.1f}s | Nova Duração: {trim_res.get('new_duration', dur_result):.1f}s",
                            output_path=out_target
                        )
                        st.session_state[f"last_edit_status_{unique_key}"] = entry
                        st.session_state[f"just_edited_{unique_key}"] = True
                        if out_target:
                            st.session_state[f"last_edited_video_{unique_key}"] = out_target
                        st.rerun()

        with tab_snip:
            st.markdown("##### 🗑️ Remover Trecho do Meio")
            st.caption("Selecione o intervalo indesejado (ex: gafe, silêncio longo, tosse). O início e o fim serão unidos automaticamente.")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                snip_start = st.number_input(
                    "Início do Trecho a Deletar (segundos):",
                    min_value=0.0,
                    max_value=max(0.0, float(dur - 0.2)),
                    value=min(1.0, float(dur * 0.2)),
                    step=0.1,
                    key=f"snip_start_{unique_key}"
                )
            with col_s2:
                snip_end = st.number_input(
                    "Fim do Trecho a Deletar (segundos):",
                    min_value=min(float(dur), snip_start + 0.1),
                    max_value=float(dur),
                    value=min(float(dur), snip_start + 2.0),
                    step=0.1,
                    key=f"snip_end_{unique_key}"
                )

            col_ps1, col_ps2 = st.columns(2)
            with col_ps1:
                st.caption(f"❌ Início do corte a deletar ({snip_start:.1f}s):")
                f_sstart = extract_frame_at_timestamp(video_path, snip_start)
                if f_sstart is not None:
                    safe_display_image(f_sstart, use_container_width=True)
            with col_ps2:
                st.caption(f"❌ Fim do corte a deletar ({snip_end:.1f}s):")
                f_send = extract_frame_at_timestamp(video_path, snip_end)
                if f_send is not None:
                    safe_display_image(f_send, use_container_width=True)

            dur_after_snip = dur - (snip_end - snip_start)
            st.info(f"⏱️ O trecho de **{snip_start:.1f}s a {snip_end:.1f}s** ({snip_end - snip_start:.1f}s) será descartado. Nova duração: **{dur_after_snip:.1f}s**.")

            btn_label_snip = "🗑️ Excluir Trecho e Salvar Novo Vídeo" if "Salvar como um novo vídeo" in save_mode else "🗑️ Excluir Trecho e Atualizar Vídeo Atual"
            if st.button(btn_label_snip, key=f"btn_apply_snip_{unique_key}", type="primary", use_container_width=True):
                with st.spinner("Excluindo trecho e unindo partes com FFmpeg..."):
                    out_target = None
                    if "Salvar como um novo vídeo" in save_mode:
                        v_dir = os.path.dirname(video_path)
                        b_name, ext = os.path.splitext(os.path.basename(video_path))
                        out_target = os.path.join(v_dir, f"{b_name}{custom_suffix}{ext}")

                    snip_res = remove_snippet_and_merge(video_path, snip_start, snip_end, output_path=out_target)
                    if snip_res.get("error"):
                        st.error(f"Erro ao remover trecho: {snip_res['error']}")
                    else:
                        entry = record_quick_edit(
                            video_path=video_path,
                            action_name="🗑️ Remover Trecho (Snip & Merge)",
                            details=f"Trecho Removido: {snip_start:.1f}s a {snip_end:.1f}s ({snip_end - snip_start:.1f}s) | Nova Duração: {snip_res.get('new_duration', dur_after_snip):.1f}s",
                            output_path=out_target
                        )
                        st.session_state[f"last_edit_status_{unique_key}"] = entry
                        st.session_state[f"just_edited_{unique_key}"] = True
                        if out_target:
                            st.session_state[f"last_edited_video_{unique_key}"] = out_target
                        st.rerun()

        with tab_overlay:
            st.markdown("##### 🎨 Sobreposição de Banner, Tarja (GC) e Marca d'Água")
            st.caption("Adicione tarjas personalizadas, cubra GCs de emissoras de TV ou insira logos com posicionamento e escala customizáveis.")

            # 1. Seleção / Upload de Imagem de Banner
            v_dir = os.path.dirname(video_path)
            existing_imgs = []
            if os.path.exists(v_dir):
                for f_img in os.listdir(v_dir):
                    if f_img.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not f_img.startswith('thumbnail') and not f_img.startswith('temp'):
                        existing_imgs.append(f_img)

            col_src, col_up = st.columns([1.2, 1.8])
            with col_src:
                img_source_choice = st.radio(
                    "Origem da imagem:",
                    ["📁 Arquivos do Projeto", "📤 Enviar Nova Imagem"],
                    key=f"ov_src_choice_{unique_key}"
                )

            selected_banner_path = None
            with col_up:
                if "Arquivos do Projeto" in img_source_choice and existing_imgs:
                    sel_file = st.selectbox(
                        "Selecione a imagem do projeto:",
                        existing_imgs,
                        key=f"ov_sel_file_{unique_key}"
                    )
                    selected_banner_path = os.path.join(v_dir, sel_file)
                else:
                    up_file = st.file_uploader(
                        "Upload de imagem (PNG/JPG/WebP):",
                        type=["png", "jpg", "jpeg", "webp"],
                        key=f"ov_up_file_{unique_key}"
                    )
                    if up_file:
                        temp_save_path = os.path.join(v_dir, f"uploaded_banner_{up_file.name}")
                        with open(temp_save_path, "wb") as f_up:
                            f_up.write(up_file.getbuffer())
                        selected_banner_path = temp_save_path

            # Presets Rápidos
            ov_preset_keys = list(OVERLAY_PRESETS.keys())
            ov_preset_labels = [OVERLAY_PRESETS[k]["name"] for k in ov_preset_keys]
            sel_ov_lbl = st.selectbox(
                "Estilo / Preset Rápido:",
                ov_preset_labels,
                index=0,
                key=f"ov_preset_sel_{unique_key}"
            )
            sel_ov_key = ov_preset_keys[ov_preset_labels.index(sel_ov_lbl)]
            ov_preset_data = OVERLAY_PRESETS[sel_ov_key]

            # Ajustes Finos (Expander)
            with st.expander("⚙️ Ajustes Finos de Posição, Escala e Logo Embutido", expanded=(sel_ov_key == "custom")):
                col_ov1, col_ov2, col_ov3 = st.columns(3)
                with col_ov1:
                    sel_valign = st.selectbox(
                        "Alinhamento Vertical:",
                        ["bottom", "top", "center"],
                        index=["bottom", "top", "center"].index(ov_preset_data.get("valign", "bottom")),
                        key=f"ov_valign_{unique_key}"
                    )
                with col_ov2:
                    sel_scale_mode = st.selectbox(
                        "Modo de Escala:",
                        ["fill", "fit", "cover"],
                        index=["fill", "fit", "cover"].index(ov_preset_data.get("scale_mode", "fill")),
                        format_func=lambda x: {
                            "fill": "Esticar para Preencher (100% largura)",
                            "fit": "Ajustar Proporcionalmente",
                            "cover": "Cobrir e Cortar Excedente"
                        }[x],
                        key=f"ov_scale_mode_{unique_key}"
                    )
                with col_ov3:
                    sel_height_px = st.number_input(
                        "Altura em Pixels (0 = automático):",
                        min_value=0, max_value=1920,
                        value=int(ov_preset_data.get("height_px", 0)),
                        step=10,
                        key=f"ov_hpx_{unique_key}",
                        help="Defina uma altura exata em pixels (ex: 220px para tarjas de TV) quando usar modo 'Esticar'."
                    )

                col_ov4, col_ov5, col_ov6 = st.columns(3)
                with col_ov4:
                    sel_width_pct = st.slider(
                        "Largura (% da tela):",
                        min_value=10, max_value=100,
                        value=int(ov_preset_data.get("width_pct", 100)),
                        step=5,
                        key=f"ov_wpct_{unique_key}"
                    )
                with col_ov5:
                    sel_offset_y = st.number_input(
                        "Margem Vertical Y (px):",
                        min_value=-500, max_value=500,
                        value=int(ov_preset_data.get("offset_y", 0)),
                        step=10,
                        key=f"ov_offy_{unique_key}"
                    )
                with col_ov6:
                    sel_opacity = st.slider(
                        "Opacidade do Banner (%):",
                        min_value=10, max_value=100,
                        value=int(ov_preset_data.get("opacity", 1.0) * 100),
                        step=5,
                        key=f"ov_opac_{unique_key}"
                    ) / 100.0

                # Configuração de Logo / Imagem Secundária Embutida
                st.markdown("---")
                st.markdown("###### 🏷️ Logo / Selo Embutido na Faixa:")
                col_lg1, col_lg2 = st.columns([1.5, 1.5])
                with col_lg1:
                    enable_logo = st.toggle("Adicionar Logo ou Selo Secundário", value=False, key=f"ov_en_logo_{unique_key}")
                    selected_logo_path = None
                    if enable_logo:
                        if existing_imgs:
                            sel_lg_file = st.selectbox("Selecione a imagem do Logo:", existing_imgs, key=f"ov_sel_logo_{unique_key}")
                            selected_logo_path = os.path.join(v_dir, sel_lg_file)
                with col_lg2:
                    if enable_logo:
                        logo_pos = st.selectbox("Posição do Logo no Banner:", ["left", "right", "center"], index=0, key=f"ov_lg_pos_{unique_key}")
                        logo_scale = st.slider("Escala do Logo (% da altura do banner):", min_value=30, max_value=95, value=75, step=5, key=f"ov_lg_scale_{unique_key}") / 100.0
                    else:
                        logo_pos = "left"
                        logo_scale = 0.75

            current_ov_cfg = {
                "valign": sel_valign,
                "halign": "center",
                "scale_mode": sel_scale_mode,
                "width_pct": sel_width_pct,
                "height_px": sel_height_px,
                "offset_x": 0,
                "offset_y": sel_offset_y,
                "opacity": sel_opacity,
                "logo_pos": logo_pos,
                "logo_scale": logo_scale
            }

            # 3. Prévia Visual Instantânea
            if selected_banner_path and os.path.exists(selected_banner_path):
                st.markdown("---")
                st.markdown("##### 👁️ Prévia em Tempo Real:")
                ov_preview_sec = st.slider("Segundo do vídeo para prévia:", min_value=0.0, max_value=float(dur), value=min(2.0, float(dur/2)), step=0.5, key=f"ov_prev_sec_{unique_key}")
                prev_frame = generate_overlay_preview(
                    video_path=video_path,
                    banner_path_or_array=selected_banner_path,
                    config=current_ov_cfg,
                    timestamp_s=ov_preview_sec,
                    logo_path_or_array=selected_logo_path
                )
                if prev_frame is not None:
                    safe_display_image(prev_frame, caption=f"Prévia do Banner aplicado em {ov_preview_sec:.1f}s", use_container_width=True)

            # 4. Botão de Aplicação / Renderização
            st.markdown("")
            btn_label_ov = "🎨 Salvar como Novo Vídeo com Banner" if "Salvar como um novo vídeo" in save_mode else "🎨 Aplicar Banner no Vídeo Atual"
            if st.button(btn_label_ov, key=f"btn_apply_overlay_{unique_key}", type="primary", use_container_width=True):
                with st.spinner("Renderizando vídeo com sobreposição acelerada por GPU (NVENC)..."):
                    out_target = None
                    if "Salvar como um novo vídeo" in save_mode:
                        v_dir_edit = os.path.dirname(video_path)
                        b_name, ext = os.path.splitext(os.path.basename(video_path))
                        suf = custom_suffix if custom_suffix else "_com_banner"
                        out_target = os.path.join(v_dir_edit, f"{b_name}{suf}{ext}")

                    ov_res = apply_overlay_to_video(
                        video_path=video_path,
                        banner_path=selected_banner_path,
                        config=current_ov_cfg,
                        output_path=out_target,
                        logo_path=selected_logo_path
                    )

                    if ov_res.get("error"):
                        st.error(f"Erro ao aplicar banner: {ov_res['error']}")
                    else:
                        entry = record_quick_edit(
                            video_path=video_path,
                            action_name="🎨 Banner / Tarja (Overlay)",
                            details=f"Banner: {os.path.basename(selected_banner_path) if selected_banner_path else 'N/A'} | Modo: {current_ov_cfg.get('scale_mode', 'fill')} | Posição Y: {current_ov_cfg.get('valign', 'bottom')}",
                            output_path=out_target
                        )
                        st.session_state[f"last_edit_status_{unique_key}"] = entry
                        st.session_state[f"just_edited_{unique_key}"] = True
                        if out_target:
                            st.session_state[f"last_edited_video_{unique_key}"] = out_target
                        st.rerun()

        # ── TAB 4: HEADLINE / TÍTULO DE TOPO (PÓS-CORTE) ──────────────────────
        with tab_headline:
            st.markdown("##### 🏷️ Headline / Título de Topo Magnético (Pós-Corte)")
            st.caption("Adicione, ajuste ou troque o título fixo no topo do corte com visualização instantânea em tempo real e renderização ultra-rápida por GPU!")

            # 1. Texto da Headline
            col_htxt, col_hbtn = st.columns([4, 1.2])
            with col_htxt:
                def_hl_text = st.session_state.get("input_cut_headline") or st.session_state.get("input_cut_title") or "PREPARO DE RENAN SANTOS\nESTÁ MUITO ACIMA DO NORMAL"
                hl_text_input = st.text_area(
                    "Texto da Headline (use Enter para quebrar linhas manualmente):",
                    value=def_hl_text,
                    height=80,
                    key=f"hl_post_text_{unique_key}",
                    help="Digite ou edite o texto. Linhas separadas por Enter serão formatadas em caixas independentes estilo TikTok/Reels!"
                )
            with col_hbtn:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("✨ Condensar", key=f"hl_post_condense_{unique_key}", use_container_width=True, help="Ajusta o texto para caixa alta e quebra inteligente de 2 a 3 linhas"):
                    cleaned_hl = clean_and_condense_headline(hl_text_input)
                    if cleaned_hl:
                        st.session_state[f"hl_post_text_{unique_key}"] = format_headline_text(cleaned_hl).replace(r"\N", "\n")
                        st.rerun()

            # 2. Preset de Estilo Rápido
            hl_preset_keys = list(HEADLINE_PRESETS.keys())
            hl_preset_labels = [HEADLINE_PRESETS[k]["name"] for k in hl_preset_keys]
            sel_hl_preset_lbl = st.selectbox(
                "Preset de Estilo da Headline:",
                hl_preset_labels,
                index=0,
                key=f"hl_post_preset_{unique_key}"
            )
            sel_hl_preset_key = hl_preset_keys[hl_preset_labels.index(sel_hl_preset_lbl)]
            sel_hl_preset_data = HEADLINE_PRESETS[sel_hl_preset_key]

            # 3. Controles Customizáveis e Modo de Container
            col_hl_m1, col_hl_m2, col_hl_m3 = st.columns(3)
            with col_hl_m1:
                sel_hl_mode = st.selectbox(
                    "Modo do Container:",
                    ["line_boxes", "single_card", "outline_only"],
                    index=0 if sel_hl_preset_key != "floating_bold" else 2,
                    format_func=lambda x: {
                        "line_boxes": "📦 Caixa por Linha (TikTok/Reels)",
                        "single_card": "🃏 Card Único (Bloco)",
                        "outline_only": "✨ Sem Caixa (Contorno)"
                    }[x],
                    key=f"hl_post_mode_{unique_key}"
                )
            with col_hl_m2:
                saved_margin_top = int(_cfg.get("headline_margin_top", 240))
                sel_hl_margin_top = st.number_input(
                    "Margem do Topo Y (px):",
                    min_value=0,
                    max_value=1200,
                    value=saved_margin_top,
                    step=10,
                    key=f"hl_post_mtop_{unique_key}",
                    help="Distância em pixels a partir da borda superior."
                )
            with col_hl_m3:
                saved_font_size = int(_cfg.get("headline_font_size", 70))
                sel_hl_font_size = st.number_input(
                    "Tamanho da Fonte:",
                    min_value=20,
                    max_value=200,
                    value=saved_font_size,
                    step=2,
                    key=f"hl_post_fsize_{unique_key}"
                )

            with st.expander("⚙️ Ajustes Finos de Cores, Padding, Cantos e Sombra", expanded=False):
                col_hl_c1, col_hl_c2, col_hl_c3, col_hl_c4 = st.columns(4)
                with col_hl_c1:
                    sel_hl_text_color = st.color_picker(
                        "Cor do Texto:",
                        value=sel_hl_preset_data.get("text_color") or sel_hl_preset_data.get("primary_color", "#000000"),
                        key=f"hl_post_tcolor_{unique_key}"
                    )
                with col_hl_c2:
                    sel_hl_bg_color = st.color_picker(
                        "Cor do Fundo / Caixa:",
                        value=sel_hl_preset_data.get("bg_color") or sel_hl_preset_data.get("box_color", "#FFDA29"),
                        key=f"hl_post_bgcolor_{unique_key}"
                    )
                with col_hl_c3:
                    sel_hl_bg_alpha = st.slider(
                        "Opacidade do Fundo (%):",
                        min_value=0, max_value=100,
                        value=95 if sel_hl_preset_key != "floating_bold" else 0,
                        step=5,
                        key=f"hl_post_bgalpha_{unique_key}"
                    ) / 100.0
                with col_hl_c4:
                    sel_hl_align = st.selectbox(
                        "Alinhamento:",
                        ["center", "left", "right"],
                        index=0,
                        format_func=lambda x: {"center": "Centralizado", "left": "Esquerda", "right": "Direita"}[x],
                        key=f"hl_post_align_{unique_key}"
                    )

                col_hl_p1, col_hl_p2, col_hl_p3, col_hl_p4 = st.columns(4)
                with col_hl_p1:
                    sel_hl_pad_h = st.slider("Padding Horizontal:", 10, 80, 28, 2, key=f"hl_post_padh_{unique_key}")
                with col_hl_p2:
                    sel_hl_pad_v = st.slider("Padding Vertical:", 5, 50, 16, 2, key=f"hl_post_padv_{unique_key}")
                with col_hl_p3:
                    sel_hl_line_spacing = st.slider("Espaçamento Linhas:", 0, 50, 14, 2, key=f"hl_post_linesp_{unique_key}")
                with col_hl_p4:
                    sel_hl_corner = st.slider("Cantos Arredondados:", 0, 50, 12, 2, key=f"hl_post_corner_{unique_key}")

                col_hl_s1, col_hl_s2 = st.columns(2)
                with col_hl_s1:
                    sel_hl_max_w_pct = st.slider("Largura Máxima do Bloco (% da tela):", 50, 100, 90, 5, key=f"hl_post_maxw_{unique_key}") / 100.0
                with col_hl_s2:
                    sel_hl_shadow = st.toggle("Sombra Projetada Suave (Drop Shadow)", value=True, key=f"hl_post_shadow_{unique_key}")

            current_hl_cfg = {
                "mode": sel_hl_mode,
                "margin_top": sel_hl_margin_top,
                "font_size": sel_hl_font_size,
                "text_color": sel_hl_text_color,
                "bg_color": sel_hl_bg_color,
                "bg_alpha": sel_hl_bg_alpha,
                "alignment": sel_hl_align,
                "padding_h": sel_hl_pad_h,
                "padding_v": sel_hl_pad_v,
                "line_spacing": sel_hl_line_spacing,
                "corner_radius": sel_hl_corner,
                "max_width_pct": sel_hl_max_w_pct,
                "shadow": sel_hl_shadow,
                "stroke_color": "#000000",
                "stroke_width": 2 if sel_hl_mode == "outline_only" else 0
            }

            # 4. Prévia Visual Instantânea do Frame em Tempo Real
            st.markdown("---")
            st.markdown("##### 👁️ Prévia da Headline em Tempo Real:")
            col_hl_prev_ctrl, col_hl_prev_view = st.columns([1.5, 2.5])
            with col_hl_prev_ctrl:
                hl_preview_sec = st.slider("Segundo para visualização:", 0.0, float(dur), min(1.5, float(dur/2)), 0.5, key=f"hl_post_prev_sec_{unique_key}")
                st.caption("Ajuste qualquer parâmetro acima e a prévia será atualizada instantaneamente!")
            with col_hl_prev_view:
                prev_hl_frame = generate_headline_preview(
                    video_path=video_path,
                    text=hl_text_input,
                    config=current_hl_cfg,
                    timestamp_s=hl_preview_sec
                )
                if prev_hl_frame is not None:
                    safe_display_image(prev_hl_frame, caption=f"Prévia com Headline aos {hl_preview_sec:.1f}s", use_container_width=True)

            # 5. Botão de Aplicação no Vídeo
            st.markdown("")
            btn_label_hl = "🚀 Salvar como Novo Vídeo com Headline" if "Salvar como um novo vídeo" in save_mode else "🚀 Aplicar Headline no Vídeo Atual"
            if st.button(btn_label_hl, key=f"btn_apply_headline_post_{unique_key}", type="primary", use_container_width=True):
                with st.spinner("Queimando Headline no vídeo com aceleração GPU (NVENC)..."):
                    out_target_hl = None
                    if "Salvar como um novo vídeo" in save_mode:
                        v_dir_edit = os.path.dirname(video_path)
                        b_name, ext = os.path.splitext(os.path.basename(video_path))
                        suf = custom_suffix if custom_suffix else "_com_headline"
                        out_target_hl = os.path.join(v_dir_edit, f"{b_name}{suf}{ext}")

                    hl_res = apply_headline_to_video(
                        video_path=video_path,
                        text=hl_text_input,
                        config=current_hl_cfg,
                        output_path=out_target_hl
                    )

                    if hl_res.get("error"):
                        st.error(f"Erro ao aplicar headline: {hl_res['error']}")
                    else:
                        entry = record_quick_edit(
                            video_path=video_path,
                            action_name="🏷️ Headline de Topo",
                            details=f"Texto: '{hl_text_input.replace(chr(10), ' ')}' | Modo: {current_hl_cfg.get('mode', 'line_boxes')} | Preset: {sel_hl_preset_data['name']}",
                            output_path=out_target_hl
                        )
                        st.session_state[f"last_edit_status_{unique_key}"] = entry
                        st.session_state[f"just_edited_{unique_key}"] = True
                        if out_target_hl:
                            st.session_state[f"last_edited_video_{unique_key}"] = out_target_hl
                        st.rerun()

        # ── TAB 5: EQUALIZADOR & TRATAMENTO DE ÁUDIO (PÓS-CORTE) ──────────────
        with tab_audio:
            st.markdown("##### 🎙️ Equalizador, Anti-Estouro & Nivelador de Áudio")
            st.caption("Recupere microfones estourados/saturados, nivele a voz com a torcida/som ambiente e aplique limiter profissional sem perda de qualidade de vídeo!")

            # 1. Seletor de Preset
            eq_preset_keys = list(AUDIO_EQUALIZER_PRESETS.keys())
            eq_preset_labels = [AUDIO_EQUALIZER_PRESETS[k]["name"] for k in eq_preset_keys]
            sel_eq_lbl = st.selectbox(
                "Perfil de Equalização & Tratamento:",
                eq_preset_labels,
                index=0,
                key=f"eq_preset_sel_{unique_key}"
            )
            sel_eq_key = eq_preset_keys[eq_preset_labels.index(sel_eq_lbl)]
            eq_preset_data = AUDIO_EQUALIZER_PRESETS[sel_eq_key]
            st.info(f"💡 **Como atua este perfil**: {eq_preset_data['description']}")

            # 2. Ajustes Finos (Expander)
            with st.expander("⚙️ Ajustes Finos de Equalização, Torcida/Ambiente e Limiter", expanded=(sel_eq_key == "custom")):
                col_eq1, col_eq2, col_eq3 = st.columns(3)
                with col_eq1:
                    sel_highpass = st.slider(
                        "Corte de Graves / Vento (Hz):",
                        min_value=20, max_value=160,
                        value=int(eq_preset_data.get("highpass_hz", 75)),
                        step=5,
                        key=f"eq_highpass_{unique_key}",
                        help="Remove rumbles e barulhos de vento/microfone abaixo desta frequência."
                    )
                with col_eq2:
                    sel_deharsh = st.slider(
                        "Atenuação de Agudos Estridentes (dB):",
                        min_value=-8.0, max_value=2.0,
                        value=float(eq_preset_data.get("deharsh_eq_db", -3.5)),
                        step=0.5,
                        key=f"eq_deharsh_{unique_key}",
                        help="Suaviza frequências agudas metálicas e estouradas do microfone em 3.2 kHz."
                    )
                with col_eq3:
                    sel_limiter_db = st.slider(
                        "Teto Anti-Estouro / Limiter (dB):",
                        min_value=-6.0, max_value=-0.2,
                        value=float(eq_preset_data.get("limiter_limit_db", -1.2)),
                        step=0.1,
                        key=f"eq_limiter_{unique_key}",
                        help="Impede qualquer distorção ou estouro no alto-falante estabelecendo um teto seguro."
                    )

                col_eq4, col_eq5, col_eq6 = st.columns(3)
                with col_eq4:
                    sel_dynaudnorm = st.toggle(
                        "Nivelador Dinâmico (Realçar Torcida/Fundo)",
                        value=bool(eq_preset_data.get("dynaudnorm_enabled", True)),
                        key=f"eq_dynaud_{unique_key}",
                        help="Eleva suavemente o som da torcida/ambiente nas pausas de fala e controla gritos próximos ao microfone."
                    )
                with col_eq5:
                    sel_vol_gain = st.slider(
                        "Ganho Geral de Volume (dB):",
                        min_value=-12.0, max_value=12.0,
                        value=float(eq_preset_data.get("volume_gain_db", 0.0)),
                        step=0.5,
                        key=f"eq_vol_gain_{unique_key}"
                    )
                with col_eq6:
                    sel_denoise = st.toggle(
                        "Redução de Chiado de Fundo (Denoise)",
                        value=bool(eq_preset_data.get("denoise_enabled", False)),
                        key=f"eq_denoise_{unique_key}"
                    )

            current_eq_cfg = {
                "preset_key": sel_eq_key,
                "highpass_hz": sel_highpass,
                "deharsh_eq_db": sel_deharsh,
                "limiter_limit_db": sel_limiter_db,
                "dynaudnorm_enabled": sel_dynaudnorm,
                "dynaudnorm_framelen": int(eq_preset_data.get("dynaudnorm_framelen", 150)),
                "dynaudnorm_maxgain": int(eq_preset_data.get("dynaudnorm_maxgain", 15)),
                "volume_gain_db": sel_vol_gain,
                "denoise_enabled": sel_denoise
            }

            # 3. Prévia de Áudio em Tempo Real
            st.markdown("---")
            st.markdown("##### 🎧 Ouvir Prévia do Áudio Equalizado:")
            col_prev_a1, col_prev_a2 = st.columns([1.5, 2.5])
            with col_prev_a1:
                if st.button("▶️ Gerar / Atualizar Prévia de Áudio", key=f"btn_gen_eq_prev_{unique_key}", use_container_width=True):
                    with st.spinner("Gerando prévia sonora em alta fidelidade..."):
                        prev_a_path = generate_audio_preview_sample(video_path, current_eq_cfg, max_duration_s=min(45.0, float(dur)))
                        if prev_a_path and os.path.exists(prev_a_path):
                            st.session_state[f"last_eq_audio_prev_{unique_key}"] = prev_a_path
                            st.rerun()

            with col_prev_a2:
                last_a_prev = st.session_state.get(f"last_eq_audio_prev_{unique_key}")
                if last_a_prev and os.path.exists(last_a_prev):
                    st.audio(last_a_prev, format="audio/mp4")

            # 4. Botão de Aplicação no Vídeo
            st.markdown("")
            btn_label_eq = "🚀 Salvar como Novo Vídeo Equalizado" if "Salvar como um novo vídeo" in save_mode else "🚀 Aplicar Equalização no Vídeo Atual"
            if st.button(btn_label_eq, key=f"btn_apply_eq_{unique_key}", type="primary", use_container_width=True):
                with st.spinner("Equalizando áudio e gerando vídeo final (Stream Copy em ~1s)..."):
                    out_target_eq = None
                    if "Salvar como um novo vídeo" in save_mode:
                        v_dir_edit = os.path.dirname(video_path)
                        b_name, ext = os.path.splitext(os.path.basename(video_path))
                        suf = custom_suffix if custom_suffix else "_audio_equalizado"
                        out_target_eq = os.path.join(v_dir_edit, f"{b_name}{suf}{ext}")

                    eq_res = equalize_video_audio(
                        video_path=video_path,
                        config=current_eq_cfg,
                        output_path=out_target_eq
                    )

                    if eq_res.get("error"):
                        st.error(f"Erro ao equalizar áudio: {eq_res['error']}")
                    else:
                        entry = record_quick_edit(
                            video_path=video_path,
                            action_name="🎙️ Equalizador & Tratamento de Áudio",
                            details=f"Perfil: {eq_preset_data['name']} | Highpass: {current_eq_cfg.get('highpass_hz')}Hz | De-Harsh: {current_eq_cfg.get('deharsh_eq_db')}dB | Limiter: {current_eq_cfg.get('limiter_limit_db')}dB",
                            output_path=out_target_eq
                        )
                        st.session_state[f"last_edit_status_{unique_key}"] = entry
                        st.session_state[f"just_edited_{unique_key}"] = True
                        if out_target_eq:
                            st.session_state[f"last_edited_video_{unique_key}"] = out_target_eq
                        st.rerun()

        # Se uma nova versão foi gerada recentemente para este componente, exibe player e download
        last_new_v = st.session_state.get(f"last_edited_video_{unique_key}")
        if last_new_v and os.path.exists(last_new_v):
            st.markdown("---")
            st.markdown(f"##### 🎬 Última Nova Versão Gerada (`{os.path.basename(last_new_v)}`):")
            safe_display_video(last_new_v)
            with open(last_new_v, "rb") as vf_last_new:
                st.download_button(
                    label=f"💾 Baixar Nova Versão ({os.path.basename(last_new_v)})",
                    data=vf_last_new,
                    file_name=os.path.basename(last_new_v),
                    mime="video/mp4",
                    type="primary",
                    use_container_width=True,
                    key=f"dl_last_new_btn_{unique_key}"
                )

def load_video_saved_artifacts(video_id: str):
    """Carrega todas as ações e análises salvas individualmente para o vídeo."""
    if not video_id:
        return
    v_dir = os.path.join("data", video_id)
    
    # 1. Transcrição
    t_file = os.path.join(v_dir, "transcript.json")
    if os.path.exists(t_file):
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                t_data = json.load(f)
                st.session_state.full_text = t_data.get("full_text", "")
                st.session_state.segments = t_data.get("segments", [])
                st.session_state.transcript_source = t_data.get("source", "YouTube Oficial")
                st.session_state.transcription_done = True
        except Exception:
            pass
            
    # 2. Pautas Mapeadas
    p_file = os.path.join(v_dir, "pautas.json")
    if os.path.exists(p_file):
        try:
            with open(p_file, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                st.session_state.pautas = p_data.get("pautas", []) if isinstance(p_data, dict) else p_data
        except Exception:
            st.session_state.pautas = []
    else:
        st.session_state.pautas = []

    # 3. Séries (10+ min)
    s_file = os.path.join(v_dir, "series.json")
    if os.path.exists(s_file):
        try:
            with open(s_file, "r", encoding="utf-8") as f:
                st.session_state.bundles = json.load(f)
        except Exception:
            st.session_state.bundles = []
    else:
        st.session_state.bundles = []

    # 4. Ganchos Virais & Pequenos Cortes (Shorts / Reels)
    sh_file = os.path.join(v_dir, "shorts.json")
    if os.path.exists(sh_file):
        try:
            with open(sh_file, "r", encoding="utf-8") as f:
                st.session_state.shorts = json.load(f)
        except Exception:
            st.session_state.shorts = []
    else:
        st.session_state.shorts = []

    # 5. Histórico de Passos / Cortes Montados
    steps_file = os.path.join(v_dir, "saved_steps.json")
    if os.path.exists(steps_file):
        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                st.session_state.saved_steps = json.load(f)
        except Exception:
            st.session_state.saved_steps = []
    else:
        st.session_state.saved_steps = []


# Barra Lateral (Biblioteca & Configurações)
st.sidebar.header("📚 Biblioteca de Vídeos")

library_videos = get_library()
if library_videos:
    st.sidebar.caption(f"**{len(library_videos)}** vídeos registrados")
    for v in library_videos:
        v_title = v.get("title", "Vídeo sem título")
        v_date = v.get("upload_date", "Data N/D")
        v_id = v.get("video_id")
        
        with st.sidebar.expander(f"🎬 {v_title[:35]}...", expanded=False):
            if v.get("thumbnail"):
                if os.path.exists(v["thumbnail"]):
                    safe_display_image(v["thumbnail"], use_container_width=True)
                elif str(v["thumbnail"]).startswith("http"):
                    st.image(v["thumbnail"], use_container_width=True)
            st.markdown(f"**Título:** {v_title}")
            st.markdown(f"📅 **Data:** `{v_date}`")
            if v.get("channel"):
                st.caption(f"📺 {v['channel']}")
            if v.get("added_at"):
                st.caption(f"➕ Adicionado: {v['added_at']}")
            
            col_l1, col_l2 = st.columns(2)
            with col_l1:
                if st.button("📥 Abrir", key=f"btn_load_{v_id}", use_container_width=True):
                    v_url = v.get("url") or (f"local://{v_id}" if str(v_id).startswith("local_") else f"https://www.youtube.com/watch?v={v_id}")
                    st.session_state.video_url = v_url
                    st.session_state.input_yt_url = v_url
                    load_video_saved_artifacts(v_id)
                    st.rerun()

            with col_l2:
                if st.button("🗑️ Excluir", key=f"btn_del_{v_id}", use_container_width=True):
                    remove_video_from_library(v_id, delete_folder=True)
                    if st.session_state.get("video_url") == v.get("url") or st.session_state.get("input_yt_url") == v.get("url"):
                        st.session_state.transcription_done = False
                        st.session_state.full_text = ""
                        st.session_state.segments = []
                        st.session_state.pautas = []
                        st.session_state.bundles = []
                        st.session_state.shorts = []
                        st.session_state.saved_steps = []
                        st.session_state.video_url = ""
                        st.session_state.input_yt_url = ""
                    st.rerun()
else:
    st.sidebar.info("Nenhum vídeo registrado ainda. Insira uma URL abaixo para começar!")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configurações")

_devices = ["cuda", "cpu"]
_dev_idx = _devices.index(_cfg.get("device_option", "cuda")) if _cfg.get("device_option") in _devices else 0
device_option = st.sidebar.selectbox("Dispositivo de Processamento", _devices, index=_dev_idx)

_model_sizes = ["tiny", "small", "medium", "large-v3"]
_ms_idx = _model_sizes.index(_cfg.get("model_size", "small")) if _cfg.get("model_size") in _model_sizes else 1
model_size = st.sidebar.selectbox("Tamanho do Modelo Whisper", _model_sizes, index=_ms_idx)

st.sidebar.markdown("---")
st.sidebar.subheader("Modelo de IA (Ollama)")
_ollama_models = ["llama3", "mistral", "qwen2.5", "llama3.1", "gemma2"]
_om_idx = _ollama_models.index(_cfg.get("ollama_model", "llama3")) if _cfg.get("ollama_model") in _ollama_models else 0
ollama_model = st.sidebar.selectbox(
    "Modelo:",
    _ollama_models,
    index=_om_idx,
    help="Para usar mistral ou qwen2.5 rode: ollama pull mistral"
)

# 🌐 Integrações & Exportação Direta (Fase 3)
st.sidebar.markdown("---")
with st.sidebar.expander("🌐 Integrações & Webhooks (Fase 3)", expanded=False):
    st.markdown("##### 🔴 YouTube Shorts API")
    yt_secrets_path = st.text_input(
        "Caminho do client_secrets.json:",
        value=_cfg.get("youtube_client_secrets_path", "data/client_secrets.json"),
        help="Arquivo de credenciais baixado do Google Cloud Console para envio direto ao YouTube Shorts."
    )
    auth_status = get_youtube_auth_status(yt_secrets_path)
    if auth_status.get("authenticated"):
        st.success(f"✅ {auth_status['message']}")
    else:
        st.info(f"ℹ️ {auth_status['message']}")
        if os.path.exists(yt_secrets_path):
            if st.button("🔑 Conectar Conta Google / YouTube", key="btn_auth_yt_side", use_container_width=True):
                with st.spinner("Abrindo autenticação Google no navegador..."):
                    auth_res = authenticate_youtube_oauth(yt_secrets_path)
                    if auth_res.get("success"):
                        st.success("🎉 Conectado com sucesso ao YouTube!")
                        st.rerun()
                    else:
                        st.error(f"Erro na autenticação: {auth_res.get('error')}")

    st.markdown("##### 📡 Webhook (n8n / Make / Zapier)")
    sb_webhook_url = st.text_input(
        "URL do Webhook:",
        value=_cfg.get("webhook_url", ""),
        placeholder="https://sua-instancia-n8n.com/webhook/cortes",
        help="Endpoint HTTP para disparo de automação quando um corte for concluído."
    )
    sb_webhook_auth = st.text_input(
        "Header de Autorização (Opcional):",
        value=_cfg.get("webhook_auth_header", ""),
        placeholder="Bearer seu_token_aqui",
        type="password"
    )
    if sb_webhook_url:
        if st.button("🧪 Testar Webhook", key="btn_test_webhook", use_container_width=True):
            with st.spinner("Enviando payload de teste..."):
                test_res = send_to_webhook(
                    sb_webhook_url,
                    {"event": "test_ping", "message": "Conexão com ViralCut testada com sucesso!"},
                    auth_header=sb_webhook_auth
                )
                if test_res.get("success"):
                    st.success(f"✅ Conexão OK! HTTP {test_res.get('status_code')}")
                else:
                    st.error(f"❌ Falha: {test_res.get('error')}")

    save_setting("youtube_client_secrets_path", yt_secrets_path)
    save_setting("webhook_url", sb_webhook_url)
    save_setting("webhook_auth_header", sb_webhook_auth)


# Estado da sessão
if 'transcription_done' not in st.session_state:
    st.session_state.transcription_done = False
if 'full_text' not in st.session_state:
    st.session_state.full_text = ""
if 'segments' not in st.session_state:
    st.session_state.segments = []
if 'ai_results' not in st.session_state:
    st.session_state.ai_results = ""
if 'video_url' not in st.session_state:
    st.session_state.video_url = ""
if 'input_yt_url' not in st.session_state:
    st.session_state.input_yt_url = st.session_state.video_url

video_url = st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""

# Seção 1
st.header("1. Ingestão e Transcrição do Vídeo")

input_mode = st.radio(
    "Escolha a Origem do Vídeo:",
    ["🌐 Link da Web (YouTube, Instagram, TikTok...)", "💻 Carregar Arquivo de Vídeo Local (MP4, MOV, MKV...)"],
    index=0 if not str(st.session_state.get("video_url", "")).startswith("local://") and not str(st.session_state.get("video_url", "")).startswith("local_") else 1,
    horizontal=True,
    key="video_source_mode"
)

if input_mode.startswith("🌐 Link"):
    video_url = st.text_input(
        "Cole a URL do vídeo (YouTube, Instagram Reel/Post, TikTok, etc.):",
        key="input_yt_url",
        placeholder="https://www.youtube.com/watch?v=... ou https://www.instagram.com/reel/..."
    )

    with st.expander("⏱️ Baixar Apenas um Trecho Específico (Lives / Podcasts Longos)", expanded=False):
        st.caption("💡 **Time-Range Slicing**: Em vez de baixar gigabytes de um vídeo ou live de 2 a 4 horas, baixe apenas o trecho desejado. É até **50x mais rápido** e consome muito menos disco!")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            yt_start_time_str = st.text_input(
                "Início do Trecho (opcional):",
                placeholder="Ex: 00:15:00 ou 900",
                key="input_yt_slice_start",
                help="Formato flexível: HH:MM:SS, MM:SS, 1h30m ou segundos."
            )
        with col_t2:
            yt_end_time_str = st.text_input(
                "Fim do Trecho (opcional):",
                placeholder="Ex: 00:20:30 ou 1230",
                key="input_yt_slice_end",
                help="Formato flexível: HH:MM:SS, MM:SS, 1h30m ou segundos."
            )

        parsed_s = parse_time_str(yt_start_time_str)
        parsed_e = parse_time_str(yt_end_time_str)
        if parsed_s is not None or parsed_e is not None:
            s_label = format_time_sec(parsed_s or 0.0)
            if parsed_e is not None and parsed_s is not None and parsed_e > parsed_s:
                diff_sec = parsed_e - parsed_s
                e_label = format_time_sec(parsed_e)
                dur_txt = f"{int(diff_sec // 60)}m {int(diff_sec % 60)}s" if diff_sec >= 60 else f"{int(diff_sec)}s"
                st.success(f"🎯 **Trecho selecionado**: de `{s_label}` até `{e_label}` (Duração: **{dur_txt}**). Economia massiva de tempo e banda!")
            elif parsed_s is not None and parsed_e is None:
                st.info(f"🎯 **Trecho selecionado**: a partir de `{s_label}` até o fim do vídeo.")
            elif parsed_e is not None and parsed_s is None:
                e_label = format_time_sec(parsed_e)
                st.info(f"🎯 **Trecho selecionado**: do início até `{e_label}`.")
            elif parsed_e is not None and parsed_s is not None and parsed_e <= parsed_s:
                st.error("⚠️ O tempo final deve ser maior que o tempo inicial.")

    col_yt_b1, col_yt_b2 = st.columns([1.5, 1])
    with col_yt_b1:
        btn_process_yt = st.button("🚀 Processar Vídeo Online (Completo)", type="primary", key="btn_process_yt", use_container_width=True)
    with col_yt_b2:
        btn_audio_yt = st.button("🎵 Extrair Apenas Áudio (MP3)", key="btn_extract_audio_yt", use_container_width=True)

    # Identificação de corte de tempo ativo
    active_slice_start = parse_time_str(st.session_state.get("input_yt_slice_start", ""))
    active_slice_end = parse_time_str(st.session_state.get("input_yt_slice_end", ""))

    if btn_audio_yt:
        if not video_url:
            st.warning("Por favor, insira uma URL válida.")
        else:
            base_vid = get_video_id(video_url)
            if not base_vid:
                st.error("URL inválida ou formato de link não reconhecido.")
            else:
                if active_slice_start is not None or active_slice_end is not None:
                    s_tag = f"{int(active_slice_start)}" if active_slice_start is not None else "0"
                    e_tag = f"{int(active_slice_end)}" if active_slice_end is not None else "end"
                    video_id = f"{base_vid}_t_{s_tag}_{e_tag}"
                else:
                    video_id = base_vid

                data_dir = os.path.join("data", video_id)
                os.makedirs(data_dir, exist_ok=True)
                audio_path = os.path.join(data_dir, "audio.mp3")

                with st.spinner("🎵 Extraindo áudio de alta qualidade (192kbps MP3) e identificando a música exata..."):
                    meta = get_video_metadata(video_url)
                    v_title = meta.get("title") or f"Áudio {video_id}"
                    if active_slice_start is not None or active_slice_end is not None:
                        s_lbl = format_time_sec(active_slice_start or 0.0)
                        e_lbl = format_time_sec(active_slice_end) if active_slice_end else "fim"
                        v_title = f"{v_title} ({s_lbl} - {e_lbl})"

                    v_date = meta.get("upload_date")
                    v_thumb = meta.get("thumbnail")
                    v_dur = meta.get("duration")
                    is_live_flag = meta.get("is_live", False)

                    add_or_update_video_in_library(
                        video_id=video_id,
                        title=v_title,
                        upload_date_raw=v_date,
                        url=video_url,
                        thumbnail_url=v_thumb,
                        duration_sec=v_dur,
                        channel=meta.get("channel"),
                        is_live=is_live_flag
                    )

                    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                        download_audio(
                            video_url,
                            audio_path,
                            is_live=is_live_flag,
                            start_sec=active_slice_start,
                            end_sec=active_slice_end
                        )

                    # Identificação Inteligente da Música / Som (ignora títulos genéricos e busca o som real)
                    from core.music_recognizer import identify_song_from_audio_and_meta
                    rec_res = identify_song_from_audio_and_meta(
                        audio_path=audio_path,
                        meta=meta,
                        ollama_model=ollama_model if 'ollama_model' in locals() or 'ollama_model' in globals() else "llama3:latest",
                        use_ai=True
                    )
                    v_clean_music = rec_res["music_title"]
                    v_sugg_cat = rec_res["category_label"]
                    v_rec_source = rec_res.get("source", "Identificação Automática")

                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    st.session_state["extracted_music_card"] = {
                        "path": audio_path,
                        "clean_title": v_clean_music,
                        "orig_title": v_title,
                        "suggested_category": v_sugg_cat,
                        "rec_source": v_rec_source,
                        "video_id": video_id
                    }
                else:
                    st.error("Não foi possível extrair o áudio do link fornecido.")

    # Renderiza o Card de Identificação e Biblioteca se houver música extraída
    if "extracted_music_card" in st.session_state and st.session_state["extracted_music_card"]:
        m_info = st.session_state["extracted_music_card"]
        m_path = m_info["path"]
        if os.path.exists(m_path):
            with st.container():
                st.success(f"🎉 **Música / Som Identificado ({m_info.get('rec_source', 'Reconhecimento')})!**")
                col_mc1, col_mc2 = st.columns([2, 1.2])
                with col_mc1:
                    custom_m_name = st.text_input(
                        "🏷️ Nome da Música / Artista (Identificado):",
                        value=m_info.get("clean_title", "Trilha Sonora"),
                        help="Nome real da música (ex: 'Iron Maiden - Fear of the Dark') que aparecerá nos seletores de trilha de fundo.",
                        key="input_clean_music_name"
                    )
                    all_cat_options = [
                        "⚡ Phonk / Superação & Força",
                        "🎸 Heavy Rock / Adrenalina",
                        "🎭 Cômico / Meme & Humor",
                        "🏆 Épico / Glória & Inspiração",
                        "🧘 Lo-Fi Chill / Relax",
                        "🔥 Tensão / Suspense",
                        "🎵 Trilha Personalizada"
                    ]
                    default_cat_idx = all_cat_options.index(m_info.get("suggested_category")) if m_info.get("suggested_category") in all_cat_options else 6
                    custom_m_cat = st.selectbox(
                        "🎨 Estilo / Vibe do Som:",
                        all_cat_options,
                        index=default_cat_idx,
                        key="sel_music_detected_cat"
                    )

                    with open(m_path, "rb") as af_dl:
                        st.audio(af_dl.read(), format="audio/mp3")

                with col_mc2:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    with open(m_path, "rb") as af_dl:
                        st.download_button(
                            label="📥 Baixar MP3 no Computador",
                            data=af_dl.read(),
                            file_name=f"{re.sub(r'[^a-zA-Z0-9_]+', '_', custom_m_name)[:35]}.mp3",
                            mime="audio/mp3",
                            use_container_width=True,
                            key="btn_download_extracted_audio_yt"
                        )
                    
                    if st.button("🌟 Adicionar à Biblioteca de Trilhas de Fundo", type="primary", use_container_width=True, key="btn_add_to_audio_library"):
                        reg_res = register_custom_audio_track(
                            source_path=m_path,
                            title=custom_m_name,
                            category_name=custom_m_cat,
                            description=f"Som de fundo ({custom_m_cat}) extraído do vídeo"
                        )
                        if reg_res.get("error"):
                            st.error(reg_res["error"])
                        else:
                            st.success(f"🚀 **{custom_m_name}** foi adicionada permanentemente à biblioteca `assets/audio` e já pode ser usada em qualquer corte!")
                            st.rerun()

    if btn_process_yt:
        if not video_url:
            st.warning("Por favor, insira uma URL válida.")
        else:
            st.session_state.video_url = video_url
            base_vid = get_video_id(video_url)
            if not base_vid:
                st.error("URL inválida ou formato de link não reconhecido.")
            else:
                if active_slice_start is not None or active_slice_end is not None:
                    s_tag = f"{int(active_slice_start)}" if active_slice_start is not None else "0"
                    e_tag = f"{int(active_slice_end)}" if active_slice_end is not None else "end"
                    video_id = f"{base_vid}_t_{s_tag}_{e_tag}"
                else:
                    video_id = base_vid

                data_dir = os.path.join("data", video_id)
                os.makedirs(data_dir, exist_ok=True)
                transcript_file = os.path.join(data_dir, "transcript.json")
                audio_path = os.path.join(data_dir, "audio.mp3")
                
                # Passo 1: Extrai e Registra Metadados na Biblioteca
                with st.spinner("Buscando informações e metadados oficiais do vídeo..."):
                    meta = get_video_metadata(video_url)
                    v_title = meta.get("title") or f"Vídeo {video_id}"
                    if active_slice_start is not None or active_slice_end is not None:
                        s_lbl = format_time_sec(active_slice_start or 0.0)
                        e_lbl = format_time_sec(active_slice_end) if active_slice_end else "fim"
                        v_title = f"{v_title} ({s_lbl} - {e_lbl})"

                    v_date = meta.get("upload_date")
                    v_thumb = meta.get("thumbnail")
                    v_dur = meta.get("duration")
                    is_live_flag = meta.get("is_live", False)

                    add_or_update_video_in_library(
                        video_id=video_id,
                        title=v_title,
                        upload_date_raw=v_date,
                        url=video_url,
                        thumbnail_url=v_thumb,
                        duration_sec=v_dur,
                        channel=meta.get("channel"),
                        is_live=is_live_flag
                    )

                if is_live_flag:
                    st.warning("🔴 **Transmissão Ao Vivo (LIVE) Detectada!** O vídeo ainda está em andamento. O sistema capturará o conteúdo transmitido.")

                # CACHE: Verifica se já temos a transcrição pronta
                if os.path.exists(transcript_file):
                    st.success("✅ Cache encontrado! Carregando transcrição e histórico salvo...")
                    load_video_saved_artifacts(video_id)
                    if is_live_flag:
                        st.info("💡 **Dica de Live**: Como a transmissão continua no YouTube, você pode sincronizar novos minutos a qualquer momento.")
                        if st.button("🔄 Sincronizar / Atualizar com o Momento Atual da Live", key="btn_sync_live_cache"):
                            if os.path.exists(transcript_file):
                                os.remove(transcript_file)
                            if os.path.exists(audio_path):
                                os.remove(audio_path)
                            v_full_cache = os.path.join(data_dir, "video_full.mp4")
                            if os.path.exists(v_full_cache):
                                os.remove(v_full_cache)
                            st.rerun()
                    
                    # Download automático do vídeo completo (se ainda não baixado)
                    _vfull_cache_path = os.path.join(data_dir, "video_full.mp4")
                    if not is_live_flag and not os.path.exists(_vfull_cache_path):
                        with st.spinner("⏳ Baixando vídeo (ou trecho) em 1080p para habilitar o Recorte Final..."):
                            download_full_video(
                                video_url,
                                _vfull_cache_path,
                                is_live=False,
                                start_sec=active_slice_start,
                                end_sec=active_slice_end
                            )
                        if os.path.exists(_vfull_cache_path):
                            st.success("🎥 Vídeo baixado e pronto para recorte!")
                    elif os.path.exists(_vfull_cache_path):
                        st.info(f"🎥 Vídeo já no cache — pronto para recorte.")
                else:
                    platform_label = "Instagram" if video_id.startswith("ig_") else ("TikTok" if video_id.startswith("tt_") else "YouTube/Web")
                    st.info(f"Iniciando extração do vídeo ({platform_label})...")
                    if meta.get("title"):
                        st.success(f"🎬 Vídeo: **{v_title}** (Publicado em: `{meta.get('upload_date')}`) ")

                    # Passo 2: Transcrição (Tenta legendas oficiais primeiro se for YouTube e sem corte complexo, fallback Whisper PT-BR)
                    transcribe_res = {}
                    if not base_vid.startswith(("ig_", "tt_", "tw_", "local_")):
                        with st.spinner("Buscando transcrição oficial do YouTube (alta precisão e fidelidade)..."):
                            raw_yt_tr = fetch_youtube_transcript(base_vid)

                        if raw_yt_tr.get("transcript_segments"):
                            # Se há corte por tempo ativo, filtra e re-baseia os segmentos oficiais
                            if active_slice_start is not None or active_slice_end is not None:
                                s_min = active_slice_start or 0.0
                                s_max = active_slice_end if active_slice_end is not None else float('inf')
                                sliced_segs = []
                                for seg in raw_yt_tr["transcript_segments"]:
                                    seg_start = seg.get("start", 0.0)
                                    seg_end = seg.get("end", 0.0)
                                    if seg_end >= s_min and seg_start <= s_max:
                                        adj = dict(seg)
                                        adj["start"] = max(0.0, seg_start - s_min)
                                        adj["end"] = max(0.0, seg_end - s_min)
                                        sliced_segs.append(adj)
                                if sliced_segs:
                                    transcribe_res = {
                                        "transcript_segments": sliced_segs,
                                        "full_text": " ".join([s["text"] for s in sliced_segs]),
                                        "source": f"YouTube Oficial (Trecho {format_time_sec(s_min)} - {format_time_sec(s_max) if s_max != float('inf') else 'Fim'})"
                                    }
                            else:
                                transcribe_res = raw_yt_tr

                            if transcribe_res.get("transcript_segments"):
                                st.success(f"⚡ Transcrição oficial do YouTube carregada ({len(transcribe_res['transcript_segments'])} segmentos)! Máxima precisão.")
                                langs = raw_yt_tr.get("available_languages", [])
                                if len(langs) > 1:
                                    st.caption(f"🌐 **Idiomas detectados no YouTube ({len(langs)} faixas):** {', '.join([l['name'] for l in langs])}")

                    # Se não obteve segmentos oficiais (ou for Instagram/TikTok/Web), processa áudio via Whisper local
                    if not transcribe_res.get("transcript_segments"):
                        if not base_vid.startswith(("ig_", "tt_", "tw_", "local_")):
                            st.info("Legendas oficiais em português não encontradas no YouTube. Processando áudio via Whisper local (PT-BR)...")
                        else:
                            st.info(f"Processando áudio do {platform_label} via Whisper local (PT-BR)...")

                        if os.path.exists(audio_path):
                            audio_res = {"path": audio_path, "error": None}
                        else:
                            with st.spinner(f"Baixando áudio do vídeo ({platform_label})..."):
                                audio_res = download_audio(
                                    video_url,
                                    output_path=audio_path,
                                    is_live=is_live_flag,
                                    start_sec=active_slice_start,
                                    end_sec=active_slice_end
                                )
                                
                        if audio_res.get("error"):
                            st.error(f"Erro no download: {audio_res['error']}")
                            transcribe_res = {"error": audio_res["error"]}
                        else:
                            # Atualiza a duração se era desconhecida
                            if os.path.exists(audio_path):
                                v_dur = get_video_duration(audio_path)
                                add_or_update_video_in_library(
                                    video_id=video_id,
                                    title=v_title,
                                    upload_date_raw=v_date,
                                    url=video_url,
                                    thumbnail_url=v_thumb,
                                    duration_sec=v_dur,
                                    channel=meta.get("channel"),
                                    is_live=is_live_flag
                                )

                            with st.spinner(f"Transcrevendo áudio com Whisper ({model_size}) em Português na {device_option.upper()}..."):
                                transcribe_res = transcribe_audio(
                                    audio_res["path"], 
                                    model_size=model_size, 
                                    device=device_option,
                                    language="pt"
                                )
                                
                    if transcribe_res.get("error"):
                        st.error(f"Erro na transcrição: {transcribe_res['error']}")
                    else:
                        st.success("Transcrição concluída com sucesso!")
                        st.session_state.transcription_done = True
                        st.session_state.full_text = transcribe_res["full_text"]
                        st.session_state.segments = transcribe_res["transcript_segments"]
                        st.session_state.transcript_source = transcribe_res.get("source", "YouTube Oficial")
                        
                        # Salvar no cache
                        with open(transcript_file, "w", encoding="utf-8") as f:
                            json.dump({
                                "full_text": st.session_state.full_text,
                                "segments": st.session_state.segments,
                                "source": st.session_state.transcript_source
                            }, f, ensure_ascii=False, indent=4)

                        # Download automático do vídeo completo/trecho logo após a transcrição
                        _vfull_path = os.path.join(data_dir, "video_full.mp4")
                        if not is_live_flag and not os.path.exists(_vfull_path):
                            with st.spinner("⏬ Baixando vídeo em 1080p Full HD (necessário para o Recorte Final)..."):
                                _vres = download_full_video(
                                    video_url,
                                    _vfull_path,
                                    is_live=False,
                                    start_sec=active_slice_start,
                                    end_sec=active_slice_end
                                )
                            if _vres.get("error"):
                                st.warning(f"⚠️ Vídeo baixado parcialmente ou com aviso: {_vres['error']}")
                            elif os.path.exists(_vfull_path):
                                st.success("🎥 Vídeo baixado e pronto para recorte na Seção 3!")

else:
    # 💻 Modo Arquivo de Vídeo Local do Computador (Suporte a 1 ou 2 vídeos)
    uploaded_files = st.file_uploader(
        "Selecione ou arraste até 2 arquivos de vídeo do seu computador:",
        type=["mp4", "mov", "mkv", "avi", "webm"],
        accept_multiple_files=True,
        key="local_video_uploader",
        help="Formatos suportados: MP4, MOV, MKV, AVI, WebM. Selecione 1 arquivo para corte individual ou 2 arquivos para composição sequencial inteligente."
    )

    if not uploaded_files:
        st.info("💡 **Dica**: Você pode carregar **1 arquivo** para processamento padrão ou até **2 arquivos** para criar uma **Composição Dupla (Split Screen com frame P&B ➔ Transição para Tela Cheia)**.")

    elif len(uploaded_files) > 2:
        st.warning("⚠️ **Limite excedido**: Você selecionou mais de 2 arquivos. Por favor, remova os excedentes e selecione no máximo 2 vídeos.")

    elif len(uploaded_files) == 1:
        # Modo Individual (1 Vídeo)
        uploaded_file = uploaded_files[0]
        col_loc1, col_loc2 = st.columns([2, 1])
        with col_loc1:
            custom_local_title = st.text_input(
                "Título do Vídeo (Opcional):",
                value=os.path.splitext(uploaded_file.name)[0] if uploaded_file else "",
                placeholder="Ex: Entrevista Podcast com Convidado",
                key="custom_local_title"
            )
        with col_loc2:
            st.caption("📁 Arquivo individual carregado do disco, processado 100% offline com Whisper e GPU.")

        col_loc_b1, col_loc_b2 = st.columns([1.5, 1])
        with col_loc_b1:
            btn_process_local = st.button("🚀 Processar Arquivo Local (Completo)", type="primary", key="btn_process_local", use_container_width=True)
        with col_loc_b2:
            btn_audio_local = st.button("🎵 Extrair Apenas Áudio (MP3)", key="btn_extract_audio_local", use_container_width=True)

        if btn_audio_local:
            orig_filename = uploaded_file.name
            video_id = generate_local_video_id(orig_filename)
            data_dir = os.path.join("data", video_id)
            os.makedirs(data_dir, exist_ok=True)
            v_full_path = os.path.join(data_dir, "video_full.mp4")
            audio_path = os.path.join(data_dir, "audio.mp3")
            v_title = custom_local_title.strip() if custom_local_title.strip() else os.path.splitext(orig_filename)[0]

            with st.spinner("🎵 Extraindo faixa de áudio de alta qualidade e identificando a música exata..."):
                file_bytes = uploaded_file.getbuffer()
                with open(v_full_path, "wb") as f_out:
                    f_out.write(file_bytes)
                v_dur = get_video_duration(v_full_path)
                extract_audio_from_local_video(v_full_path, audio_path)

                add_or_update_video_in_library(
                    video_id=video_id,
                    title=v_title,
                    upload_date_raw=datetime.now().strftime("%d/%m/%Y"),
                    url=f"local://{video_id}",
                    thumbnail_url=None,
                    duration_sec=int(v_dur),
                    channel="Vídeo Local (Upload)",
                    is_live=False
                )

                from core.music_recognizer import identify_song_from_audio_and_meta
                rec_res = identify_song_from_audio_and_meta(
                    audio_path=audio_path,
                    meta={"title": v_title},
                    ollama_model=ollama_model if 'ollama_model' in locals() or 'ollama_model' in globals() else "llama3:latest",
                    use_ai=True
                )
                v_clean_music = rec_res["music_title"]
                v_sugg_cat = rec_res["category_label"]
                v_rec_source = rec_res.get("source", "Identificação Automática")

            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                st.session_state["extracted_music_card"] = {
                    "path": audio_path,
                    "clean_title": v_clean_music,
                    "orig_title": v_title,
                    "suggested_category": v_sugg_cat,
                    "rec_source": v_rec_source,
                    "video_id": video_id
                }
            else:
                st.error("Não foi possível extrair o áudio do arquivo selecionado.")

        if btn_process_local:
            orig_filename = uploaded_file.name
            video_id = generate_local_video_id(orig_filename)
            local_url = f"local://{video_id}"
            st.session_state.video_url = local_url
            st.session_state.input_yt_url = local_url

            data_dir = os.path.join("data", video_id)
            os.makedirs(data_dir, exist_ok=True)
            v_full_path = os.path.join(data_dir, "video_full.mp4")
            audio_path = os.path.join(data_dir, "audio.mp3")
            thumb_path = os.path.join(data_dir, "thumbnail.jpg")
            transcript_file = os.path.join(data_dir, "transcript.json")

            # 1. Salva o arquivo de vídeo na pasta do projeto
            with st.spinner("Salvando e organizando arquivo de vídeo local..."):
                file_bytes = uploaded_file.getbuffer()
                with open(v_full_path, "wb") as f_out:
                    f_out.write(file_bytes)

            # 2. Metadados e Thumbnail
            v_title = custom_local_title.strip() if custom_local_title.strip() else os.path.splitext(orig_filename)[0]
            v_dur = get_video_duration(v_full_path)
            extract_thumbnail_from_video(v_full_path, thumb_path, timestamp_sec=min(2.0, max(0.0, v_dur * 0.1)))

            add_or_update_video_in_library(
                video_id=video_id,
                title=v_title,
                upload_date_raw=datetime.now().strftime("%d/%m/%Y"),
                url=local_url,
                thumbnail_url=thumb_path if os.path.exists(thumb_path) else None,
                duration_sec=int(v_dur),
                channel="Vídeo Local (Upload)",
                is_live=False
            )

            # 3. Extração de Áudio e Transcrição
            if os.path.exists(transcript_file):
                st.success("✅ Cache de transcrição encontrado para este arquivo! Carregando...")
                load_video_saved_artifacts(video_id)
            else:
                with st.spinner("Extraindo áudio do vídeo local com FFmpeg..."):
                    audio_res = extract_audio_from_local_video(v_full_path, audio_path)

                if audio_res.get("error"):
                    st.error(f"Erro ao extrair áudio: {audio_res['error']}")
                else:
                    with st.spinner(f"Transcrevendo áudio com Whisper ({model_size}) na {device_option.upper()}..."):
                        transcribe_res = transcribe_audio(
                            audio_path,
                            model_size=model_size,
                            device=device_option
                        )

                    if transcribe_res.get("error"):
                        st.error(f"Erro na transcrição: {transcribe_res['error']}")
                    else:
                        st.success("🎉 Transcrição do vídeo local concluída com sucesso!")
                        st.session_state.transcription_done = True
                        st.session_state.full_text = transcribe_res["full_text"]
                        st.session_state.segments = transcribe_res["transcript_segments"]
                        st.session_state.transcript_source = "Whisper Local (Arquivo do Computador)"

                        with open(transcript_file, "w", encoding="utf-8") as f:
                            json.dump({
                                "full_text": st.session_state.full_text,
                                "segments": st.session_state.segments,
                                "source": st.session_state.transcript_source
                            }, f, ensure_ascii=False, indent=4)

    else:
        # Modo Composição Dupla (2 Vídeos Selecionados)
        file_a = uploaded_files[0]
        file_b = uploaded_files[1]

        st.info(
            "✨ **Composição Sequencial Dupla Ativada (2 Vídeos Selecionados)**\n\n"
            "• **1ª Etapa (Início)**: A tela fica dividida (Split). O **1º vídeo** é reproduzido na parte superior com áudio ativo, enquanto o **2º vídeo** fica congelado na parte inferior em modo **Monocromático (Preto e Branco)**.\n"
            "• **2ª Etapa (Transição)**: Assim que o 1º vídeo termina, o **2º vídeo assume 100% da tela cheia** com áudio ativo até a conclusão."
        )

        st.markdown("### 🎬 1. Configuração da Ordem de Reprodução")
        order_choice = st.radio(
            "Escolha qual vídeo será reproduzido primeiro:",
            [
                f"1️⃣ Início: **{file_a.name}** (Topo) ➔ Sequência: **{file_b.name}** (Base P&B ➔ Tela Cheia)",
                f"2️⃣ Início: **{file_b.name}** (Topo) ➔ Sequência: **{file_a.name}** (Base P&B ➔ Tela Cheia)"
            ],
            index=0,
            key="dual_video_order_selection"
        )

        first_file = file_a if order_choice.startswith("1️⃣") else file_b
        second_file = file_b if order_choice.startswith("1️⃣") else file_a

        st.markdown("### ⚙️ 2. Ajustes Visuais da Composição")
        col_d1, col_d2 = st.columns([2, 2])
        with col_d1:
            default_dual_title = f"{os.path.splitext(first_file.name)[0]} + {os.path.splitext(second_file.name)[0]}"
            custom_dual_title = st.text_input(
                "Título do Projeto Composto (Opcional):",
                value=default_dual_title,
                key="custom_dual_title"
            )
            dual_freeze_bw = st.checkbox(
                "🖼️ Efeito Monocromático (Preto e Branco) no frame congelado da base",
                value=True,
                help="Mantém o segundo vídeo em preto e branco enquanto o primeiro vídeo está tocando no topo.",
                key="dual_freeze_bw_toggle"
            )

        with col_d2:
            dual_freeze_ts = st.number_input(
                "⏱️ Segundo do frame congelado do 2º vídeo:",
                min_value=0.0,
                max_value=3600.0,
                value=0.0,
                step=0.5,
                help="Timestamp do segundo vídeo que será capturado para servir de imagem congelada na base.",
                key="dual_freeze_ts_input"
            )
            col_d2_sub1, col_d2_sub2 = st.columns(2)
            with col_d2_sub1:
                dual_aspect_choice = st.selectbox(
                    "📐 Formato Final:",
                    ["9:16 (Vertical Reels/TikTok/Shorts)", "16:9 (Horizontal)"],
                    index=0,
                    key="dual_aspect_choice"
                )
            with col_d2_sub2:
                dual_divider_color = st.selectbox(
                    "Linha Divisória:",
                    ["black", "white", "gray", "none"],
                    format_func=lambda x: {"black": "Preta", "white": "Branca", "gray": "Cinza", "none": "Sem Linha"}[x],
                    index=0,
                    key="dual_divider_color_choice"
                )

        # 3. Ambientação Sonora Independente para Cada Vídeo
        st.markdown("### 🎧 3. Ambientação Sonora Diferenciada (Música para Cada Vídeo)")
        st.caption("Escolha uma trilha sonora para ilustrar o contraste entre o 1º vídeo (Início/Split) e o 2º vídeo (Superação/Tela Cheia).")
        
        dual_available_tracks = [{"id": "none", "title": "🚫 Sem Trilha (Apenas Áudio Original)", "path": None}] + list_available_tracks()
        dual_track_labels = [f"{t['title']}" for t in dual_available_tracks]
        
        # Padrões sugeridos: 1º Vídeo = Cômico/Humor (se existir) ou Lo-Fi; 2º Vídeo = Phonk Agressivo (se existir) ou Heavy Rock
        v1_default_idx = 0
        v2_default_idx = 0
        
        # Verifica se houve upload recente pelo usuário
        last_up_v1 = st.session_state.get("_last_uploaded_dual_v1")
        last_up_v2 = st.session_state.get("_last_uploaded_dual_v2")

        for i_t, t_obj in enumerate(dual_available_tracks):
            if last_up_v1 and t_obj["id"] == last_up_v1:
                v1_default_idx = i_t
            elif not last_up_v1 and t_obj["id"] == "comedy_meme_funny":
                v1_default_idx = i_t
            
            if last_up_v2 and t_obj["id"] == last_up_v2:
                v2_default_idx = i_t
            elif not last_up_v2 and t_obj["id"] == "phonk_power_override":
                v2_default_idx = i_t

        if v1_default_idx == 0 and len(dual_available_tracks) > 5 and not last_up_v1:
            v1_default_idx = 5 # Lo-fi
        if v2_default_idx == 0 and len(dual_available_tracks) > 1 and not last_up_v2:
            v2_default_idx = 1 # Phonk ou primeiro

        # Aplica qualquer override de upload pendente ANTES de instanciar os selectboxes
        if "_override_dual_v1_music" in st.session_state:
            st.session_state["sel_dual_v1_music"] = st.session_state.pop("_override_dual_v1_music")
        if "_override_dual_v2_music" in st.session_state:
            st.session_state["sel_dual_v2_music"] = st.session_state.pop("_override_dual_v2_music")

        if "sel_dual_v1_music" in st.session_state and st.session_state["sel_dual_v1_music"] not in dual_track_labels:
            st.session_state["sel_dual_v1_music"] = dual_track_labels[v1_default_idx]
        if "sel_dual_v2_music" in st.session_state and st.session_state["sel_dual_v2_music"] not in dual_track_labels:
            st.session_state["sel_dual_v2_music"] = dual_track_labels[v2_default_idx]

        col_snd1, col_snd2 = st.columns(2)
        with col_snd1:
            st.markdown(f"**🎵 Som do 1º Vídeo** (`{first_file.name[:25]}...` - Split Top):")
            sel_v1_lbl = st.selectbox("Trilha Sonora da Parte 1:", dual_track_labels, index=v1_default_idx, key="sel_dual_v1_music")
            sel_v1_obj = dual_available_tracks[dual_track_labels.index(sel_v1_lbl)]
            dual_v1_track_id = sel_v1_obj["id"]
            
            dual_v1_vol = st.slider("Volume da Trilha 1:", min_value=0.05, max_value=0.60, value=0.18, step=0.02, key="sl_dual_v1_vol")
            if sel_v1_obj.get("path") and os.path.exists(sel_v1_obj["path"]):
                with open(sel_v1_obj["path"], "rb") as af_p1:
                    _fmt1 = "audio/mp3" if sel_v1_obj["path"].endswith(".mp3") else "audio/wav"
                    st.audio(af_p1.read(), format=_fmt1)

            with st.expander("📁 Carregar Arquivo de Som do Computador (Parte 1)", expanded=False):
                up_v1 = st.file_uploader("Upload de Áudio (.mp3, .wav, .m4a):", type=["mp3", "wav", "m4a", "aac", "ogg"], key="uploader_dual_v1")
                if up_v1 is not None:
                    _sig_v1 = f"{up_v1.name}_{up_v1.size}"
                    if st.session_state.get("_processed_sig_v1") != _sig_v1:
                        st.session_state["_processed_sig_v1"] = _sig_v1
                        _tmp_p1 = os.path.join("data", f"temp_dual1_{up_v1.name}")
                        os.makedirs("data", exist_ok=True)
                        with open(_tmp_p1, "wb") as _f_up1:
                            _f_up1.write(up_v1.getbuffer())
                        _reg_v1 = register_custom_audio_track(_tmp_p1, title=f"📁 {os.path.splitext(up_v1.name)[0]}", category_name="Personalizada (Parte 1)")
                        if _reg_v1.get("track"):
                            st.session_state["_last_uploaded_dual_v1"] = _reg_v1["track"]["id"]
                            st.session_state["_override_dual_v1_music"] = _reg_v1["track"]["title"]
                            st.rerun()

        with col_snd2:
            st.markdown(f"**⚡ Som do 2º Vídeo** (`{second_file.name[:25]}...` - Tela Cheia):")
            sel_v2_lbl = st.selectbox("Trilha Sonora da Parte 2:", dual_track_labels, index=v2_default_idx, key="sel_dual_v2_music")
            sel_v2_obj = dual_available_tracks[dual_track_labels.index(sel_v2_lbl)]
            dual_v2_track_id = sel_v2_obj["id"]
            
            dual_v2_vol = st.slider("Volume da Trilha 2:", min_value=0.05, max_value=0.70, value=0.25, step=0.02, key="sl_dual_v2_vol")
            if sel_v2_obj.get("path") and os.path.exists(sel_v2_obj["path"]):
                with open(sel_v2_obj["path"], "rb") as af_p2:
                    _fmt2 = "audio/mp3" if sel_v2_obj["path"].endswith(".mp3") else "audio/wav"
                    st.audio(af_p2.read(), format=_fmt2)

            with st.expander("📁 Carregar Arquivo de Som do Computador (Parte 2)", expanded=False):
                up_v2 = st.file_uploader("Upload de Áudio (.mp3, .wav, .m4a):", type=["mp3", "wav", "m4a", "aac", "ogg"], key="uploader_dual_v2")
                if up_v2 is not None:
                    _sig_v2 = f"{up_v2.name}_{up_v2.size}"
                    if st.session_state.get("_processed_sig_v2") != _sig_v2:
                        st.session_state["_processed_sig_v2"] = _sig_v2
                        _tmp_p2 = os.path.join("data", f"temp_dual2_{up_v2.name}")
                        os.makedirs("data", exist_ok=True)
                        with open(_tmp_p2, "wb") as _f_up2:
                            _f_up2.write(up_v2.getbuffer())
                        _reg_v2 = register_custom_audio_track(_tmp_p2, title=f"📁 {os.path.splitext(up_v2.name)[0]}", category_name="Personalizada (Parte 2)")
                        if _reg_v2.get("track"):
                            st.session_state["_last_uploaded_dual_v2"] = _reg_v2["track"]["id"]
                            st.session_state["_override_dual_v2_music"] = _reg_v2["track"]["title"]
                            st.rerun()

        dual_audio_ducking = st.checkbox(
            "🎧 Aplicar Audio Ducking Inteligente (Atenua a música automaticamente durante as falas)",
            value=True,
            key="dual_audio_ducking_tgl",
            help="Reduz suavemente o volume das trilhas enquanto os oradores falam, garantindo 100% de clareza nas vozes."
        )

        col_dual_b1, col_dual_b2 = st.columns([1.5, 1])
        with col_dual_b1:
            btn_process_dual_local = st.button("🚀 Processar Composição Dupla (Split ➔ Full Screen)", type="primary", key="btn_process_dual_local", use_container_width=True)
        with col_dual_b2:
            btn_audio_dual = st.button("🎵 Extrair Áudio da Composição (MP3)", key="btn_extract_audio_dual", use_container_width=True)

        if btn_audio_dual:
            video_id = generate_local_dual_video_id(first_file.name, second_file.name)
            data_dir = os.path.join("data", video_id)
            os.makedirs(data_dir, exist_ok=True)
            raw_v1_path = os.path.join(data_dir, "raw_video_1.mp4")
            raw_v2_path = os.path.join(data_dir, "raw_video_2.mp4")
            v_full_path = os.path.join(data_dir, "video_full.mp4")
            audio_path = os.path.join(data_dir, "audio.mp3")
            v_title = custom_dual_title.strip() if custom_dual_title.strip() else default_dual_title

            with st.spinner("🎵 Extraindo e unificando trilha de áudio da composição dupla com ambientação sonora..."):
                with open(raw_v1_path, "wb") as f1_out:
                    f1_out.write(first_file.getbuffer())
                with open(raw_v2_path, "wb") as f2_out:
                    f2_out.write(second_file.getbuffer())

                comp_res = compose_dual_video_split_sequence(
                    video1_path=raw_v1_path,
                    video2_path=raw_v2_path,
                    output_path=v_full_path,
                    freeze_timestamp_sec=float(dual_freeze_ts),
                    freeze_monochrome=dual_freeze_bw,
                    aspect_ratio="9:16" if "9:16" in dual_aspect_choice else "16:9",
                    divider_color=dual_divider_color,
                    divider_width=4 if dual_divider_color != "none" else 0,
                    video1_audio_track=dual_v1_track_id,
                    video1_audio_volume=float(dual_v1_vol),
                    video2_audio_track=dual_v2_track_id,
                    video2_audio_volume=float(dual_v2_vol),
                    audio_ducking_enabled=dual_audio_ducking
                )
                if not comp_res.get("error"):
                    extract_audio_from_local_video(v_full_path, audio_path)

            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                st.success(f"🎉 Áudio da composição dupla extraído com sucesso: **{v_title}**")
                col_adp1, col_adp2 = st.columns([2, 1])
                with col_adp1:
                    with open(audio_path, "rb") as af_dl:
                        st.audio(af_dl.read(), format="audio/mp3")
                with col_adp2:
                    with open(audio_path, "rb") as af_dl:
                        st.download_button(
                            label="📥 Baixar Áudio Composto (MP3)",
                            data=af_dl.read(),
                            file_name=f"{re.sub(r'[^a-zA-Z0-9_]+', '_', v_title)[:30]}.mp3",
                            mime="audio/mp3",
                            use_container_width=True,
                            key="btn_download_extracted_audio_dual"
                        )
            else:
                st.error("Não foi possível gerar o áudio da composição.")

        if btn_process_dual_local:
            video_id = generate_local_dual_video_id(first_file.name, second_file.name)
            local_url = f"local://{video_id}"
            st.session_state.video_url = local_url
            st.session_state.input_yt_url = local_url

            data_dir = os.path.join("data", video_id)
            os.makedirs(data_dir, exist_ok=True)
            raw_v1_path = os.path.join(data_dir, "raw_video_1.mp4")
            raw_v2_path = os.path.join(data_dir, "raw_video_2.mp4")
            v_full_path = os.path.join(data_dir, "video_full.mp4")
            audio_path = os.path.join(data_dir, "audio.mp3")
            thumb_path = os.path.join(data_dir, "thumbnail.jpg")
            transcript_file = os.path.join(data_dir, "transcript.json")

            # 1. Salva os dois arquivos de vídeo brutos
            with st.spinner("Salvando os dois arquivos de vídeo locais..."):
                with open(raw_v1_path, "wb") as f1_out:
                    f1_out.write(first_file.getbuffer())
                with open(raw_v2_path, "wb") as f2_out:
                    f2_out.write(second_file.getbuffer())

            # 2. Renderiza a Composição Sequencial Completa
            with st.spinner("🎬 Renderizando composição inteligente (Split com Base P&B ➔ Tela Cheia com Trilhas)..."):
                comp_res = compose_dual_video_split_sequence(
                    video1_path=raw_v1_path,
                    video2_path=raw_v2_path,
                    output_path=v_full_path,
                    freeze_timestamp_sec=float(dual_freeze_ts),
                    freeze_monochrome=dual_freeze_bw,
                    aspect_ratio="9:16" if "9:16" in dual_aspect_choice else "16:9",
                    divider_color=dual_divider_color,
                    divider_width=4 if dual_divider_color != "none" else 0,
                    video1_audio_track=dual_v1_track_id,
                    video1_audio_volume=float(dual_v1_vol),
                    video2_audio_track=dual_v2_track_id,
                    video2_audio_volume=float(dual_v2_vol),
                    audio_ducking_enabled=dual_audio_ducking
                )

            if comp_res.get("error"):
                st.error(f"Erro na composição dos vídeos: {comp_res['error']}")
            else:
                st.success(
                    f"✨ Composição gerada com sucesso! Duração total: **{comp_res.get('total_duration', 0.0):.1f}s** "
                    f"(1º Vídeo: `{comp_res.get('video1_duration', 0.0):.1f}s` | 2º Vídeo: `{comp_res.get('video2_duration', 0.0):.1f}s`)"
                )

                # 3. Metadados e Thumbnail
                v_title = custom_dual_title.strip() if custom_dual_title.strip() else default_dual_title
                tot_dur = comp_res.get("total_duration") or get_video_duration(v_full_path)
                extract_thumbnail_from_video(v_full_path, thumb_path, timestamp_sec=min(2.0, max(0.0, tot_dur * 0.1)))

                add_or_update_video_in_library(
                    video_id=video_id,
                    title=v_title,
                    upload_date_raw=datetime.now().strftime("%d/%m/%Y"),
                    url=local_url,
                    thumbnail_url=thumb_path if os.path.exists(thumb_path) else None,
                    duration_sec=int(tot_dur),
                    channel="Composição Dupla (Split ➔ Full)",
                    is_live=False
                )

                # 4. Extração de Áudio e Transcrição Unificada da Composição
                with st.spinner("Extraindo faixa de áudio unificada da composição..."):
                    audio_res = extract_audio_from_local_video(v_full_path, audio_path)

                if audio_res.get("error"):
                    st.error(f"Erro ao extrair áudio: {audio_res['error']}")
                else:
                    with st.spinner(f"Transcrevendo áudio unificado com Whisper ({model_size}) na {device_option.upper()}..."):
                        transcribe_res = transcribe_audio(
                            audio_path,
                            model_size=model_size,
                            device=device_option
                        )

                    if transcribe_res.get("error"):
                        st.error(f"Erro na transcrição: {transcribe_res['error']}")
                    else:
                        st.success("🎉 Transcrição da composição concluída com sucesso! Pronta para cortes e IA.")
                        st.session_state.transcription_done = True
                        st.session_state.full_text = transcribe_res["full_text"]
                        st.session_state.segments = transcribe_res["transcript_segments"]
                        st.session_state.transcript_source = "Whisper Local (Composição Dupla)"

                        with open(transcript_file, "w", encoding="utf-8") as f:
                            json.dump({
                                "full_text": st.session_state.full_text,
                                "segments": st.session_state.segments,
                                "source": st.session_state.transcript_source
                            }, f, ensure_ascii=False, indent=4)


if st.session_state.transcription_done:
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    from core.transcriber import build_youtube_transcript_blocks, format_badge_time
    
    active_u_main = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
    v_id_main = get_video_id(active_u_main)
    main_audio_path = os.path.join("data", v_id_main, "audio.mp3") if v_id_main else None

    if main_audio_path and os.path.exists(main_audio_path) and os.path.getsize(main_audio_path) > 0:
        with st.expander("🎵 Faixa de Áudio Isolada do Vídeo Completo (MP3 de Alta Fidelidade)", expanded=False):
            col_aud1, col_aud2 = st.columns([2.5, 1])
            with col_aud1:
                with open(main_audio_path, "rb") as f_m_aud:
                    st.audio(f_m_aud.read(), format="audio/mp3")
            with col_aud2:
                with open(main_audio_path, "rb") as f_m_aud:
                    st.download_button(
                        label="📥 Baixar Áudio Completo (MP3)",
                        data=f_m_aud.read(),
                        file_name=f"{v_id_main}_audio_completo.mp3",
                        mime="audio/mp3",
                        use_container_width=True,
                        key="btn_dl_main_audio_full"
                    )

    yt_blocks = build_youtube_transcript_blocks(st.session_state.segments)

    src_badge = st.session_state.get("transcript_source", "YouTube Oficial")
    with st.expander(f"📜 Transcrição em Blocos (Estilo YouTube Oficial)", expanded=False):
        col_search, col_cnt = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 Pesquisar na transcrição:", placeholder="Ex: ministro, justiça, reforma, imposto...", key="yt_transcript_search")
        
        # Filtra blocos se houver termo de busca
        displayed_blocks = yt_blocks
        if search_term.strip():
            displayed_blocks = [b for b in yt_blocks if search_term.lower() in b['text'].lower()]
            with col_cnt:
                st.caption(f"🎯 **{len(displayed_blocks)}** blocos encontrados")
        else:
            with col_cnt:
                st.caption(f"Total: **{len(yt_blocks)}** blocos ({src_badge})")
        
        # Container nativo do Streamlit com rolagem e renderização visual limpa
        with st.container(height=420):
            for b in displayed_blocks:
                text_display = b['text']
                if search_term.strip():
                    escaped = re.escape(search_term.strip())
                    text_display = re.sub(
                        f"({escaped})",
                        r"<mark style='background-color:#ffe082;color:#111;font-weight:bold;padding:1px 4px;border-radius:3px;'>\1</mark>",
                        text_display,
                        flags=re.IGNORECASE
                    )
                
                # HTML em linha única sem recuo de espaços para não ser interpretado como código
                line_html = (
                    f"<div style='display:flex;align-items:flex-start;margin-bottom:10px;line-height:1.5;'>"
                    f"<span style='display:inline-block;min-width:48px;background-color:#2b2b2b;color:#58a6ff;font-size:12px;font-weight:700;padding:2px 8px;border-radius:12px;margin-right:12px;text-align:center;letter-spacing:0.5px;'>{b['time_label']}</span>"
                    f"<span style='color:#e6edf3;font-size:14px;flex:1;'>{text_display}</span>"
                    f"</div>"
                )
                st.markdown(line_html, unsafe_allow_html=True)
    
    st.header("2. Inteligência Temática (Llama 3)")
    st.markdown("Use a Inteligência Artificial para extrair os tempos exatos para cortes.")
    
    # Construir lista de chunks estruturada (com start/end em segundos)
    def build_chunks_list(segments, chunk_seconds=60):
        """Retorna lista de dicts com start, end, text para cada chunk de 1 minuto."""
        if not segments:
            return []
        chunks = []
        chunk_start = segments[0]['start']
        chunk_texts = []
        
        for seg in segments:
            chunk_texts.append(seg['text'].strip())
            if seg['end'] - chunk_start >= chunk_seconds:
                chunks.append({
                    'start': chunk_start,
                    'end': seg['end'],
                    'text': ' '.join(chunk_texts)
                })
                chunk_start = seg['end']
                chunk_texts = []
        
        if chunk_texts:
            chunks.append({
                'start': chunk_start,
                'end': segments[-1]['end'],
                'text': ' '.join(chunk_texts)
            })
        return chunks

    chunks_list = build_chunks_list(st.session_state.segments)
    chunked_transcript = "\n".join(
        f"[{format_time(c['start'])} - {format_time(c['end'])}] {c['text']}"
        for c in chunks_list
    )

    # --- Seção 2: Seleção de Cortes e Compositor ---
    st.header("2. Seleção e Composição de Cortes")
    
    tab_composer, tab_series, tab_shorts, tab_manual = st.tabs([
        "🧩 Compositor de Pautas (Micro-Assuntos)",
        "💡 Séries Sugeridas",
        "🔥 Ganchos Virais (Shorts)",
        "🖱️ Seleção Manual (Chunks)"
    ])
    
    # ── TAB 1: COMPOSITOR DE PAUTAS ───────────────────────────────────────────
    with tab_composer:
        st.markdown(
            "Selecione o tipo de conteúdo para o mapeamento inteligente de cortes e pautas:"
        )
        
        col_strat, col_act = st.columns([3, 1])
        with col_strat:
            _strat_options = [
                "🎙️ Entrevistas, Sabatinas & Podcasts (Perguntas e Respostas Exatas)",
                "🧠 Temático / Monólogos, Aulas & Palestras (Transições de Assunto)"
            ]
            _strat_idx = 0 if "Entrevistas" in _cfg.get("analysis_strategy", "") else 1
            strategy_choice = st.radio(
                "🎯 Estratégia de Identificação de Pautas:",
                _strat_options,
                index=_strat_idx,
                horizontal=False,
                key="analysis_strategy_radio"
            )
            strat_code = "qa_interview" if "Entrevistas" in strategy_choice else "semantic_topics"

        with col_act:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔍 Mapear Pautas (IA)", key="btn_map_pautas", type="primary", use_container_width=True):
                with st.spinner("Mapeando perguntas e limites de pauta com IA..."):
                    res = analyze_transcript(
                        chunked_transcript, "pautas",
                        model=ollama_model,
                        chunks_list=chunks_list,
                        segments=st.session_state.segments,
                        strategy=strat_code
                    )
                    if res.get("error"):
                        st.error(f"Erro na análise: {res['error']}")
                    else:
                        st.session_state.pautas = res.get("pautas", [])
                        st.session_state.bundles = res.get("bundles", [])
                        st.session_state.ai_raw = res.get("raw", "")
                        
                        active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        v_id = get_video_id(active_u)
                        if v_id:
                            p_file = os.path.join("data", v_id, "pautas.json")
                            with open(p_file, "w", encoding="utf-8") as f:
                                json.dump({"pautas": st.session_state.pautas, "raw": st.session_state.ai_raw}, f, ensure_ascii=False, indent=4)
                        st.rerun()

        if 'pautas' in st.session_state and st.session_state.pautas:
            pautas = st.session_state.pautas
            
            # Carrega passos salvos do disco se existirem
            active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
            v_id = get_video_id(active_u)
            steps_file = os.path.join("data", v_id, "saved_steps.json") if v_id else "data/saved_steps.json"
            if 'saved_steps' not in st.session_state or not st.session_state.saved_steps:
                if os.path.exists(steps_file):
                    try:
                        with open(steps_file, "r", encoding="utf-8") as f:
                            st.session_state.saved_steps = json.load(f)
                    except Exception:
                        st.session_state.saved_steps = []
                else:
                    st.session_state.saved_steps = []

            def _save_steps_to_disk():
                os.makedirs(os.path.dirname(steps_file), exist_ok=True)
                with open(steps_file, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.saved_steps, f, indent=2, ensure_ascii=False)

            col_head1, col_head2 = st.columns([3, 2])
            with col_head1:
                st.markdown(f"### 📋 Pautas Detectadas ({len(pautas)} encontradas):")
            with col_head2:
                col_btn_uncheck, col_btn_reanalyze = st.columns(2)
                with col_btn_uncheck:
                    if st.button("🧹 Desmarcar Tudo", key="btn_uncheck_all", help="Limpa as seleções para iniciar um novo corte"):
                        for p in pautas:
                            st.session_state[f"chk_pauta_{p['id']}"] = False
                        st.rerun()
                with col_btn_reanalyze:
                    pass

            # Monta lista de pautas em cards selecionáveis
            st.markdown("")
            selected_pauta_objs = []

            for p in pautas:
                chk_key = f"chk_pauta_{p['id']}"
                if chk_key not in st.session_state:
                    st.session_state[chk_key] = False

                col_chk, col_p_info, col_dur = st.columns([0.5, 4.5, 1.2])
                with col_chk:
                    is_checked = st.checkbox(f"Pauta {p['id']}", key=chk_key, label_visibility="collapsed")
                    if is_checked:
                        selected_pauta_objs.append(p)
                with col_p_info:
                    st.markdown(f"**Pauta #{p['id']}**: `[{p['start']} → {p['end']}]` **{p['title']}**")
                    if p.get('text_snippet'):
                        st.caption(f"💬 *\"{p['text_snippet']}...\"*")
                with col_dur:
                    st.markdown(f"⏱️ **{p['duration_label']}**")
                st.divider()

            # ── BARRA INFORMATIVA DA SELEÇÃO (COMPOSITOR) ─────────────────────────
            if selected_pauta_objs:
                # Ordena por timestamp de início
                selected_pauta_objs = sorted(selected_pauta_objs, key=lambda x: x["start_s"])
                comb_start = selected_pauta_objs[0]["start"]
                comb_end = selected_pauta_objs[-1]["end"]
                comb_dur_s = sum(x["duration_s"] for x in selected_pauta_objs)
                comb_dur_fmt = format_time(comb_dur_s)
                
                # Título composto inteligente
                if len(selected_pauta_objs) == 1:
                    comb_title = selected_pauta_objs[0]["title"]
                else:
                    comb_title = f"{selected_pauta_objs[0]['title']} (+ {len(selected_pauta_objs)-1} pautas)"

                st.info(
                    f"🎯 **Corte Composto**: `[{comb_start} → {comb_end}]` | "
                    f"⏱️ Duração Total: **{comb_dur_fmt}** | "
                    f"Pautas Inclusas: **{len(selected_pauta_objs)}** ({', '.join(f'#{x['id']}' for x in selected_pauta_objs)})"
                )

                col_ap1, col_ap2 = st.columns([2, 1])
                with col_ap1:
                    if st.button("✂️ Carregar Seleção para Exportação (Seção 3)", key="btn_apply_composed", type="primary", use_container_width=True):
                        st.session_state.final_start_time = normalize_time_mask(comb_start)
                        st.session_state.final_end_time = normalize_time_mask(comb_end)
                        st.session_state.final_corte_title = comb_title
                        st.session_state.cut_ready_banner = f"✅ Composição pronta para corte: [{comb_start} → {comb_end}] ({comb_dur_fmt})"
                        st.rerun()

                with col_ap2:
                    step_num = len(st.session_state.saved_steps) + 1
                    if st.button("💾 Guardar como Passo", key="btn_save_step", use_container_width=True, help="Salva esta composição no histórico de passos para poder montar múltiplos cortes sem perder o progresso"):
                        new_step = {
                            "step_id": step_num,
                            "start": comb_start,
                            "end": comb_end,
                            "start_s": selected_pauta_objs[0]["start_s"],
                            "end_s": selected_pauta_objs[-1]["end_s"],
                            "duration_s": comb_dur_s,
                            "duration_label": comb_dur_fmt,
                            "title": comb_title,
                            "pauta_ids": [x["id"] for x in selected_pauta_objs],
                            "pautas_titles": [f"Pauta #{x['id']}: {x['title']} ({x['duration_label']})" for x in selected_pauta_objs]
                        }
                        st.session_state.saved_steps.append(new_step)
                        _save_steps_to_disk()
                        st.success(f"🎉 Passo #{step_num} guardado com sucesso!")
                        st.rerun()

            else:
                if 'cut_ready_banner' in st.session_state:
                    st.session_state.cut_ready_banner = ""

            # ── PAINEL DE PASSOS GUARDADOS ────────────────────────────────────────
            st.markdown("---")
            st.markdown("### 🗂️ Histórico de Passos / Cortes Salvos:")
            if 'saved_steps' in st.session_state and st.session_state.saved_steps:
                st.caption(f"Você possui **{len(st.session_state.saved_steps)} passos/cortes** guardados.")
                
                for idx, step in enumerate(st.session_state.saved_steps):
                    with st.container():
                        col_s_info, col_s_redo, col_s_del = st.columns([4, 1.2, 1])
                        with col_s_info:
                            st.markdown(f"**Passo #{idx+1}**: `[{step['start']} → {step['end']}]` **{step['title']}**")
                            st.caption(f"⏱️ Duração: **{step['duration_label']}**")
                        
                        with col_s_redo:
                            if st.button("🔁 Carregar", key=f"btn_redo_step_{idx}"):
                                st.session_state.final_start_time = step['start']
                                st.session_state.final_end_time = step['end']
                                st.session_state.final_corte_title = step['title']
                                st.rerun()

                        with col_s_del:
                            if st.button("🗑️ Excluir", key=f"btn_del_step_{idx}"):
                                st.session_state.saved_steps.pop(idx)
                                _save_steps_to_disk()
                                st.rerun()
                        st.divider()

                if st.button("🗑️ Excluir Todos os Passos", key="btn_clear_all_steps"):
                    st.session_state.saved_steps = []
                    _save_steps_to_disk()
                    st.success("Todos os passos foram excluídos.")
                    st.rerun()
            else:
                st.info("Nenhum passo guardado ainda. Selecione pautas acima e clique em **'💾 Guardar como Passo'** para montar sua fila de cortes!")


    # ── TAB 2: SÉRIES SUGERIDAS ───────────────────────────────────────────────
    with tab_series:
        st.markdown("Séries sugeridas agrupando sequências de pautas para publicação como **Vídeos Normais no YouTube** (Horizontal 16:9 Full HD) ou outros formatos.")
        st.info("ℹ️ **Modo Vídeo Normal (YouTube 16:9)**: Séries e vídeos longos são renderizados no formato original widescreen limpo (sem tarjas de topo, zoom punches periódicos ou barras de progresso de Shorts), preservando a experiência de vídeo tradicional do YouTube.")

        if "batch_feedback" in st.session_state:
            fb = st.session_state.pop("batch_feedback")
            if fb.get("type") == "success":
                st.success(fb.get("msg", ""))
            elif fb.get("type") == "warning":
                st.warning(fb.get("msg", ""))
            else:
                st.error(fb.get("msg", ""))
        
        col_s_min, col_s_btn = st.columns([1.5, 2.5])
        with col_s_min:
            saved_min_mins = float(_cfg.get("series_min_minutes", 10.0))
            series_min_mins = st.number_input(
                "⏱️ Tempo Mínimo por Corte (minutos):",
                min_value=1.0,
                max_value=120.0,
                value=saved_min_mins,
                step=1.0,
                key="series_min_minutes_input",
                on_change=lambda: save_setting("series_min_minutes", st.session_state.series_min_minutes_input),
                help="Define a duração mínima de agrupamento para cada série/episódio gerado."
            )

        with col_s_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            _btn_label = f"🧠 Gerar / Reagrupar Séries Sugeridas ({series_min_mins:.0f}+ min)" if series_min_mins == int(series_min_mins) else f"🧠 Gerar / Reagrupar Séries Sugeridas ({series_min_mins:.1f}+ min)"
            if st.button(_btn_label, key="btn_series", type="primary", use_container_width=True):
                with st.spinner(f"Agrupando pautas em séries de {series_min_mins:.0f}+ min..."):
                    if 'pautas' in st.session_state and st.session_state.pautas:
                        st.session_state.bundles = build_suggested_bundles(st.session_state.pautas, min_minutes=series_min_mins)
                    else:
                        res = analyze_transcript(
                            chunked_transcript, "blocos",
                            model=ollama_model,
                            chunks_list=chunks_list,
                            segments=st.session_state.segments,
                            strategy="qa_interview" if "Entrevistas" in strategy_choice else "semantic_topics",
                            min_series_minutes=series_min_mins
                        )
                        if res.get("error"):
                            st.error(f"Erro no Ollama: {res['error']}")
                        else:
                            st.session_state.bundles = res.get("bundles", [])
                            st.session_state.pautas = res.get("pautas", [])
                            st.session_state.ai_raw = res.get("raw", "")
                    
                    active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id = get_video_id(active_u)
                    if v_id and 'bundles' in st.session_state:
                        s_file = os.path.join("data", v_id, "series.json")
                        with open(s_file, "w", encoding="utf-8") as f:
                            json.dump(st.session_state.bundles, f, ensure_ascii=False, indent=4)
                    st.rerun()

        if 'bundles' in st.session_state and st.session_state.bundles:
            # Reseta seleção de checkboxes de forma segura antes da instanciação dos widgets
            if st.session_state.get("_reset_bundles_selection"):
                st.session_state["_reset_bundles_selection"] = False
                for b_i in range(len(st.session_state.bundles)):
                    st.session_state[f"chk_bundle_{b_i}"] = False
                st.session_state["batch_bundle_selected"] = {}

            if "batch_bundle_selected" not in st.session_state:
                st.session_state["batch_bundle_selected"] = {}

            col_bb1, col_bb2, col_bb3, _ = st.columns([1.4, 1.4, 1.4, 1.8])
            with col_bb1:
                if st.button("☑️ Marcar Tudo", key="btn_sel_all_bundles", use_container_width=True):
                    for b_i, b_item in enumerate(st.session_state.bundles):
                        st.session_state[f"chk_bundle_{b_i}"] = True
                        st.session_state["batch_bundle_selected"][b_i] = b_item
                    st.rerun()
            with col_bb2:
                if st.button("⬜ Desmarcar Tudo", key="btn_clear_bundles_batch", use_container_width=True):
                    st.session_state["_reset_bundles_selection"] = True
                    st.rerun()
            with col_bb3:
                if st.button("🔄 Inverter Seleção", key="btn_invert_bundles_batch", use_container_width=True):
                    for b_i, b_item in enumerate(st.session_state.bundles):
                        cur_val = st.session_state.get(f"chk_bundle_{b_i}", False)
                        new_val = not cur_val
                        st.session_state[f"chk_bundle_{b_i}"] = new_val
                        if new_val:
                            st.session_state["batch_bundle_selected"][b_i] = b_item
                        else:
                            st.session_state["batch_bundle_selected"].pop(b_i, None)
                    st.rerun()

            st.markdown(f"### 📦 Séries Sugeridas ({len(st.session_state.bundles)}):")
            for idx, b in enumerate(st.session_state.bundles):
                with st.container():
                    col_chk, col_info, col_btn = st.columns([0.3, 3.7, 1])
                    with col_chk:
                        chk_val = st.checkbox("Fila", key=f"chk_bundle_{idx}", label_visibility="collapsed")
                        if chk_val:
                            st.session_state["batch_bundle_selected"][idx] = b
                        else:
                            st.session_state["batch_bundle_selected"].pop(idx, None)
                    with col_info:
                        badge = f"**{b.get('series_label', f'Vídeo {idx+1}')}**"
                        st.markdown(f"{badge}: `[{b['start']} - {b['end']}]` **{b['title']}**")
                        st.caption(f"⏱️ Duração: {b.get('duration_label', '')}")
                    with col_btn:
                        if st.button("✂️ Usar", key=f"btn_use_bundle_{idx}"):
                            st.session_state.final_start_time = b['start']
                            st.session_state.final_end_time = b['end']
                            st.session_state.final_corte_title = b['title']
                            st.session_state.cut_ready_banner = f"✅ Série selecionada: [{b['start']} → {b['end']}] ({b['title']})"
                            st.rerun()
                    st.divider()

            # Painel da Fila de Produção em Lote para Séries
            selected_bundles = list(st.session_state["batch_bundle_selected"].values())
            if selected_bundles:
                with st.container():
                    st.markdown("---")
                    st.markdown(f"### 📦 Fila de Produção em Lote para Séries (**{len(selected_bundles)}** séries selecionadas)")
                    
                    col_sp1, col_sp2 = st.columns([2, 2])
                    with col_sp1:
                        _series_aspect_map = {
                            "💻 Horizontal 16:9 (Original 1080p Full HD - Padrão YouTube)": "16:9",
                            "📱 Vertical 9:16 (Fundo Desfocado / Blur)": "9:16_blur",
                            "📱 Vertical 9:16 (🎯 Auto-Reframing Facial)": "9:16_smart_face",
                            "📱 Vertical 9:16 (👥 Split Screen)": "9:16_split",
                            "📱 Vertical 9:16 (Corte Central 100%)": "9:16_crop"
                        }
                        series_aspect_choice = st.selectbox(
                            "Formato de Enquadramento:",
                            list(_series_aspect_map.keys()),
                            index=0,
                            key="series_aspect_choice"
                        )
                        series_aspect_mode = _series_aspect_map[series_aspect_choice]
                    with col_sp2:
                        series_sub_enabled = st.toggle("✨ Ativar Legendas Dinâmicas", value=_cfg.get("subtitle_enabled", False), key="series_sub_toggle")
                        st.caption(f"Fontes e cores: {_cfg.get('subtitle_font_size', 80)}px • Destaque {_cfg.get('subtitle_highlight_color', '#FFFF00')}")

                    if st.button(f"⚡ Iniciar Renderização em Lote ({len(selected_bundles)} Séries)", type="primary", use_container_width=True, key="btn_start_series_batch"):
                        _active_u_sbatch = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        _vid_id_sbatch = get_video_id(_active_u_sbatch)
                        if not _vid_id_sbatch:
                            st.error("URL do vídeo do YouTube não identificada.")
                        else:
                            s_prog_bar = st.progress(0)
                            s_status_box = st.empty()
                            s_live_logs = []

                            def _s_batch_cb(cur, tot, msg):
                                pct = int((cur / max(tot, 1)) * 100)
                                s_prog_bar.progress(min(pct, 100))
                                s_status_box.info(f"**Progresso ({cur}/{tot}):** {msg}")

                            def _s_log_cb(line):
                                s_live_logs.append(line)

                            s_batch_res = process_batch_cuts(
                                video_id=_vid_id_sbatch,
                                active_url=_active_u_sbatch,
                                cut_items=selected_bundles,
                                aspect_ratio_mode=series_aspect_mode,
                                subtitle_enabled=series_sub_enabled,
                                subtitle_highlight_color=_cfg.get("subtitle_highlight_color", "#FFFF00"),
                                subtitle_base_color=_cfg.get("subtitle_base_color", "#FFFFFF"),
                                subtitle_font_size=_cfg.get("subtitle_font_size", 80),
                                ollama_model=ollama_model,
                                aspect_params=dict(_cfg),
                                force_rerender=False,
                                progress_callback=_s_batch_cb,
                                log_callback=_s_log_cb
                            )

                            s_prog_bar.progress(100)
                            if not isinstance(s_batch_res, list):
                                s_batch_res = [s_batch_res] if s_batch_res else []

                            success_count = sum(1 for r in s_batch_res if isinstance(r, dict) and r.get("success"))
                            error_items = [r for r in s_batch_res if isinstance(r, dict) and r.get("error")]

                            if error_items:
                                err_details = "\n".join([f"- **{e.get('title', 'Série')}**: {e.get('error')}" for e in error_items])
                                st.session_state["batch_feedback"] = {
                                    "type": "warning" if success_count > 0 else "error",
                                    "msg": f"Processamento de séries concluído com {success_count} sucesso(s) e {len(error_items)} erro(s):\n{err_details}"
                                }
                            else:
                                st.session_state["batch_feedback"] = {
                                    "type": "success",
                                    "msg": f"🎉 **Renderização de séries em lote concluída com sucesso!** {success_count} séries geradas e disponíveis na Galeria (Seção 4)."
                                }
                            st.session_state["_reset_bundles_selection"] = True
                            st.rerun()

    # ── TAB 3: GANCHOS VIRAIS & PEQUENOS CORTES (SHORTS / REELS) ───────────────
    with tab_shorts:
        st.markdown(
            "Geração de **Pequenos Cortes** para Shorts/Reels estruturados sob as **6 Regras de Ouro Editoriais**."
        )
        
        col_sh_max, col_sh_btn = st.columns([1.5, 2.5])
        with col_sh_max:
            saved_max_shorts = float(_cfg.get("shorts_max_seconds", 60.0))
            shorts_max_secs = st.number_input(
                "⏱️ Duração Máxima do Short (segundos):",
                min_value=15.0,
                max_value=180.0,
                value=saved_max_shorts,
                step=5.0,
                key="shorts_max_seconds_input",
                on_change=lambda: save_setting("shorts_max_seconds", st.session_state.shorts_max_seconds_input),
                help="Define o teto de duração máxima para cada corte vertical gerado (Shorts, Reels, TikTok)."
            )

        with col_sh_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            _btn_sh_label = f"🔥 Gerar / Reestruturar Pequenos Cortes (Até {shorts_max_secs:.0f}s)"
            if st.button(_btn_sh_label, key="btn_shorts", type="primary", use_container_width=True):
                with st.spinner(f"Estruturando pequenos cortes (máx. {shorts_max_secs:.0f}s) sob as 6 Regras de Ouro..."):
                    if 'pautas' in st.session_state and st.session_state.pautas:
                        st.session_state.shorts = build_golden_rule_micro_cuts(
                            st.session_state.pautas,
                            st.session_state.segments,
                            max_duration_s=shorts_max_secs
                        )
                    else:
                        res = analyze_transcript(
                            chunked_transcript, "ganchos",
                            model=ollama_model,
                            chunks_list=chunks_list,
                            segments=st.session_state.segments,
                            strategy="qa_interview" if "Entrevistas" in strategy_choice else "semantic_topics",
                            max_shorts_seconds=shorts_max_secs
                        )
                        if res.get("error"):
                            st.error(f"Erro na análise: {res['error']}")
                        else:
                            st.session_state.shorts = res.get("micro_cuts", []) or res.get("cortes", [])
                            st.session_state.pautas = res.get("pautas", [])
                            st.session_state.ai_raw = res.get("raw", "")
                    
                    active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id = get_video_id(active_u)
                    if v_id and 'shorts' in st.session_state:
                        sh_file = os.path.join("data", v_id, "shorts.json")
                        with open(sh_file, "w", encoding="utf-8") as f:
                            json.dump(st.session_state.shorts, f, ensure_ascii=False, indent=4)
                    st.rerun()

        if "batch_feedback" in st.session_state:
            fb = st.session_state.pop("batch_feedback")
            if fb.get("type") == "success":
                st.success(fb.get("msg", ""))
            elif fb.get("type") == "warning":
                st.warning(fb.get("msg", ""))
            else:
                st.error(fb.get("msg", ""))

        if 'shorts' in st.session_state and st.session_state.shorts:
            # Reseta seleção de checkboxes de forma segura antes da instanciação dos widgets
            if st.session_state.get("_reset_batch_selection"):
                st.session_state["_reset_batch_selection"] = False
                for s_i in range(len(st.session_state.shorts)):
                    st.session_state[f"chk_short_{s_i}"] = False
                st.session_state["batch_short_selected"] = {}

            if "batch_short_selected" not in st.session_state:
                st.session_state["batch_short_selected"] = {}

            col_bk1, col_bk2, col_bk3, _ = st.columns([1.4, 1.4, 1.4, 1.8])
            with col_bk1:
                if st.button("☑️ Marcar Tudo", key="btn_sel_all_shorts", use_container_width=True):
                    for s_i, s_item in enumerate(st.session_state.shorts):
                        st.session_state[f"chk_short_{s_i}"] = True
                        st.session_state["batch_short_selected"][s_i] = s_item
                    st.rerun()
            with col_bk2:
                if st.button("⬜ Desmarcar Tudo", key="btn_clear_shorts_batch", use_container_width=True):
                    st.session_state["_reset_batch_selection"] = True
                    st.rerun()
            with col_bk3:
                if st.button("🔄 Inverter Seleção", key="btn_invert_shorts_batch", use_container_width=True):
                    for s_i, s_item in enumerate(st.session_state.shorts):
                        cur_val = st.session_state.get(f"chk_short_{s_i}", False)
                        new_val = not cur_val
                        st.session_state[f"chk_short_{s_i}"] = new_val
                        if new_val:
                            st.session_state["batch_short_selected"][s_i] = s_item
                        else:
                            st.session_state["batch_short_selected"].pop(s_i, None)
                    st.rerun()

            st.markdown(f"### 🎬 Pequenos Cortes Gerados ({len(st.session_state.shorts)}):")
            for idx, s in enumerate(st.session_state.shorts):
                with st.container():
                    col_chk, col_info = st.columns([0.3, 4.7])
                    with col_chk:
                        chk_val = st.checkbox("Fila", key=f"chk_short_{idx}", label_visibility="collapsed")
                        if chk_val:
                            st.session_state["batch_short_selected"][idx] = s
                        else:
                            st.session_state["batch_short_selected"].pop(idx, None)
                    with col_info:
                        st.markdown(f"**{s.get('type', 'Corte')}** | `[{s['start']} → {s['end']}]` **{s['title']}**")
                        st.caption(f"⏱️ Duração: **{s.get('duration_label', '')}**")
                        if s.get('snippet'):
                            st.markdown(f"💬 *\"{s['snippet']}\"*")
                    st.divider()

            # ── PAINEL DA FILA DE PRODUÇÃO EM LOTE ────────────────────────────
            selected_items = list(st.session_state["batch_short_selected"].values())
            if selected_items:
                with st.container():
                    st.markdown("---")
                    st.markdown(f"### 📦 Fila de Produção em Lote (**{len(selected_items)}** cortes selecionados)")
                    
                    _batch_aspect_list = [
                        "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)",
                        "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)",
                        "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)",
                        "📱 Vertical 9:16 (Corte Central 100% Tela)",
                        "💻 Horizontal 16:9 (Original 1080p Full HD)"
                    ]
                    _default_b_aspect = _cfg.get("aspect_option", _batch_aspect_list[0])
                    _b_idx = _batch_aspect_list.index(_default_b_aspect) if _default_b_aspect in _batch_aspect_list else 0

                    col_bp1, col_bp2 = st.columns(2)
                    with col_bp1:
                        batch_aspect_choice = st.selectbox(
                            "📐 Enquadramento para o Lote:",
                            _batch_aspect_list,
                            index=_b_idx,
                            key="batch_aspect_select"
                        )
                        b_aspect_map = {
                            "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)": "9:16_blur",
                            "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)": "9:16_smart_face",
                            "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)": "9:16_split",
                            "📱 Vertical 9:16 (Corte Central 100% Tela)": "9:16_crop",
                            "💻 Horizontal 16:9 (Original 1080p Full HD)": "16:9"
                        }
                        batch_aspect_mode = b_aspect_map[batch_aspect_choice]
                        st.caption(f"🎯 Modo ativo: `{batch_aspect_mode}`")

                    with col_bp2:
                        batch_sub_enabled = st.toggle("✨ Ativar Legendas Dinâmicas", value=_cfg.get("subtitle_enabled", True), key="batch_sub_toggle")
                        st.caption(f"Fontes e cores: {_cfg.get('subtitle_font_size', 80)}px • Destaque {_cfg.get('subtitle_highlight_color', '#FFFF00')}")

                    with st.expander("⚙️ Personalizações da Fase 3 & 4 para o Lote (Headlines, Retenção, Capas & Áudio)", expanded=False):
                        col_bopt1, col_bopt2 = st.columns(2)
                        with col_bopt1:
                            b_hl_on = st.toggle("🏷️ Headline de Retenção no Topo", value=_cfg.get("headline_enabled", False), key="b_hl_toggle")
                            b_em_on = st.toggle("😃 Emojis Contextuais", value=_cfg.get("emojis_enabled", False), key="b_em_toggle")
                            b_zp_on = st.toggle("🔍 Zoom Punch Dinâmico", value=_cfg.get("zoom_punch_enabled", False), key="b_zp_toggle")
                            b_cz_on = st.toggle("🎯 Zoom de Clímax na Frase Final", value=_cfg.get("climax_zoom_enabled", False), key="b_cz_toggle")
                        with col_bopt2:
                            b_pb_on = st.toggle("⏳ Barra de Progresso no Rodapé", value=_cfg.get("progress_bar_enabled", False), key="b_pb_toggle")
                            b_co_on = st.toggle("📌 Banner de Chamada / Callout", value=_cfg.get("callout_enabled", False), key="b_co_toggle")
                            b_th_on = st.toggle("🖼️ Gerar Capa / Thumbnail 9:16", value=_cfg.get("thumbnail_enabled", True), key="b_th_toggle")
                            b_bgm_on = st.toggle("🎵 Trilha Sonora & Ducking", value=_cfg.get("bg_music_enabled", False), key="b_bgm_toggle")
                            if b_bgm_on:
                                b_bgm_trk = st.selectbox(
                                    "Trilha:",
                                    ["lofi_chill", "dynamic_pulse", "tension_suspense", "inspirational_epic"],
                                    format_func=lambda x: {"lofi_chill": "🧘 Lo-Fi Chill", "dynamic_pulse": "⚡ Dinâmica", "tension_suspense": "🔥 Tensão", "inspirational_epic": "✨ Inspiracional"}.get(x, x),
                                    key="b_bgm_trk_sel"
                                )
                            else:
                                b_bgm_trk = _cfg.get("bg_music_track_id", "lofi_chill")

                    batch_force_rerender = st.checkbox(
                        "🔄 Forçar Re-renderização de Cortes Já Gerados",
                        value=False,
                        help="Por padrão, a aplicação pula e reaproveita cortes que já foram gerados neste formato. Marque para reprocessar tudo."
                    )

                    if st.button(f"⚡ Iniciar Renderização em Lote ({len(selected_items)} Cortes)", type="primary", use_container_width=True, key="btn_start_batch"):
                        _active_u_batch = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        _vid_id_batch = get_video_id(_active_u_batch)
                        if not _vid_id_batch:
                            st.error("URL do vídeo do YouTube não identificada.")
                        else:
                            prog_bar = st.progress(0)
                            status_box = st.empty()

                            live_logs_list = []

                            def _batch_cb(cur, tot, msg):
                                pct = int((cur / max(tot, 1)) * 100)
                                prog_bar.progress(min(pct, 100))
                                status_box.info(f"**Progresso ({cur}/{tot}):** {msg}")

                            def _log_cb(line):
                                live_logs_list.append(line)

                            batch_params_merged = dict(_cfg)
                            batch_params_merged.update({
                                "headline_enabled": b_hl_on,
                                "emojis_enabled": b_em_on,
                                "zoom_punch_enabled": b_zp_on,
                                "climax_zoom_enabled": b_cz_on,
                                "progress_bar_enabled": b_pb_on,
                                "callout_enabled": b_co_on,
                                "callout_text": _cfg.get("callout_text", "💬 O que você acha? Comente abaixo!"),
                                "thumbnail_enabled": b_th_on,
                                "bg_music_enabled": b_bgm_on,
                                "bg_music_track_id": b_bgm_trk,
                            })

                            batch_res = process_batch_cuts(
                                video_id=_vid_id_batch,
                                active_url=_active_u_batch,
                                cut_items=selected_items,
                                aspect_ratio_mode=batch_aspect_mode,
                                subtitle_enabled=batch_sub_enabled,
                                subtitle_highlight_color=_cfg.get("subtitle_highlight_color", "#FFFF00"),
                                subtitle_base_color=_cfg.get("subtitle_base_color", "#FFFFFF"),
                                subtitle_font_size=_cfg.get("subtitle_font_size", 80),
                                ollama_model=ollama_model,
                                aspect_params=batch_params_merged,
                                force_rerender=batch_force_rerender,
                                progress_callback=_batch_cb,
                                log_callback=_log_cb
                            )

                            prog_bar.progress(100)

                            # Salva todos os logs completos para visualização e cópia
                            full_logs_text = "\n".join(live_logs_list)
                            st.session_state["last_batch_logs"] = full_logs_text

                            # Agenda o reset limpo dos checkboxes para a próxima renderização
                            st.session_state["_reset_batch_selection"] = True

                            success_count = sum(1 for r in batch_res if r.get("success"))
                            error_items = [r for r in batch_res if r.get("error")]

                            if error_items:
                                err_details = "\n".join([f"- **{e.get('title', 'Corte')}**: {e.get('error')}" for e in error_items])
                                st.session_state["batch_feedback"] = {
                                    "type": "warning" if success_count > 0 else "error",
                                    "msg": f"Processamento concluído com {success_count} sucesso(s) e {len(error_items)} erro(s):\n{err_details}"
                                }
                            else:
                                st.session_state["batch_feedback"] = {
                                    "type": "success",
                                    "msg": f"🎉 **Renderização em lote concluída com sucesso!** {success_count} cortes gerados e disponíveis na Galeria (Seção 4)."
                                }
                            st.rerun()

    # ── TAB 4: SELEÇÃO MANUAL ────────────────────────────────────────────────
    with tab_manual:
        
        mode_manual = st.radio("Modo de Seleção:", ["📜 Blocos de Legenda (Estilo YouTube)", "⏱️ Intervalos de 1 Minuto"], horizontal=True)
        
        if mode_manual == "📜 Blocos de Legenda (Estilo YouTube)":
            if yt_blocks:
                block_labels = [
                    f"[{b['time_label']}]  {b['text'][:90]}..."
                    for b in yt_blocks
                ]
                col_s, col_e = st.columns(2)
                idx_start = col_s.selectbox("Fala de Início:", range(len(yt_blocks)),
                                             format_func=lambda i: block_labels[i], key="yt_block_start")
                idx_end = col_e.selectbox("Fala de Fim:", range(len(yt_blocks)),
                                           format_func=lambda i: block_labels[i],
                                           index=min(len(yt_blocks)-1, 50), key="yt_block_end")
                
                if idx_start is not None and idx_end is not None:
                    if idx_end >= idx_start:
                        start_s = yt_blocks[idx_start]['start']
                        end_s = yt_blocks[idx_end]['end']
                        st.success(f"Trecho Selecionado: **{format_time(start_s)}** → **{format_time(end_s)}** ({(end_s - start_s)/60:.1f} min)")
                        if st.button("✂️ Usar este trecho na Fábrica de Cortes", key="btn_manual_yt"):
                            st.session_state.final_start_time = format_time(start_s)
                            st.session_state.final_end_time = format_time(end_s)
                            st.session_state.final_corte_title = f"Corte Manual [{yt_blocks[idx_start]['time_label']} - {yt_blocks[idx_end]['time_label']}]"
                            st.session_state.cut_ready_banner = f"✅ Corte manual: [{format_time(start_s)} → {format_time(end_s)}]"
                            st.rerun()
                    else:
                        st.warning("⚠️ A fala de fim deve ser posterior ou igual à fala de início.")
            else:
                st.info("Nenhum bloco de legenda disponível para seleção manual neste vídeo.")
        else:
            if chunks_list:
                chunk_labels = [
                    f"[{format_time(c['start'])} - {format_time(c['end'])}]  {c['text'][:80]}..."
                    for c in chunks_list
                ]
                col_s, col_e = st.columns(2)
                idx_start = col_s.selectbox("Chunk de Início:", range(len(chunks_list)),
                                             format_func=lambda i: chunk_labels[i], key="manual_start")
                idx_end = col_e.selectbox("Chunk de Fim:", range(len(chunks_list)),
                                           format_func=lambda i: chunk_labels[i],
                                           index=min(len(chunks_list)-1, 9), key="manual_end")
                
                if idx_start is not None and idx_end is not None:
                    if idx_end >= idx_start:
                        start_s = chunks_list[idx_start]['start']
                        end_s = chunks_list[idx_end]['end']
                        st.success(f"Trecho: **{format_time(start_s)}** → **{format_time(end_s)}** ({(end_s - start_s)/60:.1f} min)")
                        if st.button("✂️ Usar este trecho na Fábrica de Cortes", key="btn_manual"):
                            st.session_state.final_start_time = format_time(start_s)
                            st.session_state.final_end_time = format_time(end_s)
                            st.session_state.final_corte_title = "Corte Manual"
                            st.session_state.cut_ready_banner = f"✅ Corte manual: [{format_time(start_s)} → {format_time(end_s)}]"
                            st.rerun()
                    else:
                        st.warning("⚠️ O intervalo de fim deve ser posterior ou igual ao intervalo de início.")
            else:
                st.info("Nenhum intervalo disponível para seleção manual.")


    if 'ai_raw' in st.session_state and st.session_state.ai_raw:
        with st.expander("🔍 Detalhes do Log da IA (Debug)"):
            st.code(st.session_state.ai_raw)

    st.markdown("---")
    st.header("3. Fábrica de Cortes (Recorte Final)")
    st.markdown("Baixe o vídeo real usando o trecho selecionado.")
    
    if 'cut_ready_banner' in st.session_state and st.session_state.cut_ready_banner:
        st.success(st.session_state.cut_ready_banner)
    
    if 'final_start_time' not in st.session_state:
        st.session_state.final_start_time = ""
    if 'final_end_time' not in st.session_state:
        st.session_state.final_end_time = ""

    # ── Botões de atalho de tempo ──────────────────────────────────────
    _btn_col_full, _btn_col_clear, _btn_col_spacer = st.columns([1.4, 1, 3])
    with _btn_col_full:
        if st.button("📺 Vídeo Inteiro", key="btn_use_full_video", use_container_width=True,
                     help="Preenche automaticamente o tempo inicial (00:00:00) e o tempo final com a duração total do vídeo"):
            _active_url_full = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
            _vid_id_full = get_video_id(_active_url_full)
            _vid_path_full = os.path.join("data", _vid_id_full, "video_full.mp4") if _vid_id_full else None
            if _vid_path_full and os.path.exists(_vid_path_full):
                _total_dur = get_video_duration(_vid_path_full)
                def _fmt(s):
                    h, m, sec = int(s // 3600), int((s % 3600) // 60), int(s % 60)
                    return f"{h:02d}:{m:02d}:{sec:02d}.00"
                st.session_state.final_start_time = "00:00:00.00"
                st.session_state.final_end_time = _fmt(_total_dur)
                st.session_state.cut_ready_banner = f"✅ Vídeo inteiro selecionado: [00:00:00.00 → {_fmt(_total_dur)}]"
                st.rerun()
            else:
                st.warning("⚠️ Vídeo ainda não baixado. Gere o corte uma vez para baixar o vídeo completo.")
    with _btn_col_clear:
        if st.button("🗑️ Limpar", key="btn_clear_times", use_container_width=True,
                     help="Limpa os campos de tempo inicial e final"):
            st.session_state.final_start_time = ""
            st.session_state.final_end_time = ""
            st.session_state.cut_ready_banner = ""
            st.rerun()

    def _on_start_time_change():
        val = st.session_state.get("final_start_time", "")
        if val:
            st.session_state.final_start_time = normalize_time_mask(val)

    def _on_end_time_change():
        val = st.session_state.get("final_end_time", "")
        if val:
            st.session_state.final_end_time = normalize_time_mask(val)

    col_start, col_end = st.columns(2)
    start_time = col_start.text_input(
        "Tempo Inicial (HH:MM:SS.ms)",
        key="final_start_time",
        placeholder="00:00:00.00",
        on_change=_on_start_time_change,
        help="Máscara automática (HH:MM:SS.ms) com 2 dígitos de milissegundos — digite os números ou use o formato HH:MM:SS.ms"
    )
    end_time = col_end.text_input(
        "Tempo Final (HH:MM:SS.ms)",
        key="final_end_time",
        placeholder="00:10:00.00",
        on_change=_on_end_time_change,
        help="Máscara automática (HH:MM:SS.ms) com 2 dígitos de milissegundos — digite os números ou use o formato HH:MM:SS.ms"
    )

    _aspect_list = [
        "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)",
        "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)",
        "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)",
        "📱 Vertical 9:16 (Corte Central 100% Tela)",
        "💻 Horizontal 16:9 (Original 1080p Full HD)"
    ]
    _saved_aspect = _cfg.get("aspect_option", _aspect_list[1])
    _asp_idx = _aspect_list.index(_saved_aspect) if _saved_aspect in _aspect_list else 1

    def _on_aspect_change():
        if "aspect_ratio_choice" in st.session_state:
            save_setting("aspect_option", st.session_state.aspect_ratio_choice)

    st.markdown("#### 📐 Formato de Exportação do Vídeo")
    aspect_option = st.radio(
        "Escolha o enquadramento:",
        _aspect_list,
        index=_asp_idx,
        horizontal=False,
        key="aspect_ratio_choice",
        on_change=_on_aspect_change
    )
    
    aspect_map = {
        "📱 Vertical 9:16 (👥 Layout Dividido / Split Screen - Estilo Podpah & Flow)": "9:16_split",
        "📱 Vertical 9:16 (🎯 Rastreamento Inteligente de Rosto / Auto-Reframing)": "9:16_smart_face",
        "📱 Vertical 9:16 (Fundo Desfocado / Blur - Shorts/TikTok/Reels)": "9:16_blur",
        "📱 Vertical 9:16 (Corte Central 100% Tela)": "9:16_crop",
        "💻 Horizontal 16:9 (Original 1080p Full HD)": "16:9"
    }
    selected_aspect = aspect_map[aspect_option]

    horizontal_zoom_val = float(_cfg.get("horizontal_zoom", 1.0))
    blur_zoom_val = 1.0
    blur_pan_val = 0.0
    blur_int_val = _cfg.get("blur_intensity", 25)
    mode_blur_ctrl = _cfg.get("blur_mode_ctrl", "🤖 Auto-Zoom Inteligente no Personagem (Recomendado)")
    face_zoom_active = True
    face_margin_val = 1.55
    person_pref_val = "auto"
    split_top_pan = -0.65
    split_bottom_pan = 0.65
    split_zoom_val = 1.15
    split_div_color = "black"
    split_div_w = 4
    split_auto_switch = True
    split_source_type = "main_video"
    split_video_path = None
    split_image_paths = []
    split_media_position = "bottom"
    split_blur_margin_pct = 5.0

    if selected_aspect == "9:16_split":
        with st.expander("👥 Ajustes do Layout Dividido (Split Screen 9:16)", expanded=True):
            saved_split_src = _cfg.get("split_source_type", "main_video")
            _src_map = {
                "👥 Câmera Dupla (Vídeo Principal no Topo & Base)": "main_video",
                "🎬 Vídeo Secundário Local / B-Roll / Gameplay (Looping)": "video",
                "🖼️ Slideshow de Imagens (Apresentação Proporcional)": "images"
            }
            _src_inv_map = {v: k for k, v in _src_map.items()}
            _saved_src_label = _src_inv_map.get(saved_split_src, list(_src_map.keys())[0])
            _src_idx = list(_src_map.keys()).index(_saved_src_label) if _saved_src_label in _src_map else 0

            split_source_type_label = st.radio(
                "🧩 Composição das Metades da Tela:",
                list(_src_map.keys()),
                index=_src_idx,
                key="split_src_type_radio",
                on_change=lambda: save_setting("split_source_type", _src_map.get(st.session_state.split_src_type_radio, "main_video"))
            )
            split_source_type = _src_map[split_source_type_label]

            if split_source_type in ["video", "images"]:
                col_pos, col_auto = st.columns(2)
                with col_pos:
                    saved_pos = _cfg.get("split_media_position", "bottom")
                    _pos_map = {
                        "⬇️ Parte Inferior / Base (Recomendado)": "bottom",
                        "⬆️ Parte Superior / Topo": "top"
                    }
                    _pos_inv_map = {v: k for k, v in _pos_map.items()}
                    _pos_idx = 0 if saved_pos == "bottom" else 1
                    pos_label = st.radio(
                        "📍 Posição do Conteúdo Secundário:",
                        list(_pos_map.keys()),
                        index=_pos_idx,
                        key="split_pos_radio",
                        on_change=lambda: save_setting("split_media_position", _pos_map.get(st.session_state.split_pos_radio, "bottom"))
                    )
                    split_media_position = _pos_map[pos_label]
                with col_auto:
                    st.info("💡 O vídeo principal ocupará a outra metade da tela com foco ajustável pelo zoom e posição horizontal.")

                if split_source_type == "video":
                    st.markdown("##### 🎬 Seleção do Vídeo Secundário (B-Roll / Gameplay / Satisfatório)")
                    col_vup, col_vpath = st.columns([1.5, 1])
                    with col_vup:
                        sec_vid_file = st.file_uploader(
                            "Faça upload do arquivo de vídeo secundário:",
                            type=["mp4", "mov", "mkv", "webm", "avi"],
                            key="split_sec_video_uploader",
                            help="Se o vídeo for menor que a duração do corte, ele rodará em looping contínuo automaticamente."
                        )
                    with col_vpath:
                        saved_vpath = _cfg.get("split_video_path", "")
                        sec_vid_path_input = st.text_input(
                            "Ou digite o caminho local:",
                            value=saved_vpath,
                            placeholder="C:\\Videos\\gameplay.mp4",
                            key="split_vpath_input",
                            on_change=lambda: save_setting("split_video_path", st.session_state.split_vpath_input)
                        )

                    if sec_vid_file is not None:
                        broll_dir = os.path.join("data", "custom_broll")
                        os.makedirs(broll_dir, exist_ok=True)
                        save_dest = os.path.join(broll_dir, sec_vid_file.name)
                        with open(save_dest, "wb") as f_broll:
                            f_broll.write(sec_vid_file.getbuffer())
                        split_video_path = save_dest
                        st.success(f"✅ Vídeo secundário carregado: `{sec_vid_file.name}` (Looping automático ativado)")
                    elif sec_vid_path_input.strip() and os.path.exists(sec_vid_path_input.strip()):
                        split_video_path = sec_vid_path_input.strip()
                        st.success(f"✅ Vídeo secundário localizado: `{os.path.basename(split_video_path)}`")
                    else:
                        st.warning("⚠️ Nenhum vídeo secundário selecionado. Selecione um arquivo ou envie pelo botão acima.")

                elif split_source_type == "images":
                    st.markdown("##### 🖼️ Slideshow de Imagens Proporcionais")
                    col_iup, col_ifolder = st.columns([1.5, 1])
                    with col_iup:
                        uploaded_imgs = st.file_uploader(
                            "Selecione uma ou mais imagens (PNG, JPG, WEBP):",
                            type=["png", "jpg", "jpeg", "webp"],
                            accept_multiple_files=True,
                            key="split_img_uploader"
                        )
                    with col_ifolder:
                        saved_ifolder = _cfg.get("split_image_folder", "")
                        img_folder_input = st.text_input(
                            "Ou informe uma pasta local com imagens:",
                            value=saved_ifolder,
                            placeholder="C:\\Imagens\\Slides",
                            key="split_ifolder_input",
                            on_change=lambda: save_setting("split_image_folder", st.session_state.split_ifolder_input)
                        )

                    split_image_paths = []
                    if uploaded_imgs:
                        slides_dir = os.path.join("data", "custom_slides")
                        os.makedirs(slides_dir, exist_ok=True)
                        for u_img in uploaded_imgs:
                            s_path = os.path.join(slides_dir, u_img.name)
                            with open(s_path, "wb") as f_s:
                                f_s.write(u_img.getbuffer())
                            split_image_paths.append(s_path)
                    elif img_folder_input.strip() and os.path.isdir(img_folder_input.strip()):
                        valid_exts = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
                        for fname in sorted(os.listdir(img_folder_input.strip())):
                            if fname.lower().endswith(valid_exts):
                                split_image_paths.append(os.path.join(img_folder_input.strip(), fname))

                    if split_image_paths:
                        num_s = len(split_image_paths)
                        calc_dur = 60.0
                        if start_time and end_time:
                            try:
                                from core.analyzer import parse_time_str_to_seconds
                                s_sec = parse_time_str_to_seconds(start_time)
                                e_sec = parse_time_str_to_seconds(end_time)
                                if e_sec > s_sec:
                                    calc_dur = e_sec - s_sec
                            except Exception:
                                pass
                        time_per_slide = calc_dur / float(num_s)
                        st.success(f"✨ **{num_s} imagem(ns) pronta(s)** • Cada slide ficará visível por **{time_per_slide:.1f} segundos** (tempo proporcional ao corte de {calc_dur:.0f}s).")
                        
                        with st.expander("👁️ Ver sequência dos slides carregados", expanded=False):
                            cols_thumbs = st.columns(min(6, num_s))
                            for idx_th, th_p in enumerate(split_image_paths[:12]):
                                with cols_thumbs[idx_th % len(cols_thumbs)]:
                                    st.image(th_p, caption=f"Slide #{idx_th+1}", use_container_width=True)
                    else:
                        st.warning("⚠️ Nenhuma imagem carregada. Envie arquivos ou informe a pasta de imagens.")

                # Pan / Enquadramento do Vídeo Principal
                saved_top_pan = float(_cfg.get("split_top_pan", 0.0))
                split_top_pan = st.slider(
                    "↔️ Enquadramento Horizontal do Vídeo Principal:", -1.0, 1.0, saved_top_pan, 0.05,
                    key="split_top_pan_slider",
                    on_change=lambda: save_setting("split_top_pan", st.session_state.split_top_pan_slider),
                    help="Ajuste para centralizar o personagem do vídeo principal no seu respectivo quadro."
                )
                split_bottom_pan = split_top_pan

            else:
                # Modo Câmera Dupla Padrão
                saved_split_auto = _cfg.get("split_auto_switch", True)
                split_auto_switch = st.toggle(
                    "🤖 Transição Dinâmica Inteligente (Auto-Switch)",
                    value=saved_split_auto,
                    key="split_auto_switch_tgl",
                    on_change=lambda: save_setting("split_auto_switch", st.session_state.split_auto_switch_tgl),
                    help="Recomendado: Quando houver 2+ pessoas no enquadramento, aplica o Split Screen. Se a câmera fechar em Close-up de apenas 1 pessoa, expande suavemente para 9:16 Full Screen sem cortar ninguém!"
                )
                col_sp1, col_sp2 = st.columns(2)
                with col_sp1:
                    saved_split_preset = _cfg.get("split_preset", "👈 Entrevistador(es) no Topo | 👉 Entrevistado na Base (Padrão Podpah/Flow)")
                    split_presets_list = [
                        "👈 Entrevistador(es) no Topo | 👉 Entrevistado na Base (Padrão Podpah/Flow)",
                        "👉 Entrevistado no Topo | 👈 Entrevistador(es) na Base",
                        "🎛️ Personalizado (Sliders Manuais)"
                    ]
                    split_p_idx = split_presets_list.index(saved_split_preset) if saved_split_preset in split_presets_list else 0
                    split_preset = st.selectbox(
                        "🎬 Distribuição dos Personagens:",
                        split_presets_list,
                        index=split_p_idx,
                        key="split_preset_choice",
                        on_change=lambda: save_setting("split_preset", st.session_state.split_preset_choice)
                    )
                    
                    if split_preset == "👈 Entrevistador(es) no Topo | 👉 Entrevistado na Base (Padrão Podpah/Flow)":
                        split_top_pan = -0.65
                        split_bottom_pan = 0.65
                    elif split_preset == "👉 Entrevistado no Topo | 👈 Entrevistador(es) na Base":
                        split_top_pan = 0.65
                        split_bottom_pan = -0.65
                    else:
                        saved_top_pan = float(_cfg.get("split_top_pan", -0.65))
                        saved_bottom_pan = float(_cfg.get("split_bottom_pan", 0.65))
                        split_top_pan = st.slider(
                            "↔️ Foco Horizontal do Topo:", -1.0, 1.0, saved_top_pan, 0.05,
                            key="split_top_pan_slider",
                            on_change=lambda: save_setting("split_top_pan", st.session_state.split_top_pan_slider)
                        )
                        split_bottom_pan = st.slider(
                            "↔️ Foco Horizontal da Base:", -1.0, 1.0, saved_bottom_pan, 0.05,
                            key="split_bottom_pan_slider",
                            on_change=lambda: save_setting("split_bottom_pan", st.session_state.split_bottom_pan_slider)
                        )

            # Controles comuns de Zoom, Margem com Blur e Linha Divisória
            col_z, col_m = st.columns(2)
            with col_z:
                saved_split_zoom = float(_cfg.get("split_zoom", 1.15))
                split_zoom_val = st.slider(
                    "🔍 Zoom / Aproximação dos Quadros:",
                    min_value=1.0,
                    max_value=2.0,
                    value=saved_split_zoom,
                    step=0.05,
                    format="%.2fx",
                    key="split_zoom_slider",
                    on_change=lambda: save_setting("split_zoom", st.session_state.split_zoom_slider),
                    help="Aumente para aproximar o enquadramento do vídeo principal."
                )
            with col_m:
                saved_blur_margin = float(_cfg.get("split_blur_margin_pct", 5.0))
                split_blur_margin_pct = st.slider(
                    "🌫️ Margem com Fundo Desfocado (Topo & Base):",
                    min_value=0.0,
                    max_value=20.0,
                    value=saved_blur_margin,
                    step=0.5,
                    format="%.1f%%",
                    key="split_blur_margin_slider",
                    on_change=lambda: save_setting("split_blur_margin_pct", st.session_state.split_blur_margin_slider),
                    help="Adiciona uma faixa com fundo desfocado no topo e na base (ex: 5% = 96px em cada borda), evitando que os botões do Shorts/Reels e títulos cubram os oradores."
                )

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                saved_div_col = _cfg.get("split_divider_color", "black")
                div_cols_list = ["black", "white", "gray", "none"]
                div_c_idx = div_cols_list.index(saved_div_col) if saved_div_col in div_cols_list else 0
                split_div_color = st.selectbox(
                    "Linha Divisória:",
                    div_cols_list,
                    index=div_c_idx,
                    key="split_div_color_sel",
                    on_change=lambda: save_setting("split_divider_color", st.session_state.split_div_color_sel),
                    format_func=lambda x: {"black": "⬛ Preta", "white": "⬜ Branca", "gray": "🔘 Cinza", "none": "🚫 Sem Linha"}[x]
                )
            with col_d2:
                saved_div_w = int(_cfg.get("split_divider_width", 4))
                split_div_w = st.slider(
                    "Espessura da Linha:", 0, 8, saved_div_w,
                    key="split_div_w_slider",
                    on_change=lambda: save_setting("split_divider_width", st.session_state.split_div_w_slider)
                )

            if start_time:
                if st.button("👁️ Visualizar Prévia do Split Screen", key="btn_prev_split"):
                    active_u = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id = get_video_id(active_u)
                    v_full = os.path.join("data", v_id, "video_full.mp4") if v_id else ""
                    if os.path.exists(v_full):
                        from core.face_tracker import generate_split_preview_image
                        prev_sp_path = os.path.join("data", v_id, "preview_split.jpg")
                        p_res = generate_split_preview_image(
                            v_full,
                            start_time,
                            prev_sp_path,
                            top_pan=split_top_pan,
                            bottom_pan=split_bottom_pan,
                            zoom=split_zoom_val,
                            divider_color=split_div_color,
                            divider_width=split_div_w,
                            split_source_type=split_source_type,
                            split_video_path=split_video_path,
                            split_image_paths=split_image_paths,
                            split_media_position=split_media_position,
                            split_blur_margin_pct=split_blur_margin_pct
                        )
                        if p_res.get("path") and os.path.exists(p_res["path"]):
                            st.image(p_res["path"], caption=f"Prévia 9:16 Split Screen em {start_time}", use_container_width=True)
                        else:
                            st.error(f"Erro na prévia: {p_res.get('error')}")
                    else:
                        st.info("O vídeo precisa ser baixado para gerar a prévia.")

    elif selected_aspect == "9:16_smart_face":
        with st.expander("🎯 Ajustes de Rastreamento, Foco e Margens do Personagem", expanded=True):
            col_fz1, col_fz2 = st.columns(2)
            with col_fz1:
                saved_face_target = _cfg.get("face_target_choice", "🎯 Automático (Maior Dominância)")
                face_target_list = [
                    "👥 Ambos os Interlocutores (Plano Conjunto / Dual)",
                    "👉 Personagem da Direita / Entrevistado",
                    "👈 Personagem da Esquerda",
                    "🔍 Personagem Mais Central",
                    "🎯 Automático (Maior Dominância)"
                ]
                face_t_idx = face_target_list.index(saved_face_target) if saved_face_target in face_target_list else 4
                target_choice = st.selectbox(
                    "👤 Personagem Alvo (Trava de Continuidade):",
                    face_target_list,
                    index=face_t_idx,
                    key="face_target_sel",
                    on_change=lambda: save_setting("face_target_choice", st.session_state.face_target_sel),
                    help="Trava o rastreamento no interlocutor selecionado ou enquadra ambos em plano conjunto simultaneamente."
                )
                target_map = {
                    "👥 Ambos os Interlocutores (Plano Conjunto / Dual)": "both",
                    "👉 Personagem da Direita / Entrevistado": "right",
                    "👈 Personagem da Esquerda": "left",
                    "🔍 Personagem Mais Central": "center",
                    "🎯 Automático (Maior Dominância)": "auto"
                }
                person_pref_val = target_map[target_choice]

                saved_face_zoom = _cfg.get("face_auto_zoom", True)
                face_zoom_active = st.toggle(
                    "🔍 Auto-Zoom Máximo no Personagem",
                    value=saved_face_zoom,
                    key="face_auto_zoom_tgl",
                    on_change=lambda: save_setting("face_auto_zoom", st.session_state.face_auto_zoom_tgl),
                    help="Aproxima a câmera vertical no interlocutor principal detectado, eliminando espaços vazios com máxima nitidez."
                )

            with col_fz2:
                saved_face_margin = _cfg.get("face_margin_choice", "Equilibrada (Busto & Rosto - Recomendado)")
                face_margins_list = ["Estreita (Close-up Máximo)", "Equilibrada (Busto & Rosto - Recomendado)", "Ampla (Plano Médio)"]
                face_m_val = saved_face_margin if saved_face_margin in face_margins_list else face_margins_list[1]
                margin_choice = st.select_slider(
                    "📏 Margem Lateral de Segurança:",
                    options=face_margins_list,
                    value=face_m_val,
                    key="face_margin_sel",
                    on_change=lambda: save_setting("face_margin_choice", st.session_state.face_margin_sel)
                )
                if margin_choice == "Estreita (Close-up Máximo)":
                    face_margin_val = 1.30
                elif margin_choice == "Ampla (Plano Médio)":
                    face_margin_val = 1.85
                else:
                    face_margin_val = 1.55

                # Botão de prévia instantânea de enquadramento
                if start_time:
                    if st.button("👁️ Visualizar Prévia do Enquadramento", key="btn_preview_face"):
                        _active_preview_url = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                        video_id = get_video_id(_active_preview_url)
                        v_full = os.path.join("data", video_id, "video_full.mp4") if video_id else ""
                        if os.path.exists(v_full):
                            from core.face_tracker import generate_face_preview_image
                            prev_path = os.path.join("data", video_id, "preview_face.jpg")
                            p_res = generate_face_preview_image(
                                v_full,
                                start_time,
                                prev_path,
                                person_preference=person_pref_val,
                                auto_zoom=face_zoom_active,
                                margin_ratio=face_margin_val
                            )
                            if p_res.get("path") and os.path.exists(p_res["path"]):
                                if p_res.get("dual_shot"):
                                    if p_res.get("broadcast_split"):
                                        st.success("🎙️ **Debate TV / Split-Screen Detectado!** Enquadramento Dual Shot aplicado — ambos os interlocutores na moldura. Linha divisória de broadcast identificada por análise estrutural.")
                                    else:
                                        st.success("👥 **Dual Shot Detectado!** Bounding box composta englobando ambos os interlocutores.")
                                st.image(p_res["path"], caption=f"Prévia em {start_time} — Azul: DUAL SHOT | Amarelo: Moldura 9:16 | Verde: Alvo | Laranja: Interlocutor", use_container_width=True)
                            else:
                                st.error(f"Erro na prévia: {p_res.get('error')}")
                        else:
                            st.info("O vídeo precisa ser baixado para gerar a prévia.")

    elif selected_aspect == "9:16_blur":
        with st.expander("🌫️ Ajustes do Fundo Desfocado (Auto-Zoom e Margens)", expanded=True):
            saved_blur_mode = _cfg.get("blur_mode_ctrl", "🤖 Auto-Zoom Inteligente no Personagem (Recomendado)")
            blur_mode_list = ["🤖 Auto-Zoom Inteligente no Personagem (Recomendado)", "🎛️ Manual (Sliders de Zoom e Posição)"]
            blur_m_idx = blur_mode_list.index(saved_blur_mode) if saved_blur_mode in blur_mode_list else 0
            mode_blur_ctrl = st.radio(
                "Modo de Enquadramento:",
                blur_mode_list,
                index=blur_m_idx,
                horizontal=True,
                key="mode_blur_ctrl_radio",
                on_change=lambda: save_setting("blur_mode_ctrl", st.session_state.mode_blur_ctrl_radio)
            )

            if mode_blur_ctrl == "🤖 Auto-Zoom Inteligente no Personagem (Recomendado)":
                col_ab1, col_ab2 = st.columns(2)
                with col_ab1:
                    saved_blur_target = _cfg.get("blur_target_choice", "🎯 Automático (Detecta se há 1 ou 2 oradores)")
                    blur_target_list = [
                        "👥 Ambos os Interlocutores (Plano Conjunto / Dual)",
                        "🎯 Automático (Detecta se há 1 ou 2 oradores)",
                        "👉 Personagem da Direita / Entrevistado",
                        "👈 Personagem da Esquerda",
                        "🔍 Personagem Mais Central"
                    ]
                    blur_t_idx = blur_target_list.index(saved_blur_target) if saved_blur_target in blur_target_list else 1
                    blur_target_choice = st.selectbox(
                        "👤 Personagem Alvo:",
                        blur_target_list,
                        index=blur_t_idx,
                        key="blur_target_sel",
                        on_change=lambda: save_setting("blur_target_choice", st.session_state.blur_target_sel)
                    )
                    blur_target_map = {
                        "👥 Ambos os Interlocutores (Plano Conjunto / Dual)": "both",
                        "🎯 Automático (Detecta se há 1 ou 2 oradores)": "auto",
                        "👉 Personagem da Direita / Entrevistado": "right",
                        "👈 Personagem da Esquerda": "left",
                        "🔍 Personagem Mais Central": "center"
                    }
                    blur_person_pref = blur_target_map[blur_target_choice]
                    person_pref_val = blur_person_pref

                with col_ab2:
                    saved_blur_margin = _cfg.get("blur_margin_choice", "Equilibrada (Busto & Rosto)")
                    blur_margins_list = ["Estreita (Close-up Máximo / Menor Desfoque)", "Equilibrada (Busto & Rosto)", "Ampla (Plano Médio)"]
                    blur_m_val = saved_blur_margin if saved_blur_margin in blur_margins_list else blur_margins_list[1]
                    blur_margin_choice = st.select_slider(
                        "📏 Margem Lateral de Segurança:",
                        options=blur_margins_list,
                        value=blur_m_val,
                        key="blur_margin_sel",
                        on_change=lambda: save_setting("blur_margin_choice", st.session_state.blur_margin_sel)
                    )
                    if blur_margin_choice == "Estreita (Close-up Máximo / Menor Desfoque)":
                        blur_margin_val = 1.30
                    elif blur_margin_choice == "Ampla (Plano Médio)":
                        blur_margin_val = 1.85
                    else:
                        blur_margin_val = 1.55

                # Calcula automaticamente o Zoom e Pan
                _active_blur_url = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                video_id = get_video_id(_active_blur_url)
                v_full = os.path.join("data", video_id, "video_full.mp4") if video_id else ""
                if os.path.exists(v_full) and start_time:
                    from core.face_tracker import calculate_auto_blur_params, generate_blur_preview_image
                    auto_p = calculate_auto_blur_params(v_full, start_time, blur_person_pref, blur_margin_val)
                    blur_zoom_val = auto_p["zoom"]
                    blur_pan_val = auto_p["pan"]

                    if auto_p.get("dual_shot"):
                        if auto_p.get("broadcast_split"):
                            st.success(f"🎙️ **Debate TV / Split-Screen Detectado!** Zoom: **{blur_zoom_val:.2f}x** | Pan: **{blur_pan_val:+.2f}** — Enquadramento calibrado para exibir ambos os candidatos. Linha divisória de broadcast identificada.")
                        else:
                            st.info("👥 **Plano Conjunto / Dual Detectado!** Enquadramento calibrado para exibir ambos os interlocutores.")
                    else:
                        st.caption(f"✨ Auto-Zoom Calculado: **{blur_zoom_val:.2f}x** | Foco Horizontal: **{blur_pan_val:+.2f}**")

                    st.info("🎥 **Rastreamento Dinâmico Ativo**: A câmera acompanhará o orador suavemente durante todo o corte, mantendo-o enquadrado e centralizado.")

                    if st.button("👁️ Visualizar Prévia com Fundo Desfocado", key="btn_prev_blur"):
                        prev_b_path = os.path.join("data", video_id, "preview_blur.jpg")
                        p_res = generate_blur_preview_image(v_full, start_time, prev_b_path, blur_zoom_val, blur_pan_val, blur_int_val)
                        if p_res.get("path") and os.path.exists(p_res["path"]):
                            dual_caption = " [DUAL SHOT]" if auto_p.get("dual_shot") else ""
                            st.image(p_res["path"], caption=f"Prévia 9:16 Fundo Desfocado em {start_time}{dual_caption} (Zoom: {blur_zoom_val:.2f}x)", use_container_width=True)
                        else:
                            st.error(f"Erro na prévia: {p_res.get('error')}")
                else:
                    blur_zoom_val = 1.0 if blur_person_pref == "both" else (1.45 if blur_person_pref != "center" else 1.35)
                    blur_pan_val = 0.0 if blur_person_pref == "both" else (0.6 if blur_person_pref == "right" else (-0.6 if blur_person_pref == "left" else 0.0))

            else:
                col_z1, col_z2 = st.columns(2)
                with col_z1:
                    saved_blur_zoom = float(_cfg.get("blur_zoom_custom", 1.35))
                    blur_zoom_val = st.slider(
                        "🔍 Nível de Aproximação (Zoom Manual):",
                        min_value=1.0,
                        max_value=2.5,
                        value=saved_blur_zoom,
                        step=0.05,
                        format="%.2fx",
                        key="blur_zoom_slider",
                        on_change=lambda: save_setting("blur_zoom_custom", st.session_state.blur_zoom_slider),
                        help="Aumente para o vídeo preencher mais a tela e diminuir as faixas superior/inferior de desfoque."
                    )
                with col_z2:
                    saved_pan_preset = _cfg.get("blur_pan_preset", "Centro (0%)")
                    pan_presets_list = [
                        "Centro (0%)",
                        "Personagem à Esquerda (-60%)",
                        "Personagem à Direita (+60%)",
                        "Extrema Esquerda (-100%)",
                        "Extrema Direita (+100%)",
                        "Ajuste Fino Personalizado"
                    ]
                    pan_p_idx = pan_presets_list.index(saved_pan_preset) if saved_pan_preset in pan_presets_list else 0
                    pan_preset = st.selectbox(
                        "↔️ Posição / Foco Horizontal:",
                        pan_presets_list,
                        index=pan_p_idx,
                        key="blur_pan_preset_sel",
                        on_change=lambda: save_setting("blur_pan_preset", st.session_state.blur_pan_preset_sel)
                    )
                    if pan_preset == "Personagem à Esquerda (-60%)":
                        blur_pan_val = -0.6
                    elif pan_preset == "Personagem à Direita (+60%)":
                        blur_pan_val = 0.6
                    elif pan_preset == "Extrema Esquerda (-100%)":
                        blur_pan_val = -1.0
                    elif pan_preset == "Extrema Direita (+100%)":
                        blur_pan_val = 1.0
                    elif pan_preset == "Ajuste Fino Personalizado":
                        saved_pan_custom = float(_cfg.get("blur_pan_custom", 0.0))
                        blur_pan_val = st.slider(
                            "Deslocamento Horizontal:", -1.0, 1.0, saved_pan_custom, 0.05,
                            key="blur_pan_custom_slider",
                            on_change=lambda: save_setting("blur_pan_custom", st.session_state.blur_pan_custom_slider)
                        )
                    else:
                        blur_pan_val = 0.0

    elif selected_aspect == "16:9":
        with st.expander("🔍 Ajustes do Modo Horizontal 16:9 (Aproximação / Zoom Geral)", expanded=True):
            col_hz1, col_hz2 = st.columns([2, 1])
            with col_hz1:
                saved_hz_zoom = float(_cfg.get("horizontal_zoom", 1.0))
                horizontal_zoom_val = st.number_input(
                    "🔎 Nível de Aproximação (Zoom):",
                    min_value=1.00,
                    max_value=3.00,
                    value=saved_hz_zoom,
                    step=0.02,
                    format="%.2f",
                    key="hz_zoom_slider",
                    help="Aproxima o enquadramento horizontal centralizado (ideal para focar nos oradores ou remover marcas d'água e barras pretas das bordas)."
                )
            with col_hz2:
                if horizontal_zoom_val > 1.00:
                    st.caption(f"✨ Zoom ativo: **{horizontal_zoom_val:.2f}x** (+{int((horizontal_zoom_val - 1.0) * 100)}% de aproximação)")
                else:
                    st.caption("✨ Enquadramento original 1:1 (Sem zoom)")

            if start_time:
                if st.button("👁️ Visualizar Prévia com Aproximação 16:9", key="btn_prev_169"):
                    _active_preview_url = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    video_id = get_video_id(_active_preview_url)
                    v_full = os.path.join("data", video_id, "video_full.mp4") if video_id else ""
                    if os.path.exists(v_full):
                        from core.face_tracker import generate_169_preview_image
                        prev_169_path = os.path.join("data", video_id, "preview_169.jpg")
                        p_res = generate_169_preview_image(v_full, start_time, prev_169_path, zoom_factor=horizontal_zoom_val)
                        if p_res.get("path") and os.path.exists(p_res["path"]):
                            st.image(p_res["path"], caption=f"Prévia 16:9 em {start_time} com Zoom {horizontal_zoom_val:.2f}x", use_container_width=True)
                        else:
                            st.error(f"Erro na prévia: {p_res.get('error')}")
                    else:
                        st.info("O vídeo precisa ser baixado para gerar a prévia.")

    # ─────────────────────────────────────────────────────────────────
    # Legendas Dinâmicas (Fase 2)
    # ─────────────────────────────────────────────────────────────────
    subtitle_enabled = _cfg.get("subtitle_enabled", False)
    subtitle_highlight_color = _cfg.get("subtitle_highlight_color", "#FFFF00")
    subtitle_base_color = _cfg.get("subtitle_base_color", "#FFFFFF")
    subtitle_font_size = _cfg.get("subtitle_font_size", 80)

    with st.expander("📝 Legendas Dinâmicas (Estilo CapCut / Alex Hormozi)", expanded=subtitle_enabled):
        subtitle_enabled = st.toggle(
            "✨ Ativar Legendas Palavra-a-Palavra",
            value=subtitle_enabled,
            help="Queima legendas sincronizadas diretamente no vídeo renderizado, com destaque animado na palavra atual."
        )
        if subtitle_enabled:
            # Verifica se a transcrição está disponível com timestamps
            _vid_id_sub = get_video_id(video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or "")
            _transcript_path_sub = os.path.join("data", _vid_id_sub, "transcript.json") if _vid_id_sub else ""
            _has_transcript = os.path.exists(_transcript_path_sub)

            if not _has_transcript:
                st.warning("⚠️ Transcrição não encontrada. Realize a transcrição na Seção 1 antes de ativar as legendas.")
                subtitle_enabled = False
            else:
                # Verifica se há word_timestamps no transcript salvo
                import json as _json_sub
                try:
                    with open(_transcript_path_sub, encoding="utf-8") as _tf:
                        _td = _json_sub.load(_tf)
                    _segs = _td.get("segments", [])
                    _has_words = any(s.get("words") for s in _segs[:5])
                    if not _has_words:
                        st.info("ℹ️ Transcrição sem timestamps por palavra. As legendas usarão distribuição proporcional (recomenda-se retranscrever com Whisper para precisão máxima).")
                except Exception:
                    pass

                col_sub1, col_sub2, col_sub3 = st.columns([2, 2, 1])
                with col_sub1:
                    subtitle_highlight_color = st.color_picker(
                        "🎨 Cor do Destaque (Palavra Atual)",
                        value=subtitle_highlight_color,
                        key="sub_highlight_color",
                        help="Cor vibrante que pisca na palavra sendo falada."
                    )
                with col_sub2:
                    subtitle_base_color = st.color_picker(
                        "💤 Cor das Demais Palavras",
                        value=subtitle_base_color,
                        key="sub_base_color",
                        help="Cor das palavras da linha atual que ainda não foram ditas."
                    )
                with col_sub3:
                    subtitle_font_size = st.number_input(
                        "🔤 Fonte",
                        min_value=10,
                        max_value=300,
                        value=subtitle_font_size,
                        step=5,
                        key="sub_font_size",
                        help="Tamanho da fonte das legendas (recomendado entre 75 e 110 para cortes 9:16 estilo Alex Hormozi)."
                    )
                st.caption("📌 Legendas no terço inferior da tela • Fonte Montserrat Bold • Contorno preto para legibilidade em qualquer fundo")

    # ─────────────────────────────────────────────────────────────────
    # 🏷️ Headline / Título Fixo de Retenção no Topo (Fase 3)
    # ─────────────────────────────────────────────────────────────────
    headline_enabled = _cfg.get("headline_enabled", False)
    headline_preset = _cfg.get("headline_preset", "yellow_black")
    headline_text_color = _cfg.get("headline_text_color", "#000000")
    headline_bg_color = _cfg.get("headline_bg_color", "#FFDA29")
    headline_font_size = _cfg.get("headline_font_size", 46)
    headline_margin_top = _cfg.get("headline_margin_top", 120)

    with st.expander("🏷️ Headline / Título Fixo de Retenção no Topo (9:16 - Fase 3)", expanded=headline_enabled):
        headline_enabled = st.toggle(
            "📌 Fixar Título Chamativo no Topo do Vídeo",
            value=headline_enabled,
            key="headline_enabled_tgl",
            on_change=lambda: save_setting("headline_enabled", st.session_state.headline_enabled_tgl),
            help="Adiciona uma caixa de headline magnética na parte superior do corte 9:16 (estilo vídeos virais de TikTok/Reels) que segura a atenção nos primeiros segundos."
        )
        if headline_enabled:
            col_hp1, col_hp2, col_hp3 = st.columns([2, 1.2, 1.2])
            with col_hp1:
                preset_keys = list(HEADLINE_PRESETS.keys()) + ["custom"]
                preset_labels = [HEADLINE_PRESETS[k]["name"] for k in HEADLINE_PRESETS] + ["🎨 Cores Personalizadas"]
                cur_preset_idx = preset_keys.index(headline_preset) if headline_preset in preset_keys else 0
                sel_preset_label = st.selectbox(
                    "Estilo Visual da Headline:",
                    preset_labels,
                    index=cur_preset_idx,
                    key="headline_preset_sel",
                    on_change=lambda: save_setting("headline_preset", preset_keys[preset_labels.index(st.session_state.headline_preset_sel)])
                )
                headline_preset = preset_keys[preset_labels.index(sel_preset_label)]

            with col_hp2:
                headline_font_size = st.number_input(
                    "Tamanho da Fonte:", min_value=10, max_value=200, value=headline_font_size, step=2,
                    key="hl_font_sz",
                    on_change=lambda: save_setting("headline_font_size", st.session_state.hl_font_sz)
                )

            with col_hp3:
                headline_margin_top = st.number_input(
                    "Margem do Topo:", min_value=0, max_value=1000, value=headline_margin_top, step=10,
                    key="hl_margin_tp",
                    on_change=lambda: save_setting("headline_margin_top", st.session_state.hl_margin_tp),
                    help="Distância da borda superior para não cobrir elementos da interface do TikTok/Shorts."
                )

            if headline_preset == "custom":
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    headline_text_color = st.color_picker(
                        "Cor do Texto:", headline_text_color,
                        key="hl_txt_col",
                        on_change=lambda: save_setting("headline_text_color", st.session_state.hl_txt_col)
                    )
                with col_c2:
                    headline_bg_color = st.color_picker(
                        "Cor da Caixa de Fundo:", headline_bg_color,
                        key="hl_bg_col",
                        on_change=lambda: save_setting("headline_bg_color", st.session_state.hl_bg_col)
                    )

            st.caption("💡 O texto da Headline puxará automaticamente o Título Viral gerado pela IA ou digitado no Kit de Publicação abaixo.")

    # ─────────────────────────────────────────────────────────────────
    # 🖼️ Efeitos Visuais & Retenção de Feed (Fases 3 e 4)
    # ─────────────────────────────────────────────────────────────────
    zoom_punch_enabled = _cfg.get("zoom_punch_enabled", False)
    emojis_enabled = _cfg.get("emojis_enabled", False)

    with st.expander("🖼️ Efeitos de Retenção Visual (Zoom Punch & Emojis - Fase 3)", expanded=(zoom_punch_enabled or emojis_enabled)):
        col_ef1, col_ef2 = st.columns(2)
        with col_ef1:
            zoom_punch_enabled = st.toggle(
                "🔍 Zoom Punch Dinâmico",
                value=zoom_punch_enabled,
                help="Aplica pulsos suaves de aproximação (1.07x) a cada ~8 segundos para quebrar a monotonia visual e elevar a retenção de feed."
            )
        with col_ef2:
            emojis_enabled = st.toggle(
                "😃 Emojis Contextuais nas Legendas",
                value=emojis_enabled,
                help="Insere automaticamente stickers e emojis (💰, 🔥, 🚀, 🧠, ⚠️) ao lado de palavras de alta carga emocional."
            )

    # ─────────────────────────────────────────────────────────────────
    # 🚀 Polimento Visual, Thumbnails & Retenção Dinâmica (Fase 4)
    # ─────────────────────────────────────────────────────────────────
    progress_bar_enabled = _cfg.get("progress_bar_enabled", False)
    progress_bar_color = _cfg.get("progress_bar_color", "#FF0000")
    progress_bar_height = int(_cfg.get("progress_bar_height", 8))
    callout_enabled = _cfg.get("callout_enabled", False)
    callout_preset = _cfg.get("callout_preset", "comment")
    callout_text = _cfg.get("callout_text", "💬 O que você acha? Comente abaixo!")
    callout_duration = float(_cfg.get("callout_duration", 4.5))
    climax_zoom_enabled = _cfg.get("climax_zoom_enabled", False)
    climax_zoom_factor = float(_cfg.get("climax_zoom_factor", 1.14))
    thumbnail_enabled = _cfg.get("thumbnail_enabled", True)

    with st.expander("🚀 Retenção Dinâmica, Thumbnails & Callout (Fase 4)", expanded=(progress_bar_enabled or callout_enabled or climax_zoom_enabled or thumbnail_enabled)):
        col_f4_1, col_f4_2 = st.columns(2)
        with col_f4_1:
            progress_bar_enabled = st.toggle(
                "⏳ Barra de Progresso no Rodapé",
                value=progress_bar_enabled,
                help="Desenha uma linha minimalista no rodapé indicando o progresso do corte para reter o espectador até o final."
            )
            if progress_bar_enabled:
                col_pb1, col_pb2 = st.columns([1.5, 1])
                with col_pb1:
                    pb_color_keys = list(PROGRESS_BAR_COLORS.keys())
                    pb_color_labels = [PROGRESS_BAR_COLORS[k]["name"] for k in pb_color_keys]
                    cur_pb_col_idx = 0
                    for i_k, k in enumerate(pb_color_keys):
                        if PROGRESS_BAR_COLORS[k]["color"].upper() == progress_bar_color.upper():
                            cur_pb_col_idx = i_k
                            break
                    sel_pb_label = st.selectbox("Cor da Barra:", pb_color_labels, index=cur_pb_col_idx, key="sel_pb_color")
                    progress_bar_color = PROGRESS_BAR_COLORS[pb_color_keys[pb_color_labels.index(sel_pb_label)]]["color"]
                with col_pb2:
                    progress_bar_height = st.number_input("Espessura (px):", min_value=1, max_value=60, value=progress_bar_height, step=1, key="sl_pb_height")

            st.divider()

            climax_zoom_enabled = st.toggle(
                "🎯 Zoom de Ênfase no Clímax (Punchline Final)",
                value=climax_zoom_enabled,
                help="Aproxima dramaticamente no rosto do orador nos últimos segundos da conclusão para reforçar a frase de impacto."
            )
            if climax_zoom_enabled:
                climax_zoom_factor = st.number_input(
                    "Intensidade do Zoom de Clímax:",
                    min_value=1.00, max_value=3.00, value=climax_zoom_factor, step=0.02,
                    format="%.2f",
                    help="1.08x = Suave | 1.14x = Médio/Dramático | 1.20x = Impacto Forte"
                )

        with col_f4_2:
            thumbnail_enabled = st.toggle(
                "🖼️ Gerar Capa / Thumbnail 9:16 com IA",
                value=thumbnail_enabled,
                help="Captura automaticamente o melhor frame com MediaPipe/nitidez, compõe com a Headline magnética e salva thumbnail.jpg na pasta do corte."
            )

            st.divider()

            callout_enabled = st.toggle(
                "📌 Banner de Chamada / Lower Third (Callout)",
                value=callout_enabled,
                help="Exibe um banner elegante nos últimos 4-5 segundos provocando comentários e seguidores nas redes."
            )
            if callout_enabled:
                co_keys = list(ENGAGEMENT_CALLOUT_PRESETS.keys())
                co_labels = [ENGAGEMENT_CALLOUT_PRESETS[k]["name"] for k in co_keys]
                cur_co_idx = co_keys.index(callout_preset) if callout_preset in co_keys else 0
                sel_co_label = st.selectbox("Modelo de Chamada:", co_labels, index=cur_co_idx, key="sel_co_preset")
                callout_preset = co_keys[co_labels.index(sel_co_label)]

                if callout_preset != "custom":
                    callout_text = ENGAGEMENT_CALLOUT_PRESETS[callout_preset]["text"]

                callout_text = st.text_input(
                    "Texto do Banner:",
                    value=callout_text,
                    key="txt_callout_val"
                )
                callout_duration = st.number_input("Duração do Banner (segundos no final):", min_value=0.5, max_value=30.0, value=callout_duration, step=0.5, key="sl_co_dur")

    # ─────────────────────────────────────────────────────────────────
    # 🎵 Trilha Sonora de Fundo & Audio Ducking Inteligente (Fase 3)
    # ─────────────────────────────────────────────────────────────────
    bg_music_enabled = _cfg.get("bg_music_enabled", False)
    bg_music_track_id = _cfg.get("bg_music_track_id", "lofi_chill")
    bg_music_volume = float(_cfg.get("bg_music_volume", 0.15))
    ducking_preset = _cfg.get("ducking_preset", "medio")

    available_tracks = list_available_tracks()
    track_ids = [t["id"] for t in available_tracks]
    track_labels = [f"{t['title']} — {t['description']}" for t in available_tracks]
    cur_track_idx = track_ids.index(bg_music_track_id) if bg_music_track_id in track_ids else 0

    with st.expander("🎵 Trilha Sonora & Audio Ducking Inteligente (Fase 3)", expanded=bg_music_enabled):
        bg_music_enabled = st.toggle(
            "🎶 Adicionar Música de Fundo com Audio Ducking",
            value=bg_music_enabled,
            help="A música toca no fundo e reduz suavemente de volume sempre que alguém estiver falando (via sidechaincompress FFmpeg)."
        )
        bg_music_track_path = None
        if bg_music_enabled and available_tracks:
            col_m1, col_m2 = st.columns([2, 1.2])
            with col_m1:
                sel_track_label = st.selectbox("Escolha a Trilha Sonora:", track_labels, index=cur_track_idx)
                selected_track_obj = available_tracks[track_labels.index(sel_track_label)]
                bg_music_track_id = selected_track_obj["id"]
                bg_music_track_path = selected_track_obj["path"]

                # Player de áudio para prévia da música
                if os.path.exists(bg_music_track_path):
                    with open(bg_music_track_path, "rb") as af_prev:
                        _fmt = "audio/mp3" if bg_music_track_path.endswith(".mp3") else "audio/wav"
                        st.audio(af_prev.read(), format=_fmt)

            with col_m2:
                bg_music_volume = st.number_input("Volume da Música:", min_value=0.01, max_value=1.00, value=bg_music_volume, step=0.02, format="%.2f", help="Volume base da música quando não houver fala.")
                duck_keys = list(DUCKING_PRESETS.keys())
                duck_labels = [DUCKING_PRESETS[k]["name"] for k in duck_keys]
                cur_duck_idx = duck_keys.index(ducking_preset) if ducking_preset in duck_keys else 1
                sel_duck_label = st.selectbox("Atenuação na Fala (Ducking):", duck_labels, index=cur_duck_idx)
                ducking_preset = duck_keys[duck_labels.index(sel_duck_label)]

            # Uploader de músicas e botão de abrir pasta
            col_u1, col_u2 = st.columns([2, 1])
            with col_u1:
                upload_custom_music = st.file_uploader(
                    "➕ Importar Trilha / Som Personalizado (.mp3 ou .wav):",
                    type=["mp3", "wav", "m4a", "aac", "ogg"],
                    key="custom_music_uploader",
                    help="Arraste qualquer música ou efeito sonoro do seu computador para adicioná-lo permanentemente à biblioteca."
                )
                if upload_custom_music is not None:
                    _sig_sec3 = f"{upload_custom_music.name}_{upload_custom_music.size}"
                    if st.session_state.get("_processed_sig_sec3") != _sig_sec3:
                        st.session_state["_processed_sig_sec3"] = _sig_sec3
                        _tmp_sec3 = os.path.join("data", f"temp_sec3_{upload_custom_music.name}")
                        os.makedirs("data", exist_ok=True)
                        with open(_tmp_sec3, "wb") as f_m_out:
                            f_m_out.write(upload_custom_music.getbuffer())
                        _reg_sec3 = register_custom_audio_track(_tmp_sec3, title=f"📁 {os.path.splitext(upload_custom_music.name)[0]}", category_name="Personalizada")
                        if _reg_sec3.get("track"):
                            save_setting("bg_music_track_id", _reg_sec3["track"]["id"])
                            st.rerun()

            with col_u2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("📂 Abrir Pasta de Áudios", key="btn_open_audio_dir", use_container_width=True):
                    _a_dir = os.path.abspath(os.path.join("assets", "audio"))
                    os.makedirs(_a_dir, exist_ok=True)
                    os.startfile(_a_dir)

        elif not available_tracks:
            st.info("Nenhuma trilha encontrada em assets/audio.")

    # Salva continuamente todas as configurações ativas
    save_all_settings({
        "device_option": device_option,
        "model_size": model_size,
        "ollama_model": ollama_model,
        "analysis_strategy": strategy_choice,
        "aspect_option": aspect_option,
        "face_auto_zoom": face_zoom_active,
        "face_margin_ratio": face_margin_val,
        "person_preference": person_pref_val,
        "split_auto_switch": split_auto_switch,
        "split_zoom": split_zoom_val,
        "split_divider_color": split_div_color,
        "split_divider_width": split_div_w,
        "blur_zoom_custom": blur_zoom_val,
        "blur_intensity": blur_int_val,
        "blur_pan_custom": blur_pan_val,
        "subtitle_enabled": subtitle_enabled,
        "subtitle_highlight_color": subtitle_highlight_color,
        "subtitle_base_color": subtitle_base_color,
        "subtitle_font_size": subtitle_font_size,
        "headline_enabled": headline_enabled,
        "headline_preset": headline_preset,
        "headline_text_color": headline_text_color,
        "headline_bg_color": headline_bg_color,
        "headline_font_size": headline_font_size,
        "headline_margin_top": headline_margin_top,
        "zoom_punch_enabled": zoom_punch_enabled,
        "emojis_enabled": emojis_enabled,
        "progress_bar_enabled": progress_bar_enabled,
        "progress_bar_color": progress_bar_color,
        "progress_bar_height": progress_bar_height,
        "callout_enabled": callout_enabled,
        "callout_preset": callout_preset,
        "callout_text": callout_text,
        "callout_duration": callout_duration,
        "climax_zoom_enabled": climax_zoom_enabled,
        "climax_zoom_factor": climax_zoom_factor,
        "thumbnail_enabled": thumbnail_enabled,
        "bg_music_enabled": bg_music_enabled,
        "bg_music_track_id": bg_music_track_id,
        "bg_music_volume": bg_music_volume,
        "ducking_preset": ducking_preset,
    })

    # ─────────────────────────────────────────────────────────────────
    # Kit de Publicação Viral & Título (IA)
    # ─────────────────────────────────────────────────────────────────
    _active_url_cat = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
    _vid_id_cat = get_video_id(_active_url_cat) or ""

    # Consulta se a minutagem e o formato específico já foram gerados anteriormente
    existing_cut = get_cut_entry(_vid_id_cat, start_time, end_time) if (_vid_id_cat and start_time and end_time) else None
    existing_inst = get_format_instance(_vid_id_cat, start_time, end_time, selected_aspect) if (_vid_id_cat and start_time and end_time) else None

    if "meta_generated" not in st.session_state:
        st.session_state["meta_generated"] = False

    # Se existe entrada salva no catálogo para esta minutagem, sincroniza automaticamente
    if existing_cut and not st.session_state.get("meta_generated"):
        st.session_state["input_cut_title"] = existing_cut.get("title", "Corte Selecionado")
        st.session_state["input_cut_desc"] = existing_cut.get("description", "")
        st.session_state["input_cut_hashtags"] = " ".join(existing_cut.get("hashtags", []))
        st.session_state["input_cut_tags_seo"] = existing_cut.get("tags_seo", "")
        st.session_state["meta_generated"] = True
    elif "input_cut_title" not in st.session_state or not st.session_state["input_cut_title"]:
        if st.session_state.get("final_corte_title"):
            st.session_state["input_cut_title"] = st.session_state["final_corte_title"]
            st.session_state["meta_generated"] = True

    # ── Flush de atualizações pendentes dos botões individuais ──────────
    # (Deve ser aplicado ANTES dos widgets serem criados para evitar
    #  StreamlitAPIException ao modificar chave de widget já renderizado)
    _pending_map = {
        "_pending_cut_title":    "input_cut_title",
        "_pending_cut_headline": "input_cut_headline",
        "_pending_cut_desc":     "input_cut_desc",
        "_pending_cut_hashtags": "input_cut_hashtags",
        "_pending_cut_tags_seo": "input_cut_tags_seo",
    }
    for _pkey, _wkey in _pending_map.items():
        if _pkey in st.session_state:
            st.session_state[_wkey] = st.session_state.pop(_pkey)
    if "_pending_alt_titles" in st.session_state:
        st.session_state["meta_alt_titles"] = st.session_state.pop("_pending_alt_titles")

    with st.expander("🚀 Kit de Publicação Viral (Título, Descrição & Tags para Redes)", expanded=True):
        # ── Campo de Orientação Editorial / Tom e Assunto para IA ────────────
        user_guidance_val = st.text_input(
            "🎯 Guia Editorial para IA (Tom, Assunto e Foco do Corte - Opcional):",
            value=st.session_state.get("input_viral_kit_guidance", ""),
            placeholder="Ex: Foque na resposta sobre corrupção com tom polêmico e urgente; enfatize a frase de fechamento...",
            key="input_viral_kit_guidance",
            help="Instrua a IA sobre o tom desejado (ex: polêmico, indignado, bem-humorado, sério, urgente, reflexivo) e o assunto ou frase central que você quer priorizar no título, headline, descrição e tags."
        )

        col_meta_btn, col_meta_status = st.columns([1.8, 2.2])
        with col_meta_btn:
            if st.button("✨ Gerar Título e Textos com IA", use_container_width=True, type="secondary", help="Analisa o trecho exato do corte e gera Título Viral específico, Descrição contextualizada com CTA e Hashtags estratégicas."):
                _transcript_path_meta = os.path.join("data", _vid_id_cat, "transcript.json") if _vid_id_cat else ""
                if not os.path.exists(_transcript_path_meta):
                    st.warning("⚠️ Transcrição não encontrada. Transcreva o vídeo na Seção 1 primeiro.")
                elif not start_time or not end_time:
                    st.warning("⚠️ Defina o tempo inicial e final do corte primeiro.")
                else:
                    with st.spinner(f"Analisando falas de [{start_time} → {end_time}] e gerando kit viral com {ollama_model}..."):
                        import core.analyzer
                        from core.subtitle_burner import extract_words_in_range
                        words_meta = extract_words_in_range(_transcript_path_meta, start_time, end_time)
                        snippet_text = " ".join(w["word"] for w in words_meta)
                        if not snippet_text:
                            st.warning("Nenhuma fala encontrada no intervalo selecionado.")
                        else:
                            model_for_meta = ollama_model if 'ollama_model' in locals() and ollama_model else "llama3"
                            meta_res = core.analyzer.generate_viral_cut_metadata(
                                snippet_text,
                                model=model_for_meta,
                                user_guidance=user_guidance_val
                            )
                            
                            st.session_state["input_cut_title"] = meta_res.get("titulo_principal", "Corte Selecionado")
                            st.session_state["input_cut_headline"] = meta_res.get("headline_topo") or meta_res.get("titulo_principal", "Corte Selecionado")
                            st.session_state["input_cut_desc"] = meta_res.get("descricao", "")
                            st.session_state["input_cut_hashtags"] = " ".join(meta_res.get("hashtags", ["#shorts", "#viral", "#cortes"]))
                            st.session_state["input_cut_tags_seo"] = meta_res.get("tags_seo", "")
                            st.session_state["meta_alt_titles"] = meta_res.get("titulos_alternativos", [])
                            st.session_state["meta_generated"] = True
                            st.rerun()

        with col_meta_status:
            if existing_inst:
                st.success(f"⚡ **Instância Encontrada no Cache ({existing_inst.get('rendered_at')})!**")
            elif existing_cut:
                other_formats = list(existing_cut.get("formats", {}).keys())
                st.info(f"💡 Minutagem já gerada em: `{', '.join(other_formats)}`. Textos reaproveitados!")
            elif st.session_state.get("meta_generated"):
                st.success("✅ **Textos Gerados pela IA!** Conteúdo contextual pronto para postagem.")
            else:
                st.info("ℹ️ Clique no botão ao lado para gerar textos específicos com base no áudio.")

        # Sinalização visual no título de cada campo
        is_gen = st.session_state.get("meta_generated", False)
        badge_title = "🟢 [GERADO POR IA]" if is_gen else "⚪ [PADRÃO - CLIQUE ACIMA PARA GERAR]"
        badge_desc = "🟢 [GERADA POR IA COM CTA]" if is_gen else "⚪ [PADRÃO]"
        badge_tags = "🟢 [TAGS CONTEXTUAIS]" if is_gen else "⚪ [PADRÃO]"

        # Utilitário interno: extrai snippet do transcript do trecho selecionado
        def _get_snippet_for_regen():
            import core.analyzer
            from core.subtitle_burner import extract_words_in_range
            _tp = os.path.join("data", _vid_id_cat, "transcript.json") if _vid_id_cat else ""
            if not os.path.exists(_tp):
                st.warning("⚠️ Transcrição não encontrada. Transcreva o vídeo na Seção 1 primeiro.")
                return None
            if not start_time or not end_time:
                st.warning("⚠️ Defina o tempo inicial e final do corte primeiro.")
                return None
            _words = extract_words_in_range(_tp, start_time, end_time)
            _snip = " ".join(w["word"] for w in _words)
            if not _snip:
                st.warning("Nenhuma fala encontrada no intervalo selecionado.")
                return None
            return _snip

        _model_ind = ollama_model if 'ollama_model' in locals() and ollama_model else "llama3"

        # ── Linha 1: Título + Headline ─────────────────────────────────────────
        col_t1, col_t2 = st.columns([1.4, 1.0])
        with col_t1:
            col_t1_field, col_t1_btn = st.columns([5, 1])
            with col_t1_field:
                cut_title_val = st.text_input(
                    f"🏷️ Título do Corte (YouTube/Redes) {badge_title}:",
                    value=st.session_state.get("input_cut_title", "Corte Selecionado"),
                    key="input_cut_title"
                )
            with col_t1_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✨", key="btn_regen_title", use_container_width=True, help="Regerar Título com IA"):
                    _snip = _get_snippet_for_regen()
                    if _snip:
                        with st.spinner("Gerando título..."):
                            import core.analyzer
                            _r = core.analyzer.generate_title_individual(_snip, model=_model_ind, user_guidance=user_guidance_val)
                        st.session_state["_pending_cut_title"] = _r.get("titulo_principal", st.session_state.get("input_cut_title", ""))
                        st.session_state["_pending_alt_titles"] = _r.get("titulos_alternativos", [])
                        st.rerun()
        with col_t2:
            col_t2_field, col_t2_btn = st.columns([5, 1])
            with col_t2_field:
                cut_headline_val = st.text_input(
                    f"📌 Headline de Topo 9:16 (Curta) {badge_title}:",
                    value=st.session_state.get("input_cut_headline", st.session_state.get("input_cut_title", "Corte Selecionado")),
                    key="input_cut_headline",
                    help="Frase de gancho curta e completa (máx 35-40 caracteres) fixada na caixa magnética no topo do vídeo."
                )
            with col_t2_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✨", key="btn_regen_headline", use_container_width=True, help="Regerar Headline com IA"):
                    _snip = _get_snippet_for_regen()
                    if _snip:
                        with st.spinner("Gerando headline..."):
                            import core.analyzer
                            _r = core.analyzer.generate_headline_individual(_snip, model=_model_ind, user_guidance=user_guidance_val)
                        st.session_state["_pending_cut_headline"] = _r.get("headline_topo", st.session_state.get("input_cut_headline", ""))
                        st.rerun()

        # Prévia do nome da pasta e do arquivo de vídeo gerados
        _preview_folder = build_cut_folder_name(selected_aspect, cut_title_val, start_time_str=start_time, end_time_str=end_time)
        st.caption(f"📁 **Pasta da Instância ({selected_aspect}):** `data/{_vid_id_cat}/{_preview_folder}/`  |  🎬 **Vídeo:** `{_preview_folder}.mp4`")

        # Se houver títulos alternativos sugeridos pela IA, exibe botões rápidos de troca
        alt_titles = st.session_state.get("meta_alt_titles", [])
        if alt_titles:
            st.markdown("💡 **Variações de Título Sugeridas pela IA (Clique para aplicar):**")
            col_alts = st.columns(len(alt_titles))
            for idx_alt, alt_t in enumerate(alt_titles):
                with col_alts[idx_alt]:
                    if st.button(f"📌 {alt_t}", key=f"btn_alt_title_{idx_alt}", use_container_width=True):
                        st.session_state["input_cut_title"] = alt_t
                        st.rerun()

        # ── Linha 2: Descrição + (Hashtags + Tags SEO) ────────────────────────
        col_desc, col_tags = st.columns([1.5, 1])
        with col_desc:
            col_d_field, col_d_btn = st.columns([8, 1])
            with col_d_field:
                cut_desc_val = st.text_area(
                    f"📝 Descrição / Legenda {badge_desc}:",
                    value=st.session_state.get("input_cut_desc", "Confira a declaração e participe do debate nos comentários!"),
                    height=110,
                    key="input_cut_desc"
                )
            with col_d_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✨", key="btn_regen_desc", use_container_width=True, help="Regerar Descrição com IA"):
                    _snip = _get_snippet_for_regen()
                    if _snip:
                        with st.spinner("Gerando descrição..."):
                            import core.analyzer
                            _r = core.analyzer.generate_description_individual(_snip, model=_model_ind, user_guidance=user_guidance_val)
                        st.session_state["_pending_cut_desc"] = _r.get("descricao", st.session_state.get("input_cut_desc", ""))
                        st.rerun()
        with col_tags:
            col_h_field, col_h_btn = st.columns([5, 1])
            with col_h_field:
                cut_hashtags_val = st.text_input(
                    f"🏷️ Hashtags {badge_tags}:",
                    value=st.session_state.get("input_cut_hashtags", "#shorts #viral #cortes #reels"),
                    key="input_cut_hashtags"
                )
            with col_h_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✨", key="btn_regen_hashtags", use_container_width=True, help="Regerar Hashtags com IA"):
                    _snip = _get_snippet_for_regen()
                    if _snip:
                        with st.spinner("Gerando hashtags..."):
                            import core.analyzer
                            _r = core.analyzer.generate_hashtags_individual(_snip, model=_model_ind, user_guidance=user_guidance_val)
                        st.session_state["_pending_cut_hashtags"] = " ".join(_r.get("hashtags", []))
                        st.rerun()
            col_s_field, col_s_btn = st.columns([5, 1])
            with col_s_field:
                cut_tags_seo_val = st.text_input(
                    f"🔍 Tags SEO {badge_tags}:",
                    value=st.session_state.get("input_cut_tags_seo", "cortes, viral, shorts, podcast, debate"),
                    key="input_cut_tags_seo"
                )
            with col_s_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✨", key="btn_regen_tags_seo", use_container_width=True, help="Regerar Tags SEO com IA"):
                    _snip = _get_snippet_for_regen()
                    if _snip:
                        with st.spinner("Gerando tags SEO..."):
                            import core.analyzer
                            _r = core.analyzer.generate_tags_seo_individual(_snip, model=_model_ind, user_guidance=user_guidance_val)
                        st.session_state["_pending_cut_tags_seo"] = _r.get("tags_seo", st.session_state.get("input_cut_tags_seo", ""))
                        st.rerun()

        # Ações Rápidas Independentes (Não exigem re-renderização de vídeo)
        col_act_txt, col_act_th = st.columns(2)
        with col_act_txt:
            if existing_cut:
                if st.button("💾 Atualizar Apenas Textos (Sem Renderizar Vídeo)", use_container_width=True):
                    _meta_file_quick = os.path.join("data", _vid_id_cat, "metadata.json")
                    orig_info_quick = {}
                    if os.path.exists(_meta_file_quick):
                        try:
                            with open(_meta_file_quick, "r", encoding="utf-8") as _mfq:
                                orig_info_quick = json.load(_mfq)
                        except Exception:
                            pass
                    update_res = update_cut_texts_only(
                        video_id=_vid_id_cat,
                        start_time=start_time,
                        end_time=end_time,
                        title=cut_title_val,
                        description=cut_desc_val,
                        hashtags=cut_hashtags_val.split(),
                        tags_seo=cut_tags_seo_val,
                        orig_video_info=orig_info_quick
                    )
                    st.success("✅ Textos atualizados no disco!")

        with col_act_th:
            if start_time and end_time:
                if st.button("🖼️ Gerar / Recriar Capas Agora (Sem Renderizar Vídeo)", type="secondary", use_container_width=True):
                    active_u_th = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
                    v_id_th = get_video_id(active_u_th)
                    if v_id_th:
                        v_full_th = os.path.join("data", v_id_th, "video_full.mp4")
                        if not os.path.exists(v_full_th):
                            st.warning("O vídeo original precisa estar baixado na Seção 1 para extrair os frames em alta resolução.")
                        else:
                            with st.spinner("Extraindo frame, aplicando Rembg e gerando 3 variações de capa..."):
                                f_dest_dir = existing_inst.get("folder_path") if existing_inst else os.path.join("data", v_id_th, f"temp_thumbs_{selected_aspect.replace(':', '-')}")
                                os.makedirs(f_dest_dir, exist_ok=True)
                                target_thumb_path = os.path.join(f_dest_dir, "thumbnail.jpg")

                                th_standalone_res = create_cut_thumbnail(
                                    source_video_or_frame=v_full_th,
                                    headline_text=cut_headline_val,
                                    output_path=target_thumb_path,
                                    start_time_str=start_time,
                                    end_time_str=end_time,
                                    preset=headline_preset,
                                    custom_text_color=headline_text_color,
                                    custom_bg_color=headline_bg_color,
                                    aspect_mode=selected_aspect
                                )
                                if th_standalone_res.get("error"):
                                    st.error(f"Erro ao gerar capas: {th_standalone_res['error']}")
                                else:
                                    if existing_inst:
                                        update_cut_thumbnail_in_catalog(
                                            video_id=v_id_th,
                                            start_time=start_time,
                                            end_time=end_time,
                                            aspect_mode=selected_aspect,
                                            thumbnail_path=target_thumb_path,
                                            variations=th_standalone_res.get("variations", [])
                                        )
                                    st.success("🎉 3 Variações de Capa geradas com sucesso!")
                                    st.rerun()

    # Exibição imediata da instância existente do cache se já renderizada
    if existing_inst and os.path.exists(existing_inst.get("video_path", "")):
        st.markdown(f"#### 🎬 Prévia da Instância Pronta ({aspect_option})")
        
        cached_thumb = existing_inst.get("thumbnail_path") or os.path.join(existing_inst.get("folder_path", ""), "thumbnail.jpg")
        has_cached_thumb = cached_thumb and os.path.exists(cached_thumb)

        if "9:16" in selected_aspect:
            if has_cached_thumb:
                col_pv1, col_pv2, col_pv3, col_pv4 = st.columns([1.0, 1.2, 1.2, 1.0])
                with col_pv2:
                    st.caption("🎬 **Vídeo Renderizado:**")
                    safe_display_video(existing_inst["video_path"])
                with col_pv3:
                    st.caption("🖼️ **Capa / Thumbnail Principal:**")
                    safe_display_image(cached_thumb, use_container_width=True)
            else:
                col_pv1, col_pv2, col_pv3 = st.columns([1.6, 1.2, 1.6])
                with col_pv2:
                    safe_display_video(existing_inst["video_path"])
        else:
            if has_cached_thumb:
                col_pv1, col_pv2 = st.columns(2)
                with col_pv1:
                    st.caption("🎬 **Vídeo 16:9 Full HD:**")
                    safe_display_video(existing_inst["video_path"])
                with col_pv2:
                    st.caption("🖼️ **Capa / Thumbnail Principal (16:9):**")
                    safe_display_image(cached_thumb, use_container_width=True)
            else:
                col_pv1, col_pv2, col_pv3 = st.columns([1, 2, 1])
                with col_pv2:
                    safe_display_video(existing_inst["video_path"])

        # Variações de Capa Disponíveis
        f_dir = existing_inst.get("folder_path", "")
        var_list = []
        for v_i, v_name in [(1, "⚡ Impacto Neon (Glow)"), (2, "✨ Clean Focus (Sombra 3D)"), (3, "🎬 Moldura Dinâmica (HDR)")]:
            v_p = os.path.join(f_dir, f"thumbnail_{v_i}.jpg")
            if os.path.exists(v_p):
                var_list.append((v_i, v_name, v_p))

        if len(var_list) > 1:
            with st.expander("🖼️ Variações de Capa / Thumbnail Disponíveis (Escolha sua preferida)", expanded=False):
                st.caption("Clique em **⭐ Ativar como Principal** para trocar a capa oficial do corte:")
                v_cols = st.columns(len(var_list))
                active_var = existing_inst.get("active_variation", 1)
                for v_idx_col, (v_i, v_name, v_p) in enumerate(var_list):
                    with v_cols[v_idx_col]:
                        is_active = (v_i == active_var)
                        st.markdown(f"**{v_name}**" + (" ⭐ *(Ativa)*" if is_active else ""))
                        safe_display_image(v_p, use_container_width=True)
                        col_bt1, col_bt2 = st.columns(2)
                        with col_bt1:
                            if not is_active:
                                if st.button("⭐ Ativar", key=f"btn_set_var_cached_{v_i}", use_container_width=True):
                                    set_active_thumbnail_variation(_vid_id_cat, start_time, end_time, selected_aspect, v_i)
                                    st.success(f"Capa {v_i} definida como principal!")
                                    st.rerun()
                            else:
                                st.button("✅ Ativa", disabled=True, key=f"btn_active_cached_{v_i}", use_container_width=True)
                        with col_bt2:
                            with open(v_p, "rb") as vf_var:
                                st.download_button(
                                    label="⬇️ JPG",
                                    data=vf_var,
                                    file_name=f"thumbnail_{v_i}.jpg",
                                    mime="image/jpeg",
                                    key=f"btn_dl_var_cached_{v_i}",
                                    use_container_width=True
                                )

        col_dl1, col_dl_fol, col_dl2 = st.columns([1.5, 1.2, 1.2] if has_cached_thumb else [1.5, 1.2, 0.001])
        with col_dl1:
            with open(existing_inst["video_path"], "rb") as vf_cached:
                st.download_button(
                    label=f"💾 Baixar Vídeo ({existing_inst['video_filename']})",
                    data=vf_cached,
                    file_name=existing_inst["video_filename"],
                    mime="video/mp4",
                    type="primary",
                    use_container_width=True,
                    key="btn_dl_cached_instance"
                )
        with col_dl_fol:
            if st.button("📂 Abrir Pasta", key="btn_open_fol_cached", use_container_width=True, help="Abre a pasta deste corte no Explorador de Arquivos do Windows"):
                open_in_file_explorer(existing_inst.get("folder_path") or existing_inst.get("video_path"))
        if has_cached_thumb:
            with col_dl2:
                with open(cached_thumb, "rb") as tf_cached:
                    st.download_button(
                        label="🖼️ Baixar Thumbnail (JPG)",
                        data=tf_cached,
                        file_name="thumbnail.jpg",
                        mime="image/jpeg",
                        type="secondary",
                        use_container_width=True,
                        key="btn_dl_cached_thumb"
                    )

        # Áudio Isolado do Corte (MP3)
        cut_audio_file = None
        if f_dir and os.path.exists(f_dir):
            for _f in os.listdir(f_dir):
                if _f.endswith(".mp3"):
                    cut_audio_file = os.path.join(f_dir, _f)
                    break
        if not cut_audio_file and existing_inst.get("video_path") and os.path.exists(existing_inst["video_path"]):
            cut_audio_file = os.path.splitext(existing_inst["video_path"])[0] + ".mp3"
            if not os.path.exists(cut_audio_file):
                try:
                    extract_audio_from_local_video(existing_inst["video_path"], cut_audio_file)
                except Exception:
                    pass

        if cut_audio_file and os.path.exists(cut_audio_file) and os.path.getsize(cut_audio_file) > 0:
            col_ca_p1, col_ca_p2 = st.columns([2, 1])
            with col_ca_p1:
                with open(cut_audio_file, "rb") as af_cut:
                    st.audio(af_cut.read(), format="audio/mp3")
            with col_ca_p2:
                with open(cut_audio_file, "rb") as af_cut:
                    st.download_button(
                        label=f"🎵 Baixar Áudio do Corte (MP3)",
                        data=af_cut.read(),
                        file_name=os.path.basename(cut_audio_file),
                        mime="audio/mp3",
                        use_container_width=True,
                        key="btn_dl_cut_audio_inst"
                    )
        
        abs_fol_c = os.path.abspath(existing_inst.get("folder_path", ""))
        link_fol_c = abs_fol_c.replace('\\', '/')
        st.markdown(f"📁 **Pasta Local:** [{existing_inst.get('folder_name', 'Abrir Pasta')}](file:///{link_fol_c}) &nbsp; `📁 {abs_fol_c}`", unsafe_allow_html=True)
        render_quick_editor_component(existing_inst["video_path"], f"cached_{_vid_id_cat}_{start_time}_{end_time}_{selected_aspect}")

    st.markdown("")
    render_button_label = "🔄 Forçar Re-renderização no Formato Escolhido" if existing_inst else "✂️ Gerar Corte no Formato Escolhido"
    if st.button(render_button_label, type="primary" if not existing_inst else "secondary", use_container_width=True):
        if not start_time or not end_time:
            st.warning("Preencha o tempo inicial e final.")
        else:
            import importlib
            import core.video_processor
            importlib.reload(core.video_processor)
            from core.video_processor import download_full_video, cut_video, get_video_resolution
            
            active_url = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
            video_id = get_video_id(active_url)
            
            if not video_id:
                st.error("URL do vídeo do YouTube não identificada. Por favor, confirme a URL na Seção 1.")
            else:
                data_dir = os.path.join("data", video_id)
                os.makedirs(data_dir, exist_ok=True)
                video_full_path = os.path.join(data_dir, "video_full.mp4")
                # Normaliza o aspect ratio para nome de arquivo temporário seguro
                safe_aspect_name = selected_aspect.replace(":", "-")
                corte_output_path = os.path.join(data_dir, f"corte_{safe_aspect_name}.mp4")
                
                # Detecta se o vídeo no cache é de baixa resolução (< 720p) e força o download em 1080p
                need_download = not os.path.exists(video_full_path)
                if os.path.exists(video_full_path):
                    current_res = get_video_resolution(video_full_path)
                    try:
                        h = int(current_res.split('x')[1])
                        if h < 720:
                            st.info(f"🔄 Cache antigo detectado em baixa resolução ({current_res}). Baixando automaticamente em 1080p Full HD...")
                            if os.path.exists(video_full_path):
                                os.remove(video_full_path)
                            need_download = True
                    except Exception:
                        pass

                if need_download:
                    with st.spinner("Baixando vídeo original na máxima resolução disponível (1080p Full HD)..."):
                        _meta_local = os.path.join(data_dir, "metadata.json")
                        _is_live_corte = False
                        if os.path.exists(_meta_local):
                            try:
                                with open(_meta_local, "r", encoding="utf-8") as _mf:
                                    _is_live_corte = bool(json.load(_mf).get("is_live"))
                            except Exception:
                                pass
                        video_res = download_full_video(active_url, video_full_path, is_live=_is_live_corte)
                else:
                    current_res = get_video_resolution(video_full_path)
                    st.success(f"Vídeo em alta qualidade encontrado no cache ({current_res})!")
                    video_res = {"path": video_full_path, "error": None}
                    
                if video_res.get("error"):
                    st.error(f"Erro ao baixar vídeo: {video_res['error']}")
                else:
                    extra_info = ""
                    if selected_aspect == "16:9" and horizontal_zoom_val > 1.00:
                        extra_info = f" (Zoom: {horizontal_zoom_val:.2f}x)"
                    elif selected_aspect == "9:16_blur":
                        extra_info = f" (Zoom: {blur_zoom_val:.2f}x)"
                    elif selected_aspect == "9:16_smart_face" and face_zoom_active:
                        extra_info = f" (Auto-Zoom Inteligente)"
                    elif selected_aspect == "9:16_split":
                        extra_info = f" (Split Screen + Auto-Switch)" if split_auto_switch else " (Split Screen Fixo)"
                    if subtitle_enabled:
                        extra_info += " + 📝 Legendas"
                    if headline_enabled:
                        extra_info += " + 🏷️ Headline"
                    if bg_music_enabled:
                        extra_info += " + 🎵 Música/Ducking"

                    with st.spinner(f"Renderizando corte [{start_time} → {end_time}] no formato {aspect_option}{extra_info}..."):
                        _transcript_path_cut = os.path.join(data_dir, "transcript.json")
                        cut_res = cut_video(
                            video_res["path"],
                            start_time,
                            end_time,
                            corte_output_path,
                            aspect_ratio_mode=selected_aspect,
                            horizontal_zoom=horizontal_zoom_val,
                            blur_zoom=blur_zoom_val,
                            blur_pan=blur_pan_val,
                            blur_intensity=blur_int_val,
                            blur_auto_tracking=(mode_blur_ctrl == "🤖 Auto-Zoom Inteligente no Personagem (Recomendado)"),
                            face_auto_zoom=face_zoom_active,
                            face_margin_ratio=face_margin_val,
                            person_preference=person_pref_val,
                            split_top_pan=split_top_pan,
                            split_bottom_pan=split_bottom_pan,
                            split_zoom=split_zoom_val,
                            split_divider_color=split_div_color,
                            split_divider_width=split_div_w,
                            split_auto_switch=split_auto_switch,
                            split_source_type=split_source_type,
                            split_video_path=split_video_path,
                            split_image_paths=split_image_paths,
                            split_media_position=split_media_position,
                            split_blur_margin_pct=split_blur_margin_pct,
                            # Legendas Dinâmicas (Fase 2)
                            subtitle_enabled=subtitle_enabled,
                            subtitle_transcript_path=_transcript_path_cut,
                            subtitle_highlight_color=subtitle_highlight_color,
                            subtitle_base_color=subtitle_base_color,
                            subtitle_font_size=subtitle_font_size,
                            # Fase 3: Retenção & Áudio
                            headline_enabled=headline_enabled,
                            headline_text=cut_headline_val or cut_title_val or st.session_state.get("input_cut_headline") or st.session_state.get("input_cut_title", "Corte Selecionado"),
                            headline_preset=headline_preset,
                            headline_text_color=headline_text_color,
                            headline_bg_color=headline_bg_color,
                            headline_font_size=headline_font_size,
                            headline_margin_top=headline_margin_top,
                            emojis_enabled=emojis_enabled,
                            zoom_punch_enabled=zoom_punch_enabled,
                            bg_music_enabled=bg_music_enabled,
                            bg_music_track_path=bg_music_track_path,
                            bg_music_volume=bg_music_volume,
                            ducking_preset=ducking_preset,
                            # Fase 4: Retenção Dinâmica & Thumbnails
                            progress_bar_enabled=progress_bar_enabled,
                            progress_bar_color=progress_bar_color,
                            progress_bar_height=progress_bar_height,
                            callout_enabled=callout_enabled,
                            callout_text=callout_text,
                            callout_duration=callout_duration,
                            climax_zoom_enabled=climax_zoom_enabled,
                            climax_zoom_factor=climax_zoom_factor,
                            thumbnail_enabled=thumbnail_enabled,
                        )
                        if cut_res.get("error"):
                            st.error(f"Erro ao cortar: {cut_res['error']}")
                        else:
                            out_res = get_video_resolution(corte_output_path)
                            _sub_badge = " 📝 Legendas" if subtitle_enabled and not cut_res.get("subtitle_error") and not cut_res.get("subtitle_warning") else ""
                            _hl_badge = " 🏷️ Headline" if headline_enabled else ""
                            _mus_badge = " 🎵 Ducking" if bg_music_enabled else ""
                            _pb_badge = " ⏳ Barra" if progress_bar_enabled else ""
                            _cz_badge = " 🎯 Clímax" if climax_zoom_enabled else ""
                            _th_badge = " 🖼️ Thumbnail" if thumbnail_enabled and cut_res.get("thumbnail_path") else ""
                            st.success(f"🎉 Corte gerado com sucesso! Resolução: **{out_res}** | Formato: **{aspect_option}**{_sub_badge}{_hl_badge}{_mus_badge}{_pb_badge}{_cz_badge}{_th_badge}")
                            
                            # Avisos de legendas / áudio
                            if cut_res.get("subtitle_error"):
                                st.warning(f"⚠️ Legendas não aplicadas: {cut_res['subtitle_error']}")
                            elif cut_res.get("subtitle_warning"):
                                st.info(f"ℹ️ {cut_res['subtitle_warning']}")
                            if cut_res.get("audio_warning"):
                                st.info(f"ℹ️ {cut_res['audio_warning']}")
                            
                            gen_thumb_path = cut_res.get("thumbnail_path")
                            has_gen_thumb = gen_thumb_path and os.path.exists(gen_thumb_path)

                            if "9:16" in selected_aspect:
                                if has_gen_thumb:
                                    col_v1, col_v2, col_v3, col_v4 = st.columns([1.0, 1.2, 1.2, 1.0])
                                    with col_v2:
                                        st.caption("🎬 **Vídeo Renderizado:**")
                                        safe_display_video(corte_output_path)
                                    with col_v3:
                                        st.caption("🖼️ **Capa / Thumbnail Principal:**")
                                        safe_display_image(gen_thumb_path, use_container_width=True)
                                else:
                                    col_v1, col_v2, col_v3 = st.columns([1.6, 1.2, 1.6])
                                    with col_v2:
                                        safe_display_video(corte_output_path)
                            else:
                                if has_gen_thumb:
                                    col_v1, col_v2 = st.columns(2)
                                    with col_v1:
                                        st.caption("🎬 **Vídeo 16:9 Full HD:**")
                                        safe_display_video(corte_output_path)
                                    with col_v2:
                                        st.caption("🖼️ **Capa / Thumbnail Principal (16:9):**")
                                        safe_display_image(gen_thumb_path, use_container_width=True)
                                else:
                                    col_v1, col_v2, col_v3 = st.columns([1, 2, 1])
                                    with col_v2:
                                        safe_display_video(corte_output_path)
                            
                            # Carrega metadados do vídeo original
                            _meta_file = os.path.join(data_dir, "metadata.json")
                            orig_info = {}
                            if os.path.exists(_meta_file):
                                try:
                                    with open(_meta_file, "r", encoding="utf-8") as _mf:
                                        orig_info = json.load(_mf)
                                except Exception:
                                    pass
                            if not orig_info:
                                orig_info = {
                                    "title": f"Vídeo {video_id}",
                                    "channel": "Canal Oficial",
                                    "upload_date": "N/D",
                                    "url": active_url
                                }

                            # Criação da Pasta Estruturada do Corte (incluindo legendas .SRT e thumbnails)
                            import core.export_kit
                            package_res = core.export_kit.create_viral_package(
                                video_path=corte_output_path,
                                title=cut_title_val,
                                description=cut_desc_val,
                                hashtags=cut_hashtags_val.split(),
                                tags_seo=cut_tags_seo_val,
                                aspect_mode=selected_aspect,
                                output_base_dir=data_dir,
                                orig_video_info=orig_info,
                                thumbnail_path=gen_thumb_path,
                                transcript_path=_transcript_path_cut,
                                start_time_str=start_time,
                                end_time_str=end_time
                            )

                            # Registra no Catálogo de Cortes
                            register_cut_instance(
                                video_id=video_id,
                                start_time=start_time,
                                end_time=end_time,
                                title=cut_title_val,
                                description=cut_desc_val,
                                hashtags=cut_hashtags_val.split(),
                                tags_seo=cut_tags_seo_val,
                                aspect_mode=selected_aspect,
                                folder_name=package_res["folder_name"],
                                folder_path=package_res["package_dir"],
                                video_path=package_res["video_dest_path"],
                                resolution=out_res,
                                thumbnail_path=package_res.get("thumbnail_dest_path")
                            )

                            # Botões de Ação do Corte Renderizado
                            saved_thumb = package_res.get("thumbnail_dest_path")
                            has_saved_thumb = saved_thumb and os.path.exists(saved_thumb)

                            if has_saved_thumb:
                                col_b1, col_b_fol, col_b_th, col_b2, col_b3 = st.columns([1.5, 1.2, 1.2, 1.2, 1.2])
                            else:
                                col_b1, col_b_fol, col_b2, col_b3 = st.columns([1.5, 1.2, 1.2, 1.2])

                            with col_b1:
                                with open(package_res["video_dest_path"], "rb") as vf:
                                    st.download_button(
                                        label=f"💾 Baixar Vídeo ({package_res['video_filename']})",
                                        data=vf,
                                        file_name=package_res["video_filename"],
                                        mime="video/mp4",
                                        type="primary",
                                        use_container_width=True
                                    )

                            with col_b_fol:
                                if st.button("📂 Abrir Pasta", key="btn_open_fol_rendered", use_container_width=True, help="Abre a pasta deste corte no Explorador de Arquivos do Windows"):
                                    open_in_file_explorer(package_res.get("package_dir"))

                            if has_saved_thumb:
                                with col_b_th:
                                    with open(saved_thumb, "rb") as tf_btn:
                                        st.download_button(
                                            label="🖼️ Baixar Thumbnail",
                                            data=tf_btn,
                                            file_name="thumbnail.jpg",
                                            mime="image/jpeg",
                                            type="secondary",
                                            use_container_width=True
                                        )
                            with col_b2:
                                with st.popover("🔴 Publicar no Shorts", use_container_width=True):
                                    st.markdown("##### 🚀 Enviar para o YouTube Shorts")
                                    yt_priv = st.selectbox(
                                        "Privacidade:",
                                        ["unlisted", "private", "public"],
                                        format_func=lambda x: {"unlisted": "🔗 Não Listado (Recomendado)", "private": "🔒 Privado / Rascunho", "public": "🌍 Público"}[x],
                                        key="yt_priv_single"
                                    )
                                    if st.button("Confirmar Upload", key="btn_conf_yt_single", type="primary", use_container_width=True):
                                        with st.spinner("Enviando vídeo para o canal do YouTube..."):
                                            yt_res = upload_to_youtube_shorts(
                                                video_path=package_res["video_dest_path"],
                                                title=cut_title_val,
                                                description=cut_desc_val,
                                                tags=cut_hashtags_val.split(),
                                                privacy_status=yt_priv,
                                                client_secrets_path=_cfg.get("youtube_client_secrets_path")
                                            )
                                            if yt_res.get("success"):
                                                st.success(f"🎉 Publicado com sucesso! [Ver no Shorts]({yt_res.get('url')})")
                                            else:
                                                st.error(f"Erro no upload: {yt_res.get('error')}")
                            with col_b3:
                                if st.button("📡 Disparar Webhook", key="btn_send_wh_single", use_container_width=True, help="Envia o pacote com vídeo e metadados para seu webhook configurado (n8n, Make, Zapier)"):
                                    wh_url = _cfg.get("webhook_url", "")
                                    if not wh_url:
                                        st.warning("Configure a URL do Webhook na barra lateral primeiro.")
                                    else:
                                        with st.spinner("Despachando para o Webhook..."):
                                            wh_payload = {
                                                "event": "cut_ready",
                                                "video_id": video_id,
                                                "title": cut_title_val,
                                                "description": cut_desc_val,
                                                "hashtags": cut_hashtags_val.split(),
                                                "tags_seo": cut_tags_seo_val,
                                                "start_time": start_time,
                                                "end_time": end_time,
                                                "aspect_mode": selected_aspect,
                                                "video_path": package_res["video_dest_path"],
                                                "video_filename": package_res["video_filename"],
                                                "folder_path": package_res["package_dir"],
                                                "original_video": orig_info
                                            }
                                            wh_res = send_to_webhook(wh_url, wh_payload, auth_header=_cfg.get("webhook_auth_header", ""))
                                            if wh_res.get("success"):
                                                st.success(f"✅ Webhook acionado! HTTP {wh_res.get('status_code')}")
                                            else:
                                                st.error(f"Falha no webhook: {wh_res.get('error')}")

                            # Ferramenta de Edição Rápida / Ajuste Fino
                            render_quick_editor_component(package_res["video_dest_path"], f"newly_rendered_{video_id}_{start_time}_{end_time}_{selected_aspect}")

                            abs_pkg_p = os.path.abspath(package_res['package_dir'])
                            link_pkg_p = abs_pkg_p.replace('\\', '/')
                            with st.expander(f"📁 Pasta de Publicação Criada em: {package_res['folder_name']}", expanded=True):
                                st.markdown(f"📂 **Caminho da Pasta:** [{package_res['folder_name']}](file:///{link_pkg_p}) &nbsp; `📁 {abs_pkg_p}`", unsafe_allow_html=True)
                                st.markdown(f"**🎬 Arquivo de Vídeo:** `{package_res['video_filename']}`")
                                if package_res.get("subtitle_srt_path"):
                                    st.markdown(f"**📝 Legenda (.SRT):** `{os.path.basename(package_res['subtitle_srt_path'])}` &nbsp; | &nbsp; **📄 Transcrição de Fala (.TXT):** `transcricao_corte.txt`")
                                st.markdown(f"**📌 Título:** `{cut_title_val}`")
                                st.markdown(f"**📝 Legenda para Redes:**\n```\n{cut_desc_val}\n```")
                                st.markdown(f"**🏷️ Hashtags:** `{cut_hashtags_val}`")
                                st.markdown(f"**🔍 Tags SEO:** `{cut_tags_seo_val}`")
                                st.divider()
                                st.markdown("##### 📺 Dados do Vídeo Original Salvos no `info_publicacao.txt`:")
                                st.markdown(f"• **Título Original:** {orig_info.get('title')}\n• **Canal:** {orig_info.get('channel')}\n• **Lançamento:** {orig_info.get('upload_date')}\n• **Link:** {orig_info.get('url')}")


    # ─────────────────────────────────────────────────────────────────
    # SEÇÃO 4: GALERIA DE CORTES PRODUZIDOS
    # ─────────────────────────────────────────────────────────────────
    _active_u_gal = video_url or st.session_state.get("video_url") or st.session_state.get("input_yt_url") or ""
    _vid_id_gal = get_video_id(_active_u_gal) or ""

    if _vid_id_gal:
        st.markdown("---")
        st.header("4. 🎬 Galeria de Cortes Produzidos")
        st.markdown("Visualize, reproduza e baixe todos os cortes finalizados para este vídeo.")

        catalog_gal = load_cuts_catalog(_vid_id_gal)
        if not catalog_gal:
            st.info("Nenhum corte registrado nesta galeria ainda. Gere cortes individuais na **Seção 3** ou use a **Renderização em Lote** na **Seção 2**!")
        else:
            st.caption(f"📁 Total de **{len(catalog_gal)}** minutagens e instâncias registradas no catálogo.")
            for c_idx, (t_key, cut_item) in enumerate(catalog_gal.items()):
                with st.container():
                    # Cabeçalho do corte
                    st.subheader(f"📌 {cut_item.get('title', 'Corte sem título')}")
                    st.markdown(f"⏱️ Trecho: `[{cut_item.get('start_time')} → {cut_item.get('end_time')}]` • Atualizado em: `{cut_item.get('updated_at', 'N/D')}`")
                    
                    # Instâncias de formatos renderizadas para esta minutagem
                    formats_dict = cut_item.get("formats", {})
                    if formats_dict:
                        num_fmt = len(formats_dict)
                        if num_fmt == 1:
                            f_cols = st.columns([1.3, 2.7])
                        elif num_fmt == 2:
                            f_cols = st.columns([1.3, 1.3, 1.4])
                        elif num_fmt == 3:
                            f_cols = st.columns([1.1, 1.1, 1.1, 0.7])
                        else:
                            f_cols = st.columns(num_fmt)

                        for f_idx, (fmt_key, fmt_data) in enumerate(formats_dict.items()):
                            with f_cols[f_idx]:
                                fmt_badge = {
                                    "9:16_smart_face": "📱 9:16 Smart Face (VRIRA)",
                                    "9:16_split": "📱 9:16 Split Screen (VLDSS)",
                                    "9:16_blur": "📱 9:16 Blur (VFDBS)",
                                    "9:16_crop": "📱 9:16 Crop (VCCFT)",
                                    "16:9": "💻 16:9 Original (HOFHD)"
                                }.get(fmt_key, fmt_key)
                                
                                st.markdown(f"**{fmt_badge}**")
                                v_file = fmt_data.get("video_path")
                                g_thumb = fmt_data.get("thumbnail_path") or os.path.join(fmt_data.get("folder_path", ""), "thumbnail.jpg")
                                has_g_thumb = g_thumb and os.path.exists(g_thumb)

                                if v_file and os.path.exists(v_file):
                                    safe_display_video(v_file)
                                    
                                    if has_g_thumb:
                                        g_folder = fmt_data.get("folder_path", "")
                                        g_var_list = []
                                        for v_i, v_name in [(1, "⚡ Impacto Neon (Glow)"), (2, "✨ Clean Focus (Sombra 3D)"), (3, "🎬 Moldura Dinâmica (HDR)")]:
                                            v_p = os.path.join(g_folder, f"thumbnail_{v_i}.jpg")
                                            if os.path.exists(v_p):
                                                g_var_list.append((v_i, v_name, v_p))

                                        with st.expander(f"🖼️ Visualizar Capa / Thumbnail ({'16:9' if fmt_key == '16:9' else '9:16'})", expanded=False):
                                            safe_display_image(g_thumb, caption="Capa Principal Ativa", use_container_width=True)
                                            if len(g_var_list) > 1:
                                                st.markdown("##### 🎨 Variações de Capa:")
                                                g_vcols = st.columns(len(g_var_list))
                                                active_g_var = fmt_data.get("active_variation", 1)
                                                for g_vi, (gv_id, gv_name, gv_path) in enumerate(g_var_list):
                                                    with g_vcols[g_vi]:
                                                        is_g_act = (gv_id == active_g_var)
                                                        st.caption(f"**{gv_name}**" + (" ⭐" if is_g_act else ""))
                                                        safe_display_image(gv_path, use_container_width=True)
                                                        col_g1, col_g2 = st.columns(2)
                                                        with col_g1:
                                                            if not is_g_act:
                                                                if st.button("⭐ Ativar", key=f"btn_set_gvar_{c_idx}_{f_idx}_{gv_id}", use_container_width=True):
                                                                    set_active_thumbnail_variation(_vid_id_gal, cut_item.get('start_time'), cut_item.get('end_time'), fmt_key, gv_id)
                                                                    st.success(f"Capa {gv_id} ativada!")
                                                                    st.rerun()
                                                            else:
                                                                st.button("✅", disabled=True, key=f"btn_act_gvar_{c_idx}_{f_idx}_{gv_id}", use_container_width=True)
                                                        with col_g2:
                                                            with open(gv_path, "rb") as tg_var:
                                                                st.download_button(
                                                                    label="⬇️",
                                                                    data=tg_var,
                                                                    file_name=f"thumbnail_{gv_id}.jpg",
                                                                    mime="image/jpeg",
                                                                    key=f"dl_gvar_{c_idx}_{f_idx}_{gv_id}",
                                                                    use_container_width=True
                                                                )
                                            else:
                                                with open(g_thumb, "rb") as tf_gal:
                                                    st.download_button(
                                                        label="💾 Baixar Thumbnail (JPG)",
                                                        data=tf_gal,
                                                        file_name="thumbnail.jpg",
                                                        mime="image/jpeg",
                                                        key=f"dl_thumb_gal_{c_idx}_{f_idx}",
                                                        use_container_width=True
                                                    )

                                            st.markdown("")
                                            if st.button("🔄 Recriar 3 Capas com IA (Sem Renderizar Vídeo)", key=f"btn_regen_gal_{c_idx}_{f_idx}", use_container_width=True):
                                                v_full_gal = os.path.join("data", _vid_id_gal, "video_full.mp4")
                                                if os.path.exists(v_full_gal):
                                                    with st.spinner("Recriando capas com Rembg e IA..."):
                                                        th_g_res = create_cut_thumbnail(
                                                            source_video_or_frame=v_full_gal,
                                                            headline_text=cut_item.get("title", ""),
                                                            output_path=g_thumb,
                                                            start_time_str=cut_item.get("start_time"),
                                                            end_time_str=cut_item.get("end_time"),
                                                            aspect_mode=fmt_key
                                                        )
                                                        if th_g_res.get("error"):
                                                            st.error(f"Erro ao recriar: {th_g_res['error']}")
                                                        else:
                                                            update_cut_thumbnail_in_catalog(
                                                                video_id=_vid_id_gal,
                                                                start_time=cut_item.get("start_time"),
                                                                end_time=cut_item.get("end_time"),
                                                                aspect_mode=fmt_key,
                                                                thumbnail_path=g_thumb,
                                                                variations=th_g_res.get("variations", [])
                                                            )
                                                            st.success("Capas recriadas com sucesso!")
                                                            st.rerun()
                                                else:
                                                    st.warning("Vídeo original não encontrado em data.")

                                    col_b_dl, col_b_fol, col_b_yt, col_b_wh, col_b_del = st.columns([1.5, 1.2, 1.0, 1.0, 0.6])
                                    with col_b_dl:
                                        with open(v_file, "rb") as vf_gal:
                                            st.download_button(
                                                label=f"💾 Baixar ({fmt_data.get('resolution', 'HD')})",
                                                data=vf_gal,
                                                file_name=fmt_data.get("video_filename", f"{fmt_key}.mp4"),
                                                mime="video/mp4",
                                                key=f"dl_gal_{c_idx}_{f_idx}",
                                                use_container_width=True
                                            )
                                    with col_b_fol:
                                        if st.button("📂 Abrir Pasta", key=f"btn_open_fol_gal_{c_idx}_{f_idx}", use_container_width=True, help="Abre a pasta deste corte no Explorador de Arquivos do Windows"):
                                            open_in_file_explorer(fmt_data.get("folder_path") or v_file)
                                    with col_b_yt:
                                        with st.popover("🔴 Shorts", use_container_width=True, help="Publicar no YouTube Shorts"):
                                            st.markdown(f"##### 🚀 Upload: {cut_item.get('title', 'Corte')[:30]}...")
                                            g_yt_priv = st.selectbox(
                                                "Privacidade:",
                                                ["unlisted", "private", "public"],
                                                format_func=lambda x: {"unlisted": "🔗 Não Listado", "private": "🔒 Privado", "public": "🌍 Público"}[x],
                                                key=f"yt_priv_gal_{c_idx}_{f_idx}"
                                            )
                                            if st.button("Enviar", key=f"btn_send_yt_gal_{c_idx}_{f_idx}", type="primary", use_container_width=True):
                                                with st.spinner("Enviando vídeo para o YouTube..."):
                                                    yt_res = upload_to_youtube_shorts(
                                                        video_path=v_file,
                                                        title=cut_item.get('title', 'Corte'),
                                                        description=cut_item.get('description', ''),
                                                        tags=cut_item.get('hashtags', []),
                                                        privacy_status=g_yt_priv,
                                                        client_secrets_path=_cfg.get("youtube_client_secrets_path")
                                                    )
                                                    if yt_res.get("success"):
                                                        st.success(f"🎉 Publicado! [Ver Shorts]({yt_res.get('url')})")
                                                    else:
                                                        st.error(f"Erro: {yt_res.get('error')}")
                                    with col_b_wh:
                                        if st.button("📡 Webhook", key=f"btn_wh_gal_{c_idx}_{f_idx}", use_container_width=True, help="Disparar para Webhook (n8n/Make)"):
                                            wh_url = _cfg.get("webhook_url", "")
                                            if not wh_url:
                                                st.warning("Configure o Webhook na barra lateral.")
                                            else:
                                                with st.spinner("Enviando..."):
                                                    wh_payload = {
                                                        "event": "cut_ready",
                                                        "video_id": _vid_id_gal,
                                                        "title": cut_item.get('title', 'Corte'),
                                                        "description": cut_item.get('description', ''),
                                                        "hashtags": cut_item.get('hashtags', []),
                                                        "tags_seo": cut_item.get('tags_seo', ''),
                                                        "start_time": cut_item.get('start_time'),
                                                        "end_time": cut_item.get('end_time'),
                                                        "aspect_mode": fmt_key,
                                                        "video_path": v_file,
                                                        "video_filename": fmt_data.get("video_filename"),
                                                        "folder_path": fmt_data.get("folder_path")
                                                    }
                                                    wh_res = send_to_webhook(wh_url, wh_payload, auth_header=_cfg.get("webhook_auth_header", ""))
                                                    if wh_res.get("success"):
                                                        st.success(f"✅ OK! HTTP {wh_res.get('status_code')}")
                                                    else:
                                                        st.error(f"Falha: {wh_res.get('error')}")
                                    with col_b_del:
                                        with st.popover("🗑️", use_container_width=True, help=f"Excluir este vídeo ({fmt_key})"):
                                            st.markdown(f"⚠️ **Excluir {fmt_badge}?**")
                                            del_fmt_choice = st.radio(
                                                "Opção de exclusão:",
                                                [
                                                    "🎬 Apenas este Vídeo (.mp4)\n*(Preserva textos e kit)*",
                                                    "💥 Pasta e Kit deste formato"
                                                ],
                                                key=f"rad_del_fmt_{c_idx}_{f_idx}"
                                            )
                                            if st.button("Confirmar", key=f"btn_cnf_fmt_del_{c_idx}_{f_idx}", type="primary", use_container_width=True):
                                                is_full = "Pasta e Kit" in del_fmt_choice
                                                delete_format_instance(_vid_id_gal, cut_item.get('start_time'), cut_item.get('end_time'), fmt_key, delete_publication_kit=is_full)
                                                st.success("Excluído com sucesso.")
                                                st.rerun()
                                    abs_fol_g = os.path.abspath(fmt_data.get("folder_path", ""))
                                    link_fol_g = abs_fol_g.replace('\\', '/')
                                    st.markdown(f"📁 **Pasta Local:** [{fmt_data.get('folder_name', 'Abrir Pasta')}](file:///{link_fol_g}) &nbsp; `📁 {abs_fol_g}`", unsafe_allow_html=True)
                                    render_quick_editor_component(v_file, f"gal_{_vid_id_gal}_{c_idx}_{f_idx}")
                                else:
                                    st.warning("Vídeo excluído / não encontrado.")
                                    if st.button("🗑️ Remover do Catálogo", key=f"btn_clean_fmt_{c_idx}_{f_idx}"):
                                        delete_format_instance(_vid_id_gal, cut_item.get('start_time'), cut_item.get('end_time'), fmt_key, delete_publication_kit=True)
                                        st.rerun()

                    with st.expander("📝 Visualizar Textos e Tags de Publicação"):
                        st.markdown(f"**Legenda:**\n```\n{cut_item.get('description', '')}\n```")
                        st.markdown(f"**Hashtags:** `{' '.join(cut_item.get('hashtags', []))}`")
                        st.markdown(f"**Tags SEO:** `{cut_item.get('tags_seo', '')}`")

                    st.divider()


