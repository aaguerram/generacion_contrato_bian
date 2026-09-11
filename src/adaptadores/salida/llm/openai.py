"""Estrategia OpenAI (opcional). `pip install langchain-openai`."""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from .estrategia import ProveedorLLMStrategy

logger = logging.getLogger(__name__)


class OpenAIStrategy(ProveedorLLMStrategy):
    nombre = "openai"

    def _import(self):
        try:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings

            return ChatOpenAI, OpenAIEmbeddings
        except ImportError as exc:
            raise RuntimeError("Estrategia 'openai': pip install langchain-openai") from exc

    def crear_chat_model(self) -> BaseChatModel:
        ChatOpenAI, _ = self._import()
        c = self._config
        if not c.api_key:
            raise RuntimeError("OPENAI_API_KEY no está definida.")
        for extra in ({"reasoning_effort": c.esfuerzo}, {}):
            try:
                modelo = ChatOpenAI(model=c.chat_model, api_key=c.api_key, temperature=c.temperature, **extra)
            except (TypeError, ValidationError):
                continue
            logger.info("OpenAI chat '%s' | %s", c.chat_model, extra or "config básica")
            return modelo
        raise RuntimeError("No se pudo instanciar ChatOpenAI.")

    def crear_embeddings(self) -> Embeddings:
        _, OpenAIEmbeddings = self._import()
        c = self._config
        return OpenAIEmbeddings(model=c.embeddings_model, api_key=c.api_key)
