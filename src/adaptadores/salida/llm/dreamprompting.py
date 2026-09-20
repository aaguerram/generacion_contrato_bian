"""Estrategia DreamPrompting — meta-router de free tiers, API compatible OpenAI.

Reenvía a Cloudflare, Groq, NVIDIA, Mistral, Cohere, Google, HuggingFace y OpenRouter con UNA
clave (`DREAMPROMPTING_API_KEY`), y el id de modelo lleva el prefijo del proveedor destino
(`nvidia/nvidia/nemotron-3-super-120b-a12b`, `groq/openai/gpt-oss-120b`).

Por qué es un proveedor propio y no un modelo más de `freellmapi`: el adaptador de DreamPrompting
del router valida que la respuesta devuelva el MISMO identificador de modelo que se pidió, y este
servicio reescribe esa identidad al reenviar. Medido el 2026-09-20: por el router solo pasaban 2
de 10 modelos ("DreamPrompting returned a different or missing model identity"), mientras que
llamándolo directo respondieron los 10 con `json_schema`. `ChatOpenAI` no comprueba la identidad,
así que aquí se aprovecha el catálogo entero.
"""

from __future__ import annotations

from .openai_compat import OpenAICompatibleStrategy


class DreamPromptingStrategy(OpenAICompatibleStrategy):
    nombre = "dreamprompting"
    base_url_por_defecto = "https://dreamprompting.com/api/v1"
    key_env_hint = "DREAMPROMPTING_API_KEY"
