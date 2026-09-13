"""Grafo completo sin API (proveedor 'fake'): camino exacto y camino RAG (léxico) + LLM."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.configuracion.contenedor import crear_caso_uso

from unit_test.support import config_test


class TestGrafo(unittest.TestCase):
    def test_camino_coincidencia_exacta(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = crear_caso_uso(config_test(), proveedor="fake")
            r = caso.ejecutar("issued device administration", tmp)

            self.assertTrue(r.existe)
            self.assertEqual(r.service_domain_canonico, "Issued Device Administration")
            self.assertEqual(r.metodo, "coincidencia_exacta")
            self.assertEqual(r.confianza, 1.0)
            self.assertEqual(r.candidatos, [])  # no se activó el RAG

            doc = json.loads((Path(tmp) / "validacion-service-domain.json").read_text(encoding="utf-8"))
            self.assertTrue(doc["existe"])
            self.assertIn("generado_en", doc)

    def test_banda_baja_determinista_sin_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = crear_caso_uso(config_test(), proveedor="fake")
            r = caso.ejecutar("Concepto Inventado Que No Existe 123", tmp)

            self.assertFalse(r.existe)
            self.assertEqual(r.metodo, "similitud_baja")
            self.assertGreater(len(r.candidatos), 0)
            self.assertIsNone(r.service_domain_canonico)

    def test_banda_alta_determinista_sin_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = crear_caso_uso(config_test(), proveedor="fake")
            r = caso.ejecutar("Issued Device Adminstration", tmp)  # typo, similitud ~0.98

            self.assertTrue(r.existe)
            self.assertEqual(r.service_domain_canonico, "Issued Device Administration")
            self.assertEqual(r.metodo, "similitud_alta")
            self.assertGreaterEqual(r.confianza, 0.90)

    def test_banda_gris_llama_al_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            caso = crear_caso_uso(
                config_test(validar_sd={"rag_umbral_bajo": 0.0, "rag_umbral_alto": 1.0}),
                proveedor="fake",
            )
            r = caso.ejecutar("saving", tmp)
            self.assertEqual(r.metodo, "rag_llm")  # lo decidió el LLM (fake -> existe=False)
            self.assertFalse(r.existe)


if __name__ == "__main__":
    unittest.main()
