"""Chat con failover multi-proveedor / multi-modelo.

Se recorre una lista ordenada de `(proveedor, modelo)`:
  - error transitorio (503 / timeout / overloaded)  -> reintenta el MISMO modelo (backoff)
  - sin cuota / no disponible (429 / 402 / 404 / sin créditos / parser roto) -> pasa al SIGUIENTE
  - error real (bug, config)                          -> se propaga
Si se agotan todos, se lanza `TodosLosModelosAgotados` con el último error.

`ChatConFailover` no es un `BaseChatModel` pero expone `with_structured_output(schema)` que
devuelve un `Runnable` — así las cadenas `PROMPT | chat.with_structured_output(X)` no cambian.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable, RunnableLambda


class SoportaStructured(Protocol):
    """Lo mínimo que los adaptadores necesitan de un chat: `with_structured_output`.

    Lo cumplen `BaseChatModel` (incl. el fake) y `ChatConFailover`.
    """

    def with_structured_output(self, schema, **kw) -> Runnable: ...  # noqa: N802

logger = logging.getLogger("generacion_contrato_ia_v2.llm.failover")

_TRANSITORIO = ("503", "UNAVAILABLE", "OVERLOADED", "DEADLINE", "TIMEOUT", "TIMED OUT",
                "INTERNAL", "ECONNRESET", "CONNECTION RESET", "502", "504", "TEMPORARILY")
# Motivos por los que este (proveedor, modelo) no puede servir la petición -> siguiente modelo.
_SIN_CUOTA = ("429", "RESOURCE_EXHAUSTED", "RATE LIMIT", "RATE-LIMIT", "RATELIMIT", "QUOTA",
              "EXCEEDED", "CREDITS", "402", "PAYMENT REQUIRED", "INSUFFICIENT", "NO ENDPOINTS",
              "UNAVAILABLE FOR FREE", "IS NOT AVAILABLE", "NOT A VALID MODEL", "INVALID MODEL",
              "UNKNOWN MODEL", "MODEL_NOT_FOUND", "MODEL NOT FOUND", "DOES NOT EXIST",
              "DO NOT HAVE ACCESS", "REQUEST TOO LARGE", "NO ALLOWED PROVIDERS", "NO INFERENCE PROVIDER",
              "PERMISSION DENIED", "NOT ALLOWED", "DATA POLICY", "DECOMMISSIONED")
_PARSER = ("OUTPUTPARSEREXCEPTION", "VALIDATIONERROR", "JSONDECODEERROR", "FAILED TO PARSE",
           "DID NOT MATCH", "RESPONSE_FORMAT", "COULD NOT PARSE", "PYDANTIC", "INVALID_REQUEST_BODY",
           "FAILED TO VALIDATE JSON", "DOES NOT SUPPORT", "JSON_VALIDATE_FAILED")


def _txt(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}".upper()


def es_transitorio(exc: BaseException) -> bool:
    t = _txt(exc)
    return any(m in t for m in _TRANSITORIO) and not any(m in t for m in _SIN_CUOTA)


def degradar_a_siguiente(exc: BaseException) -> bool:
    t = _txt(exc)
    return any(m in t for m in _SIN_CUOTA) or any(m in t for m in _PARSER)


class TodosLosModelosAgotados(RuntimeError):
    pass


@dataclass(frozen=True)
class UsoModelo:
    """Modelo que resolvió la invocación actual del hilo."""

    proveedor: str
    modelo: str
    intento: int


@dataclass
class EntradaModelo:
    proveedor: str
    modelo: str
    chat: BaseChatModel
    structured_method: str | None = None

    def __post_init__(self) -> None:
        self._cache: dict[tuple, Runnable] = {}

    def etiqueta(self) -> str:
        return f"{self.proveedor}:{self.modelo}"

    def structured(self, schema, **kw) -> Runnable:
        metodo = kw.pop("method", None) or self.structured_method
        clave = (id(schema), metodo, tuple(sorted(kw.items())))
        if clave not in self._cache:
            try:
                self._cache[clave] = (
                    self.chat.with_structured_output(schema, method=metodo, **kw)
                    if metodo
                    else self.chat.with_structured_output(schema, **kw)
                )
            except TypeError:  # el adaptador no acepta `method` (p.ej. el fake)
                self._cache[clave] = self.chat.with_structured_output(schema, **kw)
        return self._cache[clave]


class ChatConFailover:
    def __init__(
        self,
        entradas: list[EntradaModelo],
        *,
        reintentos_transitorios: int = 4,
        backoff_inicial_seg: float = 2.0,
        backoff_max_seg: float = 30.0,
    ) -> None:
        if not entradas:
            raise ValueError("ChatConFailover necesita al menos un modelo.")
        self._entradas = entradas
        self._reintentos = max(1, reintentos_transitorios)
        self._b0 = backoff_inicial_seg
        self._bmax = backoff_max_seg
        # LangGraph puede evaluar candidatos en paralelo. Un valor global en la instancia
        # mezclaría el modelo de llamadas concurrentes; thread-local mantiene cada huella ligada
        # a la misma invocación síncrona que acaba de terminar.
        self._uso_local = threading.local()

    @property
    def descripcion(self) -> str:
        return " -> ".join(e.etiqueta() for e in self._entradas)

    def ultimo_uso(self) -> UsoModelo | None:
        """Devuelve el modelo efectivo de la última llamada realizada en el hilo actual."""
        return getattr(self._uso_local, "valor", None)

    def with_structured_output(self, schema, **kw) -> Runnable:  # noqa: N802 (compat LangChain)
        def _invocar(prompt_value, config=None):
            self._uso_local.valor = None
            ultimo: BaseException | None = None
            intento_total = 0
            for entrada in self._entradas:
                runnable = entrada.structured(schema, **dict(kw))
                for intento in range(1, self._reintentos + 1):
                    intento_total += 1
                    try:
                        r = runnable.invoke(prompt_value, config=config)
                        self._uso_local.valor = UsoModelo(
                            proveedor=entrada.proveedor,
                            modelo=entrada.modelo,
                            intento=intento_total,
                        )
                        if entrada is not self._entradas[0] or intento > 1:
                            logger.info("failover OK con %s", entrada.etiqueta())
                        return r
                    except Exception as exc:  # noqa: BLE001
                        ultimo = exc
                        if es_transitorio(exc) and intento < self._reintentos:
                            espera = min(self._bmax, self._b0 * (2 ** (intento - 1)))
                            logger.warning(
                                "%s transitorio (%s); reintento %d/%d en %.0fs",
                                entrada.etiqueta(), _corto(exc), intento, self._reintentos, espera,
                            )
                            time.sleep(espera)
                            continue
                        if degradar_a_siguiente(exc) or es_transitorio(exc):
                            logger.warning(
                                "%s no disponible (%s); siguiente modelo",
                                entrada.etiqueta(), _corto(exc),
                            )
                            break
                        raise  # error real -> propagar
            raise TodosLosModelosAgotados(
                f"Se agotaron todos los modelos [{self.descripcion}]. Último error: {_corto(ultimo)}"
            ) from ultimo

        return RunnableLambda(_invocar)


def _corto(exc: BaseException | None) -> str:
    if exc is None:
        return "-"
    s = " ".join(str(exc).split())
    return (s[:180] + "…") if len(s) > 180 else s
