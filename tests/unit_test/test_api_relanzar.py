"""Relanzar una generación: archivar la vieja y dejar una copia lista, sin tocar Postgres.

Lo que se fija aquí es lo que NO se ve en una corrida feliz: de qué fecha sale el sufijo, en qué
orden se escribe, y qué se niega a hacer. La base queda fuera con dobles; el SQL se prueba contra
la pila real, no aquí.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from api import almacen
from api.modelos import Funcionalidad, Generacion, HistoriaEntrada, OpcionesEjecucion


def _generacion(**campos: Any) -> Generacion:
    base = datetime(2026, 9, 22, 12, 53, 4, tzinfo=timezone.utc)
    datos: dict[str, Any] = {
        "id": "abc123",
        "nombre": "e2e001",
        "creado_en": base,
        "actualizado_en": base,
        "estado": "completado",
        "historias": [HistoriaEntrada(titulo="HU-01", detalle="Como usuario…")],
        "funcionalidad": Funcionalidad(label="Actualización de datos", detalle="…"),
        "opciones": OpcionesEjecucion(concurrencia=2),
        "iniciado_en": base + timedelta(minutes=11),
        "corrida": "corrida-vieja",
    }
    datos.update(campos)
    return Generacion(**datos)


class TestNombreArchivado(unittest.TestCase):
    def test_pega_la_fecha_de_la_corrida_al_nombre(self) -> None:
        cuando = datetime(2026, 9, 22, 13, 4, 37, tzinfo=timezone.utc).astimezone()
        self.assertEqual(
            almacen.nombre_archivado("e2e001", cuando),
            f"e2e001-{cuando.strftime('%d-%m-%Y_%H:%M:%S')}",
        )

    def test_el_nombre_original_se_conserva_entero(self) -> None:
        """El sufijo se AÑADE: el nombre con el que se reconoce la generación sigue delante."""
        salida = almacen.nombre_archivado("mapeo cuentas de menores", datetime.now(timezone.utc))
        self.assertTrue(salida.startswith("mapeo cuentas de menores-"))


class TestRelanzar(unittest.TestCase):
    """`relanzar` con la base sustituida por dobles: importa el orden y las negativas."""

    def setUp(self) -> None:
        self.escrituras: list[tuple[str, tuple[Any, ...]]] = []
        self.creadas: list[Any] = []
        self._originales = {
            n: getattr(almacen, n)
            for n in ("leer", "guardar_nuevo", "validacion", "guardar_validacion")
        }
        self._ejecutar = almacen.db.ejecutar
        almacen.db.ejecutar = lambda sql, params=(): self.escrituras.append((sql, params))
        almacen.validacion = lambda id_: None
        almacen.guardar_nuevo = self._guardar_nuevo

    def tearDown(self) -> None:
        for nombre, fn in self._originales.items():
            setattr(almacen, nombre, fn)
        almacen.db.ejecutar = self._ejecutar

    def _guardar_nuevo(self, datos: Any) -> Generacion:
        self.creadas.append(datos)
        return _generacion(id="copia1", estado="guardado", iniciado_en=None, corrida="")

    def test_la_copia_hereda_nombre_historias_funcionalidad_y_opciones(self) -> None:
        vieja = _generacion()
        almacen.leer = lambda id_: vieja

        copia = almacen.relanzar("abc123")

        self.assertEqual(copia.id, "copia1")
        self.assertEqual(copia.estado, "guardado", "la copia nace sin ejecutar")
        (datos,) = self.creadas
        self.assertEqual(datos.nombre, "e2e001", "el nombre limpio pasa a la copia")
        self.assertEqual(datos.historias, vieja.historias)
        self.assertEqual(datos.funcionalidad, vieja.funcionalidad)
        self.assertEqual(datos.opciones, vieja.opciones)

    def test_archiva_la_vieja_con_la_fecha_de_SU_corrida(self) -> None:
        """No con la de ahora: lo que identifica una versión archivada es cuándo se ejecutó."""
        vieja = _generacion()
        almacen.leer = lambda id_: vieja

        almacen.relanzar("abc123")

        (sql, params) = self.escrituras[-1]
        self.assertIn("UPDATE generaciones SET nombre=%s, relanzada_como=%s", sql)
        esperado = vieja.iniciado_en.astimezone().strftime("%d-%m-%Y_%H:%M:%S")
        self.assertEqual(params[0], f"e2e001-{esperado}")
        self.assertEqual(params[1], "copia1", "la vieja apunta a la copia que la reemplaza")
        self.assertEqual(params[3], "abc123")

    def test_la_copia_se_crea_antes_de_tocar_la_vieja(self) -> None:
        """Si la copia falla, la vieja no puede quedar renombrada apuntando a nada."""
        almacen.leer = lambda id_: _generacion()

        def _falla(datos: Any) -> Generacion:
            raise RuntimeError("sin espacio en disco")

        almacen.guardar_nuevo = _falla
        with self.assertRaises(RuntimeError):
            almacen.relanzar("abc123")
        self.assertEqual(self.escrituras, [], "no se escribió nada sobre la generación vieja")

    def test_una_generacion_ya_relanzada_no_se_relanza_otra_vez(self) -> None:
        almacen.leer = lambda id_: _generacion(relanzada_como="copia0")
        with self.assertRaises(almacen.YaRelanzada):
            almacen.relanzar("abc123")
        self.assertEqual(self.creadas, [])

    def test_una_generacion_sin_ejecutar_no_tiene_nada_que_archivar(self) -> None:
        almacen.leer = lambda id_: _generacion(estado="guardado", iniciado_en=None)
        with self.assertRaises(almacen.SinEjecutar):
            almacen.relanzar("abc123")
        self.assertEqual(self.creadas, [])

    def test_el_archivo_de_validacion_NO_viaja_a_la_copia(self) -> None:
        """Se sube a propósito en cada versión: heredarlo compararía contra algo no elegido."""
        almacen.leer = lambda id_: _generacion(tiene_validacion=True, nombre_validacion="val.json")
        almacen.validacion = lambda id_: {"historias": []}
        copiadas: list[tuple[str, str, dict[str, Any]]] = []
        almacen.guardar_validacion = lambda id_, nombre, contenido: (
            copiadas.append((id_, nombre, contenido)) or _generacion(id="copia1")
        )

        copia = almacen.relanzar("abc123")

        self.assertEqual(copiadas, [], "la copia nace sin archivo de validación")
        self.assertFalse(copia.tiene_validacion)
        self.assertEqual(copia.nombre_validacion, "")


if __name__ == "__main__":
    unittest.main()
