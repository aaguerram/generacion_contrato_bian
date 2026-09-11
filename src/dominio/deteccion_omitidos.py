"""Segundo pase determinista: detecta Service Domains que el LLM NO propuso.

No usa LLM ni red. Toma las senales funcionales ya extraidas por el paso 1
(`business_actions`, `business_objects`, `capacidades_funcionales`, `outcomes`) y las
contrasta lexicamente contra los 341 SD del catalogo (`service_domain` + `service_role`).
Devuelve los mejores candidatos que NO estan ya en la lista propuesta, para que un revisor
compruebe si hubo un falso negativo por omision. No decide nada.
"""

from __future__ import annotations

from src.dominio.historias import IntencionHistoriaLLM, ServiceDomainOmitido
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import normalizar
from src.dominio.scoring_bian import _sim, _tokens

_UMBRAL_OMITIDO = 0.34
_TOP_N = 5


def detectar_omitidos(
    intencion: IntencionHistoriaLLM,
    catalogo: list[EntradaCatalogo],
    ya_propuestos: set[str],
    *,
    top_n: int = _TOP_N,
    umbral: float = _UMBRAL_OMITIDO,
) -> list[ServiceDomainOmitido]:
    """`ya_propuestos` = nombres de SD (normalizados) que el LLM ya evaluo (en cualquier grupo)."""
    señales = " ".join(
        [
            *intencion.business_actions,
            *intencion.business_objects,
            *intencion.capacidades_funcionales,
            *intencion.outcomes,
        ]
    ).strip()
    tokens_señal = _tokens(señales)
    if not tokens_señal:
        return []

    candidatos: list[tuple[float, EntradaCatalogo, list[str]]] = []
    for e in catalogo:
        if normalizar(e.service_domain) in ya_propuestos:
            continue
        nombre_sim = _sim(señales, e.service_domain)
        rol_sim = _sim(señales, e.service_role or "")
        score = round(max(nombre_sim, 0.6 * rol_sim + 0.4 * nombre_sim), 4)
        if score < umbral:
            continue
        comunes = sorted(tokens_señal & (_tokens(e.service_domain) | _tokens(e.service_role or "")))
        candidatos.append((score, e, comunes))

    candidatos.sort(key=lambda c: (-c[0], c[1].service_domain.lower()))
    return [
        ServiceDomainOmitido(
            service_domain=e.service_domain,
            score_lexico=score,
            business_area=e.business_area,
            business_domain=e.business_domain,
            rol_bian=e.service_role,
            señales=comunes[:8],
        )
        for score, e, comunes in candidatos[:top_n]
    ]
