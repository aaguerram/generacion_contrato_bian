"""Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import ResultadoMapeoHistorias


class MapearHistoriasUseCase(ABC):
    @abstractmethod
    def ejecutar(
        self, directorio_hu: str, ruta_funcionalidad: str, directorio_salida: str
    ) -> ResultadoMapeoHistorias:
        """Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea cada
        historia a sus Service Domains (SD.json) y publica el resultado en `directorio_salida`."""
