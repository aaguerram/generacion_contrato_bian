"""
Genera `docs/entity.json`: un diccionario {nombre de clase/enum BIAN -> ficha}
que responde "en que diagramas (BOM y/o Control Record, de que Service Domain)
aparece esta clase" + "que es esta clase" (descripcion, propiedades y, cuando
existe, la referencia a un estandar externo como ISO 20022 o UK Open Banking).

Fuentes usadas (todas locales, sin llamadas a bian.org):

1. `docs/bian-diagrams/puml-bom/*.puml` y `docs/bian-diagrams/puml-control-record/*.puml`
   (generados por `scripts/svg_to_puml` y `scripts/svg_to_puml_control_record`).
   Cada archivo trae, en comentarios de cabecera, el Service Domain y la URL
   de bian.org de la que salio ese diagrama, y declara cada clase/enum del
   diagrama como una caja PlantUML (`class "Nombre" as ALIAS { ... }` /
   `enum "Nombre" as ALIAS { ... }`), a veces con un `note right of ALIAS`
   con metadatos (Extensible, BQ, AssetType, ControlRecord, GenericArtifact,
   HelperDiagram, BOMDiagram, BianBom). Esto responde el "en que diagramas
   aparece" + "con que atributos se ve en ESE diagrama puntual".

2. `docs/BIANBOM4XMI.xlsx`, hoja "BIAN BOM" (export XMI del modelo BIAN
   completo: 1699 clases + 1210 enums + 123 data types/primitive types, cada
   una con su documentacion y sus atributos/enum-values, y -cuando existe- la
   referencia a un estandar externo tal como se ve en la pagina bian.org de
   cada clase, columnas "Reference Type" / "Referenced Aspect" / "Reference
   Name" / "URL Reference", p.ej. para "Agreement": Standard / ISO20022 BM /
   Agreement / https://www.iso20022.org/standardsrepository/type/Agreement).
   Esto responde el "que es y que propiedades tiene" de forma canonica (no
   depende de que atributos se hayan dibujado en tal o cual diagrama).

3. `docs/bian-view-catalog.json` (generado por `scripts/bian_view_catalog`):
   por Service Domain, los links a la pagina "SD Overview" ademas de BOM y
   Control Record (el propio .puml ya trae el link de BOM o de Control
   Record segun corresponda; este catalogo completa el link "SD Overview"
   que el .puml no trae).

Ver README.md en esta misma carpeta para el detalle de las 3 fuentes, el
formato exacto de entity.json y las decisiones de diseno (por que se
matchea por nombre y no por UID, que pasa con las ~130 clases dupliacadas en
el xlsx, que entidades quedan sin ficha BIAN BOM, etc).
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
DIAGRAMS_DIR = DOCS_DIR / "bian-diagrams"
BOM_PUML_DIR = DIAGRAMS_DIR / "puml-bom"
CR_PUML_DIR = DIAGRAMS_DIR / "puml-control-record"
BOM_SVG_DIR = DIAGRAMS_DIR / "svg_bom"
CR_SVG_DIR = DIAGRAMS_DIR / "svg_control_record"
DEFAULT_XLSX = DOCS_DIR / "BIANBOM4XMI.xlsx"
DEFAULT_VIEW_CATALOG = DOCS_DIR / "bian-view-catalog.json"
DEFAULT_OBJECT_CATALOG = DOCS_DIR / "bian-object-catalog.json"
DEFAULT_OUTPUT = DOCS_DIR / "entity.json"

BOM_BOM_SHEET_NAME = "BIAN BOM"


# ---------------------------------------------------------------------------
# Lector .xlsx minimo (solo stdlib: zipfile + xml.etree). El repo no trae
# openpyxl/pandas y no hace falta agregar la dependencia solo para leer 1
# hoja: un .xlsx es un zip de XML y alcanza con sharedStrings.xml + la hoja.
# ---------------------------------------------------------------------------

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col_to_idx(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _load_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(t.text or "" for t in si.findall(".//m:t", _NS))
        for si in root.findall("m:si", _NS)
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


def read_sheet_as_dicts(xlsx_path: Path, sheet_name: str, header_row_index: int = 1) -> List[dict]:
    """Lee una hoja completa como lista de dicts {encabezado: valor}.

    Todas las hojas de BIANBOM4XMI.xlsx comparten el mismo layout: fila 0 =
    titulo (una sola celda combinada), fila 1 = encabezados reales, fila 2+
    = datos. `header_row_index=1` refleja eso.
    """

    with zipfile.ZipFile(xlsx_path) as zf:
        shared = _load_shared_strings(zf)
        target = _sheet_target_path(zf, sheet_name)
        root = ET.fromstring(zf.read(target))

    rows: List[List[Optional[str]]] = []
    for row_el in root.find("m:sheetData", _NS).findall("m:row", _NS):
        cells: Dict[int, Optional[str]] = {}
        max_idx = -1
        for c in row_el.findall("m:c", _NS):
            idx = _col_to_idx(c.get("r"))
            v = c.find("m:v", _NS)
            if v is None:
                inline = c.find("m:is", _NS)
                value = "".join(t.text or "" for t in inline.findall(".//m:t", _NS)) if inline is not None else None
            else:
                value = v.text
                if c.get("t") == "s" and value is not None:
                    value = shared[int(value)]
            cells[idx] = value
            max_idx = max(max_idx, idx)
        rows.append([cells.get(i) for i in range(max_idx + 1)])

    header = rows[header_row_index]
    dicts = []
    for row in rows[header_row_index + 1 :]:
        dicts.append({h: (row[i] if h is not None and i < len(row) else None) for i, h in enumerate(header)})
    return dicts


# ---------------------------------------------------------------------------
# Catalogo BIAN BOM (descripcion + propiedades + referencia a estandar
# externo por clase/enum/data type), a partir de la hoja "BIAN BOM".
# ---------------------------------------------------------------------------

DEFINITION_KINDS = {"Class", "Enumeration", "Data type", "Primitive type"}
REQUIRED_COLUMNS = {
    "UML Type",
    "Business Object",
    "Feature",
    "Description",
    "Data Type",
    "Reference Type",
    "Referenced Aspect",
    "Reference Name",
    "URL Reference",
}
_URL_IN_PARENS_RE = re.compile(r"\((https?://[^)]+)\)\s*$")


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    # `_x000D_` es como Excel escapa un CR suelto dentro de un inline string.
    value = value.replace("_x000D_", "\n").replace("\r\n", "\n").replace("\r", "\n")
    value = value.strip()
    return value or None


def _extract_reference(row: dict) -> Optional[dict]:
    ref_type = _clean_text(row.get("Reference Type"))
    aspect = _clean_text(row.get("Referenced Aspect"))
    ref_name = _clean_text(row.get("Reference Name"))
    url_raw = _clean_text(row.get("URL Reference"))
    if not (ref_type or aspect or ref_name or url_raw):
        return None
    if aspect:
        aspect = re.sub(r"\s*\(\)\s*$", "", aspect)  # "ISO20022 BM ()" -> "ISO20022 BM"
    url = url_raw
    if url_raw:
        m = _URL_IN_PARENS_RE.search(url_raw)
        if m:
            url = m.group(1)
    return {"type": ref_type, "referenced_aspect": aspect, "reference_name": ref_name, "url": url}


def build_bian_bom_catalog(xlsx_path: Path) -> Dict[str, dict]:
    """{nombre BIAN BOM -> {kind, description, reference, properties[], enum_values[]}}.

    Se agrupa por nombre (columna "Business Object"), no por UID: es lo que
    despues se necesita para matchear contra los nombres humanos que usan los
    .puml, y en la practica el nombre es unico salvo 3 casos (Duty, Object,
    Token) que quedan clasificados con el primer "kind" que aparece.
    Alrededor de 123 clases estan literalmente duplicadas en el xlsx (misma
    fila de definicion repetida dos veces con UID distinto); como se agrupa
    por nombre y se dedupea por nombre de atributo/literal, el duplicado no
    genera propiedades repetidas.
    """

    rows = read_sheet_as_dicts(xlsx_path, BOM_BOM_SHEET_NAME, header_row_index=1)
    if rows and not REQUIRED_COLUMNS.issubset(rows[0].keys()):
        missing = REQUIRED_COLUMNS - set(rows[0].keys())
        raise ValueError(
            f"La hoja '{BOM_BOM_SHEET_NAME}' de {xlsx_path} no tiene las columnas esperadas "
            f"(faltan: {sorted(missing)}). El layout del xlsx pudo haber cambiado."
        )

    catalog: Dict[str, dict] = {}
    for row in rows:
        name = _clean_text(row.get("Business Object"))
        if not name:
            continue
        entry = catalog.setdefault(
            name,
            {"kind": None, "description": None, "reference": None, "_properties": {}, "_enum_values": {}},
        )
        uml_type = row.get("UML Type")
        feature = _clean_text(row.get("Feature"))

        if uml_type in DEFINITION_KINDS and not feature:
            if entry["kind"] is None:
                entry["kind"] = uml_type
            if entry["description"] is None:
                entry["description"] = _clean_text(row.get("Description"))
            if entry["reference"] is None:
                entry["reference"] = _extract_reference(row)
        elif uml_type == "Attribute" and feature:
            entry["_properties"].setdefault(
                feature,
                {
                    "name": feature,
                    "description": _clean_text(row.get("Description")),
                    "data_type": _clean_text(row.get("Data Type")),
                    "reference": _extract_reference(row),
                },
            )
        elif uml_type == "Enumeration literal" and feature:
            entry["_enum_values"].setdefault(
                feature, {"value": feature, "description": _clean_text(row.get("Description"))}
            )

    for entry in catalog.values():
        entry["properties"] = list(entry.pop("_properties").values())
        entry["enum_values"] = list(entry.pop("_enum_values").values())

    return catalog


# ---------------------------------------------------------------------------
# Parser de los .puml (BOM y Control Record). No es un parser de PlantUML
# generico: se apoya en como `svg_to_puml` / `svg_to_puml_control_record`
# emiten SIEMPRE el mismo layout (ver sus README) para extraer, con
# regex, exactamente lo que hace falta.
# ---------------------------------------------------------------------------

_HEADER_SERVICE_DOMAIN_RE = re.compile(r"^'\s*Service Domain:\s*(.+?)\s*$", re.MULTILINE)
_HEADER_SOURCE_RE = re.compile(r"^'\s*(?:BIAN source|Source):\s*(.+?)\s*$", re.MULTILINE)
_HEADER_EXTRACTION_RE = re.compile(r"^'\s*Extraction:\s*(.+?)\s*$", re.MULTILINE)
_TITLE_RE = re.compile(r"^title\s+(.+?)\s*$", re.MULTILINE)

# `class "Nombre" as ALIAS <<stereotype>> {` (el `{` y el stereotype son
# opcionales: los diagramas RASTER_RECONSTRUCTED declaran clases sin cuerpo,
# solo con el stereotype, p.ej. `class "Corporate Card" as AT <<AssetType>>`)
_ENTITY_DECL_RE = re.compile(
    r'^(?P<kind>class|enum)\s+"(?P<name>(?:[^"\\]|\\.)*)"\s+as\s+(?P<alias>\S+?)'
    r'(?:\s+<<(?P<stereotype>\w+)>>)?\s*(?P<has_body>\{)?\s*$',
    re.MULTILINE,
)
_NOTE_RE = re.compile(r"^note (?:right|left|top|bottom) of (\S+)\s*\n(.*?)\nend note", re.DOTALL | re.MULTILINE)
_NOTE_KV_RE = re.compile(r"^\s*([A-Za-z]+):\s*(.+?)\s*$", re.MULTILINE)
_ATTRIBUTE_RE = re.compile(r"^\s*[+\-#~]\s*(.+?)\s*:\s*(.+?)\s*$")


def _extract_body(text: str, start_pos: int) -> (str, int):
    """A partir de justo despues del `{` de una declaracion, devuelve
    (cuerpo, posicion despues del `}` de cierre). El `}` de cierre siempre
    esta solo en su propia linea (no hay metodos ni cuerpos anidados)."""

    end_match = re.search(r"^\}\s*$", text[start_pos:], re.MULTILINE)
    if not end_match:
        return "", start_pos
    body = text[start_pos : start_pos + end_match.start()]
    return body, start_pos + end_match.end()


def _parse_notes(text: str) -> Dict[str, dict]:
    notes: Dict[str, dict] = {}
    for alias, body in _NOTE_RE.findall(text):
        kv = {k: v for k, v in _NOTE_KV_RE.findall(body)}
        if kv:
            notes.setdefault(alias, {}).update(kv)
    return notes


def parse_puml_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")

    sd_match = _HEADER_SERVICE_DOMAIN_RE.search(text)
    source_match = _HEADER_SOURCE_RE.search(text)
    extraction_match = _HEADER_EXTRACTION_RE.search(text)
    title_match = _TITLE_RE.search(text)

    notes_by_alias = _parse_notes(text)

    entities = []
    for m in _ENTITY_DECL_RE.finditer(text):
        kind = m.group("kind")
        name = m.group("name")
        alias = m.group("alias")
        stereotype = m.group("stereotype")

        attributes: List[dict] = []
        enum_values: List[str] = []
        if m.group("has_body"):
            body, _ = _extract_body(text, m.end())
            for line in body.splitlines():
                if not line.strip():
                    continue
                attr_match = _ATTRIBUTE_RE.match(line)
                if attr_match:
                    attributes.append({"name": attr_match.group(1), "type": attr_match.group(2)})
                elif kind == "enum":
                    enum_values.append(line.strip())

        entities.append(
            {
                "name": name,
                "alias": alias,
                "kind": kind,
                "stereotype": stereotype,
                "attributes": attributes,
                "enum_values": enum_values,
                "notes": notes_by_alias.get(alias, {}),
            }
        )

    return {
        "service_domain": sd_match.group(1) if sd_match else None,
        "bian_source_url": source_match.group(1) if source_match else None,
        "extraction": extraction_match.group(1) if extraction_match else None,
        "title": title_match.group(1) if title_match else None,
        "entities": entities,
    }


# ---------------------------------------------------------------------------
# Catalogo de links por Service Domain (SD Overview / BOM / Control Record).
# ---------------------------------------------------------------------------


def load_view_catalog(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["service_domain"]: entry for entry in data}


# ---------------------------------------------------------------------------
# Catalogo opcional de links a la pagina de OBJETO de bian.org (documentacion
# en prosa de una clase o de un Service Domain puntual, distinta de las
# paginas de diagrama de arriba). Lo genera `scripts/bian_object_catalog/`;
# es opcional porque requiere red (descarga ~142 MB de bian.org la primera
# vez) y `generate_entities.py` debe poder correr sin el.
# ---------------------------------------------------------------------------


def load_object_catalog(path: Path) -> Dict[str, Dict[str, dict]]:
    if not path.exists():
        return {"service_domains": {}, "bian_bom_classes": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "service_domains": data.get("service_domains", {}),
        "bian_bom_classes": data.get("bian_bom_classes", {}),
    }


# ---------------------------------------------------------------------------
# Orquestacion: recorre los .puml, cruza contra el catalogo BIAN BOM y el
# catalogo de vistas, y arma el diccionario final de entidades.
# ---------------------------------------------------------------------------


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _iter_diagram_files(puml_dir: Path, svg_dir: Path, diagram_type: str):
    for puml_path in sorted(puml_dir.glob("*.puml")):
        svg_path = svg_dir / f"{puml_path.stem}.svg"
        yield diagram_type, puml_path, svg_path if svg_path.exists() else None


def build_entities(
    bom_puml_dir: Path,
    cr_puml_dir: Path,
    bom_svg_dir: Path,
    cr_svg_dir: Path,
    bian_bom_catalog: Dict[str, dict],
    view_catalog: Dict[str, dict],
    object_catalog: Dict[str, Dict[str, dict]],
) -> Dict[str, dict]:
    entities: Dict[str, dict] = {}
    sd_objects = object_catalog.get("service_domains", {})
    class_objects = object_catalog.get("bian_bom_classes", {})

    diagram_sources = list(_iter_diagram_files(bom_puml_dir, bom_svg_dir, "bom")) + list(
        _iter_diagram_files(cr_puml_dir, cr_svg_dir, "control_record")
    )

    for diagram_type, puml_path, svg_path in diagram_sources:
        parsed = parse_puml_file(puml_path)
        service_domain = parsed["service_domain"]
        sd_links = view_catalog.get(service_domain, {}) if service_domain else {}
        sd_object = sd_objects.get(service_domain) if service_domain else None

        for ent in parsed["entities"]:
            is_new = ent["name"] not in entities
            record = entities.setdefault(
                ent["name"],
                {"name": ent["name"], "bian_bom": bian_bom_catalog.get(ent["name"]), "occurrences": []},
            )
            if is_new and record["bian_bom"] is not None:
                class_object = class_objects.get(ent["name"])
                record["bian_bom"]["object_url"] = class_object["url"] if class_object else None

            record["occurrences"].append(
                {
                    "service_domain": service_domain,
                    "diagram_type": diagram_type,
                    "diagram_title": parsed["title"],
                    "puml_path": _relative(puml_path),
                    "svg_path": _relative(svg_path) if svg_path else None,
                    "bian_source_url": parsed["bian_source_url"],
                    "sd_overview_url": sd_links.get("sd_overview_url"),
                    "sd_object_url": sd_object["url"] if sd_object else None,
                    "alias": ent["alias"],
                    "kind": ent["kind"],
                    "stereotype": ent["stereotype"],
                    "notes": ent["notes"],
                    "attributes": ent["attributes"],
                    "enum_values": ent["enum_values"],
                }
            )

    return dict(sorted(entities.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX, help=f"Ruta a BIANBOM4XMI.xlsx (default: {DEFAULT_XLSX})")
    parser.add_argument(
        "--view-catalog", type=Path, default=DEFAULT_VIEW_CATALOG, help=f"Ruta a bian-view-catalog.json (default: {DEFAULT_VIEW_CATALOG})"
    )
    parser.add_argument("--bom-puml-dir", type=Path, default=BOM_PUML_DIR, help=f"default: {BOM_PUML_DIR}")
    parser.add_argument("--cr-puml-dir", type=Path, default=CR_PUML_DIR, help=f"default: {CR_PUML_DIR}")
    parser.add_argument("--bom-svg-dir", type=Path, default=BOM_SVG_DIR, help=f"default: {BOM_SVG_DIR}")
    parser.add_argument("--cr-svg-dir", type=Path, default=CR_SVG_DIR, help=f"default: {CR_SVG_DIR}")
    parser.add_argument(
        "--object-catalog",
        type=Path,
        default=DEFAULT_OBJECT_CATALOG,
        help=(
            "Ruta a bian-object-catalog.json (generado por scripts/bian_object_catalog/, opcional: "
            f"si no existe se omiten los links de objeto) (default: {DEFAULT_OBJECT_CATALOG})"
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"Ruta del JSON de salida (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    print(f"Leyendo catalogo BIAN BOM de {args.xlsx} ...")
    bian_bom_catalog = build_bian_bom_catalog(args.xlsx)
    print(f"  {len(bian_bom_catalog)} clases/enums/data types con ficha BIAN BOM")

    print(f"Leyendo catalogo de vistas de {args.view_catalog} ...")
    view_catalog = load_view_catalog(args.view_catalog)
    print(f"  {len(view_catalog)} Service Domains con links a bian.org")

    print(f"Leyendo catalogo de objetos de {args.object_catalog} ...")
    object_catalog = load_object_catalog(args.object_catalog)
    if args.object_catalog.exists():
        print(
            f"  {len(object_catalog['service_domains'])} Service Domains y "
            f"{len(object_catalog['bian_bom_classes'])} clases BIAN BOM con link de objeto en bian.org"
        )
    else:
        print("  no existe (opcional) -> las entidades quedaran sin 'object_url'/'sd_object_url'; "
              "correr scripts/bian_object_catalog/ para generarlo")

    print(f"Recorriendo diagramas .puml en {args.bom_puml_dir} y {args.cr_puml_dir} ...")
    entities = build_entities(
        args.bom_puml_dir,
        args.cr_puml_dir,
        args.bom_svg_dir,
        args.cr_svg_dir,
        bian_bom_catalog,
        view_catalog,
        object_catalog,
    )

    total_occurrences = sum(len(e["occurrences"]) for e in entities.values())
    with_bian_bom = sum(1 for e in entities.values() if e["bian_bom"] is not None)
    with_object_url = sum(1 for e in entities.values() if e["bian_bom"] and e["bian_bom"].get("object_url"))
    only_bom = sum(1 for e in entities.values() if {o["diagram_type"] for o in e["occurrences"]} == {"bom"})
    only_cr = sum(1 for e in entities.values() if {o["diagram_type"] for o in e["occurrences"]} == {"control_record"})
    both = sum(1 for e in entities.values() if {o["diagram_type"] for o in e["occurrences"]} == {"bom", "control_record"})

    output = {
        "release": "14.0.0",
        "sources": {
            "puml_bom_dir": _relative(args.bom_puml_dir),
            "puml_control_record_dir": _relative(args.cr_puml_dir),
            "bian_bom_xlsx": _relative(args.xlsx),
            "view_catalog": _relative(args.view_catalog) if args.view_catalog.exists() else None,
            "object_catalog": _relative(args.object_catalog) if args.object_catalog.exists() else None,
        },
        "stats": {
            "total_entities": len(entities),
            "total_occurrences": total_occurrences,
            "entities_with_bian_bom_definition": with_bian_bom,
            "entities_with_object_url": with_object_url,
            "entities_only_in_bom_diagrams": only_bom,
            "entities_only_in_control_record_diagrams": only_cr,
            "entities_in_both_diagram_types": both,
        },
        "entities": entities,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(entities)} entidades distintas ({total_occurrences} apariciones en total)")
    print(f"  {with_bian_bom} con ficha BIAN BOM (descripcion + propiedades), {with_object_url} de ellas con link de objeto en bian.org")
    print(f"  {only_bom} solo en diagramas BOM, {only_cr} solo en Control Record, {both} en ambos")
    print(f"Escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
