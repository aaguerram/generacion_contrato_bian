"""Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad macro de un JSON.

- Historias: cualquier archivo de texto del directorio (`.txt`, `.md`, `.markdown`). El titulo se
  deriva del nombre de archivo (se quita un prefijo tipo `HU-`, `HU_`, `HU 794679 ` y la extension).
- Funcionalidad: un archivo JSON con `funcionalidad_macro` + `detalle` (se toleran alias, ver
  `FuncionalidadMacro.desde_dict`).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.aplicacion.puertos.lector_historias import LectorHistoriasPort
from src.dominio.historias import FuncionalidadMacro, HistoriaUsuario

logger = logging.getLogger(__name__)

_EXTENSIONES = (".txt", ".md", ".markdown")
_PREFIJO_HU = re.compile(r"^\s*HU[\s._-]*\d*[\s._-]*", re.IGNORECASE)


def _titulo_desde_nombre(nombre_archivo: str) -> str:
    tronco = Path(nombre_archivo).stem
    tronco = _PREFIJO_HU.sub("", tronco).strip(" -_.")
    return tronco or Path(nombre_archivo).stem


class LectorHistoriasFilesystem(LectorHistoriasPort):
    def leer_historias(self, directorio: str) -> list[HistoriaUsuario]:
        raiz = Path(directorio)
        if not raiz.is_dir():
            raise FileNotFoundError(f"El directorio de Historias de Usuario no existe: {raiz}")

        archivos = sorted(
            (p for p in raiz.iterdir() if p.is_file() and p.suffix.lower() in _EXTENSIONES),
            key=lambda p: p.name.lower(),
        )
        historias: list[HistoriaUsuario] = []
        for p in archivos:
            texto = p.read_text(encoding="utf-8", errors="replace").strip()
            if not texto:
                logger.warning("HU vacia, se omite: %s", p.name)
                continue
            historias.append(
                HistoriaUsuario(
                    archivo=p.name, titulo=_titulo_desde_nombre(p.name), contenido=texto
                )
            )
        logger.info("HU leidas de %s: %d", raiz, len(historias))
        return historias

    def leer_funcionalidad(self, ruta: str) -> FuncionalidadMacro:
        archivo = Path(ruta)
        if not archivo.is_file():
            raise FileNotFoundError(f"No se encontro el JSON de funcionalidad: {archivo}")
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"El archivo de funcionalidad no es JSON valido: {exc}") from exc
        return FuncionalidadMacro.desde_dict(datos)
