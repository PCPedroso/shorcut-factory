"""
Módulo de Publicação Assistida para Kwai.
Como o Kwai não disponibiliza API pública aberta de publicação para criadores individuais,
este módulo implementa o fluxo de Exportação Assistida:
1. Validação de pré-voo do vídeo (9:16, MP4, limites de duração)
2. Adaptação da legenda com hashtags virais para o limite do Kwai
3. Cópia instantânea da legenda para a Área de Transferência do Windows
4. Abertura do Windows Explorer destacando o arquivo de vídeo pronto
5. Abertura opcional do Kwai Creator Web no navegador
"""

import os
import subprocess
import webbrowser
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

KWAI_CREATOR_URL = "https://creator.kwai.com/"


class KwaiPublisher(BasePublisher):
    """
    Publicador assistido para Kwai Creator.
    Elimina o risco de bloqueios por CAPTCHA/anti-bot de automações headless,
    oferecendo um pipeline guiado de alta produtividade para o operador.
    """

    def __init__(self, vault: Optional[CredentialVault] = None):
        super().__init__(Platform.KWAI)
        self.vault = vault or CredentialVault()

    def get_auth_status(self) -> AuthStatus:
        """Kwai opera em modo assistido local, sempre disponível."""
        return AuthStatus(
            is_authenticated=True,
            platform=self.platform,
            message="Modo Exportação Assistida ativo (não requer tokens de API).",
            account_name="Kwai Creator (Exportação Local)"
        )

    def validate_preflight(self, video_path: str) -> PreflightResult:
        """Valida se o vídeo cumpre as especificações verticais do Kwai."""
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
        """Adapta a legenda aos limites de 500 caracteres e estilo Kwai."""
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
        """Copia texto diretamente para a área de transferência do Windows via utilitário nativo clip."""
        try:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.encode("utf-16le"))
            return p.returncode == 0
        except Exception:
            return False

    def _reveal_in_windows_explorer(self, file_path: str):
        """Abre o Windows Explorer com o arquivo de vídeo selecionado."""
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
        Executa a exportação assistida do vídeo para Kwai:
        - Copia a legenda para o clipboard
        - Revela o arquivo no Windows Explorer
        - Abre a página de upload do Kwai Creator
        """
        options = options or {}
        open_browser = options.get("open_browser", True)

        if not os.path.exists(video_path):
            return PublishResult(
                success=False,
                platform=self.platform,
                error=f"Arquivo de vídeo não encontrado: {video_path}"
            )

        # Prepara texto da legenda
        if isinstance(caption_data, AdaptedCaption):
            final_caption = caption_data.full_text or (f"{caption_data.title}\n{caption_data.description}").strip()
        else:
            final_caption = caption_data.get("caption") or caption_data.get("title") or ""

        # 1. Copia legenda para a área de transferência do Windows
        clipboard_ok = self._copy_to_windows_clipboard(final_caption)

        # 2. Revela arquivo no Windows Explorer
        self._reveal_in_windows_explorer(video_path)

        # 3. Abre Kwai Creator Web no navegador se solicitado
        if open_browser:
            try:
                webbrowser.open(KWAI_CREATOR_URL)
            except Exception:
                pass

        instructions = (
            "✅ Exportação Assistida Kwai concluída:\n"
            "1. A legenda otimizada foi copiada para sua Área de Transferência (Ctrl+V).\n"
            "2. O vídeo foi selecionado no Windows Explorer.\n"
            "3. O Kwai Creator Web foi aberto no navegador. Arraste o vídeo e cole a legenda."
        )

        return PublishResult(
            success=True,
            platform=self.platform,
            post_id=None,
            post_url=KWAI_CREATOR_URL,
            requires_manual_step=True,
            manual_instructions=instructions,
            raw_response={"clipboard_copied": clipboard_ok, "video_path": video_path}
        )


# Registra na factory de plataformas
PlatformRegistry.register(Platform.KWAI, KwaiPublisher)
