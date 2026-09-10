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
    
    common_flags = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'playlist_items': '1',
        'ignoreerrors': True
    }

    options_list = [
        dict(common_flags),
        dict(common_flags, extractor_args={'youtube': {'player_client': ['android', 'web']}}),
        dict(common_flags, live_from_start=True),
    ]

    # Se houver cookies disponíveis, injeta como primeira opção
    if cookie_file:
        options_list.insert(0, dict(common_flags, cookiefile=cookie_file))

    last_error = None
    for ydl_opts in options_list:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    continue

                # Se for playlist ou artigo com múltiplos vídeos (ex: Globo/G1, UOL, etc.),
                # seleciona a entrada principal (primeiro item) para obter metadados reais
                target = info
                if info.get('_type') == 'playlist' or 'entries' in info:
                    entries = [e for e in info.get('entries', []) if e]
                    if entries:
                        target = entries[0]

                heatmap = target.get('heatmap') or info.get('heatmap')
                title = target.get('title') or info.get('title') or target.get('description', '')[:80] or info.get('description', '')[:80] or "Vídeo da Web"
                duration = target.get('duration') or info.get('duration')
                upload_date = target.get('upload_date') or info.get('upload_date')
                thumbnail = target.get('thumbnail') or info.get('thumbnail')
                uploader = target.get('uploader') or target.get('channel') or target.get('uploader_id') or info.get('uploader') or info.get('channel') or "Perfil / Canal"
                webpage_url = target.get('webpage_url') or info.get('webpage_url') or url
                track_name = target.get('track') or info.get('track')
                artist_name = target.get('artist') or target.get('creator') or info.get('artist')
                album_name = target.get('album') or info.get('album')
                genre_name = target.get('genre') or info.get('genre')
                
                # Detecção de Live Stream / Transmissão ao Vivo
                live_status = target.get('live_status') or info.get('live_status') or ('is_live' if (target.get('is_live') or info.get('is_live')) else 'not_live')
                is_live = bool(target.get('is_live') or info.get('is_live') or (live_status == 'is_live'))
                was_live = bool(target.get('was_live') or info.get('was_live') or (live_status in ('was_live', 'post_live')))

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


def download_live_audio_snapshot(
    url: str,
    output_path: str = "temp_audio.mp3",
    start_sec: float = None,
    end_sec: float = None
) -> dict:
    """
    Baixa snapshot do áudio de uma transmissão ao vivo (live stream) em andamento em alta velocidade.
    Em vez de travar o downloader aguardando novos fragmentos em tempo real indefinidamente,
    captura a playlist HLS até o instante atual, injeta a terminação '#EXT-X-ENDLIST' e 
    converte diretamente via FFmpeg multithread para MP3 192kbps com suporte a Time-Range Slicing.
    """
    import urllib.request
    import subprocess
    import tempfile

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cookie_file = get_cookie_file()

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'playlist_items': '1',
    }
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return {"path": None, "error": "Falha ao extrair metadados da transmissão ao vivo"}

            if info.get('_type') == 'playlist' or 'entries' in info:
                entries = [e for e in info.get('entries', []) if e]
                if entries:
                    info = entries[0]

            formats = info.get('formats', [])
            aud_formats = [
                f for f in formats
                if f.get('vcodec') == 'none' and f.get('protocol') in ('m3u8_native', 'm3u8', 'http_dash_segments_generator')
            ]

            target_stream_url = None
            if aud_formats:
                target_stream_url = aud_formats[-1].get('url')

            if not target_stream_url:
                for f in formats:
                    if f.get('protocol') in ('m3u8_native', 'm3u8') and f.get('url'):
                        target_stream_url = f.get('url')
                        break

            if not target_stream_url and info.get('manifest_url'):
                target_stream_url = info.get('manifest_url')

            if not target_stream_url:
                return {"path": None, "error": "Nenhum stream HLS ao vivo encontrado para extração de snapshot"}

            m3u8_text = None
            try:
                req = urllib.request.Request(
                    target_stream_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    m3u8_text = resp.read().decode('utf-8', errors='ignore')
            except Exception:
                m3u8_text = None

            temp_m3u8_path = None
            input_source = target_stream_url

            if m3u8_text and ('#EXTM3U' in m3u8_text or '#EXTINF' in m3u8_text):
                if '#EXT-X-ENDLIST' not in m3u8_text:
                    m3u8_text = m3u8_text.strip() + '\n#EXT-X-ENDLIST\n'

                out_dir = os.path.dirname(output_path) or '.'
                os.makedirs(out_dir, exist_ok=True)
                temp_fd, temp_m3u8_path = tempfile.mkstemp(suffix='_live_snap.m3u8', dir=out_dir)
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f_snap:
                    f_snap.write(m3u8_text)
                input_source = temp_m3u8_path

            out_dir = os.path.dirname(os.path.abspath(output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass

            s_parsed = parse_time_str(start_sec)
            e_parsed = parse_time_str(end_sec)

            cmd = [
                ffmpeg_exe, '-y',
                '-protocol_whitelist', 'file,http,https,tcp,tls',
            ]
            if s_parsed is not None and s_parsed > 0:
                cmd.extend(['-ss', str(s_parsed)])

            cmd.extend(['-i', input_source])

            if e_parsed is not None:
                dur = (e_parsed - (s_parsed or 0.0)) if (s_parsed and e_parsed > s_parsed) else e_parsed
                if dur > 0:
                    cmd.extend(['-t', str(dur)])

            cmd.extend([
                '-vn',
                '-c:a', 'libmp3lame',
                '-b:a', '192k',
                output_path
            ])

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if temp_m3u8_path and os.path.exists(temp_m3u8_path):
                try:
                    os.remove(temp_m3u8_path)
                except Exception:
                    pass

            if os.path.exists(output_path) and os.path.getsize(output_path) > 10240:
                return {"path": output_path, "error": None}
            else:
                err_msg = proc.stderr[-400:] if proc.stderr else "Erro ao converter áudio da live via FFmpeg"
                return {"path": None, "error": err_msg}

    except Exception as e:
        return {"path": None, "error": str(e)}


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
    Para transmissões ao vivo (is_live=True), aciona o motor de Live Snapshot M3U8 para captura
    ultra-rápida sem ficar preso em loops de streaming contínuo.
    """
    # 🔴 Para transmissões ao vivo, aciona o snapshot M3U8 de alta velocidade
    if is_live:
        snap_res = download_live_audio_snapshot(
            url=url,
            output_path=output_path,
            start_sec=start_sec,
            end_sec=end_sec
        )
        if snap_res.get("path") and os.path.exists(snap_res["path"]):
            return snap_res

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    cookie_file = get_cookie_file()

    # Sanitização de extractor_args: nunca usar cliente android em lives
    ext_args = {'youtube': {'player_client': ['web']}} if is_live else {'youtube': {'player_client': ['web', 'android']}}

    base_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[protocol=https]/bestaudio/best',
        'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
        'ffmpeg_location': os.path.dirname(ffmpeg_path) if ffmpeg_path else None,
        'extractor_args': ext_args,
        'concurrent_fragment_downloads': 16,
        'http_chunk_size': 10485760,  # 10MB chunk size
        'buffersize': 1048576,        # 1MB buffer
        'retries': 10,
        'fragment_retries': 10,
        'noplaylist': True,
        'playlist_items': '1',
        'ignoreerrors': True,
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
            # Se o áudio principal já foi baixado com sucesso (> 10KB), não precisa retentar
            if os.path.exists(output_path) and os.path.getsize(output_path) > 10240:
                return {"path": output_path, "error": None}
            continue

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return {"path": output_path, "error": None}
    return {"path": None, "error": last_err or "Falha ao baixar áudio"}


def get_video_components_status(video_id: str, data_dir: str = "data", remote_duration: float = None) -> dict:
    """
    Analisa os arquivos locais do vídeo em data/<video_id> e retorna um diagnóstico
    completo e estruturado dos componentes existentes e faltantes.
    """
    import json
    v_dir = os.path.join(data_dir, video_id) if video_id else None
    res = {
        "video_id": video_id,
        "exists_dir": bool(v_dir and os.path.isdir(v_dir)),
        "has_audio": False,
        "audio_size_mb": 0.0,
        "has_transcript": False,
        "segments_count": 0,
        "first_transcript_sec": None,
        "last_transcript_sec": None,
        "has_video": False,
        "video_size_mb": 0.0,
        "video_resolution": None,
        "has_ai_analysis": False,
        "pautas_count": 0,
        "shorts_count": 0,
        "is_live": False,
        "missing_components": [],
        "new_minutes_available": 0.0,
        "can_process_incrementally": False
    }
    if not res["exists_dir"]:
        res["missing_components"] = ["audio", "transcript", "video", "ai_analysis"]
        return res

    # 1. Metadados
    meta_file = os.path.join(v_dir, "metadata.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                res["is_live"] = bool(meta.get("is_live"))
                if not remote_duration:
                    remote_duration = meta.get("duration") or meta.get("duration_sec")
        except Exception:
            pass

    # 2. Áudio
    audio_path = os.path.join(v_dir, "audio.mp3")
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 10240:
        res["has_audio"] = True
        res["audio_size_mb"] = round(os.path.getsize(audio_path) / (1024 * 1024), 2)
    else:
        res["missing_components"].append("audio")

    # 3. Transcrição
    tr_path = os.path.join(v_dir, "transcript.json")
    if os.path.exists(tr_path) and os.path.getsize(tr_path) > 10:
        try:
            with open(tr_path, "r", encoding="utf-8") as f:
                tr_data = json.load(f)
                segs = tr_data.get("segments", [])
                if segs:
                    res["has_transcript"] = True
                    res["segments_count"] = len(segs)
                    res["first_transcript_sec"] = float(segs[0].get("start", 0.0))
                    res["last_transcript_sec"] = float(segs[-1].get("end", 0.0))
        except Exception:
            pass
    if not res["has_transcript"]:
        res["missing_components"].append("transcript")

    # 4. Vídeo
    video_path = os.path.join(v_dir, "video_full.mp4")
    if os.path.exists(video_path) and os.path.getsize(video_path) > 10240:
        res["has_video"] = True
        res["video_size_mb"] = round(os.path.getsize(video_path) / (1024 * 1024), 2)
        try:
            from core.video_processor import get_video_resolution
            res["video_resolution"] = get_video_resolution(video_path)
        except Exception:
            pass
    else:
        res["missing_components"].append("video")

    # 5. IA (Pautas e Shorts)
    pautas_file = os.path.join(v_dir, "pautas.json")
    if os.path.exists(pautas_file):
        try:
            with open(pautas_file, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                res["pautas_count"] = len(p_data.get("pautas", []) if isinstance(p_data, dict) else p_data)
        except Exception:
            pass

    shorts_file = os.path.join(v_dir, "shorts.json")
    if os.path.exists(shorts_file):
        try:
            with open(shorts_file, "r", encoding="utf-8") as f:
                res["shorts_count"] = len(json.load(f))
        except Exception:
            pass

    if res["pautas_count"] > 0 or res["shorts_count"] > 0:
        res["has_ai_analysis"] = True
    else:
        res["missing_components"].append("ai_analysis")

    # 6. Minutos adicionais se for Live
    if res["is_live"] and res["last_transcript_sec"] is not None and remote_duration:
        try:
            diff_sec = float(remote_duration) - float(res["last_transcript_sec"])
            if diff_sec > 60:  # Mais de 1 minuto novo disponível
                res["new_minutes_available"] = round(diff_sec / 60.0, 1)
                res["missing_components"].append("new_live_minutes")
        except Exception:
            pass

    res["can_process_incrementally"] = bool(res["has_transcript"] and len(res["missing_components"]) > 0)
    return res

