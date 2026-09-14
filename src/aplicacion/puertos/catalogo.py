"""Puerto driven: acceso al catálogo de Service Domains (BIAN Service Landscape)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.modelos import EntradaCatalogo


class CatalogoServiceDomainsPort(ABC):
    @abstractmethod
    def cargar(self) -> list[EntradaCatalogo]:
        """Todas las entradas del catálogo."""

    @abstractmethod
    def buscar_exacto(self, nombre: str) -> EntradaCatalogo | None:
        """Coincidencia exacta tras normalizar (case/espacios/PascalCase). None si no existe."""
