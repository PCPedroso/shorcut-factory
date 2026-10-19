import streamlit as st
import time
from typing import Optional
from .radar_service import ShopeeRadarService

# Vitrines populares de Achadinhos pré-configuradas para varredura rápida
PRESET_STOREFRONTS = {
    "🌟 Achadinhos Gerais & Utilidades (Ativo)": "https://linktr.ee/achadinhosshopee",
    "🍳 Cozinha Prática & Eletros (Produtos Diretos)": "https://linktr.ee/shopeecozinha",
    "🏠 Casa & Decoração (Hub Multicategorias)": "https://linktr.ee/achadinhosparacasa",
    "🧸 Brinquedos & Criatividade (Sub-vitrine)": "https://linktr.ee/shopeebrinquedos"
}

# Sugestões de produtos mais vendidos para criadores de Cortes de Vídeo / Podcasts / Conteúdo Falado
NICHE_PRODUCT_SUGGESTIONS = [
    {
        "nome": "Microfone de Lapela Sem Fio para Celular (K9 / K8)",
        "motivo": "Produto nº 1 em conversão para perfis de cortes e podcasts. O público que consome áudio compra para gravar seus próprios vídeos.",
        "busca_termo": "microfone lapela sem fio celular k9"
    },
    {
        "nome": "Suporte Articulado de Celular para Mesa / Gravação",
        "motivo": "Acessório essencial de baixo custo (R$ 20 - R$ 40) com altíssimo volume de vendas diárias.",
        "busca_termo": "suporte celular articulado mesa"
    },
    {
        "nome": "Fone de Ouvido Bluetooth TWS Sem Fio",
        "motivo": "Alta conversão para quem assiste podcasts e vídeos longos no celular.",
        "busca_termo": "fone ouvido bluetooth sem fio tws"
    },
    {
        "nome": "Ring Light de Mesa com Mini Tripé USB",
        "motivo": "Item clássico de criadores de conteúdo com ticket médio acessível.",
        "busca_termo": "ring light mesa mini tripe"
    }
]

def render_shopee_radar_tab():
    """
    Renderiza a aba 'Radar Shopee' no Streamlit, com suporte a:
    1. Rastreamento Direto por Link da Shopee (Sem depender do Instagram)
    2. Varredura Autônoma de Vitrine (Linktree / Beacons / Bio)
    3. Rastreamento Guiado por Reel do Instagram (Auto-detecção + Assistente de Associação)
    4. Scanner em Lote de Links
    5. Base Consolidada no SQLite
    """
    if "shopee_radar_service" not in st.session_state:
        st.session_state["shopee_radar_service"] = ShopeeRadarService()

    service: ShopeeRadarService = st.session_state["shopee_radar_service"]
    limiter_info = service.get_protection_status()

    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 1.6rem; font-weight: 700; color: #f8fafc; display: flex; align-items: center; gap: 10px;">
            🛍️ Radar Shopee — Rastreador & Minerador de Vendas
            <span style="font-size: 0.75rem; background: rgba(238, 77, 45, 0.2); color: #ff5722; padding: 4px 10px; border-radius: 9999px; border: 1px solid rgba(238, 77, 45, 0.4);">
                Autônomo & Inteligente
            </span>
        </h2>
        <p style="margin-top: 4px; color: #94a3b8; font-size: 0.95rem;">
            Descubra os produtos mais vendidos da Shopee: cole o link de um produto, varra vitrines inteiras de afiliados ou analise posts do Instagram com diagnóstico inteligente.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── BARRA DE PROTEÇÃO ANTI-BLOQUEIO DE IP ──────────────────────────────────────────
    can_req = limiter_info["can_request"]
    reqs_hour = limiter_info["requests_last_hour"]
    max_hour = limiter_info["max_requests_per_hour"]
    wait_sec = limiter_info["wait_seconds"]

    col_stat1, col_stat2, col_stat3 = st.columns([1.5, 1.2, 1.3])
    with col_stat1:
        if can_req:
            st.success("🛡️ **Proteção de IP:** Ativa & Segura (Pronto)", icon="✅")
        else:
            st.warning(f"⏳ **Cooldown Ativo:** Aguarde {wait_sec}s", icon="⚠️")

    with col_stat2:
        st.info(f"📊 **Quota Horária:** `{reqs_hour} / {max_hour}` reqs", icon="ℹ️")

    with col_stat3:
        st.markdown(
            """
            <div style="background: rgba(30, 41, 59, 0.6); padding: 9px 14px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.08); font-size: 12px; color: #94a3b8;">
                💾 <b>Cache Inteligente:</b> Produtos salvos são lidos localmente sem gastar requisições.
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── MODOS DE RASTREAMENTO ──────────────────────────────────────────────────────────
    tab_direct, tab_storefront, tab_reel, tab_bulk, tab_database = st.tabs([
        "🎯 Rastrear por Link Shopee (Direto)",
        "🏪 Varrer Vitrine de Criador (Sem Post)",
        "🎬 Rastrear por Reel do Instagram",
        "📦 Scanner em Lote de Links",
        "🏆 Catálogo Geral de Produtos Minerados"
    ])

    # ── 1. RASTREAR PRODUTO POR LINK DIRETO DA SHOPEE ─────────────────────────────────
    with tab_direct:
        st.subheader("🎯 Consulta Direta de Produto da Shopee")
        st.caption("Cole qualquer link de produto da Shopee (link encurtado de afiliado shope.ee, s.shopee.com.br ou link completo) para ver vendas reais, estoque e iniciar o monitoramento de velocidade.")

        col_d1, col_d2 = st.columns([2, 1])
        with col_d1:
            direct_input_url = st.text_input(
                "Link do produto na Shopee (ou link de afiliado):",
                placeholder="https://shope.ee/... ou https://s.shopee.com.br/... ou https://shopee.com.br/product/...",
                key="direct_prod_url"
            )
        with col_d2:
            direct_force = st.checkbox("Forçar consulta externa (ignorar cache)", value=False, key="direct_force_refresh")

        btn_consult_direct = st.button("🔍 Consultar Vendas e Estoque na Shopee", type="primary", use_container_width=True, key="btn_direct_consult")

        if btn_consult_direct:
            if not direct_input_url or not direct_input_url.strip():
                st.error("Por favor, cole um link da Shopee.")
            else:
                with st.spinner("Desencurtando link e consultando Shopee com segurança..."):
                    res = service.analyze_instagram_post(
                        post_url="https://instagram.com/radar_manual_entry",
                        direct_shopee_url=direct_input_url.strip(),
                        force_refresh=direct_force
                    )
                    st.session_state["last_direct_result"] = res

        last_dir = st.session_state.get("last_direct_result")
        if last_dir:
            for note in last_dir.get("notes", []):
                if "Cache Ativo" in note:
                    st.success(note)
                elif "Falha" in note or "Bloqueio" in note:
                    st.warning(note)
                else:
                    st.info(note)

            prod = last_dir.get("shopee_product")
            if prod and last_dir.get("product_found"):
                st.markdown("### 📦 Métricas Reais do Produto")
                card_c1, card_c2 = st.columns([1, 2.5])
                with card_c1:
                    if prod.get("image_url"):
                        st.image(prod.get("image_url"), use_container_width=True)
                with card_c2:
                    st.markdown(f"### {prod.get('title')}")
                    st.markdown(f"**Preço:** R$ {prod.get('price', 0.0):.2f} | **Estoque Atual:** {prod.get('stock')} unidades")
                    st.markdown(f"⭐ **Avaliação:** {prod.get('rating_star', 0.0)} ({prod.get('rating_count', 0)} avaliações)")

                    m1, m2 = st.columns(2)
                    m1.metric("Vendas no Último Mês", f"{prod.get('monthly_sold', 0):,}".replace(",", "."))
                    m2.metric("Vendas Totais Acumuladas", f"{prod.get('historical_sold', 0):,}".replace(",", "."))

                    vel = last_dir.get("velocity", {})
                    if vel and vel.get("snapshots_count", 0) > 1:
                        st.info(f"📈 **Aceleração (Delta):** +{vel.get('delta_sold')} vendas nas últimas {vel.get('hours_elapsed')}h.")

                    st.markdown(f"[🛒 Abrir Anúncio na Shopee]({prod.get('url')})", unsafe_allow_html=True)

    # ── 2. VARREDURA DE VITRINE (STOREFRONT) ───────────────────────────────────────────
    with tab_storefront:
        st.subheader("Varredura Autônoma de Vitrine (Bio / Linktree / Agregadores)")
        st.caption("Insira o link da bio de um criador de Achadinhos para extrair todos os produtos da vitrine e descobrir quais realmente vendem na Shopee.")

        c_sf1, c_sf2 = st.columns([2, 1])
        with c_sf1:
            sf_preset = st.selectbox(
                "Escolha um perfil/vitrine de referência ou use personalizado:",
                ["✏️ Inserir URL personalizada..."] + list(PRESET_STOREFRONTS.keys()),
                key="sf_preset_select"
            )

            if sf_preset == "✏️ Inserir URL personalizada...":
                target_sf_url = st.text_input(
                    "URL da vitrine (Linktree, Beacons, etc.):",
                    placeholder="https://linktr.ee/achadinhosshopee",
                    key="sf_custom_url"
                )
            else:
                target_sf_url = PRESET_STOREFRONTS[sf_preset]
                st.text_input("URL selecionada:", value=target_sf_url, disabled=True, key="sf_preset_url_disp")

        with c_sf2:
            sf_limit = st.slider("Máximo de produtos a analisar:", min_value=3, max_value=25, value=10, step=1, key="sf_limit_slider")
            sf_force = st.checkbox("Forçar consulta externa (ignorar cache)", value=False, key="sf_force_refresh")

        btn_scan_sf = st.button("🚀 Varrer Vitrine e Ranquear Mais Vendidos", type="primary", use_container_width=True, key="btn_scan_sf")

        if btn_scan_sf:
            if not target_sf_url or not target_sf_url.strip():
                st.error("Informe a URL da vitrine a ser analisada.")
            else:
                with st.spinner("Extraindo links da vitrine e consultando volume de vendas na Shopee com proteção de taxa..."):
                    sf_res = service.scan_storefront(
                        storefront_url=target_sf_url,
                        max_items=int(sf_limit),
                        force_refresh=sf_force
                    )
                    st.session_state["last_storefront_result"] = sf_res

        last_sf = st.session_state.get("last_storefront_result")
        if last_sf:
            st.markdown("### 📊 Resultado da Varredura de Vitrine")
            c_res1, c_res2, c_res3 = st.columns(3)
            c_res1.metric("Itens Encontrados na Vitrine", last_sf.get("total_items_found", 0))
            c_res2.metric("Itens Processados com Sucesso", last_sf.get("processed_count", 0))
            c_res3.metric("Carregados do Cache Seguro", last_sf.get("cached_count", 0))

            if last_sf.get("skipped_reason"):
                st.warning(last_sf["skipped_reason"])

            # Exibe sub-categorias/pastas se a vitrine for organizada em múltiplos links
            categories_found = last_sf.get("categories_found", [])
            if categories_found:
                st.markdown("#### 📁 Categorias / Pastas Encontradas Nesta Vitrine:")
                st.caption("Esta vitrine organiza os achadinhos em páginas separadas. Você pode copiar uma URL abaixo para analisar uma pasta específica:")
                cat_cols = st.columns(min(max(len(categories_found), 1), 3))
                for idx_c, cat in enumerate(categories_found[:6]):
                    with cat_cols[idx_c % len(cat_cols)]:
                        st.markdown(f"**{cat.get('title') or 'Categoria'}**")
                        st.code(cat.get("url", ""), language="text")

            # Diagnóstico transparente quando itens não puderam ser carregados como produtos
            skipped_items = last_sf.get("skipped_items", [])
            if last_sf.get("processed_count", 0) == 0 and skipped_items:
                with st.expander(f"🔍 Entenda por que os {len(skipped_items)} links não puderam ser carregados como produtos:", expanded=True):
                    st.markdown("""
                    **Como funcionam os links da Shopee em agregadores (Linktree/Beacons):**
                    - ⚠️ **Links Expirados (`error_page`):** A Shopee expira links de afiliados antigos após determinado tempo ou quando o anúncio é pausado pelo vendedor.
                    - 🏷️ **Links de Categorias Gerais:** Criadores frequentemente colocam links para departamentos inteiros da Shopee (ex: *'Compre Celulares'* ou páginas de campanha) que não são um produto individual.
                    - 📂 **Sub-Vitrines:** Criadores com centenas de itens usam Linktrees adicionais para separar categorias.
                    """)
                    for s in skipped_items:
                        st.markdown(f"- **{s.get('title')}**: `{s.get('reason')}` ([Ver Link]({s.get('url')}))")

            prods = last_sf.get("products", [])
            if prods:
                st.markdown("#### 🥇 Ranking dos Produtos Mais Vendidos Desta Vitrine:")
                for rank, p in enumerate(prods, 1):
                    cat_prefix = f"[{p.get('category_name')}] " if p.get('category_name') else ""
                    with st.expander(f"#{rank} | {cat_prefix}{p.get('title')[:60]}... — Vendas Mês: {p.get('monthly_sold', 0):,} | R$ {p.get('price', 0.0):.2f}", expanded=(rank <= 2)):
                        col_p1, col_p2 = st.columns([1, 3])
                        with col_p1:
                            if p.get("image_url"):
                                st.image(p.get("image_url"), use_container_width=True)
                        with col_p2:
                            st.markdown(f"**Título:** {p.get('title')}")
                            if p.get("category_name"):
                                st.markdown(f"📁 **Categoria:** `{p.get('category_name')}`")
                            st.markdown(f"**Preço:** R$ {p.get('price', 0.0):.2f} | ⭐ {p.get('rating_star', 0.0)} ({p.get('rating_count', 0)} reviews)")
                            st.markdown(f"📦 **Vendas Mensais:** `{p.get('monthly_sold', 0):,}` | **Total Histórico:** `{p.get('historical_sold', 0):,}` unidades")
                            st.markdown(f"[🔗 Abrir Produto na Shopee]({p.get('url')}) | [🎯 Link Original de Afiliado]({p.get('original_affiliate_url')})")

    # ── 3. RASTREAR POR REEL DO INSTAGRAM (COM AUTO-FETCH & GUIA DE ASSOCIAÇÃO) ────────
    with tab_reel:
        st.subheader("🎬 Rastrear e Associar Produto por Reel do Instagram")
        st.caption("Cole a URL do Reel. A ferramenta lê automaticamente o perfil, curtidas, comentários e legenda.")

        col_in1, col_in2 = st.columns([2, 1])
        with col_in1:
            post_url = st.text_input(
                "Cole a URL do Reel do Instagram:",
                placeholder="https://www.instagram.com/reel/DehPSyMNnRK/",
                key="radar_input_url"
            )
            reel_affiliate_link = st.text_input(
                "Link da Shopee do produto associado a este vídeo (opcional se já estiver na legenda):",
                placeholder="https://shope.ee/... ou https://s.shopee.com.br/...",
                key="radar_reel_direct_shopee",
                help="Se você marcou o produto no Instagram pela etiqueta de compra ou nos stories, cole o link dele aqui para monitorarmos suas vendas!"
            )

        with col_in2:
            catalog_url = st.text_input(
                "URL da Bio / Catálogo (Linktree do seu perfil):",
                placeholder="https://linktr.ee/seu_perfil",
                key="radar_input_catalog",
                help="Se seu perfil tem um Linktree na bio, informe aqui para cruzarmos os códigos."
            )
            force_refresh = st.checkbox("Forçar busca externa", value=False, key="radar_force_refresh_reel")

        btn_analyze = st.button("🚀 Analisar Reel e Rastrear Vendas", type="primary", use_container_width=True, key="btn_analyze_reel")

        if btn_analyze:
            if not post_url or not post_url.strip():
                st.error("Informe a URL do Reel do Instagram.")
            else:
                with st.spinner("Lendo metadados do Instagram e consultando Shopee com segurança..."):
                    result = service.analyze_instagram_post(
                        post_url=post_url.strip(),
                        catalog_url=catalog_url,
                        direct_shopee_url=reel_affiliate_link.strip() if reel_affiliate_link else None,
                        force_refresh=force_refresh
                    )
                    st.session_state["last_radar_result"] = result

        last_res = st.session_state.get("last_radar_result")
        if last_res:
            st.markdown("### 📊 Diagnóstico e Análise do Post")
            
            # Detalhes do post lido pelo auto-fetch
            uploader = last_res.get("uploader") or "Perfil do Instagram"
            ig_m = last_res.get("instagram_metrics") or {}
            st.info(f"👤 **Canal:** `@{uploader}` | 👍 **Curtidas:** {ig_m.get('likes', 0)} | 💬 **Comentários:** {ig_m.get('comments', 0)}")
            
            caption_read = last_res.get("caption", "").strip()
            if caption_read:
                with st.expander("📝 Visualizar Legenda Completa Lida do Post:", expanded=False):
                    st.code(caption_read, language="text")

            # Diagnóstico quando não há produto na legenda
            if not last_res.get("product_found"):
                st.warning("⚠️ **Diagnóstico:** Nenhum link encurtado da Shopee (`shope.ee`) ou código numérico de catálogo foi encontrado no texto da legenda deste vídeo.")
                
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 107, 0, 0.3); border-radius: 10px; padding: 16px; margin: 15px 0;">
                    <h4 style="margin: 0 0 8px 0; color: #ff9800;">💡 Como funciona a associação de produtos no Instagram?</h4>
                    <p style="margin: 0; font-size: 0.9rem; color: #cbd5e1; line-height: 1.5;">
                        Quando você usa a <b>etiqueta nativa de produto (Instagram Shopping)</b> ou fala no vídeo para pedir o link nos comentários, o Instagram não inclui a URL da Shopee no texto público da legenda.<br><br>
                        <b>Para rastrear as vendas do produto deste vídeo:</b><br>
                        1. Cole o link do produto da Shopee no campo acima <i>'Link da Shopee do produto associado a este vídeo'</i> e clique novamente em <b>Analisar</b>.<br>
                        2. Ou escolha uma das ideias abaixo para promover neste conteúdo e medir a tração!
                    </p>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("#### 🎯 Ideias de Produtos em Alta para Vídeos de Cortes & Podcasts:")
                for item in NICHE_PRODUCT_SUGGESTIONS:
                    with st.expander(f"⭐ {item['nome']}", expanded=False):
                        st.markdown(f"**Por que vende:** {item['motivo']}")
                        st.markdown(f"👉 *Dica de divulgação:* Fixe nos comentários: *'Microfone / acessório usado na gravação no link da bio!'*")

            else:
                # Produto encontrado e vinculado com sucesso!
                prod = last_res.get("shopee_product")
                st.success("✅ **Produto da Shopee vinculado com sucesso ao post!**")
                card_col1, card_col2 = st.columns([1, 2.5])
                with card_col1:
                    img_url = prod.get("image_url")
                    if img_url:
                        st.image(img_url, use_container_width=True)
                    else:
                        st.markdown("*(Sem imagem disponível)*")

                with card_col2:
                    st.markdown(f"### {prod.get('title')}")
                    st.markdown(f"**Preço:** R$ {prod.get('price', 0.0):.2f} | **Estoque:** {prod.get('stock')} unidades")
                    st.markdown(f"⭐ **Avaliação:** {prod.get('rating_star', 0.0)} ({prod.get('rating_count', 0)} reviews)")

                    m1, m2, m3 = st.columns(3)
                    m1.metric("Vendas no Mês", f"{prod.get('monthly_sold', 0):,}".replace(",", "."))
                    m2.metric("Vendas Totais", f"{prod.get('historical_sold', 0):,}".replace(",", "."))
                    m3.metric("Viral Score", f"{last_res.get('viral_score', 0.0)} / 100")

                    vel = last_res.get("velocity", {})
                    if vel and vel.get("snapshots_count", 0) > 1:
                        st.info(f"📈 **Delta Registrado:** +{vel.get('delta_sold')} vendas nas últimas {vel.get('hours_elapsed')}h.")

                    st.markdown(f"[🔗 Abrir Produto na Shopee]({prod.get('url')})", unsafe_allow_html=True)

    # ── 4. SCANNER EM LOTE DE LINKS ───────────────────────────────────────────────────
    with tab_bulk:
        st.subheader("Processamento em Lote de Links da Shopee")
        st.caption("Cole vários links da Shopee ou mensagens com links copiadas do WhatsApp/Telegram para descobrir em massa quais mais vendem.")

        bulk_text = st.text_area(
            "Cole aqui o texto ou lista de links (um por linha ou dentro de texto):",
            placeholder="Exemplo:\nhttps://shope.ee/link1\nhttps://s.shopee.com.br/link2\nhttps://shopee.com.br/product/123/456",
            height=130,
            key="bulk_links_input"
        )

        c_b1, c_b2 = st.columns([1, 2])
        with c_b1:
            bulk_limit = st.slider("Limite de links a processar:", min_value=2, max_value=20, value=8, step=1, key="bulk_limit_slider")
        with c_b2:
            bulk_force = st.checkbox("Forçar consulta externa em todos", value=False, key="bulk_force_refresh")

        btn_bulk_scan = st.button("🔍 Processar Lote e Comparar Vendas", type="primary", use_container_width=True, key="btn_bulk_scan")

        if btn_bulk_scan:
            if not bulk_text or not bulk_text.strip():
                st.error("Cole ao menos um link ou texto com links da Shopee.")
            else:
                with st.spinner("Extraindo e consultando links em lote com pausas de segurança..."):
                    b_res = service.scan_bulk_links(
                        links_or_text=bulk_text,
                        max_items=int(bulk_limit),
                        force_refresh=bulk_force
                    )
                    st.session_state["last_bulk_result"] = b_res

        last_b = st.session_state.get("last_bulk_result")
        if last_b:
            st.markdown("### 📊 Resultado da Comparação em Lote")
            if last_b.get("skipped_reason"):
                st.warning(last_b["skipped_reason"])

            b_prods = last_b.get("products", [])
            if b_prods:
                for idx, p in enumerate(b_prods, 1):
                    with st.expander(f"#{idx} | {p.get('title')[:55]}... — {p.get('monthly_sold', 0):,} vendas/mês | R$ {p.get('price', 0.0):.2f}", expanded=(idx <= 2)):
                        c_bp1, c_bp2 = st.columns([1, 3])
                        with c_bp1:
                            if p.get("image_url"):
                                st.image(p.get("image_url"), use_container_width=True)
                        with c_bp2:
                            st.markdown(f"**Título:** {p.get('title')}")
                            st.markdown(f"**Preço:** R$ {p.get('price', 0.0):.2f} | **Vendas no Mês:** `{p.get('monthly_sold', 0):,}`")
                            st.markdown(f"[🔗 Abrir Produto na Shopee]({p.get('url')})")

    # ── 5. CATÁLOGO GERAL DE PRODUTOS MINERADOS ────────────────────────────────────────
    with tab_database:
        st.subheader("🏆 Base Consolidada de Produtos Rastreados")

        col_ref1, col_ref2 = st.columns([3, 1])
        with col_ref1:
            st.caption("Todos os produtos minerados de vitrines, listas de links ou reels, ordenados por tração comercial.")
        with col_ref2:
            if st.button("🔄 Atualizar Lote (Seguro)", help="Atualiza produtos com mais de 12h sem consulta respeitando o rate limiter", key="btn_db_refresh"):
                with st.spinner("Atualizando produtos elegíveis com pausas de segurança..."):
                    refresh_res = service.refresh_tracked_products(max_batch_size=3, min_age_hours=12.0)
                    st.success(f"Atualização concluída: {refresh_res['updated_count']} atualizados, {refresh_res['skipped_count']} pulados por proteção de taxa.")

        opportunities = service.get_top_opportunities(limit=50)
        if not opportunities:
            st.info("Nenhum produto cadastrado no banco ainda. Use as abas de Consulta Direta ou Varredura acima para minerar seus primeiros achadinhos!")
        else:
            for idx, item in enumerate(opportunities, 1):
                with st.expander(f"#{idx} | {item.get('title')[:60]}... — Vendas Mês: {item.get('velocity', {}).get('monthly_sold', 0):,} | Score: {item.get('viral_score')} | R$ {item.get('price'):.2f}", expanded=(idx <= 2)):
                    c_img, c_info = st.columns([1, 3])
                    with c_img:
                        if item.get("image_url"):
                            st.image(item.get("image_url"), use_container_width=True)
                    with c_info:
                        st.markdown(f"**Título Completo:** {item.get('title')}")
                        st.markdown(f"**Preço Atual:** R$ {item.get('price', 0.0):.2f} | **Estoque:** {item.get('stock')}")
                        st.markdown(f"📦 **Vendas Mensais:** `{item.get('velocity', {}).get('monthly_sold', 0):,}` | **Score Viral:** `{item.get('viral_score')}/100`")
                        if item.get("max_reel_views"):
                            st.caption(f"📱 Reel mais visualizado: {item.get('max_reel_views'):,} views | Intenção: {item.get('max_intent_score')}%")
                        st.markdown(f"[🛒 Ver Anúncio na Shopee]({item.get('url')})")
