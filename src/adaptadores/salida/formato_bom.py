"""Formateo compartido del BOM (schemas de la Semantic API + modelo de clases PUML) para prompts.

Usado por `analista_mapeo_langchain.py` (evaluar_candidato) y `mapeador_operaciones_langchain.py`
(seleccionar_operaciones / detección de BQ personalizado).
"""

from __future__ import annotations

from src.dominio.historias import ModeloBomPuml, SchemaBom


def _recortar(texto: str, limite: int) -> str:
    t = " ".join((texto or "").split())
    return t if len(t) <= limite else t[:limite].rsplit(" ", 1)[0] + "..."


def formatear_schemas_bom(schemas_detalle: list[SchemaBom], *, limite: int = 22) -> str:
    if not schemas_detalle:
        return "  (la evidencia solo trae nombres de schema, sin cuerpo)"
    filas = []
    for s in schemas_detalle[:limite]:
        if s.kind == "enum":
            filas.append(f"  {s.name} (enum): {', '.join(s.enum_values[:12])}")
        elif s.properties:
            props = ", ".join(
                (f"{p.name}:{p.ref or p.type}" if (p.ref or p.type) else p.name) for p in s.properties[:12]
            )
            filas.append(f"  {s.name}: {{ {props} }}")
        else:
            filas.append(f"  {s.name} ({s.kind})")
    if len(schemas_detalle) > limite:
        filas.append(f"  … (+{len(schemas_detalle) - limite} schemas más)")
    return "\n".join(filas)


def formatear_bom_puml(modelo: ModeloBomPuml | None, *, limite: int = 14) -> str:
    if modelo is None or not (modelo.clases or modelo.enums):
        return "  (sin diagrama BOM PUML local para este Service Domain)"
    filas = []
    for c in modelo.clases[:limite]:
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
