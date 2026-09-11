"""Regla de dominio: clasifica el resultado del RAG en bandas por similitud léxica.

La banda determina QUIÉN decide:
    alta  -> coincide (determinista, sin LLM)
    baja  -> no coincide (determinista, sin LLM)
    gris  -> lo adjudica el LLM

Así el LLM solo interviene en la franja ambigua y el resto es 100% reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.dominio.modelos import CandidatoSD

Banda = Literal["alta", "gris", "baja"]


@dataclass(frozen=True)
class Umbrales:
    alto: float = 0.90  # similitud_nombre >= alto  -> "alta"
    bajo: float = 0.60  # similitud_nombre <  bajo  -> "baja"

    def __post_init__(self) -> None:
        if not (0.0 <= self.bajo <= self.alto <= 1.0):
            raise ValueError(f"Umbrales inválidos: bajo={self.bajo}, alto={self.alto}")


def mejor_candidato(candidatos: list[CandidatoSD]) -> CandidatoSD | None:
    """El candidato con mayor similitud léxica estricta (no el mejor de recuperación)."""
    return max(candidatos, key=lambda c: c.similitud_nombre) if candidatos else None


def clasificar(candidatos: list[CandidatoSD], umbrales: Umbrales) -> Banda:
    mejor = mejor_candidato(candidatos)
    if mejor is None:
        return "baja"
    if mejor.similitud_nombre >= umbrales.alto:
        return "alta"
    if mejor.similitud_nombre < umbrales.bajo:
        return "baja"
    return "gris"
