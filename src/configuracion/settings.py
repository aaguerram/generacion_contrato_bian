"""Punto de entrada de configuración: carga el `.env` (solo API keys) y `config.yaml` (todo lo demás).

- `.env` / entorno del SO: `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `LANGSMITH_API_KEY`. Nada más.
- `config.yaml`: modelos por proveedor, orden de failover, umbrales, rutas, observabilidad.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from dotenv import load_dotenv

from src.configuracion.config_yaml import Config, cargar_config

_ENV_CARGADO = False


def _asegurar_env() -> None:
    global _ENV_CARGADO
    if not _ENV_CARGADO:
        load_dotenv()  # una var ya presente en el entorno NO se pisa
        _ENV_CARGADO = True


def cargar_settings(
    *, ruta_config: str | Path | None = None, esfuerzo: str | None = None
) -> Config:
    """Carga la configuración efectiva. `esfuerzo` (opcional) pisa `llm.esfuerzo` del yaml."""
    _asegurar_env()
    config = cargar_config(ruta_config)
    if esfuerzo:
        config = dataclasses.replace(config, llm=dataclasses.replace(config.llm, esfuerzo=esfuerzo))
    return config


# alias histórico
get_settings = cargar_settings
Settings = Config
