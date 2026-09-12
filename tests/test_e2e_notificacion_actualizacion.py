"""Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks): equivalente a

    python -m src mapear-historias --directorio-hu tests/resources/notificacion_actualizacion \\
        --funcionalidad tests/resources/notificacion_actualizacion/funcionalidad-notificacion-actualizacion-datos.json \\
        --directorio tests/resources/notificacion_actualizacion --sin-timestamp

contra la evidencia BIAN cacheada real (`docs/bian-cache/`) y el LLM real (failover de
`routing.llm_priority` en `config.yaml`, con las API keys de `.env`).

Es la regresión del falso negativo observado en `salida/2026-09-11_17-59-40/` para la HU
"Notificar actualización de datos": el evaluador aislado clasificó Correspondence como
CONSUMED_DEPENDENCY/AUDIT_OR_NOTIFICATION (score 0.5033 < umbral_tentativo) aunque la propia
evaluación citaba `InitiateOutbound` como evidencia -- quedaba REJECTED/CONSUMED_DEPENDENCY sin
ninguna operación anclada. La corrección determinista (`determinar_promociones` /
`candidatos_operacion_elegibles` en `src/dominio/clasificacion_historias.py`) debe:

- recuperar y evaluar Correspondence (no desaparece);
- no dejarlo REJECTED por RELATED_NOT_OWNED ni por un CONSUMED_DEPENDENCY incompatible con la
  acción directa que la historia ejecuta;
- anclar `InitiateOutbound` (POST, BQ, grupo Outbound, bajo CorrespondenceOperatingSession) como
  operación seleccionada -- ver `docs/bian-cache/release14.0.0/Correspondence.json`.

Ver también `tests/test_grafo_mapeo.py::TestGrafoMapeoPromocionOwnership`, que prueba el MISMO
mecanismo sin LLM real (guionado, determinista, corre siempre). Esta prueba E2E depende del LLM
real y por eso queda gateada -- ver `e2e_support.py`.
"""

from __future__ import annotations

import unittest

from e2e_support import ejecutar_caso, requiere_e2e

_SD_ESPERADO = "Correspondence"
_OPERACION_ESPERADA = "InitiateOutbound"


@requiere_e2e
class TestE2ENotificacionActualizacion(unittest.TestCase):
    """Réplica del comando real de `mapear-historias` sobre
    `tests/resources/notificacion_actualizacion/` (entrada Y salida propias de esta prueba)."""

    def test_correspondence_owned_con_initiate_outbound(self):
        resultado = ejecutar_caso(
            "notificacion_actualizacion", "funcionalidad-notificacion-actualizacion-datos.json"
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
        self.assertIn(
            _OPERACION_ESPERADA, sd.selected_operations,
            f"'{_OPERACION_ESPERADA}' no quedó anclada; selected_operations={sd.selected_operations}",
        )

        # method/tipo/grupo vienen del anclaje por-historia, no del consolidado (que solo trae operationId).
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

        # trazabilidad + scores por etapa deben seguir presentes (sección 3 del plan: ningún
        # candidato pierde su score/rango/motivo/evidencia al pasar por la promoción determinista).
        self.assertTrue(sd.ownership_traceability or sd.dependency_traceability)
        self.assertTrue(sd.evidence.content_sha256)


if __name__ == "__main__":
    unittest.main()
