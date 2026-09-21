"""Separar en Historias de Usuario el texto que el usuario pega en un solo `textarea`.

El CLI recibe un DIRECTORIO con un archivo por historia; el formulario recibe todo pegado. Esta
es la única traducción entre ambos mundos, y vive aquí y no en `src/` porque es un problema de la
interfaz, no del mapeo.

La regla es deliberadamente conservadora: se parte por un separador EXPLÍCITO (una línea de tres o
más guiones/iguales, o una línea `## algo`, o `HU-...:`), y si no aparece ninguno el texto entero
es UNA sola historia. Adivinar dónde empieza cada historia cuando el usuario no lo dijo produce
historias partidas por la mitad, que es peor que una historia larga.
"""

from __future__ import annotations

import re
import unicodedata

# Una línea que solo tiene --- o === (3+), o un encabezado markdown de nivel 1-2, o "HU-xxx:".
_SEPARADOR = re.compile(
    r"^[ \t]*(?:[-=_*]{3,}|#{1,2}[ \t]+\S.*|HU[ _-]?\d+[ \t]*[:.-].*)[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)
_TITULO_MAX = 90


def _slug(texto: str, respaldo: str) -> str:
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^A-Za-z0-9]+", "-", plano).strip("-")[:60]
    return limpio or respaldo


# Una línea que es SOLO una regla horizontal: separa, pero no dice nada. A diferencia de
# `## Título` o `HU-01: ...`, que separan Y titulan.
_REGLA = re.compile(r"^[ \t]*[-=_*]{3,}[ \t]*$")


def _sin_regla_inicial(bloque: str) -> str:
    lineas = bloque.splitlines()
    while lineas and _REGLA.match(lineas[0]):
        lineas.pop(0)
    return "\n".join(lineas).strip()


def _titulo_de(bloque: str) -> str:
    for linea in bloque.splitlines():
        s = linea.strip().lstrip("#").strip()
        if s and not _REGLA.match(linea):
            return s[:_TITULO_MAX]
    return "Historia sin titulo"


def separar_historias(texto: str) -> list[tuple[str, str, str]]:
    """`[(nombre de archivo, título, contenido)]`, en el orden en que aparecen.

    Sin separador explícito devuelve una sola historia con TODO el texto: es lo que el usuario
    escribió, y el pipeline la tratará como una HU larga en vez de como cinco a medias.
    """
    texto = (texto or "").replace("\r\n", "\n").strip()
    if not texto:
        return []

    cortes = [m.start() for m in _SEPARADOR.finditer(texto)]
    if not cortes:
        bloques = [texto]
    else:
        # El separador encabeza su bloque (un `## Título` pertenece a la historia que abre).
        limites = sorted({0, *cortes, len(texto)})
        bloques = [texto[a:b].strip() for a, b in zip(limites, limites[1:]) if texto[a:b].strip()]

    historias: list[tuple[str, str, str]] = []
    vistos: set[str] = set()
    for i, bloque in enumerate(bloques, 1):
        # Un bloque que es SOLO el separador (`-----`) no es una historia.
        bloque = _sin_regla_inicial(bloque)
        if not re.sub(r"[-=_*#\s]", "", bloque):
            continue
        titulo = _titulo_de(bloque)
        base = f"{i:02d}-{_slug(titulo, f'historia-{i}')}"
        nombre = base
        n = 2
        while nombre in vistos:
            nombre, n = f"{base}-{n}", n + 1
        vistos.add(nombre)
        historias.append((f"{nombre}.txt", titulo, bloque))
    return historias
