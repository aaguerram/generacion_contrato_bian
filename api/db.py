"""Acceso a PostgreSQL. Un pool, un esquema, y nada más.

Por qué Postgres y no archivos: un intento se guarda, se ejecuta varias veces, se compara y se
consulta desde el navegador. Eso es estado compartido entre procesos (el servidor web y el hilo
que ejecuta el mapeo), y ahí un archivo JSON por intento se corrompe en cuanto dos escrituras se
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
CREATE TABLE IF NOT EXISTS intentos (
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
CREATE INDEX IF NOT EXISTS intentos_creado_en_idx ON intentos (creado_en DESC);
ALTER TABLE intentos ADD COLUMN IF NOT EXISTS corrida TEXT NOT NULL DEFAULT '';

-- Un registro por PASO del grafo. No es un log: son datos consultables (qué entró, qué salió,
-- qué modelo respondió, cuánto tardó), y son la memoria de la corrida cuando el proceso ya no
-- está. La interfaz los reproduce para pintar el flujo sin depender de haber estado conectada.
CREATE TABLE IF NOT EXISTS eventos_nodo (
    id            BIGSERIAL PRIMARY KEY,
    intento_id    TEXT        NOT NULL REFERENCES intentos(id) ON DELETE CASCADE,
    -- Una corrida es un intento EJECUTADO. El mismo intento se ejecuta varias veces y cada
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
CREATE INDEX IF NOT EXISTS eventos_nodo_intento_idx ON eventos_nodo (intento_id, id DESC);
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


def inicializar(intentos: int = 30, espera: float = 2.0) -> None:
    """Crea el esquema, esperando a que Postgres acepte conexiones.

    El reintento no es paranoia: en `docker compose` la API arranca a la vez que la base, y sin
    esta espera el primer despliegue falla siempre aunque todo esté bien configurado.
    """
    ultimo: Exception | None = None
    for intento in range(1, intentos + 1):
        try:
            with conexion() as con:
                con.execute(_ESQUEMA)
                _migrar_historias_a_lista(con)
                con.commit()
            return
        except Exception as exc:  # noqa: BLE001 - se reintenta a propósito
            ultimo = exc
            if intento == intentos:
                break
            time.sleep(espera)
    raise RuntimeError(f"No se pudo inicializar la base tras {intentos} intentos: {ultimo}")


def _migrar_historias_a_lista(con: Connection) -> None:
    """Convierte la columna `historias` de TEXT a JSONB partiendo el texto guardado.

    El formulario pasó de un `textarea` con todo pegado a una lista de historias con título y
    detalle. Los intentos ya guardados llevan el texto viejo, y tirarlos sería perder el trabajo
    del usuario por un cambio de interfaz: se parten UNA vez, con el mismo separador de entonces,
    y desde ahí viven como lista. Es idempotente: si la columna ya es JSONB no hace nada.
    """
    from psycopg.types.json import Jsonb

    from api.historias import separar_historias

    fila = con.execute(
        """SELECT data_type FROM information_schema.columns
           WHERE table_name='intentos' AND column_name='historias'"""
    ).fetchone()
    if not fila or fila["data_type"] == "jsonb":
        return

    viejos = con.execute("SELECT id, historias FROM intentos").fetchall()
    con.execute("ALTER TABLE intentos ALTER COLUMN historias DROP DEFAULT")
    con.execute("ALTER TABLE intentos ALTER COLUMN historias TYPE JSONB USING '[]'::jsonb")
    con.execute("ALTER TABLE intentos ALTER COLUMN historias SET DEFAULT '[]'::jsonb")
    for f in viejos:
        lista = [
            {"titulo": titulo, "detalle": cuerpo}
            for _, titulo, cuerpo in separar_historias(f["historias"] or "")
        ]
        con.execute("UPDATE intentos SET historias=%s WHERE id=%s", (Jsonb(lista), f["id"]))
    print(f"migrados {len(viejos)} intento(s) de historias en texto a lista")


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
