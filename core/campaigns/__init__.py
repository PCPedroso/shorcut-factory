"""
core/campaigns — Módulo de Gestão de Campanhas de Cortes, Métricas e Ganhos.
"""

from .db import init_db, get_connection, transaction, DEFAULT_DB_PATH
from .money import (
    parse_money_cents,
    format_money_cents,
    calculate_cut_earnings,
    parse_iso_date,
    format_date_br,
    is_campaign_expired,
    days_until_expiration,
    validate_campaign_data,
    validate_post_data,
    validate_snapshot_data,
    SUPPORTED_PLATFORMS,
    PLATFORM_LABELS,
)
from .repo import CampaignRepo
from .licensing_bridge import apply_campaign_license, can_apply_campaign_license
from .export import export_posts_metrics_csv, export_campaigns_summary_csv

__all__ = [
    "init_db",
    "get_connection",
    "transaction",
    "DEFAULT_DB_PATH",
    "parse_money_cents",
    "format_money_cents",
    "calculate_cut_earnings",
    "parse_iso_date",
    "format_date_br",
    "validate_campaign_data",
    "validate_post_data",
    "validate_snapshot_data",
    "SUPPORTED_PLATFORMS",
    "PLATFORM_LABELS",
    "is_campaign_expired",
    "days_until_expiration",
    "CampaignRepo",
    "apply_campaign_license",
    "can_apply_campaign_license",
    "export_posts_metrics_csv",
    "export_campaigns_summary_csv",
]

