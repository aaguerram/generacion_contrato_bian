"""Canal denso del paso 1: embeddings sobre el documento de cada clase con dueño.

Lee `ConsultaClases.texto` -la HU en español, sin traducir-: un modelo multilingüe es justo lo
que quita la dependencia del diccionario ES->EN, que es el punto frágil medido del canal (sin la
entrada `cliente -> party`, el dueño de `Party` se cae del top-4). El índice se persiste en disco
por modelo de embeddings y firma del corpus, igual que `RecuperadorVectorial`.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from src.aplicacion.puertos.catalogo_entidades import CatalogoEntidadesBianPort
from src.aplicacion.puertos.recuperador_clases import RecuperadorClasesPort
from src.dominio.entidades_bian import CandidatoClase, ConsultaClases, documentos_indexables

logger = logging.getLogger(__name__)


class RecuperadorClasesVectorial(RecuperadorClasesPort):
    def __init__(
        self,
        catalogo: CatalogoEntidadesBianPort,
        embeddings: Embeddings,
        *,
        modelo_embeddings: str,
        dir_cache: str | Path = ".cache",
    ) -> None:
        self._catalogo = catalogo
        self._embeddings = embeddings
        self._slug = re.sub(r"[^a-z0-9]+", "-", modelo_embeddings.lower()).strip("-")
        self._persistir = self._slug != "fake"
        self._dir_cache = Path(dir_cache)
        self._store: InMemoryVectorStore | None = None

    @property
    def nombre(self) -> str:
        return "vectorial"

    def _ruta_cache(self, docs: list[tuple[str, str]]) -> Path:
        # Se invalida si cambia el corpus (nombres o textos) o el modelo de embeddings.
        firma = hashlib.sha256(
            "\x1f".join(f"{n}\x1e{t}" for n, t in docs).encode()
        ).hexdigest()[:10]
        return self._dir_cache / f"clases-bom.vectorstore.{self._slug}.{firma}.json"

    def _asegurar(self) -> InMemoryVectorStore:
        if self._store is not None:
            return self._store
        docs = documentos_indexables(
            self._catalogo.clases(), nombres_enum=self._catalogo.nombres_enum()
        )
        ruta = self._ruta_cache(docs)
        if self._persistir and ruta.is_file():
            logger.info("cargando índice vectorial de clases BOM de %s", ruta)
            self._store = InMemoryVectorStore.load(str(ruta), self._embeddings)
            return self._store
        logger.info("construyendo índice vectorial de clases BOM (%d clases con dueño)...", len(docs))
        self._store = InMemoryVectorStore.from_documents(
            [Document(page_content=texto, metadata={"clase": nombre}) for nombre, texto in docs],
            self._embeddings,
        )
        if self._persistir:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._store.dump(str(ruta))
            except Exception as exc:  # pragma: no cover - persistencia best-effort
                logger.warning("no se pudo persistir el índice de clases: %s", exc)
        return self._store

    def recuperar(self, consulta: ConsultaClases, k: int) -> list[CandidatoClase]:
        if not consulta.texto.strip():
            return []
        resultados = self._asegurar().similarity_search_with_score(consulta.texto, k=k)
        return [
            CandidatoClase(clase=doc.metadata.get("clase", ""), score=round(float(score), 4))
            for doc, score in resultados
        ]
