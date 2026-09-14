"""Adaptadores nuevos de retrieval: grafo, reranker y Qdrant. Deterministas, sin red ni modelos.

Lo que se fija aquí es la degradación: las tres piezas son OPCIONALES y ninguna puede tumbar una
corrida cuando falta su dependencia (grafo sin ingestar, `sentence-transformers` sin instalar,
Qdrant apagado). Y el respaldo del reranker no reordena a propósito: medido con
`scripts/evaluate_retrieval/`, reordenar por solapamiento léxico hundía Recall@10 de 0.71 a 0.14,
porque compara una consulta en español contra el catálogo BIAN en inglés.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.grafo_bian_json import GrafoBianJson
from src.adaptadores.salida.recuperador_qdrant import RecuperadorQdrant
from src.adaptadores.salida.reranker_local import (
    RerankerCrossEncoder,
    RerankerLexico,
    RerankerNulo,
)

_DOCS = [
    ("correspondence", "Correspondence. Outbound correspondence generation and tracking."),
    ("party", "Party Reference Data Directory. Contact details and demographic details."),
    ("fraud", "Fraud Evaluation. Assess suspicious activity."),
]


class TestGrafoBianJsonSinArchivo(unittest.TestCase):
    def test_sin_grafo_ingestado_devuelve_vacio_y_no_revienta(self):
        adaptador = GrafoBianJson("/no/existe/grafo.json")
        self.assertEqual(adaptador.expandir(["Correspondence"], tope=3), [])
        # Segunda llamada: no debe volver a avisar ni fallar.
        self.assertEqual(adaptador.expandir(["Correspondence"], tope=3), [])

    def test_sin_candidatos_de_partida_no_consulta_nada(self):
        self.assertEqual(GrafoBianJson("/no/existe.json").expandir([], tope=3), [])


class TestRerankers(unittest.TestCase):
    def test_el_nulo_conserva_el_orden(self):
        salida = RerankerNulo().reordenar("cualquier consulta", _DOCS, tope=3)
        self.assertEqual([c for c, _ in salida], ["correspondence", "party", "fraud"])

    def test_el_nulo_respeta_el_tope(self):
        self.assertEqual(len(RerankerNulo().reordenar("x", _DOCS, tope=2)), 2)

    def test_el_lexico_ordena_por_solapamiento(self):
        salida = RerankerLexico().reordenar("contact details demographic", _DOCS, tope=3)
        self.assertEqual(salida[0][0], "party")

    def test_cross_encoder_sin_dependencia_no_reordena_en_vez_de_fallar(self):
        """Si `sentence-transformers` no está, el respaldo es NO reordenar (no el léxico)."""
        reranker = RerankerCrossEncoder("modelo-que-no-existe")
        reranker._fallido = True  # simula el ImportError sin depender de si está instalado
        salida = reranker.reordenar("contact details", _DOCS, tope=3)
        self.assertEqual([c for c, _ in salida], ["correspondence", "party", "fraud"])

    def test_sin_documentos_devuelve_vacio(self):
        self.assertEqual(RerankerCrossEncoder().reordenar("x", [], tope=5), [])


class _EmbeddingsFalsos:
    def embed_query(self, texto: str):
        return [0.0, 1.0]


class TestRecuperadorQdrantApagado(unittest.TestCase):
    def test_sin_servidor_devuelve_vacio(self):
        r = RecuperadorQdrant(_EmbeddingsFalsos(), url="http://127.0.0.1:1", timeout=0.2)
        self.assertEqual(r.recuperar("consulta", 5), [])

    def test_no_reintenta_indefinidamente(self):
        r = RecuperadorQdrant(_EmbeddingsFalsos(), url="http://127.0.0.1:1", timeout=0.2)
        r.recuperar("consulta", 5)
        self.assertTrue(
            r._fallido, "tras fallar una vez debe quedar inactivo, no reintentar por HU"
        )


if __name__ == "__main__":
    unittest.main()
