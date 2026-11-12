"""
core/campaigns/db.py — Camada de Banco de Dados SQLite para Campanhas e Métricas.

Implementa:
- Conexão segura com timeout=10.0, row_factory=sqlite3.Row e foreign_keys=ON;
- Modo WAL (Write-Ahead Logging) para alta concorrência com Streamlit;
- Gerenciamento de transações com commit/rollback;
- Versionamento e migrações idempotentes via PRAGMA user_version.
"""

import os
import sqlite3
import contextlib
from typing import Optional, List, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "campaigns.db")


# ── MIGRATIONS ───────────────────────────────────────────────────────────────
# Cada item é uma tupla (versao_alvo: int, lista_de_comandos_sql: List[str]).
# Para adicionar uma nova versão no futuro (ex: v2):
# 1. Adicione a tupla (2, ["ALTER TABLE ...", "CREATE TABLE ..."]) ao final da lista.
# 2. init_db() aplicará automaticamente em transação e atualizará PRAGMA user_version = 2.
MIGRATIONS: List[Tuple[int, List[str]]] = [
    (
        1,
        [
            # Tabela de Campanhas
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                source_name TEXT,
                briefing_url TEXT,
                currency TEXT NOT NULL CHECK(currency IN ('BRL', 'USD')),
                rate_per_1000_cents INTEGER NOT NULL CHECK(rate_per_1000_cents >= 0),
                cap_per_clip_cents INTEGER CHECK(cap_per_clip_cents IS NULL OR cap_per_clip_cents >= 0),
                fee_bp INTEGER NOT NULL DEFAULT 0 CHECK(fee_bp >= 0 AND fee_bp <= 10000),
                hold_days INTEGER NOT NULL DEFAULT 0 CHECK(hold_days >= 0 AND hold_days <= 365),
                starts_on TEXT,
                ends_on TEXT,
                status TEXT NOT NULL DEFAULT 'ativa' CHECK(status IN ('ativa', 'pausada', 'encerrada')),
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            # Tabela associativa de Plataformas aceitas pela Campanha
            """
            CREATE TABLE IF NOT EXISTS campaign_platforms (
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                PRIMARY KEY(campaign_id, platform)
            );
            """,
            # Tabela de Publicações (Posts)
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER REFERENCES campaigns(id) ON DELETE RESTRICT,
                video_id TEXT,
                cut_key TEXT,
                cut_title TEXT,
                platform TEXT NOT NULL,
                account_label TEXT,
                post_url TEXT,
                posted_on TEXT NOT NULL,
                currency TEXT NOT NULL CHECK(currency IN ('BRL', 'USD')),
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_posts_campaign_id ON posts (campaign_id);",
            "CREATE INDEX IF NOT EXISTS idx_posts_video_cut ON posts (video_id, cut_key);",
            "CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts (platform);",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_posts_post_url ON posts (post_url)
            WHERE post_url IS NOT NULL AND post_url != '';
            """,
            # Tabela de Lançamentos Acumulados de Visualizações e Ganhos
            """
            CREATE TABLE IF NOT EXISTS view_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                snapshot_on TEXT NOT NULL,
                views INTEGER NOT NULL CHECK(views >= 0),
                earnings_cents INTEGER CHECK(earnings_cents IS NULL OR earnings_cents >= 0),
                note TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(post_id, snapshot_on)
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_snapshots_post_date ON view_snapshots (post_id, snapshot_on);",
        ],
    ),
]


@contextlib.contextmanager
def get_connection(db_path: Optional[str] = None):
    """Context manager para abrir conexão SQLite isolada.

    Configura:
    - timeout=10.0 para resiliência a locks concorrentes;
    - row_factory=sqlite3.Row para acesso associativo por nome de coluna;
    - PRAGMA foreign_keys = ON em toda conexão.
    """
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


@contextlib.contextmanager
def transaction(db_path: Optional[str] = None):
    """Context manager para blocos transacionais (commit automático ou rollback em erro)."""
    with get_connection(db_path) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def init_db(db_path: Optional[str] = None) -> int:
    """Inicializa ou migra o banco de dados via PRAGMA user_version.

    Executa PRAGMA journal_mode = WAL e aplica migrações pendentes em transação.
    Retorna a versão final do schema.
    """
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    with get_connection(path) as conn:
        # Ativa modo WAL para suportar múltiplos leitores e 1 escritor concorrentes
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
        except Exception:
            pass

        # Lê versão atual do schema
        cur_ver = conn.execute("PRAGMA user_version;").fetchone()[0]

    # Aplica migrações pendentes em ordem
    for target_ver, statements in MIGRATIONS:
        if target_ver > cur_ver:
            with transaction(path) as conn:
                for sql in statements:
                    clean_sql = sql.strip()
                    if clean_sql:
                        conn.execute(clean_sql)
                # Atualiza versão do schema
                conn.execute(f"PRAGMA user_version = {target_ver};")
            cur_ver = target_ver

    return cur_ver

