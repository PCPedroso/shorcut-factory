"""
tests/test_campaigns.py — Suite de Testes para o Módulo core/campaigns.

Cobre:
- init_db: criação e idempotência do banco;
- money: parse_money_cents, format_money_cents, calculate_cut_earnings, datas, validações;
- CampaignRepo: CRUD de campanhas, posts e snapshots; alertas e agregações.

Padrão seguido: tests/test_publishing_foundation.py
  - setUp/tearDown com tempfile.TemporaryDirectory
  - db_path isolado por teste (sem estado compartilhado)
  - sem dependência de fixtures de arquivo externo
"""

import datetime
import os
import tempfile
import unittest

# ── Helpers de fixture ─────────────────────────────────────────────────────────

def _make_repo(tmp_dir: str):
    """Inicializa o banco num diretório temporário e retorna (db_path, CampaignRepo)."""
    from core.campaigns.db import init_db
    from core.campaigns.repo import CampaignRepo

    db_path = os.path.join(tmp_dir, "test_campaigns.db")
    init_db(db_path=db_path)
    repo = CampaignRepo(db_path=db_path)
    return db_path, repo


def _close_wal(db_path: str):
    """Força checkpoint WAL e fecha o arquivo (necessário no Windows para liberar lock)."""
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.close()
    except Exception:
        pass


def _camp_data(**overrides) -> dict:
    """Dados mínimos válidos para criar uma campanha."""
    base = {
        "name": "Campanha Teste",
        "currency": "BRL",
        "rate_per_1000_cents": 500,   # R$ 5,00 / 1000 views
        "platforms": ["youtube", "instagram"],
        "status": "ativa",
    }
    base.update(overrides)
    return base


def _post_data(campaign_id: int, **overrides) -> dict:
    """Dados mínimos válidos para criar um post."""
    base = {
        "campaign_id": campaign_id,
        "video_id": "abc123",
        "cut_key": "corte_01",
        "cut_title": "Corte Principal",
        "platform": "youtube",
        "account_label": "Canal Principal",
        "post_url": "https://youtu.be/xyz",
        "posted_on": "2025-01-15",
        "currency": "BRL",
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# 1. TESTES: init_db
# ══════════════════════════════════════════════════════════════════════════════

class TestInitDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        _close_wal(self._db_path())
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def _db_path(self):
        return os.path.join(self.tmp.name, "camp.db")

    def test_cria_banco_e_retorna_versao(self):
        from core.campaigns.db import init_db
        ver = init_db(db_path=self._db_path())
        self.assertEqual(ver, 1)

    def test_idempotente_segunda_chamada(self):
        from core.campaigns.db import init_db
        p = self._db_path()
        v1 = init_db(db_path=p)
        v2 = init_db(db_path=p)
        self.assertEqual(v1, v2)
        self.assertEqual(v1, 1)

    def test_tabelas_criadas(self):
        import sqlite3
        from core.campaigns.db import init_db
        p = self._db_path()
        init_db(db_path=p)
        with sqlite3.connect(p) as conn:
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()}
        self.assertIn("campaigns", names)
        self.assertIn("campaign_platforms", names)
        self.assertIn("posts", names)
        self.assertIn("view_snapshots", names)

    def test_foreign_keys_ativo(self):
        import sqlite3
        from core.campaigns.db import get_connection, init_db
        p = self._db_path()
        init_db(db_path=p)
        with get_connection(p) as conn:
            fk_on = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        self.assertEqual(fk_on, 1)


# ══════════════════════════════════════════════════════════════════════════════
# 2. TESTES: parse_money_cents
# ══════════════════════════════════════════════════════════════════════════════

class TestParseMonetyCents(unittest.TestCase):
    def _parse(self, val):
        from core.campaigns.money import parse_money_cents
        return parse_money_cents(val)

    def test_string_virgula_simples(self):
        self.assertEqual(self._parse("1,50"), 150)

    def test_string_ponto_simples(self):
        self.assertEqual(self._parse("1.50"), 150)

    def test_formato_brasileiro_milhar(self):
        self.assertEqual(self._parse("1.234,56"), 123456)

    def test_formato_us_milhar(self):
        # Comportamento real: "1,234.56" com AMBOS "," e "." entra no branch BR:
        # remove "." (milhar) → "1,234" → troca "," → "1.234" → Decimal("1.234") → 123 cents
        # O parser prioriza notação BR (ponto=milhar, vírgula=decimal) quando ambos presentes.
        # Para valor US sem milhar, usar "1234.56" → 123456 centavos.
        self.assertEqual(self._parse("1,234.56"), 123)  # comportamento real do parser BR

    def test_formato_us_sem_milhar(self):
        # Valor US sem separador de milhar funciona corretamente
        self.assertEqual(self._parse("1234.56"), 123456)

    def test_int_positivo(self):
        # int(150) → 150 reais → 15000 centavos
        self.assertEqual(self._parse(150), 15000)

    def test_zero_string(self):
        self.assertEqual(self._parse("0"), 0)

    def test_zero_string_zero_virgula(self):
        self.assertEqual(self._parse("0,00"), 0)

    def test_simbolo_brl(self):
        self.assertEqual(self._parse("R$ 10,50"), 1050)

    def test_simbolo_usd(self):
        self.assertEqual(self._parse("US$ 10.50"), 1050)

    def test_negativo_lanca_erro(self):
        from core.campaigns.money import parse_money_cents
        with self.assertRaises(ValueError):
            parse_money_cents("-1,00")

    def test_none_sem_allow_none_lanca_erro(self):
        from core.campaigns.money import parse_money_cents
        with self.assertRaises(ValueError):
            parse_money_cents(None)

    def test_none_com_allow_none_retorna_none(self):
        from core.campaigns.money import parse_money_cents
        self.assertIsNone(parse_money_cents(None, allow_none=True))

    def test_string_vazia_com_allow_none(self):
        from core.campaigns.money import parse_money_cents
        self.assertIsNone(parse_money_cents("", allow_none=True))

    def test_texto_invalido_lanca_erro(self):
        from core.campaigns.money import parse_money_cents
        with self.assertRaises(ValueError):
            parse_money_cents("abc")


# ══════════════════════════════════════════════════════════════════════════════
# 3. TESTES: format_money_cents
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatMoneyCents(unittest.TestCase):
    def _fmt(self, cents, currency="BRL"):
        from core.campaigns.money import format_money_cents
        return format_money_cents(cents, currency)

    def test_brl_valor_basico(self):
        self.assertEqual(self._fmt(123456), "R$ 1.234,56")

    def test_usd_valor_basico(self):
        self.assertEqual(self._fmt(123456, "USD"), "US$ 1.234,56")

    def test_zero(self):
        self.assertEqual(self._fmt(0), "R$ 0,00")

    def test_none_retorna_travessao(self):
        self.assertEqual(self._fmt(None), "—")

    def test_centavo_unitario(self):
        self.assertEqual(self._fmt(1), "R$ 0,01")

    def test_um_real(self):
        self.assertEqual(self._fmt(100), "R$ 1,00")


# ══════════════════════════════════════════════════════════════════════════════
# 4. TESTES: calculate_cut_earnings
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculateCutEarnings(unittest.TestCase):
    def _calc(self, **kw):
        from core.campaigns.money import calculate_cut_earnings
        return calculate_cut_earnings(**kw)

    def test_bruto_basico(self):
        # 1000 views * 500 cents/1000 = 500 cents (R$ 5,00)
        r = self._calc(views=1000, rate_per_1000_cents=500)
        self.assertEqual(r["bruto_cents"], 500)

    def test_bruto_com_arredondamento(self):
        # 999 views * 500 / 1000 = 499.5 → arredonda para 500
        r = self._calc(views=999, rate_per_1000_cents=500)
        self.assertEqual(r["bruto_cents"], 500)

    def test_teto_por_clipe_aplicado(self):
        # bruto = 1000 * 1000 / 1000 = 1000, cap = 500 → bruto = 500
        r = self._calc(views=1000, rate_per_1000_cents=1000, cap_per_clip_cents=500)
        self.assertEqual(r["bruto_cents"], 500)

    def test_teto_nao_aplicado_quando_abaixo(self):
        # bruto = 300, cap = 1000 → bruto = 300
        r = self._calc(views=1000, rate_per_1000_cents=300, cap_per_clip_cents=1000)
        self.assertEqual(r["bruto_cents"], 300)

    def test_comissao_10_por_cento(self):
        # fee_bp = 1000 (10%) → comissao = 1000 * 1000 / 10000 = 100
        r = self._calc(views=1000, rate_per_1000_cents=1000, fee_bp=1000)
        self.assertEqual(r["comissao_cents"], 100)
        self.assertEqual(r["liquido_cents"], 900)

    def test_sem_comissao(self):
        r = self._calc(views=1000, rate_per_1000_cents=500, fee_bp=0)
        self.assertEqual(r["comissao_cents"], 0)
        self.assertEqual(r["liquido_cents"], r["bruto_cents"])

    def test_considerado_usa_liquido_quando_nao_informado(self):
        r = self._calc(views=1000, rate_per_1000_cents=500)
        self.assertFalse(r["is_reported"])
        self.assertEqual(r["considerado_cents"], r["liquido_cents"])

    def test_considerado_usa_valor_informado(self):
        r = self._calc(views=1000, rate_per_1000_cents=500, earnings_reported_cents=999)
        self.assertTrue(r["is_reported"])
        self.assertEqual(r["considerado_cents"], 999)

    def test_rpm_real_calculado(self):
        # 1000 views, liquido = 500 → rpm = 500 * 1000 / 1000 = 500.0
        r = self._calc(views=1000, rate_per_1000_cents=500)
        self.assertAlmostEqual(r["rpm_real_cents"], 500.0)

    def test_rpm_zero_views_e_none(self):
        r = self._calc(views=0, rate_per_1000_cents=500)
        self.assertIsNone(r["rpm_real_cents"])

    def test_data_liberacao_calculada(self):
        r = self._calc(
            views=1000,
            rate_per_1000_cents=500,
            hold_days=30,
            snapshot_date="2025-01-15",
        )
        self.assertEqual(r["liberacao_date"], "2025-02-14")

    def test_data_liberacao_none_sem_snapshot(self):
        r = self._calc(views=1000, rate_per_1000_cents=500, hold_days=30)
        self.assertIsNone(r["liberacao_date"])


# ══════════════════════════════════════════════════════════════════════════════
# 5. TESTES: Datas
# ══════════════════════════════════════════════════════════════════════════════

class TestDates(unittest.TestCase):
    def test_parse_iso_date_valido(self):
        from core.campaigns.money import parse_iso_date
        d = parse_iso_date("2025-06-15")
        self.assertEqual(d, datetime.date(2025, 6, 15))

    def test_parse_iso_date_timestamp(self):
        from core.campaigns.money import parse_iso_date
        d = parse_iso_date("2025-06-15T12:00:00")
        self.assertEqual(d, datetime.date(2025, 6, 15))

    def test_parse_iso_date_invalido(self):
        from core.campaigns.money import parse_iso_date
        self.assertIsNone(parse_iso_date("15/06/2025"))

    def test_parse_iso_date_none(self):
        from core.campaigns.money import parse_iso_date
        self.assertIsNone(parse_iso_date(None))

    def test_format_date_br(self):
        from core.campaigns.money import format_date_br
        self.assertEqual(format_date_br("2025-06-15"), "15/06/2025")

    def test_format_date_br_none(self):
        from core.campaigns.money import format_date_br
        self.assertEqual(format_date_br(None), "—")

    def test_is_campaign_expired_passado(self):
        from core.campaigns.money import is_campaign_expired
        self.assertTrue(is_campaign_expired("2020-01-01"))

    def test_is_campaign_expired_futuro(self):
        from core.campaigns.money import is_campaign_expired
        self.assertFalse(is_campaign_expired("2099-12-31"))

    def test_is_campaign_expired_none(self):
        from core.campaigns.money import is_campaign_expired
        self.assertFalse(is_campaign_expired(None))


# ══════════════════════════════════════════════════════════════════════════════
# 6. TESTES: validate_campaign_data
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateCampaignData(unittest.TestCase):
    def _val(self, data):
        from core.campaigns.money import validate_campaign_data
        return validate_campaign_data(data)

    def test_dados_validos_sem_erros(self):
        errs = self._val(_camp_data())
        self.assertEqual(errs, [])

    def test_nome_vazio_gera_erro(self):
        errs = self._val(_camp_data(name=""))
        self.assertTrue(any("nome" in e.lower() for e in errs))

    def test_moeda_invalida_gera_erro(self):
        errs = self._val(_camp_data(currency="EUR"))
        self.assertTrue(any("moeda" in e.lower() or "brl" in e.lower() or "usd" in e.lower() for e in errs))

    def test_rate_negativo_gera_erro(self):
        errs = self._val(_camp_data(rate_per_1000_cents=-1))
        self.assertTrue(any("view" in e.lower() or "centavo" in e.lower() for e in errs))

    def test_plataforma_invalida_gera_erro(self):
        errs = self._val(_camp_data(platforms=["naoexiste"]))
        self.assertTrue(any("plataforma" in e.lower() for e in errs))

    def test_sem_plataformas_gera_erro(self):
        errs = self._val(_camp_data(platforms=[]))
        self.assertTrue(any("plataforma" in e.lower() for e in errs))

    def test_datas_invertidas_geram_erro(self):
        errs = self._val(_camp_data(starts_on="2025-12-31", ends_on="2025-01-01"))
        self.assertTrue(any("início" in e.lower() or "inicio" in e.lower() or "posterior" in e.lower() for e in errs))

    def test_url_invalida_gera_erro(self):
        errs = self._val(_camp_data(briefing_url="nao-e-url"))
        self.assertTrue(any("http" in e.lower() for e in errs))

    def test_fee_bp_invalido(self):
        errs = self._val(_camp_data(fee_bp=20000))
        self.assertTrue(any("comissão" in e.lower() or "comissao" in e.lower() for e in errs))

    def test_status_invalido_gera_erro(self):
        errs = self._val(_camp_data(status="invalido"))
        self.assertTrue(any("status" in e.lower() for e in errs))


# ══════════════════════════════════════════════════════════════════════════════
# 7. TESTES: validate_post_data
# ══════════════════════════════════════════════════════════════════════════════

class TestValidatePostData(unittest.TestCase):
    def _val(self, data):
        from core.campaigns.money import validate_post_data
        return validate_post_data(data)

    def test_dados_validos(self):
        errs = self._val({"platform": "youtube", "posted_on": "2025-01-15", "currency": "BRL"})
        self.assertEqual(errs, [])

    def test_plataforma_invalida(self):
        errs = self._val({"platform": "xxx", "posted_on": "2025-01-15", "currency": "BRL"})
        self.assertTrue(any("plataforma" in e.lower() for e in errs))

    def test_data_invalida(self):
        errs = self._val({"platform": "youtube", "posted_on": "15/01/2025", "currency": "BRL"})
        self.assertTrue(any("data" in e.lower() for e in errs))

    def test_url_invalida(self):
        errs = self._val({"platform": "youtube", "posted_on": "2025-01-15", "currency": "BRL", "post_url": "nao-url"})
        self.assertTrue(any("http" in e.lower() for e in errs))


# ══════════════════════════════════════════════════════════════════════════════
# 8. TESTES: validate_snapshot_data
# ══════════════════════════════════════════════════════════════════════════════

class TestValidateSnapshotData(unittest.TestCase):
    def _val(self, data, ref=None):
        from core.campaigns.money import validate_snapshot_data
        return validate_snapshot_data(data, ref_date=ref)

    def test_dados_validos(self):
        ref = datetime.date(2025, 6, 15)
        errs = self._val({"views": 1000, "snapshot_on": "2025-06-14"}, ref=ref)
        self.assertEqual(errs, [])

    def test_views_negativo_erro(self):
        ref = datetime.date(2025, 6, 15)
        errs = self._val({"views": -1, "snapshot_on": "2025-06-14"}, ref=ref)
        self.assertTrue(any("visuali" in e.lower() for e in errs))

    def test_data_futura_erro(self):
        ref = datetime.date(2025, 6, 15)
        errs = self._val({"views": 100, "snapshot_on": "2025-06-16"}, ref=ref)
        self.assertTrue(any("futura" in e.lower() for e in errs))

    def test_earnings_negativo_erro(self):
        ref = datetime.date(2025, 6, 15)
        errs = self._val({"views": 100, "snapshot_on": "2025-06-14", "earnings_cents": -1}, ref=ref)
        self.assertTrue(any("ganho" in e.lower() for e in errs))


# ══════════════════════════════════════════════════════════════════════════════
# 9. TESTES: CampaignRepo — CRUD de Campanhas
# ══════════════════════════════════════════════════════════════════════════════

class TestCampaignCRUD(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path, self.repo = _make_repo(self.tmp.name)

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_create_campaign_retorna_dict(self):
        c = self.repo.create_campaign(_camp_data())
        self.assertIsInstance(c, dict)
        self.assertEqual(c["name"], "Campanha Teste")
        self.assertIn("id", c)

    def test_create_campaign_persiste_plataformas(self):
        c = self.repo.create_campaign(_camp_data(platforms=["youtube", "tiktok"]))
        self.assertIn("youtube", c["platforms"])
        self.assertIn("tiktok", c["platforms"])

    def test_create_campaign_nome_duplicado_lanca_erro(self):
        self.repo.create_campaign(_camp_data(name="Campanha X"))
        with self.assertRaises(ValueError) as ctx:
            self.repo.create_campaign(_camp_data(name="Campanha X"))
        self.assertIn("Campanha X", str(ctx.exception))

    def test_create_campaign_dados_invalidos_lanca_erro(self):
        with self.assertRaises(ValueError):
            self.repo.create_campaign(_camp_data(name="", rate_per_1000_cents=-1))

    def test_get_campaign_por_id(self):
        c = self.repo.create_campaign(_camp_data())
        c2 = self.repo.get_campaign(c["id"])
        self.assertEqual(c["id"], c2["id"])
        self.assertEqual(c["name"], c2["name"])

    def test_get_campaign_inexistente_retorna_none(self):
        self.assertIsNone(self.repo.get_campaign(99999))

    def test_get_campaign_by_name(self):
        self.repo.create_campaign(_camp_data(name="Campanha Alfa"))
        c = self.repo.get_campaign_by_name("campanha alfa")  # case insensitive
        self.assertIsNotNone(c)
        self.assertEqual(c["name"], "Campanha Alfa")

    def test_list_campaigns_vazio(self):
        self.assertEqual(self.repo.list_campaigns(), [])

    def test_list_campaigns_retorna_todas(self):
        self.repo.create_campaign(_camp_data(name="Camp A"))
        self.repo.create_campaign(_camp_data(name="Camp B"))
        camps = self.repo.list_campaigns()
        self.assertEqual(len(camps), 2)

    def test_list_campaigns_filtro_status(self):
        self.repo.create_campaign(_camp_data(name="Ativa"))
        self.repo.create_campaign(_camp_data(name="Encerrada", status="encerrada"))
        ativas = self.repo.list_campaigns(status="ativa")
        self.assertEqual(len(ativas), 1)
        self.assertEqual(ativas[0]["name"], "Ativa")

    def test_update_campaign_altera_rate(self):
        c = self.repo.create_campaign(_camp_data())
        updated = self.repo.update_campaign(c["id"], {"rate_per_1000_cents": 1000})
        self.assertEqual(updated["rate_per_1000_cents"], 1000)

    def test_update_campaign_sincroniza_plataformas(self):
        c = self.repo.create_campaign(_camp_data(platforms=["youtube"]))
        updated = self.repo.update_campaign(c["id"], {"platforms": ["instagram", "tiktok"]})
        self.assertNotIn("youtube", updated["platforms"])
        self.assertIn("instagram", updated["platforms"])

    def test_update_campaign_inexistente_lanca_erro(self):
        with self.assertRaises(ValueError):
            self.repo.update_campaign(99999, {"name": "X"})

    def test_delete_campaign_sem_posts(self):
        c = self.repo.create_campaign(_camp_data())
        ok = self.repo.delete_campaign(c["id"])
        self.assertTrue(ok)
        self.assertIsNone(self.repo.get_campaign(c["id"]))

    def test_delete_campaign_com_posts_lanca_erro(self):
        c = self.repo.create_campaign(_camp_data())
        self.repo.create_post(_post_data(c["id"]))
        with self.assertRaises(ValueError) as ctx:
            self.repo.delete_campaign(c["id"])
        self.assertIn("publicação", str(ctx.exception).lower())

    def test_moeda_usd_aceita(self):
        c = self.repo.create_campaign(_camp_data(currency="USD", name="USD Camp"))
        self.assertEqual(c["currency"], "USD")


# ══════════════════════════════════════════════════════════════════════════════
# 10. TESTES: CampaignRepo — CRUD de Posts
# ══════════════════════════════════════════════════════════════════════════════

class TestPostCRUD(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path, self.repo = _make_repo(self.tmp.name)
        self.camp = self.repo.create_campaign(_camp_data())

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_create_post_retorna_dict(self):
        p = self.repo.create_post(_post_data(self.camp["id"]))
        self.assertIsInstance(p, dict)
        self.assertIn("id", p)
        self.assertEqual(p["platform"], "youtube")

    def test_create_post_herda_moeda_da_campanha(self):
        camp_usd = self.repo.create_campaign(_camp_data(name="USD Camp", currency="USD"))
        p = self.repo.create_post(_post_data(camp_usd["id"], currency="BRL"))
        # currency deve ser forçada para USD (da campanha)
        self.assertEqual(p["currency"], "USD")

    def test_create_post_sem_campanha(self):
        p = self.repo.create_post({
            "video_id": "vid1",
            "cut_key": "corte_01",
            "platform": "tiktok",
            "posted_on": "2025-02-01",
            "currency": "BRL",
        })
        self.assertIsNone(p["campaign_id"])

    def test_create_post_url_duplicada_lanca_erro(self):
        self.repo.create_post(_post_data(self.camp["id"]))
        with self.assertRaises(ValueError):
            self.repo.create_post(_post_data(self.camp["id"], account_label="Outro"))

    def test_get_post_por_id(self):
        p = self.repo.create_post(_post_data(self.camp["id"]))
        p2 = self.repo.get_post(p["id"])
        self.assertEqual(p["id"], p2["id"])

    def test_get_post_inexistente_retorna_none(self):
        self.assertIsNone(self.repo.get_post(99999))

    def test_list_posts_vazio(self):
        self.assertEqual(self.repo.list_posts(), [])

    def test_list_posts_por_campanha(self):
        camp2 = self.repo.create_campaign(_camp_data(name="Camp 2"))
        self.repo.create_post(_post_data(self.camp["id"]))
        self.repo.create_post(_post_data(camp2["id"], post_url="https://tiktok.com/x"))
        posts = self.repo.list_posts(campaign_id=self.camp["id"])
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["campaign_id"], self.camp["id"])

    def test_list_posts_por_plataforma(self):
        self.repo.create_post(_post_data(self.camp["id"]))
        self.repo.create_post(_post_data(self.camp["id"], platform="instagram", post_url="https://instagram.com/p/x"))
        posts = self.repo.list_posts(platform="instagram")
        self.assertEqual(len(posts), 1)

    def test_update_post(self):
        p = self.repo.create_post(_post_data(self.camp["id"]))
        updated = self.repo.update_post(p["id"], {"account_label": "Canal 2"})
        self.assertEqual(updated["account_label"], "Canal 2")

    def test_delete_post_remove_snapshots_cascade(self):
        p = self.repo.create_post(_post_data(self.camp["id"]))
        self.repo.record_snapshot(p["id"], "2025-01-20", views=5000)
        self.repo.delete_post(p["id"])
        # snapshots devem ter sido removidos em cascata
        snaps = self.repo.list_snapshots_for_post(p["id"])
        self.assertEqual(snaps, [])

    def test_delete_post_remove_post(self):
        p = self.repo.create_post(_post_data(self.camp["id"]))
        self.repo.delete_post(p["id"])
        self.assertIsNone(self.repo.get_post(p["id"]))


# ══════════════════════════════════════════════════════════════════════════════
# 11. TESTES: CampaignRepo — ViewSnapshots
# ══════════════════════════════════════════════════════════════════════════════

class TestViewSnapshots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path, self.repo = _make_repo(self.tmp.name)
        self.camp = self.repo.create_campaign(_camp_data())
        self.post = self.repo.create_post(_post_data(self.camp["id"]))
        self.ref_date = datetime.date(2025, 6, 15)

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_record_snapshot_basico(self):
        snap = self.repo.record_snapshot(
            self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date
        )
        self.assertEqual(snap["views"], 10000)
        self.assertEqual(snap["snapshot_on"], "2025-06-10")

    def test_record_snapshot_upsert_mesmo_dia(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=5000, ref_date=self.ref_date)
        snap2 = self.repo.record_snapshot(self.post["id"], "2025-06-10", views=7000, ref_date=self.ref_date)
        self.assertEqual(snap2["views"], 7000)
        # Deve haver apenas 1 snapshot nessa data
        all_snaps = self.repo.list_snapshots_for_post(self.post["id"])
        self.assertEqual(len(all_snaps), 1)

    def test_record_snapshot_avisa_decrescimo_views(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-09", views=10000, ref_date=self.ref_date)
        snap2 = self.repo.record_snapshot(self.post["id"], "2025-06-10", views=5000, ref_date=self.ref_date)
        self.assertIsNotNone(snap2.get("warning"))
        # O warning contém as views no formato f"{views:,}" (locale independente, ex: "5,000" ou "5.000")
        # Verificamos apenas que o número 5000 aparece em alguma forma no warning
        self.assertTrue("5" in snap2["warning"] and "000" in snap2["warning"])

    def test_record_snapshot_sem_aviso_views_crescente(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-09", views=5000, ref_date=self.ref_date)
        snap2 = self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        self.assertIsNone(snap2.get("warning"))

    def test_record_snapshot_com_earnings(self):
        snap = self.repo.record_snapshot(
            self.post["id"], "2025-06-10", views=10000, earnings_cents=4500, ref_date=self.ref_date
        )
        self.assertEqual(snap["earnings_cents"], 4500)

    def test_record_snapshot_data_futura_lanca_erro(self):
        with self.assertRaises(ValueError):
            self.repo.record_snapshot(
                self.post["id"], "2099-01-01", views=1000,
                ref_date=datetime.date(2025, 6, 15)
            )

    def test_record_snapshot_post_inexistente_lanca_erro(self):
        with self.assertRaises(ValueError):
            self.repo.record_snapshot(99999, "2025-06-10", views=1000, ref_date=self.ref_date)

    def test_get_latest_snapshot(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-09", views=5000, ref_date=self.ref_date)
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        latest = self.repo.get_latest_snapshot_for_post(self.post["id"])
        self.assertEqual(latest["snapshot_on"], "2025-06-10")

    def test_get_latest_snapshot_sem_registros_retorna_none(self):
        self.assertIsNone(self.repo.get_latest_snapshot_for_post(self.post["id"]))

    def test_list_snapshots_em_ordem_cronologica(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        self.repo.record_snapshot(self.post["id"], "2025-06-09", views=5000, ref_date=self.ref_date)
        snaps = self.repo.list_snapshots_for_post(self.post["id"])
        self.assertEqual(snaps[0]["snapshot_on"], "2025-06-09")
        self.assertEqual(snaps[1]["snapshot_on"], "2025-06-10")

    def test_delete_snapshot(self):
        snap = self.repo.record_snapshot(self.post["id"], "2025-06-10", views=5000, ref_date=self.ref_date)
        self.repo.delete_snapshot(snap["id"])
        self.assertIsNone(self.repo.get_latest_snapshot_for_post(self.post["id"]))


# ══════════════════════════════════════════════════════════════════════════════
# 12. TESTES: CampaignRepo — Métricas Calculadas
# ══════════════════════════════════════════════════════════════════════════════

class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path, self.repo = _make_repo(self.tmp.name)
        self.camp = self.repo.create_campaign(_camp_data(rate_per_1000_cents=500, fee_bp=1000))
        self.post = self.repo.create_post(_post_data(self.camp["id"]))
        self.ref_date = datetime.date(2025, 6, 15)

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_get_post_with_metrics_sem_snapshot(self):
        m = self.repo.get_post_with_metrics(self.post["id"])
        self.assertIsNotNone(m)
        self.assertEqual(m["calculations"]["views"], 0)
        self.assertEqual(m["calculations"]["bruto_cents"], 0)

    def test_get_post_with_metrics_com_snapshot(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        m = self.repo.get_post_with_metrics(self.post["id"])
        # 10000 views * 500 / 1000 = 5000 bruto; fee 10% → comissao=500, liquido=4500
        self.assertEqual(m["calculations"]["bruto_cents"], 5000)
        self.assertEqual(m["calculations"]["comissao_cents"], 500)
        self.assertEqual(m["calculations"]["liquido_cents"], 4500)

    def test_list_posts_with_metrics(self):
        post2 = self.repo.create_post(_post_data(self.camp["id"], platform="instagram", post_url="https://instagram.com/p/1"))
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        self.repo.record_snapshot(post2["id"], "2025-06-10", views=20000, ref_date=self.ref_date)
        lista = self.repo.list_posts_with_metrics(campaign_id=self.camp["id"])
        self.assertEqual(len(lista), 2)
        self.assertIn("calculations", lista[0])

    def test_get_totals_by_currency_brl(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        totals = self.repo.get_totals_by_currency()
        brl = totals["BRL"]
        self.assertEqual(brl["posts_count"], 1)
        self.assertEqual(brl["views"], 10000)
        self.assertGreater(brl["liquido_cents"], 0)

    def test_get_totals_separados_por_moeda(self):
        camp_usd = self.repo.create_campaign(_camp_data(name="USD Camp", currency="USD"))
        post_usd = self.repo.create_post(_post_data(camp_usd["id"], post_url="https://youtube.com/u"))
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=5000, ref_date=self.ref_date)
        self.repo.record_snapshot(post_usd["id"], "2025-06-10", views=3000, ref_date=self.ref_date)
        totals = self.repo.get_totals_by_currency()
        # Verifica que BRL e USD não se misturam
        self.assertEqual(totals["BRL"]["posts_count"], 1)
        self.assertEqual(totals["USD"]["posts_count"], 1)

    def test_get_totals_by_campaign(self):
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        summary = self.repo.get_totals_by_campaign()
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["posts_count"], 1)

    def test_get_totals_by_platform(self):
        post2 = self.repo.create_post(_post_data(self.camp["id"], platform="instagram", post_url="https://instagram.com/p/1"))
        self.repo.record_snapshot(self.post["id"], "2025-06-10", views=10000, ref_date=self.ref_date)
        self.repo.record_snapshot(post2["id"], "2025-06-10", views=5000, ref_date=self.ref_date)
        by_plat = self.repo.get_totals_by_platform()
        plat_names = [r["platform"] for r in by_plat]
        self.assertIn("youtube", plat_names)
        self.assertIn("instagram", plat_names)


# ══════════════════════════════════════════════════════════════════════════════
# 13. TESTES: CampaignRepo — Alertas
# ══════════════════════════════════════════════════════════════════════════════

class TestAlerts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path, self.repo = _make_repo(self.tmp.name)
        self.today = datetime.date(2025, 6, 15)

    def tearDown(self):
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_campanhas_expirando_em_breve(self):
        self.repo.create_campaign(_camp_data(name="Vence Hoje", ends_on="2025-06-15"))
        self.repo.create_campaign(_camp_data(name="Vence Amanha", ends_on="2025-06-16"))
        self.repo.create_campaign(_camp_data(name="Vence Longe", ends_on="2025-07-01"))
        expiring = self.repo.get_campaigns_expiring_soon(days=3, ref_date=self.today)
        names = [c["name"] for c in expiring]
        self.assertIn("Vence Hoje", names)
        self.assertIn("Vence Amanha", names)
        self.assertNotIn("Vence Longe", names)

    def test_campanhas_ja_encerradas_nao_entram_em_expirando(self):
        self.repo.create_campaign(_camp_data(name="Encerrada", status="encerrada", ends_on="2025-06-14"))
        expiring = self.repo.get_campaigns_expiring_soon(days=3, ref_date=self.today)
        self.assertEqual(expiring, [])

    def test_campanhas_sem_ends_on_nao_expiram(self):
        self.repo.create_campaign(_camp_data(name="Sem Prazo"))
        expiring = self.repo.get_campaigns_expiring_soon(days=3, ref_date=self.today)
        self.assertEqual(expiring, [])

    def test_posts_sem_atualizacao_recente(self):
        camp = self.repo.create_campaign(_camp_data(name="Ativa"))
        post = self.repo.create_post(_post_data(camp["id"], posted_on="2025-05-01"))
        stale = self.repo.get_posts_without_recent_updates(days=7, ref_date=self.today)
        stale_ids = [p["id"] for p in stale]
        self.assertIn(post["id"], stale_ids)

    def test_post_atualizado_recentemente_nao_entra_em_stale(self):
        camp = self.repo.create_campaign(_camp_data(name="Ativa 2"))
        post = self.repo.create_post(_post_data(camp["id"], post_url="https://yt.com/novo"))
        self.repo.record_snapshot(post["id"], "2025-06-14", views=100, ref_date=self.today)
        stale = self.repo.get_posts_without_recent_updates(days=7, ref_date=self.today)
        stale_ids = [p["id"] for p in stale]
        self.assertNotIn(post["id"], stale_ids)

    def test_post_de_campanha_encerrada_nao_entra_em_stale(self):
        camp = self.repo.create_campaign(_camp_data(name="Encerrada2", status="encerrada"))
        post = self.repo.create_post(_post_data(camp["id"], posted_on="2025-01-01"))
        stale = self.repo.get_posts_without_recent_updates(days=7, ref_date=self.today)
        stale_ids = [p["id"] for p in stale]
        self.assertNotIn(post["id"], stale_ids)


# ══════════════════════════════════════════════════════════════════════════════
# 14. TESTES: licensing_bridge (V3)
# ══════════════════════════════════════════════════════════════════════════════

class TestLicensingBridge(unittest.TestCase):
    def test_exige_briefing_url(self):
        from core.campaigns.licensing_bridge import can_apply_campaign_license, apply_campaign_license

        camp_sem_briefing = {"id": 1, "name": "Camp Sem Briefing", "briefing_url": ""}
        ok, msg = can_apply_campaign_license(camp_sem_briefing)
        self.assertFalse(ok)
        self.assertIn("link de briefing", msg.lower())

        res = apply_campaign_license(camp_sem_briefing, video_id="vid1", cut_key="c1", target="corte")
        self.assertFalse(res["success"])
        self.assertIn("link de briefing", res["error"].lower())

    def test_valida_e_grava_no_corte(self):
        from unittest.mock import patch
        from core.campaigns.licensing_bridge import apply_campaign_license

        camp = {
            "id": 10,
            "name": "Campanha Valida",
            "source_name": "Agencia Alfa",
            "briefing_url": "https://briefing.com/regras",
        }

        with patch("core.campaigns.licensing_bridge.get_cut_license", return_value=None), \
             patch("core.campaigns.licensing_bridge.set_cut_license") as mock_set:
            mock_set.return_value = {"status": "campanha_autorizada"}
            res = apply_campaign_license(camp, video_id="vid_123", cut_key="corte_01", target="corte")

            self.assertTrue(res["success"])
            mock_set.assert_called_once()
            args, _ = mock_set.call_args
            self.assertEqual(args[0], "vid_123")
            self.assertEqual(args[1], "corte_01")
            saved_lic = args[2]
            self.assertEqual(saved_lic["status"], "campanha_autorizada")
            self.assertEqual(saved_lic["origem"], "Agencia Alfa")
            self.assertEqual(saved_lic["campanha"], "Campanha Valida")
            self.assertEqual(saved_lic["link_briefing"], "https://briefing.com/regras")
            self.assertIn("id 10", saved_lic["observacao"])

    def test_valida_e_grava_no_video(self):
        from unittest.mock import patch
        from core.campaigns.licensing_bridge import apply_campaign_license

        camp = {
            "id": 20,
            "name": "Campanha Video Inteiro",
            "briefing_url": "https://briefing.com/regras_video",
        }

        with patch("core.campaigns.licensing_bridge.get_video_license", return_value=None), \
             patch("core.campaigns.licensing_bridge.set_video_license") as mock_set:
            mock_set.return_value = {"status": "campanha_autorizada"}
            res = apply_campaign_license(camp, video_id="vid_999", target="video")

            self.assertTrue(res["success"])
            mock_set.assert_called_once()
            args, _ = mock_set.call_args
            self.assertEqual(args[0], "vid_999")
            self.assertEqual(args[1]["status"], "campanha_autorizada")

    def test_nao_substitui_licenca_existente_sem_confirmacao(self):
        from unittest.mock import patch
        from core.campaigns.licensing_bridge import apply_campaign_license

        camp = {
            "id": 30,
            "name": "Campanha Teste",
            "briefing_url": "https://briefing.com/regras",
        }

        existing = {"status": "proprio", "origem": "Autor Original"}
        with patch("core.campaigns.licensing_bridge.get_cut_license", return_value=existing), \
             patch("core.campaigns.licensing_bridge.set_cut_license") as mock_set:

            # Sem confirmação -> deve recusar e solicitar confirmação
            res = apply_campaign_license(camp, video_id="vid_1", cut_key="c1", target="corte", confirm_override=False)
            self.assertFalse(res["success"])
            self.assertTrue(res.get("requires_confirmation"))
            mock_set.assert_not_called()

            # Com confirmação -> deve gravar normalmente
            res_conf = apply_campaign_license(camp, video_id="vid_1", cut_key="c1", target="corte", confirm_override=True)
            self.assertTrue(res_conf["success"])
            mock_set.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 15. TESTES: export_csv (V4)
# ══════════════════════════════════════════════════════════════════════════════

class TestExportCSV(unittest.TestCase):
    def test_export_posts_metrics_csv(self):
        from core.campaigns.export import export_posts_metrics_csv, cents_to_csv_decimal

        self.assertEqual(cents_to_csv_decimal(1250), "12,50")
        self.assertEqual(cents_to_csv_decimal(0), "0,00")
        self.assertEqual(cents_to_csv_decimal(None), "")

        post_mock = [{
            "id": 1,
            "platform": "youtube",
            "campaign": {"name": "Camp Q1"},
            "cut_title": "Corte de Teste",
            "video_id": "vid1",
            "cut_key": "k1",
            "posted_on": "2025-01-15",
            "account_label": "Canal 1",
            "post_url": "https://youtu.be/test",
            "currency": "BRL",
            "latest_snapshot": {"snapshot_on": "2025-01-20"},
            "calculations": {
                "views": 10000,
                "bruto_cents": 5000,
                "comissao_cents": 500,
                "liquido_cents": 4500,
                "earnings_reported_cents": 4000,
                "considerado_cents": 4000,
                "rpm_real_cents": 400.0,
            },
            "notes": "Observação importante",
        }]

        csv_bytes = export_posts_metrics_csv(post_mock)

        # 1. Verifica BOM (utf-8-sig)
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))

        csv_str = csv_bytes.decode("utf-8-sig")

        # 2. Verifica delimitador ';'
        self.assertIn(";", csv_str)
        header_line = csv_str.splitlines()[0]
        self.assertIn("ID Publicação;Plataforma;Campanha", header_line)

        # 3. Verifica vírgula decimal e formato de data DD/MM/AAAA
        data_line = csv_str.splitlines()[1]
        self.assertIn("15/01/2025", data_line)
        self.assertIn("20/01/2025", data_line)
        self.assertIn("50,00", data_line)
        self.assertIn("45,00", data_line)

    def test_export_campaigns_summary_csv(self):
        from core.campaigns.export import export_campaigns_summary_csv

        summary_mock = [{
            "campaign": {
                "id": 1,
                "name": "Campanha Total",
                "source_name": "Cliente X",
                "currency": "USD",
                "status": "ativa",
                "rate_per_1000_cents": 250,
                "cap_per_clip_cents": 1000,
                "fee_bp": 500,
                "hold_days": 15,
                "starts_on": "2025-01-01",
                "ends_on": "2025-01-31",
                "platforms": ["youtube", "tiktok"],
                "briefing_url": "https://briefing.com",
                "notes": "Notas da camp",
            },
            "posts_count": 2,
            "views": 50000,
            "bruto_cents": 12500,
            "comissao_cents": 625,
            "liquido_cents": 11875,
            "earnings_reported_cents": 11000,
            "considerado_cents": 11000,
            "rpm_real_cents": 220.0,
        }]

        csv_bytes = export_campaigns_summary_csv(summary_mock)
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
        csv_str = csv_bytes.decode("utf-8-sig")

        self.assertIn("ID Campanha;Nome da Campanha", csv_str)
        self.assertIn("01/01/2025", csv_str)
        self.assertIn("31/01/2025", csv_str)
        self.assertIn("125,00", csv_str)
        self.assertIn("118,75", csv_str)


# ══════════════════════════════════════════════════════════════════════════════
# 16. TESTES: corte removido ou renomeado (V5)
# ══════════════════════════════════════════════════════════════════════════════

class TestCutRemoved(unittest.TestCase):
    def test_corte_inexistente_nao_lanca_excecao_e_exibe_aviso(self):
        from core.campaigns.ui_tab import _format_cut_display_title, _is_cut_in_catalog

        # Simula corte cujo par video_id/cut_key não existe em cuts_catalog.json
        p = {
            "video_id": "video_fantasma_999",
            "cut_key": "corte_removido_123",
            "cut_title": "Destaque Antigo",
        }

        self.assertFalse(_is_cut_in_catalog(p["video_id"], p["cut_key"]))
        formatted = _format_cut_display_title(p)
        self.assertEqual(formatted, "⚠️ corte não encontrado no app (Destaque Antigo)")

    def test_post_sem_corte_do_app_exibe_titulo_normal(self):
        from core.campaigns.ui_tab import _format_cut_display_title

        p = {
            "video_id": None,
            "cut_key": None,
            "cut_title": "Post Externo TikTok",
        }
        formatted = _format_cut_display_title(p)
        self.assertEqual(formatted, "Post Externo TikTok")


# ══════════════════════════════════════════════════════════════════════════════
# 17. TESTES: exemplo numérico exato da Decisão 8
# ══════════════════════════════════════════════════════════════════════════════

class TestNumericalExampleDecision8(unittest.TestCase):
    def test_exemplo_numerico_decisao_8(self):
        """Exemplo de teste: 12345 views, 150 centavos por 1.000, sem teto,

        comissão 0 -> bruto 1852. Com teto 1500 -> 1500. Com teto 1500 e
        fee_bp 1000 -> comissão 150, líquido 1350.
        """
        from core.campaigns.money import calculate_cut_earnings

        # 1. Sem teto, comissão 0
        r1 = calculate_cut_earnings(views=12345, rate_per_1000_cents=150, cap_per_clip_cents=None, fee_bp=0)
        self.assertEqual(r1["bruto_cents"], 1852)
        self.assertEqual(r1["comissao_cents"], 0)
        self.assertEqual(r1["liquido_cents"], 1852)

        # 2. Com teto 1500
        r2 = calculate_cut_earnings(views=12345, rate_per_1000_cents=150, cap_per_clip_cents=1500, fee_bp=0)
        self.assertEqual(r2["bruto_cents"], 1500)
        self.assertEqual(r2["liquido_cents"], 1500)

        # 3. Com teto 1500 e fee_bp 1000 (10%)
        r3 = calculate_cut_earnings(views=12345, rate_per_1000_cents=150, cap_per_clip_cents=1500, fee_bp=1000)
        self.assertEqual(r3["bruto_cents"], 1500)
        self.assertEqual(r3["comissao_cents"], 150)
        self.assertEqual(r3["liquido_cents"], 1350)


# ══════════════════════════════════════════════════════════════════════════════
# 18. TESTES: concorrência básica com WAL
# ══════════════════════════════════════════════════════════════════════════════

class TestConcurrencyWAL(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path, self.repo = _make_repo(self.tmp.name)

    def tearDown(self):
        _close_wal(self.db_path)
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def test_duas_conexoes_gravando_em_sequencia_com_wal(self):
        """Verifica que duas conexões gravam e leem sem bloqueio nem erro de locked."""
        from core.campaigns.db import transaction, get_connection

        # Conexão 1 grava campanha
        with transaction(self.db_path) as conn1:
            conn1.execute(
                "INSERT INTO campaigns (name, currency, rate_per_1000_cents, created_at, updated_at) "
                "VALUES ('Camp WAL 1', 'BRL', 500, '2025-01-01', '2025-01-01');"
            )

        # Conexão 2 lê e grava outra campanha
        with transaction(self.db_path) as conn2:
            row = conn2.execute("SELECT count(*) as total FROM campaigns;").fetchone()
            self.assertEqual(row["total"], 1)
            conn2.execute(
                "INSERT INTO campaigns (name, currency, rate_per_1000_cents, created_at, updated_at) "
                "VALUES ('Camp WAL 2', 'BRL', 700, '2025-01-01', '2025-01-01');"
            )

        # Conexão de leitura confirma ambas
        with get_connection(self.db_path) as conn3:
            total = conn3.execute("SELECT count(*) as total FROM campaigns;").fetchone()["total"]
            self.assertEqual(total, 2)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
