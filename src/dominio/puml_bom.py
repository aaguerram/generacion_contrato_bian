"""Parser del PUML BOM BIAN -> `ModeloBomPuml` (clases + enums + asociaciones).

Puro: stdlib + dominio. Los `.puml` viven en `generacion_contrato_ia_v2/docs/bian-puml/`
(copiados de los diagramas BOM UML oficiales de BIAN R14, extracción SVG). El adaptador
`CatalogoBomPuml` los lee; este módulo solo parsea texto.
"""

from __future__ import annotations

import re

from src.dominio.historias import AsociacionBom, AtributoBom, ClaseBom, EnumBom, ModeloBomPuml

_RE_BLOQUE = re.compile(r'^\s*(class|enum)\s+"([^"]+)"\s+as\s+(\w+)\s*\{?\s*$')
_RE_ATRIBUTO = re.compile(r"^\s*\+\s*(.+?)\s*:\s*(.+?)\s*$")
_RE_CARD = re.compile(r"^(.*?)\s*\[([^\]]+)\]\s*$")
_RE_VALOR_ENUM = re.compile(r"^\s*([A-Za-z][\w /-]*?)\s*$")
_RE_SD = re.compile(r"Service Domain:\s*(.+?)\s*$")
_RE_SRC = re.compile(r"BIAN source:\s*(\S+)")
# N1 "card" -- "card" N2   |   N1 <|-- N2   |   N1 --|> N2   |   N1 --> N2
_RE_REL = re.compile(
    r'^\s*(\w+)\s+(?:"([^"]*)"\s+)?(<\|--|--\|>|-->|<--|\.\.>|<\.\.|--)\s+(?:"([^"]*)"\s+)?(\w+)\s*$'
)


def parsear_puml_bom(texto: str, *, service_domain: str = "", slug: str = "") -> ModeloBomPuml:
    alias: dict[str, str] = {}          # Nxxxx -> nombre legible
    clases: dict[str, ClaseBom] = {}
    enums: dict[str, EnumBom] = {}
    asociaciones: list[AsociacionBom] = []
    sd, src = service_domain, ""

    actual_tipo: str | None = None      # "class" | "enum" mientras estamos dentro de un bloque {}
    actual_nombre: str | None = None
    en_relaciones = False

    for linea in texto.splitlines():
        cruda = linea.rstrip()
        cuerpo = cruda.lstrip("' ").strip()

        if not sd and (m := _RE_SD.search(cuerpo)):
            sd = m.group(1)
        if not src and (m := _RE_SRC.search(cuerpo)):
            src = m.group(1)
        if cuerpo.lower().startswith("relationships"):
            en_relaciones = True
            continue

        if actual_tipo is not None:
            if cruda.strip() == "}":
                actual_tipo = actual_nombre = None
                continue
            if actual_tipo == "class":
                if (m := _RE_ATRIBUTO.match(cruda)):
                    tipo_raw = m.group(2)
                    card = ""
                    if (mc := _RE_CARD.match(tipo_raw)):
                        tipo_raw, card = mc.group(1).strip(), mc.group(2).strip()
                    clases[actual_nombre].attributes.append(
                        AtributoBom(name=m.group(1).strip(), type=tipo_raw, cardinality=card)
                    )
            elif actual_tipo == "enum":
                token = cruda.strip()
                if token and token != "{" and (m := _RE_VALOR_ENUM.match(token)):
                    enums[actual_nombre].values.append(m.group(1).strip())
            continue

        if (m := _RE_BLOQUE.match(cruda)):
            kind, nombre, ident = m.group(1), m.group(2).strip(), m.group(3)
            alias[ident] = nombre
            if kind == "class":
                clases.setdefault(nombre, ClaseBom(name=nombre))
            else:
                enums.setdefault(nombre, EnumBom(name=nombre))
            # ¿abre bloque en esta misma línea?
            actual_tipo = kind if cruda.rstrip().endswith("{") else None
            actual_nombre = nombre if actual_tipo else None
            continue

        if en_relaciones and (m := _RE_REL.match(cruda)):
            a, la, flecha, lb, b = m.groups()
            na, nb = alias.get(a, a), alias.get(b, b)
            etiqueta = " / ".join(p for p in (la, lb) if p)
            if flecha in ("<|--", "<.."):        # b hereda de a
                asociaciones.append(AsociacionBom(origen=nb, destino=na, tipo="herencia"))
            elif flecha in ("--|>", "..>"):      # a hereda de b
                asociaciones.append(AsociacionBom(origen=na, destino=nb, tipo="herencia"))
            else:
                asociaciones.append(
                    AsociacionBom(origen=na, destino=nb, etiqueta=etiqueta, tipo="asociacion")
                )

    return ModeloBomPuml(
        service_domain=sd or service_domain,
        source_url=src,
        slug=slug,
        clases=sorted(clases.values(), key=lambda c: c.name),
        enums=sorted(enums.values(), key=lambda e: e.name),
        asociaciones=asociaciones,
    )
