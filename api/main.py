"""API HTTP del generador de contratos BIAN. Arranca con:

    .venv/bin/uvicorn api.main:app --reload --port 8000

No impone NINGÚN límite de tiempo al mapeo: `POST /api/intentos/{id}/ejecutar` arranca la corrida
en un hilo y devuelve al instante; el cliente sigue el avance con `/estado`. Ver `api/ejecutor.py`.
"""

from __future__ import annotations

import json

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import almacen, db, ejecutor
from api.modelos import (
    EstadoEjecucion,
    Intento,
    IntentoCrear,
    ListaIntentos,
    Proveedores,
)

app = FastAPI(
    title="Generación de contratos BIAN — API",
    version="1.0.0",
    description=(
        "Capa de entrada HTTP del pipeline de mapeo de Historias de Usuario a BIAN Service "
        "Domains. Guarda intentos, los ejecuta sin límite de tiempo y los compara contra un "
        "archivo de validación."
    ),
)

# El frontend de Vite sirve en 5173; en producción se sirve desde el mismo origen y esto sobra.
@app.on_event("startup")
def _crear_esquema() -> None:
    """Crea las tablas al arrancar, esperando a que Postgres acepte conexiones (ver `db`)."""
    db.inicializar()


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _leer(id_: str) -> Intento:
    try:
        return almacen.leer(id_)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No existe el intento '{id_}'") from None


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


# ── Intentos ────────────────────────────────────────────────────────────────
@app.get("/api/intentos", response_model=ListaIntentos)
def listar_intentos() -> ListaIntentos:
    intentos = almacen.listar()
    return ListaIntentos(total=len(intentos), intentos=intentos)


@app.post("/api/intentos", response_model=Intento, status_code=201)
def crear_intento(datos: IntentoCrear) -> Intento:
    """Guarda el intento. **No ejecuta nada**: deja el formulario listo para pulsar Ejecutar."""
    return almacen.guardar_nuevo(datos)


@app.get("/api/intentos/{id_}", response_model=Intento)
def obtener_intento(id_: str) -> Intento:
    return _leer(id_)


@app.put("/api/intentos/{id_}", response_model=Intento)
def actualizar_intento(id_: str, datos: IntentoCrear) -> Intento:
    _leer(id_)
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="El intento se está ejecutando ahora mismo.")
    return almacen.actualizar(id_, datos)


@app.delete("/api/intentos/{id_}", status_code=204)
def borrar_intento(id_: str) -> None:
    _leer(id_)
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="El intento se está ejecutando ahora mismo.")
    almacen.borrar(id_)


# ── Validación ──────────────────────────────────────────────────────────────
@app.post("/api/intentos/{id_}/validacion", response_model=Intento)
async def subir_validacion(id_: str, archivo: UploadFile = File(...)) -> Intento:
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


@app.delete("/api/intentos/{id_}/validacion", response_model=Intento)
def quitar_validacion(id_: str) -> Intento:
    _leer(id_)
    return almacen.quitar_validacion(id_)


# ── Ejecución ───────────────────────────────────────────────────────────────
@app.post("/api/intentos/{id_}/ejecutar", response_model=Intento, status_code=202)
def ejecutar(id_: str) -> Intento:
    """Arranca el mapeo y **devuelve de inmediato** (202). La corrida no tiene límite de tiempo."""
    intento = _leer(id_)
    if not intento.historias_detectadas:
        raise HTTPException(status_code=400, detail="El intento no tiene ninguna Historia de Usuario.")
    if ejecutor.esta_ejecutando(id_):
        raise HTTPException(status_code=409, detail="Ya se está ejecutando.")
    return ejecutor.lanzar(id_)


@app.get("/api/intentos/{id_}/estado", response_model=EstadoEjecucion)
def estado(id_: str, desde: int = Query(default=0, ge=0)) -> EstadoEjecucion:
    """Avance de la corrida. `desde` evita reenviar las líneas de log ya vistas."""
    intento = _leer(id_)
    return EstadoEjecucion(
        id=id_,
        estado=intento.estado,
        segundos=intento.segundos,
        error=intento.error,
        lineas_log=ejecutor.lineas_log(id_, desde),
    )


@app.get("/api/intentos/{id_}/resultado")
def resultado(id_: str) -> JSONResponse:
    """El `mapeo-historias-service-domains.json` completo de la última corrida."""
    _leer(id_)
    datos = almacen.resultado(id_)
    if datos is None:
        raise HTTPException(status_code=404, detail="Este intento todavía no tiene resultado.")
    return JSONResponse(datos)


@app.get("/api/intentos/{id_}/validacion")
def obtener_validacion(id_: str) -> JSONResponse:
    _leer(id_)
    datos = almacen.validacion(id_)
    if datos is None:
        raise HTTPException(status_code=404, detail="Este intento no tiene archivo de validación.")
    return JSONResponse(datos)
