"""
core/runtime_env.py — Detecção Automática de Ambiente de Execução (Local Windows vs Google Colab / Cloud / Linux).
Garante que download de vídeos (yt-dlp/FFmpeg), reprodução de mídia (streaming) e acesso a arquivos/pastas
funcionem de forma 100% transparente e sem intervenção manual do operador em qualquer ambiente.
"""

import os
import re
import sys
import shutil
import zipfile
import io
import platform
import subprocess
import urllib.request
import json
from typing import Dict, Any, List, Optional
import imageio_ffmpeg


def is_colab_env() -> bool:
    """Retorna True se estiver executando dentro do Google Colab."""
    if "google.colab" in sys.modules:
        return True
    if os.environ.get("COLAB_GPU") is not None or os.environ.get("COLAB_RELEASE_TAG") is not None:
        return True
    if os.path.exists("/content") and os.name != "nt":
        return True
    return False


def is_linux_or_cloud_env() -> bool:
    """Retorna True se estiver em Linux, Docker, WSL ou ambiente de nuvem (como Google Colab)."""
    if is_colab_env():
        return True
    if os.name != "nt" or platform.system().lower() != "windows":
        return True
    return False


def is_remote_browser_session() -> bool:
    """
    Detecta automaticamente se o operador está acessando a interface via navegador remoto / túnel
    (ex: Google Colab, Cloudflare Tunnel, LocalTunnel, Ngrok, servidor remoto) ou localmente na mesma máquina.
    """
    if is_linux_or_cloud_env():
        return True

    try:
        import streamlit as st
        ctx = getattr(st, "context", None)
        headers = getattr(ctx, "headers", None) if ctx else None
        if headers:
            host = str(headers.get("Host") or headers.get("host") or headers.get("X-Forwarded-Host") or "").lower()
            if host and not host.startswith(("localhost", "127.0.0.1", "[::1]")):
                return True
    except Exception:
        pass

    return False


def get_preferred_compute_device(saved_preference: str = "cuda") -> str:
    """
    Detecta automaticamente se a GPU CUDA está disponível no ambiente atual (Local ou Colab).
    Se 'cuda' estiver selecionado mas o runtime atual não tiver GPU ativa, faz fallback transparente para 'cpu'.
    """
    try:
        import torch
        has_cuda = bool(torch.cuda.is_available())
    except Exception:
        has_cuda = False

    if saved_preference == "cuda" and not has_cuda:
        return "cpu"
    return saved_preference if saved_preference in ("cuda", "cpu") else ("cuda" if has_cuda else "cpu")


def ensure_ffmpeg_environment() -> str:
    """
    Resolve e prepara o executável FFmpeg ideal para o sistema operacional atual (Windows ou Linux/Colab).
    - No Linux/Colab: prioriza o ffmpeg completo do sistema (/usr/bin/ffmpeg, que já acompanha ffprobe)
      e garante que também exista um binário 'ffmpeg' sem extensão no diretório do imageio_ffmpeg.
    - No Windows: garante o alias 'ffmpeg.exe' no diretório do imageio_ffmpeg.
    Retorna o caminho absoluto do executável FFmpeg.
    """
    img_ffmpeg = None
    try:
        img_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        img_ffmpeg = None

    if img_ffmpeg and os.path.exists(img_ffmpeg):
        ff_dir = os.path.dirname(os.path.abspath(img_ffmpeg))
        alias_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        alias_path = os.path.join(ff_dir, alias_name)
        if not os.path.exists(alias_path):
            try:
                if os.name != "nt":
                    try:
                        os.symlink(img_ffmpeg, alias_path)
                    except Exception:
                        shutil.copy2(img_ffmpeg, alias_path)
                        os.chmod(alias_path, 0o755)
                else:
                    shutil.copy2(img_ffmpeg, alias_path)
            except Exception:
                pass

        cur_path = os.environ.get("PATH", "")
        if ff_dir not in cur_path:
            os.environ["PATH"] = ff_dir + os.pathsep + cur_path

    # Em Linux/Colab, se /usr/bin/ffmpeg existir (possui ffprobe junto), prioriza-o
    if os.name != "nt":
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg and os.path.exists(sys_ffmpeg):
            return sys_ffmpeg

    if img_ffmpeg and os.path.exists(img_ffmpeg):
        return img_ffmpeg

    return shutil.which("ffmpeg") or "ffmpeg"


def get_js_runtimes_config() -> Dict[str, Dict[str, str]]:
    """
    Detecta automaticamente runtimes JavaScript (Deno ou Node.js) tanto no Windows quanto no Linux/Colab
    para que o yt-dlp possa resolver desafios de assinatura (n-sig / cipher) do YouTube.
    """
    runtimes: Dict[str, Dict[str, str]] = {}

    deno_candidates = [
        shutil.which("deno"),
        os.path.expanduser("~/.deno/bin/deno.exe" if os.name == "nt" else "~/.deno/bin/deno"),
    ]
    for d_path in deno_candidates:
        if d_path and os.path.exists(d_path):
            runtimes["deno"] = {"path": d_path}
            break

    node_candidates = [
        shutil.which("node"),
        "/usr/bin/node",
        "/usr/local/bin/node",
        r"C:\Program Files\nodejs\node.exe",
    ]
    for n_path in node_candidates:
        if n_path and os.path.exists(n_path):
            runtimes["node"] = {"path": n_path}
            break

    return runtimes


def get_youtube_client_Strategies() -> List[List[str]]:
    """
    Retorna a ordem de perfis de cliente (player_client) do YouTube conforme o ambiente:
    - No Google Colab / Cloud (IP de Datacenter): prioriza clientes ('android_vr', 'tv_embedded', 'ios', 'mweb')
      que contornam restrições de IP de datacenter e entregam streams diretos sem bloqueio HTTP 403.
    - No Desktop Local (IP Residencial): prioriza 'web' e 'ios' com fallback completo.
    """
    if is_linux_or_cloud_env():
        return [
            ["android_vr", "tv_embedded", "ios", "mweb"],
            ["ios", "android_vr", "web_embedded"],
            ["tv_embedded", "mweb", "web"],
            ["android", "web"],
        ]
    return [
        ["web", "ios"],
        ["android_vr", "tv_embedded", "ios"],
        ["android", "web"],
    ]


def get_youtube_extractor_args_list(is_live: bool = False) -> List[Dict[str, Any]]:
    """
    Retorna lista de dicionários `extractor_args` progressivos para yt-dlp.
    Inclui tentativa com `player_skip=['webpage', 'configs']` para evitar bloqueio de HTML watch page em IPs de nuvem.
    """
    if is_live:
        return [
            {"youtube": {"player_client": ["web", "ios", "tv_embedded"]}},
            {"youtube": {"player_client": ["ios", "mweb"], "player_skip": ["webpage", "configs"]}},
        ]

    strategies = get_youtube_client_Strategies()
    out: List[Dict[str, Any]] = []
    if is_linux_or_cloud_env():
        # Em nuvem/Colab, pular a webpage HTML evita o captcha de datacenter do YouTube na chamada Innertube
        out.append({
            "youtube": {
                "player_client": ["android_vr", "tv_embedded", "ios"],
                "player_skip": ["webpage", "configs"],
            }
        })
    for strat in strategies:
        out.append({"youtube": {"player_client": strat}})
    if not is_linux_or_cloud_env():
        out.append({
            "youtube": {
                "player_client": ["android_vr", "tv_embedded", "ios"],
                "player_skip": ["webpage", "configs"],
            }
        })
    return out


def download_youtube_via_public_mirrors(
    url: str,
    output_path: str,
    ffmpeg_exe: Optional[str] = None,
    start_sec: Optional[float] = None,
    end_sec: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Fallback automático de contingência para quando o IP de datacenter (ex: Google Colab)
    sofre bloqueio severo direto do YouTube e não há cookies configurados.
    Consulta APIs públicas espelho (Piped / Invidious) para obter a URL direta do stream e gravar via FFmpeg.
    """
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([A-Za-z0-9_-]{11})", str(url))
    if not m:
        return {"path": None, "error": "ID do YouTube não identificado para fallback."}

    yt_id = m.group(1)
    ff_bin = ffmpeg_exe or ensure_ffmpeg_environment()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }

    piped_instances = [
        f"https://pipedapi.kavin.rocks/streams/{yt_id}",
        f"https://api.piped.private.coffee/streams/{yt_id}",
        f"https://pipedapi.tokhmi.xyz/streams/{yt_id}",
    ]
    invidious_instances = [
        f"https://inv.nadeko.net/api/v1/videos/{yt_id}",
        f"https://yewtu.be/api/v1/videos/{yt_id}",
        f"https://invidious.nerdvpn.de/api/v1/videos/{yt_id}",
    ]

    def _run_ffmpeg_dl(v_url: str, a_url: Optional[str] = None) -> bool:
        cmd = [ff_bin, "-y"]
        if start_sec is not None and start_sec > 0:
            cmd.extend(["-ss", f"{float(start_sec):.3f}"])
        cmd.extend(["-i", v_url])
        if a_url:
            if start_sec is not None and start_sec > 0:
                cmd.extend(["-ss", f"{float(start_sec):.3f}"])
            cmd.extend(["-i", a_url])
        if end_sec is not None and end_sec > (start_sec or 0):
            dur = float(end_sec) - float(start_sec or 0.0)
            cmd.extend(["-t", f"{dur:.3f}"])
        if a_url:
            cmd.extend(["-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", output_path])
        else:
            cmd.extend(["-c", "copy", "-movflags", "+faststart", output_path])
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10240

    # 1. Tenta instâncias Piped
    for api_url in piped_instances:
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            v_streams = [s for s in data.get("videoStreams", []) if s.get("url") and not s.get("videoOnly", True)]
            if v_streams:
                v_streams.sort(key=lambda x: int(x.get("height") or 0), reverse=True)
                if _run_ffmpeg_dl(v_streams[0]["url"]):
                    return {"path": output_path, "error": None}
            v_only = [s for s in data.get("videoStreams", []) if s.get("url") and s.get("videoOnly", False) and int(s.get("height") or 0) <= 1080]
            a_only = [s for s in data.get("audioStreams", []) if s.get("url")]
            if v_only and a_only:
                v_only.sort(key=lambda x: int(x.get("height") or 0), reverse=True)
                a_only.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
                if _run_ffmpeg_dl(v_only[0]["url"], a_only[0]["url"]):
                    return {"path": output_path, "error": None}
        except Exception:
            continue

    # 2. Tenta instâncias Invidious
    for api_url in invidious_instances:
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            fmt_streams = [s for s in data.get("formatStreams", []) if s.get("url")]
            if fmt_streams:
                fmt_streams.sort(key=lambda x: int(str(x.get("resolution", "0")).replace("p", "") or 0), reverse=True)
                if _run_ffmpeg_dl(fmt_streams[0]["url"]):
                    return {"path": output_path, "error": None}
        except Exception:
            continue

    return {"path": None, "error": "Mirrors indisponíveis"}


def build_directory_zip_bytes(folder_path: str) -> bytes:
    """
    Compacta uma pasta de corte/projeto em memória (ZIP) para download direto pelo navegador
    quando a aplicação estiver rodando remotamente (ex: Google Colab).
    """
    buf = io.BytesIO()
    abs_root = os.path.abspath(folder_path)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isfile(abs_root):
            zf.write(abs_root, arcname=os.path.basename(abs_root))
        elif os.path.isdir(abs_root):
            for root, _, files in os.walk(abs_root):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, abs_root)
                    zf.write(full_p, arcname=rel_p)
    buf.seek(0)
    return buf.getvalue()
