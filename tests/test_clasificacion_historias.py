"""Regla de dominio: resolución, tope por rol contractual y reparto en 3 grupos (sin API)."""

from __future__ import annotations

import unittest

from src.dominio.clasificacion_historias import (
    UmbralesMapeo,
    aplicar_hallazgos_adversariales,
    clasificar_service_domains,
    resolver_nombre_sd,
)
from src.dominio.historias import ServiceDomainPropuestoLLM
from src.dominio.historias import (
    EvidenciaBian,
    HallazgoAdversarial,
    OperacionBian,
    RevisionAdversarialLLM,
)
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar


def _cat(*nombres: str) -> list[EntradaCatalogo]:
    return [
        EntradaCatalogo(
            service_domain=n,
            service_role=f"rol de {n}",
            functional_pattern="Manage",
            business_area="Sales and Service",
            business_domain="Cross Channel",
        )
        for n in nombres
    ]


def _p(
    nombre: str,
    confianza: float,
    rol: str = "OWNED_CONTRACT",
    dep: str | None = None,
    just: str = "porque si",
) -> ServiceDomainPropuestoLLM:
    return ServiceDomainPropuestoLLM(
        service_domain=nombre,
        rol_contractual=rol,
        dependency_kind=dep,
        justificacion=just,
        confianza=confianza,
        escenarios_hu=["Escenario 1. Algo"],
    )


class TestUmbralesMapeo(unittest.TestCase):
    def test_invalidos(self):
        with self.assertRaises(ValueError):
            UmbralesMapeo(directo=0.5, tentativo=0.8)

    def test_grupo_de(self):
        u = UmbralesMapeo(directo=0.90, tentativo=0.63)
        self.assertEqual(u.grupo_de(0.95), "directo")
        self.assertEqual(u.grupo_de(0.90), "directo")
        self.assertEqual(u.grupo_de(0.89), "tentativo")
        self.assertEqual(u.grupo_de(0.62), "descartado")


class TestResolver(unittest.TestCase):
    CAT = _cat("Party Authentication", "Transaction Authorization", "Customer Event History")
    IDX = {normalizar(e.service_domain): e for e in CAT}

    def test_match_exacto_normalizado(self):
        e, r = resolver_nombre_sd("party authentication", self.IDX)
        self.assertEqual(r, "MATCH")
        self.assertEqual(e.service_domain, "Party Authentication")

    def test_recupera_por_subcadena_unica(self):
        e, r = resolver_nombre_sd("Transaction Authorization Service", self.IDX)
        self.assertEqual(r, "MATCH")
        self.assertEqual(e.service_domain, "Transaction Authorization")

    def test_no_encontrado(self):
        _, r = resolver_nombre_sd("Inventado XYZ", self.IDX)
        self.assertEqual(r, "NOT_FOUND")

    def test_ambiguo(self):
        idx = {normalizar(e.service_domain): e for e in _cat("Authentication A", "Authentication B")}
        _, r = resolver_nombre_sd("authentication", idx)
        self.assertEqual(r, "AMBIGUOUS")


class TestClasificar(unittest.TestCase):
    def test_score_oficial_puede_seleccionar_owned_directo(self):
        propuesta = _p("Transaction Authorization", 0.97)
        propuesta = propuesta.model_copy(update={
            "accion_objeto": "autorizar una transaccion",
            "escenarios_hu": ["Autorizar transaccion", "Registrar resultado"],
        })
        op = OperacionBian(operation_id="Evaluate", method="POST", path="/Evaluate", tipo="CR",
                           grupo="Transaction Authorization", summary="Evaluate transaction authorization")
        r = clasificar_service_domains(
            [propuesta], self.CAT, self.U,
            operaciones_por_sd={"Transaction Authorization": [op]},
            evidencias_por_sd={"Transaction Authorization": EvidenciaBian(
                estado="CACHED_VERIFIED", source_url="https://example.invalid", source_commit_sha="abc",
                content_sha256="def")},
        )
        self.assertEqual(r.candidatos_directos[0].decision_contractual, "SELECTED")
        self.assertGreaterEqual(r.candidatos_directos[0].desglose_score.total, 0.90)
    U = UmbralesMapeo(directo=0.90, tentativo=0.63)
    CAT = _cat("Party Authentication", "Transaction Authorization", "Customer Event History")

    def test_owned_alto_es_directo_con_jerarquia(self):
        r = clasificar_service_domains([_p("Transaction Authorization", 0.95)], self.CAT, self.U)
        a = r.candidatos_directos[0]
        self.assertEqual(a.service_domain, "Transaction Authorization")
        self.assertEqual(a.rol_contractual, "OWNED_CONTRACT")
        self.assertEqual(a.business_area, "Sales and Service")
        self.assertEqual(a.rol_bian, "rol de Transaction Authorization")
        self.assertEqual(a.resolucion, "MATCH")

    def test_consumed_dependency_nunca_es_directo(self):
        r = clasificar_service_domains(
            [_p("Party Authentication", 0.98, rol="CONSUMED_DEPENDENCY", dep="SECURITY_GUARD")],
            self.CAT,
            self.U,
        )
        self.assertEqual(r.candidatos_directos, [])
        a = r.candidatos_tentativos[0]
        self.assertEqual(a.service_domain, "Party Authentication")
        self.assertLess(a.confianza, self.U.directo)
        self.assertEqual(a.confianza_llm, 0.98)  # se conserva la confianza cruda del LLM
        self.assertEqual(a.dependency_kind, "SECURITY_GUARD")
        # eje contractual: una dependencia consumida NUNCA genera contrato
        self.assertEqual(a.decision_contractual, "REJECTED")
        self.assertEqual(a.motivo_decision, "CONSUMED_DEPENDENCY")

    def test_evidencia_ausente_con_score_alto_es_no_official_evidence(self):
        p = _p("Transaction Authorization", 0.97)
        p = p.model_copy(update={"match_service_role": 3, "match_objeto_negocio": 3,
                                 "accion_objeto": "autorizar una transaccion",
                                 "escenarios_hu": ["Autorizar transaccion", "Registrar resultado"]})
        r = clasificar_service_domains(
            [p], self.CAT, self.U,
            operaciones_por_sd={"Transaction Authorization": []},
            evidencias_por_sd={"Transaction Authorization": EvidenciaBian()},  # UNAVAILABLE
        )
        a = (r.candidatos_directos + r.candidatos_tentativos + r.candidatos_descartados)[0]
        self.assertEqual(a.decision_contractual, "UNRESOLVED")
        self.assertEqual(a.motivo_decision, "NO_OFFICIAL_BIAN_EVIDENCE")

    def test_evidencia_ausente_con_score_bajo_es_out_of_scope(self):
        p = _p("Transaction Authorization", 0.40)  # sin rúbrica ni accion_objeto -> score bajo
        r = clasificar_service_domains(
            [p], self.CAT, self.U,
            operaciones_por_sd={"Transaction Authorization": []},
            evidencias_por_sd={"Transaction Authorization": EvidenciaBian()},
        )
        a = (r.candidatos_directos + r.candidatos_tentativos + r.candidatos_descartados)[0]
        self.assertEqual(a.grupo, "descartado")
        self.assertEqual(a.decision_contractual, "REJECTED")
        self.assertEqual(a.motivo_decision, "OUT_OF_SCOPE")

    def test_related_not_owned_topado(self):
        r = clasificar_service_domains(
            [_p("Customer Event History", 0.93, rol="RELATED_NOT_OWNED")], self.CAT, self.U
        )
        self.assertEqual(r.candidatos_directos, [])
        self.assertEqual(r.candidatos_tentativos[0].service_domain, "Customer Event History")

    def test_descarta_nombre_fuera_del_catalogo(self):
        r = clasificar_service_domains([_p("Inventado XYZ", 0.99)], self.CAT, self.U)
        self.assertEqual(
            (r.candidatos_directos, r.candidatos_tentativos, r.candidatos_descartados), ([], [], [])
        )

    def test_dedup_mayor_confianza(self):
        r = clasificar_service_domains(
            [_p("Party Authentication", 0.55), _p("Party Authentication", 0.93)], self.CAT, self.U
        )
        self.assertEqual(len(r.candidatos_directos), 1)
        self.assertEqual(r.candidatos_directos[0].confianza, 0.93)


class TestAplicarAdversarial(unittest.TestCase):
    U = UmbralesMapeo()
    CAT = _cat("Transaction Authorization", "Party Authentication")

    def _seleccionado(self):
        p = _p("Transaction Authorization", 0.97)
        p = p.model_copy(update={"match_service_role": 3, "match_objeto_negocio": 3,
                                 "accion_objeto": "autorizar una transaccion",
                                 "escenarios_hu": ["Autorizar", "Registrar"]})
        return clasificar_service_domains(
            [p], self.CAT, self.U,
            operaciones_por_sd={"Transaction Authorization": []},
            evidencias_por_sd={"Transaction Authorization": EvidenciaBian(
                estado="CACHED_VERIFIED", content_sha256="abc")},
        )

    def test_dependencia_promovida_degrada_selected_a_unresolved(self):
        grupos = self._seleccionado()
        self.assertEqual(grupos.candidatos_directos[0].decision_contractual, "SELECTED")
        rev = RevisionAdversarialLLM(hallazgos=[HallazgoAdversarial(
            tipo="DEPENDENCIA_PROMOVIDA_A_CONTRATO", service_domain="Transaction Authorization",
            detalle="la historia solo consulta la autorización")])
        out, bloqueos = aplicar_hallazgos_adversariales(grupos, rev)
        a = out.candidatos_directos[0]
        self.assertEqual(a.decision_contractual, "UNRESOLVED")
        self.assertIn("BIAN-SCOPE-002", a.reason_codes)
        self.assertIn("BIAN-SCOPE-002", a.blocking_codes)

    def test_candidato_omitido_es_bloqueo_de_historia_no_toca_sd(self):
        grupos = self._seleccionado()
        rev = RevisionAdversarialLLM(hallazgos=[HallazgoAdversarial(
            tipo="CANDIDATO_OMITIDO", service_domain="", reason_codes=["BIAN-SCOPE-009"])])
        out, bloqueos = aplicar_hallazgos_adversariales(grupos, rev)
        self.assertIn("BIAN-SCOPE-009", bloqueos)
        self.assertEqual(out.candidatos_directos[0].decision_contractual, "SELECTED")


if __name__ == "__main__":
    unittest.main()
