"""
core/multicam_crop.py — Motor de Enquadramento Multicâmera Interativo (2 a N Câmeras)
Permite selecionar múltiplas regiões de interesse (ROIs) sobre o vídeo original (ex: estúdio com 2 a 3 câmeras),
ordená-las verticalmente (Topo, Meio, Base) e renderizar cortes verticais proporcionais (1080x1920)
com suporte a alternância temporal ao longo do vídeo (Timeline de Cenas/Intervalos).
"""

import os
import re
import cv2
import json
import tempfile
import subprocess
import numpy as np
from PIL import Image, ImageDraw
import imageio_ffmpeg
from core.frame_capturer import parse_time_str_to_seconds, format_seconds_to_time_str, extract_frame_at_timestamp

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def patch_streamlit_drawable_canvas_compat():
    """
    Garante compatibilidade entre streamlit-drawable-canvas e versões modernas do Streamlit (1.60+).
    Nas versões recentes do Streamlit, `image_to_url` foi movido para
    `streamlit.elements.lib.image_utils` e espera `LayoutConfig` como segundo argumento.
    """
    try:
        import base64
        import io
        from PIL import Image
        import streamlit.elements.image as st_image
        import streamlit.elements.lib.image_utils as iu
        from streamlit.elements.lib.layout_utils import LayoutConfig

        if not hasattr(st_image, "image_to_url") or getattr(st_image, "_is_multicam_patched", False) is False:
            def _compat_image_to_url(image, width_or_layout=None, clamp=False, channels="RGB", output_format="PNG", image_id=""):
                if isinstance(width_or_layout, (int, float)):
                    layout_config = LayoutConfig(width=int(width_or_layout))
                elif isinstance(width_or_layout, LayoutConfig):
                    layout_config = width_or_layout
                else:
                    layout_config = LayoutConfig()

                url = ""
                try:
                    url = iu.image_to_url(image, layout_config, clamp, channels, output_format, image_id)
                except Exception:
                    pass

                if not url:
                    if isinstance(image, Image.Image):
                        buf = io.BytesIO()
                        image.save(buf, format="PNG")
                        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                        return f"data:image/png;base64,{b64}"
                return url

            st_image.image_to_url = _compat_image_to_url
            st_image._is_multicam_patched = True
    except Exception:
        pass


# Aplica o patch imediatamente
patch_streamlit_drawable_canvas_compat()


def normalize_box_coordinates(
    raw_box: dict,
    canvas_w: int,
    canvas_h: int,
    video_w: int,
    video_h: int
) -> dict:
    """
    Converte coordenadas de um retângulo do Fabric.js / streamlit-drawable-canvas
    para coordenadas exatas em pixels do vídeo original (ex: 1920x1080).
    
    Trata transformações de escala (scaleX, scaleY), offsets e garante
    que largura e altura sejam números pares maiores que zero dentro dos limites do vídeo.
    """
    scale_x = float(raw_box.get("scaleX", 1.0) or 1.0)
    scale_y = float(raw_box.get("scaleY", 1.0) or 1.0)
    
    b_left = float(raw_box.get("left", 0.0) or 0.0)
    b_top = float(raw_box.get("top", 0.0) or 0.0)
    b_w = float(raw_box.get("width", 0.0) or 0.0) * scale_x
    b_h = float(raw_box.get("height", 0.0) or 0.0) * scale_y

    ratio_x = float(video_w) / float(canvas_w) if canvas_w > 0 else 1.0
    ratio_y = float(video_h) / float(canvas_h) if canvas_h > 0 else 1.0

    vx = int(round(b_left * ratio_x))
    vy = int(round(b_top * ratio_y))
    vw = int(round(b_w * ratio_x))
    vh = int(round(b_h * ratio_y))

    # Clamping nos limites da imagem
    vx = max(0, min(video_w - 2, vx))
    vy = max(0, min(video_h - 2, vy))
    vw = max(2, min(video_w - vx, vw))
    vh = max(2, min(video_h - vy, vh))

    # Garante paridade par (exigido por encoders h264/yuv420p)
    if vw % 2 != 0:
        vw -= 1
    if vh % 2 != 0:
        vh -= 1
    if vx % 2 != 0:
        vx += 1
    if vy % 2 != 0:
        vy += 1

    vw = max(2, vw)
    vh = max(2, vh)

    return {
        "x": int(vx),
        "y": int(vy),
        "w": int(vw),
        "h": int(vh),
        "order": int(raw_box.get("order", 0)),
        "label": str(raw_box.get("label", ""))
    }


def compute_slot_heights(num_boxes: int, target_h: int = 1920) -> list:
    """
    Calcula as alturas em pixels de cada slot vertical para somar exatamente target_h (1920).
    Exemplos:
      1 caixa -> [1920]
      2 caixas -> [960, 960]
      3 caixas -> [640, 640, 640]
      4 caixas -> [480, 480, 480, 480]
    """
    if num_boxes <= 1:
        return [target_h]

    base_h = target_h // num_boxes
    # Assegura paridade par para cada slot
    if base_h % 2 != 0:
        base_h -= 1

    heights = [base_h] * num_boxes
    remainder = target_h - sum(heights)
    # Adiciona o restante ao slot do meio ou último
    if remainder > 0:
        mid_idx = num_boxes // 2
        heights[mid_idx] += remainder
        if heights[mid_idx] % 2 != 0:
            heights[mid_idx] += 1
            heights[-1] -= 1

    return heights


def crop_and_fit_image_slot(
    img_bgr: np.ndarray,
    box: dict,
    target_w: int,
    target_h: int
) -> np.ndarray:
    """
    Recorta a região da caixa na imagem original e redimensiona para preencher
    o slot vertical mantendo rigorosamente a proporção de aspecto (sem distorção/esticamento).
    Faz 'scale to fill' com corte centralizado caso a proporção da caixa seja diferente do slot.
    """
    img_h, img_w = img_bgr.shape[:2]
    x = max(0, min(img_w - 2, box.get("x", 0)))
    y = max(0, min(img_h - 2, box.get("y", 0)))
    w = max(2, min(img_w - x, box.get("w", img_w)))
    h = max(2, min(img_h - y, box.get("h", img_h)))

    cropped = img_bgr[y:y+h, x:x+w]
    if cropped.size == 0 or cropped.shape[0] < 2 or cropped.shape[1] < 2:
        return np.zeros((target_h, target_w, 3), dtype=np.uint8)

    c_h, c_w = cropped.shape[:2]
    scale = max(target_w / float(c_w), target_h / float(c_h))
    new_w = int(round(c_w * scale))
    new_h = int(round(c_h * scale))

    resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Center crop para encaixar perfeitamente em target_w x target_h
    start_x = max(0, (new_w - target_w) // 2)
    start_y = max(0, (new_h - target_h) // 2)

    fitted = resized[start_y:start_y+target_h, start_x:start_x+target_w]

    # Garantia de dimensões exatas
    if fitted.shape[0] != target_h or fitted.shape[1] != target_w:
        fitted = cv2.resize(fitted, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

    return fitted


def compose_multicam_preview_image(
    video_path: str,
    timestamp_s: float,
    boxes: list,
    output_path: str = None,
    divider_color: str = "black",
    divider_width: int = 4
) -> dict:
    """
    Gera uma imagem de prévia instantânea 1080x1920 (9:16) no ponto timestamp_s
    com as caixas empilhadas verticalmente de cima para baixo na ordem configurada.
    """
    res_snap = extract_frame_at_timestamp(video_path, timestamp_s)
    if not res_snap.get("frame") is not None:
        return {"error": res_snap.get("error", "Não foi possível extrair o frame do vídeo.")}

    frame_bgr = res_snap["frame"]
    total_w = 1080
    total_h = 1920

    if not boxes:
        # Fallback: centro 9:16 do vídeo
        f_h, f_w = frame_bgr.shape[:2]
        crop_w = int(f_h * (9 / 16))
        start_x = max(0, (f_w - crop_w) // 2)
        center_crop = frame_bgr[:, start_x:start_x+crop_w]
        preview_bgr = cv2.resize(center_crop, (total_w, total_h), interpolation=cv2.INTER_LINEAR)
    else:
        # Ordena caixas pelo atributo order (0 = Topo, 1 = Meio, 2 = Base)
        sorted_boxes = sorted(boxes, key=lambda b: b.get("order", 0))
        slot_heights = compute_slot_heights(len(sorted_boxes), target_h=total_h)

        rendered_slots = []
        for i, box in enumerate(sorted_boxes):
            slot_h = slot_heights[i]
            slot_img = crop_and_fit_image_slot(frame_bgr, box, target_w=total_w, target_h=slot_h)
            rendered_slots.append(slot_img)

        # Empilhamento vertical
        preview_bgr = np.vstack(rendered_slots)

        # Desenho de linhas divisórias opcionais
        if divider_width > 0 and len(rendered_slots) > 1:
            color_bgr = (0, 0, 0)
            if divider_color.lower() in ["white", "branco", "#ffffff"]:
                color_bgr = (255, 255, 255)
            elif divider_color.lower() in ["yellow", "amarelo", "#ffd700", "#ffff00"]:
                color_bgr = (0, 215, 255)
            elif divider_color.startswith("#") and len(divider_color) == 7:
                try:
                    c_hex = divider_color.lstrip("#")
                    r = int(c_hex[0:2], 16)
                    g = int(c_hex[2:4], 16)
                    b = int(c_hex[4:6], 16)
                    color_bgr = (b, g, r)
                except Exception:
                    color_bgr = (0, 0, 0)

            cur_y = 0
            for h in slot_heights[:-1]:
                cur_y += h
                y_top = max(0, cur_y - (divider_width // 2))
                y_bottom = min(total_h, cur_y + ((divider_width + 1) // 2))
                cv2.rectangle(preview_bgr, (0, y_top), (total_w, y_bottom), color_bgr, -1)

    if not output_path:
        out_dir = os.path.dirname(video_path) if video_path else tempfile.gettempdir()
        output_path = os.path.join(out_dir, f"preview_multicam_{int(timestamp_s*1000)}.jpg")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, preview_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])

    return {
        "status": "success",
        "path": output_path,
        "width": total_w,
        "height": total_h,
        "timestamp_s": timestamp_s
    }


def build_multicam_filtergraph(
    boxes: list,
    input_tag: str = "0:v",
    out_tag: str = "v_multicam",
    target_w: int = 1080,
    target_h: int = 1920,
    divider_color: str = "black",
    divider_width: int = 4
) -> str:
    """
    Gera a cláusula filter_complex do FFmpeg para recortar e empilhar verticalmente N câmeras.
    Garante aspecto 9:16 proporcional sem distorção facial usando scale proporcional + center crop.
    """
    if not boxes:
        # Fallback: crop central 9:16
        return f"[{input_tag}]crop=ih*(9/16):ih:(iw-ow)/2:0,scale={target_w}:{target_h},setsar=1[{out_tag}]"

    sorted_boxes = sorted(boxes, key=lambda b: b.get("order", 0))
    n = len(sorted_boxes)

    if n == 1:
        box = sorted_boxes[0]
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        return (
            f"[{input_tag}]crop={w}:{h}:{x}:{y},"
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h}:(iw-ow)/2:(ih-oh)/2,setsar=1[{out_tag}]"
        )

    slot_heights = compute_slot_heights(n, target_h=target_h)
    clauses = []
    stack_tags = []

    for i, box in enumerate(sorted_boxes):
        slot_h = slot_heights[i]
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]
        cam_tag = f"cam_{i}"
        clauses.append(
            f"[{input_tag}]crop={w}:{h}:{x}:{y},"
            f"scale={target_w}:{slot_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{slot_h}:(iw-ow)/2:(ih-oh)/2,setsar=1[{cam_tag}]"
        )
        stack_tags.append(f"[{cam_tag}]")

    # Empilhamento vertical com vstack
    vstack_clause = "".join(stack_tags) + f"vstack=inputs={n}"
    
    # Divisórias horizontais entre os slots com drawbox se divider_width > 0
    if divider_width > 0:
        c_name = divider_color.lower()
        if c_name in ["white", "branco"]:
            draw_col = "white"
        elif c_name in ["yellow", "amarelo"]:
            draw_col = "yellow"
        elif c_name.startswith("#"):
            draw_col = f"0x{c_name.lstrip('#')}"
        else:
            draw_col = "black"

        cur_y = 0
        drawbox_chain = []
        for sh in slot_heights[:-1]:
            cur_y += sh
            y_box = max(0, cur_y - (divider_width // 2))
            drawbox_chain.append(f"drawbox=x=0:y={y_box}:w={target_w}:h={divider_width}:color={draw_col}:t=fill")

        box_filter = ",".join(drawbox_chain)
        clauses.append(f"{vstack_clause},{box_filter}[{out_tag}]")
    else:
        clauses.append(f"{vstack_clause}[{out_tag}]")

    return ";".join(clauses)


def render_multicam_scene_clip(
    input_video_path: str,
    start_time_str: str,
    end_time_str: str,
    boxes: list,
    output_scene_path: str,
    divider_color: str = "black",
    divider_width: int = 4
) -> dict:
    """
    Renderiza um trecho/cena individual com a configuração multicâmera especificada.
    """
    if os.path.exists(output_scene_path):
        try:
            os.remove(output_scene_path)
        except Exception:
            pass

    filter_complex = build_multicam_filtergraph(
        boxes=boxes,
        input_tag="0:v",
        out_tag="v_out",
        divider_color=divider_color,
        divider_width=divider_width
    )

    cmd = [
        FFMPEG_EXE, "-y",
        "-ss", str(start_time_str),
        "-to", str(end_time_str),
        "-i", input_video_path,
        "-filter_complex", filter_complex,
        "-map", "[v_out]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_scene_path
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    if res.returncode != 0 or not os.path.exists(output_scene_path) or os.path.getsize(output_scene_path) == 0:
        return {
            "status": "error",
            "error": f"Erro FFmpeg ao renderizar cena multicâmera: {res.stderr[-400:] if res.stderr else 'Desconhecido'}"
        }

    return {"status": "success", "path": output_scene_path, "output_path": output_scene_path}


def render_multicam_cut(
    input_video_path: str,
    scenes: list,
    output_video_path: str,
    fallback_start_time: str = "00:00:00.00",
    fallback_end_time: str = ""
) -> dict:
    """
    Processa o corte completo suportando 1 cena única ou múltiplas cenas alternadas no tempo.
    Quando há mais de 1 cena temporal, renderiza cada segmento separadamente e une
    com concatenação sem perdas mantendo áudio perfeitamente contínuo.
    """
    if not scenes:
        return {"status": "error", "error": "Nenhuma cena ou enquadramento configurado para renderização multicâmera."}

    # Validação e ordenação cronológica das cenas
    valid_scenes = []
    for s in scenes:
        s_start = s.get("start_time") or fallback_start_time
        s_end = s.get("end_time") or fallback_end_time
        boxes = s.get("boxes", [])
        div_col = s.get("divider_color", "black")
        div_w = int(s.get("divider_width", 4))
        valid_scenes.append({
            "start_time": s_start,
            "end_time": s_end,
            "boxes": boxes,
            "divider_color": div_col,
            "divider_width": div_w,
            "start_sec": parse_time_str_to_seconds(s_start),
            "end_sec": parse_time_str_to_seconds(s_end) if s_end else 999999.0
        })

    valid_scenes.sort(key=lambda x: x["start_sec"])

    # Caso 1: Apenas 1 cena (o caso mais comum e ultra rápido)
    if len(valid_scenes) == 1:
        single = valid_scenes[0]
        return render_multicam_scene_clip(
            input_video_path=input_video_path,
            start_time_str=single["start_time"],
            end_time_str=single["end_time"],
            boxes=single["boxes"],
            output_scene_path=output_video_path,
            divider_color=single["divider_color"],
            divider_width=single["divider_width"]
        )

    # Caso 2: Múltiplas cenas temporais alternadas
    temp_dir = tempfile.mkdtemp(prefix="multicam_concat_")
    segment_paths = []

    try:
        for idx, scn in enumerate(valid_scenes):
            seg_out = os.path.join(temp_dir, f"segment_{idx:03d}.mp4")
            seg_res = render_multicam_scene_clip(
                input_video_path=input_video_path,
                start_time_str=scn["start_time"],
                end_time_str=scn["end_time"],
                boxes=scn["boxes"],
                output_scene_path=seg_out,
                divider_color=scn["divider_color"],
                divider_width=scn["divider_width"]
            )
            if seg_res.get("status") != "success":
                return seg_res
            segment_paths.append(seg_out)

        # Concatenação dos segmentos
        concat_list_file = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_file, "w", encoding="utf-8") as f_cat:
            for p in segment_paths:
                p_escaped = p.replace("\\", "/")
                f_cat.write(f"file '{p_escaped}'\n")

        if os.path.exists(output_video_path):
            try:
                os.remove(output_video_path)
            except Exception:
                pass

        concat_cmd = [
            FFMPEG_EXE, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_file,
            "-c", "copy",
            "-movflags", "+faststart",
            output_video_path
        ]
        cat_res = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        if cat_res.returncode != 0 or not os.path.exists(output_video_path) or os.path.getsize(output_video_path) == 0:
            return {
                "status": "error",
                "error": f"Erro na concatenação dos segmentos multicâmera: {cat_res.stderr[-300:] if cat_res.stderr else 'Desconhecido'}"
            }

        return {"status": "success", "path": output_video_path, "output_path": output_video_path}

    finally:
        # Limpeza segura dos temporários
        try:
            for p in segment_paths:
                if os.path.exists(p):
                    os.remove(p)
            concat_list = os.path.join(temp_dir, "concat_list.txt")
            if os.path.exists(concat_list):
                os.remove(concat_list)
            os.rmdir(temp_dir)
        except Exception:
            pass
