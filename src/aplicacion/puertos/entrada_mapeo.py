"""Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.historias import ResultadoMapeoHistorias


class MapearHistoriasUseCase(ABC):
    @abstractmethod
    def ejecutar(
        self,
        directorio_hu: str,
        ruta_funcionalidad: str,
        directorio_salida: str,
        *,
        reanudar: str | None = None,
    ) -> ResultadoMapeoHistorias:
        """Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea cada
        historia a sus Service Domains y publica el resultado en `directorio_salida`.

        `reanudar` = el `thread_id` de una corrida anterior que murió a mitad (cuota agotada,
        Ctrl-C, el proceso caído). Con durabilidad activada, el checkpointer guardó el estado de
        cada superstep, así que continuar desde ahí solo paga lo que faltaba. Sin durabilidad no
        hay estado que reanudar y se rechaza: es preferible decirlo a re-ejecutar entera una
        corrida que el usuario creía que iba a continuar."""
