"""
export_kit.py — Criação do Pacote de Publicação Viral (Vídeo + Descrição + Hashtags + Tags SEO + ZIP)
"""

import os
import re
import shutil
import zipfile


def sanitize_filename(name: str) -> str:
    """
    Sanitiza uma string para ser usada com segurança como nome de arquivo e pasta em Windows/Linux/Mac.
    Remove caracteres especiais, pontuações e acentos excessivos, substituindo espaços por sublinhados.
    """
    # Remove caracteres inválidos no Windows: <>:"/\|?*
    clean = re.sub(r'[<>:"/\\|?*]', '', name)
    # Substitui múltiplos espaços e hífens por underscore
    clean = re.sub(r'[\s\-]+', '_', clean).strip('._ ')
    if not clean:
        clean = "corte_viral"
    # Limita tamanho do nome
    return clean[:70]


def create_viral_package(
    video_path: str,
    title: str,
    description: str,
    hashtags: list,
    tags_seo: str,
    output_base_dir: str
) -> dict:
    """
    Cria a pasta estruturada do corte e gera o arquivo ZIP contendo:
    1. Vídeo renderizado (.mp4) com o nome baseado no título
    2. info_publicacao.txt (resumo completo pronto para copiar e postar)
    3. descricao.txt (apenas a legenda)
    4. tags.txt (hashtags e tags SEO)
    5. Pacote compactado .zip para download com 1 clique no navegador
    """
    try:
        safe_title = sanitize_filename(title)
        cortes_dir = os.path.join(output_base_dir, "cortes")
        package_dir = os.path.join(cortes_dir, safe_title)
        os.makedirs(package_dir, exist_ok=True)

        # 1. Copia o vídeo com o novo nome
        video_filename = f"{safe_title}.mp4"
        video_dest_path = os.path.join(package_dir, video_filename)
        if os.path.exists(video_path):
            shutil.copy2(video_path, video_dest_path)

        # Formata hashtags
        hashtags_str = " ".join(h if h.startswith("#") else f"#{h}" for h in hashtags) if hashtags else "#shorts #viral #cortes"

        # 2. info_publicacao.txt
        info_content = f"""════════════════════════════════════════════════════════════════
🚀 PACOTE DE PUBLICAÇÃO VIRAL — {title}
════════════════════════════════════════════════════════════════

📌 TÍTULO DO VÍDEO:
{title}

📝 DESCRIÇÃO / LEGENDA (Instagram Reels, TikTok, YouTube Shorts):
{description}

{hashtags_str}

🏷️ TAGS SEO (separadas por vírgula):
{tags_seo}

📁 ARQUIVO DE VÍDEO:
{video_filename}
"""
        with open(os.path.join(package_dir, "info_publicacao.txt"), "w", encoding="utf-8") as f:
            f.write(info_content)

        # 3. descricao.txt (apenas o texto da descrição + hashtags)
        desc_content = f"{description}\n\n{hashtags_str}"
        with open(os.path.join(package_dir, "descricao.txt"), "w", encoding="utf-8") as f:
            f.write(desc_content)

        # 4. tags.txt (tags SEO + hashtags)
        tags_content = f"HASHTAGS:\n{hashtags_str}\n\nTAGS SEO:\n{tags_seo}\n"
        with open(os.path.join(package_dir, "tags.txt"), "w", encoding="utf-8") as f:
            f.write(tags_content)

        # 5. Gera arquivo ZIP
        zip_filename = f"{safe_title}_kit_publicacao.zip"
        zip_dest_path = os.path.join(cortes_dir, zip_filename)
        with zipfile.ZipFile(zip_dest_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=package_dir)
                    zipf.write(file_path, arcname=arcname)

        return {
            "package_dir": package_dir,
            "zip_path": zip_dest_path,
            "video_filename": video_filename,
            "video_dest_path": video_dest_path,
            "safe_title": safe_title,
            "error": None
        }

    except Exception as exc:
        return {
            "package_dir": None,
            "zip_path": None,
            "video_filename": f"{sanitize_filename(title)}.mp4",
            "video_dest_path": video_path,
            "safe_title": sanitize_filename(title),
            "error": str(exc)
        }
