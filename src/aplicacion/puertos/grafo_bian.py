"""Puerto driven: expansión de candidatos por el grafo canónico BIAN."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.grafo_bian import CandidatoGrafo, ObjetoCompartido


class GrafoBianPort(ABC):
    @abstractmethod
    def expandir(self, service_domains: list[str], *, tope: int) -> list[CandidatoGrafo]:
        """Service Domains relacionados con los dados por relaciones VERIFICADAS del catálogo.

        Nunca por similitud temática: solo aristas que existen en el BOM o en la Semantic API, y
        cada candidato dice por qué nodo puente se llegó. Devuelve como mucho `tope`, ordenados
        por especificidad de la conexión.
        """

    def objetos_compartidos(self, service_domains: list[str]) -> list[ObjetoCompartido]:
        """Objetos del catálogo que tocan dos o más de esos Service Domains, con especificidad.

        Sirve para comprobar un `ownership_conflict` contra el catálogo en vez de creerle al
        revisor adversarial. No es abstracto a propósito: una implementación que solo sepa
        expandir sigue siendo válida y devuelve la lista vacía (= "no puedo confirmarlo"), que es
        lo mismo que hacía el pipeline antes de existir esta señal.
        """
        return []
