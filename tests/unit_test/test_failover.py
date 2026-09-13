"""Failover multi-proveedor / multi-modelo (sin API)."""

from __future__ import annotations

import unittest

from langchain_core.runnables import Runnable, RunnableLambda

from src.adaptadores.salida.llm.failover import (
    ChatConFailover,
    EntradaModelo,
    TodosLosModelosAgotados,
    degradar_a_siguiente,
    es_transitorio,
)


class _ChatGuion:
    """Chat de mentira: `with_structured_output` devuelve un runnable que reproduce `guion`."""

    def __init__(self, *guion):
        self._guion = list(guion)

    def with_structured_output(self, schema, **kw) -> Runnable:  # noqa: N802
        it = iter(self._guion)

        def _run(_entrada, config=None):
            paso = next(it)
            if isinstance(paso, Exception):
                raise paso
            return paso

        return RunnableLambda(_run)


def _entrada(nombre, *guion) -> EntradaModelo:
    return EntradaModelo(nombre, nombre, _ChatGuion(*guion))  # type: ignore[arg-type]


class TestClasificacionErrores(unittest.TestCase):
    def test_transitorio(self):
        self.assertTrue(es_transitorio(RuntimeError("503 UNAVAILABLE high demand")))
        self.assertFalse(es_transitorio(RuntimeError("429 RESOURCE_EXHAUSTED")))

    def test_degradar(self):
        for msg in ("429 Too Many Requests", "402 Payment Required", "quota exceeded",
                    "bogus is not a valid model ID", "No endpoints found",
                    "model `x` does not exist or you do not have access to it",
                    "Request too large for model `x`",
                    "This model does not support response format `json_schema`",
                    "Failed to validate JSON. Please adjust your prompt"):
            self.assertTrue(degradar_a_siguiente(RuntimeError(msg)), msg)
        self.assertFalse(degradar_a_siguiente(RuntimeError("KeyError: 'foo'")))


class TestChatConFailover(unittest.TestCase):
    def _ch(self, *entradas):
        return ChatConFailover(list(entradas), reintentos_transitorios=2,
                               backoff_inicial_seg=0.0, backoff_max_seg=0.0)

    def test_primer_modelo_ok(self):
        ch = self._ch(_entrada("a", "RESULTADO-A"), _entrada("b", "RESULTADO-B"))
        self.assertEqual(ch.with_structured_output(object).invoke({}), "RESULTADO-A")

    def test_degrada_por_cuota(self):
        ch = self._ch(
            _entrada("a", RuntimeError("429 rate limit exceeded")),
            _entrada("b", "RESULTADO-B"),
        )
        self.assertEqual(ch.with_structured_output(object).invoke({}), "RESULTADO-B")
        uso = ch.ultimo_uso()
        self.assertIsNotNone(uso)
        self.assertEqual((uso.proveedor, uso.modelo, uso.intento), ("b", "b", 2))

    def test_registra_primer_modelo_como_intento_uno(self):
        ch = self._ch(_entrada("a", "RESULTADO-A"), _entrada("b", "RESULTADO-B"))
        ch.with_structured_output(object).invoke({})
        uso = ch.ultimo_uso()
        self.assertIsNotNone(uso)
        self.assertEqual((uso.proveedor, uso.modelo, uso.intento), ("a", "a", 1))

    def test_reintenta_transitorio_y_luego_avanza(self):
        ch = self._ch(
            _entrada("a", RuntimeError("503 unavailable"), RuntimeError("503 unavailable")),
            _entrada("b", "OK-B"),
        )
        self.assertEqual(ch.with_structured_output(object).invoke({}), "OK-B")

    def test_error_real_se_propaga(self):
        ch = self._ch(_entrada("a", ValueError("bug de verdad")), _entrada("b", "OK-B"))
        with self.assertRaises(ValueError):
            ch.with_structured_output(object).invoke({})

    def test_todos_agotados(self):
        ch = self._ch(
            _entrada("a", RuntimeError("429 quota")),
            _entrada("b", RuntimeError("402 insufficient credits")),
        )
        with self.assertRaises(TodosLosModelosAgotados):
            ch.with_structured_output(object).invoke({})
        self.assertIsNone(ch.ultimo_uso())

    def test_descripcion(self):
        ch = self._ch(_entrada("a", "x"), _entrada("b", "y"))
        self.assertEqual(ch.descripcion, "a:a -> b:b")


if __name__ == "__main__":
    unittest.main()
