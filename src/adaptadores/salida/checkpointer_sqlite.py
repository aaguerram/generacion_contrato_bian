"""Adaptador: checkpointer persistente de LangGraph sobre SQLite.

`durabilidad: sync|async` no sirve de nada con un checkpointer en memoria: guarda el estado de
cada superstep, sí, pero muere con el proceso — justo el caso que hay que cubrir, porque lo que
mata estas corridas es que el proceso termine a mitad (cuota agotada, Ctrl-C, una corrida de ~300 s
que se corta). Con SQLite el estado sobrevive y `thread_id` permite reanudar.

Qué cubre cada mecanismo, para no confundirlos:

- **Caché de nodos** (`CacheNodosArchivo`): re-ejecutar la MISMA corrida no vuelve a pagar las
  llamadas LLM ya hechas. Es lo que abarata repetir, y funciona aunque se pierda el estado.
- **Checkpointer**: el estado del grafo sobrevive al proceso, así que una corrida se puede
  *reanudar* donde estaba en vez de re-ejecutarse, y habilita `interrupt` / human-in-the-loop —
  que es lo que pide el estado `UNRESOLVED` "bloqueado para revisión humana" del dominio.

La base se **crea si no existe** (directorios incluidos) y `setup()` crea las tablas; es
idempotente, así que abrir una base ya poblada no la toca. Nunca se versiona: `.gitignore` excluye
`*.sqlite*` y `.cache/`, que es donde vive por defecto.

Si la base no se puede abrir (permisos, disco lleno, archivo corrupto) se degrada a `InMemorySaver`
**con aviso**, no en silencio: perder la persistencia cuesta una re-ejecución; tumbar la corrida
las cuesta todas.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)

# El estado del grafo lleva modelos del dominio (`EvaluacionCandidatoLLM`,
# `ServiceDomainsDeHistoria`, ...). LangGraph los serializa sin problema, pero al RELEERLOS avisa de
# que son tipos "no registrados" y anuncia que una versión futura los bloqueará: es decir, reanudar
# dejaría de funcionar tras una actualización. Declararlos permitidos lo arregla ahora y deja
# explícito qué se acepta deserializar: SOLO los modelos de nuestro dominio, que son código propio
# y versionado, nunca un módulo arbitrario.
#
# La lista se construye por reflexión sobre los dos módulos del dominio, no a mano: escribirla a
# mano significaría que cada modelo nuevo rompe el reanudar en silencio -- un tipo fuera de la
# lista NO falla, se deserializa como `dict`, y el error salta mucho más tarde y en otro sitio
# (medido: `AttributeError: 'dict' object has no attribute 'candidatos_directos'` dentro de
# `determinar_promociones`).


def _clases_del_dominio() -> list[type]:
    import inspect

    from pydantic import BaseModel

    from src.dominio import historias, modelos

    return [
        objeto
        for modulo in (historias, modelos)
        for _, objeto in inspect.getmembers(modulo, inspect.isclass)
        if issubclass(objeto, BaseModel) and objeto.__module__ == modulo.__name__
    ]


def _serde():
    """Serializador con los modelos del dominio declarados como permitidos (o el de siempre si
    esta versión de LangGraph todavía no acepta el parámetro)."""
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    try:
        return JsonPlusSerializer(allowed_msgpack_modules=_clases_del_dominio())
    except TypeError:  # pragma: no cover - versión anterior de langgraph
        return JsonPlusSerializer()


def crear_checkpointer(ruta: str | Path) -> BaseCheckpointSaver:
    """Checkpointer SQLite en `ruta`, creando la base y sus directorios si no existen."""
    destino = Path(ruta)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver

        destino.parent.mkdir(parents=True, exist_ok=True)
        existia = destino.is_file()
        # `check_same_thread=False`: LangGraph ejecuta las HU y los candidatos en varios hilos
        # (`max_concurrency`). `SqliteSaver` serializa sus escrituras con su propio lock, así que
        # compartir la conexión entre hilos es correcto; lo que no valdría es una conexión por
        # hilo escribiendo a la vez sobre el mismo archivo.
        conexion = sqlite3.connect(str(destino), check_same_thread=False)
        saver = SqliteSaver(conexion, serde=_serde())
        saver.setup()  # idempotente: crea las tablas solo si faltan
        logger.info(
            "checkpointer SQLite %s: %s", "abierto" if existia else "creado", destino
        )
        return saver
    except ImportError:
        logger.warning(
            "langgraph-checkpoint-sqlite no está instalado; la durabilidad se queda EN MEMORIA "
            "(no sobrevive al proceso). `pip install langgraph-checkpoint-sqlite` para activarla."
        )
    except (sqlite3.Error, OSError) as exc:
        logger.warning(
            "no se pudo abrir el checkpointer SQLite en %s (%s); durabilidad EN MEMORIA "
            "(no sobrevive al proceso)",
            destino,
            exc,
        )
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()
