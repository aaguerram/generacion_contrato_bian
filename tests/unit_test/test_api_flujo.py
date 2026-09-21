"""El flujo del grafo tal como lo ve la interfaz: topología y resumen de los datos de cada nodo.

Determinista y sin base de datos: la topología se lee del grafo real compilado con `fake`, y el
resumen de estado es una función pura.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from api.serializacion import CLAVES_RESUMIDAS, MAX_ITEMS, MAX_TEXTO, huella_del_nodo, resumir  # noqa: E402


class TestResumirEstado(unittest.TestCase):
    """Lo que se guarda de cada nodo tiene que caber y tiene que decir qué recortó."""

    def test_el_catalogo_no_se_guarda_entero(self) -> None:
        """Viaja en el estado de casi todos los nodos: guardarlo 60 veces llenaría la base."""
        salida = resumir({"catalogo": list(range(341))})
        self.assertIn("_resumido", salida["catalogo"])
        self.assertIn("341", salida["catalogo"]["_resumido"])

    def test_lo_resumido_dice_que_habia_algo(self) -> None:
        """Recortar en silencio haría indistinguible 'no había datos' de 'no caben'."""
        for clave in CLAVES_RESUMIDAS:
            with self.subTest(clave=clave):
                self.assertIn("_resumido", resumir({clave: ["a", "b"]})[clave])

    def test_un_texto_largo_se_recorta_diciendo_cuanto(self) -> None:
        salida = resumir("x" * (MAX_TEXTO + 500))
        self.assertLess(len(salida), MAX_TEXTO + 60)
        self.assertIn("+500", salida)

    def test_una_lista_larga_se_recorta_diciendo_cuanto(self) -> None:
        salida = resumir(list(range(MAX_ITEMS + 7)))
        self.assertEqual(len(salida), MAX_ITEMS + 1)
        self.assertIn("_recortado", salida[-1])

    def test_un_objeto_del_dominio_se_convierte(self) -> None:
        from src.dominio.historias import IntencionHistoriaLLM

        salida = resumir(IntencionHistoriaLLM(resumen_funcional="ver mis datos"))
        self.assertIsInstance(salida, dict)
        self.assertEqual(salida["resumen_funcional"], "ver mis datos")

    def test_lo_que_no_sabe_convertir_no_revienta(self) -> None:
        class Raro:
            def __repr__(self) -> str:
                return "<raro>"

        self.assertEqual(resumir(Raro()), "<raro>")

    def test_una_estructura_muy_anidada_no_se_va_al_infinito(self) -> None:
        d: dict = {}
        actual = d
        for _ in range(40):
            actual["mas"] = {}
            actual = actual["mas"]
        import json

        json.dumps(resumir(d))  # si no acotara la profundidad, aquí reventaría


class TestHuellaDelNodo(unittest.TestCase):
    """De qué modelo salió la respuesta de un nodo. Es lo que se enseña en el modal."""

    def test_saca_proveedor_modelo_y_prompt(self) -> None:
        salida = {
            "huellas": [
                {
                    "prompt_id": "mapeo.intencion",
                    "provider_used": "freellmapi",
                    "model_used": "kimi-k3",
                }
            ]
        }
        self.assertEqual(huella_del_nodo(salida), ("freellmapi", "kimi-k3", "mapeo.intencion"))

    def test_un_nodo_determinista_no_tiene_huella(self) -> None:
        self.assertEqual(huella_del_nodo({"propuestos": [1, 2, 3]}), ("", "", ""))

    def test_la_busca_aunque_esté_anidada(self) -> None:
        salida = {"evaluaciones": [{"metadatos": {"prompt_id": "x", "model_used": "m"}}]}
        self.assertEqual(huella_del_nodo(salida)[1], "m")


class TestTopologiaDelGrafo(unittest.TestCase):
    """El dibujo se lee del grafo REAL: si alguien añade un nodo, aparece solo.

    Por eso se comprueba la FORMA (hay dos ámbitos, el puente entre ellos existe, los nodos LLM
    están marcados) y no una lista cerrada de nombres, que obligaría a tocar el test cada vez que
    el pipeline cambie y acabaría relajándose.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from api.grafo import topologia

        cls.g = topologia()

    def test_trae_los_dos_grafos(self) -> None:
        ambitos = {n.grafo for n in self.g.nodos}
        self.assertEqual(ambitos, {"principal", "historia"})

    def test_cada_arista_apunta_a_nodos_que_existen(self) -> None:
        ids = {n.id for n in self.g.nodos}
        for a in self.g.aristas:
            self.assertIn(a.origen, ids, f"arista con origen desconocido: {a.origen}")
            self.assertIn(a.destino, ids, f"arista con destino desconocido: {a.destino}")

    def test_el_puente_entre_los_dos_grafos_esta_declarado(self) -> None:
        """`procesar_historia` invoca el subgrafo con `.invoke()`, así que esa arista no existe
        en ninguno de los dos y hay que ponerla, o el dibujo serían dos islas."""
        puentes = [
            a
            for a in self.g.aristas
            if a.origen == "procesar_historia" and a.destino.endswith("__hu")
        ]
        self.assertEqual(len(puentes), 1)

    def test_los_nodos_que_llaman_al_modelo_estan_marcados(self) -> None:
        llm = {n.id for n in self.g.nodos if n.llm}
        self.assertIn("extraer_intencion", llm)
        self.assertIn("evaluar_candidato", llm)
        self.assertNotIn("clasificar", llm, "clasificar es determinista")

    def test_los_nodos_del_abanico_estan_marcados(self) -> None:
        abanico = {n.id for n in self.g.nodos if n.abanico}
        self.assertIn("evaluar_candidato", abanico)
        self.assertIn("procesar_historia", abanico)

    def test_los_extremos_de_los_dos_grafos_no_se_confunden(self) -> None:
        ids = [n.id for n in self.g.nodos]
        self.assertEqual(len(ids), len(set(ids)), "hay identificadores repetidos")


if __name__ == "__main__":
    unittest.main()
