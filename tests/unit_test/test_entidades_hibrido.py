"""Paso 1 del canal de propiedad de clases BOM como recuperación híbrida. Determinista, sin red.

Lo que se defiende: (1) el documento por el que se recupera una clase es SU modelo (definición,
atributos, valores de enum) y nunca el nombre del Service Domain; (2) la fusión RRF de varios
canales sigue filtrando por propiedad -una clase sin dueño o un enum no se vuelve candidato por
salir en un ranking-; (3) un `RecuperadorClasesPort` cualquiera entra al nodo 2a y deja rastro
auditable (qué canal y en qué posición propuso cada clase); (4) un canal caído no tumba el nodo.
"""

from __future__ import annotations

import tempfile
import unittest

from langchain_core.embeddings import Embeddings

from src.adaptadores.salida.catalogo_entidades_json import CatalogoEntidadesJson
from src.adaptadores.salida.recuperador_clases_bm25 import RecuperadorClasesBM25
from src.adaptadores.salida.recuperador_clases_vectorial import RecuperadorClasesVectorial
from src.aplicacion.puertos.recuperador_clases import RecuperadorClasesPort
from src.dominio.entidades_bian import (
    CandidatoClase,
    ConsultaClases,
    candidatos_por_propiedad,
    clases_requeridas_desde_rankings,
    documento_de_clase,
    documentos_indexables,
    es_artefacto_del_metamodelo,
)
from unit_test.support import DOCS
from src.dominio.entidades_bian import ClaseBian, OcurrenciaClase
from unit_test.test_entidades_bian import LDM, PRDD, _catalogo
from unit_test.test_routing_jerarquico import _AnalistaContacto, _entrada, _servicio


class TestDocumentoDeClase(unittest.TestCase):
    def test_lleva_el_modelo_de_la_clase_y_no_el_nombre_del_sd(self) -> None:
        clases, enums = _catalogo()
        doc = documento_de_clase(clases["Contact Point"], nombres_enum=enums,
                                 enums={"ContactPointTypeValues": ("Electronic Address", "Phone Number")})
        self.assertIn("Contact Point", doc)
        self.assertIn("Electronic Address", doc, "el valor del enum es la cita más literal del BOM")
        self.assertIn("Reference", doc, "el BQ sí viaja: es lo más cerca de una operación que da el BOM")
        self.assertNotIn(PRDD, doc, "emparejar nombres de SD es trabajo de otro canal")

    def test_las_cajas_del_metamodelo_no_son_clases_de_negocio(self) -> None:
        """`X_SD_Operations`, `X_Instantiation`... tienen dueño pero no son objetos: fuera del corpus."""
        for nombre in ("Customer Consent_SD_Operations", "Corporate Card Facility_Instantiation",
                       "Customer Mandate Agreement_Invocation", "Corporate Card Facility_Reporting",
                       "Customer Mandate Agreement_ Analytics Object"):
            self.assertTrue(es_artefacto_del_metamodelo(nombre), nombre)
        for nombre in ("Party_Party Relationship", "Correspondence Management Function", "Contact Point"):
            self.assertFalse(es_artefacto_del_metamodelo(nombre), nombre)
        clases, enums = _catalogo()
        clases = dict(clases)
        clases["Party Reference Data Directory_SD_Operations"] = ClaseBian(
            "Party Reference Data Directory_SD_Operations", (OcurrenciaClase(service_domain=PRDD),)
        )
        nombres = {n for n, _ in documentos_indexables(clases, nombres_enum=enums)}
        self.assertNotIn("Party Reference Data Directory_SD_Operations", nombres)
        requeridas = clases_requeridas_desde_rankings(
            {"vectorial": ["Party Reference Data Directory_SD_Operations", "Party"]}, clases
        )
        self.assertEqual([r.clase for r in requeridas], ["Party"])

    def test_solo_se_indexan_clases_con_dueno_que_no_son_enum(self) -> None:
        clases, enums = _catalogo()
        nombres = {n for n, _ in documentos_indexables(clases, nombres_enum=enums)}
        self.assertIn("Party", nombres)
        self.assertIn("Phone Address", nombres)
        self.assertNotIn("ContactPointTypeValues", nombres, "un enum tipifica, no es candidato")


class TestFusionDeRankings(unittest.TestCase):
    def test_fusiona_y_deja_rastro_del_canal_y_la_posicion(self) -> None:
        clases, _ = _catalogo()
        requeridas = clases_requeridas_desde_rankings(
            {"bm25": ["Contact Point", "Party"], "vectorial": ["Party", "Location"]}, clases, k=20
        )
        por_nombre = {r.clase: r for r in requeridas}
        self.assertEqual(requeridas[0].clase, "Party", "aparecer en dos canales pesa más que top-1 en uno")
        self.assertEqual(por_nombre["Party"].motivos, ("bm25#2", "vectorial#1"))
        self.assertAlmostEqual(por_nombre["Contact Point"].peso, 1.0, places=3,
                               msg="el top-1 de un canal con peso 1.0 vale 1.0")

    def test_lo_que_no_tiene_dueno_no_entra_aunque_un_canal_lo_proponga(self) -> None:
        clases, _ = _catalogo()
        requeridas = clases_requeridas_desde_rankings(
            {"vectorial": ["ContactPointTypeValues", "Inexistente", "Party"]}, clases
        )
        self.assertEqual([r.clase for r in requeridas], ["Party"])

    def test_sin_rankings_no_hay_requeridas(self) -> None:
        clases, _ = _catalogo()
        self.assertEqual(clases_requeridas_desde_rankings({}, clases), [])
        self.assertEqual(clases_requeridas_desde_rankings({"bm25": []}, clases), [])

    def test_la_propiedad_sigue_decidiendo_el_service_domain(self) -> None:
        clases, enums = _catalogo()
        requeridas = clases_requeridas_desde_rankings({"bm25": ["Party", "Phone Address"]}, clases)
        candidatos = candidatos_por_propiedad(requeridas, clases, nombres_enum=enums)
        self.assertEqual(candidatos[0].service_domain, PRDD)
        self.assertEqual({c.service_domain for c in candidatos}, {PRDD, LDM})


class TestRecuperadorClasesBM25(unittest.TestCase):
    """Sobre el `entity.json` real: la consulta del E2E 1 tiene que llegar a las clases de contacto."""

    def test_recupera_las_clases_de_contacto_desde_la_hu_en_espanol(self) -> None:
        r = RecuperadorClasesBM25(CatalogoEntidadesJson(str(DOCS / "entity.json")))
        consulta = ConsultaClases.desde_textos(
            ["consultar y mostrar los datos personales del cliente, número de celular y correo electrónico"]
        )
        clases = [c.clase for c in r.recuperar(consulta, 12)]
        self.assertTrue({"Contact Point", "Phone Address"} & set(clases), clases)

    def test_sin_terminos_no_hay_resultados(self) -> None:
        r = RecuperadorClasesBM25(CatalogoEntidadesJson(str(DOCS / "entity.json")))
        self.assertEqual(r.recuperar(ConsultaClases(texto="", terminos=frozenset()), 5), [])


class _EmbeddingsPorLetras(Embeddings):
    """Vector determinista por histograma de letras: no es semántico, pero es estable."""

    def _vec(self, texto: str) -> list[float]:
        v = [0.0] * 27
        for ch in texto.lower():
            if ch.isalpha() and ch.isascii():
                v[ord(ch) - 97] += 1.0
        v[26] = 1.0
        norma = sum(x * x for x in v) ** 0.5 or 1.0
        return [x / norma for x in v]

    def embed_documents(self, textos):
        return [self._vec(t) for t in textos]

    def embed_query(self, texto):
        return self._vec(texto)


class _CatalogoEnMemoria:
    def __init__(self):
        self._clases, self._enums = _catalogo()

    def clases(self):
        return self._clases

    def nombres_enum(self):
        return self._enums


class TestRecuperadorClasesVectorial(unittest.TestCase):
    def test_indexa_solo_clases_con_dueno_y_devuelve_clases(self) -> None:
        r = RecuperadorClasesVectorial(_CatalogoEnMemoria(), _EmbeddingsPorLetras(), modelo_embeddings="fake")
        resultado = r.recuperar(ConsultaClases(texto="phone number of the party"), 10)
        nombres = {c.clase for c in resultado}
        self.assertTrue(nombres <= {"Party", "Contact Point", "Phone Address", "Location"}, nombres)
        self.assertNotIn("ContactPointTypeValues", nombres)

    def test_consulta_vacia_no_llama_al_indice(self) -> None:
        r = RecuperadorClasesVectorial(_CatalogoEnMemoria(), _EmbeddingsPorLetras(), modelo_embeddings="fake")
        self.assertEqual(r.recuperar(ConsultaClases(texto="   "), 5), [])


class _CanalGuion(RecuperadorClasesPort):
    def __init__(self, nombre: str, clases: list[str]) -> None:
        self._nombre, self._clases = nombre, clases
        self.consultas: list[ConsultaClases] = []

    @property
    def nombre(self) -> str:
        return self._nombre

    def recuperar(self, consulta, k):
        self.consultas.append(consulta)
        return [CandidatoClase(c, 1.0) for c in self._clases[:k]]


class _CanalRoto(RecuperadorClasesPort):
    @property
    def nombre(self) -> str:
        return "roto"

    def recuperar(self, consulta, k):
        raise ConnectionError("embeddings caídos")


class TestNodo2aConCanalesDeClases(unittest.TestCase):
    _SD = PRDD

    @staticmethod
    def _correr(analista, **extra):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            return _servicio(analista, routing=True, entidades=entidades, **extra).ejecutar(hu, func, salida)

    def test_un_canal_externo_rescata_al_propietario_sin_diccionario(self) -> None:
        canal = _CanalGuion("vectorial", ["Contact Point"])
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = self._correr(
            a, recuperadores_clases=[canal], entidades_canal_diccionario=False
        )
        self.assertIn(self._SD, a.catalogo_candidatos)
        dueno = next(c for c in resultado.historias[0].candidatos_por_clase if c.service_domain == self._SD)
        contacto = next(e for e in dueno.evidencias if e.clase == "Contact Point")
        self.assertEqual(contacto.motivos, ["vectorial#1"], "el rastro dice qué canal y en qué posición")
        self.assertEqual(len(canal.consultas), 1)
        self.assertIn("contacto", canal.consultas[0].texto, "el canal denso recibe el texto natural")
        self.assertIn("party", canal.consultas[0].terminos, "el disperso recibe los términos del BOM")
        self.assertEqual(resultado.parametros["entidades_canales"], ["vectorial"])
        self.assertTrue(resultado.parametros["entidades_bom_activo"])

    def test_el_diccionario_es_un_canal_mas_en_la_fusion(self) -> None:
        canal = _CanalGuion("bm25", ["Location"])  # el disperso se equivoca de clase
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = self._correr(a, recuperadores_clases=[canal])
        self.assertEqual(resultado.parametros["entidades_canales"], ["diccionario", "bm25"])
        self.assertIn(self._SD, a.catalogo_candidatos, "el diccionario sigue aportando a Party")

    def test_un_canal_caido_no_tumba_el_nodo(self) -> None:
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = self._correr(a, recuperadores_clases=[_CanalRoto()])
        self.assertIn(self._SD, a.catalogo_candidatos)
        self.assertTrue(resultado.historias[0].candidatos_por_clase)

    def test_sin_recuperadores_el_paso_1_es_el_diccionario_de_siempre(self) -> None:
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = self._correr(a)
        self.assertEqual(resultado.parametros["entidades_canales"], ["diccionario"])
        dueno = next(c for c in resultado.historias[0].candidatos_por_clase if c.service_domain == self._SD)
        self.assertTrue(any(m.startswith("nombre:") or m.startswith("enum:") for e in dueno.evidencias for m in e.motivos))


if __name__ == "__main__":
    unittest.main()
