"""
core/campaigns/repo.py — Repositório de Dados para Campanhas, Publicações e Lançamentos.

Implementa:
- Operações CRUD para Campanhas (com suporte transacional a plataformas associadas);
- Proteção de integridade referencial: campanhas com posts não podem ser excluídas;
- CRUD para Publicações (Posts) com herança estrita de moeda da campanha vinculada;
- Lançamentos acumulados (ViewSnapshots) com semântica de Upsert (post_id + snapshot_on);
- Detecção e alerta se views forem menores que o lançamento anterior;
- Consultas analíticas agregadas em SQL separadas estritamente por moeda (BRL / USD);
- Alertas de campanhas a expirar (<= 3 dias) e publicações sem atualização (> 7 dias).
"""

import datetime
import sqlite3
from typing import Optional, Dict, Any, List, Tuple

from .db import get_connection, transaction, DEFAULT_DB_PATH
from .money import (
    calculate_cut_earnings,
    validate_campaign_data,
    validate_post_data,
    validate_snapshot_data,
    parse_iso_date,
    SUPPORTED_PLATFORMS,
)


class CampaignRepo:
    """Repositório de persistência e consultas do painel de Campanhas & Métricas."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.now().isoformat()

    # ── CAMPANHAS ─────────────────────────────────────────────────────────────

    def create_campaign(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria uma nova campanha com suas plataformas aceitas."""
        errors = validate_campaign_data(data)
        if errors:
            raise ValueError(f"Erros de validação na campanha: {'; '.join(errors)}")

        now = self._now_iso()
        name = str(data["name"]).strip()
        source_name = str(data.get("source_name") or "").strip() or None
        briefing_url = str(data.get("briefing_url") or "").strip() or None
        currency = str(data.get("currency") or "BRL").upper().strip()
        rate = int(data["rate_per_1000_cents"])
        cap = int(data["cap_per_clip_cents"]) if data.get("cap_per_clip_cents") is not None else None
        fee_bp = int(data.get("fee_bp") or 0)
        hold_days = int(data.get("hold_days") or 0)
        starts_on = str(data["starts_on"]).strip() if data.get("starts_on") else None
        ends_on = str(data["ends_on"]).strip() if data.get("ends_on") else None
        status = str(data.get("status") or "ativa").lower().strip()
        notes = str(data.get("notes") or "").strip() or None
        platforms = data.get("platforms", [])

        try:
            with transaction(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO campaigns (
                        name, source_name, briefing_url, currency, rate_per_1000_cents,
                        cap_per_clip_cents, fee_bp, hold_days, starts_on, ends_on,
                        status, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        name, source_name, briefing_url, currency, rate,
                        cap, fee_bp, hold_days, starts_on, ends_on,
                        status, notes, now, now
                    ),
                )
                camp_id = cur.lastrowid

                for p in platforms:
                    cur.execute(
                        "INSERT INTO campaign_platforms (campaign_id, platform) VALUES (?, ?);",
                        (camp_id, str(p).lower().strip()),
                    )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() and "NAME" in str(exc).upper():
                raise ValueError(f"Já existe uma campanha cadastrada com o nome '{name}'.")
            raise

        res = self.get_campaign(camp_id)
        if not res:
            raise RuntimeError("Falha ao recuperar a campanha recém-criada.")
        return res

    def update_campaign(self, campaign_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza os dados de uma campanha existente e sincroniza suas plataformas."""
        existing = self.get_campaign(campaign_id)
        if not existing:
            raise ValueError(f"Campanha ID #{campaign_id} não encontrada.")

        # Mescla dados existentes com os novos
        merged = dict(existing)
        merged.update(data)
        if "platforms" not in data:
            merged["platforms"] = existing.get("platforms", [])

        errors = validate_campaign_data(merged)
        if errors:
            raise ValueError(f"Erros de validação na campanha: {'; '.join(errors)}")

        now = self._now_iso()
        name = str(merged["name"]).strip()
        source_name = str(merged.get("source_name") or "").strip() or None
        briefing_url = str(merged.get("briefing_url") or "").strip() or None
        currency = str(merged.get("currency") or "BRL").upper().strip()
        rate = int(merged["rate_per_1000_cents"])
        cap = int(merged["cap_per_clip_cents"]) if merged.get("cap_per_clip_cents") is not None else None
        fee_bp = int(merged.get("fee_bp") or 0)
        hold_days = int(merged.get("hold_days") or 0)
        starts_on = str(merged["starts_on"]).strip() if merged.get("starts_on") else None
        ends_on = str(merged["ends_on"]).strip() if merged.get("ends_on") else None
        status = str(merged.get("status") or "ativa").lower().strip()
        notes = str(merged.get("notes") or "").strip() or None
        platforms = merged.get("platforms", [])

        try:
            with transaction(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE campaigns
                    SET name = ?, source_name = ?, briefing_url = ?, currency = ?,
                        rate_per_1000_cents = ?, cap_per_clip_cents = ?, fee_bp = ?,
                        hold_days = ?, starts_on = ?, ends_on = ?, status = ?,
                        notes = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        name, source_name, briefing_url, currency, rate,
                        cap, fee_bp, hold_days, starts_on, ends_on,
                        status, notes, now, campaign_id
                    ),
                )
                # Sincroniza plataformas
                conn.execute("DELETE FROM campaign_platforms WHERE campaign_id = ?;", (campaign_id,))
                for p in platforms:
                    conn.execute(
                        "INSERT INTO campaign_platforms (campaign_id, platform) VALUES (?, ?);",
                        (campaign_id, str(p).lower().strip()),
                    )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc).upper() and "NAME" in str(exc).upper():
                raise ValueError(f"Já existe uma campanha cadastrada com o nome '{name}'.")
            raise

        res = self.get_campaign(campaign_id)
        if not res:
            raise RuntimeError("Falha ao recuperar a campanha atualizada.")
        return res

    def get_campaign(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Recupera detalhes de uma campanha com suas plataformas aceitas."""
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM campaigns WHERE id = ?;", (campaign_id,)).fetchone()
            if not row:
                return None
            camp = dict(row)
            p_rows = conn.execute(
                "SELECT platform FROM campaign_platforms WHERE campaign_id = ? ORDER BY platform;",
                (campaign_id,),
            ).fetchall()
            camp["platforms"] = [r["platform"] for r in p_rows]
            return camp

    def get_campaign_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Recupera campanha pelo nome (case-insensitive)."""
        if not name:
            return None
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM campaigns WHERE name = ? COLLATE NOCASE;", (name.strip(),)).fetchone()
            if not row:
                return None
            return self.get_campaign(row["id"])

    def list_campaigns(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todas as campanhas cadastradas com filtros opcionais de status."""
        query = "SELECT * FROM campaigns"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.lower().strip())
        query += " ORDER BY id DESC;"

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            camps = []
            for r in rows:
                c = dict(r)
                p_rows = conn.execute(
                    "SELECT platform FROM campaign_platforms WHERE campaign_id = ? ORDER BY platform;",
                    (c["id"],),
                ).fetchall()
                c["platforms"] = [pr["platform"] for pr in p_rows]
                camps.append(c)
            return camps

    def delete_campaign(self, campaign_id: int) -> bool:
        """Exclui uma campanha se não possuir publicações vinculadas.

        Regra da Decisão 9: Campanha com publicações NÃO pode ser excluída
        (sugere alterar status para 'encerrada').
        """
        with get_connection(self.db_path) as conn:
            row_cnt = conn.execute(
                "SELECT count(*) as total FROM posts WHERE campaign_id = ?;",
                (campaign_id,),
            ).fetchone()
            if row_cnt and row_cnt["total"] > 0:
                raise ValueError(
                    f"Esta campanha possui {row_cnt['total']} publicação(ões) vinculada(s) e não pode ser excluída. "
                    "Recomendamos alterar o status da campanha para 'encerrada'."
                )

        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM campaigns WHERE id = ?;", (campaign_id,))
        return True

    # ── PUBLICAÇÕES (POSTS) ───────────────────────────────────────────────────

    def create_post(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registra uma nova publicação de corte."""
        campaign_id = data.get("campaign_id")
        camp = self.get_campaign(campaign_id) if campaign_id else None

        # Decisão 6: Se a publicação tem campanha, currency = a da campanha (impor na camada de repo)
        if camp:
            data["currency"] = camp["currency"]
        elif not data.get("currency"):
            data["currency"] = "BRL"

        errors = validate_post_data(data)
        if errors:
            raise ValueError(f"Erros de validação na publicação: {'; '.join(errors)}")

        now = self._now_iso()
        video_id = str(data.get("video_id") or "").strip() or None
        cut_key = str(data.get("cut_key") or "").strip() or None
        cut_title = str(data.get("cut_title") or "").strip() or "Sem título"
        platform = str(data["platform"]).lower().strip()
        account_label = str(data.get("account_label") or "").strip() or None
        post_url = str(data.get("post_url") or "").strip() or None
        posted_on = str(data["posted_on"]).strip()
        currency = str(data["currency"]).upper().strip()
        notes = str(data.get("notes") or "").strip() or None

        try:
            with transaction(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO posts (
                        campaign_id, video_id, cut_key, cut_title, platform,
                        account_label, post_url, posted_on, currency, notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        campaign_id, video_id, cut_key, cut_title, platform,
                        account_label, post_url, posted_on, currency, notes,
                        now, now
                    ),
                )
                post_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            if "UQ_POSTS_POST_URL" in str(exc).upper() or "POST_URL" in str(exc).upper():
                raise ValueError(f"Já existe uma publicação registrada com o link: '{post_url}'.")
            raise

        res = self.get_post(post_id)
        if not res:
            raise RuntimeError("Falha ao recuperar o post recém-criado.")
        return res

    def update_post(self, post_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza dados de uma publicação existente."""
        existing = self.get_post(post_id)
        if not existing:
            raise ValueError(f"Publicação ID #{post_id} não encontrada.")

        merged = dict(existing)
        merged.update(data)

        # Se houver campanha vinculada, força moeda da campanha
        camp_id = merged.get("campaign_id")
        if camp_id:
            camp = self.get_campaign(camp_id)
            if camp:
                merged["currency"] = camp["currency"]

        errors = validate_post_data(merged)
        if errors:
            raise ValueError(f"Erros de validação na publicação: {'; '.join(errors)}")

        now = self._now_iso()
        campaign_id = merged.get("campaign_id")
        video_id = str(merged.get("video_id") or "").strip() or None
        cut_key = str(merged.get("cut_key") or "").strip() or None
        cut_title = str(merged.get("cut_title") or "").strip() or "Sem título"
        platform = str(merged["platform"]).lower().strip()
        account_label = str(merged.get("account_label") or "").strip() or None
        post_url = str(merged.get("post_url") or "").strip() or None
        posted_on = str(merged["posted_on"]).strip()
        currency = str(merged["currency"]).upper().strip()
        notes = str(merged.get("notes") or "").strip() or None

        try:
            with transaction(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE posts
                    SET campaign_id = ?, video_id = ?, cut_key = ?, cut_title = ?,
                        platform = ?, account_label = ?, post_url = ?, posted_on = ?,
                        currency = ?, notes = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        campaign_id, video_id, cut_key, cut_title, platform,
                        account_label, post_url, posted_on, currency, notes,
                        now, post_id
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if "UQ_POSTS_POST_URL" in str(exc).upper() or "POST_URL" in str(exc).upper():
                raise ValueError(f"Já existe uma publicação registrada com o link: '{post_url}'.")
            raise

        res = self.get_post(post_id)
        if not res:
            raise RuntimeError("Falha ao recuperar o post atualizado.")
        return res

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Recupera detalhes de uma publicação."""
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?;", (post_id,)).fetchone()
            return dict(row) if row else None

    def list_posts(
        self,
        campaign_id: Optional[int] = None,
        platform: Optional[str] = None,
        video_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista publicações com filtros opcionais."""
        query = "SELECT * FROM posts WHERE 1=1"
        params: List[Any] = []

        if campaign_id is not None:
            query += " AND campaign_id = ?"
            params.append(campaign_id)
        if platform:
            query += " AND platform = ?"
            params.append(platform.lower().strip())
        if video_id:
            query += " AND video_id = ?"
            params.append(video_id.strip())

        query += " ORDER BY id DESC;"

        with get_connection(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def delete_post(self, post_id: int) -> bool:
        """Exclui uma publicação e seus lançamentos (cascade explícito/foreign key)."""
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM posts WHERE id = ?;", (post_id,))
        return True

    # ── LANÇAMENTOS (VIEW SNAPSHOTS) ──────────────────────────────────────────

    def record_snapshot(
        self,
        post_id: int,
        snapshot_on: str,
        views: int,
        earnings_cents: Optional[int] = None,
        note: Optional[str] = None,
        ref_date: Optional[datetime.date] = None,
    ) -> Dict[str, Any]:
        """Registra ou atualiza (upsert) o lançamento acumulado de views e ganhos de um post em uma data.

        Regra da Decisão 6: Um lançamento por post por dia (repetir atualiza).
        Regra da Etapa B: Se views for MENOR que o lançamento anterior do mesmo post, permitir, mas avisar.
        """
        post = self.get_post(post_id)
        if not post:
            raise ValueError(f"Publicação ID #{post_id} não encontrada.")

        snap_data = {
            "snapshot_on": str(snapshot_on).strip(),
            "views": int(views),
            "earnings_cents": int(earnings_cents) if earnings_cents is not None else None,
        }
        errors = validate_snapshot_data(snap_data, ref_date=ref_date)
        if errors:
            raise ValueError(f"Erros de validação no lançamento: {'; '.join(errors)}")

        clean_snap_on = snap_data["snapshot_on"]
        clean_views = snap_data["views"]
        clean_earnings = snap_data["earnings_cents"]
        clean_note = str(note or "").strip() or None
        now = self._now_iso()

        # Verifica lançamento imediatamente anterior cronologicamente para detectar decréscimo de views
        warning_msg: Optional[str] = None
        with get_connection(self.db_path) as conn:
            prev_row = conn.execute(
                """
                SELECT views, snapshot_on FROM view_snapshots
                WHERE post_id = ? AND snapshot_on < ?
                ORDER BY snapshot_on DESC, id DESC
                LIMIT 1;
                """,
                (post_id, clean_snap_on),
            ).fetchone()
            if prev_row and clean_views < prev_row["views"]:
                warning_msg = (
                    f"Atenção: as views informadas ({clean_views:,}) são inferiores às views do lançamento anterior "
                    f"({prev_row['views']:,} em {prev_row['snapshot_on']})."
                )

        with transaction(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO view_snapshots (post_id, snapshot_on, views, earnings_cents, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id, snapshot_on) DO UPDATE SET
                    views = excluded.views,
                    earnings_cents = excluded.earnings_cents,
                    note = excluded.note;
                """,
                (post_id, clean_snap_on, clean_views, clean_earnings, clean_note, now),
            )
            snap_id = cur.lastrowid

        # Recupera registro atualizado
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM view_snapshots WHERE post_id = ? AND snapshot_on = ?;",
                (post_id, clean_snap_on),
            ).fetchone()
            res = dict(row)
            res["warning"] = warning_msg
            return res

    def get_latest_snapshot_for_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Retorna o lançamento mais recente de um post (maior snapshot_on)."""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM view_snapshots
                WHERE post_id = ?
                ORDER BY snapshot_on DESC, id DESC
                LIMIT 1;
                """,
                (post_id,),
            ).fetchone()
            return dict(row) if row else None

    def list_snapshots_for_post(self, post_id: int) -> List[Dict[str, Any]]:
        """Lista todo o histórico de lançamentos de um post em ordem cronológica."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM view_snapshots
                WHERE post_id = ?
                ORDER BY snapshot_on ASC, id ASC;
                """,
                (post_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_snapshot(self, snapshot_id: int) -> bool:
        """Remove um lançamento específico."""
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM view_snapshots WHERE id = ?;", (snapshot_id,))
        return True

    # ── CONSULTAS AGREGADAS & MÉTRICAS ────────────────────────────────────────

    def get_post_with_metrics(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Retorna uma publicação com dados da campanha, último lançamento e valores calculados."""
        post = self.get_post(post_id)
        if not post:
            return None

        camp = self.get_campaign(post["campaign_id"]) if post.get("campaign_id") else None
        latest_snap = self.get_latest_snapshot_for_post(post_id)

        rate = camp["rate_per_1000_cents"] if camp else 0
        cap = camp.get("cap_per_clip_cents") if camp else None
        fee_bp = camp.get("fee_bp", 0) if camp else 0
        hold_days = camp.get("hold_days", 0) if camp else 0

        views = latest_snap["views"] if latest_snap else 0
        reported = latest_snap["earnings_cents"] if latest_snap else None
        snap_date = latest_snap["snapshot_on"] if latest_snap else None

        calc = calculate_cut_earnings(
            views=views,
            rate_per_1000_cents=rate,
            cap_per_clip_cents=cap,
            fee_bp=fee_bp,
            earnings_reported_cents=reported,
            hold_days=hold_days,
            snapshot_date=snap_date,
        )

        item = dict(post)
        item["campaign"] = camp
        item["latest_snapshot"] = latest_snap
        item["calculations"] = calc
        return item

    def list_posts_with_metrics(
        self,
        campaign_id: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lista todas as publicações combinadas com campanha, métricas mais recentes e cálculos."""
        posts = self.list_posts(campaign_id=campaign_id, platform=platform)
        results = []
        for p in posts:
            m = self.get_post_with_metrics(p["id"])
            if m:
                results.append(m)
        return results

    def get_totals_by_currency(self) -> Dict[str, Dict[str, Any]]:
        """Consolida os totais gerais separados estritamente por moeda (BRL e USD).

        Regra da Decisão 4: SEM conversão cambial. Totais sempre separados por moeda.
        """
        posts_with_metrics = self.list_posts_with_metrics()
        totals: Dict[str, Dict[str, Any]] = {
            "BRL": {
                "currency": "BRL",
                "posts_count": 0,
                "views": 0,
                "bruto_cents": 0,
                "comissao_cents": 0,
                "liquido_cents": 0,
                "earnings_reported_cents": 0,
                "considerado_cents": 0,
            },
            "USD": {
                "currency": "USD",
                "posts_count": 0,
                "views": 0,
                "bruto_cents": 0,
                "comissao_cents": 0,
                "liquido_cents": 0,
                "earnings_reported_cents": 0,
                "considerado_cents": 0,
            },
        }

        for p in posts_with_metrics:
            curr = p.get("currency", "BRL").upper()
            if curr not in totals:
                totals[curr] = {
                    "currency": curr,
                    "posts_count": 0,
                    "views": 0,
                    "bruto_cents": 0,
                    "comissao_cents": 0,
                    "liquido_cents": 0,
                    "earnings_reported_cents": 0,
                    "considerado_cents": 0,
                }

            c = p["calculations"]
            totals[curr]["posts_count"] += 1
            totals[curr]["views"] += c["views"]
            totals[curr]["bruto_cents"] += c["bruto_cents"]
            totals[curr]["comissao_cents"] += c["comissao_cents"]
            totals[curr]["liquido_cents"] += c["liquido_cents"]
            if c["earnings_reported_cents"] is not None:
                totals[curr]["earnings_reported_cents"] += c["earnings_reported_cents"]
            totals[curr]["considerado_cents"] += c["considerado_cents"]

        return totals

    def get_totals_by_campaign(self, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """Agrupa métricas e ganhos totais por campanha."""
        camps = self.list_campaigns()
        summary = []
        for camp in camps:
            if currency and camp.get("currency") != currency.upper():
                continue

            posts = self.list_posts_with_metrics(campaign_id=camp["id"])
            views = sum(p["calculations"]["views"] for p in posts)
            bruto = sum(p["calculations"]["bruto_cents"] for p in posts)
            comissao = sum(p["calculations"]["comissao_cents"] for p in posts)
            liquido = sum(p["calculations"]["liquido_cents"] for p in posts)
            reported = sum(p["calculations"]["earnings_reported_cents"] or 0 for p in posts)
            considerado = sum(p["calculations"]["considerado_cents"] for p in posts)
            rpm_real = (considerado * 1000 / views) if views > 0 else None

            summary.append({
                "campaign": camp,
                "currency": camp["currency"],
                "posts_count": len(posts),
                "views": views,
                "bruto_cents": bruto,
                "comissao_cents": comissao,
                "liquido_cents": liquido,
                "earnings_reported_cents": reported,
                "considerado_cents": considerado,
                "rpm_real_cents": rpm_real,
            })
        return summary

    def get_totals_by_platform(self, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """Agrupa métricas e ganhos totais por plataforma para uma moeda específica."""
        posts = self.list_posts_with_metrics()
        by_plat: Dict[str, Dict[str, Any]] = {}

        for p in posts:
            curr = p.get("currency", "BRL").upper()
            if currency and curr != currency.upper():
                continue

            plat = p.get("platform", "outra")
            if plat not in by_plat:
                by_plat[plat] = {
                    "platform": plat,
                    "currency": currency or curr,
                    "posts_count": 0,
                    "views": 0,
                    "bruto_cents": 0,
                    "comissao_cents": 0,
                    "liquido_cents": 0,
                    "considerado_cents": 0,
                }

            c = p["calculations"]
            by_plat[plat]["posts_count"] += 1
            by_plat[plat]["views"] += c["views"]
            by_plat[plat]["bruto_cents"] += c["bruto_cents"]
            by_plat[plat]["comissao_cents"] += c["comissao_cents"]
            by_plat[plat]["liquido_cents"] += c["liquido_cents"]
            by_plat[plat]["considerado_cents"] += c["considerado_cents"]

        # Calcula RPM real
        result = []
        for plat_k, item in by_plat.items():
            v = item["views"]
            cons = item["considerado_cents"]
            item["rpm_real_cents"] = (cons * 1000 / v) if v > 0 else None
            result.append(item)

        result.sort(key=lambda x: x["considerado_cents"], reverse=True)
        return result

    # ── ALERTAS ───────────────────────────────────────────────────────────────

    def get_campaigns_expiring_soon(self, days: int = 3, ref_date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """Retorna campanhas ativas que vencem em até N dias (hoje <= ends_on <= hoje + N dias)."""
        today = ref_date or datetime.date.today()
        camps = self.list_campaigns(status="ativa")
        expiring = []

        for c in camps:
            ends_on = c.get("ends_on")
            if not ends_on:
                continue
            d_end = parse_iso_date(ends_on)
            if not d_end:
                continue
            delta = (d_end - today).days
            if 0 <= delta <= days:
                c_copy = dict(c)
                c_copy["days_left"] = delta
                expiring.append(c_copy)

        expiring.sort(key=lambda x: x["days_left"])
        return expiring

    def get_posts_without_recent_updates(self, days: int = 7, ref_date: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
        """Retorna publicações em campanhas ativas sem atualização há mais de N dias.

        Conta a partir do último lançamento ou, se não houver, de posted_on.
        """
        today = ref_date or datetime.date.today()
        posts_with_metrics = self.list_posts_with_metrics()
        stale = []

        for p in posts_with_metrics:
            camp = p.get("campaign")
            # Aplica apenas para campanhas ativas
            if not camp or camp.get("status") != "ativa":
                continue

            latest_snap = p.get("latest_snapshot")
            if latest_snap and latest_snap.get("snapshot_on"):
                last_activity_date = parse_iso_date(latest_snap["snapshot_on"])
            else:
                last_activity_date = parse_iso_date(p.get("posted_on"))

            if not last_activity_date:
                continue

            days_idle = (today - last_activity_date).days
            if days_idle > days:
                p_copy = dict(p)
                p_copy["days_idle"] = days_idle
                p_copy["last_activity_date"] = last_activity_date.isoformat()
                stale.append(p_copy)

        stale.sort(key=lambda x: x["days_idle"], reverse=True)
        return stale

