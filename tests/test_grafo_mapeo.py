"""Grafo de mapeo Historias -> Service Domains: outer map-reduce + subgrafo por HU con
fan-out por candidato. Completo y sin API (proveedor 'fake')."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.servicios.mapear_historias_service_domain import MapearHistoriasServiceDomainsService
from src.configuracion.contenedor import crear_caso_uso_mapeo
from src.dominio.clasificacion_historias import UmbralesMapeo
from src.dominio.historias import (
    BqPersonalizadoPropuestoLLM,
    CandidatosHistoriaLLM,
    CandidatoServiceDomainLLM,
    EvaluacionCandidatoLLM,
    IntencionHistoriaLLM,
    MapeoOperacionesLLM,
    OperacionPropuestaLLM,
    ReconciliacionFuncionalidadLLM,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
)

from support import DOCS, config_test


def _entrada(tmp: str) -> tuple[str, str, str]:
    raiz = Path(tmp)
    hu = raiz / "HU"
    hu.mkdir()
    (hu / "HU-Actualizar correo.txt").write_text(
        "Como usuario quiero modificar mi correo electrónico registrado.\n"
        "Escenario 1. Edición del correo\n"
        "Nota: al pulsar Continuar se solicita Smart Token y se notifica el cambio.",
        encoding="utf-8",
    )
    (hu / "HU-Pantalla datos personales.txt").write_text(
        "Como usuario autenticado quiero ver una pantalla de datos personales.\n"
        "Escenario 1. Ingresar a la pantalla",
        encoding="utf-8",
    )
    func = raiz / "func.json"
    func.write_text(
        json.dumps({"funcionalidad_macro": "Gestión de datos personales", "detalle": "actualizar contacto"}),
        encoding="utf-8",
    )
    return str(hu), str(func), str(raiz / "salida")


class TestGrafoMapeo(unittest.TestCase):
    def test_json_con_historias_grupos_rol_y_jerarquia(self):
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            r = crear_caso_uso_mapeo(config_test(), proveedor="fake").ejecutar(hu, func, salida)

            self.assertEqual(r.total_historias, 2)
            self.assertEqual(
                [h.archivo for h in r.historias],
                ["HU-Actualizar correo.txt", "HU-Pantalla datos personales.txt"],
            )
            self.assertTrue(r.parametros["paso2_operaciones"])
            self.assertIn("fake:fake", r.parametros["cadena_llm"])
            self.assertIn("max_candidatos_hu", r.parametros)

            for h in r.historias:
                g = h.service_domains
                for a in g.candidatos_directos:
                    self.assertGreaterEqual(a.confianza, 0.90)
                    self.assertEqual(a.rol_contractual, "OWNED_CONTRACT")
                    self.assertEqual(a.resolucion, "MATCH")
                for a in g.candidatos_tentativos:
                    self.assertLess(a.confianza, 0.90)
                for grupo in (g.candidatos_directos, g.candidatos_tentativos, g.candidatos_descartados):
                    for a in grupo:
                        self.assertIsNotNone(a.business_area)
                        self.assertIsNotNone(a.business_domain)
                        self.assertIn(a.origen_candidato, ("llm", "completitud", "omitido"))

            # huella reproducible de cada llamada LLM (punto 12)
            self.assertTrue(r.huellas_prompts)
            ids = {m.prompt_id for m in r.huellas_prompts}
            self.assertIn("mapeo.intencion", ids)
            self.assertIn("mapeo.evaluacion", ids)
            for m in r.huellas_prompts:
                self.assertEqual(len(m.prompt_sha256), 64)
                self.assertTrue(m.prompt_version)

            doc = json.loads(
                (Path(salida) / "mapeo-historias-service-domains.json").read_text(encoding="utf-8")
            )
            self.assertIn("generado_en", doc)
            self.assertEqual(doc["parametros"]["umbral_tentativo"], 0.63)
            self.assertIn("reconciliacion", doc)
            self.assertIn("huellas_prompts", doc)

    def test_operaciones_atadas_al_catalogo_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            ops_json = json.loads((DOCS / "bian-operation-catalogs.json").read_text(encoding="utf-8"))
            validas = {
                sd: {o["operation_id"] for o in cuerpo["operations"]}
                for sd, cuerpo in ops_json["service_domains"].items()
            }
            r = crear_caso_uso_mapeo(config_test(), proveedor="fake").ejecutar(hu, func, salida)
            for h in r.historias:
                for a in h.service_domains.candidatos_directos:
                    for op in a.operaciones_bian:
                        self.assertTrue(any(op.operation_id in v for v in validas.values()))

    def test_sin_operaciones_desactiva_paso2(self):
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            cfg = config_test(mapear_historias={"paso2_operaciones": False})
            r = crear_caso_uso_mapeo(cfg, proveedor="fake").ejecutar(hu, func, salida)
            self.assertFalse(r.parametros["paso2_operaciones"])
            for h in r.historias:
                for a in h.service_domains.candidatos_directos:
                    self.assertEqual(a.operaciones_bian, [])

    def test_determinista(self):
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            a = crear_caso_uso_mapeo(config_test(), proveedor="fake").ejecutar(hu, func, salida + "/a")
            b = crear_caso_uso_mapeo(config_test(), proveedor="fake").ejecutar(hu, func, salida + "/b")
            self.assertEqual(a.model_dump(), b.model_dump())

    def test_directorio_hu_vacio_falla(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "HU").mkdir()
            func = raiz / "func.json"
            func.write_text(json.dumps({"funcionalidad_macro": "X"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                crear_caso_uso_mapeo(config_test(), proveedor="fake").ejecutar(
                    str(raiz / "HU"), str(func), str(raiz / "out")
                )

    def test_omitidos_y_motivo_en_consolidados(self):
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            r = crear_caso_uso_mapeo(config_test(), proveedor="fake").ejecutar(hu, func, salida)
            for c in r.service_domains_consolidados:
                self.assertIn(
                    c.motivo,
                    {"OWNED_SELECTED", "TENTATIVE_SCORE", "NO_OFFICIAL_BIAN_EVIDENCE",
                     "CONSUMED_DEPENDENCY", "RELATED_NOT_OWNED", "OUT_OF_SCOPE", "NAME_UNRESOLVED"},
                )
            for h in r.historias:
                for a in h.service_domains.candidatos_descartados:
                    if a.rol_contractual == "OWNED_CONTRACT":
                        self.assertEqual(a.decision_contractual, "REJECTED")
            self.assertIsInstance(r.service_domains_omitidos, list)


class _AnalistaGuion(AnalistaMapeoBianPort):
    """Analista scriptado: TA propietario directo, Fraud Evaluation dependencia de riesgo."""

    def extraer_intencion(self, historia, funcionalidad):
        return IntencionHistoriaLLM(
            resumen_funcional="guion", business_actions=["authorize"],
            business_objects=["transaction"], traceability_ids=["SC-01", "SC-02"],
        )

    def generar_candidatos(self, historia, funcionalidad, intencion, catalogo):
        return CandidatosHistoriaLLM(candidatos=[
            CandidatoServiceDomainLLM(service_domain="Transaction Authorization"),
            CandidatoServiceDomainLLM(service_domain="Fraud Evaluation"),
        ])

    def revisar_completitud(self, historia, intencion, candidatos, catalogo, disponibilidad_evidencia):
        return RevisionCompletitudLLM()

    def evaluar_candidato(self, historia, funcionalidad, intencion, paquete):
        if paquete.service_domain == "Transaction Authorization":
            return EvaluacionCandidatoLLM(
                service_domain=paquete.service_domain, estado="DIRECTO", rol_contractual="OWNED_CONTRACT",
                accion_objeto="autorizar una transaccion", functional_object="transaction",
                match_action=3, match_business_object=3, match_service_role=3, evidence_quality=3,
                ambiguity="NONE", ownership_traceability=["SC-01", "SC-02"],
                justification="La historia ejecuta la autorización de la transacción.",
            )
        return EvaluacionCandidatoLLM(
            service_domain=paquete.service_domain, estado="DESCARTADO",
            rol_contractual="CONSUMED_DEPENDENCY", dependency_kind="RISK_INPUT",
            match_service_role=1, evidence_quality=2, ambiguity="LOW",
            dependency_traceability=["SC-01"], justification="Solo consulta el riesgo.",
        )

    def revisar_adversarial(self, historia, intencion, grupos):
        return RevisionAdversarialLLM(resumen="sin contradicciones")

    def reconciliar_funcionalidad(self, funcionalidad, resumen_por_historia):
        return ReconciliacionFuncionalidadLLM()


class _MapeadorGuion(MapeadorOperacionesBianPort):
    def mapear(self, historia, funcionalidad, operaciones_por_sd, paquetes_por_sd):
        ops = []
        for sd, lista in operaciones_por_sd.items():
            if lista:
                ops.append(OperacionPropuestaLLM(
                    service_domain=sd, operation_id=lista[0].operation_id,
                    escenarios_hu=["Escenario 1"], justificacion="guion", traceability=["SC-01"],
                ))
        bqs = []
        if "Transaction Authorization" in operaciones_por_sd:
            # "Transaction Name" solo existe en el BOM PUML (no en el schema del CR) -> caso real
            # de la regla: campo no cubierto por CR/BQ oficiales pero respaldado por una clase del BOM.
            bqs.append(BqPersonalizadoPropuestoLLM(
                service_domain="Transaction Authorization", nombre_bq="TransactionLabel", verbo="Update",
                campo_no_cubierto="etiqueta descriptiva de la transaccion", clase_bom="Transaction",
                atributo_bom="Transaction Name", escenarios_hu=["Escenario 1"],
                justificacion="guion: ni el CR ni ningun BQ oficial exponen el nombre de la transaccion.",
            ))
            # cita inventada (la clase no existe en el BOM real) -> debe descartarse
            bqs.append(BqPersonalizadoPropuestoLLM(
                service_domain="Transaction Authorization", nombre_bq="Inventado", verbo="Update",
                campo_no_cubierto="campo inventado", clase_bom="ClaseQueNoExiste", atributo_bom="X",
            ))
        return MapeoOperacionesLLM(operaciones=ops, bq_personalizados=bqs)


class TestGrafoMapeoSeleccionReal(unittest.TestCase):
    """Camino directo real (SELECTED + operaciones) usando la caché BIAN sembrada de docs/."""

    def _servicio(self):
        return MapearHistoriasServiceDomainsService(
            CatalogoJson(str(DOCS / "SD.json"), str(DOCS / "bian-business-areas.json")),
            LectorHistoriasFilesystem(),
            _AnalistaGuion(),
            PublicadorMapeoJson(),
            CatalogoBianCache(str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
                              "14.0.0", permitir_descargas=False),
            _MapeadorGuion(),
            catalogo_bom=CatalogoBomPuml(str(DOCS / "bian-puml")),
            umbrales=UmbralesMapeo(),
            concurrencia=1,
        )

    def test_owned_cacheado_sale_selected_con_operaciones(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "HU").mkdir()
            (raiz / "HU" / "HU-01.txt").write_text(
                "Como cliente quiero autorizar una transacción con Smart Token.\nEscenario 1. Autorización",
                encoding="utf-8")
            func = raiz / "f.json"
            func.write_text(json.dumps({"funcionalidad_macro": "Autorización de transacciones"}), encoding="utf-8")
            r = self._servicio().ejecutar(str(raiz / "HU"), str(func), str(raiz / "out"))

            sel = [c for c in r.service_domains_consolidados if c.decision == "SELECTED"]
            self.assertEqual([c.service_domain for c in sel], ["Transaction Authorization"])
            self.assertEqual(sel[0].motivo, "OWNED_SELECTED")
            self.assertTrue(sel[0].selected_operations)
            self.assertTrue(sel[0].evidence.content_sha256)
            self.assertEqual(sel[0].ownership_traceability, ["SC-01", "SC-02"])

            # BQ personalizado: "Transaction Name" solo existe en el BOM PUML, no en el schema del
            # CR ni en ninguna operación oficial -> se propone, se ancla, y NUNCA es "selected".
            self.assertEqual(len(sel[0].custom_bq_candidates), 1)
            candidato = sel[0].custom_bq_candidates[0]
            self.assertEqual(candidato.operation_id, "UpdateTransactionLabel")
            self.assertEqual(candidato.path_propuesto, "/TransactionAuthorization/{id}/TransactionLabel/Update")
            self.assertEqual(candidato.clase_bom, "Transaction")
            self.assertEqual(candidato.estado, "CUSTOM_BQ_CANDIDATE")
            self.assertNotIn(candidato.operation_id, sel[0].selected_operations)
            # la cita inventada (clase inexistente) se descartó sin dejar rastro
            self.assertTrue(all(c.clase_bom != "ClaseQueNoExiste" for c in sel[0].custom_bq_candidates))

            fraude = next(c for c in r.service_domains_consolidados if c.service_domain == "Fraud Evaluation")
            self.assertEqual(fraude.decision, "REJECTED")
            self.assertEqual(fraude.motivo, "CONSUMED_DEPENDENCY")
            self.assertEqual(fraude.custom_bq_candidates, [])


if __name__ == "__main__":
    unittest.main()
