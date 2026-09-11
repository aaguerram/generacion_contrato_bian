"""Puerto driven: recuperación semántica (RAG) sobre el catálogo."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.modelos import CandidatoSD


class RecuperadorSemanticoPort(ABC):
    @abstractmethod
    def recuperar(self, consulta: str, k: int) -> list[CandidatoSD]:
        """Top-k Service Domains más parecidos a la consulta, ordenados por similitud desc."""
