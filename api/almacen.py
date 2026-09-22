"""Generaciones en PostgreSQL + el workspace en disco que el pipeline necesita.

Dos almacenamientos, cada uno con su razón:

  - **Postgres** guarda la generación entera (formulario, estado, resultado, comparación, log). Es
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
from api.historias import archivos_de_historias
from api.modelos import (
    Funcionalidad,
    HistoriaDetectada,
    HistoriaEntrada,
    Generacion,
    GeneracionCrear,
    OpcionesEjecucion,
    ResumenComparacion,
)

_COLUMNAS = (
    "id, nombre, creado_en, actualizado_en, estado, historias, funcionalidad_label, "
    "funcionalidad_detalle, opciones, historias_detectadas, nombre_validacion, "
    "(validacion IS NOT NULL) AS tiene_validacion, iniciado_en, terminado_en, segundos, error, "
    "(resultado IS NOT NULL) AS tiene_resultado, comparacion, corrida"
)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def workspace() -> Path:
    p = Path(os.environ.get("API_WORKSPACE", str(Path(__file__).resolve().parents[1] / "api_datos")))
    p.mkdir(parents=True, exist_ok=True)
    return p


def dir_generacion(id_: str) -> Path:
    d = workspace() / id_
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── mapeo fila <-> modelo ───────────────────────────────────────────────────
def _a_modelo(f: dict[str, Any]) -> Generacion:
    comp = f.get("comparacion")
    return Generacion(
        id=f["id"],
        nombre=f["nombre"],
        creado_en=f["creado_en"],
        actualizado_en=f["actualizado_en"],
        estado=f["estado"],
        historias=[HistoriaEntrada(**h) for h in (f["historias"] or [])],
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
        corrida=f.get("corrida") or "",
    )


# ── escritura del workspace ─────────────────────────────────────────────────
def materializar(generacion: Generacion) -> list[HistoriaDetectada]:
    """Deja en disco lo que el CLI espera como rutas. Se regenera entero en cada llamada."""
    d = dir_generacion(generacion.id)
    hu = d / "hu"
    if hu.exists():
        shutil.rmtree(hu)  # re-guardar reemplaza las historias, nunca las acumula
    hu.mkdir(parents=True, exist_ok=True)
    detectadas: list[HistoriaDetectada] = []
    pares = [(h.titulo, h.detalle) for h in generacion.historias]
    for archivo, titulo, contenido in archivos_de_historias(pares):
        (hu / archivo).write_text(contenido, encoding="utf-8")
        detectadas.append(
            HistoriaDetectada(archivo=archivo, titulo=titulo, caracteres=len(contenido))
        )
    (d / "funcionalidad.json").write_text(
        json.dumps(
            {
                "funcionalidad_macro": generacion.funcionalidad.label,
                "detalle": generacion.funcionalidad.detalle,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (d / "salida").mkdir(exist_ok=True)
    return detectadas


# ── operaciones ─────────────────────────────────────────────────────────────
def guardar_nuevo(datos: GeneracionCrear) -> Generacion:
    """Crea la generación. **Guardar no ejecuta nada.**"""
    id_ = uuid.uuid4().hex[:12]
    t = ahora()
    borrador = Generacion(
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
        """INSERT INTO generaciones (id, nombre, creado_en, actualizado_en, estado, historias,
               funcionalidad_label, funcionalidad_detalle, opciones, historias_detectadas)
           VALUES (%s,%s,%s,%s,'guardado',%s,%s,%s,%s,%s)""",
        (
            id_,
            borrador.nombre,
            t,
            t,
            Jsonb([h.model_dump() for h in datos.historias]),
            datos.funcionalidad.label,
            datos.funcionalidad.detalle,
            Jsonb(datos.opciones.model_dump()),
            Jsonb([h.model_dump() for h in detectadas]),
        ),
    )
    return leer(id_)


def actualizar(id_: str, datos: GeneracionCrear) -> Generacion:
    """Reemplaza el formulario y vuelve a materializar el workspace."""
    actual = leer(id_)
    actual.historias = datos.historias
    actual.funcionalidad = datos.funcionalidad
    detectadas = materializar(actual)
    db.ejecutar(
        """UPDATE generaciones SET nombre=%s, historias=%s, funcionalidad_label=%s,
               funcionalidad_detalle=%s, opciones=%s, historias_detectadas=%s, actualizado_en=%s
           WHERE id=%s""",
        (
            datos.nombre or datos.funcionalidad.label,
            Jsonb([h.model_dump() for h in datos.historias]),
            datos.funcionalidad.label,
            datos.funcionalidad.detalle,
            Jsonb(datos.opciones.model_dump()),
            Jsonb([h.model_dump() for h in detectadas]),
            ahora(),
            id_,
        ),
    )
    return leer(id_)


def leer(id_: str) -> Generacion:
    fila = db.uno(f"SELECT {_COLUMNAS} FROM generaciones WHERE id=%s", (id_,))
    if fila is None:
        raise KeyError(id_)
    return _a_modelo(fila)


def listar() -> list[Generacion]:
    return [
        _a_modelo(f)
        for f in db.consultar(f"SELECT {_COLUMNAS} FROM generaciones ORDER BY creado_en DESC")
    ]


def borrar(id_: str) -> None:
    db.ejecutar("DELETE FROM generaciones WHERE id=%s", (id_,))
    shutil.rmtree(workspace() / id_, ignore_errors=True)


def marcar_ejecutando(id_: str, corrida: str) -> Generacion:
    """Abre una corrida nueva. Los pasos de la anterior NO se borran: son su historia.

    Lo que sí se limpia es el resultado, el log y la comparación, que describen la corrida
    anterior y confundirían con los de esta.
    """
    db.ejecutar(
        """UPDATE generaciones SET estado='ejecutando', iniciado_en=%s, terminado_en=NULL,
               segundos=NULL, error='', resultado=NULL, comparacion=NULL, log='', corrida=%s
           WHERE id=%s""",
        (ahora(), corrida, id_),
    )
    return leer(id_)


def marcar_completado(
    id_: str, segundos: float, resultado: dict[str, Any] | None, comparacion: dict[str, Any] | None
) -> None:
    db.ejecutar(
        """UPDATE generaciones SET estado='completado', terminado_en=%s, segundos=%s, error='',
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
        """UPDATE generaciones SET estado='fallido', terminado_en=%s, segundos=%s, error=%s,
               actualizado_en=%s WHERE id=%s""",
        (ahora(), round(segundos, 1), error[:4000], ahora(), id_),
    )


def guardar_validacion(id_: str, nombre: str, contenido: dict[str, Any]) -> Generacion:
    db.ejecutar(
        "UPDATE generaciones SET validacion=%s, nombre_validacion=%s, actualizado_en=%s WHERE id=%s",
        (Jsonb(contenido), nombre, ahora(), id_),
    )
    return leer(id_)


def quitar_validacion(id_: str) -> Generacion:
    db.ejecutar(
        "UPDATE generaciones SET validacion=NULL, nombre_validacion='', actualizado_en=%s WHERE id=%s",
        (ahora(), id_),
    )
    return leer(id_)


def validacion(id_: str) -> dict[str, Any] | None:
    fila = db.uno("SELECT validacion FROM generaciones WHERE id=%s", (id_,))
    return (fila or {}).get("validacion")


def resultado(id_: str) -> dict[str, Any] | None:
    fila = db.uno("SELECT resultado FROM generaciones WHERE id=%s", (id_,))
    return (fila or {}).get("resultado")


def anexar_log(id_: str, texto: str) -> None:
    """El log se acumula en la fila: sobrevive al reinicio del contenedor y se ve desde la web."""
    db.ejecutar("UPDATE generaciones SET log = log || %s WHERE id=%s", (texto, id_))


def log(id_: str) -> str:
    fila = db.uno("SELECT log FROM generaciones WHERE id=%s", (id_,))
    return (fila or {}).get("log") or ""


# ── eventos de nodo (el paso a paso de una corrida) ─────────────────────────
def abrir_evento_nodo(
    generacion_id: str, corrida: str, nodo: str, instancia: str, entrada: Any
) -> int:
    """Registra que el grafo ENTRÓ en un nodo y devuelve el id de la fila, para cerrarla luego.

    Se escribe al entrar y no al salir porque la interfaz tiene que poder pintar "este nodo está
    trabajando". Un nodo LLM puede tardar un minuto, y hasta ahora ese minuto era indistinguible
    de estar colgado.
    """
    fila = db.uno(
        """INSERT INTO eventos_nodo (generacion_id, corrida, nodo, instancia, estado, entrada,
               iniciado_en)
           VALUES (%s,%s,%s,%s,'en_curso',%s,%s) RETURNING id""",
        (generacion_id, corrida, nodo, instancia, Jsonb(entrada), ahora()),
        commit=True,
    )
    return int(fila["id"])


def cerrar_evento_nodo(
    fila: int,
    estado: str,
    salida: Any,
    ms: float,
    error: str = "",
    proveedor: str = "",
    modelo: str = "",
    prompt_id: str = "",
) -> None:
    db.ejecutar(
        """UPDATE eventos_nodo SET estado=%s, salida=%s, ms=%s, error=%s, proveedor=%s,
               modelo=%s, prompt_id=%s, terminado_en=%s WHERE id=%s""",
        (estado, Jsonb(salida) if salida is not None else None, ms, error, proveedor,
         modelo, prompt_id, ahora(), fila),
    )


def eventos_desde(corrida: str, desde: int = 0, limite: int = 500) -> list[dict[str, Any]]:
    """Los pasos de una corrida con id mayor que `desde`, en orden.

    Es la lectura que hace el canal de eventos, tanto en vivo como al reconectar: el cliente dice
    por dónde iba y se le manda lo que falta. Por eso el estado vive en la base y no solo en
    memoria — reconectar no puede costar la corrida.
    """
    return db.consultar(
        """SELECT id, nodo, instancia, estado, proveedor, modelo, prompt_id, ms,
                  iniciado_en, terminado_en, error
             FROM eventos_nodo WHERE corrida=%s AND id > %s ORDER BY id LIMIT %s""",
        (corrida, desde, limite),
    )


def evento_nodo(id_: int) -> dict[str, Any] | None:
    """Un paso CON sus datos de entrada y salida. Es lo que abre el modal de un nodo."""
    return db.uno(
        """SELECT id, generacion_id, corrida, nodo, instancia, estado, entrada, salida, proveedor,
                  modelo, prompt_id, ms, iniciado_en, terminado_en, error
             FROM eventos_nodo WHERE id=%s""",
        (id_,),
    )


def eventos_de_corrida(corrida: str) -> list[dict[str, Any]]:
    """Todos los pasos de una corrida con sus datos. Lo que se pinta al abrir una generación ya hecha."""
    return db.consultar(
        """SELECT id, nodo, instancia, estado, entrada, salida, proveedor, modelo, prompt_id, ms,
                  iniciado_en, terminado_en, error
             FROM eventos_nodo WHERE corrida=%s ORDER BY id""",
        (corrida,),
    )


def marcar_detenido(id_: str, segundos: float, nodo: str) -> None:
    """Una corrida cortada a petición NO es un fallo: se distingue en el estado."""
    db.ejecutar(
        """UPDATE generaciones SET estado='detenido', terminado_en=%s, segundos=%s,
               error=%s, actualizado_en=%s WHERE id=%s""",
        (ahora(), segundos, f"detenida a petición después del nodo '{nodo}'", ahora(), id_),
    )


def cerrar_pasos_huerfanos(corrida: str, motivo: str) -> int:
    """Cierra los pasos que se quedaron en `en_curso` cuando la corrida terminó.

    Al detener o al fallar, los nodos que estaban a mitad nunca reciben su aviso de salida, así
    que su fila se quedaría abierta para siempre y la interfaz los pintaría girando eternamente.
    No son un fallo del nodo: son trabajo interrumpido, y se marcan como tal.
    """
    filas = db.consultar(
        """UPDATE eventos_nodo SET estado='interrumpido', error=%s, terminado_en=%s
            WHERE corrida=%s AND estado='en_curso' RETURNING id""",
        (motivo, ahora(), corrida),
    )
    return len(filas)
