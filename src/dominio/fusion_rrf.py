"""Reciprocal Rank Fusion: combina varios rankings (léxico, vectorial, ...) en uno solo sin
mezclar escalas incompatibles (similitud coseno vs. WRatio). Puro: solo stdlib.
"""

from __future__ import annotations

_K_DEFECTO = 60  # constante estándar de RRF (Cormack et al.): amortigua el peso del top-1


def fusion_rrf(rankings: list[list[str]], *, k: int = _K_DEFECTO) -> list[tuple[str, float]]:
    """Cada ranking es una lista de nombres YA ordenada por relevancia desc (mejor primero).
    Devuelve `(nombre, score_fusionado)` ordenado desc; un nombre presente en varios rankings
    acumula `1/(k+posicion+1)` de cada uno, así que aparecer arriba en más de una fuente pesa más
    que aparecer arriba en una sola."""
    puntajes: dict[str, float] = {}
    for ranking in rankings:
        for posicion, nombre in enumerate(ranking):
            puntajes[nombre] = puntajes.get(nombre, 0.0) + 1.0 / (k + posicion + 1)
    return sorted(puntajes.items(), key=lambda kv: (-kv[1], kv[0]))
