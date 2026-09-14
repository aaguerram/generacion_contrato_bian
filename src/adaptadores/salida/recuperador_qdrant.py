"""Adaptador `RecuperadorSemanticoPort` sobre Qdrant (índice externo, opcional).

Cuándo usarlo: cuando el índice deba compartirse entre procesos o máquinas, o cuando crezca más
allá de lo que conviene reconstruir en memoria por corrida. Para el caso base —341 Service
Domains cargados en un `InMemoryVectorStore`— no hace falta: ver `docs/adr/0001-vector-store.md`.

El índice lo puebla `scripts/rebuild_index/rebuild.py`; este adaptador solo consulta. Si Qdrant no
responde o la colección no existe, **no rompe la corrida**: registra el motivo y devuelve vacío,
de modo que el pipeline siga con los recuperadores que sí estén disponibles (la misma degradación
que ya aplica `_recuperadores_hibridos` cuando no hay embeddings).

`qdrant-client` es una dependencia OPCIONAL y se importa perezosamente: quien no use este backend
no la necesita instalada.
"""

from __future__ import annotations

import logging

from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.dominio.modelos import CandidatoSD

logger = logging.getLogger(__name__)

COLECCION_POR_DEFECTO = "bian_service_domains"


class RecuperadorQdrant(RecuperadorSemanticoPort):
    def __init__(
        self,
        embeddings,
        *,
        url: str = "http://localhost:6333",
        coleccion: str = COLECCION_POR_DEFECTO,
        timeout: float = 5.0,
    ) -> None:
        self._embeddings = embeddings
        self._url = url
        self._coleccion = coleccion
        self._timeout = timeout
        self._cliente = None
        self._fallido = False

    def _conectar(self):
        if self._cliente is not None or self._fallido:
            return self._cliente
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            logger.warning(
                "qdrant-client no está instalado; recuperador Qdrant inactivo "
                "(pip install qdrant-client)"
            )
            self._fallido = True
            return None
        try:
            cliente = QdrantClient(url=self._url, timeout=self._timeout)
            if not cliente.collection_exists(self._coleccion):
                logger.warning(
                    "Qdrant en %s no tiene la colección '%s'; poblarla con "
                    "scripts/rebuild_index/rebuild.py --backend qdrant",
                    self._url,
                    self._coleccion,
                )
                self._fallido = True
                return None
            self._cliente = cliente
        except Exception as exc:
            logger.warning("Qdrant no disponible en %s (%s); recuperador inactivo", self._url, exc)
            self._fallido = True
        return self._cliente

    def recuperar(self, consulta: str, k: int) -> list[CandidatoSD]:
        cliente = self._conectar()
        if cliente is None:
            return []
        try:
            vector = self._embeddings.embed_query(consulta)
            hits = cliente.query_points(
                collection_name=self._coleccion, query=vector, limit=k, with_payload=True
            ).points
        except Exception as exc:
            logger.warning("Consulta a Qdrant falló (%s); se sigue sin este recuperador", exc)
            return []

        from src.adaptadores.salida.recuperador_lexico import similitud_nombre

        candidatos = []
        for h in hits:
            payload = h.payload or {}
            nombre = payload.get("service_domain", "")
            if not nombre:
                continue
            candidatos.append(
                CandidatoSD(
                    service_domain=nombre,
                    score=round(float(h.score), 4),
                    similitud_nombre=round(similitud_nombre(consulta, nombre), 4),
                    service_role=payload.get("service_role"),
                    functional_pattern=payload.get("functional_pattern"),
                )
            )
        logger.info("Qdrant top-%d: %s", k, ", ".join(c.service_domain for c in candidatos))
        return candidatos
