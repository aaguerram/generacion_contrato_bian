"""Regresión: el revisor adversarial debe ver el MISMO Service Role que el evaluador.

`revisar_adversarial` puede emitir `DIRECTO_SIN_SERVICE_ROLE` ("el Service Role no describe
verbo+objeto de la historia") contra la decisión que tomó `evaluar_candidato`. Si ve el rol más
recortado que él, contradice con menos evidencia de la que se usó para decidir.

Caso real que lo motivó (corrida E2E del 2026-09-14, `ownership_conflict_rate = 1.0`): con el
límite viejo de 120 chars, el rol de "Party Reference Data Directory" (498 chars) llegaba cortado
en "...wide range of party reference data that might ", ocultando "contact details ... demographic
details" — justo el objeto de la historia. El SD quedó `UNRESOLVED` pese a tener score 1.0.
El corte alcanzaba al 90% de los 341 SD del catálogo (mediana 309 chars).
"""

from __future__ import annotations

import unittest

from langchain_core.runnables import RunnableLambda

from src.adaptadores.salida import analista_mapeo_langchain as ana
from src.dominio.historias import (
    HistoriaUsuario,
    IntencionHistoriaLLM,
    RevisionAdversarialLLM,
    ServiceDomainAsignado,
    ServiceDomainsDeHistoria,
)

# Rol largo y realista: el objeto de negocio aparece DESPUÉS del carácter 120, como en el caso real.
_ROL_LARGO = (
    "The party reference data directory service domain maintains a potentially wide range of "
    "party reference data that might be used in any interaction between the bank and the party "
    "including relationship development, sales/marketing, servicing and product delivery. This "
    "can include general reference and contact details, party associations, demographic details "
    "and some servicing preferences."
)
_OBJETO_TARDIO = "demographic details"


class _ChatEspia:
    """Captura el prompt YA RENDERIZADO (lo que vería el modelo), sin llamar a ninguno.

    Cumple `SoportaStructured`: al pipe `spec.template | chat.with_structured_output(...)` le
    basta con que el lado derecho sea un Runnable.
    """

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        return RunnableLambda(self._capturar)

    def _capturar(self, prompt_value):
        self.prompts.append(prompt_value.to_string())
        return RevisionAdversarialLLM(hallazgos=[], blocking_codes=[], resumen="sin hallazgos")


def _asignado() -> ServiceDomainAsignado:
    return ServiceDomainAsignado(
        service_domain="Party Reference Data Directory",
        resolucion="MATCH",
        rol_contractual="OWNED_CONTRACT",
        confianza=1.0,
        confianza_pct=100,
        confianza_llm=1.0,
        grupo="directo",
        decision_contractual="SELECTED",
        motivo_decision="OWNED_SELECTED",
        accion_objeto="consultar datos personales",
        rol_bian=_ROL_LARGO,
    )


class TestServiceRoleEnRevisionAdversarial(unittest.TestCase):
    def setUp(self):
        self.chat = _ChatEspia()
        self.analista = ana.AnalistaMapeoBianLangChain(self.chat)

    def _revisar(self) -> str:
        self.analista.revisar_adversarial(
            HistoriaUsuario(
                archivo="HU-x.txt", titulo="Crear pantalla de datos personales", contenido="..."
            ),
            IntencionHistoriaLLM(
                resumen="consultar datos personales",
                business_actions=["consultar"],
                business_objects=["datos personales"],
                outcomes=["datos mostrados"],
            ),
            ServiceDomainsDeHistoria(candidatos_directos=[_asignado()]),
        )
        return self.chat.prompts[-1]

    def test_el_revisor_ve_el_objeto_de_negocio_que_aparece_tarde_en_el_rol(self):
        prompt = self._revisar()
        self.assertIn(
            _OBJETO_TARDIO,
            prompt,
            "el Service Role llega recortado antes del objeto de negocio: el revisor no puede "
            "juzgar DIRECTO_SIN_SERVICE_ROLE sin la parte del rol que nombra ese objeto",
        )

    def test_mismo_limite_de_rol_que_el_evaluador(self):
        self.assertGreaterEqual(
            ana._ROL_REVISION_MAX_CHARS,
            len(_ROL_LARGO),
            "el límite debe cubrir un Service Role típico del catálogo (mediana 309, p90 563)",
        )


if __name__ == "__main__":
    unittest.main()
