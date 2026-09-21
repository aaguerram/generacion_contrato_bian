"""Traducción entre las Historias de Usuario del formulario y los archivos que espera el CLI.

El caso de uso recibe un DIRECTORIO con un archivo por historia. El formulario mantiene una
**lista**: cada historia tiene su título y su detalle en campos separados, así que no hay que
adivinar dónde empieza ninguna. `archivos_de_historias` es esa traducción, y es la que usa la API.

`separar_historias` es la traducción ANTIGUA, cuando todo llegaba pegado en un solo `textarea` y
había que partirlo por marcadores. Se conserva para migrar los intentos guardados con aquel
formato y para importar un pegote de texto, pero ya no está en el camino de guardar: el separador
partía por la mitad cualquier historia cuyo detalle llevara una línea de guiones o un encabezado
Markdown, que es justo lo que trae una historia escrita en Markdown.

Vive aquí y no en `src/` porque es un problema de la interfaz, no del mapeo.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Sequence

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


def _nombres_unicos(bases: Iterable[str]) -> list[str]:
    """Numera los repetidos. Dos historias pueden llamarse igual; dos archivos, no."""
    vistos: set[str] = set()
    salida: list[str] = []
    for base in bases:
        nombre, n = base, 2
        while nombre in vistos:
            nombre, n = f"{base}-{n}", n + 1
        vistos.add(nombre)
        salida.append(nombre)
    return salida


def archivos_de_historias(
    historias: Sequence[tuple[str, str]],
) -> list[tuple[str, str, str]]:
    """`[(nombre de archivo, título, contenido)]` a partir de `[(título, detalle)]`.

    El título entra en el contenido del archivo: el pipeline solo lee el texto de la HU, y el
    título es parte de lo que la historia dice. Si el detalle ya empieza por el título no se
    repite. Una historia sin detalle deja un archivo con solo el título, que es exactamente lo que
    el usuario escribió y el pipeline lo reportará como historia pobre en vez de desaparecer.
    """
    resultado: list[tuple[str, str, str]] = []
    limpias = [
        (t.strip()[:_TITULO_MAX] or "Historia sin titulo", (d or "").replace("\r\n", "\n").strip())
        for t, d in historias
        if (t or "").strip() or (d or "").strip()
    ]
    bases = _nombres_unicos(
        f"{i:02d}-{_slug(t, f'historia-{i}')}" for i, (t, _) in enumerate(limpias, 1)
    )
    for base, (titulo, detalle) in zip(bases, limpias):
        cuerpo = detalle if detalle.lower().startswith(titulo.lower()) else f"{titulo}\n\n{detalle}"
        resultado.append((f"{base}.txt", titulo, cuerpo.strip()))
    return resultado
