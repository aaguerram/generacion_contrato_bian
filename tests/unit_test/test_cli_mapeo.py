"""CLI mapear-historias: resolución del directorio de salida por ejecución."""

from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path

from src.adaptadores.entrada.cli_mapeo import _directorio_run


class TestDirectorioRun(unittest.TestCase):
    BASE = Path("salida")
    AHORA = dt.datetime(2026, 9, 10, 16, 45, 3)

    def test_subcarpeta_con_fecha_hora_por_defecto(self):
        d = _directorio_run(self.BASE, sin_timestamp=False, ahora=self.AHORA)
        self.assertEqual(d, self.BASE / "2026-09-10_16-45-03")

    def test_sin_timestamp_escribe_en_la_base(self):
        d = _directorio_run(self.BASE, sin_timestamp=True, ahora=self.AHORA)
        self.assertEqual(d, self.BASE)

    def test_dos_ejecuciones_distinto_segundo_no_colisionan(self):
        a = _directorio_run(self.BASE, sin_timestamp=False, ahora=self.AHORA)
        b = _directorio_run(self.BASE, sin_timestamp=False, ahora=self.AHORA.replace(second=4))
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
