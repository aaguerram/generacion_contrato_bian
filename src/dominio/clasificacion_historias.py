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
"""

from __future__ import annotations

from dataclasses import dataclass

from src.dominio.historias import (
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
_DEGRADA_SELECTED = {
    "DEPENDENCIA_PROMOVIDA_A_CONTRATO": "BIAN-SCOPE-002",
    "DIRECTO_SIN_SERVICE_ROLE": "BIAN-SCOPE-003",
    "ACCION_DIRECTA_COMO_DEPENDENCIA": "BIAN-SCOPE-002",
}


def aplicar_hallazgos_adversariales(
    grupos: ServiceDomainsDeHistoria, revision: RevisionAdversarialLLM
) -> tuple[ServiceDomainsDeHistoria, list[str]]:
    """Aplica la revisión adversarial de forma determinista.

    El revisor adversarial es un asesor: solo puede DEGRADAR (`SELECTED` -> `UNRESOLVED`) y
    anotar `reason_codes`. Nunca puede seleccionar ni subir de grupo. Devuelve los grupos
    (posiblemente re-clasificados) y la lista de `blocking_codes` a nivel de historia.
    """
    todos = [
        *grupos.candidatos_directos,
        *grupos.candidatos_tentativos,
        *grupos.candidatos_descartados,
    ]
    por_sd = {normalizar(a.service_domain): a for a in todos}
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

    for code in revision.blocking_codes:
        if code and code not in bloqueos_hu:
            bloqueos_hu.append(code)
    return grupos, list(dict.fromkeys(bloqueos_hu))
