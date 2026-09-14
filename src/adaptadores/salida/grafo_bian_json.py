"""Adaptador: expansión por el grafo canónico BIAN ingestado en `docs/bian-graph/`.

Carga perezosa y una sola vez por proceso: el grafo real son ~26.000 nodos y ~58.000 aristas
(18 MB), y su carga cuesta ~0,1 s — barato frente a una llamada LLM, pero no algo que hacer por
cada historia. Si el archivo no existe (nadie corrió `scripts/ingest_bian/`), el adaptador se
comporta como si no hubiera grafo: devuelve vacío y lo dice UNA vez en el log, en vez de reventar
la corrida. Misma filosofía que el resto del retrieval: si una fuente falta, se sigue con lo que
haya.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.aplicacion.puertos.grafo_bian import GrafoBianPort
from src.dominio.grafo_bian import CandidatoGrafo, GrafoBian

logger = logging.getLogger(__name__)


class GrafoBianJson(GrafoBianPort):
    def __init__(self, ruta_grafo: str | Path, *, max_sd_por_puente: int | None = None) -> None:
        self._ruta = Path(ruta_grafo)
        self._max_sd_por_puente = max_sd_por_puente
        self._grafo: GrafoBian | None = None
        self._avisado = False

    def _cargar(self) -> GrafoBian | None:
        if self._grafo is not None:
            return self._grafo
        if not self._ruta.is_file():
            if not self._avisado:
                logger.warning(
                    "Grafo BIAN no encontrado en %s; expansión por grafo desactivada "
                    "(generarlo con scripts/ingest_bian/ingest_bian.py)",
                    self._ruta,
                )
                self._avisado = True
            return None
        self._grafo = GrafoBian.model_validate_json(self._ruta.read_text(encoding="utf-8"))
        logger.info(
            "Grafo BIAN cargado: %d nodos, %d aristas", len(self._grafo.nodos), len(self._grafo.aristas)
        )
        return self._grafo

    def expandir(self, service_domains: list[str], *, tope: int) -> list[CandidatoGrafo]:
        grafo = self._cargar()
        if grafo is None or not service_domains:
            return []

        kwargs = {"tope": tope}
        if self._max_sd_por_puente is not None:
            kwargs["max_sd_por_puente"] = self._max_sd_por_puente

        # Un SD alcanzado desde VARIOS de los candidatos de partida es mejor señal que uno
        # alcanzado desde uno solo: se suman los scores y se unen los puentes que lo justifican.
        acumulado: dict[str, CandidatoGrafo] = {}
        origen = {sd for sd in service_domains}
        for sd in service_domains:
            for c in grafo.service_domains_alcanzables(sd, **kwargs):
                if c.service_domain in origen:
                    continue
                previo = acumulado.get(c.service_domain)
                if previo is None:
                    acumulado[c.service_domain] = c.model_copy(deep=True)
                    continue
                previo.score = round(min(1.0, previo.score + c.score), 4)
                for p in c.puentes:
                    if p not in previo.puentes:
                        previo.puentes.append(p)

        salida = sorted(acumulado.values(), key=lambda c: (-c.score, c.service_domain))
        return salida[:tope]
