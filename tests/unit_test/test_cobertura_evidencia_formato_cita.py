"""Regresión: una cita `Campo:Tipo` es válida — es el formato en que el prompt muestra los campos.

`_campos_respuesta` (mapeador_operaciones_langchain) renderiza
`campos_respuesta={CorrespondenceAddressee:Address, CorrespondenceContent:string, ...}` y el
prompt pide "cita el nombre EXACTO del campo de campos_respuesta". El LLM obedece literalmente y
devuelve `"CorrespondenceAddressee:Address"`.

Caso real (corrida E2E del 2026-09-14, `operation_grounding_rate = 0.0`):
`Correspondence/InitiateOutbound` quedó marcada `OPERATION_EVIDENCE_UNVERIFIED` pese a que sus
tres `evidence_refs` existen literalmente como propiedades del `response_schema` `Outbound` — la
cita entera se normalizaba a `correspondenceaddresseeaddress` y no empataba con
`correspondenceaddressee`.

Sin red y sin LLM: lee la evidencia oficial ya cacheada en `docs/`.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.dominio.cobertura_operaciones import operacion_evidencia_verificable
from unit_test.support import DOCS

_SD = "Correspondence"
_OPERACION = "InitiateOutbound"


class TestFormatoDeCitaEnEvidenceRefs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = CatalogoBianCache(
            str(DOCS / "bian-operation-catalogs.json"),
            str(DOCS / "bian-cache"),
            "14.0.0",
            permitir_descargas=False,
        )
        cls.schemas = cache.schemas_detalle_de(_SD)
        cls.op = next(o for o in cache.operaciones_de(_SD) if o.operation_id == _OPERACION)

    def test_cita_con_tipo_pegado_cuenta_como_evidencia(self):
        # Exactamente lo que devolvió el LLM en la corrida real.
        refs = [
            "CorrespondenceAddressee:Address",
            "CorrespondenceContent:string",
            "CorrespondenceMediaorChannel:Channel",
        ]
        self.assertTrue(
            operacion_evidencia_verificable(self.op, refs, self.schemas),
            "los tres campos existen en el response_schema 'Outbound'; el formato Campo:Tipo es "
            "el que el propio prompt renderiza y no puede invalidar la cita",
        )

    def test_cita_del_campo_pelado_sigue_contando(self):
        self.assertTrue(
            operacion_evidencia_verificable(self.op, ["CorrespondenceAddressee"], self.schemas)
        )

    def test_no_afloja_el_antialucinacion(self):
        # Un campo inventado no pasa, ni pelado ni con tipo pegado.
        for ref in ("CampoQueNoExiste", "CampoQueNoExiste:string", "NoExiste:TampocoExiste"):
            with self.subTest(ref=ref):
                self.assertFalse(
                    operacion_evidencia_verificable(self.op, [ref], self.schemas),
                    f"'{ref}' no está en el catálogo: no puede contar como evidencia",
                )

    def test_sin_refs_no_hay_evidencia(self):
        self.assertFalse(operacion_evidencia_verificable(self.op, [], self.schemas))


if __name__ == "__main__":
    unittest.main()
