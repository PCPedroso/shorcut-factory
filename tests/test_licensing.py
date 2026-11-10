"""tests/test_licensing.py — Bateria de Testes para o Recurso Fonte e Licença.

Cobre:
- Validação por status, campos obrigatórios, links e limites de tamanho.
- Leitura defensiva e fail-safe (valores nulos, tipos incorretos, status desconhecidos).
- Resolução de regras de herança (corte, vídeo, padrão).
- Persistência e não-apagamento em library_manager e cuts_catalog.
- Retrocompatibilidade com arquivos legados (sem a chave licenca).
- Guard de bloqueio em PublishQueue, PublishWorker, send_to_webhook e upload_to_youtube_shorts.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.licensing import (
    STATUS_NAO_VERIFICADO,
    STATUS_PROPRIO,
    STATUS_CAMPANHA,
    STATUS_LICENCA_LIVRE,
    STATUS_AUTORIZACAO_DIRETA,
    STATUS_VALIDOS,
    normalize_license,
    validate_license,
    is_publishable,
    resolve_effective_license,
    resolve_cut_reference_from_path,
    check_publishable,
    format_license_for_saving,
)
from core.library_manager import (
    get_video_license,
    set_video_license,
    add_or_update_video_in_library,
)
from core.cuts_catalog import (
    get_cut_license,
    set_cut_license,
    get_effective_license_for_cut,
    register_cut_instance,
    update_cut_texts_only,
    _raw_load_cuts_catalog,
)
from core.publishing.base import Platform, JobStatus, BasePublisher, PublishResult
from core.publishing.publish_queue import PublishQueue
from core.publishing.worker import PublishWorker
from core.publishing.platform_registry import PlatformRegistry
from core.integrations import send_to_webhook, upload_to_youtube_shorts
import core.publishing.platform_registry as _pr_module


class TestLicensingValidation(unittest.TestCase):
    """Testa validação e regras de negócio de licença ao salvar."""

    def test_status_proprio_valid(self):
        lic = {"status": STATUS_PROPRIO}
        errors = validate_license(lic)
        self.assertEqual(errors, [])

    def test_status_nao_verificado_valid(self):
        lic = {"status": STATUS_NAO_VERIFICADO}
        errors = validate_license(lic)
        self.assertEqual(errors, [])

    def test_status_campanha_missing_fields(self):
        # Falta campanha e link_briefing
        lic = {"status": STATUS_CAMPANHA}
        errors = validate_license(lic)
        self.assertTrue(any("campanha é obrigatório" in e for e in errors))
        self.assertTrue(any("link do briefing" in e for e in errors))

    def test_status_campanha_valid(self):
        lic = {
            "status": STATUS_CAMPANHA,
            "campanha": "Campanha Black Friday 2026",
            "link_briefing": "https://notion.so/briefing-123",
        }
        errors = validate_license(lic)
        self.assertEqual(errors, [])

    def test_status_licenca_livre_missing_link(self):
        lic = {"status": STATUS_LICENCA_LIVRE}
        errors = validate_license(lic)
        self.assertTrue(any("link da licença" in e for e in errors))

    def test_status_licenca_livre_valid(self):
        lic = {
            "status": STATUS_LICENCA_LIVRE,
            "link_briefing": "https://creativecommons.org/licenses/by/4.0/",
            "observacao": "CC BY 4.0",
        }
        errors = validate_license(lic)
        self.assertEqual(errors, [])

    def test_status_autorizacao_direta_missing_obs(self):
        lic = {"status": STATUS_AUTORIZACAO_DIRETA}
        errors = validate_license(lic)
        self.assertTrue(any("observação é obrigatória" in e for e in errors))

    def test_status_autorizacao_direta_valid(self):
        lic = {
            "status": STATUS_AUTORIZACAO_DIRETA,
            "observacao": "Autorizado por e-mail pelo criador Fulano em 10/11/2026",
        }
        errors = validate_license(lic)
        self.assertEqual(errors, [])

    def test_invalid_status(self):
        lic = {"status": "invalido_status_xyz"}
        errors = validate_license(lic)
        self.assertTrue(any("Status inválido" in e for e in errors))

    def test_invalid_url_protocol(self):
        lic = {
            "status": STATUS_CAMPANHA,
            "campanha": "Campanha Teste",
            "link_briefing": "ftp://servidor/arquivo.pdf",
        }
        errors = validate_license(lic)
        self.assertTrue(any("deve começar com 'http://' ou 'https://'" in e for e in errors))

    def test_max_length_limits(self):
        lic = {
            "status": STATUS_PROPRIO,
            "origem": "a" * 305,
            "campanha": "b" * 305,
            "link_briefing": "https://" + "c" * 505,
            "observacao": "d" * 1005,
        }
        errors = validate_license(lic)
        self.assertTrue(any("Origem" in e for e in errors))
        self.assertTrue(any("Campanha" in e for e in errors))
        self.assertTrue(any("Link" in e for e in errors))
        self.assertTrue(any("Observação" in e for e in errors))


class TestLicensingDefensiveReading(unittest.TestCase):
    """Testa leitura defensiva, normalização fail-safe e publicabilidade."""

    def test_normalize_none_or_non_dict(self):
        res = normalize_license(None)
        self.assertEqual(res["status"], STATUS_NAO_VERIFICADO)
        self.assertEqual(res["origem"], "")

        res_str = normalize_license("string_invalida")
        self.assertEqual(res_str["status"], STATUS_NAO_VERIFICADO)

    def test_normalize_unknown_status(self):
        res = normalize_license({"status": "fantasma", "origem": "Youtube"})
        self.assertEqual(res["status"], STATUS_NAO_VERIFICADO)
        self.assertEqual(res["origem"], "Youtube")

    def test_is_publishable(self):
        self.assertFalse(is_publishable(None))
        self.assertFalse(is_publishable({"status": STATUS_NAO_VERIFICADO}))
        self.assertFalse(is_publishable({"status": "status_inexistente"}))
        self.assertTrue(is_publishable({"status": STATUS_PROPRIO}))
        self.assertTrue(is_publishable({"status": STATUS_CAMPANHA}))
        self.assertTrue(is_publishable({"status": STATUS_LICENCA_LIVRE}))
        self.assertTrue(is_publishable({"status": STATUS_AUTORIZACAO_DIRETA}))


class TestLicensingInheritance(unittest.TestCase):
    """Testa a resolução de herança entre vídeo e corte."""

    def test_both_none(self):
        eff, src = resolve_effective_license(None, None)
        self.assertEqual(eff["status"], STATUS_NAO_VERIFICADO)
        self.assertEqual(src, "padrao")

    def test_video_only(self):
        v_lic = {"status": STATUS_PROPRIO, "origem": "Canal Oficial"}
        eff, src = resolve_effective_license(v_lic, None)
        self.assertEqual(eff["status"], STATUS_PROPRIO)
        self.assertEqual(src, "video")

    def test_cut_override(self):
        v_lic = {"status": STATUS_PROPRIO}
        c_lic = {"status": STATUS_NAO_VERIFICADO, "observacao": "Contém música com copyright"}
        eff, src = resolve_effective_license(v_lic, c_lic)
        self.assertEqual(eff["status"], STATUS_NAO_VERIFICADO)
        self.assertEqual(src, "corte")

    def test_cut_inherits_when_empty_dict(self):
        v_lic = {"status": STATUS_CAMPANHA, "campanha": "Promo X"}
        c_lic = {}
        eff, src = resolve_effective_license(v_lic, c_lic)
        self.assertEqual(eff["status"], STATUS_CAMPANHA)
        self.assertEqual(src, "video")


class TestLicensingPersistence(unittest.TestCase):
    """Testa persistência e preservação de metadados em library_manager e cuts_catalog."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_data_dir = "data"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_video_license_persistence(self):
        with patch("core.library_manager.DATA_DIR", self.temp_dir.name):
            vid = "test_vid_123"
            v_dir = os.path.join(self.temp_dir.name, vid)
            os.makedirs(v_dir, exist_ok=True)

            # Inicialmente não tem licença
            init_lic = get_video_license(vid)
            self.assertEqual(init_lic["status"], STATUS_NAO_VERIFICADO)

            # Define licença
            saved_meta = set_video_license(
                vid,
                format_license_for_saving(STATUS_PROPRIO, origem="Gravação própria")
            )
            self.assertIn("licenca", saved_meta)
            self.assertEqual(saved_meta["licenca"]["status"], STATUS_PROPRIO)

            # Consulta novamente
            read_lic = get_video_license(vid)
            self.assertEqual(read_lic["status"], STATUS_PROPRIO)
            self.assertEqual(read_lic["origem"], "Gravação própria")

            # add_or_update_video_in_library NÃO deve apagar a chave licenca
            with patch("core.library_manager.get_library", return_value=[]), \
                 patch("core.library_manager.save_library_list"):
                add_or_update_video_in_library(
                    video_id=vid,
                    title="Novo Título Atualizado",
                    upload_date_raw="20261110",
                    url="https://youtube.com/watch?v=123"
                )

            # Verifica se licença foi preservada
            after_lic = get_video_license(vid)
            self.assertEqual(after_lic["status"], STATUS_PROPRIO)
            self.assertEqual(after_lic["origem"], "Gravação própria")

    def test_cut_license_persistence_and_rerender(self):
        with patch("core.cuts_catalog._get_catalog_path", return_value=os.path.join(self.temp_dir.name, "cuts_catalog.json")):
            vid = "vid_cut_test"
            cut_key = "00:00:10.00_00:00:30.00"

            # Registra corte inicial
            register_cut_instance(
                video_id=vid,
                start_time="00:00:10.00",
                end_time="00:00:30.00",
                title="Corte Original",
                description="Desc",
                hashtags=[],
                tags_seo="",
                aspect_mode="9:16_blur",
                folder_name="VFDBS_cut_1",
                folder_path="",
                video_path=""
            )

            # Define licença própria no corte
            set_cut_license(
                vid,
                cut_key,
                format_license_for_saving(STATUS_AUTORIZACAO_DIRETA, observacao="Autorizado por João")
            )

            lic_corte = get_cut_license(vid, cut_key)
            self.assertEqual(lic_corte["status"], STATUS_AUTORIZACAO_DIRETA)

            # Re-renderização / re-registro NÃO deve apagar a licença do corte
            register_cut_instance(
                video_id=vid,
                start_time="00:00:10.00",
                end_time="00:00:30.00",
                title="Corte Atualizado Render",
                description="Nova Desc",
                hashtags=[],
                tags_seo="",
                aspect_mode="9:16_smart_face",
                folder_name="VRIRA_cut_1",
                folder_path="",
                video_path=""
            )

            lic_after_rerender = get_cut_license(vid, cut_key)
            self.assertEqual(lic_after_rerender["status"], STATUS_AUTORIZACAO_DIRETA)
            self.assertEqual(lic_after_rerender["observacao"], "Autorizado por João")

            # update_cut_texts_only NÃO deve apagar a licença do corte
            update_cut_texts_only(
                video_id=vid,
                start_time="00:00:10.00",
                end_time="00:00:30.00",
                title="Título Text Only",
                description="Desc Text Only",
                hashtags=["#teste"],
                tags_seo="seo"
            )

            lic_after_texts = get_cut_license(vid, cut_key)
            self.assertEqual(lic_after_texts["status"], STATUS_AUTORIZACAO_DIRETA)

            # Remover sobrescrita volta a retornar None (herdar do vídeo)
            set_cut_license(vid, cut_key, None)
            self.assertIsNone(get_cut_license(vid, cut_key))


class TestPublishGuard(unittest.TestCase):
    """Testa os pontos de bloqueio de publicação (enqueue, worker, integrations)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        # Limpa registry global para evitar contaminação entre testes
        _pr_module._REGISTRY.clear()
        _pr_module._PUBLISHER_CLASSES.clear()

    def tearDown(self):
        self.temp_dir.cleanup()
        _pr_module._REGISTRY.clear()
        _pr_module._PUBLISHER_CLASSES.clear()

    def test_enqueue_blocks_unverified(self):
        db_path = os.path.join(self.temp_dir.name, "queue.db")
        q = PublishQueue(db_path=db_path)

        with patch("core.publishing.publish_queue.check_publishable", return_value={"ok": False, "motivo": "Bloqueado: não verificado"}):
            res = q.enqueue(
                cut_folder="VFDBS_cut",
                platform=Platform.YOUTUBE,
                cut_title="Teste Bloqueio",
                payload={"video_path": "video.mp4"}
            )
            self.assertFalse(res["success"])
            self.assertIn("Bloqueado", res["error"])

    def test_enqueue_allows_verified(self):
        db_path = os.path.join(self.temp_dir.name, "queue.db")
        q = PublishQueue(db_path=db_path)

        with patch("core.publishing.publish_queue.check_publishable", return_value={"ok": True, "motivo": ""}):
            res = q.enqueue(
                cut_folder="VFDBS_cut",
                platform=Platform.YOUTUBE,
                cut_title="Teste Liberado",
                payload={"video_path": "video.mp4"}
            )
            self.assertTrue(res["success"])

    def test_worker_fails_job_if_unverified_on_dispatch(self):
        db_path = os.path.join(self.temp_dir.name, "queue_worker.db")
        q = PublishQueue(db_path=db_path)

        # Enfileira inicialmente liberado
        with patch("core.publishing.publish_queue.check_publishable", return_value={"ok": True, "motivo": ""}):
            res = q.enqueue(
                cut_folder="VFDBS_cut_worker",
                platform=Platform.YOUTUBE,
                cut_title="Job Worker",
                payload={"video_path": "video.mp4"}
            )
        job_id = res["job_id"]

        mock_publisher = MagicMock(spec=BasePublisher)
        PlatformRegistry.register(Platform.YOUTUBE, lambda p: mock_publisher)

        worker = PublishWorker(queue=q, poll_interval_sec=0.1)
        pending = q.get_pending_jobs(limit=1)

        # No momento do disparo pelo worker, a licença está 'não verificado'
        with patch("core.publishing.worker.check_publishable", return_value={"ok": False, "motivo": "Bloqueado: não verificado"}):
            worker._process_single_job(pending[0])

        # Não deve chamar publisher.publish
        mock_publisher.publish.assert_not_called()

        # Job deve ser marcado como FAILED definitivo
        job = q.get_job(job_id)
        self.assertEqual(job["status"], JobStatus.FAILED.value)
        self.assertIn("Bloqueado: fonte/licença não verificada", job["error_message"])

    @patch("requests.post")
    def test_send_to_webhook_blocks_unverified(self, mock_post):
        with patch("core.integrations.check_publishable", return_value={"ok": False, "motivo": "Bloqueado: sem licenca"}):
            res = send_to_webhook(
                webhook_url="https://example.com/wh",
                payload={"video_path": "corte.mp4", "event": "cut_ready"}
            )
            self.assertFalse(res["success"])
            self.assertIn("Bloqueado", res["error"])
            mock_post.assert_not_called()

    def test_upload_to_youtube_shorts_blocks_unverified(self):
        with patch("core.integrations.check_publishable", return_value={"ok": False, "motivo": "Bloqueado: sem licenca"}):
            res = upload_to_youtube_shorts(
                video_path="corte.mp4",
                title="Shorts Bloqueado",
                description="Desc"
            )
            self.assertFalse(res["success"])
            self.assertIn("Bloqueado", res["error"])


if __name__ == "__main__":
    unittest.main()
