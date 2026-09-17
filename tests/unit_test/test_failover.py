"""Failover multi-proveedor / multi-modelo (sin API)."""

from __future__ import annotations

import unittest
from unittest import mock

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
from src.adaptadores.salida.llm.tokens import estimar_tokens


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


class TestPresupuestoDeclaradoPorModelo(unittest.TestCase):
    """`max_input_tokens` por modelo: el prompt se mide ANTES de llamar.

    La diferencia con el aprendizaje por 413 es cuándo actúa. El aprendizaje necesita que el
    modelo ya haya rechazado una petición al menos una vez -y esa primera llamada se paga en cada
    proceso nuevo-; el presupuesto declarado evita también esa. Con la cadena real
    (`groq -> gemini -> ...`) y el catálogo BIAN de ~36k tokens, eso son dos llamadas fallidas a
    Groq menos por CADA nodo de prompt grande de CADA corrida.

    Sin API.
    """

    def _entrada_con_presupuesto(self, nombre, tope, *guion) -> EntradaModelo:
        return EntradaModelo(
            nombre, nombre, _ChatGuion(*guion), max_input_tokens=tope  # type: ignore[arg-type]
        )

    def test_un_prompt_que_no_cabe_en_el_presupuesto_no_gasta_la_llamada(self):
        # Si `pequeno` llegara a llamarse, su guion daría "ok-pequeno".
        pequeno = self._entrada_con_presupuesto("groq", 10, "ok-pequeno")
        grande = self._entrada_con_presupuesto("gemini", 100_000, "ok-grande")
        chat = ChatConFailover([pequeno, grande], reintentos_transitorios=1)

        self.assertEqual(chat.with_structured_output(dict).invoke("P" * 4000), "ok-grande")
        self.assertEqual(chat.ultimo_uso().proveedor, "gemini")

    def test_el_mismo_modelo_sigue_siendo_el_primero_para_un_prompt_que_si_cabe(self):
        """No es un latch sobre el modelo: es una decisión sobre ESTA petición."""
        pequeno = self._entrada_con_presupuesto("groq", 50, "ok-pequeno")
        grande = self._entrada_con_presupuesto("gemini", 100_000, "ok-grande")
        chat = ChatConFailover([pequeno, grande], reintentos_transitorios=1)
        runnable = chat.with_structured_output(dict)

        runnable.invoke("P" * 4000)  # no cabe en groq
        self.assertEqual(runnable.invoke("P" * 8), "ok-pequeno")  # este sí
        self.assertEqual(chat.ultimo_uso().proveedor, "groq")

    def test_sin_presupuesto_declarado_se_llama_como_siempre(self):
        chat = ChatConFailover([_entrada("groq", "ok-groq")], reintentos_transitorios=1)
        self.assertEqual(chat.with_structured_output(dict).invoke("P" * 100_000), "ok-groq")

    def test_si_ningun_presupuesto_admite_el_prompt_se_pide_reducirlo(self):
        """`PeticionDemasiadoGrande`, no `TodosLosModelosAgotados`: el analista reduce el catálogo.

        Es la propiedad que hace que esto sea gratis en vez de peligroso — cero llamadas gastadas
        y, aun así, la misma señal que habría producido un 413 real.
        """
        chat = ChatConFailover(
            [
                self._entrada_con_presupuesto("groq", 10, "nunca"),
                self._entrada_con_presupuesto("gemini", 20, "nunca"),
            ],
            reintentos_transitorios=1,
        )
        with self.assertRaises(PeticionDemasiadoGrande) as ctx:
            chat.with_structured_output(dict).invoke("P" * 4000)
        # El mensaje nombra qué presupuestos no daban: sin eso, diagnosticar por qué una corrida
        # no llamó a nadie obligaba a leer el yaml a mano.
        self.assertIn("groq:groq<=10", str(ctx.exception))
        self.assertIn("gemini:gemini<=20", str(ctx.exception))

    def test_el_presupuesto_no_tapa_el_413_real(self):
        """El estimador es aproximado: un modelo con presupuesto generoso de más sigue pudiendo
        devolver 413, y ese camino tiene que seguir funcionando."""
        optimista = self._entrada_con_presupuesto(
            "groq", 100_000, RuntimeError("413 Request too large")
        )
        respaldo = self._entrada_con_presupuesto("gemini", 100_000, "ok-respaldo")
        chat = ChatConFailover([optimista, respaldo], reintentos_transitorios=1)
        self.assertEqual(chat.with_structured_output(dict).invoke("P" * 4000), "ok-respaldo")


class TestEstimacionDeTokens(unittest.TestCase):
    def test_crece_con_el_texto_y_es_cero_para_vacio(self):
        self.assertEqual(estimar_tokens(""), 0)
        self.assertLess(estimar_tokens("hola"), estimar_tokens("hola " * 500))

    def test_el_heuristico_por_caracteres_respeta_la_razon(self):
        """Por defecto la estimación es `len / chars_por_token`, redondeando hacia arriba."""
        self.assertEqual(estimar_tokens("x" * 400, chars_por_token=4.0), 100)
        self.assertEqual(estimar_tokens("x" * 401, chars_por_token=4.0), 101)
        self.assertEqual(estimar_tokens("x" * 400, chars_por_token=2.0), 200)

    def test_una_razon_invalida_no_revienta(self):
        self.assertEqual(estimar_tokens("x" * 400, chars_por_token=0), 100)

    def test_el_default_no_toca_tiktoken(self):
        """Regresión del cuelgue: `tiktoken.get_encoding` DESCARGA el vocabulario la primera vez
        y sin red no vuelve nunca. Si el camino por defecto lo tocara, colgaría la primera
        llamada LLM de cada corrida en una máquina sin salida a Internet."""
        with mock.patch("src.adaptadores.salida.llm.tokens._encoder") as encoder:
            estimar_tokens("x" * 400)
            encoder.assert_not_called()

    def test_un_tokenizador_roto_degrada_al_heuristico(self):
        roto = mock.Mock()
        roto.encode.side_effect = RuntimeError("boom")
        with mock.patch("src.adaptadores.salida.llm.tokens._encoder", return_value=roto):
            self.assertEqual(
                estimar_tokens("x" * 400, chars_por_token=4.0, tokenizador="tiktoken"), 100
            )

    def test_tiktoken_se_usa_solo_si_se_pide(self):
        cod = mock.Mock()
        cod.encode.return_value = [0] * 7
        with mock.patch("src.adaptadores.salida.llm.tokens._encoder", return_value=cod):
            self.assertEqual(estimar_tokens("x" * 400, tokenizador="tiktoken"), 7)


class TestPresupuestoDesdeConfig(unittest.TestCase):
    """`providers.<n>.llm.models[].max_input_tokens` y su valor por defecto por proveedor."""

    def _prov(self, llm: dict):
        from src.configuracion.config_yaml import _proveedor

        return _proveedor("p", {"api_key_env": "", "llm": llm})

    def test_forma_de_siempre_sigue_funcionando(self):
        prov = self._prov({"models": ["a", "b"]})
        self.assertEqual(prov.llm_models, ("a", "b"))
        self.assertIsNone(prov.max_input_tokens("a"))

    def test_presupuesto_por_modelo(self):
        prov = self._prov({"models": ["a", {"name": "b", "max_input_tokens": 12000}]})
        self.assertEqual(prov.llm_models, ("a", "b"))
        self.assertIsNone(prov.max_input_tokens("a"))
        self.assertEqual(prov.max_input_tokens("b"), 12000)

    def test_el_default_del_proveedor_se_aplica_a_sus_modelos(self):
        prov = self._prov(
            {"max_input_tokens": 12000, "models": ["a", {"name": "b", "max_input_tokens": 500}]}
        )
        self.assertEqual(prov.max_input_tokens("a"), 12000)
        self.assertEqual(prov.max_input_tokens("b"), 500, "el del modelo manda sobre el default")

    def test_un_presupuesto_invalido_falla_al_cargar_y_no_en_la_primera_llamada(self):
        for llm in (
            {"max_input_tokens": 0, "models": ["a"]},
            {"models": [{"name": "a", "max_input_tokens": -1}]},
            {"models": [{"name": "a", "max_input_tokens": "muchos"}]},
            {"models": [{"max_input_tokens": 100}]},  # objeto sin `name`
        ):
            with self.assertRaises(ValueError):
                self._prov(llm)

    def test_config_yaml_real_declara_presupuesto_en_toda_la_cadena_de_failover(self):
        """Regresión del objetivo de la feature: si alguien añade un modelo a la cadena por
        defecto sin presupuesto, vuelve a gastarse un 413 por corrida para descubrirlo."""
        from src.configuracion.config_yaml import cargar_config

        config = cargar_config()
        sin_presupuesto = [
            f"{prov}:{modelo}"
            for prov in config.routing.llm_priority
            for modelo in getattr(config.proveedores.get(prov), "llm_models", ())
            if config.proveedores[prov].max_input_tokens(modelo) is None
        ]
        self.assertEqual(sin_presupuesto, [])
