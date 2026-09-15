"""Canal disperso BM25 + fusión ponderada.

Lo que fija este test y por qué importa:

1. **El puente ES->EN no es un adorno**: sin traducir, BM25 sobre consultas en español contra un
   catálogo íntegramente en inglés no recupera NADA. Esa —y no la falta de pesos— es la razón de
   fondo por la que el canal léxico medía 0.29 y arrastraba la fusión.
2. BM25 ordena por rareza del término (IDF), que es lo que pide `mapear-historias`: los términos
   que deciden son raros y los que confunden ("customer", "party") están en cientos de SD.
3. `fusion_rrf` acepta `k` y un peso por canal, y `peso=0` apaga un canal sin recablear nada.
4. `validar-sd` no se toca: para una consulta que ES un nombre, el canal correcto sigue siendo el
   léxico por nombre.

Sin red, sin LLM y sin embeddings: BM25 es stdlib puro sobre el catálogo local.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.recuperador_bm25 import RecuperadorBM25
from src.adaptadores.salida.recuperador_lexico import RecuperadorLexico
from src.dominio.bm25 import IndiceBM25, tokenizar
from src.dominio.fusion_rrf import fusion_rrf
from unit_test.support import DOCS

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"


class TestTokenizacion(unittest.TestCase):
    def test_traduce_el_vocabulario_de_negocio_al_ingles(self):
        tokens = tokenizar("notificar al cliente por correo electrónico")
        self.assertIn("notify", tokens)
        self.assertIn("customer", tokens)
        self.assertIn("mail", tokens)
        self.assertNotIn("notificar", tokens)

    def test_quita_vacias_y_acentos(self):
        self.assertEqual(tokenizar("de la Autenticación"), ["authentication"])


class TestIndiceBM25(unittest.TestCase):
    def test_pesa_por_rareza_no_por_frecuencia(self):
        indice = IndiceBM25(
            [
                ("comun", "customer customer customer party party"),
                ("raro", "customer collateral"),
            ]
        )
        self.assertEqual(indice.buscar("collateral", 2)[0][0], "raro")

    def test_no_devuelve_documentos_sin_ningun_termino(self):
        indice = IndiceBM25([("a", "customer party"), ("b", "collateral")])
        self.assertEqual(indice.buscar("payment", 5), [])


class TestRecuperadorBM25(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = CatalogoJson(CATALOGO)
        cls.bm25 = RecuperadorBM25(cls.catalogo)

    def test_recupera_con_consulta_en_espanol_contra_catalogo_en_ingles(self):
        nombres = [
            c.service_domain
            for c in self.bm25.recuperar(
                "notificar al cliente por correo y SMS que sus datos de contacto "
                "fueron actualizados",
                10,
            )
        ]
        self.assertIn("Correspondence", nombres)

    def test_los_dos_vocabularios_no_se_tocan_sin_el_puente(self):
        """La evidencia del punto 1: el término español NO existe en el corpus, su traducción sí.

        Un canal disperso empareja términos literales. Si la consulta dice "notificar" y el corpus
        entero dice "notify", el emparejamiento es vacío por construcción — ninguna ponderación de
        la fusión arregla eso, y es la razón por la que este canal medía 0.29.
        """
        corpus = " ".join(e.texto_para_indexar() for e in self.catalogo.cargar()).lower()
        for espanol, ingles in (
            ("notificar", "notify"),
            ("cliente", "customer"),
            ("actualizar", "update"),
        ):
            self.assertNotIn(espanol, corpus, f"'{espanol}' no debería estar en un corpus inglés")
            self.assertIn(ingles, corpus)

    def test_devuelve_como_mucho_k(self):
        self.assertLessEqual(len(self.bm25.recuperar("customer data", 5)), 5)

    def test_el_canal_por_nombre_sigue_siendo_el_de_validar_sd(self):
        lexico = RecuperadorLexico(self.catalogo)
        self.assertEqual(lexico.recuperar("Current Account", 1)[0].service_domain, "Current Account")


class TestFusionPonderada(unittest.TestCase):
    def test_sin_pesos_se_comporta_como_siempre(self):
        rankings = [["a", "b"], ["b", "a"]]
        self.assertEqual(
            [n for n, _ in fusion_rrf(rankings)], [n for n, _ in fusion_rrf(rankings, pesos=[1, 1])]
        )

    def test_el_peso_decide_quien_manda(self):
        # Cada canal propone SOLO su favorito: así el orden final depende únicamente del peso.
        rankings = [["disperso_top"], ["denso_top"]]
        con_denso = [n for n, _ in fusion_rrf(rankings, pesos=[0.25, 1.0])]
        self.assertEqual(con_denso[0], "denso_top")
        con_disperso = [n for n, _ in fusion_rrf(rankings, pesos=[1.0, 0.25])]
        self.assertEqual(con_disperso[0], "disperso_top")

    def test_peso_cero_apaga_el_canal(self):
        fusionado = fusion_rrf([["solo_aqui"], ["otro"]], pesos=[0.0, 1.0])
        self.assertEqual([n for n, _ in fusionado], ["otro"])

    def test_k_pequeno_separa_mas_las_primeras_posiciones(self):
        ranking = [["primero", "segundo"]]
        brecha = lambda k: dict(fusion_rrf(ranking, k=k))["primero"] - dict(  # noqa: E731
            fusion_rrf(ranking, k=k)
        )["segundo"]
        self.assertGreater(brecha(10), brecha(60))

    def test_un_peso_por_canal_o_error(self):
        with self.assertRaises(ValueError):
            fusion_rrf([["a"], ["b"]], pesos=[1.0])


if __name__ == "__main__":
    unittest.main()
