"""Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks): equivalente al
comando manual usado para validar esta corrección en producción real —

    python -m src mapear-historias --directorio-hu ./HU \\
        --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json \\
        --directorio ./salida

replicado sobre su propia copia congelada en `tests/resources/datos_personales_notificacion/`
(nunca sobre `./HU` / `./ejemplos`, que son mutables y son para pruebas manuales del CLI — ver
`e2e_support.py`).

Es un escenario DISTINTO de `test_e2e_notificacion_actualizacion.py`: la misma HU "Notificar
actualización de datos", pero bajo la funcionalidad macro más amplia "Actualización de datos
personales" (la misma que usa `test_e2e_datos_personales.py` para su propia HU) en vez de
"Notificar actualización de datos". El framing de la funcionalidad SÍ cambia el score que el LLM
le da al candidato (observado en corridas reales: 0.5033 / 0.6733 / 0.98 para Correspondence según
el contexto y el modelo del failover que respondió) — por eso vale la pena cubrir ambos framings
por separado, no asumir que uno generaliza al otro.

Regresión de los dos gaps corregidos el mismo día que el de ownership (ver CLAUDE.md, paso 9 y
`finalizar_por_operacion_solida` / `resolver_operation_id`):
- Correspondence no debe quedar REJECTED (ni por RELATED_NOT_OWNED ni por un CONSUMED_DEPENDENCY
  incompatible con la acción directa que la historia ejecuta) — se corrija por promoción de
  ownership o porque el LLM ya lo evaluó OWNED_CONTRACT desde el inicio.
- Si el LLM ancla `InitiateOutbound` (con o sin el formato exacto del operationId), debe terminar
  citado en `selected_operations`, method=POST, tipo=BQ, grupo=Outbound.

Equivalente determinista sin LLM real (corre siempre): `tests/test_grafo_mapeo.py`
(`TestGrafoMapeoPromocionOwnership`, `TestGrafoMapeoFinalizacionPorOperacion`). Esta prueba
depende del LLM real y por eso queda gateada — ver `e2e_support.py`.
"""

from __future__ import annotations

import unittest

from e2e_support import ejecutar_caso, requiere_e2e

_SD_ESPERADO = "Correspondence"
_OPERACION_ESPERADA = "InitiateOutbound"


@requiere_e2e
class TestE2EDatosPersonalesNotificacion(unittest.TestCase):
    """Réplica del comando real de `mapear-historias` usado para validar esta corrección, sobre
    `tests/resources/datos_personales_notificacion/` (entrada Y salida propias de esta prueba)."""

    def test_correspondence_no_queda_rejected_y_ancla_initiate_outbound_si_corresponde(self):
        resultado = ejecutar_caso(
            "datos_personales_notificacion", "funcionalidad-actualizacion-datos-personales.json"
        )

        consolidados = {c.service_domain: c for c in resultado.service_domains_consolidados}
        self.assertIn(
            _SD_ESPERADO, consolidados,
            f"'{_SD_ESPERADO}' ni siquiera fue evaluado; consolidados: {sorted(consolidados)}",
        )
        sd = consolidados[_SD_ESPERADO]

        self.assertEqual(
            sd.contract_role, "OWNED_CONTRACT",
            f"'{_SD_ESPERADO}' debía detectarse como OWNED_CONTRACT, salió {sd.contract_role} "
            f"(motivo={sd.motivo})",
        )
        self.assertNotEqual(
            sd.decision, "REJECTED",
            f"'{_SD_ESPERADO}' fue rechazado (motivo={sd.motivo}); no debía quedar REJECTED por "
            "RELATED_NOT_OWNED ni por un CONSUMED_DEPENDENCY incompatible con la acción directa "
            "que la historia ejecuta",
        )

        # Si el paso de operaciones logró anclar algo para este SD (puede fallar por razones
        # ajenas al ownership: cuota agotada en el proveedor que respondió esa llamada), debe ser
        # la operación correcta con los atributos BIAN correctos -- nunca aceptar cualquier cosa.
        if sd.selected_operations:
            self.assertIn(_OPERACION_ESPERADA, sd.selected_operations)
            hu = next(h for h in resultado.historias if any(
                a.service_domain == _SD_ESPERADO
                for a in (*h.service_domains.candidatos_directos, *h.service_domains.candidatos_tentativos)
            ))
            asignado = next(
                a for a in (*hu.service_domains.candidatos_directos, *hu.service_domains.candidatos_tentativos)
                if a.service_domain == _SD_ESPERADO
            )
            op = next(o for o in asignado.operaciones_bian if o.operation_id == _OPERACION_ESPERADA)
            self.assertEqual(op.method, "POST")
            self.assertEqual(op.tipo, "BQ")
            self.assertEqual(op.grupo, "Outbound")

        self.assertTrue(sd.ownership_traceability or sd.dependency_traceability)
        self.assertTrue(sd.evidence.content_sha256)


if __name__ == "__main__":
    unittest.main()
