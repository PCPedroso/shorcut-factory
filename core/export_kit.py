"""
export_kit.py — Criação do Pacote de Publicação Viral Estruturado
Salva a pasta do corte em data/<video_id>/<PREFIXO>_<Palavras_Do_Titulo>/
com vídeo renderizado, info_publicacao.txt (incluindo dados do vídeo original),
descricao.txt e tags.txt.
"""

import os
import re
import shutil


def build_cut_folder_name(aspect_mode: str, title: str) -> str:
    """
    Gera o nome padronizado da pasta e arquivos conforme a regra de negócio:
    
    Prefixos de 5 letras:
      - Vertical 9:16 ( Layout Dividido Split Screen... )           -> VLDSS
      - Vertical 9:16 ( Rastreamento Inteligente de Rosto / Auto )  -> VRIRA
      - Vertical 9:16 ( Fundo Desfocado / Blur-Short )              -> VFDBS
      - Vertical 9:16 ( Corte Central 100% Tela )                   -> VCCFT
      - Horizontal ( Original Full HD )                             -> HOFHD
      
    Sufixo do Título:
      Primeiras palavras COMPLETAS do título, com no MÁXIMO 25 caracteres.
      Caso a próxima palavra ultrapasse o limite de 25 caracteres, ela é descartada.
    """
    prefix_map = {
        "9:16_split": "VLDSS",
        "9:16_smart_face": "VRIRA",
        "9:16_blur": "VFDBS",
        "9:16_crop": "VCCFT",
        "16:9": "HOFHD"
    }
    prefix = prefix_map.get(aspect_mode, "VRIRA")

    # Limpa caracteres especiais, mantendo letras e números
    clean_title = re.sub(r'[^\w\s]', '', title).strip()
    words = clean_title.split()

    selected_words = []
    current_len = 0

    for w in words:
        added_len = len(w) if not selected_words else (len(w) + 1)
        if current_len + added_len <= 25:
            selected_words.append(w)
            current_len += added_len
        else:
            break

    title_suffix = "_".join(selected_words) if selected_words else "corte"
    return f"{prefix}_{title_suffix}"


def create_viral_package(
    video_path: str,
    title: str,
    description: str,
    hashtags: list,
    tags_seo: str,
    aspect_mode: str,
    output_base_dir: str,
    orig_video_info: dict = None,
    thumbnail_path: str = None,
) -> dict:
    """
    Cria a pasta estruturada do corte dentro de data/<video_id>/<PREFIXO>_<Palavras>/
    e gera:
    1. Vídeo renderizado (.mp4) nomeado com o código do corte
    2. Capa / Thumbnail 9:16 (thumbnail.jpg) em alta resolução
    3. info_publicacao.txt (guia completo de postagem + dados do vídeo original)
    4. descricao.txt (apenas a legenda pronta para colar)
    5. tags.txt (hashtags e tags SEO)
    """
    try:
        folder_name = build_cut_folder_name(aspect_mode, title)
        package_dir = os.path.join(output_base_dir, folder_name)
        os.makedirs(package_dir, exist_ok=True)

        # 1. Copia o vídeo renderizado com o nome padronizado
        video_filename = f"{folder_name}.mp4"
        video_dest_path = os.path.join(package_dir, video_filename)
        if os.path.exists(video_path):
            shutil.copy2(video_path, video_dest_path)

        # 2. Copia ou move a thumbnail gerada
        thumb_dest_path = None
        thumb_filename = "thumbnail.jpg"
        if thumbnail_path and os.path.exists(thumbnail_path):
            thumb_dest_path = os.path.join(package_dir, thumb_filename)
            shutil.copy2(thumbnail_path, thumb_dest_path)

        # Formata hashtags
        hashtags_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags) if hashtags else "#shorts #viral #cortes"

        # Dados do vídeo original
        orig_info = orig_video_info or {}
        orig_title = orig_info.get("title", "Título Desconhecido")
        orig_channel = orig_info.get("channel", "Canal Desconhecido")
        orig_date = orig_info.get("upload_date", "Data N/D")
        orig_url = orig_info.get("url", "")

        thumb_info_str = f"• Capa / Thumbnail: {thumb_filename}\n" if thumb_dest_path else ""

        # 3. info_publicacao.txt
        info_content = f"""════════════════════════════════════════════════════════════════
🚀 PACOTE DE PUBLICAÇÃO VIRAL
📁 CÓDIGO DO CORTE: {folder_name}
════════════════════════════════════════════════════════════════

📌 TÍTULO DO CORTE:
{title}

📝 DESCRIÇÃO / LEGENDA (Instagram Reels, TikTok, YouTube Shorts):
{description}

{hashtags_str}

🏷️ TAGS SEO (separadas por vírgula):
{tags_seo}

🎬 ARQUIVO DE VÍDEO GERADO:
{video_filename}
{thumb_info_str}
════════════════════════════════════════════════════════════════
📺 INFORMAÇÕES DO VÍDEO ORIGINAL
════════════════════════════════════════════════════════════════
• Título Original: {orig_title}
• Canal do YouTube: {orig_channel}
• Data de Lançamento: {orig_date}
• Link do Vídeo: {orig_url}
"""
        with open(os.path.join(package_dir, "info_publicacao.txt"), "w", encoding="utf-8") as f:
            f.write(info_content)

        # 4. descricao.txt
        desc_content = f"{description}\n\n{hashtags_str}"
        with open(os.path.join(package_dir, "descricao.txt"), "w", encoding="utf-8") as f:
            f.write(desc_content)

        # 5. tags.txt
        tags_content = f"HASHTAGS:\n{hashtags_str}\n\nTAGS SEO:\n{tags_seo}\n"
        with open(os.path.join(package_dir, "tags.txt"), "w", encoding="utf-8") as f:
            f.write(tags_content)

        return {
            "folder_name": folder_name,
            "package_dir": package_dir,
            "video_filename": video_filename,
            "video_dest_path": video_dest_path,
            "thumbnail_filename": thumb_filename if thumb_dest_path else None,
            "thumbnail_dest_path": thumb_dest_path,
            "error": None
        }

    except Exception as exc:
        return {
            "folder_name": "corte_viral",
            "package_dir": output_base_dir,
            "video_filename": f"{aspect_mode}_corte.mp4",
            "video_dest_path": video_path,
            "error": str(exc)
        }
