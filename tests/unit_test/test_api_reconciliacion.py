"""Corridas que un reinicio del servidor dejó colgadas, sin tocar Postgres.

El mapeo corre en hilos del proceso de la API, así que un proceso recién arrancado no puede tener
ninguna corrida viva. Lo que se fija aquí es que el arranque lo asuma: que cierre lo que la base
diga `ejecutando`, que cierre también sus pasos a medias, y que no invente trabajo cuando no hay
nada colgado.
"""

from __future__ import annotations

import unittest
from typing import Any

from api import almacen


class TestReconciliarCorridasInterrumpidas(unittest.TestCase):
    def setUp(self) -> None:
        self.consultas: list[tuple[str, tuple[Any, ...]]] = []
        self.cerrados: list[tuple[str, str]] = []
        self.filas: list[dict[str, Any]] = []
        self._consultar = almacen.db.consultar
        self._cerrar = almacen.cerrar_pasos_huerfanos

        def _consultar_doble(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
            self.consultas.append((sql, params))
            return self.filas

        almacen.db.consultar = _consultar_doble
        almacen.cerrar_pasos_huerfanos = lambda corrida, motivo: self.cerrados.append(
            (corrida, motivo)
        )

    def tearDown(self) -> None:
        almacen.db.consultar = self._consultar
        almacen.cerrar_pasos_huerfanos = self._cerrar

    def test_marca_como_fallida_toda_generacion_que_diga_ejecutando(self) -> None:
        self.filas = [{"id": "abc", "corrida": "c1"}, {"id": "def", "corrida": "c2"}]

        self.assertEqual(almacen.reconciliar_corridas_interrumpidas(), 2)

        (sql, params) = self.consultas[0]
        self.assertIn("UPDATE generaciones SET estado='fallido'", sql)
        self.assertIn("WHERE estado='ejecutando'", sql)
        self.assertIn("reinici", params[1], "el error dice qué pasó, no solo que falló")

    def test_cierra_los_pasos_a_medias_de_cada_corrida(self) -> None:
        """Sin esto los nodos que estaban corriendo se pintan girando para siempre."""
        self.filas = [{"id": "abc", "corrida": "c1"}, {"id": "def", "corrida": "c2"}]

        almacen.reconciliar_corridas_interrumpidas()

        self.assertEqual([c for c, _ in self.cerrados], ["c1", "c2"])
        self.assertTrue(all("reinici" in motivo for _, motivo in self.cerrados))

    def test_una_generacion_sin_corrida_no_intenta_cerrar_pasos(self) -> None:
        """Quedó en `ejecutando` antes de abrir corrida: no hay pasos que cerrar."""
        self.filas = [{"id": "abc", "corrida": ""}]

        self.assertEqual(almacen.reconciliar_corridas_interrumpidas(), 1)
        self.assertEqual(self.cerrados, [])

    def test_sin_corridas_colgadas_no_hace_nada(self) -> None:
        self.filas = []

        self.assertEqual(almacen.reconciliar_corridas_interrumpidas(), 0)
        self.assertEqual(self.cerrados, [])


if __name__ == "__main__":
    unittest.main()
