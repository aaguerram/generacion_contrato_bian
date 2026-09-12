"""Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks): equivalente a

    python -m src mapear-historias --directorio-hu tests/resources/datos_personales \\
        --funcionalidad tests/resources/datos_personales/funcionalidad-actualizacion-datos-personales.json \\
        --directorio tests/resources/datos_personales --sin-timestamp

contra la evidencia BIAN cacheada real (`docs/bian-cache/`) y el LLM real (failover de
`routing.llm_priority` en `config.yaml`, con las API keys de `.env`). Es la regresión de la HU
"Crear pantalla de datos personales": debe detectar el Service Domain "Party Reference Data
Directory" como OWNED (nunca REJECTED) y anclar una operación del BQ `Reference`
(`RetrieveReference` / `UpdateReference`, que exponen `CellPhoneNumber`/`eMailAddress`) — nunca
`RetrieveDemographics` (BQ `Demographics`, sin ningún campo de contacto; ver GRAFOS_LANGGRAPH.md y
`src/dominio/cobertura_operaciones.py` para el detalle de la corrección).

Datos y estructura reutilizable para futuras pruebas E2E: ver `tests/e2e_support.py`.
"""

from __future__ import annotations

import unittest

from e2e_support import ejecutar_caso, requiere_e2e

_SD_ESPERADO = "Party Reference Data Directory"
_OPERACIONES_CORRECTAS = ("RetrieveReference", "UpdateReference")
_OPERACION_INCORRECTA = "RetrieveDemographics"


@requiere_e2e
class TestE2EDatosPersonales(unittest.TestCase):
    """Réplica del comando real de `mapear-historias` sobre `tests/resources/datos_personales/`
    (entrada Y salida propias de esta prueba), usando el failover LLM de producción (sin
    `--proveedor`)."""

    def test_detecta_service_domain_y_operacion_correctos(self):
        resultado = ejecutar_caso("datos_personales", "funcionalidad-actualizacion-datos-personales.json")

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
            f"'{_SD_ESPERADO}' fue rechazado (motivo={sd.motivo}); debía quedar SELECTED o, en el "
            "peor caso, UNRESOLVED, nunca REJECTED",
        )

        self.assertTrue(
            any(op in sd.selected_operations for op in _OPERACIONES_CORRECTAS),
            f"no se ancló ninguna operación del BQ Reference {_OPERACIONES_CORRECTAS}; "
            f"selected_operations={sd.selected_operations}",
        )
        self.assertNotIn(
            _OPERACION_INCORRECTA, sd.selected_operations,
            f"regresión: volvió a seleccionarse '{_OPERACION_INCORRECTA}' (BQ Demographics, sin "
            "ningún campo de contacto) para una historia de celular/correo",
        )


if __name__ == "__main__":
    unittest.main()
