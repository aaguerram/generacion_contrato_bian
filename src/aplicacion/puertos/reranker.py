"""Puerto driven: reordenamiento fino de candidatos ya recuperados."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RerankerPort(ABC):
    @abstractmethod
    def reordenar(
        self, consulta: str, documentos: list[tuple[str, str]], *, tope: int
    ) -> list[tuple[str, float]]:
        """Reordena `(clave, texto)` por relevancia real frente a la consulta.

        Devuelve `(clave, score)` de mayor a menor, como mucho `tope`. Es un RECUPERADOR, no un
        juez: reordena y recorta, nunca decide ownership ni inventa candidatos. Si el motivo de
        recorte importa aguas abajo, quien llama lo registra; este puerto no toma decisiones
        contractuales.
        """
