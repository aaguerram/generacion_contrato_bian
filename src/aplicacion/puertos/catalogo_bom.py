"""Puerto driven: modelo estructural BOM (clases/enums/asociaciones) por Service Domain.

Fuente: `generacion_contrato_ia_v2/docs/bian-puml/<slug>.puml` (diagramas BOM UML oficiales
de BIAN R14). Complementa a los schemas de la Semantic API: da atributos tipados con
cardinalidad, enums y asociaciones que el OpenAPI no explicita. Sin red.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import ModeloBomPuml


class CatalogoBomPort(ABC):
    @abstractmethod
    def modelo_de(self, service_domain: str) -> ModeloBomPuml | None:
        """Modelo de clases del PUML BOM del Service Domain, o None si no hay `.puml` local."""

    @abstractmethod
    def service_domains_con_bom(self) -> set[str]:
        """Slugs de los Service Domains que tienen `.puml` local."""
