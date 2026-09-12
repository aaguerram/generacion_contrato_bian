"""Estrategia Ollama — servidor propio (docker), API compatible OpenAI vía `/v1`.

Self-hosted: sin cuota ni free-tier, primera opción de failover tanto para chat como para
embeddings (ver `routing.llm_priority` / `routing.embedding_priority` en `config.yaml`).
El endpoint OpenAI-compatible de Ollama ignora el valor de la API key, pero `langchain-openai`
exige que no esté vacía -- `OLLAMA_API_KEY` en `.env` es un placeholder, no un secreto real.
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from .openai_compat import OpenAICompatibleStrategy


class OllamaStrategy(OpenAICompatibleStrategy):
    nombre = "ollama"
    base_url_por_defecto = "http://localhost:11434/v1"
    key_env_hint = "OLLAMA_API_KEY"

    def crear_embeddings(self) -> Embeddings:
        # Ollama no es OpenAI: `OpenAIEmbeddings` por defecto tokeniza con `tiktoken` y manda
        # arrays de token-ids ("invalid input type" en Ollama, que espera texto crudo).
        # `check_embedding_ctx_length=False` bypassea esa tokenización.
        _, OpenAIEmbeddings = self._import()
        c = self._config
        return OpenAIEmbeddings(
            model=c.embeddings_model,
            api_key=c.api_key,
            base_url=self._base_url(),
            check_embedding_ctx_length=False,
        )
