import re
from typing import Optional, Dict, Any, List

class InstagramDetector:
    """
    Identifica menções de produtos da Shopee em legendas e metadados de posts do Instagram.
    Extrai códigos de links (ex: "Link 45", "Código 12"), chamadas de ação e calcula sinais de viralidade.
    """

    REEL_URL_REGEX = re.compile(
        r"instagram\.com\/(?:reel|p|tv)\/([A-Za-z0-9_-]+)",
        re.IGNORECASE
    )

    # Padrões comuns usados por criadores de achadinhos:
    # "Link 34", "link: 34", "código 102", "nº 5", "produto 12", "achadinho 44"
    CODE_PATTERNS = [
        re.compile(r"(?:link|c[oó]digo|n[uú]mero|n[ºo]|ref|produto|achadinho)\s*[:#-]?\s*(\d{1,5})\b", re.IGNORECASE),
        re.compile(r"\b(\d{1,5})\s*[-–]\s*(?:link|shopee|achadinho)", re.IGNORECASE),
        re.compile(r"comente\s*[\"']?(\w+)[\"']?", re.IGNORECASE)  # Ex: Comente "QUERO"
    ]

    @classmethod
    def extract_shortcode(cls, url: str) -> Optional[str]:
        """Extrai o shortcode (ID único) do Reel ou Post do Instagram."""
        m = cls.REEL_URL_REGEX.search(url)
        return m.group(1) if m else None

    @classmethod
    def extract_product_references(cls, caption: str) -> Dict[str, Any]:
        """
        Analisa a legenda procurando por códigos numéricos de catálogo,
        gatilhos de automação (ManyChat) e referências a link na bio.
        """
        result = {
            "catalog_codes": [],
            "automation_triggers": [],
            "has_bio_reference": False,
            "has_shopee_mention": False
        }

        if not caption:
            return result

        caption_lower = caption.lower()
        result["has_bio_reference"] = any(k in caption_lower for k in ["bio", "perfil", "link na bio", "destaques"])
        result["has_shopee_mention"] = any(k in caption_lower for k in ["shopee", "achadinho", "achadinhos"])

        # Procura códigos numéricos
        for pattern in cls.CODE_PATTERNS[:2]:
            matches = pattern.findall(caption)
            for m in matches:
                if m not in result["catalog_codes"]:
                    result["catalog_codes"].append(m)

        # Procura triggers (ex: Comente QUERO, Comente EU QUERO)
        m_trigger = cls.CODE_PATTERNS[2].search(caption)
        if m_trigger:
            result["automation_triggers"].append(m_trigger.group(1).upper())

        return result

    @staticmethod
    def calculate_viral_engagement(views: int, likes: int, comments: int) -> Dict[str, float]:
        """
        Calcula taxas de engajamento e potencial viral de um Reel.
        Em vídeos de vendas da Shopee, uma alta taxa de comentários ("quero")
        é o principal preditor de conversão comercial.
        """
        views = max(views, 1)
        like_rate = (likes / views) * 100.0
        comment_rate = (comments / views) * 100.0

        # Score de Potencial de Compra: Comentários têm peso 4x maior que likes
        # pois indicam intenção ativa de pedir o link.
        intent_score = round(min(100.0, (comment_rate * 25.0) + (like_rate * 5.0)), 2)

        return {
            "like_rate_pct": round(like_rate, 2),
            "comment_rate_pct": round(comment_rate, 2),
            "intent_score": intent_score
        }

    @classmethod
    def fetch_instagram_metadata(cls, url: str) -> Dict[str, Any]:
        """
        Consulta automaticamente os metadados do post/Reel do Instagram via yt-dlp:
        autor, legenda completa, visualizações, likes e comentários.
        """
        data = {
            "title": "",
            "uploader": "",
            "caption": "",
            "views": 0,
            "likes": 0,
            "comments": 0,
            "success": False,
            "error": None
        }
        try:
            import yt_dlp
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                data["title"] = info.get("title", "")
                data["uploader"] = info.get("uploader", "") or info.get("channel", "")
                data["caption"] = info.get("description", "") or ""
                data["views"] = info.get("view_count") or 0
                data["likes"] = info.get("like_count") or 0
                data["comments"] = info.get("comment_count") or 0
                data["success"] = True
        except Exception as e:
            data["error"] = str(e)

        return data

