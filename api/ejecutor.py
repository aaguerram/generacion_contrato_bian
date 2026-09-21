"""Ejecuta el mapeo SIN límite de tiempo, fuera del ciclo de la petición HTTP.

Una corrida real tarda de minutos a decenas de minutos: depende de cuántas HU, de cuántos
candidatos y, sobre todo, de qué proveedor del failover conteste. Hacer esperar a una petición
HTTP todo ese rato es pedirle un timeout a alguien -al navegador, a un proxy, al propio servidor-,
así que aquí NO se espera: `lanzar()` arranca un hilo y devuelve al instante, y el cliente
pregunta por el estado cuando quiera. El hilo no tiene deadline por diseño.

El mapeo se invoca exactamente como lo hace el CLI: `crear_caso_uso_mapeo(...).ejecutar(...)` con
rutas en disco. Este módulo no conoce ninguna regla de negocio del pipeline.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time
import json
import traceback
from collections import deque
from pathlib import Path

from api import almacen
from api.modelos import Intento

logger = logging.getLogger("api.ejecutor")

# Estado en memoria de las corridas vivas: id -> (hilo, log). El log también se escribe a disco,
# así que reiniciar el servidor pierde el streaming pero no el histórico.
_VIVAS: dict[str, "Corrida"] = {}
# RLock y no Lock: `lanzar()` ya tiene el cerrojo cuando llama a `esta_ejecutando()`, que vuelve a
# pedirlo. Con un Lock corriente eso es un interbloqueo del propio hilo -- y peor, el cerrojo queda
# tomado para siempre, así que TODA petición posterior que lo pida (`/estado`) se cuelga también.
_CERROJO = threading.RLock()
_MAX_LINEAS = 500


class _CapturaLog(logging.Handler):
    """Se engancha al logger raíz mientras dura UNA corrida y guarda sus líneas.

    Escribe a la fila del intento en Postgres por lotes: una sentencia UPDATE por línea de log
    ahogaría la base en una corrida que emite cientos, y el detalle por línea no vale ese coste.
    """

    def __init__(self, id_: str, destino: deque[str]) -> None:
        super().__init__(level=logging.INFO)
        self._id = id_
        self._destino = destino
        self._buffer: list[str] = []
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            linea = self.format(record)
        except Exception:  # pragma: no cover - un log roto no puede tumbar la corrida
            return
        self._destino.append(linea)
        self._buffer.append(linea)
        if len(self._buffer) >= 20:
            self.volcar()

    def volcar(self) -> None:
        if not self._buffer:
            return
        texto, self._buffer = "\n".join(self._buffer) + "\n", []
        try:
            almacen.anexar_log(self._id, texto)
        except Exception:  # pragma: no cover - perder log nunca puede tumbar la corrida
            pass


class Corrida:
    def __init__(self, id_: str) -> None:
        self.id = id_
        self.lineas: deque[str] = deque(maxlen=_MAX_LINEAS)
        self.hilo: threading.Thread | None = None


def corrida_viva(id_: str) -> Corrida | None:
    with _CERROJO:
        return _VIVAS.get(id_)


def esta_ejecutando(id_: str) -> bool:
    c = corrida_viva(id_)
    return bool(c and c.hilo and c.hilo.is_alive())


def _correr(intento: Intento) -> None:
    """Cuerpo del hilo. Cualquier error acaba en `estado='fallido'` con su traza, nunca se pierde."""
    # Import perezoso: cargar el pipeline entero (LangGraph, catálogos) cuesta segundos, y no debe
    # pagarse al arrancar el servidor ni en las peticiones que solo listan intentos.
    from src.configuracion.contenedor import crear_caso_uso_mapeo
    from src.configuracion.settings import cargar_settings

    d = almacen.dir_intento(intento.id)
    # El workspace se regenera SIEMPRE antes de correr: la fuente de verdad es Postgres, y el
    # contenedor puede haberse reiniciado desde que se guardó el intento.
    almacen.materializar(intento)
    corrida = corrida_viva(intento.id)
    captura = _CapturaLog(intento.id, corrida.lineas if corrida else deque())
    raiz = logging.getLogger()
    nivel_previo = raiz.level
    raiz.addHandler(captura)
    if nivel_previo > logging.INFO or nivel_previo == logging.NOTSET:
        raiz.setLevel(logging.INFO)

    inicio = time.perf_counter()
    try:
        cfg = cargar_settings()
        o = intento.opciones
        # Los mismos "pisa el config.yaml" que ofrece el CLI, sin tocar el archivo versionado.
        # `Config` y `MapearHistorias` son dataclasses FROZEN: se copian con `replace`, nunca se
        # mutan -- así dos corridas simultáneas con opciones distintas no se pisan la una a la otra.
        cambios = {
            k: v
            for k, v in (
                ("umbral_directo", o.umbral_directo),
                ("umbral_tentativo", o.umbral_tentativo),
                ("concurrencia", o.concurrencia),
                ("paso2_operaciones", False if o.sin_operaciones else None),
            )
            if v is not None
        }
        if cambios:
            cfg = dataclasses.replace(
                cfg, mapear_historias=dataclasses.replace(cfg.mapear_historias, **cambios)
            )

        caso = crear_caso_uso_mapeo(
            cfg, proveedor=o.proveedor or None, actualizar_cache_bian=o.actualizar_cache_bian
        )
        logger.info("intento %s: arranca el mapeo (sin límite de tiempo)", intento.id)
        resultado = caso.ejecutar(str(d / "hu"), str(d / "funcionalidad.json"), str(d / "salida"))
        segundos = time.perf_counter() - inicio

        ruta = _ruta_resultado_mas_reciente(d / "salida")
        datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta else None
        comparacion = _comparar_si_hay(intento.id, datos)
        almacen.marcar_completado(intento.id, segundos, datos, comparacion)
        logger.info(
            "intento %s: completado en %.1fs · %d historia(s)",
            intento.id, segundos, getattr(resultado, "total_historias", 0),
        )
    except Exception as exc:
        segundos = time.perf_counter() - inicio
        logger.error("intento %s: FALLÓ tras %.1fs — %s", intento.id, segundos, exc)
        try:
            almacen.marcar_fallido(intento.id, segundos, f"{type(exc).__name__}: {exc}")
        except Exception:  # pragma: no cover
            pass
        if corrida:
            corrida.lineas.append(traceback.format_exc())
    finally:
        raiz.removeHandler(captura)
        raiz.setLevel(nivel_previo)
        captura.volcar()


def _ruta_resultado_mas_reciente(salida: Path) -> Path | None:
    candidatos = sorted(
        salida.rglob("mapeo-historias-service-domains.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidatos[0] if candidatos else None


def _comparar_si_hay(id_: str, resultado: dict | None) -> dict | None:
    """Compara contra el archivo de validación, si el intento tiene uno."""
    esperado = almacen.validacion(id_)
    if not (resultado and esperado):
        return None
    from api.comparacion import comparar

    try:
        return comparar(resultado, esperado).model_dump()
    except Exception as exc:  # un archivo de validación inválido no invalida la corrida
        from api.modelos import ResumenComparacion

        return ResumenComparacion(
            disponible=False, detalle=f"No se pudo comparar: {type(exc).__name__}: {exc}"
        ).model_dump()


def lanzar(id_: str) -> Intento:
    """Arranca la corrida y devuelve AL INSTANTE. El cliente consulta `/estado` cuando quiera."""
    with _CERROJO:
        if esta_ejecutando(id_):
            return almacen.leer(id_)
        intento = almacen.marcar_ejecutando(id_)
        corrida = Corrida(id_)
        corrida.hilo = threading.Thread(
            target=_correr, args=(intento,), name=f"mapeo-{id_}", daemon=True
        )
        _VIVAS[id_] = corrida
        corrida.hilo.start()
        return intento


def lineas_log(id_: str, desde: int = 0) -> list[str]:
    """Las líneas de la corrida en curso; si no hay ninguna viva, las que quedaron en Postgres."""
    c = corrida_viva(id_)
    if c and c.lineas:
        return list(c.lineas)[desde:]
    return almacen.log(id_).splitlines()[desde:]
