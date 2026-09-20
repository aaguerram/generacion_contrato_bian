"""Estrategia ACLIDE — free tier de 20 EUR/mes en créditos compartidos, **Responses API**.

Dos particularidades, ambas medidas el 2026-09-20, que obligan a un adaptador propio:

1. **No expone Chat Completions.** Su API OpenAI-compatible es `/v1/responses` (y una
   Anthropic-compatible en `/v1/messages`). `ChatOpenAI` lo habla con `use_responses_api=True`.
2. **Ignora `response_format`.** Con `structured_method: json_schema` los modelos contestan
   markdown y el parseo falla ("Invalid JSON: expected value at line 1 column 1"). Con
   `function_calling` responden bien: Claude Opus 5 en 10 s, GPT-6 Astra en 8 s. Por eso el
   proveedor declara `structured_method: function_calling` en `config.yaml`.

Tampoco sirve por el router local: su adaptador valida que la respuesta traiga el mismo
identificador de modelo y ACLIDE devuelve otro ("ACLIDE returned a different or missing model
identity"), así que los 8 modelos que se probaron ahí quedaron fuera.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from .openai_compat import OpenAICompatibleStrategy

logger = logging.getLogger(__name__)


class AclideStrategy(OpenAICompatibleStrategy):
    nombre = "aclide"
    base_url_por_defecto = "https://aclide.com/v1"
    key_env_hint = "ACLIDE_API_KEY"

    def crear_chat_model(self) -> BaseChatModel:
        """Como el genérico, pero hablando la Responses API en vez de Chat Completions."""
        from langchain_openai import ChatOpenAI

        c = self._config
        if not c.api_key:
            raise RuntimeError(f"{self.key_env_hint} no está definida para '{self.nombre}'.")
        base = dict(
            model=c.chat_model,
            api_key=c.api_key,
            base_url=self._base_url(),
            temperature=c.temperature,
            max_retries=0,  # el failover gestiona los reintentos
            use_responses_api=True,
        )
        for extra in ({"seed": c.seed} if c.seed is not None else {}, {}):
            try:
                modelo = ChatOpenAI(**base, **extra)
            except (TypeError, ValidationError):
                continue
            logger.info("%s chat '%s' (responses API)", self.nombre, c.chat_model)
            return modelo
        raise RuntimeError(f"No se pudo instanciar ChatOpenAI para '{self.nombre}'.")
