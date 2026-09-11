"""Patrón Strategy: un proveedor por estrategia. Cada estrategia da chat + embeddings."""

from .estrategia import ConfiguracionProveedor, ProveedorLLMStrategy
from .factory import crear_estrategia, estrategias_disponibles, registrar_estrategia

__all__ = [
    "ConfiguracionProveedor",
    "ProveedorLLMStrategy",
    "crear_estrategia",
    "estrategias_disponibles",
    "registrar_estrategia",
]
