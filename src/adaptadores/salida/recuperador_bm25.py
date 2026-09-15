"""Adaptador RAG **disperso** (BM25 sobre el texto del Service Domain) — sin API de embeddings.

Complementa, no sustituye, a `RecuperadorLexico`:

- `RecuperadorLexico` (rapidfuzz) compara la consulta con el **nombre** del SD. Es el canal de
  `validar-sd`, donde la consulta ES un nombre y lo que se mide es "¿es el mismo nombre?".
- `RecuperadorBM25` indexa el **texto** del SD (`texto_para_indexar()`) y pesa términos por IDF.
  Es el canal para `mapear-historias`, donde la consulta es lenguaje natural.

El índice se construye una vez (341 documentos, milisegundos) y se reutiliza.
"""

from __future__ import annotations

import logging

from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.dominio.bm25 import IndiceBM25
from src.dominio.modelos import CandidatoSD

logger = logging.getLogger(__name__)


class RecuperadorBM25(RecuperadorSemanticoPort):
    def __init__(self, catalogo: CatalogoServiceDomainsPort) -> None:
        self._catalogo = catalogo
        self._indice: IndiceBM25 | None = None
        self._por_nombre: dict = {}

    def _asegurar(self) -> IndiceBM25:
        if self._indice is None:
            entradas = self._catalogo.cargar()
            self._por_nombre = {e.service_domain: e for e in entradas}
            self._indice = IndiceBM25(
                [(e.service_domain, e.texto_para_indexar()) for e in entradas]
            )
            logger.info("índice BM25 construido: %d Service Domains", len(self._indice))
        return self._indice

    def recuperar(self, consulta: str, k: int) -> list[CandidatoSD]:
        indice = self._asegurar()
        hits = indice.buscar(consulta, k)
        # BM25 no está acotado a [0,1]: se normaliza por el mejor de ESTA consulta, solo para que
        # `score` sea comparable dentro del ranking. La fusión usa posiciones, no este número.
        mejor = hits[0][1] if hits else 1.0
        return [
            CandidatoSD(
                service_domain=nombre,
                score=round(score / mejor, 4) if mejor else 0.0,
                similitud_nombre=0.0,  # BM25 no dice nada sobre el NOMBRE; ese es el canal léxico
                service_role=self._por_nombre[nombre].service_role,
                functional_pattern=self._por_nombre[nombre].functional_pattern,
            )
            for nombre, score in hits
        ]
