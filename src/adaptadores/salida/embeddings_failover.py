"""Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.

`routing.embedding_priority` (proveedores) × `providers.<n>.embedding.models` (modelos, el 1º es el
más preciso) definen una lista ordenada de candidatos. `resolver()` prueba cada uno con una
consulta mínima y se queda con el primero que responde (sin cuota agotada / disponible); a partir
de ahí delega, y si ese candidato cae en ejecución (429 / sin créditos / modelo retirado) baja al
siguiente que quede.

El modelo activo se fija ANTES de tocar la caché del índice vectorial (`RecuperadorVectorial` la
nombra por ese modelo), así una corrida que hace failover no carga un índice con otra dimensión.
"""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings

from src.adaptadores.salida.llm.failover import degradar_a_siguiente, es_transitorio

logger = logging.getLogger("generacion_contrato_ia_v2.embeddings.failover")


def _corto(exc: BaseException | None) -> str:
    if exc is None:
        return "-"
    s = " ".join(str(exc).split())
    return (s[:180] + "…") if len(s) > 180 else s

_SONDA = "banking service domain authorization"  # texto corto para verificar clave/modelo/cuota


class TodosLosEmbeddingsAgotados(RuntimeError):
    pass


class EmbeddingsConFailover(Embeddings):
    def __init__(self, candidatos: list[tuple[str, str, Embeddings]]) -> None:
        if not candidatos:
            raise ValueError("EmbeddingsConFailover necesita al menos un candidato.")
        self._candidatos = list(candidatos)
        self._activo: tuple[str, str, Embeddings] | None = None

    @property
    def descripcion(self) -> str:
        return " -> ".join(f"{p}:{m}" for p, m, _ in self._candidatos)

    @property
    def modelo(self) -> str:
        return self.resolver()[1]

    def resolver(self) -> tuple[str, str]:
        """Fija el candidato activo probándolos en orden. Idempotente."""
        if self._activo is not None:
            return self._activo[0], self._activo[1]
        ultimo: BaseException | None = None
        for i, (prov, modelo, emb) in enumerate(self._candidatos):
            try:
                emb.embed_query(_SONDA)
            except Exception as exc:  # noqa: BLE001
                ultimo = exc
                if degradar_a_siguiente(exc) or es_transitorio(exc):
                    logger.warning("embeddings %s:%s no disponible (%s); siguiente", prov, modelo, _corto(exc))
                    continue
                raise
            if i:
                logger.info("embeddings: failover a %s:%s", prov, modelo)
            self._activo = (prov, modelo, emb)
            self._candidatos = self._candidatos[i:]  # los ya descartados no vuelven
            return prov, modelo
        raise TodosLosEmbeddingsAgotados(
            f"Se agotaron todos los embeddings [{self.descripcion}]. Último error: {_corto(ultimo)}"
        ) from ultimo

    def _delegar(self, fn_nombre: str, arg):
        self.resolver()
        while self._candidatos:
            prov, modelo, emb = self._candidatos[0]
            try:
                return getattr(emb, fn_nombre)(arg)
            except Exception as exc:  # noqa: BLE001
                if len(self._candidatos) > 1 and (degradar_a_siguiente(exc) or es_transitorio(exc)):
                    logger.warning("embeddings %s:%s cayó (%s); siguiente", prov, modelo, _corto(exc))
                    self._candidatos = self._candidatos[1:]
                    self._activo = None
                    self.resolver()
                    continue
                raise
        raise TodosLosEmbeddingsAgotados("Se agotaron todos los embeddings en ejecución.")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._delegar("embed_documents", texts)

    def embed_query(self, text: str) -> list[float]:
        return self._delegar("embed_query", text)
