"""Adaptador de `CatalogoEntidadesBianPort` sobre `docs/entity.json`. Carga perezosa, sin red.

El archivo pesa ~8 MB y se lee UNA vez por proceso: el resultado es inmutable y lo comparten
todas las Historias de Usuario de la corrida.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.aplicacion.puertos.catalogo_entidades import CatalogoEntidadesBianPort
from src.dominio.entidades_bian import AtributoClase, ClaseBian, OcurrenciaClase

logger = logging.getLogger(__name__)


class CatalogoEntidadesJson(CatalogoEntidadesBianPort):
    def __init__(self, ruta: str | Path) -> None:
        self._ruta = Path(ruta)
        self._clases: dict[str, ClaseBian] | None = None
        self._enums: frozenset[str] | None = None

    def clases(self) -> dict[str, ClaseBian]:
        if self._clases is None:
            self._cargar()
        return self._clases or {}

    def nombres_enum(self) -> frozenset[str]:
        if self._enums is None:
            self._cargar()
        return self._enums or frozenset()

    # ── carga ────────────────────────────────────────────────────────────────────────────
    def _cargar(self) -> None:
        if not self._ruta.is_file():
            # Ausente no es un error: el canal simplemente no aporta candidatos.
            logger.warning("entity.json no encontrado en %s; el canal de entidades queda inactivo", self._ruta)
            self._clases, self._enums = {}, frozenset()
            return
        datos = json.loads(self._ruta.read_text(encoding="utf-8"))
        clases: dict[str, ClaseBian] = {}
        enums: set[str] = set()
        for nombre, entrada in (datos.get("entities") or {}).items():
            ocurrencias = tuple(
                self._ocurrencia(o) for o in (entrada.get("occurrences") or [])
            )
            if any(o.kind == "enum" for o in ocurrencias):
                enums.add(nombre)
            # `bian_bom` es el modelo genérico de la clase: su definición en prosa y sus
            # propiedades. Es el texto que un canal de recuperación puede leer; la propiedad la
            # siguen diciendo las ocurrencias.
            generico = entrada.get("bian_bom") or {}
            clases[nombre] = ClaseBian(
                nombre=nombre,
                ocurrencias=ocurrencias,
                descripcion=str(generico.get("description") or "").strip(),
                propiedades=tuple(
                    str(p.get("name") or "").strip()
                    for p in (generico.get("properties") or [])
                    if p.get("name")
                ),
            )
        self._clases, self._enums = clases, frozenset(enums)
        logger.info(
            "entity.json: %d clases (%d enums) desde %s", len(clases), len(enums), self._ruta.name
        )

    @staticmethod
    def _ocurrencia(o: dict) -> OcurrenciaClase:
        notas = o.get("notes") or {}
        return OcurrenciaClase(
            service_domain=o.get("service_domain", ""),
            diagrama=o.get("diagram_type", ""),
            kind=o.get("kind", "class"),
            # `None` (ausente) y `"no"` son cosas distintas: ausente = el SD define la clase.
            extensible=notas.get("Extensible"),
            bq=notas.get("BQ", ""),
            control_record=notas.get("ControlRecord", ""),
            asset_type=notas.get("AssetType", ""),
            bom_de=notas.get("BOMDiagram", ""),
            atributos=tuple(
                AtributoClase(nombre=a.get("name", ""), tipo=a.get("type", ""))
                for a in (o.get("attributes") or [])
            ),
            valores_enum=tuple(o.get("enum_values") or []),
        )
