"""Lectura de HU (.txt) y de la funcionalidad macro (JSON) desde el sistema de ficheros (sin API)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.dominio.historias import FuncionalidadMacro


class TestLeerHistorias(unittest.TestCase):
    def test_lee_txt_ordenado_y_deriva_titulo(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "HU-Actualizar correo electrónico.txt").write_text("Como usuario...", encoding="utf-8")
            (d / "HU 794525 Actualizar número celular.txt").write_text("Como usuario...", encoding="utf-8")
            (d / "notas.docx").write_text("ignorar", encoding="utf-8")
            (d / "vacia.txt").write_text("   ", encoding="utf-8")

            historias = LectorHistoriasFilesystem().leer_historias(str(d))

        self.assertEqual([h.archivo for h in historias], [
            "HU 794525 Actualizar número celular.txt",
            "HU-Actualizar correo electrónico.txt",
        ])
        self.assertEqual(historias[0].titulo, "Actualizar número celular")
        self.assertEqual(historias[1].titulo, "Actualizar correo electrónico")

    def test_directorio_inexistente(self):
        with self.assertRaises(FileNotFoundError):
            LectorHistoriasFilesystem().leer_historias("/no/existe/jamas")


class TestLeerFuncionalidad(unittest.TestCase):
    def test_claves_canonicas(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "f.json"
            ruta.write_text(
                json.dumps({"funcionalidad_macro": "Datos personales", "detalle": "contexto"}),
                encoding="utf-8",
            )
            f = LectorHistoriasFilesystem().leer_funcionalidad(str(ruta))
        self.assertEqual(f, FuncionalidadMacro(funcionalidad_macro="Datos personales", detalle="contexto"))

    def test_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "f.json"
            ruta.write_text(
                json.dumps({"nombre": "X", "descripcion": "Y"}), encoding="utf-8"
            )
            f = LectorHistoriasFilesystem().leer_funcionalidad(str(ruta))
        self.assertEqual((f.funcionalidad_macro, f.detalle), ("X", "Y"))

    def test_sin_macro_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "f.json"
            ruta.write_text(json.dumps({"detalle": "solo detalle"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                LectorHistoriasFilesystem().leer_funcionalidad(str(ruta))


if __name__ == "__main__":
    unittest.main()
