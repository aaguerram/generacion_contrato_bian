"""
Enriquece los .puml de docs/bian-puml/ con las anotaciones (BQ, AssetType,
ControlRecord, GenericArtifact, HelperDiagram, BOMDiagram) que en el .svg
fuente aparecen como notas turquesa/gris "pegadas" a una clase mediante una
linea conectora (o, para los recuadros "<Clase> Helper/BOM Diagram", por
coincidencia de nombre o cercania geometrica).

Ver README.md en esta misma carpeta para el detalle del algoritmo y ejemplos
de uso.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BBox = Tuple[float, float, float, float]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SVG_DIR = REPO_ROOT / "docs" / "bian-diagrams" / "svg"
DEFAULT_PUML_DIR = REPO_ROOT / "docs" / "bian-puml"

LEGEND = """' Annotation legend (notes linked to a class via an SVG connector line/geometry):
'   Extensible: yes/no      -> from the class box border color in the SVG:
'                              red border only (fill #eae8e8 / stroke #c47474) = yes,
'                              this class's attributes MAY be pulled into this
'                              diagram from its owning Service Domain if needed;
'                              fully red (fill #ff8080 / stroke #d91616) = no,
'                              extending it is not allowed. Absent = plain
'                              class (fill #ffffff / stroke #d9d9d9), not part
'                              of this distinction.
'   BQ: <name>              -> Behavior Qualifier note linked to this class
'   AssetType: <name>       -> AssetType note linked to this class
'   ControlRecord: <name>   -> ControlRecord note linked to this class
'   GenericArtifact: <name> -> GenericArtifact note linked to this class
'   HelperDiagram: <name>   -> local BOM helper-diagram box named "<Class> Helper Diagram"
'   BOMDiagram: <name>      -> cross-service-domain BOM diagram box named "<Class> BOM Diagram"
"""

# Class-box border styles that carry the BIAN "can this be extended into the
# current diagram" semantic (see docs/bian-diagrams/svg/*.svg <style> block,
# selector ".object{bizzid} {fill:...;stroke:...}"). Confirmed identical
# across every SD checked (party-reference-data-directory, transaction-
# authorization, session-dialogue, card-clearing, letter-of-credit).
EXTENSIBLE_STYLE = ("#eae8e8", "#c47474")  # red border, light fill -> may extend
SEALED_STYLE = ("#ff8080", "#d91616")  # fully red -> must not extend


@dataclass
class SvgNode:
    bizzid: str
    label: str
    bbox: BBox


@dataclass
class ExtractionReport:
    svg_file: str
    classes: int = 0
    annotated_classes: int = 0
    tag_lines: int = 0
    unmatched_notes: List[str] = field(default_factory=list)
    unclassified_notes: List[str] = field(default_factory=list)
    unclassified_diagram_boxes: List[str] = field(default_factory=list)
    proximity_matches: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


# --------------------------------------------------------------------------
# SVG parsing
# --------------------------------------------------------------------------

def _pts_from_path_d(d: str) -> List[Tuple[float, float]]:
    nums = re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", d)
    return [(float(a), float(b)) for a, b in nums]


def _bbox_from_points(pts: List[Tuple[float, float]]) -> BBox:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_svg(svg_text: str) -> Tuple[Dict[str, SvgNode], Dict[str, SvgNode], Dict[str, SvgNode], Dict[str, List[Tuple[float, float]]]]:
    """Returns (classes, notes, diagram_boxes, edges), all keyed by bizzid."""

    # A label block is always <g bizzid="label{id}"><g font-family=...>
    # {one or more <text>}</g></g> -- bounded structurally by its own two
    # closing </g> tags, NOT by the outer node's "-lvl" marker (that marker
    # sits after every sibling, e.g. a class's attribute rows, so anchoring
    # on it would swallow unrelated text). Multi-line notes such as
    # "ControlRecord: \nParty Reference Data Directory Entry" or
    # "Interbank \nRelationship \nManagement \nBOM Diagram" are joined here.
    label_block_re = re.compile(
        r'<g bizzid="label(\d+)"[^>]*>\s*<g[^>]*>((?:\s*<text[^>]*>[^<]*</text>\s*)+)</g>\s*</g>'
    )
    labels: Dict[str, str] = {}
    for m in label_block_re.finditer(svg_text):
        bizzid, block = m.groups()
        texts = re.findall(r"<text[^>]*>([^<]*)</text>", block)
        labels[bizzid] = _clean_label("".join(texts))

    classes: Dict[str, SvgNode] = {}
    class_re = re.compile(
        r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="UML_Class" bizztype="node" bizzsymbol="rectangle">\s*'
        r'<g>\s*<g class="object\1">\s*<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"'
    )
    for m in class_re.finditer(svg_text):
        bizzid, x, y, w, h = m.groups()
        x, y, w, h = float(x), float(y), float(w), float(h)
        classes[bizzid] = SvgNode(bizzid, labels.get(bizzid, "?"), (x, y, x + w, y + h))

    notes: Dict[str, SvgNode] = {}
    dogear_re = re.compile(
        r'<g bizzid="(\d+)" bizzsemantic="\1" bizzconcept="ViewGraphic" bizztype="node" bizzsymbol="dogear">\s*'
        r'<g class="object\1">\s*<path[^>]*d="([^"]+)"'
    )
    for m in dogear_re.finditer(svg_text):
        bizzid, d = m.groups()
        notes[bizzid] = SvgNode(bizzid, labels.get(bizzid, "?"), _bbox_from_points(_pts_from_path_d(d)))

    diagram_boxes: Dict[str, SvgNode] = {}
    diag_re = re.compile(
        r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="UML_ClassDiagram" bizztype="node" bizzsymbol="rectangle">\s*'
        r'<g class="object\1">\s*<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"'
    )
    for m in diag_re.finditer(svg_text):
        bizzid, x, y, w, h = m.groups()
        x, y, w, h = float(x), float(y), float(w), float(h)
        diagram_boxes[bizzid] = SvgNode(bizzid, labels.get(bizzid, "?"), (x, y, x + w, y + h))

    edges: Dict[str, List[Tuple[float, float]]] = {}
    edge_re = re.compile(
        r'<g bizzid="(\d+)" bizzconcept="ViewEdge" bizztype="relation" bizzsymbol="link">\s*'
        r'<g>\s*<g class="object\1">\s*<path[^>]*d="([^"]+)"'
    )
    for m in edge_re.finditer(svg_text):
        bizzid, d = m.groups()
        edges[bizzid] = _pts_from_path_d(d)

    return classes, notes, diagram_boxes, edges


def parse_class_styles(svg_text: str) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    """Returns bizzid -> (fill, stroke) parsed from the <style>.object{id}{...}
    CSS rules. Only fill/stroke are read; other properties (stroke-width,
    dasharray, fill-opacity) don't matter for the extend/no-extend distinction.
    """

    style_re = re.compile(r"\.object(\d+)\s*\{([^}]*)\}")
    fill_re = re.compile(r"fill:\s*(#[0-9a-fA-F]{6})")
    stroke_re = re.compile(r"stroke:\s*(#[0-9a-fA-F]{6})")

    styles: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for m in style_re.finditer(svg_text):
        bizzid, body = m.groups()
        fill_m = fill_re.search(body)
        stroke_m = stroke_re.search(body)
        styles[bizzid] = (
            fill_m.group(1).lower() if fill_m else None,
            stroke_m.group(1).lower() if stroke_m else None,
        )
    return styles


def classify_class_styles(
    classes: Dict[str, SvgNode], styles: Dict[str, Tuple[Optional[str], Optional[str]]]
) -> Dict[str, List[Tuple[str, str]]]:
    """Returns class_bizzid -> [("Extensible", "yes"/"no")], only for classes
    whose border marks them as extensible or sealed; plain classes get
    nothing (that distinction doesn't apply to them).
    """

    result: Dict[str, List[Tuple[str, str]]] = {}
    for bizzid in classes:
        style = styles.get(bizzid)
        if style == EXTENSIBLE_STYLE:
            result[bizzid] = [("Extensible", "yes")]
        elif style == SEALED_STYLE:
            result[bizzid] = [("Extensible", "no")]
    return result


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------

def _point_near_bbox(pt: Tuple[float, float], bbox: BBox, tol: float = 15.0) -> bool:
    x, y = pt
    x0, y0, x1, y1 = bbox
    return (x0 - tol) <= x <= (x1 + tol) and (y0 - tol) <= y <= (y1 + tol)


def _closest_class(pt: Tuple[float, float], classes: Dict[str, SvgNode]) -> Tuple[Optional[str], float]:
    best, best_d = None, None
    for bizzid, node in classes.items():
        x0, y0, x1, y1 = node.bbox
        cx = min(max(pt[0], x0), x1)
        cy = min(max(pt[1], y0), y1)
        d = ((pt[0] - cx) ** 2 + (pt[1] - cy) ** 2) ** 0.5
        if best_d is None or d < best_d:
            best_d, best = d, bizzid
    return best, (best_d if best_d is not None else float("inf"))


# --------------------------------------------------------------------------
# Note / diagram-box -> class matching
# --------------------------------------------------------------------------

NOTE_KIND_PATTERNS = [
    ("BQ", re.compile(r"^BQ(?::\s*|\s+)(.+)$")),
    ("AssetType", re.compile(r"^AssetType:\s*(.+)$")),
    ("ControlRecord", re.compile(r"^ControlRecord:\s*(.+)$")),
    ("GenericArtifact", re.compile(r"^GenericArtifact:\s*(.+)$")),
]


def classify_note(label: str) -> Optional[Tuple[str, str]]:
    for kind, pattern in NOTE_KIND_PATTERNS:
        m = pattern.match(label)
        if m:
            return kind, m.group(1).strip()
    return None


def match_notes_to_classes(
    notes: Dict[str, SvgNode],
    classes: Dict[str, SvgNode],
    edges: Dict[str, List[Tuple[float, float]]],
    report: ExtractionReport,
) -> Dict[str, List[Tuple[str, str]]]:
    """Returns class_bizzid -> list[(kind, value)]."""

    result: Dict[str, List[Tuple[str, str]]] = {}
    for note_id, note in notes.items():
        classified = classify_note(note.label)
        if classified is None:
            report.unclassified_notes.append(f"{note_id} {note.label!r}")
            continue
        kind, value = classified

        matched_any = False
        for edge_id, pts in edges.items():
            if len(pts) < 2:
                continue
            start, end = pts[0], pts[-1]
            touches_start = _point_near_bbox(start, note.bbox)
            touches_end = _point_near_bbox(end, note.bbox)
            if not (touches_start or touches_end):
                continue
            other = end if touches_start else start
            class_id, dist = _closest_class(other, classes)
            if class_id is None or dist > 30:
                continue
            matched_any = True
            result.setdefault(class_id, []).append((kind, value))

        if not matched_any:
            report.unmatched_notes.append(f"{note_id} {note.label!r}")

    return result


def match_diagram_boxes_to_classes(
    diagram_boxes: Dict[str, SvgNode],
    classes: Dict[str, SvgNode],
    report: ExtractionReport,
) -> Dict[str, List[Tuple[str, str]]]:
    result: Dict[str, List[Tuple[str, str]]] = {}
    name_lookup = {node.label.strip().lower(): bizzid for bizzid, node in classes.items()}

    for box_id, box in diagram_boxes.items():
        label = box.label
        if label.endswith(" Helper Diagram"):
            kind = "HelperDiagram"
            base_name = label[: -len(" Helper Diagram")].strip()
        elif label.endswith(" BOM Diagram"):
            kind = "BOMDiagram"
            base_name = label[: -len(" BOM Diagram")].strip()
        else:
            report.unclassified_diagram_boxes.append(f"{box_id} {label!r}")
            continue

        class_id = name_lookup.get(base_name.lower())
        if class_id is None:
            # Cross-service-domain reference (e.g. "Party Lifecycle Management
            # BOM Diagram" naming another SD, not a local class) -> fall back
            # to the nearest class geometrically.
            x0, y0, x1, y1 = box.bbox
            bottom_center = ((x0 + x1) / 2, y1)
            class_id, dist = _closest_class(bottom_center, classes)
            if class_id is None:
                continue
            report.proximity_matches.append(
                f"{box_id} {label!r} -> {classes[class_id].label!r} (dist={dist:.1f})"
            )

        result.setdefault(class_id, []).append((kind, label))

    return result


def merge_tags(*maps: Dict[str, List[Tuple[str, str]]]) -> Dict[str, List[Tuple[str, str]]]:
    merged: Dict[str, List[Tuple[str, str]]] = {}
    for m in maps:
        for class_id, tags in m.items():
            merged.setdefault(class_id, []).extend(tags)
    return merged


KIND_ORDER = ["Extensible", "BQ", "AssetType", "ControlRecord", "GenericArtifact", "HelperDiagram", "BOMDiagram"]


def render_tag_lines(tags: List[Tuple[str, str]]) -> List[str]:
    def sort_key(t: Tuple[str, str]) -> Tuple[int, str]:
        kind, value = t
        return (KIND_ORDER.index(kind) if kind in KIND_ORDER else len(KIND_ORDER), value)

    lines = []
    for kind, value in sorted(set(tags), key=sort_key):
        lines.append(f"{kind}: {value}")
    return lines


# --------------------------------------------------------------------------
# PUML injection
# --------------------------------------------------------------------------

CLASS_DECL_RE = re.compile(r'class\s+"[^"]+"\s+as\s+(N\d+)\s*\{[^{}]*\}')


def ensure_legend(puml_text: str) -> str:
    if "Annotation legend" in puml_text:
        return puml_text
    marker = "hide methods"
    if marker not in puml_text:
        return puml_text
    return puml_text.replace(marker, LEGEND + marker, 1)


def inject_notes(puml_text: str, class_tags: Dict[str, List[str]]) -> str:
    """class_tags is keyed by the PUML alias, e.g. 'N199916'."""

    out: List[str] = []
    cursor = 0
    for m in CLASS_DECL_RE.finditer(puml_text):
        alias = m.group(1)
        out.append(puml_text[cursor : m.end()])
        cursor = m.end()

        # Strip a previously-generated note block for this alias, if present,
        # so re-running the script is idempotent.
        note_strip_re = re.compile(
            r"\n(?:[ \t]*\n)*note right of " + re.escape(alias) + r"\n(?:.*\n)*?end note"
        )
        nm = note_strip_re.match(puml_text, cursor)
        if nm:
            cursor = nm.end()

        lines = class_tags.get(alias)
        if lines:
            body = "\n".join(f"  {line}" for line in lines)
            out.append(f"\nnote right of {alias}\n{body}\nend note")

    out.append(puml_text[cursor:])
    return "".join(out)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def process_pair(svg_path: Path, puml_path: Path) -> Tuple[str, ExtractionReport]:
    svg_text = svg_path.read_text(encoding="utf-8")
    puml_text = puml_path.read_text(encoding="utf-8")

    classes, notes, diagram_boxes, edges = parse_svg(svg_text)
    report = ExtractionReport(svg_file=svg_path.name, classes=len(classes))

    styles = parse_class_styles(svg_text)
    style_tags = classify_class_styles(classes, styles)
    note_tags = match_notes_to_classes(notes, classes, edges, report)
    diagram_tags = match_diagram_boxes_to_classes(diagram_boxes, classes, report)
    merged = merge_tags(style_tags, note_tags, diagram_tags)

    class_tags = {f"N{bizzid}": render_tag_lines(tags) for bizzid, tags in merged.items()}
    report.annotated_classes = len(class_tags)
    report.tag_lines = sum(len(v) for v in class_tags.values())

    # Some .svg files are empty placeholders (the source diagram only ever
    # existed as a low-res PNG, per the .puml's own "raster reconstruction"
    # comment) -- report.classes==0 in that case. Adding the legend there
    # would falsely imply this .puml follows the vector-SVG extraction
    # convention, so skip it entirely and leave that .puml untouched.
    if report.classes == 0:
        return puml_text, report

    new_puml = ensure_legend(puml_text)
    new_puml = inject_notes(new_puml, class_tags)
    return new_puml, report


def find_pairs(svg_dir: Path, puml_dir: Path, only: Optional[str]) -> List[Tuple[Path, Path]]:
    pairs = []
    for svg_path in sorted(svg_dir.glob("*.svg")):
        stem = svg_path.stem
        if only and only != stem:
            continue
        puml_path = puml_dir / f"{stem}.puml"
        if puml_path.exists():
            pairs.append((svg_path, puml_path))
    return pairs


def main() -> int:
    # Windows consoles often default to cp1252; some BIAN labels contain
    # non-Latin1 punctuation (arrows, smart quotes), so force UTF-8 stdout.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-dir", type=Path, default=DEFAULT_SVG_DIR)
    parser.add_argument("--puml-dir", type=Path, default=DEFAULT_PUML_DIR)
    parser.add_argument("--only", help="Procesar solo el par cuyo nombre base (sin extension) coincida, p.ej. party-reference-data-directory")
    parser.add_argument("--dry-run", action="store_true", help="No escribe cambios; solo reporta lo que haria")
    parser.add_argument("--report", type=Path, help="Ruta opcional para volcar un resumen JSON de la corrida")
    args = parser.parse_args()

    pairs = find_pairs(args.svg_dir, args.puml_dir, args.only)
    if not pairs:
        print("No se encontraron pares .svg/.puml con nombre coincidente.", file=sys.stderr)
        return 1

    all_reports = []
    for svg_path, puml_path in pairs:
        new_puml, report = process_pair(svg_path, puml_path)
        all_reports.append(report.to_dict())

        status = "DRY-RUN" if args.dry_run else "OK"
        print(
            f"[{status}] {svg_path.name}: {report.classes} clases, "
            f"{report.annotated_classes} anotadas, {report.tag_lines} tags"
        )
        if report.unmatched_notes:
            print(f"    notas sin clase asociada: {report.unmatched_notes}")
        if report.unclassified_notes:
            print(f"    notas con texto no reconocido (BQ/AssetType/ControlRecord/GenericArtifact): {report.unclassified_notes}")
        if report.unclassified_diagram_boxes:
            print(f"    recuadros de diagrama sin patron Helper/BOM: {report.unclassified_diagram_boxes}")
        if report.proximity_matches:
            print(f"    asociados por cercania geometrica (revisar): {report.proximity_matches}")

        if not args.dry_run:
            puml_path.write_text(new_puml, encoding="utf-8")

    if args.report:
        args.report.write_text(json.dumps(all_reports, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reporte JSON escrito en {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
