"""Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks): equivalente a

    python -m src mapear-historias --directorio-hu tests/resources/datos_personales \\
        --funcionalidad tests/resources/datos_personales/funcionalidad-actualizacion-datos-personales.json \\
        --directorio tests/resources/datos_personales --sin-timestamp

contra la evidencia BIAN cacheada real (`docs/bian-cache/`) y el LLM real (failover de
`routing.llm_priority` en `config.yaml`, con las API keys de `.env`). Es la regresión de la HU
"Crear pantalla de datos personales": debe reproducir los mismos Service Domain candidatos y las
mismas operaciones ancladas (`operationId`/`method`/`path`/`tipo`/`grupo`) que la corrida de
referencia -- en particular, `Party Reference Data Directory` con `RetrieveReference` /
`UpdateReference` (BQ `Reference`, expone `CellPhoneNumber`/`eMailAddress`) — nunca
`RetrieveDemographics` (BQ `Demographics`, sin ningún campo de contacto; ver GRAFOS_LANGGRAPH.md y
`src/dominio/cobertura_operaciones.py` para el detalle de la corrección).

La corrida de referencia completa vive en `tests/resources/datos_personales/expected-result.json`
(curada a mano, NUNCA hardcodeada aquí) — ver `tests/e2e/shared/e2e_common.py` para la regla
completa y qué compara `verificar_candidatos_y_operaciones()`.
"""

from __future__ import annotations

import unittest

from e2e.shared.e2e_common import (
    requiere_e2e,
    verificar_caso,
)

_CARPETA = "datos_personales"


@requiere_e2e
class TestE2EDatosPersonales(unittest.TestCase):
    """Réplica del comando real de `mapear-historias` sobre `tests/resources/datos_personales/`
    (entrada Y salida propias de esta prueba), usando el failover LLM de producción (sin
    `--proveedor`)."""

    def test_mismos_candidatos_y_operaciones_que_la_corrida_de_referencia(self):
        # `verificar_caso` corre el caso `E2E_REPETICIONES` veces (1 por defecto) y exige
        # mayoría: con 27% de fallo por varianza del modelo medido, una sola pasada no distingue
        # una regresión de una mala tirada.
        verificar_caso(self, _CARPETA)


if __name__ == "__main__":
    unittest.main()
