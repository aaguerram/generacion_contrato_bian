"""Adaptador: caché de nodos de LangGraph persistida en archivos. Sin dependencias nuevas.

`InMemoryCache` (la que trae LangGraph) muere con el proceso, así que solo deduplica dentro de
UNA corrida. El bucle que hay que abaratar es el otro: medir flag por flag (`canary.py`) vuelve a
pagar TODAS las llamadas LLM aunque solo cambie un flag que afecta a un nodo, y una corrida de
~600s que muere a mitad por cuota agotada se pierde entera.

Esta caché escribe cada resultado de nodo en `<raiz>/<grafo>/<nodo>/<sha>.json`, así que:

- re-ejecutar tras un fallo salta todo lo ya calculado y solo llama al LLM por lo que falta
  (resume por caché: es lo que hoy sustituye al checkpointer persistente, que exigiría instalar
  `langgraph-checkpoint-sqlite`);
- el mismo Service Domain evaluado en varias HU de la misma funcionalidad se paga una vez;
- cambiar un flag invalida solo los nodos cuya entrada cambió, porque la clave la calcula el
  `key_func` de cada nodo a partir de sus entradas semánticas (ver `_clave_nodo` en el servicio),
  nunca del estado entero.

La clave incluye la firma del LLM (cadena de failover + esfuerzo) y el SHA del catálogo: un
resultado producido por otro modelo o sobre otra evidencia NO se reutiliza en silencio.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from langgraph.cache.base import BaseCache, FullKey, Namespace, ValueT
from langgraph.checkpoint.serde.base import SerializerProtocol

logger = logging.getLogger(__name__)

_SEGURO = re.compile(r"[^A-Za-z0-9._-]+")


def _segmento(valor: str) -> str:
    limpio = _SEGURO.sub("-", valor).strip("-")
    return limpio[:60] or "_"


class CacheNodosArchivo(BaseCache[ValueT]):
    """`BaseCache` de LangGraph sobre el sistema de archivos. Tolerante a fallos: si una entrada
    está corrupta o no se puede leer/escribir, se comporta como un fallo de caché y sigue —
    perder un acierto de caché cuesta una llamada; romper la corrida, todas."""

    def __init__(self, raiz: str | Path, *, serde: SerializerProtocol | None = None) -> None:
        super().__init__(serde=serde)
        self._raiz = Path(raiz)
        self._lock = threading.RLock()
        self.aciertos = 0
        self.fallos = 0

    def _ruta(self, ns: Namespace, key: str) -> Path:
        sha = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
        return self._raiz.joinpath(*(_segmento(p) for p in ns)) / f"{sha}.json"

    def get(self, keys: Sequence[FullKey]) -> dict[FullKey, ValueT]:
        valores: dict[FullKey, ValueT] = {}
        if not keys:
            return valores
        ahora = time.time()
        with self._lock:
            for ns_tupla, key in keys:
                ns = Namespace(ns_tupla)
                ruta = self._ruta(ns, key)
                try:
                    if not ruta.is_file():
                        self.fallos += 1
                        continue
                    crudo = json.loads(ruta.read_text(encoding="utf-8"))
                    expira = crudo.get("expira")
                    if expira is not None and ahora >= expira:
                        ruta.unlink(missing_ok=True)
                        self.fallos += 1
                        continue
                    valores[(ns, key)] = self.serde.loads_typed(
                        (crudo["enc"], base64.b64decode(crudo["valor"]))
                    )
                    self.aciertos += 1
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    logger.warning("entrada de caché ilegible %s: %s", ruta, exc)
                    self.fallos += 1
        return valores

    async def aget(self, keys: Sequence[FullKey]) -> dict[FullKey, ValueT]:
        return self.get(keys)

    def set(self, keys: Mapping[FullKey, tuple[ValueT, int | None]]) -> None:
        with self._lock:
            for (ns, key), (valor, ttl) in keys.items():
                ruta = self._ruta(Namespace(ns), key)
                try:
                    enc, datos = self.serde.dumps_typed(valor)
                    ruta.parent.mkdir(parents=True, exist_ok=True)
                    tmp = ruta.with_suffix(".tmp")
                    tmp.write_text(
                        json.dumps(
                            {
                                "clave": key,
                                "enc": enc,
                                "valor": base64.b64encode(datos).decode("ascii"),
                                "expira": (time.time() + ttl) if ttl else None,
                            }
                        ),
                        encoding="utf-8",
                    )
                    tmp.replace(ruta)  # atómico: nadie lee un JSON a medio escribir
                except (OSError, ValueError, TypeError) as exc:
                    logger.warning("no se pudo cachear el nodo %s: %s", ns, exc)

    async def aset(self, keys: Mapping[FullKey, tuple[ValueT, int | None]]) -> None:
        self.set(keys)

    def clear(self, namespaces: Sequence[Namespace] | None = None) -> None:
        import shutil

        with self._lock:
            objetivos = (
                [self._raiz]
                if namespaces is None
                else [self._raiz.joinpath(*(_segmento(p) for p in ns)) for ns in namespaces]
            )
            for destino in objetivos:
                if destino.is_dir():
                    shutil.rmtree(destino, ignore_errors=True)

    async def aclear(self, namespaces: Sequence[Namespace] | None = None) -> None:
        self.clear(namespaces)
