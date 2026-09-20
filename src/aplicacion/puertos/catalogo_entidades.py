"""Puerto driven: catálogo de CLASES del BOM BIAN y su propiedad por Service Domain.

Fuente: `generacion_contrato_ia_v2/docs/entity.json` (2.668 clases extraídas de los diagramas BOM
y Control Record de BIAN R14). Responde una sola pregunta que ninguna otra fuente contesta:
**qué Service Domain DEFINE cada clase** -frente a los que solo la referencian-, que es la señal
con la que `entidades_bian` propone candidatos.

Sin red y sin LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.entidades_bian import ClaseBian


class CatalogoEntidadesBianPort(ABC):
    @abstractmethod
    def clases(self) -> dict[str, ClaseBian]:
        """Todas las clases indexadas por nombre exacto. Vacío si no hay archivo local."""

    @abstractmethod
    def nombres_enum(self) -> frozenset[str]:
        """Nombres de las clases que son enumeraciones (para distinguir tipificar de guardar)."""
