"""Base para proveedores con API compatible OpenAI (OpenRouter, Groq, …).

`pip install langchain-openai`. `ChatOpenAI` + `base_url`. La salida estructurada usa
`method="json_schema"` por defecto (`structured_method` en config.yaml); el failover ya
gestiona los reintentos, así que `max_retries=0`.
"""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from .estrategia import ProveedorLLMStrategy

logger = logging.getLogger(__name__)


class OpenAICompatibleStrategy(ProveedorLLMStrategy):
    """Subclases: definen `nombre`, `base_url_por_defecto` y opcionalmente `headers_extra`."""

    base_url_por_defecto: str = ""
    headers_extra: dict[str, str] = {}
    key_env_hint: str = "API key"

    def _import(self):
        try:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings

            return ChatOpenAI, OpenAIEmbeddings
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(f"Estrategia '{self.nombre}': pip install langchain-openai") from exc

    def _base_url(self) -> str:
        return self._config.base_url or self.base_url_por_defecto

    def crear_chat_model(self) -> BaseChatModel:
        ChatOpenAI, _ = self._import()
        c = self._config
        if not c.api_key:
            raise RuntimeError(f"{self.key_env_hint} no está definida para '{self.nombre}'.")
        base = dict(
            model=c.chat_model,
            api_key=c.api_key,
            base_url=self._base_url(),
            temperature=c.temperature,
            max_retries=0,  # el failover gestiona los reintentos
        )
        if self.headers_extra:
            base["default_headers"] = dict(self.headers_extra)
        for extra in ({"seed": c.seed} if c.seed is not None else {}, {}):
            try:
                modelo = ChatOpenAI(**base, **extra)
            except (TypeError, ValidationError):
                continue
            logger.info("%s chat '%s'%s", self.nombre, c.chat_model, " seed=" + str(c.seed) if extra else "")
            return modelo
        raise RuntimeError(f"No se pudo instanciar ChatOpenAI para '{self.nombre}'.")

    def crear_embeddings(self) -> Embeddings:
        _, OpenAIEmbeddings = self._import()
        c = self._config
        return OpenAIEmbeddings(model=c.embeddings_model, api_key=c.api_key, base_url=self._base_url())
