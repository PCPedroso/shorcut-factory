"""
Testes para geração e persistência automática do Código do Vídeo (11 caracteres estilo YouTube).
"""
import json
import os
import streamlit as st

import core.library_manager as lm
from core.ui_theme import render_section_header


def test_generate_youtube_style_id_matches_reference():
    texto = "Por que Trump prioriza a disputa com a China e trata a política do Brasil como interesse estratégico?"
    code = lm.generate_youtube_style_id(texto)
    assert code == "e4HKbdr7NhI"
    assert len(code) == 11


def test_add_or_update_video_generates_and_saves_video_code(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(lm, "LIBRARY_FILE", str(tmp_path / "library.json"))

    entry = lm.add_or_update_video_in_library(
        video_id="tw_12345",
        title="Por que Trump prioriza a disputa com a China e trata a política do Brasil como interesse estratégico?",
        upload_date_raw="20261030",
        url="https://x.com/test/status/12345"
    )
    assert entry["video_code"] == "e4HKbdr7NhI"

    meta = json.loads((tmp_path / "tw_12345" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["video_code"] == "e4HKbdr7NhI"


def test_ensure_project_video_code_backfills_legacy_project(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "DATA_DIR", str(tmp_path))
    lib_file = tmp_path / "library.json"
    monkeypatch.setattr(lm, "LIBRARY_FILE", str(lib_file))

    v_dir = tmp_path / "legacy_vid"
    v_dir.mkdir()
    legacy_meta = {
        "video_id": "legacy_vid",
        "title": "Por que Trump prioriza a disputa com a China e trata a política do Brasil como interesse estratégico?",
        "url": "https://x.com/test/status/999"
    }
    (v_dir / "metadata.json").write_text(json.dumps(legacy_meta), encoding="utf-8")
    lib_file.write_text(json.dumps([dict(legacy_meta)]), encoding="utf-8")

    code = lm.ensure_project_video_code("legacy_vid")
    assert code == "e4HKbdr7NhI"

    updated_lib = json.loads(lib_file.read_text(encoding="utf-8"))
    assert updated_lib[0]["video_code"] == "e4HKbdr7NhI"

    updated_meta = json.loads((v_dir / "metadata.json").read_text(encoding="utf-8"))
    assert updated_meta["video_code"] == "e4HKbdr7NhI"


def test_render_section_header_includes_active_video_code(monkeypatch):
    rendered = []
    monkeypatch.setattr(st, "session_state", {"active_video_code": "e4HKbdr7NhI"})
    monkeypatch.setattr(st, "markdown", lambda html, **kw: rendered.append(html))

    render_section_header("3", "Fábrica de Cortes", "Pronto", "success")
    assert any("e4HKbdr7NhI" in h for h in rendered)
