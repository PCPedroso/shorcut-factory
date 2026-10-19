"""
core/publishing/publish_queue.py — Fila Persistente de Publicação com SQLite.
Gerencia agendamentos, status de postagens, deduplicação de envios,
histórico de publicações e retentativas automáticas com backoff.
"""

import os
import json
import sqlite3
import datetime
from typing import Dict, Any, Optional, List, Tuple
from .base import Platform, JobStatus

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
QUEUE_DB_PATH = os.path.join(DATA_DIR, "publish_queue.db")


import contextlib

class PublishQueue:
    """
    Fila de execução assíncrona persistente baseada em SQLite.
    Permite agendar cortes para postagem futura e auditar o histórico de postagens.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or QUEUE_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Inicializa as tabelas necessárias."""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS publishing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cut_folder TEXT NOT NULL,
                cut_title TEXT,
                platform TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                scheduled_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                error_message TEXT,
                external_id TEXT,
                external_url TEXT,
                payload_json TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pub_status_sched ON publishing_jobs (status, scheduled_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pub_cut_plat ON publishing_jobs (cut_folder, platform);")
            conn.commit()

    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.now().isoformat()

    def enqueue(
        self,
        cut_folder: str,
        platform: Platform | str,
        cut_title: str,
        payload: Dict[str, Any],
        scheduled_at: Optional[datetime.datetime | str] = None,
        max_retries: int = 3,
        force_duplicate: bool = False
    ) -> Dict[str, Any]:
        """
        Adiciona um corte na fila para publicação imediata ou agendada.
        Garante deduplicação automática evitando criar jobs idênticos ativos.
        """
        plat_val = platform.value if isinstance(platform, Platform) else str(platform)
        
        # Deduplicação
        if not force_duplicate and self.is_already_active(cut_folder, plat_val):
            return {
                "success": False,
                "job_id": None,
                "error": f"Já existe um envio ativo ou concluído para este corte no {plat_val}."
            }

        if scheduled_at is None:
            sched_str = self._now_iso()
        elif isinstance(scheduled_at, datetime.datetime):
            sched_str = scheduled_at.isoformat()
        else:
            sched_str = str(scheduled_at)

        now = self._now_iso()
        payload_str = json.dumps(payload, ensure_ascii=False)

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO publishing_jobs (
                cut_folder, cut_title, platform, status, scheduled_at,
                created_at, updated_at, retry_count, max_retries, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?);
            """, (cut_folder, cut_title, plat_val, JobStatus.QUEUED.value, sched_str, now, now, max_retries, payload_str))
            job_id = cur.lastrowid
            conn.commit()

        return {
            "success": True,
            "job_id": job_id,
            "platform": plat_val,
            "scheduled_at": sched_str,
            "error": None
        }

    def is_already_active(self, cut_folder: str, platform: Platform | str) -> bool:
        """Verifica se o corte já está na fila ou foi publicado."""
        plat_val = platform.value if isinstance(platform, Platform) else str(platform)
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT id FROM publishing_jobs
            WHERE cut_folder = ? AND platform = ? AND status IN ('queued', 'uploading', 'processing', 'published')
            LIMIT 1;
            """, (cut_folder, plat_val)).fetchone()
            return row is not None

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Recupera os detalhes completos de um job pelo ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM publishing_jobs WHERE id = ?;", (job_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            if res.get("payload_json"):
                try:
                    res["payload"] = json.loads(res["payload_json"])
                except Exception:
                    res["payload"] = {}
            return res

    def get_pending_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Busca jobs na fila prontos para execução imediata (scheduled_at <= now)."""
        now = self._now_iso()
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT * FROM publishing_jobs
            WHERE status = ? AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
            LIMIT ?;
            """, (JobStatus.QUEUED.value, now, limit)).fetchall()
            
            jobs = []
            for r in rows:
                item = dict(r)
                if item.get("payload_json"):
                    try:
                        item["payload"] = json.loads(item["payload_json"])
                    except Exception:
                        item["payload"] = {}
                jobs.append(item)
            return jobs

    def update_job_status(
        self,
        job_id: int,
        status: JobStatus | str,
        error_message: Optional[str] = None,
        external_id: Optional[str] = None,
        external_url: Optional[str] = None
    ):
        """Atualiza o estado de execução de um job."""
        st_val = status.value if isinstance(status, JobStatus) else str(status)
        now = self._now_iso()

        with self._get_connection() as conn:
            conn.execute("""
            UPDATE publishing_jobs
            SET status = ?,
                error_message = coalesce(?, error_message),
                external_id = coalesce(?, external_id),
                external_url = coalesce(?, external_url),
                updated_at = ?
            WHERE id = ?;
            """, (st_val, error_message, external_id, external_url, now, job_id))
            conn.commit()

    def retry_job(self, job_id: int, delay_seconds: int = 60) -> bool:
        """Incrementa a contagem de tentativas e reagenda com atraso (backoff)."""
        job = self.get_job(job_id)
        if not job:
            return False

        new_count = (job.get("retry_count") or 0) + 1
        max_r = job.get("max_retries") or 3

        if new_count >= max_r:
            self.update_job_status(job_id, JobStatus.FAILED, error_message=f"Esgotadas {max_r} tentativas de publicação.")
            return False

        next_time = (datetime.datetime.now() + datetime.timedelta(seconds=delay_seconds)).isoformat()
        now = self._now_iso()

        with self._get_connection() as conn:
            conn.execute("""
            UPDATE publishing_jobs
            SET status = ?,
                retry_count = ?,
                scheduled_at = ?,
                updated_at = ?
            WHERE id = ?;
            """, (JobStatus.QUEUED.value, new_count, next_time, now, job_id))
            conn.commit()
        return True

    def cancel_job(self, job_id: int) -> bool:
        """Cancela um job pendente na fila."""
        job = self.get_job(job_id)
        if not job or job.get("status") in [JobStatus.PUBLISHED.value, JobStatus.CANCELLED.value]:
            return False

        self.update_job_status(job_id, JobStatus.CANCELLED)
        return True

    def list_jobs(
        self,
        platform: Optional[Platform | str] = None,
        status: Optional[JobStatus | str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Lista histórico ou estado atual dos jobs com filtros opcionais."""
        query = "SELECT * FROM publishing_jobs WHERE 1=1"
        params = []

        if platform:
            plat_val = platform.value if isinstance(platform, Platform) else str(platform)
            query += " AND platform = ?"
            params.append(plat_val)

        if status:
            st_val = status.value if isinstance(status, JobStatus) else str(status)
            query += " AND status = ?"
            params.append(st_val)

        query += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            jobs = []
            for r in rows:
                item = dict(r)
                if item.get("payload_json"):
                    try:
                        item["payload"] = json.loads(item["payload_json"])
                    except Exception:
                        item["payload"] = {}
                jobs.append(item)
            return jobs

    def get_summary_stats(self) -> Dict[str, int]:
        """Estatísticas gerais da fila para exibição em métricas na UI."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT status, count(*) as cnt
            FROM publishing_jobs
            GROUP BY status;
            """)
            counts = {row["status"]: row["cnt"] for row in cur.fetchall()}
            
            return {
                "queued": counts.get(JobStatus.QUEUED.value, 0),
                "uploading": counts.get(JobStatus.UPLOADING.value, 0),
                "published": counts.get(JobStatus.PUBLISHED.value, 0),
                "failed": counts.get(JobStatus.FAILED.value, 0),
                "needs_action": counts.get(JobStatus.NEEDS_ACTION.value, 0),
                "total": sum(counts.values())
            }
