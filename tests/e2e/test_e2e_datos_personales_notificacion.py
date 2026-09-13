"""Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks): equivalente al
comando manual usado para validar esta corrección en producción real —

    python -m src mapear-historias --directorio-hu ./HU \\
        --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json \\
        --directorio ./salida

replicado sobre su propia copia congelada en `tests/resources/datos_personales_notificacion/`
(nunca sobre `./HU` / `./ejemplos`, que son mutables y son para pruebas manuales del CLI — ver
`tests/e2e/shared/e2e_common.py`).

Es un escenario DISTINTO del de `datos_personales`: la misma HU "Notificar actualización de
datos", pero bajo la funcionalidad macro más amplia "Actualización de datos personales" (la misma
que usa `datos_personales` para su propia HU) en vez de "Notificar actualización de datos". El
framing de la funcionalidad SÍ cambia el score que el LLM le da al candidato (observado en
corridas reales: 0.5033 / 0.6733 / 0.98 para Correspondence según el contexto y el modelo del
failover que respondió) — por eso vale la pena cubrir ambos framings por separado, no asumir que
uno generaliza al otro.

Regresión de los dos gaps corregidos el mismo día que el de ownership (ver CLAUDE.md, paso 9 y
`finalizar_por_operacion_solida` / `resolver_operation_id`): la corrida debe reproducir los mismos
Service Domain candidatos y las mismas operaciones ancladas que la corrida de referencia —
`Correspondence` con `InitiateOutbound` (POST, BQ, grupo Outbound), no `REJECTED` ni sin operación.

Equivalente determinista sin LLM real (corre siempre): `tests/unit_test/test_grafo_mapeo.py`
(`TestGrafoMapeoPromocionOwnership`, `TestGrafoMapeoFinalizacionPorOperacion`). Esta prueba
depende del LLM real y por eso queda gateada — ver `tests/e2e/shared/e2e_common.py`.

La corrida de referencia completa vive en
`tests/resources/datos_personales_notificacion/expected-result.json` (curada a mano, NUNCA
hardcodeada aquí) — ver `tests/e2e/shared/e2e_common.py` para la regla completa y qué compara
`verificar_candidatos_y_operaciones()`.
"""

from __future__ import annotations

import unittest

from e2e.shared.e2e_common import cargar_esperado, ejecutar_caso, requiere_e2e, verificar_candidatos_y_operaciones

_CARPETA = "datos_personales_notificacion"


@requiere_e2e
class TestE2EDatosPersonalesNotificacion(unittest.TestCase):
    """Réplica del comando real de `mapear-historias` usado para validar esta corrección, sobre
    `tests/resources/datos_personales_notificacion/` (entrada Y salida propias de esta prueba)."""

    def test_mismos_candidatos_y_operaciones_que_la_corrida_de_referencia(self):
        resultado = ejecutar_caso(_CARPETA)
        esperado = cargar_esperado(_CARPETA)
        verificar_candidatos_y_operaciones(self, resultado, esperado)


if __name__ == "__main__":
    unittest.main()
