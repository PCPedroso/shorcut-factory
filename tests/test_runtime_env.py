import os
import zipfile
import io
from core.runtime_env import (
    is_colab_env,
    is_linux_or_cloud_env,
    is_remote_browser_session,
    has_cuda_support,
    get_preferred_compute_device,
    get_ffmpeg_hwaccel_flags,
    get_ffmpeg_video_encode_flags,
    convert_ffmpeg_cmd_to_cpu,
    ensure_ffmpeg_environment,
    get_js_runtimes_config,
    get_youtube_client_Strategies,
    get_youtube_extractor_args_list,
    build_directory_zip_bytes,
    patch_windows_asyncio_connection_lost,
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
        if not item:
            continue
        assert "youtube" in item
        assert "player_client" in item["youtube"]

    # Deve conter pelo menos uma estratégia com player_skip para contornar bloqueios de HTML em nuvem
    assert any("player_skip" in item.get("youtube", {}) for item in vod_args)

    live_args = get_youtube_extractor_args_list(is_live=True)
    assert isinstance(live_args, list)
    assert len(live_args) >= 1


def test_get_preferred_compute_device():
    dev_cpu = get_preferred_compute_device("cpu")
    assert dev_cpu == "cpu"
    dev_cuda = get_preferred_compute_device("cuda")
    assert dev_cuda in ("cuda", "cpu")
    if has_cuda_support():
        assert dev_cuda == "cuda"


def test_ffmpeg_gpu_and_cpu_flags():
    cpu_hw = get_ffmpeg_hwaccel_flags("cpu")
    assert cpu_hw == []
    cpu_enc = get_ffmpeg_video_encode_flags(device="cpu", preset_cpu="veryfast", crf=20)
    assert "-c:v" in cpu_enc
    assert "libx264" in cpu_enc

    fake_gpu_cmd = [
        "ffmpeg", "-y", "-hwaccel", "cuda", "-i", "in.mp4",
        "-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr",
        "-cq", "20", "-b:v", "0", "-maxrate", "8M", "-bufsize", "16M",
        "out.mp4"
    ]
    fallback_cmd = convert_ffmpeg_cmd_to_cpu(fake_gpu_cmd, preset_cpu="veryfast", crf=20)
    assert "-hwaccel" not in fallback_cmd
    assert "h264_nvenc" not in fallback_cmd
    assert "libx264" in fallback_cmd


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


def test_patch_windows_asyncio_connection_lost():
    patch_windows_asyncio_connection_lost()
    if os.name == "nt":
        from asyncio.proactor_events import _ProactorBasePipeTransport
        import asyncio
        assert getattr(_ProactorBasePipeTransport, "_viralcut_patched_10054", False) is True
        assert getattr(asyncio.BaseEventLoop, "_viralcut_patched_10054", False) is True

