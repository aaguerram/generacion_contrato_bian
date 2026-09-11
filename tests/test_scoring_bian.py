"""Scoring determinista: tokenización camelCase, coherencia de jerarquía y rúbrica estructurada."""

from __future__ import annotations

import unittest

from src.dominio.historias import EvidenciaBian, OperacionBian, ServiceDomainPropuestoLLM
from src.dominio.modelos import EntradaCatalogo
from src.dominio.scoring_bian import _tokens, calcular_score


def _p(**kw) -> ServiceDomainPropuestoLLM:
    base = dict(
        service_domain="X",
        rol_contractual="OWNED_CONTRACT",
        accion_objeto="",
        justificacion="j",
        confianza=0.5,
        escenarios_hu=["Escenario 1", "Escenario 2"],
    )
    base.update(kw)
    return ServiceDomainPropuestoLLM(**base)


class TestTokens(unittest.TestCase):
    def test_separa_camelcase_y_digitos(self):
        self.assertEqual(
            _tokens("IssuedDeviceAdministration"), {"issued", "device", "administration"}
        )
        self.assertIn("token", _tokens("PartyAuthToken2Factor"))


class TestCalcularScore(unittest.TestCase):
    ENTRADA = EntradaCatalogo(
        service_domain="Transaction Authorization",
        service_role="Manage the authorization of a transaction",
        functional_pattern="Transact",
        business_area="Operations and Execution",
        business_domain="Transaction Processing",
    )
    EV = EvidenciaBian(estado="CACHED_VERIFIED", source_commit_sha="abc", content_sha256="def")

    def test_matchea_grupo_cr_camelcase(self):
        op = OperacionBian(operation_id="Evaluate", method="POST", path="/Evaluate", tipo="CR",
                           grupo="TransactionAuthorizationAssessment", summary="", description="")
        d, _ = calcular_score(_p(accion_objeto="authorization transaction"), self.ENTRADA, [op], self.EV)
        self.assertGreater(d.accion_oficial, 0.3)  # antes era 0 por el token camelCase pegado

    def test_coherencia_jerarquia_usa_area_y_dominio(self):
        d, _ = calcular_score(
            _p(accion_objeto="transaction processing", justificacion="procesa la transacción"),
            self.ENTRADA, [], self.EV,
        )
        self.assertGreater(d.coherencia_jerarquia, 0.0)  # 'transaction'/'processing' están en area/domain

    def test_rubrica_estructurada_sustituye_al_lexico(self):
        # sin solape léxico (accion_objeto vacío) pero rúbrica máxima -> accion/objeto altos
        d, _ = calcular_score(_p(accion_objeto="", match_service_role=3, match_objeto_negocio=3),
                              self.ENTRADA, [], self.EV)
        self.assertEqual(d.accion_oficial, 1.0)
        self.assertEqual(d.objeto_bom, 1.0)

    def test_confianza_libre_del_llm_no_entra_al_score(self):
        alta = calcular_score(_p(confianza=1.0, match_service_role=1), self.ENTRADA, [], self.EV)[0].total
        baja = calcular_score(_p(confianza=0.0, match_service_role=1), self.ENTRADA, [], self.EV)[0].total
        self.assertEqual(alta, baja)

    def test_evidencia_ausente_penaliza(self):
        con = calcular_score(_p(match_service_role=3), self.ENTRADA, [], self.EV)[0].total
        sin = calcular_score(_p(match_service_role=3), self.ENTRADA, [],
                             EvidenciaBian(estado="BIAN_EVIDENCE_UNAVAILABLE"))[0].total
        self.assertGreater(con, sin)

    def test_match_action_sube_la_accion_oficial(self):
        d, _ = calcular_score(_p(accion_objeto="", match_service_role=0, match_action=3),
                              self.ENTRADA, [], self.EV)
        self.assertEqual(d.accion_oficial, 1.0)

    def test_ambiguedad_alta_penaliza(self):
        alto = calcular_score(_p(match_service_role=3, ambiguity="NONE"), self.ENTRADA, [], self.EV)[0].total
        bajo = calcular_score(_p(match_service_role=3, ambiguity="HIGH"), self.ENTRADA, [], self.EV)[0].total
        self.assertGreater(alto, bajo)

    def test_evidence_quality_debil_penaliza_frente_a_no_puntuada(self):
        neutral = calcular_score(_p(match_service_role=3, evidence_quality=0), self.ENTRADA, [], self.EV)[0].total
        debil = calcular_score(_p(match_service_role=3, evidence_quality=1), self.ENTRADA, [], self.EV)[0].total
        self.assertGreater(neutral, debil)


if __name__ == "__main__":
    unittest.main()
