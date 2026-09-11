"""
ViralCut Studio - Design System & UI Theme Engine
Fornece tokens de estilo, Glassmorphism, Badges dinâmicos, Empty States e Navegação por Stepper.
"""

import streamlit as st

VIRALCUT_CSS = """
<style>
/* ==========================================================================
   VIRALCUT STUDIO - MODERN DESIGN SYSTEM & GLASSMORPHISM
   ========================================================================== */

/* 1. Reset, Fontes e Fundo Imersivo */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Fundo sutil com gradiente radial elegante */
.stApp {
    background: radial-gradient(circle at 12% 15%, rgba(99, 102, 241, 0.08) 0%, transparent 45%),
                radial-gradient(circle at 88% 80%, rgba(236, 72, 153, 0.05) 0%, transparent 45%),
                #090d16 !important;
    color: #f8fafc !important;
}

/* 2. Top Bar & Stepper de Workflow */
.viralcut-stepper-box {
    background: rgba(18, 24, 38, 0.75);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 8px 14px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
}

/* 3. Cards Glassmorphism */
.viralcut-card {
    background: rgba(18, 24, 38, 0.7) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 14px !important;
    padding: 1.25rem !important;
    margin-bottom: 1rem !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25) !important;
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.viralcut-card:hover {
    border-color: rgba(99, 102, 241, 0.35) !important;
    box-shadow: 0 10px 30px rgba(99, 102, 241, 0.12) !important;
}

/* 4. Badges de Status Modernos */
.viral-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    vertical-align: middle;
}
.viral-badge-success {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
}
.viral-badge-processing {
    background: rgba(99, 102, 241, 0.18);
    color: #a5b4fc;
    border: 1px solid rgba(99, 102, 241, 0.35);
}
.viral-badge-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.35);
}
.viral-badge-score {
    background: rgba(236, 72, 153, 0.18);
    color: #f472b6;
    border: 1px solid rgba(236, 72, 153, 0.35);
    font-family: 'JetBrains Mono', monospace;
}
.viral-badge-neutral {
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
    border: 1px solid rgba(148, 163, 184, 0.25);
}

/* 5. Cabeçalhos de Seção com Destaque */
.viral-section-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 0.5rem;
    margin-top: 1rem;
    margin-bottom: 1.25rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.viral-section-title h2 {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    color: #f8fafc !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* 6. Botões Primários Estilizados com Efeito Neon */
button[kind="primary"], div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.25rem !important;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5) !important;
}

/* 7. Botões Secundários */
button[kind="secondary"], div.stButton > button[kind="secondary"] {
    background: rgba(30, 41, 59, 0.6) !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}
button[kind="secondary"]:hover {
    background: rgba(51, 65, 85, 0.8) !important;
    border-color: #818cf8 !important;
    color: #ffffff !important;
}

/* 8. Tabs Modernas */
div[data-testid="stTabs"] button[role="tab"] {
    border-radius: 8px !important;
    padding: 6px 14px !important;
    color: #94a3b8 !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: rgba(99, 102, 241, 0.15) !important;
    color: #818cf8 !important;
    border-bottom: 2px solid #6366f1 !important;
}

/* 9. Estilo para Campos de Timecode */
input[aria-label*="HH:MM:SS"], 
input[aria-label*="tempo inicial"], 
input[aria-label*="tempo final"],
input[placeholder*="00:00:00"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
    color: #38bdf8 !important;
    letter-spacing: 0.03em !important;
}

/* 10. Empty States */
.viral-empty-state {
    text-align: center;
    padding: 2.5rem 1.5rem;
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    background: rgba(18, 24, 38, 0.4);
    margin: 1rem 0;
}
.viral-empty-state-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
    opacity: 0.85;
}
.viral-empty-state-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 0.35rem;
}
.viral-empty-state-desc {
    font-size: 0.875rem;
    color: #94a3b8;
    max-width: 480px;
    margin: 0 auto;
}

/* 11. Limite de altura proporcional para vídeos 9:16 verticais */
div[data-testid="stVideo"] video {
    max-height: 520px !important;
    border-radius: 8px !important;
    object-fit: contain !important;
}
</style>
"""

WORKFLOW_STEPS = [
    "1. 📥 Ingestão & Transcrição",
    "2. 🧠 Mineração & IA (Llama 3)",
    "3. ✂️ Fábrica de Enquadramento 9:16",
    "4. 🎬 Galeria de Cortes & Pós",
    "🌐 Fluxo Completo (Todas as Seções)"
]

def inject_viralcut_theme():
    """Injeta as regras de CSS customizadas do ViralCut Studio."""
    st.markdown(VIRALCUT_CSS, unsafe_allow_html=True)

def render_status_badge(text: str, variant: str = "neutral") -> str:
    """
    Retorna o HTML formatado de um badge semântico moderno.
    Variantes aceitas: 'success', 'processing', 'warning', 'score', 'neutral'.
    """
    valid_variants = {"success", "processing", "warning", "score", "neutral"}
    safe_variant = variant if variant in valid_variants else "neutral"
    return f'<span class="viral-badge viral-badge-{safe_variant}">{text}</span>'

def render_empty_state_html(icon: str, title: str, description: str) -> str:
    """Retorna o HTML estruturado para um Empty State moderno."""
    return f"""
    <div class="viral-empty-state">
        <div class="viral-empty-state-icon">{icon}</div>
        <div class="viral-empty-state-title">{title}</div>
        <div class="viral-empty-state-desc">{description}</div>
    </div>
    """

def render_section_header(number: str, title: str, badge_text: str = None, badge_variant: str = "neutral"):
    """Renderiza um cabeçalho de seção profissional com título e badge de status inline."""
    badge_html = render_status_badge(badge_text, badge_variant) if badge_text else ""
    html = f"""
    <div class="viral-section-title">
        <h2>{number}. {title}</h2>
        <div>{badge_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_workflow_stepper(default_step: str = None) -> str:
    """
    Renderiza o Stepper de navegação horizontal no topo da aplicação.
    Permite alternar entre as 4 seções focadas ou visão completa contínua.
    """
    if "active_workflow_step" not in st.session_state:
        st.session_state["active_workflow_step"] = default_step or WORKFLOW_STEPS[0]

    # Garante que o step atual seja válido
    if st.session_state["active_workflow_step"] not in WORKFLOW_STEPS:
        st.session_state["active_workflow_step"] = WORKFLOW_STEPS[0]

    st.markdown('<div class="viralcut-stepper-box">', unsafe_allow_html=True)
    
    current_index = WORKFLOW_STEPS.index(st.session_state["active_workflow_step"])
    
    selected_step = st.radio(
        "Navegação do Workflow Studio:",
        WORKFLOW_STEPS,
        index=current_index,
        horizontal=True,
        label_visibility="collapsed",
        key="workflow_stepper_radio"
    )
    
    st.markdown('</div>', unsafe_allow_html=True)

    if selected_step != st.session_state["active_workflow_step"]:
        st.session_state["active_workflow_step"] = selected_step

    return st.session_state["active_workflow_step"]

def navigate_to_step(step_name_or_number: str):
    """
    Função utilitária para redirecionar programaticamente a etapa ativa no Stepper.
    Ex: navigate_to_step('3') ou navigate_to_step('Fábrica')
    """
    match_str = str(step_name_or_number).strip().lower()
    
    # Se for um dígito (ex: '1', '2', '3', '4'), busca pelo prefixo exato
    if match_str.isdigit():
        for step in WORKFLOW_STEPS:
            if step.startswith(f"{match_str}."):
                st.session_state["active_workflow_step"] = step
                return True

    for step in WORKFLOW_STEPS:
        if match_str in step.lower():
            st.session_state["active_workflow_step"] = step
            return True
    return False
