"""Modelos del dominio para el mapeo Historia de Usuario -> BIAN Service Domains.

Puro: solo stdlib + pydantic. Sin frameworks, sin adaptadores.

Arquitectura de nodos LLM del caso de uso `MapearHistoriasUseCase` (map-reduce sobre las HU;
por cada HU un subgrafo con fan-out por candidato):

    extraer_intencion        -> IntencionHistoriaLLM      (interpretacion + acciones + objetos)
    enrutar_dominios         -> EnrutamientoDominiosLLM   (36 Business Domains; opcional, ver flag)
    generar_candidatos       -> CandidatosHistoriaLLM     (nombres de SD, pista, no exhaustivo)
    revisar_completitud      -> RevisionCompletitudLLM    (missing / unsupported / conflicts / gaps)
      [det] union candidatos LLM + omitidos lexicos + missing -> paquete de evidencia por candidato
    evaluar_candidato (xN)   -> EvaluacionCandidatoLLM    (1 candidato vs 1 paquete de evidencia)
      [det] scoring_bian + clasificacion_historias (dos ejes, tope por rol)
    revisar_adversarial      -> RevisionAdversarialLLM    (prompt distinto: revisa la hipotesis)
      [det] aplicar hallazgos (reason_codes / blocking)
    seleccionar_operaciones  -> MapeoOperacionesLLM       (operationId literales, conjunto minimo)
    reconciliar_funcionalidad-> ReconciliacionFuncionalidadLLM (1 vez, ve todas las HU; asesor)
      [det] _consolidar -> ResultadoMapeoHistorias -> JSON

El LLM NUNCA decide el estado final (SELECTED / UNRESOLVED / REJECTED): devuelve senales
ordinales 0-3, trazabilidad con identificadores, supuestos y gaps. El codigo determinista
calcula score, confianza, clasificacion y bloqueos. Toda la evidencia BIAN vive dentro de
`generacion_contrato_ia_v2/docs/` (`BIAN_Service_Landscape_V14.0_Matrix_View.json`,
`bian-operation-catalogs.json`, `bian-cache/`). Sin Internet, sin memoria del modelo como evidencia.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Grupo = Literal["directo", "tentativo", "descartado"]

# Rol contractual del SD respecto a la funcionalidad (taxonomía BIAN business-alignment).
RolContractual = Literal["OWNED_CONTRACT", "CONSUMED_DEPENDENCY", "RELATED_NOT_OWNED"]

# Tipo de dependencia cuando el rol es CONSUMED_DEPENDENCY.
DependencyKind = Literal[
    "SECURITY_GUARD",
    "SUPPORTING_LOOKUP",
    "EXTERNAL_PROVIDER",
    "RISK_INPUT",
    "AUDIT_OR_NOTIFICATION",
    "OTHER_DEPENDENCY",
]

# Resultado de resolver el nombre propuesto contra el catálogo BIAN R14 local.
Resolucion = Literal["MATCH", "AMBIGUOUS", "NOT_FOUND"]
EstadoEvidencia = Literal["VERIFIED", "CACHED_VERIFIED", "BIAN_EVIDENCE_UNAVAILABLE"]

# Eje contractual (¿se materializa o no un contrato para este SD?).
DecisionContractual = Literal["SELECTED", "UNRESOLVED", "REJECTED"]
EstadoEvaluacion = Literal["DIRECTO", "TENTATIVO", "DESCARTADO", "NO_RESUELTO"]
NivelAmbiguedad = Literal["NONE", "LOW", "HIGH"]

# Origen de un candidato en la lista unificada a evaluar.
# "crag": lo reinyectó la vuelta correctiva cuando el lote de evidencia salió vacío o sin
# operaciones/BOM (ver `_vuelta_correctiva`). Se distingue de "retrieval_hibrido" a propósito: el
# híbrido siempre aporta candidatos, el CRAG solo aparece cuando la primera pasada no sostenía
# ninguna decisión -- y eso es justo lo que hay que poder contar en las métricas.
OrigenCandidato = Literal[
    "llm", "omitido", "completitud", "retrieval_hibrido", "graph_rag", "crag"
]

# Motivo de la decisión contractual (sub-taxonomía del diagrama de dos ejes).
MotivoDecision = Literal[
    "OWNED_SELECTED",  # OWNED_CONTRACT con score directo y evidencia oficial verificable
    "TENTATIVE_SCORE",  # score en banda tentativa: aplica pero no alcanza el umbral directo
    "NO_OFFICIAL_BIAN_EVIDENCE",  # score suficiente pero sin BOM oficial verificable -> sin resolver
    "CONSUMED_DEPENDENCY",  # dependencia consumida (no se posee el ciclo de vida)
    "RELATED_NOT_OWNED",  # relación temática, no necesaria para implementar la historia
    "OUT_OF_SCOPE",  # score por debajo de la banda tentativa: no aplica
    "NAME_UNRESOLVED",  # el nombre propuesto no resolvió contra el catálogo BIAN R14
    # Propietario con evidencia, pero NINGUNA de sus operaciones oficiales pudo anclarse: un
    # contrato sin operación no es accionable, así que no puede presentarse como resuelto.
    "NO_OPERATION_ANCHORED",
]

# alias tolerados en el JSON de entrada de la funcionalidad macro
_ALIAS_MACRO = ("funcionalidad_macro", "funcionalidad", "nombre", "macro", "titulo", "name")
_ALIAS_DETALLE = ("detalle", "descripcion", "detail", "description", "contexto", "resumen")


class FuncionalidadMacro(BaseModel):
    """La funcionalidad macro a implementar y su detalle (contexto transversal a todas las HU)."""

    funcionalidad_macro: str = Field(description="Nombre de la funcionalidad macro a implementar.")
    detalle: str = Field(default="", description="Detalle / contexto de la funcionalidad macro.")

    @classmethod
    def desde_dict(cls, datos: dict) -> FuncionalidadMacro:
        """Construye desde un dict tolerando alias de claves (funcionalidad_macro/detalle y sinónimos)."""
        if not isinstance(datos, dict):
            raise ValueError("El archivo de funcionalidad debe contener un objeto JSON.")
        macro = next((str(datos[k]).strip() for k in _ALIAS_MACRO if datos.get(k)), "")
        detalle = next((str(datos[k]).strip() for k in _ALIAS_DETALLE if datos.get(k)), "")
        if not macro:
            raise ValueError(
                "El JSON de funcionalidad no trae 'funcionalidad_macro' (ni un alias: "
                f"{', '.join(_ALIAS_MACRO)})."
            )
        return cls(funcionalidad_macro=macro, detalle=detalle)


class HistoriaUsuario(BaseModel):
    """Una Historia de Usuario leída de un archivo del directorio de entrada."""

    archivo: str = Field(description="Nombre del archivo de origen (con extensión).")
    titulo: str = Field(
        description="Título legible de la historia (derivado del nombre de archivo)."
    )
    contenido: str = Field(
        description="Texto completo de la historia (Como/Quiero/Para + escenarios)."
    )


class OperacionBian(BaseModel):
    """Una operación oficial de un Service Domain (Control Record o Behavior Qualifier)."""

    operation_id: str
    method: str
    path: str
    tipo: Literal["CR", "BQ"]
    grupo: str = Field(
        description="Nombre del Control Record o Behavior Qualifier al que pertenece."
    )
    parent_control_record: str | None = None
    request_schema: str = Field(
        default="", description="Nombre del schema del requestBody (resuelto del $ref)."
    )
    response_schema: str = Field(
        default="", description="Nombre del schema de la respuesta 200 (resuelto del $ref)."
    )
    summary: str = ""
    description: str = ""


# ── BOM: schemas de la Semantic API + modelo de clases del PUML ──────────────
class PropiedadSchema(BaseModel):
    name: str
    type: str = ""
    ref: str = Field(
        default="", description="Nombre del schema referenciado si la propiedad es un $ref."
    )


class SchemaBom(BaseModel):
    """Un schema de `components.schemas` del OpenAPI oficial, con su cuerpo (no solo el nombre)."""

    name: str
    kind: Literal["object", "enum", "value", "array"] = "object"
    description: str = ""
    properties: list[PropiedadSchema] = Field(default_factory=list)
    enum_values: list[str] = Field(default_factory=list)


class AtributoBom(BaseModel):
    name: str
    type: str = ""
    cardinality: str = ""


class ClaseBom(BaseModel):
    name: str
    attributes: list[AtributoBom] = Field(default_factory=list)


class EnumBom(BaseModel):
    name: str
    values: list[str] = Field(default_factory=list)


class AsociacionBom(BaseModel):
    origen: str
    destino: str
    etiqueta: str = ""
    tipo: Literal["asociacion", "herencia"] = "asociacion"


class ModeloBomPuml(BaseModel):
    """Modelo estructural (clases/enums/asociaciones) de un Service Domain, extraído del PUML BOM
    BIAN (`docs/bian-diagrams/puml-bom/<slug>.puml`). Complementa a los schemas de la Semantic API."""

    service_domain: str
    source_url: str = ""
    slug: str = ""
    clases: list[ClaseBom] = Field(default_factory=list)
    enums: list[EnumBom] = Field(default_factory=list)
    asociaciones: list[AsociacionBom] = Field(default_factory=list)


class EvidenciaBian(BaseModel):
    estado: EstadoEvidencia = "BIAN_EVIDENCE_UNAVAILABLE"
    release: str = "14.0.0"
    source_url: str = ""
    source_commit_sha: str = ""
    content_sha256: str = ""
    cache_path: str = ""
    recuperado_en: str = ""
    error: str = ""


class DesgloseScore(BaseModel):
    accion_oficial: float = 0.0
    objeto_bom: float = 0.0
    ownership_outcome: float = 0.0
    trazabilidad_escenarios: float = 0.0
    coherencia_jerarquia: float = 0.0
    penalizacion: float = 0.0
    total: float = 0.0
    # Etapas adicionales del score (aditivas; no participan en `total` — ver scoring_bian.py).
    retrieval_score: float = Field(
        default=0.0,
        description="Score de fusión RRF si el candidato entró por retrieval híbrido (0.0 = no aplica / origen LLM).",
    )
    operation_support_score: float = Field(
        default=0.0,
        description="Fracción de las operaciones ancladas de este SD con evidencia verificable "
        "(sin OPERATION_EVIDENCE_UNVERIFIED). 0.0 si no se ancló ninguna operación todavía.",
    )
    graph_score: float = Field(
        default=0.0,
        description="Especificidad de la conexión por el grafo canónico BIAN si el SD fue "
        "alcanzado por expansión (1/nº de SD que comparten el nodo puente). 0.0 = no aplica.",
    )
    rerank_score: float = Field(
        default=0.0,
        description="Score del reranker sobre la intención de la historia, si se aplicó. "
        "Ordena el recorte previo al fan-out; no participa en `total`.",
    )


class MetadatosPrompt(BaseModel):
    """Huella reproducible de una llamada LLM; nunca participa en la decisión."""

    prompt_id: str
    prompt_version: str
    prompt_sha256: str
    nodo: str = ""
    historia: str = ""
    # `model` conserva la cadena completa por compatibilidad y reproducibilidad.
    model: str = ""
    provider_used: str = ""
    model_used: str = ""
    attempt: int | None = None
    temperature: float | None = None
    catalog_sha256: str = ""
    evidence_snapshot_id: str = ""


# ── Nodo 1: extracción de intención funcional (sin decisiones BIAN todavía) ───
class IntencionHistoriaLLM(BaseModel):
    """Interpretación funcional de la historia. Sin nombres de Service Domain."""

    resumen_funcional: str = ""
    capacidades_funcionales: list[str] = Field(default_factory=list)
    business_actions: list[str] = Field(
        default_factory=list, description="Verbos de negocio concretos."
    )
    business_objects: list[str] = Field(
        default_factory=list, description="Objetos de negocio administrados."
    )
    outcomes: list[str] = Field(default_factory=list)
    external_dependencies: list[str] = Field(default_factory=list)
    traceability_ids: list[str] = Field(
        default_factory=list,
        description="Identificadores de la historia (HU-.../SC-..., BR-...) mencionados o derivables.",
    )
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    metadatos: MetadatosPrompt | None = None


# ── Nodo 2a: enrutamiento por la taxonomía BIAN (antes de ver ningún SD) ──────
class EnrutamientoDominiosLLM(BaseModel):
    """Qué Business Domains de la taxonomía BIAN pueden contener los SD de esta historia.

    Primera etapa del routing jerárquico: reduce una decisión de 341 vías con el rol recortado a
    una de 36 vías con la documentación COMPLETA de cada nodo de la jerarquía. Lo que gana no es
    filtrar -- es que la segunda etapa pueda mostrar el texto entero de los SD que sobreviven.

    No nombra ningún Service Domain: eso es el nodo 2b.
    """

    business_domains: list[str] = Field(
        default_factory=list,
        description="Nombres EXACTOS de Business Domain de la taxonomía, incluidos los de las dependencias.",
    )
    rationale: str = ""
    # Las dependencias (auth, permisos, riesgo, auditoría, notificación) viven casi siempre en
    # otro Business Domain -- y a veces en otra Business Area- que el propietario. Medido sobre
    # los tres casos E2E: los candidatos reales de una HU abarcan de 3 a 5 dominios y hasta 4
    # áreas. Si el router solo persigue al propietario, las pierde todas.
    dependency_domains: list[str] = Field(
        default_factory=list,
        description="Business Domains elegidos por cubrir una external_dependency, no la acción principal.",
    )
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    metadatos: MetadatosPrompt | None = None

    def todos(self) -> list[str]:
        """Unión sin duplicados y conservando el orden: es lo que se usa para filtrar."""
        return list(dict.fromkeys([*self.business_domains, *self.dependency_domains]))


# ── Nodo 2a (determinista): propiedad de clases del BOM -> Service Domains ────
class EvidenciaClaseBom(BaseModel):
    """Una clase del BOM que un Service Domain DEFINE (su ocurrencia no lleva `Extensible`).

    No es recuperación léxica: es una atribución del propio modelo BIAN. Ver `entidades_bian`.
    """

    clase: str
    bq: str = Field(default="", description="Behavior Qualifier al que pertenece la clase (notes.BQ).")
    control_record: str = ""
    motivos: list[str] = Field(default_factory=list)
    enum: str = Field(default="", description="Enum con el que la clase tipifica el dato buscado.")
    valores_enum: list[str] = Field(default_factory=list)
    # La distinción que necesita el nodo 3: un enum TIPIFICA; los atributos adicionales son los
    # que GUARDAN el valor. `Contact Point` dice que un Party tiene un correo, `Phone Address`
    # guarda el número. Sin esto los dos Service Domains parecen aportar lo mismo.
    atributos_adicionales: list[str] = Field(default_factory=list)
    # Otros Service Domains que TAMBIÉN definen esta clase (ocurrencia sin `Extensible`). Vacío =
    # atribución inequívoca del modelo. No reparte el peso: los dos la definen, los dos son
    # candidatos, y quién es el dueño del DATO de la historia lo decide la evaluación, no el canal.
    compartida_con: list[str] = Field(default_factory=list)
    importada_en: list[str] = Field(
        default_factory=list,
        description="Service Domains que la referencian sin definirla (llevan `Extensible`).",
    )
    nota: str = ""


class CandidatoClaseBom(BaseModel):
    service_domain: str
    score: float = 0.0
    evidencias: list[EvidenciaClaseBom] = Field(default_factory=list)

    def bqs(self) -> list[str]:
        """Behavior Qualifiers citados, sin duplicar y en orden de aparición."""
        vistos: list[str] = []
        for e in self.evidencias:
            if e.bq and e.bq not in vistos:
                vistos.append(e.bq)
        return vistos


# ── Nodo 2b: generación de candidatos (pista, no exhaustiva) ──────────────────
class CandidatoServiceDomainLLM(BaseModel):
    service_domain: str = Field(
        description="Nombre de un Service Domain del catálogo (copia literal)."
    )
    rationale: str = ""
    supporting_intent: list[str] = Field(
        default_factory=list, description="business_actions / business_objects que lo sugieren."
    )


class CandidatosHistoriaLLM(BaseModel):
    candidatos: list[CandidatoServiceDomainLLM] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    metadatos: MetadatosPrompt | None = None


# ── Nodo 3: revisión de completitud de la lista de candidatos ─────────────────
class RevisionCompletitudLLM(BaseModel):
    missing_candidates: list[str] = Field(
        default_factory=list, description="Nombres del índice global que faltan y hay que evaluar."
    )
    unsupported_candidates: list[str] = Field(
        default_factory=list, description="Candidatos propuestos sin evidencia disponible."
    )
    ownership_conflicts: list[str] = Field(default_factory=list)
    duplicated_responsibilities: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    review_summary: str = ""
    metadatos: MetadatosPrompt | None = None


# ── Paquete de evidencia oficial cerrado por candidato (entrada de evaluar) ───
class PaqueteEvidenciaCandidato(BaseModel):
    """Todo lo que el LLM ve para evaluar UN candidato. Se arma en código desde la caché oficial."""

    service_domain: str = Field(description="Nombre canónico del catálogo BIAN R14.")
    business_area: str | None = None
    business_domain: str | None = None
    service_role: str = ""
    functional_pattern: str | None = None
    asset_type: str | None = None
    control_records: list[str] = Field(default_factory=list)
    behavior_qualifiers: list[str] = Field(default_factory=list)
    operations: list[OperacionBian] = Field(default_factory=list)
    schemas: list[str] = Field(default_factory=list, description="Nombres de schema (compat).")
    schemas_detalle: list[SchemaBom] = Field(
        default_factory=list,
        description="Schemas de la Semantic API con cuerpo (properties / enum values).",
    )
    bom_modelo: ModeloBomPuml | None = Field(
        default=None, description="Modelo de clases del PUML BOM BIAN, si hay evidencia local."
    )
    evidencia: EvidenciaBian = Field(default_factory=EvidenciaBian)
    origen: OrigenCandidato = "llm"
    supporting_intent: list[str] = Field(default_factory=list)


# ── Nodo 4: evaluación aislada de un candidato ───────────────────────────────
class EvaluacionCandidatoLLM(BaseModel):
    """Evaluación de UN candidato contra su paquete de evidencia. Señales ordinales, no confianza."""

    service_domain: str = Field(
        description="Eco del nombre del paquete de evidencia (copia literal)."
    )
    estado: EstadoEvaluacion = "NO_RESUELTO"
    rol_contractual: RolContractual = "RELATED_NOT_OWNED"
    dependency_kind: DependencyKind | None = None
    accion_objeto: str = Field(
        default="",
        description="verbo + objeto de negocio de la historia que empata con la evidencia.",
    )
    functional_object: str = Field(
        default="",
        description="Objeto de negocio funcional real (NO el wrapper técnico del Control Record).",
    )
    match_action: int = Field(default=0, ge=0, le=3)
    match_business_object: int = Field(default=0, ge=0, le=3)
    match_service_role: int = Field(default=0, ge=0, le=3)
    evidence_quality: int = Field(default=0, ge=0, le=3)
    ambiguity: NivelAmbiguedad = "HIGH"
    ownership_traceability: list[str] = Field(
        default_factory=list,
        description="HU-.../SC-..., BR-... que demuestran responsabilidad DIRECTA.",
    )
    dependency_traceability: list[str] = Field(
        default_factory=list,
        description="HU-.../SC-... que demuestran CONSUMO (nunca reusar como ownership).",
    )
    evidence_refs: list[str] = Field(
        default_factory=list, description="operationId / schema / Service Role citados del paquete."
    )
    reason_codes: list[str] = Field(default_factory=list)
    justification: str = Field(
        default="", description="Justificación breve verificable (<=3 frases)."
    )
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    metadatos: MetadatosPrompt | None = None


# ── Nodo 5: revisión adversarial independiente (prompt distinto) ─────────────
TipoHallazgo = Literal[
    "ACCION_DIRECTA_COMO_DEPENDENCIA",  # un verbo+objeto directo quedó como CONSUMED_DEPENDENCY
    "OBJETO_SIN_PROPIETARIO",  # un objeto funcional central sin SD OWNED
    "DIRECTO_SIN_SERVICE_ROLE",  # SD directo sin Service Role compatible en la evidencia
    "DEPENDENCIA_PROMOVIDA_A_CONTRATO",  # una dependencia consumida quedó como OWNED_CONTRACT
    "CANDIDATO_OMITIDO",  # falta evaluar un SD razonable
    "EXCESO_DE_CONTRATOS",  # demasiados OWNED para el alcance de la historia
]


class HallazgoAdversarial(BaseModel):
    tipo: TipoHallazgo
    service_domain: str = ""
    reason_codes: list[str] = Field(default_factory=list)
    detalle: str = ""


class RevisionAdversarialLLM(BaseModel):
    hallazgos: list[HallazgoAdversarial] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    resumen: str = ""
    metadatos: MetadatosPrompt | None = None


# ── Nodo 7: reconciliación a nivel de funcionalidad (asesor, no decide) ──────
class ReconciliacionServiceDomainLLM(BaseModel):
    service_domain: str
    functionality_role: RolContractual = "RELATED_NOT_OWNED"
    supporting_stories: list[str] = Field(default_factory=list)
    contradicting_stories: list[str] = Field(default_factory=list)
    recommended_status: DecisionContractual | None = None
    reason_codes: list[str] = Field(default_factory=list)
    rationale: str = ""


class ReconciliacionFuncionalidadLLM(BaseModel):
    service_domains: list[ReconciliacionServiceDomainLLM] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    metadatos: MetadatosPrompt | None = None


# ── Entrada canónica del scoring determinista ────────────────────────────────
class ServiceDomainPropuestoLLM(BaseModel):
    """Registro de entrada del scoring determinista para UN Service Domain.

    Se materializa desde `EvaluacionCandidatoLLM` (`desde_evaluacion`) o directamente en tests.
    La `confianza` libre NO participa del score (`scoring_bian`); solo se conserva como `confianza_llm`.
    """

    service_domain: str = Field(
        description="Nombre EXACTO de un Service Domain del catálogo BIAN provisto (copia literal)."
    )
    rol_contractual: RolContractual = Field(
        description=(
            "OWNED_CONTRACT: la historia ADMINISTRA/EJECUTA esa capacidad y su ciclo de vida u objeto. "
            "CONSUMED_DEPENDENCY: la historia solo CONSULTA/VALIDA/CONSUME la capacidad como precondición. "
            "RELATED_NOT_OWNED: hay relación temática pero no es necesaria para implementar la historia."
        )
    )
    dependency_kind: DependencyKind | None = Field(
        default=None,
        description="Solo si rol_contractual = CONSUMED_DEPENDENCY: qué tipo de dependencia es.",
    )
    accion_objeto: str = Field(
        default="",
        description="Verbo + objeto de negocio de la historia que empata con la evidencia oficial del SD.",
    )
    match_action: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Rúbrica 0-3: empate del verbo de la historia con un action term de una operación oficial.",
    )
    match_service_role: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Rúbrica 0-3: qué tan directamente el verbo+objeto coincide con el Service Role del SD.",
    )
    match_objeto_negocio: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Rúbrica 0-3: alineación del objeto que ADMINISTRA la historia con el objeto/asset del SD.",
    )
    evidence_quality: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Rúbrica 0-3: qué tan concluyente es la evidencia oficial disponible para este candidato.",
    )
    ambiguity: NivelAmbiguedad = Field(
        default="NONE", description="Ambigüedad residual de la evaluación (NONE / LOW / HIGH)."
    )
    escenarios_hu: list[str] = Field(
        default_factory=list,
        description="Escenarios / criterios LITERALES de la historia que justifican el SD (cita corta).",
    )
    ownership_traceability: list[str] = Field(default_factory=list)
    dependency_traceability: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    justificacion: str = Field(
        default="",
        description="2-4 frases enlazando la capacidad concreta de la historia con el Service Role del SD.",
    )
    confianza: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confianza cruda del LLM. NO entra al score; solo se conserva como confianza_llm.",
    )

    @classmethod
    def desde_evaluacion(
        cls, ev: EvaluacionCandidatoLLM, *, service_domain_canonico: str
    ) -> ServiceDomainPropuestoLLM:
        """Proyecta la evaluación aislada de un candidato al registro de entrada del scoring."""
        es_owned = ev.rol_contractual == "OWNED_CONTRACT"
        escenarios = list(
            dict.fromkeys(
                [*ev.ownership_traceability, *ev.dependency_traceability] or ev.evidence_refs
            )
        )
        # confianza cruda derivada de las señales ordinales (NO decide nada; auditoría)
        cruda = round(
            (
                ev.match_action
                + ev.match_business_object
                + ev.match_service_role
                + ev.evidence_quality
            )
            / 12.0,
            4,
        )
        return cls(
            service_domain=service_domain_canonico,
            rol_contractual=ev.rol_contractual,
            dependency_kind=ev.dependency_kind if not es_owned else None,
            accion_objeto=ev.accion_objeto.strip() or ev.functional_object.strip(),
            match_action=ev.match_action,
            match_service_role=ev.match_service_role,
            match_objeto_negocio=ev.match_business_object,
            evidence_quality=ev.evidence_quality,
            ambiguity=ev.ambiguity,
            escenarios_hu=[s.strip() for s in escenarios if s and s.strip()],
            ownership_traceability=[
                s.strip() for s in ev.ownership_traceability if s and s.strip()
            ],
            dependency_traceability=[
                s.strip() for s in ev.dependency_traceability if s and s.strip()
            ],
            evidence_refs=[s.strip() for s in ev.evidence_refs if s and s.strip()],
            reason_codes=list(dict.fromkeys(ev.reason_codes)),
            assumptions=list(ev.assumptions),
            gaps=list(ev.gaps),
            blocking_codes=list(dict.fromkeys(ev.blocking_codes)),
            justificacion=ev.justification.strip(),
            confianza=cruda,
        )


class ServiceDomainOmitido(BaseModel):
    """Un Service Domain del catálogo que la evaluación LLM NO propuso pero cuyas señales
    funcionales sugieren revisar (segundo pase determinista, sin LLM)."""

    service_domain: str
    score_lexico: float = Field(ge=0.0, le=1.0)
    business_area: str | None = None
    business_domain: str | None = None
    rol_bian: str | None = None
    señales: list[str] = Field(
        default_factory=list, description="Tokens de la historia que dispararon la coincidencia."
    )


# ── Paso 2: salida estructurada del LLM (operaciones) ────────────────────────
class OperacionPropuestaLLM(BaseModel):
    """Una operación oficial que el LLM asigna a una historia dentro de un Service Domain directo."""

    service_domain: str = Field(
        description="Nombre exacto del Service Domain (de la lista provista)."
    )
    operation_id: str = Field(
        description="operationId EXACTO de la lista de operaciones provista para ese SD."
    )
    escenarios_hu: list[str] = Field(
        default_factory=list, description="Escenarios de la historia que esta operación implementa."
    )
    justificacion: str = Field(
        default="", description="1-2 frases: qué hace esta operación por la historia."
    )
    action_term: str = ""
    business_object: str = ""
    bq_seed: str = Field(
        default="",
        description="Fragmento único del use case (semilla BQ) que cubre esta operación.",
    )
    traceability: list[str] = Field(
        default_factory=list, description="HU-.../SC-.../BR-... que esta operación cubre."
    )
    evidence_refs: list[str] = Field(default_factory=list)
    datos_cubiertos: list[str] = Field(
        default_factory=list,
        description=(
            "Datos requeridos por la historia que esta operación cubre, citados por su NÚMERO o "
            "su texto literal de la lista `<datos_requeridos>` del prompt (lista cerrada: una "
            "cita que no resuelve contra ella no cuenta)."
        ),
    )
    reason_codes: list[str] = Field(default_factory=list)


# Vocabulario de verbos BIAN para operaciones de Control Record / Behavior Qualifier.
VerboBian = Literal[
    "Initiate",
    "Update",
    "Retrieve",
    "Control",
    "Request",
    "Execute",
    "Exchange",
    "Grant",
    "Register",
]


class BqPersonalizadoPropuestoLLM(BaseModel):
    """Propuesta de una operación NO oficial dentro de un Control Record o Behavior Qualifier
    YA EXISTENTE del Service Domain.

    Un Control Record no se puede editar: si una historia necesita un campo que ni el CR ni
    ningún BQ oficial exponen con NINGÚN verbo, se revisa el BOM del Service Domain (schemas de
    la Semantic API + modelo de clases del PUML). Solo si una clase del BOM tiene realmente ese
    campo -aunque sea una clase asociada, no el objeto raíz del CR- se puede proponer esta
    operación, citando la evidencia exacta. NUNCA crea un grupo/tag nuevo: siempre se añade un
    verbo nuevo dentro de un CR/BQ que YA aparece en `<operaciones_disponibles>` de ese Service
    Domain. Nunca es una operación oficial: el código la ancla por separado y queda pendiente de
    revisión BIAN.
    """

    service_domain: str = Field(
        description="Nombre exacto del Service Domain (de la lista provista)."
    )
    grupo_existente: str = Field(
        description=(
            "Nombre EXACTO de un Control Record o Behavior Qualifier YA EXISTENTE en "
            "<operaciones_disponibles> de ese Service Domain (copia literal del `grupo` de alguna "
            "operación provista) — NUNCA un grupo/tag nuevo. La operación propuesta se añade DENTRO "
            "de ese grupo, con un verbo distinto a los ya usados en él."
        )
    )
    verbo: VerboBian = Field(
        description="Verbo BIAN de la operación (define operationId = Verbo+NombreDelGrupoExistente)."
    )
    campo_no_cubierto: str = Field(
        description="Capacidad/campo que la historia necesita y que NINGUNA operación oficial (CR ni BQ) expone."
    )
    clase_bom: str = Field(
        description="Nombre EXACTO de una clase citada en schemas_bom o modelo_bom_puml que tiene ese campo."
    )
    atributo_bom: str = Field(
        default="",
        description="Nombre EXACTO del atributo/propiedad dentro de clase_bom que respalda el campo.",
    )
    escenarios_hu: list[str] = Field(default_factory=list)
    justificacion: str = Field(
        default="", description="Por qué el CR y los BQ oficiales NO cubren este campo."
    )
    reason_codes: list[str] = Field(default_factory=list)


class MapeoOperacionesLLM(BaseModel):
    """Salida estructurada del LLM para el paso 2 (todas las operaciones de una historia)."""

    operaciones: list[OperacionPropuestaLLM] = Field(default_factory=list)
    bq_personalizados: list[BqPersonalizadoPropuestoLLM] = Field(
        default_factory=list,
        description="Solo cuando ningún CR/BQ oficial cubre un campo Y el BOM del SD lo respalda.",
    )
    datos_no_cubiertos: list[str] = Field(
        default_factory=list,
        description=(
            "Datos requeridos que NINGUNA operación oficial de este Service Domain expone, "
            "citados contra la misma lista `<datos_requeridos>`. Declararlos es un resultado "
            "legítimo; callarlos no (ver `cobertura_datos_requeridos`)."
        ),
    )
    gaps: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    citas_descartadas: list[str] = Field(
        default_factory=list,
        description=(
            "Citas 'ServiceDomain/operationId' que el blindaje anti-alucinación del adaptador "
            "tiró por no resolver contra el catálogo real de ESE Service Domain. Antes solo "
            "quedaban en un `logger.warning`: si el modelo se inventaba TODAS las operaciones, el "
            "resultado era indistinguible de 'no propuso ninguna' y la corrida no lo reportaba."
        ),
    )
    metadatos: MetadatosPrompt | None = None


class BqPersonalizadoAplicado(BaseModel):
    """Una operación personalizada anclada a evidencia BOM real, DENTRO de un CR/BQ ya existente
    del Service Domain (nunca crea un grupo/tag nuevo). NUNCA es una operación oficial BIAN;
    requiere revisión/gobierno antes de tratarse como endpoint real. Vive separado de
    `operaciones_bian` / `selected_operations` para que nunca se confunda con lo oficial."""

    service_domain: str
    grupo_existente: str = Field(
        description="CR/BQ ya existente del Service Domain donde se añade la operación."
    )
    operation_id: str = Field(
        description="Verbo+NombreDelGrupoExistente, siguiendo la convención BIAN (p.ej. 'RegisterReference')."
    )
    verbo: str
    path_propuesto: str = Field(
        description="Path real de una operación existente de `grupo_existente`, con el verbo final reemplazado."
    )
    parent_control_record: str = ""
    campo_no_cubierto: str = ""
    clase_bom: str = ""
    atributo_bom: str = ""
    escenarios_hu: list[str] = Field(default_factory=list)
    justificacion: str = ""
    reason_codes: list[str] = Field(default_factory=list)
    estado: Literal["CUSTOM_BQ_CANDIDATE"] = "CUSTOM_BQ_CANDIDATE"


# ── Resultado ya clasificado y anclado a la evidencia local ──────────────────
class OperacionBianAplicada(BaseModel):
    """Una operación oficial asignada a la historia, anclada al catálogo local."""

    operation_id: str
    method: str
    path: str
    tipo: Literal["CR", "BQ"]
    grupo: str
    escenarios_hu: list[str] = Field(default_factory=list)
    justificacion: str = ""
    action_term: str = ""
    business_object: str = ""
    bq_seed: str = ""
    traceability: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    datos_cubiertos: list[str] = Field(
        default_factory=list,
        description=(
            "Datos requeridos de la historia que esta operación cubre, ya RESUELTOS contra "
            "`intencion.business_objects` (texto canónico, no la cita cruda del LLM)."
        ),
    )
    reason_codes: list[str] = Field(default_factory=list)


class ServiceDomainAsignado(BaseModel):
    """Un Service Domain ya clasificado y enriquecido con evidencia de docs/ (Service Landscape)."""

    service_domain: str = Field(
        description="Nombre canónico exacto tal cual aparece en el Service Landscape."
    )
    resolucion: Resolucion = Field(
        description="Cómo resolvió el nombre propuesto contra el catálogo BIAN R14."
    )
    rol_contractual: RolContractual
    dependency_kind: DependencyKind | None = None
    confianza: float = Field(ge=0.0, le=1.0)
    confianza_pct: int = Field(ge=0, le=100)
    confianza_llm: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza cruda del LLM antes de aplicar el tope por rol contractual.",
    )
    grupo: Grupo
    accion_objeto: str = ""
    escenarios_hu: list[str] = Field(default_factory=list)
    justificacion: str = Field(
        default="", description="Justificación acotada al contexto de la historia."
    )
    business_area: str | None = Field(
        default=None, description="Business Area BIAN R14 (jerarquía local)."
    )
    business_domain: str | None = Field(
        default=None, description="Business Domain BIAN R14 (jerarquía local)."
    )
    rol_bian: str | None = Field(
        default=None, description="Service Role del SD copiado del Service Landscape (evidencia)."
    )
    patron_funcional: str | None = Field(
        default=None, description="Functional Pattern del SD (Service Landscape)."
    )
    origen_candidato: OrigenCandidato = "llm"
    operaciones_bian: list[OperacionBianAplicada] = Field(
        default_factory=list,
        description="Solo SD directos con catálogo local: operaciones oficiales que implementan la historia.",
    )
    bq_personalizados_propuestos: list[BqPersonalizadoAplicado] = Field(
        default_factory=list,
        description="BQ NO oficiales propuestos por falta de cobertura CR/BQ, anclados a evidencia BOM real.",
    )
    evidencia_bian: EvidenciaBian = Field(default_factory=EvidenciaBian)
    desglose_score: DesgloseScore = Field(default_factory=DesgloseScore)
    decision_contractual: DecisionContractual = "UNRESOLVED"
    motivo_decision: MotivoDecision = "OUT_OF_SCOPE"
    ambiguity: NivelAmbiguedad = "NONE"
    observaciones_adversariales: list[str] = Field(default_factory=list)
    ownership_traceability: list[str] = Field(default_factory=list)
    dependency_traceability: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)


class DecisionServiceDomainConsolidada(BaseModel):
    service_domain: str
    decision: DecisionContractual
    motivo: MotivoDecision = "OUT_OF_SCOPE"
    contract_role: str
    functionality_role: str = ""
    grupo: Grupo
    score: float = Field(ge=0.0, le=1.0)
    historias: list[str] = Field(default_factory=list)
    supporting_stories: list[str] = Field(default_factory=list)
    contradicting_stories: list[str] = Field(default_factory=list)
    traceability: list[str] = Field(default_factory=list)
    ownership_traceability: list[str] = Field(default_factory=list)
    dependency_traceability: list[str] = Field(default_factory=list)
    selected_operations: list[str] = Field(default_factory=list)
    custom_bq_candidates: list[BqPersonalizadoAplicado] = Field(
        default_factory=list,
        description="BQ NO oficiales propuestos (evidencia BOM citada); requieren revisión BIAN, nunca 'selected'.",
    )
    reason_codes: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    evidence: EvidenciaBian = Field(default_factory=EvidenciaBian)
    rationale: str = ""


class ServiceDomainsDeHistoria(BaseModel):
    """Los Service Domains de una historia repartidos en 3 grupos por confianza (post-tope de rol)."""

    candidatos_directos: list[ServiceDomainAsignado] = Field(default_factory=list)
    candidatos_tentativos: list[ServiceDomainAsignado] = Field(default_factory=list)
    candidatos_descartados: list[ServiceDomainAsignado] = Field(default_factory=list)


class HistoriaConServiceDomains(BaseModel):
    """Resultado del mapeo para una historia."""

    archivo: str
    titulo: str
    razonamiento: str = ""
    capacidades_funcionales: list[str] = Field(default_factory=list)
    business_actions: list[str] = Field(default_factory=list)
    business_objects: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    external_dependencies: list[str] = Field(default_factory=list)
    traceability_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    blocking_codes: list[str] = Field(default_factory=list)
    intencion: IntencionHistoriaLLM = Field(default_factory=IntencionHistoriaLLM)
    # Vacío cuando el routing jerárquico está apagado: entonces el nodo de candidatos vio los 341.
    enrutamiento: EnrutamientoDominiosLLM = Field(default_factory=EnrutamientoDominiosLLM)
    service_domains_visibles: int = Field(
        default=0,
        description="Cuántos SD vio el nodo de candidatos (341 sin routing; los de los dominios elegidos con él).",
    )
    candidatos_por_clase: list[CandidatoClaseBom] = Field(
        default_factory=list,
        description="Service Domains que DEFINEN una clase del BOM que la historia necesita (nodo 2a determinista).",
    )
    revision_completitud: RevisionCompletitudLLM = Field(default_factory=RevisionCompletitudLLM)
    revision_adversarial: RevisionAdversarialLLM = Field(default_factory=RevisionAdversarialLLM)
    total_directos: int = 0
    total_tentativos: int = 0
    total_descartados: int = 0
    service_domains: ServiceDomainsDeHistoria = Field(default_factory=ServiceDomainsDeHistoria)
    service_domains_omitidos: list[ServiceDomainOmitido] = Field(
        default_factory=list,
        description="Candidatos que el LLM no propuso y que el segundo pase léxico marca para revisión.",
    )


class ResultadoMapeoHistorias(BaseModel):
    """Documento final: la funcionalidad macro y la lista de historias con sus Service Domains."""

    funcionalidad_macro: str
    detalle: str
    total_historias: int
    parametros: dict = Field(default_factory=dict)
    historias: list[HistoriaConServiceDomains] = Field(default_factory=list)
    service_domains_consolidados: list[DecisionServiceDomainConsolidada] = Field(
        default_factory=list
    )
    service_domains_omitidos: list[ServiceDomainOmitido] = Field(
        default_factory=list,
        description="Unión de los candidatos omitidos por HU (segundo pase léxico), a nivel de funcionalidad.",
    )
    reconciliacion: ReconciliacionFuncionalidadLLM = Field(
        default_factory=ReconciliacionFuncionalidadLLM
    )
    huellas_prompts: list[MetadatosPrompt] = Field(
        default_factory=list, description="Huella reproducible de cada llamada LLM del run."
    )
    incidencias: list[dict] = Field(default_factory=list)
    metricas: dict = Field(
        default_factory=dict,
        description="Fase 0 (observabilidad): candidate_drop_rate, ownership_conflict_rate, "
        "operation_grounding_rate y sus conteos crudos. Ver `_metricas` en el caso de uso.",
    )
