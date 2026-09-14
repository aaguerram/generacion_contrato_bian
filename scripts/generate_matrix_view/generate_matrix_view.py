"""
Genera `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`: el arbol completo
Business Area -> Business Domain -> Service Domain del Service Landscape BIAN
14.0.0, tal como se ve en
https://bian.org/servicelandscape-14-0-0/views/view_54081.html ("BIAN Service
Landscape V14.0 Matrix View").

## Los 2 escenarios de anidamiento

Esa vista mezcla 2 formas de agrupar un Service Domain bajo su Business Area:

1. Business Area -> Business Domain -> Business Domain -> Service Domain
   (un Business Domain "padre" agrupa a otros Business Domain "hijos", y los
   Service Domain cuelgan del hijo). Ejemplo real:
   `Operations and Execution > Cross Product Operations > Account Management > Account Reconciliation`.
2. Business Area -> Business Domain -> Service Domain (sin nivel intermedio;
   el Service Domain cuelga directo del Business Domain).

## De donde sale esto (100% local, sin red)

`docs/BIANv14.xlsm`, hoja "Service Domains", ya trae esta jerarquia en 2
familias de columnas paralelas:

- **Modelo** (`mBusiness Area` / `mBusiness Domain parent` / `mBusiness
  Domain`): la jerarquia curada que arma el escenario 1 cuando
  `mBusiness Domain parent` viene poblado (129 de 341 filas) y el escenario 2
  cuando viene vacio (212 de 341).
- **Vista** (`vBusiness Area` / `vBusinessDomain`): un eje de clasificacion
  DISTINTO (no una version simplificada del modelo — verificado: un mismo
  `mBusiness Area` se reparte entre hasta 6 `vBusiness Area` distintos). No
  se usa como fallback del modelo (mezclaria 2 ejes incompatibles).

Verificado antes de escribir el script: los 3 conjuntos de nombres (Business
Domain usado como padre / usado como hoja plana / usado como hijo anidado)
son mutuamente excluyentes — ningun nombre cumple 2 roles a la vez, y un
mismo par (padre, hijo) siempre cae bajo la misma Business Area. El arbol es
consistente.

2 Service Domains (`Prospect Campaign Management`, `Trade Settlement`) traen
`mBusiness Area`/`mBusiness Domain` vacios en el xlsm. Se resolvieron
bajando la pagina oficial del Matrix View y parseando las coordenadas SVG de
sus cajas: ambos caen geometricamente dentro de un Business Domain que YA
existe en este mismo arbol (`Market Operations` y `Marketing`
respectivamente) — ver el diccionario `KNOWN_MODEL_GAPS` y su comentario
para la evidencia completa (object_id, coordenadas, hermanos tematicos). El
bucket sentinela `UNCLASSIFIED_AREA` (`is_unclassified: true`) sigue
existiendo como red de seguridad generica, pero hoy no lo dispara ningun
Service Domain.

Si `docs/bian-object-catalog.json` existe (generado por
`scripts/bian_object_catalog/`, con su seccion `business_areas`), cada
Business Area real (no el bucket sentinela) recibe ademas `object_url` (link
a su pagina de objeto en bian.org, `object_<N>.html?object=<id>`) y
`documentation` (el texto de esa pagina, extraido del shard local).

Ver README.md en esta misma carpeta para el formato completo de salida.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_XLSM = REPO_ROOT / "docs" / "BIANv14.xlsm"
DEFAULT_OBJECT_CATALOG = REPO_ROOT / "docs" / "bian-object-catalog.json"
DEFAULT_SD_JSON = REPO_ROOT / "docs" / "SD.json"
DEFAULT_ENTITY_JSON = REPO_ROOT / "docs" / "entity.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "BIAN_Service_Landscape_V14.0_Matrix_View.json"
SHEET_NAME = "Service Domains"
SOURCE_VIEW_URL = "https://bian.org/servicelandscape-14-0-0/views/view_54081.html"

REQUIRED_COLUMNS = {
    "mBusiness Area",
    "mBusiness Domain parent",
    "mBusiness Domain",
    "vBusiness Area",
    "vBusinessDomain",
    "Service Domain",
}


# ---------------------------------------------------------------------------
# Lector .xlsm minimo (solo stdlib: un .xlsm es un .xlsx con macros, mismo
# formato ZIP/XML — igual que en scripts/generate_entities/ y
# scripts/bian_object_catalog/, sin agregar openpyxl/pandas).
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


def read_sheet_as_dicts(xlsm_path: Path, sheet_name: str, header_row_index: int = 1) -> list[dict]:
    """Fila 0 = titulo, fila 1 = encabezados, fila 2+ = datos (mismo layout
    que las demas hojas de este workbook y de BIANBOM4XMI.xlsx)."""

    with zipfile.ZipFile(xlsm_path) as zf:
        shared = _load_shared_strings(zf)
        target = _sheet_target_path(zf, sheet_name)
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

    header = rows[header_row_index]
    dicts = []
    for row in rows[header_row_index + 1 :]:
        dicts.append(
            {h: (row[i] if h is not None and i < len(row) else None) for i, h in enumerate(header)}
        )
    return dicts


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


# ---------------------------------------------------------------------------
# Catalogo opcional de links+documentacion de objeto en bian.org (generado
# por scripts/bian_object_catalog/, secciones "business_areas",
# "business_domains" y "service_domains"). Opcional porque requiere red (la
# primera vez que se corre ESE script); sin el, este script sigue
# funcionando igual, solo sin `object_url`/`documentation`.
# ---------------------------------------------------------------------------


def load_object_catalog_section(path: Path, section: str) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get(section, {})


# "mBusiness Area"/"mBusinessDomain" (modelo) y "vBusiness Area"/
# "vBusinessDomain" (vista) NO son el mismo eje simplificado — son 2
# categorizaciones BIAN independientes y cruzadas (verificado: el mismo
# "mBusiness Area" se reparte entre hasta 6 "vBusiness Area" distintos segun
# el Service Domain). Por eso NO se puede caer de una a la otra fila por
# fila sin mezclar nombres de ejes distintos dentro del mismo arbol.
UNCLASSIFIED_AREA = "(Sin Business Area de modelo — solo clasificado por vista)"

# 2 filas de `docs/BIANv14.xlsm` ("Service Domains") no traen NADA en las
# columnas de modelo (`mBusiness Area`/`mBusiness Domain` en blanco) — un
# vacio del propio xlsm, no una clasificacion real "fuera de modelo". Se
# resolvio bajando la pagina oficial del Matrix View
# (https://bian.org/servicelandscape-14-0-0/views/view_54081.html) y
# parseando las coordenadas SVG de cada caja para ver donde las dibuja
# bian.org de verdad:
#
# - "Trade Settlement" (bizzsemantic/object_id 43346, caja en x=4765,y=3060)
#   cae geometricamente DENTRO de la caja de "Market Operations"
#   (object_id 216875), que a su vez cae dentro de "Product Specific
#   Fulfillment" (object_id 216824) — ambos ya existen en este mismo arbol
#   (via otras filas) bajo Business Area "Operations and Execution", con
#   "Market Operations" agrupando otros 11 Service Domains de trading
#   (Trade Clearing, Trade Confirmation Matching, Trade and Price
#   Reporting, ...) — "Trade Settlement" encaja exactamente ahi.
# - "Prospect Campaign Management" (object_id 33231, caja en x=1985,y=900)
#   cae dentro de la caja de "Marketing" (object_id 216774), que en este
#   arbol ya existe bajo Business Area "Sales and Service" agrupando otros
#   8 Service Domains de campanas/marketing (Prospect Campaign Design,
#   Customer Campaign Management, ...) — de nuevo, encaja exacto.
#
# Ninguna de las 2 cajas de Business Area/Domain que las contienen visualmente
# se llama distinto a lo que ya usa el resto del arbol — no es una
# corrección inventada, es completar con la fuente oficial un dato que el
# xlsm dejo vacio. Si una futura version de BIANv14.xlsm completa estas 2
# filas, este diccionario queda sin efecto (nunca se usa si la fila ya trae
# `mBusiness Area`/`mBusiness Domain`).
KNOWN_MODEL_GAPS = {
    "Trade Settlement": {
        "area": "Operations and Execution",
        "parent_domain": "Product Specific Fulfillment",
        "domain": "Market Operations",
    },
    "Prospect Campaign Management": {
        "area": "Sales and Service",
        "parent_domain": None,
        "domain": "Marketing",
    },
}

# Secciones numeradas que trae la pagina de objeto de un Service Domain en
# bian.org (ademas de la generica "documentation" — ver
# bian_object_catalog.py::_extract_documentation_sections para el bug que
# esto corrige: tomar solo la primera seccion como "la documentacion" del
# objeto devolvia el texto de "1. Role Definition" en vez del de la seccion
# realmente titulada "documentation", que en varios Service Domains viene
# vacia — verificado con "Card Authorization", object_id 41757).
KNOWN_SD_SECTION_KEYS = ("role_definition", "example_of_use", "executive_summary", "key_features")


# ---------------------------------------------------------------------------
# docs/SD.json (341 Service Domains, columnas L..V de BIANv14.xlsm — ver
# CLAUDE.md de este proyecto). Se comparo contra `role_definition` /
# `example_of_use` / `executive_summary` / `key_features` / `documentation`
# (ya presentes, sacados de bian.org): "Service Role" / "Examples of Use" /
# "Executive Summary" / "Features" traen EXACTAMENTE el mismo texto, solo
# con otro nombre (confirmado con "Card Authorization") — por eso no se
# duplican, se agregan solo los 4 que SD.json trae y bian.org no:
# `functional_pattern`, `asset_type`, `generic_artifact_type`,
# `control_record`, `registration_status`.
#
# "Documentation" de SD.json es la concatenacion de esos mismos 4 campos +
# una seccion "General comment" al final (que es exactamente el
# `documentation` de bian.org — verificado texto por texto con los 3 unicos
# casos donde no viene vacia: Bank Guarantee, Collateral Asset
# Administration, Financial Accounting). La diferencia es que bian.org dejo
# esa seccion vacia para la ENORME mayoria de Service Domains (verificado
# con "Card Network Participant Facility": tambien vacia ahi, no es un bug
# de extraccion), mientras SD.json SIEMPRE trae el campo completo. Por eso
# `documentation` usa SD.json como respaldo cuando bian.org no trajo nada
# (ver `sd_node()`) — nunca lo pisa cuando bian.org SI trae texto real.
SD_JSON_FIELD_MAP = {
    "Functional Pattern": "functional_pattern",
    "Asset Type": "asset_type",
    "Generic Artifact Type": "generic_artifact_type",
    "Control Record <AssetType><ArtifactType>": "control_record",
    "Registration Status": "registration_status",
    "Documentation": "documentation",
}


def load_sd_metadata(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {}
    for row in data:
        name = row.get("Service Domain")
        if not name:
            continue
        result[name] = {
            slug: row.get(sd_json_key) for sd_json_key, slug in SD_JSON_FIELD_MAP.items()
        }
    return result


# ---------------------------------------------------------------------------
# docs/entity.json (generado por scripts/generate_entities/): cada entidad
# BIAN BOM trae, por cada Service Domain donde aparece, 1 "aparicion" por
# diagrama (bom/control_record) con su `puml_path`/`svg_path` local +
# `bian_source_url` (el link de ESE diagrama puntual) + `sd_overview_url`.
# Los primeros 3 son propiedades del DIAGRAMA (bom y control_record tienen
# cada uno el suyo); `sd_overview_url` en cambio es un valor general del
# Service Domain — el mismo en la aparicion bom y en la control_record de
# un mismo SD (verificado: 0 inconsistencias en las 272 combinaciones
# Service Domain+tipo-de-diagrama que trae entity.json) — asi que va en la
# raiz del Service Domain (junto a `object_url`/`asset_type`/etc.), no
# duplicado dentro de cada uno de los 2 sub-objetos de diagrama. Alcanza con
# recorrer entity.json 1 sola vez y quedarse con la primera aparicion de
# cada (service_domain, diagram_type) — no hace falta cruzar entidad por
# entidad.
DIAGRAM_INFO_FIELDS = ("puml_path", "svg_path", "bian_source_url")


def load_sd_diagram_info(path: Path) -> dict[str, dict]:
    """{Service Domain -> {"bom": {...}|None, "control_record": {...}|None, "sd_overview_url": ...}}.

    `bom`/`control_record` solo cubren los 272 Service Domains que tienen
    diagrama extraido localmente (`docs/bian-diagrams/`) — los otros ~69 de
    los 341 totales (sin diagrama publicado en bian.org 14.0.0) quedan en
    `None`."""

    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for entity in data.get("entities", {}).values():
        for occ in entity.get("occurrences", []):
            sd = occ.get("service_domain")
            dt = occ.get("diagram_type")
            if not sd or dt not in ("bom", "control_record"):
                continue
            by_sd = result.setdefault(
                sd, {"bom": None, "control_record": None, "sd_overview_url": None}
            )
            if by_sd[dt] is None:
                by_sd[dt] = {field: occ.get(field) for field in DIAGRAM_INFO_FIELDS}
            if by_sd["sd_overview_url"] is None:
                by_sd["sd_overview_url"] = occ.get("sd_overview_url")
    return result


# ---------------------------------------------------------------------------
# Armado del arbol.
# ---------------------------------------------------------------------------


def build_matrix_tree(
    xlsm_path: Path,
    business_area_objects: dict[str, dict] | None = None,
    business_domain_objects: dict[str, dict] | None = None,
    service_domain_objects: dict[str, dict] | None = None,
    sd_metadata: dict[str, dict] | None = None,
    sd_diagram_info: dict[str, dict] | None = None,
) -> dict:
    rows = read_sheet_as_dicts(xlsm_path, SHEET_NAME)
    if rows and not REQUIRED_COLUMNS.issubset(rows[0].keys()):
        missing = REQUIRED_COLUMNS - set(rows[0].keys())
        raise ValueError(
            f"La hoja '{SHEET_NAME}' de {xlsm_path} no tiene las columnas esperadas (faltan: {sorted(missing)})."
        )

    # area -> dominio_raiz -> dominio_padre_o_None -> set(service domains)
    tree: dict[str, dict[str, dict[str | None, set]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    unclassified_in_model: list[dict] = []
    skipped_no_sd = 0

    for row in rows:
        service_domain = _clean(row.get("Service Domain"))
        if not service_domain:
            skipped_no_sd += 1
            continue

        area = _clean(row.get("mBusiness Area"))
        domain = _clean(row.get("mBusiness Domain"))
        parent_domain = _clean(row.get("mBusiness Domain parent"))

        if not area or not domain:
            gap_fix = KNOWN_MODEL_GAPS.get(service_domain)
            if gap_fix:
                area, domain, parent_domain = (
                    gap_fix["area"],
                    gap_fix["domain"],
                    gap_fix["parent_domain"],
                )
            else:
                view_area = _clean(row.get("vBusiness Area"))
                view_domain = _clean(row.get("vBusinessDomain"))
                unclassified_in_model.append(
                    {
                        "service_domain": service_domain,
                        "view_business_area": view_area,
                        "view_business_domain": view_domain,
                    }
                )
                area = UNCLASSIFIED_AREA
                domain = view_domain or view_area or "(sin clasificar)"
                parent_domain = None

        if parent_domain:
            tree[area][parent_domain][domain].add(service_domain)
        else:
            tree[area][domain][None].add(service_domain)

    def sd_node(name: str) -> dict:
        # La pagina de objeto de un Service Domain en bian.org trae varias
        # secciones numeradas (ademas de la generica "documentation", que a
        # veces viene vacia — ver el bug documentado en
        # bian_object_catalog.py::_extract_documentation_sections). Se
        # agregan como atributos propios del Service Domain, no colapsadas
        # en un solo campo. Las 4 conocidas siempre estan presentes (en
        # `None` si esa pagina puntual no las trae); cualquier seccion
        # adicional no prevista (bian.org agrega una "5. ..." a futuro) se
        # suma igual, sin perderla.
        obj = (service_domain_objects or {}).get(name)
        sections = (obj or {}).get("documentation_sections") or {}
        diagrams = (sd_diagram_info or {}).get(name) or {}
        node = {
            "name": name,
            "object_url": obj["url"] if obj else None,
            "sd_overview_url": diagrams.get("sd_overview_url"),
        }
        for key in KNOWN_SD_SECTION_KEYS:
            node[key] = sections.get(key)
        node["documentation"] = obj["documentation"] if obj else None
        for key, value in sections.items():
            node.setdefault(key, value)

        # Metadatos de docs/SD.json: functional_pattern/asset_type/
        # generic_artifact_type/control_record/registration_status no
        # tienen equivalente en bian.org, se agregan directo. "documentation"
        # SI tiene equivalente (la seccion homonima de bian.org) pero esa
        # viene vacia en la enorme mayoria de Service Domains — SD.json la
        # trae siempre completa, asi que se usa como respaldo SOLO cuando
        # bian.org no trajo nada, nunca pisando un valor real de bian.org.
        meta = (sd_metadata or {}).get(name) or {}
        for slug in SD_JSON_FIELD_MAP.values():
            if slug == "documentation":
                continue
            node[slug] = meta.get(slug)
        if not node["documentation"]:
            node["documentation"] = meta.get("documentation")

        # Rutas locales (.puml/.svg) + URL de bian.org del diagrama BOM y del
        # Control Record de este Service Domain, sacadas de docs/entity.json
        # (nombradas "..._diagram" para no chocar con el "control_record" de
        # arriba, que es el nombre del Control Record segun SD.json, un
        # string — esto es un objeto con las rutas/URL de SU diagrama;
        # `sd_overview_url` ya se puso en la raiz mas arriba, no se repite
        # aca). `None` cuando ese Service Domain no tiene ese diagrama
        # publicado localmente (69 de los 341 no tienen ninguno de los dos).
        node["bom_diagram"] = diagrams.get("bom")
        node["control_record_diagram"] = diagrams.get("control_record")
        return node

    def bd_node(name: str, nested: list[dict], service_domains: list[str]) -> dict:
        obj = (business_domain_objects or {}).get(name)
        return {
            "name": name,
            "object_url": obj["url"] if obj else None,
            "documentation": obj["documentation"] if obj else None,
            "business_domains": nested,
            "service_domains": [sd_node(sd) for sd in service_domains],
        }

    business_areas = []
    for area in sorted(tree):
        domains_out = []
        for domain_name in sorted(tree[area]):
            children_map = tree[area][domain_name]
            direct_sds = sorted(children_map.get(None, set()))
            nested_domains = [
                bd_node(child_name, [], sorted(sds))
                for child_name, sds in sorted(children_map.items())
                if child_name is not None
            ]
            domains_out.append(bd_node(domain_name, nested_domains, direct_sds))
        area_object = (business_area_objects or {}).get(area)
        business_areas.append(
            {
                "name": area,
                "is_unclassified": area == UNCLASSIFIED_AREA,
                "object_url": area_object["url"] if area_object else None,
                "documentation": area_object["documentation"] if area_object else None,
                "business_domains": domains_out,
            }
        )

    total_service_domains = sum(
        len(bd["service_domains"])
        + sum(len(nd["service_domains"]) for nd in bd["business_domains"])
        for ba in business_areas
        for bd in ba["business_domains"]
    )
    total_nested_domains = sum(
        len(bd["business_domains"]) for ba in business_areas for bd in ba["business_domains"]
    )
    total_root_domains = sum(len(ba["business_domains"]) for ba in business_areas)

    return {
        "release": "14.0.0",
        "source_view": SOURCE_VIEW_URL,
        "source_file": "docs/BIANv14.xlsm (hoja 'Service Domains')",
        "stats": {
            "business_areas": len(business_areas),
            "root_business_domains": total_root_domains,
            "nested_business_domains": total_nested_domains,
            "service_domains": total_service_domains,
            "service_domains_skipped": skipped_no_sd,
        },
        "business_areas": business_areas,
        "unclassified_in_model": unclassified_in_model,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--xlsm", type=Path, default=DEFAULT_XLSM, help=f"default: {DEFAULT_XLSM}")
    parser.add_argument(
        "--object-catalog",
        type=Path,
        default=DEFAULT_OBJECT_CATALOG,
        help=(
            "Ruta a bian-object-catalog.json (opcional: si no existe se omiten "
            f"'object_url'/'documentation' de Business Areas/Domains/Service Domains) (default: {DEFAULT_OBJECT_CATALOG})"
        ),
    )
    parser.add_argument(
        "--sd-json",
        type=Path,
        default=DEFAULT_SD_JSON,
        help=(
            "Ruta a SD.json (opcional: si no existe se omiten 'functional_pattern'/'asset_type'/"
            f"'generic_artifact_type'/'control_record'/'registration_status') (default: {DEFAULT_SD_JSON})"
        ),
    )
    parser.add_argument(
        "--entity-json",
        type=Path,
        default=DEFAULT_ENTITY_JSON,
        help=(
            "Ruta a entity.json (opcional: si no existe se omiten 'bom_diagram'/'control_record_diagram' "
            f"con las rutas .puml/.svg y URLs de bian.org de cada Service Domain) (default: {DEFAULT_ENTITY_JSON})"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help=f"default: {DEFAULT_OUTPUT}"
    )
    args = parser.parse_args()

    business_area_objects = load_object_catalog_section(args.object_catalog, "business_areas")
    business_domain_objects = load_object_catalog_section(args.object_catalog, "business_domains")
    service_domain_objects = load_object_catalog_section(args.object_catalog, "service_domains")
    if args.object_catalog.exists():
        print(
            f"Leyendo catalogo de objetos de {args.object_catalog} "
            f"({len(business_area_objects)} Business Areas, {len(business_domain_objects)} Business Domains, "
            f"{len(service_domain_objects)} Service Domains con URL+documentacion) ..."
        )
    else:
        print(
            f"  {args.object_catalog} no existe (opcional) -> todo quedara sin 'object_url'/'documentation'"
        )

    sd_metadata = load_sd_metadata(args.sd_json)
    if args.sd_json.exists():
        print(f"Leyendo metadatos de {args.sd_json} ({len(sd_metadata)} Service Domains) ...")
    else:
        print(
            f"  {args.sd_json} no existe (opcional) -> los Service Domains quedaran sin functional_pattern/asset_type/etc."
        )

    sd_diagram_info = load_sd_diagram_info(args.entity_json)
    if args.entity_json.exists():
        print(
            f"Leyendo diagramas de {args.entity_json} ({len(sd_diagram_info)} Service Domains con bom_diagram/control_record_diagram) ..."
        )
    else:
        print(
            f"  {args.entity_json} no existe (opcional) -> los Service Domains quedaran sin bom_diagram/control_record_diagram"
        )

    print(f"Leyendo hoja '{SHEET_NAME}' de {args.xlsm} ...")
    result = build_matrix_tree(
        args.xlsm,
        business_area_objects,
        business_domain_objects,
        service_domain_objects,
        sd_metadata,
        sd_diagram_info,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    stats = result["stats"]
    print(
        f"  {stats['business_areas']} Business Areas (incluye el bucket '{UNCLASSIFIED_AREA}' si aplica)"
    )
    print(f"  {stats['root_business_domains']} Business Domains de primer nivel")
    print(f"  {stats['nested_business_domains']} Business Domains anidados (escenario 1)")
    print(f"  {stats['service_domains']} Service Domains en total")
    if result["unclassified_in_model"]:
        print(
            f"  {len(result['unclassified_in_model'])} sin Business Area/Domain de MODELO (agrupados aparte, ver 'unclassified_in_model'):"
        )
        for item in result["unclassified_in_model"]:
            print(
                f"    - {item['service_domain']} (vista: {item['view_business_area']} / {item['view_business_domain']})"
            )
    if stats["service_domains_skipped"]:
        print(
            f"  ADVERTENCIA: {stats['service_domains_skipped']} filas sin ningun Service Domain resoluble"
        )
    print(f"Escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
