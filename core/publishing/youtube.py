"""
core/publishing/youtube.py — Publicador Oficial para YouTube Shorts via YouTube Data API v3.
Inclui upload resumable em blocos (8 MB) com retentativas automáticas, suporte a agendamento
nativo (publishAt), tags SEO sem '#' e upload opcional de capa personalizada.
"""

import os
import time
import random
from typing import Dict, Any, Optional, List
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .base import (
    Platform,
    BasePublisher,
    AuthStatus,
    PreflightResult,
    AdaptedCaption,
    PublishResult
)
from .credentials import CredentialVault, LEGACY_YT_TOKEN
from .media_preflight import MediaPreflight
from .caption_adapter import CaptionAdapter
from .platform_registry import PlatformRegistry

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

CHUNK_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB por bloco


class YouTubePublisher(BasePublisher):
    """
    Publicador robusto para o YouTube Shorts utilizando a API oficial Data v3.
    """

    def __init__(self, platform: Platform = Platform.YOUTUBE, vault: Optional[CredentialVault] = None):
        super().__init__(platform)
        self.vault = vault or CredentialVault()

    def get_auth_status(self, client_secrets_path: Optional[str] = None) -> AuthStatus:
        """Verifica se há credenciais válidas e ativas para o YouTube."""
        creds = self._get_credentials(client_secrets_path=client_secrets_path)
        if creds and creds.valid:
            # Tenta obter o nome do canal se possível
            account_name = "Canal Conectado"
            try:
                youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
                res = youtube.channels().list(part="snippet", mine=True).execute()
                items = res.get("items", [])
                if items:
                    account_name = items[0].get("snippet", {}).get("title", account_name)
            except Exception:
                pass

            return AuthStatus(
                is_authenticated=True,
                platform=self.platform,
                account_name=account_name,
                message=f"Conectado ao canal '{account_name}'."
            )

        if client_secrets_path and os.path.exists(client_secrets_path):
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Client Secrets configurado. Clique em 'Conectar Conta Google'."
            )

        return AuthStatus(
            is_authenticated=False,
            platform=self.platform,
            message="Nenhuma credencial configurada. Baixe o client_secrets.json do Google Cloud."
        )

    def authenticate_oauth(self, client_secrets_path: str, port: int = 8080) -> Dict[str, Any]:
        """Inicia o fluxo OAuth local no navegador para autorizar acesso ao canal do YouTube."""
        if not os.path.exists(client_secrets_path):
            return {"success": False, "error": f"Arquivo client_secrets.json não encontrado: {client_secrets_path}"}

        try:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=port, prompt="consent")

            creds_data = json_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }

            # Salva no cofre seguro
            self.vault.save_credential(Platform.YOUTUBE, creds_data)

            # Mantém cópia legada para retrocompatibilidade
            try:
                os.makedirs(os.path.dirname(LEGACY_YT_TOKEN), exist_ok=True)
                with open(LEGACY_YT_TOKEN, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            except Exception:
                pass

            return {"success": True, "error": None}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _get_credentials(self, client_secrets_path: Optional[str] = None) -> Optional[Credentials]:
        """Carrega e renova credenciais a partir do cofre ou arquivos locais."""
        creds = None

        # 1. Tenta carregar do cofre seguro
        vault_data = self.vault.get_credential(Platform.YOUTUBE)
        if vault_data and "token" in vault_data:
            try:
                creds = Credentials.from_authorized_user_info(vault_data, YOUTUBE_SCOPES)
            except Exception:
                creds = None

        # 2. Fallback no arquivo legado youtube_token.json
        if not creds and os.path.exists(LEGACY_YT_TOKEN):
            try:
                creds = Credentials.from_authorized_user_file(LEGACY_YT_TOKEN, YOUTUBE_SCOPES)
            except Exception:
                creds = None

        # 3. Renovação automática se expirado
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                creds_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes
                }
                self.vault.save_credential(Platform.YOUTUBE, creds_data)
                with open(LEGACY_YT_TOKEN, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            except Exception:
                creds = None

        return creds

    def validate_preflight(self, video_path: str) -> PreflightResult:
        """Audita vídeo contra as especificações técnicas do YouTube Shorts."""
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
        """Adapta metadados para os limites do YouTube Shorts."""
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
        Executa upload seguro e em blocos com retries para o YouTube Shorts.
        """
        options = options or {}
        privacy_status = options.get("privacy_status", "unlisted")
        scheduled_at = options.get("scheduled_at")
        category_id = options.get("category_id", "22")
        client_secrets_path = options.get("client_secrets_path")

        if not os.path.exists(video_path):
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Arquivo de vídeo não encontrado: {video_path}"
            )

        creds = self._get_credentials(client_secrets_path=client_secrets_path)
        if not creds or not creds.valid:
            return PublishResult(
                success=False,
                platform=self.platform,
                error="Credenciais do YouTube inválidas ou expiradas. Conecte sua conta novamente na barra lateral."
            )

        # Trata formato de entrada (AdaptedCaption ou dict)
        if isinstance(caption_data, AdaptedCaption):
            final_title = caption_data.title
            final_desc = caption_data.description
            final_tags = caption_data.tags_seo or [h.lstrip("#") for h in caption_data.hashtags]
        else:
            final_title = caption_data.get("title", "Corte Viral #Shorts")
            final_desc = caption_data.get("description", "")
            final_tags = caption_data.get("tags") or caption_data.get("tags_seo") or ["Shorts", "ViralCut"]

        # Corpo do vídeo
        body: Dict[str, Any] = {
            "snippet": {
                "title": final_title,
                "description": final_desc,
                "tags": final_tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            }
        }

        # Agendamento nativo (exige privacyStatus='private')
        if scheduled_at:
            body["status"]["privacyStatus"] = "private"
            # Formata para ISO 8601 UTC se necessário
            body["status"]["publishAt"] = str(scheduled_at)

        try:
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            media = MediaFileUpload(video_path, chunksize=CHUNK_SIZE_BYTES, resumable=True, mimetype="video/mp4")
            insert_request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            # Upload com laço de retry resiliente
            response = None
            retries = 0
            max_retries = 5

            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                except Exception as exc:
                    retries += 1
                    if retries > max_retries:
                        raise exc
                    sleep_sec = (2 ** retries) + random.uniform(0.5, 1.5)
                    time.sleep(sleep_sec)

            video_id = response.get("id")
            video_url = f"https://youtube.com/shorts/{video_id}"

            # Upload de thumbnail opcional (se o canal tiver permissão de parceiro)
            if thumbnail_path and os.path.exists(thumbnail_path) and video_id:
                try:
                    thumb_media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
                    youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()
                except Exception:
                    # Falha de thumbnail é silenciosa pois requer canal verificado por telefone
                    pass

            return PublishResult(
                success=True,
                platform=self.platform,
                post_id=video_id,
                post_url=video_url,
                raw_response=response
            )

        except Exception as exc:
            err_str = str(exc)
            # Diagnóstico de projeto Google não verificado
            if "forbidden" in err_str.lower() or "quota" in err_str.lower():
                err_str += " (Verifique a cota diária ou se o projeto Google Cloud foi auditado para uploads públicos)."
            return PublishResult(
                success=False,
                platform=self.platform,
                error=err_str
            )
        finally:
            if 'media' in locals() and hasattr(media, '_fd') and media._fd:
                try:
                    media._fd.close()
                except Exception:
                    pass
            if 'thumb_media' in locals() and hasattr(thumb_media, '_fd') and thumb_media._fd:
                try:
                    thumb_media._fd.close()
                except Exception:
                    pass


# Registra automaticamente no PlatformRegistry
PlatformRegistry.register(Platform.YOUTUBE, YouTubePublisher)
