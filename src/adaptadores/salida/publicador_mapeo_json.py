"""Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como JSON."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from src.aplicacion.puertos.publicador_mapeo import PublicadorMapeoPort
from src.dominio.historias import ResultadoMapeoHistorias

_NOMBRE = "mapeo-historias-service-domains.json"


class PublicadorMapeoJson(PublicadorMapeoPort):
    def __init__(self, nombre_archivo: str = _NOMBRE) -> None:
        self._nombre = nombre_archivo

    def publicar(self, resultado: ResultadoMapeoHistorias, directorio: str) -> str:
        destino = Path(directorio)
        destino.mkdir(parents=True, exist_ok=True)
        documento = resultado.model_dump()
        documento["generado_en"] = dt.datetime.now(dt.timezone.utc).isoformat()
        ruta = destino / self._nombre
        ruta.write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(ruta)
