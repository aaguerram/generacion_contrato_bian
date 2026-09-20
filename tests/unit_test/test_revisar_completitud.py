"""Nodo 3 `revisar_completitud` (prompt mapeo.completitud 1.1.0). Determinista, sin red.

Lo que se defiende, todo motivado por la corrida real del E2E 1 del 2026-09-20 donde el nodo
devolvió CERO en todos sus campos y aun así costó 51 s:

1. el revisor ve la evidencia de clases del BOM que produjo el nodo 2a -sin ella no tenía con qué
   poblar `ownership_conflicts`-;
2. los candidatos actuales llegan con su `service_role` COMPLETO -con el nombre solo no se puede
   juzgar si dos se pisan-;
3. el índice global NO repite los candidatos actuales -su única función es encontrar ausencias-;
4. `unsupported_candidates` lo escribe el CÓDIGO, no el LLM;
5. las métricas dicen si el nodo se paga solo.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.analista_mapeo_langchain import (
    _formatear_indice_global,
    formatear_candidatos_para_revision,
    formatear_propietarios_bom,
)
from src.adaptadores.salida.catalogo_entidades_json import CatalogoEntidadesJson
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.prompts_mapeo import SPEC_COMPLETITUD
from src.dominio.historias import (
    CandidatoClaseBom,
    CandidatosHistoriaLLM,
    CandidatoServiceDomainLLM,
    EvidenciaClaseBom,
    RevisionCompletitudLLM,
)
from src.dominio.normalizacion import normalizar
from unit_test.support import DOCS
from unit_test.test_routing_jerarquico import _AnalistaContacto, _entrada, _servicio

_SD = "Party Reference Data Directory"
_LDM = "Location Data Management"


def _catalogo():
    return CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")).cargar()


class TestPrompt110(unittest.TestCase):
    def test_pide_el_conflicto_con_la_evidencia_del_bom_y_no_pide_unsupported(self):
        # El prompt va justificado a 100 columnas: se comparan espacios normalizados.
        sistema = " ".join(SPEC_COMPLETITUD.template.messages[0].prompt.template.split())
        humano = SPEC_COMPLETITUD.template.messages[1].prompt.template
        self.assertEqual(SPEC_COMPLETITUD.version, "1.3.0")
        self.assertIn("<propietarios_bom", humano)
        self.assertIn("SOLO TIPIFICA", sistema)
        self.assertIn("No devuelvas `unsupported_candidates`", sistema)
        self.assertIn("GUARDA EL VALOR", sistema)
        self.assertNotIn("unsupported_candidates, ownership_conflicts", humano)
        self.assertIn("NO incluye los candidatos actuales", humano)


class TestHallazgosNoInventario(unittest.TestCase):
    """`ownership_conflicts` y `duplicated_responsibilities` llevan hallazgos, no negaciones.

    Medido con Claude Opus 5 de juez: devolvía 8 `duplicated_responsibilities` y ninguna era una
    duplicación -todas explicaban que NO la había-, y esas negaciones acababan en el JSON de la
    historia como si fueran hallazgos.
    """

    def test_el_prompt_prohibe_las_negaciones_y_declara_vacio_como_normal(self):
        sistema = " ".join(SPEC_COMPLETITUD.template.messages[0].prompt.template.split())
        self.assertIn("HALLAZGOS CONFIRMADOS, no un inventario", sistema)
        self.assertIn("Vacío es la respuesta normal y correcta", sistema)
        self.assertIn("Prohibido escribir una entrada para decir que NO hay conflicto", sistema)
        self.assertIn("va en `review_summary`", sistema)

    def test_pide_nombrar_las_dos_partes(self):
        sistema = " ".join(SPEC_COMPLETITUD.template.messages[0].prompt.template.split())
        self.assertIn("nombrar a los DOS candidatos", sistema)
        self.assertIn("PAREJAS de candidatos cuya responsabilidad se solapa de verdad", sistema)


class TestSenalCrudaSinVeredicto(unittest.TestCase):
    """El nodo 3 ve TODO el canal del 2a, así que necesita el peso de cada uno -- pero como DATO.

    Ocultar los que el umbral de rescate filtró sesgaría hacia el umbral; etiquetarlos
    "descartados" sesgaría en contra. Se da el número y se dice que no es un veredicto.
    """

    @staticmethod
    def _candidatos():
        return [
            CandidatoClaseBom(service_domain=_LDM, score=2.70, evidencias=[EvidenciaClaseBom(
                clase="Phone Address", motivos=["bm25#4", "vectorial#8"],
                atributos_adicionales=["Phone Number"])]),
            CandidatoClaseBom(service_domain="Correspondence", score=0.91, evidencias=[EvidenciaClaseBom(
                clase="Correspondence", motivos=["bm25#2"], atributos_adicionales=["Correspondence Type"])]),
        ]

    def test_la_senal_lleva_score_y_canales(self):
        texto = formatear_propietarios_bom(self._candidatos(), con_senal=True)
        self.assertIn(f'- "{_LDM}" (señal 2.70, 2 canal(es): bm25, vectorial) define', texto)
        self.assertIn('- "Correspondence" (señal 0.91, 1 canal(es): bm25) define', texto)

    def test_no_emite_ningun_veredicto(self):
        texto = formatear_propietarios_bom(self._candidatos(), con_senal=True).lower()
        for palabra in ("filtrado", "descartado", "rechazado", "no rescatado", "debil", "recomend"):
            self.assertNotIn(palabra, texto)

    def test_el_nodo_2b_no_ve_la_senal(self):
        """Su bloque solo trae rescatados: todos pasaron el umbral y la cifra sería ruido."""
        self.assertNotIn("señal", formatear_propietarios_bom(self._candidatos()))

    def test_el_prompt_dice_que_la_senal_no_es_un_veredicto(self):
        sistema = " ".join(SPEC_COMPLETITUD.template.messages[0].prompt.template.split())
        self.assertIn("NO un veredicto", sistema)
        self.assertIn("una señal baja no significa que el Service Domain sobre", sistema)
        self.assertIn("proponlos en `missing_candidates`", sistema)


class TestFormateoParaElRevisor(unittest.TestCase):
    def test_los_candidatos_llevan_su_rol_completo(self):
        catalogo = _catalogo()
        cands = [CandidatoServiceDomainLLM(service_domain=_SD, rationale="r", supporting_intent=["visualizar"])]
        texto = formatear_candidatos_para_revision(cands, catalogo)
        entrada = next(e for e in catalogo if e.service_domain == _SD)
        self.assertIn("service_role:", texto)
        self.assertIn(entrada.service_role, texto, "el rol va ENTERO, no recortado")
        self.assertIn("Customer Management", texto, "con su jerarquía, para desambiguar")
        self.assertIn("visualizar", texto)

    def test_un_candidato_que_no_resuelve_no_rompe_el_formateo(self):
        cands = [CandidatoServiceDomainLLM(service_domain="Inventado SD", rationale="r")]
        self.assertIn("Inventado SD", formatear_candidatos_para_revision(cands, _catalogo()))

    def test_el_indice_global_excluye_los_ya_propuestos(self):
        catalogo = _catalogo()
        completo = _formatear_indice_global(catalogo)
        parcial = _formatear_indice_global(catalogo, excluir={normalizar(_SD), normalizar(_LDM)})
        self.assertIn(f'- "{_SD}"', completo)
        self.assertNotIn(f'- "{_SD}"', parcial)
        self.assertNotIn(f'- "{_LDM}"', parcial)
        self.assertEqual(len(parcial.splitlines()), len(completo.splitlines()) - 2)


class _AnalistaCompletitud(_AnalistaContacto):
    """Registra lo que recibe el nodo 3 y devuelve un `unsupported` INVENTADO, que el código debe pisar."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.completitud_kwargs: dict = {}

    def revisar_completitud(self, historia, intencion, candidatos, catalogo, disponibilidad_evidencia, **kw):
        self.completitud_kwargs = {
            "disponibilidad": dict(disponibilidad_evidencia),
            "propietarios_bom": [c.service_domain for c in (kw.get("propietarios_bom") or [])],
        }
        return RevisionCompletitudLLM(
            unsupported_candidates=["Un SD que el LLM se inventó"],
            missing_candidates=[],
            review_summary="guion",
        )


class TestNodo3EnElGrafo(unittest.TestCase):
    @staticmethod
    def _correr(analista, **extra):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            return _servicio(analista, routing=True, entidades=entidades, **extra).ejecutar(hu, func, salida)

    def test_el_nodo_3_recibe_la_evidencia_de_clases_bom_del_2a(self):
        a = _AnalistaCompletitud(["Market Data"], candidatos=[_SD])
        resultado = self._correr(a)
        propietarios = a.completitud_kwargs["propietarios_bom"]
        self.assertTrue(propietarios, "el nodo 3 tiene que ver candidatos_por_clase")
        self.assertEqual(
            propietarios,
            [c.service_domain for c in resultado.historias[0].candidatos_por_clase],
        )

    def test_unsupported_candidates_lo_escribe_el_codigo_no_el_llm(self):
        a = _AnalistaCompletitud(["Market Data"], candidatos=[_SD])
        resultado = self._correr(a)
        rev = resultado.historias[0].revision_completitud
        self.assertNotIn("Un SD que el LLM se inventó", rev.unsupported_candidates,
                         "lo que dijo el LLM se descarta")
        esperado = sorted(
            sd for sd, est in a.completitud_kwargs["disponibilidad"].items()
            if est == "BIAN_EVIDENCE_UNAVAILABLE"
        )
        self.assertEqual(rev.unsupported_candidates, esperado)

    def test_sin_canal_de_entidades_el_nodo_3_recibe_lista_vacia(self):
        a = _AnalistaCompletitud(["Market Data"], candidatos=[_SD])
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            _servicio(a, routing=True).ejecutar(hu, func, salida)
        self.assertEqual(a.completitud_kwargs["propietarios_bom"], [])


class TestMetricasDelNodo3(unittest.TestCase):
    def test_cuentan_lo_que_aporta_el_nodo(self):
        a = _AnalistaContacto(["Market Data"], candidatos=[_SD])
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            r = _servicio(a, routing=True, entidades=entidades).ejecutar(hu, func, salida)
        for clave in ("completitud_candidatos_aportados", "completitud_candidatos_seleccionados",
                      "completitud_conflictos_detectados"):
            self.assertIn(clave, r.metricas)
            self.assertIsInstance(r.metricas[clave], int)
        self.assertEqual(r.metricas["completitud_candidatos_aportados"], 0,
                         "el guion no aporta missing_candidates")


if __name__ == "__main__":
    unittest.main()
