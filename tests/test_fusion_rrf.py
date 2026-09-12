"""Reciprocal Rank Fusion: puro, sin API."""

from __future__ import annotations

import unittest

from src.dominio.fusion_rrf import fusion_rrf


class TestFusionRRF(unittest.TestCase):
    def test_un_solo_ranking_conserva_el_orden(self):
        r = fusion_rrf([["A", "B", "C"]])
        self.assertEqual([n for n, _ in r], ["A", "B", "C"])

    def test_coincidencia_en_ambos_rankings_pesa_mas_que_una_sola_fuente(self):
        # "B" es 2º en léxico y 1º en vectorial -> debe superar a "A" (1º en léxico, ausente en vectorial)
        r = fusion_rrf([["A", "B"], ["B", "C"]])
        nombres = [n for n, _ in r]
        self.assertEqual(nombres[0], "B")
        self.assertIn("A", nombres)
        self.assertIn("C", nombres)

    def test_lista_vacia(self):
        self.assertEqual(fusion_rrf([]), [])
        self.assertEqual(fusion_rrf([[], []]), [])

    def test_desempate_alfabetico_estable(self):
        r = fusion_rrf([["Z"], ["A"]])  # ambos en posición 0 -> mismo score
        self.assertEqual([n for n, _ in r], ["A", "Z"])

    def test_k_mas_alto_aplana_las_diferencias_de_posicion(self):
        bajo = dict(fusion_rrf([["A", "B"]], k=1))
        alto = dict(fusion_rrf([["A", "B"]], k=1000))
        # con k bajo, el hueco entre 1º y 2º es proporcionalmente mayor que con k alto
        self.assertGreater(bajo["A"] - bajo["B"], alto["A"] - alto["B"])


if __name__ == "__main__":
    unittest.main()
