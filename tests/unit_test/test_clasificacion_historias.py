"""Regla de dominio: resolución, tope por rol contractual y reparto en 3 grupos (sin API)."""

from __future__ import annotations

import unittest

from src.dominio.clasificacion_historias import (
    UmbralesMapeo,
    aplicar_hallazgos_adversariales,
    candidatos_operacion_elegibles,
    clasificar_service_domains,
    determinar_degradaciones,
    determinar_promociones,
    propuestos_degradados,
    propuestos_promovidos,
    resolver_nombre_sd,
)
from src.dominio.historias import (
    EvidenciaBian,
    HallazgoAdversarial,
    IntencionHistoriaLLM,
    OperacionBian,
    RevisionAdversarialLLM,
    ServiceDomainPropuestoLLM,
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
        idx = {
            normalizar(e.service_domain): e for e in _cat("Authentication A", "Authentication B")
        }
        _, r = resolver_nombre_sd("authentication", idx)
        self.assertEqual(r, "AMBIGUOUS")


class TestClasificar(unittest.TestCase):
    def test_score_oficial_puede_seleccionar_owned_directo(self):
        propuesta = _p("Transaction Authorization", 0.97)
        propuesta = propuesta.model_copy(
            update={
                "accion_objeto": "autorizar una transaccion",
                "escenarios_hu": ["Autorizar transaccion", "Registrar resultado"],
            }
        )
        op = OperacionBian(
            operation_id="Evaluate",
            method="POST",
            path="/Evaluate",
            tipo="CR",
            grupo="Transaction Authorization",
            summary="Evaluate transaction authorization",
        )
        r = clasificar_service_domains(
            [propuesta],
            self.CAT,
            self.U,
            operaciones_por_sd={"Transaction Authorization": [op]},
            evidencias_por_sd={
                "Transaction Authorization": EvidenciaBian(
                    estado="CACHED_VERIFIED",
                    source_url="https://example.invalid",
                    source_commit_sha="abc",
                    content_sha256="def",
                )
            },
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
        p = p.model_copy(
            update={
                "match_service_role": 3,
                "match_objeto_negocio": 3,
                "accion_objeto": "autorizar una transaccion",
                "escenarios_hu": ["Autorizar transaccion", "Registrar resultado"],
            }
        )
        r = clasificar_service_domains(
            [p],
            self.CAT,
            self.U,
            operaciones_por_sd={"Transaction Authorization": []},
            evidencias_por_sd={"Transaction Authorization": EvidenciaBian()},  # UNAVAILABLE
        )
        a = (r.candidatos_directos + r.candidatos_tentativos + r.candidatos_descartados)[0]
        self.assertEqual(a.decision_contractual, "UNRESOLVED")
        self.assertEqual(a.motivo_decision, "NO_OFFICIAL_BIAN_EVIDENCE")

    def test_evidencia_ausente_con_score_bajo_es_out_of_scope(self):
        p = _p("Transaction Authorization", 0.40)  # sin rúbrica ni accion_objeto -> score bajo
        r = clasificar_service_domains(
            [p],
            self.CAT,
            self.U,
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
        p = p.model_copy(
            update={
                "match_service_role": 3,
                "match_objeto_negocio": 3,
                "accion_objeto": "autorizar una transaccion",
                "escenarios_hu": ["Autorizar", "Registrar"],
            }
        )
        return clasificar_service_domains(
            [p],
            self.CAT,
            self.U,
            operaciones_por_sd={"Transaction Authorization": []},
            evidencias_por_sd={
                "Transaction Authorization": EvidenciaBian(
                    estado="CACHED_VERIFIED", content_sha256="abc"
                )
            },
        )

    def test_dependencia_promovida_degrada_selected_a_unresolved(self):
        grupos = self._seleccionado()
        self.assertEqual(grupos.candidatos_directos[0].decision_contractual, "SELECTED")
        rev = RevisionAdversarialLLM(
            hallazgos=[
                HallazgoAdversarial(
                    tipo="DEPENDENCIA_PROMOVIDA_A_CONTRATO",
                    service_domain="Transaction Authorization",
                    detalle="la historia solo consulta la autorización",
                )
            ]
        )
        out, bloqueos = aplicar_hallazgos_adversariales(grupos, rev)
        a = out.candidatos_directos[0]
        self.assertEqual(a.decision_contractual, "UNRESOLVED")
        self.assertIn("BIAN-SCOPE-002", a.reason_codes)
        self.assertIn("BIAN-SCOPE-002", a.blocking_codes)

    def test_candidato_omitido_es_bloqueo_de_historia_no_toca_sd(self):
        grupos = self._seleccionado()
        rev = RevisionAdversarialLLM(
            hallazgos=[
                HallazgoAdversarial(
                    tipo="CANDIDATO_OMITIDO", service_domain="", reason_codes=["BIAN-SCOPE-009"]
                )
            ]
        )
        out, bloqueos = aplicar_hallazgos_adversariales(grupos, rev)
        self.assertIn("BIAN-SCOPE-009", bloqueos)
        self.assertEqual(out.candidatos_directos[0].decision_contractual, "SELECTED")

    def test_accion_directa_como_dependencia_ya_no_degrada_selected(self):
        # regresión: este hallazgo significa lo OPUESTO a DEPENDENCIA_PROMOVIDA_A_CONTRATO (una
        # acción directa quedó como dependencia, no una dependencia que se coló como contrato) --
        # nunca debe degradar un SELECTED existente.
        grupos = self._seleccionado()
        rev = RevisionAdversarialLLM(
            hallazgos=[
                HallazgoAdversarial(
                    tipo="ACCION_DIRECTA_COMO_DEPENDENCIA",
                    service_domain="Transaction Authorization",
                    reason_codes=["BIAN-SCOPE-002"],
                )
            ]
        )
        out, _ = aplicar_hallazgos_adversariales(grupos, rev)
        self.assertEqual(out.candidatos_directos[0].decision_contractual, "SELECTED")

    def _tentativo_promovido(self, *, estado_evidencia: str) -> ServiceDomainsDeHistoria:
        # score deliberadamente bajo en objeto/jerarquía -- igual que Correspondence real (0.6733):
        # el LLM calificó esas rúbricas mientras todavía enmarcaba el candidato como dependencia.
        p = _p("Party Authentication", 0.60, dep="AUDIT_OR_NOTIFICATION")
        p = p.model_copy(
            update={
                "accion_objeto": "notificar algo",
                "match_service_role": 2,
                "match_objeto_negocio": 1,
                "escenarios_hu": ["Escenario 1. Algo", "Escenario 2. Otro"],
            }
        )
        return clasificar_service_domains(
            [p],
            self.CAT,
            self.U,
            operaciones_por_sd={"Party Authentication": []},
            evidencias_por_sd={
                "Party Authentication": EvidenciaBian(estado=estado_evidencia, content_sha256="x")
            },
        )

    def test_promocion_con_evidencia_verificada_finaliza_directo_selected(self):
        grupos = self._tentativo_promovido(estado_evidencia="CACHED_VERIFIED")
        self.assertEqual(grupos.candidatos_tentativos[0].service_domain, "Party Authentication")
        out, _ = aplicar_hallazgos_adversariales(
            grupos, RevisionAdversarialLLM(), promovidos=frozenset({"partyauthentication"})
        )
        self.assertEqual(out.candidatos_tentativos, [])
        a = out.candidatos_directos[0]
        self.assertEqual(a.grupo, "directo")
        self.assertEqual(a.decision_contractual, "SELECTED")
        self.assertEqual(a.motivo_decision, "OWNED_SELECTED")
        self.assertIn("OWNERSHIP_PROMOTED_BY_ADVERSARIAL", a.reason_codes)

    def test_promocion_sin_evidencia_verificada_no_fuerza_directo(self):
        # sin evidencia BIAN verificable, el score cae más (penalización de scoring_bian) y la
        # propuesta queda descartada -- pero eso, no una promoción silenciosa a "directo".
        grupos = self._tentativo_promovido(estado_evidencia="BIAN_EVIDENCE_UNAVAILABLE")
        self.assertEqual(grupos.candidatos_descartados[0].service_domain, "Party Authentication")
        out, _ = aplicar_hallazgos_adversariales(
            grupos, RevisionAdversarialLLM(), promovidos=frozenset({"partyauthentication"})
        )
        # se anota la promoción, pero sin evidencia oficial verificable no se inventa un "directo"
        self.assertEqual(out.candidatos_directos, [])
        a = next(
            a for a in out.candidatos_descartados if a.service_domain == "Party Authentication"
        )
        self.assertIn("OWNERSHIP_PROMOTED_BY_ADVERSARIAL", a.reason_codes)
        self.assertNotEqual(a.decision_contractual, "SELECTED")


class TestDeterminarPromociones(unittest.TestCase):
    """`determinar_promociones` / `propuestos_promovidos`: el caso real de "Notificar
    actualización de datos" (Correspondence CONSUMED_DEPENDENCY/AUDIT_OR_NOTIFICATION con
    ACCION_DIRECTA_COMO_DEPENDENCIA) -- ver salida/2026-09-11_17-59-40 -- y el falso positivo real
    de "Party Authentication" (evidence_refs citando su propio Control Record
    `PartyAuthenticationAssessment` para una historia de "enviar notificación", sin relación real
    con el objeto de negocio) que motivó el piso `objeto_bom_minimo` -- ver
    salida/2026-09-12_*/mapeo-historias-service-domains.json, objeto_bom=0.0 exacto."""

    U = UmbralesMapeo()
    CAT = _cat("Correspondence")

    def _grupos(self, **overrides) -> ServiceDomainsDeHistoria:
        base = dict(
            service_domain="Correspondence",
            rol_contractual="CONSUMED_DEPENDENCY",
            dependency_kind="AUDIT_OR_NOTIFICATION",
            justificacion="consume Correspondence",
            confianza=0.6667,
            dependency_traceability=["SC-01", "SC-02"],
            evidence_refs=["InitiateOutbound"],
        )
        base.update(overrides)
        propuesta = ServiceDomainPropuestoLLM(**base)
        return clasificar_service_domains(
            [propuesta],
            self.CAT,
            self.U,
            operaciones_por_sd={"Correspondence": []},
            evidencias_por_sd={
                "Correspondence": EvidenciaBian(estado="CACHED_VERIFIED", content_sha256="x")
            },
        )

    def _propuestos_de(self, grupos) -> dict[str, ServiceDomainPropuestoLLM]:
        """Reconstruye el dict que necesita `propuestos_promovidos` a partir del `ServiceDomainAsignado`
        ya clasificado (mismo patrón que usa el servicio real: `_h_clasificar` guarda este dict por
        separado; aquí se reconstruye a mano porque el test opera un nivel más abajo)."""
        a = (
            *grupos.candidatos_directos,
            *grupos.candidatos_tentativos,
            *grupos.candidatos_descartados,
        )[0]
        return {
            normalizar(a.service_domain): ServiceDomainPropuestoLLM(
                service_domain=a.service_domain,
                rol_contractual=a.rol_contractual,
                dependency_kind=a.dependency_kind,
                justificacion=a.justificacion,
                confianza=a.confianza_llm,
                dependency_traceability=a.dependency_traceability,
                evidence_refs=a.evidence_refs,
            )
        }

    def _revision(self, tipos: list[str], *, sd: str = "Correspondence") -> RevisionAdversarialLLM:
        return RevisionAdversarialLLM(
            hallazgos=[HallazgoAdversarial(tipo=t, service_domain=sd) for t in tipos]
        )

    def test_promueve_con_evidencia_fuerte(self):
        # match_objeto_negocio=3 -> objeto_bom=1.0 (rúbrica del LLM sosteniendo el match real)
        grupos = self._grupos(match_objeto_negocio=3)
        promovidos = determinar_promociones(
            grupos, self._revision(["ACCION_DIRECTA_COMO_DEPENDENCIA"])
        )
        self.assertEqual(promovidos, frozenset({"correspondence"}))

        propuestos = self._propuestos_de(grupos)
        nuevos = propuestos_promovidos(propuestos, promovidos)
        p = nuevos["correspondence"]
        self.assertEqual(p.rol_contractual, "OWNED_CONTRACT")
        self.assertIsNone(p.dependency_kind)

    def test_no_promueve_objeto_bom_cero_aunque_todo_lo_demas_califique(self):
        # regresión del falso positivo real: "Party Authentication" citó su propio CR como
        # evidence_refs para una historia de notificación -- ACCION_DIRECTA_COMO_DEPENDENCIA +
        # dependency_kind + trazabilidad + evidence_refs no vacíos, TODO presente, pero
        # objeto_bom=0.0 (ninguna correspondencia léxica ni de rúbrica con el objeto de negocio).
        grupos = self._grupos()  # match_objeto_negocio por defecto = 0, sin operaciones/esquemas
        self.assertEqual(grupos.candidatos_descartados[0].desglose_score.objeto_bom, 0.0)
        promovidos = determinar_promociones(
            grupos, self._revision(["ACCION_DIRECTA_COMO_DEPENDENCIA"])
        )
        self.assertEqual(promovidos, frozenset())

    def test_no_promueve_sin_hallazgo(self):
        grupos = self._grupos(match_objeto_negocio=3)
        self.assertEqual(determinar_promociones(grupos, self._revision([])), frozenset())

    def test_no_promueve_si_revisor_contradice_service_role(self):
        grupos = self._grupos(match_objeto_negocio=3)
        rev = self._revision(["ACCION_DIRECTA_COMO_DEPENDENCIA", "DIRECTO_SIN_SERVICE_ROLE"])
        self.assertEqual(determinar_promociones(grupos, rev), frozenset())

    def test_no_promueve_dependency_kind_de_precondicion(self):
        # SECURITY_GUARD / SUPPORTING_LOOKUP / EXTERNAL_PROVIDER / RISK_INPUT: precondiciones
        # consultadas antes de actuar, no la salida que la historia produce -- nunca promueven.
        grupos = self._grupos(dependency_kind="SECURITY_GUARD", match_objeto_negocio=3)
        promovidos = determinar_promociones(
            grupos, self._revision(["ACCION_DIRECTA_COMO_DEPENDENCIA"])
        )
        self.assertEqual(promovidos, frozenset())

    def test_no_promueve_sin_trazabilidad_ni_evidencia(self):
        grupos = self._grupos(dependency_traceability=[], evidence_refs=[], match_objeto_negocio=3)
        promovidos = determinar_promociones(
            grupos, self._revision(["ACCION_DIRECTA_COMO_DEPENDENCIA"])
        )
        self.assertEqual(promovidos, frozenset())

    def test_no_promueve_related_not_owned(self):
        grupos = self._grupos(
            rol_contractual="RELATED_NOT_OWNED",
            dependency_kind=None,
            match_objeto_negocio=3,
        )
        promovidos = determinar_promociones(
            grupos, self._revision(["ACCION_DIRECTA_COMO_DEPENDENCIA"])
        )
        self.assertEqual(promovidos, frozenset())


class TestDeterminarDegradaciones(unittest.TestCase):
    """`determinar_degradaciones` / `propuestos_degradados`: el caso real de "Notificar
    actualización de datos" -> "Party Reference Data Directory" fue evaluado OWNED_CONTRACT
    (accion_objeto="actualizar número de celular o correo electrónico") para una historia que solo
    NOTIFICA (la actualización ya es una precondición ocurrida antes: "cuando el usuario
    actualiza..."). El revisor adversarial señaló DEPENDENCIA_PROMOVIDA_A_CONTRATO; antes de este
    fix solo se degradaba a UNRESOLVED (bloqueado para revisión humana), nunca se reclasificaba."""

    U = UmbralesMapeo()
    CAT = _cat("Party Reference Data Directory")

    def _grupos(self, **overrides) -> ServiceDomainsDeHistoria:
        base = dict(
            service_domain="Party Reference Data Directory",
            rol_contractual="OWNED_CONTRACT",
            accion_objeto="actualizar numero de celular o correo electronico",
            justificacion="administra los datos de contacto",
            confianza=1.0,
            escenarios_hu=["SC-01. Notificar", "SC-02. Notificar", "SC-03. Notificar"],
            ownership_traceability=["SC-01", "SC-02", "SC-03"],
            match_action=3,
            match_objeto_negocio=3,
        )
        base.update(overrides)
        propuesta = ServiceDomainPropuestoLLM(**base)
        return clasificar_service_domains(
            [propuesta],
            self.CAT,
            self.U,
            operaciones_por_sd={"Party Reference Data Directory": []},
            evidencias_por_sd={
                "Party Reference Data Directory": EvidenciaBian(
                    estado="CACHED_VERIFIED", content_sha256="x"
                ),
            },
        )

    def _intencion(self, acciones: list[str]) -> IntencionHistoriaLLM:
        return IntencionHistoriaLLM(business_actions=acciones)

    def _revision(self, tipos: list[str]) -> RevisionAdversarialLLM:
        return RevisionAdversarialLLM(
            hallazgos=[
                HallazgoAdversarial(tipo=t, service_domain="Party Reference Data Directory")
                for t in tipos
            ]
        )

    def test_degrada_cuando_la_accion_citada_no_es_ninguna_de_la_historia(self):
        grupos = self._grupos()
        # antes de degradar: rúbricas altas -> SELECTED (el mismo punto de partida que en el caso
        # real, donde solo el hallazgo adversarial + este chequeo evitan que se publique así).
        self.assertEqual(grupos.candidatos_directos[0].decision_contractual, "SELECTED")
        degradados = determinar_degradaciones(
            grupos,
            self._intencion(["notificar", "registrar"]),
            self._revision(["DEPENDENCIA_PROMOVIDA_A_CONTRATO"]),
        )
        self.assertEqual(degradados, frozenset({"partyreferencedatadirectory"}))

        propuestos = {
            "partyreferencedatadirectory": ServiceDomainPropuestoLLM(
                service_domain="Party Reference Data Directory",
                rol_contractual="OWNED_CONTRACT",
                ownership_traceability=["SC-01", "SC-02"],
            )
        }
        nuevos = propuestos_degradados(propuestos, degradados)
        p = nuevos["partyreferencedatadirectory"]
        self.assertEqual(p.rol_contractual, "CONSUMED_DEPENDENCY")
        self.assertEqual(p.dependency_kind, "SUPPORTING_LOOKUP")
        self.assertEqual(p.dependency_traceability, ["SC-01", "SC-02"])
        self.assertEqual(p.ownership_traceability, [])

    def test_no_degrada_sin_hallazgo(self):
        grupos = self._grupos()
        degradados = determinar_degradaciones(
            grupos, self._intencion(["notificar"]), self._revision([])
        )
        self.assertEqual(degradados, frozenset())

    def test_no_degrada_si_la_accion_si_coincide_con_la_historia(self):
        # la propia historia SÍ declara "actualizar" entre sus acciones -> hay sustento
        # independiente, no se reclasifica solo por el hallazgo del revisor.
        grupos = self._grupos()
        degradados = determinar_degradaciones(
            grupos,
            self._intencion(["actualizar", "notificar"]),
            self._revision(["DEPENDENCIA_PROMOVIDA_A_CONTRATO"]),
        )
        self.assertEqual(degradados, frozenset())

    def test_no_degrada_si_no_es_owned(self):
        grupos = self._grupos(rol_contractual="RELATED_NOT_OWNED")
        degradados = determinar_degradaciones(
            grupos,
            self._intencion(["notificar"]),
            self._revision(["DEPENDENCIA_PROMOVIDA_A_CONTRATO"]),
        )
        self.assertEqual(degradados, frozenset())

    def test_no_degrada_sin_business_actions_en_la_intencion(self):
        # sin acciones propias con qué confirmar nada, se queda en el UNRESOLVED bloqueado
        # (conservador por defecto) en vez de reclasificar a ciegas.
        grupos = self._grupos()
        degradados = determinar_degradaciones(
            grupos,
            self._intencion([]),
            self._revision(["DEPENDENCIA_PROMOVIDA_A_CONTRATO"]),
        )
        self.assertEqual(degradados, frozenset())


class TestCandidatosOperacionElegibles(unittest.TestCase):
    U = UmbralesMapeo()
    CAT = _cat("Correspondence")

    def test_incluye_owned_directo_y_tentativo_excluye_no_owned(self):
        directo = _p("Correspondence", 0.95)
        r_directo = clasificar_service_domains([directo], self.CAT, self.U)

        tentativo = _p("Correspondence", 0.70)
        r_tentativo = clasificar_service_domains([tentativo], self.CAT, self.U)

        no_owned = _p("Correspondence", 0.70, rol="CONSUMED_DEPENDENCY", dep="OTHER_DEPENDENCY")
        r_no_owned = clasificar_service_domains([no_owned], self.CAT, self.U)

        self.assertEqual(len(candidatos_operacion_elegibles(r_directo)), 1)
        self.assertEqual(len(candidatos_operacion_elegibles(r_tentativo)), 1)
        self.assertEqual(candidatos_operacion_elegibles(r_no_owned), [])

    def test_excluye_descartados_aunque_sean_owned(self):
        r = clasificar_service_domains([_p("Correspondence", 0.10)], self.CAT, self.U)
        self.assertEqual(r.candidatos_descartados[0].rol_contractual, "OWNED_CONTRACT")
        self.assertEqual(candidatos_operacion_elegibles(r), [])


if __name__ == "__main__":
    unittest.main()
