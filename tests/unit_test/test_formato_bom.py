"""`formatear_schemas_bom` truncaba en orden alfabético sin criterio de relevancia: en el caso real
`docs/bian-cache/release14.0.0/PartyReferenceDataDirectory.json` (67 schemas) eso dejaba fuera del
prompt tanto `Reference` (índice 63) como `Demographics` (índice 22) -exactamente los dos schemas
que decidían el caso-. `priorizar` corrige eso: los schemas relevantes nunca quedan fuera."""

from __future__ import annotations

import re
import unittest

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.formato_bom import formatear_schemas_bom

from unit_test.support import DOCS

_SD = "Party Reference Data Directory"


def _tiene_schema(texto: str, nombre: str) -> bool:
    """¿Aparece `nombre` como CABECERA de schema (línea `  Nombre: {...}`)? Un `in` plano también
    matcharía un campo compuesto que TERMINA en ese nombre (p.ej. "...AttorneyReference:Party"
    contiene "Reference:"), así que ancla al inicio de línea."""
    return re.search(rf"(?m)^  {re.escape(nombre)}: \{{", texto) is not None


class TestFormatearSchemasBomPriorizado(unittest.TestCase):
    def setUp(self):
        cache = CatalogoBianCache(str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
                                   "14.0.0", permitir_descargas=False)
        self.schemas = cache.schemas_detalle_de(_SD)
        self.assertGreater(len(self.schemas), 22, "el fixture debe tener más de 22 schemas para probar el corte")

    def test_sin_priorizar_el_corte_alfabetico_deja_fuera_reference_y_demographics(self):
        texto = formatear_schemas_bom(self.schemas)
        self.assertFalse(_tiene_schema(texto, "Reference"))
        self.assertFalse(_tiene_schema(texto, "Demographics"))

    def test_priorizar_reference_lo_incluye_pese_al_corte(self):
        texto = formatear_schemas_bom(self.schemas, priorizar={"reference"})
        self.assertTrue(_tiene_schema(texto, "Reference"))
        self.assertIn("CellPhoneNumber", texto)

    def test_priorizar_varios_los_incluye_a_todos(self):
        texto = formatear_schemas_bom(self.schemas, priorizar={"reference", "demographics"})
        self.assertTrue(_tiene_schema(texto, "Reference"))
        self.assertTrue(_tiene_schema(texto, "Demographics"))

    def test_priorizar_no_afecta_el_resultado_cuando_ya_caben_todos(self):
        pocos = self.schemas[:5]
        self.assertEqual(
            formatear_schemas_bom(pocos, limite=22),
            formatear_schemas_bom(pocos, limite=22, priorizar={"reference"}),
        )


if __name__ == "__main__":
    unittest.main()
