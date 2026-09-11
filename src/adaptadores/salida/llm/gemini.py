"""Estrategia Google Gemini: chat (gemini-3.6-flash) + embeddings."""

from __future__ import annotations

import logging
import os

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from .estrategia import ProveedorLLMStrategy

logger = logging.getLogger(__name__)


def _api_key(cfg_key: str | None) -> str:
    key = cfg_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "No hay API key de Gemini. Exporta GOOGLE_API_KEY (o GEMINI_API_KEY) o ponla en .env."
        )
    return key


class GeminiStrategy(ProveedorLLMStrategy):
    nombre = "gemini"

    def crear_chat_model(self) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        c = self._config
        base = dict(
            model=c.chat_model,
            google_api_key=_api_key(c.api_key),
            temperature=c.temperature,
            max_retries=2,
        )
        # seed para reproducibilidad (probamos si el SDK lo acepta como kwarg directo).
        seed_kw: dict = {}
        if c.seed is not None:
            try:
                ChatGoogleGenerativeAI(**base, seed=c.seed)
                seed_kw = {"seed": c.seed}
            except (TypeError, ValidationError):
                logger.info("Gemini: 'seed' no soportado por esta versión del SDK; se omite")

        for extra in (
            {"thinking_budget": c.presupuesto_pensamiento},
            {"thinking_level": "high" if c.esfuerzo == "high" else "low"},
            {},
        ):
            try:
                modelo = ChatGoogleGenerativeAI(**base, **extra, **seed_kw)
            except (TypeError, ValidationError):
                continue
            logger.info(
                "Gemini chat '%s' | esfuerzo=%s%s | %s",
                c.chat_model,
                c.esfuerzo,
                " seed=" + str(c.seed) if seed_kw else "",
                extra or "sin control de razonamiento",
            )
            return modelo
        raise RuntimeError("No se pudo instanciar ChatGoogleGenerativeAI.")

    def crear_embeddings(self) -> Embeddings:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        c = self._config
        logger.info("Gemini embeddings '%s' (dim=768)", c.embeddings_model)
        # 768 dims (truncado MRL) basta para 341 items y reduce payload/caché.
        return GoogleGenerativeAIEmbeddings(
            model=c.embeddings_model,
            google_api_key=_api_key(c.api_key),
            output_dimensionality=768,
        )
