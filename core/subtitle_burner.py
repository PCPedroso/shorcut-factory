"""
subtitle_burner.py — Legendas Dinâmicas Estilo CapCut / Alex Hormozi (ASS / libass)
Queima legendas sincronizadas palavra-a-palavra diretamente no vídeo renderizado,
utilizando o formato padrão de indústria ASS (Advanced SubStation Alpha) e o renderizador nativo libass do FFmpeg.
"""

import os
import re
import json
import hashlib
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
        pass


def _time_str_to_seconds(t_str: str) -> float:
    """Converte 'MM:SS', 'HH:MM:SS' ou 'SS' para float de segundos."""
    try:
        parts = t_str.strip().split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(parts[0])
    except Exception:
        pass
    return 0.0


def _format_ass_time(seconds: float) -> str:
    """Converte segundos em float para o formato de tempo do ASS: H:MM:SS.cs"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _hex_to_ass_color(hex_color: str, alpha: float = 0.0) -> str:
    """
    Converte cor hexadecimal (#RRGGBB) para o formato ASS (&HAABBGGRR&).
    No ASS: Alpha 0 = totalmente opaco, Alpha 255 = transparente.
    A ordem dos canais é Blue, Green, Red (BGR).
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    else:
        r, g, b = "FF", "FF", "FF"
    a_val = int(alpha * 255)
    a_hex = format(a_val, "02X")
    return f"&H{a_hex}{b.upper()}{g.upper()}{r.upper()}&"


def _clean_word_text(text: str) -> str:
    """Remove pontuações residuais de marcadores (como '>>', '<<', '[Música]')."""
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'[><]{2,}', '', text)
    return text.strip()


def extract_words_in_range(transcript_path: str, start_time_str: str, end_time_str: str) -> list:
    """
    Lê o transcript.json e extrai todas as palavras que ocorrem dentro do intervalo do corte.
    Trata tanto transcripts com word_timestamps (Whisper) quanto transcripts do YouTube ASR
    (que possuem janelas de segmentos sobrepostas).
    Remove marcadores de interlocutor ('>>') e ruído ('[Música]'), marcando quebras de fala.
    Garante estrita ordem cronológica e zero sobreposição temporal entre palavras.
    """
    if not os.path.exists(transcript_path):
        return []

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    cut_start = _time_str_to_seconds(start_time_str)
    cut_end = _time_str_to_seconds(end_time_str)

    if cut_end <= cut_start:
        return []

    segments = data.get("segments", [])
    raw_words = []

    for i, seg in enumerate(segments):
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", 0.0)

        # 1. Se tem word_timestamps detalhados (Whisper)
        if "words" in seg and seg["words"]:
            for w in seg["words"]:
                w_start = w.get("start", seg_start)
                w_end = w.get("end", seg_end)
                word_text = _clean_word_text(w.get("word", ""))
                is_break = bool(re.search(r'[><]{2,}', w.get("word", "")))
                if word_text:
                    raw_words.append({
                        "word": word_text,
                        "start": w_start,
                        "end": w_end,
                        "break_before": is_break
                    })
        else:
            # 2. Transcrição por segmentos (ex: YouTube ASR)
            raw_text = seg.get("text", "").strip()
            # Remove ruídos entre colchetes como [Música], [Aplausos]
            raw_text = re.sub(r'\[.*?\]', '', raw_text)
            if not raw_text.strip():
                continue

            if i < len(segments) - 1 and segments[i + 1].get("start", 0.0) > seg_start:
                actual_end = segments[i + 1]["start"]
            else:
                actual_end = seg_end

            # Divide o texto considerando marcadores de interlocutor '>>'
            speaker_parts = re.split(r'\s*>{2,}\s*', raw_text)
            # Agrupa palavras por parte
            total_words_in_seg = sum(len(p.split()) for p in speaker_parts if p.strip())
            if total_words_in_seg == 0:
                continue

            seg_duration = max(0.1, actual_end - seg_start)
            word_duration = seg_duration / total_words_in_seg

            word_counter = 0
            for part_idx, part in enumerate(speaker_parts):
                part_words = part.split()
                for word_idx, w in enumerate(part_words):
                    cleaned_w = _clean_word_text(w)
                    if not cleaned_w:
                        continue
                    w_start = seg_start + word_counter * word_duration
                    w_end = w_start + word_duration
                    # Se a palavra é o início de um novo interlocutor pós-'>>'
                    is_break = (part_idx > 0 and word_idx == 0)
                    raw_words.append({
                        "word": cleaned_w,
                        "start": w_start,
                        "end": w_end,
                        "break_before": is_break
                    })
                    word_counter += 1

    if not raw_words:
        return []

    # 3. Ordena cronologicamente e elimina estritamente qualquer sobreposição
    raw_words.sort(key=lambda x: x["start"])
    for k in range(len(raw_words) - 1):
        if raw_words[k]["end"] > raw_words[k + 1]["start"]:
            raw_words[k]["end"] = raw_words[k + 1]["start"]
        if raw_words[k + 1]["start"] < raw_words[k]["start"]:
            raw_words[k + 1]["start"] = raw_words[k]["start"]

    # 4. Filtra apenas as palavras que caem dentro do intervalo [cut_start, cut_end]
    # e ajusta os timestamps para serem relativos ao início do corte (t = 0)
    relative_words = []
    for w in raw_words:
        if w["end"] >= cut_start and w["start"] <= cut_end:
            rel_start = max(0.0, w["start"] - cut_start)
            rel_end = min(cut_end - cut_start, w["end"] - cut_start)
            if rel_end > rel_start:
                relative_words.append({
                    "word": w["word"],
                    "start": rel_start,
                    "end": rel_end
                })

    return relative_words


def group_words_into_lines(words: list, max_words_per_line: int = 4, max_gap_seconds: float = 1.0) -> list:
    """
    Agrupa palavras em blocos/linhas curtas para exibição dinâmica estilo CapCut.
    Quebra de linha ocorre quando:
      - Atinge max_words_per_line
      - Ocorre uma pausa longa (> max_gap_seconds)
      - Ocorre uma quebra de interlocutor/assunto (marcador '>>')
    """
    if not words:
        return []

    lines = []
    current_line_words = []

    for i, w in enumerate(words):
        if not current_line_words:
            current_line_words.append(w)
            continue

        prev_w = current_line_words[-1]
        gap = w["start"] - prev_w["end"]
        is_break = w.get("break_before", False)

        # Se atingiu o limite de palavras, houve pausa ou mudança de interlocutor ('>>'), fecha a linha
        if len(current_line_words) >= max_words_per_line or gap > max_gap_seconds or is_break:
            line_start = current_line_words[0]["start"]
            line_end = current_line_words[-1]["end"]
            lines.append({
                "words": list(current_line_words),
                "line_start": line_start,
                "line_end": line_end,
                "text": " ".join(item["word"] for item in current_line_words)
            })
            current_line_words = [w]
        else:
            current_line_words.append(w)

    if current_line_words:
        line_start = current_line_words[0]["start"]
        line_end = current_line_words[-1]["end"]
        lines.append({
            "words": list(current_line_words),
            "line_start": line_start,
            "line_end": line_end,
            "text": " ".join(item["word"] for item in current_line_words)
        })

    return lines


def generate_ass_file(
    lines: list,
    output_ass_path: str,
    video_width: int = 1080,
    video_height: int = 1920,
    font_size: int = 75,
    highlight_color: str = "#FFFF00",
    base_color: str = "#FFFFFF",
    outline_color: str = "#000000",
    outline_width: int = None,
    shadow_depth: int = None,
) -> bool:
    """
    Gera arquivo de legendas .ass completo com estilos e eventos karaokê palavra-a-palavra.
    Garante transições perfeitas sem nunca sobrepor duas falas ou linhas simultâneas.
    """
    _ensure_font()

    ass_base_color = _hex_to_ass_color(base_color, alpha=0.0)
    ass_highlight_color = _hex_to_ass_color(highlight_color, alpha=0.0)
    ass_outline_color = _hex_to_ass_color(outline_color, alpha=0.0)
    ass_shadow_color = "&H80000000&"  # Sombra preta 50%

    # Margem vertical inferior (aproximadamente 22% a partir do fundo = posição no terço inferior)
    margin_v = int(video_height * 0.22)
    margin_lr = int(video_width * 0.05)

    # Outline e sombra proporcionais ao tamanho da fonte para manter o estilo Alex Hormozi nítido
    if outline_width is None:
        outline_width = max(4, int(font_size * 0.08))
    if shadow_depth is None:
        shadow_depth = max(2, int(font_size * 0.035))

    # Monta cabeçalho do script ASS
    content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Montserrat ExtraBold,{font_size},{ass_base_color},&H000000FF&,{ass_outline_color},{ass_shadow_color},"
        f"-1,0,0,0,100,100,0,0,1,{outline_width},{shadow_depth},2,{margin_lr},{margin_lr},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for line_idx, line in enumerate(lines):
        words = line["words"]
        n_words = len(words)

        # Se houver uma próxima linha, a linha atual não deve invadir o tempo de início da próxima
        next_line_start = lines[line_idx + 1]["line_start"] if line_idx < len(lines) - 1 else None

        for i, curr_w in enumerate(words):
            event_start = curr_w["start"]

            # O evento dura até o início da próxima palavra dentro da mesma linha
            if i < n_words - 1:
                event_end = words[i + 1]["start"]
            else:
                # Última palavra da linha: permanece na tela até o fim da palavra (ou até a próxima linha começar)
                base_end = curr_w["end"] + 0.10
                if next_line_start is not None:
                    event_end = min(base_end, next_line_start)
                else:
                    event_end = base_end

            # Garante que event_end > event_start
            if event_end <= event_start:
                event_end = event_start + 0.05

            # Monta a linha com a palavra ativa destacada com tag de cor
            line_parts = []
            for j, w in enumerate(words):
                w_text = w["word"]
                if j == i:
                    # Palavra atual em destaque
                    line_parts.append(f"{{\\c{ass_highlight_color}}}{w_text}{{\\c{ass_base_color}}}")
                else:
                    line_parts.append(w_text)

            dialogue_text = " ".join(line_parts)
            start_str = _format_ass_time(event_start)
            end_str = _format_ass_time(event_end)

            content.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{dialogue_text}")

    try:
        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")
        return True
    except Exception:
        return False


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
    Aplica legendas dinâmicas palavra-a-palavra queimadas via pass-2 FFmpeg com motor libass.
    Retorna dicionário com {'path': str, 'error': str|None, 'warning': str|None}.
    """
    if not os.path.exists(input_video_path):
        return {"path": None, "error": f"Arquivo de vídeo de entrada não encontrado: {input_video_path}"}

    if not os.path.exists(transcript_path):
        return {"path": input_video_path, "error": None, "warning": "Transcrição não encontrada. Legendas não aplicadas."}

    try:
        # 1. Extrai palavras dentro do intervalo do corte (limpas e sequenciais)
        words = extract_words_in_range(transcript_path, start_time_str, end_time_str)
        if not words:
            return {"path": input_video_path, "error": None, "warning": "Nenhuma palavra encontrada no intervalo selecionado."}

        # 2. Agrupa em linhas curtas (3-4 palavras)
        lines = group_words_into_lines(words, max_words_per_line=max_words_per_line)
        if not lines:
            return {"path": input_video_path, "error": None, "warning": "Não foi possível agrupar as palavras em linhas."}

        # 3. Detecta resolução real do vídeo
        video_width = 1080
        video_height = 1920
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

        # 4. Cria arquivo .ass
        _hash = hashlib.md5(output_video_path.encode()).hexdigest()[:10]
        _tmp_dir = os.path.dirname(output_video_path) or "."
        ass_path = os.path.join(_tmp_dir, f"_sub_{_hash}.ass")
        tmp_output = os.path.join(_tmp_dir, f"_subs_tmp_{_hash}.mp4")

        success = generate_ass_file(
            lines=lines,
            output_ass_path=ass_path,
            video_width=video_width,
            video_height=video_height,
            font_size=font_size,
            highlight_color=highlight_color,
            base_color=base_color,
        )

        if not success or not os.path.exists(ass_path):
            return {"path": input_video_path, "error": None, "warning": "Falha ao gerar arquivo de legendas .ass."}

        try:
            # 5. Prepara caminhos para o filtro FFmpeg
            # Para máxima compatibilidade no Windows, usamos caminhos relativos normalizados com barras
            rel_ass = os.path.relpath(ass_path, start=".").replace("\\", "/")
            rel_fonts = os.path.relpath(_FONTS_DIR, start=".").replace("\\", "/")

            vf_filter = f"ass={rel_ass}:fontsdir={rel_fonts}"

            cmd = [
                FFMPEG_EXE, "-y",
                "-i", input_video_path,
                "-vf", vf_filter,
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
                return {"path": None, "error": f"FFmpeg libass subtitle pass-2 falhou:\n{err_detail}"}

        finally:
            # Limpa arquivo .ass temporário
            if os.path.exists(ass_path):
                os.remove(ass_path)

    except Exception as e:
        return {"path": None, "error": str(e)}
