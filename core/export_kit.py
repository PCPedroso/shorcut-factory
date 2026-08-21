"""
export_kit.py — Criação do Pacote de Publicação Viral Estruturado
Salva a pasta do corte em data/<video_id>/<PREFIXO>_<Palavras_Do_Titulo>/
com vídeo renderizado, textos de publicação, tags e arquivo ZIP compactado.
"""

import os
import re
import shutil
import zipfile


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
    output_base_dir: str
) -> dict:
    """
    Cria a pasta estruturada do corte dentro de data/<video_id>/<PREFIXO>_<Palavras>/
    e gera:
    1. Vídeo renderizado (.mp4) nomeado com o código do corte
    2. info_publicacao.txt (guia completo de postagem formatado)
    3. descricao.txt (apenas a legenda pronta para colar)
    4. tags.txt (hashtags e tags SEO)
    5. Pacote compactado .zip para download rápido
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

        # Formata hashtags
        hashtags_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags) if hashtags else "#shorts #viral #cortes"

        # 2. info_publicacao.txt
        info_content = f"""════════════════════════════════════════════════════════════════
🚀 PACOTE DE PUBLICAÇÃO VIRAL — {title}
📁 CÓDIGO DO CORTE: {folder_name}
════════════════════════════════════════════════════════════════

📌 TÍTULO DO VÍDEO:
{title}

📝 DESCRIÇÃO / LEGENDA (Instagram Reels, TikTok, YouTube Shorts):
{description}

{hashtags_str}

🏷️ TAGS SEO (separadas por vírgula):
{tags_seo}

🎬 ARQUIVO DE VÍDEO:
{video_filename}
"""
        with open(os.path.join(package_dir, "info_publicacao.txt"), "w", encoding="utf-8") as f:
            f.write(info_content)

        # 3. descricao.txt
        desc_content = f"{description}\n\n{hashtags_str}"
        with open(os.path.join(package_dir, "descricao.txt"), "w", encoding="utf-8") as f:
            f.write(desc_content)

        # 4. tags.txt
        tags_content = f"HASHTAGS:\n{hashtags_str}\n\nTAGS SEO:\n{tags_seo}\n"
        with open(os.path.join(package_dir, "tags.txt"), "w", encoding="utf-8") as f:
            f.write(tags_content)

        # 5. Gera arquivo ZIP
        zip_filename = f"{folder_name}_kit_publicacao.zip"
        zip_dest_path = os.path.join(package_dir, zip_filename)
        with zipfile.ZipFile(zip_dest_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(package_dir):
                for file in files:
                    if file == zip_filename:
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=package_dir)
                    zipf.write(file_path, arcname=arcname)

        return {
            "folder_name": folder_name,
            "package_dir": package_dir,
            "zip_path": zip_dest_path,
            "video_filename": video_filename,
            "video_dest_path": video_dest_path,
            "error": None
        }

    except Exception as exc:
        return {
            "folder_name": "corte_viral",
            "package_dir": output_base_dir,
            "zip_path": None,
            "video_filename": f"{aspect_mode}_corte.mp4",
            "video_dest_path": video_path,
            "error": str(exc)
        }
