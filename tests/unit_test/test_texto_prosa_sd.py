"""Un índice y un reranker no quieren el mismo texto, y por eso no lo comparten.

`texto_para_indexar()` optimiza **cobertura de vocabulario**: mete jerarquía, patrón funcional,
tipo de activo y nombre del Control Record pegados, porque en un índice cualquier término extra es
una oportunidad más de coincidir y da igual cómo se lea. Un cross-encoder, en cambio, **lee** el
par (consulta, documento): esa clasificación no le dice nada, le añade ruido y le gasta ventana.
Medido con el texto del índice, puntuaba los 10 candidatos en ~0.003 y hundía R@1 de 0.50 a 0.17.

`texto_prosa(variante)` produce las alternativas, y cuál se usa lo decide el barrido
`evaluate.py --barrido-texto`, no la intuición. Este test fija que las variantes son lo que dicen
ser: prosa de verdad, sin clasificación, y que ninguna se queda muda si al Service Domain le falta
un campo.

Sin red y sin LLM.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.dominio.modelos import VARIANTES_TEXTO_SD, EntradaCatalogo
from unit_test.support import DOCS

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"


class TestTextoProsa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = CatalogoJson(CATALOGO).cargar()
        cls.por_nombre = {e.service_domain: e for e in cls.catalogo}

    def test_ninguna_variante_deja_a_un_sd_sin_texto(self):
        """Ni los 3 SD a los que el landscape no les publica algún campo."""
        for variante in VARIANTES_TEXTO_SD:
            vacios = [e.service_domain for e in self.catalogo if not e.texto_prosa(variante).strip()]
            self.assertEqual(vacios, [], f"variante '{variante}' deja SD sin texto")

    def test_toda_variante_en_prosa_nombra_su_service_domain(self):
        """Si el documento no dice de qué SD habla, el cross-encoder compite a ciegas."""
        for variante in ("nombre_rol", "prosa", "prosa_features", "documentacion_limpia"):
            for entrada in self.catalogo[:40]:
                self.assertIn(
                    entrada.service_domain,
                    entrada.texto_prosa(variante),
                    f"{variante} / {entrada.service_domain}",
                )

    def test_la_prosa_no_arrastra_la_clasificacion_del_indice(self):
        correspondence = self.por_nombre["Correspondence"]
        prosa = correspondence.texto_prosa("prosa")
        indice = correspondence.texto_para_indexar()
        self.assertIn(correspondence.functional_pattern or "", indice)
        self.assertNotIn(correspondence.functional_pattern or "xxxx", prosa)

    def test_documentacion_limpia_convierte_los_marcadores_en_encabezados(self):
        texto = self.por_nombre["Correspondence"].texto_prosa("documentacion_limpia")
        self.assertNotIn("**", texto)
        self.assertIn("Role:", texto)

    def test_la_variante_indice_es_exactamente_el_texto_del_indice(self):
        for entrada in self.catalogo[:20]:
            self.assertEqual(entrada.texto_prosa("indice"), entrada.texto_para_indexar())

    def test_una_variante_desconocida_falla_en_vez_de_devolver_algo_raro(self):
        with self.assertRaises(ValueError):
            self.catalogo[0].texto_prosa("lo_que_sea")

    def test_un_sd_sin_ningun_texto_cae_en_su_nombre(self):
        pelado = EntradaCatalogo(service_domain="Service Domain Pelado")
        for variante in VARIANTES_TEXTO_SD:
            self.assertIn("Pelado", pelado.texto_prosa(variante))


if __name__ == "__main__":
    unittest.main()
