"""Estrategia Hugging Face — router de Inference Providers, API compatible OpenAI.

`base_url = https://router.huggingface.co/v1`. El token (`HF_TOKEN`) enruta a distintos
proveedores de inferencia. Free tier: crédito mensual muy pequeño -> pensado como fallback.

Modelos con salida estructurada (`json_schema`) verificados: `deepseek-ai/DeepSeek-V4-Flash`,
`openai/gpt-oss-120b`, `meta-llama/Llama-3.3-70B-Instruct`. Varios (V4.1-Flash, Qwen3.5-122B,
GLM-4) NO soportan `json_schema`.
"""

from __future__ import annotations

from .openai_compat import OpenAICompatibleStrategy


class HuggingFaceStrategy(OpenAICompatibleStrategy):
    nombre = "huggingface"
    base_url_por_defecto = "https://router.huggingface.co/v1"
    key_env_hint = "HF_TOKEN"
