"""Checkpointer persistente: se crea si no existe, sobrevive al proceso y nunca se versiona.

`durabilidad: sync|async` con un checkpointer en memoria no cubre el caso que importa: lo que mata
estas corridas es que el PROCESO termine a mitad -cuota agotada, Ctrl-C, una corrida de ~300 s que
se corta-, y un saver en memoria muere con el. Con SQLite el estado sobrevive.

No se confunde con la cache de nodos, que resuelve otra cosa: la cache evita re-pagar las llamadas
LLM al RE-EJECUTAR; el checkpointer permite REANUDAR y habilita `interrupt`/human-in-the-loop, que
es lo que pide el estado `UNRESOLVED` "bloqueado para revision humana" del dominio.

Sin red y sin LLM.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from src.adaptadores.salida.checkpointer_sqlite import crear_checkpointer


class TestCrearCheckpointer(unittest.TestCase):
    def test_crea_la_base_y_sus_directorios_si_no_existen(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "no" / "existe" / "todavia" / "mapeo.sqlite"
            self.assertFalse(ruta.parent.exists())
            saver = crear_checkpointer(ruta)
            self.assertTrue(ruta.is_file(), "la base debe crearse")
            self.assertNotIsInstance(saver, InMemorySaver)

    def test_reabrir_una_base_existente_no_la_pisa(self):
        """`setup()` es idempotente: abrir una base ya poblada conserva lo que hay dentro."""
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mapeo.sqlite"
            crear_checkpointer(ruta)
            with sqlite3.connect(ruta) as con:
                con.execute("CREATE TABLE marca (x INTEGER)")
                con.execute("INSERT INTO marca VALUES (1)")
            crear_checkpointer(ruta)
            with sqlite3.connect(ruta) as con:
                self.assertEqual(con.execute("SELECT x FROM marca").fetchone()[0], 1)

    def test_el_estado_guardado_sobrevive_a_cerrar_el_saver(self):
        """Lo que distingue a este checkpointer del de memoria: otro saver lo vuelve a leer."""
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mapeo.sqlite"
            config = {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}}
            saver = crear_checkpointer(ruta)
            saver.put(
                config,
                {"v": 1, "id": "c1", "ts": "2026-09-15T00:00:00+00:00", "channel_values": {"x": 7}},
                {"source": "input", "step": 1},
                {},
            )
            otro = crear_checkpointer(ruta)  # simula OTRO proceso abriendo la misma base
            recuperado = otro.get(config)
            self.assertIsNotNone(recuperado, "el estado debe sobrevivir al saver que lo escribió")
            self.assertEqual(recuperado["channel_values"]["x"], 7)

    def test_una_ruta_imposible_degrada_a_memoria_con_aviso_en_vez_de_tumbar_la_corrida(self):
        """Perder la persistencia cuesta una re-ejecución; tumbar la corrida las cuesta todas."""
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "soy-un-archivo"
            archivo.write_text("x", encoding="utf-8")
            with self.assertLogs("src.adaptadores.salida.checkpointer_sqlite", "WARNING"):
                saver = crear_checkpointer(archivo / "imposible.sqlite")
            self.assertIsInstance(saver, InMemorySaver)


class TestNoSeVersiona(unittest.TestCase):
    def test_gitignore_excluye_las_bases_sqlite(self):
        raiz = Path(__file__).resolve().parents[2]
        ignore = (raiz / ".gitignore").read_text(encoding="utf-8")
        for patron in ("*.sqlite", "*.sqlite-wal", ".cache/"):
            self.assertIn(patron, ignore, f"falta {patron} en .gitignore")


if __name__ == "__main__":
    unittest.main()


class TestModelosDelDominioSeDeserializanEnteros(unittest.TestCase):
    """Un tipo fuera de la lista permitida NO falla: vuelve como `dict`, y el error salta mucho
    despues y en otro sitio.

    Medido al implementarlo: con una lista escrita a mano e incompleta, reanudar devolvia
    `ServiceDomainsDeHistoria` como `dict` y reventaba dentro de `determinar_promociones` con
    `AttributeError: 'dict' object has no attribute 'candidatos_directos'`. Por eso la lista se
    construye por reflexion sobre el dominio y por eso existe este test: un modelo nuevo no puede
    romper el reanudar en silencio.
    """

    def test_la_lista_cubre_todos_los_modelos_del_dominio(self):
        import inspect

        from pydantic import BaseModel

        from src.adaptadores.salida.checkpointer_sqlite import _clases_del_dominio
        from src.dominio import historias, modelos

        declarados = {c.__name__ for c in _clases_del_dominio()}
        for modulo in (historias, modelos):
            for nombre, objeto in inspect.getmembers(modulo, inspect.isclass):
                if issubclass(objeto, BaseModel) and objeto.__module__ == modulo.__name__:
                    self.assertIn(nombre, declarados, f"{nombre} no entraria entero al reanudar")

    def test_un_modelo_del_dominio_sobrevive_al_viaje_de_ida_y_vuelta(self):
        from src.adaptadores.salida.checkpointer_sqlite import _serde
        from src.dominio.historias import ServiceDomainsDeHistoria

        serde = _serde()
        original = ServiceDomainsDeHistoria()
        vuelta = serde.loads_typed(serde.dumps_typed(original))
        self.assertIsInstance(
            vuelta, ServiceDomainsDeHistoria, "volvio como dict: el reanudar se romperia"
        )
