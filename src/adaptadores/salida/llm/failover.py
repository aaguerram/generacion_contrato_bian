"""Chat con failover multi-proveedor / multi-modelo.

Se recorre una lista ordenada de `(proveedor, modelo)`:
  - error transitorio (503 / timeout / overloaded)  -> reintenta el MISMO modelo (backoff)
  - sin cuota / no disponible (429 / 402 / 404 / sin créditos / parser roto) -> pasa al SIGUIENTE
  - error real (bug, config)                          -> se propaga
Si se agotan todos, se lanza `TodosLosModelosAgotados` con el último error.

ANTES de llamar a cada modelo se comprueba que el prompt quepa en su presupuesto de entrada
(`EntradaModelo.max_input_tokens`, que sale de `providers.<n>.llm.models[].max_input_tokens`).
Un modelo cuyo contexto no admite esta petición se **salta sin gastar la llamada**: los intentos
se gastan solo donde el contexto entra. Si nadie la admite se lanza `PeticionDemasiadoGrande`
—la misma señal que produce un 413 real—, así que quien armó el prompt puede reducirlo. Un
modelo sin `max_input_tokens` declarado se llama igual que siempre y su límite se aprende del
primer 413.

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

from src.adaptadores.salida.llm.tokens import CHARS_POR_TOKEN_POR_DEFECTO, estimar_tokens


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
              "DO NOT HAVE ACCESS", "NO ALLOWED PROVIDERS", "NO INFERENCE PROVIDER",
              "PERMISSION DENIED", "NOT ALLOWED", "DATA POLICY", "DECOMMISSIONED")
# "No cabe" NO es lo mismo que "sin cuota", aunque ambos acaben pasando al siguiente modelo: la
# cuota vuelve sola y el tamaño no. Un 413 dice algo sobre ESTA petición y ESTE modelo, y esa
# información sirve dos veces -- para no repetir el error con la misma petición (ver
# `_demasiado_grande` en `ChatConFailover`) y para que quien construyó el prompt pueda reducirlo
# en vez de rendirse (`PeticionDemasiadoGrande`).
_NO_CABE = ("413", "REQUEST TOO LARGE", "TOO LARGE", "CONTEXT LENGTH", "MAXIMUM CONTEXT",
            "CONTEXT_LENGTH_EXCEEDED", "TOO MANY TOKENS", "REDUCE THE LENGTH", "PROMPT IS TOO LONG")
_PARSER = ("OUTPUTPARSEREXCEPTION", "VALIDATIONERROR", "JSONDECODEERROR", "FAILED TO PARSE",
           "DID NOT MATCH", "RESPONSE_FORMAT", "COULD NOT PARSE", "PYDANTIC", "INVALID_REQUEST_BODY",
           "FAILED TO VALIDATE JSON", "DOES NOT SUPPORT", "JSON_VALIDATE_FAILED")


def _txt(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}".upper()


def es_transitorio(exc: BaseException) -> bool:
    t = _txt(exc)
    return any(m in t for m in _TRANSITORIO) and not any(m in t for m in _SIN_CUOTA)


def no_cabe(exc: BaseException) -> bool:
    """El modelo rechazó la petición por TAMAÑO (413 y equivalentes)."""
    return any(m in _txt(exc) for m in _NO_CABE)


def degradar_a_siguiente(exc: BaseException) -> bool:
    t = _txt(exc)
    return any(m in t for m in _SIN_CUOTA) or any(m in t for m in _PARSER) or no_cabe(exc)


class TodosLosModelosAgotados(RuntimeError):
    pass


class PeticionDemasiadoGrande(TodosLosModelosAgotados):
    """Se agotó la cadena y al menos un modelo rechazó la petición por TAMAÑO.

    Se distingue de `TodosLosModelosAgotados` para que quien construyó el prompt pueda hacer lo
    único que arregla esto -- mandar menos -- en vez de rendirse. Ver
    `AnalistaMapeoBianLangChain`, que reintenta con el catálogo reducido.
    """


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
    # Presupuesto de ENTRADA declarado para este modelo, en tokens
    # (`providers.<n>.llm.models[].max_input_tokens`). `None` = sin límite declarado: se llama y
    # se deja que el proveedor conteste, que es el comportamiento histórico.
    max_input_tokens: int | None = None

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
        chars_por_token: float = CHARS_POR_TOKEN_POR_DEFECTO,
        tokenizador: str = "caracteres",
    ) -> None:
        if not entradas:
            raise ValueError("ChatConFailover necesita al menos un modelo.")
        self._entradas = entradas
        self._reintentos = max(1, reintentos_transitorios)
        self._b0 = backoff_inicial_seg
        self._bmax = backoff_max_seg
        # Cómo se mide un prompt contra el presupuesto de cada modelo; ver `tokens.estimar_tokens`.
        self._chars_por_token = chars_por_token
        self._tokenizador = tokenizador
        # LangGraph puede evaluar candidatos en paralelo. Un valor global en la instancia
        # mezclaría el modelo de llamadas concurrentes; thread-local mantiene cada huella ligada
        # a la misma invocación síncrona que acaba de terminar.
        self._uso_local = threading.local()
        # {etiqueta del modelo: menor tamaño de prompt que rechazó por 413}. Compartido entre
        # llamadas del proceso a propósito: es lo que evita repetir el mismo 413 en cada nodo.
        self._limite_tamano: dict[str, int] = {}

    @property
    def descripcion(self) -> str:
        return " -> ".join(e.etiqueta() for e in self._entradas)

    def ultimo_uso(self) -> UsoModelo | None:
        """Devuelve el modelo efectivo de la última llamada realizada en el hilo actual."""
        return getattr(self._uso_local, "valor", None)

    @staticmethod
    def _texto(prompt_value) -> str:
        try:
            return prompt_value.to_string()
        except Exception:  # noqa: BLE001 - cualquier prompt raro cae a su repr
            return str(prompt_value)

    @classmethod
    def _tamano(cls, prompt_value) -> int:
        return len(cls._texto(prompt_value))

    def with_structured_output(self, schema, **kw) -> Runnable:  # noqa: N802 (compat LangChain)
        def _invocar(prompt_value, config=None):
            self._uso_local.valor = None
            ultimo: BaseException | None = None
            intento_total = 0
            rechazo_por_tamano = False
            texto = self._texto(prompt_value)
            tamano = len(texto)
            # Se estima UNA vez por invocación y se compara contra el presupuesto de cada modelo:
            # tokenizar es barato al lado de un round-trip HTTP, y así la decisión es la misma
            # para toda la cadena.
            tokens = estimar_tokens(
                texto,
                chars_por_token=self._chars_por_token,
                tokenizador=self._tokenizador,
            )
            sin_presupuesto: list[str] = []
            for entrada in self._entradas:
                # PRIMER filtro, antes de gastar nada: el presupuesto DECLARADO en config.yaml.
                # Si el prompt no cabe en lo que este modelo admite, llamarlo solo sirve para
                # leer un 413 que ya sabíamos. A diferencia del aprendizaje de abajo, esto no
                # necesita haber fallado antes ni una vez -- y es lo que hace que los intentos se
                # gasten solo en modelos donde el contexto entra.
                if entrada.max_input_tokens is not None and tokens > entrada.max_input_tokens:
                    logger.info(
                        "%s omitido sin llamar: ~%d tokens estimados > max_input_tokens=%d",
                        entrada.etiqueta(), tokens, entrada.max_input_tokens,
                    )
                    rechazo_por_tamano = True
                    sin_presupuesto.append(f"{entrada.etiqueta()}<={entrada.max_input_tokens}")
                    continue
                # SEGUNDO filtro, aprendido: si este modelo ya rechazó por tamaño una petición
                # igual o MENOR, mandarle esta es gastar un round-trip para leer el mismo 413. No
                # es un latch sobre el modelo -sigue siendo el primero que se prueba para
                # cualquier prompt más pequeño-, es memoria sobre el TAMAÑO. Medido: con CAG
                # encendido, Groq devolvía 413 en los dos modelos en cada nodo grande, corrida
                # tras corrida. Sigue haciendo falta con `max_input_tokens` declarado: cubre al
                # modelo cuyo presupuesto real es menor que el declarado (o el no declarado).
                limite = self._limite_tamano.get(entrada.etiqueta())
                if limite is not None and tamano >= limite:
                    logger.info(
                        "%s omitido sin llamar: ya rechazó por tamaño >= %d chars (esta: %d)",
                        entrada.etiqueta(), limite, tamano,
                    )
                    rechazo_por_tamano = True
                    continue
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
                        if no_cabe(exc):
                            rechazo_por_tamano = True
                            previo = self._limite_tamano.get(entrada.etiqueta())
                            self._limite_tamano[entrada.etiqueta()] = (
                                tamano if previo is None else min(previo, tamano)
                            )
                            logger.warning(
                                "%s no acepta esta petición (%d chars): %s; siguiente modelo",
                                entrada.etiqueta(), tamano, _corto(exc),
                            )
                            break
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
            if rechazo_por_tamano:
                detalle = (
                    f" Sin presupuesto declarado suficiente: {', '.join(sin_presupuesto)}."
                    if sin_presupuesto
                    else ""
                )
                raise PeticionDemasiadoGrande(
                    f"Ningún modelo aceptó una petición de {tamano} chars (~{tokens} tokens) "
                    f"[{self.descripcion}].{detalle} Último error: {_corto(ultimo)}"
                ) from ultimo
            raise TodosLosModelosAgotados(
                f"Se agotaron todos los modelos [{self.descripcion}]. Último error: {_corto(ultimo)}"
            ) from ultimo

        return RunnableLambda(_invocar)


def _corto(exc: BaseException | None) -> str:
    if exc is None:
        return "-"
    s = " ".join(str(exc).split())
    return (s[:180] + "…") if len(s) > 180 else s
