"""
test_phase3_pipeline.py — Validação Integral dos Módulos da Fase 3
"""

import os
import sys

# Garante path correto e utf-8
sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.headline_drawer import HEADLINE_PRESETS, format_headline_text, build_ass_headline_style
from core.retention_effects import attach_contextual_emojis_to_words, generate_zoom_punch_filter
from core.audio_mixer import list_available_tracks, DUCKING_PRESETS
from core.integrations import get_youtube_auth_status, send_to_webhook
from core.subtitle_burner import generate_ass_file


def run_tests():
    print("=== 1. Teste Headline Drawer ===")
    assert len(HEADLINE_PRESETS) >= 4, "Presets de headline insuficientes"
    formatted = format_headline_text("Como ficar rico e faturar milhões com inteligência artificial hoje")
    print("Headline Formatada:", repr(formatted))
    style_ass = build_ass_headline_style(preset_key="yellow_black")
    assert "Style: Headline" in style_ass, "Estilo ASS de headline incorreto"
    print("Estilo Headline ASS OK!")

    print("\n=== 2. Teste Efeitos de Retenção (Emojis & Zoom Punch) ===")
    sample_words = [
        {"word": "esse", "start": 0.0, "end": 0.5},
        {"word": "dinheiro", "start": 0.5, "end": 1.0},
        {"word": "é", "start": 1.0, "end": 1.2},
        {"word": "fogo", "start": 1.2, "end": 1.7},
        {"word": "e", "start": 1.7, "end": 1.9},
        {"word": "segredo", "start": 1.9, "end": 2.4},
    ]
    enriched = attach_contextual_emojis_to_words(sample_words)
    print("Palavras Enriquecidas:", [w["word"] for w in enriched])
    assert any("💰" in w["word"] for w in enriched), "Emoji 💰 não anexado"
    assert any("🔥" in w["word"] for w in enriched), "Emoji 🔥 não anexado"
    assert any("🤫" in w["word"] for w in enriched), "Emoji 🤫 não anexado"

    punch_filter = generate_zoom_punch_filter(duration=30.0, interval=8.0)
    print("Zoom Punch Filter:", punch_filter[:80] + "...")
    assert "crop=" in punch_filter and "between(t," in punch_filter, "Filtro Zoom Punch incorreto"
    print("Zoom Punch Filter OK!")

    print("\n=== 3. Teste Audio Mixer & Trilhas ===")
    tracks = list_available_tracks()
    print(f"Trilhas encontradas: {len(tracks)}")
    assert len(tracks) >= 4, "Menos de 4 trilhas encontradas"
    for t in tracks:
        assert os.path.exists(t["path"]), f"Arquivo de trilha não existe: {t['path']}"
    assert "medio" in DUCKING_PRESETS, "Preset médio de ducking ausente"
    print("Trilhas e Presets de Ducking OK!")

    print("\n=== 4. Teste ASS Completo com Headline & Legendas ===")
    test_ass_path = os.path.join("scratch", "test_output.ass")
    os.makedirs("scratch", exist_ok=True)
    sample_lines = [{
        "words": enriched,
        "line_start": 0.0,
        "line_end": 2.5,
        "text": "esse dinheiro é fogo e segredo"
    }]
    success = generate_ass_file(
        lines=sample_lines,
        output_ass_path=test_ass_path,
        headline_enabled=True,
        headline_text="SEGREDO MILIONÁRIO",
        headline_preset="yellow_black",
        total_duration=3.0
    )
    assert success, "Falha ao gerar arquivo .ass"
    assert os.path.exists(test_ass_path), "Arquivo .ass não foi criado"
    with open(test_ass_path, "r", encoding="utf-8") as f:
        ass_content = f.read()
    assert "Style: Headline" in ass_content, "Style Headline ausente no .ass"
    assert "SEGREDO MILIONÁRIO" in ass_content, "Texto da Headline ausente no .ass"
    print("Geração do .ass com Headline e Emojis OK!")

    print("\n=== 5. Teste Integrações (YouTube & Webhooks) ===")
    yt_status = get_youtube_auth_status("data/client_secrets.json")
    print("YouTube Auth Status:", yt_status)
    assert "authenticated" in yt_status, "Retorno inválido de YouTube status"

    print("\n🎉 TODOS OS TESTES DOS MÓDULOS DA FASE 3 PASSARAM COM SUCESSO!")


if __name__ == "__main__":
    run_tests()
