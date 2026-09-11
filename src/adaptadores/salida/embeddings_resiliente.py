"""Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el retryDelay de Google)."""

from __future__ import annotations

import logging
import re
import time

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

_TRANSITORIO = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL", "DEADLINE")
_RETRY_DELAY = re.compile(r"retry(?:\s+in|Delay['\"]?:?\s*['\"]?)\s*([\d.]+)\s*s", re.I)


def _es_transitorio(exc: Exception) -> bool:
    t = str(exc).upper()
    return any(m in t for m in _TRANSITORIO)


def _delay_sugerido(exc: Exception) -> float | None:
    m = _RETRY_DELAY.search(str(exc))
    return float(m.group(1)) if m else None


class EmbeddingsResiliente(Embeddings):
    def __init__(self, base: Embeddings, *, max_intentos: int = 5, espera_inicial: float = 2.0) -> None:
        self._base = base
        self._max = max_intentos
        self._espera = espera_inicial

    def _con_reintento(self, fn, *args):
        for intento in range(self._max):
            try:
                return fn(*args)
            except Exception as exc:  # noqa: BLE001 - se re-lanza si no es transitorio
                if not _es_transitorio(exc) or intento == self._max - 1:
                    raise
                pausa = min((_delay_sugerido(exc) or self._espera * 2**intento) + 1.0, 65.0)
                logger.warning(
                    "embeddings: error transitorio (intento %d/%d); reintento en %.0fs",
                    intento + 1,
                    self._max,
                    pausa,
                )
                time.sleep(pausa)
        raise RuntimeError("embeddings: reintentos agotados")  # pragma: no cover

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._con_reintento(self._base.embed_documents, texts)

    def embed_query(self, text: str) -> list[float]:
        return self._con_reintento(self._base.embed_query, text)
