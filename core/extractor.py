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
                track_name = info.get('track')
                artist_name = info.get('artist') or info.get('creator')
                album_name = info.get('album')
                genre_name = info.get('genre')
                
                # Detecção de Live Stream / Transmissão ao Vivo
                live_status = info.get('live_status') or ('is_live' if info.get('is_live') else 'not_live')
                is_live = bool(info.get('is_live') or (live_status == 'is_live'))
                was_live = bool(info.get('was_live') or (live_status in ('was_live', 'post_live')))

                # Identificação inteligente do nome da música
                clean_track_title = clean_music_title(title, artist=artist_name, track=track_name)
                suggested_cat_label, suggested_cat_key = detect_music_category_suggestion(clean_track_title or title)

                return {
                    "title": title,
                    "clean_music_title": clean_track_title,
                    "artist": artist_name,
                    "track": track_name,
                    "album": album_name,
                    "genre": genre_name,
                    "suggested_category_label": suggested_cat_label,
                    "suggested_category_key": suggested_cat_key,
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
        "clean_music_title": None,
        "artist": None,
        "track": None,
        "album": None,
        "genre": None,
        "suggested_category_label": "🎵 Trilha Personalizada",
        "suggested_category_key": "custom",
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


def clean_music_title(raw_title: str, artist: str = None, track: str = None) -> str:
    """
    Limpa títulos de músicas removendo ruídos de clipes e tags comuns do YouTube/TikTok.
    Ex: 'Kordhell - Murder In My Mind (Official Music Video) [4K]' -> 'Kordhell - Murder In My Mind'
    """
    if track and artist:
        return f"{artist.strip()} - {track.strip()}"
    if track:
        return track.strip()
    
    t = raw_title or "Trilha Sonora"
    patterns_to_remove = [
        r'\[official\s+(?:music\s+)?video\]',
        r'\(official\s+(?:music\s+)?video\)',
        r'\[official\s+audio\]',
        r'\(official\s+audio\)',
        r'\[audio\s+oficial\]',
        r'\(audio\s+oficial\)',
        r'\[clipe\s+oficial\]',
        r'\(clipe\s+oficial\)',
        r'\[video\s+oficial\]',
        r'\(video\s+oficial\)',
        r'\[hd\]', r'\(hd\)',
        r'\[4k\]', r'\(4k\)',
        r'\[lyrics\]', r'\(lyrics\)',
        r'\[letra\]', r'\(letra\)',
        r'\[visualizer\]', r'\(visualizer\)',
        r'\(slowed\s*\+\s*reverb\)',
        r'\[slowed\s*\+\s*reverb\]',
        r'\[prod\.\s*by\s*[^\]]+\]',
        r'\(prod\.\s*by\s*[^\)]+\)',
        r'\[free\]', r'\(free\)',
        r'\|\s*tiktok\s*(?:sound|trend|viral)?',
        r'#shorts', r'#viral', r'#tiktok'
    ]
    for pat in patterns_to_remove:
        t = re.sub(pat, '', t, flags=re.IGNORECASE)
    
    t = re.sub(r'\s+', ' ', t).strip(' -_[]()|')
    return t or raw_title


def detect_music_category_suggestion(title_text: str) -> tuple:
    """Sugere a categoria/vibe do som baseado em palavras-chave no título."""
    txt = (title_text or "").lower()
    if any(k in txt for k in ["phonk", "drift", "sigma", "gym", "workout", "brazilian phonk", "montagem"]):
        return "⚡ Phonk / Superação & Força", "phonk_power_override"
    if any(k in txt for k in ["rock", "metal", "guitar", "heavy", "punk", "overdrive", "riff"]):
        return "🎸 Heavy Rock / Adrenalina", "heavy_rock_overdrive"
    if any(k in txt for k in ["meme", "funny", "comedy", "engraçado", "comedia", "risada", "cartoon", "troll", "laugh"]):
        return "🎭 Cômico / Meme & Humor", "comedy_meme_funny"
    if any(k in txt for k in ["epic", "cinematic", "glory", "soundtrack", "trailer", "orchestra", "hans zimmer", "two steps", "épico"]):
        return "🏆 Épico / Glória & Inspiração", "epic_hype_glory"
    if any(k in txt for k in ["lofi", "lo-fi", "chill", "relax", "study", "calm", "suave"]):
        return "🧘 Lo-Fi Chill / Relax", "lofi_chill"
    if any(k in txt for k in ["suspense", "tension", "dark", "mystery", "terror", "drama", "tensão"]):
        return "🔥 Tensão / Suspense", "tension_suspense"
    return "🎵 Trilha Personalizada", "custom"


def parse_time_str(time_input) -> float | None:
    """
    Converte strings de tempo em segundos (float).
    Suporta:
      - '01:15:30' -> 4530.0
      - '15:30' -> 930.0
      - '90' ou '90.5' -> 90.5
      - '1h30m' ou '1h 30m 10s' -> 5410.0
      - 120 (número) -> 120.0
    Retorna None se inválido ou vazio.
    """
    if time_input is None:
        return None
    if isinstance(time_input, (int, float)):
        return float(time_input) if time_input >= 0 else None
    
    t_str = str(time_input).strip().lower()
    if not t_str:
        return None
    
    # Formato com sufixos: 1h30m15s, 1h 30m, 45m, 30s
    if any(unit in t_str for unit in ['h', 'm', 's']):
        h_match = re.search(r'(\d+(?:\.\d+)?)\s*h', t_str)
        m_match = re.search(r'(\d+(?:\.\d+)?)\s*m', t_str)
        s_match = re.search(r'(\d+(?:\.\d+)?)\s*s', t_str)
        total = 0.0
        found = False
        if h_match:
            total += float(h_match.group(1)) * 3600.0
            found = True
        if m_match:
            total += float(m_match.group(1)) * 60.0
            found = True
        if s_match:
            total += float(s_match.group(1))
            found = True
        if found:
            return total

    # Formato HH:MM:SS ou MM:SS ou SS
    parts = t_str.split(':')
    try:
        if len(parts) == 3:
            h = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return h * 3600.0 + m * 60.0 + s
        elif len(parts) == 2:
            m = float(parts[0])
            s = float(parts[1])
            return m * 60.0 + s
        elif len(parts) == 1:
            return float(parts[0])
    except (ValueError, TypeError):
        pass

    return None


def format_time_sec(seconds: float) -> str:
    """Formata segundos em formato legível HH:MM:SS ou MM:SS."""
    if seconds is None or seconds < 0:
        return "00:00"
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def format_elapsed_time(seconds: float) -> str:
    """Formata tempo decorrido com precisão amigável (ex: '4.2s', '1m 23s', '13m 16s')."""
    if seconds is None or seconds < 0:
        return "0.0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"


def download_audio(
    url: str,
    output_path: str = "temp_audio.mp3",
    is_live: bool = False,
    start_sec: float = None,
    end_sec: float = None
):
    """
    Baixa o áudio de um vídeo do YouTube, Instagram, TikTok ou Web com aceleração multi-thread
    e suporte a download parcial por intervalo de tempo (Time-Range Slicing).
    """
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    cookie_file = get_cookie_file()

    base_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[protocol=https]/bestaudio/best',
        'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
        'ffmpeg_location': os.path.dirname(ffmpeg_path) if ffmpeg_path else None,
        'extractor_args': {'youtube': {'player_client': ['web', 'android']}},
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

    # Se um intervalo de tempo foi especificado, aplica download seletivo de seções
    s_parsed = parse_time_str(start_sec)
    e_parsed = parse_time_str(end_sec)
    if s_parsed is not None or e_parsed is not None:
        try:
            from yt_dlp.utils import download_range_func
            s_val = s_parsed if s_parsed is not None and s_parsed >= 0 else 0.0
            e_val = e_parsed if e_parsed is not None and e_parsed > s_val else None
            base_opts['download_ranges'] = download_range_func(None, [(s_val, e_val)])
            base_opts['force_keyframes_at_cuts'] = False
        except Exception:
            pass

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
