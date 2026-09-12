"""Formateo compartido del BOM (schemas de la Semantic API + modelo de clases PUML) para prompts.

Usado por `analista_mapeo_langchain.py` (evaluar_candidato) y `mapeador_operaciones_langchain.py`
(seleccionar_operaciones / detección de BQ personalizado).
"""

from __future__ import annotations

from src.dominio.historias import ModeloBomPuml, SchemaBom
from src.dominio.normalizacion import normalizar


def _recortar(texto: str, limite: int) -> str:
    t = " ".join((texto or "").split())
    return t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "..."


def _ordenar_priorizado(elementos: list, clave_nombre, priorizar: set[str] | None) -> list:
    """Reordena `elementos` (no los descarta) para que los que calzan `priorizar` (nombres
    normalizados) vayan primero. Sin esto, un corte por `limite` puede excluir en silencio un
    schema/clase que SÍ es relevante (p.ej. el response_schema de una operación candidata) solo
    porque su nombre cae después alfabéticamente. `priorizar=None` deja el orden intacto."""
    if not priorizar:
        return elementos
    return sorted(elementos, key=lambda e: 0 if normalizar(clave_nombre(e)) in priorizar else 1)


def formatear_schemas_bom(
    schemas_detalle: list[SchemaBom], *, limite: int = 22, priorizar: set[str] | None = None
) -> str:
    if not schemas_detalle:
        return "  (la evidencia solo trae nombres de schema, sin cuerpo)"
    ordenados = _ordenar_priorizado(schemas_detalle, lambda s: s.name, priorizar)
    filas = []
    for s in ordenados[:limite]:
        if s.kind == "enum":
            filas.append(f"  {s.name} (enum): {', '.join(s.enum_values[:12])}")
        elif s.properties:
            props = ", ".join(
                (f"{p.name}:{p.ref or p.type}" if (p.ref or p.type) else p.name) for p in s.properties[:12]
            )
            filas.append(f"  {s.name}: {{ {props} }}")
        else:
            filas.append(f"  {s.name} ({s.kind})")
    if len(ordenados) > limite:
        filas.append(f"  … (+{len(ordenados) - limite} schemas más)")
    return "\n".join(filas)


def formatear_bom_puml(
    modelo: ModeloBomPuml | None, *, limite: int = 14, priorizar: set[str] | None = None
) -> str:
    if modelo is None or not (modelo.clases or modelo.enums):
        return "  (sin diagrama BOM PUML local para este Service Domain)"
    filas = []
    for c in _ordenar_priorizado(modelo.clases, lambda c: c.name, priorizar)[:limite]:
        if c.attributes:
            attrs = ", ".join(
                (f"{a.name}: {a.type}{'[' + a.cardinality + ']' if a.cardinality else ''}").strip()
                for a in c.attributes[:10]
            )
            filas.append(f"  class {c.name} {{ {attrs} }}")
        else:
            filas.append(f"  class {c.name}")
    for e in modelo.enums[:6]:
        filas.append(f"  enum {e.name}: {', '.join(e.values[:10])}")
    for a in modelo.asociaciones[:12]:
        rel = "--|>" if a.tipo == "herencia" else "--"
        et = f' "{a.etiqueta}"' if a.etiqueta else ""
        filas.append(f"  {a.origen} {rel}{et} {a.destino}")
    return "\n".join(filas)
