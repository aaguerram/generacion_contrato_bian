"""Regla de dominio: ancla los Service Domains propuestos por el LLM a la evidencia local y
los reparte en dos ejes: aplicabilidad semantica (grupo) y decision contractual (motivo).

Pasos deterministas (stdlib + pydantic + dominio, sin frameworks, sin API):

1. **Resolución** de cada nombre propuesto contra el catálogo BIAN R14 (`SD.json`, 341 SD):
   - match normalizado exacto            -> MATCH   (nombre canónico del catálogo)
   - si no, subcadena normalizada única  -> MATCH   (se recupera el nombre canónico)
   - varias coincidencias                -> AMBIGUOUS  (se descarta, se registra el motivo)
   - ninguna                             -> NOT_FOUND  (se descarta)
2. **Anclaje**: nombre canónico + Service Role + Functional Pattern + Business Area/Domain
   se copian DESDE el catálogo, nunca del LLM.
3. **Score determinista** (`scoring_bian`): correspondencia con la evidencia oficial (Service
   Role, operaciones, schemas), rúbrica estructurada 0-3, ownership, trazabilidad y jerarquía.
   La confianza libre del LLM NO entra en el score (solo se conserva como `confianza_llm`).
4. **Tope por rol contractual**: un SD cuyo `rol_contractual` no es `OWNED_CONTRACT`
   **nunca** cae en `candidatos_directos`.
5. **Dos ejes de decisión**:
   - grupo (aplicabilidad): `directo` (>= umbral_directo) / `tentativo` / `descartado`.
   - decision_contractual: `SELECTED` / `UNRESOLVED` / `REJECTED` + `motivo_decision`.
     Evidencia BOM ausente NO degrada a rechazo semántico salvo que el score ya sea de por sí
     `descartado` (score < umbral_tentativo): entonces es `OUT_OF_SCOPE`. Si el score alcanza la
     banda tentativa pero falta evidencia -> `UNRESOLVED / NO_OFFICIAL_BIAN_EVIDENCE`.
6. **Dedup** por SD (se queda con la mayor confianza cruda) y orden por confianza desc.
7. **Promoción de ownership** (`determinar_promociones` / `propuestos_promovidos`): el revisor
   adversarial puede señalar que una acción directa de la historia quedó mal clasificada como
   `CONSUMED_DEPENDENCY`. El código nunca confía en esa sola señal: solo promueve a
   `OWNED_CONTRACT` cuando, ADEMÁS, `dependency_kind` es del tipo que significa "este SD es el
   resultado/salida que la historia produce" (no una precondición), hay trazabilidad de
   escenarios y evidencia de operación oficial citada, y el propio revisor no contradijo el
   Service Role para el mismo SD. Es simétrico a la degradación (`_DEGRADA_SELECTED`): ninguna de
   las dos la decide el LLM solo, ambas son reglas deterministas sobre lo que el LLM reportó.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.dominio.historias import (
    DependencyKind,
    DesgloseScore,
    EvidenciaBian,
    RevisionAdversarialLLM,
    ServiceDomainAsignado,
    ServiceDomainPropuestoLLM,
    ServiceDomainsDeHistoria,
)
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar
from src.dominio.scoring_bian import calcular_score

_EPS = 0.001  # margen para dejar un SD topado justo por debajo del umbral directo


@dataclass(frozen=True)
class UmbralesMapeo:
    directo: float = 0.90  # confianza >= directo  -> candidato directo
    tentativo: float = 0.63  # tentativo <= confianza < directo -> tentativo; menos -> descartado

    def __post_init__(self) -> None:
        if not (0.0 <= self.tentativo <= self.directo <= 1.0):
            raise ValueError(
                f"Umbrales de mapeo inválidos: tentativo={self.tentativo}, directo={self.directo}"
            )

    def grupo_de(self, confianza: float) -> str:
        if confianza >= self.directo:
            return "directo"
        if confianza >= self.tentativo:
            return "tentativo"
        return "descartado"


def resolver_nombre_sd(
    nombre: str, indice: dict[str, EntradaCatalogo]
) -> tuple[EntradaCatalogo | None, str]:
    """Resuelve `nombre` contra el índice normalizado del catálogo. Devuelve (entrada, resolución)."""
    clave = normalizar(nombre)
    if not clave:
        return None, "NOT_FOUND"
    exacto = indice.get(clave)
    if exacto is not None:
        return exacto, "MATCH"
    contiene = [
        entrada
        for k, entrada in indice.items()
        if len(clave) >= 4 and (clave in k or k in clave)
    ]
    if len(contiene) == 1:
        return contiene[0], "MATCH"
    if len(contiene) > 1:
        return None, "AMBIGUOUS"
    return None, "NOT_FOUND"


def _decidir(
    *,
    es_owned: bool,
    rol_contractual: str,
    grupo: str,
    scoring_activo: bool,
    evidencia_faltante: bool,
) -> tuple[str, str]:
    """(decision_contractual, motivo_decision) a partir de los dos ejes. Determinista."""
    if not es_owned:
        # una dependencia consumida / relación temática NUNCA genera contrato: contractualmente
        # es REJECTED. El grupo/score sigue reflejando lo requerida que está la dependencia.
        motivo = "CONSUMED_DEPENDENCY" if rol_contractual == "CONSUMED_DEPENDENCY" else "RELATED_NOT_OWNED"
        return "REJECTED", motivo

    if grupo == "descartado":
        # score por debajo de la banda tentativa: no aplica, aunque falte evidencia oficial
        return "REJECTED", "OUT_OF_SCOPE"

    if scoring_activo and evidencia_faltante:
        # score suficiente pero sin BOM oficial verificable -> nunca "no aplica"
        return "UNRESOLVED", "NO_OFFICIAL_BIAN_EVIDENCE"

    if grupo == "directo":
        return "SELECTED", "OWNED_SELECTED"

    return "UNRESOLVED", "TENTATIVE_SCORE"


def clasificar_service_domains(
    propuestos: list[ServiceDomainPropuestoLLM],
    catalogo: list[EntradaCatalogo],
    umbrales: UmbralesMapeo,
    *,
    operaciones_por_sd: dict[str, list] | None = None,
    evidencias_por_sd: dict | None = None,
    esquemas_por_sd: dict[str, list[str]] | None = None,
    origen_por_sd: dict[str, str] | None = None,
) -> ServiceDomainsDeHistoria:
    """Convierte la lista cruda del LLM en los 3 grupos, anclando cada SD a la evidencia local."""
    indice = {normalizar(e.service_domain): e for e in catalogo}

    mejor: dict[str, tuple[ServiceDomainPropuestoLLM, EntradaCatalogo]] = {}
    for p in propuestos:
        entrada, resolucion = resolver_nombre_sd(p.service_domain, indice)
        if entrada is None or resolucion != "MATCH":
            continue  # AMBIGUOUS / NOT_FOUND -> fuera (anti-alucinación)
        clave = entrada.service_domain
        confianza_llm = max(0.0, min(1.0, float(p.confianza)))
        actual = mejor.get(clave)
        if actual is None or confianza_llm > float(actual[0].confianza):
            mejor[clave] = (p.model_copy(update={"confianza": confianza_llm}), entrada)

    scoring_activo = evidencias_por_sd is not None
    tope_no_owned = max(0.0, umbrales.directo - _EPS)
    asignados: list[ServiceDomainAsignado] = []
    for clave, (p, entrada) in mejor.items():
        confianza_llm = float(p.confianza)
        es_owned = p.rol_contractual == "OWNED_CONTRACT"
        evidencia = (evidencias_por_sd or {}).get(clave)
        operaciones = (operaciones_por_sd or {}).get(clave, [])
        esquemas = (esquemas_por_sd or {}).get(clave, [])

        if evidencia is not None:
            desglose, observaciones = calcular_score(p, entrada, operaciones, evidencia, esquemas)
            confianza = desglose.total
        else:
            desglose, observaciones = DesgloseScore(total=confianza_llm), []
            evidencia = EvidenciaBian()
            confianza = confianza_llm

        evidencia_faltante = scoring_activo and evidencia.estado == "BIAN_EVIDENCE_UNAVAILABLE"
        confianza = confianza if es_owned else min(confianza, tope_no_owned)
        if evidencia_faltante:
            confianza = min(confianza, tope_no_owned)

        grupo = umbrales.grupo_de(confianza)
        decision, motivo = _decidir(
            es_owned=es_owned,
            rol_contractual=p.rol_contractual,
            grupo=grupo,
            scoring_activo=scoring_activo,
            evidencia_faltante=evidencia_faltante,
        )

        asignados.append(
            ServiceDomainAsignado(
                service_domain=entrada.service_domain,
                resolucion="MATCH",
                rol_contractual=p.rol_contractual,
                dependency_kind=p.dependency_kind if not es_owned else None,
                confianza=round(confianza, 4),
                confianza_pct=round(confianza * 100),
                confianza_llm=round(confianza_llm, 4),
                grupo=grupo,  # type: ignore[arg-type]
                accion_objeto=p.accion_objeto.strip(),
                escenarios_hu=[s.strip() for s in p.escenarios_hu if s and s.strip()],
                justificacion=p.justificacion.strip(),
                business_area=entrada.business_area,
                business_domain=entrada.business_domain,
                rol_bian=entrada.service_role,
                patron_funcional=entrada.functional_pattern,
                origen_candidato=(origen_por_sd or {}).get(clave, "llm"),  # type: ignore[arg-type]
                evidencia_bian=evidencia,
                desglose_score=desglose.model_copy(update={"total": round(confianza, 4)}),
                decision_contractual=decision,  # type: ignore[arg-type]
                motivo_decision=motivo,  # type: ignore[arg-type]
                ambiguity=p.ambiguity,
                observaciones_adversariales=observaciones,
                ownership_traceability=[s.strip() for s in p.ownership_traceability if s and s.strip()],
                dependency_traceability=[s.strip() for s in p.dependency_traceability if s and s.strip()],
                evidence_refs=[s.strip() for s in p.evidence_refs if s and s.strip()],
                reason_codes=list(dict.fromkeys(p.reason_codes)),
                assumptions=list(p.assumptions),
                gaps=list(p.gaps),
                blocking_codes=list(dict.fromkeys(p.blocking_codes)),
            )
        )

    def _orden(x: ServiceDomainAsignado) -> tuple[float, str]:
        return (-x.confianza, x.service_domain.lower())

    return ServiceDomainsDeHistoria(
        candidatos_directos=sorted((a for a in asignados if a.grupo == "directo"), key=_orden),
        candidatos_tentativos=sorted((a for a in asignados if a.grupo == "tentativo"), key=_orden),
        candidatos_descartados=sorted((a for a in asignados if a.grupo == "descartado"), key=_orden),
    )


# Hallazgos adversariales que degradan una decisión (el LLM nunca promueve, solo el código decide).
# NOTA: "ACCION_DIRECTA_COMO_DEPENDENCIA" NO degrada -> significa lo opuesto (una acción directa
# quedó como dependencia) y solo puede PROMOVER, nunca degradar; ver `determinar_promociones`.
_DEGRADA_SELECTED = {
    "DEPENDENCIA_PROMOVIDA_A_CONTRATO": "BIAN-SCOPE-002",
    "DIRECTO_SIN_SERVICE_ROLE": "BIAN-SCOPE-003",
}

# `dependency_kind` que puede indicar que el SD produce el RESULTADO que la historia ejecuta
# (p.ej. una notificación es la salida directa), en vez de ser una precondición consultada antes
# de actuar (SECURITY_GUARD/SUPPORTING_LOOKUP/EXTERNAL_PROVIDER/RISK_INPUT). Solo estos tipos son
# elegibles para promoción — no cualquier `CONSUMED_DEPENDENCY` con un hallazgo adversarial.
_PROMOCION_DEPENDENCY_KINDS: frozenset[DependencyKind] = frozenset({"AUDIT_OR_NOTIFICATION"})

PROMOTED_REASON_CODE = "OWNERSHIP_PROMOTED_BY_ADVERSARIAL"


def determinar_promociones(
    propuestos_por_sd: dict[str, ServiceDomainPropuestoLLM],
    revision: RevisionAdversarialLLM,
) -> frozenset[str]:
    """Nombres normalizados de SD que pasan de `CONSUMED_DEPENDENCY` a `OWNED_CONTRACT`.

    Exige TODO lo siguiente (genérico, sin nombrar ningún Service Domain):
    - un hallazgo `ACCION_DIRECTA_COMO_DEPENDENCIA` para ese SD, Y ningún `DIRECTO_SIN_SERVICE_ROLE`
      para el mismo SD (el propio revisor no contradice el Service Role);
    - `rol_contractual == CONSUMED_DEPENDENCY` con `dependency_kind` en `_PROMOCION_DEPENDENCY_KINDS`
      (el SD es la salida/resultado que la historia produce, no una precondición consultada);
    - trazabilidad a escenarios (`dependency_traceability`) y al menos una cita de evidencia
      (`evidence_refs`, típicamente una operación oficial) — sin esto, no hay base determinista.
    """
    hallazgos_por_sd: dict[str, list[str]] = {}
    for h in revision.hallazgos:
        if h.service_domain:
            hallazgos_por_sd.setdefault(normalizar(h.service_domain), []).append(h.tipo)

    promovidos: set[str] = set()
    for clave, tipos in hallazgos_por_sd.items():
        if "ACCION_DIRECTA_COMO_DEPENDENCIA" not in tipos or "DIRECTO_SIN_SERVICE_ROLE" in tipos:
            continue
        p = propuestos_por_sd.get(clave)
        if (
            p is not None
            and p.rol_contractual == "CONSUMED_DEPENDENCY"
            and p.dependency_kind in _PROMOCION_DEPENDENCY_KINDS
            and p.dependency_traceability
            and p.evidence_refs
        ):
            promovidos.add(clave)
    return frozenset(promovidos)


def propuestos_promovidos(
    propuestos_por_sd: dict[str, ServiceDomainPropuestoLLM], promovidos: frozenset[str]
) -> dict[str, ServiceDomainPropuestoLLM]:
    """Copia `propuestos_por_sd` con los SD de `promovidos` reescritos a `OWNED_CONTRACT`.

    La trazabilidad que el LLM etiquetó como "consumo" pasa a ser trazabilidad de ownership: ya
    está probado (por la regla de `determinar_promociones`) que es responsabilidad directa, no
    una precondición. El llamador debe recalcular score/decisión con `clasificar_service_domains`
    sobre el resultado — este helper solo reescribe la entrada, nunca el score.
    """
    salida = dict(propuestos_por_sd)
    for clave in promovidos:
        p = salida.get(clave)
        if p is None:
            continue
        salida[clave] = p.model_copy(update={
            "rol_contractual": "OWNED_CONTRACT",
            "dependency_kind": None,
            "ownership_traceability": list(dict.fromkeys([*p.ownership_traceability, *p.dependency_traceability])),
            "dependency_traceability": [],
        })
    return salida


def candidatos_operacion_elegibles(grupos: ServiceDomainsDeHistoria) -> list[ServiceDomainAsignado]:
    """SD con base suficiente para intentar anclar operaciones oficiales: `OWNED_CONTRACT`,
    directo O tentativo. Desacopla la selección de operaciones del umbral de confianza directa
    (0.90): un SD correctamente identificado como propietario pero con confianza tentativa sigue
    teniendo una operación oficial real que documentar para revisión — no depende de que la
    historia por sí sola alcance el umbral de "directo". Los descartados no entran: ahí el score
    es demasiado bajo o el rol no es de ownership, no hay base para anclar nada. Nunca incluye
    `CONSUMED_DEPENDENCY`/`RELATED_NOT_OWNED`: eso seguiría mezclando "operación referenciada" con
    "operación contratada", que es exactamente lo que este desacople evita."""
    return [
        a for a in (*grupos.candidatos_directos, *grupos.candidatos_tentativos)
        if a.rol_contractual == "OWNED_CONTRACT"
    ]


def aplicar_hallazgos_adversariales(
    grupos: ServiceDomainsDeHistoria,
    revision: RevisionAdversarialLLM,
    *,
    promovidos: frozenset[str] = frozenset(),
) -> tuple[ServiceDomainsDeHistoria, list[str]]:
    """Aplica la revisión adversarial de forma determinista.

    El revisor adversarial (LLM) es un asesor: por sí solo, un hallazgo aislado nunca decide nada
    aquí. Dos movimientos, ambos gobernados por reglas ya evaluadas ANTES de llegar a esta función:
    DEGRADAR (`SELECTED` -> `UNRESOLVED`) para `DEPENDENCIA_PROMOVIDA_A_CONTRATO`/
    `DIRECTO_SIN_SERVICE_ROLE`, y FINALIZAR una promoción ya decidida por `determinar_promociones`
    (no se re-decide aquí si promover, solo se completa): si el SD promovido tiene evidencia BIAN
    oficial verificada, queda `SELECTED`/`OWNED_SELECTED` y se mueve a `candidatos_directos`
    aunque su score léxico crudo (heredado de la evaluación cuando el LLM lo enmarcaba como
    dependencia) siga en banda tentativa o incluso descartada — la barra de promoción ya es más
    estricta que el umbral numérico. Sin evidencia oficial verificada, se anota la promoción
    (`reason_codes`) pero se deja el grupo/decisión tal como salieron de la reclasificación
    (probablemente `UNRESOLVED`/`NO_OFFICIAL_BIAN_EVIDENCE`) — no se inventa una operación sobre
    evidencia inexistente. Devuelve los grupos (posiblemente reordenados/movidos) y los
    `blocking_codes` a nivel de historia.
    """
    directos = list(grupos.candidatos_directos)
    tentativos = list(grupos.candidatos_tentativos)
    descartados = list(grupos.candidatos_descartados)
    por_sd = {normalizar(a.service_domain): a for a in (*directos, *tentativos, *descartados)}
    bloqueos_hu: list[str] = []

    for h in revision.hallazgos:
        codigos = list(dict.fromkeys([*h.reason_codes, *(
            [_DEGRADA_SELECTED[h.tipo]] if h.tipo in _DEGRADA_SELECTED else []
        )]))
        if h.tipo in ("CANDIDATO_OMITIDO", "OBJETO_SIN_PROPIETARIO", "EXCESO_DE_CONTRATOS"):
            bloqueos_hu.extend(codigos or [h.tipo])
        objetivo = por_sd.get(normalizar(h.service_domain)) if h.service_domain else None
        if objetivo is None:
            continue
        objetivo.reason_codes = list(dict.fromkeys([*objetivo.reason_codes, *codigos]))
        if h.detalle:
            objetivo.observaciones_adversariales = [
                *objetivo.observaciones_adversariales, f"[adversarial] {h.detalle}"
            ]
        if h.tipo in _DEGRADA_SELECTED and objetivo.decision_contractual == "SELECTED":
            objetivo.decision_contractual = "UNRESOLVED"
            objetivo.motivo_decision = "TENTATIVE_SCORE"
            objetivo.blocking_codes = list(dict.fromkeys([*objetivo.blocking_codes, *codigos]))

    for clave in promovidos:
        objetivo = por_sd.get(clave)
        if objetivo is None:
            continue
        objetivo.reason_codes = list(dict.fromkeys([*objetivo.reason_codes, PROMOTED_REASON_CODE]))
        objetivo.observaciones_adversariales = [
            *objetivo.observaciones_adversariales,
            "[adversarial] Promovido a OWNED_CONTRACT: accion directa con evidencia oficial y "
            "trazabilidad de escenarios, inicialmente clasificada como dependencia consumida.",
        ]
        # La barra de promoción (hallazgo independiente + dependency_kind de salida/resultado +
        # trazabilidad + evidencia citada + sin contradicción de Service Role) es más estricta que
        # el umbral numérico de "directo": si además la evidencia BIAN es oficial y verificable, el
        # score léxico crudo (heredado de cuando el LLM todavía enmarcaba esto como dependencia, y
        # por eso venía bajo en objeto/jerarquía) no debe dejarlo varado en tentativo/descartado.
        # Simétrico en sentido inverso al tope que ya aplica a los no-owned (`tope_no_owned`).
        if objetivo.evidencia_bian.estado in ("VERIFIED", "CACHED_VERIFIED"):
            if objetivo.grupo != "directo":
                tentativos = [a for a in tentativos if normalizar(a.service_domain) != clave]
                descartados = [a for a in descartados if normalizar(a.service_domain) != clave]
                objetivo.grupo = "directo"
                directos.append(objetivo)
            objetivo.decision_contractual = "SELECTED"
            objetivo.motivo_decision = "OWNED_SELECTED"

    for code in revision.blocking_codes:
        if code and code not in bloqueos_hu:
            bloqueos_hu.append(code)

    def _orden(a: ServiceDomainAsignado) -> tuple[float, str]:
        return (-a.confianza, a.service_domain.lower())

    grupos_salida = ServiceDomainsDeHistoria(
        candidatos_directos=sorted(directos, key=_orden),
        candidatos_tentativos=sorted(tentativos, key=_orden),
        candidatos_descartados=sorted(descartados, key=_orden),
    )
    return grupos_salida, list(dict.fromkeys(bloqueos_hu))
