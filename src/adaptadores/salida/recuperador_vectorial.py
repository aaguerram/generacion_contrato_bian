"""Adaptador RAG: índice vectorial en memoria sobre el catálogo (langchain-core InMemoryVectorStore).

- El índice se construye de forma perezosa: si la consulta acierta por coincidencia exacta,
  no se llama nunca a los embeddings.
- Se persiste en disco por modelo de embeddings; en corridas siguientes se carga.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from src.adaptadores.salida.recuperador_lexico import similitud_nombre
from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.dominio.modelos import CandidatoSD

logger = logging.getLogger(__name__)


class RecuperadorVectorial(RecuperadorSemanticoPort):
    def __init__(
        self,
        catalogo: CatalogoServiceDomainsPort,
        embeddings: Embeddings,
        *,
        modelo_embeddings: str,
        dir_cache: str | Path = ".cache",
    ) -> None:
        self._catalogo = catalogo
        self._embeddings = embeddings
        self._slug = re.sub(r"[^a-z0-9]+", "-", modelo_embeddings.lower()).strip("-")
        self._persistir = self._slug != "fake"  # el índice fake no se cachea
        self._dir_cache = Path(dir_cache)
        self._store: InMemoryVectorStore | None = None

    def _ruta_cache(self, entradas) -> Path:
        # la caché se invalida si cambia el catálogo o el modelo de embeddings
        firma = hashlib.sha256(
            "\x1f".join(sorted(e.service_domain for e in entradas)).encode()
        ).hexdigest()[:10]
        return self._dir_cache / f"SD.vectorstore.{self._slug}.{firma}.json"

    def _asegurar_indice(self) -> InMemoryVectorStore:
        if self._store is not None:
            return self._store

        entradas = self._catalogo.cargar()
        ruta = self._ruta_cache(entradas)
        if self._persistir and ruta.is_file():
            logger.info("cargando índice vectorial de %s", ruta)
            self._store = InMemoryVectorStore.load(str(ruta), self._embeddings)
            return self._store
        logger.info("construyendo índice vectorial (%d Service Domains)...", len(entradas))
        docs = [
            Document(
                page_content=e.texto_para_indexar(),
                metadata={
                    "service_domain": e.service_domain,
                    "service_role": e.service_role,
                    "functional_pattern": e.functional_pattern,
                },
            )
            for e in entradas
        ]
        self._store = InMemoryVectorStore.from_documents(docs, self._embeddings)
        if self._persistir:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._store.dump(str(ruta))
            except Exception as exc:  # pragma: no cover - persistencia best-effort
                logger.warning("no se pudo persistir el índice: %s", exc)
        return self._store

    def recuperar(self, consulta: str, k: int) -> list[CandidatoSD]:
        store = self._asegurar_indice()
        resultados = store.similarity_search_with_score(consulta, k=k)
        candidatos: list[CandidatoSD] = []
        for doc, score in resultados:
            nombre = doc.metadata.get("service_domain", "")
            candidatos.append(
                CandidatoSD(
                    service_domain=nombre,
                    score=round(float(score), 4),
                    similitud_nombre=round(similitud_nombre(consulta, nombre), 4),
                    service_role=doc.metadata.get("service_role"),
                    functional_pattern=doc.metadata.get("functional_pattern"),
                )
            )
        return candidatos
