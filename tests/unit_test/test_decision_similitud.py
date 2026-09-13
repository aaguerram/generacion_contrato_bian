"""Regla de dominio: bandas por similitud (sin API, sin frameworks)."""

from __future__ import annotations

import unittest

from src.dominio.decision_similitud import Umbrales, clasificar, mejor_candidato
from src.dominio.modelos import CandidatoSD


def _cand(nombre: str, sim: float, score: float | None = None) -> CandidatoSD:
    return CandidatoSD(service_domain=nombre, score=score if score is not None else sim, similitud_nombre=sim)


class TestUmbrales(unittest.TestCase):
    def test_validos(self):
        u = Umbrales(alto=0.9, bajo=0.6)
        self.assertEqual((u.alto, u.bajo), (0.9, 0.6))

    def test_invalidos(self):
        with self.assertRaises(ValueError):
            Umbrales(alto=0.5, bajo=0.8)  # bajo > alto
        with self.assertRaises(ValueError):
            Umbrales(alto=1.5, bajo=0.6)


class TestClasificar(unittest.TestCase):
    U = Umbrales(alto=0.90, bajo=0.60)

    def test_alta(self):
        self.assertEqual(clasificar([_cand("Savings Account", 0.97)], self.U), "alta")

    def test_gris(self):
        self.assertEqual(clasificar([_cand("Card Authorization", 0.67)], self.U), "gris")

    def test_baja(self):
        self.assertEqual(clasificar([_cand("Savings Account", 0.57)], self.U), "baja")

    def test_sin_candidatos(self):
        self.assertEqual(clasificar([], self.U), "baja")

    def test_usa_la_mayor_similitud_no_la_de_recuperacion(self):
        cands = [
            _cand("Leasing", 0.50, score=0.95),          # gana en recuperación (score alto)
            _cand("Savings Account", 0.58, score=0.80),  # mayor similitud de nombre
        ]
        # decide por similitud_nombre (0.58 < 0.60 -> baja), no por score de recuperación
        self.assertEqual(clasificar(cands, self.U), "baja")
        self.assertEqual(mejor_candidato(cands).service_domain, "Savings Account")


if __name__ == "__main__":
    unittest.main()
