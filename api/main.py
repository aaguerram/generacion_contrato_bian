"""API HTTP del generador de contratos BIAN. Arranca con:

    .venv/bin/uvicorn api.main:app --reload --port 8000

No impone NINGÚN límite de tiempo al mapeo: `POST /api/generaciones/{id}/ejecutar` arranca la corrida
en un hilo y devuelve al instante; el cliente sigue el avance con `/estado`. Ver `api/ejecutor.py`.
"""

from __future__ import annotations

import json
import logging

import asyncio

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from api import almacen, db, ejecutor, grafo as grafo_mod
from api.modelos import (
    DetallePaso,
    EstadoEjecucion,
    Grafo,
    Generacion,
    GeneracionCrear,
    ListaGeneraciones,
    PasoNodo,
    Proveedores,
)

logger = logging.getLogger("api.main")

app = FastAPI(
    title="Generación de contratos BIAN — API",
    version="1.0.0",
    description=(
        "Capa de entrada HTTP del pipeline de mapeo de Historias de Usuario a BIAN Service "
        "Domains. Guarda generaciones, las ejecuta sin límite de tiempo y las compara contra un "
        "archivo de validación."
    ),
)

@app.on_event("startup")
def _crear_esquema() -> None:
    """Prepara la base al arrancar: esquema primero (ver `db`), corridas colgadas después.

    El orden importa: la reconciliación escribe sobre `generaciones`, que el esquema acaba de
    crear o migrar.
    """
    db.inicializar()
    colgadas = almacen.reconciliar_corridas_interrumpidas()
    if colgadas:
        logger.warning(
            "%d corrida(s) quedaron a medias en el reinicio anterior y se marcaron como fallidas",
            colgadas,
        )


# El frontend de Vite sirve en 5173; en producción se sirve desde el mismo origen y esto sobra.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _leer(id_: str) -> Generacion:
    try:
        return almacen.leer(id_)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No existe la generación '{id_}'") from None


@app.get("/api/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


@app.get("/api/proveedores", response_model=Proveedores)
def proveedores() -> Proveedores:
    """Los proveedores LLM que el formulario puede ofrecer, leídos de la configuración real."""
    from src.adaptadores.salida.llm.factory import estrategias_disponibles
    from src.configuracion.settings import cargar_settings

    try:
        cadena = list(cargar_settings().routing.llm_priority)
    except Exception:
        cadena = []
    return Proveedores(disponibles=sorted(estrategias_disponibles()), cadena_por_defecto=cadena)


# ── Generaciones ────────────────────────────────────────────────────────────────
@app.get("/api/generaciones", response_model=ListaGeneraciones)
def listar_generaciones() -> ListaGeneraciones:
    generaciones = almacen.listar()
    return ListaGeneraciones(total=len(generaciones), generaciones=generaciones)


@app.post("/api/generaciones", response_model=Generacion, status_code=201)
def crear_generacion(datos: GeneracionCrear) -> Generacion:
    """Guarda la generación. **No ejecuta nada**: deja el formulario listo para pulsar Ejecutar."""
    return almacen.guardar_nuevo(datos)


@app.get("/api/generaciones/{id_}", response_model=Generacion)
def obtener_generacion(id_: str) -> Generacion:
    return _leer(id_)


@app.put("/api/generaciones/{id_}", response_model=Generacion)
def actualizar_generacion(id_: str, datos: GeneracionCrear) -> Generacion:
    _leer(id_)
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="La generación se está ejecutando ahora mismo.")
    return almacen.actualizar(id_, datos)


@app.delete("/api/generaciones/{id_}", status_code=204)
def borrar_generacion(id_: str) -> None:
    _leer(id_)
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="La generación se está ejecutando ahora mismo.")
    almacen.borrar(id_)


# ── Validación ──────────────────────────────────────────────────────────────
@app.post("/api/generaciones/{id_}/validacion", response_model=Generacion)
async def subir_validacion(id_: str, archivo: UploadFile = File(...)) -> Generacion:
    """Archivo con el resultado esperado, para comparar con lo que produzca la ejecución."""
    _leer(id_)
    crudo = await archivo.read()
    try:
        contenido = json.loads(crudo.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"El archivo de validación no es un JSON válido: {exc}"
        ) from None
    if not isinstance(contenido, dict):
        raise HTTPException(status_code=400, detail="Se esperaba un objeto JSON en la raíz.")
    return almacen.guardar_validacion(id_, archivo.filename or "validacion.json", contenido)


@app.delete("/api/generaciones/{id_}/validacion", response_model=Generacion)
def quitar_validacion(id_: str) -> Generacion:
    _leer(id_)
    return almacen.quitar_validacion(id_)


# ── Ejecución ───────────────────────────────────────────────────────────────
@app.post("/api/generaciones/{id_}/ejecutar", response_model=Generacion, status_code=202)
def ejecutar(id_: str) -> Generacion:
    """Arranca el mapeo y **devuelve de inmediato** (202). La corrida no tiene límite de tiempo."""
    generacion = _leer(id_)
    if not generacion.historias_detectadas:
        raise HTTPException(status_code=400, detail="La generación no tiene ninguna Historia de Usuario.")
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="Ya se está ejecutando.")
    return ejecutor.lanzar(id_)


@app.post("/api/generaciones/{id_}/relanzar", response_model=Generacion, status_code=201)
def relanzar(id_: str) -> Generacion:
    """Archiva esta generación y devuelve la COPIA que hereda su nombre, lista para ejecutar.

    No ejecuta nada: deja preparada la siguiente versión. Quien la llama navega a la copia, que
    es la que ya tiene el botón de ejecutar.
    """
    _leer(id_)
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="La generación se está ejecutando ahora mismo.")
    try:
        return almacen.relanzar(id_)
    except almacen.YaRelanzada:
        raise HTTPException(
            status_code=409,
            detail="Esta generación ya se relanzó: su nombre lo tiene la copia.",
        ) from None
    except almacen.SinEjecutar:
        raise HTTPException(
            status_code=409,
            detail="Todavía no se ha ejecutado: no hay ninguna corrida que archivar.",
        ) from None


@app.get("/api/generaciones/{id_}/estado", response_model=EstadoEjecucion)
def estado(id_: str, desde: int = Query(default=0, ge=0)) -> EstadoEjecucion:
    """Avance de la corrida. `desde` evita reenviar las líneas de log ya vistas."""
    generacion = _leer(id_)
    return EstadoEjecucion(
        id=id_,
        estado=generacion.estado,
        segundos=generacion.segundos,
        error=generacion.error,
        lineas_log=ejecutor.lineas_log(id_, desde),
    )


@app.get("/api/generaciones/{id_}/resultado")
def resultado(id_: str) -> JSONResponse:
    """El `mapeo-historias-service-domains.json` completo de la última corrida."""
    _leer(id_)
    datos = almacen.resultado(id_)
    if datos is None:
        raise HTTPException(status_code=404, detail="Esta generación todavía no tiene resultado.")
    return JSONResponse(datos)


@app.get("/api/generaciones/{id_}/validacion")
def obtener_validacion(id_: str) -> JSONResponse:
    _leer(id_)
    datos = almacen.validacion(id_)
    if datos is None:
        raise HTTPException(status_code=404, detail="Esta generación no tiene archivo de validación.")
    return JSONResponse(datos)


# ── el flujo del grafo, paso a paso ─────────────────────────────────────────
@app.get("/api/grafo", response_model=Grafo)
def grafo() -> Grafo:
    """La topología del flujo, leída del grafo real de LangGraph. No cambia entre corridas."""
    return grafo_mod.topologia()


@app.get("/api/generaciones/{id_}/pasos", response_model=list[PasoNodo])
def pasos(id_: str) -> list[PasoNodo]:
    """Los pasos ya registrados de la última corrida, SIN sus datos.

    Sin datos a propósito: es lo que se pide al abrir la pantalla para pintar qué nodos se
    encendieron, y mandar la entrada y la salida de todos pesaría megabytes para dibujar colores.
    El detalle se pide por paso, cuando alguien abre uno.
    """
    generacion = _leer(id_)
    if not generacion.corrida:
        return []
    return [PasoNodo(**f) for f in almacen.eventos_desde(generacion.corrida, 0, limite=5000)]


@app.get("/api/pasos/{paso_id}", response_model=DetallePaso)
def paso(paso_id: int) -> DetallePaso:
    """Un paso CON su entrada y su salida. Es lo que abre el modal de un nodo."""
    fila = almacen.evento_nodo(paso_id)
    if fila is None:
        raise HTTPException(status_code=404, detail=f"No existe el paso {paso_id}")
    fila.pop("generacion_id", None)
    fila.pop("corrida", None)
    return DetallePaso(**fila)


def _sse(evento: str, datos: str, id_: int | None = None) -> str:
    """Un mensaje del canal de eventos. El formato es texto plano con líneas `campo: valor`."""
    trozos = []
    if id_ is not None:
        trozos.append(f"id: {id_}")
    trozos.append(f"event: {evento}")
    # Cada salto de línea del cuerpo va en su propia línea `data:`, o el mensaje se corta ahí.
    for linea in datos.splitlines() or [""]:
        trozos.append(f"data: {linea}")
    return "\n".join(trozos) + "\n\n"


@app.get("/api/generaciones/{id_}/eventos")
async def eventos(id_: str, desde: int = Query(default=0, ge=0)) -> StreamingResponse:
    """Canal de eventos del servidor con el avance del grafo, un mensaje por paso.

    Es un canal de UNA sola dirección -- el servidor cuenta, el cliente escucha --, así que no
    hace falta un socket bidireccional: menos superficie expuesta y reconexión automática de
    serie. `desde` es el último paso que el cliente ya vio; al reconectar se le manda lo que
    falta desde la base, no desde memoria, así que perder la conexión no cuesta la corrida.
    """
    generacion = _leer(id_)
    corrida = generacion.corrida

    async def flujo():
        import json as _json

        ultimo = desde
        if not corrida:
            yield _sse("fin", _json.dumps({"motivo": "sin corrida"}))
            return

        silencio = 0.0
        while True:
            filas = await run_in_threadpool(almacen.eventos_desde, corrida, ultimo)
            for f in filas:
                ultimo = int(f["id"])
                yield _sse("paso", _json.dumps(f, default=str), ultimo)

            actual = await run_in_threadpool(almacen.leer, id_)
            if actual.corrida != corrida:
                # Alguien relanzó la generación: esta corrida ya no es la vigente y el cliente debe
                # reconectar contra la nueva en vez de seguir escuchando una muerta.
                yield _sse("fin", _json.dumps({"motivo": "corrida reemplazada"}))
                return
            if actual.estado != "ejecutando" and not filas:
                yield _sse(
                    "fin",
                    _json.dumps({"motivo": actual.estado, "segundos": actual.segundos}),
                )
                return

            await asyncio.sleep(0.25)
            silencio += 0.25
            if silencio >= 15:
                # Comentario de mantenimiento: hay proxies que cierran una conexión en silencio.
                silencio = 0.0
                yield ": latido\n\n"

    return StreamingResponse(
        flujo(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx bufferiza por defecto y se tragaría los eventos hasta cerrar la respuesta,
            # que es justo lo contrario de lo que hace falta aquí.
            "X-Accel-Buffering": "no",
        },
    )
