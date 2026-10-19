"""
Módulo de Publicação para Instagram Reels via Meta Graph API v20.0.
Suporta contas Creator e Business vinculadas a uma Página do Facebook.
Implementa o fluxo oficial de Resumable Upload (rupload.facebook.com) e Container Polling.
"""

import os
import time
import requests
from typing import Optional, Dict, Any, List

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

GRAPH_API_VERSION = "v20.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramPublisher(BasePublisher):
    """
    Publicador oficial do Instagram Reels via Meta Graph API.
    Fluxo de publicação:
    1. Criação do container de mídia resumable (POST /{ig_user_id}/media?media_type=REELS&upload_type=resumable)
    2. Upload binário para o endpoint de upload retornado (rupload.facebook.com)
    3. Polling de status do container até status_code == 'FINISHED'
    4. Publicação final (POST /{ig_user_id}/media_publish?creation_id={container_id})
    """

    def __init__(self, vault: Optional[CredentialVault] = None):
        super().__init__(Platform.INSTAGRAM)
        self.vault = vault or CredentialVault()

    def get_auth_status(self) -> AuthStatus:
        """Verifica se o access_token e ig_user_id estão configurados no cofre."""
        creds = self.vault.get_credential(Platform.INSTAGRAM)
        if not creds:
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Nenhuma credencial do Instagram configurada no cofre seguro."
            )

        token = creds.get("access_token")
        ig_user_id = creds.get("ig_user_id")

        if not token or not ig_user_id:
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Credenciais incompletas: informe Access Token e ID da Conta do Instagram."
            )

        # Opcional: testar token via Graph API me?fields=id,name se houver conexão
        username = creds.get("username")
        details = f"Conectado como @{username}" if username else f"ID: {ig_user_id}"

        return AuthStatus(
            is_authenticated=True,
            platform=self.platform,
            message="Instagram Creator/Business conectado.",
            account_name=details,
            account_id=str(ig_user_id)
        )

    def refresh_long_lived_token(self, client_id: str, client_secret: str) -> Dict[str, Any]:
        """
        Renova um short-lived ou long-lived token para mais 60 dias de validade.
        """
        creds = self.vault.get_credential(Platform.INSTAGRAM)
        if not creds or not creds.get("access_token"):
            return {"success": False, "error": "Nenhum token existente para renovar."}

        current_token = creds["access_token"]
        url = f"{GRAPH_API_BASE}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": current_token
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if "access_token" in data:
                new_token = data["access_token"]
                expires_in = data.get("expires_in", 5184000)  # default 60 dias
                expires_at = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + expires_in)
                )
                creds["access_token"] = new_token
                creds["token_expires_at"] = expires_at
                self.vault.save_credential(Platform.INSTAGRAM, creds)
                return {"success": True, "token_expires_at": expires_at}
            else:
                return {"success": False, "error": data.get("error", {}).get("message", "Falha na renovação")}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def validate_preflight(self, video_path: str) -> PreflightResult:
        """Valida codec, aspect ratio 9:16 e limites técnicos do Instagram Reels."""
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
        """Adapta título, descrição e hashtags para os limites do Instagram (2200 chars, 30 hashtags)."""
        return CaptionAdapter.adapt(
            platform=self.platform,
            title=title,
            description=description,
            hashtags=hashtags,
            tags_seo=tags_seo,
            orig_video_info=orig_video_info,
            options=options
        )

    def publish(
        self,
        video_path: str,
        caption_data: AdaptedCaption | Dict[str, Any],
        thumbnail_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> PublishResult:
        """
        Publica um vídeo no Instagram Reels usando a Graph API oficial com Resumable Upload.
        """
        options = options or {}
        creds = self.vault.get_credential(Platform.INSTAGRAM)
        if not creds or not creds.get("access_token") or not creds.get("ig_user_id"):
            return PublishResult(
                success=False,
                platform=self.platform,
                error="Credenciais do Instagram não configuradas. Configure seu Access Token e IG User ID."
            )

        access_token = creds["access_token"]
        ig_user_id = creds["ig_user_id"]

        if not os.path.exists(video_path):
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Arquivo de vídeo não encontrado: {video_path}"
            )

        # Prepara texto da legenda
        if isinstance(caption_data, AdaptedCaption):
            caption_text = caption_data.full_text or (f"{caption_data.title}\n\n{caption_data.description}").strip()
        else:
            caption_text = caption_data.get("caption") or caption_data.get("description") or ""

        file_size = os.path.getsize(video_path)

        try:
            # 1. Criação do container de mídia (Resumable)
            init_url = f"{GRAPH_API_BASE}/{ig_user_id}/media"
            init_params = {
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption_text,
                "access_token": access_token
            }
            if thumbnail_path and os.path.exists(thumbnail_path):
                # Se houver cover_url público ou opção de capa
                pass

            init_resp = requests.post(init_url, data=init_params, timeout=30)
            init_data = init_resp.json()

            if "id" not in init_data or "uri" not in init_data:
                err_msg = init_data.get("error", {}).get("message", "Falha ao inicializar container de Reels")
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Erro Meta Graph API: {err_msg}",
                    raw_response=init_data
                )

            container_id = init_data["id"]
            upload_uri = init_data["uri"]

            # 2. Upload do binário para upload_uri com headers de offset
            with open(video_path, "rb") as vf:
                video_bytes = vf.read()

            upload_headers = {
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size)
            }
            upload_resp = requests.post(upload_uri, headers=upload_headers, data=video_bytes, timeout=120)
            upload_data = upload_resp.json()

            if not upload_resp.ok or upload_data.get("success") is False:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Falha no upload binário do vídeo para o Instagram: {upload_resp.text}",
                    raw_response=upload_data
                )

            # 3. Polling de status do container até FINISHED
            status_url = f"{GRAPH_API_BASE}/{container_id}"
            max_wait_seconds = 120
            poll_interval = 4
            elapsed = 0
            container_ready = False

            while elapsed < max_wait_seconds:
                status_resp = requests.get(
                    status_url,
                    params={"fields": "status_code,status", "access_token": access_token},
                    timeout=15
                )
                status_data = status_resp.json()
                status_code = status_data.get("status_code")

                if status_code == "FINISHED":
                    container_ready = True
                    break
                elif status_code in ["ERROR", "EXPIRED"]:
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error=f"Processamento do container falhou no Instagram: {status_data.get('status')}",
                        raw_response=status_data
                    )

                time.sleep(poll_interval)
                elapsed += poll_interval

            if not container_ready:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Timeout aguardando processamento do vídeo no Instagram ({max_wait_seconds}s excedidos)."
                )

            # 4. Publicação do container (media_publish)
            publish_url = f"{GRAPH_API_BASE}/{ig_user_id}/media_publish"
            publish_params = {
                "creation_id": container_id,
                "access_token": access_token
            }
            publish_resp = requests.post(publish_url, data=publish_params, timeout=30)
            publish_data = publish_resp.json()

            if "id" not in publish_data:
                err_msg = publish_data.get("error", {}).get("message", "Falha ao publicar container no feed/reels")
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Erro ao publicar no Instagram: {err_msg}",
                    raw_response=publish_data
                )

            published_media_id = publish_data["id"]

            # 5. Obtém permalink do Reels recém-publicado
            permalink = None
            try:
                media_info = requests.get(
                    f"{GRAPH_API_BASE}/{published_media_id}",
                    params={"fields": "permalink", "access_token": access_token},
                    timeout=10
                ).json()
                permalink = media_info.get("permalink")
            except Exception:
                pass

            final_url = permalink or f"https://www.instagram.com/p/{published_media_id}"

            return PublishResult(
                success=True,
                platform=self.platform,
                post_id=published_media_id,
                post_url=final_url,
                raw_response=publish_data
            )

        except Exception as exc:
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Exceção durante publicação no Instagram: {str(exc)}"
            )


# Registra o publicador na factory
PlatformRegistry.register(Platform.INSTAGRAM, InstagramPublisher)
