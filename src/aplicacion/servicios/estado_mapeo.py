"""Estado del grafo (outer) de mapeo Historias de Usuario -> Service Domains."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from src.dominio.historias import (
    FuncionalidadMacro,
    HistoriaConServiceDomains,
    HistoriaUsuario,
    MetadatosPrompt,
    ReconciliacionFuncionalidadLLM,
)
from src.dominio.modelos import EntradaCatalogo


class EstadoMapeo(TypedDict, total=False):
    # entrada
    directorio_hu: str
    ruta_funcionalidad: str
    directorio_salida: str
    # cargado
    funcionalidad: FuncionalidadMacro
    historias: list[HistoriaUsuario]
    catalogo: list[EntradaCatalogo]
    # fan-out: cada rama procesa una historia y aporta un elemento (reducer = concatenar)
    procesadas: Annotated[list[HistoriaConServiceDomains], operator.add]
    incidencias: Annotated[list[dict], operator.add]
    huellas_prompts: Annotated[list[MetadatosPrompt], operator.add]
    # reconciliación a nivel de funcionalidad (asesor; el código decide)
    reconciliacion: ReconciliacionFuncionalidadLLM
    # salida
    total_historias: int
    ruta_resultado: str
