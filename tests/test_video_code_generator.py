"""
Testes para geração, unicidade global (anti-colisão) e persistência automática
do Código do Vídeo Base e do Código Exclusivo de cada Corte (11 caracteres estilo YouTube).
"""
import json
import os
import streamlit as st

import core.library_manager as lm
import core.cuts_catalog as cc
import core.export_kit as ek
from core.video_code_manager import allocate_cut_code, allocate_project_code
from core.ui_theme import render_section_header, render_copyable_code_html


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


def test_two_projects_with_identical_title_never_collide(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(lm, "LIBRARY_FILE", str(tmp_path / "library.json"))

    same_title = "Por que Trump prioriza a disputa com a China e trata a política do Brasil como interesse estratégico?"
    entry1 = lm.add_or_update_video_in_library(
        video_id="proj_1",
        title=same_title,
        upload_date_raw="20261030",
        url="https://youtube.com/watch?v=proj_1"
    )
    entry2 = lm.add_or_update_video_in_library(
        video_id="proj_2",
        title=same_title,
        upload_date_raw="20261030",
        url="https://youtube.com/watch?v=proj_2"
    )

    assert entry1["video_code"] == "e4HKbdr7NhI"
    assert len(entry2["video_code"]) == 11
    assert entry1["video_code"] != entry2["video_code"]

    # Idempotência ao consultar novamente o mesmo owner
    assert lm.ensure_project_video_code("proj_1") == entry1["video_code"]
    assert lm.ensure_project_video_code("proj_2") == entry2["video_code"]


def test_each_cut_and_format_gets_exclusive_code(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(lm, "LIBRARY_FILE", str(tmp_path / "library.json"))

    vid = "vid_cuts_01"
    v_dir = tmp_path / vid
    v_dir.mkdir(parents=True)

    dummy_mp4 = v_dir / "temp_cut.mp4"
    dummy_mp4.write_bytes(b"\x00" * 2048)

    pkg1 = ek.create_viral_package(
        video_path=str(dummy_mp4),
        title="Corte Bombástico",
        description="Desc 1",
        hashtags=["#shorts"],
        tags_seo="tag1, tag2",
        aspect_mode="9:16_smart_face",
        output_base_dir=str(v_dir),
        orig_video_info={"video_id": vid, "title": "Vídeo Base"},
        start_time_str="00:01:00.00",
        end_time_str="00:02:00.00"
    )
    pkg2 = ek.create_viral_package(
        video_path=str(dummy_mp4),
        title="Corte Bombástico",
        description="Desc 1",
        hashtags=["#shorts"],
        tags_seo="tag1, tag2",
        aspect_mode="16:9",
        output_base_dir=str(v_dir),
        orig_video_info={"video_id": vid, "title": "Vídeo Base"},
        start_time_str="00:01:00.00",
        end_time_str="00:02:00.00"
    )

    assert len(pkg1["cut_code"]) == 11
    assert len(pkg2["cut_code"]) == 11
    assert pkg1["cut_code"] != pkg2["cut_code"]

    info_txt = open(os.path.join(pkg1["package_dir"], "info_publicacao.txt"), "r", encoding="utf-8").read()
    assert f"🔑 CÓDIGO EXCLUSIVO DO CORTE (11 CHARS): {pkg1['cut_code']}" in info_txt


def test_legacy_cuts_catalog_backfills_exclusive_codes(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(lm, "LIBRARY_FILE", str(tmp_path / "library.json"))
    monkeypatch.setattr(cc, "_get_catalog_path", lambda vid: str(tmp_path / vid / "cuts_catalog.json"))

    vid = "legacy_proj_cuts"
    v_dir = tmp_path / vid
    v_dir.mkdir(parents=True)

    legacy_catalog = {
        "00:00:10.00_00:01:10.00": {
            "start_time": "00:00:10.00",
            "end_time": "00:01:10.00",
            "title": "Corte Antigo 1",
            "formats": {
                "9:16_smart_face": {
                    "aspect_mode": "9:16_smart_face",
                    "video_path": str(v_dir / "c1_916.mp4")
                },
                "16:9": {
                    "aspect_mode": "16:9",
                    "video_path": str(v_dir / "c1_169.mp4")
                }
            }
        }
    }
    cat_file = v_dir / "cuts_catalog.json"
    cat_file.write_text(json.dumps(legacy_catalog), encoding="utf-8")

    loaded = cc.load_cuts_catalog(vid)
    entry = loaded["00:00:10.00_00:01:10.00"]
    c_916 = entry["formats"]["9:16_smart_face"].get("cut_code")
    c_169 = entry["formats"]["16:9"].get("cut_code")

    assert c_916 and len(c_916) == 11
    assert c_169 and len(c_169) == 11
    assert c_916 != c_169

    # Recarregar mantém exatamente os mesmos códigos (idempotência)
    loaded_again = cc.load_cuts_catalog(vid)
    assert loaded_again["00:00:10.00_00:01:10.00"]["formats"]["9:16_smart_face"]["cut_code"] == c_916
    assert loaded_again["00:00:10.00_00:01:10.00"]["formats"]["16:9"]["cut_code"] == c_169


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
    assert any("data-copy-code=\"e4HKbdr7NhI\"" in h for h in rendered)


def test_render_copyable_code_html_attributes():
    html = render_copyable_code_html("ZeLFAqzfsTY", label="Código do Corte:", prefix_icon="🔑")
    assert 'data-copy-code="ZeLFAqzfsTY"' in html
    assert 'class="viralcut-copyable-code"' in html
    assert 'role="button"' in html
    assert 'tabindex="0"' in html
    assert 'ZeLFAqzfsTY' in html
    assert '🔑' in html
    assert '📋' in html
    assert 'Código do Corte:' in html

    # Casos nulos ou vazios retornam string vazia
    assert render_copyable_code_html("") == ""
    assert render_copyable_code_html(None) == ""
