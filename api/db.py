"""Acceso a PostgreSQL. Un pool, un esquema, y nada más.

Por qué Postgres y no archivos: una generación se guarda, se ejecuta varias veces, se compara y se
consulta desde el navegador. Eso es estado compartido entre procesos (el servidor web y el hilo
que ejecuta el mapeo), y ahí un archivo JSON por generación se corrompe en cuanto dos escrituras se
cruzan.

Lo que NO se guarda aquí: los archivos que el pipeline necesita en disco (el directorio de HU y el
JSON de funcionalidad). Esos se materializan en un workspace efímero justo antes de ejecutar,
porque el caso de uso los recibe como RUTAS y no vamos a cambiarlo por la interfaz.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS generaciones (
    id                    TEXT PRIMARY KEY,
    nombre                TEXT        NOT NULL DEFAULT '',
    creado_en             TIMESTAMPTZ NOT NULL,
    actualizado_en        TIMESTAMPTZ NOT NULL,
    estado                TEXT        NOT NULL DEFAULT 'guardado',
    historias             JSONB       NOT NULL DEFAULT '[]'::jsonb,
    funcionalidad_label   TEXT        NOT NULL,
    funcionalidad_detalle TEXT        NOT NULL DEFAULT '',
    opciones              JSONB       NOT NULL DEFAULT '{}'::jsonb,
    historias_detectadas  JSONB       NOT NULL DEFAULT '[]'::jsonb,
    nombre_validacion     TEXT        NOT NULL DEFAULT '',
    validacion            JSONB,
    iniciado_en           TIMESTAMPTZ,
    terminado_en          TIMESTAMPTZ,
    segundos              DOUBLE PRECISION,
    error                 TEXT        NOT NULL DEFAULT '',
    resultado             JSONB,
    comparacion           JSONB,
    log                   TEXT        NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS generaciones_creado_en_idx ON generaciones (creado_en DESC);
ALTER TABLE generaciones ADD COLUMN IF NOT EXISTS corrida TEXT NOT NULL DEFAULT '';
-- Id de la copia que la reemplaza. Una generación ya ejecutada no se vuelve a ejecutar encima de
-- su propio resultado: al relanzarla se archiva con la fecha de su corrida y el nombre queda
-- libre para la copia. Vacío = todavía es la versión viva de ese nombre.
ALTER TABLE generaciones ADD COLUMN IF NOT EXISTS relanzada_como TEXT NOT NULL DEFAULT '';

-- Un registro por PASO del grafo. No es un log: son datos consultables (qué entró, qué salió,
-- qué modelo respondió, cuánto tardó), y son la memoria de la corrida cuando el proceso ya no
-- está. La interfaz los reproduce para pintar el flujo sin depender de haber estado conectada.
CREATE TABLE IF NOT EXISTS eventos_nodo (
    id            BIGSERIAL PRIMARY KEY,
    generacion_id TEXT        NOT NULL REFERENCES generaciones(id) ON DELETE CASCADE,
    -- Una corrida es una generación EJECUTADA. La misma generación se ejecuta varias veces y cada
    -- corrida tiene su propia historia de nodos: sin esto se mezclarían.
    corrida       TEXT        NOT NULL,
    nodo          TEXT        NOT NULL,
    -- Distingue las repeticiones de un nodo en el abanico de `Send` (una por historia, grupo o
    -- candidato). Cadena vacía = el nodo corre una sola vez.
    instancia     TEXT        NOT NULL DEFAULT '',
    estado        TEXT        NOT NULL,         -- en_curso | completado | fallido
    entrada       JSONB,
    salida        JSONB,
    proveedor     TEXT        NOT NULL DEFAULT '',
    modelo        TEXT        NOT NULL DEFAULT '',
    prompt_id     TEXT        NOT NULL DEFAULT '',
    ms            DOUBLE PRECISION,
    iniciado_en   TIMESTAMPTZ NOT NULL,
    terminado_en  TIMESTAMPTZ,
    error         TEXT        NOT NULL DEFAULT ''
);
-- El índice es por (corrida, id): así se lee "dame lo nuevo desde el evento N" de una corrida sin
-- recorrer la tabla, que es exactamente lo que hace la reconexión del canal de eventos.
CREATE INDEX IF NOT EXISTS eventos_nodo_corrida_idx ON eventos_nodo (corrida, id);
CREATE INDEX IF NOT EXISTS eventos_nodo_generacion_idx ON eventos_nodo (generacion_id, id DESC);
"""

_pool: ConnectionPool | None = None


def dsn() -> str:
    return os.environ.get(
        "DATABASE_URL", "postgresql://contratos:contratos@localhost:5434/contratos"
    )


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(dsn(), min_size=1, max_size=8, kwargs={"row_factory": dict_row})
    return _pool


@contextmanager
def conexion() -> Iterator[Connection]:
    with pool().connection() as con:
        yield con


def inicializar(reintentos: int = 30, espera: float = 2.0) -> None:
    """Crea el esquema, esperando a que Postgres acepte conexiones.

    El reintento no es paranoia: en `docker compose` la API arranca a la vez que la base, y sin
    esta espera el primer despliegue falla siempre aunque todo esté bien configurado.
    """
    ultimo: Exception | None = None
    for reintento in range(1, reintentos + 1):
        try:
            with conexion() as con:
                _renombrar_intentos_a_generaciones(con)
                con.execute(_ESQUEMA)
                _migrar_historias_a_lista(con)
                con.commit()
            return
        except Exception as exc:  # noqa: BLE001 - se reintenta a propósito
            ultimo = exc
            if reintento == reintentos:
                break
            time.sleep(espera)
    raise RuntimeError(f"No se pudo inicializar la base tras {reintentos} intentos: {ultimo}")


def _renombrar_intentos_a_generaciones(con: Connection) -> None:
    """Renombra el esquema viejo, de cuando una generación se llamaba "intento".

    Corre ANTES de `_ESQUEMA`, y ese orden es lo único importante aquí: el `CREATE TABLE IF NOT
    EXISTS generaciones` de después no falla si la tabla no existe, la crea VACÍA, y la tabla
    `intentos` con el trabajo del usuario se quedaría al lado sin que nada la leyera.

    Es idempotente: en una base nueva no hay nada que renombrar y en una ya migrada tampoco.
    Lo que NO se renombra son las restricciones (`intentos_pkey`,
    `eventos_nodo_intento_id_fkey`): su nombre no lo usa ninguna consulta, así que cambiarlo solo
    añadiría SQL condicional para que una base migrada y una nueva se vieran igual por dentro.
    """
    con.execute("ALTER TABLE IF EXISTS intentos RENAME TO generaciones")
    con.execute("ALTER INDEX IF EXISTS intentos_creado_en_idx RENAME TO generaciones_creado_en_idx")
    con.execute(
        "ALTER INDEX IF EXISTS eventos_nodo_intento_idx RENAME TO eventos_nodo_generacion_idx"
    )
    # `RENAME COLUMN` no admite `IF EXISTS` para la columna, así que se pregunta primero.
    columna = con.execute(
        """SELECT 1 FROM information_schema.columns
           WHERE table_name='eventos_nodo' AND column_name='intento_id'"""
    ).fetchone()
    if columna:
        con.execute("ALTER TABLE eventos_nodo RENAME COLUMN intento_id TO generacion_id")
        print("migrado el esquema: intentos -> generaciones")


def _migrar_historias_a_lista(con: Connection) -> None:
    """Convierte la columna `historias` de TEXT a JSONB partiendo el texto guardado.

    El formulario pasó de un `textarea` con todo pegado a una lista de historias con título y
    detalle. Las generaciones ya guardadas llevan el texto viejo, y tirarlas sería perder el trabajo
    del usuario por un cambio de interfaz: se parten UNA vez, con el mismo separador de entonces,
    y desde ahí viven como lista. Es idempotente: si la columna ya es JSONB no hace nada.
    """
    from psycopg.types.json import Jsonb

    from api.historias import separar_historias

    fila = con.execute(
        """SELECT data_type FROM information_schema.columns
           WHERE table_name='generaciones' AND column_name='historias'"""
    ).fetchone()
    if not fila or fila["data_type"] == "jsonb":
        return

    viejos = con.execute("SELECT id, historias FROM generaciones").fetchall()
    con.execute("ALTER TABLE generaciones ALTER COLUMN historias DROP DEFAULT")
    con.execute("ALTER TABLE generaciones ALTER COLUMN historias TYPE JSONB USING '[]'::jsonb")
    con.execute("ALTER TABLE generaciones ALTER COLUMN historias SET DEFAULT '[]'::jsonb")
    for f in viejos:
        lista = [
            {"titulo": titulo, "detalle": cuerpo}
            for _, titulo, cuerpo in separar_historias(f["historias"] or "")
        ]
        con.execute("UPDATE generaciones SET historias=%s WHERE id=%s", (Jsonb(lista), f["id"]))
    print(f"migradas {len(viejos)} generación(es) de historias en texto a lista")


def consultar(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Varias filas. Vale también para un UPDATE ... RETURNING: la salida del `with` confirma."""
    with conexion() as con:
        return con.execute(sql, params).fetchall()


def uno(sql: str, params: tuple[Any, ...] = (), commit: bool = False) -> dict[str, Any] | None:
    """Una fila. `commit=True` para un INSERT ... RETURNING, que escribe y devuelve a la vez."""
    with conexion() as con:
        fila = con.execute(sql, params).fetchone()
        if commit:
            con.commit()
        return fila


def ejecutar(sql: str, params: tuple[Any, ...] = ()) -> None:
    with conexion() as con:
        con.execute(sql, params)
        con.commit()
