"""Estrategia FreeLLMAPI — router local de free tiers (servidor propio, `compose.yaml` en
`~/Desktop/claude_cli/freellmapi`), API compatible OpenAI vía `/v1`.

Una sola clave (la "unified key" del dashboard, `FREELLMAPI_API_KEY` en `.env`) da acceso a los
proveedores que tenga configurados el router (HuggingFace, Groq, OpenRouter, Kilo, Ollama...);
el id de modelo es el slug canónico del router (`kimi-k3`, `deepseek-v4-pro`, `glm-5.2`) y el
router elige en qué plataforma servirlo, con sus propios cooldowns por 429/5xx. Por eso aquí
NO se piden `auto`/`auto:smart`: la huella del prompt tiene que decir qué modelo respondió, y con
`auto` solo lo diría la cabecera `X-Routed-Via`, que LangChain no persiste.
"""

from __future__ import annotations

from .openai_compat import OpenAICompatibleStrategy


class FreeLLMAPIStrategy(OpenAICompatibleStrategy):
    nombre = "freellmapi"
    base_url_por_defecto = "http://localhost:3011/v1"
    key_env_hint = "FREELLMAPI_API_KEY"
