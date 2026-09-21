"""Adaptador del `ObservadorEjecucionPort`: guarda cada paso del grafo en PostgreSQL.

Cumple el puerto que define la capa de aplicación. La regla que impone el puerto y que aquí se
respeta en todos los métodos: **observar no puede tumbar lo observado**. Si la base no responde,
la corrida sigue y lo único que se pierde es el detalle de ese paso; al revés sería cambiar una
corrida de media hora por un fallo de escritura.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from api import almacen
from api.serializacion import huella_del_nodo, resumir

logger = logging.getLogger("api.observador")


class ObservadorPostgres:
    """Un observador por CORRIDA. Escribe una fila por paso y sabe dónde hay que parar."""

    def __init__(self, intento_id: str, corrida: str, detener_en: str | None = None) -> None:
        self.intento_id = intento_id
        self.corrida = corrida
        self.detener_en = (detener_en or "").strip() or None
        self.detenido = False
        # nodo+instancia -> id de la fila abierta, para cerrarla al terminar.
        self._abiertos: dict[tuple[str, str], int] = {}

    # ── puerto ────────────────────────────────────────────────────────────
    def nodo_inicia(self, nodo: str, instancia: str, entrada: Mapping[str, Any]) -> None:
        try:
            fila = almacen.abrir_evento_nodo(
                self.intento_id, self.corrida, nodo, instancia, resumir(dict(entrada))
            )
            self._abiertos[(nodo, instancia)] = fila
        except Exception:
            logger.warning("no se pudo registrar la entrada al nodo %s", nodo, exc_info=True)

    def nodo_termina(self, nodo: str, instancia: str, salida: Any, ms: float) -> None:
        proveedor, modelo, prompt_id = huella_del_nodo(salida)
        self._cerrar(nodo, instancia, "completado", resumir(salida), ms, "", proveedor, modelo, prompt_id)

    def nodo_falla(self, nodo: str, instancia: str, error: str, ms: float) -> None:
        self._cerrar(nodo, instancia, "fallido", None, ms, error, "", "", "")

    def detener_tras(self, nodo: str) -> bool:
        if self.detener_en and nodo == self.detener_en:
            self.detenido = True
            return True
        return False

    # ── interno ───────────────────────────────────────────────────────────
    def _cerrar(
        self,
        nodo: str,
        instancia: str,
        estado: str,
        salida: Any,
        ms: float,
        error: str,
        proveedor: str,
        modelo: str,
        prompt_id: str,
    ) -> None:
        fila = self._abiertos.pop((nodo, instancia), None)
        if fila is None:
            # No debería pasar (todo cierre viene de una apertura), pero perder el paso entero
            # por eso sería peor que registrarlo sin su fila de apertura.
            logger.debug("cierre de %s sin apertura registrada", nodo)
            return
        try:
            almacen.cerrar_evento_nodo(fila, estado, salida, ms, error, proveedor, modelo, prompt_id)
        except Exception:
            logger.warning("no se pudo registrar la salida del nodo %s", nodo, exc_info=True)
