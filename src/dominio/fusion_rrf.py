"""Reciprocal Rank Fusion: combina varios rankings (léxico, vectorial, ...) en uno solo sin
mezclar escalas incompatibles (similitud coseno vs. WRatio). Puro: solo stdlib.
"""

from __future__ import annotations

from collections.abc import Sequence

_K_DEFECTO = 60  # constante estándar de RRF (Cormack et al.): amortigua el peso del top-1


def fusion_rrf(
    rankings: list[list[str]],
    *,
    k: int = _K_DEFECTO,
    pesos: Sequence[float] | None = None,
) -> list[tuple[str, float]]:
    """Cada ranking es una lista de nombres YA ordenada por relevancia desc (mejor primero).
    Devuelve `(nombre, score_fusionado)` ordenado desc; un nombre presente en varios rankings
    acumula `peso_i/(k+posicion+1)` de cada uno, así que aparecer arriba en más de una fuente pesa
    más que aparecer arriba en una sola.

    `k` amortigua el top-1: 60 es el valor del paper, calibrado para corpus de miles de
    documentos. Con 341 Service Domains y top-20, un `k` menor (10-20) diferencia más las primeras
    posiciones. `pesos` (uno por ranking, 1.0 por defecto) existe porque la fusión sin pesos trata
    igual a un canal que acierta 0.29 y a otro que acierta 0.86 — medido sobre el corpus dorado,
    eso bajaba Recall@10 de 0.86 a 0.71. Un peso 0 apaga ese canal sin tener que recablear nada.
    """
    if pesos is not None and len(pesos) != len(rankings):
        raise ValueError(
            f"se dieron {len(pesos)} pesos para {len(rankings)} rankings: debe haber uno por canal"
        )
    puntajes: dict[str, float] = {}
    for indice, ranking in enumerate(rankings):
        peso = 1.0 if pesos is None else float(pesos[indice])
        if peso == 0.0:
            continue
        for posicion, nombre in enumerate(ranking):
            puntajes[nombre] = puntajes.get(nombre, 0.0) + peso / (k + posicion + 1)
    return sorted(puntajes.items(), key=lambda kv: (-kv[1], kv[0]))
