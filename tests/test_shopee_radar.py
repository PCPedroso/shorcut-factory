import os
import tempfile
import pytest
from unittest.mock import MagicMock
from core.shopee_radar.link_resolver import ShopeeLinkResolver
from core.shopee_radar.shopee_client import ShopeeClient
from core.shopee_radar.instagram_detector import InstagramDetector
from core.shopee_radar.catalog_resolver import CatalogResolver
from core.shopee_radar.trend_engine import ShopeeTrendEngine
from core.shopee_radar.radar_service import ShopeeRadarService
from core.shopee_radar.rate_limiter import ShopeeRateLimiter


def test_link_resolver_parse_ids():
    # 1. Padrão /product/shop_id/item_id
    url1 = "https://shopee.com.br/product/12345678/987654321?sp_atk=abc-123"
    s_id, i_id = ShopeeLinkResolver.parse_ids_from_url(url1)
    assert s_id == "12345678"
    assert i_id == "987654321"

    # 2. Padrão slug-i.shop_id.item_id
    url2 = "https://shopee.com.br/Garrafa-Termica-Inox-500ml-i.87654321.1122334455"
    s_id, i_id = ShopeeLinkResolver.parse_ids_from_url(url2)
    assert s_id == "87654321"
    assert i_id == "1122334455"

    # 3. Padrão query string
    url3 = "https://shopee.com.br/universal-link?itemid=55667788&shopid=998877"
    s_id, i_id = ShopeeLinkResolver.parse_ids_from_url(url3)
    assert s_id == "998877"
    assert i_id == "55667788"


def test_link_resolver_extract_short_urls():
    resolver = ShopeeLinkResolver()
    caption = "Meninas olha esse achadinho incrível! Link aqui: https://shope.ee/abc123XYZ e https://s.shopee.com.br/def456UVW"
    urls = resolver.extract_short_urls(caption)
    assert len(urls) == 2
    assert "https://shope.ee/abc123XYZ" in urls
    assert "https://s.shopee.com.br/def456UVW" in urls


def test_link_resolver_mocked_redirect():
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.url = "https://shopee.com.br/product/555444/999888"
    mock_session.get.return_value = mock_response

    resolver = ShopeeLinkResolver(session=mock_session)
    res = resolver.resolve_url("https://shope.ee/xyz")
    assert res["success"] is True
    assert res["shop_id"] == "555444"
    assert res["item_id"] == "999888"
    assert res["canonical_url"] == "https://shopee.com.br/product/555444/999888"


def test_shopee_client_parse():
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "itemid": 999888,
            "shopid": 555444,
            "name": "Mini Processador Elétrico Triturador USB",
            "price": 2990000, # R$ 29.90
            "price_min": 2500000,
            "price_max": 2990000,
            "historical_sold": 15420,
            "sold": 1250,
            "stock": 450,
            "shop_location": "São Paulo",
            "is_official_shop": True,
            "image": "br-11134207-7r98o-xyz",
            "item_rating": {
                "rating_star": 4.85,
                "rating_count": [0, 5, 12, 50, 800]
            }
        }
    }
    mock_session.get.return_value = mock_response

    client = ShopeeClient(session=mock_session)
    data = client.get_product_details("555444", "999888")

    assert data["success"] is True
    assert data["title"] == "Mini Processador Elétrico Triturador USB"
    assert data["price"] == 29.90
    assert data["historical_sold"] == 15420
    assert data["monthly_sold"] == 1250
    assert data["rating_star"] == 4.85
    assert data["stock"] == 450
    assert "br-11134207-7r98o-xyz" in data["image_url"]


def test_instagram_detector():
    url = "https://www.instagram.com/reel/C8xyz123_AB/?igsh=abc"
    shortcode = InstagramDetector.extract_shortcode(url)
    assert shortcode == "C8xyz123_AB"

    caption = "Gente, esse organizador de geladeira mudou minha vida! Código: 345 no link da bio. Ou comente QUERO que envio no direct!"
    refs = InstagramDetector.extract_product_references(caption)
    assert "345" in refs["catalog_codes"]
    assert "QUERO" in refs["automation_triggers"]
    assert refs["has_bio_reference"] is True

    engagement = InstagramDetector.calculate_viral_engagement(views=100000, likes=5000, comments=2500)
    assert engagement["like_rate_pct"] == 5.0
    assert engagement["comment_rate_pct"] == 2.5
    assert engagement["intent_score"] > 80.0


def test_catalog_resolver_matching():
    resolver = CatalogResolver()
    # Mock extract_linktree_items
    resolver.extract_linktree_items = MagicMock(return_value=[
        {"title": "042 - Mini Selador de Embalagens", "url": "https://shope.ee/link42"},
        {"title": "105 - Fritadeira Air Fryer", "url": "https://shope.ee/link105"},
    ])

    url = resolver.find_item_by_code("https://linktr.ee/achadinhos", "42")
    assert url == "https://shope.ee/link42"

    url_105 = resolver.find_item_by_code("https://linktr.ee/achadinhos", 105)
    assert url_105 == "https://shope.ee/link105"

    url_none = resolver.find_item_by_code("https://linktr.ee/achadinhos", "999")
    assert url_none is None


def test_shopee_trend_engine(tmp_path):
    db_path = str(tmp_path / "test_shopee_trends.db")
    engine = ShopeeTrendEngine(db_path=db_path)

    # 1. Registra produto snapshot 1
    prod1 = {
        "shop_id": "1001",
        "item_id": "2002",
        "title": "Mop Giratório Limpeza Fácil",
        "price": 49.90,
        "historical_sold": 1000,
        "monthly_sold": 200,
        "rating_star": 4.9,
        "stock": 50
    }
    engine.record_product(prod1)

    # 2. Registra menção do Instagram
    engine.record_instagram_mention(
        post_url="https://instagram.com/reel/C123/",
        shop_id="1001",
        item_id="2002",
        creator="achadinhos_da_lu",
        caption="Link na bio 12",
        views=50000,
        likes=3000,
        comments=1500,
        intent_score=85.0
    )

    # 3. Registra snapshot 2 (aumento de 150 vendas)
    prod1_snap2 = dict(prod1)
    prod1_snap2["historical_sold"] = 1150
    engine.record_product(prod1_snap2)

    velocity = engine.get_sales_velocity("1001", "2002")
    assert velocity["delta_sold"] == 150
    assert velocity["snapshots_count"] == 2

    top = engine.get_top_trending_products(limit=5)
    assert len(top) == 1
    assert top[0]["title"] == "Mop Giratório Limpeza Fácil"
    assert top[0]["viral_score"] > 50.0


def test_shopee_radar_service(tmp_path):
    db_path = str(tmp_path / "service_test.db")
    service = ShopeeRadarService(db_path=db_path)

    # Mock Shopee Client
    service.shopee_client.get_product_details = MagicMock(return_value={
        "success": True,
        "item_id": "778899",
        "shop_id": "112233",
        "title": "Robô Aspirador Inteligente Bivolt",
        "price": 149.90,
        "historical_sold": 5400,
        "monthly_sold": 820,
        "rating_star": 4.8,
        "rating_count": 950,
        "stock": 120,
        "image_url": "https://img.shopee.com/robo.jpg",
        "url": "https://shopee.com.br/product/112233/778899"
    })

    # Mock Link Resolver
    service.link_resolver.resolve_url = MagicMock(return_value={
        "success": True,
        "item_id": "778899",
        "shop_id": "112233",
        "canonical_url": "https://shopee.com.br/product/112233/778899"
    })

    result = service.analyze_instagram_post(
        post_url="https://www.instagram.com/reel/C899123/",
        caption="Meninas esse robô limpa a casa toda sozinho! Link: https://shope.ee/robo123",
        views=250000,
        likes=12000,
        comments=4500
    )

    assert result["product_found"] is True
    assert result["shopee_product"]["title"] == "Robô Aspirador Inteligente Bivolt"
    assert result["viral_score"] > 20.0
    assert result["instagram_metrics"]["views"] == 250000

    opps = service.get_top_opportunities(limit=5)
    assert len(opps) == 1
    assert opps[0]["item_id"] == "778899"


def test_shopee_rate_limiter(tmp_path):
    state_file = str(tmp_path / "rate_state.json")
    limiter = ShopeeRateLimiter(
        min_interval_sec=1.0,
        max_requests_per_hour=3,
        state_file=state_file
    )

    # 1. Primeira requisição permitida
    can_req, msg, wait = limiter.check_can_request()
    assert can_req is True
    limiter.record_request_made()

    # 2. Imediatamente após, cooldown deve barrar
    can_req2, msg2, wait2 = limiter.check_can_request()
    assert can_req2 is False
    assert wait2 > 0

    # 3. Informações de status
    info = limiter.get_status_info()
    assert info["requests_last_hour"] == 1
    assert info["max_requests_per_hour"] == 3


def test_shopee_radar_cache_and_protection(tmp_path):
    db_path = str(tmp_path / "radar_cache.db")
    state_file = str(tmp_path / "rate_state.json")
    limiter = ShopeeRateLimiter(min_interval_sec=0.1, state_file=state_file)
    service = ShopeeRadarService(db_path=db_path, rate_limiter=limiter)

    # Mock Shopee Client
    service.shopee_client.get_product_details = MagicMock(return_value={
        "success": True,
        "item_id": "443322",
        "shop_id": "998877",
        "title": "Mini Selador Térmico Portátil",
        "price": 19.90,
        "historical_sold": 3000,
        "monthly_sold": 450,
        "rating_star": 4.7,
        "rating_count": 500,
        "stock": 80,
        "image_url": "https://img.shopee.com/selador.jpg",
        "url": "https://shopee.com.br/product/998877/443322"
    })

    service.link_resolver.resolve_url = MagicMock(return_value={
        "success": True,
        "item_id": "443322",
        "shop_id": "998877",
        "canonical_url": "https://shopee.com.br/product/998877/443322"
    })

    # Primeira chamada: executa consulta externa
    res1 = service.analyze_instagram_post(
        post_url="https://www.instagram.com/reel/C1122/",
        caption="Link: https://shope.ee/selador",
        views=10000
    )
    assert res1["product_found"] is True
    assert res1["from_cache"] is False
    assert service.shopee_client.get_product_details.call_count == 1

    # Segunda chamada idêntica: DEVE usar cache e NÃO chamar a Shopee de novo!
    res2 = service.analyze_instagram_post(
        post_url="https://www.instagram.com/reel/C1122/",
        caption="Link: https://shope.ee/selador",
        views=15000,
        force_refresh=False
    )
    assert res2["product_found"] is True
    assert res2["from_cache"] is True
    # O call_count da Shopee API continua sendo 1 (IP 100% protegido)
    assert service.shopee_client.get_product_details.call_count == 1


def test_shopee_radar_scan_storefront(tmp_path):
    db_path = str(tmp_path / "storefront.db")
    limiter = ShopeeRateLimiter(min_interval_sec=0, state_file=str(tmp_path / "limiter_sf.json"))
    limiter.apply_safe_delay = MagicMock()
    service = ShopeeRadarService(db_path=db_path, rate_limiter=limiter)

    # Mock catalog resolver
    service.catalog_resolver.extract_storefront_items = MagicMock(return_value=[
        {"title": "01 - Garrafa Térmica 1L", "url": "https://shope.ee/garrafa"},
        {"title": "02 - Dispenser de Detergente", "url": "https://shope.ee/dispenser"}
    ])

    service.link_resolver.resolve_url = MagicMock(side_effect=[
        {"success": True, "shop_id": "101", "item_id": "201"},
        {"success": True, "shop_id": "102", "item_id": "202"},
    ])

    service.shopee_client.get_product_details = MagicMock(side_effect=[
        {"success": True, "shop_id": "101", "item_id": "201", "title": "Garrafa Térmica Inox", "price": 45.0, "historical_sold": 5000, "monthly_sold": 800, "stock": 50, "rating_star": 4.9, "rating_count": 300},
        {"success": True, "shop_id": "102", "item_id": "202", "title": "Dispenser Automático", "price": 25.0, "historical_sold": 2000, "monthly_sold": 1200, "stock": 90, "rating_star": 4.7, "rating_count": 150},
    ])

    res = service.scan_storefront("https://linktr.ee/achadinhos_teste", max_items=5)
    assert res["total_items_found"] == 2
    assert res["processed_count"] == 2
    # O primeiro deve ser o de 1200 vendas no mês (Dispenser)
    assert res["products"][0]["title"] == "Dispenser Automático"
    assert res["products"][0]["monthly_sold"] == 1200


def test_shopee_radar_scan_bulk_links(tmp_path):
    db_path = str(tmp_path / "bulk.db")
    limiter = ShopeeRateLimiter(min_interval_sec=0, state_file=str(tmp_path / "limiter_bulk.json"))
    limiter.apply_safe_delay = MagicMock()
    service = ShopeeRadarService(db_path=db_path, rate_limiter=limiter)

    service.link_resolver.resolve_url = MagicMock(return_value={
        "success": True, "shop_id": "555", "item_id": "666"
    })

    service.shopee_client.get_product_details = MagicMock(return_value={
        "success": True, "shop_id": "555", "item_id": "666",
        "title": "Mop Limpeza Pesada", "price": 59.90, "historical_sold": 8000,
        "monthly_sold": 1500, "stock": 40, "rating_star": 4.8, "rating_count": 600
    })

    text_msg = "Olha essa oferta incrível https://shope.ee/mop123 e aproveita o cupom!"
    res = service.scan_bulk_links(text_msg, max_items=3)

    assert res["total_links_found"] >= 1
    assert res["processed_count"] == 1
    assert res["products"][0]["title"] == "Mop Limpeza Pesada"


def test_catalog_resolver_classification():
    cr = CatalogResolver()
    # URLs de produto
    assert cr.is_shopee_product_url("https://shope.ee/abc123XYZ") is True
    assert cr.is_shopee_product_url("https://s.shopee.com.br/def456") is True
    assert cr.is_shopee_product_url("https://shopee.com.br/product/123/456") is True
    assert cr.is_shopee_product_url("https://shopee.com.br/Garrafa-Inox-i.123.456") is True
    # URLs que NÃO são produtos
    assert cr.is_shopee_product_url("https://linktr.ee/shopeecozinha") is False
    assert cr.is_shopee_product_url("https://shopee.com.br/loja_vendedor") is False
    # Agregadores
    assert cr.is_aggregator_url("https://linktr.ee/achadinhos") is True
    assert cr.is_aggregator_url("https://beacons.ai/achados") is True
    assert cr.is_aggregator_url("https://shope.ee/abc") is False


def test_shopee_radar_scan_storefront_diagnostics(tmp_path):
    db_path = str(tmp_path / "diag.db")
    limiter = ShopeeRateLimiter(min_interval_sec=0, state_file=str(tmp_path / "limiter_diag.json"))
    service = ShopeeRadarService(db_path=db_path, rate_limiter=limiter)

    # Simula vitrine com links que falharam (1 expirado e 1 categoria)
    service.catalog_resolver.inspect_storefront = MagicMock(return_value={
        "url": "https://linktr.ee/vitrine_teste",
        "categories": [{"title": "Cozinha", "url": "https://linktr.ee/cozinha"}],
        "direct_products": [],
        "store_or_campaigns": []
    })
    service.catalog_resolver.extract_storefront_items = MagicMock(return_value=[
        {"title": "Item Expirado", "url": "https://shope.ee/old_expired"},
        {"title": "Página Celulares", "url": "https://shope.ee/cat_celulares"}
    ])

    service.link_resolver.resolve_url = MagicMock(side_effect=[
        {"success": False, "error": "Link da Shopee expirado ou desativado pelo vendedor (redirecionou para error_page)."},
        {"success": False, "error": "Link aponta para uma página de categoria ou campanha promocional da Shopee, não um produto individual."}
    ])

    res = service.scan_storefront("https://linktr.ee/vitrine_teste")
    assert res["total_items_found"] == 2
    assert res["processed_count"] == 0
    assert len(res["skipped_items"]) == 2
    assert len(res["categories_found"]) == 1
    assert res["skipped_reason"] is not None
    assert "expirados" in res["skipped_reason"] or "categoria" in res["skipped_reason"]


