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
    fusionar_propuestas_de_operacion,
    operacion_evidencia_verificable,
    operation_id_en_uso,
    resolver_operation_id,
)
from src.dominio.historias import OperacionBian, OperacionPropuestaLLM

from unit_test.support import DOCS

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


class TestFusionarPropuestasDeOperacion(unittest.TestCase):
    """Regresión del caso real: el LLM citó `InitiateOutbound` 4 veces para "Notificar
    actualización de datos" -- una por escenario (SC-01..SC-04) -- y cada cita se anclaba como una
    entrada DUPLICADA en `operaciones_bian` con el mismo operation_id/method/path, solo cambiando
    escenarios_hu/justificacion/bq_seed. `fusionar_propuestas_de_operacion` las une en una sola."""

    def _propuesta(self, **overrides) -> OperacionPropuestaLLM:
        base = dict(
            service_domain="Correspondence", operation_id="InitiateOutbound",
            escenarios_hu=["SC-01"], justificacion="Envia notificacion",
            action_term="Notificar", business_object="Correspondence",
            bq_seed="el sistema envie una notificacion", traceability=["HU-Notificar"],
            evidence_refs=["CorrespondenceAddressee"],
        )
        base.update(overrides)
        return OperacionPropuestaLLM(**base)

    def test_fusiona_escenarios_traceability_y_evidence_refs_sin_duplicar(self):
        p1 = self._propuesta(escenarios_hu=["SC-01"], justificacion="Notifica al contacto anterior",
                              bq_seed="notificar al contacto anterior", traceability=["HU-Notificar", "SC-01"],
                              evidence_refs=["CorrespondenceAddressee"])
        p2 = self._propuesta(escenarios_hu=["SC-02"], justificacion="Notifica al contacto nuevo",
                              bq_seed="notificar al contacto nuevo", traceability=["HU-Notificar", "SC-02"],
                              evidence_refs=["CorrespondenceAddressee", "CorrespondenceContent"])
        fusion = fusionar_propuestas_de_operacion([p1, p2])

        self.assertEqual(fusion.service_domain, "Correspondence")
        self.assertEqual(fusion.operation_id, "InitiateOutbound")
        self.assertEqual(fusion.escenarios_hu, ["SC-01", "SC-02"])
        self.assertEqual(fusion.justificacion, "Notifica al contacto anterior; Notifica al contacto nuevo")
        self.assertEqual(fusion.bq_seed, "notificar al contacto anterior; notificar al contacto nuevo")
        # "HU-Notificar" aparece en ambas -> no se duplica
        self.assertEqual(fusion.traceability, ["HU-Notificar", "SC-01", "SC-02"])
        self.assertEqual(fusion.evidence_refs, ["CorrespondenceAddressee", "CorrespondenceContent"])

    def test_una_sola_propuesta_se_devuelve_intacta(self):
        p = self._propuesta()
        fusion = fusionar_propuestas_de_operacion([p])
        self.assertEqual(fusion.escenarios_hu, ["SC-01"])
        self.assertEqual(fusion.justificacion, "Envia notificacion")

    def test_cuatro_propuestas_del_caso_real_se_fusionan_en_una(self):
        propuestas = [
            self._propuesta(escenarios_hu=[f"SC-0{i}"], justificacion=f"Justificacion {i}",
                             bq_seed=f"seed {i}", traceability=[f"SC-0{i}"])
            for i in range(1, 5)
        ]
        fusion = fusionar_propuestas_de_operacion(propuestas)
        self.assertEqual(fusion.escenarios_hu, ["SC-01", "SC-02", "SC-03", "SC-04"])
        self.assertEqual(fusion.traceability, ["SC-01", "SC-02", "SC-03", "SC-04"])
        self.assertEqual(fusion.justificacion, "Justificacion 1; Justificacion 2; Justificacion 3; Justificacion 4")

    def test_action_term_y_business_object_toman_el_primero_no_vacio(self):
        p1 = self._propuesta(action_term="", business_object="")
        p2 = self._propuesta(action_term="Notificar", business_object="Correspondence")
        fusion = fusionar_propuestas_de_operacion([p1, p2])
        self.assertEqual(fusion.action_term, "Notificar")
        self.assertEqual(fusion.business_object, "Correspondence")

    def test_reason_codes_se_unen_sin_duplicar(self):
        p1 = self._propuesta(reason_codes=["BIAN-SCOPE-008"])
        p2 = self._propuesta(reason_codes=["BIAN-SCOPE-008", "OTRO"])
        fusion = fusionar_propuestas_de_operacion([p1, p2])
        self.assertEqual(fusion.reason_codes, ["BIAN-SCOPE-008", "OTRO"])


if __name__ == "__main__":
    unittest.main()
