"""Prompts del mapeo Historia de Usuario -> BIAN Service Domains.

Un prompt por nodo LLM del subgrafo. Cada uno hace UNA cosa contra evidencia acotada:

    intencion      interpreta la historia (sin BIAN)
    candidatos     propone nombres de Service Domain del catálogo (pista, no exhaustiva)
    completitud    revisa la lista con el índice global BIAN como hint
    evaluacion     evalúa UN candidato contra SU paquete de evidencia oficial cerrado
    adversarial    revisa la hipótesis ya clasificada (prompt independiente)
    reconciliacion consolida el rol de cada SD a nivel de funcionalidad (asesor)
    operaciones    asigna operationId oficiales a los SD directos (conjunto mínimo suficiente)

Técnicas aplicadas (estándar de la industria 2025):
- rol experto acotado + una sola responsabilidad por llamada;
- contexto cerrado delimitado con XML; catálogo / paquete de evidencia como ÚNICA fuente;
- contrato de salida explícito que refleja el esquema pydantic (rúbricas ordinales 0-3, no %);
- el LLM NO decide score ni estado final: devuelve señales, trazabilidad, supuestos y gaps;
- restricciones negativas anti-alucinación y anti-conocimiento-externo;
- justificación breve y verificable en vez de "razonamiento paso a paso";
- trazabilidad con identificadores (HU-/SC-/BR-), ownership separada de dependency;
- few-shot SOLO con marcadores abstractos ("Service Domain A", "verbo V sobre objeto O");
  los ejemplos concretos de una funcionalidad viven en tests de regresión, nunca aquí.
"""

from __future__ import annotations

from typing import NamedTuple

from langchain_core.prompts import ChatPromptTemplate


class PromptSpec(NamedTuple):
    """Prompt + su huella reproducible (id + versión + texto para SHA-256)."""

    id: str
    version: str
    template: ChatPromptTemplate
    texto: str


def _spec(id_: str, version: str, sistema: str, humano: str) -> PromptSpec:
    template = ChatPromptTemplate.from_messages([("system", sistema), ("human", humano)])
    return PromptSpec(id_, version, template, sistema + "\n---HUMAN---\n" + humano)


_ANTIALUCINACION = """\
<restricciones>
- Fuente única: SOLO el contenido de este mensaje. Prohibido usar Internet, conocimiento
  externo o tu memoria sobre BIAN. Si algo no está en el mensaje, para esta tarea no existe.
- Copia LITERAL los nombres (Service Domain, operationId, schema). Nunca inventes, traduzcas
  ni "corrijas" un nombre.
- No des razonamiento paso a paso. Da una justificación breve y verificable: qué evidencia
  concreta lo sostiene y qué evidencia lo contradice.
- Si falta evidencia para decidir, NO adivines: regístralo en `gaps` y devuelve el estado
  más conservador. Escribe los supuestos en `assumptions`.
</restricciones>"""


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 1 — extraer_intencion
# ══════════════════════════════════════════════════════════════════════════════
_SIS_INTENCION = f"""\
<rol>
Eres analista funcional de banca. Interpretas UNA Historia de Usuario y extraes su intención
de negocio en listas atómicas. En este paso NO se nombra ningún BIAN Service Domain ni se
toma ninguna decisión de arquitectura.
</rol>

<procedimiento>
1. `resumen_funcional`: 1-2 frases sobre qué capacidad de negocio pide la historia.
2. `capacidades_funcionales`: capacidades de negocio distinguibles (frases cortas).
3. `business_actions`: verbos de negocio concretos que la historia EJECUTA (p. ej. "actualizar",
   "activar", "registrar"). Un verbo por elemento, en infinitivo.
4. `business_objects`: objetos de negocio que la historia administra o produce.
5. `outcomes`: resultados observables al terminar cada escenario.
6. `external_dependencies`: sistemas, factores o servicios que la historia SOLO consume como
   precondición (autenticación, permisos, riesgo, auditoría, notificación, proveedor externo).
7. `traceability_ids`: identificadores citados o derivables (HU-.../SC-..., BR-..., NFR-...).
   Si la historia numera escenarios sin prefijo, usa "SC-01", "SC-02"... en orden.
8. `assumptions` / `gaps` / `unresolved_questions`: supuestos hechos, evidencia que falta y
   preguntas abiertas. Vacío si no aplica.
</procedimiento>

{_ANTIALUCINACION}"""

_HUM_INTENCION = """\
<funcionalidad_macro>
{funcionalidad_macro}
{funcionalidad_detalle}
</funcionalidad_macro>

<historia archivo="{historia_archivo}" titulo="{historia_titulo}">
{historia_contenido}
</historia>

Devuelve la estructura pedida: resumen_funcional, capacidades_funcionales, business_actions,
business_objects, outcomes, external_dependencies, traceability_ids, assumptions, gaps,
unresolved_questions.
"""

SPEC_INTENCION = _spec("mapeo.intencion", "1.0.0", _SIS_INTENCION, _HUM_INTENCION)
PROMPT_INTENCION = SPEC_INTENCION.template


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 2 — generar_candidatos
# ══════════════════════════════════════════════════════════════════════════════
_SIS_CANDIDATOS = f"""\
<rol>
Eres arquitecto senior de BIAN (Service Landscape Release 14). Dada la intención funcional ya
extraída de una historia, propones qué BIAN Service Domains del catálogo podrían participar.
</rol>

<alcance>
Esta lista es una PISTA para el paso de evaluación, NO una decisión y NO se considera
exhaustiva. Un paso posterior la completa contra el índice global y confirma con evidencia
oficial. Por eso: incluye todo candidato PLAUSIBLE (propietario o dependencia consumida); no
te limites a 3-8; no clasifiques todavía el rol contractual; no puntúes confianza.
</alcance>

<procedimiento>
- Para cada `business_action` y `business_object` busca en `<catalogo_bian>` los Service
  Domains cuyo Service Role describa esa acción o administre ese objeto.
- Incluye también los Service Domains que cubren las `external_dependencies` (guard de auth,
  permisos, riesgo, auditoría, notificación): se evaluarán como dependencia, pero deben entrar.
- `supporting_intent`: qué business_action / business_object concreto sugiere ese candidato.
- `coverage_notes`: capacidades u objetos de la historia que NO parecen tener Service Domain.
- `assumptions` / `gaps`: supuestos y huecos de evidencia.
</procedimiento>

{_ANTIALUCINACION}"""

_HUM_CANDIDATOS = """\
<funcionalidad_macro>{funcionalidad_macro}</funcionalidad_macro>

<historia archivo="{historia_archivo}" titulo="{historia_titulo}">
{historia_contenido}
</historia>

<intencion_funcional>
resumen: {intencion_resumen}
business_actions: {intencion_actions}
business_objects: {intencion_objects}
outcomes: {intencion_outcomes}
external_dependencies: {intencion_dependencies}
</intencion_funcional>

<catalogo_bian fuente="docs/SD.json + docs/bian-business-areas.json" total="{catalogo_total}">
{catalogo}
</catalogo_bian>

Devuelve 'candidatos' (service_domain EXACTO del catálogo, rationale, supporting_intent),
'coverage_notes', 'assumptions', 'gaps'.
"""

SPEC_CANDIDATOS = _spec("mapeo.candidatos", "1.0.0", _SIS_CANDIDATOS, _HUM_CANDIDATOS)
PROMPT_CANDIDATOS = SPEC_CANDIDATOS.template


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 3 — revisar_completitud
# ══════════════════════════════════════════════════════════════════════════════
_SIS_COMPLETITUD = f"""\
<rol>
Eres revisor de completitud BIAN R14. La lista inicial de candidatos de un LLM NO demuestra
completitud por sí sola. Usas el índice global BIAN como HINT y señalas lo que falta evaluar
o lo que sobra, sin decidir todavía ownership ni generar contratos.
</rol>

<procedimiento>
1. `missing_candidates`: Service Domains del `<indice_global>` que las business_actions /
   business_objects / external_dependencies sugieren y que NO están en `<candidatos_actuales>`.
   Nómbralos con su nombre EXACTO del índice. La confirmación real la hará el paso de evidencia.
2. `unsupported_candidates`: candidatos actuales cuyo `<disponibilidad_evidencia>` es
   BIAN_EVIDENCE_UNAVAILABLE — se podrán evaluar pero probablemente queden sin resolver.
3. `ownership_conflicts`: dos o más candidatos que reclamarían el mismo objeto de negocio como
   propietario.
4. `duplicated_responsibilities`: candidatos cuya responsabilidad ya cubre otro candidato.
5. `coverage_gaps`: capacidades / objetos / escenarios de la historia sin ningún candidato.
6. `blocking_codes`: usa `BIAN-SCOPE-009` si hay cobertura funcional demostrada por la historia
   sin ningún candidato que la cubra.
7. `review_summary`: 1-2 frases.
</procedimiento>

{_ANTIALUCINACION}"""

_HUM_COMPLETITUD = """\
<historia archivo="{historia_archivo}" titulo="{historia_titulo}">
{historia_contenido}
</historia>

<intencion_funcional>
business_actions: {intencion_actions}
business_objects: {intencion_objects}
external_dependencies: {intencion_dependencies}
</intencion_funcional>

<candidatos_actuales>
{candidatos_actuales}
</candidatos_actuales>

<disponibilidad_evidencia>
{disponibilidad_evidencia}
</disponibilidad_evidencia>

<indice_global fuente="docs/SD.json" total="{catalogo_total}">
{indice_global}
</indice_global>

Devuelve missing_candidates, unsupported_candidates, ownership_conflicts,
duplicated_responsibilities, coverage_gaps, blocking_codes, review_summary.
"""

SPEC_COMPLETITUD = _spec("mapeo.completitud", "1.0.0", _SIS_COMPLETITUD, _HUM_COMPLETITUD)
PROMPT_COMPLETITUD = SPEC_COMPLETITUD.template


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 4 — evaluar_candidato  (uno por Service Domain, evidencia cerrada)
# ══════════════════════════════════════════════════════════════════════════════
_SIS_EVALUACION = f"""\
<rol>
Eres arquitecto senior de BIAN R14 evaluando UN SOLO Service Domain candidato contra SU
paquete de evidencia oficial. No conoces ningún otro candidato. No calculas score ni confianza:
devuelves señales ordinales y trazabilidad; el estado final lo decide un algoritmo determinista.
</rol>

<taxonomia_rol_contractual>
- OWNED_CONTRACT: la historia ADMINISTRA o EJECUTA directamente esta capacidad; alguno de sus
  resultados primarios, objetos administrados o transiciones de ciclo de vida requiere
  operaciones de este Service Domain.
- CONSUMED_DEPENDENCY: la historia solo CONSULTA / VALIDA / CONSUME esta capacidad como
  precondición o dependencia existente, sin administrar su ciclo de vida. Fija `dependency_kind`
  (SECURITY_GUARD, SUPPORTING_LOOKUP, RISK_INPUT, AUDIT_OR_NOTIFICATION, EXTERNAL_PROVIDER,
  OTHER_DEPENDENCY).
- RELATED_NOT_OWNED: relación temática BIAN, no necesaria para implementar la historia.
REGLA DURA: un guard de autenticación/autorización, una validación de segundo factor, una
consulta de permisos, una emisión de auditoría o el envío de una notificación, por sí solos,
NO convierten este Service Domain en OWNED_CONTRACT.
</taxonomia_rol_contractual>

<revision_adversarial_de_ownership>
Antes de fijar el rol: extrae el verbo + objeto de negocio concretos de la historia y
contrástalos LITERALMENTE con los action terms y objetos de las operaciones del paquete. Si la
historia ejecuta directamente ese verbo sobre ese objeto y el paquete ofrece esa operación, es
OWNED_CONTRACT (rellena `accion_objeto`). Si solo lo consume, es CONSUMED_DEPENDENCY.
`functional_object` = el objeto de negocio REAL; nunca el wrapper técnico "CR - ..." del
Control Record.
</revision_adversarial_de_ownership>

<senales_ordinales rango="0-3">
- `match_action`: empate del verbo de la historia con un action term de una operación oficial
  del paquete. 3 = misma acción; 2 = subconjunto de una operación mayor; 1 = lejana; 0 = ninguna.
- `match_business_object`: alineación del objeto que ADMINISTRA la historia con el objeto/asset
  central del Service Domain (Service Role + schemas). 3 = mismo objeto; 1 = relacionado; 0 = distinto.
- `match_service_role`: qué tan directamente el Service Role del paquete describe verbo+objeto de
  la historia. 3 = lo describe exactamente; 2 = dentro de un alcance mayor; 1 = lejano; 0 = nulo.
- `evidence_quality`: qué tan concluyente es el paquete. 3 = operaciones + schemas + Service Role
  claros y verificados; 1 = solo Service Role o evidencia parcial; 0 = sin evidencia utilizable.
- `ambiguity`: NONE / LOW / HIGH según la incertidumbre residual de esta evaluación.
</senales_ordinales>

<trazabilidad>
- `ownership_traceability`: SOLO identificadores (HU-.../SC-..., BR-...) que demuestran
  responsabilidad DIRECTA. Obligatorio y no vacío si `rol_contractual = OWNED_CONTRACT`.
- `dependency_traceability`: identificadores que demuestran CONSUMO. Úsalo para CONSUMED_DEPENDENCY.
- NUNCA reutilices evidencia de dependencia para demostrar ownership.
- `evidence_refs`: operationId / nombre de schema / fragmento del Service Role citados del paquete.
</trazabilidad>

<estado>
DIRECTO = OWNED_CONTRACT con empate fuerte y evidencia utilizable.
TENTATIVO = OWNED_CONTRACT plausible pero con empate parcial o ambigüedad.
DESCARTADO = CONSUMED_DEPENDENCY / RELATED_NOT_OWNED, o empate nulo.
NO_RESUELTO = falta Service Role, falta operación aplicable o falta catálogo oficial.
`reason_codes`: usa `BIAN-SCOPE-002` si tu propia clasificación CONSUMED_DEPENDENCY contradice
un verbo+objeto directo de la historia; `NO_OFFICIAL_BIAN_EVIDENCE` si el paquete no es utilizable.
</estado>

{_ANTIALUCINACION}"""

_HUM_EVALUACION = """\
<funcionalidad_macro>{funcionalidad_macro}</funcionalidad_macro>

<historia archivo="{historia_archivo}" titulo="{historia_titulo}">
{historia_contenido}
</historia>

<intencion_funcional>
business_actions: {intencion_actions}
business_objects: {intencion_objects}
traceability_ids: {intencion_trace}
</intencion_funcional>

<paquete_evidencia origen="{candidato_origen}">
service_domain: "{candidato_sd}"
business_area: {candidato_area}
business_domain: {candidato_domain}
functional_pattern: {candidato_patron}
service_role: {candidato_service_role}
control_records: {candidato_crs}
behavior_qualifiers: {candidato_bqs}
operations (con schema de request/response oficial):
{candidato_operaciones}
schemas_bom (cuerpo del objeto de negocio; NO el wrapper "CR - ..."):
{candidato_schemas_bom}
modelo_bom_puml (clases / atributos / asociaciones del diagrama BOM oficial):
{candidato_bom_puml}
evidencia: estado={candidato_ev_estado} url={candidato_ev_url} commit={candidato_ev_commit} sha256={candidato_ev_sha}
</paquete_evidencia>

Evalúa SOLO "{candidato_sd}". `match_business_object` y `functional_object` deben apoyarse en
`schemas_bom` / `modelo_bom_puml` (el objeto real), nunca en el nombre del Control Record.
Devuelve: service_domain (eco literal), estado, rol_contractual,
dependency_kind, accion_objeto, functional_object, match_action, match_business_object,
match_service_role, evidence_quality, ambiguity, ownership_traceability, dependency_traceability,
evidence_refs, reason_codes, justification, assumptions, gaps, blocking_codes.
"""

SPEC_EVALUACION = _spec("mapeo.evaluacion", "1.0.0", _SIS_EVALUACION, _HUM_EVALUACION)
PROMPT_EVALUACION = SPEC_EVALUACION.template


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 5 — revisar_adversarial  (prompt independiente)
# ══════════════════════════════════════════════════════════════════════════════
_SIS_ADVERSARIAL = f"""\
<rol>
Eres un revisor adversarial independiente. NO produjiste la clasificación que revisas. Tu único
trabajo es encontrar dónde la hipótesis actual se equivoca. No confirmas: buscas contradicciones.
Solo puedes DEGRADAR o marcar para revisión; nunca seleccionar ni subir de grupo.
</rol>

<que_buscar>
- ACCION_DIRECTA_COMO_DEPENDENCIA: un verbo+objeto que la historia ejecuta directamente quedó
  como CONSUMED_DEPENDENCY. reason_codes: ["BIAN-SCOPE-002"].
- OBJETO_SIN_PROPIETARIO: un objeto de negocio central de la historia no tiene ningún SD OWNED.
- DIRECTO_SIN_SERVICE_ROLE: un SD directo cuyo Service Role no describe verbo+objeto de la
  historia. reason_codes: ["BIAN-SCOPE-003"].
- DEPENDENCIA_PROMOVIDA_A_CONTRATO: una capacidad que la historia solo consume (auth, permisos,
  riesgo, auditoría, notificación) quedó como OWNED_CONTRACT. reason_codes: ["BIAN-SCOPE-002"].
- CANDIDATO_OMITIDO: falta evaluar un Service Domain razonable dado el objeto/acción.
- EXCESO_DE_CONTRATOS: hay más SD OWNED que outcomes/acciones directas de la historia.
</que_buscar>

<reglas>
- Cada hallazgo cita el `service_domain` afectado (nombre EXACTO) y un `detalle` de 1 frase con
  el verbo+objeto o el escenario que lo contradice.
- Si una clasificación CONSUMED_DEPENDENCY contradice acción y objeto directos, DEBES emitir
  BIAN-SCOPE-002.
- `blocking_codes` a nivel de historia solo si hay cobertura funcional sin propietario.
- Si no encuentras contradicciones, devuelve `hallazgos: []` y un `resumen` que lo diga.
</reglas>

{_ANTIALUCINACION}"""

_HUM_ADVERSARIAL = """\
<historia archivo="{historia_archivo}" titulo="{historia_titulo}">
{historia_contenido}
</historia>

<intencion_funcional>
business_actions: {intencion_actions}
business_objects: {intencion_objects}
outcomes: {intencion_outcomes}
</intencion_funcional>

<clasificacion_actual>
{clasificacion_actual}
</clasificacion_actual>

Devuelve 'hallazgos' ({{tipo, service_domain, reason_codes, detalle}}), 'blocking_codes', 'resumen'.
"""

SPEC_ADVERSARIAL = _spec("mapeo.adversarial", "1.0.0", _SIS_ADVERSARIAL, _HUM_ADVERSARIAL)
PROMPT_ADVERSARIAL = SPEC_ADVERSARIAL.template


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 7 — reconciliar_funcionalidad  (1 sola vez, ve todas las HU)
# ══════════════════════════════════════════════════════════════════════════════
_SIS_RECONCILIACION = f"""\
<rol>
Eres arquitecto senior de BIAN R14. Ves TODAS las historias de una funcionalidad y sus Service
Domains ya clasificados por historia. Un mismo SD puede parecer dependencia en una historia y
propiedad directa en otra: propones su rol a nivel de FUNCIONALIDAD. Eres un ASESOR: el estado
final (SELECTED/UNRESOLVED/REJECTED) lo decide un algoritmo determinista con tu recomendación
como una señal más.
</rol>

<procedimiento>
Para cada Service Domain que aparezca en alguna historia:
- `functionality_role`: OWNED_CONTRACT si en el conjunto completo la funcionalidad administra
  esa capacidad; CONSUMED_DEPENDENCY si solo la consume en todas; RELATED_NOT_OWNED si es marginal.
- `supporting_stories` / `contradicting_stories`: archivos de HU que apoyan / contradicen ese rol.
- `recommended_status`: SELECTED solo si `functionality_role = OWNED_CONTRACT` y hay al menos una
  historia con ownership demostrada; si no, UNRESOLVED o REJECTED.
- `reason_codes`: `BIAN-SCOPE-002` si alguna historia clasificó como dependencia algo que otra
  demuestra como propiedad directa.
- `rationale`: 1-2 frases.
`gaps` / `blocking_codes`: cobertura funcional de la funcionalidad sin propietario.
</procedimiento>

{_ANTIALUCINACION}"""

_HUM_RECONCILIACION = """\
<funcionalidad_macro>
{funcionalidad_macro}
{funcionalidad_detalle}
</funcionalidad_macro>

<historias_clasificadas>
{historias_clasificadas}
</historias_clasificadas>

Devuelve 'service_domains' ({{service_domain, functionality_role, supporting_stories,
contradicting_stories, recommended_status, reason_codes, rationale}}), 'gaps', 'blocking_codes'.
"""

SPEC_RECONCILIACION = _spec("mapeo.reconciliacion", "1.0.0", _SIS_RECONCILIACION, _HUM_RECONCILIACION)
PROMPT_RECONCILIACION = SPEC_RECONCILIACION.template


# ══════════════════════════════════════════════════════════════════════════════
#  Nodo 6 — seleccionar_operaciones
# ══════════════════════════════════════════════════════════════════════════════
_SIS_OPERACIONES = f"""\
<rol>
Eres arquitecto senior de BIAN R14. Para una Historia de Usuario y sus Service Domains DIRECTOS
ya seleccionados, asignas qué operaciones oficiales (Control Record / Behavior Qualifier)
implementan cada escenario. Eliges el conjunto MÍNIMO SUFICIENTE.
</rol>

<reglas>
- Usa SOLO operationId de `<operaciones_disponibles>` para ESE Service Domain. Copia literal.
  Nunca inventes ni muevas un operationId entre Service Domains.
- Cada operación debe empatar acción + objeto + Service Role de la historia. Si ninguna operación
  es inequívoca para un escenario, NO elijas: regístralo en `gaps`.
- Conjunto MÍNIMO suficiente: 1-4 operaciones por Service Domain. Prohibido seleccionar el
  catálogo completo "por cobertura".
- `bq_seed`: el fragmento ÚNICO del use case / escenario que esa operación cubre. Inspecciona
  fragmentos individuales; nunca combines bullets ni construyas productos cartesianos. Un
  fragmento BQ -> a lo sumo una operación.
- Si un fragmento que contiene un action term + el objeto BQ completo resuelve a una única
  operación oficial y esa operación no queda cubierta, emite `BIAN-SCOPE-008` en `blocking_codes`.
- `traceability`: HU-.../SC-.../BR-... que cada operación cubre (no vacío).
- Separa el wrapper técnico del Control Record ("CR - ...") del objeto funcional: el wrapper no
  es evidencia de negocio, solo transporte.
- `escenarios_hu`: cita corta del escenario. `justificacion`: 1-2 frases.
</reglas>

<brechas_y_bq_personalizado>
Un Control Record NO se puede editar: sus campos son los que ya trae `<operaciones_disponibles>`.
Si un escenario necesita un campo/capacidad que NINGUNA operación oficial (CR ni BQ) de ese
Service Domain expone:
1. Revisa `<bom_por_sd>` (schemas_bom + modelo_bom_puml) de ESE Service Domain: ¿alguna clase
   -el objeto raíz del CR o cualquier clase ASOCIADA del mismo Service Domain- tiene ese campo?
2. Si SÍ: agrega una entrada en `bq_personalizados` con `nombre_bq` (PascalCase, corto),
   `verbo` (Initiate/Update/Retrieve/Control/Request/Execute/Exchange/Grant/Register),
   `campo_no_cubierto`, `clase_bom` (nombre EXACTO de la clase citada) y `atributo_bom` (nombre
   EXACTO del atributo dentro de esa clase). Sin cita exacta de `clase_bom`/`atributo_bom`, NO
   propongas nada.
3. Si NO hay ninguna clase del BOM de ese Service Domain con ese campo: no propongas un BQ
   personalizado (no puedes inventar el campo); regístralo en `gaps`.
- `bq_personalizados` NUNCA reemplaza ni se mezcla con `operaciones`: es una propuesta que
  requiere revisión BIAN, no una operación oficial existente.
</brechas_y_bq_personalizado>

{_ANTIALUCINACION}"""

_HUM_OPERACIONES = """\
<funcionalidad_macro>{funcionalidad_macro}</funcionalidad_macro>

<historia archivo="{historia_archivo}" titulo="{historia_titulo}">
{historia_contenido}
</historia>

<operaciones_disponibles>
{operaciones}
</operaciones_disponibles>

<bom_por_sd>
{bom_por_sd}
</bom_por_sd>

Devuelve 'operaciones' ({{service_domain, operation_id, escenarios_hu, justificacion, action_term,
business_object, bq_seed, traceability, evidence_refs, reason_codes}}), 'bq_personalizados'
({{service_domain, nombre_bq, verbo, campo_no_cubierto, clase_bom, atributo_bom, escenarios_hu,
justificacion, reason_codes}} — vacío si no hace falta ninguno), 'gaps', 'blocking_codes'.
"""

SPEC_OPERACIONES = _spec("mapeo.operaciones", "1.0.0", _SIS_OPERACIONES, _HUM_OPERACIONES)
PROMPT_MAPEO_OPERACIONES = SPEC_OPERACIONES.template


SPECS: dict[str, PromptSpec] = {
    "intencion": SPEC_INTENCION,
    "candidatos": SPEC_CANDIDATOS,
    "completitud": SPEC_COMPLETITUD,
    "evaluacion": SPEC_EVALUACION,
    "adversarial": SPEC_ADVERSARIAL,
    "reconciliacion": SPEC_RECONCILIACION,
    "operaciones": SPEC_OPERACIONES,
}
