"""
Genera `docs/bian-object-catalog.json`: para cada Service Domain, cada clase
del BIAN BOM y cada Business Area, el link directo a su pagina de objeto en
bian.org (`object_<N>.html?object=<id>` — la pagina a la que se llega al
hacer click en una clase/Service Domain/Business Area, con su documentacion
en prosa) y esa documentacion ya extraida como texto plano.

## Por que esto no es un simple "armar la URL"

La URL tiene la forma `object_<N>.html?object=<id>` y en un principio parece
que `<N>` fuera un "tipo" fijo (Service Domain, Class, ...). No lo es: es el
numero de un **shard interno del sitio** (`data/all_objects_data_<N>.js`),
resultado de como bian.org particiono su base de ~127.000 objetos en 47
archivos. Confirmado navegando bian.org en vivo:

- `data/all_objects_data_mapping.js` trae `{object_id: numero_de_shard}`
  para los ~127.000 objetos del sitio (no solo Service Domains ni BOM).
- Cada `data/all_objects_data_<N>.js` (N de 1 a 47) trae, para los objetos
  de ESE shard, `{object_id: {name, type, categories:[documentacion...]}}`.
- El shard de un objeto **no se puede predecir por su nombre o su tipo**: el
  shard 14 (3266 KB) tiene 3495 objetos, de los cuales solo 243 de los 348
  Service Domains conocidos estan ahi — el resto cae en otros shards, y lo
  mismo pasa con las clases del BIAN BOM. La unica forma confiable de
  resolver "nombre -> object_id" es indexar los 47 shards completos (~142 MB
  en total) y buscar por nombre en el indice combinado.

Se valido el mecanismo con los 2 IDs conocidos: `object_14.html?object=31128`
es realmente "Customer Product and Service Directory", y
`object_8.html?object=31805` es realmente "Product Agreement" (no 31806:
ese es el id de un objeto vecino).

Ver README.md en esta misma carpeta para el detalle completo, el formato de
`bian-object-catalog.json` y como se resuelven los nombres ambiguos.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = "https://bian.org/servicelandscape-14-0-0"
MAPPING_URL = f"{BASE}/data/all_objects_data_mapping.js"
SHARD_URL_TMPL = f"{BASE}/data/all_objects_data_{{n}}.js"
OBJECT_URL_TMPL = f"{BASE}/object_{{shard}}.html?object={{object_id}}"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "descarga" / "bian-object-catalog-shards"
DEFAULT_VIEW_CATALOG = REPO_ROOT / "docs" / "bian-view-catalog.json"
DEFAULT_XLSX = REPO_ROOT / "docs" / "BIANBOM4XMI.xlsx"
DEFAULT_MATRIX_VIEW = REPO_ROOT / "docs" / "BIAN_Service_Landscape_V14.0_Matrix_View.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "bian-object-catalog.json"

# Tipo ArchiMate/InSite preferido cuando un nombre matchea mas de 1 objeto en
# el indice combinado. Esto pasa MUCHO (no poco): cada vez que una clase se
# dibuja dentro de un diagrama, bian.org le da su propio objeto de tipo
# "Class" (equivalente al alias posicional que ya vimos en los .puml locales
# — de hecho coinciden: p.ej. el candidato "Class"/81615 de "Product
# Agreement" es EL MISMO id que el alias `N81615` que extrajo
# `svg_to_puml` para esa clase en el diagrama de Customer Product and
# Service Directory). Esos "Class" son, en la enorme mayoria de los casos,
# duplicados de una unica definicion canonica marcada con un tipo mas
# especifico — por eso la lista esta ORDENADA por prioridad: se usa el
# primer tipo de la lista que matchee exactamente 1 candidato.
PREFERRED_TYPES = {
    "service_domains": ("Capability",),
    "bian_bom_classes": ("Business object", "Enumeration", "Data type", "Primitive type"),
    "business_areas": ("Grouping",),  # confirmado con "Reference Data": stereotype BusinessArea
    "business_domains": (
        "Capability",
    ),  # confirmado con "Party": type Capability, stereotype BusinessDomain
}


# ---------------------------------------------------------------------------
# Descarga con cache local (los shards pesan ~142 MB en total: se bajan una
# sola vez a `.cache/` -ignorado por git- y las corridas siguientes los
# reusan sin pegarle de nuevo a bian.org).
# ---------------------------------------------------------------------------


def _fetch_text(url: str, cache_path: Path, force_refresh: bool) -> str:
    if cache_path.exists() and not force_refresh:
        return cache_path.read_text(encoding="utf-8")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def _extract_js_object(text: str, var_name: str) -> dict:
    m = re.search(rf"var {var_name}\s*=\s*(\{{.*\}})\s*;", text, re.DOTALL)
    if not m:
        raise ValueError(f"No se encontro 'var {var_name} = {{...}}' en el archivo fuente")
    return json.loads(m.group(1))


_BLOCK_TAG_RE = re.compile(r"</?(?:p|br|div)[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_NUMBERED_TITLE_RE = re.compile(r"^\s*\d+\s*\.\s*(.+)$")


def _clean_html(raw: str) -> str | None:
    """HTML/RTF suelto (p.ej. `<span style="...">texto&nbsp;<p>...</p></span>`)
    a texto plano, preservando saltos de linea en los tags de bloque (`<p>`,
    `<br>`) para no pegar en una sola linea listas como "Key Features"."""

    text = _BLOCK_TAG_RE.sub("\n", raw)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines) if lines else None


def _slugify_section_title(title: str) -> str:
    """ "1. Role Definition" -> "role_definition"; "documentation" ->
    "documentation" (el titulo generico y literal que trae bian.org para la
    seccion "Documentation" de la pagina, la unica que NO viene numerada)."""

    m = _NUMBERED_TITLE_RE.match(title or "")
    text = m.group(1) if m else (title or "documentation")
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "documentation"


def _extract_documentation_sections(entry_data: dict) -> dict[str, str | None]:
    """{slug -> texto plano} de CADA categoria `type: "documentation"` del
    objeto. Un objeto de Service Domain en bian.org trae varias: "1. Role
    Definition", "2. Example of Use", "3. Executive Summary", "4. Key
    Features", mas una seccion generica titulada literalmente
    "documentation" (a veces vacia — VERIFICADO con "Card Authorization"
    (object_id 41757): esa 5ta seccion esta vacia `""` en el propio dato de
    bian.org, mientras "1. Role Definition" trae todo el texto; tomar solo
    la PRIMERA categoria (como hacia una version anterior de esta funcion)
    devolvia el texto de Role Definition como si fuera "la documentacion"
    del objeto, cuando la pagina real muestra esa seccion vacia). Por eso se
    devuelven todas, separadas por su propio slug — nunca se colapsan en 1
    sola string."""

    sections: dict[str, str | None] = {}
    for category in entry_data.get("categories") or []:
        if category.get("type") != "documentation":
            continue
        title = category.get("title") or "documentation"
        raw = (category.get("content") or {}).get("value") or ""
        sections[_slugify_section_title(title)] = _clean_html(raw)
    return sections


def load_shard_mapping(cache_dir: Path, force_refresh: bool) -> dict[str, int]:
    text = _fetch_text(MAPPING_URL, cache_dir / "all_objects_data_mapping.js", force_refresh)
    return _extract_js_object(text, "objectDataMapping")


def load_shard(cache_dir: Path, shard_n: int, force_refresh: bool) -> dict[str, dict]:
    url = SHARD_URL_TMPL.format(n=shard_n)
    text = _fetch_text(url, cache_dir / f"all_objects_data_{shard_n}.js", force_refresh)
    return _extract_js_object(text, "objectData")


def build_name_index(
    cache_dir: Path, force_refresh: bool
) -> tuple[dict[str, list[dict]], dict[int, dict[str, str | None]]]:
    """({nombre -> [{object_id, shard, type}, ...]}, {object_id -> {slug_seccion -> texto}})
    recorriendo los 47 shards.

    Un mismo nombre puede aparecer mas de una vez (en el mismo shard o en
    shards distintos) si bian.org tiene 2 objetos con el mismo texto visible
    (p.ej. un Service Domain y una nota/grouping con igual nombre).

    IMPORTANTE: un mismo `object_id` aparece fisicamente duplicado en varios
    shards a la vez (se comprobo: el id 31128 -"Customer Product and Service
    Directory"- esta repetido, identico, en 15+ de los 47 shards — no es que
    haya 15 objetos distintos, es el mismo registro replicado). Por eso se
    dedupea por `object_id` (no por (object_id, shard)) y el `shard` que se
    reporta es siempre el CANONICO de `all_objects_data_mapping.js`, sin
    importar en cual de los shards duplicados se lo haya visto primero.
    """

    shard_mapping = load_shard_mapping(cache_dir, force_refresh)
    shard_numbers = sorted(set(shard_mapping.values()))
    print(
        f"  {len(shard_mapping)} objetos indexados en {len(shard_numbers)} shards (data/all_objects_data_<N>.js)"
    )

    index: dict[str, dict[int, dict]] = {}
    object_sections: dict[int, dict[str, str | None]] = {}
    for i, shard_n in enumerate(shard_numbers, start=1):
        t0 = time.time()
        shard_data = load_shard(cache_dir, shard_n, force_refresh)
        for object_id_str, obj in shard_data.items():
            entries = obj.get("data") or []
            if not entries:
                continue
            entry0 = entries[0]
            name = entry0.get("name")
            obj_type = entry0.get("type")
            if not name:
                continue
            object_id = int(object_id_str)
            canonical_shard = shard_mapping.get(object_id_str, shard_n)
            index.setdefault(name, {})[object_id] = {
                "object_id": object_id,
                "shard": canonical_shard,
                "type": obj_type,
            }
            if object_id not in object_sections:
                object_sections[object_id] = _extract_documentation_sections(entry0)
        print(
            f"  [{i}/{len(shard_numbers)}] shard {shard_n}: {len(shard_data)} objetos ({time.time() - t0:.1f}s)"
        )

    return {name: list(candidates.values()) for name, candidates in index.items()}, object_sections


# ---------------------------------------------------------------------------
# Nombres objetivo: Service Domains (bian-view-catalog.json) y clases del
# BIAN BOM (hoja "BIAN BOM" de BIANBOM4XMI.xlsx — mismo lector minimo que usa
# generate_entities.py, sin dependencias externas).
# ---------------------------------------------------------------------------

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col_to_idx(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(t.text or "" for t in si.findall(".//m:t", _NS)) for si in root.findall("m:si", _NS)
    ]


def _sheet_target_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rid = None
    for sheet in workbook.findall(".//m:sheets/m:sheet", _NS):
        if sheet.get("name") == sheet_name:
            rid = sheet.get(f"{{{_REL_NS['r']}}}id")
            break
    if rid is None:
        raise ValueError(f"No se encontro la hoja '{sheet_name}' en el workbook")
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    for rel in rels:
        if rel.get("Id") == rid:
            return "xl/" + rel.get("Target")
    raise ValueError(f"No se resolvio el r:id '{rid}' de la hoja '{sheet_name}'")


def load_bian_bom_class_names(xlsx_path: Path) -> list[str]:
    """Nombres distintos de la columna "Business Object" de la hoja "BIAN
    BOM" (fila 0 = titulo, fila 1 = encabezados reales, igual que en
    generate_entities.py — ver ese script para el detalle del layout)."""

    with zipfile.ZipFile(xlsx_path) as zf:
        shared = _load_shared_strings(zf)
        target = _sheet_target_path(zf, "BIAN BOM")
        root = ET.fromstring(zf.read(target))

    rows: list[list[str | None]] = []
    for row_el in root.find("m:sheetData", _NS).findall("m:row", _NS):
        cells: dict[int, str | None] = {}
        max_idx = -1
        for c in row_el.findall("m:c", _NS):
            idx = _col_to_idx(c.get("r"))
            v = c.find("m:v", _NS)
            value = v.text if v is not None else None
            if c.get("t") == "s" and value is not None:
                value = shared[int(value)]
            cells[idx] = value
            max_idx = max(max_idx, idx)
        rows.append([cells.get(i) for i in range(max_idx + 1)])

    header = rows[1]
    col_idx = header.index("Business Object")

    names = set()
    for row in rows[2:]:
        if col_idx < len(row) and row[col_idx]:
            names.add(row[col_idx].strip())
    return sorted(names)


def load_service_domain_names(view_catalog_path: Path) -> list[str]:
    data = json.loads(view_catalog_path.read_text(encoding="utf-8"))
    return sorted({entry["service_domain"] for entry in data})


def load_business_area_names(matrix_view_path: Path) -> list[str]:
    """Nombres de las Business Area REALES del modelo (excluye el bucket
    sentinela `is_unclassified: true` que arma generate_matrix_view.py para
    los Service Domains sin Business Area de modelo asignada)."""

    if not matrix_view_path.exists():
        return []
    data = json.loads(matrix_view_path.read_text(encoding="utf-8"))
    return sorted(
        ba["name"] for ba in data.get("business_areas", []) if not ba.get("is_unclassified")
    )


def load_business_domain_names(matrix_view_path: Path) -> list[str]:
    """Nombres de todos los Business Domain del arbol (de primer nivel y
    anidados, escenario 1 y 2), excluyendo el bucket sentinela."""

    if not matrix_view_path.exists():
        return []
    data = json.loads(matrix_view_path.read_text(encoding="utf-8"))
    names = set()
    for ba in data.get("business_areas", []):
        if ba.get("is_unclassified"):
            continue
        for bd in ba.get("business_domains", []):
            names.add(bd["name"])
            for nested in bd.get("business_domains", []):
                names.add(nested["name"])
    return sorted(names)


# ---------------------------------------------------------------------------
# Resolucion nombre -> object_id (con desambiguacion por tipo preferido).
# ---------------------------------------------------------------------------


def resolve_names(
    names: list[str],
    index: dict[str, list[dict]],
    category: str,
    object_sections: dict[int, dict[str, str | None]],
) -> dict:
    priority = PREFERRED_TYPES[category]
    resolved, ambiguous, unresolved = {}, {}, []

    for name in names:
        candidates = index.get(name, [])
        if not candidates:
            unresolved.append(name)
            continue

        if len(candidates) == 1:
            chosen = candidates[0]
            is_ambiguous = False
        else:
            chosen = None
            best_pool = (
                None  # candidatos del tipo de mayor prioridad que SI aparece, aunque sean 2+
            )
            for preferred_type in priority:
                matches = [c for c in candidates if c["type"] == preferred_type]
                if matches and best_pool is None:
                    best_pool = matches
                if len(matches) == 1:
                    chosen = matches[0]
                    break
            is_ambiguous = chosen is None
            if chosen is None:
                # Ninguna prioridad desempato a 1 solo: nos quedamos con el
                # primero del tipo de mayor prioridad disponible (mejor que
                # un "Class" suelto, que sabemos que es un duplicado de
                # diagrama) en vez de un candidates[0] sin criterio.
                chosen = (best_pool or candidates)[0]

        sections = object_sections.get(chosen["object_id"], {})
        entry = {
            "object_id": chosen["object_id"],
            "shard": chosen["shard"],
            "matched_type": chosen["type"],
            "url": OBJECT_URL_TMPL.format(shard=chosen["shard"], object_id=chosen["object_id"]),
            # "documentation" es la seccion literalmente titulada "documentation"
            # en bian.org (puede venir vacia — no es un fallback a otra seccion,
            # ver el bug documentado en _extract_documentation_sections).
            "documentation": sections.get("documentation"),
            # Secciones adicionales de la pagina (numeradas en bian.org: role_definition,
            # example_of_use, executive_summary, key_features, y cualquier otra que
            # aparezca a futuro) — solo se llenan para objetos que las traen (tipicamente
            # Service Domains; Business Area/Domain suelen tener nada mas que "documentation").
            "documentation_sections": sections,
        }
        if is_ambiguous:
            entry["ambiguous_candidates"] = candidates
            ambiguous[name] = entry
        else:
            resolved[name] = entry

    all_resolved = {**resolved, **ambiguous}
    return {
        "entries": all_resolved,
        "stats": {
            "total": len(names),
            "resolved": len(resolved),
            "ambiguous": len(ambiguous),
            "unresolved": len(unresolved),
        },
        "unresolved": unresolved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help=f"default: {DEFAULT_CACHE_DIR}"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignorar la cache local y volver a descargar todo de bian.org",
    )
    parser.add_argument(
        "--view-catalog",
        type=Path,
        default=DEFAULT_VIEW_CATALOG,
        help=f"default: {DEFAULT_VIEW_CATALOG}",
    )
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX, help=f"default: {DEFAULT_XLSX}")
    parser.add_argument(
        "--matrix-view",
        type=Path,
        default=DEFAULT_MATRIX_VIEW,
        help=(
            "Ruta a BIAN_Service_Landscape_V14.0_Matrix_View.json, de donde salen los nombres de "
            f"Business Area a resolver (opcional: si no existe se omite esa categoria) (default: {DEFAULT_MATRIX_VIEW})"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help=f"default: {DEFAULT_OUTPUT}"
    )
    args = parser.parse_args()

    print(f"Indexando objetos de {BASE} (cache: {args.cache_dir}) ...")
    index, object_sections = build_name_index(args.cache_dir, args.force_refresh)
    print(f"  {len(index)} nombres distintos indexados en total\n")

    print(f"Resolviendo Service Domains de {args.view_catalog} ...")
    sd_names = load_service_domain_names(args.view_catalog)
    sd_result = resolve_names(sd_names, index, "service_domains", object_sections)
    print(f"  {sd_result['stats']}\n")

    print(f"Resolviendo clases BIAN BOM de {args.xlsx} ...")
    class_names = load_bian_bom_class_names(args.xlsx)
    class_result = resolve_names(class_names, index, "bian_bom_classes", object_sections)
    print(f"  {class_result['stats']}\n")

    empty_result = {
        "entries": {},
        "stats": {"total": 0, "resolved": 0, "ambiguous": 0, "unresolved": 0},
        "unresolved": [],
    }

    print(f"Resolviendo Business Areas de {args.matrix_view} ...")
    area_names = load_business_area_names(args.matrix_view)
    if area_names:
        area_result = resolve_names(area_names, index, "business_areas", object_sections)
        print(f"  {area_result['stats']}\n")
    else:
        print(
            "  no existe (o no tiene Business Areas) -> se omite esta categoria; "
            "correr scripts/generate_matrix_view/ primero\n"
        )
        area_result = empty_result

    print(f"Resolviendo Business Domains de {args.matrix_view} ...")
    domain_names = load_business_domain_names(args.matrix_view)
    if domain_names:
        domain_result = resolve_names(domain_names, index, "business_domains", object_sections)
        print(f"  {domain_result['stats']}\n")
    else:
        print(
            "  no existe (o no tiene Business Domains) -> se omite esta categoria; "
            "correr scripts/generate_matrix_view/ primero\n"
        )
        domain_result = empty_result

    output = {
        "source": {
            "mapping_url": MAPPING_URL,
            "shard_url_template": SHARD_URL_TMPL,
            "object_url_template": OBJECT_URL_TMPL,
        },
        "stats": {
            "service_domains": sd_result["stats"],
            "bian_bom_classes": class_result["stats"],
            "business_areas": area_result["stats"],
            "business_domains": domain_result["stats"],
        },
        "service_domains": sd_result["entries"],
        "bian_bom_classes": class_result["entries"],
        "business_areas": area_result["entries"],
        "business_domains": domain_result["entries"],
        "unresolved": {
            "service_domains": sd_result["unresolved"],
            "bian_bom_classes": class_result["unresolved"],
            "business_areas": area_result["unresolved"],
            "business_domains": domain_result["unresolved"],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
