"""Regresión directa del caso real: `RetrieveDemographics` fue elegido para celular/correo cuando
el candidato correcto era `RetrieveReference` (BQ `Reference`, que sí expone `CellPhoneNumber` /
`eMailAddress`). Usa el fixture real `docs/bian-cache/release14.0.0/PartyReferenceDataDirectory.json`
(67 schemas) para probar los helpers deterministas que cierran ese hueco."""

from __future__ import annotations

import unittest

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.dominio.cobertura_operaciones import (
    campos_alcanzables,
    derivar_path_grupo,
    operacion_evidencia_verificable,
    operation_id_en_uso,
    resolver_operation_id,
)
from src.dominio.historias import OperacionBian

from support import DOCS

_SD = "Party Reference Data Directory"


def _cache() -> CatalogoBianCache:
    return CatalogoBianCache(str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
                              "14.0.0", permitir_descargas=False)


def _operacion(operation_id: str, operaciones: list[OperacionBian]) -> OperacionBian:
    return next(o for o in operaciones if o.operation_id == operation_id)


class TestCamposAlcanzables(unittest.TestCase):
    def setUp(self):
        self.schemas = _cache().schemas_detalle_de(_SD)
        self.assertTrue(self.schemas, "fixture real de PartyReferenceDataDirectory debe existir")

    def test_reference_expone_celular_y_correo(self):
        campos = campos_alcanzables("Reference", self.schemas)
        self.assertIn("cellphonenumber", campos)
        self.assertIn("emailaddress", campos)

    def test_demographics_no_expone_ningun_dato_de_contacto(self):
        campos = campos_alcanzables("Demographics", self.schemas)
        self.assertNotIn("cellphonenumber", campos)
        self.assertNotIn("emailaddress", campos)

    def test_schema_desconocido_devuelve_solo_su_propio_nombre(self):
        campos = campos_alcanzables("SchemaQueNoExiste", self.schemas)
        self.assertEqual(campos, {"schemaquenoexiste"})

    def test_schema_vacio_no_alcanza_nada(self):
        self.assertEqual(campos_alcanzables("", self.schemas), set())


class TestOperacionEvidenciaVerificable(unittest.TestCase):
    def setUp(self):
        self.schemas = _cache().schemas_detalle_de(_SD)
        self.operaciones = _cache().operaciones_de(_SD)

    def test_cita_real_de_campo_pasa(self):
        op = _operacion("RetrieveReference", self.operaciones)
        self.assertTrue(operacion_evidencia_verificable(op, ["CellPhoneNumber"], self.schemas))

    def test_cita_de_campo_ajeno_no_pasa(self):
        # "CellPhoneNumber" no es alcanzable desde el response_schema de RetrieveDemographics.
        op = _operacion("RetrieveDemographics", self.operaciones)
        self.assertFalse(operacion_evidencia_verificable(op, ["CellPhoneNumber"], self.schemas))

    def test_cita_del_propio_grupo_o_operation_id_pasa(self):
        op = _operacion("RetrieveReference", self.operaciones)
        self.assertTrue(operacion_evidencia_verificable(op, ["Reference"], self.schemas))
        self.assertTrue(operacion_evidencia_verificable(op, ["RetrieveReference"], self.schemas))

    def test_sin_evidence_refs_no_pasa(self):
        op = _operacion("RetrieveReference", self.operaciones)
        self.assertFalse(operacion_evidencia_verificable(op, [], self.schemas))


class TestDerivarPathGrupo(unittest.TestCase):
    def setUp(self):
        self.operaciones = _cache().operaciones_de(_SD)

    def test_reusa_el_prefijo_real_del_grupo(self):
        path = derivar_path_grupo("Reference", "Register", self.operaciones)
        self.assertEqual(
            path, "/PartyReferenceDataDirectory/{partyreferencedatadirectoryid}/Reference/{referenceid}/Register"
        )

    def test_grupo_inexistente_devuelve_none(self):
        self.assertIsNone(derivar_path_grupo("GrupoQueNoExiste", "Update", self.operaciones))


class TestOperationIdEnUso(unittest.TestCase):
    def setUp(self):
        self.operaciones = _cache().operaciones_de(_SD)

    def test_operation_id_oficial_esta_en_uso(self):
        self.assertTrue(operation_id_en_uso("RetrieveReference", self.operaciones))

    def test_operation_id_nuevo_no_esta_en_uso(self):
        self.assertFalse(operation_id_en_uso("RegisterReference", self.operaciones))


class TestResolverOperationId(unittest.TestCase):
    """Regresión del caso real observado en producción (corrida CLI real, failover a un modelo
    más débil): `seleccionar_operaciones` devolvió `"POST /Correspondence/{correspondenceid}/
    Outbound/Initiate"` en vez de `"InitiateOutbound"` -- se descartaba en silencio y la HU
    "Notificar actualización de datos" quedaba sin ninguna operación anclada pese a que
    Correspondence ya era OWNED_CONTRACT/directo."""

    def setUp(self):
        self.operaciones = CatalogoBianCache(
            str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
            "14.0.0", permitir_descargas=False,
        ).operaciones_de("Correspondence")
        self.assertTrue(self.operaciones, "fixture real de Correspondence debe existir")

    def test_operation_id_exacto(self):
        o = resolver_operation_id("InitiateOutbound", self.operaciones)
        self.assertIsNotNone(o)
        self.assertEqual(o.operation_id, "InitiateOutbound")

    def test_operation_id_con_espacios_o_mayusculas_distintas(self):
        o = resolver_operation_id("  initiateoutbound ", self.operaciones)
        self.assertEqual(o.operation_id, "InitiateOutbound")

    def test_reconstruye_desde_metodo_y_path_real(self):
        # el caso real exacto observado
        o = resolver_operation_id(
            "POST /Correspondence/{correspondenceid}/Outbound/Initiate", self.operaciones
        )
        self.assertIsNotNone(o)
        self.assertEqual(o.operation_id, "InitiateOutbound")

    def test_metodo_no_coincide_no_resuelve(self):
        # mismo path, método equivocado -> no debe colarse como si fuera otra operación
        o = resolver_operation_id(
            "GET /Correspondence/{correspondenceid}/Outbound/Initiate", self.operaciones
        )
        self.assertIsNone(o)

    def test_path_sin_metodo_tambien_resuelve(self):
        o = resolver_operation_id(
            "/Correspondence/{correspondenceid}/Outbound/Initiate", self.operaciones
        )
        self.assertEqual(o.operation_id, "InitiateOutbound")

    def test_string_irreconocible_no_inventa_nada(self):
        self.assertIsNone(resolver_operation_id("EnviarNotificacion", self.operaciones))
        self.assertIsNone(resolver_operation_id("", self.operaciones))

    def test_nunca_cruza_a_otro_service_domain(self):
        # un path real de OTRO SD no debe resolver contra el catálogo de Correspondence
        otras = CatalogoBianCache(
            str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
            "14.0.0", permitir_descargas=False,
        ).operaciones_de("Party Reference Data Directory")
        ajena = next(o for o in otras if o.operation_id == "RetrieveReference")
        self.assertIsNone(resolver_operation_id(f"{ajena.method} {ajena.path}", self.operaciones))


if __name__ == "__main__":
    unittest.main()
