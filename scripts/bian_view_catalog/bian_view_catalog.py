"""
Genera un catalogo JSON {Service Domain -> link SD Overview, BOM Diagram,
Control Record Diagram} en bian.org, cruzando por nombre las 2285 vistas que
trae el propio sitio en data/all_objects_on_views.js (variable `insiteViews`).

Ver README.md en esta misma carpeta para el detalle de como se descubrio esta
fuente y por que no hace falta rastrear pagina por pagina.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

BASE = "https://bian.org/servicelandscape-14-0-0"
VIEWS_DATA_URL = f"{BASE}/data/all_objects_on_views.js"
VIEW_URL_TMPL = f"{BASE}/views/view_{{id}}.html"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "bian-view-catalog.json"

SUFFIXES = {
    "sd_overview": " SD Overview",
    "bom_diagram": " BOM Diagram",
    "control_record_diagram": " Control Record Diagram",
}


def fetch_insite_views(source: Path | None) -> dict[str, dict]:
    """Returns {view_id: {"id": view_id, "name": "<title>"}} for every view
    published on the BIAN 14.0.0 service landscape site."""

    if source:
        text = source.read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(VIEWS_DATA_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")

    # The file declares two globals back to back: `objectsOnViews` (an
    # object-id -> [view_id,...] index we don't need here) followed by
    # `insiteViews` (view-id -> {id, name}), which is what we want.
    m = re.search(r"var insiteViews\s*=\s*(\{.*\})\s*;?\s*$", text, re.DOTALL)
    if not m:
        raise ValueError("No se encontro 'var insiteViews = {...}' en el archivo fuente")
    return json.loads(m.group(1))


def build_catalog(insite_views: dict[str, dict]) -> list:
    by_kind: dict[str, dict[str, str]] = {kind: {} for kind in SUFFIXES}
    for view_id, entry in insite_views.items():
        name = entry.get("name", "")
        for kind, suffix in SUFFIXES.items():
            if name.endswith(suffix):
                sd_name = name[: -len(suffix)].strip()
                by_kind[kind][sd_name] = view_id
                break

    catalog = []
    for sd_name, overview_id in sorted(by_kind["sd_overview"].items()):
        bom_id = by_kind["bom_diagram"].get(sd_name)
        cr_id = by_kind["control_record_diagram"].get(sd_name)
        catalog.append(
            {
                "service_domain": sd_name,
                "sd_overview_url": VIEW_URL_TMPL.format(id=overview_id),
                "bom_diagram_url": VIEW_URL_TMPL.format(id=bom_id) if bom_id else None,
                "control_record_diagram_url": VIEW_URL_TMPL.format(id=cr_id) if cr_id else None,
            }
        )
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="Usar un all_objects_on_views.js ya descargado en vez de bajarlo de bian.org",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Ruta del JSON de salida (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    insite_views = fetch_insite_views(args.source)
    catalog = build_catalog(insite_views)

    args.output.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    total = len(catalog)
    with_bom = sum(1 for c in catalog if c["bom_diagram_url"])
    with_cr = sum(1 for c in catalog if c["control_record_diagram_url"])
    with_both = sum(1 for c in catalog if c["bom_diagram_url"] and c["control_record_diagram_url"])
    print(f"{total} Service Domains con pagina 'SD Overview'")
    print(f"  {with_bom} con BOM Diagram encontrado")
    print(f"  {with_cr} con Control Record Diagram encontrado")
    print(f"  {with_both} con los 3 links completos")
    print(f"Escrito en {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
