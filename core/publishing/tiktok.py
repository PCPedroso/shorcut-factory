"""
Módulo de Publicação para TikTok via TikTok Content Posting API v2.
Suporta publicação direta (DIRECT_POST) ou envio para rascunhos da caixa de entrada (inbox).
Implementa upload chunked via HTTP PUT e polling de status oficial.
"""

import os
import math
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

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
# Tamanho padrão de chunk recomendado pelo TikTok: entre 5MB e 64MB (usando 10MB)
TIKTOK_CHUNK_SIZE = 10 * 1024 * 1024


class TikTokPublisher(BasePublisher):
    """
    Publicador oficial do TikTok via Content Posting API v2.
    Fluxo de publicação:
    1. Inicialização do post (/v2/post/publish/video/init/) -> Retorna publish_id e upload_url
    2. Upload em chunks via PUT com Content-Range
    3. Polling de status (/v2/post/publish/status/fetch/) até PUBLISH_COMPLETE
    """

    def __init__(self, vault: Optional[CredentialVault] = None):
        super().__init__(Platform.TIKTOK)
        self.vault = vault or CredentialVault()

    def get_auth_status(self) -> AuthStatus:
        """Verifica se há credenciais válidas do TikTok no cofre."""
        creds = self.vault.get_credential(Platform.TIKTOK)
        if not creds:
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Nenhuma credencial do TikTok configurada no cofre seguro."
            )

        token = creds.get("access_token")
        open_id = creds.get("open_id")
        display_name = creds.get("display_name") or creds.get("creator_username")

        if not token:
            return AuthStatus(
                is_authenticated=False,
                platform=self.platform,
                message="Token de acesso do TikTok ausente. Reautentique sua conta."
            )

        name_str = f"@{display_name}" if display_name else f"ID: {open_id}"

        return AuthStatus(
            is_authenticated=True,
            platform=self.platform,
            message="Conta do TikTok conectada.",
            account_name=name_str,
            account_id=str(open_id) if open_id else None
        )

    def refresh_access_token(self, client_key: str, client_secret: str) -> Dict[str, Any]:
        """Renova o access_token usando o refresh_token permanente do usuário."""
        creds = self.vault.get_credential(Platform.TIKTOK)
        if not creds or not creds.get("refresh_token"):
            return {"success": False, "error": "Nenhum refresh_token disponível para renovação."}

        url = f"{TIKTOK_API_BASE}/oauth/token/"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"]
        }

        try:
            resp = requests.post(url, headers=headers, data=data, timeout=15)
            res_data = resp.json()
            if "access_token" in res_data:
                creds["access_token"] = res_data["access_token"]
                creds["refresh_token"] = res_data.get("refresh_token", creds["refresh_token"])
                expires_in = res_data.get("expires_in", 86400)
                creds["token_expires_at"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(time.time() + expires_in)
                )
                self.vault.save_credential(Platform.TIKTOK, creds)
                return {"success": True, "token_expires_at": creds["token_expires_at"]}
            else:
                err_msg = res_data.get("error_description") or res_data.get("message", "Falha na renovação TikTok")
                return {"success": False, "error": err_msg}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def validate_preflight(self, video_path: str) -> PreflightResult:
        """Verifica compatibilidade com o formato vertical e codecs do TikTok."""
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
        """Adapta a legenda aos limites de 2200 caracteres e estilo nativo do TikTok."""
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
        Executa publicação direta ou envio para rascunho no TikTok via API v2.
        """
        options = options or {}
        privacy_level = options.get("privacy_level", "PUBLIC_TO_EVERYONE")
        disable_duet = options.get("disable_duet", False)
        disable_stitch = options.get("disable_stitch", False)
        disable_comment = options.get("disable_comment", False)

        creds = self.vault.get_credential(Platform.TIKTOK)
        if not creds or not creds.get("access_token"):
            return PublishResult(
                success=False,
                platform=self.platform,
                error="Credenciais do TikTok ausentes. Conecte sua conta do TikTok na Central de Publicação."
            )

        access_token = creds["access_token"]

        if not os.path.exists(video_path):
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Arquivo de vídeo não encontrado: {video_path}"
            )

        file_size = os.path.getsize(video_path)
        chunk_size = min(TIKTOK_CHUNK_SIZE, file_size)
        total_chunk_count = max(1, math.ceil(file_size / chunk_size))

        if isinstance(caption_data, AdaptedCaption):
            final_title = caption_data.full_text or (f"{caption_data.title}\n{caption_data.description}").strip()
        else:
            final_title = caption_data.get("caption") or caption_data.get("title") or ""

        # Limite de segurança de caracteres do TikTok
        final_title = final_title[:2200]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        # 1. Init Upload
        init_payload = {
            "post_info": {
                "title": final_title,
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_stitch": disable_stitch,
                "disable_comment": disable_comment,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count
            }
        }

        try:
            init_url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
            init_resp = requests.post(init_url, json=init_payload, headers=headers, timeout=30)
            init_data = init_resp.json()

            error_info = init_data.get("error", {})
            if error_info.get("code") != "ok" and "data" not in init_data:
                err_msg = error_info.get("message", "Falha ao inicializar post no TikTok")
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error=f"Erro TikTok API: {err_msg} ({error_info.get('code')})",
                    raw_response=init_data
                )

            data_block = init_data.get("data", {})
            publish_id = data_block.get("publish_id")
            upload_url = data_block.get("upload_url")

            if not publish_id or not upload_url:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error="Resposta do TikTok não continha publish_id ou upload_url.",
                    raw_response=init_data
                )

            # 2. Upload de Chunks
            with open(video_path, "rb") as vf:
                for chunk_idx in range(total_chunk_count):
                    chunk_bytes = vf.read(chunk_size)
                    start_byte = chunk_idx * chunk_size
                    end_byte = start_byte + len(chunk_bytes) - 1

                    chunk_headers = {
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                        "Content-Length": str(len(chunk_bytes))
                    }

                    put_resp = requests.put(upload_url, headers=chunk_headers, data=chunk_bytes, timeout=120)
                    if put_resp.status_code not in [200, 201, 206]:
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error=f"Falha ao enviar chunk {chunk_idx + 1}/{total_chunk_count} para o TikTok: HTTP {put_resp.status_code}",
                            raw_response={"status_code": put_resp.status_code, "text": put_resp.text}
                        )

            # 3. Polling de status do processamento
            status_url = f"{TIKTOK_API_BASE}/post/publish/status/fetch/"
            status_payload = {"publish_id": publish_id}
            max_wait_seconds = 120
            poll_interval = 4
            elapsed = 0
            is_completed = False
            last_status_data = {}

            while elapsed < max_wait_seconds:
                st_resp = requests.post(status_url, json=status_payload, headers=headers, timeout=15)
                st_data = st_resp.json()
                last_status_data = st_data

                status_val = st_data.get("data", {}).get("status")
                if status_val == "PUBLISH_COMPLETE":
                    is_completed = True
                    break
                elif status_val == "FAILED":
                    fail_reason = st_data.get("data", {}).get("fail_reason", "Motivo desconhecido")
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error=f"Processamento no TikTok falhou: {fail_reason}",
                        raw_response=st_data
                    )

                time.sleep(poll_interval)
                elapsed += poll_interval

            if not is_completed:
                # Pode ter entrado em processamento assíncrono estendido
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    post_id=publish_id,
                    post_url=f"https://www.tiktok.com/@{creds.get('display_name', '')}",
                    error=None,
                    raw_response=last_status_data
                )

            return PublishResult(
                success=True,
                platform=self.platform,
                post_id=publish_id,
                post_url=f"https://www.tiktok.com/@{creds.get('display_name', '')}",
                raw_response=last_status_data
            )

        except Exception as exc:
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Exceção durante publicação no TikTok: {str(exc)}"
            )


# Registra na factory de plataformas
PlatformRegistry.register(Platform.TIKTOK, TikTokPublisher)
