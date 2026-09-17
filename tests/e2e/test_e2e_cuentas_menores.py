"""Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks): equivalente a

    python -m src mapear-historias --directorio-hu tests/resources/cuentas_menores \\
        --funcionalidad tests/resources/cuentas_menores/funcionalidad-actualizacion-datos-personales.json \\
        --directorio tests/resources/cuentas_menores --sin-timestamp

contra la evidencia BIAN cacheada real (`docs/bian-cache/`) y el LLM real (failover de
`routing.llm_priority` en `config.yaml`, con las API keys de `.env`). Es la regresión de la HU
"Actualizar cuentas de menores": la historia pide DOS datos que viven en DOS Behavior Qualifier
distintos del MISMO Service Domain -- los datos de contacto en `Reference` y la relación
menor↔tutor ("el nombre del tutor será enviado por BE") en `Associations`, el único BQ de
`Party Reference Data Directory` que expone la asociación entre dos Party
(`AssociateReference`/`AssociateType`).

La corrida del 2026-09-15 anclaba solo `RetrieveReference` y terminaba en verde
(`operation_coverage_rate` 1.0) porque el nodo de operaciones nunca recibía los datos que la
historia pedía: la intención ya los había extraído (`business_objects`) y el prompt solo veía la
HU cruda, con la regla "conjunto mínimo suficiente" empujando a parar en la primera operación que
resuelve el escenario principal. Ver `cobertura_datos_requeridos` en
`src/dominio/cobertura_operaciones.py` y la regresión determinista equivalente (sin LLM, corre
siempre) en `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoCoberturaDatosRequeridos`.

La corrida de referencia completa vive en `tests/resources/cuentas_menores/expected-result.json`
(curada a mano, NUNCA hardcodeada aquí) — ver `tests/e2e/shared/e2e_common.py` para la regla
completa y qué compara `verificar_candidatos_y_operaciones()`.
"""

from __future__ import annotations

import unittest

from e2e.shared.e2e_common import (
    requiere_e2e,
    verificar_caso,
)

_CARPETA = "cuentas_menores"


@requiere_e2e
class TestE2ECuentasMenores(unittest.TestCase):
    """Réplica del comando real de `mapear-historias` sobre `tests/resources/cuentas_menores/`
    (entrada Y salida propias de esta prueba), usando el failover LLM de producción (sin
    `--proveedor`)."""

    def test_mismos_candidatos_y_operaciones_que_la_corrida_de_referencia(self):
        # `verificar_caso` corre el caso `E2E_REPETICIONES` veces (1 por defecto) y exige
        # mayoría: con 27% de fallo por varianza del modelo medido, una sola pasada no distingue
        # una regresión de una mala tirada.
        verificar_caso(self, _CARPETA)


if __name__ == "__main__":
    unittest.main()
