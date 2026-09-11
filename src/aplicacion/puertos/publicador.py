"""Puerto driven: persistencia del resultado en el directorio del run."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.modelos import ResultadoValidacion


class PublicadorResultadoPort(ABC):
    @abstractmethod
    def publicar(self, resultado: ResultadoValidacion, directorio: str) -> str:
        """Escribe el resultado en `directorio` y devuelve la ruta del archivo."""
