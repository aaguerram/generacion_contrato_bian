"""Estrategia Cohere — SOLO embeddings (retrieval multilingüe ES↔EN).

`pip install langchain-cohere`. El token (`COHERE_API_KEY`) es de free-tier / trial: da acceso a
TODOS los modelos de embed, con límite de ratio (~100 req/min · 1000 req/mes), no de modelo.

Cohere pone `input_type` automáticamente (`search_document` al indexar, `search_query` al
consultar) — no hay que tocarlo. Este proveedor NO expone chat: `crear_chat_model` lanza.
"""

from __future__ import annotations

import logging
import os

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from .estrategia import ProveedorLLMStrategy

logger = logging.getLogger(__name__)


def _api_key(cfg_key: str | None) -> str:
    key = cfg_key or os.getenv("COHERE_API_KEY") or os.getenv("CO_API_KEY")
    if not key:
        raise RuntimeError("No hay API key de Cohere. Exporta COHERE_API_KEY o ponla en .env.")
    return key


class CohereStrategy(ProveedorLLMStrategy):
    nombre = "cohere"

    def crear_chat_model(self) -> BaseChatModel:
        raise RuntimeError(
            "El proveedor 'cohere' está configurado solo para embeddings; no aporta chat. "
            "Quítalo de routing.llm_priority en config.yaml."
        )

    def crear_embeddings(self) -> Embeddings:
        try:
            from langchain_cohere import CohereEmbeddings
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Estrategia 'cohere': pip install langchain-cohere") from exc

        c = self._config
        logger.info("Cohere embeddings '%s'", c.embeddings_model)
        return CohereEmbeddings(model=c.embeddings_model, cohere_api_key=_api_key(c.api_key), max_retries=0)
