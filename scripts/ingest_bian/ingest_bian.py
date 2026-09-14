"""Construye el modelo canónico BIAN (`GrafoBian`) desde las fuentes de `docs/`.

Entradas (todas locales, sin red):
  - `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` -> Service Domains + jerarquía
  - `docs/bian-cache/release14.0.0/<SD>.json`            -> Control Records, BQ, operaciones, schemas
  - `docs/bian-diagrams/puml-bom/<slug>.puml`            -> clases y asociaciones del BOM

Salida: `docs/bian-graph/release14.0.0/grafo.json` (un `GrafoBian` serializado).

Qué aporta sobre lo que ya había: hoy cada adaptador parsea su fuente y el pipeline las cruza por
nombre donde hace falta. Eso responde "¿qué operaciones tiene este SD?" pero no "¿con qué otros SD
se relaciona según el propio BOM de BIAN?", que es lo que necesita la expansión por grafo.

Dos reglas que no se relajan:
  - **Toda arista lleva su archivo de origen.** Una relación sin procedencia no se ingesta.
  - **Las referencias colgantes no se silencian**: una operación cuyo `response_schema` no existe
    en `schemas_detalle`, o una asociación del PUML hacia una clase que el diagrama no declara,
    se anotan en `incidencias` y quedan en el JSON.

Idempotente: mismas entradas -> mismo grafo (nodos y aristas ordenados). Sin red.

Uso:
    .venv/bin/python scripts/ingest_bian/ingest_bian.py
    .venv/bin/python scripts/ingest_bian/ingest_bian.py --verificar
    .venv/bin/python scripts/ingest_bian/ingest_bian.py --solo "Correspondence,Party Authentication"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache  # noqa: E402
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml  # noqa: E402
from src.adaptadores.salida.catalogo_json import CatalogoJson  # noqa: E402
from src.dominio.grafo_bian import AristaBian, GrafoBian, NodoBian, id_nodo  # noqa: E402

DOCS = RAIZ / "docs"
LANDSCAPE = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"
CACHE = DOCS / "bian-cache"
OPERACIONES_LEGADO = DOCS / "bian-operation-catalogs.json"
PUML = DOCS / "bian-diagrams/puml-bom"
RELEASE = "14.0.0"
SALIDA = DOCS / "bian-graph" / f"release{RELEASE}" / "grafo.json"

_ORIGEN_LANDSCAPE = f"docs/{LANDSCAPE.name}"
_ORIGEN_CACHE = f"docs/bian-cache/release{RELEASE}"
_ORIGEN_PUML = "docs/bian-diagrams/puml-bom"


class _Constructor:
    def __init__(self) -> None:
        self.nodos: dict[str, NodoBian] = {}
        self.aristas: set[tuple[str, str, str, str]] = set()
        self.incidencias: list[str] = []

    def nodo(
        self,
        tipo,
        nombre: str,
        *,
        clave: tuple[str, ...],
        origen: str,
        sd=None,
        atributos: dict | None = None,
    ):
        # `atributos` va como dict y no como **kwargs: los datos de la fuente incluyen claves como
        # `tipo` o `nombre`, que chocarían con los parámetros del método.
        atrs = atributos or {}
        nid = id_nodo(tipo, *clave)
        if nid not in self.nodos:
            self.nodos[nid] = NodoBian(
                id=nid,
                tipo=tipo,
                nombre=nombre,
                service_domain=sd,
                atributos={k: str(v) for k, v in atrs.items() if v},
                origen=origen,
            )
        return nid

    def arista(self, desde: str, hasta: str, tipo: str, origen: str) -> None:
        if desde and hasta:
            self.aristas.add((desde, hasta, tipo, origen))

    def construir(self) -> GrafoBian:
        return GrafoBian(
            release=RELEASE,
            nodos=sorted(self.nodos.values(), key=lambda n: (n.tipo, n.id)),
            aristas=sorted(
                (AristaBian(desde=d, hasta=h, tipo=t, origen=o) for d, h, t, o in self.aristas),
                key=lambda a: (a.tipo, a.desde, a.hasta),
            ),
            incidencias=sorted(set(self.incidencias)),
        )


def ingestar(solo: set[str] | None = None) -> GrafoBian:
    c = _Constructor()
    catalogo = CatalogoJson(LANDSCAPE)
    cache = CatalogoBianCache(
        str(OPERACIONES_LEGADO), str(CACHE), RELEASE, permitir_descargas=False
    )
    bom = CatalogoBomPuml(str(PUML))

    for e in catalogo.cargar():
        if solo and e.service_domain not in solo:
            continue
        sd_id = c.nodo(
            "SERVICE_DOMAIN",
            e.service_domain,
            clave=(e.service_domain,),
            origen=_ORIGEN_LANDSCAPE,
            sd=e.service_domain,
            atributos={
                "functional_pattern": e.functional_pattern,
                "asset_type": e.asset_type,
                "control_record": e.control_record,
            },
        )
        if e.business_domain:
            bd_id = c.nodo(
                "BUSINESS_DOMAIN",
                e.business_domain,
                clave=(e.business_domain,),
                origen=_ORIGEN_LANDSCAPE,
            )
            c.arista(sd_id, bd_id, "PERTENECE_A", _ORIGEN_LANDSCAPE)
            if e.business_area:
                ba_id = c.nodo(
                    "BUSINESS_AREA",
                    e.business_area,
                    clave=(e.business_area,),
                    origen=_ORIGEN_LANDSCAPE,
                )
                c.arista(bd_id, ba_id, "PERTENECE_A", _ORIGEN_LANDSCAPE)

        _ingestar_operaciones(c, cache, e.service_domain, sd_id)
        _ingestar_bom(c, bom, e.service_domain, sd_id)

    return c.construir()


def _ingestar_operaciones(c: _Constructor, cache, sd: str, sd_id: str) -> None:
    operaciones = cache.operaciones_de(sd)
    if not operaciones:
        return
    schemas = {s.name for s in cache.schemas_detalle_de(sd)}

    for op in operaciones:
        tipo_grupo = "CONTROL_RECORD" if op.tipo == "CR" else "BEHAVIOR_QUALIFIER"
        grupo_id = c.nodo(tipo_grupo, op.grupo, clave=(sd, op.grupo), origen=_ORIGEN_CACHE, sd=sd)
        if op.tipo == "CR":
            c.arista(sd_id, grupo_id, "HAS_CR", _ORIGEN_CACHE)
        else:
            padre = op.parent_control_record
            if padre:
                padre_id = c.nodo(
                    "CONTROL_RECORD", padre, clave=(sd, padre), origen=_ORIGEN_CACHE, sd=sd
                )
                c.arista(padre_id, grupo_id, "HAS_BQ", _ORIGEN_CACHE)
                c.arista(sd_id, padre_id, "HAS_CR", _ORIGEN_CACHE)
            else:
                c.arista(sd_id, grupo_id, "HAS_BQ", _ORIGEN_CACHE)
                c.incidencias.append(f"BQ sin parent_control_record: {sd}/{op.grupo}")

        op_id = c.nodo(
            "OPERATION",
            op.operation_id,
            clave=(sd, op.operation_id),
            origen=_ORIGEN_CACHE,
            sd=sd,
            atributos={"method": op.method, "path": op.path, "tipo_operacion": op.tipo},
        )
        c.arista(grupo_id, op_id, "HAS_OPERATION", _ORIGEN_CACHE)

        for schema, rel in ((op.response_schema, "RESPONDE_CON"), (op.request_schema, "RECIBE")):
            if not schema:
                continue
            if schema not in schemas:
                c.incidencias.append(
                    f"{sd}/{op.operation_id}: schema '{schema}' no está en schemas_detalle"
                )
                continue
            s_id = c.nodo("SCHEMA", schema, clave=(sd, schema), origen=_ORIGEN_CACHE, sd=sd)
            c.arista(op_id, s_id, rel, _ORIGEN_CACHE)

    # $ref entre schemas del mismo SD: relación real declarada por la Semantic API.
    for s in cache.schemas_detalle_de(sd):
        origen_id = c.nodo("SCHEMA", s.name, clave=(sd, s.name), origen=_ORIGEN_CACHE, sd=sd)
        for prop in s.properties:
            if prop.ref and prop.ref in schemas:
                destino_id = c.nodo(
                    "SCHEMA", prop.ref, clave=(sd, prop.ref), origen=_ORIGEN_CACHE, sd=sd
                )
                c.arista(origen_id, destino_id, "REFERENCIA", _ORIGEN_CACHE)


def _ingestar_bom(c: _Constructor, bom, sd: str, sd_id: str) -> None:
    modelo = bom.modelo_de(sd)
    if modelo is None:
        return
    declaradas = {cl.name for cl in modelo.clases}
    for cl in modelo.clases:
        cid = c.nodo(
            "BOM_CLASS",
            cl.name,
            clave=(cl.name,),  # sin el SD: la MISMA clase compartida entre SD es la señal de grafo
            origen=_ORIGEN_PUML,
            atributos={"atributos_n": len(cl.attributes)},
        )
        c.arista(sd_id, cid, "MODELA", _ORIGEN_PUML)

    for aso in modelo.asociaciones:
        for extremo in (aso.origen, aso.destino):
            if extremo not in declaradas:
                c.incidencias.append(
                    f"{sd}: asociación BOM hacia clase no declarada en el diagrama ('{extremo}')"
                )
        if aso.origen in declaradas and aso.destino in declaradas:
            c.arista(
                id_nodo("BOM_CLASS", aso.origen),
                id_nodo("BOM_CLASS", aso.destino),
                "ASOCIA",
                _ORIGEN_PUML,
            )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--verificar",
        action="store_true",
        help="No escribe; falla si el grafo en disco no coincide.",
    )
    p.add_argument(
        "--solo", default="", help="Lista de Service Domains separados por coma (para pruebas)."
    )
    args = p.parse_args(argv)

    solo = {s.strip() for s in args.solo.split(",") if s.strip()} or None
    grafo = ingestar(solo)
    texto = grafo.model_dump_json(indent=2) + "\n"

    from collections import Counter

    print(f"nodos   : {len(grafo.nodos)}  {dict(Counter(n.tipo for n in grafo.nodos))}")
    print(f"aristas : {len(grafo.aristas)}  {dict(Counter(a.tipo for a in grafo.aristas))}")
    print(f"incidencias: {len(grafo.incidencias)}")
    for i in grafo.incidencias[:5]:
        print(f"   - {i}")

    if args.verificar:
        if not SALIDA.is_file():
            print(f"FALTA {SALIDA.relative_to(RAIZ)}: correr el script sin --verificar")
            return 1
        if SALIDA.read_text(encoding="utf-8") != texto:
            print(f"DESACTUALIZADO {SALIDA.relative_to(RAIZ)}: regenerar")
            return 1
        print(f"OK {SALIDA.relative_to(RAIZ)} al día")
        return 0

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(texto, encoding="utf-8")
    print(f"escrito {SALIDA.relative_to(RAIZ)} ({len(texto) / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
