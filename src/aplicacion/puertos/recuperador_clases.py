"""Puerto driven: recuperación de CLASES del BOM BIAN (paso 1 del canal de propiedad).

Distinto de `RecuperadorSemanticoPort`, que devuelve Service Domains: aquí el corpus son las
clases con dueño de `entity.json` y la respuesta es una clase, no un SD. Quién es el dueño lo
decide después el dominio (`candidatos_por_propiedad`), nunca el canal.

Cada adaptador elige qué forma de la consulta lee (`ConsultaClases.texto` natural o
`ConsultaClases.terminos` ya traducidos al BOM) y expone `nombre` para que la fusión y la salida
digan qué canal propuso cada clase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.entidades_bian import CandidatoClase, ConsultaClases


class RecuperadorClasesPort(ABC):
    @property
    @abstractmethod
    def nombre(self) -> str:
        """Identificador estable del canal (`bm25`, `vectorial`, ...) para motivos y métricas."""

    @abstractmethod
    def recuperar(self, consulta: ConsultaClases, k: int) -> list[CandidatoClase]:
        """Top-k clases del BOM más afines a la consulta, mejor primero. Vacío si nada coincide."""
