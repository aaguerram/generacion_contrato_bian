"""Routing jerárquico: el paso de candidatos partido en 2a (`enrutar_dominios`) + 2b.

La propiedad que estos tests defienden NO es "el router acierta" -eso no se puede medir sin
corpus dorado-, sino que **enrutar mal cuesta tokens y nunca candidatos**:

- un nombre de dominio inventado no filtra nada y queda como incidencia;
- si no resuelve ninguno, se sigue con los 341 (degradación, no muerte);
- `preparar_candidatos` sigue resolviendo nombres contra el catálogo COMPLETO, así que un
  candidato de un dominio no enrutado -lo proponga quien lo proponga- se resuelve igual.

Todo determinista, sin API.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_entidades_json import CatalogoEntidadesJson
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.dominio.historias import (
    CandidatoServiceDomainLLM,
    CandidatosHistoriaLLM,
    EnrutamientoDominiosLLM,
    EvaluacionCandidatoLLM,
    IntencionHistoriaLLM,
    MapeoOperacionesLLM,
    ReconciliacionFuncionalidadLLM,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
)
from unit_test.support import DOCS

# El dominio real del SD que la HU de prueba debe encontrar.
_DOMINIO = "Customer Management"
_SD = "Party Reference Data Directory"
# Un SD de OTRO Business Domain: sirve para comprobar que el recorte no lo deja fuera del
# catálogo global con el que `preparar_candidatos` resuelve nombres.
_SD_FUERA = "Correspondence"


class _AnalistaEnrutado(AnalistaMapeoBianPort):
    """Registra qué catálogo vio cada nodo, que es justo lo que el routing cambia."""

    def __init__(self, dominios: list[str], *, candidatos: list[str] | None = None) -> None:
        self._dominios = dominios
        self._candidatos = candidatos if candidatos is not None else [_SD]
        self.catalogo_enrutamiento: list[str] = []
        self.catalogo_candidatos: list[str] = []
        self.texto_completo: bool | None = None
        self.llamadas_enrutar = 0

    def extraer_intencion(self, historia, funcionalidad):
        return IntencionHistoriaLLM(
            resumen_funcional="guion",
            business_actions=["visualizar"],
            business_objects=["datos personales"],
            external_dependencies=["notificacion"],
            traceability_ids=["SC-01"],
        )

    def enrutar_dominios(self, historia, funcionalidad, intencion, catalogo):
        self.llamadas_enrutar += 1
        self.catalogo_enrutamiento = [e.service_domain for e in catalogo]
        return EnrutamientoDominiosLLM(
            business_domains=self._dominios, rationale="guion"
        )

    def generar_candidatos(
        self, historia, funcionalidad, intencion, catalogo, *, texto_completo=False
    ):
        self.catalogo_candidatos = [e.service_domain for e in catalogo]
        self.texto_completo = texto_completo
        return CandidatosHistoriaLLM(
            candidatos=[CandidatoServiceDomainLLM(service_domain=n) for n in self._candidatos]
        )

    def revisar_completitud(
        self, historia, intencion, candidatos, catalogo, disponibilidad_evidencia
    ):
        return RevisionCompletitudLLM()

    def evaluar_candidato(self, historia, funcionalidad, intencion, paquete):
        return EvaluacionCandidatoLLM(
            service_domain=paquete.service_domain,
            estado="DIRECTO",
            rol_contractual="OWNED_CONTRACT",
            accion_objeto="visualizar datos personales",
            functional_object="datos personales",
            match_action=3,
            match_business_object=3,
            match_service_role=3,
            evidence_quality=3,
            ambiguity="NONE",
            ownership_traceability=["SC-01"],
            justification="guion",
        )

    def revisar_adversarial(self, historia, intencion, grupos):
        return RevisionAdversarialLLM()

    def reconciliar_funcionalidad(self, funcionalidad, resumen_por_historia):
        return ReconciliacionFuncionalidadLLM()


class _MapeadorNulo(MapeadorOperacionesBianPort):
    def mapear(self, *a, **kw) -> MapeoOperacionesLLM:
        return MapeoOperacionesLLM()


def _entrada(tmp: str) -> tuple[str, str, str]:
    raiz = Path(tmp)
    (raiz / "HU").mkdir()
    (raiz / "HU" / "HU-01.txt").write_text(
        "Como usuario quiero ver mis datos personales.\nEscenario 1. Consulta",
        encoding="utf-8",
    )
    func = raiz / "f.json"
    func.write_text(
        json.dumps({"funcionalidad_macro": "Datos personales"}), encoding="utf-8"
    )
    return str(raiz / "HU"), str(func), str(raiz / "out")


def _servicio(
    analista, *, routing: bool, entidades=None, **extra
) -> MapearHistoriasServiceDomainsService:
    return MapearHistoriasServiceDomainsService(
        CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")),
        LectorHistoriasFilesystem(),
        analista,
        PublicadorMapeoJson(),
        CatalogoBianCache(
            str(DOCS / "bian-operation-catalogs.json"),
            str(DOCS / "bian-cache"),
            "14.0.0",
            permitir_descargas=False,
        ),
        _MapeadorNulo(),
        routing_jerarquico=routing,
        catalogo_entidades=entidades,
        mapear_operaciones=False,
        concurrencia=1,
        **extra,
    )


def _correr(analista, *, routing: bool):
    with tempfile.TemporaryDirectory() as tmp:
        hu, func, salida = _entrada(tmp)
        return _servicio(analista, routing=routing).ejecutar(hu, func, salida)


class TestRoutingRecortaElCatalogoDe2b(unittest.TestCase):
    def test_2a_ve_los_341_y_2b_solo_el_dominio_enrutado(self):
        a = _AnalistaEnrutado([_DOMINIO])
        _correr(a, routing=True)

        self.assertEqual(len(a.catalogo_enrutamiento), 341, "2a decide sobre la taxonomía entera")
        self.assertLess(len(a.catalogo_candidatos), 341)
        self.assertIn(_SD, a.catalogo_candidatos)
        self.assertNotIn(_SD_FUERA, a.catalogo_candidatos, "otro Business Domain no debe colarse")

    def test_2b_recibe_texto_completo(self):
        """La ganancia del routing: el catálogo acotado se manda SIN recortar."""
        a = _AnalistaEnrutado([_DOMINIO])
        _correr(a, routing=True)
        self.assertIs(a.texto_completo, True)

    def test_con_el_flag_apagado_no_hay_nodo_2a(self):
        a = _AnalistaEnrutado([_DOMINIO])
        _correr(a, routing=False)

        self.assertEqual(a.llamadas_enrutar, 0, "sin flag no se paga la llamada extra")
        self.assertEqual(len(a.catalogo_candidatos), 341)
        self.assertIs(a.texto_completo, False, "sin routing, el catálogo va recortado como siempre")


class TestRoutingNuncaPierdeCandidatos(unittest.TestCase):
    """Enrutar mal debe costar tokens, nunca candidatos."""

    def test_un_dominio_inexistente_queda_como_incidencia(self):
        a = _AnalistaEnrutado([_DOMINIO, "Dominio Que No Existe"])
        r = _correr(a, routing=True)

        motivos = [i["motivo"] for i in r.incidencias]
        self.assertIn("ROUTING_DOMINIO_NO_RESUELTO", motivos)
        self.assertEqual(r.metricas["routing_dominios_no_resueltos"], 1)
        # ...y el dominio que SÍ resolvió sigue filtrando.
        self.assertIn(_SD, a.catalogo_candidatos)
        self.assertNotIn(_SD_FUERA, a.catalogo_candidatos)

    def test_sin_ningun_dominio_resoluble_se_usa_el_catalogo_completo(self):
        a = _AnalistaEnrutado(["Nada", "Tampoco"])
        r = _correr(a, routing=True)

        self.assertEqual(len(a.catalogo_candidatos), 341, "degradar, no morir")
        self.assertIn("ROUTING_SIN_DOMINIOS", [i["motivo"] for i in r.incidencias])
        self.assertEqual(r.metricas["routing_fallback_catalogo_completo"], 1)

    def test_un_enrutamiento_vacio_tambien_cae_al_catalogo_completo(self):
        a = _AnalistaEnrutado([])
        r = _correr(a, routing=True)
        self.assertEqual(len(a.catalogo_candidatos), 341)
        self.assertIn("ROUTING_SIN_DOMINIOS", [i["motivo"] for i in r.incidencias])

    def test_un_candidato_de_otro_dominio_se_resuelve_igual(self):
        """Red de seguridad estructural: `preparar_candidatos` resuelve contra los 341, no contra
        el recorte. Si 2b (o el nodo 3) nombra un SD de un dominio no enrutado, entra igual."""
        a = _AnalistaEnrutado([_DOMINIO], candidatos=[_SD, _SD_FUERA])
        r = _correr(a, routing=True)

        evaluados = {
            x.service_domain
            for h in r.historias
            for x in (
                *h.service_domains.candidatos_directos,
                *h.service_domains.candidatos_tentativos,
                *h.service_domains.candidatos_descartados,
            )
        }
        self.assertIn(_SD_FUERA, evaluados)


class TestRoutingObservable(unittest.TestCase):
    def test_metricas_y_parametros_declaran_el_routing(self):
        a = _AnalistaEnrutado([_DOMINIO])
        r = _correr(a, routing=True)

        self.assertIs(r.parametros["routing_jerarquico_activo"], True)
        self.assertEqual(r.metricas["routing_dominios_por_hu"], 1.0)
        self.assertLess(r.metricas["routing_sd_visibles_por_hu"], 341)
        self.assertEqual(r.historias[0].enrutamiento.business_domains, [_DOMINIO])
        self.assertEqual(
            r.historias[0].service_domains_visibles, len(a.catalogo_candidatos)
        )

    def test_la_huella_del_nodo_2a_viaja_en_el_resultado(self):
        """Sin huella no hay reproducibilidad: el routing decide qué vio el nodo siguiente."""
        a = _AnalistaEnrutado([_DOMINIO])
        r = _correr(a, routing=True)
        # El doble no pone metadatos; lo que se fija aquí es que el enrutamiento persiste con sus
        # dominios, que es el dato con el que se reproduce qué catálogo vio 2b.
        self.assertEqual(r.historias[0].enrutamiento.todos(), [_DOMINIO])

    def test_sin_routing_las_metricas_lo_dicen(self):
        a = _AnalistaEnrutado([_DOMINIO])
        r = _correr(a, routing=False)

        self.assertIs(r.parametros["routing_jerarquico_activo"], False)
        self.assertIsNone(r.metricas["routing_dominios_por_hu"])
        self.assertEqual(r.metricas["routing_sd_visibles_por_hu"], 341.0)


class TestEnrutamientoDominiosLLM(unittest.TestCase):
    def test_todos_une_sin_duplicar_y_conserva_el_orden(self):
        e = EnrutamientoDominiosLLM(
            business_domains=["A", "B"], dependency_domains=["B", "C"]
        )
        self.assertEqual(e.todos(), ["A", "B", "C"])

    def test_un_puerto_que_no_enruta_devuelve_vacio(self):
        """`enrutar_dominios` no es abstracto: enrutar es una estrategia, no un requisito."""

        class _Minimo(AnalistaMapeoBianPort):
            def extraer_intencion(self, *a):
                return IntencionHistoriaLLM()

            def generar_candidatos(self, *a, **kw):
                return CandidatosHistoriaLLM()

            def revisar_completitud(self, *a):
                return RevisionCompletitudLLM()

            def evaluar_candidato(self, *a):
                return EvaluacionCandidatoLLM(service_domain="x")

            def revisar_adversarial(self, *a):
                return RevisionAdversarialLLM()

            def reconciliar_funcionalidad(self, *a):
                return ReconciliacionFuncionalidadLLM()

        self.assertEqual(_Minimo().enrutar_dominios(None, None, None, []).todos(), [])


class _AnalistaContacto(_AnalistaEnrutado):
    """Intención de la HU real del E2E 1: el correo y el celular del cliente."""

    def extraer_intencion(self, historia, funcionalidad):
        return IntencionHistoriaLLM(
            resumen_funcional="guion",
            business_actions=["mostrar"],
            business_objects=[
                "informacion de contacto del cliente (numero celular y correo electronico)"
            ],
            traceability_ids=["SC-01"],
        )


class TestPropiedadDeClaseRescataAlPropietario(unittest.TestCase):
    """El canal determinista de 2a: el modelo BIAN atribuye la clase, el router no puede perderla.

    Con `entity.json`, un Service Domain que DEFINE en su BOM una clase que la historia necesita
    entra al catálogo de 2b aunque el enrutamiento por LLM no eligiera su Business Domain. Es el
    modo de fallo medido del router (2 de 7 candidatos invisibles en una corrida real).
    """

    @staticmethod
    def _correr(analista):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            servicio = _servicio(analista, routing=True, entidades=entidades)
            return servicio.ejecutar(hu, func, salida)

    def test_el_propietario_entra_aunque_su_dominio_no_se_enrutara(self):
        # El router elige un Business Domain que NO contiene a Party Reference Data Directory.
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = self._correr(a)

        self.assertIn(_SD, a.catalogo_candidatos, "2b tiene que ver al dueño de la clase Party")
        motivos = [i.get("motivo") for i in resultado.incidencias]
        self.assertIn("ROUTING_PROPIETARIO_DE_CLASE_BOM", motivos)

    def test_queda_auditable_en_el_json_con_su_bq_y_la_nota_del_enum(self):
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = self._correr(a)

        por_clase = resultado.historias[0].candidatos_por_clase
        self.assertTrue(por_clase, "el canal debe dejar su rastro en el resultado")
        dueno = next(c for c in por_clase if c.service_domain == _SD)
        self.assertIn("Reference", dueno.bqs(), "entity.json llega al BQ, nunca a la operación")
        contacto = next(e for e in dueno.evidencias if e.clase == "Contact Point")
        self.assertIn("Electronic Address", contacto.valores_enum)
        self.assertIn("SOLO tipifica", contacto.nota, "el enum no guarda el valor: lo dice la nota")

    def test_sin_catalogo_de_entidades_el_nodo_2a_es_el_de_siempre(self):
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        resultado = _correr(a, routing=True)

        self.assertNotIn(_SD, a.catalogo_candidatos)
        self.assertEqual(resultado.historias[0].candidatos_por_clase, [])
