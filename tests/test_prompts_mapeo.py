"""Regresión de prompts: agnosticismo (sin hardcode de funcionalidad) + huella reproducible.

Los ejemplos concretos de una funcionalidad (Smart Token / OTP / nombres de Service Domain como
respuesta) viven en tests, nunca en los prompts productivos
(`01-bian-business-alignment.agent.md`: invariante de agnosticismo).
"""

from __future__ import annotations

import re
import unittest

from src.adaptadores.salida.prompts import PROMPT_ADJUDICADOR
from src.adaptadores.salida.prompts_mapeo import SPECS
from src.dominio.historias import EvaluacionCandidatoLLM, ServiceDomainPropuestoLLM

# Nombres de funcionalidad / feature concretos que NO pueden aparecer en un prompt productivo.
_PROHIBIDO = [
    "smart token", "smarttoken", "one-time password", "one time password",
    " otp ", "segundo factor smart", "activar smart",
]


class TestAgnosticismoPrompts(unittest.TestCase):
    def test_prompts_mapeo_no_hardcodean_una_funcionalidad(self):
        for nombre, spec in SPECS.items():
            low = f" {spec.texto.lower()} "
            hits = [p for p in _PROHIBIDO if p in low]
            self.assertEqual(hits, [], f"prompt '{nombre}' contiene hardcode de funcionalidad: {hits}")

    def test_prompt_adjudicador_sin_razonamiento_paso_a_paso(self):
        texto = " ".join(m.prompt.template for m in PROMPT_ADJUDICADOR.messages).lower()
        self.assertNotIn("paso a paso", texto)
        self.assertIn("counter_evidence", texto)
        self.assertIn("reason_codes", texto)

    def test_specs_tienen_id_y_version_estables(self):
        ids = {spec.id for spec in SPECS.values()}
        self.assertEqual(len(ids), len(SPECS))  # un id por prompt
        for spec in SPECS.values():
            self.assertTrue(spec.id.startswith("mapeo."))
            self.assertRegex(spec.version, r"^\d+\.\d+\.\d+$")
            self.assertTrue(spec.texto)


class TestProyeccionEvaluacion(unittest.TestCase):
    def test_desde_evaluacion_separa_ownership_de_dependency(self):
        ev = EvaluacionCandidatoLLM(
            service_domain="X", rol_contractual="OWNED_CONTRACT",
            match_action=3, match_business_object=2, match_service_role=3, evidence_quality=3,
            ownership_traceability=["HU-1/SC-03", "BR-012"], dependency_traceability=["HU-1/SC-09"],
            accion_objeto="verbo objeto",
        )
        p = ServiceDomainPropuestoLLM.desde_evaluacion(ev, service_domain_canonico="X canónico")
        self.assertEqual(p.service_domain, "X canónico")
        self.assertEqual(p.ownership_traceability, ["HU-1/SC-03", "BR-012"])
        self.assertEqual(p.dependency_traceability, ["HU-1/SC-09"])
        self.assertEqual(p.match_action, 3)
        self.assertGreater(p.confianza, 0.0)  # cruda derivada de señales, no la decide el LLM

    def test_dependencia_no_arrastra_dependency_kind_si_es_owned(self):
        ev = EvaluacionCandidatoLLM(
            service_domain="X", rol_contractual="OWNED_CONTRACT", dependency_kind="RISK_INPUT",
        )
        p = ServiceDomainPropuestoLLM.desde_evaluacion(ev, service_domain_canonico="X")
        self.assertIsNone(p.dependency_kind)


if __name__ == "__main__":
    unittest.main()
