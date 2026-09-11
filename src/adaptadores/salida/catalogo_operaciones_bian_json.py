"""Adaptador: catálogo local de operaciones oficiales por Service Domain.

Fuente: `docs/bian-operation-catalogs.json` — extracto normalizado de los catálogos BOM
Extended API oficiales de BIAN R14 (9 Service Domains materializados). El nombre del SD
se resuelve de forma laxa (normalización) porque las claves del JSON vienen en forma
compacta (`PartyAuthentication`) y SD.json usa la forma con espacios (`Party Authentication`).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.aplicacion.puertos.catalogo_operaciones_bian import CatalogoOperacionesBianPort
from src.dominio.historias import OperacionBian
from src.dominio.normalizacion import normalizar

logger = logging.getLogger(__name__)

_POR_DEFECTO = "bian-operation-catalogs.json"


class CatalogoOperacionesBianJson(CatalogoOperacionesBianPort):
    def __init__(self, ruta: str | Path) -> None:
        self._ruta = Path(ruta)
        self._por_norma: dict[str, tuple[str, list[OperacionBian]]] | None = None

    def _cargar(self) -> dict[str, tuple[str, list[OperacionBian]]]:
        if self._por_norma is not None:
            return self._por_norma
        salida: dict[str, tuple[str, list[OperacionBian]]] = {}
        if not self._ruta.is_file():
            logger.warning("Catálogo de operaciones BIAN no encontrado en %s; paso 2 desactivado", self._ruta)
            self._por_norma = salida
            return salida
        crudo = json.loads(self._ruta.read_text(encoding="utf-8"))
        for nombre, cuerpo in (crudo.get("service_domains") or {}).items():
            operaciones = [
                OperacionBian(
                    operation_id=str(o.get("operation_id", "")),
                    method=str(o.get("method", "")),
                    path=str(o.get("path", "")),
                    tipo=o.get("tipo", "CR"),
                    grupo=str(o.get("grupo", "")),
                    parent_control_record=o.get("parent_control_record"),
                )
                for o in (cuerpo.get("operations") or [])
                if o.get("operation_id")
            ]
            salida[normalizar(nombre)] = (nombre, operaciones)
        self._por_norma = salida
        return salida

    def operaciones_de(self, service_domain: str) -> list[OperacionBian] | None:
        entrada = self._cargar().get(normalizar(service_domain))
        return list(entrada[1]) if entrada is not None else None

    def service_domains_con_catalogo(self) -> set[str]:
        return {nombre for nombre, _ in self._cargar().values()}
