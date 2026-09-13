"""2º pase determinista: detección léxica de Service Domains que el LLM no propuso."""

from __future__ import annotations

import unittest

from src.dominio.deteccion_omitidos import detectar_omitidos
from src.dominio.historias import IntencionHistoriaLLM
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar


def _cat(*pares: tuple[str, str]) -> list[EntradaCatalogo]:
    return [EntradaCatalogo(service_domain=n, service_role=r) for n, r in pares]


class TestDetectarOmitidos(unittest.TestCase):
    CAT = _cat(
        ("Party Authentication", "Manage the authentication of a customer party"),
        ("Transaction Authorization", "Authorize a payment transaction against limits"),
        ("Card Collections", "Chase overdue card balances"),
    )

    def test_propone_sd_no_evaluado_que_casa_con_las_senales(self):
        analisis = IntencionHistoriaLLM(
            business_actions=["authorize"], business_objects=["transaction"]
        )
        omitidos = detectar_omitidos(analisis, self.CAT, ya_propuestos=set())
        self.assertIn("Transaction Authorization", [o.service_domain for o in omitidos])

    def test_no_repite_lo_ya_evaluado(self):
        analisis = IntencionHistoriaLLM(
            business_actions=["authorize"], business_objects=["transaction"]
        )
        ya = {normalizar("Transaction Authorization")}
        omitidos = detectar_omitidos(analisis, self.CAT, ya_propuestos=ya)
        self.assertNotIn("Transaction Authorization", [o.service_domain for o in omitidos])

    def test_sin_senales_no_devuelve_nada(self):
        self.assertEqual(detectar_omitidos(IntencionHistoriaLLM(), self.CAT, set()), [])

    def test_respeta_top_n(self):
        analisis = IntencionHistoriaLLM(
            business_actions=["authenticate", "authorize"],
            business_objects=["customer", "transaction", "card"],
        )
        self.assertLessEqual(len(detectar_omitidos(analisis, self.CAT, set(), top_n=1)), 1)


if __name__ == "__main__":
    unittest.main()
