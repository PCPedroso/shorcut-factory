"""
core/publishing/caption_adapter.py — Adaptador Inteligente de Títulos, Legendas e Tags por Rede Social.
Garante que cada plataforma receba textos calibrados exatamente para seus limites estritos
de caracteres, contagem de hashtags e formato de tags SEO, incluindo créditos do criador original.
"""

from typing import List, Dict, Any, Optional
from .base import Platform, AdaptedCaption


class CaptionAdapter:
    """
    Formata e valida os metadados do kit de publicação para cada plataforma social.
    """

    @classmethod
    def adapt(
        cls,
        platform: Platform,
        title: str,
        description: str,
        hashtags: List[str],
        tags_seo: str = "",
        orig_video_info: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AdaptedCaption:
        """Adapta título, descrição e tags para a plataforma informada."""
        options = options or {}
        include_credits = options.get("include_credits", True)

        # Higienização inicial
        clean_title = (title or "Corte Viral").strip()
        clean_desc = (description or "").strip()
        clean_hashtags = [
            h if h.startswith("#") else f"#{h}"
            for h in hashtags if h and h.strip()
        ]

        if platform == Platform.YOUTUBE:
            return cls._adapt_for_youtube(clean_title, clean_desc, clean_hashtags, tags_seo, orig_video_info, include_credits)
        elif platform == Platform.INSTAGRAM:
            return cls._adapt_for_instagram(clean_title, clean_desc, clean_hashtags, orig_video_info, include_credits)
        elif platform == Platform.TIKTOK:
            return cls._adapt_for_tiktok(clean_title, clean_desc, clean_hashtags, orig_video_info, include_credits)
        elif platform == Platform.X:
            return cls._adapt_for_x(clean_title, clean_hashtags, orig_video_info, include_credits)
        elif platform == Platform.KWAI:
            return cls._adapt_for_kwai(clean_title, clean_desc, clean_hashtags, orig_video_info, include_credits)
        else:
            return cls._adapt_generic(clean_title, clean_desc, clean_hashtags, tags_seo)

    @classmethod
    def _adapt_for_youtube(
        cls,
        title: str,
        desc: str,
        hashtags: List[str],
        tags_seo: str,
        orig_info: Optional[Dict[str, Any]],
        include_credits: bool
    ) -> AdaptedCaption:
        # Título máx 100 caracteres com #Shorts
        t = title
        if "#Shorts" not in t and "#shorts" not in t.lower():
            if len(t) <= 90:
                t = f"{t} #Shorts"
            else:
                t = f"{t[:87]}... #Shorts"
        if len(t) > 100:
            t = t[:97] + "..."

        # Descrição com créditos e hashtags
        desc_parts = [desc]
        if hashtags:
            desc_parts.append(" ".join(hashtags[:10]))

        if include_credits and orig_info:
            channel = orig_info.get("channel", "")
            orig_title = orig_info.get("title", "")
            orig_url = orig_info.get("url", "")
            credit_lines = ["\n── Créditos do Conteúdo Original ──"]
            if channel:
                credit_lines.append(f"Canal: {channel}")
            if orig_title:
                credit_lines.append(f"Vídeo: {orig_title}")
            if orig_url:
                credit_lines.append(f"Link: {orig_url}")
            desc_parts.append("\n".join(credit_lines))

        full_desc = "\n\n".join(filter(None, desc_parts))
        if len(full_desc) > 5000:
            full_desc = full_desc[:4990] + "..."

        # Tags SEO sem '#' somando até 500 caracteres
        clean_tags_list = []
        accum_len = 0
        raw_tags = [t.strip().lstrip("#") for t in (tags_seo or "").split(",") if t.strip()]
        for tag in raw_tags:
            tag_cost = len(tag) + 1
            if accum_len + tag_cost <= 500:
                clean_tags_list.append(tag)
                accum_len += tag_cost

        return AdaptedCaption(
            platform=Platform.YOUTUBE,
            title=t,
            description=full_desc,
            hashtags=hashtags[:10],
            tags_seo=clean_tags_list,
            full_text=f"{t}\n\n{full_desc}",
            character_count=len(full_desc),
            max_characters=5000,
            is_within_limits=True
        )

    @classmethod
    def _adapt_for_instagram(
        cls,
        title: str,
        desc: str,
        hashtags: List[str],
        orig_info: Optional[Dict[str, Any]],
        include_credits: bool
    ) -> AdaptedCaption:
        # Legenda até 2200 caracteres, máx 30 hashtags
        parts = []
        if title:
            parts.append(f"🔥 {title}\n")
        if desc:
            parts.append(desc)

        if include_credits and orig_info:
            channel = orig_info.get("channel")
            if channel:
                parts.append(f"\n🎬 Canal: {channel}")

        # Limite rigoroso de 30 hashtags no Instagram
        ig_tags = hashtags[:30]
        if ig_tags:
            parts.append("\n" + " ".join(ig_tags))

        full_caption = "\n".join(parts).strip()
        warnings = []
        if len(full_caption) > 2200:
            full_caption = full_caption[:2190] + "..."
            warnings.append("Legenda reduzida para 2200 caracteres (limite do Instagram).")

        return AdaptedCaption(
            platform=Platform.INSTAGRAM,
            title=title,
            description=full_caption,
            hashtags=ig_tags,
            full_text=full_caption,
            character_count=len(full_caption),
            max_characters=2200,
            is_within_limits=len(full_caption) <= 2200,
            warnings=warnings
        )

    @classmethod
    def _adapt_for_tiktok(
        cls,
        title: str,
        desc: str,
        hashtags: List[str],
        orig_info: Optional[Dict[str, Any]],
        include_credits: bool
    ) -> AdaptedCaption:
        # Limite de 2200 caracteres no Direct Post
        parts = [title]
        if desc and desc != title:
            parts.append(desc)

        if include_credits and orig_info:
            channel = orig_info.get("channel")
            if channel:
                parts.append(f"Créditos: {channel}")

        tt_tags = hashtags[:15]
        if tt_tags:
            parts.append(" ".join(tt_tags))

        full_text = "\n\n".join(parts).strip()
        warnings = []
        if len(full_text) > 2200:
            full_text = full_text[:2190] + "..."
            warnings.append("Texto ajustado para limite de 2200 caracteres do TikTok.")

        return AdaptedCaption(
            platform=Platform.TIKTOK,
            title=title[:100],
            description=full_text,
            hashtags=tt_tags,
            full_text=full_text,
            character_count=len(full_text),
            max_characters=2200,
            is_within_limits=len(full_text) <= 2200,
            warnings=warnings
        )

    @classmethod
    def _adapt_for_x(
        cls,
        title: str,
        hashtags: List[str],
        orig_info: Optional[Dict[str, Any]],
        include_credits: bool
    ) -> AdaptedCaption:
        # Limite rigoroso de 280 caracteres
        # No X, qualquer URL ocupa 23 caracteres (t.co)
        top_tags = hashtags[:2]
        tags_str = " ".join(top_tags)

        url_str = ""
        if include_credits and orig_info and orig_info.get("url"):
            url_str = orig_info["url"]

        # No X, URLs ocupam 23 caracteres no t.co; reservamos o tamanho real para garantir len <= 280
        url_len_budget = max(24, (len(url_str) + 1) if url_str else 0)
        tags_cost = (len(tags_str) + 1) if tags_str else 0
        available_title_chars = max(20, 280 - url_len_budget - tags_cost - 4)

        t = title
        if len(t) > available_title_chars:
            t = t[:max(10, available_title_chars - 3)] + "..."

        x_parts = [t]
        if url_str:
            x_parts.append(url_str)
        if tags_str:
            x_parts.append(tags_str)

        tweet_text = " ".join(x_parts).strip()
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."

        return AdaptedCaption(
            platform=Platform.X,
            title=t,
            description=tweet_text,
            hashtags=top_tags,
            full_text=tweet_text,
            character_count=len(tweet_text),
            max_characters=280,
            is_within_limits=len(tweet_text) <= 280
        )

    @classmethod
    def _adapt_for_kwai(
        cls,
        title: str,
        desc: str,
        hashtags: List[str],
        orig_info: Optional[Dict[str, Any]],
        include_credits: bool
    ) -> AdaptedCaption:
        parts = [f"🔥 {title}"]
        if desc and desc != title:
            parts.append(desc)
        if include_credits and orig_info and orig_info.get("channel"):
            parts.append(f"Créditos: {orig_info['channel']}")

        kw_tags = hashtags[:10]
        if kw_tags:
            parts.append(" ".join(kw_tags))

        full_kwai = "\n\n".join(parts)
        return AdaptedCaption(
            platform=Platform.KWAI,
            title=title,
            description=full_kwai,
            hashtags=kw_tags,
            full_text=full_kwai,
            character_count=len(full_kwai),
            max_characters=1000,
            is_within_limits=True
        )

    @classmethod
    def _adapt_generic(
        cls,
        title: str,
        desc: str,
        hashtags: List[str],
        tags_seo: str
    ) -> AdaptedCaption:
        full = f"{title}\n\n{desc}\n\n{' '.join(hashtags)}"
        return AdaptedCaption(
            platform=Platform.YOUTUBE,
            title=title,
            description=desc,
            hashtags=hashtags,
            tags_seo=[t.strip() for t in tags_seo.split(",") if t.strip()],
            full_text=full,
            character_count=len(full),
            max_characters=5000,
            is_within_limits=True
        )
