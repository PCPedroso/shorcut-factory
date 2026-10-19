"""
core/publishing — Esteira de Publicação Multiplataforma Nativa do ViralCut.
Suporta YouTube Shorts, Instagram Reels, TikTok, X e Kwai com fila persistente,
inspeção de mídia (preflight), adaptação de legendas e cofre seguro de credenciais.
"""

from .base import (
    Platform,
    JobStatus,
    AuthStatus,
    PreflightResult,
    AdaptedCaption,
    PublishResult,
    BasePublisher
)
from .credentials import CredentialVault
from .media_preflight import MediaPreflight
from .caption_adapter import CaptionAdapter
from .publish_queue import PublishQueue
from .worker import PublishWorker
from .platform_registry import PlatformRegistry
from .youtube import YouTubePublisher
from .instagram import InstagramPublisher
from .tiktok import TikTokPublisher
from .x_publisher import XPublisher
from .kwai import KwaiPublisher

__all__ = [
    "Platform",
    "JobStatus",
    "AuthStatus",
    "PreflightResult",
    "AdaptedCaption",
    "PublishResult",
    "BasePublisher",
    "CredentialVault",
    "MediaPreflight",
    "CaptionAdapter",
    "PublishQueue",
    "PublishWorker",
    "PlatformRegistry",
    "YouTubePublisher",
    "InstagramPublisher",
    "TikTokPublisher",
    "XPublisher",
    "KwaiPublisher",
]
