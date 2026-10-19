"""
core/publishing/worker.py — Worker em Background para Execução e Retry da Fila de Publicação.
Monitora a fila SQLite, respeita intervalos de segurança entre postagens na mesma rede,
executa uploads assíncronos e gerencia retentativas com backoff.
"""

import time
import threading
from typing import Optional, Dict
from .base import Platform, JobStatus
from .publish_queue import PublishQueue
from .platform_registry import PlatformRegistry

# Intervalo mínimo de segurança (segundos) entre uploads consecutivos na mesma plataforma
MIN_PLATFORM_INTERVALS = {
    Platform.YOUTUBE.value: 15.0,
    Platform.INSTAGRAM.value: 30.0,
    Platform.TIKTOK.value: 20.0,
    Platform.X.value: 15.0,
    Platform.KWAI.value: 10.0,
}


class PublishWorker:
    """
    Worker daemon que consome a fila de postagens de forma assíncrona,
    garantindo que a interface web (Streamlit) permaneça leve e responsiva.
    """

    def __init__(self, queue: Optional[PublishQueue] = None, poll_interval_sec: float = 3.0):
        self.queue = queue or PublishQueue()
        self.poll_interval_sec = poll_interval_sec
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_post_time: Dict[str, float] = {}
        self._lock = threading.Lock()

    def start(self):
        """Inicia o worker daemon se ainda não estiver em execução."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="ViralCut-PublishWorker"
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0):
        """Sinaliza para o worker encerrar."""
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                return
            self._stop_event.set()
        self._thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _can_post_to_platform(self, platform_str: str) -> bool:
        """Checa se o intervalo mínimo de segurança entre posts já foi respeitado."""
        min_sec = MIN_PLATFORM_INTERVALS.get(platform_str, 15.0)
        last_t = self._last_post_time.get(platform_str, 0.0)
        return (time.time() - last_t) >= min_sec

    def _run_loop(self):
        """Loop contínuo de verificação de jobs prontos na fila."""
        while not self._stop_event.is_set():
            try:
                pending = self.queue.get_pending_jobs(limit=5)
                for job in pending:
                    if self._stop_event.is_set():
                        break

                    plat_str = job.get("platform")
                    if not self._can_post_to_platform(plat_str):
                        # Respeita o cooldown da plataforma e aguarda próximo ciclo
                        continue

                    self._process_single_job(job)

            except Exception:
                pass

            self._stop_event.wait(timeout=self.poll_interval_sec)

    def _process_single_job(self, job: dict):
        """Executa um job individual."""
        job_id = job["id"]
        plat_str = job["platform"]
        payload = job.get("payload") or {}

        try:
            plat_enum = Platform(plat_str)
        except ValueError:
            self.queue.update_job_status(job_id, JobStatus.FAILED, error_message=f"Plataforma desconhecida: {plat_str}")
            return

        publisher = PlatformRegistry.get_publisher(plat_enum)
        if not publisher:
            self.queue.update_job_status(
                job_id,
                JobStatus.FAILED,
                error_message=f"Publicador para {plat_enum.display_name} ainda não está registrado ou configurado."
            )
            return

        # 1. Marca como uploading
        self.queue.update_job_status(job_id, JobStatus.UPLOADING)

        video_path = payload.get("video_path")
        caption_data = payload.get("caption_data")
        thumb_path = payload.get("thumbnail_path")
        options = payload.get("options") or {}

        try:
            # 2. Executa a publicação
            pub_res = publisher.publish(
                video_path=video_path,
                caption_data=caption_data,
                thumbnail_path=thumb_path,
                options=options
            )

            # Atualiza o timestamp do último post nesta rede
            self._last_post_time[plat_str] = time.time()

            if pub_res.success:
                if pub_res.requires_manual_step:
                    self.queue.update_job_status(
                        job_id,
                        JobStatus.NEEDS_ACTION,
                        external_id=pub_res.post_id,
                        external_url=pub_res.post_url,
                        error_message=pub_res.manual_instructions
                    )
                else:
                    self.queue.update_job_status(
                        job_id,
                        JobStatus.PUBLISHED,
                        external_id=pub_res.post_id,
                        external_url=pub_res.post_url
                    )
            else:
                # Trata retry
                did_retry = self.queue.retry_job(job_id, delay_seconds=60)
                if not did_retry:
                    self.queue.update_job_status(job_id, JobStatus.FAILED, error_message=pub_res.error)

        except Exception as exc:
            did_retry = self.queue.retry_job(job_id, delay_seconds=60)
            if not did_retry:
                self.queue.update_job_status(job_id, JobStatus.FAILED, error_message=str(exc))
