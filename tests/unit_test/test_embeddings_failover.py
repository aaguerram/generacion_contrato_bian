"""Failover de embeddings multi-modelo, en orden de precisión (sin API)."""

from __future__ import annotations

import unittest

from langchain_core.embeddings import Embeddings

from src.adaptadores.salida.embeddings_failover import EmbeddingsConFailover, TodosLosEmbeddingsAgotados


class _Emb(Embeddings):
    def __init__(self, dim: int, falla: Exception | None = None, falla_tras: int = 0):
        self.dim, self._falla, self._falla_tras, self.llamadas = dim, falla, falla_tras, 0

    def _v(self):
        self.llamadas += 1
        if self._falla and self.llamadas > self._falla_tras:
            raise self._falla
        return [0.1] * self.dim

    def embed_query(self, text):
        return self._v()

    def embed_documents(self, texts):
        return [self._v() for _ in texts]


class TestEmbeddingsConFailover(unittest.TestCase):
    def test_usa_el_primero_que_responde(self):
        fo = EmbeddingsConFailover([("cohere", "embed-v4.0", _Emb(1536)), ("gemini", "g", _Emb(768))])
        self.assertEqual(fo.resolver(), ("cohere", "embed-v4.0"))
        self.assertEqual(len(fo.embed_query("x")), 1536)

    def test_baja_al_siguiente_si_el_primero_no_tiene_cuota(self):
        malo = _Emb(1536, falla=RuntimeError("429 rate limit exceeded"))
        fo = EmbeddingsConFailover([("cohere", "embed-v4.0", malo), ("cohere", "embed-multilingual-v3.0", _Emb(1024))])
        self.assertEqual(fo.resolver(), ("cohere", "embed-multilingual-v3.0"))
        self.assertEqual(len(fo.embed_query("x")), 1024)

    def test_error_real_se_propaga(self):
        fo = EmbeddingsConFailover([("cohere", "e", _Emb(4, falla=ValueError("bug de config")))])
        with self.assertRaises(ValueError):
            fo.resolver()

    def test_todo_agotado(self):
        fo = EmbeddingsConFailover([
            ("a", "1", _Emb(4, falla=RuntimeError("429 quota"))),
            ("b", "2", _Emb(4, falla=RuntimeError("402 insufficient credits"))),
        ])
        with self.assertRaises(TodosLosEmbeddingsAgotados):
            fo.resolver()

    def test_caida_en_ejecucion_pasa_al_siguiente(self):
        malo = _Emb(1536, falla=RuntimeError("429 quota"), falla_tras=1)  # pasa el probe, cae después
        fo = EmbeddingsConFailover([("cohere", "embed-v4.0", malo), ("cohere", "v3", _Emb(1024))])
        fo.resolver()
        self.assertEqual(len(fo.embed_query("x")), 1024)  # ya delega en el 2º


if __name__ == "__main__":
    unittest.main()
