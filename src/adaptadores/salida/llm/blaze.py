"""Estrategia BlazeAPI — free tier de 200k tokens/día sobre modelos DeepSeek, compatible OpenAI.

El free tier exige verificar la cuenta en su Discord antes de que la API responda (si no, 403
`permission_error` en `chat/completions` aunque `usage` y `models` sí contesten).

Solo se declaran los modelos VERIFICADOS con `json_schema`: el 2026-09-20 su proveedor de DeepSeek
estaba caído y 10 de 11 devolvían 503 tras 13-18 s cada uno. Declarar un modelo caído no es
gratis -- `ChatConFailover` paga ese tiempo antes de saltar al siguiente --, así que la lista se
amplía cuando se comprueba que responden, no antes.
"""

from __future__ import annotations

from .openai_compat import OpenAICompatibleStrategy


class BlazeStrategy(OpenAICompatibleStrategy):
    nombre = "blaze"
    base_url_por_defecto = "https://api.blazeapi.org/paid/v1"
    key_env_hint = "BLAZE_API_KEY"
