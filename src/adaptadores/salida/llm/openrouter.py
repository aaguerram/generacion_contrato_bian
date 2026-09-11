"""Estrategia OpenRouter — API compatible OpenAI, muchos modelos (varios `:free`)."""

from __future__ import annotations

from .openai_compat import OpenAICompatibleStrategy


class OpenRouterStrategy(OpenAICompatibleStrategy):
    nombre = "openrouter"
    base_url_por_defecto = "https://openrouter.ai/api/v1"
    key_env_hint = "OPENROUTER_API_KEY"
    headers_extra = {
        "HTTP-Referer": "https://github.com/generacion-contrato-ia",
        "X-Title": "generacion_contrato_ia_v2",
    }
