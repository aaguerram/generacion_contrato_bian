"""Adaptador: carga el catálogo desde SD.json (columnas L..V) y lo enriquece con la
jerarquía BIAN R14 (`bian-business-areas.json`) — Business Area / Business Domain por SD.

Ambos archivos viven en `docs/` y traen los mismos 341 Service Domains de la release 14.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import construir_indice_exacto, normalizar

logger = logging.getLogger(__name__)

# clave del JSON (cabecera de la hoja Excel)  ->  campo del modelo
_MAPEO = {
    "Service Domain": "service_domain",
    "Service Role": "service_role",
    "Examples of Use": "examples_of_use",
    "Executive Summary": "executive_summary",
    "Features": "features",
    "Functional Pattern": "functional_pattern",
    "Asset Type": "asset_type",
    "Generic Artifact Type": "generic_artifact_type",
    "Control Record <AssetType><ArtifactType>": "control_record",
    "Registration Status": "registration_status",
}

_JERARQUIA_POR_DEFECTO = "bian-business-areas.json"


class CatalogoJson(CatalogoServiceDomainsPort):
    def __init__(
        self, ruta_sd_json: str | Path, ruta_jerarquia: str | Path | None = None
    ) -> None:
        self._ruta = Path(ruta_sd_json)
        self._ruta_jerarquia = (
            Path(ruta_jerarquia)
            if ruta_jerarquia is not None
            else self._ruta.parent / _JERARQUIA_POR_DEFECTO
        )
        self._entradas: list[EntradaCatalogo] | None = None
        self._indice: dict[str, str] = {}
        self._por_nombre: dict[str, EntradaCatalogo] = {}

    def _jerarquia(self) -> dict[str, tuple[str, str]]:
        """{ nombre_normalizado -> (business_area, business_domain) }."""
        if not self._ruta_jerarquia.is_file():
            logger.warning("Jerarquía BIAN no encontrada en %s; SD sin Business Area/Domain", self._ruta_jerarquia)
            return {}
        crudo = json.loads(self._ruta_jerarquia.read_text(encoding="utf-8"))
        salida: dict[str, tuple[str, str]] = {}
        for area in crudo.get("businessAreas", []):
            an = str(area.get("name", ""))
            for dominio in area.get("businessDomains", []):
                dn = str(dominio.get("name", ""))
                for sd in dominio.get("serviceDomains", []):
                    nombre = str(sd.get("name", ""))
                    if nombre:
                        salida[normalizar(nombre)] = (an, dn)
        return salida

    def _cargar(self) -> None:
        if self._entradas is not None:
            return
        if not self._ruta.is_file():
            raise FileNotFoundError(f"No se encontró SD.json en {self._ruta}")
        crudo = json.loads(self._ruta.read_text(encoding="utf-8"))
        jerarquia = self._jerarquia()
        entradas: list[EntradaCatalogo] = []
        for fila in crudo:
            datos = {campo: fila.get(clave) for clave, campo in _MAPEO.items()}
            if not datos.get("service_domain"):
                continue
            area, dominio = jerarquia.get(normalizar(datos["service_domain"]), (None, None))
            datos["business_area"] = area
            datos["business_domain"] = dominio
            entradas.append(EntradaCatalogo(**datos))
        self._entradas = entradas
        self._por_nombre = {e.service_domain: e for e in entradas}
        self._indice = construir_indice_exacto([e.service_domain for e in entradas])

    def cargar(self) -> list[EntradaCatalogo]:
        self._cargar()
        assert self._entradas is not None
        return self._entradas

    def buscar_exacto(self, nombre: str) -> EntradaCatalogo | None:
        self._cargar()
        canonico = self._indice.get(normalizar(nombre))
        return self._por_nombre.get(canonico) if canonico else None
