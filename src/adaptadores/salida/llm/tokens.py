"""Estimación del tamaño de un prompt en TOKENS.

Existe para poder decidir **antes de llamar** si un prompt cabe en el presupuesto declarado de
un modelo (`providers.<n>.llm.models[].max_input_tokens`). Hasta ahora el único juez del tamaño
era el propio proveedor: se mandaba la petición y se leía el 413. Eso cuesta un round-trip por
modelo y por nodo, corrida tras corrida, justo en los nodos de prompt grande.

Dos estimadores, y el barato es el que viene por defecto (`llm.tokenizador`):

- **`caracteres`** (por defecto): `len(texto) / chars_por_token` (`llm.chars_por_token`, 4.0).
  Sin dependencias, sin red, determinista. Es la misma regla con la que ya se dimensionaba el
  catálogo BIAN en la documentación del proyecto.
- **`tiktoken`**: tokeniza de verdad con `o200k_base`. No es el tokenizador exacto de Gemini,
  Llama o Qwen, pero el error queda muy por debajo del margen con el que se declaran los
  presupuestos.

`tiktoken` NO es el default por una razón medida, no por purismo: `get_encoding()` **descarga**
el vocabulario la primera vez y, sin salida a Internet, la llamada se queda colgada
indefinidamente — colgaría la primera invocación LLM de la corrida. Por eso, además de ser
opt-in, la carga se hace en un hilo con plazo: si no resuelve a tiempo se degrada al heurístico
con un aviso, y no se vuelve a intentar en este proceso. Una estimación peor cuesta un 413 de
más; un cuelgue cuesta la corrida entera.
"""

from __future__ import annotations

import logging
import math
import threading

logger = logging.getLogger("generacion_contrato_ia_v2.llm.tokens")

CHARS_POR_TOKEN_POR_DEFECTO = 4.0
TOKENIZADORES = ("caracteres", "tiktoken")
# Plazo para cargar el vocabulario de tiktoken (incluye la descarga de la primera vez).
_PLAZO_CARGA_SEG = 20.0

_lock = threading.Lock()
_codificador = None
_resuelto = False


def _cargar_tiktoken() -> None:
    global _codificador
    import tiktoken

    _codificador = tiktoken.get_encoding("o200k_base")


def _encoder():
    """El codificador de `tiktoken`, o `None`. Se resuelve una sola vez por proceso.

    La carga va en un hilo daemon con plazo: `tiktoken.get_encoding` descarga el vocabulario si
    no está en caché y, sin red, no vuelve nunca.
    """
    global _resuelto
    if _resuelto:
        return _codificador
    with _lock:
        if not _resuelto:
            hilo = threading.Thread(target=_cargar_tiktoken, daemon=True, name="carga-tiktoken")
            hilo.start()
            hilo.join(_PLAZO_CARGA_SEG)
            if hilo.is_alive():
                logger.warning(
                    "tiktoken no cargó en %.0fs (¿sin red para bajar el vocabulario?); "
                    "los tokens se estiman por caracteres",
                    _PLAZO_CARGA_SEG,
                )
            elif _codificador is None:
                logger.info("tiktoken no disponible; los tokens se estiman por caracteres")
            _resuelto = True
    return _codificador


def estimar_tokens(
    texto: str,
    *,
    chars_por_token: float = CHARS_POR_TOKEN_POR_DEFECTO,
    tokenizador: str = "caracteres",
) -> int:
    """Tokens estimados de `texto`. Nunca lanza: cualquier fallo cae al heurístico."""
    if not texto:
        return 0
    if tokenizador == "tiktoken":
        cod = _encoder()
        if cod is not None:
            try:
                # `disallowed_special=()` es obligatorio: un prompt que contenga literalmente
                # "<|endoftext|>" -o cualquier token especial- haría fallar el encode por defecto.
                return len(cod.encode(texto, disallowed_special=()))
            except Exception as exc:  # noqa: BLE001
                logger.debug("tiktoken falló (%s); estimo por caracteres", exc)
    ratio = (
        chars_por_token
        if chars_por_token and chars_por_token > 0
        else CHARS_POR_TOKEN_POR_DEFECTO
    )
    return math.ceil(len(texto) / ratio)
