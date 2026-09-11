"""Estrategia Groq — API compatible OpenAI, inferencia LPU muy rápida, free tier generoso.

Modelos con salida estructurada (`json_schema`) verificados: `openai/gpt-oss-120b`,
`openai/gpt-oss-20b`. Los `groq/compound*` y algunos `qwen` NO soportan `json_schema`.
"""

from __future__ import annotations

from .openai_compat import OpenAICompatibleStrategy


class GroqStrategy(OpenAICompatibleStrategy):
    nombre = "groq"
    base_url_por_defecto = "https://api.groq.com/openai/v1"
    key_env_hint = "GROQ_API_KEY"
