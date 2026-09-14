"""El texto que se indexa para retrieval usa TODO lo que el Landscape sabe del Service Domain.

Antes se indexaba nombre + clasificación + rol recortado a 320 chars, y quedaban fuera
`examples_of_use`, `features`, `executive_summary` y `documentation`. Una historia de usuario rara
vez repite el rol formal de BIAN, pero sí menciona el escenario o una capacidad concreta: ese
vocabulario estaba sin indexar.

Sin red y sin LLM: lee el catálogo real de `docs/`.
"""

from __future__ import annotations

import statistics
import unittest

from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.dominio.modelos import _MAX_CHARS_INDICE, EntradaCatalogo
from unit_test.support import DOCS

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"


class TestTextoParaIndexar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entradas = CatalogoJson(CATALOGO).cargar()
        cls.por_nombre = {e.service_domain: e for e in cls.entradas}

    def test_incluye_el_vocabulario_de_negocio_y_no_solo_el_rol(self):
        e = self.por_nombre["Party Reference Data Directory"]
        texto = e.texto_para_indexar()
        for esperado in (
            e.service_domain,
            "Sales and Service",  # jerarquía
            "Catalog",  # functional pattern
            "pre-populate an application form",  # examples_of_use: escenario, no rol
        ):
            self.assertIn(esperado, texto, f"falta '{esperado}' en el texto indexado")

    def test_todos_los_sd_ganan_contexto(self):
        largos = [len(e.texto_para_indexar()) for e in self.entradas]
        self.assertGreater(
            statistics.median(largos),
            800,
            "el texto indexado sigue siendo tan corto como cuando solo traía nombre + rol",
        )

    def test_respeta_el_tope(self):
        self.assertLessEqual(
            max(len(e.texto_para_indexar()) for e in self.entradas), _MAX_CHARS_INDICE
        )

    def test_el_recorte_conserva_lo_discriminante(self):
        """Al recortar debe sobrar la documentación, nunca el nombre ni la clasificación."""
        e = self.por_nombre["Party Reference Data Directory"]
        corto = e.texto_para_indexar(max_chars=120)
        self.assertTrue(corto.startswith(e.service_domain))
        self.assertIn("Catalog", corto)

    def test_sd_sin_textos_opcionales_no_rompe(self):
        e = EntradaCatalogo(service_domain="X Domain", functional_pattern="Manage")
        self.assertEqual(e.texto_para_indexar(), "X Domain. Manage")


if __name__ == "__main__":
    unittest.main()
