"""Normalización + carga real de SD.json (sin API)."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.recuperador_lexico import RecuperadorLexico
from src.dominio.normalizacion import normalizar

SD_JSON = Path(__file__).resolve().parents[2] / "docs" / "SD.json"


class TestNormalizacion(unittest.TestCase):
    def test_variantes_colapsan_al_mismo_token(self):
        objetivo = "issueddeviceadministration"
        for v in (
            "Issued Device Administration",
            "IssuedDeviceAdministration",
            "issued_device_administration",
            "  ISSUED-DEVICE-ADMINISTRATION ",
        ):
            self.assertEqual(normalizar(v), objetivo)


class TestCatalogoJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = CatalogoJson(SD_JSON)

    def test_carga(self):
        entradas = self.cat.cargar()
        self.assertGreater(len(entradas), 300)  # 341
        self.assertTrue(all(e.service_domain for e in entradas))

    def test_enriquece_con_jerarquia_bian(self):
        # bian-business-areas.json (en docs/) aporta Business Area / Business Domain por SD
        e = self.cat.buscar_exacto("Party Authentication")
        self.assertIsNotNone(e)
        self.assertEqual(e.business_area, "Sales and Service")
        self.assertTrue(e.business_domain)
        # los 341 SD de SD.json están en la jerarquía
        self.assertTrue(all(x.business_area for x in self.cat.cargar()))

    def test_exacto_con_variantes(self):
        for v in ("Current Account", "current account", "CurrentAccount", "CURRENT_ACCOUNT"):
            e = self.cat.buscar_exacto(v)
            self.assertIsNotNone(e, v)
            self.assertEqual(e.service_domain, "Current Account")

    def test_inexistente(self):
        self.assertIsNone(self.cat.buscar_exacto("Segundo Factor Tokens XYZ"))


class TestRecuperadorLexico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = RecuperadorLexico(CatalogoJson(SD_JSON))

    def test_typo_rankea_primero_y_similitud_alta(self):
        top = self.rec.recuperar("Issued Device Adminstration", 6)  # falta una 'i'
        self.assertEqual(top[0].service_domain, "Issued Device Administration")
        self.assertGreater(top[0].similitud_nombre, 0.9)  # estricta -> alta

    def test_orden_de_palabras(self):
        top = self.rec.recuperar("authentication party", 5)
        m = next(c for c in top if c.service_domain == "Party Authentication")
        self.assertGreater(m.similitud_nombre, 0.9)  # token_sort tolera el orden

    def test_nombre_incompleto_similitud_baja(self):
        top = self.rec.recuperar("saving", 6)
        m = next((c for c in top if c.service_domain == "Savings Account"), None)
        self.assertIsNotNone(m)              # WRatio lo mete en el shortlist
        self.assertLess(m.similitud_nombre, 0.60)   # pero estricta -> baja

    def test_devuelve_k_candidatos(self):
        self.assertEqual(len(self.rec.recuperar("cualquier cosa rara", 4)), 4)


if __name__ == "__main__":
    unittest.main()
