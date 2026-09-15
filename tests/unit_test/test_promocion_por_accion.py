"""Cerrar la asimetria: un CONSUMED_DEPENDENCY mal clasificado tenia UNA salida, y dependia del LLM.

Asimetria medida en una corrida E2E real: un `OWNED_CONTRACT` mal clasificado tiene TRES redes
-promocion adversarial, finalizacion por operacion solida, degradacion controlada-; un
`CONSUMED_DEPENDENCY` mal clasificado tenia UNA, `determinar_promociones`, que ademas exige que el
revisor adversarial TAMBIEN lo haya detectado: dos juicios del LLM tienen que coincidir. Si el
revisor no lo marca no habia salida, porque `_decidir` fuerza REJECTED sin mirar el score y
`candidatos_operacion_elegibles` excluye a los no-owned -- el paso de operaciones ni se ejecuta, y
ningun rescate por evidencia de operacion puede actuar. Caso real: Party Reference Data Directory
quedo CONSUMED_DEPENDENCY (confianza 0.795) en una historia de consultar y mostrar datos
personales, y la HU termino sin ningun contrato.

`determinar_promociones_por_accion` es el espejo de `determinar_degradaciones`: aquella baja cuando
la accion citada NO comparte ningun token con las acciones declaradas por la historia; esta sube
cuando SI las comparte. Como no hay hallazgo adversarial que respalde el movimiento, exige ademas
objeto_bom >= 0.50 (muy por encima del 0.15 de la promocion con hallazgo) y evidencia verificada.

LO QUE NO HACE, y es lo que permite que el piso sea exigente sin ser paranoico: NO decide el
contrato. Solo devuelve el rol a OWNED_CONTRACT, que abre la puerta al paso de operaciones; de ahi
en adelante manda la evidencia (`finalizar_por_operacion_solida` sube si hay operacion verificada,
`degradar_sin_operacion_anclada` baja si no hay ninguna).

Sin red y sin LLM.
"""

from __future__ import annotations

import unittest

from src.dominio.clasificacion_historias import (
    OBJETO_BOM_MINIMO_PROMOCION_DIRECTA,
    determinar_degradaciones,
    determinar_promociones_por_accion,
)
from src.dominio.historias import (
    DesgloseScore,
    EvidenciaBian,
    IntencionHistoriaLLM,
    RevisionAdversarialLLM,
    ServiceDomainAsignado,
    ServiceDomainsDeHistoria,
)
from src.dominio.normalizacion import normalizar


def _sd(
    nombre="Party Reference Data Directory",
    *,
    rol="CONSUMED_DEPENDENCY",
    accion="visualizar los datos personales y de contacto del cliente",
    objeto_bom=1.0,
    evidencia="CACHED_VERIFIED",
):
    return ServiceDomainAsignado(
        service_domain=nombre,
        resolucion="MATCH",
        rol_contractual=rol,
        confianza=0.795,
        confianza_pct=79,
        confianza_llm=0.8,
        grupo="tentativo",
        accion_objeto=accion,
        desglose_score=DesgloseScore(objeto_bom=objeto_bom),
        evidencia_bian=EvidenciaBian(estado=evidencia),
    )


def _grupos(*sds):
    return ServiceDomainsDeHistoria(candidatos_tentativos=list(sds))


HISTORIA = IntencionHistoriaLLM(business_actions=["visualizar", "consultar"])


class TestPromocionPorAccionDeclarada(unittest.TestCase):
    def test_promueve_cuando_la_accion_citada_es_una_de_las_de_la_historia(self):
        promovidos = determinar_promociones_por_accion(_grupos(_sd()), HISTORIA)
        self.assertIn(normalizar("Party Reference Data Directory"), promovidos)

    def test_no_promueve_si_la_accion_citada_no_es_de_la_historia(self):
        """El caso legitimo de dependencia: la historia notifica, el SD actualiza."""
        sd = _sd(accion="actualizar el numero de celular registrado")
        self.assertEqual(
            determinar_promociones_por_accion(_grupos(sd), IntencionHistoriaLLM(business_actions=["notificar"])),
            frozenset(),
        )

    def test_no_promueve_con_objeto_bom_flojo(self):
        """Sin hallazgo adversarial que respalde, el objeto de negocio tiene que coincidir de
        verdad: es el unico contrapeso disponible."""
        sd = _sd(objeto_bom=OBJETO_BOM_MINIMO_PROMOCION_DIRECTA - 0.01)
        self.assertEqual(determinar_promociones_por_accion(_grupos(sd), HISTORIA), frozenset())

    def test_no_promueve_sin_evidencia_bian_verificada(self):
        sd = _sd(evidencia="BIAN_EVIDENCE_UNAVAILABLE")
        self.assertEqual(determinar_promociones_por_accion(_grupos(sd), HISTORIA), frozenset())

    def test_no_toca_a_los_que_ya_son_propietarios(self):
        sd = _sd(rol="OWNED_CONTRACT")
        self.assertEqual(determinar_promociones_por_accion(_grupos(sd), HISTORIA), frozenset())

    def test_sin_acciones_declaradas_no_hay_con_que_confirmar_nada(self):
        self.assertEqual(
            determinar_promociones_por_accion(_grupos(_sd()), IntencionHistoriaLLM()), frozenset()
        )

    def test_una_relacion_tematica_no_es_promovible(self):
        sd = _sd(rol="RELATED_NOT_OWNED")
        self.assertEqual(determinar_promociones_por_accion(_grupos(sd), HISTORIA), frozenset())


class TestSimetriaConLaDegradacion(unittest.TestCase):
    """Las dos reglas miran lo MISMO -- el cruce entre la accion citada y las acciones que la
    historia declaro- y deben dar veredictos opuestos sobre el mismo par."""

    def test_lo_que_una_sube_la_otra_no_lo_baja(self):
        grupos = _grupos(_sd())
        sube = determinar_promociones_por_accion(grupos, HISTORIA)
        self.assertTrue(sube)
        propietario = _grupos(_sd(rol="OWNED_CONTRACT"))
        revision = RevisionAdversarialLLM(
            hallazgos=[
                {"tipo": "DEPENDENCIA_PROMOVIDA_A_CONTRATO", "service_domain": "Party Reference Data Directory"}
            ]
        )
        self.assertEqual(
            determinar_degradaciones(propietario, HISTORIA, revision),
            frozenset(),
            "la accion citada SI es de la historia: degradar seria contradecir a la promocion",
        )


if __name__ == "__main__":
    unittest.main()
