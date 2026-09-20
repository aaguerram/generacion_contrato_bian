"""Canal disperso del paso 1: BM25 sobre el documento de cada clase con dueño. Sin API.

Lee `ConsultaClases.terminos` -la HU ya traducida al vocabulario del BOM- porque el corpus está
entero en inglés (`Contact Point`, `Electronic Address`); con el texto en español no compartiría
ni un término. El índice (~1.2k documentos) se construye una vez por proceso.
"""

from __future__ import annotations

import logging

from src.aplicacion.puertos.catalogo_entidades import CatalogoEntidadesBianPort
from src.aplicacion.puertos.recuperador_clases import RecuperadorClasesPort
from src.dominio.bm25 import IndiceBM25
from src.dominio.entidades_bian import CandidatoClase, ConsultaClases, documentos_indexables

logger = logging.getLogger(__name__)


class RecuperadorClasesBM25(RecuperadorClasesPort):
    def __init__(self, catalogo: CatalogoEntidadesBianPort) -> None:
        self._catalogo = catalogo
        self._indice: IndiceBM25 | None = None

    @property
    def nombre(self) -> str:
        return "bm25"

    def _asegurar(self) -> IndiceBM25:
        if self._indice is None:
            docs = documentos_indexables(
                self._catalogo.clases(), nombres_enum=self._catalogo.nombres_enum()
            )
            self._indice = IndiceBM25(docs)
            logger.info("índice BM25 de clases BOM construido: %d clases con dueño", len(docs))
        return self._indice

    def recuperar(self, consulta: ConsultaClases, k: int) -> list[CandidatoClase]:
        if not consulta.terminos:
            return []
        hits = self._asegurar().buscar(consulta.terminos_texto, k)
        mejor = hits[0][1] if hits else 1.0
        return [
            CandidatoClase(clase=nombre, score=round(score / mejor, 4) if mejor else 0.0)
            for nombre, score in hits
        ]
