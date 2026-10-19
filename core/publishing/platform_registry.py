"""
core/publishing/platform_registry.py — Registro Dinâmico de Publicadores por Plataforma.
"""

from typing import Dict, Type, Optional, List
from .base import Platform, BasePublisher

_REGISTRY: Dict[Platform, BasePublisher] = {}
_PUBLISHER_CLASSES: Dict[Platform, Type[BasePublisher]] = {}


class PlatformRegistry:
    """Centraliza o registro e instanciação de implementações de cada rede social."""

    @classmethod
    def register(cls, platform: Platform, publisher_class: Type[BasePublisher]):
        """Registra a classe publicadora para uma plataforma."""
        _PUBLISHER_CLASSES[platform] = publisher_class

    @classmethod
    def get_publisher(cls, platform: Platform, vault: Optional[Any] = None) -> Optional[BasePublisher]:
        """Retorna ou instancia o publicador correspondente à plataforma."""
        if platform in _REGISTRY and vault is None:
            return _REGISTRY[platform]
        
        if platform in _PUBLISHER_CLASSES:
            factory = _PUBLISHER_CLASSES[platform]
            try:
                inst = factory(vault=vault)
            except TypeError:
                try:
                    inst = factory(vault)
                except TypeError:
                    inst = factory()

            if vault is None:
                _REGISTRY[platform] = inst
            return inst
        return None

    @classmethod
    def list_supported_platforms(cls) -> List[Platform]:
        """Lista plataformas que possuem publicador implementado e registrado."""
        return list(_PUBLISHER_CLASSES.keys())
