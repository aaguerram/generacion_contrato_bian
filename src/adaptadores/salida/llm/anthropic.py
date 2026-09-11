"""Estrategia Anthropic (opcional). `pip install langchain-anthropic`.

Nota: usa embeddings de Gemini como fallback, salvo que definas otra cosa — Anthropic no
publica endpoint de embeddings. Para RAG con Anthropic, combina con embeddings de otro proveedor.
"""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from .estrategia import ProveedorLLMStrategy
from .gemini import GeminiStrategy

logger = logging.getLogger(__name__)


class AnthropicStrategy(ProveedorLLMStrategy):
    nombre = "anthropic"

    def crear_chat_model(self) -> BaseChatModel:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Estrategia 'anthropic': pip install langchain-anthropic") from exc

        c = self._config
        if not c.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY no está definida.")
        for extra in ({"thinking": {"type": "adaptive"}}, {}):
            try:
                modelo = ChatAnthropic(model=c.chat_model, api_key=c.api_key, max_tokens=8000, **extra)
            except (TypeError, ValidationError):
                continue
            logger.info("Anthropic chat '%s' | %s", c.chat_model, extra or "config básica")
            return modelo
        raise RuntimeError("No se pudo instanciar ChatAnthropic.")

    def crear_embeddings(self) -> Embeddings:
        logger.warning("Anthropic no tiene embeddings; usando embeddings de Gemini para el RAG.")
        return GeminiStrategy(self._config).crear_embeddings()
