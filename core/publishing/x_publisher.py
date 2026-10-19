"""
Módulo de Publicação para a plataforma X (antigo Twitter) via X API v1.1 / v2.
Implementa o protocolo de 4 estágios de chunked upload (INIT, APPEND, FINALIZE, STATUS)
e criação de Tweets com vídeo anexado via API v2 endpoints.
"""

import os
import math
import time
import requests
from typing import Optional, Dict, Any, List
from requests_oauthlib import OAuth1

from core.publishing.base import (
    BasePublisher,
    Platform,
    AuthStatus,
    PreflightResult,
    AdaptedCaption,
    PublishResult
)
from core.publishing.credentials import CredentialVault
from core.publishing.media_preflight import MediaPreflight
from core.publishing.caption_adapter import CaptionAdapter
from core.publishing.platform_registry import PlatformRegistry

UPLOAD_ENDPOINT = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_ENDPOINT = "https://api.twitter.com/2/tweets"
# Chunks de upload para o X (max 5MB por chunk)
X_CHUNK_SIZE = 4 * 1024 * 1024


class XPublisher(BasePublisher):
    """
    Publicador oficial para X / Twitter.
    Suporta autenticação OAuth 1.0a (User Context) ou OAuth 2.0 Bearer Token.
    Fluxo de upload de vídeo:
    1. INIT -> Inicializa sessão de upload de vídeo
    2. APPEND -> Envia segmentos do arquivo em blocos de até 4MB
    3. FINALIZE -> Finaliza o upload e recebe processing_info
    4. STATUS -> Faz polling até que o processamento do vídeo seja 'succeeded'
    5. POST /2/tweets -> Publica o tweet com media_ids
    """

    def __init__(self, vault: Optional[CredentialVault] = None):
        super().__init__(Platform.X)
        self.vault = vault or CredentialVault()

    def get_auth_status(self) -> AuthStatus:
        """Verifica se há credenciais válidas do X no cofre seguro."""
        creds = self.vault.get_credential(Platform.X)
        if not creds:
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Nenhuma credencial do X (Twitter) configurada no cofre seguro."
            )

        # Suporte a Modo Assistido (Gratuito / Sem API Paga)
        if creds.get("mode") == "assisted":
            return AuthStatus(
                is_authenticated=True,
                platform=self.platform,
                message="Modo Manual Assistido ativo (sem custos de API).",
                account_name="X / Twitter (Exportação Manual)"
            )

        screen_name = creds.get("screen_name") or creds.get("username")

        # Verifica OAuth 1.0a
        has_oauth1 = (
            creds.get("api_key")
            and creds.get("api_secret")
            and creds.get("access_token")
            and creds.get("access_token_secret")
        )

        # Verifica OAuth 2.0 Bearer
        has_bearer = bool(creds.get("bearer_token"))

        if not has_oauth1 and not has_bearer:
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Credenciais do X incompletas. Forneça chaves OAuth 1.0a ou Bearer Token."
            )

        name_str = f"@{screen_name}" if screen_name else "Conta do X conectada"

        return AuthStatus(
            is_authenticated=True,
            platform=self.platform,
            message="X (Twitter) conectado com sucesso.",
            account_name=name_str
        )

    def _get_auth(self, creds: Dict[str, Any]):
        """Retorna autenticador OAuth1 ou headers Bearer."""
        if (
            creds.get("api_key")
            and creds.get("api_secret")
            and creds.get("access_token")
            and creds.get("access_token_secret")
        ):
            return OAuth1(
                creds["api_key"],
                creds["api_secret"],
                creds["access_token"],
                creds["access_token_secret"]
            )
        return None

    def validate_preflight(self, video_path: str) -> PreflightResult:
        """Verifica compatibilidade com os limites técnicos do X (140s, 512MB)."""
        return MediaPreflight.validate_for_platform(video_path, self.platform)

    def adapt_caption(
        self,
        title: str,
        description: str,
        hashtags: List[str],
        tags_seo: str = "",
        orig_video_info: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AdaptedCaption:
        """Adapta o texto para o limite estrito de 280 caracteres do X."""
        return CaptionAdapter.adapt(
            platform=self.platform,
            title=title,
            description=description,
            hashtags=hashtags,
            tags_seo=tags_seo,
            orig_video_info=orig_video_info,
            options=options
        )

    def _copy_to_windows_clipboard(self, text: str) -> bool:
        """Copia texto diretamente para a área de transferência do Windows via utilitário clip."""
        import subprocess
        try:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.encode("utf-16le"))
            return p.returncode == 0
        except Exception:
            return False

    def _reveal_in_windows_explorer(self, file_path: str):
        """Abre o Windows Explorer com o arquivo de vídeo selecionado."""
        import subprocess
        norm_path = os.path.normpath(file_path)
        try:
            subprocess.Popen(f'explorer /select,"{norm_path}"')
        except Exception:
            pass

    def publish(
        self,
        video_path: str,
        caption_data: AdaptedCaption | Dict[str, Any],
        thumbnail_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> PublishResult:
        """
        Executa upload de vídeo em 4 fases e publica o tweet no X.
        Suporta modo manual assistido (gratuito) caso o usuário não possua chaves pagas de API.
        """
        options = options or {}
        creds = self.vault.get_credential(Platform.X)

        # Trata modo assistido manual gratuito
        if (creds and creds.get("mode") == "assisted") or options.get("assisted_mode"):
            if not os.path.exists(video_path):
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Arquivo de vídeo não encontrado: {video_path}"
                )

            if isinstance(caption_data, AdaptedCaption):
                tweet_text = caption_data.full_text or caption_data.title
            else:
                tweet_text = caption_data.get("text") or caption_data.get("caption") or caption_data.get("title") or ""
            tweet_text = tweet_text[:280]

            self._copy_to_windows_clipboard(tweet_text)
            self._reveal_in_windows_explorer(video_path)
            if options.get("open_browser", True):
                try:
                    import webbrowser
                    webbrowser.open("https://x.com/compose/post")
                except Exception:
                    pass

            instructions = (
                "✅ Exportação Assistida para X (Twitter) concluída:\n"
                "1. O texto do Tweet foi copiado para sua Área de Transferência (Ctrl+V).\n"
                "2. O vídeo foi selecionado no Windows Explorer.\n"
                "3. O X (Twitter) foi aberto no navegador. Arraste o vídeo e cole o tweet."
            )
            return PublishResult(
                success=True,
                platform=self.platform,
                post_id=None,
                post_url="https://x.com/compose/post",
                requires_manual_step=True,
                manual_instructions=instructions
            )

        if not creds:
            return PublishResult(
                success=False,
                platform=self.platform,
                error="Credenciais do X não configuradas no cofre."
            )

        auth = self._get_auth(creds)
        bearer = creds.get("bearer_token")

        if not auth and not bearer:
            return PublishResult(
                success=False,
                platform=self.platform,
                error="Nenhum método de autenticação válido para o X (OAuth 1.0a ou Bearer Token)."
            )

        if not os.path.exists(video_path):
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Arquivo de vídeo não encontrado: {video_path}"
            )

        file_size = os.path.getsize(video_path)

        # Prepara texto do tweet (respeita 280 chars)
        if isinstance(caption_data, AdaptedCaption):
            tweet_text = caption_data.full_text or caption_data.title
        else:
            tweet_text = caption_data.get("text") or caption_data.get("caption") or caption_data.get("title") or ""

        tweet_text = tweet_text[:280]

        headers_bearer = {"Authorization": f"Bearer {bearer}"} if bearer else {}

        try:
            # 1. INIT
            init_data = {
                "command": "INIT",
                "total_bytes": str(file_size),
                "media_type": "video/mp4",
                "media_category": "tweet_video"
            }
            init_resp = requests.post(
                UPLOAD_ENDPOINT,
                data=init_data,
                auth=auth,
                headers=headers_bearer if not auth else None,
                timeout=30
            )
            init_json = init_resp.json()

            media_id = init_json.get("media_id_string")
            if not media_id:
                err_msg = init_json.get("error") or init_json.get("errors") or "Falha ao inicializar upload no X"
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Erro INIT no X: {err_msg}",
                    raw_response=init_json
                )

            # 2. APPEND (chunks)
            total_chunks = max(1, math.ceil(file_size / X_CHUNK_SIZE))
            with open(video_path, "rb") as vf:
                for seg_idx in range(total_chunks):
                    chunk_bytes = vf.read(X_CHUNK_SIZE)
                    append_data = {
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": str(seg_idx)
                    }
                    append_files = {"media": chunk_bytes}

                    app_resp = requests.post(
                        UPLOAD_ENDPOINT,
                        data=append_data,
                        files=append_files,
                        auth=auth,
                        headers=headers_bearer if not auth else None,
                        timeout=90
                    )
                    if app_resp.status_code not in [200, 204]:
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error=f"Falha ao enviar segmento {seg_idx} para o X: HTTP {app_resp.status_code}",
                            raw_response={"status_code": app_resp.status_code, "text": app_resp.text}
                        )

            # 3. FINALIZE
            finalize_data = {
                "command": "FINALIZE",
                "media_id": media_id
            }
            fin_resp = requests.post(
                UPLOAD_ENDPOINT,
                data=finalize_data,
                auth=auth,
                headers=headers_bearer if not auth else None,
                timeout=30
            )
            fin_json = fin_resp.json()

            # 4. STATUS (Polling assíncrono se necessário)
            processing_info = fin_json.get("processing_info")
            if processing_info:
                state = processing_info.get("state")
                check_after = processing_info.get("check_after_secs", 2)
                max_checks = 40
                checks = 0

                while state in ["pending", "in_progress"] and checks < max_checks:
                    time.sleep(check_after)
                    checks += 1

                    status_params = {"command": "STATUS", "media_id": media_id}
                    st_resp = requests.get(
                        UPLOAD_ENDPOINT,
                        params=status_params,
                        auth=auth,
                        headers=headers_bearer if not auth else None,
                        timeout=15
                    )
                    st_json = st_resp.json()
                    processing_info = st_json.get("processing_info", {})
                    state = processing_info.get("state")
                    check_after = processing_info.get("check_after_secs", 3)

                    if state == "failed":
                        err_detail = processing_info.get("error", {}).get("message", "Falha no encode do vídeo pelo X")
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error=f"X vídeo processamento falhou: {err_detail}",
                            raw_response=st_json
                        )

            # 5. Criar Tweet via API v2
            tweet_payload = {
                "text": tweet_text,
                "media": {
                    "media_ids": [media_id]
                }
            }
            tweet_headers = {"Content-Type": "application/json"}
            if bearer:
                tweet_headers["Authorization"] = f"Bearer {bearer}"

            tw_resp = requests.post(
                TWEET_ENDPOINT,
                json=tweet_payload,
                auth=auth if not bearer else None,
                headers=tweet_headers,
                timeout=30
            )
            tw_json = tw_resp.json()

            if tw_resp.status_code not in [200, 201] or "data" not in tw_json:
                err_msg = tw_json.get("detail") or tw_json.get("title") or "Falha ao publicar tweet"
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Erro ao publicar no X: {err_msg}",
                    raw_response=tw_json
                )

            tweet_id = tw_json["data"]["id"]
            tweet_url = f"https://x.com/i/status/{tweet_id}"

            return PublishResult(
                success=True,
                platform=self.platform,
                post_id=tweet_id,
                post_url=tweet_url,
                raw_response=tw_json
            )

        except Exception as exc:
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Exceção durante publicação no X: {str(exc)}"
            )


# Registra o publicador na factory
PlatformRegistry.register(Platform.X, XPublisher)
