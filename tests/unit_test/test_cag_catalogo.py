"""CAG escalonado: el catálogo del prompt como fuente completa, no como índice.

A 341 Service Domains el catálogo entero cabe en contexto, así que el Recall@K de la recuperación
deja de ser una restricción y pasa a ser una elección. `cag_chars_por_sd` fija el escalón — y el
coste en tokens es la razón de que sea escalonado y no un interruptor:

    índice de completitud (rol 90)     ~10k tokens
    catálogo de candidatos (rol 240)   ~27k tokens   <- lo que ya se enviaba
    + CAG 300                          ~48k tokens
    + CAG 1200 (todo el negocio)       ~54k tokens

Este test fija: que apagado NO cambia ni un carácter del prompt de siempre, que encendido añade
el vocabulario de negocio (`examples_of_use`/`features`) respetando el presupuesto, y que los
escalones crecen de forma monótona y acotada.

Sin red y sin LLM.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.analista_mapeo_langchain import (
    _formatear_indice_global,
    formatear_catalogo,
)
from src.adaptadores.salida.catalogo_json import CatalogoJson
from unit_test.support import DOCS

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"


class TestCagCatalogo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = CatalogoJson(CATALOGO).cargar()
        cls.con_negocio = [e for e in cls.catalogo if e.examples_of_use or e.features]

    def test_apagado_es_exactamente_el_prompt_de_siempre(self):
        self.assertEqual(
            formatear_catalogo(self.catalogo, 240), formatear_catalogo(self.catalogo, 240, 0)
        )

    def test_encendido_anade_el_vocabulario_de_negocio(self):
        entrada = self.con_negocio[0]
        linea = formatear_catalogo([entrada], 240, 300)
        self.assertIn(" | ", linea)
        primera_palabra = (entrada.examples_of_use or entrada.features).split()[0]
        self.assertIn(primera_palabra, linea)

    def test_respeta_el_presupuesto_por_service_domain(self):
        for entrada in self.con_negocio[:50]:
            añadido = formatear_catalogo([entrada], 240, 100).split(" | ", 1)
            if len(añadido) == 2:
                self.assertLessEqual(len(añadido[1]), 104, entrada.service_domain)  # +"..."

    def test_los_escalones_crecen_y_se_estabilizan(self):
        tamanos = [len(formatear_catalogo(self.catalogo, 240, c)) for c in (0, 300, 600, 1200)]
        self.assertEqual(tamanos, sorted(tamanos))
        self.assertLess(tamanos[0], tamanos[1])
        # Con 1200 ya cabe todo lo que el landscape publica: subir más no añade nada.
        self.assertEqual(
            len(formatear_catalogo(self.catalogo, 240, 1200)),
            len(formatear_catalogo(self.catalogo, 240, 4000)),
        )

    def test_el_catalogo_completo_cabe_en_contexto(self):
        """La afirmación que sostiene todo el enfoque, medida y no supuesta."""
        tokens = len(formatear_catalogo(self.catalogo, 240, 1200)) // 4
        self.assertLess(tokens, 120_000, "ya no cabría en un modelo de 128k")

    def test_el_indice_de_completitud_tambien_escala(self):
        base = _formatear_indice_global(self.catalogo)
        cag = _formatear_indice_global(self.catalogo, chars_negocio=300)
        self.assertGreater(len(cag), len(base))
        self.assertEqual(base.count("\n"), cag.count("\n"), "mismo nº de SD, más contenido")


if __name__ == "__main__":
    unittest.main()
