"""Regresión directa del bug: el bloque `<operaciones_disponibles>` que arma `_formatear()` solo
mostraba `resp=<schema>` (el nombre), nunca sus campos -el LLM elegía `RetrieveDemographics` por
parecido de nombre con "datos personales" sin haber visto que ese schema no tiene ningún campo de
contacto, mientras `Reference` (el candidato correcto) quedaba fuera del bloque de schemas truncado
en `formatear_schemas_bom`. Ahora cada operación trae sus propios `campos_respuesta` inline."""

from __future__ import annotations

import unittest

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.mapeador_operaciones_langchain import _formatear
from src.dominio.historias import EvidenciaBian, PaqueteEvidenciaCandidato

from support import DOCS

_SD = "Party Reference Data Directory"


class TestFormatearOperacionesConCamposDeRespuesta(unittest.TestCase):
    def setUp(self):
        cache = CatalogoBianCache(str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
                                   "14.0.0", permitir_descargas=False)
        operaciones = cache.operaciones_de(_SD)
        paquete = PaqueteEvidenciaCandidato(
            service_domain=_SD,
            operations=operaciones,
            schemas_detalle=cache.schemas_detalle_de(_SD),
            evidencia=EvidenciaBian(),
        )
        self.texto = _formatear({_SD: operaciones}, {_SD: paquete})

    def test_retrieve_reference_expone_celular_y_correo_inline(self):
        linea = next(l for l in self.texto.splitlines() if l.strip().startswith("- RetrieveReference"))
        self.assertIn("CellPhoneNumber", linea)
        self.assertIn("eMailAddress", linea)

    def test_retrieve_demographics_no_expone_ningun_campo_de_contacto(self):
        linea = next(l for l in self.texto.splitlines() if l.strip().startswith("- RetrieveDemographics"))
        self.assertNotIn("CellPhoneNumber", linea)
        self.assertNotIn("eMailAddress", linea)

    def test_sin_paquete_de_evidencia_no_falla(self):
        # degradación elegante: sin schemas_detalle, la línea se arma sin `campos_respuesta`.
        texto = _formatear({_SD: [self._op_retrieve_reference()]}, {})
        self.assertIn("RetrieveReference", texto)

    def _op_retrieve_reference(self):
        cache = CatalogoBianCache(str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
                                   "14.0.0", permitir_descargas=False)
        return next(o for o in cache.operaciones_de(_SD) if o.operation_id == "RetrieveReference")


if __name__ == "__main__":
    unittest.main()
