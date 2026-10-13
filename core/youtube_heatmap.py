"""
core/youtube_heatmap.py — Mapa de Calor da Audiência do YouTube ("Mais Reproduzidos" / Most Replayed)

O YouTube divide cada vídeo consolidado em ~100 blocos temporais e atribui a cada bloco uma
intensidade normalizada (0.0 → 1.0) baseada em quantas vezes a audiência reassistiu aquele trecho.
Esses dados NÃO estão na API pública (Data API v3) nem são extraídos pelo yt-dlp; eles vêm
embutidos no JSON `ytInitialData` da página de exibição, no nó:

    frameworkUpdates.entityBatchUpdate.mutations[*].payload.macroMarkersListEntity.markersList.markers

Este módulo:
  1. Coleta e normaliza os marcadores (`fetch_youtube_heatmap`) com cache em disco.
  2. Detecta janelas quentes prontas para Shorts/Reels (`find_heatmap_hotspots`).
  3. Alinha as janelas às frases da transcrição Whisper (`snap_hotspot_to_segments`).
  4. Converte as janelas em itens de corte compatíveis com a fila de lote (`build_heatmap_cut_items`).
"""

import os
import re
import json
import time
import urllib.request

from core.frame_capturer import format_seconds_to_time_str

HEATMAP_CACHE_FILENAME = "heatmap.json"
HEATMAP_CACHE_TTL_S = 6 * 3600  # Heatmap muda devagar; 6h evita requisições repetidas

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    # Evita a página intermediária de consentimento de cookies (UE)
    "Cookie": "CONSENT=YES+cb; SOCS=CAI",
}

_VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([0-9A-Za-z_-]{11})")


# ─────────────────────────────────────────────────────────────────────────────
# Coleta
# ─────────────────────────────────────────────────────────────────────────────

def extract_youtube_video_id(url_or_id: str) -> str:
    """Retorna o ID de 11 caracteres a partir de uma URL do YouTube ou do próprio ID."""
    if not url_or_id:
        return ""
    s = str(url_or_id).strip()
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", s):
        return s
    m = _VIDEO_ID_RE.search(s)
    return m.group(1) if m else ""


def extract_initial_data_from_html(html: str) -> dict:
    """Extrai e decodifica o objeto `ytInitialData` do HTML da página de exibição."""
    if not html:
        return {}
    m = re.search(r"ytInitialData\s*=\s*({.+?});\s*</script>", html, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def parse_heatmap_markers(initial_data: dict) -> list:
    """
    Localiza os marcadores de heatmap dentro do `ytInitialData`.
    Retorna lista ordenada de dicts: start_sec, end_sec, duration_sec, intensity (0..1).
    Suporta o formato atual (macroMarkersListEntity) e o legado (heatMarkerRenderer).
    """
    if not isinstance(initial_data, dict):
        return []

    raw_markers = []

    # Formato atual: frameworkUpdates → entityBatchUpdate → mutations
    mutations = (
        initial_data.get("frameworkUpdates", {})
        .get("entityBatchUpdate", {})
        .get("mutations", [])
    ) or []
    for mut in mutations:
        mml = (mut or {}).get("payload", {}).get("macroMarkersListEntity")
        if not mml:
            continue
        markers_list = mml.get("markersList", {}) or {}
        if markers_list.get("markerType", "MARKER_TYPE_HEATMAP") != "MARKER_TYPE_HEATMAP":
            continue
        for mk in markers_list.get("markers", []) or []:
            raw_markers.append((
                mk.get("startMillis"),
                mk.get("durationMillis"),
                mk.get("intensityScoreNormalized", mk.get("heatMarkerIntensityScoreNormalized")),
            ))
        if raw_markers:
            break

    # Formato legado: playerOverlays → ... → heatMarkerRenderer
    if not raw_markers:
        data_s = json.dumps(initial_data)
        for m in re.finditer(r'"heatMarkerRenderer"\s*:\s*({[^{}]+})', data_s):
            try:
                hm = json.loads(m.group(1))
                raw_markers.append((
                    hm.get("timeRangeStartMillis"),
                    hm.get("markerDurationMillis"),
                    hm.get("heatMarkerIntensityScoreNormalized"),
                ))
            except Exception:
                continue

    markers = []
    for s_ms, d_ms, inten in raw_markers:
        try:
            s = float(s_ms or 0) / 1000.0
            d = float(d_ms or 0) / 1000.0
            i = max(0.0, min(1.0, float(inten or 0.0)))
        except (TypeError, ValueError):
            continue
        if d <= 0:
            continue
        markers.append({
            "start_sec": round(s, 3),
            "end_sec": round(s + d, 3),
            "duration_sec": round(d, 3),
            "intensity": round(i, 4),
        })

    markers.sort(key=lambda x: x["start_sec"])
    return markers


def _fetch_watch_page_html(video_id: str, timeout: int = 12) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}&hl=pt-BR"
    req = urllib.request.Request(url, headers=_HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_youtube_heatmap(
    url_or_id: str,
    cache_dir: str = None,
    force_refresh: bool = False,
    timeout: int = 12,
    html_fetcher=None
) -> dict:
    """
    Busca o heatmap "Mais Reproduzidos" de um vídeo do YouTube.

    Retorna:
      {
        "video_id": str,
        "has_heatmap": bool,
        "markers": [ {start_sec, end_sec, duration_sec, intensity}, ... ],
        "fetched_at": float (epoch),
        "source": "cache" | "youtube",
        "error": str | None,
        "reason": str | None   # motivo amigável quando não há heatmap
      }
    """
    video_id = extract_youtube_video_id(url_or_id)
    base = {"video_id": video_id, "has_heatmap": False, "markers": [], "fetched_at": None,
            "source": None, "error": None, "reason": None}

    if not video_id:
        base["error"] = "URL não pertence ao YouTube ou ID do vídeo inválido."
        return base

    cache_path = os.path.join(cache_dir, HEATMAP_CACHE_FILENAME) if cache_dir else None

    # 1. Cache em disco
    if cache_path and not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            age = time.time() - float(cached.get("fetched_at") or 0)
            # Heatmap positivo vale por TTL; ausência é re-checada após 1h (pode ter sido consolidado)
            ttl = HEATMAP_CACHE_TTL_S if cached.get("has_heatmap") else 3600
            if age < ttl and cached.get("video_id") == video_id:
                cached["source"] = "cache"
                cached.setdefault("error", None)
                return cached
        except Exception:
            pass

    # 2. Página de exibição do YouTube
    try:
        fetcher = html_fetcher or _fetch_watch_page_html
        html = fetcher(video_id, timeout) if html_fetcher is None else fetcher(video_id)
    except Exception as exc:
        base["error"] = f"Falha ao acessar o YouTube: {exc}"
        return base

    initial_data = extract_initial_data_from_html(html)
    if not initial_data:
        base["error"] = "Não foi possível ler os dados da página do YouTube (ytInitialData ausente)."
        return base

    markers = parse_heatmap_markers(initial_data)
    result = dict(base)
    result.update({
        "has_heatmap": bool(markers),
        "markers": markers,
        "fetched_at": time.time(),
        "source": "youtube",
    })
    if not markers:
        result["reason"] = (
            "O YouTube ainda não gerou o gráfico 'Mais reproduzidos' para este vídeo "
            "(comum em lives em andamento, vídeos recentes ou com poucas visualizações)."
        )

    if cache_path:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Análise
# ─────────────────────────────────────────────────────────────────────────────

def _marker_at(markers: list, t: float) -> int:
    for i, mk in enumerate(markers):
        if mk["start_sec"] <= t < mk["end_sec"]:
            return i
    return len(markers) - 1


def find_heatmap_hotspots(
    markers: list,
    min_duration: float = 35.0,
    max_duration: float = 90.0,
    top_n: int = 8,
    min_intensity: float = 0.35,
    skip_intro_sec: float = None,
    video_duration: float = None
) -> list:
    """
    Detecta as janelas temporais de maior interesse da audiência.

    Algoritmo (crescimento guloso a partir dos picos):
      1. Ignora o bloco inicial (o 1º bloco quase sempre é 100% por artefato de início do player).
      2. Ordena os blocos por intensidade e, para cada pico ainda não coberto:
         - expande para o vizinho mais quente enquanto a janela < min_duration;
         - continua expandindo enquanto o vizinho mantém ≥ 55% da intensidade do pico
           e a janela < max_duration.
      3. Garante a duração mínima com preenchimento simétrico e descarta sobreposições.

    Retorna lista ordenada por intensidade do pico (rank 1 = mais quente):
      {rank, start_sec, end_sec, duration_sec, peak_sec, peak_intensity, avg_intensity, start, end}
    """
    if not markers:
        return []

    mks = sorted(markers, key=lambda x: x["start_sec"])
    total_end = float(video_duration or mks[-1]["end_sec"])

    if skip_intro_sec is None:
        skip_intro_sec = mks[0]["end_sec"] if len(mks) > 1 else 0.0

    candidates = [
        (i, mk) for i, mk in enumerate(mks)
        if mk["end_sec"] > skip_intro_sec and mk["intensity"] >= min_intensity
    ]
    candidates.sort(key=lambda x: x[1]["intensity"], reverse=True)

    hotspots = []
    covered = []  # lista de (start, end)

    def _overlaps(s, e):
        for cs, ce in covered:
            inter = min(e, ce) - max(s, cs)
            if inter > 0 and inter >= 0.35 * min(e - s, ce - cs):
                return True
        return False

    for peak_idx, peak in candidates:
        if len(hotspots) >= top_n:
            break
        peak_mid = (peak["start_sec"] + peak["end_sec"]) / 2.0
        if any(cs <= peak_mid < ce for cs, ce in covered):
            continue

        lo, hi = peak_idx, peak_idx
        keep_ratio = 0.55

        def _width():
            return mks[hi]["end_sec"] - mks[lo]["start_sec"]

        while True:
            left_ok = lo - 1 >= 0 and mks[lo - 1]["end_sec"] > skip_intro_sec
            right_ok = hi + 1 < len(mks)
            if not left_ok and not right_ok:
                break
            left_i = mks[lo - 1]["intensity"] if left_ok else -1.0
            right_i = mks[hi + 1]["intensity"] if right_ok else -1.0
            best_side = "left" if left_i >= right_i else "right"
            best_val = max(left_i, right_i)

            next_w = (_width() + (mks[lo - 1]["duration_sec"] if best_side == "left" else mks[hi + 1]["duration_sec"]))
            if next_w > max_duration:
                break
            if _width() >= min_duration and best_val < peak["intensity"] * keep_ratio:
                break
            if best_side == "left":
                lo -= 1
            else:
                hi += 1

        start_s = mks[lo]["start_sec"]
        end_s = mks[hi]["end_sec"]

        # Preenchimento simétrico até a duração mínima
        width = end_s - start_s
        if width < min_duration:
            pad = (min_duration - width) / 2.0
            start_s -= pad
            end_s += pad
        if end_s - start_s > max_duration:
            center = peak_mid
            start_s = center - max_duration / 2.0
            end_s = center + max_duration / 2.0

        # Limites do vídeo
        if start_s < 0:
            end_s -= start_s
            start_s = 0.0
        if end_s > total_end:
            start_s -= (end_s - total_end)
            end_s = total_end
        start_s = max(0.0, start_s)

        if _overlaps(start_s, end_s):
            continue

        window_mks = [mk for mk in mks if mk["end_sec"] > start_s and mk["start_sec"] < end_s]
        avg_i = sum(mk["intensity"] for mk in window_mks) / max(1, len(window_mks))

        covered.append((start_s, end_s))
        hotspots.append({
            "start_sec": round(start_s, 2),
            "end_sec": round(end_s, 2),
            "duration_sec": round(end_s - start_s, 2),
            "peak_sec": round(peak_mid, 2),
            "peak_intensity": round(peak["intensity"], 4),
            "avg_intensity": round(avg_i, 4),
        })

    hotspots.sort(key=lambda h: h["peak_intensity"], reverse=True)
    for rank, h in enumerate(hotspots, start=1):
        h["rank"] = rank
        h["start"] = format_seconds_to_time_str(h["start_sec"])
        h["end"] = format_seconds_to_time_str(h["end_sec"])
    return hotspots


def snap_hotspot_to_segments(
    hotspot: dict,
    segments: list,
    max_duration: float = None,
    max_shift_s: float = 8.0
) -> dict:
    """
    Alinha início e fim da janela às fronteiras de frases da transcrição (Whisper/YouTube),
    para que o corte comece numa frase completa e termine com o pensamento concluído.
    Nunca desloca cada borda mais do que `max_shift_s`.
    """
    if not hotspot or not segments:
        return dict(hotspot or {})

    s0 = float(hotspot["start_sec"])
    e0 = float(hotspot["end_sec"])

    segs = sorted(
        [s for s in segments if s is not None and "start" in s and "end" in s],
        key=lambda s: float(s["start"])
    )
    if not segs:
        return dict(hotspot)

    # Início: começo da frase que contém s0 (ou a última frase iniciada antes de s0)
    new_start = s0
    started_before = [float(seg["start"]) for seg in segs if float(seg["start"]) <= s0]
    if started_before and s0 - started_before[-1] <= max_shift_s:
        new_start = started_before[-1]

    # Fim: término da frase que contém e0 (ou a primeira frase que termina após e0)
    new_end = e0
    ending_after = [float(seg["end"]) for seg in segs if float(seg["end"]) >= e0]
    if ending_after and ending_after[0] - e0 <= max_shift_s:
        new_end = ending_after[0]

    if max_duration and new_end - new_start > max_duration + max_shift_s:
        new_end = e0
    if new_end <= new_start:
        new_start, new_end = s0, e0

    snapped = dict(hotspot)
    snapped["start_sec"] = round(new_start, 2)
    snapped["end_sec"] = round(new_end, 2)
    snapped["duration_sec"] = round(new_end - new_start, 2)
    snapped["start"] = format_seconds_to_time_str(new_start)
    snapped["end"] = format_seconds_to_time_str(new_end)
    snapped["snapped_to_transcript"] = True
    return snapped


def get_text_for_range(segments: list, start_s: float, end_s: float, max_chars: int = 220) -> str:
    """Concatena o texto da transcrição dentro do intervalo (para snippet e títulos)."""
    if not segments:
        return ""
    parts = [
        str(seg.get("text", "")).strip()
        for seg in segments
        if float(seg.get("end", 0)) > start_s and float(seg.get("start", 0)) < end_s
    ]
    text = " ".join(p for p in parts if p)
    return (text[:max_chars].rsplit(" ", 1)[0] + "...") if len(text) > max_chars else text


def intensity_label(intensity: float) -> str:
    """Rótulo amigável de calor."""
    i = float(intensity or 0)
    if i >= 0.85:
        return "🔥🔥🔥 Pico Máximo"
    if i >= 0.60:
        return "🔥🔥 Muito Quente"
    if i >= 0.40:
        return "🔥 Quente"
    return "🌡️ Morno"


def build_heatmap_cut_items(hotspots: list, segments: list = None, title_prefix: str = "🔥 Top") -> list:
    """
    Converte hotspots em itens de corte compatíveis com a fila de lote
    (`core.batch_processor.process_batch_cuts`) e com a lista de Shorts da Seção 2.
    """
    items = []
    for h in hotspots or []:
        dur = float(h["end_sec"]) - float(h["start_sec"])
        snippet = get_text_for_range(segments or [], h["start_sec"], h["end_sec"]) if segments else ""
        first_words = " ".join(snippet.split()[:8]).rstrip(".,;:!?") if snippet else ""
        title = f"{title_prefix} {h.get('rank', len(items) + 1)} Mais Reassistido"
        if first_words:
            title += f" — {first_words}"
        items.append({
            "type": f"🔥 Heatmap #{h.get('rank', len(items) + 1)} ({h['peak_intensity']:.0%})",
            "title": title,
            "start": h["start"],
            "end": h["end"],
            "start_s": float(h["start_sec"]),
            "end_s": float(h["end_sec"]),
            "duration_label": f"{int(dur // 60)}m {int(dur % 60):02d}s" if dur >= 60 else f"{int(round(dur))}s",
            "snippet": snippet,
            "source": "youtube_heatmap",
            "peak_intensity": h["peak_intensity"],
            "avg_intensity": h.get("avg_intensity"),
            "peak_sec": h.get("peak_sec"),
            "rank": h.get("rank"),
        })
    return items
