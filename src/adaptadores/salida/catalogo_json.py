"""Adaptador: carga los Service Domains desde la fuente ÚNICA del runtime,
`docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` (341 SD de la release 14).

Ese archivo trae, por Service Domain, los textos (`role_definition`, `example_of_use`,
`executive_summary`, `key_features`, `documentation`), la clasificación funcional
(`functional_pattern`, `asset_type`, `generic_artifact_type`, `control_record`,
`registration_status`) y la jerarquía Business Area / Business Domain, que aquí se resuelve
aplanando el árbol. Antes esto salía de dos archivos que este adaptador cruzaba en cada carga
(`SD.json` + `bian-business-areas.json`); hoy SD.json solo sirve para completarle huecos al
landscape fuera de línea (`scripts/enrich_service_landscape/`) y ninguno de los dos se lee en
tiempo de ejecución.

Los nombres del landscape mandan en el archivo; el mapeo a los campos de `EntradaCatalogo` vive
aquí y solo aquí, que es lo que le toca a un adaptador.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.dominio.modelos import EntradaCatalogo
from src.dominio.normalizacion import construir_indice_exacto, normalizar

# campo en el landscape -> campo de EntradaCatalogo (los que no aparecen se llaman igual)
_RENOMBRES = {
    "name": "service_domain",
    "role_definition": "service_role",
    "example_of_use": "examples_of_use",
    "key_features": "features",
}
_IGUALES = (
    "executive_summary",
    "documentation",
    "functional_pattern",
    "asset_type",
    "generic_artifact_type",
    "control_record",
    "registration_status",
)


def _texto(valor: Any) -> str | None:
    """Los vacíos del landscape ("", "None", null) se normalizan a None."""
    if valor is None:
        return None
    s = str(valor).strip()
    return None if s in ("", "None") else s


class CatalogoJson(CatalogoServiceDomainsPort):
    def __init__(self, ruta_catalogo: str | Path) -> None:
        self._ruta = Path(ruta_catalogo)
        self._entradas: list[EntradaCatalogo] | None = None
        self._indice: dict[str, str] = {}
        self._por_nombre: dict[str, EntradaCatalogo] = {}
        self._rutas_bom: dict[str, str] = {}

    def _aplanar(
        self, nodos: list[dict], area: str | None = None, dominio: str | None = None
    ) -> Iterator[tuple[dict, str | None, str | None]]:
        """Recorre Business Area -> Business Domain (anidable) -> Service Domain."""
        for nodo in nodos:
            nombre = _texto(nodo.get("name"))
            for hijo in nodo.get("business_domains", []):
                yield from self._aplanar([hijo], area or nombre, _texto(hijo.get("name")))
            for sd in nodo.get("service_domains", []):
                yield sd, area or nombre, dominio or nombre

    def _cargar(self) -> None:
        if self._entradas is not None:
            return
        if not self._ruta.is_file():
            raise FileNotFoundError(f"No se encontró el catálogo BIAN en {self._ruta}")
        crudo = json.loads(self._ruta.read_text(encoding="utf-8"))
        if not isinstance(crudo, dict) or "business_areas" not in crudo:
            raise ValueError(
                f"{self._ruta} no es el BIAN Service Landscape Matrix View "
                "({release, business_areas: [...]}), que es la única fuente de Service Domains."
            )

        entradas: list[EntradaCatalogo] = []
        for sd, area, dominio in self._aplanar(crudo["business_areas"]):
            datos = {destino: _texto(sd.get(origen)) for origen, destino in _RENOMBRES.items()}
            if not datos["service_domain"]:
                continue
            datos.update({campo: _texto(sd.get(campo)) for campo in _IGUALES})
            datos["business_area"] = area
            datos["business_domain"] = dominio
            entradas.append(EntradaCatalogo(**datos))
            ruta_bom = _texto((sd.get("bom_diagram") or {}).get("puml_path"))
            if ruta_bom:
                self._rutas_bom[datos["service_domain"]] = ruta_bom

        self._entradas = entradas
        self._por_nombre = {e.service_domain: e for e in entradas}
        self._indice = construir_indice_exacto([e.service_domain for e in entradas])

    def cargar(self) -> list[EntradaCatalogo]:
        self._cargar()
        assert self._entradas is not None
        return self._entradas

    def rutas_bom_puml(self) -> dict[str, str]:
        """Ruta del PUML BOM que el propio landscape declara por Service Domain (`bom_diagram`).

        265 de los 341 SD la traen. `CatalogoBomPuml` la prefiere sobre deducir el nombre del
        archivo por convención kebab-case: hoy ambas coinciden en los 265 (lo fija
        `tests/unit_test/test_catalogo_bom_puml.py`), pero la convención es una suposición sobre
        cómo nombró los archivos `scripts/svg_to_puml_bom/`, no un dato publicado.
        """
        self._cargar()
        return dict(self._rutas_bom)

    def buscar_exacto(self, nombre: str) -> EntradaCatalogo | None:
        self._cargar()
        canonico = self._indice.get(normalizar(nombre))
        return self._por_nombre.get(canonico) if canonico else None
