"""Caso de uso `MapearHistoriasUseCase` orquestado con LangGraph.

Outer graph (map-reduce sobre las HU):

    START -> cargar -> (Send por HU) -> procesar_historia --+--> reconciliar -> publicar -> END

`procesar_historia` invoca un SUBGRAFO por historia con su propio fan-out por candidato:

    extraer_intencion -> generar_candidatos -> revisar_completitud
      -> preparar_candidatos            [det: unión LLM ∪ missing + paquete de evidencia por SD]
      -> (Send por candidato) evaluar_candidato   [1 llamada aislada / paquete de evidencia cerrado]
      -> clasificar                     [det: scoring_bian + dos ejes + tope por rol]
      -> revisar_adversarial            [LLM, prompt independiente]
      -> aplicar_adversarial            [det: solo degrada, nunca promueve]
      -> seleccionar_operaciones        [LLM + anclaje al catálogo local]
      -> ensamblar

El LLM nunca decide el estado final: `scoring_bian` + `clasificacion_historias` + `_consolidar`
son el árbitro. `reconciliar_funcionalidad` es un asesor a nivel de funcionalidad.
Depende SOLO de: dominio, puertos y `langgraph`.
"""

from __future__ import annotations

import logging
import re

from langgraph.graph import END, START, StateGraph

try:
    from langgraph.types import RetryPolicy, Send
except ImportError:  # pragma: no cover
    from langgraph.pregel import RetryPolicy  # type: ignore
    from langgraph.constants import Send  # type: ignore

from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.catalogo_bom import CatalogoBomPort
from src.aplicacion.puertos.catalogo_operaciones_bian import CatalogoOperacionesBianPort
from src.aplicacion.puertos.entrada_mapeo import MapearHistoriasUseCase
from src.aplicacion.puertos.lector_historias import LectorHistoriasPort
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.puertos.publicador_mapeo import PublicadorMapeoPort
from src.aplicacion.servicios.estado_historia import EstadoHistoria
from src.aplicacion.servicios.estado_mapeo import EstadoMapeo
from src.dominio.clasificacion_historias import (
    UmbralesMapeo,
    aplicar_hallazgos_adversariales,
    clasificar_service_domains,
    resolver_nombre_sd,
)
from src.dominio.deteccion_omitidos import detectar_omitidos
from src.dominio.historias import (
    BqPersonalizadoAplicado,
    DecisionServiceDomainConsolidada,
    EvidenciaBian,
    HistoriaConServiceDomains,
    HistoriaUsuario,
    MetadatosPrompt,
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
    if "TODOSLOSMODELOSAGOTADOS" in type(exc).__name__.upper() or "SE AGOTARON TODOS LOS MODELOS" in t:
        return False
    return any(m in t for m in _TRANSITORIOS)


_RETRY = RetryPolicy(
    max_attempts=3, initial_interval=2.0, backoff_factor=2.0, max_interval=20.0, retry_on=_es_transitorio
)


def _huellas(*modelos) -> list[MetadatosPrompt]:
    return [m.metadatos for m in modelos if m is not None and getattr(m, "metadatos", None) is not None]


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
_VERBOS_BIAN = {"Initiate", "Update", "Retrieve", "Control", "Request", "Execute", "Exchange", "Grant", "Register"}


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
            len(historias), funcionalidad.funcionalidad_macro, len(catalogo),
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
            Send("procesar_historia", {
                "historia": h,
                "funcionalidad": estado["funcionalidad"],
                "catalogo": estado["catalogo"],
            })
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
            estado["historia"], estado["intencion"], estado["candidatos"],
            estado["catalogo"], disponibilidad,
        )
        return {"revision_completitud": rev, "huellas": _huellas(rev)}

    def _h_preparar(self, estado: EstadoHistoria) -> dict:
        catalogo = estado["catalogo"]
        indice = {normalizar(e.service_domain): e for e in catalogo}
        comp = estado.get("revision_completitud") or RevisionCompletitudLLM()

        propuestos: list[tuple[str, str, list[str]]] = [
            (c.service_domain, "llm", list(c.supporting_intent)) for c in estado["candidatos"].candidatos
        ] + [(n, "completitud", []) for n in comp.missing_candidates]

        incidencias: list[dict] = []
        resueltos: dict[str, tuple[EntradaCatalogo, str, list[str]]] = {}
        for nombre, origen, intent in propuestos:
            entrada, resol = resolver_nombre_sd(nombre, indice)
            if entrada is None or resol != "MATCH":
                incidencias.append({
                    "historia": estado["historia"].archivo,
                    "service_domain_propuesto": nombre,
                    "resolucion": resol,
                    "decision": "REJECTED",
                    "motivo": "NAME_UNRESOLVED",
                    "detalle": "Nombre no resoluble contra el catalogo BIAN R14",
                })
                continue
            resueltos.setdefault(normalizar(entrada.service_domain), (entrada, origen, list(intent)))

        seleccion = list(resueltos.values())[: self._max_candidatos_hu]
        nombres = [e.service_domain for e, _, _ in seleccion]
        evidencias = self._catalogo_operaciones.asegurar(nombres, actualizar=self._actualizar_cache_bian)

        a_evaluar: list[PaqueteEvidenciaCandidato] = []
        for entrada, origen, intent in seleccion:
            ops = self._catalogo_operaciones.operaciones_de(entrada.service_domain) or []
            esq = self._catalogo_operaciones.esquemas_de(entrada.service_domain)
            det = self._catalogo_operaciones.schemas_detalle_de(entrada.service_domain)
            bom = self._catalogo_bom.modelo_de(entrada.service_domain) if self._catalogo_bom else None
            a_evaluar.append(_paquete_de(
                entrada, evidencias.get(entrada.service_domain, EvidenciaBian()),
                ops, esq, origen=origen, supporting_intent=intent,
                schemas_detalle=det, bom_modelo=bom,
            ))
        a_evaluar.sort(key=lambda p: p.service_domain.lower())

        ya = {normalizar(p.service_domain) for p in a_evaluar}
        omitidos = (
            detectar_omitidos(estado["intencion"], catalogo, ya, top_n=self._top_n_omitidos)
            if self._top_n_omitidos else []
        )
        return {"a_evaluar": a_evaluar, "omitidos": omitidos, "incidencias": incidencias}

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

    def _h_clasificar(self, estado: EstadoHistoria) -> dict:
        paquetes = {p.service_domain: p for p in estado.get("a_evaluar", [])}
        evals = sorted(estado.get("evaluaciones", []), key=lambda e: e.service_domain.lower())
        propuestos = [
            ServiceDomainPropuestoLLM.desde_evaluacion(e, service_domain_canonico=e.service_domain)
            for e in evals
        ]
        grupos = clasificar_service_domains(
            propuestos, estado["catalogo"], self._umbrales,
            operaciones_por_sd={n: p.operations for n, p in paquetes.items()},
            evidencias_por_sd={n: p.evidencia for n, p in paquetes.items()},
            esquemas_por_sd={n: p.schemas for n, p in paquetes.items()},
            origen_por_sd={n: p.origen for n, p in paquetes.items()},
        )
        return {"grupos": grupos}

    def _h_adversarial(self, estado: EstadoHistoria) -> dict:
        rev = self._analista.revisar_adversarial(
            estado["historia"], estado["intencion"], estado["grupos"]
        )
        return {"revision_adversarial": rev, "huellas": _huellas(rev)}

    def _h_aplicar_adversarial(self, estado: EstadoHistoria) -> dict:
        grupos, bloqueos = aplicar_hallazgos_adversariales(
            estado["grupos"], estado.get("revision_adversarial") or RevisionAdversarialLLM()
        )
        return {"grupos": grupos, "bloqueos_hu": bloqueos}

    def _h_operaciones(self, estado: EstadoHistoria) -> dict:
        huella = self._asignar_operaciones(
            estado["historia"], estado["funcionalidad"],
            estado["grupos"].candidatos_directos, estado.get("a_evaluar", []),
        )
        return {"grupos": estado["grupos"], "huellas": [huella] if huella is not None else []}

    def _h_ensamblar(self, estado: EstadoHistoria) -> dict:
        historia: HistoriaUsuario = estado["historia"]
        intencion = estado["intencion"]
        grupos = estado["grupos"]
        comp = estado.get("revision_completitud") or RevisionCompletitudLLM()
        adv = estado.get("revision_adversarial") or RevisionAdversarialLLM()
        bloqueos = list(estado.get("bloqueos_hu", []))
        omitidos = estado.get("omitidos", [])

        n_ops = sum(len(a.operaciones_bian) for a in grupos.candidatos_directos)
        logger.info(
            "HU '%s' -> candidatos=%d directos=%d tentativos=%d descartados=%d | operaciones=%d | omitidos=%d",
            historia.titulo, len(estado.get("a_evaluar", [])),
            len(grupos.candidatos_directos), len(grupos.candidatos_tentativos),
            len(grupos.candidatos_descartados), n_ops, len(omitidos),
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
            assumptions=list(dict.fromkeys([*intencion.assumptions, *estado["candidatos"].assumptions])),
            gaps=list(dict.fromkeys([*intencion.gaps, *estado["candidatos"].gaps, *comp.coverage_gaps])),
            unresolved_questions=list(intencion.unresolved_questions),
            blocking_codes=list(dict.fromkeys([*bloqueos, *comp.blocking_codes, *adv.blocking_codes])),
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

    # ── paso 6: operaciones oficiales (+ BQ personalizados) para los SD directos ─
    def _asignar_operaciones(
        self,
        historia: HistoriaUsuario,
        funcionalidad,
        directos: list[ServiceDomainAsignado],
        a_evaluar: list[PaqueteEvidenciaCandidato],
    ) -> MetadatosPrompt | None:
        if not self._mapear_operaciones or not directos:
            return None
        operaciones_por_sd = {}
        for sd in directos:
            ops = self._catalogo_operaciones.operaciones_de(sd.service_domain)
            if ops:
                operaciones_por_sd[sd.service_domain] = ops
        if not operaciones_por_sd:
            return None

        nombres_directos = {normalizar(sd.service_domain) for sd in directos}
        paquetes_por_sd = {p.service_domain: p for p in a_evaluar if normalizar(p.service_domain) in nombres_directos}

        mapeo = self._mapeador_operaciones.mapear(historia, funcionalidad, operaciones_por_sd, paquetes_por_sd)
        por_sd_norm = {sd.service_domain.casefold(): sd for sd in directos}
        indice_ops = {
            nombre: {o.operation_id: o for o in ops} for nombre, ops in operaciones_por_sd.items()
        }
        for op in mapeo.operaciones:
            asignado = por_sd_norm.get(op.service_domain.casefold())
            fuente = indice_ops.get(op.service_domain, {}).get(op.operation_id) or next(
                (v.get(op.operation_id) for v in indice_ops.values() if op.operation_id in v), None
            )
            if asignado is None or fuente is None:
                continue
            asignado.operaciones_bian.append(OperacionBianAplicada(
                operation_id=fuente.operation_id,
                method=fuente.method,
                path=fuente.path,
                tipo=fuente.tipo,
                grupo=fuente.grupo,
                escenarios_hu=[s.strip() for s in op.escenarios_hu if s and s.strip()],
                justificacion=op.justificacion.strip(),
                action_term=op.action_term.strip(),
                business_object=op.business_object.strip(),
                bq_seed=op.bq_seed.strip(),
                traceability=[s.strip() for s in op.traceability if s and s.strip()],
                evidence_refs=list(op.evidence_refs),
                reason_codes=list(op.reason_codes),
            ))
        for sd in directos:
            sd.operaciones_bian.sort(key=lambda o: (o.tipo, o.grupo, o.operation_id))

        self._anclar_bq_personalizados(mapeo.bq_personalizados, por_sd_norm, paquetes_por_sd, historia.titulo)
        return mapeo.metadatos

    @staticmethod
    def _anclar_bq_personalizados(
        propuestos, por_sd_norm: dict[str, ServiceDomainAsignado],
        paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato], historia_titulo: str,
    ) -> None:
        """Determinista: un BQ personalizado SOLO se ancla si (a) el campo no está ya cubierto por
        una operación oficial, (b) el nombre no colisiona con un CR/BQ oficial existente, y
        (c) la clase/atributo BOM citados existen de verdad. Nunca se "arregla" una cita floja."""
        for p in propuestos:
            asignado = por_sd_norm.get(p.service_domain.casefold())
            paquete = paquetes_por_sd.get(p.service_domain) or next(
                (v for k, v in paquetes_por_sd.items() if k.casefold() == p.service_domain.casefold()), None
            )
            if asignado is None or paquete is None:
                continue
            grupos_existentes = {normalizar(g) for g in (*paquete.control_records, *paquete.behavior_qualifiers)}
            if normalizar(p.nombre_bq) in grupos_existentes:
                logger.info(
                    "HU '%s': BQ personalizado '%s' ya existe como CR/BQ oficial de %s; descartado",
                    historia_titulo, p.nombre_bq, p.service_domain,
                )
                continue
            ya_cubierto = normalizar(p.campo_no_cubierto) and any(
                normalizar(p.campo_no_cubierto) in normalizar(f"{o.operation_id} {o.summary} {o.description}")
                for o in paquete.operations
            )
            if ya_cubierto:
                logger.info(
                    "HU '%s': campo '%s' ya cubierto por una operación oficial de %s; BQ personalizado descartado",
                    historia_titulo, p.campo_no_cubierto, p.service_domain,
                )
                continue
            if not _bom_respalda(paquete, p.clase_bom, p.atributo_bom):
                logger.warning(
                    "HU '%s': BQ personalizado '%s' para %s cita clase/atributo BOM no verificable "
                    "('%s'.'%s'); descartado",
                    historia_titulo, p.nombre_bq, p.service_domain, p.clase_bom, p.atributo_bom,
                )
                continue

            verbo = p.verbo if p.verbo in _VERBOS_BIAN else "Update"
            nombre_bq = _pascal(p.nombre_bq)
            slug_sd = re.sub(r"[^A-Za-z0-9]", "", asignado.service_domain)
            asignado.bq_personalizados_propuestos.append(BqPersonalizadoAplicado(
                service_domain=asignado.service_domain,
                nombre_bq=nombre_bq,
                operation_id=f"{verbo}{nombre_bq}",
                verbo=verbo,
                path_propuesto=f"/{slug_sd}/{{id}}/{nombre_bq}/{verbo}",
                parent_control_record=(paquete.control_records[0] if paquete.control_records else ""),
                campo_no_cubierto=p.campo_no_cubierto.strip(),
                clase_bom=p.clase_bom.strip(),
                atributo_bom=p.atributo_bom.strip(),
                escenarios_hu=[s.strip() for s in p.escenarios_hu if s and s.strip()],
                justificacion=p.justificacion.strip(),
                reason_codes=list(dict.fromkeys(p.reason_codes)),
            ))
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
                for a in (*g.candidatos_directos, *g.candidatos_tentativos, *g.candidatos_descartados)
            ],
        }

    def _resultado_mapeo(self, estado: EstadoMapeo) -> ResultadoMapeoHistorias:
        procesadas = self._procesadas_ordenadas(estado)
        funcionalidad = estado.get("funcionalidad")
        reconciliacion = estado.get("reconciliacion") or ReconciliacionFuncionalidadLLM()
        parametros = {
            **self._parametros_base,
            "umbral_directo": self._umbrales.directo,
            "umbral_tentativo": self._umbrales.tentativo,
            "concurrencia": self._concurrencia,
            "concurrencia_candidatos": self._concurrencia_candidatos,
            "max_candidatos_hu": self._max_candidatos_hu,
            "paso2_operaciones": self._mapear_operaciones,
            "actualizar_cache_bian": self._actualizar_cache_bian,
            "top_n_omitidos": self._top_n_omitidos,
        }
        huellas = sorted(
            estado.get("huellas_prompts", []),
            key=lambda m: (m.historia, m.nodo, m.prompt_id, m.evidence_snapshot_id, m.prompt_sha256),
        )
        incidencias = sorted(
            estado.get("incidencias", []),
            key=lambda d: (d.get("historia", ""), d.get("service_domain_propuesto", "")),
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
        )

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
                (a for a in asignados
                 if a.rol_contractual == "OWNED_CONTRACT" and a.decision_contractual == "SELECTED"),
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
            salida.append(DecisionServiceDomainConsolidada(
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
                ownership_traceability=sorted({t for a in asignados for t in a.ownership_traceability}),
                dependency_traceability=sorted({t for a in asignados for t in a.dependency_traceability}),
                selected_operations=sorted({o.operation_id for a in asignados for o in a.operaciones_bian}),
                custom_bq_candidates=sorted(
                    {b.operation_id: b for a in asignados for b in a.bq_personalizados_propuestos}.values(),
                    key=lambda b: b.operation_id,
                ),
                reason_codes=sorted({
                    c for a in asignados for c in a.reason_codes
                } | (set(r.reason_codes) if r else set())),
                blocking_codes=sorted({c for a in asignados for c in a.blocking_codes}),
                evidence=base.evidencia_bian,
                rationale=base.justificacion,
            ))
        prioridad = {"SELECTED": 0, "UNRESOLVED": 1, "REJECTED": 2}
        return sorted(salida, key=lambda x: (prioridad[x.decision], -x.score, x.service_domain))

    @staticmethod
    def _consolidar_omitidos(historias: list[HistoriaConServiceDomains]) -> list[ServiceDomainOmitido]:
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
