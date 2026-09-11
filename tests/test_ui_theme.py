import pytest
from core.ui_theme import (
    VIRALCUT_CSS, WORKFLOW_STEPS,
    render_status_badge, render_empty_state_html,
    navigate_to_step
)

def test_workflow_steps_structure():
    assert len(WORKFLOW_STEPS) == 5
    assert "1. 📥 Ingestão & Transcrição" in WORKFLOW_STEPS
    assert "2. 🧠 Mineração & IA (Llama 3)" in WORKFLOW_STEPS
    assert "3. ✂️ Fábrica de Enquadramento 9:16" in WORKFLOW_STEPS
    assert "4. 🎬 Galeria de Cortes & Pós" in WORKFLOW_STEPS
    assert "🌐 Fluxo Completo (Todas as Seções)" in WORKFLOW_STEPS

def test_viralcut_css_contains_design_tokens():
    assert "Plus Jakarta Sans" in VIRALCUT_CSS
    assert "JetBrains Mono" in VIRALCUT_CSS
    assert "viralcut-card" in VIRALCUT_CSS
    assert "viral-badge-success" in VIRALCUT_CSS
    assert "viral-badge-score" in VIRALCUT_CSS
    assert "#6366f1" in VIRALCUT_CSS

def test_render_status_badge_variants():
    badge_suc = render_status_badge("Concluído", "success")
    assert 'class="viral-badge viral-badge-success"' in badge_suc
    assert "Concluído" in badge_suc

    badge_proc = render_status_badge("Processando", "processing")
    assert 'class="viral-badge viral-badge-processing"' in badge_proc

    badge_score = render_status_badge("95/100", "score")
    assert 'class="viral-badge viral-badge-score"' in badge_score

    # Fallback para variante inválida
    badge_fallback = render_status_badge("Outro", "unknown_variant")
    assert 'class="viral-badge viral-badge-neutral"' in badge_fallback

def test_render_empty_state_html():
    html = render_empty_state_html("🎬", "Nenhum corte", "Gere seu primeiro corte acima.")
    assert "viral-empty-state" in html
    assert "🎬" in html
    assert "Nenhum corte" in html
    assert "Gere seu primeiro corte acima." in html

def test_navigate_to_step(monkeypatch):
    import streamlit as st
    # Simula session_state como dicionário
    fake_state = {}
    monkeypatch.setattr(st, "session_state", fake_state)

    res3 = navigate_to_step("3")
    assert res3 is True
    assert fake_state["active_workflow_step"] == "3. ✂️ Fábrica de Enquadramento 9:16"
    assert fake_state["workflow_stepper_radio"] == "3. ✂️ Fábrica de Enquadramento 9:16"

    res1 = navigate_to_step("ingestão")
    assert res1 is True
    assert fake_state["active_workflow_step"] == "1. 📥 Ingestão & Transcrição"
    assert fake_state["workflow_stepper_radio"] == "1. 📥 Ingestão & Transcrição"

    res_inv = navigate_to_step("etapa_inexistente_999")
    assert res_inv is False
