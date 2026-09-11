"""Puerto driving: la API que ofrece la aplicación."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.dominio.modelos import ResultadoValidacion


class ValidarServiceDomainUseCase(ABC):
    @abstractmethod
    def ejecutar(self, service_domain: str, directorio: str) -> ResultadoValidacion:
        """Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en `directorio`."""
