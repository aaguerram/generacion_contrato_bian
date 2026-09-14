"""Puerto driven: expansión de candidatos por el grafo canónico BIAN."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.grafo_bian import CandidatoGrafo


class GrafoBianPort(ABC):
    @abstractmethod
    def expandir(self, service_domains: list[str], *, tope: int) -> list[CandidatoGrafo]:
        """Service Domains relacionados con los dados por relaciones VERIFICADAS del catálogo.

        Nunca por similitud temática: solo aristas que existen en el BOM o en la Semantic API, y
        cada candidato dice por qué nodo puente se llegó. Devuelve como mucho `tope`, ordenados
        por especificidad de la conexión.
        """
