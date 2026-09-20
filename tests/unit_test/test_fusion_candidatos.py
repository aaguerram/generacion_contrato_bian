"""Reduce determinista del fan-out de 2b (`src/dominio/fusion_candidatos.py`). Sin red."""

from __future__ import annotations

import unittest

from src.dominio.fusion_candidatos import fusionar_candidatos
from src.dominio.historias import CandidatoServiceDomainLLM, CandidatosHistoriaLLM


def _c(sd, *intent, rationale="r"):
    return CandidatoServiceDomainLLM(service_domain=sd, rationale=rationale, supporting_intent=list(intent))


class TestFusionarCandidatos(unittest.TestCase):
    def test_une_sin_duplicar_y_conserva_el_orden_de_aparicion(self):
        a = CandidatosHistoriaLLM(candidatos=[_c("Party Reference Data Directory", "visualizar"), _c("Party Authentication", "auth")],
                                  coverage_notes=["ui"], gaps=["g1"])
        b = CandidatosHistoriaLLM(candidatos=[_c("party reference data directory", "correo"), _c("Correspondence", "notificar")],
                                  coverage_notes=["ui", "avatar"], assumptions=["a1"])
        f = fusionar_candidatos([a, b])
        self.assertEqual([c.service_domain for c in f.candidatos],
                         ["Party Reference Data Directory", "Party Authentication", "Correspondence"])
        self.assertEqual(f.candidatos[0].supporting_intent, ["visualizar", "correo"])
        self.assertEqual(f.coverage_notes, ["ui", "avatar"]); self.assertEqual(f.assumptions, ["a1"]); self.assertEqual(f.gaps, ["g1"])
        self.assertIsNone(f.metadatos, "cada llamada dejó su huella aparte; la fusión no inventa una")

    def test_con_nombres_de_grupo_etiqueta_gaps_y_notas(self):
        a = CandidatosHistoriaLLM(candidatos=[_c("Y", "0")], gaps=["no hay quien administre el dato"], coverage_notes=["ui"])
        b = CandidatosHistoriaLLM(candidatos=[_c("X", "1")], assumptions=["a"])
        f = fusionar_candidatos([a, b], ["IT Management (13 SD)", "Customer Management (15 SD)"])
        self.assertEqual(f.gaps, ["[IT Management (13 SD)] no hay quien administre el dato"])
        self.assertEqual(f.coverage_notes, ["[IT Management (13 SD)] ui"])
        self.assertEqual(f.assumptions, ["[Customer Management (15 SD)] a"])
        self.assertEqual([c.service_domain for c in f.candidatos], ["Y", "X"], "los candidatos no se etiquetan")

    def test_un_grupo_vacio_no_aporta_gaps_ni_notas(self):
        vacio = CandidatosHistoriaLLM(candidatos=[], gaps=["falta el dueño del dato en este grupo"], coverage_notes=["x"])
        lleno = CandidatosHistoriaLLM(candidatos=[_c("X", "1")], gaps=["g"])
        f = fusionar_candidatos([vacio, lleno], ["IT Management", "Customer Management"])
        self.assertEqual(f.gaps, ["[Customer Management] g"]); self.assertEqual(f.coverage_notes, [])

    def test_sin_parciales_devuelve_vacio(self):
        f = fusionar_candidatos([])
        self.assertEqual(f.candidatos, [])

    def test_no_muta_los_parciales(self):
        a = CandidatosHistoriaLLM(candidatos=[_c("X", "1")]); b = CandidatosHistoriaLLM(candidatos=[_c("X", "2")])
        fusionar_candidatos([a, b])
        self.assertEqual(a.candidatos[0].supporting_intent, ["1"])


if __name__ == "__main__":
    unittest.main()
