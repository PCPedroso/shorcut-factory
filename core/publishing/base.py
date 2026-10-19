"""
core/publishing/base.py — Interfaces, Enums e Tipos Básicos da Esteira de Publicação.
Define a classe abstrata BasePublisher e estruturas padronizadas para validação de mídia,
textos adaptados, credenciais e fila de postagem.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import datetime


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    KWAI = "kwai"

    @property
    def display_name(self) -> str:
        names = {
            Platform.YOUTUBE: "YouTube Shorts",
            Platform.INSTAGRAM: "Instagram Reels",
            Platform.TIKTOK: "TikTok",
            Platform.X: "X (Twitter)",
            Platform.KWAI: "Kwai",
        }
        return names.get(self, self.value.title())

    @property
    def icon(self) -> str:
        icons = {
            Platform.YOUTUBE: "🔴",
            Platform.INSTAGRAM: "📸",
            Platform.TIKTOK: "🎵",
            Platform.X: "✖️",
            Platform.KWAI: "🟠",
        }
        return icons.get(self, "🌐")


class JobStatus(str, Enum):
    QUEUED = "queued"          # Na fila aguardando horário ou disponibilidade
    UPLOADING = "uploading"    # Upload de bytes em andamento
    PROCESSING = "processing"  # Plataforma processando o vídeo
    PUBLISHED = "published"    # Publicado com sucesso
    FAILED = "failed"          # Falhou após esgotar tentativas
    NEEDS_ACTION = "needs_action"  # Requer intervenção manual (ex: reautenticação, Kwai assistido)
    CANCELLED = "cancelled"    # Cancelado pelo usuário


@dataclass
class AuthStatus:
    is_authenticated: bool
    platform: Platform
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    expires_at: Optional[datetime.datetime] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreflightResult:
    is_valid: bool
    platform: Platform
    video_path: str
    duration_sec: float = 0.0
    width: int = 0
    height: int = 0
    file_size_bytes: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    fps: float = 0.0
    has_faststart: bool = True
    needs_transcode: bool = False
    reasons: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)


@dataclass
class AdaptedCaption:
    platform: Platform
    title: str = ""
    description: str = ""
    hashtags: List[str] = field(default_factory=list)
    tags_seo: List[str] = field(default_factory=list)
    full_text: str = ""
    character_count: int = 0
    max_characters: int = 0
    is_within_limits: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class PublishResult:
    success: bool
    platform: Platform
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    error: Optional[str] = None
    requires_manual_step: bool = False
    manual_instructions: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


class BasePublisher:
    """
    Interface abstrata que todo publicador de rede social deve implementar.
    Garante uniformidade de autenticação, pré-validação e disparo.
    """

    def __init__(self, platform: Platform):
        self.platform = platform

    def get_auth_status(self) -> AuthStatus:
        """Verifica o status atual de conexão e validade das credenciais."""
        raise NotImplementedError

    def validate_preflight(self, video_path: str) -> PreflightResult:
        """Valida se o arquivo de vídeo atende às especificações técnicas da plataforma."""
        raise NotImplementedError

    def adapt_caption(
        self,
        title: str,
        description: str,
        hashtags: List[str],
        tags_seo: str = "",
        orig_video_info: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AdaptedCaption:
        """Adapta título, legenda, tags e créditos às restrições da plataforma."""
        raise NotImplementedError

    def publish(
        self,
        video_path: str,
        caption_data: AdaptedCaption,
        thumbnail_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> PublishResult:
        """Realiza o upload ou despacho do corte para a plataforma."""
        raise NotImplementedError
