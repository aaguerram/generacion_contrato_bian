"""Un modelo debil no puede garantizar una buena respuesta; si puede garantizarse que se NOTE.

Caso real que motiva estos tests (corrida E2E del 2026-09-14 con los seis flags encendidos): Groq
devolvio 413 por el tamaño del prompt, Gemini estaba sin cuota diaria, respondio un modelo mas
debil de la cadena y `seleccionar_operaciones` no ancló ni una operacion. La corrida termino con
`Correspondence` como OWNED_CONTRACT tentativo, cero operaciones y **`operation_grounding_rate`
en 1.0**: el peor resultado posible marcado como perfecto, sin una sola incidencia. El fallo solo
se vio porque una prueba E2E comparaba contra una corrida de referencia.

Tres agujeros, tres cierres:

1. Un Service Domain ELEGIBLE que acaba con cero operaciones ancladas deja incidencia
   `OPERATION_MAPPING_EMPTY`. Antes el bucle de anclaje no se ejecutaba y la funcion devolvia
   sin incidencias.
2. Las citas que el blindaje anti-alucinacion del adaptador descarta viajan de vuelta
   (`MapeoOperacionesLLM.citas_descartadas`) y se registran como `OPERATION_ID_UNRESOLVED`, el
   mismo motivo que ya se usaba cuando la cita llegaba hasta el servicio. Antes solo existian en
   un `logger.warning`, asi que "el modelo se invento todo" era indistinguible de "no propuso
   nada".
3. `operation_grounding_rate` ya no vale 1.0 cuando no se anclo nada, y se acompaña de
   `operation_coverage_rate` (de los SD que DEBIAN recibir operacion, cuantos la recibieron):
   es la tasa que distingue "ancle poco y bien" de "no ancle nada".
4. Una historia que no produce NINGUN contrato deja incidencia `HISTORIA_SIN_CONTRATO`, y las dos
   tasas pasan a `null` (no aplica) en vez de 1.0. Este agujero aparecio al medir la varianza: en
   una de tres corridas reales la historia acabo con CERO Service Domains SELECTED -el peor
   resultado posible- y el JSON mostraba cobertura 1.0 y grounding 1.0, porque sin elegibles no
   habia nada que anclar. Es el mismo error de forma del punto 3, un nivel mas arriba.

Sin red y sin LLM.
"""

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
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.dominio.clasificacion_historias import UmbralesMapeo
from src.dominio.historias import MapeoOperacionesLLM, OperacionPropuestaLLM
from unit_test.support import DOCS
from unit_test.test_grafo_mapeo import _AnalistaGuion

HU = "Como cliente quiero autorizar una transacción con Smart Token.\nEscenario 1. Autorización"


class _MapeadorVacio(MapeadorOperacionesBianPort):
    """El modelo respondio, pero no propuso ninguna operacion."""

    def mapear(self, historia, funcionalidad, operaciones_por_sd, paquetes_por_sd):
        return MapeoOperacionesLLM(operaciones=[])


class _MapeadorAlucinado(MapeadorOperacionesBianPort):
    """El modelo propuso operaciones que no existen: el blindaje las tira y lo deja anotado."""

    def mapear(self, historia, funcionalidad, operaciones_por_sd, paquetes_por_sd):
        return MapeoOperacionesLLM(
            operaciones=[],
            citas_descartadas=["Transaction Authorization/InventarUnaOperacion"],
        )


class _AnalistaSinPropietario(_AnalistaGuion):
    """Ningun candidato es propietario: la historia no produce contrato."""

    def evaluar_candidato(self, historia, funcionalidad, intencion, paquete):
        from src.dominio.historias import EvaluacionCandidatoLLM

        return EvaluacionCandidatoLLM(
            service_domain=paquete.service_domain,
            estado="DESCARTADO",
            rol_contractual="CONSUMED_DEPENDENCY",
            dependency_kind="SUPPORTING_LOOKUP",
            match_service_role=1,
            evidence_quality=2,
            ambiguity="LOW",
            dependency_traceability=["SC-01"],
            justification="solo consulta.",
        )


class _MapeadorBueno(MapeadorOperacionesBianPort):
    def mapear(self, historia, funcionalidad, operaciones_por_sd, paquetes_por_sd):
        sd, ops = next(iter(operaciones_por_sd.items()))
        return MapeoOperacionesLLM(
            operaciones=[
                OperacionPropuestaLLM(
                    service_domain=sd,
                    operation_id=ops[0].operation_id,
                    justificacion="cubre el escenario",
                )
            ]
        )


def _ejecutar(mapeador, analista=None) -> tuple:
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        (raiz / "HU").mkdir()
        (raiz / "HU" / "HU-01.txt").write_text(HU, encoding="utf-8")
        func = raiz / "f.json"
        func.write_text(json.dumps({"funcionalidad_macro": "Autorización"}), encoding="utf-8")
        servicio = MapearHistoriasServiceDomainsService(
            CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")),
            LectorHistoriasFilesystem(),
            analista or _AnalistaGuion(),
            PublicadorMapeoJson(),
            CatalogoBianCache(
                str(DOCS / "bian-operation-catalogs.json"),
                str(DOCS / "bian-cache"),
                "14.0.0",
                permitir_descargas=False,
            ),
            mapeador,
            catalogo_bom=CatalogoBomPuml(str(DOCS / "bian-diagrams" / "puml-bom")),
            umbrales=UmbralesMapeo(),
            concurrencia=1,
        )
        r = servicio.ejecutar(str(raiz / "HU"), str(func), str(raiz / "out"))
        return r, {i["motivo"] for i in r.incidencias}, r.metricas


class TestVisibilidadDeOperaciones(unittest.TestCase):
    def test_un_sd_elegible_sin_operaciones_deja_incidencia(self):
        _, motivos, metricas = _ejecutar(_MapeadorVacio())
        self.assertIn("OPERATION_MAPPING_EMPTY", motivos)
        self.assertEqual(metricas["operation_mapping_empty"], 1)

    def test_el_grounding_ya_no_marca_verde_sin_operaciones(self):
        _, _, metricas = _ejecutar(_MapeadorVacio())
        self.assertEqual(metricas["operaciones_ancladas"], 0)
        self.assertGreater(metricas["service_domains_elegibles"], 0)
        self.assertEqual(metricas["operation_grounding_rate"], 0.0)
        self.assertEqual(metricas["operation_coverage_rate"], 0.0)

    def test_las_citas_que_el_blindaje_descarta_quedan_registradas(self):
        resultado, motivos, _ = _ejecutar(_MapeadorAlucinado())
        self.assertIn("OPERATION_ID_UNRESOLVED", motivos)
        detalle = next(
            i for i in resultado.incidencias if i["motivo"] == "OPERATION_ID_UNRESOLVED"
        )
        self.assertIn("InventarUnaOperacion", detalle["detalle"])

    def test_una_corrida_sana_no_gana_incidencias_nuevas(self):
        _, motivos, metricas = _ejecutar(_MapeadorBueno())
        self.assertNotIn("OPERATION_MAPPING_EMPTY", motivos)
        self.assertNotIn("OPERATION_ID_UNRESOLVED", motivos)
        self.assertEqual(metricas["operation_coverage_rate"], 1.0)
        self.assertGreater(metricas["operaciones_ancladas"], 0)


if __name__ == "__main__":
    unittest.main()


class TestHistoriaSinContrato(unittest.TestCase):
    """El peor resultado posible no puede ser el que mejor pinta en el JSON."""

    def test_deja_incidencia_nombrando_al_mejor_candidato(self):
        resultado, motivos, metricas = _ejecutar(_MapeadorBueno(), _AnalistaSinPropietario())
        self.assertIn("HISTORIA_SIN_CONTRATO", motivos)
        self.assertEqual(metricas["historias_sin_contrato"], 1)
        detalle = next(
            i for i in resultado.incidencias if i["motivo"] == "HISTORIA_SIN_CONTRATO"
        )
        self.assertIn("candidatos evaluados", detalle["detalle"])

    def test_las_tasas_de_operacion_pasan_a_null_en_vez_de_1_0(self):
        _, _, metricas = _ejecutar(_MapeadorBueno(), _AnalistaSinPropietario())
        self.assertEqual(metricas["service_domains_elegibles"], 0)
        self.assertIsNone(metricas["operation_coverage_rate"])
        self.assertIsNone(metricas["operation_grounding_rate"])

    def test_una_corrida_con_contrato_no_gana_la_incidencia(self):
        _, motivos, metricas = _ejecutar(_MapeadorBueno())
        self.assertNotIn("HISTORIA_SIN_CONTRATO", motivos)
        self.assertEqual(metricas["historias_sin_contrato"], 0)
        self.assertIsNotNone(metricas["operation_coverage_rate"])
