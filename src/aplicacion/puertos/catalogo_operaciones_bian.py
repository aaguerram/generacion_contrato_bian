"""Puerto driven: catálogo local de operaciones oficiales por Service Domain (CR/BQ).

Fuente: `docs/bian-operation-catalogs.json` (extracto normalizado de los catálogos BOM
Extended API oficiales de BIAN R14). Solo cubre los Service Domains para los que hay
evidencia materializada localmente; para el resto devuelve None.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import EvidenciaBian, OperacionBian, SchemaBom


class CatalogoOperacionesBianPort(ABC):
    def asegurar(self, service_domains: list[str], *, actualizar: bool = False) -> dict[str, EvidenciaBian]:
        return {sd: self.evidencia_de(sd) for sd in service_domains}

    def evidencia_de(self, service_domain: str) -> EvidenciaBian:
        return EvidenciaBian()

    def esquemas_de(self, service_domain: str) -> list[str]:
        """Nombres de schema / objetos BOM del Service Domain, o lista vacía si no hay evidencia."""
        return []

    def schemas_detalle_de(self, service_domain: str) -> list[SchemaBom]:
        """Schemas de la Semantic API con cuerpo (properties / enum values), o lista vacía."""
        return []

    def catalogo_estructurado_de(self, service_domain: str) -> dict:
        """Vista `control_records` / `behavior_qualifiers` (con parent_control_record), o {}."""
        return {}

    @abstractmethod
    def operaciones_de(self, service_domain: str) -> list[OperacionBian] | None:
        """Operaciones oficiales (CR + BQ) del Service Domain, o None si no hay catálogo local."""

    @abstractmethod
    def service_domains_con_catalogo(self) -> set[str]:
        """Nombres canónicos de los Service Domains que tienen catálogo de operaciones local."""
