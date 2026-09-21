"""Pruebas deterministas del módulo `api/` que NO necesitan Postgres ni red.

Solo se prueba aquí lo que no depende de la base: el cerrojo del ejecutor y el separador de
historias. Todo lo que toca Postgres vive fuera de la suite determinista a propósito.
"""

from __future__ import annotations

import threading
import unittest


class TestCerrojoDelEjecutorEsReentrante(unittest.TestCase):
    """`lanzar()` llama a `esta_ejecutando()` TENIENDO ya el cerrojo.

    Con un `threading.Lock` corriente eso es un interbloqueo del propio hilo, y además deja el
    cerrojo tomado para siempre: la petición de arranque se cuelga y, detrás de ella, toda
    consulta de estado. Visto en la pila real del servidor:

        corrida_viva (api/ejecutor.py) <- esta_ejecutando <- lanzar <- POST /ejecutar

    Por eso el cerrojo tiene que ser reentrante, y por eso esto es una regresión.
    """

    def test_se_puede_reentrar_en_el_mismo_hilo(self) -> None:
        from api import ejecutor

        with ejecutor._CERROJO:
            # Si el cerrojo no fuera reentrante, esta llamada no volvería nunca.
            self.assertFalse(ejecutor.esta_ejecutando("inexistente"))
            self.assertIsNone(ejecutor.corrida_viva("inexistente"))

    def test_sigue_excluyendo_a_otro_hilo(self) -> None:
        """Reentrante no es "sin exclusión": otro hilo tiene que seguir esperando."""
        from api import ejecutor

        entro = threading.Event()

        def otro() -> None:
            with ejecutor._CERROJO:
                entro.set()

        with ejecutor._CERROJO:
            hilo = threading.Thread(target=otro, daemon=True)
            hilo.start()
            self.assertFalse(entro.wait(timeout=0.3), "el otro hilo no debería haber entrado")
        hilo.join(timeout=2)
        self.assertTrue(entro.is_set())


class TestSepararHistorias(unittest.TestCase):
    """El texto pegado se parte SOLO por un marcador explícito."""

    def test_sin_separador_es_una_sola_historia(self) -> None:
        from api.historias import separar_historias

        hs = separar_historias("Como usuario quiero ver mis datos\npara confirmarlos.")
        self.assertEqual(len(hs), 1)

    def test_separa_por_regla_horizontal(self) -> None:
        from api.historias import separar_historias

        hs = separar_historias("Historia A\n\n---\n\nHistoria B")
        self.assertEqual(len(hs), 2)
        self.assertNotIn("---", [t for _, t, _ in hs], "la regla no puede quedar como título")

    def test_separa_por_encabezado_y_por_codigo_hu(self) -> None:
        from api.historias import separar_historias

        self.assertEqual(len(separar_historias("## Una\ntexto\n## Otra\ntexto")), 2)
        self.assertEqual(len(separar_historias("HU-01: Una\ntexto\nHU-02: Otra\ntexto")), 2)

    def test_texto_vacio_no_produce_historias(self) -> None:
        from api.historias import separar_historias

        self.assertEqual(separar_historias("   \n\n  "), [])

    def test_los_nombres_de_archivo_son_unicos(self) -> None:
        from api.historias import separar_historias

        hs = separar_historias("## Igual\nuno\n## Igual\ndos")
        nombres = [a for a, _, _ in hs]
        self.assertEqual(len(set(nombres)), len(nombres))


if __name__ == "__main__":
    unittest.main()
