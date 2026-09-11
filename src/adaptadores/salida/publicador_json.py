"""Adaptador de persistencia: escribe el resultado como JSON en el directorio del run."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from src.aplicacion.puertos.publicador import PublicadorResultadoPort
from src.dominio.modelos import ResultadoValidacion

_NOMBRE = "validacion-service-domain.json"


class PublicadorJson(PublicadorResultadoPort):
    def publicar(self, resultado: ResultadoValidacion, directorio: str) -> str:
        destino = Path(directorio)
        destino.mkdir(parents=True, exist_ok=True)
        documento = resultado.model_dump()
        documento["generado_en"] = dt.datetime.now(dt.timezone.utc).isoformat()
        ruta = destino / _NOMBRE
        ruta.write_text(
            json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(ruta)
