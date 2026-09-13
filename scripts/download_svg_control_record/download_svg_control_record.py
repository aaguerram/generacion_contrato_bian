"""
Descarga el SVG del "Control Record Diagram" de cada BIAN Service Domain
listado en docs/bian-view-catalog.json y lo guarda en
docs/bian-diagrams/svg_control_record/<slug-del-service-domain>.svg.

Ver README.md en esta misma carpeta para el detalle de por que esto funciona
con un simple fetch (sin ejecutar JavaScript) y como se arma el nombre de
archivo.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = REPO_ROOT / "docs" / "bian-view-catalog.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "bian-diagrams" / "svg_control_record"

XML_DECL_RE = re.compile(r"<\?xml[^>]*\?>", re.IGNORECASE)
# Every BIAN page's boilerplate copyright comment near the top literally
# contains the text "<svg></svg>" as prose (not a real tag) -- anchor on
# `<svg version=` (what the real, attribute-bearing root tag looks like on
# every page checked) so that sentence is never mistaken for the diagram.
SVG_OPEN_RE = re.compile(r"<svg\s+version=", re.IGNORECASE)


def slugify(name: str) -> str:
    """Same convention already used by every file in docs/bian-diagrams/svg_bom/:
    lowercase, non-alphanumeric runs collapsed to one hyphen, no leading/
    trailing hyphen. Verified to reproduce all 272 existing filenames from
    their Service Domain name before writing this script.
    """

    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def extract_svg(html: str) -> Optional[str]:
    """The BIAN view pages are NOT rendered client-side for the diagram
    itself (only the site chrome/navigation is Backbone+Handlebars) -- the
    actual diagram is a complete, standalone <svg>...</svg> tree sitting
    verbatim in the page's static HTML, in the exact same Bizzdesign export
    format already used by docs/bian-diagrams/svg_bom/*.svg (bizzid attributes,
    etc). We just need to slice it out.
    """

    svg_m = SVG_OPEN_RE.search(html)
    if not svg_m:
        return None
    xml_m = XML_DECL_RE.search(html, 0, svg_m.start())
    start = xml_m.start() if xml_m else svg_m.start()

    end = html.rfind("</svg>")
    if end == -1 or end < start:
        return None
    end += len("</svg>")
    return html[start:end].strip() + "\n"


def fetch(url: str, timeout: float = 30.0, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < retries:
                # Rate-limited: back off much longer than a normal retry,
                # honoring Retry-After when bian.org sends one.
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 20.0 * (attempt + 1)
                print(f"    (429 rate limit, esperando {wait:.0f}s antes de reintentar)", flush=True)
                time.sleep(wait)
                continue
            if attempt < retries:
                time.sleep(3.0 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(3.0 * (attempt + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {last_err}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="Ruta a bian-view-catalog.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Carpeta donde guardar los .svg")
    parser.add_argument("--only", help="Procesar solo el Service Domain cuyo nombre coincida exactamente")
    parser.add_argument("--force", action="store_true", help="Redescargar aunque el .svg ya exista")
    parser.add_argument(
        "--delay",
        type=float,
        default=2.5,
        help="Segundos de espera entre requests (default 2.5 -- bian.org rate-limita si se va mas rapido que esto)",
    )
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    entries = [c for c in catalog if c.get("control_record_diagram_url")]
    if args.only:
        entries = [c for c in entries if c["service_domain"] == args.only]
        if not entries:
            print(f"'{args.only}' no tiene control_record_diagram_url en el catalogo.", file=sys.stderr)
            return 1

    skipped_no_url = sum(1 for c in catalog if not c.get("control_record_diagram_url"))
    print(f"{len(entries)} Service Domains con Control Record Diagram ({skipped_no_url} sin URL, se omiten)", flush=True)

    ok, skipped_existing, failed = 0, 0, []
    for i, entry in enumerate(entries, 1):
        sd = entry["service_domain"]
        url = entry["control_record_diagram_url"]
        out_path = args.output_dir / f"{slugify(sd)}.svg"

        if out_path.exists() and not args.force:
            skipped_existing += 1
            print(f"[{i}/{len(entries)}] SKIP (ya existe) {out_path.name}", flush=True)
            continue

        try:
            html = fetch(url)
            svg = extract_svg(html)
            if svg is None:
                raise RuntimeError("no se encontro un bloque <svg>...</svg> en la pagina")
            out_path.write_text(svg, encoding="utf-8")
            ok += 1
            print(f"[{i}/{len(entries)}] OK {out_path.name} ({len(svg)} bytes)", flush=True)
        except Exception as e:
            failed.append((sd, url, str(e)))
            print(f"[{i}/{len(entries)}] ERROR {sd}: {e}", file=sys.stderr, flush=True)

        if args.delay:
            time.sleep(args.delay)

    print()
    print(f"Descargados: {ok}, ya existian: {skipped_existing}, fallidos: {len(failed)}")
    if failed:
        print("Fallidos:")
        for sd, url, err in failed:
            print(f"  - {sd} ({url}): {err}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
