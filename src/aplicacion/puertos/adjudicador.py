"""Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.modelos import CandidatoSD, VeredictoLLM


class AdjudicadorLLMPort(ABC):
    @abstractmethod
    def adjudicar(self, consulta: str, candidatos: list[CandidatoSD]) -> VeredictoLLM:
        """Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`."""
