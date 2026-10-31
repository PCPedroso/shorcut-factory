import os
import zipfile
import io
from core.runtime_env import (
    is_colab_env,
    is_linux_or_cloud_env,
    is_remote_browser_session,
    get_preferred_compute_device,
    ensure_ffmpeg_environment,
    get_js_runtimes_config,
    get_youtube_client_Strategies,
    get_youtube_extractor_args_list,
    build_directory_zip_bytes,
)


def test_environment_detection_booleans():
    assert isinstance(is_colab_env(), bool)
    assert isinstance(is_linux_or_cloud_env(), bool)
    assert isinstance(is_remote_browser_session(), bool)


def test_ensure_ffmpeg_environment():
    ff_path = ensure_ffmpeg_environment()
    assert isinstance(ff_path, str)
    assert len(ff_path) > 0


def test_get_js_runtimes_config():
    runtimes = get_js_runtimes_config()
    assert isinstance(runtimes, dict)
    for k, v in runtimes.items():
        assert k in ("deno", "node")
        assert "path" in v
        assert os.path.exists(v["path"])


def test_get_youtube_extractor_args_list():
    vod_args = get_youtube_extractor_args_list(is_live=False)
    assert isinstance(vod_args, list)
    assert len(vod_args) >= 3
    for item in vod_args:
        assert "youtube" in item
        assert "player_client" in item["youtube"]

    # Deve conter pelo menos uma estratégia com player_skip para contornar bloqueios de HTML em nuvem
    assert any("player_skip" in item["youtube"] for item in vod_args)

    live_args = get_youtube_extractor_args_list(is_live=True)
    assert isinstance(live_args, list)
    assert len(live_args) >= 1


def test_get_preferred_compute_device():
    dev_cpu = get_preferred_compute_device("cpu")
    assert dev_cpu == "cpu"
    dev_cuda = get_preferred_compute_device("cuda")
    assert dev_cuda in ("cuda", "cpu")


def test_build_directory_zip_bytes(tmp_path):
    sub = tmp_path / "corte_01"
    sub.mkdir()
    (sub / "readme.txt").write_text("conteudo de teste", encoding="utf-8")
    (tmp_path / "metadata.json").write_text('{"ok": true}', encoding="utf-8")

    raw_zip = build_directory_zip_bytes(str(tmp_path))
    assert isinstance(raw_zip, bytes)
    assert len(raw_zip) > 0

    with zipfile.ZipFile(io.BytesIO(raw_zip), "r") as zf:
        names = zf.namelist()
        assert "metadata.json" in names
        assert any(n.endswith("readme.txt") for n in names)
