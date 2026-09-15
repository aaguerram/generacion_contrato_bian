"""El PUML BOM de un Service Domain se resuelve por la ruta que declara el landscape.

`bom_diagram.puml_path` es un dato publicado en
`docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`; el slug kebab-case del nombre es solo una
suposición sobre cómo nombró los archivos `scripts/svg_to_puml_bom/`. Hoy las dos coinciden en los
265 Service Domains que declaran diagrama — y por eso el cambio no mueve ningún resultado; lo que
compra es que una regeneración del landscape o de los diagramas que cambie el criterio de nombres
falle aquí en vez de dejar sin BOM al paquete de evidencia en silencio (`objeto_bom` a 0.0, sin
error ni log).

Sin red y sin LLM.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml, slug_service_domain
from src.adaptadores.salida.catalogo_json import CatalogoJson
from unit_test.support import DOCS, RAIZ

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"
PUML_BOM = DOCS / "bian-diagrams" / "puml-bom"


class TestCatalogoBomPuml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rutas = CatalogoJson(CATALOGO).rutas_bom_puml()

    def test_el_landscape_declara_la_ruta_de_la_mayoria_de_los_bom(self):
        self.assertEqual(len(self.rutas), 265)

    def test_toda_ruta_declarada_existe_en_docs(self):
        faltan = [sd for sd, ruta in self.rutas.items() if not (RAIZ / ruta).is_file()]
        self.assertEqual(faltan, [], f"{len(faltan)} SD declaran un PUML que no está en docs/")

    def test_la_convencion_de_nombres_sigue_coincidiendo_con_lo_declarado(self):
        """Si esto falla, el respaldo por slug dejó de encontrar el archivo correcto."""
        divergen = [
            f"{sd}: declarado={Path(ruta).stem} slug={slug_service_domain(sd)}"
            for sd, ruta in self.rutas.items()
            if Path(ruta).stem != slug_service_domain(sd)
        ]
        self.assertEqual(divergen, [], "\n".join(divergen))

    def test_ningun_sd_sin_ruta_declarada_tiene_un_puml_por_convencion(self):
        """El landscape no se guarda BOMs: los 76 SD sin `bom_diagram` tampoco tienen archivo."""
        crudo = json.loads(CATALOGO.read_text(encoding="utf-8"))

        def service_domains(nodos):
            for nodo in nodos:
                for hijo in nodo.get("business_domains", []):
                    yield from service_domains([hijo])
                yield from nodo.get("service_domains", [])

        archivos = {p.stem for p in PUML_BOM.glob("*.puml")}
        huerfanos = [
            sd["name"]
            for sd in service_domains(crudo["business_areas"])
            if sd["name"] not in self.rutas and slug_service_domain(sd["name"]) in archivos
        ]
        self.assertEqual(huerfanos, [])

    def test_resuelve_el_modelo_por_la_ruta_declarada(self):
        catalogo = CatalogoBomPuml(PUML_BOM, self.rutas)
        modelo = catalogo.modelo_de("Business Unit Management")
        self.assertIsNotNone(modelo)
        assert modelo is not None
        self.assertTrue(modelo.clases)
        self.assertEqual(
            modelo.source_url, "https://bian.org/servicelandscape-14-0-0/views/view_36397.html"
        )

    def test_una_ruta_declarada_rota_cae_en_la_convencion(self):
        catalogo = CatalogoBomPuml(PUML_BOM, {"Business Unit Management": "docs/no-existe.puml"})
        modelo = catalogo.modelo_de("Business Unit Management")
        self.assertIsNotNone(modelo)

    def test_un_sd_sin_bom_devuelve_none(self):
        catalogo = CatalogoBomPuml(PUML_BOM, self.rutas)
        self.assertIsNone(catalogo.modelo_de("Service Domain Que No Existe"))


if __name__ == "__main__":
    unittest.main()
