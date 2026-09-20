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
        self.llamadas_candidatos: list[dict] = []

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
        self, historia, funcionalidad, intencion, catalogo, *, texto_completo=False, **kw
    ):
        self.catalogo_candidatos = [e.service_domain for e in catalogo]
        self.texto_completo = texto_completo
        self.totales_por_dominio = kw.get("totales_por_dominio")
        self.propietarios_bom = kw.get("propietarios_bom")
        self.llamadas_candidatos.append({
            "grupo": kw.get("grupo"),
            "catalogo": [e.service_domain for e in catalogo],
            "dominios": sorted({e.business_domain for e in catalogo}),
            "propietarios_bom": [c.service_domain for c in (kw.get("propietarios_bom") or [])],
        })
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


class TestTaxonomiaConDominiosAbiertosAMedias(unittest.TestCase):
    """Desde que 2a puede añadir un SD suelto, la taxonomía de 2b debe decir cuánto ve de cada rama."""

    def test_un_dominio_parcial_dice_cuantos_ve_de_cuantos(self):
        from src.adaptadores.salida.analista_mapeo_langchain import formatear_taxonomia

        catalogo = CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")).cargar()
        totales = {}
        for e in catalogo:
            totales[e.business_domain] = totales.get(e.business_domain, 0) + 1
        parcial = [e for e in catalogo if e.service_domain in ("Savings Account", _SD)]
        texto = formatear_taxonomia(parcial, totales)
        self.assertIn(f'"Loans and Deposits" (1 de {totales["Loans and Deposits"]} SD visibles)', texto)
        # Sin totales, la etiqueta es la de siempre (compatibilidad con validar-sd y con 2a).
        self.assertIn('"Loans and Deposits" (1 SD)', formatear_taxonomia(parcial))

    def test_un_dominio_entero_conserva_la_etiqueta_de_siempre(self):
        from src.adaptadores.salida.analista_mapeo_langchain import formatear_taxonomia

        catalogo = CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")).cargar()
        totales = {}
        for e in catalogo:
            totales[e.business_domain] = totales.get(e.business_domain, 0) + 1
        entero = [e for e in catalogo if e.business_domain == _DOMINIO]
        self.assertIn(f'"{_DOMINIO}" ({len(entero)} SD)', formatear_taxonomia(entero, totales))

    def test_2b_recibe_los_totales_solo_con_routing(self):
        a = _AnalistaEnrutado([_DOMINIO])
        _correr(a, routing=True)
        self.assertIsInstance(a.totales_por_dominio, dict)
        self.assertEqual(sum(a.totales_por_dominio.values()), 341)
        b = _AnalistaEnrutado([_DOMINIO])
        _correr(b, routing=False)
        self.assertIsNone(b.totales_por_dominio)


class TestCacheDelNodo2aIncluyeElCanal(unittest.TestCase):
    """Cambiar la configuración del canal de propiedad con la caché caliente NO puede devolver la
    salida anterior: la firma del canal entra en la clave del nodo 2a."""

    def test_otro_tope_del_canal_vuelve_a_ejecutar_2a(self):
        from src.adaptadores.salida.cache_nodos_archivo import CacheNodosArchivo

        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            cache = CacheNodosArchivo(Path(tmp) / "cache")
            a1 = _AnalistaContacto(["Market Data"], candidatos=[])
            _servicio(a1, routing=True, entidades=entidades, cache_nodos=cache,
                      entidades_max_candidatos=10).ejecutar(hu, func, salida + "1")
            a2 = _AnalistaContacto(["Market Data"], candidatos=[])
            _servicio(a2, routing=True, entidades=entidades, cache_nodos=cache,
                      entidades_max_candidatos=10).ejecutar(hu, func, salida + "2")
            self.assertEqual(a2.llamadas_enrutar, 0, "misma configuración: 2a sale de la caché")
            a3 = _AnalistaContacto(["Market Data"], candidatos=[])
            _servicio(a3, routing=True, entidades=entidades, cache_nodos=cache,
                      entidades_max_candidatos=3).ejecutar(hu, func, salida + "3")
            self.assertEqual(a3.llamadas_enrutar, 1, "otro tope del canal: 2a se vuelve a ejecutar")


class TestEvidenciaBomEnCandidatos(unittest.TestCase):
    """El flag `evidencia_bom_en_candidatos` decide si 2b ve POR QUÉ está cada rescatado."""

    @staticmethod
    def _correr(analista, **extra):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            return _servicio(analista, routing=True, entidades=entidades, **extra).ejecutar(hu, func, salida)

    def test_sin_flag_2b_no_recibe_la_evidencia(self):
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        r = self._correr(a)
        self.assertIsNone(a.propietarios_bom)
        self.assertFalse(r.parametros["evidencia_bom_en_candidatos"])

    def test_con_flag_2b_recibe_los_candidatos_por_clase_del_2a(self):
        a = _AnalistaContacto(["Market Data"], candidatos=[])
        r = self._correr(a, evidencia_bom_en_candidatos=True)
        self.assertTrue(a.propietarios_bom, "2b tiene que recibir la lista del canal")
        self.assertEqual(
            [c.service_domain for c in a.propietarios_bom],
            [c.service_domain for c in r.historias[0].candidatos_por_clase],
        )
        self.assertTrue(r.parametros["evidencia_bom_en_candidatos"])

    def test_la_metrica_cuenta_rescatados_propuestos(self):
        # El guion propone a PRDD, que el router NO enrutó (Market Data) y el canal rescató.
        a = _AnalistaContacto(["Market Data"], candidatos=[_SD])
        r = self._correr(a)
        self.assertGreaterEqual(r.metricas["bom_rescatados"], 1)
        self.assertEqual(r.metricas["bom_rescatados_propuestos"], 1)
        self.assertGreater(r.metricas["bom_rescatados_propuestos_rate"], 0)
        b = _AnalistaContacto([_DOMINIO], candidatos=[_SD])   # nada que rescatar: PRDD ya estaba
        r2 = self._correr(b)
        if r2.metricas["bom_rescatados"] == 0:
            self.assertIsNone(r2.metricas["bom_rescatados_propuestos_rate"])


class _AnalistaConDatos(_AnalistaContacto):
    """Nodo 1 con el campo `datos` (prompt 1.1.0): la consulta del canal son los datos, no los objetos."""

    def extraer_intencion(self, historia, funcionalidad):
        i = super().extraer_intencion(historia, funcionalidad)
        return i.model_copy(update={"business_objects": ["informacion de contacto del cliente"],
                                    "datos": ["numero celular", "correo electronico"]})


class _CanalEspia(RecuperadorClasesPortEspia := __import__("src.aplicacion.puertos.recuperador_clases", fromlist=["RecuperadorClasesPort"]).RecuperadorClasesPort):
    def __init__(self):
        self.consultas = []

    @property
    def nombre(self):
        return "espia"

    def recuperar(self, consulta, k):
        self.consultas.append(consulta)
        return []


class TestConsultaDelCanalUsaDatos(unittest.TestCase):
    def test_con_datos_la_consulta_son_los_datos(self):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        espia = _CanalEspia()
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            _servicio(_AnalistaConDatos(["Market Data"], candidatos=[]), routing=True, entidades=entidades,
                      recuperadores_clases=[espia]).ejecutar(hu, func, salida)
        self.assertEqual(len(espia.consultas), 1)
        self.assertEqual(espia.consultas[0].texto, "numero celular. correo electronico")
        self.assertNotIn("contacto", espia.consultas[0].texto)

    def test_sin_datos_se_cae_a_los_objetos(self):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        espia = _CanalEspia()
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            _servicio(_AnalistaContacto(["Market Data"], candidatos=[]), routing=True, entidades=entidades,
                      recuperadores_clases=[espia]).ejecutar(hu, func, salida)
        self.assertIn("contacto", espia.consultas[0].texto)


class TestFanOutDeCandidatosPorDominio(unittest.TestCase):
    """2b en `Send`: una llamada por Business Domain enrutado + una por los rescatados."""

    def _correr(self, analista, **extra):
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            return _servicio(analista, routing=True, entidades=entidades, candidatos_por_dominio=True, **extra).ejecutar(hu, func, salida)

    def test_una_llamada_por_dominio_y_una_por_rescatados(self):
        a = _AnalistaContacto(["Market Data", _DOMINIO], candidatos=[_SD])
        r = self._correr(a)
        llamadas = a.llamadas_candidatos
        self.assertGreaterEqual(len(llamadas), 2, "al menos los dos dominios enrutados")
        por_dominio = [l for l in llamadas if len(l["dominios"]) == 1]
        self.assertEqual(len(por_dominio), 2, "cada grupo de dominio ve UN solo Business Domain")
        self.assertTrue(all(l["propietarios_bom"] == [] for l in por_dominio), "los grupos de dominio no ven el bloque")
        rescatados = [l for l in llamadas if len(l["dominios"]) > 1 or l not in por_dominio]
        self.assertTrue(r.parametros["candidatos_por_dominio_activo"])
        self.assertTrue(r.metricas["bom_rescatados"] >= 1, "la HU de contacto rescata propietarios")
        self.assertEqual(len(rescatados), 1, "un único grupo de rescatados")

    def test_el_grupo_de_rescatados_es_el_unico_que_ve_la_evidencia(self):
        a = _AnalistaContacto(["Market Data"], candidatos=[_SD])
        self._correr(a, evidencia_bom_en_candidatos=True)
        con_bloque = [l for l in a.llamadas_candidatos if l["propietarios_bom"]]
        self.assertEqual(len(con_bloque), 1)
        self.assertTrue(set(con_bloque[0]["propietarios_bom"]) <= set(con_bloque[0]["catalogo"]),
                        "la evidencia solo habla de los SD de ESE grupo")

    def test_la_fusion_llega_al_nodo_3_y_al_resultado(self):
        a = _AnalistaContacto(["Market Data", _DOMINIO], candidatos=[_SD])
        r = self._correr(a)
        todos = [*r.historias[0].service_domains.candidatos_directos, *r.historias[0].service_domains.candidatos_tentativos,
                 *r.historias[0].service_domains.candidatos_descartados]
        self.assertIn(_SD, [x.service_domain for x in todos], "el candidato del guion sobrevive a la fusión")
        # (las huellas por llamada las pone el adaptador real; el doble no adjunta metadatos)

    def test_cada_llamada_de_grupo_lleva_su_nombre_y_el_prompt_de_grupo(self):
        from src.adaptadores.salida.prompts_mapeo import SPEC_CANDIDATOS_GRUPO, SPEC_CANDIDATOS_GRUPO_BOM

        a = _AnalistaContacto(["Market Data", _DOMINIO], candidatos=[_SD])
        self._correr(a)
        self.assertTrue(all(l["grupo"] for l in a.llamadas_candidatos), "cada llamada dice qué grupo ve")
        self.assertIn("<alcance_catalogo>", SPEC_CANDIDATOS_GRUPO.template.messages[1].prompt.template)
        self.assertIn("devuelve `candidatos` VACÍO", SPEC_CANDIDATOS_GRUPO.template.messages[0].prompt.template)
        self.assertIn("<propietarios_bom", SPEC_CANDIDATOS_GRUPO_BOM.template.messages[1].prompt.template)
        self.assertEqual((SPEC_CANDIDATOS_GRUPO.version, SPEC_CANDIDATOS_GRUPO_BOM.version), ("1.3.0", "1.3.1"))

    def test_sin_routing_no_hay_fan_out(self):
        a = _AnalistaContacto([_DOMINIO], candidatos=[_SD])
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            _servicio(a, routing=False, candidatos_por_dominio=True).ejecutar(hu, func, salida)
        self.assertEqual(len(a.llamadas_candidatos), 1)
        self.assertEqual(len(a.llamadas_candidatos[0]["catalogo"]), 341)


class TestRescateConUmbral(unittest.TestCase):
    """Poca señal (un solo canal, score bajo) no abre 2b, pero queda como incidencia."""

    def test_un_candidato_debil_no_se_rescata_y_deja_incidencia(self):
        from src.dominio.historias import CandidatoClaseBom, EvidenciaClaseBom
        catalogo = CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")).cargar()
        filtrado = [e for e in catalogo if e.business_domain == "Payments"]  # sin ninguno de los tres
        fuerte = CandidatoClaseBom(service_domain="Location Data Management", score=3.6,
                                   evidencias=[EvidenciaClaseBom(clase="Phone Address", motivos=["bm25#4", "vectorial#8"])])
        dos_canales = CandidatoClaseBom(service_domain=_SD, score=0.9,
                                        evidencias=[EvidenciaClaseBom(clase="Contact Point", motivos=["bm25#1", "vectorial#2"])])
        debil = CandidatoClaseBom(service_domain="Suitability Checking", score=0.84,
                                  evidencias=[EvidenciaClaseBom(clase="Suitability Assessment Involvement", motivos=["vectorial#5"])])
        historia = type("H", (), {"archivo": "HU-01.txt"})()
        nuevo, inc = MapearHistoriasServiceDomainsService._rescatar_propietarios(
            historia, catalogo, filtrado, [fuerte, dos_canales, debil], min_score=1.0, min_canales=2)
        nombres = {e.service_domain for e in nuevo}
        self.assertIn("Location Data Management", nombres, "score alto: rescatado")
        self.assertIn(_SD, nombres, "dos canales: rescatado aunque el score sea < 1.0")
        self.assertNotIn("Suitability Checking", nombres)
        motivos = {i["service_domain_propuesto"]: i["motivo"] for i in inc}
        self.assertEqual(motivos["Suitability Checking"], "ROUTING_PROPIETARIO_NO_RESCATADO")
        self.assertEqual(motivos["Location Data Management"], "ROUTING_PROPIETARIO_DE_CLASE_BOM")


class TestGruposPequenos(unittest.TestCase):
    def test_los_dominios_pequenos_se_juntan(self):
        a = _AnalistaContacto(["Party", _DOMINIO], candidatos=[_SD])   # Party tiene 2 SD
        entidades = CatalogoEntidadesJson(str(DOCS / "entity.json"))
        with tempfile.TemporaryDirectory() as tmp:
            hu, func, salida = _entrada(tmp)
            _servicio(a, routing=True, entidades=entidades, candidatos_por_dominio=True,
                      candidatos_grupo_min_sd=3).ejecutar(hu, func, salida)
        solos = [l for l in a.llamadas_candidatos if l["dominios"] == ["Party"]]
        self.assertEqual(solos, [], "Party (2 SD) no va solo")
        self.assertTrue(any("Party" in (l["grupo"] or "") for l in a.llamadas_candidatos), "pero sí se evalúa, en un grupo compuesto")
