"""Estado del grafo de LangGraph."""

from __future__ import annotations

from typing import TypedDict

from src.dominio.modelos import CandidatoSD


class EstadoGrafo(TypedDict, total=False):
    # entrada
    service_domain: str
    directorio: str
    # trabajo
    existe: bool
    service_domain_canonico: str | None
    confianza: float
    razonamiento: str
    metodo: str
    candidatos: list[CandidatoSD]
    banda: str  # "alta" | "gris" | "baja"
    # salida
    ruta_resultado: str
