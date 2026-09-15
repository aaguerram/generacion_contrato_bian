"""Failover multi-proveedor / multi-modelo (sin API)."""

from __future__ import annotations

import unittest

from langchain_core.runnables import Runnable, RunnableLambda

from src.adaptadores.salida.llm.failover import (
    ChatConFailover,
    EntradaModelo,
    PeticionDemasiadoGrande,
    TodosLosModelosAgotados,
    degradar_a_siguiente,
    es_transitorio,
    no_cabe,
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
        for msg in (
            "429 Too Many Requests",
            "402 Payment Required",
            "quota exceeded",
            "bogus is not a valid model ID",
            "No endpoints found",
            "model `x` does not exist or you do not have access to it",
            "Request too large for model `x`",
            "This model does not support response format `json_schema`",
            "Failed to validate JSON. Please adjust your prompt",
        ):
            self.assertTrue(degradar_a_siguiente(RuntimeError(msg)), msg)
        self.assertFalse(degradar_a_siguiente(RuntimeError("KeyError: 'foo'")))


class TestChatConFailover(unittest.TestCase):
    def _ch(self, *entradas):
        return ChatConFailover(
            list(entradas), reintentos_transitorios=2, backoff_inicial_seg=0.0, backoff_max_seg=0.0
        )

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


class TestFailoverReintentaLaCadenaEnCadaLlamada(unittest.TestCase):
    """Cada llamada arranca en el PRIMER modelo de la cadena — con una excepción por TAMAÑO.

    Es la propiedad que hace utilizable el mix de proveedores: un modelo que rechaza un nodo por
    tamaño de prompt (Groq devuelve 413 "Request too large" con el catálogo CAG de ~48k tokens) NO
    queda descartado para el resto de la corrida; el siguiente nodo, cuyo prompt es mucho más
    pequeño, vuelve a intentarlo y normalmente le cabe. Si alguien añadiera un latch del tipo
    "recuerda el modelo que funcionó", el mix se quedaría pegado al último superviviente.

    El matiz que introduce el manejo del 413: lo que se recuerda no es el MODELO sino el TAMAÑO.
    Un prompt igual o mayor al que ya rechazó se salta **sin llamar** —repetirlo es gastar un
    round-trip para leer el mismo error, y medido pasaba en cada nodo grande de cada corrida—,
    pero uno más pequeño se sigue intentando primero, que es justo el caso que importa.

    Sin API.
    """

    def _cadena(self):
        # El primer modelo rechaza por tamaño; el respaldo responde siempre.
        grande = _entrada("groq", RuntimeError("413 Request too large"), "ok-groq")
        respaldo = _entrada("ollama", "ok-respaldo", "ok-respaldo", "ok-respaldo")
        return ChatConFailover([grande, respaldo], reintentos_transitorios=1)

    def test_un_prompt_mas_pequeno_vuelve_a_intentar_al_primer_modelo(self):
        chat = self._cadena()
        runnable = chat.with_structured_output(dict)

        self.assertEqual(runnable.invoke("P" * 5000), "ok-respaldo")
        self.assertEqual(chat.ultimo_uso().proveedor, "ollama")

        # Otro nodo, prompt mucho menor: la cadena vuelve a empezar por groq, que ahora responde.
        self.assertEqual(runnable.invoke("P" * 50), "ok-groq")
        self.assertEqual(chat.ultimo_uso().proveedor, "groq")

    def test_un_prompt_igual_o_mayor_se_salta_sin_llamar(self):
        chat = self._cadena()
        runnable = chat.with_structured_output(dict)
        runnable.invoke("P" * 5000)  # aprende que groq no acepta >= 5000

        # Si groq se volviera a llamar, su guion daría "ok-groq"; que devuelva el respaldo prueba
        # que ni se intentó (y por tanto no se gastó la llamada).
        self.assertEqual(runnable.invoke("P" * 6000), "ok-respaldo")
        self.assertEqual(chat.ultimo_uso().proveedor, "ollama")

    def test_si_ningun_modelo_acepta_el_tamano_se_distingue_del_agotamiento(self):
        """`PeticionDemasiadoGrande` existe para que quien armó el prompt pueda mandar menos."""
        chat = ChatConFailover(
            [
                _entrada("groq", RuntimeError("413 Request too large")),
                _entrada("gemini", RuntimeError("400 context length exceeded")),
            ],
            reintentos_transitorios=1,
        )
        with self.assertRaises(PeticionDemasiadoGrande):
            chat.with_structured_output(dict).invoke("P" * 5000)

    def test_agotar_la_cadena_por_cuota_NO_es_peticion_demasiado_grande(self):
        chat = ChatConFailover(
            [_entrada("groq", RuntimeError("429 rate limit"))], reintentos_transitorios=1
        )
        with self.assertRaises(TodosLosModelosAgotados) as ctx:
            chat.with_structured_output(dict).invoke("x")
        self.assertNotIsInstance(ctx.exception, PeticionDemasiadoGrande)

    def test_la_descripcion_de_la_cadena_no_cambia_entre_llamadas(self):
        chat = self._cadena()
        antes = chat.descripcion
        chat.with_structured_output(dict).invoke("x")
        self.assertEqual(chat.descripcion, antes)


class TestPrioridadPorNodo(unittest.TestCase):
    """`routing.llm_priority_por_nodo` da otro orden de proveedores a un nodo concreto."""

    def _config(self, por_nodo):
        from unit_test.support import config_test

        import dataclasses

        base = config_test()
        return dataclasses.replace(
            base, routing=dataclasses.replace(base.routing, llm_priority_por_nodo=por_nodo)
        )

    def test_sin_override_todos_los_nodos_comparten_la_cadena(self):
        config = self._config({})
        self.assertEqual(
            [p.nombre for p in config.orden_llm()],
            [p.nombre for p in config.orden_llm(nodo="mapeo.operaciones")],
        )

    def test_un_nodo_con_override_usa_su_propio_orden(self):
        config = self._config({"mapeo.operaciones": ("fake",)})
        self.assertEqual([p.nombre for p in config.orden_llm(nodo="mapeo.operaciones")], ["fake"])

    def test_proveedor_forzado_manda_sobre_el_override_del_nodo(self):
        """`--proveedor X` es una decisión del operador: no la puede pisar una entrada del yaml."""
        config = self._config({"mapeo.operaciones": ("noexiste",)})
        self.assertEqual(
            [p.nombre for p in config.orden_llm("fake", nodo="mapeo.operaciones")], ["fake"]
        )


class TestClasificacionPorTamano(unittest.TestCase):
    def test_reconoce_las_formas_habituales_del_413(self):
        for mensaje in (
            "Error code: 413 - Request too large for model",
            "400 context_length_exceeded",
            "Please reduce the length of the messages",
            "prompt is too long: 250000 tokens",
        ):
            self.assertTrue(no_cabe(RuntimeError(mensaje)), mensaje)

    def test_una_cuota_no_es_un_problema_de_tamano(self):
        self.assertFalse(no_cabe(RuntimeError("429 rate limit reached")))

    def test_por_tamano_tambien_se_pasa_al_siguiente_modelo(self):
        self.assertTrue(degradar_a_siguiente(RuntimeError("413 Request too large")))
