import time
from typing import Optional, Dict, Any, List
from .link_resolver import ShopeeLinkResolver
from .shopee_client import ShopeeClient
from .catalog_resolver import CatalogResolver
from .instagram_detector import InstagramDetector
from .trend_engine import ShopeeTrendEngine
from .rate_limiter import ShopeeRateLimiter

class ShopeeRadarService:
    """
    Serviço central que orquestra a detecção de produtos no Instagram,
    resolução de links, enriquecimento de vendas na Shopee, controle de taxa anti-bloqueio
    e cálculo de tendências comerciais.
    """

    def __init__(
        self,
        db_path: str = "data/shopee_trends.db",
        rate_limiter: Optional[ShopeeRateLimiter] = None
    ):
        self.link_resolver = ShopeeLinkResolver()
        self.shopee_client = ShopeeClient()
        self.catalog_resolver = CatalogResolver()
        self.detector = InstagramDetector()
        self.engine = ShopeeTrendEngine(db_path=db_path)
        self.rate_limiter = rate_limiter or ShopeeRateLimiter()

    def get_protection_status(self) -> Dict[str, Any]:
        """Retorna o status do rate limiter e da proteção de IP."""
        return self.rate_limiter.get_status_info()

    def analyze_instagram_post(
        self,
        post_url: str,
        caption: str = "",
        catalog_url: Optional[str] = None,
        views: int = 0,
        likes: int = 0,
        comments: int = 0,
        direct_shopee_url: Optional[str] = None,
        force_refresh: bool = False,
        cache_ttl_hours: float = 6.0
    ) -> Dict[str, Any]:
        """
        Processa um post/Reel do Instagram com proteção integrada de IP:
        1. Identifica menção de produto ou link direto
        2. Resolve códigos de catálogo (Linktree/MyCollection) para URL da Shopee
        3. Desencurta e extrai IDs da Shopee
        4. Verifica se o produto já está em cache local dentro do TTL
        5. Se necessário consultar a Shopee, aplica rate limiter, jitter e registra a quota
        6. Persiste dados e calcula o score de viralidade comercial
        """
        result: Dict[str, Any] = {
            "post_url": post_url,
            "uploader": "",
            "caption": caption,
            "product_found": False,
            "shopee_product": None,
            "instagram_metrics": None,
            "velocity": None,
            "viral_score": 0.0,
            "from_cache": False,
            "diagnostic": None,
            "notes": []
        }

        # Auto-fetch via yt-dlp se caption ou métricas não foram passadas e é uma URL do Instagram
        if (not caption or (likes == 0 and comments == 0)) and "instagram.com" in post_url:
            auto_meta = self.detector.fetch_instagram_metadata(post_url)
            if auto_meta.get("success"):
                if not caption:
                    caption = auto_meta.get("caption", "")
                result["caption"] = caption
                result["uploader"] = auto_meta.get("uploader", "")
                if views == 0:
                    views = auto_meta.get("views", 0)
                if likes == 0:
                    likes = auto_meta.get("likes", 0)
                if comments == 0:
                    comments = auto_meta.get("comments", 0)
                result["notes"].append(f"Auto-leitura do Instagram concluída (@{auto_meta.get('uploader')} - {likes} likes, {comments} coms).")

        # 1. Análise do post do Instagram
        refs = self.detector.extract_product_references(caption)
        engagement = self.detector.calculate_viral_engagement(views, likes, comments)
        result["instagram_metrics"] = {
            "views": views,
            "likes": likes,
            "comments": comments,
            "references": refs,
            "engagement": engagement
        }

        # 2. Localização da URL da Shopee
        target_shopee_url = direct_shopee_url

        if not target_shopee_url:
            short_urls = self.link_resolver.extract_short_urls(caption)
            if short_urls:
                target_shopee_url = short_urls[0]
                result["notes"].append(f"Link detectado na legenda: {target_shopee_url}")

        if not target_shopee_url and refs["catalog_codes"] and catalog_url:
            code = refs["catalog_codes"][0]
            resolved_from_catalog = self.catalog_resolver.find_item_by_code(catalog_url, code)
            if resolved_from_catalog:
                target_shopee_url = resolved_from_catalog
                result["notes"].append(f"Código {code} resolvido no catálogo: {target_shopee_url}")
            else:
                result["notes"].append(f"Código {code} detectado, mas não encontrado no catálogo {catalog_url}.")

        if not target_shopee_url:
            result["diagnostic"] = "no_link_in_post"
            result["notes"].append("Nenhum link ou código de produto Shopee foi encontrado na legenda deste vídeo.")

            self.engine.record_instagram_mention(
                post_url=post_url,
                caption=caption,
                views=views,
                likes=likes,
                comments=comments,
                intent_score=engagement["intent_score"]
            )
            return result

        # 3. Resolução de redirecionamento e extração de IDs
        resolved = self.link_resolver.resolve_url(target_shopee_url)
        if not resolved["success"]:
            result["notes"].append(f"Falha ao resolver URL da Shopee: {resolved.get('error')}")
            return result

        shop_id = resolved["shop_id"]
        item_id = resolved["item_id"]

        # 4. Verificação de Cache Local vs Consulta Externa à Shopee
        cached_product = None
        if not force_refresh:
            cached_product = self.engine.get_cached_product(shop_id, item_id, max_age_hours=cache_ttl_hours)

        product_data = None
        if cached_product:
            product_data = cached_product
            result["from_cache"] = True
            age_min = cached_product.get("cache_age_minutes", 0)
            result["notes"].append(f"🛡️ Cache Ativo: dados carregados localmente (há {age_min} min). IP protegido.")
        else:
            # Requer consulta externa: aguarda cooldown curto automaticamente
            ok, msg = self.rate_limiter.wait_if_needed(max_wait_sec=5.0)
            if not ok:
                # Tenta fallback de cache antigo (até 7 dias)
                fallback = self.engine.get_cached_product(shop_id, item_id, max_age_hours=168.0)
                if fallback:
                    product_data = fallback
                    result["from_cache"] = True
                    result["notes"].append(f"⚠️ {msg} - Exibindo último snapshot em cache.")
                else:
                    result["notes"].append(f"🚫 {msg}")
                    return result
            else:
                self.rate_limiter.apply_safe_delay()
                product_data = self.shopee_client.get_product_details(shop_id, item_id)
                self.rate_limiter.record_request_made()

                if not product_data["success"]:
                    # Fallback gracioso: o link foi resolvido com sucesso
                    product_data = {
                        "shop_id": shop_id,
                        "item_id": item_id,
                        "title": f"Produto Shopee #{item_id}",
                        "price": 0.0,
                        "historical_sold": 0,
                        "monthly_sold": 0,
                        "rating_star": 5.0,
                        "rating_count": 0,
                        "stock": 0,
                        "image_url": "",
                        "url": resolved.get("canonical_url", target_shopee_url),
                        "success": True,
                        "status_note": "Identificado via Link (Proteção WAF Shopee)"
                    }
                    self.engine.record_product(product_data)
                    result["notes"].append("Link do produto desmascarado e salvo no banco local.")
                else:
                    self.engine.record_product(product_data)
                    result["notes"].append("⚡ Consulta externa realizada e salva em cache com sucesso.")

        result["product_found"] = True
        result["shopee_product"] = product_data


        # 5. Registra menção do Instagram
        self.engine.record_instagram_mention(
            post_url=post_url,
            shop_id=shop_id,
            item_id=item_id,
            caption=caption,
            views=views,
            likes=likes,
            comments=comments,
            intent_score=engagement["intent_score"]
        )

        # 6. Cálculo de velocidade e score de oportunidade
        velocity = self.engine.get_sales_velocity(shop_id, item_id)
        result["velocity"] = velocity

        monthly_pts = min(40.0, (product_data.get("monthly_sold", 0) / 1000.0) * 10.0)
        delta_pts = min(30.0, velocity.get("delta_sold", 0) * 3.0)
        ig_pts = min(30.0, engagement["intent_score"] * 0.3)
        result["viral_score"] = round(monthly_pts + delta_pts + ig_pts, 1)

        return result

    def refresh_tracked_products(
        self,
        max_batch_size: int = 5,
        min_age_hours: float = 12.0
    ) -> Dict[str, Any]:
        """
        Atualiza produtos no banco respeitando rigorosamente o Rate Limiter e quota horária.
        Apenas produtos mais antigos que min_age_hours são atualizados, limitados a max_batch_size.
        """
        top_products = self.engine.get_top_trending_products(limit=100)
        now = int(time.time())
        min_age_sec = int(min_age_hours * 3600)

        eligible = [
            p for p in top_products
            if (now - (p.get("updated_at") or 0)) >= min_age_sec
        ][:max_batch_size]

        updated_count = 0
        skipped_count = 0

        for prod in eligible:
            can_req, msg, wait_sec = self.rate_limiter.check_can_request()
            if not can_req:
                skipped_count += 1
                break

            self.rate_limiter.apply_safe_delay()
            fresh = self.shopee_client.get_product_details(prod["shop_id"], prod["item_id"])
            self.rate_limiter.record_request_made()

            if fresh["success"]:
                self.engine.record_product(fresh)
                updated_count += 1

        return {
            "eligible_count": len(eligible),
            "updated_count": updated_count,
            "skipped_count": skipped_count
        }

    def get_top_opportunities(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retorna o ranking de produtos com maior tração e viralidade."""
        return self.engine.get_top_trending_products(limit=limit)

    def scan_storefront(
        self,
        storefront_url: str,
        max_items: int = 15,
        force_refresh: bool = False,
        cache_ttl_hours: float = 6.0
    ) -> Dict[str, Any]:
        """
        Rastreia de forma autônoma todos os produtos da vitrine de um criador (Linktree, Beacons, etc.),
        sem depender de um post específico do Instagram.
        Retorna o ranking dos produtos mais vendidos daquela vitrine na Shopee.
        """
        storefront_url = storefront_url.strip()
        inspection = self.catalog_resolver.inspect_storefront(storefront_url)
        items = self.catalog_resolver.extract_storefront_items(storefront_url)

        summary = {
            "storefront_url": storefront_url,
            "total_items_found": len(items),
            "categories_found": inspection.get("categories", []),
            "processed_count": 0,
            "cached_count": 0,
            "new_fetched_count": 0,
            "products": [],
            "skipped_items": [],
            "skipped_reason": None
        }

        if not items:
            if summary["categories_found"]:
                summary["skipped_reason"] = "Esta vitrine funciona como um menu de categorias/pastas. Selecione uma categoria abaixo para explorar os produtos."
            else:
                summary["skipped_reason"] = "Nenhum link de produto Shopee foi encontrado nesta vitrine."
            return summary

        # Limita a quantidade para proteger a quota
        target_items = items[:max_items]

        for it in target_items:
            raw_url = it.get("url")
            creator_title = it.get("title", "")
            cat_name = it.get("category_name", "")
            if not raw_url:
                continue

            # 1. Resolve URL
            resolved = self.link_resolver.resolve_url(raw_url)
            if not resolved["success"]:
                summary["skipped_items"].append({
                    "title": creator_title or "Link sem título",
                    "url": raw_url,
                    "reason": resolved.get("error", "Não foi possível identificar o produto na Shopee."),
                    "category": cat_name
                })
                continue

            shop_id = resolved["shop_id"]
            item_id = resolved["item_id"]

            # 2. Cache vs Requisição Externa
            cached = None
            if not force_refresh:
                cached = self.engine.get_cached_product(shop_id, item_id, max_age_hours=cache_ttl_hours)

            prod_data = None
            if cached:
                prod_data = cached
                summary["cached_count"] += 1
            else:
                ok, msg = self.rate_limiter.wait_if_needed(max_wait_sec=5.0)
                if not ok:
                    # Tenta fallback de cache antigo
                    old_c = self.engine.get_cached_product(shop_id, item_id, max_age_hours=168.0)
                    if old_c:
                        prod_data = old_c
                        summary["cached_count"] += 1
                    else:
                        summary["skipped_reason"] = f"Pausado pela quota horária: {msg}"
                        break
                else:
                    self.rate_limiter.apply_safe_delay()
                    fresh = self.shopee_client.get_product_details(shop_id, item_id)
                    self.rate_limiter.record_request_made()
                    if fresh["success"]:
                        self.engine.record_product(fresh)
                        prod_data = fresh
                        summary["new_fetched_count"] += 1

            # Fallback gracioso: produto identificado mesmo com WAF da Shopee
            if not prod_data:
                prod_data = {
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "title": creator_title or f"Produto Shopee #{item_id}",
                    "price": 0.0,
                    "historical_sold": 0,
                    "monthly_sold": 0,
                    "rating_star": 5.0,
                    "rating_count": 0,
                    "stock": 0,
                    "image_url": "",
                    "url": resolved.get("canonical_url", raw_url),
                    "original_affiliate_url": raw_url,
                    "success": True,
                    "status_note": "Identificado na vitrine"
                }
                self.engine.record_product(prod_data)

            if prod_data:
                # Enriquecimento com o título da vitrine se houver
                if creator_title and (not prod_data.get("title") or prod_data.get("title").startswith("Produto Shopee")):
                    prod_data["title"] = creator_title
                prod_data["storefront_title"] = creator_title
                prod_data["category_name"] = cat_name
                prod_data["original_affiliate_url"] = raw_url
                velocity = self.engine.get_sales_velocity(shop_id, item_id)
                prod_data["velocity"] = velocity

                summary["products"].append(prod_data)
                summary["processed_count"] += 1

        # Diagnóstico se nenhum produto foi carregado com sucesso
        if summary["processed_count"] == 0 and summary["skipped_items"]:
            expired_n = sum(1 for s in summary["skipped_items"] if "expirado" in s.get("reason", "").lower())
            cat_n = sum(1 for s in summary["skipped_items"] if "categoria" in s.get("reason", "").lower() or "campanha" in s.get("reason", "").lower())
            msg_parts = []
            if expired_n:
                msg_parts.append(f"{expired_n} link(s) estavam expirados/desativados na Shopee (redirecionam para error_page)")
            if cat_n:
                msg_parts.append(f"{cat_n} link(s) apontavam para categorias gerais da Shopee")
            extra = f" ({'; '.join(msg_parts)})" if msg_parts else ""
            summary["skipped_reason"] = f"Nenhum produto individual pôde ser carregado desta vitrine{extra}. Abra os detalhes abaixo para ver cada link."

        # Ordena os produtos minerados pelo total de vendas mensais / históricas decrescente
        summary["products"].sort(
            key=lambda p: (p.get("monthly_sold") or 0, p.get("historical_sold") or 0),
            reverse=True
        )

        return summary

    def scan_bulk_links(
        self,
        links_or_text: str | List[str],
        max_items: int = 15,
        force_refresh: bool = False,
        cache_ttl_hours: float = 6.0
    ) -> Dict[str, Any]:
        """
        Processa uma lista avulsa de links ou texto contendo links da Shopee (ex: copiados do WhatsApp, Telegram, etc.),
        sem necessidade de dados de post do Instagram.
        """
        if isinstance(links_or_text, str):
            urls = self.link_resolver.extract_short_urls(links_or_text)
            import re
            full_urls = re.findall(r'https?:\/\/(?:www\.)?shopee\.com\.br\/[^\s\'"<>]+', links_or_text)
            all_urls = list(dict.fromkeys(urls + full_urls))
        else:
            all_urls = list(dict.fromkeys(links_or_text))

        summary = {
            "total_links_found": len(all_urls),
            "processed_count": 0,
            "cached_count": 0,
            "new_fetched_count": 0,
            "products": [],
            "skipped_reason": None
        }

        if not all_urls:
            summary["skipped_reason"] = "Nenhum link da Shopee detectado no texto."
            return summary

        target_urls = all_urls[:max_items]

        for u in target_urls:
            resolved = self.link_resolver.resolve_url(u)
            if not resolved["success"]:
                continue

            shop_id = resolved["shop_id"]
            item_id = resolved["item_id"]

            cached = None
            if not force_refresh:
                cached = self.engine.get_cached_product(shop_id, item_id, max_age_hours=cache_ttl_hours)

            prod_data = None
            if cached:
                prod_data = cached
                summary["cached_count"] += 1
            else:
                ok, msg = self.rate_limiter.wait_if_needed(max_wait_sec=5.0)
                if not ok:
                    old_c = self.engine.get_cached_product(shop_id, item_id, max_age_hours=168.0)
                    if old_c:
                        prod_data = old_c
                        summary["cached_count"] += 1
                    else:
                        summary["skipped_reason"] = f"Pausado pela quota horária: {msg}"
                        break
                else:
                    self.rate_limiter.apply_safe_delay()
                    fresh = self.shopee_client.get_product_details(shop_id, item_id)
                    self.rate_limiter.record_request_made()
                    if fresh["success"]:
                        self.engine.record_product(fresh)
                        prod_data = fresh
                        summary["new_fetched_count"] += 1

            if not prod_data:
                prod_data = {
                    "shop_id": shop_id,
                    "item_id": item_id,
                    "title": f"Produto Shopee #{item_id}",
                    "price": 0.0,
                    "historical_sold": 0,
                    "monthly_sold": 0,
                    "rating_star": 5.0,
                    "rating_count": 0,
                    "stock": 0,
                    "image_url": "",
                    "url": resolved.get("canonical_url", u),
                    "original_input_url": u,
                    "success": True,
                    "status_note": "Identificado via Link"
                }
                self.engine.record_product(prod_data)

            if prod_data:
                prod_data["original_input_url"] = u
                velocity = self.engine.get_sales_velocity(shop_id, item_id)
                prod_data["velocity"] = velocity
                summary["products"].append(prod_data)
                summary["processed_count"] += 1

        summary["products"].sort(
            key=lambda p: (p.get("monthly_sold") or 0, p.get("historical_sold") or 0),
            reverse=True
        )

        return summary

