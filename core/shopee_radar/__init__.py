"""
Shopee Radar - Módulo de Rastreamento de Tendências e Vendas (Instagram -> Shopee)
Identifica produtos da Shopee promovidos no Instagram e mede volume de vendas e aceleração.
"""

from .link_resolver import ShopeeLinkResolver
from .shopee_client import ShopeeClient
from .catalog_resolver import CatalogResolver
from .instagram_detector import InstagramDetector
from .trend_engine import ShopeeTrendEngine
from .rate_limiter import ShopeeRateLimiter
from .radar_service import ShopeeRadarService
from .ui_tab import render_shopee_radar_tab

__all__ = [
    "ShopeeLinkResolver",
    "ShopeeClient",
    "CatalogResolver",
    "InstagramDetector",
    "ShopeeTrendEngine",
    "ShopeeRateLimiter",
    "ShopeeRadarService",
    "render_shopee_radar_tab",
]
