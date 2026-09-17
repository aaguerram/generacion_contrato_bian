"""La jerarquía BIAN del prompt deja de ser una etiqueta sin definir.

Cada línea del catálogo de candidatos lleva `· Sales and Service > Customer Management`, y esa
jerarquía pesa un 10% del score de clasificación — pero hasta ahora el prompt nunca decía QUÉ
cubre cada Business Area o Business Domain. El landscape sí lo documenta; `CatalogoJson` lo
descartaba al aplanar.

Este test fija las dos decisiones:
  1. el parser arrastra la `documentation` de los DOS niveles de la jerarquía hasta cada SD;
  2. el prompt la manda DEDUPLICADA (5 áreas + 36 dominios ~ 3.3k tokens) y no inline por SD
     (~23k tokens): 8x más caro por exactamente la misma información.

Sin red y sin LLM.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.analista_mapeo_langchain import (
    formatear_catalogo,
    formatear_taxonomia,
)
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.prompts_mapeo import SPEC_CANDIDATOS
from unit_test.support import DOCS

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"


class TestTaxonomiaBian(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = CatalogoJson(CATALOGO).cargar()
        cls.taxonomia = formatear_taxonomia(cls.catalogo)

    def test_el_parser_arrastra_la_documentacion_de_los_dos_niveles(self):
        sin_area = [e.service_domain for e in self.catalogo if not e.business_area_doc]
        sin_dominio = [e.service_domain for e in self.catalogo if not e.business_domain_doc]
        self.assertEqual(sin_area, [])
        self.assertEqual(sin_dominio, [])

    def test_hay_una_linea_por_nodo_de_la_jerarquia_no_por_service_domain(self):
        areas = {e.business_area for e in self.catalogo}
        dominios = {(e.business_area, e.business_domain) for e in self.catalogo}
        self.assertEqual(len(self.taxonomia.splitlines()), len(areas) + len(dominios))
        self.assertLess(len(self.taxonomia.splitlines()), len(self.catalogo))

    def test_deduplicar_cuesta_una_fraccion_de_mandarla_inline(self):
        inline = sum(
            len(e.business_area_doc or "") + len(e.business_domain_doc or "") for e in self.catalogo
        )
        self.assertLess(len(self.taxonomia) * 4, inline)

    def test_el_prompt_de_candidatos_la_incluye_con_su_definicion(self):
        entrada = next(e for e in self.catalogo if e.business_area and e.business_area_doc)
        mensajes = SPEC_CANDIDATOS.template.format_messages(
            funcionalidad_macro="F",
            historia_archivo="HU.txt",
            historia_titulo="HU",
            historia_contenido="contenido",
            intencion_resumen="r",
            intencion_actions="a",
            intencion_objects="o",
            intencion_outcomes="s",
            intencion_dependencies="d",
            catalogo_total=len(self.catalogo),
            catalogo=formatear_catalogo(self.catalogo),
            taxonomia_bian=self.taxonomia,
        )
        humano = mensajes[-1].content
        self.assertIn("<taxonomia_bian>", humano)
        self.assertIn(f'Business Area "{entrada.business_area}"', humano)
        self.assertIn(" ".join(entrada.business_area_doc.split())[:60], humano)

    def test_la_version_del_prompt_subio_con_el_bloque_nuevo(self):
        self.assertEqual(SPEC_CANDIDATOS.version, "1.1.0")
        self.assertIn("{taxonomia_bian}", SPEC_CANDIDATOS.texto)


if __name__ == "__main__":
    unittest.main()
