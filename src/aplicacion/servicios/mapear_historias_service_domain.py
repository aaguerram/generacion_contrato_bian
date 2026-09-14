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

import logging
import re
import uuid

from langgraph.graph import END, START, StateGraph

try:
    from langgraph.types import RetryPolicy, Send
except ImportError:  # pragma: no cover
    from langgraph.constants import Send  # type: ignore
    from langgraph.pregel import RetryPolicy  # type: ignore

from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.catalogo_bom import CatalogoBomPort
from src.aplicacion.puertos.catalogo_operaciones_bian import CatalogoOperacionesBianPort
from src.aplicacion.puertos.entrada_mapeo import MapearHistoriasUseCase
from src.aplicacion.puertos.lector_historias import LectorHistoriasPort
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.puertos.publicador_mapeo import PublicadorMapeoPort
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.aplicacion.servicios.estado_historia import EstadoHistoria
from src.aplicacion.servicios.estado_mapeo import EstadoMapeo
from src.dominio.clasificacion_historias import (
    DEMOTED_REASON_CODE,
    OPERATION_FINALIZED_REASON_CODE,
    PROMOTED_REASON_CODE,
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
    derivar_path_grupo,
    fusionar_propuestas_de_operacion,
    operacion_evidencia_verificable,
    operation_id_en_uso,
    resolver_operation_id,
)
from src.dominio.deteccion_omitidos import detectar_omitidos
from src.dominio.fusion_rrf import fusion_rrf
from src.dominio.historias import (
    BqPersonalizadoAplicado,
    DecisionServiceDomainConsolidada,
    EvidenciaBian,
    HistoriaConServiceDomains,
    HistoriaUsuario,
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
        recuperadores: list[RecuperadorSemanticoPort] | None = None,
        retrieval_top_k: int = 20,
        retrieval_max_inyectados: int = 5,
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
        # Retrieval híbrido (Fase 3 del plan, en memoria): opcional -- lista vacía = desactivado,
        # el pipeline se comporta exactamente como antes (solo candidatos LLM + completitud).
        self._recuperadores = list(recuperadores or [])
        self._retrieval_top_k = max(1, retrieval_top_k)
        self._retrieval_max_inyectados = max(0, retrieval_max_inyectados)
        self._subgrafo = self._compilar_subgrafo()
        self._grafo = self._compilar()

    def ejecutar(
        self, directorio_hu: str, ruta_funcionalidad: str, directorio_salida: str
    ) -> ResultadoMapeoHistorias:
        estado = self._grafo.invoke(
            {
                "directorio_hu": directorio_hu,
                "ruta_funcionalidad": ruta_funcionalidad,
                "directorio_salida": directorio_salida,
            },
            config={"recursion_limit": 60, "max_concurrency": self._concurrencia},
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

    def _h_candidatos(self, estado: EstadoHistoria) -> dict:
        cand = self._analista.generar_candidatos(
            estado["historia"], estado["funcionalidad"], estado["intencion"], estado["catalogo"]
        )
        return {"candidatos": cand, "huellas": _huellas(cand)}

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
        )
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
        for nombre, score in fusion_rrf(rankings):
            puntajes[normalizar(nombre)] = round(score, 6)
            if len(fusionados) >= self._retrieval_max_inyectados or normalizar(nombre) in vistos:
                continue
            vistos.add(normalizar(nombre))
            fusionados.append((nombre, "retrieval_hibrido", []))
        return fusionados, puntajes

    def _h_preparar(self, estado: EstadoHistoria) -> dict:
        catalogo = estado["catalogo"]
        indice = {normalizar(e.service_domain): e for e in catalogo}
        comp = estado.get("revision_completitud") or RevisionCompletitudLLM()

        propuestos: list[tuple[str, str, list[str]]] = [
            (c.service_domain, "llm", list(c.supporting_intent))
            for c in estado["candidatos"].candidatos
        ] + [(n, "completitud", []) for n in comp.missing_candidates]
        inyectados, retrieval_scores = self._candidatos_retrieval_hibrido(
            estado, {normalizar(n) for n, _, _ in propuestos}
        )
        propuestos += inyectados

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

        seleccion = list(resueltos.values())[: self._max_candidatos_hu]
        truncados = list(resueltos.values())[self._max_candidatos_hu :]
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
        degradados = determinar_degradaciones(estado["grupos"], estado["intencion"], revision)

        grupos = estado["grupos"]
        if promovidos or degradados:
            # Re-clasifica con ambos ya reescritos: el score y el tope por rol deben recalcularse
            # juntos (`clasificar_service_domains`), nunca parchear solo la etiqueta de decisión
            # sobre el resultado viejo. Una sola pasada cubre las dos direcciones.
            if promovidos:
                propuestos_por_sd = propuestos_promovidos(propuestos_por_sd, promovidos)
            if degradados:
                propuestos_por_sd = propuestos_degradados(propuestos_por_sd, degradados)
            grupos = self._reclasificar(estado, propuestos_por_sd)
            if promovidos:
                logger.info(
                    "HU '%s': %d SD promovido(s) CONSUMED_DEPENDENCY -> OWNED_CONTRACT por "
                    "evidencia adversarial fuerte: %s",
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
        incidencias = [
            {
                "historia": estado["historia"].archivo,
                "service_domain_propuesto": h.service_domain,
                "resolucion": "MATCH",
                "decision": "UNRESOLVED",
                "motivo": "OWNERSHIP_CONFLICT_UNRESOLVED",
                "detalle": h.detalle
                or f"{h.tipo} sin evidencia determinista suficiente para "
                "reclasificar automáticamente; revisar manualmente.",
            }
            for h in revision.hallazgos
            if h.tipo in ("ACCION_DIRECTA_COMO_DEPENDENCIA", "DEPENDENCIA_PROMOVIDA_A_CONTRATO")
            and h.service_domain
            and normalizar(h.service_domain) not in promovidos
            and normalizar(h.service_domain) not in degradados
        ]
        return {
            "grupos": grupos,
            "bloqueos_hu": bloqueos,
            "propuestos_por_sd": propuestos_por_sd,
            "incidencias": incidencias,
        }

    def _h_operaciones(self, estado: EstadoHistoria) -> dict:
        elegibles = candidatos_operacion_elegibles(estado["grupos"])
        huella, incidencias = self._asignar_operaciones(
            estado["historia"],
            estado["funcionalidad"],
            elegibles,
            estado.get("a_evaluar", []),
        )
        # Recién ahora hay operaciones ancladas: un OWNED_CONTRACT con evidencia BIAN verificada y
        # una operación oficial concreta y verificada pesa más que el score léxico agregado (ver
        # `finalizar_por_operacion_solida`) -- no depende de haber pasado por
        # `determinar_promociones` (ese cubre el caso "el LLM lo clasificó mal como dependencia";
        # este cubre "el LLM ya lo clasificó bien pero con rúbricas de acción/objeto bajas").
        grupos = finalizar_por_operacion_solida(estado["grupos"])
        return {
            "grupos": grupos,
            "huellas": [huella] if huella is not None else [],
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

        retrieval_scores = estado.get("retrieval_scores") or {}
        if retrieval_scores:
            for a in (
                *grupos.candidatos_directos,
                *grupos.candidatos_tentativos,
                *grupos.candidatos_descartados,
            ):
                puntaje = retrieval_scores.get(normalizar(a.service_domain))
                if puntaje is not None:
                    a.desglose_score = a.desglose_score.model_copy(
                        update={"retrieval_score": puntaje}
                    )

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
            revision_completitud=comp,
            revision_adversarial=adv,
            total_directos=len(grupos.candidatos_directos),
            total_tentativos=len(grupos.candidatos_tentativos),
            total_descartados=len(grupos.candidatos_descartados),
            service_domains=grupos,
            service_domains_omitidos=omitidos,
        )
        return {"resultado": resultado}

    # ── paso 6: operaciones oficiales (+ BQ personalizados) para los SD elegibles ─
    def _asignar_operaciones(
        self,
        historia: HistoriaUsuario,
        funcionalidad,
        elegibles: list[ServiceDomainAsignado],
        a_evaluar: list[PaqueteEvidenciaCandidato],
    ) -> tuple[MetadatosPrompt | None, list[dict]]:
        """`elegibles` = `candidatos_operacion_elegibles(grupos)`: OWNED_CONTRACT, directo o
        tentativo (no solo "directo") — ver `clasificacion_historias.candidatos_operacion_elegibles`."""
        if not self._mapear_operaciones or not elegibles:
            return None, []
        operaciones_por_sd = {}
        for sd in elegibles:
            ops = self._catalogo_operaciones.operaciones_de(sd.service_domain)
            if ops:
                operaciones_por_sd[sd.service_domain] = ops
        if not operaciones_por_sd:
            return None, []

        nombres_elegibles = {normalizar(sd.service_domain) for sd in elegibles}
        paquetes_por_sd = {
            p.service_domain: p
            for p in a_evaluar
            if normalizar(p.service_domain) in nombres_elegibles
        }

        mapeo = self._mapeador_operaciones.mapear(
            historia, funcionalidad, operaciones_por_sd, paquetes_por_sd
        )
        por_sd_norm = {sd.service_domain.casefold(): sd for sd in elegibles}
        # Indexado por nombre NORMALIZADO (no el string crudo): una diferencia de capitalización o
        # acentos entre lo que devuelve el LLM y el nombre canónico del SD no debe hacer que la
        # operación "no se encuentre" y caiga a un fallback que la busca en OTRO Service Domain
        # (aislamiento estricto: un operationId de un SD nunca se ancla a otro SD).
        indice_ops = {normalizar(nombre): ops for nombre, ops in operaciones_por_sd.items()}
        incidencias: list[dict] = []
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
        return mapeo.metadatos, incidencias

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
            "umbral_directo": self._umbrales.directo,
            "umbral_tentativo": self._umbrales.tentativo,
            "concurrencia": self._concurrencia,
            "concurrencia_candidatos": self._concurrencia_candidatos,
            "max_candidatos_hu": self._max_candidatos_hu,
            "paso2_operaciones": self._mapear_operaciones,
            "actualizar_cache_bian": self._actualizar_cache_bian,
            "top_n_omitidos": self._top_n_omitidos,
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
        sin_resolver = sum(
            1 for i in incidencias if i.get("motivo") == "OWNERSHIP_CONFLICT_UNRESOLVED"
        )
        base_ownership = promovidos + degradados_count + sin_resolver
        ownership_conflict_rate = round(sin_resolver / base_ownership, 4) if base_ownership else 0.0
        finalizados_por_operacion = sum(
            1 for a in todos if OPERATION_FINALIZED_REASON_CODE in a.reason_codes
        )

        elegibles = [
            a
            for h in procesadas
            for a in (
                *h.service_domains.candidatos_directos,
                *h.service_domains.candidatos_tentativos,
            )
        ]
        ops = [o for a in elegibles for o in a.operaciones_bian]
        verificadas = sum(1 for o in ops if "OPERATION_EVIDENCE_UNVERIFIED" not in o.reason_codes)
        operation_grounding_rate = round(verificadas / len(ops), 4) if ops else 1.0
        operation_id_no_resuelto = sum(
            1 for i in incidencias if i.get("motivo") == "OPERATION_ID_UNRESOLVED"
        )

        return {
            "candidate_drop_rate": candidate_drop_rate,
            "candidatos_truncados": truncados,
            "candidatos_evaluados": total_evaluados,
            "ownership_conflict_rate": ownership_conflict_rate,
            "ownership_promovidos": promovidos,
            "ownership_degradados": degradados_count,
            "ownership_sin_resolver": sin_resolver,
            "operation_grounding_rate": operation_grounding_rate,
            "operaciones_ancladas": len(ops),
            "operation_id_no_resuelto": operation_id_no_resuelto,
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

    # ══ ensamblado de grafos ══════════════════════════════════════════════
    def _compilar_subgrafo(self):
        g = StateGraph(EstadoHistoria)
        g.add_node("extraer_intencion", self._h_intencion, retry_policy=_RETRY)
        g.add_node("generar_candidatos", self._h_candidatos, retry_policy=_RETRY)
        g.add_node("revisar_completitud", self._h_completitud, retry_policy=_RETRY)
        g.add_node("preparar_candidatos", self._h_preparar)
        g.add_node("evaluar_candidato", self._h_evaluar, retry_policy=_RETRY)
        g.add_node("clasificar", self._h_clasificar)
        g.add_node("revisar_adversarial", self._h_adversarial, retry_policy=_RETRY)
        g.add_node("aplicar_adversarial", self._h_aplicar_adversarial)
        g.add_node("seleccionar_operaciones", self._h_operaciones, retry_policy=_RETRY)
        g.add_node("ensamblar", self._h_ensamblar)

        g.add_edge(START, "extraer_intencion")
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
        return g.compile()

    def _compilar(self):
        g = StateGraph(EstadoMapeo)
        g.add_node("cargar", self._nodo_cargar)
        g.add_node("procesar_historia", self._nodo_procesar)
        g.add_node("reconciliar", self._nodo_reconciliar, retry_policy=_RETRY)
        g.add_node("publicar", self._nodo_publicar)

        g.add_edge(START, "cargar")
        g.add_conditional_edges("cargar", self._fan_out, ["procesar_historia"])
        g.add_edge("procesar_historia", "reconciliar")
        g.add_edge("reconciliar", "publicar")
        g.add_edge("publicar", END)
        return g.compile()
