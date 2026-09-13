"""Regresión SMART_TOKEN: contra el catálogo real (341 SD) + la caché BIAN real (offline),
la regla de dominio debe reproducir la evaluación de referencia:

    functionality/SMART_TOKEN/design/bian/bian-service-domain-evaluation.yaml
    - Issued Device Administration   OWNED_CONTRACT   SELECTED
    - Party Authentication           OWNED_CONTRACT   SELECTED
    - Transaction Authorization      OWNED_CONTRACT   SELECTED
    - Fraud Evaluation               CONSUMED_DEPENDENCY / RISK_INPUT   REJECTED

Sin LLM ni red: el paso 1 se fija (rúbricas máximas para los OWNED, débil para la dependencia).
"""

from __future__ import annotations

import unittest

from unit_test.support import DOCS

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.dominio.clasificacion_historias import UmbralesMapeo, clasificar_service_domains
from src.dominio.historias import ServiceDomainPropuestoLLM


def _prop(nombre, rol, msr, mon, dep=None):
    return ServiceDomainPropuestoLLM(
        service_domain=nombre, rol_contractual=rol, dependency_kind=dep,
        accion_objeto=f"administrar {nombre.lower()}",
        match_service_role=msr, match_objeto_negocio=mon,
        escenarios_hu=["Escenario 1. Solicitud", "Escenario 2. Activación"],
        justificacion="Trazado a los UC/BR de Smart Token.", confianza=0.9,
    )


class TestSmartTokenRegresion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = CatalogoJson(
            str(DOCS / "SD.json"), str(DOCS / "bian-business-areas.json")
        ).cargar()
        cls.ops = CatalogoBianCache(
            str(DOCS / "bian-operation-catalogs.json"), str(DOCS / "bian-cache"),
            "14.0.0", permitir_descargas=False,
        )

    def _clasificar(self, propuestos):
        nombres = [p.service_domain for p in propuestos]
        return clasificar_service_domains(
            propuestos, self.catalogo, UmbralesMapeo(),
            operaciones_por_sd={n: (self.ops.operaciones_de(n) or []) for n in nombres},
            evidencias_por_sd=self.ops.asegurar(nombres),
            esquemas_por_sd={n: self.ops.esquemas_de(n) for n in nombres},
        )

    def test_tres_owned_seleccionados_y_fraude_rechazado(self):
        g = self._clasificar([
            _prop("Issued Device Administration", "OWNED_CONTRACT", 3, 3),
            _prop("Party Authentication", "OWNED_CONTRACT", 3, 3),
            _prop("Transaction Authorization", "OWNED_CONTRACT", 3, 3),
            _prop("Fraud Evaluation", "CONSUMED_DEPENDENCY", 1, 0, dep="RISK_INPUT"),
        ])

        directos = {a.service_domain for a in g.candidatos_directos}
        self.assertEqual(
            directos,
            {"Issued Device Administration", "Party Authentication", "Transaction Authorization"},
        )
        for a in g.candidatos_directos:
            self.assertEqual(a.decision_contractual, "SELECTED")
            self.assertEqual(a.motivo_decision, "OWNED_SELECTED")
            self.assertIn(a.evidencia_bian.estado, ("VERIFIED", "CACHED_VERIFIED"))
            self.assertTrue(a.evidencia_bian.content_sha256)

        fraude = next(
            a for grp in (g.candidatos_tentativos, g.candidatos_descartados) for a in grp
            if a.service_domain == "Fraud Evaluation"
        )
        self.assertEqual(fraude.decision_contractual, "REJECTED")
        self.assertEqual(fraude.motivo_decision, "CONSUMED_DEPENDENCY")
        self.assertEqual(fraude.dependency_kind, "RISK_INPUT")

    def test_owned_sin_evidencia_en_cache_queda_sin_resolver_no_rechazado(self):
        # 'Employee Benefits' no tiene Semantic API publicada en bian-official/public (confirmado
        # contra el árbol real del repo) -> nunca va a tener evidencia oficial, a diferencia de un
        # SD simplemente no descargado todavía (que `--actualizar-cache-bian` sí puede resolver).
        g = self._clasificar([_prop("Employee Benefits", "OWNED_CONTRACT", 3, 3)])
        todos = [*g.candidatos_directos, *g.candidatos_tentativos, *g.candidatos_descartados]
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0].decision_contractual, "UNRESOLVED")
        self.assertEqual(todos[0].motivo_decision, "NO_OFFICIAL_BIAN_EVIDENCE")

    def test_owned_score_bajo_es_out_of_scope_aunque_falte_evidencia(self):
        g = self._clasificar([_prop("Employee Benefits", "OWNED_CONTRACT", 0, 0)])
        todos = [*g.candidatos_directos, *g.candidatos_tentativos, *g.candidatos_descartados]
        self.assertEqual(todos[0].decision_contractual, "REJECTED")
        self.assertEqual(todos[0].motivo_decision, "OUT_OF_SCOPE")


if __name__ == "__main__":
    unittest.main()
