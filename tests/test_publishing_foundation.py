import os
import tempfile
import unittest
import datetime
from unittest.mock import MagicMock, patch

from core.publishing import (
    Platform,
    JobStatus,
    PreflightResult,
    AdaptedCaption,
    PublishResult,
    BasePublisher,
    CredentialVault,
    MediaPreflight,
    CaptionAdapter,
    PublishQueue,
    PublishWorker,
    PlatformRegistry
)


class TestPublishingFoundation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    # ── 1. Enums e Dataclasses ───────────────────────────────────────────────
    def test_platform_enum_properties(self):
        self.assertEqual(Platform.YOUTUBE.display_name, "YouTube Shorts")
        self.assertEqual(Platform.INSTAGRAM.display_name, "Instagram Reels")
        self.assertEqual(Platform.TIKTOK.display_name, "TikTok")
        self.assertEqual(Platform.X.display_name, "X (Twitter)")
        self.assertEqual(Platform.KWAI.display_name, "Kwai")

        self.assertIn("🔴", Platform.YOUTUBE.icon)
        self.assertIn("📸", Platform.INSTAGRAM.icon)

    # ── 2. CredentialVault ───────────────────────────────────────────────────
    def test_credential_vault_crud(self):
        vault_path = os.path.join(self.temp_dir.name, "test_vault.enc")
        vault = CredentialVault(vault_path=vault_path)

        # Inicialmente vazio
        self.assertFalse(vault.has_credential(Platform.YOUTUBE))
        self.assertIsNone(vault.get_credential(Platform.YOUTUBE))

        # Salva credencial
        sample_token = {
            "token": "ya29.sample_access_token",
            "refresh_token": "1//sample_refresh_token",
            "client_id": "test_client_id.apps.googleusercontent.com"
        }
        vault.save_credential(Platform.YOUTUBE, sample_token)

        # Verifica recuperação
        self.assertTrue(vault.has_credential(Platform.YOUTUBE))
        loaded = vault.get_credential(Platform.YOUTUBE)
        self.assertEqual(loaded["token"], "ya29.sample_access_token")
        self.assertEqual(loaded["refresh_token"], "1//sample_refresh_token")

        # Lista plataformas ativas
        connected = vault.list_connected_platforms()
        self.assertIn(Platform.YOUTUBE, connected)

        # Deleta credencial
        self.assertTrue(vault.delete_credential(Platform.YOUTUBE))
        self.assertFalse(vault.has_credential(Platform.YOUTUBE))

    # ── 3. CaptionAdapter ────────────────────────────────────────────────────
    def test_caption_adapter_youtube(self):
        res = CaptionAdapter.adapt(
            platform=Platform.YOUTUBE,
            title="Como criar cortes virais com IA",
            description="Aprenda neste vídeo como minerar os melhores ganchos.",
            hashtags=["cortes", "podcast", "viral"],
            tags_seo="cortes podcast, como fazer cortes, inteligência artificial",
            orig_video_info={"channel": "Flow Podcast", "title": "Episódio Completo", "url": "https://youtube.com/watch?v=123"}
        )
        self.assertTrue(res.is_within_limits)
        self.assertIn("#Shorts", res.title)
        self.assertIn("Flow Podcast", res.description)
        # As tags SEO não devem ter '#' e devem ser lista limpa
        self.assertTrue(all(not t.startswith("#") for t in res.tags_seo))
        self.assertIn("cortes podcast", res.tags_seo)

    def test_caption_adapter_instagram_limit(self):
        # 35 hashtags fornecidas -> deve limitar a 30
        tags = [f"tag{i}" for i in range(35)]
        res = CaptionAdapter.adapt(
            platform=Platform.INSTAGRAM,
            title="Dica de Ouro",
            description="Confira esta super dica para criadores.",
            hashtags=tags
        )
        self.assertTrue(res.is_within_limits)
        self.assertLessEqual(len(res.hashtags), 30)

    def test_caption_adapter_x_character_limit(self):
        long_title = "Este é um título extremamente longo que descreve detalhadamente uma situação complexa " * 4
        res = CaptionAdapter.adapt(
            platform=Platform.X,
            title=long_title,
            description="descrição ignorada no x",
            hashtags=["viral", "cortes", "tech"],
            orig_video_info={"url": "https://youtube.com/watch?v=xyz123"}
        )
        self.assertTrue(res.is_within_limits)
        self.assertLessEqual(res.character_count, 280)
        self.assertIn("https://youtube.com/watch?v=xyz123", res.description)

    # ── 4. MediaPreflight ────────────────────────────────────────────────────
    def test_media_preflight_validation(self):
        # Mock de vídeo com duração de 120s para o Instagram Reels (limite é 90s)
        with patch.object(MediaPreflight, "probe_media") as mock_probe:
            mock_probe.return_value = {
                "width": 1080,
                "height": 1920,
                "duration_sec": 120.0,
                "file_size_bytes": 45 * 1024 * 1024,
                "video_codec": "h264",
                "audio_codec": "aac",
                "fps": 30.0,
                "has_faststart": True,
                "error": None
            }

            # No Instagram (máx 90s), 120s deve ser inválido e sugerir fatiamento
            res_ig = MediaPreflight.validate_for_platform("video_fake.mp4", Platform.INSTAGRAM)
            self.assertFalse(res_ig.is_valid)
            self.assertTrue(res_ig.needs_transcode)
            self.assertTrue(any("excede o limite de 90" in r for r in res_ig.reasons))

            # No YouTube Shorts (suporta até 180s), 120s deve ser válido
            res_yt = MediaPreflight.validate_for_platform("video_fake.mp4", Platform.YOUTUBE)
            self.assertTrue(res_yt.is_valid)
            self.assertFalse(res_yt.needs_transcode)

    # ── 5. PublishQueue ──────────────────────────────────────────────────────
    def test_publish_queue_lifecycle(self):
        db_path = os.path.join(self.temp_dir.name, "test_queue.db")
        queue = PublishQueue(db_path=db_path)

        payload = {
            "video_path": "data/video.mp4",
            "title": "Corte de Teste",
            "caption": "Legenda bacana"
        }

        # 1. Enfileirar
        res = queue.enqueue(
            cut_folder="VFDBS_corte_01",
            platform=Platform.YOUTUBE,
            cut_title="Corte de Teste",
            payload=payload
        )
        self.assertTrue(res["success"])
        job_id = res["job_id"]
        self.assertIsNotNone(job_id)

        # 2. Deduplicação: tentar enfileirar de novo o mesmo corte na mesma rede deve ser barrado
        dup_res = queue.enqueue(
            cut_folder="VFDBS_corte_01",
            platform=Platform.YOUTUBE,
            cut_title="Corte de Teste",
            payload=payload
        )
        self.assertFalse(dup_res["success"])
        self.assertIn("Já existe um envio ativo", dup_res["error"])

        # 3. Consulta de pendentes
        pending = queue.get_pending_jobs(limit=10)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], job_id)
        self.assertEqual(pending[0]["payload"]["title"], "Corte de Teste")

        # 4. Atualização de status para uploading -> published
        queue.update_job_status(job_id, JobStatus.UPLOADING)
        job = queue.get_job(job_id)
        self.assertEqual(job["status"], JobStatus.UPLOADING.value)

        queue.update_job_status(
            job_id,
            JobStatus.PUBLISHED,
            external_id="yt_12345",
            external_url="https://youtube.com/shorts/yt_12345"
        )
        job_published = queue.get_job(job_id)
        self.assertEqual(job_published["status"], JobStatus.PUBLISHED.value)
        self.assertEqual(job_published["external_id"], "yt_12345")
        self.assertEqual(job_published["external_url"], "https://youtube.com/shorts/yt_12345")

        # 5. Estatísticas
        stats = queue.get_summary_stats()
        self.assertEqual(stats["published"], 1)
        self.assertEqual(stats["queued"], 0)

    def test_publish_queue_retry_and_cancel(self):
        db_path = os.path.join(self.temp_dir.name, "test_retry.db")
        queue = PublishQueue(db_path=db_path)

        res = queue.enqueue(
            cut_folder="VFDBS_corte_02",
            platform=Platform.TIKTOK,
            cut_title="Corte Falha",
            payload={"video": "abc.mp4"},
            max_retries=2
        )
        job_id = res["job_id"]

        # Primeira retentativa
        did_retry = queue.retry_job(job_id, delay_seconds=10)
        self.assertTrue(did_retry)
        j1 = queue.get_job(job_id)
        self.assertEqual(j1["retry_count"], 1)
        self.assertEqual(j1["status"], JobStatus.QUEUED.value)

        # Segunda retentativa (atinge max_retries = 2)
        did_retry_2 = queue.retry_job(job_id, delay_seconds=10)
        self.assertFalse(did_retry_2)
        j2 = queue.get_job(job_id)
        self.assertEqual(j2["status"], JobStatus.FAILED.value)

    # ── 6. PlatformRegistry & Worker ─────────────────────────────────────────
    def test_platform_registry_and_worker(self):
        # Cria um mock publisher
        mock_publisher = MagicMock(spec=BasePublisher)
        mock_publisher.publish.return_value = PublishResult(
            success=True,
            platform=Platform.YOUTUBE,
            post_id="mock_yt_vid",
            post_url="https://youtube.com/shorts/mock_yt_vid"
        )

        PlatformRegistry.register(Platform.YOUTUBE, lambda p: mock_publisher)
        pub = PlatformRegistry.get_publisher(Platform.YOUTUBE)
        self.assertIsNotNone(pub)

        # Testa worker com fila temporária
        db_path = os.path.join(self.temp_dir.name, "test_worker.db")
        queue = PublishQueue(db_path=db_path)
        queue.enqueue(
            cut_folder="VFDBS_corte_worker",
            platform=Platform.YOUTUBE,
            cut_title="Vídeo Worker",
            payload={"video_path": "fake.mp4"}
        )

        worker = PublishWorker(queue=queue, poll_interval_sec=0.1)
        # Processa 1 job diretamente
        pending = queue.get_pending_jobs(limit=1)
        self.assertEqual(len(pending), 1)

        worker._process_single_job(pending[0])

        finished_job = queue.get_job(pending[0]["id"])
        self.assertEqual(finished_job["status"], JobStatus.PUBLISHED.value)
        self.assertEqual(finished_job["external_id"], "mock_yt_vid")
        self.assertEqual(finished_job["external_url"], "https://youtube.com/shorts/mock_yt_vid")


if __name__ == "__main__":
    unittest.main()
