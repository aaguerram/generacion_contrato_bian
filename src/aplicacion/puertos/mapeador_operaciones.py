"""Puerto driven: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia y, cuando
ningún CR/BQ oficial cubre un campo que la historia necesita, propone un BQ personalizado
(solo si el BOM del Service Domain lo respalda con evidencia citable).

Solo se invoca para los Service Domains DIRECTOS de una historia que tienen catálogo de
operaciones local. El adaptador construye el prompt únicamente con esas operaciones + el BOM
provisto; los operationId que no estén en la lista se descartan aguas abajo, y todo BQ
personalizado se ancla y valida contra el BOM de forma determinista (nunca se acepta a ciegas).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import (
    FuncionalidadMacro,
    HistoriaUsuario,
    MapeoOperacionesLLM,
    OperacionBian,
    PaqueteEvidenciaCandidato,
)


class MapeadorOperacionesBianPort(ABC):
    @abstractmethod
    def mapear(
        self,
        historia: HistoriaUsuario,
        funcionalidad: FuncionalidadMacro,
        operaciones_por_sd: dict[str, list[OperacionBian]],
        paquetes_por_sd: dict[str, PaqueteEvidenciaCandidato],
    ) -> MapeoOperacionesLLM:
        """Devuelve, por Service Domain, las operaciones oficiales que implementan la historia,
        y (aparte) los BQ personalizados propuestos cuando el BOM de `paquetes_por_sd` respalda
        un campo que ninguna operación oficial cubre."""
