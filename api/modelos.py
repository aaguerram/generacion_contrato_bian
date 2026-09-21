"""Contratos HTTP del módulo API. Pydantic v2, sin dependencias de `src.dominio`.

Están separados de los modelos del dominio a propósito: el frontend no debe acoplarse a la forma
interna del pipeline, y el pipeline no debe cambiar porque cambie un formulario.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoIntento = Literal["guardado", "ejecutando", "completado", "fallido"]


class Funcionalidad(BaseModel):
    """Lo mismo que el JSON que pide el CLI en `--funcionalidad`."""

    label: str = Field(min_length=1, description="funcionalidad_macro: el nombre de la funcionalidad.")
    detalle: str = Field(default="", description="Descripción larga de la funcionalidad.")


class HistoriaEntrada(BaseModel):
    """Una Historia de Usuario tal como la escribe el formulario: título + detalle.

    Es la forma CANÓNICA: el formulario mantiene una lista y cada elemento se guarda entero, en su
    propio campo. Antes esto viajaba como un solo texto que el servidor partía por marcadores, y
    eso rompía en cuanto el detalle de una historia contenía una línea de guiones o un encabezado
    Markdown: el separador partía la historia por la mitad. Con la lista no hay nada que adivinar.
    """

    titulo: str = Field(min_length=1, max_length=200, description="Cómo se reconoce la historia.")
    detalle: str = Field(default="", description="El cuerpo de la historia, tal cual se escribió.")


class OpcionesEjecucion(BaseModel):
    """Los mismos interruptores que acepta `python -m src mapear-historias`."""

    proveedor: str | None = Field(default=None, description="Fuerza un único proveedor LLM.")
    umbral_directo: float | None = Field(default=None, ge=0, le=1)
    umbral_tentativo: float | None = Field(default=None, ge=0, le=1)
    concurrencia: int | None = Field(default=None, ge=1, le=16)
    sin_operaciones: bool = Field(default=False, description="Desactiva el paso 2 (operaciones).")
    actualizar_cache_bian: bool = False


class IntentoCrear(BaseModel):
    """Lo que el formulario manda para GUARDAR un intento. Guardar no ejecuta nada."""

    nombre: str = Field(default="", description="Etiqueta libre para reconocer el intento.")
    historias: list[HistoriaEntrada] = Field(
        min_length=1,
        description="Las Historias de Usuario, una por elemento. El orden es el que se guarda.",
    )
    funcionalidad: Funcionalidad
    opciones: OpcionesEjecucion = Field(default_factory=OpcionesEjecucion)


class HistoriaDetectada(BaseModel):
    archivo: str
    titulo: str
    caracteres: int


class ResumenComparacion(BaseModel):
    """Comparación contra el archivo de validación, si se subió uno."""

    disponible: bool = False
    historias_comparadas: int = 0
    service_domains_esperados: int = 0
    service_domains_coincidentes: int = 0
    faltantes: list[str] = Field(default_factory=list)
    inesperados: list[str] = Field(default_factory=list)
    operaciones_esperadas: int = 0
    operaciones_coincidentes: int = 0
    operaciones_faltantes: list[str] = Field(default_factory=list)
    detalle: str = ""


class Intento(BaseModel):
    """Un intento guardado. Se puede ejecutar varias veces; la última corrida manda."""

    id: str
    nombre: str = ""
    creado_en: datetime
    actualizado_en: datetime
    estado: EstadoIntento = "guardado"
    historias: list[HistoriaEntrada] = Field(default_factory=list)
    funcionalidad: Funcionalidad
    opciones: OpcionesEjecucion = Field(default_factory=OpcionesEjecucion)
    historias_detectadas: list[HistoriaDetectada] = Field(default_factory=list)
    tiene_validacion: bool = False
    nombre_validacion: str = ""
    # De la última ejecución
    iniciado_en: datetime | None = None
    terminado_en: datetime | None = None
    segundos: float | None = None
    error: str = ""
    tiene_resultado: bool = False
    comparacion: ResumenComparacion | None = None


class ListaIntentos(BaseModel):
    total: int
    intentos: list[Intento]


class EstadoEjecucion(BaseModel):
    """Lo que el cliente consulta mientras el mapeo corre. No hay límite de tiempo: se pregunta."""

    id: str
    estado: EstadoIntento
    segundos: float | None = None
    error: str = ""
    lineas_log: list[str] = Field(default_factory=list)


class Proveedores(BaseModel):
    disponibles: list[str]
    cadena_por_defecto: list[str]
