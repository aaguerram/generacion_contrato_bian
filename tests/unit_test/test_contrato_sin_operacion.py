"""Un contrato sin operación no es un contrato, y un propietario con operación sólida sí lo es.

Los dos movimientos son simétricos y los dos salieron de medir corridas reales:

1. `finalizar_por_operacion_solida` recorría solo `tentativos` y `descartados`. Estar en el grupo
   `directo` (score >= 0.90) NO implica estar `SELECTED`: `aplicar_hallazgos_adversariales` degrada
   la DECISION sin mover el candidato de grupo. Resultado medido: Party Reference Data Directory
   con confianza 0.9650, `objeto_bom` 1.0, evidencia `CACHED_VERIFIED` y `RetrieveReference`
   anclada sin reservas se quedaba en `UNRESOLVED/TENTATIVE_SCORE` -- cumplia las tres condiciones
   de la finalizacion y el bucle ni lo miraba.

2. Al reves: en 2 de 3 corridas un SD salia `SELECTED` con sus 17 operaciones oficiales
   disponibles y NINGUNA anclada. El entregable del pipeline es "que operacion BIAN implementa
   esta historia"; sin operacion no hay nada que implementar, asi que no puede presentarse como
   resuelto.

Sin red y sin LLM.
"""

from __future__ import annotations

import unittest

from src.dominio.clasificacion_historias import (
    NO_OPERATION_REASON_CODE,
    OPERATION_FINALIZED_REASON_CODE,
    degradar_sin_operacion_anclada,
    finalizar_por_operacion_solida,
)
from src.dominio.historias import (
    DesgloseScore,
    EvidenciaBian,
    OperacionBianAplicada,
    ServiceDomainAsignado,
    ServiceDomainsDeHistoria,
)


def _op(reason_codes=()):
    return OperacionBianAplicada(
        operation_id="RetrieveReference",
        method="GET",
        path="/x",
        tipo="CR",
        grupo="PartyReferenceDataDirectory",
        reason_codes=list(reason_codes),
    )


def _sd(nombre, *, grupo, decision, motivo, confianza=0.9, ops=(), objeto_bom=1.0):
    return ServiceDomainAsignado(
        service_domain=nombre,
        resolucion="MATCH",
        rol_contractual="OWNED_CONTRACT",
        confianza=confianza,
        confianza_pct=int(confianza * 100),
        confianza_llm=confianza,
        grupo=grupo,
        decision_contractual=decision,
        motivo_decision=motivo,
        evidencia_bian=EvidenciaBian(estado="CACHED_VERIFIED"),
        desglose_score=DesgloseScore(objeto_bom=objeto_bom),
        operaciones_bian=list(ops),
    )


class TestFinalizacionAlcanzaAlGrupoDirecto(unittest.TestCase):
    def test_un_directo_degradado_por_el_adversarial_se_finaliza(self):
        """El caso real: grupo `directo`, decisión `UNRESOLVED`, evidencia y operación sólidas."""
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd(
                    "Party Reference Data Directory",
                    grupo="directo",
                    decision="UNRESOLVED",
                    motivo="TENTATIVE_SCORE",
                    confianza=0.965,
                    ops=[_op()],
                )
            ]
        )
        salida = finalizar_por_operacion_solida(grupos)
        sd = salida.candidatos_directos[0]
        self.assertEqual(sd.decision_contractual, "SELECTED")
        self.assertEqual(sd.motivo_decision, "OWNED_SELECTED")
        self.assertIn(OPERATION_FINALIZED_REASON_CODE, sd.reason_codes)

    def test_un_directo_ya_selected_no_se_toca(self):
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd("A", grupo="directo", decision="SELECTED", motivo="OWNED_SELECTED", ops=[_op()])
            ]
        )
        sd = finalizar_por_operacion_solida(grupos).candidatos_directos[0]
        self.assertNotIn(OPERATION_FINALIZED_REASON_CODE, sd.reason_codes)

    def test_sin_operacion_verificada_no_se_finaliza(self):
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd(
                    "A",
                    grupo="directo",
                    decision="UNRESOLVED",
                    motivo="TENTATIVE_SCORE",
                    ops=[_op(["OPERATION_EVIDENCE_UNVERIFIED"])],
                )
            ]
        )
        self.assertEqual(
            finalizar_por_operacion_solida(grupos).candidatos_directos[0].decision_contractual,
            "UNRESOLVED",
        )


class TestDegradacionSinOperacion(unittest.TestCase):
    def test_un_selected_sin_operaciones_baja_a_unresolved(self):
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd("A", grupo="directo", decision="SELECTED", motivo="OWNED_SELECTED", ops=[])
            ]
        )
        sd = degradar_sin_operacion_anclada(grupos, {"A"}).candidatos_directos[0]
        self.assertEqual(sd.decision_contractual, "UNRESOLVED")
        self.assertEqual(sd.motivo_decision, "NO_OPERATION_ANCHORED")
        self.assertIn(NO_OPERATION_REASON_CODE, sd.reason_codes)
        self.assertEqual(sd.grupo, "directo", "degrada la decisión, no mueve de grupo")

    def test_si_el_catalogo_no_tiene_operaciones_no_se_reprocha_nada(self):
        """Un SD sin operaciones oficiales no puede anclar ninguna: no es culpa del mapeo."""
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd("A", grupo="directo", decision="SELECTED", motivo="OWNED_SELECTED", ops=[])
            ]
        )
        sd = degradar_sin_operacion_anclada(grupos, set()).candidatos_directos[0]
        self.assertEqual(sd.decision_contractual, "SELECTED")

    def test_un_selected_con_operacion_se_queda(self):
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd("A", grupo="directo", decision="SELECTED", motivo="OWNED_SELECTED", ops=[_op()])
            ]
        )
        self.assertEqual(
            degradar_sin_operacion_anclada(grupos, {"A"}).candidatos_directos[0].decision_contractual,
            "SELECTED",
        )

    def test_los_dos_movimientos_juntos_no_se_pisan(self):
        """Finalizar primero, degradar después: el que tiene operación sube y se queda arriba."""
        grupos = ServiceDomainsDeHistoria(
            candidatos_directos=[
                _sd("ConOp", grupo="directo", decision="UNRESOLVED", motivo="TENTATIVE_SCORE", ops=[_op()]),
                _sd("SinOp", grupo="directo", decision="SELECTED", motivo="OWNED_SELECTED", ops=[]),
            ]
        )
        salida = degradar_sin_operacion_anclada(finalizar_por_operacion_solida(grupos), {"ConOp", "SinOp"})
        por_nombre = {a.service_domain: a for a in salida.candidatos_directos}
        self.assertEqual(por_nombre["ConOp"].decision_contractual, "SELECTED")
        self.assertEqual(por_nombre["SinOp"].decision_contractual, "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
