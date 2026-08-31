import yt_dlp
import os
import re
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_DIR = os.path.dirname(FFMPEG_EXE)
current_path = os.environ.get("PATH", "")
if FFMPEG_DIR and os.path.exists(FFMPEG_DIR) and FFMPEG_DIR not in current_path:
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + current_path


def get_cookie_file():
    """Retorna o caminho de um arquivo de cookies se presente (cookies.txt ou instagram_cookies.txt)."""
    candidates = [
        os.path.join("data", "cookies.txt"),
        os.path.join("data", "instagram_cookies.txt"),
        "cookies.txt",
        "instagram_cookies.txt"
    ]
    for c in candidates:
        if os.path.exists(c) and os.path.getsize(c) > 10:
            return os.path.abspath(c)
    return None


def get_video_id(url: str) -> str:
    """
    Extrai identificador único para vídeos do YouTube, Instagram, TikTok, Twitter/X, arquivos locais e web.
    """
    if not url:
        return None
    url_str = str(url).strip()
    if url_str.startswith('local://'):
        return url_str.replace('local://', '')
    if url_str.startswith('local_'):
        return url_str
    if url_str.startswith(('ig_', 'tt_', 'tw_', 'fb_', 'web_')):
        return url_str

    from urllib.parse import urlparse, parse_qs
    import hashlib

    query = urlparse(url_str)
    host = (query.hostname or '').lower()

    # YouTube (Watch, Shorts, Live, Embed, YouTu.be)
    if host in ('youtu.be', 'www.youtu.be'):
        return query.path.lstrip('/')
    if host in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        if query.path == '/watch':
            return parse_qs(query.query).get('v', [None])[0]
        if query.path.startswith(('/embed/', '/v/', '/shorts/', '/live/')):
            parts = [p for p in query.path.split('/') if p]
            return parts[1] if len(parts) > 1 else parts[0]

    # Instagram (Reels, Posts, TV, Stories, Share links)
    if 'instagram.com' in host or 'instagr.am' in host:
        m = re.search(r'/(?:reel|reels|p|tv|share/reel)/([A-Za-z0-9_-]+)', query.path)
        if m:
            return f"ig_{m.group(1)}"
        clean_path = query.path.strip('/').replace('/', '_')
        if clean_path:
            return f"ig_{clean_path}"
        return f"ig_{hashlib.md5(url_str.encode()).hexdigest()[:10]}"

    # TikTok
    if 'tiktok.com' in host:
        m = re.search(r'/(?:video|v)/(\d+)', query.path)
        if m:
            return f"tt_{m.group(1)}"
        m2 = re.search(r'/t/([A-Za-z0-9_-]+)', query.path)
        if m2:
            return f"tt_{m2.group(1)}"
        return f"tt_{hashlib.md5(url_str.encode()).hexdigest()[:10]}"

    # Twitter / X
    if host in ('twitter.com', 'www.twitter.com', 'x.com', 'www.x.com'):
        m = re.search(r'/status/(\d+)', query.path)
        if m:
            return f"tw_{m.group(1)}"
        return f"tw_{hashlib.md5(url_str.encode()).hexdigest()[:10]}"

    # Pasta local existente em data/
    if os.path.exists(os.path.join("data", url_str)):
        return url_str

    # Qualquer outra URL web válida (Facebook, Vimeo, Rumble, etc.)
    if url_str.startswith(('http://', 'https://')):
        return f"web_{hashlib.md5(url_str.encode()).hexdigest()[:10]}"

    return None


def get_video_metadata(url: str):
    """
    Extrai metadados, heatmaps e status de transmissão ao vivo de vídeos do YouTube, Instagram, TikTok e web.
    """
    cookie_file = get_cookie_file()
    
    options_list = [
        {'quiet': True, 'no_warnings': True},
        {'quiet': True, 'no_warnings': True, 'extractor_args': {'youtube': {'player_client': ['android', 'web']}}},
        {'quiet': True, 'no_warnings': True, 'live_from_start': True},
    ]

    # Se houver cookies disponíveis, injeta como primeira opção
    if cookie_file:
        options_list.insert(0, {'quiet': True, 'no_warnings': True, 'cookiefile': cookie_file})

    last_error = None
    for ydl_opts in options_list:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                heatmap = info.get('heatmap')
                title = info.get('title') or info.get('description', '')[:80] or "Vídeo da Web"
                duration = info.get('duration')
                upload_date = info.get('upload_date')
                thumbnail = info.get('thumbnail')
                uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id') or "Perfil / Canal"
                webpage_url = info.get('webpage_url') or url
                
                # Detecção de Live Stream / Transmissão ao Vivo
                live_status = info.get('live_status') or ('is_live' if info.get('is_live') else 'not_live')
                is_live = bool(info.get('is_live') or (live_status == 'is_live'))
                was_live = bool(info.get('was_live') or (live_status in ('was_live', 'post_live')))

                return {
                    "title": title,
                    "heatmap": heatmap,
                    "duration": duration,
                    "upload_date": upload_date,
                    "thumbnail": thumbnail,
                    "channel": uploader,
                    "url": webpage_url,
                    "is_live": is_live,
                    "was_live": was_live,
                    "live_status": live_status,
                    "error": None
                }
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "title": None,
        "heatmap": None,
        "duration": None,
        "upload_date": None,
        "thumbnail": None,
        "channel": None,
        "url": url,
        "is_live": False,
        "was_live": False,
        "live_status": "not_live",
        "error": last_error or "Erro ao extrair metadados do vídeo"
    }


def download_audio(url: str, output_path: str = "temp_audio.mp3", is_live: bool = False):
    """
    Baixa o áudio de um vídeo do YouTube, Instagram, TikTok ou Web com aceleração multi-thread.
    """
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    cookie_file = get_cookie_file()

    base_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[protocol=https]/bestaudio/best',
        'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
        'ffmpeg_location': ffmpeg_path,
        'concurrent_fragment_downloads': 16,
        'http_chunk_size': 10485760,  # 10MB chunk size
        'buffersize': 1048576,        # 1MB buffer
        'retries': 10,
        'fragment_retries': 10,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    if cookie_file:
        base_opts['cookiefile'] = cookie_file

    attempts = [
        dict(base_opts),
        dict(base_opts, live_from_start=True, hls_use_mpegts=True)
    ]
    if is_live:
        attempts.reverse()

    last_err = None
    for ydl_opts in attempts:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return {"path": output_path, "error": None}
        except Exception as e:
            last_err = str(e)
            continue

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return {"path": output_path, "error": None}
    return {"path": None, "error": last_err or "Falha ao baixar áudio"}
