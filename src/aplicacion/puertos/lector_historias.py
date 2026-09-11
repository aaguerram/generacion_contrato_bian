"""Puerto driven: lee las Historias de Usuario y la funcionalidad macro de la entrada."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import FuncionalidadMacro, HistoriaUsuario


class LectorHistoriasPort(ABC):
    @abstractmethod
    def leer_historias(self, directorio: str) -> list[HistoriaUsuario]:
        """Todas las Historias de Usuario del `directorio`, ordenadas por nombre de archivo."""

    @abstractmethod
    def leer_funcionalidad(self, ruta: str) -> FuncionalidadMacro:
        """La funcionalidad macro + detalle desde un archivo JSON."""
