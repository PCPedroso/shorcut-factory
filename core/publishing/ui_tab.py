"""
core/publishing/ui_tab.py — Interface de Usuário para a Central de Publicação Multiplataforma.
Renderiza o painel de status das contas (YouTube, Instagram, TikTok, X, Kwai),
o gerenciador da fila de disparo (SQLite), validação pre-flight e formulário de agendamento.
"""

import os
import json
import datetime
import streamlit as st
from typing import Optional, Dict, Any, List

from core.publishing.base import (
    Platform,
    JobStatus,
    AdaptedCaption
)
from core.publishing.credentials import CredentialVault
from core.publishing.publish_queue import PublishQueue
from core.publishing.worker import PublishWorker
from core.publishing.media_preflight import MediaPreflight
from core.publishing.caption_adapter import CaptionAdapter
from core.publishing.platform_registry import PlatformRegistry
from core.ui_theme import render_section_header, render_status_badge

# Singleton para o worker em background
_BACKGROUND_WORKER: Optional[PublishWorker] = None


def get_or_start_worker() -> PublishWorker:
    """Garante que o worker de publicação em background esteja ativo."""
    global _BACKGROUND_WORKER
    if _BACKGROUND_WORKER is None or not _BACKGROUND_WORKER.is_running:
        _BACKGROUND_WORKER = PublishWorker(poll_interval_sec=4.0)
        _BACKGROUND_WORKER.start()
    return _BACKGROUND_WORKER


def render_publishing_tab(vault: Optional[CredentialVault] = None, queue: Optional[PublishQueue] = None):
    """
    Renderiza a Seção 5 completa: Central de Publicação Multiplataforma.
    """
    vault = vault or CredentialVault()
    queue = queue or PublishQueue()
    worker = get_or_start_worker()

    render_section_header("5", "Central de Publicação Multiplataforma", "Nativo & Seguro", "score")

    st.markdown("""
    Gerencie e publique seus cortes diretamente no **YouTube Shorts**, **Instagram Reels**, **TikTok**, **X (Twitter)** e **Kwai**
    com conformidade técnica (Preflight 9:16/H.264), agendamento nativo, enfileiramento resiliente e credenciais criptografadas via Windows DPAPI.
    """)

    # ── CARDS DE CONEXÃO DE CONTAS ──────────────────────────────────────────────
    st.subheader("🔑 Conexão e Autenticação de Contas")

    cols = st.columns(5)
    platforms_list = [Platform.YOUTUBE, Platform.INSTAGRAM, Platform.TIKTOK, Platform.X, Platform.KWAI]

    for idx, plat in enumerate(platforms_list):
        publisher = PlatformRegistry.get_publisher(plat, vault=vault)
        auth_status = publisher.get_auth_status() if publisher else None

        with cols[idx]:
            is_auth = auth_status.is_authenticated if auth_status else False
            status_icon = "🟢" if is_auth else "🔴"
            status_text = "Conectado" if is_auth else "Não Conectado"
            badge_var = "success" if is_auth else "warning"

            st.markdown(
                f"""
                <div style="background: rgba(255,255,255,0.04); border-radius: 10px; padding: 12px; border: 1px solid rgba(255,255,255,0.08); text-align: center;">
                    <div style="font-size: 1.8rem; margin-bottom: 4px;">{plat.icon}</div>
                    <div style="font-weight: 700; font-size: 0.95rem;">{plat.display_name}</div>
                    <div style="margin-top: 6px;">{render_status_badge(f"{status_icon} {status_text}", badge_var)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            with st.expander(f"Configurar {plat.display_name}", expanded=False):
                if plat == Platform.YOUTUBE:
                    _render_youtube_config(vault)
                elif plat == Platform.INSTAGRAM:
                    _render_instagram_config(vault)
                elif plat == Platform.TIKTOK:
                    _render_tiktok_config(vault)
                elif plat == Platform.X:
                    _render_x_config(vault)
                elif plat == Platform.KWAI:
                    st.info("O Kwai utiliza o fluxo de **Exportação Assistida Nativa** (Clipboard + Explorer + Web Uploader). Sempre ativo sem necessidade de chaves de API.")

    st.divider()

    # ── ABAS PRINCIPAIS: DISPARAR vs FILA ───────────────────────────────────────
    tab_dispatch, tab_queue, tab_settings = st.tabs([
        "🚀 Disparar / Agendar Publicação",
        "📋 Fila de Postagens & Histórico",
        "⚙️ Configurações & Worker"
    ])

    with tab_dispatch:
        _render_dispatch_panel(vault, queue)

    with tab_queue:
        _render_queue_panel(queue)

    with tab_settings:
        _render_settings_panel(worker, queue)


def _render_youtube_config(vault: CredentialVault):
    creds = vault.get_credential(Platform.YOUTUBE) or {}
    st.markdown("**YouTube Data API v3 (OAuth 2.0)**")
    client_secrets_file = st.text_input(
        "Caminho para client_secrets.json:",
        value="client_secrets.json",
        key="cfg_yt_secrets_path"
    )
    if st.button("Autenticar Canal YouTube", key="btn_auth_yt"):
        if not os.path.exists(client_secrets_file):
            st.error(f"Arquivo '{client_secrets_file}' não encontrado. Baixe as credenciais OAuth do Google Cloud Console.")
        else:
            publisher = PlatformRegistry.get_publisher(Platform.YOUTUBE, vault=vault)
            with st.spinner("Abrindo navegador para autorização do YouTube..."):
                res = publisher.authenticate_oauth(client_secrets_file)
                if res.get("success"):
                    st.success("Canal do YouTube autenticado com sucesso e salvo no cofre!")
                    st.rerun()
                else:
                    st.error(f"Erro na autenticação: {res.get('error')}")

    if creds.get("token"):
        st.caption("✅ Token OAuth presente no cofre seguro.")


def _render_instagram_config(vault: CredentialVault):
    creds = vault.get_credential(Platform.INSTAGRAM) or {}
    st.markdown("**Meta Graph API v20.0 (Reels)**")
    token = st.text_input("User/Page Access Token:", value=creds.get("access_token", ""), type="password", key="cfg_ig_token")
    ig_id = st.text_input("Instagram Account ID (ig_user_id):", value=creds.get("ig_user_id", ""), key="cfg_ig_id")
    user = st.text_input("Nome de Usuário (@):", value=creds.get("username", ""), key="cfg_ig_user")

    if st.button("Salvar Credenciais Instagram", key="btn_save_ig"):
        if token and ig_id:
            vault.save_credential(Platform.INSTAGRAM, {
                "access_token": token.strip(),
                "ig_user_id": ig_id.strip(),
                "username": user.strip()
            })
            st.success("Credenciais do Instagram salvas no cofre seguro!")
            st.rerun()
        else:
            st.warning("Preencha o Access Token e o ID da Conta.")


def _render_tiktok_config(vault: CredentialVault):
    creds = vault.get_credential(Platform.TIKTOK) or {}
    st.markdown("**TikTok Content Posting API v2**")
    token = st.text_input("Access Token:", value=creds.get("access_token", ""), type="password", key="cfg_tt_token")
    refresh = st.text_input("Refresh Token (opcional):", value=creds.get("refresh_token", ""), type="password", key="cfg_tt_refresh")
    open_id = st.text_input("Open ID / Creator ID:", value=creds.get("open_id", ""), key="cfg_tt_openid")
    name = st.text_input("Nome do Perfil (@):", value=creds.get("display_name", ""), key="cfg_tt_name")

    if st.button("Salvar Credenciais TikTok", key="btn_save_tt"):
        if token:
            vault.save_credential(Platform.TIKTOK, {
                "access_token": token.strip(),
                "refresh_token": refresh.strip(),
                "open_id": open_id.strip(),
                "display_name": name.strip()
            })
            st.success("Credenciais do TikTok salvas no cofre seguro!")
            st.rerun()
        else:
            st.warning("Informe pelo menos o Access Token.")


def _render_x_config(vault: CredentialVault):
    creds = vault.get_credential(Platform.X) or {}
    st.markdown("**Publicação no X (antigo Twitter)**")
    
    current_mode = creds.get("mode", "api" if (creds.get("api_key") or creds.get("bearer_token")) else "assisted")
    chosen_mode = st.radio(
        "Modo de Operação no X:",
        [
            "📋 Modo Manual Assistido (100% Gratuito - Clipboard + Web)",
            "🔑 API Automática (Requer plano Developer Portal / Chaves)"
        ],
        index=0 if current_mode == "assisted" else 1,
        key="cfg_x_chosen_mode"
    )

    if "Modo Manual Assistido" in chosen_mode:
        st.info("💡 **Sem custos de API**: O corte é validado, o tweet é copiado para sua Área de Transferência (Ctrl+V) e a página do X é aberta no navegador com o arquivo selecionado no Windows Explorer.")
        if st.button("Ativar Modo Manual Assistido no X", key="btn_save_x_assisted"):
            vault.save_credential(Platform.X, {"mode": "assisted"})
            st.success("Modo Manual Assistido ativo para o X!")
            st.rerun()
    else:
        method = st.radio("Método de Autenticação:", ["OAuth 1.0a (Recomendado para Vídeo)", "OAuth 2.0 Bearer Token"], horizontal=True, key="cfg_x_method")

        if "OAuth 1.0a" in method:
            api_key = st.text_input("API Key:", value=creds.get("api_key", ""), key="cfg_x_key")
            api_secret = st.text_input("API Secret:", value=creds.get("api_secret", ""), type="password", key="cfg_x_secret")
            acc_token = st.text_input("Access Token:", value=creds.get("access_token", ""), key="cfg_x_token")
            acc_secret = st.text_input("Access Token Secret:", value=creds.get("access_token_secret", ""), type="password", key="cfg_x_toksecret")
            screen_name = st.text_input("Screen Name (@perfil):", value=creds.get("screen_name", ""), key="cfg_x_name")

            if st.button("Salvar Chaves OAuth 1.0a X", key="btn_save_x1"):
                vault.save_credential(Platform.X, {
                    "mode": "api",
                    "api_key": api_key.strip(),
                    "api_secret": api_secret.strip(),
                    "access_token": acc_token.strip(),
                    "access_token_secret": acc_secret.strip(),
                    "screen_name": screen_name.strip()
                })
                st.success("Chaves do X salvas com sucesso!")
                st.rerun()
        else:
            bearer = st.text_input("Bearer Token:", value=creds.get("bearer_token", ""), type="password", key="cfg_x_bearer")
            screen_name = st.text_input("Screen Name (@perfil):", value=creds.get("screen_name", ""), key="cfg_x_bearer_name")
            if st.button("Salvar Bearer Token X", key="btn_save_xb"):
                vault.save_credential(Platform.X, {
                    "mode": "api",
                    "bearer_token": bearer.strip(),
                    "screen_name": screen_name.strip()
                })
                st.success("Bearer Token do X salvo!")
                st.rerun()


def _render_dispatch_panel(vault: CredentialVault, queue: PublishQueue):
    """Painel de seleção de corte, validação de pré-voo e despacho."""
    st.markdown("### 📤 Selecionar Corte e Plataformas de Destino")

    # Identifica cortes disponíveis no projeto ativo
    active_vid = st.session_state.get("active_video_id") or ""
    catalog_path = os.path.join("data", active_vid, "cuts_catalog.json") if active_vid else ""

    available_cuts = []
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
                available_cuts = cat_data.get("cuts", [])
        except Exception:
            available_cuts = []

    c1, c2 = st.columns([2, 1])

    with c1:
        if available_cuts:
            cut_options = [f"Corte #{c.get('index', i)}: {c.get('title', 'Sem Título')}" for i, c in enumerate(available_cuts)]
            selected_cut_idx = st.selectbox("Selecione um Corte do Catálogo:", range(len(cut_options)), format_func=lambda x: cut_options[x], key="pub_cut_select")
            chosen_cut = available_cuts[selected_cut_idx]
            chosen_video_path = chosen_cut.get("video_path") or chosen_cut.get("cropped_path")
            default_title = chosen_cut.get("title", "")
            default_desc = chosen_cut.get("description", "")
            default_tags = chosen_cut.get("hashtags", [])
            default_seo = chosen_cut.get("tags_seo", "")
        else:
            chosen_video_path = st.text_input("Caminho do Arquivo de Vídeo (MP4):", key="pub_manual_video_path")
            default_title = "Gancho Viral Incrível"
            default_desc = "Confira este momento imperdível!"
            default_tags = ["#viral", "#cortes", "#podcast"]
            default_seo = "cortes, viral, podcast"

    with c2:
        st.markdown("**Plataformas de Publicação:**")
        selected_platforms = []
        for p in [Platform.YOUTUBE, Platform.INSTAGRAM, Platform.TIKTOK, Platform.X, Platform.KWAI]:
            if st.checkbox(f"{p.icon} {p.display_name}", value=(p in [Platform.YOUTUBE, Platform.INSTAGRAM]), key=f"chk_pub_{p.value}"):
                selected_platforms.append(p)

    if not chosen_video_path or not os.path.exists(chosen_video_path):
        st.info("Selecione ou informe um arquivo de vídeo existente para visualizar a auditoria técnica de pré-voo.")
        return

    # ── AUDITORIA DE PRÉ-VOO TÉCNICO ───────────────────────────────────────────
    st.markdown("#### 🔍 Auditoria Técnica de Pré-Voo (Preflight)")
    pre_cols = st.columns(len(selected_platforms) if selected_platforms else 1)

    all_preflight_valid = True
    for p_idx, plat in enumerate(selected_platforms):
        with pre_cols[p_idx]:
            pref = MediaPreflight.validate_for_platform(chosen_video_path, plat)
            if not pref.is_valid:
                all_preflight_valid = False
                badge = render_status_badge("Incompatível", "warning")
            else:
                badge = render_status_badge("Aprovado ✓", "success")

            st.markdown(f"**{plat.icon} {plat.display_name}** {badge}", unsafe_allow_html=True)
            st.caption(f"{pref.width}x{pref.height} | {pref.duration_sec:.1f}s | {pref.video_codec}")

            if not pref.is_valid:
                for r in pref.reasons:
                    st.error(f"⚠️ {r}")

    # ── PREVIEW DE LEGENDAS ADAPTADAS POR PLATAFORMA ───────────────────────────
    st.markdown("#### 📝 Legendas Adaptadas Automaticamente")
    preview_tabs = st.tabs([f"{p.icon} {p.display_name}" for p in selected_platforms])

    adapted_captions_map: Dict[Platform, AdaptedCaption] = {}
    for p_idx, plat in enumerate(selected_platforms):
        with preview_tabs[p_idx]:
            adapted = CaptionAdapter.adapt(
                platform=plat,
                title=default_title,
                description=default_desc,
                hashtags=default_tags,
                tags_seo=default_seo
            )
            adapted_captions_map[plat] = adapted

            st.text_area(
                f"Legenda Final ({adapted.character_count}/{adapted.max_characters} caracteres):",
                value=adapted.full_text,
                height=120,
                key=f"txt_caption_preview_{plat.value}"
            )
            if adapted.warnings:
                for w in adapted.warnings:
                    st.caption(f"ℹ️ {w}")

    # ── AGENDAMENTO E DISPARO ──────────────────────────────────────────────────
    st.markdown("#### ⏱️ Modo de Disparo")
    d_mode = st.radio("Quando publicar?", ["Publicar Imediatamente (Na Fila)", "Agendar Horário Específico"], horizontal=True, key="pub_dispatch_mode")

    scheduled_dt_iso = None
    if "Agendar" in d_mode:
        s_col1, s_col2 = st.columns(2)
        with s_col1:
            sched_date = st.date_input("Data da Publicação:", value=datetime.date.today(), key="pub_sched_date")
        with s_col2:
            sched_time = st.time_input("Horário (UTC / Local):", value=datetime.datetime.now().time(), key="pub_sched_time")

        combined_dt = datetime.datetime.combine(sched_date, sched_time)
        scheduled_dt_iso = combined_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        st.caption(f"Será disparado em: `{scheduled_dt_iso}`")

    if st.button("🚀 Enfileirar para Publicação Multiplataforma", type="primary", use_container_width=True, key="btn_enqueue_multi"):
        if not selected_platforms:
            st.warning("Selecione pelo menos uma plataforma de destino.")
            return

        enqueued_count = 0
        for plat in selected_platforms:
            cap_data = adapted_captions_map.get(plat)
            payload = {
                "video_path": chosen_video_path,
                "caption_data": {
                    "title": cap_data.title if cap_data else default_title,
                    "description": cap_data.description if cap_data else default_desc,
                    "caption": cap_data.full_text if cap_data else default_desc,
                    "tags": cap_data.tags_seo if cap_data else [],
                    "hashtags": cap_data.hashtags if cap_data else default_tags
                },
                "options": {
                    "scheduled_at": scheduled_dt_iso
                }
            }

            job_res = queue.enqueue(
                cut_folder=chosen_video_path,
                platform=plat,
                cut_title=cap_data.title if cap_data else default_title,
                payload=payload,
                scheduled_at=scheduled_dt_iso
            )
            if job_res.get("success"):
                enqueued_count += 1

        st.success(f"🎉 {enqueued_count} postagem(ns) adicionada(s) à Fila com sucesso!")
        st.rerun()


def _render_queue_panel(queue: PublishQueue):
    """Exibe os itens da fila e histórico."""
    st.markdown("### 📋 Fila de Publicações Ativas e Histórico")

    c_refresh, _, c_clear = st.columns([1, 3, 1.5])
    with c_refresh:
        if st.button("🔄 Atualizar Fila", key="btn_refresh_queue"):
            st.rerun()

    jobs = queue.list_jobs(limit=50)
    if not jobs:
        st.info("Nenhuma postagem na fila de publicação no momento. Use a aba 'Disparar / Agendar' para criar tarefas.")
        return

    for job in jobs:
        j_id = job["id"]
        plat_str = job["platform"]
        status = job["status"]
        created = job["created_at"]
        sched = job.get("scheduled_at")
        ext_url = job.get("external_url")
        err = job.get("error_message")

        try:
            plat_enum = Platform(plat_str)
            icon = plat_enum.icon
            display = plat_enum.display_name
        except Exception:
            icon = "🌐"
            display = plat_str

        # Define badge variant
        if status == JobStatus.PUBLISHED.value:
            b_var = "success"
        elif status in [JobStatus.UPLOADING.value, JobStatus.PROCESSING.value]:
            b_var = "processing"
        elif status == JobStatus.FAILED.value:
            b_var = "warning"
        elif status == JobStatus.NEEDS_ACTION.value:
            b_var = "score"
        else:
            b_var = "neutral"

        col_info, col_act = st.columns([3.5, 1.5])
        with col_info:
            status_badge = render_status_badge(status.upper(), b_var)
            st.markdown(f"**{icon} {display}** {status_badge} — `ID: #{j_id}`", unsafe_allow_html=True)
            st.caption(f"📁 Vídeo: `{os.path.basename(job.get('cut_folder', ''))}` | Criado em: {created} | Agendado: {sched or 'Imediato'}")
            if ext_url:
                st.markdown(f"🔗 [Acessar Publicação Online]({ext_url})")
            if err:
                st.caption(f"⚠️ {err}")

        with col_act:
            if status in [JobStatus.QUEUED.value, JobStatus.FAILED.value, JobStatus.NEEDS_ACTION.value]:
                if st.button("Executar Agora", key=f"btn_run_{j_id}"):
                    queue.update_job_status(j_id, JobStatus.QUEUED, scheduled_at=None)
                    st.success("Priorizado!")
                    st.rerun()
                if st.button("Cancelar", key=f"btn_cancel_{j_id}"):
                    queue.cancel_job(j_id)
                    st.rerun()

        st.divider()


def _render_settings_panel(worker: PublishWorker, queue: PublishQueue):
    """Controles do Worker e métricas da fila."""
    st.markdown("### ⚙️ Status do Background Worker & Métricas")

    w_running = worker.is_running
    w_badge = render_status_badge("Ativo (Daemon)", "success") if w_running else render_status_badge("Parado", "warning")
    st.markdown(f"**Status do Processo em Segundo Plano:** {w_badge}", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if not w_running:
            if st.button("▶️ Iniciar Worker", key="btn_start_worker"):
                worker.start()
                st.rerun()
        else:
            if st.button("⏸️ Pausar Worker", key="btn_pause_worker"):
                worker.stop()
                st.rerun()

    with c2:
        all_jobs = queue.list_jobs(limit=200)
        total = len(all_jobs)
        pub_count = sum(1 for j in all_jobs if j["status"] == JobStatus.PUBLISHED.value)
        fail_count = sum(1 for j in all_jobs if j["status"] == JobStatus.FAILED.value)
        pend_count = sum(1 for j in all_jobs if j["status"] == JobStatus.QUEUED.value)

        st.metric("Total de Postagens", total)
        st.metric("Publicadas com Sucesso", pub_count)
        st.metric("Na Fila / Pendentes", pend_count)
