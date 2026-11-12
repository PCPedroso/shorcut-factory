"""
core/campaigns/ui_tab.py — Aba "6. 📊 Campanhas & Métricas" do ViralCut Studio.

Organização interna em 4 sub-abas (Decisão V2):
  1. 📋 Campanhas   : CRUD completo, selos de status e prazo, arquivamento, exclusão segura;
  2. 📌 Publicações : Origem "Corte do app" (com selo de licença 🟢/🔴 e ponte V3) ou "Post sem corte do app",
                     avisos sem bloqueio, filtros e exclusão com confirmação;
  3. 📈 Lançamentos : Lançamento em lote via st.data_editor + histórico detalhado por publicação;
  4. 💰 Resumo      : Cards por moeda com rótulos estimado/informado, tabelas analíticas com RPM real,
                     gráfico de barras por campanha, alertas (3 dias / 7 dias) e botões de download CSV (V4).
"""

from __future__ import annotations

import datetime
import os
from typing import Optional, List, Dict, Any

import pandas as pd
import streamlit as st

from .db import init_db
from .repo import CampaignRepo
from .money import (
    parse_money_cents,
    format_money_cents,
    format_date_br,
    is_campaign_expired,
    days_until_expiration,
    PLATFORM_LABELS,
    PLATFORM_ICONS,
    SUPPORTED_PLATFORMS,
)
from .licensing_bridge import apply_campaign_license, can_apply_campaign_license
from .export import export_posts_metrics_csv, export_campaigns_summary_csv
from core.library_manager import get_library
from core.cuts_catalog import _raw_load_cuts_catalog, get_effective_license_for_cut
from core.licensing import is_publishable


# ── Constantes de UI ──────────────────────────────────────────────────────────

_STATUS_LABELS = {"ativa": "✅ Ativa", "pausada": "⏸️ Pausada", "encerrada": "🔴 Encerrada"}
_STATUS_COLORS = {"ativa": "#22c55e", "pausada": "#f59e0b", "encerrada": "#ef4444"}
_CURRENCY_OPTIONS = {"BRL": "🇧🇷 BRL (Real)", "USD": "🇺🇸 USD (Dólar)"}


def _get_repo() -> CampaignRepo:
    init_db()
    return CampaignRepo()


def _is_cut_in_catalog(video_id: Optional[str], cut_key: Optional[str]) -> bool:
    """Verifica se o corte ainda existe no catálogo JSON do vídeo."""
    if not video_id or not cut_key:
        return False
    try:
        cat = _raw_load_cuts_catalog(video_id)
        return cut_key in cat
    except Exception:
        return False


def _status_badge(status: str) -> str:
    color = _STATUS_COLORS.get(status, "#6b7280")
    label = _STATUS_LABELS.get(status, status)
    return f'<span style="background:{color};color:#fff;border-radius:6px;padding:2px 8px;font-size:0.75rem;font-weight:600;">{label}</span>'


def _days_badge(ends_on: Optional[str]) -> str:
    if not ends_on:
        return ""
    days = days_until_expiration(ends_on)
    if days is None:
        return ""
    if days < 0:
        color, text = "#ef4444", f"Vencida há {abs(days)}d"
    elif days == 0:
        color, text = "#f59e0b", "Vence hoje"
    elif days <= 3:
        color, text = "#f59e0b", f"Vence em {days}d"
    else:
        color, text = "#6366f1", f"{days}d restantes"
    return f'<span style="background:{color};color:#fff;border-radius:6px;padding:2px 8px;font-size:0.72rem;font-weight:600;margin-left:6px;">{text}</span>'


def _platform_pill(platform: str) -> str:
    icon = PLATFORM_ICONS.get(platform, "🌐")
    label = PLATFORM_LABELS.get(platform, platform)
    return f'<span style="background:rgba(99,102,241,0.18);border:1px solid rgba(99,102,241,0.3);color:#a5b4fc;border-radius:20px;padding:2px 10px;font-size:0.72rem;margin:1px;">{icon} {label}</span>'


def _currency_badge(currency: str) -> str:
    if currency == "USD":
        return '<span style="background:#1d4ed8;color:#fff;border-radius:6px;padding:2px 8px;font-size:0.72rem;font-weight:700;">$ USD</span>'
    return '<span style="background:#15803d;color:#fff;border-radius:6px;padding:2px 8px;font-size:0.72rem;font-weight:700;">R$ BRL</span>'


def _fmt_views(views: int) -> str:
    if views >= 1_000_000:
        return f"{views/1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views/1_000:.1f}k"
    return str(views)


def _rpm_display(rpm_cents: Optional[float], currency: str) -> str:
    if rpm_cents is None:
        return "—"
    return format_money_cents(int(round(rpm_cents)), currency)


def _format_cut_display_title(p: Dict[str, Any]) -> str:
    """Formata o título do corte tratando casos de corte removido ou renomeado (V5)."""
    v_id = p.get("video_id")
    c_key = p.get("cut_key")
    saved_title = p.get("cut_title") or "Sem título"

    if v_id and c_key:
        if not _is_cut_in_catalog(v_id, c_key):
            return f"⚠️ corte não encontrado no app ({saved_title})"
    return saved_title


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ABA 1: 📋 CAMPANHAS
# ══════════════════════════════════════════════════════════════════════════════

def _render_campaigns_tab(repo: CampaignRepo):
    st.markdown("#### 📋 Campanhas de Monetização")
    camps = repo.list_campaigns()

    with st.expander("➕ **Cadastrar Nova Campanha**", expanded=(len(camps) == 0)):
        _render_campaign_form(repo, existing=None)

    if not camps:
        st.info("Nenhuma campanha cadastrada ainda. Utilize o formulário acima para registrar sua primeira campanha.")
        return

    st.markdown("##### Campanhas Cadastradas")
    for camp in camps:
        camp_id = camp["id"]
        name = camp["name"]
        currency = camp["currency"]
        status = camp.get("status", "ativa")
        ends_on = camp.get("ends_on")
        platforms = camp.get("platforms", [])
        rate = camp.get("rate_per_1000_cents", 0)
        cap = camp.get("cap_per_clip_cents")
        source = camp.get("source_name") or "—"

        plat_pills = " ".join(_platform_pill(p) for p in platforms)
        badge_html = _status_badge(status) + _days_badge(ends_on) + "&nbsp;" + _currency_badge(currency)

        header_md = f"""
        <div style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;'>
          <strong style='font-size:1.05rem;'>#{camp_id} · {name}</strong>
          <span>{badge_html}</span>
        </div>
        <div style='margin-top:6px;font-size:0.82rem;color:#94a3b8;'>
          Fonte/Contratante: <b>{source}</b> &nbsp;|&nbsp;
          CPM: <b>{format_money_cents(rate, currency)}</b> &nbsp;|&nbsp;
          Teto por clipe: <b>{format_money_cents(cap, currency) if cap else "Sem teto"}</b> &nbsp;|&nbsp;
          Plataformas: {plat_pills}
        </div>
        """
        with st.expander(f"📌 {name} ({status})", expanded=False):
            st.markdown(header_md, unsafe_allow_html=True)
            st.divider()

            tab_edit, tab_actions = st.tabs(["✏️ Editar Campanha", "⚙️ Ações (Arquivar / Excluir)"])

            with tab_edit:
                _render_campaign_form(repo, existing=camp)

            with tab_actions:
                col_act1, col_act2 = st.columns(2)
                with col_act1:
                    st.markdown("##### 📁 Arquivar Campanha")
                    st.caption("Altera o status da campanha para **encerrada**. Campanhas encerradas não geram alertas de expiração e permanecem no histórico.")
                    if status != "encerrada":
                        if st.button(f"⏸️ Arquivar Campanha #{camp_id}", key=f"camp_btn_archive_{camp_id}"):
                            try:
                                repo.update_campaign(camp_id, {"status": "encerrada"})
                                st.success(f"Campanha '{name}' foi arquivada (status alterado para encerrada).")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                    else:
                        st.info("Esta campanha já está arquivada (encerrada).")

                with col_act2:
                    st.markdown("##### 🗑️ Excluir Definitivamente")
                    st.caption("A exclusão permanente só é permitida se **não houver publicações vinculadas** a esta campanha.")
                    if st.button(f"🗑️ Excluir Campanha #{camp_id}", key=f"camp_btn_del_{camp_id}", type="primary"):
                        try:
                            repo.delete_campaign(camp_id)
                            st.success(f"Campanha '{name}' excluída com sucesso.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))


def _render_campaign_form(repo: CampaignRepo, existing: Optional[Dict[str, Any]]):
    """Formulário unificado com todos os campos sempre visíveis e help text explicativo."""
    is_edit = existing is not None
    camp_id = existing["id"] if is_edit else None
    form_key = f"camp_form_edit_{camp_id}" if is_edit else "camp_form_create"

    with st.form(form_key, clear_on_submit=not is_edit):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input(
                "Nome da Campanha *",
                value=existing["name"] if is_edit else "",
                placeholder="Ex: Campanha Shorts Q1/2025",
                help="Nome único identificador da campanha.",
            )
            source_name = st.text_input(
                "Fonte / Contratante",
                value=existing.get("source_name") or "" if is_edit else "",
                placeholder="Ex: Agência Creator / Marca XPTO",
                help="Nome da marca, agência ou contratante que remunera a campanha.",
            )
            briefing_url = st.text_input(
                "Link do Briefing",
                value=existing.get("briefing_url") or "" if is_edit else "",
                placeholder="https://docs.google.com/... ou https://notion.so/...",
                help="URL com as regras do briefing ou contrato. Obrigatório para a declaração de licença autorizada.",
            )
            currency = st.radio(
                "Moeda *",
                options=list(_CURRENCY_OPTIONS.keys()),
                format_func=lambda x: _CURRENCY_OPTIONS[x],
                index=0 if not is_edit else (0 if existing.get("currency") == "BRL" else 1),
                horizontal=True,
                help="Moeda na qual as visualizações são remuneradas (BRL ou USD). Todas as publicações herdarão esta moeda.",
            )

        with col2:
            rate_default_str = "0,00"
            if is_edit and existing.get("rate_per_1000_cents") is not None:
                rate_default_str = format_money_cents(existing["rate_per_1000_cents"], existing.get("currency", "BRL")).replace("R$ ", "").replace("US$ ", "")

            rate_str = st.text_input(
                "Valor por 1.000 views (CPM) *",
                value=rate_default_str,
                help="Valor em Reais ou Dólares recebido a cada 1.000 visualizações válidas. Aceita '1,50', '1.50' ou '12,00'.",
            )

            cap_default_str = ""
            if is_edit and existing.get("cap_per_clip_cents") is not None:
                cap_default_str = format_money_cents(existing["cap_per_clip_cents"], existing.get("currency", "BRL")).replace("R$ ", "").replace("US$ ", "")

            cap_str = st.text_input(
                "Teto por Clipe (opcional)",
                value=cap_default_str,
                help="Remuneração máxima por clipe, independente do volume de views. Deixe em branco se não houver teto.",
            )
            fee_pct = st.number_input(
                "Comissão / Taxa de Intermediação (%)",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                value=round((existing.get("fee_bp") or 0) / 100, 2) if is_edit else 0.0,
                help="Percentual retido por agência ou intermediário. 0% = sem comissão.",
            )
            hold_days = st.number_input(
                "Prazo de Retenção / Hold (dias)",
                min_value=0,
                max_value=365,
                value=existing.get("hold_days") or 0 if is_edit else 0,
                help="Quantidade de dias após o lançamento até o pagamento ser liberado pelo contratante.",
            )

        col3, col4 = st.columns(2)
        with col3:
            starts_on_val = None
            if is_edit and existing.get("starts_on"):
                try:
                    starts_on_val = datetime.date.fromisoformat(existing["starts_on"])
                except Exception:
                    pass
            starts_on = st.date_input(
                "Data de Início da Campanha",
                value=starts_on_val,
                help="Data em que a campanha começou a aceitar publicações.",
            )

        with col4:
            ends_on_val = None
            if is_edit and existing.get("ends_on"):
                try:
                    ends_on_val = datetime.date.fromisoformat(existing["ends_on"])
                except Exception:
                    pass
            ends_on = st.date_input(
                "Data de Término / Prazo Final",
                value=ends_on_val,
                help="Data limite para publicação e contabilização de visualizações.",
            )

        platform_opts = list(PLATFORM_LABELS.keys())
        platform_labels_list = [f"{PLATFORM_ICONS[p]} {PLATFORM_LABELS[p]}" for p in platform_opts]
        default_platforms = existing.get("platforms", []) if is_edit else ["youtube"]
        default_indices = [i for i, p in enumerate(platform_opts) if p in default_platforms]

        selected_platform_indices = st.multiselect(
            "Plataformas Aceitas na Campanha *",
            options=range(len(platform_opts)),
            default=default_indices,
            format_func=lambda i: platform_labels_list[i],
            help="Selecione as redes sociais nas quais as publicações são elegíveis a pagamento.",
        )
        selected_platforms = [platform_opts[i] for i in selected_platform_indices]

        status = st.selectbox(
            "Status da Campanha",
            options=["ativa", "pausada", "encerrada"],
            format_func=lambda x: _STATUS_LABELS[x],
            index=["ativa", "pausada", "encerrada"].index(existing.get("status", "ativa")) if is_edit else 0,
            help="'ativa' aceita publicações; 'pausada' temporariamente parada; 'encerrada' concluída/arquivada.",
        )
        notes = st.text_area(
            "Observações e Regras Específicas",
            value=existing.get("notes") or "" if is_edit else "",
            height=70,
            help="Regras adicionais, hashtags obrigatórias ou diretrizes fornecidas no briefing.",
        )

        btn_label = "💾 Salvar Alterações" if is_edit else "✅ Cadastrar Campanha"
        submitted = st.form_submit_button(btn_label, type="primary")

        if submitted:
            try:
                rate_cents = parse_money_cents(rate_str) if rate_str.strip() else 0
            except ValueError as e:
                st.error(f"Valor por 1.000 views inválido: {e}")
                return

            try:
                cap_cents = parse_money_cents(cap_str) if cap_str.strip() else None
            except ValueError as e:
                st.error(f"Teto por clipe inválido: {e}")
                return

            fee_bp = int(round(fee_pct * 100))

            data = {
                "name": name,
                "source_name": source_name,
                "briefing_url": briefing_url,
                "currency": currency,
                "rate_per_1000_cents": rate_cents,
                "cap_per_clip_cents": cap_cents,
                "fee_bp": fee_bp,
                "hold_days": int(hold_days),
                "starts_on": starts_on.isoformat() if starts_on else None,
                "ends_on": ends_on.isoformat() if ends_on else None,
                "platforms": selected_platforms,
                "status": status,
                "notes": notes,
            }

            try:
                if is_edit:
                    repo.update_campaign(camp_id, data)
                    st.success(f"Campanha '{name}' atualizada com sucesso!")
                else:
                    created = repo.create_campaign(data)
                    st.success(f"Campanha '{created['name']}' cadastrada! (ID #{created['id']})")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ABA 2: 📌 PUBLICAÇÕES
# ══════════════════════════════════════════════════════════════════════════════

def _render_posts_tab(repo: CampaignRepo):
    st.markdown("#### 📌 Registro de Publicações")
    camps = repo.list_campaigns()

    with st.expander("➕ **Registrar Nova Publicação**", expanded=True):
        _render_post_registration_form(repo, camps)

    st.markdown("---")
    st.markdown("##### Publicações Cadastradas")

    posts_all = repo.list_posts_with_metrics()
    if not posts_all:
        st.info("Nenhuma publicação registrada ainda.")
        return

    # ── Filtros ────────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        camp_filter_opts = {0: "Todas as campanhas"}
        camp_filter_opts.update({c["id"]: c["name"] for c in camps})
        camp_filter_sel = st.selectbox(
            "Filtrar por Campanha:",
            options=list(camp_filter_opts.keys()),
            format_func=lambda x: camp_filter_opts[x],
            key="camp_filter_posts_camp",
        )
    with col_f2:
        plat_filter_opts = ["todas"] + list(PLATFORM_LABELS.keys())
        plat_filter_sel = st.selectbox(
            "Filtrar por Plataforma:",
            options=plat_filter_opts,
            format_func=lambda p: "Todas as plataformas" if p == "todas" else f"{PLATFORM_ICONS.get(p, '🌐')} {PLATFORM_LABELS.get(p, p)}",
            key="camp_filter_posts_plat",
        )

    filtered_posts = posts_all
    if camp_filter_sel != 0:
        filtered_posts = [p for p in filtered_posts if p.get("campaign_id") == camp_filter_sel]
    if plat_filter_sel != "todas":
        filtered_posts = [p for p in filtered_posts if p.get("platform") == plat_filter_sel]

    st.caption(f"Exibindo **{len(filtered_posts)}** de {len(posts_all)} publicações.")

    # ── Lista de Publicações ───────────────────────────────────────────────────
    for p in filtered_posts:
        post_id = p["id"]
        platform = p.get("platform", "outra")
        icon = PLATFORM_ICONS.get(platform, "🌐")
        plat_label = PLATFORM_LABELS.get(platform, platform)
        camp = p.get("campaign")
        camp_name = camp["name"] if camp else "Sem campanha"
        currency = p.get("currency", "BRL")
        calc = p.get("calculations", {})
        views = calc.get("views", 0)
        liquido = calc.get("liquido_cents", 0)
        display_title = _format_cut_display_title(p)

        summary_label = f"{icon} **{plat_label}** · {display_title} · 👁️ {_fmt_views(views)} · {format_money_cents(liquido, currency)}"

        with st.expander(summary_label, expanded=False):
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown(f"**Campanha:** {camp_name}")
                st.markdown(f"**Publicado em:** {format_date_br(p.get('posted_on'))}")
                st.markdown(f"**Conta/Canal:** {p.get('account_label') or '—'}")
                if p.get("post_url"):
                    st.markdown(f"**Link:** [{p['post_url']}]({p['post_url']})")
                else:
                    st.markdown("**Link:** —")
            with c_b:
                st.markdown(f"**Vídeo:** `{p.get('video_id') or '—'}` | **Corte:** `{p.get('cut_key') or '—'}`")
                st.markdown(f"**Bruto estimado:** {format_money_cents(calc.get('bruto_cents'), currency)}")
                st.markdown(f"**Comissão retida:** {format_money_cents(calc.get('comissao_cents'), currency)}")
                st.markdown(f"**Líquido estimado:** {format_money_cents(calc.get('liquido_cents'), currency)}")
                if calc.get("earnings_reported_cents") is not None:
                    st.markdown(f"**Ganho informado:** {format_money_cents(calc.get('earnings_reported_cents'), currency)}")
                if calc.get("rpm_real_cents") is not None:
                    st.markdown(f"**RPM real:** {_rpm_display(calc.get('rpm_real_cents'), currency)}")

            # Excluir publicação com confirmação
            st.divider()
            col_del1, col_del2 = st.columns([2, 1])
            with col_del1:
                st.caption("A exclusão da publicação removerá permanentemente todos os seus lançamentos de métricas.")
            with col_del2:
                if st.button(f"🗑️ Excluir Publicação #{post_id}", key=f"camp_btn_del_post_{post_id}", type="primary"):
                    repo.delete_post(post_id)
                    st.success(f"Publicação #{post_id} excluída com sucesso.")
                    st.rerun()


def _render_post_registration_form(repo: CampaignRepo, camps: List[Dict[str, Any]]):
    """Formulário de cadastro com escolha de origem (Corte do App ou Post sem corte),

    avisos sem bloqueio e ponte com a licença (V3).
    """
    origin_choice = st.radio(
        "Origem do Conteúdo Publicado:",
        options=["🎬 Corte do app", "📝 Post sem corte do app"],
        horizontal=True,
        key="camp_post_origin_choice",
    )

    selected_video_id: Optional[str] = None
    selected_cut_key: Optional[str] = None
    cut_title: str = ""
    eff_lic: Optional[Dict[str, Any]] = None
    is_lic_ok: bool = True

    if origin_choice == "🎬 Corte do app":
        library_videos = get_library()
        if not library_videos:
            st.warning("Nenhum vídeo catalogado na biblioteca do app. Cadastre ou processe um vídeo na Seção 1 primeiro.")
            return

        video_map = {v["video_id"]: f"{v.get('title', 'Vídeo')} ({v['video_id']})" for v in library_videos if v.get("video_id")}
        vid_selected = st.selectbox(
            "Selecione o Vídeo de Origem:",
            options=list(video_map.keys()),
            format_func=lambda x: video_map[x],
            key="camp_post_sel_video",
        )
        selected_video_id = vid_selected

        cuts_dict = _raw_load_cuts_catalog(selected_video_id)
        if not cuts_dict:
            st.warning(f"O vídeo selecionado ({selected_video_id}) não possui cortes catalogados em cuts_catalog.json.")
            return

        cut_options = {}
        for c_key, c_val in cuts_dict.items():
            if isinstance(c_val, dict):
                t = c_val.get("title") or f"Corte [{c_val.get('start_time')} - {c_val.get('end_time')}]"
                cut_options[c_key] = f"{t} ({c_key})"

        selected_cut_key = st.selectbox(
            "Selecione o Corte:",
            options=list(cut_options.keys()),
            format_func=lambda x: cut_options[x],
            key="camp_post_sel_cut",
        )

        cut_data = cuts_dict.get(selected_cut_key, {})
        cut_title = cut_data.get("title") or cut_options.get(selected_cut_key, "Corte")

        # Verifica Licença Efetiva
        eff_lic, lic_src = get_effective_license_for_cut(selected_video_id, selected_cut_key)
        is_lic_ok = is_publishable(eff_lic)

        lic_badge = "🟢 Licença Liberada" if is_lic_ok else "🔴 Não Verificado"
        st.markdown(f"**Licença efetiva do corte:** `{lic_badge}` *(Origem da regra: {lic_src})*")

    else:
        cut_title = st.text_input(
            "Título descritivo da publicação *",
            placeholder="Ex: Corte Viral TikTok #04",
            key="camp_post_custom_title",
        )

    # ── Campos da Publicação ───────────────────────────────────────────────────
    camp_options = {0: "— Sem campanha associada —"}
    camp_options.update({c["id"]: f"#{c['id']} {c['name']}" for c in camps})

    selected_camp_id = st.selectbox(
        "Vincular à Campanha:",
        options=list(camp_options.keys()),
        format_func=lambda x: camp_options[x],
        key="camp_post_sel_campaign",
    )
    selected_camp = next((c for c in camps if c["id"] == selected_camp_id), None)

    col1, col2 = st.columns(2)
    with col1:
        platform_opts = list(PLATFORM_LABELS.keys())
        platform = st.selectbox(
            "Plataforma de Publicação *",
            options=platform_opts,
            format_func=lambda p: f"{PLATFORM_ICONS.get(p, '🌐')} {PLATFORM_LABELS.get(p, p)}",
            key="camp_post_platform_sel",
        )
        account_label = st.text_input(
            "Conta / Canal (opcional)",
            placeholder="Ex: @meucanal ou Canal Cortes 01",
            key="camp_post_account_input",
        )

    with col2:
        posted_on = st.date_input(
            "Data da Publicação *",
            value=datetime.date.today(),
            key="camp_post_date_input",
        )
        post_url = st.text_input(
            "Link da Publicação (opcional)",
            placeholder="https://youtube.com/shorts/... ou https://tiktok.com/@...",
            key="camp_post_url_input",
        )

    # Moeda da publicação
    if selected_camp:
        currency = selected_camp.get("currency", "BRL")
        st.info(f"💱 Moeda imposta pela campanha vinculada: **{currency}**", icon="ℹ️")
    else:
        currency = st.radio(
            "Moeda da Publicação:",
            options=["BRL", "USD"],
            horizontal=True,
            key="camp_post_currency_radio",
        )

    notes = st.text_area("Observações da Publicação", height=60, key="camp_post_notes_input")

    # ── Avisos Sem Bloquear (V2) ───────────────────────────────────────────────
    if selected_camp:
        # 1. Plataforma fora da campanha
        camp_plats = selected_camp.get("platforms", [])
        if camp_plats and platform not in camp_plats:
            st.warning(
                f"⚠️ **Aviso:** A plataforma selecionada (**{PLATFORM_LABELS.get(platform, platform)}**) "
                f"não consta na lista de plataformas aceitas pela campanha '{selected_camp['name']}'.",
                icon="⚠️",
            )

        # 2. Data fora do período da campanha
        posted_iso = posted_on.isoformat()
        starts_on = selected_camp.get("starts_on")
        ends_on = selected_camp.get("ends_on")
        if starts_on and posted_iso < starts_on:
            st.warning(
                f"⚠️ **Aviso:** A data informada ({format_date_br(posted_iso)}) é anterior ao início oficial da campanha ({format_date_br(starts_on)}).",
                icon="⚠️",
            )
        if ends_on and posted_iso > ends_on:
            st.warning(
                f"⚠️ **Aviso:** A data informada ({format_date_br(posted_iso)}) é posterior ao término da campanha ({format_date_br(ends_on)}).",
                icon="⚠️",
            )

    # ── Ponte com a Licença (V3) ──────────────────────────────────────────────
    if origin_choice == "🎬 Corte do app" and selected_camp and not is_lic_ok:
        st.markdown("---")
        st.error(
            "🔴 **Corte com licença 'Não verificado':** Este corte não está liberado para publicação automática na esteira. "
            "Você pode declará-lo como **Campanha autorizada** utilizando os dados desta campanha.",
            icon="🚨",
        )

        ok_can_apply, msg_can_apply = can_apply_campaign_license(selected_camp)

        if not ok_can_apply:
            st.info(f"ℹ️ **Botão de declaração desabilitado:** {msg_can_apply}")
        else:
            col_b1, col_b2 = st.columns([1, 1])
            with col_b1:
                target_choice = st.radio(
                    "Aplicar licença autorizada em:",
                    options=["Só este corte", "O vídeo inteiro"],
                    key="camp_bridge_target_radio",
                )
            with col_b2:
                target_str = "corte" if target_choice == "Só este corte" else "video"
                confirm_replace = st.checkbox(
                    "Confirmar substituição caso já exista outra licença configurada",
                    key="camp_bridge_confirm_chk",
                )

                if st.button("📝 Declarar como Campanha autorizada usando os dados desta campanha", type="secondary", key="camp_bridge_apply_btn"):
                    res_bridge = apply_campaign_license(
                        campaign=selected_camp,
                        video_id=selected_video_id,
                        cut_key=selected_cut_key if target_str == "corte" else None,
                        target=target_str,
                        confirm_override=confirm_replace,
                    )
                    if res_bridge["success"]:
                        st.success(f"✅ Licença atualizada com sucesso no {target_str}!")
                        st.rerun()
                    else:
                        st.error(f"Erro ao declarar licença: {res_bridge.get('error')}")

    # ── Botão de Envio ────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("📌 Salvar e Registrar Publicação", type="primary", key="camp_btn_save_post"):
        final_title = cut_title.strip() if cut_title else "Sem título"
        data = {
            "campaign_id": selected_camp_id if selected_camp_id != 0 else None,
            "video_id": selected_video_id,
            "cut_key": selected_cut_key,
            "cut_title": final_title,
            "platform": platform,
            "account_label": account_label.strip() if account_label else None,
            "post_url": post_url.strip() if post_url else None,
            "posted_on": posted_on.isoformat(),
            "currency": currency,
            "notes": notes.strip() if notes else None,
        }
        try:
            created = repo.create_post(data)
            st.success(f"✅ Publicação #{created['id']} ({final_title}) registrada com sucesso!")
            st.rerun()
        except ValueError as e:
            st.error(str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ABA 3: 📈 LANÇAMENTOS
# ══════════════════════════════════════════════════════════════════════════════

def _render_snapshots_tab(repo: CampaignRepo):
    st.markdown("#### 📈 Lançamentos de Visualizações & Ganhos")
    posts = repo.list_posts_with_metrics()

    if not posts:
        st.info("Nenhuma publicação encontrada para lançamento de métricas. Cadastre publicações na sub-aba '📌 Publicações' primeiro.")
        return

    tab_batch, tab_history = st.tabs(["⚡ Atualização em Lote", "📜 Histórico por Publicação"])

    # ── (a) Atualização em Lote via st.data_editor ──────────────────────────────
    with tab_batch:
        st.markdown("##### ⚡ Atualização em Lote de Métricas")
        st.caption("Informe a data de referência acumulada e preencha as novas visualizações e ganhos informados. Apenas as linhas preenchidas serão gravadas.")

        col_d, _ = st.columns([1, 2])
        with col_d:
            batch_date = st.date_input("Data do Lançamento:", value=datetime.date.today(), key="camp_batch_date_input")

        # Constrói DataFrame para o st.data_editor
        rows_data = []
        for p in posts:
            snap = p.get("latest_snapshot")
            calc = p.get("calculations", {})
            curr = p.get("currency", "BRL")

            rows_data.append({
                "ID": p["id"],
                "Publicação": _format_cut_display_title(p),
                "Plataforma": PLATFORM_LABELS.get(p.get("platform", ""), p.get("platform", "")),
                "Moeda": curr,
                "Últimas Views": calc.get("views", 0),
                "Último Ganho": format_money_cents(calc.get("earnings_reported_cents"), curr) if calc.get("earnings_reported_cents") is not None else "—",
                "Novas Views Acumuladas": 0,
                "Novo Ganho Informado": "",
            })

        df_editor = pd.DataFrame(rows_data)

        # Configura colunas editáveis
        edited_df = st.data_editor(
            df_editor,
            disabled=["ID", "Publicação", "Plataforma", "Moeda", "Últimas Views", "Último Ganho"],
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Publicação": st.column_config.TextColumn("Publicação / Corte", width="medium"),
                "Plataforma": st.column_config.TextColumn("Plataforma", width="small"),
                "Moeda": st.column_config.TextColumn("Moeda", width="small"),
                "Últimas Views": st.column_config.NumberColumn("Últimas Views", format="%d"),
                "Novas Views Acumuladas": st.column_config.NumberColumn("Novas Views Acumuladas", min_value=0, step=100, help="Informe o total acumulado de visualizações"),
                "Novo Ganho Informado": st.column_config.TextColumn("Novo Ganho Informado", help="Opcional. Valor monetário lido na plataforma (ex: 15,50)"),
            },
            hide_index=True,
            use_container_width=True,
            key="camp_batch_data_editor",
        )

        if st.button("💾 Salvar Lançamentos em Lote", type="primary", key="camp_btn_save_batch"):
            saved_count = 0
            warnings_list = []
            errors_list = []

            for _, row in edited_df.iterrows():
                post_id = int(row["ID"])
                new_views = int(row["Novas Views Acumuladas"] or 0)
                earn_str = str(row["Novo Ganho Informado"] or "").strip()

                # Só grava se o usuário digitou views > 0 ou informou ganho
                if new_views <= 0 and not earn_str:
                    continue

                earn_cents = None
                if earn_str:
                    try:
                        earn_cents = parse_money_cents(earn_str)
                    except ValueError as e:
                        errors_list.append(f"Post #{post_id}: Ganho inválido '{earn_str}' ({e})")
                        continue

                try:
                    res_snap = repo.record_snapshot(
                        post_id=post_id,
                        snapshot_on=batch_date.isoformat(),
                        views=new_views,
                        earnings_cents=earn_cents,
                        note="Lançamento em lote",
                    )
                    saved_count += 1
                    if res_snap.get("warning"):
                        warnings_list.append(f"Post #{post_id}: {res_snap['warning']}")
                except ValueError as e:
                    errors_list.append(f"Post #{post_id}: {e}")

            if errors_list:
                for err in errors_list:
                    st.error(err)

            if warnings_list:
                for w in warnings_list:
                    st.warning(w)

            if saved_count > 0:
                st.success(f"✅ {saved_count} lançamento(s) gravado(s) com sucesso para a data {format_date_br(batch_date.isoformat())}!")
                st.rerun()
            elif not errors_list:
                st.info("Nenhuma linha foi alterada ou preenchida com novas visualizações.")

    # ── (b) Histórico por Publicação ──────────────────────────────────────────
    with tab_history:
        st.markdown("##### 📜 Histórico de Lançamentos por Publicação")
        post_options = {p["id"]: f"#{p['id']} · {PLATFORM_LABELS.get(p.get('platform',''), '')} · {_format_cut_display_title(p)}" for p in posts}

        sel_post_id = st.selectbox(
            "Selecione a Publicação:",
            options=list(post_options.keys()),
            format_func=lambda x: post_options[x],
            key="camp_hist_sel_post",
        )

        chosen_post = next((p for p in posts if p["id"] == sel_post_id), None)
        if chosen_post:
            curr = chosen_post.get("currency", "BRL")
            snaps = repo.list_snapshots_for_post(sel_post_id)

            if not snaps:
                st.info(f"Nenhum lançamento registrado ainda para a publicação #{sel_post_id}.")
            else:
                hist_rows = []
                for s in reversed(snaps):
                    hist_rows.append({
                        "ID Lançamento": s["id"],
                        "Data": format_date_br(s["snapshot_on"]),
                        "Views Acumuladas": s["views"],
                        "Ganho Informado": format_money_cents(s.get("earnings_cents"), curr),
                        "Nota": s.get("note") or "—",
                        "Registrado em": s.get("created_at")[:19].replace("T", " ") if s.get("created_at") else "—",
                    })
                st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

                # Formulário inline para exclusão de lançamento específico
                st.markdown("###### Excluir Lançamento")
                col_del_s1, col_del_s2 = st.columns([2, 1])
                with col_del_s1:
                    snap_del_id = st.selectbox(
                        "Selecione o lançamento a remover:",
                        options=[s["id"] for s in snaps],
                        format_func=lambda sid: f"Lançamento #{sid} ({format_date_br(next((s['snapshot_on'] for s in snaps if s['id'] == sid), ''))})",
                        key="camp_sel_del_snap_id",
                    )
                with col_del_s2:
                    if st.button("🗑️ Excluir Lançamento", type="secondary", key="camp_btn_del_snap"):
                        repo.delete_snapshot(snap_del_id)
                        st.success(f"Lançamento #{snap_del_id} excluído com sucesso.")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SUB-ABA 4: 💰 RESUMO
# ══════════════════════════════════════════════════════════════════════════════

def _render_summary_tab(repo: CampaignRepo):
    st.markdown("#### 💰 Resumo Financeiro & Desempenho")

    totals_by_curr = repo.get_totals_by_currency()
    camps_summary = repo.get_totals_by_campaign()
    posts_metrics = repo.list_posts_with_metrics()
    expiring = repo.get_campaigns_expiring_soon(days=3)
    stale = repo.get_posts_without_recent_updates(days=7)

    # ── Alertas (Decisão V2) ───────────────────────────────────────────────────
    if expiring:
        exp_names = ", ".join(f"'{c['name']}' (vence em {c['days_left']}d)" for c in expiring)
        st.warning(f"⏰ **Atenção:** Campanhas vencendo em até 3 dias: {exp_names}.", icon="⚠️")

    if stale:
        st.info(
            f"📋 **{len(stale)} publicação(ões)** em campanhas ativas estão sem atualização há mais de 7 dias.",
            icon="ℹ️",
        )

    # ── Cards por Moeda (com rótulos estimado e informado sempre visíveis) ──────
    st.markdown("##### Totais Consolidados por Moeda")
    for curr in ("BRL", "USD"):
        t = totals_by_curr.get(curr)
        if not t or t.get("posts_count", 0) == 0:
            continue

        st.markdown(f"###### {_currency_badge(curr)} Total em {curr}", unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📱 Publicações", t["posts_count"])
        c2.metric("👁️ Views Totais", _fmt_views(t["views"]))
        c3.metric("🏦 Ganho Estimado Líquido", format_money_cents(t["liquido_cents"], curr), help="Valor líquido calculado com base no CPM e comissão")
        c4.metric("📊 Ganho Informado", format_money_cents(t["earnings_reported_cents"], curr), help="Soma dos valores informados manualmente pelo usuário")
        c5.metric("✅ Ganho Considerado", format_money_cents(t["considerado_cents"], curr), help="Usa o ganho informado quando existente; caso contrário, o líquido estimado")

    st.markdown("---")

    # ── Tabelas Analíticas por Campanha e Plataforma ───────────────────────────
    tab_by_camp, tab_by_plat = st.tabs(["🏷️ Desempenho por Campanha", "🌐 Desempenho por Plataforma"])

    with tab_by_camp:
        if camps_summary:
            rows_camp = []
            for s in camps_summary:
                camp = s["campaign"]
                rows_camp.append({
                    "Campanha": camp["name"],
                    "Moeda": s["currency"],
                    "Status": _STATUS_LABELS.get(camp.get("status", "ativa"), camp.get("status")),
                    "Publicações": s["posts_count"],
                    "Views": _fmt_views(s["views"]),
                    "Bruto Estimado": format_money_cents(s["bruto_cents"], s["currency"]),
                    "Comissão": format_money_cents(s["comissao_cents"], s["currency"]),
                    "Líquido Estimado": format_money_cents(s["liquido_cents"], s["currency"]),
                    "Ganho Informado": format_money_cents(s.get("earnings_reported_cents"), s["currency"]),
                    "Ganho Considerado": format_money_cents(s["considerado_cents"], s["currency"]),
                    "RPM Real (por 1.000)": _rpm_display(s.get("rpm_real_cents"), s["currency"]),
                })
            st.dataframe(pd.DataFrame(rows_camp), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma campanha com dados registrada.")

    with tab_by_plat:
        by_plat = repo.get_totals_by_platform()
        if by_plat:
            rows_plat = []
            for item in by_plat:
                c_curr = item.get("currency", "BRL")
                rows_plat.append({
                    "Plataforma": f"{PLATFORM_ICONS.get(item['platform'], '🌐')} {PLATFORM_LABELS.get(item['platform'], item['platform'])}",
                    "Moeda": c_curr,
                    "Publicações": item["posts_count"],
                    "Views": _fmt_views(item["views"]),
                    "Líquido Estimado": format_money_cents(item["liquido_cents"], c_curr),
                    "Ganho Considerado": format_money_cents(item["considerado_cents"], c_curr),
                    "RPM Real (por 1.000)": _rpm_display(item.get("rpm_real_cents"), c_curr),
                })
            st.dataframe(pd.DataFrame(rows_plat), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma publicação com métricas para agrupar por plataforma.")

    # ── Gráfico de Barras: Ganho Considerado por Campanha (uma moeda por vez) ─
    st.markdown("---")
    st.markdown("##### 📊 Gráfico: Ganho Considerado por Campanha")

    active_currencies = [curr for curr in ("BRL", "USD") if any(s["currency"] == curr for s in camps_summary)]
    if not active_currencies:
        active_currencies = ["BRL"]

    selected_chart_curr = st.radio(
        "Selecione a moeda para exibição do gráfico:",
        options=active_currencies,
        format_func=lambda c: _CURRENCY_OPTIONS.get(c, c),
        horizontal=True,
        key="camp_summary_chart_currency",
    )

    chart_data = {
        s["campaign"]["name"]: (s["considerado_cents"] / 100.0)
        for s in camps_summary
        if s["currency"] == selected_chart_curr and s["considerado_cents"] > 0
    }

    if chart_data:
        df_chart = pd.DataFrame.from_dict({f"Ganho Considerado ({selected_chart_curr})": chart_data})
        st.bar_chart(df_chart)
    else:
        st.info(f"Sem dados de ganho considerado para exibir no gráfico em {selected_chart_curr}.")

    # ── Botões de Exportação CSV (Decisão V4) ──────────────────────────────────
    st.markdown("---")
    st.markdown("##### 📥 Exportação de Dados (CSV / Excel)")
    st.caption("Arquivos formatados em UTF-8 com BOM, delimitador ';' e valores monetários decimais em padrão brasileiro para abertura direta no Microsoft Excel.")

    col_csv1, col_csv2 = st.columns(2)
    with col_csv1:
        csv_posts_bytes = export_posts_metrics_csv(posts_metrics)
        st.download_button(
            label="📥 Baixar Publicações + Últimas Métricas (CSV)",
            data=csv_posts_bytes,
            file_name=f"viralcut_publicacoes_metricas_{datetime.date.today().isoformat()}.csv",
            mime="text/csv",
            key="camp_btn_download_posts_csv",
            use_container_width=True,
        )

    with col_csv2:
        csv_camp_bytes = export_campaigns_summary_csv(camps_summary)
        st.download_button(
            label="📥 Baixar Resumo Consolidado por Campanha (CSV)",
            data=csv_camp_bytes,
            file_name=f"viralcut_resumo_campanhas_{datetime.date.today().isoformat()}.csv",
            mime="text/csv",
            key="camp_btn_download_camps_csv",
            use_container_width=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT PRINCIPAL: render_campaigns_tab
# ══════════════════════════════════════════════════════════════════════════════

def render_campaigns_tab():
    """Renderiza a Aba '6. 📊 Campanhas & Métricas' do ViralCut Studio."""
    from core.ui_theme import render_section_header
    render_section_header("6", "Campanhas & Métricas", "Gestão de campanhas, publicações manuais, lançamentos de visualizações e resumo financeiro")

    try:
        repo = _get_repo()
    except Exception as exc:
        st.error(f"Erro ao inicializar o banco de campanhas (campaigns.db): {exc}")
        return

    tab_camp, tab_posts, tab_snaps, tab_summary = st.tabs([
        "📋 Campanhas",
        "📌 Publicações",
        "📈 Lançamentos",
        "💰 Resumo",
    ])

    with tab_camp:
        try:
            _render_campaigns_tab(repo)
        except Exception as exc:
            st.error(f"Erro na aba Campanhas: {exc}")

    with tab_posts:
        try:
            _render_posts_tab(repo)
        except Exception as exc:
            st.error(f"Erro na aba Publicações: {exc}")

    with tab_snaps:
        try:
            _render_snapshots_tab(repo)
        except Exception as exc:
            st.error(f"Erro na aba Lançamentos: {exc}")

    with tab_summary:
        try:
            _render_summary_tab(repo)
        except Exception as exc:
            st.error(f"Erro na aba Resumo: {exc}")
