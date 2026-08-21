"""
subtitle_burner.py — Legendas Dinâmicas Estilo CapCut / Alex Hormozi
Queima legendas sincronizadas palavra-a-palavra diretamente no vídeo renderizado,
com destaque visual animado (highlight da palavra atual em cor vibrante).
"""

import os
import json
import subprocess
import imageio_ffmpeg

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

# Diretório de fontes bundled junto ao módulo
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.join(_SCRIPT_DIR, "fonts")
_FONT_BOLD_PATH = os.path.join(_FONTS_DIR, "Montserrat-ExtraBold.ttf")
_FONT_URL = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf"


def _ensure_font():
    """Garante que a fonte Montserrat-ExtraBold.ttf esteja disponível localmente."""
    if os.path.exists(_FONT_BOLD_PATH) and os.path.getsize(_FONT_BOLD_PATH) > 10000:
        return
    os.makedirs(_FONTS_DIR, exist_ok=True)
    try:
        import urllib.request
        urllib.request.urlretrieve(_FONT_URL, _FONT_BOLD_PATH)
    except Exception:
        pass  # Fallback para Arial se o download falhar

def _get_font_path() -> str:
    """Retorna o caminho da fonte disponível (bundled > fallback Arial)."""
    _ensure_font()
    if os.path.exists(_FONT_BOLD_PATH):
        # FFmpeg no Windows precisa de barras e escape no separador de drive
        return _FONT_BOLD_PATH.replace("\\", "/").replace(":", "\\:")
    return "Arial"


def parse_time_to_seconds(time_str: str) -> float:
    """Converte HH:MM:SS ou MM:SS para segundos float."""
    parts = time_str.strip().split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return float(time_str)


def _distribute_words_proportionally(text: str, seg_start: float, seg_end: float) -> list:
    """
    Fallback para segmentos sem timestamps por palavra (ex: transcrição do YouTube).
    Distribui as palavras proporcionalmente no intervalo de tempo do segmento.
    """
    words = text.strip().split()
    if not words:
        return []
    duration = max(seg_end - seg_start, 0.1)
    word_dur = duration / len(words)
    result = []
    for i, w in enumerate(words):
        result.append({
            "word": w,
            "start": round(seg_start + i * word_dur, 3),
            "end": round(seg_start + (i + 1) * word_dur, 3),
        })
    return result


def extract_words_in_range(transcript_path: str, start_s: float, end_s: float) -> list:
    """
    Lê o transcript.json e retorna lista de palavras com timestamps
    ajustados relativos ao início do corte (t' = t - start_s).

    Suporta dois formatos de transcript.json:
    1. Com word_timestamps (Whisper): segmentos têm campo 'words'
    2. Sem word_timestamps (YouTube ASR / Whisper básico): distribui proporcionalmente
    """
    if not os.path.exists(transcript_path):
        return []

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    segments = data.get("segments", [])
    word_list = []

    for seg in segments:
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", seg_start + 2.0)

        # Filtra segmentos fora do intervalo do corte
        if seg_end < start_s or seg_start > end_s:
            continue

        # Caminho 1: segmento tem timestamps por palavra (Whisper com word_timestamps=True)
        words_data = seg.get("words", [])
        if words_data:
            for w in words_data:
                w_start = w.get("start", seg_start)
                w_end = w.get("end", w_start + 0.3)
                if w_end < start_s or w_start > end_s:
                    continue
                word_text = w.get("word", "").strip()
                if not word_text:
                    continue
                word_list.append({
                    "word": word_text,
                    "start": max(0.0, round(w_start - start_s, 3)),
                    "end": max(0.0, round(w_end - start_s, 3)),
                })
        else:
            # Caminho 2: fallback proporcional
            text = seg.get("text", "").strip()
            if not text:
                continue
            clipped_start = max(seg_start, start_s)
            clipped_end = min(seg_end, end_s)
            if clipped_end <= clipped_start:
                continue
            for w in _distribute_words_proportionally(text, clipped_start, clipped_end):
                word_list.append({
                    "word": w["word"],
                    "start": max(0.0, round(w["start"] - start_s, 3)),
                    "end": max(0.0, round(w["end"] - start_s, 3)),
                })

    return word_list


def group_words_into_lines(words: list, max_words_per_line: int = 4) -> list:
    """
    Agrupa as palavras em linhas de até `max_words_per_line` palavras.
    Cada linha contém: words, line_start, line_end, text.
    """
    if not words:
        return []
    lines = []
    for i in range(0, len(words), max_words_per_line):
        chunk = words[i: i + max_words_per_line]
        lines.append({
            "words": chunk,
            "line_start": chunk[0]["start"],
            "line_end": chunk[-1]["end"],
            "text": " ".join(w["word"] for w in chunk),
        })
    return lines


def _escape_ffmpeg_text(text: str) -> str:
    """Escapa caracteres especiais para o filtro drawtext do FFmpeg."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\u2019")   # substitui aspas por caractere Unicode similar
    text = text.replace(":", "\\:")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def _hex_to_ffmpeg_color(hex_color: str, alpha: float = 1.0) -> str:
    """Converte cor hex (#RRGGBB) para formato FFmpeg 0xRRGGBBAA."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    alpha_hex = format(int(alpha * 255), "02x").upper()
    return f"0x{r.upper()}{g.upper()}{b.upper()}{alpha_hex}"


def build_drawtext_filters(
    lines: list,
    video_height: int,
    font_size: int = 55,
    highlight_color: str = "#FFFF00",
    base_color: str = "#FFFFFF",
    outline_color: str = "#000000",
    outline_width: int = 3,
    shadow_offset: int = 2,
) -> list:
    """
    Gera lista de filtros drawtext do FFmpeg para todas as linhas e palavras.

    Estratégia em 2 camadas por linha:
    1. Linha base (todas as palavras, cor semitransparente) — visível durante toda a linha
    2. Linha highlight (mesmas palavras, cor vibrante) — visível apenas no período da palavra ativa

    Retorna lista de strings de filtros drawtext.
    """
    filters = []
    font_path = _get_font_path()

    # Posição Y: 78% da altura (terço inferior)
    y_pos = int(video_height * 0.78)
    x_pos = "(w-text_w)/2"

    highlight_ffmpeg = _hex_to_ffmpeg_color(highlight_color, alpha=1.0)
    base_ffmpeg = _hex_to_ffmpeg_color(base_color, alpha=0.65)
    outline_ffmpeg = _hex_to_ffmpeg_color(outline_color, alpha=0.88)
    shadow_ffmpeg = _hex_to_ffmpeg_color("000000", alpha=0.55)

    for line in lines:
        line_start = line["line_start"]
        line_end = line["line_end"]
        line_text = _escape_ffmpeg_text(line["text"])

        # --- Camada 1: base (cor apagada, sempre visível durante a linha) ---
        base_filter = (
            f"drawtext=fontfile='{font_path}'"
            f":text='{line_text}'"
            f":fontsize={font_size}"
            f":fontcolor={base_ffmpeg}"
            f":borderw={outline_width}"
            f":bordercolor={outline_ffmpeg}"
            f":shadowx={shadow_offset}:shadowy={shadow_offset}"
            f":shadowcolor={shadow_ffmpeg}"
            f":x={x_pos}:y={y_pos}"
            f":enable='between(t,{line_start:.3f},{line_end:.3f})'"
        )
        filters.append(base_filter)

        # --- Camada 2: highlight (cor vibrante, piscando palavra por palavra) ---
        for word_data in line["words"]:
            w_start = word_data["start"]
            w_end = word_data["end"]
            # Re-renderiza a linha inteira em highlight sobre a base layer,
            # apenas no intervalo da palavra atual — cria o efeito de "karaokê"
            highlight_filter = (
                f"drawtext=fontfile='{font_path}'"
                f":text='{line_text}'"
                f":fontsize={int(font_size * 1.04)}"
                f":fontcolor={highlight_ffmpeg}"
                f":borderw={outline_width + 1}"
                f":bordercolor={outline_ffmpeg}"
                f":shadowx={shadow_offset}:shadowy={shadow_offset}"
                f":shadowcolor={shadow_ffmpeg}"
                f":x={x_pos}:y={y_pos - 1}"
                f":enable='between(t,{w_start:.3f},{w_end:.3f})'"
            )
            filters.append(highlight_filter)

    return filters


def burn_subtitles(
    input_video_path: str,
    output_video_path: str,
    transcript_path: str,
    start_time_str: str,
    end_time_str: str,
    highlight_color: str = "#FFFF00",
    base_color: str = "#FFFFFF",
    font_size: int = 55,
    max_words_per_line: int = 4,
) -> dict:
    """
    Pipeline principal: extrai palavras → agrupa em linhas → queima legendas (pass-2 FFmpeg).

    O arquivo de saída pode ser o mesmo que o de entrada (sobrescreve via temp file).
    Retorna dict com 'path' e 'error'.
    """
    try:
        # 1. Parseia timestamps absolutos do vídeo original
        start_s = parse_time_to_seconds(start_time_str)
        end_s = parse_time_to_seconds(end_time_str)

        # 2. Extrai palavras com timestamps relativos ao corte
        words = extract_words_in_range(transcript_path, start_s, end_s)
        if not words:
            return {
                "path": input_video_path,
                "error": None,
                "warning": "Sem timestamps de palavras no transcript — legendas não aplicadas.",
            }

        # 3. Agrupa em linhas
        lines = group_words_into_lines(words, max_words_per_line=max_words_per_line)

        # 4. Detecta resolução do vídeo via ffprobe
        video_width, video_height = 1080, 1920  # default 9:16
        ffprobe_exe = FFMPEG_EXE.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
        if os.path.exists(ffprobe_exe):
            try:
                probe_result = subprocess.run(
                    [ffprobe_exe, "-v", "quiet", "-print_format", "json",
                     "-show_streams", "-select_streams", "v:0", input_video_path],
                    capture_output=True, text=True, timeout=15
                )
                probe_data = json.loads(probe_result.stdout)
                stream = probe_data.get("streams", [{}])[0]
                video_width = stream.get("width", 1080)
                video_height = stream.get("height", 1920)
            except Exception:
                pass

        # 5. Monta filtros drawtext
        drawtext_filters = build_drawtext_filters(
            lines=lines,
            video_height=video_height,
            font_size=font_size,
            highlight_color=highlight_color,
            base_color=base_color,
        )

        if not drawtext_filters:
            return {"path": input_video_path, "error": None, "warning": "Nenhum filtro de legenda gerado."}

        # 6. Executa pass-2 FFmpeg via arquivo temporário
        tmp_output = output_video_path + "._subs_tmp.mp4"
        vf_chain = ",\n".join(drawtext_filters)

        # IMPORTANTE: A cadeia de filtros drawtext pode ser muito longa para a linha de comando
        # do Windows (limite ~32767 chars). Usamos -filter_script:v para ler o filtro de arquivo.
        filter_script_path = output_video_path + "._filter.txt"
        try:
            with open(filter_script_path, "w", encoding="utf-8") as f:
                f.write(vf_chain)

            cmd = [
                FFMPEG_EXE, "-y",
                "-i", input_video_path,
                "-filter_script:v", filter_script_path,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "copy",
                "-pix_fmt", "yuv420p",
                tmp_output
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(tmp_output) and os.path.getsize(tmp_output) > 0:
                if os.path.exists(output_video_path):
                    os.remove(output_video_path)
                os.rename(tmp_output, output_video_path)
                return {"path": output_video_path, "error": None}
            else:
                if os.path.exists(tmp_output):
                    os.remove(tmp_output)
                err_detail = result.stderr[-2000:] if result.stderr else "Erro desconhecido"
                return {"path": None, "error": f"FFmpeg subtitle pass-2 falhou:\n{err_detail}"}
        finally:
            # Limpa o arquivo de filtro temporário
            if os.path.exists(filter_script_path):
                os.remove(filter_script_path)

    except Exception as e:
        return {"path": None, "error": str(e)}
