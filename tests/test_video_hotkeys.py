import pytest
from unittest.mock import MagicMock
import app

def test_inject_video_hotkeys_js_definition_and_injection(monkeypatch):
    """
    Testa se inject_video_hotkeys_js está definido e injeta o script
    contendo os atalhos solicitados estilo YouTube:
    - L / l: avança 10s (Ctrl: 5s)
    - J / j: volta 10s (Ctrl: 5s)
    - K / k: pausa / reproduz
    - OSD de feedback visual
    - Proteção contra digitação em inputs/textareas
    """
    mock_st_html = MagicMock()
    monkeypatch.setattr(app.st, "html", mock_st_html)

    app.inject_video_hotkeys_js()

    assert mock_st_html.called
    call_args = mock_st_html.call_args[0][0]
    
    # 1. Verifica teclas de atalho
    assert "key !== 'j' && key !== 'k' && key !== 'l'" in call_args
    
    # 2. Verifica modificador Ctrl reduzindo para 5s (metade de 10s)
    assert "const isCtrl = e.ctrlKey || e.metaKey;" in call_args
    assert "const step = isCtrl ? 5 : 10;" in call_args

    # 3. Verifica ações
    # Avanço com L (+step)
    assert "key === 'l'" in call_args
    assert "+ step" in call_args
    assert "showVideoOsd(targetVid, '⏩', `+${step}s`);" in call_args

    # Recuo com J (-step)
    assert "key === 'j'" in call_args
    assert "- step" in call_args
    assert "showVideoOsd(targetVid, '⏪', `-${step}s`);" in call_args

    # Pausa / Alterna com K
    assert "key === 'k'" in call_args
    assert "targetVid.paused" in call_args
    assert "targetVid.pause()" in call_args
    assert "targetVid.play()" in call_args
    assert "showVideoOsd(targetVid, '⏸', 'Pausado');" in call_args
    assert "showVideoOsd(targetVid, '▶', 'Reproduzindo');" in call_args

    # 4. Verifica proteção de digitação
    assert "tag === 'input' || tag === 'textarea' || tag === 'select'" in call_args
    assert "activeEl.isContentEditable" in call_args

    # 5. Verifica estilos OSD
    assert "viralcut-player-osd" in call_args
