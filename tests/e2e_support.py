"""Helper compartido por las pruebas E2E (integración real, LLM real, bajo demanda).

Estructura práctica para que sumar una prueba E2E nueva sea mecánico. **La carpeta de recursos se
llama IGUAL que el caso de prueba** (sin el prefijo `test_e2e_`), para poder identificarla entre
las demás a simple vista:

    tests/
      resources/
        datos_personales/     <- entradas (HU + funcionalidad) Y salida de test_e2e_datos_personales.py
        <otro_caso>/          <- entradas Y salida de test_e2e_<otro_caso>.py (futura)
      test_e2e_datos_personales.py   -> ejecutar_caso("datos_personales", ...)
      test_e2e_<otro_caso>.py        -> ejecutar_caso("<otro_caso>", ...)

Cada carpeta `resources/<caso>/` es autocontenida: trae sus propias HU (.txt), su propio JSON de
funcionalidad, y `ejecutar_caso()` escribe ahí mismo `mapeo-historias-service-domains.json` como
salida -se sobreescribe en cada corrida, queda como artefacto inspeccionable, no un tempdir que se
borra-. Nunca usar las carpetas compartidas `./HU` / `./ejemplos` de la raíz del proyecto: esas son
para pruebas manuales del CLI, cambian de contenido libremente, y ya rompieron una prueba E2E por
eso.

Bajo demanda (nunca en la suite por defecto — llamadas LLM reales, consumen cuota):

    EJECUTAR_E2E=1 .venv/Scripts/python -m unittest discover -s tests -p "test_e2e_*.py" -v
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from src.configuracion.contenedor import crear_caso_uso_mapeo
from src.configuracion.settings import cargar_settings
from src.dominio.historias import ResultadoMapeoHistorias

RESOURCES = Path(__file__).resolve().parent / "resources"

requiere_e2e = unittest.skipUnless(
    os.environ.get("EJECUTAR_E2E") == "1",
    "prueba de integracion bajo demanda (llamadas LLM reales, consume cuota) -> "
    "EJECUTAR_E2E=1 para correrla explicitamente",
)


def ejecutar_caso(carpeta: str, funcionalidad: str) -> ResultadoMapeoHistorias:
    """Ejecuta `mapear-historias` (LLM real, failover de `config.yaml`) sobre
    `tests/resources/<carpeta>/`. `--directorio-hu` y `--directorio` (salida) son la MISMA
    carpeta: `leer_historias()` solo lee `.txt`/`.md`/`.markdown`, así que ignora el JSON de
    funcionalidad y el de salida que ya viven ahí."""
    datos = RESOURCES / carpeta
    if not datos.is_dir():
        raise FileNotFoundError(f"falta la carpeta de datos de la prueba: {datos}")
    ruta_funcionalidad = datos / funcionalidad
    if not ruta_funcionalidad.is_file():
        raise FileNotFoundError(f"falta el JSON de funcionalidad: {ruta_funcionalidad}")

    config = cargar_settings()
    caso_uso = crear_caso_uso_mapeo(config)
    return caso_uso.ejecutar(str(datos), str(ruta_funcionalidad), str(datos))
