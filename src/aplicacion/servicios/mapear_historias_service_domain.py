"""Caso de uso `MapearHistoriasUseCase` orquestado con LangGraph.

Outer graph (map-reduce sobre las HU):

    START -> cargar -> (Send por HU) -> procesar_historia --+--> reconciliar -> publicar -> END

`procesar_historia` invoca un SUBGRAFO por historia con su propio fan-out por candidato:

    extraer_intencion -> generar_candidatos -> revisar_completitud
      -> preparar_candidatos            [det: unión LLM ∪ missing ∪ retrieval híbrido (opcional)
                                          + paquete de evidencia por SD; nada se descarta en
                                          silencio por `max_candidatos_hu`, ver `incidencias`]
      -> (Send por candidato) evaluar_candidato   [1 llamada aislada / paquete de evidencia cerrado]
      -> clasificar                     [det: scoring_bian + dos ejes + tope por rol]
      -> revisar_adversarial            [LLM, prompt independiente]
      -> aplicar_adversarial            [det: promueve CONSUMED_DEPENDENCY->OWNED_CONTRACT solo con
                                          evidencia fuerte (`determinar_promociones`), degrada
                                          SELECTED->UNRESOLVED en el resto de hallazgos]
      -> seleccionar_operaciones        [LLM + anclaje al catálogo local; elegibles = OWNED
                                          directo o tentativo, no solo "directo"]
      -> ensamblar

El LLM nunca decide el estado final: `scoring_bian` + `clasificacion_historias` + `_consolidar`
son el árbitro. `reconciliar_funcionalidad` es un asesor a nivel de funcionalidad.
Depende SOLO de: dominio, puertos y `langgraph`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid

from langgraph.graph import END, START, StateGraph

try:
    from langgraph.types import CachePolicy, RetryPolicy, Send
except ImportError:  # pragma: no cover
    from langgraph.constants import Send  # type: ignore
    from langgraph.pregel import RetryPolicy  # type: ignore

    CachePolicy = None  # type: ignore[assignment]

from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.catalogo_bom import CatalogoBomPort
from src.aplicacion.puertos.catalogo_entidades import CatalogoEntidadesBianPort
from src.aplicacion.puertos.catalogo_operaciones_bian import CatalogoOperacionesBianPort
from src.aplicacion.puertos.entrada_mapeo import MapearHistoriasUseCase
from src.aplicacion.puertos.grafo_bian import GrafoBianPort
from src.aplicacion.puertos.lector_historias import LectorHistoriasPort
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.puertos.publicador_mapeo import PublicadorMapeoPort
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.aplicacion.puertos.recuperador_clases import RecuperadorClasesPort
from src.aplicacion.puertos.reranker import RerankerPort
from src.aplicacion.servicios.estado_historia import EstadoHistoria
from src.aplicacion.servicios.estado_mapeo import EstadoMapeo
from src.dominio.clasificacion_historias import (
    CONFLICTO_CONFIRMADO_POR_GRAFO,
    CONFLICTO_SIN_RESPALDO_DE_GRAFO,
    DEMOTED_REASON_CODE,
    OPERATION_FINALIZED_REASON_CODE,
    PROMOTED_REASON_CODE,
    PROMOTED_BY_ACTION_REASON_CODE,
    confirmar_conflictos_por_grafo,
    degradar_sin_operacion_anclada,
    determinar_promociones_por_accion,
    motivos_no_promocion,
    UmbralesMapeo,
    aplicar_hallazgos_adversariales,
    candidatos_operacion_elegibles,
    clasificar_service_domains,
    determinar_degradaciones,
    determinar_promociones,
    finalizar_por_operacion_solida,
    propuestos_degradados,
    propuestos_promovidos,
    resolver_nombre_sd,
)
from src.dominio.cobertura_operaciones import (
    campos_alcanzables,
    cobertura_datos_requeridos,
    derivar_path_grupo,
    fusionar_propuestas_de_operacion,
    operacion_evidencia_verificable,
    operation_id_en_uso,
    resolver_dato_requerido,
    resolver_operation_id,
)
from src.dominio.entidades_bian import (
    ConsultaClases,
    candidatos_por_propiedad,
    clases_requeridas,
    clases_requeridas_desde_rankings,
)
from src.dominio.deteccion_omitidos import detectar_omitidos
from src.dominio.fusion_candidatos import fusionar_candidatos
from src.dominio.fusion_rrf import fusion_rrf
from src.dominio.historias import (
    BqPersonalizadoAplicado,
    CandidatoClaseBom,
    DecisionServiceDomainConsolidada,
    EnrutamientoDominiosLLM,
    EvidenciaBian,
    HistoriaConServiceDomains,
    HistoriaUsuario,
    IntencionHistoriaLLM,
    MapeoOperacionesLLM,
    MetadatosPrompt,
    OperacionBian,
    OperacionBianAplicada,
    PaqueteEvidenciaCandidato,
    ReconciliacionFuncionalidadLLM,
    ResultadoMapeoHistorias,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
    ServiceDomainAsignado,
    ServiceDomainOmitido,
    ServiceDomainPropuestoLLM,
)
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar

logger = logging.getLogger("generacion_contrato_ia_v2.aplicacion.mapeo")

_TRANSITORIOS = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE")


def _es_transitorio(exc: Exception) -> bool:
    t = str(exc).upper()
    # el failover multi-modelo ya agotó todo -> no tiene sentido reintentar el nodo entero
    if (
        "TODOSLOSMODELOSAGOTADOS" in type(exc).__name__.upper()
        or "SE AGOTARON TODOS LOS MODELOS" in t
    ):
        return False
    return any(m in t for m in _TRANSITORIOS)


_RETRY = RetryPolicy(
    max_attempts=3,
    initial_interval=2.0,
    backoff_factor=2.0,
    max_interval=20.0,
    retry_on=_es_transitorio,
)


class _Presupuesto:
    """Reloj compartido por las etapas OPCIONALES de recuperación de una historia.

    No aborta nada a media ejecución -cortar un embedding por la mitad no ahorra nada y deja
    estado raro-: comprueba ANTES de cada etapa si queda tiempo, y si no, la salta dejándolo en
    el log. Con `segundos <= 0` no hay límite, que es el comportamiento histórico.
    """

    def __init__(self, segundos: float, historia: str) -> None:
        self._limite = segundos
        self._historia = historia
        self._inicio = time.monotonic()

    def queda(self, etapa: str) -> bool:
        if self._limite <= 0:
            return True
        usado = time.monotonic() - self._inicio
        if usado < self._limite:
            return True
        logger.warning(
            "HU '%s': presupuesto de retrieval agotado (%.1fs de %.1fs); se omite %s",
            self._historia,
            usado,
            self._limite,
            etapa,
        )
        return False


def _huellas(*modelos) -> list[MetadatosPrompt]:
    return [
        m.metadatos for m in modelos if m is not None and getattr(m, "metadatos", None) is not None
    ]


def _paquete_de(
    entrada: EntradaCatalogo,
    evidencia: EvidenciaBian,
    operaciones: list,
    esquemas: list[str],
    *,
    origen: str,
    supporting_intent: list[str],
    schemas_detalle: list | None = None,
    bom_modelo=None,
) -> PaqueteEvidenciaCandidato:
    return PaqueteEvidenciaCandidato(
        service_domain=entrada.service_domain,
        business_area=entrada.business_area,
        business_domain=entrada.business_domain,
        service_role=entrada.service_role or "",
        functional_pattern=entrada.functional_pattern,
        asset_type=entrada.asset_type,
        control_records=sorted({o.grupo for o in operaciones if o.tipo == "CR"}),
        behavior_qualifiers=sorted({o.grupo for o in operaciones if o.tipo == "BQ"}),
        operations=list(operaciones),
        schemas=list(esquemas),
        schemas_detalle=list(schemas_detalle or []),
        bom_modelo=bom_modelo,
        evidencia=evidencia,
        origen=origen,  # type: ignore[arg-type]
        supporting_intent=list(supporting_intent),
    )


# Vocabulario BIAN de verbos de operación (Control Record y Behavior Qualifier).
_VERBOS_BIAN = {
    "Initiate",
    "Update",
    "Retrieve",
    "Control",
    "Request",
    "Execute",
    "Exchange",
    "Grant",
    "Register",
}


def _pascal(texto: str) -> str:
    partes = re.split(r"[^A-Za-z0-9]+", texto or "")
    return "".join(p[:1].upper() + p[1:] for p in partes if p) or "Custom"


def _bom_respalda(paquete: PaqueteEvidenciaCandidato, clase: str, atributo: str) -> bool:
    """¿`paquete` (schemas_detalle + bom_modelo) tiene de verdad esa clase/atributo? Anti-alucinación
    de la propia PROPUESTA de BQ personalizado: sin esta evidencia real, no se ancla nada."""
    clave_clase = normalizar(clase)
    if not clave_clase:
        return False
    clave_attr = normalizar(atributo)
    for s in paquete.schemas_detalle:
        if normalizar(s.name) == clave_clase:
            if not clave_attr:
                return True
            return clave_attr in {normalizar(p.name) for p in s.properties}
    if paquete.bom_modelo is not None:
        for c in paquete.bom_modelo.clases:
            if normalizar(c.name) == clave_clase:
                if not clave_attr:
                    return True
                return clave_attr in {normalizar(a.name) for a in c.attributes}
        if any(normalizar(e.name) == clave_clase for e in paquete.bom_modelo.enums):
            return True
    return False


def _operaciones_disponibles(asignado, estado) -> int:
    """Cuántas operaciones oficiales tiene ese SD en el paquete de evidencia ya armado.

    Cero red y cero LLM: el paquete se armó en `preparar_candidatos`, aquí solo se cuenta.
    """
    clave = normalizar(asignado.service_domain)
    for paquete in estado.get("a_evaluar", []):
        if normalizar(paquete.service_domain) == clave:
            return len(paquete.operations)
    return 0


def _fusionar_mapeos(mapeos: list[MapeoOperacionesLLM]) -> MapeoOperacionesLLM:
    """Une los mapeos de las llamadas por Service Domain en uno solo.

    Las huellas NO se fusionan aqui: cada llamada tiene la suya y todas deben persistir en
    `huellas_prompts`, porque el numero de huellas ES el numero de llamadas LLM de la corrida. El
    llamador las recoge por separado (ver `_asignar_operaciones`).
    """
    if not mapeos:
        return MapeoOperacionesLLM()
    return MapeoOperacionesLLM(
        operaciones=[o for m in mapeos for o in m.operaciones],
        bq_personalizados=[b for m in mapeos for b in m.bq_personalizados],
        # Cada llamada ve UN Service Domain, así que "este dato no lo expone ninguna operación"
        # es una declaración PARCIAL: la unión se reparte después contra lo que cubrió cualquier
        # otro Service Domain (`cobertura_datos_requeridos`, donde "cubierto" gana a "declarado").
        datos_no_cubiertos=list(dict.fromkeys(d for m in mapeos for d in m.datos_no_cubiertos)),
        gaps=list(dict.fromkeys(g for m in mapeos for g in m.gaps)),
        blocking_codes=list(dict.fromkeys(c for m in mapeos for c in m.blocking_codes)),
        citas_descartadas=[c for m in mapeos for c in m.citas_descartadas],
        metadatos=next((m.metadatos for m in mapeos if m.metadatos is not None), None),
    )


def _canonico(valor) -> str:
    """Texto estable y comparable de una entrada de nodo, para la clave de caché.

    Modelos Pydantic -> su JSON (orden de campos fijo por el modelo); el resto -> JSON con claves
    ordenadas. Nunca entra el estado completo: cada `key_func` elige QUÉ entradas son semánticas
    para ese nodo, así que cambiar un flag que no afecta a un nodo no invalida su caché.
    """
    if valor is None:
        return "null"
    volcar = getattr(valor, "model_dump_json", None)
    if callable(volcar):
        return volcar()
    if isinstance(valor, (list, tuple)):
        return "[" + ",".join(_canonico(v) for v in valor) + "]"
    if isinstance(valor, dict):
        return "{" + ",".join(f"{k}:{_canonico(valor[k])}" for k in sorted(valor)) + "}"
    try:
        return json.dumps(valor, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover - defensivo
        return str(valor)


def _sha_corto(*partes: str) -> str:
    return hashlib.sha256("\x1f".join(partes).encode("utf-8")).hexdigest()[:40]


class MapearHistoriasServiceDomainsService(MapearHistoriasUseCase):
    def __init__(
        self,
        catalogo: CatalogoServiceDomainsPort,
        lector: LectorHistoriasPort,
        analista: AnalistaMapeoBianPort,
        publicador: PublicadorMapeoPort,
        catalogo_operaciones: CatalogoOperacionesBianPort,
        mapeador_operaciones: MapeadorOperacionesBianPort,
        *,
        catalogo_bom: CatalogoBomPort | None = None,
        umbrales: UmbralesMapeo | None = None,
        concurrencia: int = 1,
        concurrencia_candidatos: int = 2,
        max_candidatos_hu: int = 14,
        mapear_operaciones: bool = True,
        parametros_base: dict | None = None,
        actualizar_cache_bian: bool = False,
        top_n_omitidos: int = 5,
        routing_jerarquico: bool = False,
        catalogo_entidades: CatalogoEntidadesBianPort | None = None,
        entidades_max_candidatos: int = 5,
        recuperadores_clases: list[RecuperadorClasesPort] | None = None,
        entidades_canal_diccionario: bool = True,
        entidades_top_k_clases: int = 12,
        entidades_rrf_k: int = 20,
        entidades_min_score_rescate: float = 1.0,
        entidades_min_canales_rescate: int = 2,
        evidencia_bom_en_candidatos: bool = False,
        candidatos_por_dominio: bool = False,
        candidatos_grupo_min_sd: int = 3,
        recuperadores: list[RecuperadorSemanticoPort] | None = None,
        retrieval_top_k: int = 20,
        retrieval_max_inyectados: int = 5,
        rrf_k: int = 60,
        rrf_pesos: list[float] | None = None,
        grafo: GrafoBianPort | None = None,
        graph_rag_max_inyectados: int = 3,
        senales_grafo_adversarial: bool = False,
        crag_reintento: bool = False,
        reranker: RerankerPort | None = None,
        presupuesto_segundos_hu: float = 0.0,
        cache_nodos=None,
        cache_nodos_ttl: int = 0,
        durabilidad: str = "exit",
        checkpointer=None,
    ) -> None:
        self._catalogo = catalogo
        self._lector = lector
        self._analista = analista
        self._publicador = publicador
        self._catalogo_operaciones = catalogo_operaciones
        self._catalogo_bom = catalogo_bom
        self._mapeador_operaciones = mapeador_operaciones
        self._umbrales = umbrales or UmbralesMapeo()
        self._concurrencia = max(1, concurrencia)
        self._concurrencia_candidatos = max(1, concurrencia_candidatos)
        self._max_candidatos_hu = max(1, max_candidatos_hu)
        self._mapear_operaciones = mapear_operaciones
        self._parametros_base = dict(parametros_base or {})
        self._actualizar_cache_bian = actualizar_cache_bian
        self._top_n_omitidos = max(0, top_n_omitidos)
        # Routing jerárquico: parte el paso de candidatos en 2a (elige Business Domains sobre la
        # taxonomía) + 2b (ve solo los SD de esos dominios, pero con el texto COMPLETO). Apagado,
        # el subgrafo es exactamente el de siempre: un nodo, los 341 SD con el rol recortado.
        self._routing_jerarquico = routing_jerarquico
        # Canal DETERMINISTA del nodo 2a: quién DEFINE cada clase del BOM que la historia
        # necesita (`entidades_bian`). `None` = apagado y el nodo 2a es exactamente el de antes.
        # No sustituye al enrutamiento por LLM: le impide perder un propietario que el propio
        # modelo BIAN ya atribuye, que es el modo de fallo medido del router.
        self._catalogo_entidades = catalogo_entidades
        self._entidades_max_candidatos = max(0, entidades_max_candidatos)
        # Paso 1 del canal como recuperación híbrida: cada `RecuperadorClasesPort` propone clases
        # (BM25 sobre el texto traducido, embeddings sobre el texto natural) y el diccionario
        # `CLASES_BOM_POR_TERMINO` es un canal más; se fusionan con RRF. Sin recuperadores, el
        # paso 1 es el diccionario solo, exactamente como antes.
        self._recuperadores_clases = list(recuperadores_clases or [])
        self._entidades_canal_diccionario = entidades_canal_diccionario
        self._entidades_top_k_clases = max(1, entidades_top_k_clases)
        self._entidades_rrf_k = max(1, entidades_rrf_k)
        # Para RESCATAR (añadir al catálogo de 2b) un propietario que el router no enrutó se exige
        # o bien score >= min_score (1.0 = fue top-1 de algún canal, o acumuló) o bien que lo
        # propongan >= min_canales canales distintos. Medido en el E2E 1: los rescates ruidosos
        # (Suitability Checking, Market Information Management, Counterparty Administration)
        # venían de UN solo canal, el denso, en posiciones 5-6, con 0.81-0.88. El candidato sigue
        # en `candidatos_por_clase` (auditable); lo que no se hace es abrirle la puerta a 2b.
        self._entidades_min_score_rescate = float(entidades_min_score_rescate)
        self._entidades_min_canales_rescate = max(1, int(entidades_min_canales_rescate))
        # ¿2b ve la evidencia del canal (`<propietarios_bom>`, prompt 1.2.0)? OFF por defecto:
        # cambia el prompt y sesga a 2b hacia lo que el canal dijo; se enciende tras medirlo.
        self._evidencia_bom_en_candidatos = bool(evidencia_bom_en_candidatos)
        # Fan-out de 2b (`Send`): UNA llamada por Business Domain enrutado (+ una para los
        # propietarios rescatados por el canal, que es la única que ve `<propietarios_bom>`), y
        # un nodo determinista que une. Medido 2026-09-20 sin fan-out: 80-88 SD en un prompt de
        # 19-21k tokens, Groq excluido por presupuesto, Gemini 3.6 en 503, 43-99 s por HU. Con
        # ~15 SD por llamada el prompt baja a ~4k y cabe en toda la cadena.
        self._candidatos_por_dominio = bool(candidatos_por_dominio)
        # Un grupo con menos SD que esto no va solo: medido (grupo "Party", 2 SD), el modelo
        # propone "lo menos irrelevante" aun con el prompt de grupo. Los pequeños se juntan en un
        # solo grupo, que sigue siendo pequeño en tokens pero le da algo con qué comparar.
        self._candidatos_grupo_min_sd = max(1, int(candidatos_grupo_min_sd))
        # Firma del canal para la clave de caché del nodo 2a (ver `_compilar_subgrafo`).
        self._firma_entidades = (
            "entidades:off"
            if catalogo_entidades is None or self._entidades_max_candidatos == 0
            else "entidades:"
            + ",".join(
                (["diccionario"] if self._entidades_canal_diccionario or not self._recuperadores_clases else [])
                + [r.nombre for r in self._recuperadores_clases]
            )
            + f":tope={self._entidades_max_candidatos}:topk={self._entidades_top_k_clases}"
            f":k={self._entidades_rrf_k}"
        )
        # Retrieval híbrido (Fase 3 del plan, en memoria): opcional -- lista vacía = desactivado,
        # el pipeline se comporta exactamente como antes (solo candidatos LLM + completitud).
        self._recuperadores = list(recuperadores or [])
        self._retrieval_top_k = max(1, retrieval_top_k)
        self._retrieval_max_inyectados = max(0, retrieval_max_inyectados)
        # Fusión: `k` y un peso por canal (mismo orden que `recuperadores`). Sin pesos explícitos
        # se fusiona como siempre (todos a 1.0) -- ver `fusion_rrf`.
        self._rrf_k = max(1, rrf_k)
        self._rrf_pesos = list(rrf_pesos) if rrf_pesos else None
        self._grafo_bian = grafo
        self._graph_rag_max_inyectados = max(0, graph_rag_max_inyectados)
        # El grafo como SEÑAL para el árbitro, no como generador de candidatos: flag aparte del
        # de expansión porque son dos usos distintos del mismo artefacto y hay que poder medirlos
        # por separado (uno añade candidatos, el otro comprueba un conflicto ya afirmado).
        self._senales_grafo_adversarial = senales_grafo_adversarial
        # CRAG: UNA sola vuelta correctiva, y solo cuando el lote de evidencia sale vacío/débil.
        # Acotada a propósito: un lazo agéntico abierto rompería las dos propiedades que el
        # pipeline defiende (reproducibilidad por huellas y coste predecible por HU).
        self._crag_reintento = crag_reintento
        self._reranker = reranker
        # Presupuesto para el retrieval OPCIONAL (híbrido + grafo + reranker) de cada historia.
        # No cubre las llamadas LLM: esas ya tienen su propio failover con reintentos. Cubre justo
        # lo que se añadió después y puede colgarse sin que nadie lo note -un proveedor de
        # embeddings lento, un índice externo que no responde, un modelo que tarda en cargar-.
        # 0 = sin límite.
        self._presupuesto_segundos_hu = max(0.0, presupuesto_segundos_hu)
        # Caché de nodos (LangGraph 1.x): `None` = desactivada y el grafo se comporta exactamente
        # como antes. La clave de cada nodo lleva esta firma, así que un resultado producido por
        # otra cadena de modelos o sobre otro catálogo NUNCA se reutiliza.
        self._cache_nodos = cache_nodos
        self._cache_nodos_ttl = max(0, cache_nodos_ttl) or None
        self._firma_llm = _sha_corto(
            str(self._parametros_base.get("cadena_llm", "")),
            str(self._parametros_base.get("esfuerzo", "")),
            str(self._parametros_base.get("catalog_sha256", "")),
        )
        self._durabilidad = durabilidad if durabilidad in ("exit", "sync", "async") else "exit"
        self._checkpointer_inyectado = checkpointer
        # `thread_id` de la corrida en curso: sale en `parametros` para poder reanudarla. Vacío
        # cuando no hay durabilidad, porque entonces no hay nada que reanudar.
        self._thread_id = ""
        self._subgrafo = self._compilar_subgrafo()
        self._grafo = self._compilar()

    def ejecutar(
        self,
        directorio_hu: str,
        ruta_funcionalidad: str,
        directorio_salida: str,
        *,
        reanudar: str | None = None,
    ) -> ResultadoMapeoHistorias:
        config: dict = {"recursion_limit": 60, "max_concurrency": self._concurrencia}
        extra: dict = {}
        entrada: dict | None = {
            "directorio_hu": directorio_hu,
            "ruta_funcionalidad": ruta_funcionalidad,
            "directorio_salida": directorio_salida,
        }
        if self._durabilidad != "exit":
            # Cada corrida es su propio hilo de checkpoints: nunca se mezcla con una anterior,
            # salvo que se pida explícitamente continuar una.
            self._thread_id = reanudar or uuid.uuid4().hex
            config["configurable"] = {"thread_id": self._thread_id}
            extra["durability"] = self._durabilidad
            if reanudar:
                # `None` como entrada = "sigue donde te quedaste". Mandar la entrada otra vez
                # reiniciaría el grafo desde `cargar` y perdería el trabajo ya hecho.
                entrada = None
                logger.info("reanudando la corrida %s desde su último checkpoint", reanudar)
        elif reanudar:
            raise ValueError(
                f"no se puede reanudar la corrida '{reanudar}': la durabilidad está en 'exit', "
                "así que no se guardó ningún checkpoint. Actívala con "
                "`mapear_historias.durabilidad: sync` ANTES de la corrida que quieras reanudar."
            )
        estado = self._grafo.invoke(entrada, config=config, **extra)
        if self._cache_nodos is not None:
            logger.info(
                "caché de nodos: %d aciertos / %d fallos",
                getattr(self._cache_nodos, "aciertos", 0),
                getattr(self._cache_nodos, "fallos", 0),
            )
        return self._resultado_mapeo(estado)

    # ══ outer graph ═════════════════════════════════════════════════════════
    def _nodo_cargar(self, estado: EstadoMapeo) -> dict:
        funcionalidad = self._lector.leer_funcionalidad(estado["ruta_funcionalidad"])
        historias = self._lector.leer_historias(estado["directorio_hu"])
        if not historias:
            raise ValueError(f"No se encontraron Historias de Usuario en {estado['directorio_hu']}")
        catalogo = self._catalogo.cargar()
        logger.info(
            "cargado: %d historias | funcionalidad='%s' | catalogo=%d SD | SD con operaciones=%d",
            len(historias),
            funcionalidad.funcionalidad_macro,
            len(catalogo),
            len(self._catalogo_operaciones.service_domains_con_catalogo()),
        )
        return {
            "funcionalidad": funcionalidad,
            "historias": historias,
            "catalogo": catalogo,
            "total_historias": len(historias),
        }

    def _fan_out(self, estado: EstadoMapeo) -> list:
        return [
            Send(
                "procesar_historia",
                {
                    "historia": h,
                    "funcionalidad": estado["funcionalidad"],
                    "catalogo": estado["catalogo"],
                },
            )
            for h in estado["historias"]
        ]

    def _nodo_procesar(self, estado: dict) -> dict:
        est = self._subgrafo.invoke(
            {
                "historia": estado["historia"],
                "funcionalidad": estado["funcionalidad"],
                "catalogo": estado["catalogo"],
            },
            config={"recursion_limit": 80, "max_concurrency": self._concurrencia_candidatos},
        )
        return {
            "procesadas": [est["resultado"]],
            "incidencias": list(est.get("incidencias", [])),
            "huellas_prompts": list(est.get("huellas", [])),
        }

    def _nodo_reconciliar(self, estado: EstadoMapeo) -> dict:
        procesadas = self._procesadas_ordenadas(estado)
        rec = self._analista.reconciliar_funcionalidad(
            estado["funcionalidad"], [self._resumen_hu(h) for h in procesadas]
        )
        salida: dict = {"reconciliacion": rec}
        if rec.metadatos is not None:
            salida["huellas_prompts"] = [rec.metadatos]
        return salida

    def _nodo_publicar(self, estado: EstadoMapeo) -> dict:
        resultado = self._resultado_mapeo(estado)
        ruta = self._publicador.publicar(resultado, estado["directorio_salida"])
        logger.info("resultado -> %s", ruta)
        return {"ruta_resultado": ruta}

    # ══ subgrafo por historia ══════════════════════════════════════════════
    def _h_intencion(self, estado: EstadoHistoria) -> dict:
        intencion = self._analista.extraer_intencion(estado["historia"], estado["funcionalidad"])
        return {"intencion": intencion, "huellas": _huellas(intencion)}

    def _h_enrutar(self, estado: EstadoHistoria) -> dict:
        """Nodo 2a: elige Business Domains y recorta el catálogo que verá el nodo 2b.

        La llamada LLM elige; el recorte es DETERMINISTA y desconfiado: un nombre que no resuelve
        contra la taxonomía real no filtra nada y queda como incidencia, y si no resuelve ninguno
        se sigue con el catálogo completo. Enrutar mal debe costar tokens, nunca candidatos.
        """
        catalogo = estado["catalogo"]
        enr = self._analista.enrutar_dominios(
            estado["historia"], estado["funcionalidad"], estado["intencion"], catalogo
        )
        filtrado, incidencias = self._filtrar_por_dominios(estado["historia"], catalogo, enr)
        por_clase = self._candidatos_por_clase(estado["intencion"])
        filtrado, inc_clase = self._rescatar_propietarios(
            estado["historia"],
            catalogo,
            filtrado,
            por_clase,
            min_score=self._entidades_min_score_rescate,
            min_canales=self._entidades_min_canales_rescate,
        )
        logger.info(
            "HU '%s' -> enrutada a %d dominio(s) [%s]: %d de %d Service Domains visibles%s",
            estado["historia"].archivo,
            len(enr.todos()),
            ", ".join(enr.todos()) or "(ninguno)",
            len(filtrado),
            len(catalogo),
            f" | propiedad de clase BOM: {', '.join(c.service_domain for c in por_clase)}"
            if por_clase
            else "",
        )
        return {
            "enrutamiento": enr,
            "catalogo_enrutado": filtrado,
            "candidatos_por_clase": por_clase,
            # Los SD que el canal AÑADIÓ (no estaban en los dominios enrutados): el fan-out de 2b
            # los agrupa aparte y es el único grupo que ve la evidencia del canal.
            "sd_rescatados": [
                i["service_domain_propuesto"] for i in inc_clase if i.get("decision") == "ADDED"
            ],
            "huellas": _huellas(enr),
            "incidencias": incidencias + inc_clase,
        }

    def _candidatos_por_clase(self, intencion: IntencionHistoriaLLM) -> list[CandidatoClaseBom]:
        """Service Domains que DEFINEN una clase del BOM que la historia necesita. Sin LLM.

        Paso 1 (qué clases pide la historia) es recuperación: el diccionario ES->EN, BM25 sobre el
        documento de cada clase y/o embeddings sobre el texto natural, fusionados con RRF
        (`clases_requeridas_desde_rankings`). Pasos 2-4 (quién define cada clase, con qué
        Behavior Qualifier y si el enum solo tipifica o la clase guarda el valor) los responde el
        modelo BIAN, no un ranking (`candidatos_por_propiedad`). La consulta son los
        `business_objects` que el nodo 1 ya extrajo, y solo ellos.
        """
        if self._catalogo_entidades is None or self._entidades_max_candidatos == 0:
            return []
        clases = self._catalogo_entidades.clases()
        if not clases:
            return []
        enums = self._catalogo_entidades.nombres_enum()
        # SOLO los objetos de negocio: el canal responde "qué CLASES necesita la historia", y las
        # acciones y capacidades no son clases. Medido en la corrida real del E2E 1: con acciones +
        # capacidades ("pantalla", "avatar", "navegar", "menú Perfil") el canal denso se va a clases
        # de perfil/sesión/dispositivo y el dueño del dato cae del top-10; solo con los objetos no.
        # `datos` (nodo 1, prompt 1.1.0) son los datos concretos uno por elemento; si el modelo
        # no los dio, se cae a los objetos de negocio, que es lo que había antes.
        consulta = ConsultaClases.desde_textos(intencion.datos or intencion.business_objects)
        top_k = self._entidades_top_k_clases
        if not self._recuperadores_clases:
            # Un solo canal (el diccionario): sin fusión, con los pesos de siempre.
            requeridas = clases_requeridas(consulta.terminos, clases, nombres_enum=enums, tope=top_k)
        else:
            rankings: dict[str, list[str]] = {}
            if self._entidades_canal_diccionario:
                rankings["diccionario"] = [
                    r.clase
                    for r in clases_requeridas(
                        consulta.terminos, clases, nombres_enum=enums, tope=top_k
                    )
                ]
            for recuperador in self._recuperadores_clases:
                try:
                    rankings[recuperador.nombre] = [
                        c.clase for c in recuperador.recuperar(consulta, top_k)
                    ]
                except Exception as exc:  # un canal caído no tumba el nodo: se sigue sin él
                    logger.warning(
                        "canal de clases '%s' falló (%s); se fusiona sin él",
                        recuperador.nombre,
                        exc,
                    )
            requeridas = clases_requeridas_desde_rankings(
                rankings, clases, k=self._entidades_rrf_k, tope=top_k
            )
        return candidatos_por_propiedad(
            requeridas, clases, nombres_enum=enums, tope=self._entidades_max_candidatos
        )

    @staticmethod
    def _canales_de(candidato: CandidatoClaseBom) -> set[str]:
        """Qué canales del paso 1 propusieron alguna clase de este candidato (`bm25#3` -> `bm25`)."""
        return {
            m.split("#", 1)[0].split(":", 1)[0]
            for e in candidato.evidencias
            for m in e.motivos
            if m
        }

    @staticmethod
    def _rescatar_propietarios(
        historia: HistoriaUsuario,
        catalogo: list[EntradaCatalogo],
        filtrado: list[EntradaCatalogo],
        por_clase: list[CandidatoClaseBom],
        *,
        min_score: float = 0.0,
        min_canales: int = 1,
    ) -> tuple[list[EntradaCatalogo], list[dict]]:
        """Añade al catálogo enrutado los propietarios que el routing por LLM dejó fuera.

        Añade **el Service Domain**, no su Business Domain entero: la atribución del BOM es por
        clase y por SD, así que abrir el dominio completo metería decenas de SD sin evidencia.
        Un candidato con poca señal (score < `min_score` Y menos de `min_canales` canales) no se
        rescata, pero tampoco desaparece: queda como incidencia `ROUTING_PROPIETARIO_NO_RESCATADO`.
        """
        if not por_clase:
            return filtrado, []
        presentes = {normalizar(e.service_domain) for e in filtrado}
        indice = {normalizar(e.service_domain): e for e in catalogo}
        incidencias: list[dict] = []
        anadidos: list[EntradaCatalogo] = []
        for candidato in por_clase:
            clave = normalizar(candidato.service_domain)
            if clave in presentes or clave not in indice:
                continue
            canales = MapearHistoriasServiceDomainsService._canales_de(candidato)
            clases = ", ".join(e.clase for e in candidato.evidencias[:3])
            if candidato.score < min_score and len(canales) < min_canales:
                incidencias.append({
                    "historia": historia.archivo,
                    "service_domain_propuesto": candidato.service_domain,
                    "decision": "NOT_ADDED",
                    "motivo": "ROUTING_PROPIETARIO_NO_RESCATADO",
                    "detalle": (
                        f"Define la(s) clase(s) {clases}, pero con score {candidato.score} "
                        f"(< {min_score}) y {len(canales)} canal(es) (< {min_canales}): poca "
                        f"señal para abrirle 2b; queda en candidatos_por_clase"
                    ),
                })
                continue
            anadidos.append(indice[clave])
            presentes.add(clave)
            incidencias.append({
                "historia": historia.archivo,
                "service_domain_propuesto": candidato.service_domain,
                "decision": "ADDED",
                "motivo": "ROUTING_PROPIETARIO_DE_CLASE_BOM",
                "detalle": (
                    f"El routing no incluyo su Business Domain, pero define en su BOM la(s) "
                    f"clase(s) {clases} que la historia necesita (score {candidato.score})"
                ),
            })
        return filtrado + anadidos, incidencias

    @staticmethod
    def _filtrar_por_dominios(
        historia: HistoriaUsuario,
        catalogo: list[EntradaCatalogo],
        enr: EnrutamientoDominiosLLM,
    ) -> tuple[list[EntradaCatalogo], list[dict]]:
        """Los SD de los Business Domains elegidos. Sin dominios resolubles -> catálogo completo."""
        reales = {normalizar(e.business_domain): e.business_domain for e in catalogo if e.business_domain}
        incidencias: list[dict] = []
        elegidos: set[str] = set()
        for nombre in enr.todos():
            clave = normalizar(nombre)
            if clave in reales:
                elegidos.add(clave)
            else:
                incidencias.append({
                    "historia": historia.archivo,
                    "service_domain_propuesto": "",
                    "decision": "IGNORED",
                    "motivo": "ROUTING_DOMINIO_NO_RESUELTO",
                    "detalle": f"'{nombre}' no es un Business Domain de la taxonomia BIAN R14",
                })
        if not elegidos:
            # Nunca dejar al nodo 2b sin catálogo: sin routing utilizable se degrada al
            # comportamiento de siempre (los 341 con el rol recortado), que es peor en coste pero
            # no pierde ningún candidato.
            incidencias.append({
                "historia": historia.archivo,
                "service_domain_propuesto": "",
                "decision": "IGNORED",
                "motivo": "ROUTING_SIN_DOMINIOS",
                "detalle": "El enrutamiento no resolvio ningun Business Domain; se usa el catalogo completo",
            })
            return list(catalogo), incidencias
        return [e for e in catalogo if normalizar(e.business_domain or "") in elegidos], incidencias

    def _h_candidatos(self, estado: EstadoHistoria) -> dict:
        # Con routing, el catálogo llega acotado y se manda SIN recortar (`texto_completo`). El
        # kwarg solo viaja en ese caso: un adaptador que no enrute nunca lo recibe.
        enrutado = estado.get("catalogo_enrutado")
        extra: dict = {}
        if enrutado:
            # Con routing el catálogo puede traer dominios abiertos A MEDIAS (un propietario
            # rescatado por el canal de propiedad de clases BOM), y la taxonomía debe decirlo:
            # "1 de 12 SD visibles", no "1 SD". Los totales salen del catálogo completo.
            totales: dict[str, int] = {}
            for e in estado["catalogo"]:
                if e.business_domain:
                    totales[e.business_domain] = totales.get(e.business_domain, 0) + 1
            extra = {"texto_completo": True, "totales_por_dominio": totales}
            # La evidencia del canal de propiedad (por qué un SD rescatado está en el catálogo)
            # solo viaja con el flag: es un prompt distinto (1.2.0) y hay que poder medirlo.
            if self._evidencia_bom_en_candidatos and estado.get("candidatos_por_clase"):
                extra["propietarios_bom"] = list(estado["candidatos_por_clase"])
        cand = self._analista.generar_candidatos(
            estado["historia"],
            estado["funcionalidad"],
            estado["intencion"],
            enrutado or estado["catalogo"],
            **extra,
        )
        return {"candidatos": cand, "huellas": _huellas(cand)}

    # ── 2b en fan-out: un grupo por Business Domain + el grupo de rescatados ────────────
    def _grupos_candidatos(self, estado: EstadoHistoria) -> list[dict]:
        """Parte `catalogo_enrutado` en grupos para `Send`: uno por Business Domain enrutado y uno
        con los propietarios que rescató el canal de clases BOM (solo ese ve `<propietarios_bom>`).
        Devuelve `[]` si no hay routing (sin `catalogo_enrutado` no hay nada que partir)."""
        enrutado = estado.get("catalogo_enrutado") or []
        if not enrutado:
            return []
        rescatados = {normalizar(n) for n in estado.get("sd_rescatados") or []}
        por_dominio: dict[str, list[EntradaCatalogo]] = {}
        grupo_rescatados: list[EntradaCatalogo] = []
        for e in enrutado:
            if normalizar(e.service_domain) in rescatados:
                grupo_rescatados.append(e)
            else:
                por_dominio.setdefault(e.business_domain or "(sin dominio)", []).append(e)
        grandes = {d: sds for d, sds in por_dominio.items() if len(sds) >= self._candidatos_grupo_min_sd}
        pequenos = {d: sds for d, sds in por_dominio.items() if len(sds) < self._candidatos_grupo_min_sd}
        grupos = [{"nombre": dominio, "catalogo": sds, "propietarios_bom": None}
                  for dominio, sds in grandes.items()]
        if pequenos:
            juntos = [e for sds in pequenos.values() for e in sds]
            nombre = " + ".join(pequenos)
            if grandes and len(juntos) < self._candidatos_grupo_min_sd:
                # Aún demasiado pequeño para ir solo: al grupo grande más pequeño, como vecino.
                menor = min(grupos, key=lambda g: len(g["catalogo"]))
                menor["catalogo"] = menor["catalogo"] + juntos
                menor["nombre"] = f"{menor['nombre']} + {nombre}"
            else:
                grupos.append({"nombre": nombre, "catalogo": juntos, "propietarios_bom": None})
        if grupo_rescatados:
            evidencia = None
            if self._evidencia_bom_en_candidatos:
                evidencia = [c for c in estado.get("candidatos_por_clase") or []
                             if normalizar(c.service_domain) in rescatados] or None
            grupos.append({"nombre": "propietarios de clases BOM (rescatados)",
                           "catalogo": grupo_rescatados, "propietarios_bom": evidencia})
        return grupos

    def _fan_out_grupos_candidatos(self, estado: EstadoHistoria):
        """Arista condicional tras 2a: `Send` por grupo si el fan-out está activo y hay routing;
        si no, el nodo 2b de una sola llamada de siempre."""
        grupos = self._grupos_candidatos(estado) if self._candidatos_por_dominio else []
        if not grupos:
            return "generar_candidatos"
        totales: dict[str, int] = {}
        for e in estado["catalogo"]:
            if e.business_domain:
                totales[e.business_domain] = totales.get(e.business_domain, 0) + 1
        ctx = {
            "historia": estado["historia"],
            "funcionalidad": estado["funcionalidad"],
            "intencion": estado["intencion"],
            "totales_por_dominio": totales,
        }
        logger.info(
            "HU '%s' -> 2b en %d grupo(s): %s",
            estado["historia"].archivo,
            len(grupos),
            ", ".join(f"{g['nombre']} ({len(g['catalogo'])} SD)" for g in grupos),
        )
        return [Send("generar_candidatos_grupo", {**ctx, "grupo": g}) for g in grupos]

    def _h_candidatos_grupo(self, estado: dict) -> dict:
        """UNA llamada de 2b sobre UN grupo (~15 SD, ~4k tokens). Misma pista, catálogo acotado."""
        grupo = estado["grupo"]
        extra: dict = {
            "texto_completo": True,
            "totales_por_dominio": estado["totales_por_dominio"],
            "grupo": f"{grupo['nombre']} ({len(grupo['catalogo'])} SD)",
        }
        if grupo.get("propietarios_bom"):
            extra["propietarios_bom"] = list(grupo["propietarios_bom"])
        cand = self._analista.generar_candidatos(
            estado["historia"], estado["funcionalidad"], estado["intencion"], grupo["catalogo"], **extra
        )
        return {
            "candidatos_parciales": [cand],
            "grupos_candidatos": [grupo["nombre"]],
            "huellas": _huellas(cand),
        }

    def _h_fusionar_candidatos(self, estado: EstadoHistoria) -> dict:
        """Reduce determinista del fan-out: unión de los parciales (ver `fusionar_candidatos`)."""
        parciales = estado.get("candidatos_parciales") or []
        nombres = estado.get("grupos_candidatos") or []
        # Los dos acumuladores crecen en el mismo orden (cada grupo escribe ambos en un solo
        # update); si por lo que sea no cuadran, se fusiona sin etiquetas antes que etiquetar mal.
        if len(nombres) != len(parciales):
            nombres = []
        return {"candidatos": fusionar_candidatos(parciales, nombres)}

    def _h_completitud(self, estado: EstadoHistoria) -> dict:
        indice = {normalizar(e.service_domain): e for e in estado["catalogo"]}
        disponibilidad: dict[str, str] = {}
        for c in estado["candidatos"].candidatos:
            entrada, resol = resolver_nombre_sd(c.service_domain, indice)
            if entrada is not None and resol == "MATCH":
                disponibilidad[entrada.service_domain] = self._catalogo_operaciones.evidencia_de(
                    entrada.service_domain
                ).estado
        rev = self._analista.revisar_completitud(
            estado["historia"],
            estado["intencion"],
            estado["candidatos"],
            estado["catalogo"],
            disponibilidad,
            # La evidencia de clases del BOM que produjo el nodo 2a: es con lo que se juzga un
            # conflicto de propiedad (quién DEFINE la clase, y si solo tipifica o guarda el valor).
            propietarios_bom=list(estado.get("candidatos_por_clase") or []),
        )
        # `unsupported_candidates` NO lo decide el LLM: es una consulta a la caché de evidencia que
        # el código ya hizo para armar el prompt. Pedírselo al modelo era hacerle copiar de vuelta
        # un dato que ya le habíamos dado, con la posibilidad de que se equivocara al copiarlo.
        sin_evidencia = sorted(
            sd for sd, est in disponibilidad.items() if est == "BIAN_EVIDENCE_UNAVAILABLE"
        )
        rev = rev.model_copy(update={"unsupported_candidates": sin_evidencia})
        return {"revision_completitud": rev, "huellas": _huellas(rev)}

    def _candidatos_retrieval_hibrido(
        self, estado: EstadoHistoria, ya_normalizados: set[str]
    ) -> tuple[list[tuple[str, str, list[str]]], dict[str, float]]:
        """RRF sobre los recuperadores configurados (léxico + vectorial, en memoria — ver
        `contenedor.py`), usando las señales de intención ya extraídas por el LLM como consulta.
        Nunca reemplaza un candidato LLM/completitud ya presente; solo rellena huecos de recall
        hasta `retrieval_max_inyectados`, respetando el orden de fusión (mejor primero). Devuelve
        también el score de fusión por SD (clave normalizada) para trazabilidad en el score final."""
        if not self._recuperadores:
            return [], {}
        intencion = estado.get("intencion")
        if intencion is None:
            return [], {}
        consulta = " ".join(
            [
                *intencion.business_actions,
                *intencion.business_objects,
                *intencion.capacidades_funcionales,
                *intencion.outcomes,
            ]
        ).strip()
        if not consulta:
            return [], {}
        rankings = [
            [c.service_domain for c in r.recuperar(consulta, self._retrieval_top_k)]
            for r in self._recuperadores
        ]
        fusionados: list[tuple[str, str, list[str]]] = []
        puntajes: dict[str, float] = {}
        vistos = set(ya_normalizados)
        pesos = self._rrf_pesos[: len(rankings)] if self._rrf_pesos else None
        for nombre, score in fusion_rrf(rankings, k=self._rrf_k, pesos=pesos):
            puntajes[normalizar(nombre)] = round(score, 6)
            if len(fusionados) >= self._retrieval_max_inyectados or normalizar(nombre) in vistos:
                continue
            vistos.add(normalizar(nombre))
            fusionados.append((nombre, "retrieval_hibrido", []))
        return fusionados, puntajes

    def _candidatos_graph_rag(
        self, estado: EstadoHistoria, propuestos: list[str], ya_normalizados: set[str]
    ) -> tuple[list[tuple[str, str, list[str]]], dict[str, float]]:
        """Expande por el grafo canónico BIAN a partir de los candidatos ya propuestos.

        Encuentra lo que ningún canal textual puede encontrar: un SD relacionado por el propio BOM
        de BIAN, no por parecerse a las palabras de la historia. Solo aristas verificadas y con
        fuente (ver `GrafoBianPort`), tope propio (`graph_rag_max_inyectados`) y nunca reemplaza un
        candidato del LLM, de completitud o del retrieval híbrido: solo rellena.
        """
        if self._grafo_bian is None or not self._graph_rag_max_inyectados or not propuestos:
            return [], {}
        expandidos = self._grafo_bian.expandir(propuestos, tope=self._graph_rag_max_inyectados * 2)
        salida: list[tuple[str, str, list[str]]] = []
        scores: dict[str, float] = {}
        for c in expandidos:
            clave = normalizar(c.service_domain)
            scores[clave] = c.score
            if len(salida) >= self._graph_rag_max_inyectados or clave in ya_normalizados:
                continue
            ya_normalizados.add(clave)
            # Los puentes viajan como "intent" para que la evidencia de POR QUÉ entró este
            # candidato llegue al prompt de evaluación, igual que el supporting_intent del LLM.
            salida.append((c.service_domain, "graph_rag", [f"BOM: {p}" for p in c.puentes[:3]]))
        if salida:
            logger.info(
                "Graph RAG inyectó %d candidato(s): %s",
                len(salida),
                ", ".join(n for n, _, _ in salida),
            )
        return salida, scores

    def _reordenar_candidatos(
        self, estado: EstadoHistoria, resueltos: list[tuple[EntradaCatalogo, str, list[str]]]
    ) -> tuple[list[tuple[EntradaCatalogo, str, list[str]]], dict[str, float]]:
        """Reordena los candidatos resueltos por relevancia antes del recorte por `max_candidatos_hu`.

        Aquí es donde un reranker paga: lo que quede fuera del tope NO se evalúa, y cada candidato
        evaluado cuesta una llamada LLM con ~16k tokens de evidencia. Sin reranker el corte es por
        orden de llegada (LLM, completitud, retrieval, grafo), que no dice nada sobre relevancia.

        El reranker solo ORDENA: no elimina candidatos ni decide ownership. Lo que cae fuera del
        tope sigue registrándose como incidencia `TRUNCATED_BY_MAX_CANDIDATOS_HU`, igual que antes.
        """
        if self._reranker is None or len(resueltos) <= 1:
            return resueltos, {}
        intencion = estado.get("intencion")
        if intencion is None:
            return resueltos, {}
        consulta = " ".join(
            [
                *intencion.business_actions,
                *intencion.business_objects,
                *intencion.capacidades_funcionales,
                *intencion.outcomes,
            ]
        ).strip()
        if not consulta:
            return resueltos, {}

        por_clave = {normalizar(e.service_domain): (e, o, i) for e, o, i in resueltos}
        # PROSA, no el texto del índice: un cross-encoder lee el par (consulta, documento), así
        # que la jerarquía y la clasificación que el índice mete para cubrir vocabulario aquí solo
        # son ruido. Medido sobre `hu_real` (`evaluate.py --barrido-texto`): con el texto del
        # índice el reranker da MRR 0.300 y deja 4 `hard_negatives` delante; con `prosa`, 0.417 y
        # 2. Sigue por debajo de no reordenar (0.573 / 1) -- por eso `reranker_habilitado` es
        # `false`--, pero si alguien lo enciende no debe recibir además el peor texto posible.
        documentos = [(clave, e.texto_prosa("prosa")) for clave, (e, _, _) in por_clave.items()]
        try:
            ranking = self._reranker.reordenar(consulta, documentos, tope=len(documentos))
        except Exception as exc:  # un reranker caído no puede tumbar la corrida
            logger.warning("Reranker falló (%s); se mantiene el orden de llegada", exc)
            return resueltos, {}

        scores = {clave: round(float(score), 6) for clave, score in ranking}
        ordenados = [por_clave[clave] for clave, _ in ranking if clave in por_clave]
        # Cualquiera que el reranker no devolviera conserva su posición relativa al final.
        vistos = {clave for clave, _ in ranking}
        ordenados += [v for k, v in por_clave.items() if k not in vistos]
        return ordenados, scores

    def _h_preparar(self, estado: EstadoHistoria) -> dict:
        catalogo = estado["catalogo"]
        indice = {normalizar(e.service_domain): e for e in catalogo}
        comp = estado.get("revision_completitud") or RevisionCompletitudLLM()

        propuestos: list[tuple[str, str, list[str]]] = [
            (c.service_domain, "llm", list(c.supporting_intent))
            for c in estado["candidatos"].candidatos
        ] + [(n, "completitud", []) for n in comp.missing_candidates]
        # Todo el retrieval opcional comparte un presupuesto de tiempo: si se agota, se sigue con
        # lo que ya se tenga en vez de dejar la historia colgada de un proveedor lento.
        reloj = _Presupuesto(self._presupuesto_segundos_hu, estado["historia"].archivo)
        inyectados, retrieval_scores = (
            self._candidatos_retrieval_hibrido(estado, {normalizar(n) for n, _, _ in propuestos})
            if reloj.queda("retrieval híbrido")
            else ([], {})
        )
        propuestos += inyectados
        expandidos, graph_scores = (
            self._candidatos_graph_rag(
                estado, [n for n, _, _ in propuestos], {normalizar(n) for n, _, _ in propuestos}
            )
            if reloj.queda("graph rag")
            else ([], {})
        )
        propuestos += expandidos

        incidencias: list[dict] = []
        resueltos: dict[str, tuple[EntradaCatalogo, str, list[str]]] = {}
        for nombre, origen, intent in propuestos:
            entrada, resol = resolver_nombre_sd(nombre, indice)
            if entrada is None or resol != "MATCH":
                incidencias.append(
                    {
                        "historia": estado["historia"].archivo,
                        "service_domain_propuesto": nombre,
                        "resolucion": resol,
                        "decision": "REJECTED",
                        "motivo": "NAME_UNRESOLVED",
                        "detalle": "Nombre no resoluble contra el catalogo BIAN R14",
                    }
                )
                continue
            resueltos.setdefault(
                normalizar(entrada.service_domain), (entrada, origen, list(intent))
            )

        ordenados, rerank_scores = (
            self._reordenar_candidatos(estado, list(resueltos.values()))
            if reloj.queda("reranker")
            else (list(resueltos.values()), {})
        )
        seleccion = ordenados[: self._max_candidatos_hu]
        truncados = ordenados[self._max_candidatos_hu :]
        for entrada, origen, _intent in truncados:
            # nunca desaparece en silencio: queda visible como incidencia no bloqueante (Fase 0)
            incidencias.append(
                {
                    "historia": estado["historia"].archivo,
                    "service_domain_propuesto": entrada.service_domain,
                    "resolucion": "MATCH",
                    "decision": "NOT_EVALUATED",
                    "motivo": "TRUNCATED_BY_MAX_CANDIDATOS_HU",
                    "detalle": f"origen={origen}; recortado por max_candidatos_hu={self._max_candidatos_hu}",
                }
            )
        nombres = [e.service_domain for e, _, _ in seleccion]
        evidencias = self._catalogo_operaciones.asegurar(
            nombres, actualizar=self._actualizar_cache_bian
        )

        a_evaluar: list[PaqueteEvidenciaCandidato] = []
        for entrada, origen, intent in seleccion:
            ops = self._catalogo_operaciones.operaciones_de(entrada.service_domain) or []
            esq = self._catalogo_operaciones.esquemas_de(entrada.service_domain)
            det = self._catalogo_operaciones.schemas_detalle_de(entrada.service_domain)
            bom = (
                self._catalogo_bom.modelo_de(entrada.service_domain) if self._catalogo_bom else None
            )
            a_evaluar.append(
                _paquete_de(
                    entrada,
                    evidencias.get(entrada.service_domain, EvidenciaBian()),
                    ops,
                    esq,
                    origen=origen,
                    supporting_intent=intent,
                    schemas_detalle=det,
                    bom_modelo=bom,
                )
            )
        a_evaluar.sort(key=lambda p: p.service_domain.lower())

        # ── CRAG: una vuelta correctiva si el lote no sostiene ninguna decisión ──
        paquetes_crag, incidencia_crag = self._vuelta_correctiva(estado, a_evaluar, indice, reloj)
        if paquetes_crag:
            a_evaluar = sorted(a_evaluar + paquetes_crag, key=lambda p: p.service_domain.lower())
        if incidencia_crag:
            incidencias.append(incidencia_crag)

        ya = {normalizar(p.service_domain) for p in a_evaluar}
        omitidos = (
            detectar_omitidos(estado["intencion"], catalogo, ya, top_n=self._top_n_omitidos)
            if self._top_n_omitidos
            else []
        )
        return {
            "a_evaluar": a_evaluar,
            "omitidos": omitidos,
            "incidencias": incidencias,
            "retrieval_scores": retrieval_scores,
            "graph_scores": graph_scores,
            "rerank_scores": rerank_scores,
        }

    @staticmethod
    def _lote_debil(paquetes: list[PaqueteEvidenciaCandidato]) -> str:
        """¿El lote de evidencia puede sostener ALGUNA decisión? Devuelve el motivo, o "".

        Débil = no hay ni un candidato con evidencia utilizable: sin candidatos, o ninguno con
        operaciones oficiales ni modelo BOM. Con un lote así, `evaluar_candidato` gastaría una
        llamada LLM por candidato para terminar en `NO_OFFICIAL_BIAN_EVIDENCE` — es el único caso
        en que volver a recuperar tiene sentido, y por eso la condición es estricta: reintentar
        "por si acaso" duplicaría el coste de todas las historias para arreglar unas pocas.
        """
        if not paquetes:
            return "sin candidatos resueltos"
        if not any(p.operations or p.bom_modelo for p in paquetes):
            return "ningún candidato con operaciones oficiales ni modelo BOM"
        return ""

    def _vuelta_correctiva(self, estado: EstadoHistoria, a_evaluar, indice, reloj):
        """Reescribe la consulta con lo que la propia historia declaró que NO sabe y recupera UNA
        vez más. Nunca reemplaza candidatos: solo añade, con `origen="crag"`.

        La reescritura usa `gaps` / `unresolved_questions` / `capacidades_funcionales` de
        `extraer_intencion` —lo que quedó sin resolver— en vez de repetir la misma consulta que ya
        falló, que es lo que distingue una vuelta correctiva de un reintento ciego.
        """
        motivo = self._lote_debil(a_evaluar) if self._crag_reintento else ""
        if not motivo or not self._recuperadores or not reloj.queda("vuelta correctiva CRAG"):
            return [], None
        intencion = estado.get("intencion")
        if intencion is None:
            return [], None
        consulta = " ".join(
            [
                estado["historia"].titulo,
                *intencion.gaps,
                *intencion.unresolved_questions,
                *intencion.capacidades_funcionales,
            ]
        ).strip()
        if not consulta:
            return [], None

        ya = {normalizar(p.service_domain) for p in a_evaluar}
        rankings = [
            [c.service_domain for c in r.recuperar(consulta, self._retrieval_top_k)]
            for r in self._recuperadores
        ]
        pesos = self._rrf_pesos[: len(rankings)] if self._rrf_pesos else None
        nuevos: list[PaqueteEvidenciaCandidato] = []
        for nombre, _score in fusion_rrf(rankings, k=self._rrf_k, pesos=pesos):
            if len(nuevos) >= self._retrieval_max_inyectados:
                break
            entrada, resol = resolver_nombre_sd(nombre, indice)
            if entrada is None or resol != "MATCH" or normalizar(entrada.service_domain) in ya:
                continue
            ya.add(normalizar(entrada.service_domain))
            evidencia = self._catalogo_operaciones.asegurar(
                [entrada.service_domain], actualizar=False
            ).get(entrada.service_domain, EvidenciaBian())
            ops = self._catalogo_operaciones.operaciones_de(entrada.service_domain) or []
            if not ops:
                continue  # si sigue sin evidencia, reinyectarlo solo gastaría otra llamada LLM
            nuevos.append(
                _paquete_de(
                    entrada,
                    evidencia,
                    ops,
                    self._catalogo_operaciones.esquemas_de(entrada.service_domain),
                    origen="crag",
                    supporting_intent=[],
                    schemas_detalle=self._catalogo_operaciones.schemas_detalle_de(
                        entrada.service_domain
                    ),
                    bom_modelo=self._catalogo_bom.modelo_de(entrada.service_domain)
                    if self._catalogo_bom
                    else None,
                )
            )
        logger.info(
            "HU '%s': vuelta correctiva CRAG (%s) -> %d candidato(s) con evidencia",
            estado["historia"].titulo,
            motivo,
            len(nuevos),
        )
        return nuevos, {
            "historia": estado["historia"].archivo,
            "service_domain_propuesto": ", ".join(p.service_domain for p in nuevos) or "(ninguno)",
            "resolucion": "MATCH",
            "decision": "NOT_EVALUATED" if not nuevos else "RETRIED",
            "motivo": "CRAG_RETRY_APPLIED",
            "detalle": f"lote débil ({motivo}); consulta reescrita desde gaps/unresolved_questions",
        }

    def _fan_out_candidatos(self, estado: EstadoHistoria):
        paquetes = estado.get("a_evaluar") or []
        if not paquetes:
            return "clasificar"
        ctx = {
            "historia": estado["historia"],
            "funcionalidad": estado["funcionalidad"],
            "intencion": estado["intencion"],
        }
        return [Send("evaluar_candidato", {**ctx, "paquete": p}) for p in paquetes]

    def _h_evaluar(self, estado: dict) -> dict:
        ev = self._analista.evaluar_candidato(
            estado["historia"], estado["funcionalidad"], estado["intencion"], estado["paquete"]
        )
        return {"evaluaciones": [ev], "huellas": _huellas(ev)}

    def _reclasificar(
        self, estado: EstadoHistoria, propuestos_por_sd: dict[str, ServiceDomainPropuestoLLM]
    ):
        paquetes = {p.service_domain: p for p in estado.get("a_evaluar", [])}
        return clasificar_service_domains(
            list(propuestos_por_sd.values()),
            estado["catalogo"],
            self._umbrales,
            operaciones_por_sd={n: p.operations for n, p in paquetes.items()},
            evidencias_por_sd={n: p.evidencia for n, p in paquetes.items()},
            esquemas_por_sd={n: p.schemas for n, p in paquetes.items()},
            origen_por_sd={n: p.origen for n, p in paquetes.items()},
        )

    def _h_clasificar(self, estado: EstadoHistoria) -> dict:
        evals = sorted(estado.get("evaluaciones", []), key=lambda e: e.service_domain.lower())
        propuestos_por_sd = {
            normalizar(e.service_domain): ServiceDomainPropuestoLLM.desde_evaluacion(
                e, service_domain_canonico=e.service_domain
            )
            for e in evals
        }
        grupos = self._reclasificar(estado, propuestos_por_sd)
        return {"grupos": grupos, "propuestos_por_sd": propuestos_por_sd}

    def _h_adversarial(self, estado: EstadoHistoria) -> dict:
        rev = self._analista.revisar_adversarial(
            estado["historia"], estado["intencion"], estado["grupos"]
        )
        return {"revision_adversarial": rev, "huellas": _huellas(rev)}

    def _h_aplicar_adversarial(self, estado: EstadoHistoria) -> dict:
        revision = estado.get("revision_adversarial") or RevisionAdversarialLLM()
        propuestos_por_sd = estado.get("propuestos_por_sd") or {}
        # Ambas leen `desglose_score`/`accion_objeto` de la clasificación YA hecha
        # (`estado["grupos"]`), no de `propuestos_por_sd` (que no trae el score calculado).
        promovidos = determinar_promociones(estado["grupos"], revision)
        # Promoción que NO depende de que el revisor lo haya visto: cierra la asimetría por la que
        # un CONSUMED_DEPENDENCY mal clasificado no tenía ninguna salida determinista. Solo devuelve
        # el rol a OWNED_CONTRACT -- abre la puerta al paso de operaciones; el contrato lo decide
        # después la evidencia (`finalizar_por_operacion_solida` / `degradar_sin_operacion_anclada`).
        por_accion = determinar_promociones_por_accion(estado["grupos"], estado["intencion"])
        promovidos = frozenset(promovidos | por_accion)
        degradados = determinar_degradaciones(estado["grupos"], estado["intencion"], revision)

        grupos = estado["grupos"]
        if promovidos or degradados:
            # Re-clasifica con ambos ya reescritos: el score y el tope por rol deben recalcularse
            # juntos (`clasificar_service_domains`), nunca parchear solo la etiqueta de decisión
            # sobre el resultado viejo. Una sola pasada cubre las dos direcciones.
            if promovidos:
                propuestos_por_sd = propuestos_promovidos(propuestos_por_sd, promovidos)
                for clave in por_accion:
                    propuesto = propuestos_por_sd.get(clave)
                    if propuesto is not None:
                        propuesto.reason_codes = list(
                            dict.fromkeys([*propuesto.reason_codes, PROMOTED_BY_ACTION_REASON_CODE])
                        )
            if degradados:
                propuestos_por_sd = propuestos_degradados(propuestos_por_sd, degradados)
            grupos = self._reclasificar(estado, propuestos_por_sd)
            if promovidos:
                logger.info(
                    "HU '%s': %d SD promovido(s) CONSUMED_DEPENDENCY -> OWNED_CONTRACT "
                    "(adversarial y/o acción declarada por la propia historia): %s",
                    estado["historia"].titulo,
                    len(promovidos),
                    ", ".join(sorted(promovidos)),
                )
            if degradados:
                logger.info(
                    "HU '%s': %d SD degradado(s) OWNED_CONTRACT -> CONSUMED_DEPENDENCY: la acción "
                    "citada no coincide con ninguna acción propia de la historia: %s",
                    estado["historia"].titulo,
                    len(degradados),
                    ", ".join(sorted(degradados)),
                )

        grupos, bloqueos = aplicar_hallazgos_adversariales(
            grupos, revision, promovidos=promovidos, degradados=degradados
        )

        # Fase 0 (observabilidad): un hallazgo que NO califica para reclasificación automática
        # (ni promoción ni degradación) sigue siendo un conflicto de ownership real -- no debe
        # quedar solo en un log; ver `_metricas` en `_resultado_mapeo` (`ownership_conflict_rate`).
        sin_resolver = [
            h
            for h in revision.hallazgos
            if h.tipo in ("ACCION_DIRECTA_COMO_DEPENDENCIA", "DEPENDENCIA_PROMOVIDA_A_CONTRATO")
            and h.service_domain
            and normalizar(h.service_domain) not in promovidos
            and normalizar(h.service_domain) not in degradados
        ]
        # El grafo canónico contrasta el conflicto contra el catálogo: ¿hay un objeto ESPECÍFICO
        # que estos candidatos compartan de verdad, o solo andamiaje BIAN que medio catálogo toca?
        # No reclasifica nada -- separa conflicto accionable de ruido anotado.
        veredictos = self._veredictos_de_grafo(estado, sin_resolver)
        # Por que NO califico cada promocion que el revisor si pidio. Sin esto la incidencia solo
        # decia "hay un conflicto" y diagnosticar exigia repetir la corrida con LLM real.
        no_promocion = motivos_no_promocion(estado["grupos"], revision)
        incidencias = []
        for h in sin_resolver:
            motivo, detalle_grafo = veredictos.get(
                normalizar(h.service_domain or ""), ("OWNERSHIP_CONFLICT_UNRESOLVED", "")
            )
            base = (
                h.detalle
                or f"{h.tipo} sin evidencia determinista suficiente para "
                "reclasificar automáticamente; revisar manualmente."
            )
            por_que = no_promocion.get(normalizar(h.service_domain or ""), "")
            incidencias.append(
                {
                    "historia": estado["historia"].archivo,
                    "service_domain_propuesto": h.service_domain,
                    "resolucion": "MATCH",
                    "decision": "UNRESOLVED",
                    "motivo": motivo,
                    "detalle": " ".join(
                        p for p in (base, detalle_grafo, f"No se promovió: {por_que}." if por_que else "") if p
                    ).strip(),
                }
            )
        return {
            "grupos": grupos,
            "bloqueos_hu": bloqueos,
            "propuestos_por_sd": propuestos_por_sd,
            "incidencias": incidencias,
        }

    def _veredictos_de_grafo(self, estado: EstadoHistoria, hallazgos: list) -> dict:
        """Veredicto del grafo sobre cada conflicto sin resolver (vacío si la señal está apagada)."""
        if not self._senales_grafo_adversarial or self._grafo_bian is None or not hallazgos:
            return {}
        candidatos = [p.service_domain for p in estado.get("a_evaluar", [])]
        try:
            compartidos = self._grafo_bian.objetos_compartidos(candidatos)
        except Exception as exc:  # pragma: no cover - el grafo nunca debe tumbar la corrida
            logger.warning("señales de grafo no disponibles: %s", exc)
            return {}
        # El objeto en disputa de cada candidato sale de la clasificación que YA se hizo
        # (`accion_objeto`), no del texto libre del hallazgo: es el mismo dato que usan las
        # degradaciones, así que la confirmación se apoya en algo que el pipeline ya sostenía.
        accion_por_sd = {
            a.service_domain: a.accion_objeto
            for a in (
                *estado["grupos"].candidatos_directos,
                *estado["grupos"].candidatos_tentativos,
                *estado["grupos"].candidatos_descartados,
            )
        }
        en_disputa = {
            h.service_domain: accion_por_sd.get(h.service_domain) or h.detalle
            for h in hallazgos
            if h.service_domain
        }
        return confirmar_conflictos_por_grafo(en_disputa, compartidos)

    def _h_operaciones(self, estado: EstadoHistoria) -> dict:
        elegibles = candidatos_operacion_elegibles(estado["grupos"])
        huellas, incidencias, con_operaciones = self._asignar_operaciones(
            estado["historia"],
            estado["funcionalidad"],
            estado["intencion"],
            elegibles,
            estado.get("a_evaluar", []),
        )
        # Recién ahora hay operaciones ancladas: un OWNED_CONTRACT con evidencia BIAN verificada y
        # una operación oficial concreta y verificada pesa más que el score léxico agregado (ver
        # `finalizar_por_operacion_solida`) -- no depende de haber pasado por
        # `determinar_promociones` (ese cubre el caso "el LLM lo clasificó mal como dependencia";
        # este cubre "el LLM ya lo clasificó bien pero con rúbricas de acción/objeto bajas").
        grupos = finalizar_por_operacion_solida(estado["grupos"])
        # ...y el movimiento simétrico: un SELECTED que no ancló NINGUNA de las operaciones
        # oficiales de su SD no es un contrato accionable. Solo aplica si el SD tenía operaciones
        # disponibles: si el catálogo no trae ninguna, o el paso está apagado, no hay nada que
        # reprochar.
        grupos = degradar_sin_operacion_anclada(grupos, con_operaciones)
        return {
            "grupos": grupos,
            "huellas": huellas,
            "incidencias": incidencias,
        }

    def _h_ensamblar(self, estado: EstadoHistoria) -> dict:
        historia: HistoriaUsuario = estado["historia"]
        intencion = estado["intencion"]
        grupos = estado["grupos"]
        comp = estado.get("revision_completitud") or RevisionCompletitudLLM()
        adv = estado.get("revision_adversarial") or RevisionAdversarialLLM()
        bloqueos = list(estado.get("bloqueos_hu", []))
        omitidos = estado.get("omitidos", [])

        # Scores de recuperación (aditivos: trazan POR QUÉ llegó el candidato, no deciden nada).
        extras = {
            "retrieval_score": estado.get("retrieval_scores") or {},
            "graph_score": estado.get("graph_scores") or {},
            "rerank_score": estado.get("rerank_scores") or {},
        }
        if any(extras.values()):
            for a in (
                *grupos.candidatos_directos,
                *grupos.candidatos_tentativos,
                *grupos.candidatos_descartados,
            ):
                clave = normalizar(a.service_domain)
                update = {c: m[clave] for c, m in extras.items() if m.get(clave) is not None}
                if update:
                    a.desglose_score = a.desglose_score.model_copy(update=update)

        n_ops = sum(len(a.operaciones_bian) for a in grupos.candidatos_directos)
        logger.info(
            "HU '%s' -> candidatos=%d directos=%d tentativos=%d descartados=%d | operaciones=%d | omitidos=%d",
            historia.titulo,
            len(estado.get("a_evaluar", [])),
            len(grupos.candidatos_directos),
            len(grupos.candidatos_tentativos),
            len(grupos.candidatos_descartados),
            n_ops,
            len(omitidos),
        )
        resultado = HistoriaConServiceDomains(
            archivo=historia.archivo,
            titulo=historia.titulo,
            razonamiento=intencion.resumen_funcional.strip(),
            capacidades_funcionales=intencion.capacidades_funcionales,
            business_actions=intencion.business_actions,
            business_objects=intencion.business_objects,
            outcomes=intencion.outcomes,
            external_dependencies=intencion.external_dependencies,
            traceability_ids=intencion.traceability_ids,
            assumptions=list(
                dict.fromkeys([*intencion.assumptions, *estado["candidatos"].assumptions])
            ),
            gaps=list(
                dict.fromkeys([*intencion.gaps, *estado["candidatos"].gaps, *comp.coverage_gaps])
            ),
            unresolved_questions=list(intencion.unresolved_questions),
            blocking_codes=list(
                dict.fromkeys([*bloqueos, *comp.blocking_codes, *adv.blocking_codes])
            ),
            intencion=intencion,
            enrutamiento=estado.get("enrutamiento") or EnrutamientoDominiosLLM(),
            service_domains_visibles=len(
                estado.get("catalogo_enrutado") or estado.get("catalogo") or []
            ),
            candidatos_por_clase=list(estado.get("candidatos_por_clase") or []),
            revision_completitud=comp,
            revision_adversarial=adv,
            total_directos=len(grupos.candidatos_directos),
            total_tentativos=len(grupos.candidatos_tentativos),
            total_descartados=len(grupos.candidatos_descartados),
            service_domains=grupos,
            service_domains_omitidos=omitidos,
        )
        # Una historia que no produce NINGÚN contrato es el peor resultado posible, y hasta ahora
        # era el que mejor pintaba en el JSON: sin SD elegible no hay nada que anclar, así que
        # `operation_coverage_rate` y `operation_grounding_rate` salían en 1.0 por vacío. Es el
        # mismo error de forma que se corrigió un nivel más abajo (una tasa que da verde porque no
        # se hizo nada), y se cierra igual: con una incidencia que lo nombra.
        seleccionados = [
            a
            for a in (*grupos.candidatos_directos, *grupos.candidatos_tentativos)
            if a.decision_contractual == "SELECTED"
        ]
        incidencias = []
        if not seleccionados:
            mejor = max(
                (*grupos.candidatos_directos, *grupos.candidatos_tentativos),
                key=lambda a: a.confianza,
                default=None,
            )
            incidencias.append(
                {
                    "historia": historia.archivo,
                    "service_domain_propuesto": mejor.service_domain if mejor else "(ninguno)",
                    "resolucion": "MATCH" if mejor else "NOT_FOUND",
                    "decision": "UNRESOLVED",
                    "motivo": "HISTORIA_SIN_CONTRATO",
                    "detalle": (
                        f"ningún Service Domain quedó SELECTED entre los "
                        f"{len(estado.get('a_evaluar', []))} candidatos evaluados"
                        + (
                            f"; el mejor fue {mejor.service_domain} "
                            f"({mejor.rol_contractual}, {mejor.motivo_decision}, "
                            f"confianza {mejor.confianza:.4f})"
                            if mejor
                            else ""
                        )
                        + "."
                        # Diagnóstico sin coste: el paso de operaciones NO corre para un no-owned,
                        # así que nadie mira si ese candidato tenía operaciones oficiales. Decirlo
                        # aquí distingue "no había nada que anclar" de "había 17 y no se miraron",
                        # que es la diferencia entre un resultado correcto y una clasificación mala.
                        + (
                            f" Aviso: {mejor.service_domain} SÍ tiene "
                            f"{_operaciones_disponibles(mejor, estado)} operaciones oficiales en el "
                            "catálogo, que nadie llegó a evaluar porque su rol no es OWNED_CONTRACT."
                            if mejor and _operaciones_disponibles(mejor, estado)
                            else ""
                        )
                    ),
                }
            )
        return {"resultado": resultado, "incidencias": incidencias}

    # ── paso 6: operaciones oficiales (+ BQ personalizados) para los SD elegibles ─
    def _asignar_operaciones(
        self,
        historia: HistoriaUsuario,
        funcionalidad,
        intencion,
        elegibles: list[ServiceDomainAsignado],
        a_evaluar: list[PaqueteEvidenciaCandidato],
    ) -> tuple[list[MetadatosPrompt], list[dict], set[str]]:
        """`elegibles` = `candidatos_operacion_elegibles(grupos)`: OWNED_CONTRACT, directo o
        tentativo (no solo "directo") — ver `clasificacion_historias.candidatos_operacion_elegibles`.

        Devuelve también el conjunto de Service Domains que SÍ tenían operaciones oficiales en el
        catálogo: sin ese dato no se puede distinguir "no ancló porque no hay operaciones" de "no
        ancló aunque las había", que es lo único que justifica degradar (ver
        `degradar_sin_operacion_anclada`)."""
        if not self._mapear_operaciones or not elegibles:
            return [], [], set()
        operaciones_por_sd = {}
        for sd in elegibles:
            ops = self._catalogo_operaciones.operaciones_de(sd.service_domain)
            if ops:
                operaciones_por_sd[sd.service_domain] = ops
        if not operaciones_por_sd:
            return [], [], set()

        nombres_elegibles = {normalizar(sd.service_domain) for sd in elegibles}
        paquetes_por_sd = {
            p.service_domain: p
            for p in a_evaluar
            if normalizar(p.service_domain) in nombres_elegibles
        }

        # UNA LLAMADA POR SERVICE DOMAIN, no una con todos. El nodo mas fragil del pipeline es
        # este -- tiene que citar una operacion concreta entre decenas, y su fallo es el unico que
        # deja la historia sin contrato-. Pedirle N Service Domains a la vez multiplica el espacio
        # de error y mezcla los catalogos; aislado, cada llamada ve un solo catalogo y una sola
        # decision. Los elegibles son 1-2 en la practica (`candidatos_operacion_elegibles`), asi
        # que el coste extra es de 0-1 llamadas por HU, y la cache de nodos las absorbe al repetir.
        parciales = [
            self._mapeador_operaciones.mapear(
                historia,
                funcionalidad,
                intencion,
                {sd: operaciones},
                {sd: paquetes_por_sd[sd]} if sd in paquetes_por_sd else {},
            )
            for sd, operaciones in operaciones_por_sd.items()
        ]
        mapeo = _fusionar_mapeos(parciales)
        huellas = [m.metadatos for m in parciales if m.metadatos is not None]
        por_sd_norm = {sd.service_domain.casefold(): sd for sd in elegibles}
        # Indexado por nombre NORMALIZADO (no el string crudo): una diferencia de capitalización o
        # acentos entre lo que devuelve el LLM y el nombre canónico del SD no debe hacer que la
        # operación "no se encuentre" y caiga a un fallback que la busca en OTRO Service Domain
        # (aislamiento estricto: un operationId de un SD nunca se ancla a otro SD).
        indice_ops = {normalizar(nombre): ops for nombre, ops in operaciones_por_sd.items()}
        incidencias: list[dict] = []
        # Checklist de datos que la historia pidió (`intencion.business_objects`, nodo 1) y que
        # este paso debe cubrir con una operación o declarar sin cubrir. Ver
        # `cobertura_datos_requeridos`.
        datos_requeridos = [d.strip() for d in intencion.business_objects if d and d.strip()]
        cubiertos_historia: list[str] = []
        # 1ª pasada: resuelve cada propuesta contra el catálogo real y agrupa por (SD, operationId
        # real) -- el LLM puede citar la MISMA operación más de una vez, una por cada
        # escenario/bq_seed que cubre (`fusionar_propuestas_de_operacion`), nunca se ancla una
        # entrada duplicada por eso.
        por_grupo: dict[tuple[str, str], tuple[ServiceDomainAsignado, OperacionBian, list]] = {}
        orden_grupos: list[tuple[str, str]] = []
        for op in mapeo.operaciones:
            asignado = por_sd_norm.get(op.service_domain.casefold())
            operaciones_sd = indice_ops.get(normalizar(op.service_domain), [])
            fuente = resolver_operation_id(op.operation_id, operaciones_sd)
            if asignado is None or fuente is None:
                # Modelos más débiles del failover a veces no devuelven el operationId exacto que
                # el prompt pide (p.ej. "POST /Correspondence/{id}/Outbound/Initiate" en vez de
                # "InitiateOutbound"); `resolver_operation_id` ya intentó reconstruirlo desde el
                # path/method reales. Si ni así resuelve, no se descarta en silencio (mismo
                # principio que `OPERATION_EVIDENCE_UNVERIFIED`): queda visible para revisión.
                incidencias.append(
                    {
                        "historia": historia.archivo,
                        "service_domain_propuesto": op.service_domain,
                        "resolucion": "NOT_FOUND",
                        "decision": "NOT_EVALUATED",
                        "motivo": "OPERATION_ID_UNRESOLVED",
                        "detalle": f"operationId propuesto '{op.operation_id}' no resuelve contra el "
                        "catálogo real de ese Service Domain (ni exacto ni por path/method).",
                    }
                )
                continue
            clave = (normalizar(asignado.service_domain), fuente.operation_id)
            if clave not in por_grupo:
                orden_grupos.append(clave)
                por_grupo[clave] = (asignado, fuente, [])
            por_grupo[clave][2].append(op)

        # 2ª pasada: fusiona cada grupo en una sola propuesta y ancla UNA operación por grupo.
        for clave in orden_grupos:
            asignado, fuente, propuestas_crudas = por_grupo[clave]
            op = fusionar_propuestas_de_operacion(propuestas_crudas)
            reason_codes = list(op.reason_codes)
            if any(fuente.operation_id != p.operation_id for p in propuestas_crudas):
                reason_codes.append("OPERATION_ID_RECONSTRUCTED_FROM_PATH")
                logger.info(
                    "HU '%s': operationId propuesto no calzaba exacto en al menos una cita; "
                    "reconstruido a '%s' desde method+path reales del catálogo",
                    historia.titulo,
                    fuente.operation_id,
                )
            paquete = paquetes_por_sd.get(asignado.service_domain)
            if paquete is not None and not operacion_evidencia_verificable(
                fuente, op.evidence_refs, paquete.schemas_detalle
            ):
                # No se descarta (evitaría falsos negativos por una cita mal formateada): se deja
                # visible en la salida para revisión, en vez de fallar en silencio como antes.
                reason_codes.append("OPERATION_EVIDENCE_UNVERIFIED")
                logger.warning(
                    "HU '%s': operación %s/%s sin evidence_refs verificable contra el response_schema "
                    "'%s'; anclada igual, marcada OPERATION_EVIDENCE_UNVERIFIED",
                    historia.titulo,
                    asignado.service_domain,
                    fuente.operation_id,
                    fuente.response_schema,
                )
            # Las citas al checklist se anclan igual que el operationId: contra la lista REAL que
            # se le mostró (`resolver_dato_requerido`), nunca como texto libre. Una cita que no
            # resuelve no cubre nada y el dato sigue contando como no evaluado.
            datos_cubiertos = list(
                dict.fromkeys(
                    d
                    for d in (
                        resolver_dato_requerido(c, datos_requeridos) for c in op.datos_cubiertos
                    )
                    if d is not None
                )
            )
            cubiertos_historia.extend(datos_cubiertos)
            asignado.operaciones_bian.append(
                OperacionBianAplicada(
                    operation_id=fuente.operation_id,
                    method=fuente.method,
                    path=fuente.path,
                    tipo=fuente.tipo,
                    grupo=fuente.grupo,
                    escenarios_hu=op.escenarios_hu,
                    justificacion=op.justificacion,
                    action_term=op.action_term,
                    business_object=op.business_object,
                    bq_seed=op.bq_seed,
                    traceability=op.traceability,
                    evidence_refs=op.evidence_refs,
                    datos_cubiertos=datos_cubiertos,
                    reason_codes=list(dict.fromkeys(reason_codes)),
                )
            )
        for sd in elegibles:
            sd.operaciones_bian.sort(key=lambda o: (o.tipo, o.grupo, o.operation_id))
            if sd.operaciones_bian:
                verificadas = sum(
                    1
                    for o in sd.operaciones_bian
                    if "OPERATION_EVIDENCE_UNVERIFIED" not in o.reason_codes
                )
                sd.desglose_score = sd.desglose_score.model_copy(
                    update={
                        "operation_support_score": round(verificadas / len(sd.operaciones_bian), 4)
                    }
                )

        self._anclar_bq_personalizados(
            mapeo.bq_personalizados, por_sd_norm, paquetes_por_sd, historia.titulo
        )

        # El blindaje del adaptador tiró citas que no resuelven contra el catalogo de SU Service
        # Domain. Es el MISMO motivo que ya se registra arriba cuando la cita llega hasta aqui;
        # lo unico que cambiaba era el sitio donde se descartaba, y alli solo habia un log.
        incidencias += [
            {
                "historia": historia.archivo,
                "service_domain_propuesto": cita.split("/", 1)[0],
                "resolucion": "NOT_FOUND",
                "decision": "NOT_EVALUATED",
                "motivo": "OPERATION_ID_UNRESOLVED",
                "detalle": f"cita '{cita}' descartada por el blindaje anti-alucinacion: no "
                "resuelve contra el catalogo real de ese Service Domain.",
            }
            for cita in mapeo.citas_descartadas
        ]

        # Un Service Domain ELEGIBLE (OWNED_CONTRACT, directo o tentativo) que acaba con CERO
        # operaciones ancladas era invisible: el bucle de anclaje simplemente no se ejecutaba y
        # esta funcion devolvia sin incidencias. Es justo el sintoma de que respondio un modelo
        # incapaz de citar un operationId -- el paso mas fragil del pipeline-, y sin esto la
        # corrida termina en verde con `finalizar_por_operacion_solida` sin poder dispararse.
        incidencias += [
            {
                "historia": historia.archivo,
                "service_domain_propuesto": sd.service_domain,
                "resolucion": "MATCH",
                "decision": "UNRESOLVED",
                "motivo": "OPERATION_MAPPING_EMPTY",
                "detalle": (
                    f"{sd.service_domain} es elegible ({sd.rol_contractual}, {sd.grupo}) y tiene "
                    f"{len(operaciones_por_sd.get(sd.service_domain, []))} operaciones oficiales "
                    "en el catalogo, pero el mapeo no ancló ninguna."
                ),
            }
            for sd in elegibles
            if not sd.operaciones_bian and operaciones_por_sd.get(sd.service_domain)
        ]

        # Los `gaps`/`blocking_codes` del nodo se fusionaban (`_fusionar_mapeos`) y se TIRABAN:
        # `BIAN-SCOPE-008` ("una semilla del use case quedó sin cubrir") es justo la señal de un
        # contrato incompleto, y no llegaba a la salida ni a las métricas. Ahora es una incidencia
        # como cualquier otra: informativa, no reclasifica nada.
        incidencias += [
            {
                "historia": historia.archivo,
                "service_domain_propuesto": ", ".join(operaciones_por_sd),
                "resolucion": "MATCH",
                "decision": "NOT_EVALUATED",
                "motivo": "OPERATION_GAP_DECLARED",
                "detalle": detalle,
            }
            for detalle in [*mapeo.gaps, *(f"blocking_code {c}" for c in mapeo.blocking_codes)]
            if detalle and detalle.strip()
        ]

        # Cobertura de los DATOS que la historia pidió. La HU los declara (`business_objects`) y
        # el nodo tiene que cerrarlos uno por uno: cubrirlos con una operación o decir que ninguna
        # los expone. El silencio era invisible -- caso real 2026-09-15: "Nombre del tutor" salió
        # en la intención, el mapeo ancló solo `RetrieveReference` y la corrida terminó con
        # `operation_coverage_rate` 1.0 aunque el BQ `Associations` del MISMO Service Domain era
        # el que expone la relación entre dos Party.
        _, declarados, no_evaluados = cobertura_datos_requeridos(
            datos_requeridos,
            cubiertos_historia,
            [c for c in mapeo.datos_no_cubiertos],
        )
        incidencias += [
            {
                "historia": historia.archivo,
                "service_domain_propuesto": ", ".join(operaciones_por_sd),
                "resolucion": "MATCH",
                "decision": "NOT_EVALUATED",
                "motivo": motivo,
                "detalle": detalle,
            }
            for motivo, datos, detalle_fn in (
                (
                    "DATO_REQUERIDO_SIN_OPERACION",
                    declarados,
                    lambda d: (
                        f"el dato requerido '{d}' quedó declarado sin operación: ninguna "
                        "operación oficial de los Service Domains elegibles lo expone."
                    ),
                ),
                (
                    "DATO_REQUERIDO_NO_EVALUADO",
                    no_evaluados,
                    lambda d: (
                        f"el dato requerido '{d}' no fue ni cubierto ni declarado por el paso de "
                        "operaciones; revisar si algún CR/BQ de los Service Domains elegibles lo "
                        "expone."
                    ),
                ),
            )
            for d in datos
            for detalle in [detalle_fn(d)]
        ]
        return huellas, incidencias, set(operaciones_por_sd)

    @staticmethod
    def _anclar_bq_personalizados(
        propuestos,
        por_sd_norm: dict[str, ServiceDomainAsignado],
        paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato],
        historia_titulo: str,
    ) -> None:
        """Determinista: una operación personalizada SOLO se ancla si (a) `grupo_existente` es
        realmente un CR/BQ YA existente del Service Domain -nunca crea un grupo/tag nuevo-, (b) el
        operationId resultante no colisiona con uno oficial ya publicado, (c) el campo no está ya
        cubierto por una operación oficial (incluyendo sus campos de respuesta reales, no solo
        texto libre), y (d) la clase/atributo BOM citados existen de verdad. Nunca se "arregla"
        una cita floja."""
        for p in propuestos:
            asignado = por_sd_norm.get(p.service_domain.casefold())
            paquete = paquetes_por_sd.get(p.service_domain) or next(
                (
                    v
                    for k, v in paquetes_por_sd.items()
                    if k.casefold() == p.service_domain.casefold()
                ),
                None,
            )
            if asignado is None or paquete is None:
                continue
            grupos_existentes = {
                normalizar(g) for g in (*paquete.control_records, *paquete.behavior_qualifiers)
            }
            if normalizar(p.grupo_existente) not in grupos_existentes:
                logger.warning(
                    "HU '%s': operación personalizada cita un grupo '%s' que NO es un CR/BQ existente "
                    "de %s (no se crean tags nuevos); descartada",
                    historia_titulo,
                    p.grupo_existente,
                    p.service_domain,
                )
                continue
            ya_cubierto = normalizar(p.campo_no_cubierto) and any(
                normalizar(p.campo_no_cubierto)
                in normalizar(f"{o.operation_id} {o.summary} {o.description}")
                or normalizar(p.campo_no_cubierto)
                in campos_alcanzables(o.response_schema, paquete.schemas_detalle)
                for o in paquete.operations
            )
            if ya_cubierto:
                logger.info(
                    "HU '%s': campo '%s' ya cubierto por una operación oficial de %s; operación "
                    "personalizada descartada",
                    historia_titulo,
                    p.campo_no_cubierto,
                    p.service_domain,
                )
                continue
            if not _bom_respalda(paquete, p.clase_bom, p.atributo_bom):
                logger.warning(
                    "HU '%s': operación personalizada en grupo '%s' para %s cita clase/atributo BOM "
                    "no verificable ('%s'.'%s'); descartada",
                    historia_titulo,
                    p.grupo_existente,
                    p.service_domain,
                    p.clase_bom,
                    p.atributo_bom,
                )
                continue

            verbo = p.verbo if p.verbo in _VERBOS_BIAN else "Update"
            grupo_pascal = _pascal(p.grupo_existente)
            operation_id = f"{verbo}{grupo_pascal}"
            if operation_id_en_uso(operation_id, paquete.operations):
                logger.info(
                    "HU '%s': operación personalizada '%s' ya existe como operación oficial de %s; descartada",
                    historia_titulo,
                    operation_id,
                    p.service_domain,
                )
                continue
            path_propuesto = derivar_path_grupo(p.grupo_existente, verbo, paquete.operations)
            if path_propuesto is None:
                continue
            asignado.bq_personalizados_propuestos.append(
                BqPersonalizadoAplicado(
                    service_domain=asignado.service_domain,
                    grupo_existente=grupo_pascal,
                    operation_id=operation_id,
                    verbo=verbo,
                    path_propuesto=path_propuesto,
                    parent_control_record=(
                        paquete.control_records[0] if paquete.control_records else ""
                    ),
                    campo_no_cubierto=p.campo_no_cubierto.strip(),
                    clase_bom=p.clase_bom.strip(),
                    atributo_bom=p.atributo_bom.strip(),
                    escenarios_hu=[s.strip() for s in p.escenarios_hu if s and s.strip()],
                    justificacion=p.justificacion.strip(),
                    reason_codes=list(dict.fromkeys(p.reason_codes)),
                )
            )
        for asignado in por_sd_norm.values():
            asignado.bq_personalizados_propuestos.sort(key=lambda b: b.operation_id)

    # ══ consolidación ══════════════════════════════════════════════════════
    def _procesadas_ordenadas(self, estado: EstadoMapeo) -> list[HistoriaConServiceDomains]:
        historias = list(estado.get("historias", []))
        orden = {h.archivo: i for i, h in enumerate(historias)}
        return sorted(estado.get("procesadas", []), key=lambda p: orden.get(p.archivo, len(orden)))

    @staticmethod
    def _resumen_hu(h: HistoriaConServiceDomains) -> dict:
        g = h.service_domains
        return {
            "archivo": h.archivo,
            "titulo": h.titulo,
            "service_domains": [
                {
                    "service_domain": a.service_domain,
                    "grupo": a.grupo,
                    "rol_contractual": a.rol_contractual,
                    "decision_contractual": a.decision_contractual,
                    "ownership_traceability": a.ownership_traceability,
                    "dependency_traceability": a.dependency_traceability,
                }
                for a in (
                    *g.candidatos_directos,
                    *g.candidatos_tentativos,
                    *g.candidatos_descartados,
                )
            ],
        }

    def _resultado_mapeo(self, estado: EstadoMapeo) -> ResultadoMapeoHistorias:
        procesadas = self._procesadas_ordenadas(estado)
        funcionalidad = estado.get("funcionalidad")
        reconciliacion = estado.get("reconciliacion") or ReconciliacionFuncionalidadLLM()
        incidencias = sorted(
            estado.get("incidencias", []),
            key=lambda d: (d.get("historia", ""), d.get("service_domain_propuesto", "")),
        )
        parametros = {
            **self._parametros_base,
            "run_id": uuid.uuid4().hex,
            # Con durabilidad, ESTE es el identificador con el que se reanuda:
            # `--reanudar <thread_id>`. Sin durabilidad va vacío a propósito.
            "thread_id": self._thread_id,
            "durabilidad": self._durabilidad,
            "umbral_directo": self._umbrales.directo,
            "umbral_tentativo": self._umbrales.tentativo,
            "concurrencia": self._concurrencia,
            "concurrencia_candidatos": self._concurrencia_candidatos,
            "max_candidatos_hu": self._max_candidatos_hu,
            "paso2_operaciones": self._mapear_operaciones,
            "actualizar_cache_bian": self._actualizar_cache_bian,
            "top_n_omitidos": self._top_n_omitidos,
            "routing_jerarquico_activo": self._routing_jerarquico,
            "evidencia_bom_en_candidatos": self._evidencia_bom_en_candidatos,
            "candidatos_por_dominio_activo": self._candidatos_por_dominio and self._routing_jerarquico,
            "entidades_bom_activo": self._catalogo_entidades is not None
            and self._entidades_max_candidatos > 0,
            "entidades_canales": (
                (["diccionario"] if self._entidades_canal_diccionario or not self._recuperadores_clases else [])
                + [r.nombre for r in self._recuperadores_clases]
            )
            if self._catalogo_entidades is not None
            else [],
            "retrieval_hibrido_activo": bool(self._recuperadores),
            "retrieval_top_k": self._retrieval_top_k,
            "retrieval_max_inyectados": self._retrieval_max_inyectados,
        }
        huellas = sorted(
            estado.get("huellas_prompts", []),
            key=lambda m: (
                m.historia,
                m.nodo,
                m.prompt_id,
                m.evidence_snapshot_id,
                m.prompt_sha256,
            ),
        )
        return ResultadoMapeoHistorias(
            funcionalidad_macro=funcionalidad.funcionalidad_macro if funcionalidad else "",
            detalle=funcionalidad.detalle if funcionalidad else "",
            total_historias=estado.get("total_historias", len(procesadas)),
            parametros=parametros,
            historias=procesadas,
            service_domains_consolidados=self._consolidar(procesadas, reconciliacion),
            service_domains_omitidos=self._consolidar_omitidos(procesadas),
            reconciliacion=reconciliacion,
            huellas_prompts=huellas,
            incidencias=incidencias,
            metricas=self._metricas(procesadas, incidencias),
        )

    @staticmethod
    def _metricas(procesadas: list[HistoriaConServiceDomains], incidencias: list[dict]) -> dict:
        """Fase 0: nada debe perderse sin poder explicar en qué etapa se perdió. Tasas simples,
        derivables solo de lo que el propio resultado ya registra (sin golden set: eso es
        Recall@K de Fase 3, que necesita un corpus de consultas doradas — ver implementacion_pendiente.md)."""
        todos = [
            a
            for h in procesadas
            for a in (
                *h.service_domains.candidatos_directos,
                *h.service_domains.candidatos_tentativos,
                *h.service_domains.candidatos_descartados,
            )
        ]
        total_evaluados = len(todos)
        truncados = sum(
            1 for i in incidencias if i.get("motivo") == "TRUNCATED_BY_MAX_CANDIDATOS_HU"
        )
        base_drop = total_evaluados + truncados
        candidate_drop_rate = round(truncados / base_drop, 4) if base_drop else 0.0

        promovidos = sum(1 for a in todos if PROMOTED_REASON_CODE in a.reason_codes)
        degradados_count = sum(1 for a in todos if DEMOTED_REASON_CODE in a.reason_codes)
        # Un conflicto sin resolver puede llevar tres motivos: el de siempre (sin señal de grafo),
        # y los dos veredictos que el grafo emite cuando la señal está encendida.
        motivos_conflicto = {
            "OWNERSHIP_CONFLICT_UNRESOLVED",
            CONFLICTO_CONFIRMADO_POR_GRAFO,
            CONFLICTO_SIN_RESPALDO_DE_GRAFO,
        }
        conflictos = [i for i in incidencias if i.get("motivo") in motivos_conflicto]
        sin_resolver = len(conflictos)
        sin_respaldo = sum(
            1 for i in conflictos if i.get("motivo") == CONFLICTO_SIN_RESPALDO_DE_GRAFO
        )
        confirmados = sum(
            1 for i in conflictos if i.get("motivo") == CONFLICTO_CONFIRMADO_POR_GRAFO
        )
        base_ownership = promovidos + degradados_count + sin_resolver
        ownership_conflict_rate = round(sin_resolver / base_ownership, 4) if base_ownership else 0.0
        # Misma tasa descontando los conflictos que el catálogo BIAN NO respalda (solo objetos
        # genéricos compartidos). Con la señal de grafo apagada coincide con la de arriba.
        accionables = sin_resolver - sin_respaldo
        base_accionable = promovidos + degradados_count + accionables
        ownership_conflict_rate_respaldado = (
            round(accionables / base_accionable, 4) if base_accionable else 0.0
        )
        finalizados_por_operacion = sum(
            1 for a in todos if OPERATION_FINALIZED_REASON_CODE in a.reason_codes
        )

        # Elegibles = los que DEBIAN recibir operacion (`candidatos_operacion_elegibles`:
        # OWNED_CONTRACT directo o tentativo), no todos los directos/tentativos: si no, un SD que
        # nunca fue candidato a operacion contaria como cobertura perdida.
        elegibles = [a for h in procesadas for a in candidatos_operacion_elegibles(h.service_domains)]
        ops = [o for a in elegibles for o in a.operaciones_bian]
        verificadas = sum(1 for o in ops if "OPERATION_EVIDENCE_UNVERIFIED" not in o.reason_codes)
        # CORRECCION: antes esto devolvia 1.0 cuando NO habia ninguna operacion anclada, o sea
        # marcaba verde justo en el peor caso -medido en una corrida real: grounding 1.0 con
        # `operaciones_ancladas: 0`-. Sin operaciones no hay nada que fundamentar: si habia SD
        # elegibles, la tasa es 0.0; solo vale 1.0 cuando no habia nada que anclar.
        if ops:
            operation_grounding_rate = round(verificadas / len(ops), 4)
        elif elegibles:
            operation_grounding_rate = 0.0
        else:
            # Sin SD elegibles no hay nada que fundamentar: la tasa NO APLICA. Antes valía 1.0, y
            # una corrida que no selecciono ni un contrato salia con las dos tasas en verde
            # (medido: corrida real con 0 SELECTED, cobertura 1.0 y grounding 1.0). `null` obliga
            # a mirar `historias_sin_contrato` en vez de leer un 1.0 como exito.
            operation_grounding_rate = None
        # Lo que el grounding NO puede ver: cuantos de los SD que debian recibir operacion la
        # recibieron. Es la tasa que distingue "ancle poco y bien" de "no ancle nada".
        con_operacion = sum(1 for a in elegibles if a.operaciones_bian)
        operation_coverage_rate = round(con_operacion / len(elegibles), 4) if elegibles else None
        operation_mapping_empty = sum(
            1 for i in incidencias if i.get("motivo") == "OPERATION_MAPPING_EMPTY"
        )
        historias_sin_contrato = sum(
            1 for i in incidencias if i.get("motivo") == "HISTORIA_SIN_CONTRATO"
        )
        operation_id_no_resuelto = sum(
            1 for i in incidencias if i.get("motivo") == "OPERATION_ID_UNRESOLVED"
        )
        operation_gaps_declarados = sum(
            1 for i in incidencias if i.get("motivo") == "OPERATION_GAP_DECLARED"
        )
        datos_sin_operacion = sum(
            1 for i in incidencias if i.get("motivo") == "DATO_REQUERIDO_SIN_OPERACION"
        )
        datos_no_evaluados = sum(
            1 for i in incidencias if i.get("motivo") == "DATO_REQUERIDO_NO_EVALUADO"
        )
        # Cuántos de los datos que las historias pidieron acabaron con una operación que los
        # cubre. Solo cuentan las HU que tuvieron SD elegibles: sin elegibles el paso de
        # operaciones ni corre, y castigar ahí duplicaría lo que ya dice `historias_sin_contrato`.
        # `None` = no aplica, misma convención que las dos tasas de operaciones.
        datos_evaluables = sum(
            len([d for d in h.business_objects if d and d.strip()])
            for h in procesadas
            if candidatos_operacion_elegibles(h.service_domains)
        )
        data_coverage_rate = (
            round((datos_evaluables - datos_sin_operacion - datos_no_evaluados) / datos_evaluables, 4)
            if datos_evaluables
            else None
        )

        # ── routing jerárquico (nodo 2a) ──────────────────────────────────────
        # Lo que hay que poder vigilar de un router NO es lo que acierta, es lo que descarta: si
        # deja fuera el dominio bueno, el Service Domain no aparece en ningún sitio y la HU se
        # queda corta sin decir por qué. Por eso van los tres crudos -- dominios elegidos, SD
        # visibles y cuántas veces hubo que caer al catálogo completo -- y no una tasa de éxito,
        # que sin corpus dorado no se puede calcular.
        con_ruta = [h for h in procesadas if h.enrutamiento.todos()]
        routing_dominios_por_hu = (
            round(sum(len(h.enrutamiento.todos()) for h in con_ruta) / len(con_ruta), 2)
            if con_ruta
            else None
        )
        visibles = [h.service_domains_visibles for h in procesadas if h.service_domains_visibles]
        routing_sd_visibles_por_hu = (
            round(sum(visibles) / len(visibles), 1) if visibles else None
        )

        # ¿Cuántos de los propietarios que el canal de clases BOM AÑADIÓ al catálogo llegaron a
        # ser propuestos por 2b? Es la medida de si el rescate sirve de algo o solo cuesta tokens
        # (medido 2026-09-20 sin evidencia en el prompt: 1 de 5). `None` = no hubo rescates.
        rescatados_por_hu: dict[str, set[str]] = {}
        for i in incidencias:
            if i.get("motivo") == "ROUTING_PROPIETARIO_DE_CLASE_BOM":
                rescatados_por_hu.setdefault(i.get("historia", ""), set()).add(
                    normalizar(i.get("service_domain_propuesto", ""))
                )
        bom_rescatados = sum(len(v) for v in rescatados_por_hu.values())
        bom_rescatados_propuestos = 0
        for h in procesadas:
            propuestos = {
                normalizar(a.service_domain)
                for a in (
                    *h.service_domains.candidatos_directos,
                    *h.service_domains.candidatos_tentativos,
                    *h.service_domains.candidatos_descartados,
                )
                if getattr(a, "origen_candidato", "llm") == "llm"
            }
            bom_rescatados_propuestos += len(rescatados_por_hu.get(h.archivo, set()) & propuestos)

        # ¿El nodo 3 aporta algo? `missing_candidates` es lo ÚNICO suyo que cambia el flujo (se
        # evalúa como un candidato más, con origen "completitud"). Medido en el E2E 1 antes de
        # mejorarlo: 0 aportados en una corrida con 9 candidatos del nodo 2b. Estas tres cifras
        # dicen si la llamada se paga sola: cuántos añadió, cuántos sobrevivieron a la evaluación
        # y cuántos acabaron siendo contrato.
        completitud_aportados = sum(
            1 for a in todos if getattr(a, "origen_candidato", "llm") == "completitud"
        )
        completitud_seleccionados = sum(
            1
            for h in procesadas
            for a in h.service_domains.candidatos_directos
            if getattr(a, "origen_candidato", "llm") == "completitud"
        )
        completitud_conflictos = sum(
            len(h.revision_completitud.ownership_conflicts)
            + len(h.revision_completitud.duplicated_responsibilities)
            for h in procesadas
            if h.revision_completitud is not None
        )

        return {
            "completitud_candidatos_aportados": completitud_aportados,
            "completitud_candidatos_seleccionados": completitud_seleccionados,
            "completitud_conflictos_detectados": completitud_conflictos,
            "routing_dominios_por_hu": routing_dominios_por_hu,
            "routing_sd_visibles_por_hu": routing_sd_visibles_por_hu,
            "bom_rescatados": bom_rescatados,
            "bom_rescatados_propuestos": bom_rescatados_propuestos,
            "bom_rescatados_propuestos_rate": (
                round(bom_rescatados_propuestos / bom_rescatados, 4) if bom_rescatados else None
            ),
            "routing_dominios_no_resueltos": sum(
                1 for i in incidencias if i.get("motivo") == "ROUTING_DOMINIO_NO_RESUELTO"
            ),
            "routing_fallback_catalogo_completo": sum(
                1 for i in incidencias if i.get("motivo") == "ROUTING_SIN_DOMINIOS"
            ),
            "candidate_drop_rate": candidate_drop_rate,
            "candidatos_truncados": truncados,
            "candidatos_evaluados": total_evaluados,
            "ownership_conflict_rate": ownership_conflict_rate,
            "ownership_conflict_rate_respaldado": ownership_conflict_rate_respaldado,
            "ownership_promovidos": promovidos,
            "ownership_degradados": degradados_count,
            "ownership_sin_resolver": sin_resolver,
            "ownership_conflictos_confirmados_por_grafo": confirmados,
            "ownership_conflictos_sin_respaldo_de_grafo": sin_respaldo,
            "operation_grounding_rate": operation_grounding_rate,
            "operation_coverage_rate": operation_coverage_rate,
            "operaciones_ancladas": len(ops),
            "service_domains_elegibles": len(elegibles),
            "operation_mapping_empty": operation_mapping_empty,
            "historias_sin_contrato": historias_sin_contrato,
            "operation_id_no_resuelto": operation_id_no_resuelto,
            "operation_gaps_declarados": operation_gaps_declarados,
            "data_coverage_rate": data_coverage_rate,
            "datos_requeridos_evaluables": datos_evaluables,
            "datos_requeridos_sin_operacion": datos_sin_operacion,
            "datos_requeridos_no_evaluados": datos_no_evaluados,
            "finalizados_por_operacion_solida": finalizados_por_operacion,
        }

    @staticmethod
    def _consolidar(
        historias: list[HistoriaConServiceDomains], reconciliacion: ReconciliacionFuncionalidadLLM
    ) -> list[DecisionServiceDomainConsolidada]:
        """Reconcilia el mismo SD entre HU (determinista). Si alguna HU lo posee y quedó SELECTED
        -> SELECTED; si no, UNRESOLVED si alguna quedó sin resolver; si no, REJECTED (con su motivo).
        La reconciliación LLM solo aporta rol de funcionalidad, historias de apoyo/contra y reason_codes."""
        consejo = {normalizar(r.service_domain): r for r in reconciliacion.service_domains}
        por_sd: dict[str, list[tuple[HistoriaConServiceDomains, ServiceDomainAsignado]]] = {}
        for h in historias:
            g = h.service_domains
            for a in (*g.candidatos_directos, *g.candidatos_tentativos, *g.candidatos_descartados):
                por_sd.setdefault(a.service_domain, []).append((h, a))

        salida: list[DecisionServiceDomainConsolidada] = []
        for sd, usos in por_sd.items():
            asignados = [a for _, a in usos]
            mejor = max(asignados, key=lambda a: a.confianza)
            seleccionado = next(
                (
                    a
                    for a in asignados
                    if a.rol_contractual == "OWNED_CONTRACT"
                    and a.decision_contractual == "SELECTED"
                ),
                None,
            )
            if seleccionado is not None:
                base, decision = seleccionado, "SELECTED"
            elif any(a.decision_contractual == "UNRESOLVED" for a in asignados):
                base = next(a for a in asignados if a.decision_contractual == "UNRESOLVED")
                decision = "UNRESOLVED"
            else:
                base, decision = mejor, "REJECTED"

            r = consejo.get(normalizar(sd))
            salida.append(
                DecisionServiceDomainConsolidada(
                    service_domain=sd,
                    decision=decision,  # type: ignore[arg-type]
                    motivo=base.motivo_decision,
                    contract_role=base.rol_contractual,
                    functionality_role=(r.functionality_role if r else ""),
                    grupo=base.grupo,
                    score=base.confianza,
                    historias=sorted({h.archivo for h, _ in usos}),
                    supporting_stories=sorted(r.supporting_stories) if r else [],
                    contradicting_stories=sorted(r.contradicting_stories) if r else [],
                    traceability=sorted({t for a in asignados for t in a.escenarios_hu}),
                    ownership_traceability=sorted(
                        {t for a in asignados for t in a.ownership_traceability}
                    ),
                    dependency_traceability=sorted(
                        {t for a in asignados for t in a.dependency_traceability}
                    ),
                    selected_operations=sorted(
                        {o.operation_id for a in asignados for o in a.operaciones_bian}
                    ),
                    custom_bq_candidates=sorted(
                        {
                            b.operation_id: b
                            for a in asignados
                            for b in a.bq_personalizados_propuestos
                        }.values(),
                        key=lambda b: b.operation_id,
                    ),
                    reason_codes=sorted(
                        {c for a in asignados for c in a.reason_codes}
                        | (set(r.reason_codes) if r else set())
                    ),
                    blocking_codes=sorted({c for a in asignados for c in a.blocking_codes}),
                    evidence=base.evidencia_bian,
                    rationale=base.justificacion,
                )
            )
        prioridad = {"SELECTED": 0, "UNRESOLVED": 1, "REJECTED": 2}
        return sorted(salida, key=lambda x: (prioridad[x.decision], -x.score, x.service_domain))

    @staticmethod
    def _consolidar_omitidos(
        historias: list[HistoriaConServiceDomains],
    ) -> list[ServiceDomainOmitido]:
        mejor: dict[str, ServiceDomainOmitido] = {}
        for h in historias:
            for o in h.service_domains_omitidos:
                previo = mejor.get(o.service_domain)
                if previo is None or o.score_lexico > previo.score_lexico:
                    mejor[o.service_domain] = o
        return sorted(mejor.values(), key=lambda o: (-o.score_lexico, o.service_domain))

    # ══ caché de nodos ════════════════════════════════════════════════════
    def _clave(self, nodo: str, *piezas) -> str:
        """Clave de caché de un nodo: su firma de LLM/catálogo + sus entradas semánticas."""
        return f"{nodo}:{_sha_corto(self._firma_llm, *(_canonico(x) for x in piezas))}"

    def _checkpointer(self):
        """Checkpointer solo si se pidió durabilidad: `durability` sin checkpointer no hace nada
        (LangGraph avisa y luego falla).

        El checkpointer lo construye el contenedor y se inyecta, igual que la caché de nodos: la
        persistencia es infraestructura y esta capa no decide dónde vive un archivo. Sin uno
        inyectado se usa `InMemorySaver`, que da estado inspeccionable y reanudable DENTRO del
        proceso -- suficiente para `interrupt`, inútil si el proceso muere.
        """
        if self._durabilidad == "exit":
            return None
        if self._checkpointer_inyectado is not None:
            return self._checkpointer_inyectado
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()

    def _politica(self, nodo: str, clave):
        """`CachePolicy` del nodo, o `None` si la caché está apagada (comportamiento de siempre)."""
        if self._cache_nodos is None or CachePolicy is None:
            return None
        return CachePolicy(key_func=clave, ttl=self._cache_nodos_ttl)

    # ══ ensamblado de grafos ══════════════════════════════════════════════
    def _compilar_subgrafo(self):
        g = StateGraph(EstadoHistoria)
        # Solo se cachean los nodos LLM: son los caros y los no deterministas. Los deterministas
        # (`preparar_candidatos`, `clasificar`, `aplicar_adversarial`, `ensamblar`) cuestan
        # milisegundos y recalcularlos siempre evita que una entrada de caché vieja fije una
        # decisión que el código ya cambió.
        g.add_node(
            "extraer_intencion",
            self._h_intencion,
            retry_policy=_RETRY,
            cache_policy=self._politica(
                "intencion",
                lambda e: self._clave("intencion", e["historia"], e["funcionalidad"]),
            ),
        )
        if self._routing_jerarquico:
            g.add_node(
                "enrutar_dominios",
                self._h_enrutar,
                retry_policy=_RETRY,
                cache_policy=self._politica(
                    "enrutamiento",
                    lambda e: self._clave(
                        "enrutamiento",
                        e["historia"],
                        e["funcionalidad"],
                        e.get("intencion"),
                        # La configuración del canal de propiedad de clases BOM decide qué
                        # propietarios rescata este nodo; sin ella, cambiar los canales o el
                        # tope con la caché caliente devolvería la salida anterior.
                        self._firma_entidades,
                    ),
                ),
            )
        g.add_node(
            "generar_candidatos",
            self._h_candidatos,
            retry_policy=_RETRY,
            cache_policy=self._politica(
                "candidatos",
                # El enrutamiento entra en la clave porque decide QUÉ catálogo ve este nodo: sin
                # él, un routing distinto reutilizaría candidatos calculados sobre otros dominios.
                lambda e: self._clave(
                    "candidatos",
                    e["historia"],
                    e["funcionalidad"],
                    e.get("intencion"),
                    e.get("enrutamiento"),
                    # ...y también los propietarios que el canal de propiedad de clases BOM
                    # AÑADIÓ al catálogo enrutado: el enrutamiento LLM ya no describe solo lo
                    # que ve 2b. Se usa la lista de nombres, que es lo que cambia el prompt.
                    [x.service_domain for x in (e.get("catalogo_enrutado") or [])],
                    # ...y la evidencia del canal si 2b la ve (prompt 1.2.0): otro bloque, otra
                    # llamada. Con el flag apagado es una constante y no cambia nada.
                    e.get("candidatos_por_clase") if self._evidencia_bom_en_candidatos else None,
                ),
            ),
        )
        g.add_node(
            "revisar_completitud",
            self._h_completitud,
            retry_policy=_RETRY,
            cache_policy=self._politica(
                "completitud",
                lambda e: self._clave(
                    "completitud",
                    e["historia"],
                    e.get("intencion"),
                    e.get("candidatos"),
                    # La evidencia del canal de clases BOM entra en el prompt desde 1.1.0.
                    e.get("candidatos_por_clase"),
                ),
            ),
        )
        g.add_node("preparar_candidatos", self._h_preparar)
        g.add_node(
            "evaluar_candidato",
            self._h_evaluar,
            retry_policy=_RETRY,
            cache_policy=self._politica(
                "evaluacion",
                # El paquete de evidencia entero entra en la clave: incluye el SHA-256 de la
                # evidencia BIAN del SD, así que refrescar la caché BIAN invalida su evaluación.
                lambda e: self._clave(
                    "evaluacion",
                    e["historia"],
                    e["funcionalidad"],
                    e.get("intencion"),
                    e["paquete"],
                ),
            ),
        )
        g.add_node("clasificar", self._h_clasificar)
        g.add_node(
            "revisar_adversarial",
            self._h_adversarial,
            retry_policy=_RETRY,
            cache_policy=self._politica(
                "adversarial",
                lambda e: self._clave(
                    "adversarial", e["historia"], e.get("intencion"), e.get("grupos")
                ),
            ),
        )
        g.add_node("aplicar_adversarial", self._h_aplicar_adversarial)
        g.add_node(
            "seleccionar_operaciones",
            self._h_operaciones,
            retry_policy=_RETRY,
            cache_policy=self._politica(
                "operaciones",
                lambda e: self._clave(
                    "operaciones",
                    e["historia"],
                    e["funcionalidad"],
                    # La intención entra en la clave porque entra en el prompt: sus
                    # `business_objects` son el checklist de datos requeridos que este nodo debe
                    # cubrir o declarar. Sin esto, una intención distinta reutilizaría un mapeo
                    # calculado contra otra lista de datos.
                    e.get("intencion"),
                    e.get("grupos"),
                    e.get("a_evaluar"),
                ),
            ),
        )
        g.add_node("ensamblar", self._h_ensamblar)

        g.add_edge(START, "extraer_intencion")
        if self._routing_jerarquico:
            g.add_edge("extraer_intencion", "enrutar_dominios")
            if self._candidatos_por_dominio:
                # 2b en fan-out: `Send` por grupo -> fusión determinista -> nodo 3. La rama de
                # una sola llamada sigue registrada como red (sin grupos, p. ej. routing vacío).
                g.add_node(
                    "generar_candidatos_grupo",
                    self._h_candidatos_grupo,
                    retry_policy=_RETRY,
                    cache_policy=self._politica(
                        "candidatos_grupo",
                        lambda e: self._clave(
                            "candidatos_grupo",
                            e["historia"],
                            e["funcionalidad"],
                            e.get("intencion"),
                            [x.service_domain for x in e["grupo"]["catalogo"]],
                            [c.service_domain for c in (e["grupo"].get("propietarios_bom") or [])],
                        ),
                    ),
                )
                g.add_node("fusionar_candidatos", self._h_fusionar_candidatos)
                g.add_conditional_edges(
                    "enrutar_dominios",
                    self._fan_out_grupos_candidatos,
                    ["generar_candidatos_grupo", "generar_candidatos"],
                )
                g.add_edge("generar_candidatos_grupo", "fusionar_candidatos")
                g.add_edge("fusionar_candidatos", "revisar_completitud")
            else:
                g.add_edge("enrutar_dominios", "generar_candidatos")
        else:
            g.add_edge("extraer_intencion", "generar_candidatos")
        g.add_edge("generar_candidatos", "revisar_completitud")
        g.add_edge("revisar_completitud", "preparar_candidatos")
        g.add_conditional_edges(
            "preparar_candidatos", self._fan_out_candidatos, ["evaluar_candidato", "clasificar"]
        )
        g.add_edge("evaluar_candidato", "clasificar")
        g.add_edge("clasificar", "revisar_adversarial")
        g.add_edge("revisar_adversarial", "aplicar_adversarial")
        g.add_edge("aplicar_adversarial", "seleccionar_operaciones")
        g.add_edge("seleccionar_operaciones", "ensamblar")
        g.add_edge("ensamblar", END)
        return g.compile(cache=self._cache_nodos)

    def _compilar(self):
        g = StateGraph(EstadoMapeo)
        g.add_node("cargar", self._nodo_cargar)
        g.add_node("procesar_historia", self._nodo_procesar)
        g.add_node(
            "reconciliar",
            self._nodo_reconciliar,
            retry_policy=_RETRY,
            # `defer=True`: reconciliar ES un nodo diferido -- ve TODAS las HU. Hasta ahora eso
            # dependía de que el map-reduce de LangGraph juntara las ramas antes de la arista;
            # declararlo lo hace explícito y no depende del orden en que terminen las HU.
            defer=True,
            cache_policy=self._politica(
                "reconciliacion",
                lambda e: self._clave(
                    "reconciliacion",
                    e.get("funcionalidad"),
                    [self._resumen_hu(h) for h in self._procesadas_ordenadas(e)],
                ),
            ),
        )
        g.add_node("publicar", self._nodo_publicar)

        g.add_edge(START, "cargar")
        g.add_conditional_edges("cargar", self._fan_out, ["procesar_historia"])
        g.add_edge("procesar_historia", "reconciliar")
        g.add_edge("reconciliar", "publicar")
        g.add_edge("publicar", END)
        return g.compile(cache=self._cache_nodos, checkpointer=self._checkpointer())
