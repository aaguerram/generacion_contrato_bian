"""Scoring y revision adversarial deterministas para decisiones BIAN.

El score NO usa la confianza libre del LLM: combina correspondencia lexica (historia vs
evidencia oficial: Service Role, operaciones, schemas/objetos BOM) con una rubrica estructurada
0-3 que el LLM si puede sostener desde el prompt (`match_service_role`, `match_objeto_negocio`),
mas ownership, trazabilidad y coherencia de jerarquia. Todo acotado y reproducible.
"""

from __future__ import annotations

import re
import unicodedata

from src.dominio.historias import (
    DesgloseScore,
    EvidenciaBian,
    OperacionBian,
    ServiceDomainPropuestoLLM,
)
from src.dominio.modelos import EntradaCatalogo
from src.dominio.vocabulario_bian import EQUIVALENCIAS_BASE

# El mapa vive en `vocabulario_bian` (un solo sitio para el puente ES->EN del dominio);
# aquí se usa el BASE tal cual: la extensión de retrieval no debe mover el scoring.
_EQUIVALENCIAS = EQUIVALENCIAS_BASE
_STOP = {
    "una",
    "uno",
    "unos",
    "unas",
    "del",
    "las",
    "los",
    "para",
    "por",
    "con",
    "que",
    "and",
    "the",
    "for",
    "from",
    "this",
    "that",
    "sus",
}


def _split_camel(texto: str) -> str:
    """`IssuedDeviceAdministration` / `partyAuth3` -> tokens separables."""
    texto = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", texto or "")
    texto = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", texto)
    return re.sub(r"(?<=[0-9])(?=[A-Za-z])", " ", texto)


def _tokens(texto: str) -> set[str]:
    plano = (
        unicodedata.normalize("NFKD", _split_camel(texto).lower())
        .encode("ascii", "ignore")
        .decode()
    )
    return {
        _EQUIVALENCIAS.get(t, t)
        for t in re.findall(r"[a-z0-9]+", plano)
        if len(t) > 2 and t not in _STOP
    }


def _sim(a: str, b: str) -> float:
    x, y = _tokens(a), _tokens(b)
    return len(x & y) / min(len(x), len(y)) if x and y else 0.0


def calcular_score(
    propuesta: ServiceDomainPropuestoLLM,
    entrada: EntradaCatalogo,
    operaciones: list[OperacionBian],
    evidencia: EvidenciaBian,
    objetos_bom: list[str] | tuple[str, ...] = (),
) -> tuple[DesgloseScore, list[str]]:
    rol = entrada.service_role or ""
    grupos_ops = " ".join(o.grupo for o in operaciones)
    texto_ops = " ".join(
        f"{o.operation_id} {o.summary} {o.description} {o.grupo}" for o in operaciones
    )
    texto_bom = " ".join(objetos_bom)

    # 30% correspondencia con la ACCION oficial (Service Role + operationId/summary/description/grupo)
    accion_lexico = max(
        _sim(propuesta.accion_objeto, rol), _sim(propuesta.accion_objeto, texto_ops)
    )
    accion = max(accion_lexico, propuesta.match_service_role / 3.0, propuesta.match_action / 3.0)

    # 25% correspondencia con el OBJETO / schema BOM (grupos CR/BQ + nombres de schema + Service Role)
    objeto_lexico = max(
        _sim(propuesta.accion_objeto, grupos_ops),
        _sim(propuesta.accion_objeto, texto_bom),
        _sim(propuesta.accion_objeto, rol),
    )
    objeto = max(objeto_lexico, propuesta.match_objeto_negocio / 3.0)

    # 20% ownership / outcome
    ownership = (
        1.0
        if propuesta.rol_contractual == "OWNED_CONTRACT"
        else 0.55
        if propuesta.rol_contractual == "CONSUMED_DEPENDENCY"
        else 0.2
    )

    # 15% trazabilidad explicita a escenarios de la historia
    traza = min(1.0, len([x for x in propuesta.escenarios_hu if x.strip()]) / 2.0)

    # 10% coherencia con la jerarquia (Business Area / Business Domain reales del SD)
    jer_txt = " ".join(p for p in (entrada.business_area, entrada.business_domain) if p)
    jerarquia = _sim(f"{propuesta.accion_objeto} {propuesta.justificacion}", jer_txt)

    verificada = evidencia.estado in ("VERIFIED", "CACHED_VERIFIED")
    penalizacion, bonificacion, observaciones = 0.0, 0.0, []
    if verificada:
        bonificacion += (
            0.05  # premia tener evidencia BOM oficial verificable (simétrico a la penalización)
        )
    if evidencia.estado == "BIAN_EVIDENCE_UNAVAILABLE":
        penalizacion += 0.20
        observaciones.append("No existe evidencia BOM oficial verificable; decision sin resolver.")
    # calidad de la evidencia (rúbrica 0-3 del evaluador; 0 = no puntuada -> neutral)
    if propuesta.evidence_quality == 1 and verificada:
        penalizacion += 0.04
        observaciones.append(
            "Evidencia oficial disponible pero poco concluyente (evidence_quality=1)."
        )
    if propuesta.evidence_quality >= 3 and verificada:
        bonificacion += 0.03
    # ambigüedad residual de la evaluación aislada del candidato
    if propuesta.ambiguity == "HIGH":
        penalizacion += 0.10
        observaciones.append("Ambiguedad alta en la evaluacion del candidato.")
    elif propuesta.ambiguity == "LOW":
        penalizacion += 0.04
    if propuesta.rol_contractual != "OWNED_CONTRACT":
        penalizacion += 0.08
    if (
        propuesta.rol_contractual == "OWNED_CONTRACT"
        and operaciones
        and accion < 0.08
        and objeto < 0.08
    ):
        penalizacion += 0.18
        observaciones.append(
            "OWNED_CONTRACT sin correspondencia suficiente accion/objeto-operacion oficial."
        )
    if propuesta.rol_contractual != "OWNED_CONTRACT" and max(accion, objeto) >= 0.35:
        observaciones.append("Revisar ownership: correspondencia fuerte con catalogo oficial.")

    total = max(
        0.0,
        min(
            1.0,
            0.30 * accion
            + 0.25 * objeto
            + 0.20 * ownership
            + 0.15 * traza
            + 0.10 * jerarquia
            + bonificacion
            - penalizacion,
        ),
    )

    desglose = DesgloseScore(
        accion_oficial=round(accion, 4),
        objeto_bom=round(objeto, 4),
        ownership_outcome=round(ownership, 4),
        trazabilidad_escenarios=round(traza, 4),
        coherencia_jerarquia=round(jerarquia, 4),
        penalizacion=round(penalizacion - bonificacion, 4),  # neto: >0 penaliza, <0 bonifica
        total=round(total, 4),
    )
    return desglose, observaciones
