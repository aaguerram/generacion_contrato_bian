"""Reduce determinista del fan-out del nodo 2b. Puro: solo dominio.

Cada llamada de 2b vio UN grupo de Service Domains (un Business Domain, o los propietarios que
rescató el canal de clases BOM) y devolvió su `CandidatosHistoriaLLM`. Unirlas es una unión, no
un ranking: 2b es una PISTA sin score, y quien decide después (nodos 3-8) trata igual a un
candidato venga de un grupo o de otro.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.dominio.historias import CandidatoServiceDomainLLM, CandidatosHistoriaLLM
from src.dominio.normalizacion import normalizar


def _union(listas: Sequence[Sequence[str]]) -> list[str]:
    vistos: list[str] = []
    for lista in listas:
        for x in lista:
            if x and x not in vistos:
                vistos.append(x)
    return vistos


def fusionar_candidatos(
    parciales: Sequence[CandidatosHistoriaLLM], nombres_grupo: Sequence[str] | None = None
) -> CandidatosHistoriaLLM:
    """Unión por nombre normalizado, en orden de primera aparición.

    Un mismo Service Domain propuesto por dos grupos (raro: los grupos son disjuntos, pero el
    modelo puede nombrar uno de fuera de su grupo) se queda con la primera `rationale` y la unión
    de `supporting_intent`. `coverage_notes`/`assumptions`/`gaps` se unen sin duplicar y, si se
    pasan `nombres_grupo` (uno por parcial), cada texto lleva delante `[grupo]`: medido en el E2E
    1 (2026-09-20), aun con el prompt de grupo el modelo escribe "en este grupo no hay quien
    administre el dato" -- verdad para el grupo, falso para la HU --, y sin la etiqueta eso llega al
    JSON como un hueco de la historia. Los `metadatos` no se fusionan: cada llamada dejó su huella.
    """
    nombres = list(nombres_grupo or [])

    def _etiquetar(i: int, textos: Sequence[str]) -> list[str]:
        # Un grupo que no propuso NADA solo puede hablar de lo que le falta, y lo que le falta a
        # un grupo no le falta a la historia: sus notas no entran (medido: "no hay quien
        # administre el dato en este grupo" desde IT Management, Operational Services y Party).
        if not parciales[i].candidatos:
            return []
        if i < len(nombres) and nombres[i]:
            return [f"[{nombres[i]}] {t}" for t in textos if t]
        return [t for t in textos if t]

    por_nombre: dict[str, CandidatoServiceDomainLLM] = {}
    for parcial in parciales:
        for c in parcial.candidatos:
            clave = normalizar(c.service_domain)
            if not clave:
                continue
            previo = por_nombre.get(clave)
            if previo is None:
                por_nombre[clave] = c.model_copy(deep=True)
            else:
                previo.supporting_intent = _union([previo.supporting_intent, c.supporting_intent])
                if not previo.rationale and c.rationale:
                    previo.rationale = c.rationale
    return CandidatosHistoriaLLM(
        candidatos=list(por_nombre.values()),
        coverage_notes=_union([_etiquetar(i, p.coverage_notes) for i, p in enumerate(parciales)]),
        assumptions=_union([_etiquetar(i, p.assumptions) for i, p in enumerate(parciales)]),
        gaps=_union([_etiquetar(i, p.gaps) for i, p in enumerate(parciales)]),
    )
