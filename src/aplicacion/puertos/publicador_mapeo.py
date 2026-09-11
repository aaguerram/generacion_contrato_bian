"""Puerto driven: persiste el resultado del mapeo Historias -> Service Domains."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import ResultadoMapeoHistorias


class PublicadorMapeoPort(ABC):
    @abstractmethod
    def publicar(self, resultado: ResultadoMapeoHistorias, directorio: str) -> str:
        """Escribe el resultado en `directorio` y devuelve la ruta del archivo."""
