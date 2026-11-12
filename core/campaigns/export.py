"""
core/campaigns/export.py — Exportação de Dados em CSV (Decisão 13 / Requisito V4).

Implementa:
- Geração com módulo 'csv' padrão da linguagem;
- Delimitador ';' (ponto e vírgula) para abertura nativa no Excel em português (Brasil);
- Encoding UTF-8 com BOM (utf-8-sig) para compatibilidade perfeita com acentuação no Excel/Windows;
- Valores monetários formatados em decimal com vírgula (ex: "12,50");
- Datas formatadas em DD/MM/AAAA;
- Dois relatórios:
  1. export_posts_metrics_csv: Publicações + últimas métricas;
  2. export_campaigns_summary_csv: Resumo consolidado por campanha.
"""

import csv
import io
from typing import List, Dict, Any, Optional

from .money import format_date_br, PLATFORM_LABELS


def cents_to_csv_decimal(cents: Optional[int]) -> str:
    """Converte valor em centavos inteiros para string decimal brasileira com vírgula."""
    if cents is None:
        return ""
    val_float = cents / 100.0
    return f"{val_float:.2f}".replace(".", ",")


def export_posts_metrics_csv(posts: List[Dict[str, Any]]) -> bytes:
    """Gera o arquivo CSV de Publicações com suas últimas métricas e cálculos."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    headers = [
        "ID Publicação",
        "Plataforma",
        "Campanha",
        "Título do Corte",
        "ID do Vídeo",
        "Chave do Corte",
        "Data de Publicação",
        "Conta / Canal",
        "Link do Post",
        "Moeda",
        "Data do Último Lançamento",
        "Views Acumuladas",
        "Bruto Estimado",
        "Comissão Retida",
        "Líquido Estimado",
        "Ganho Informado",
        "Ganho Considerado",
        "RPM Real",
        "Observações",
    ]
    writer.writerow(headers)

    for p in posts:
        camp = p.get("campaign")
        camp_name = camp["name"] if camp else "Sem campanha"
        calc = p.get("calculations", {})
        snap = p.get("latest_snapshot")

        views = calc.get("views", 0)
        rpm_val = calc.get("rpm_real_cents")
        rpm_str = cents_to_csv_decimal(int(round(rpm_val))) if rpm_val is not None else ""

        row = [
            p.get("id", ""),
            PLATFORM_LABELS.get(p.get("platform", ""), p.get("platform", "")),
            camp_name,
            p.get("cut_title") or p.get("cut_key") or "",
            p.get("video_id") or "",
            p.get("cut_key") or "",
            format_date_br(p.get("posted_on")),
            p.get("account_label") or "",
            p.get("post_url") or "",
            p.get("currency") or "BRL",
            format_date_br(snap["snapshot_on"]) if snap else "",
            views,
            cents_to_csv_decimal(calc.get("bruto_cents")),
            cents_to_csv_decimal(calc.get("comissao_cents")),
            cents_to_csv_decimal(calc.get("liquido_cents")),
            cents_to_csv_decimal(calc.get("earnings_reported_cents")),
            cents_to_csv_decimal(calc.get("considerado_cents")),
            rpm_str,
            p.get("notes") or "",
        ]
        writer.writerow(row)

    # Retorna codificado com UTF-8-SIG (com BOM para abertura direta no Excel)
    return output.getvalue().encode("utf-8-sig")


def export_campaigns_summary_csv(summaries: List[Dict[str, Any]]) -> bytes:
    """Gera o arquivo CSV de Resumo Consolidado por Campanha."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    headers = [
        "ID Campanha",
        "Nome da Campanha",
        "Fonte / Contratante",
        "Moeda",
        "Status",
        "CPM (por 1.000 views)",
        "Teto por Clipe",
        "Comissão (%)",
        "Prazo Retenção (dias)",
        "Data Início",
        "Data Término",
        "Plataformas Aceitas",
        "Total de Publicações",
        "Total de Views",
        "Total Bruto",
        "Total Comissão",
        "Total Líquido",
        "Total Informado",
        "Total Considerado",
        "RPM Real Médio",
        "Link do Briefing",
        "Observações",
    ]
    writer.writerow(headers)

    for s in summaries:
        camp = s.get("campaign", {})
        platforms_list = camp.get("platforms", [])
        platforms_str = ", ".join(PLATFORM_LABELS.get(pl, pl) for pl in platforms_list)

        rate = camp.get("rate_per_1000_cents")
        cap = camp.get("cap_per_clip_cents")
        fee_bp = camp.get("fee_bp", 0)
        fee_pct_str = f"{fee_bp / 100:.2f}".replace(".", ",")

        rpm_val = s.get("rpm_real_cents")
        rpm_str = cents_to_csv_decimal(int(round(rpm_val))) if rpm_val is not None else ""

        row = [
            camp.get("id", ""),
            camp.get("name", ""),
            camp.get("source_name") or "",
            camp.get("currency") or "BRL",
            camp.get("status") or "ativa",
            cents_to_csv_decimal(rate),
            cents_to_csv_decimal(cap),
            fee_pct_str,
            camp.get("hold_days", 0),
            format_date_br(camp.get("starts_on")),
            format_date_br(camp.get("ends_on")),
            platforms_str,
            s.get("posts_count", 0),
            s.get("views", 0),
            cents_to_csv_decimal(s.get("bruto_cents")),
            cents_to_csv_decimal(s.get("comissao_cents")),
            cents_to_csv_decimal(s.get("liquido_cents")),
            cents_to_csv_decimal(s.get("earnings_reported_cents")),
            cents_to_csv_decimal(s.get("considerado_cents")),
            rpm_str,
            camp.get("briefing_url") or "",
            camp.get("notes") or "",
        ]
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")

