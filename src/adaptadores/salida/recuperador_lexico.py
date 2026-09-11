"""Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings.

Dos scores por candidato:
  - `score` (WRatio): permisivo, ordena el shortlist (mete el candidato correcto aunque
    la consulta esté incompleta).
  - `similitud_nombre` (token_sort_ratio): estricto, "¿es este el mismo nombre?" — penaliza
    palabras que faltan. Es el que usa la regla de umbrales.
"""

from __future__ import annotations

import logging

from rapidfuzz import fuzz, process, utils

from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.dominio.modelos import CandidatoSD

logger = logging.getLogger(__name__)


def similitud_nombre(consulta: str, nombre: str) -> float:
    """Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que faltan no)."""
    return fuzz.token_sort_ratio(consulta, nombre, processor=utils.default_process) / 100.0


class RecuperadorLexico(RecuperadorSemanticoPort):
    def __init__(self, catalogo: CatalogoServiceDomainsPort) -> None:
        self._catalogo = catalogo

    def recuperar(self, consulta: str, k: int) -> list[CandidatoSD]:
        entradas = self._catalogo.cargar()
        nombres = [e.service_domain for e in entradas]
        por_nombre = {e.service_domain: e for e in entradas}

        hits = process.extract(
            consulta, nombres, scorer=fuzz.WRatio, processor=utils.default_process, limit=k
        )
        candidatos = [
            CandidatoSD(
                service_domain=nombre,
                score=round(score / 100.0, 4),
                similitud_nombre=round(similitud_nombre(consulta, nombre), 4),
                service_role=por_nombre[nombre].service_role,
                functional_pattern=por_nombre[nombre].functional_pattern,
            )
            for nombre, score, _ in hits
        ]
        logger.info(
            "RAG léxico top-%d: %s",
            k,
            ", ".join(f"{c.service_domain} (rec {c.score:.2f} / nom {c.similitud_nombre:.2f})" for c in candidatos),
        )
        return candidatos
