"""Parser del PUML BOM BIAN -> ModeloBomPuml + adaptador que lee docs/bian-diagrams/puml-bom/."""

from __future__ import annotations

import unittest

from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml, slug_service_domain
from src.dominio.puml_bom import parsear_puml_bom
from unit_test.support import DOCS

_PUML = """\
@startuml
title Ejemplo - BIAN BOM UML
' Service Domain: Ejemplo Demo
' BIAN source: https://bian.org/servicelandscape-14-0-0/views/view_1.html
class "Token" as N1 {
  + Token Identification : Identifier
  + Token Type : TokenTypeValues[1..*]
}
class "Device" as N2 {
}
enum "TokenTypeValues" as N3 {
  Hardware
  Software
}
' Relationships
N2 "0..1" -- "0..*" N1
N1 <|-- N2
@enduml
"""


class TestParsearPuml(unittest.TestCase):
    def test_clases_atributos_enums_y_asociaciones(self):
        m = parsear_puml_bom(_PUML, slug="ejemplo-demo")
        self.assertEqual(m.service_domain, "Ejemplo Demo")
        self.assertTrue(m.source_url.startswith("https://bian.org/"))
        clases = {c.name: c for c in m.clases}
        self.assertEqual(
            [a.name for a in clases["Token"].attributes], ["Token Identification", "Token Type"]
        )
        self.assertEqual(clases["Token"].attributes[1].type, "TokenTypeValues")
        self.assertEqual(clases["Token"].attributes[1].cardinality, "1..*")
        self.assertEqual(
            {e.name: e.values for e in m.enums}, {"TokenTypeValues": ["Hardware", "Software"]}
        )
        tipos = {(a.tipo, a.origen, a.destino) for a in m.asociaciones}
        self.assertIn(("asociacion", "Device", "Token"), tipos)
        self.assertIn(("herencia", "Device", "Token"), tipos)  # N1 <|-- N2  => N2 hereda de N1


class TestCatalogoBomPuml(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(
            slug_service_domain("Transaction Authorization"), "transaction-authorization"
        )
        self.assertEqual(slug_service_domain("Párty Authentication"), "party-authentication")

    def test_lee_puml_real_de_docs(self):
        cat = CatalogoBomPuml(str(DOCS / "bian-diagrams" / "puml-bom"))
        m = cat.modelo_de("Transaction Authorization")
        self.assertIsNotNone(m)
        self.assertEqual(m.service_domain, "Transaction Authorization")
        self.assertTrue(m.clases)
        self.assertIsNone(cat.modelo_de("Inventado Que No Existe"))
        self.assertIn("transaction-authorization", cat.service_domains_con_bom())


if __name__ == "__main__":
    unittest.main()
