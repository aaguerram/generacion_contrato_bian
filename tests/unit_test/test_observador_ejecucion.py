"""El observador del grafo: qué ve, qué no rompe, y cómo corta la corrida.

Determinista y sin red: `--proveedor fake` y la evidencia local de `docs/`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.aplicacion.puertos.observador_ejecucion import (  # noqa: E402
    EjecucionDetenida,
    ObservadorEjecucionPort,
)
from src.configuracion.contenedor import crear_caso_uso_mapeo  # noqa: E402
from unit_test.support import config_test  # noqa: E402

HU = RAIZ / "tests" / "resources" / "datos_personales"


class _ObservadorEspia:
    """Apunta todo lo que le cuentan. Opcionalmente pide parar tras un nodo."""

    def __init__(self, detener_en: str | None = None) -> None:
        self.detener_en = detener_en
        self.inicios: list[tuple[str, str]] = []
        self.finales: list[tuple[str, str, float]] = []
        self.fallos: list[tuple[str, str]] = []

    def nodo_inicia(self, nodo, instancia, entrada):
        self.inicios.append((nodo, instancia))

    def nodo_termina(self, nodo, instancia, salida, ms):
        self.finales.append((nodo, instancia, ms))

    def nodo_falla(self, nodo, instancia, error, ms):
        self.fallos.append((nodo, error))

    def detener_tras(self, nodo):
        return nodo == self.detener_en

    @property
    def nodos_terminados(self) -> list[str]:
        return [n for n, _, _ in self.finales]


class _ObservadorRoto(_ObservadorEspia):
    """Falla en todos sus métodos. Observar no puede tumbar lo observado."""

    def nodo_inicia(self, nodo, instancia, entrada):
        raise RuntimeError("observador roto")

    def nodo_termina(self, nodo, instancia, salida, ms):
        raise RuntimeError("observador roto")

    def detener_tras(self, nodo):
        raise RuntimeError("observador roto")


def _caso(observador=None, salida: Path | None = None):
    cfg = config_test()
    return crear_caso_uso_mapeo(cfg, proveedor="fake", observador=observador)


def _ejecutar(caso, tmp: Path):
    func = next(HU.glob("funcionalidad-*.json"))
    return caso.ejecutar(str(HU), str(func), str(tmp))


class TestObservadorDeEjecucion(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_el_puerto_lo_cumple_un_observador_cualquiera(self) -> None:
        self.assertIsInstance(_ObservadorEspia(), ObservadorEjecucionPort)

    def test_ve_cada_nodo_entrar_y_salir(self) -> None:
        espia = _ObservadorEspia()
        _ejecutar(_caso(espia), self.tmp)

        # Los nodos del esqueleto del grafo, que no dependen de ninguna opción.
        for nodo in ("cargar", "procesar_historia", "extraer_intencion", "publicar"):
            self.assertIn(nodo, espia.nodos_terminados, f"no se observó '{nodo}'")
        # Entrar y salir van emparejados cuando nada falla.
        self.assertEqual(len(espia.inicios), len(espia.finales))
        self.assertEqual(espia.fallos, [])

    def test_distingue_las_repeticiones_de_un_nodo(self) -> None:
        """Con el abanico de `Send`, un nodo corre varias veces: cada una es su instancia."""
        espia = _ObservadorEspia()
        _ejecutar(_caso(espia), self.tmp)

        instancias = {i for n, i, _ in espia.finales if n == "evaluar_candidato"}
        self.assertGreater(len(instancias), 1, "el abanico debería dar más de una instancia")
        self.assertTrue(all(i for i in instancias), "una instancia del abanico no puede ir vacía")

    def test_mide_el_tiempo_de_cada_nodo(self) -> None:
        espia = _ObservadorEspia()
        _ejecutar(_caso(espia), self.tmp)
        self.assertTrue(all(ms >= 0 for _, _, ms in espia.finales))

    def test_detener_tras_un_nodo_corta_la_corrida(self) -> None:
        espia = _ObservadorEspia(detener_en="extraer_intencion")
        with self.assertRaises(EjecucionDetenida) as ctx:
            _ejecutar(_caso(espia), self.tmp)

        self.assertEqual(ctx.exception.nodo, "extraer_intencion")
        # Lo de antes sí corrió; lo de después, no.
        self.assertIn("cargar", espia.nodos_terminados)
        self.assertNotIn("clasificar", espia.nodos_terminados)
        self.assertNotIn("publicar", espia.nodos_terminados)

    def test_el_nodo_del_corte_si_termina_antes_de_parar(self) -> None:
        """Se para DESPUÉS del nodo: su salida tiene que quedar registrada."""
        espia = _ObservadorEspia(detener_en="cargar")
        with self.assertRaises(EjecucionDetenida):
            _ejecutar(_caso(espia), self.tmp)
        self.assertIn("cargar", espia.nodos_terminados)

    def test_un_observador_roto_no_tumba_la_corrida(self) -> None:
        resultado = _ejecutar(_caso(_ObservadorRoto()), self.tmp)
        self.assertGreaterEqual(resultado.total_historias, 1)

    def test_sin_observador_el_grafo_es_el_de_siempre(self) -> None:
        resultado = _ejecutar(_caso(None), self.tmp)
        self.assertGreaterEqual(resultado.total_historias, 1)


if __name__ == "__main__":
    unittest.main()
