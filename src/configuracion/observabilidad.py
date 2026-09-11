"""Activa el trazado de LangSmith desde `config.yaml` (observabilidad) + `LANGSMITH_API_KEY` del .env."""

from __future__ import annotations

import logging
import os

from src.configuracion.config_yaml import Config

logger = logging.getLogger(__name__)


def configurar_langsmith(config: Config) -> bool:
    """Devuelve True si el trazado queda activo."""
    o = config.observabilidad
    if not (o.langsmith_tracing and o.langsmith_api_key):
        os.environ["LANGSMITH_TRACING"] = "false"
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = o.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = o.langsmith_project
    if o.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = o.langsmith_endpoint
    logger.info("LangSmith activo | proyecto=%s", o.langsmith_project)
    return True
