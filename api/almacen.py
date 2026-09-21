"""Intentos en PostgreSQL + el workspace en disco que el pipeline necesita.

Dos almacenamientos, cada uno con su razón:

  - **Postgres** guarda el intento entero (formulario, estado, resultado, comparación, log). Es
    estado compartido entre el servidor web y el hilo que ejecuta el mapeo, y tiene que sobrevivir
    a reinicios del contenedor.
  - **Un workspace en disco** (`API_WORKSPACE`, un volumen) materializa lo único que el caso de
    uso recibe como RUTAS: el directorio con una HU por archivo y el JSON de funcionalidad. Es
    efímero y reconstruible: se regenera desde Postgres antes de cada corrida. La interfaz se
    adapta al pipeline, no al revés.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from api import db
from api.historias import separar_historias
from api.modelos import (
    Funcionalidad,
    HistoriaDetectada,
    Intento,
    IntentoCrear,
    OpcionesEjecucion,
    ResumenComparacion,
)

_COLUMNAS = (
    "id, nombre, creado_en, actualizado_en, estado, historias, funcionalidad_label, "
    "funcionalidad_detalle, opciones, historias_detectadas, nombre_validacion, "
    "(validacion IS NOT NULL) AS tiene_validacion, iniciado_en, terminado_en, segundos, error, "
    "(resultado IS NOT NULL) AS tiene_resultado, comparacion"
)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def workspace() -> Path:
    p = Path(os.environ.get("API_WORKSPACE", str(Path(__file__).resolve().parents[1] / "api_datos")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def dir_intento(id_: str) -> Path:
    d = workspace() / id_
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── mapeo fila <-> modelo ───────────────────────────────────────────────────
def _a_modelo(f: dict[str, Any]) -> Intento:
    comp = f.get("comparacion")
    return Intento(
        id=f["id"],
        nombre=f["nombre"],
        creado_en=f["creado_en"],
        actualizado_en=f["actualizado_en"],
        estado=f["estado"],
        historias=f["historias"],
        funcionalidad=Funcionalidad(
            label=f["funcionalidad_label"], detalle=f["funcionalidad_detalle"]
        ),
        opciones=OpcionesEjecucion(**(f["opciones"] or {})),
        historias_detectadas=[HistoriaDetectada(**h) for h in (f["historias_detectadas"] or [])],
        tiene_validacion=bool(f.get("tiene_validacion")),
        nombre_validacion=f.get("nombre_validacion") or "",
        iniciado_en=f.get("iniciado_en"),
        terminado_en=f.get("terminado_en"),
        segundos=f.get("segundos"),
        error=f.get("error") or "",
        tiene_resultado=bool(f.get("tiene_resultado")),
        comparacion=ResumenComparacion(**comp) if comp else None,
    )


# ── escritura del workspace ─────────────────────────────────────────────────
def materializar(intento: Intento) -> list[HistoriaDetectada]:
    """Deja en disco lo que el CLI espera como rutas. Se regenera entero en cada llamada."""
    d = dir_intento(intento.id)
    hu = d / "hu"
    if hu.exists():
        shutil.rmtree(hu)  # re-guardar reemplaza las historias, nunca las acumula
    hu.mkdir(parents=True, exist_ok=True)
    detectadas: list[HistoriaDetectada] = []
    for archivo, titulo, contenido in separar_historias(intento.historias):
        (hu / archivo).write_text(contenido, encoding="utf-8")
        detectadas.append(
            HistoriaDetectada(archivo=archivo, titulo=titulo, caracteres=len(contenido))
        )
    (d / "funcionalidad.json").write_text(
        json.dumps(
            {
                "funcionalidad_macro": intento.funcionalidad.label,
                "detalle": intento.funcionalidad.detalle,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (d / "salida").mkdir(exist_ok=True)
    return detectadas


# ── operaciones ─────────────────────────────────────────────────────────────
def guardar_nuevo(datos: IntentoCrear) -> Intento:
    """Crea el intento. **Guardar no ejecuta nada.**"""
    id_ = uuid.uuid4().hex[:12]
    t = ahora()
    borrador = Intento(
        id=id_,
        nombre=datos.nombre or datos.funcionalidad.label,
        creado_en=t,
        actualizado_en=t,
        estado="guardado",
        historias=datos.historias,
        funcionalidad=datos.funcionalidad,
        opciones=datos.opciones,
    )
    detectadas = materializar(borrador)
    db.ejecutar(
        """INSERT INTO intentos (id, nombre, creado_en, actualizado_en, estado, historias,
               funcionalidad_label, funcionalidad_detalle, opciones, historias_detectadas)
           VALUES (%s,%s,%s,%s,'guardado',%s,%s,%s,%s,%s)""",
        (
            id_,
            borrador.nombre,
            t,
            t,
            datos.historias,
            datos.funcionalidad.label,
            datos.funcionalidad.detalle,
            Jsonb(datos.opciones.model_dump()),
            Jsonb([h.model_dump() for h in detectadas]),
        ),
    )
    return leer(id_)


def actualizar(id_: str, datos: IntentoCrear) -> Intento:
    """Reemplaza el formulario y vuelve a materializar el workspace."""
    actual = leer(id_)
    actual.historias = datos.historias
    actual.funcionalidad = datos.funcionalidad
    detectadas = materializar(actual)
    db.ejecutar(
        """UPDATE intentos SET nombre=%s, historias=%s, funcionalidad_label=%s,
               funcionalidad_detalle=%s, opciones=%s, historias_detectadas=%s, actualizado_en=%s
           WHERE id=%s""",
        (
            datos.nombre or datos.funcionalidad.label,
            datos.historias,
            datos.funcionalidad.label,
            datos.funcionalidad.detalle,
            Jsonb(datos.opciones.model_dump()),
            Jsonb([h.model_dump() for h in detectadas]),
            ahora(),
            id_,
        ),
    )
    return leer(id_)


def leer(id_: str) -> Intento:
    fila = db.uno(f"SELECT {_COLUMNAS} FROM intentos WHERE id=%s", (id_,))
    if fila is None:
        raise KeyError(id_)
    return _a_modelo(fila)


def listar() -> list[Intento]:
    return [
        _a_modelo(f)
        for f in db.consultar(f"SELECT {_COLUMNAS} FROM intentos ORDER BY creado_en DESC")
    ]


def borrar(id_: str) -> None:
    db.ejecutar("DELETE FROM intentos WHERE id=%s", (id_,))
    shutil.rmtree(workspace() / id_, ignore_errors=True)


def marcar_ejecutando(id_: str) -> Intento:
    db.ejecutar(
        """UPDATE intentos SET estado='ejecutando', iniciado_en=%s, terminado_en=NULL,
               segundos=NULL, error='', resultado=NULL, comparacion=NULL, log='' WHERE id=%s""",
        (ahora(), id_),
    )
    return leer(id_)


def marcar_completado(
    id_: str, segundos: float, resultado: dict[str, Any] | None, comparacion: dict[str, Any] | None
) -> None:
    db.ejecutar(
        """UPDATE intentos SET estado='completado', terminado_en=%s, segundos=%s, error='',
               resultado=%s, comparacion=%s, actualizado_en=%s WHERE id=%s""",
        (
            ahora(),
            round(segundos, 1),
            Jsonb(resultado) if resultado is not None else None,
            Jsonb(comparacion) if comparacion is not None else None,
            ahora(),
            id_,
        ),
    )


def marcar_fallido(id_: str, segundos: float, error: str) -> None:
    db.ejecutar(
        """UPDATE intentos SET estado='fallido', terminado_en=%s, segundos=%s, error=%s,
               actualizado_en=%s WHERE id=%s""",
        (ahora(), round(segundos, 1), error[:4000], ahora(), id_),
    )


def guardar_validacion(id_: str, nombre: str, contenido: dict[str, Any]) -> Intento:
    db.ejecutar(
        "UPDATE intentos SET validacion=%s, nombre_validacion=%s, actualizado_en=%s WHERE id=%s",
        (Jsonb(contenido), nombre, ahora(), id_),
    )
    return leer(id_)


def quitar_validacion(id_: str) -> Intento:
    db.ejecutar(
        "UPDATE intentos SET validacion=NULL, nombre_validacion='', actualizado_en=%s WHERE id=%s",
        (ahora(), id_),
    )
    return leer(id_)


def validacion(id_: str) -> dict[str, Any] | None:
    fila = db.uno("SELECT validacion FROM intentos WHERE id=%s", (id_,))
    return (fila or {}).get("validacion")


def resultado(id_: str) -> dict[str, Any] | None:
    fila = db.uno("SELECT resultado FROM intentos WHERE id=%s", (id_,))
    return (fila or {}).get("resultado")


def anexar_log(id_: str, texto: str) -> None:
    """El log se acumula en la fila: sobrevive al reinicio del contenedor y se ve desde la web."""
    db.ejecutar("UPDATE intentos SET log = log || %s WHERE id=%s", (texto, id_))


def log(id_: str) -> str:
    fila = db.uno("SELECT log FROM intentos WHERE id=%s", (id_,))
    return (fila or {}).get("log") or ""
