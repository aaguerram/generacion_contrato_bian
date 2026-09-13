"""
Genera, desde cero, un .puml por cada SVG de Control Record en
docs/bian-diagrams/svg_control_record/ -- a diferencia de scripts/svg_to_puml
(que solo *enriquece* un .puml ya existente con notas), este script no
depende de ningun .puml previo: lee el SVG y reconstruye clases, datatypes,
enums, atributos (con su cardinalidad), relaciones (con cardinalidad y rol en
cada extremo) y las mismas anotaciones de scripts/svg_to_puml (BQ, AssetType,
ControlRecord, GenericArtifact, HelperDiagram, BOMDiagram, Extensible), mas
una nueva: BianBom, para las clases que en el SVG estan dentro del recuadro
punteado "BIAN BOM".

Ver README.md en esta misma carpeta para el detalle de cada convencion del
SVG y como se mapea a PlantUML.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BBox = Tuple[float, float, float, float]
Point = Tuple[float, float]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SVG_DIR = REPO_ROOT / "docs" / "bian-diagrams" / "svg_control_record"
DEFAULT_PUML_DIR = REPO_ROOT / "docs" / "bian-diagrams" / "puml-control-record"
DEFAULT_CATALOG = REPO_ROOT / "docs" / "bian-view-catalog.json"

LEGEND = """' Annotation legend:
'   <<datatype>>            -> the SVG marks this shape as UML_DataType (not a plain class)
'   BianBom: yes            -> this class/enum/datatype sits inside the SVG's
'                              dashed "BIAN BOM" grouping box
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

EXTENSIBLE_STYLE = ("#eae8e8", "#c47474")
SEALED_STYLE = ("#ff8080", "#d91616")

CARDINALITY_RE = re.compile(r"^\*$|^\d+$|^\d+\.\.(\d+|\*)$")


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Element:
    """A UML_Class, UML_DataType or UML_Enumeration shape."""

    bizzid: str
    label: str
    bbox: BBox
    kind: str  # "class" | "datatype" | "enum"
    attributes: List[Tuple[str, str, str]] = field(default_factory=list)  # (name, type, card)
    literals: List[str] = field(default_factory=list)
    tags: List[Tuple[str, str]] = field(default_factory=list)  # (kind, value) e.g. ("BQ","Reference")


@dataclass
class Relationship:
    kind: str  # "association" | "generalization" | "plain"
    from_id: str
    to_id: str
    from_label: str = ""
    to_label: str = ""


@dataclass
class SvgNode:
    bizzid: str
    label: str
    bbox: BBox


@dataclass
class ExtractionReport:
    svg_file: str
    classes: int = 0
    datatypes: int = 0
    enums: int = 0
    attributes: int = 0
    relationships: int = 0
    bian_bom_elements: int = 0
    unmatched_notes: List[str] = field(default_factory=list)
    unclassified_notes: List[str] = field(default_factory=list)
    unclassified_diagram_boxes: List[str] = field(default_factory=list)
    unresolved_edges: List[str] = field(default_factory=list)
    proximity_matches: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


# --------------------------------------------------------------------------
# Low-level SVG parsing helpers
# --------------------------------------------------------------------------

def _pts_from_path_d(d: str) -> List[Point]:
    nums = re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", d)
    return [(float(a), float(b)) for a, b in nums]


def _bbox_from_points(pts: List[Point]) -> BBox:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


STEREOTYPE_PREFIX_RE = re.compile(r"^«[^»]*»\s*")


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _strip_stereotype(text: str) -> str:
    """UML_DataType/UML_Enumeration labels carry a literal leading
    "«datatype»"/"«enumeration»" line (HTML-entity-encoded in the SVG,
    e.g. "&#xab;datatype&#xbb;&#xa;") ahead of the real name -- PlantUML
    already renders that stereotype from the `enum` keyword or our own
    `<<datatype>>` tag, so it's stripped here to avoid doubling it up.
    """

    return STEREOTYPE_PREFIX_RE.sub("", text).strip()


def _find_body(content: str, bizzid: str, start: int) -> Tuple[int, int]:
    """Returns (body_start, body_end) for the node opened at `start`, bounded
    by that same node's own "#object{bizzid}-lvl" closing marker. Every
    nested child (attribute, literal, or another shape geometrically inside
    a grouping box) lies inside this span.
    """

    marker = f"#object{bizzid}-lvl"
    end = content.find(marker, start)
    if end == -1:
        end = len(content)
    return start, end


# --------------------------------------------------------------------------
# Label extraction (shared with scripts/svg_to_puml)
# --------------------------------------------------------------------------

LABEL_BLOCK_RE = re.compile(
    r'<g bizzid="label(\d+)"[^>]*>\s*<g[^>]*>((?:\s*<text[^>]*>[^<]*</text>\s*)+)</g>\s*</g>'
)


def parse_labels(content: str) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for m in LABEL_BLOCK_RE.finditer(content):
        bizzid, block = m.groups()
        texts = re.findall(r"<text[^>]*>([^<]*)</text>", block)
        labels[bizzid] = _clean_label("".join(texts))
    return labels


# --------------------------------------------------------------------------
# Shapes: UML_Class / UML_DataType / UML_Enumeration
# --------------------------------------------------------------------------

SHAPE_HEADER_RE = re.compile(
    r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="(UML_Class|UML_DataType|UML_Enumeration)" '
    r'bizztype="node" bizzsymbol="rectangle">\s*<g>?\s*<g class="object\1">\s*'
    r'<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"'
)

ATTR_HEADER_RE = re.compile(
    r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="UML_Attribute" bizztype="node" bizzsymbol="rectangle">'
)
LITERAL_HEADER_RE = re.compile(
    r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="UML_EnumerationLiteral" bizztype="node" bizzsymbol="rectangle">'
)

ATTR_TEXT_RE = re.compile(r"^(?P<name>.+?)\s*:\s*(?P<type>[^\[]+?)(?:\[(?P<card>[^\]]*)\])?$")


def parse_elements(content: str, labels: Dict[str, str]) -> Tuple[Dict[str, Element], Dict[str, int]]:
    elements: Dict[str, Element] = {}
    starts: Dict[str, int] = {}
    kind_map = {"UML_Class": "class", "UML_DataType": "datatype", "UML_Enumeration": "enum"}

    for m in SHAPE_HEADER_RE.finditer(content):
        bizzid, concept, x, y, w, h = m.groups()
        x, y, w, h = float(x), float(y), float(w), float(h)
        kind = kind_map[concept]
        el = Element(bizzid=bizzid, label=_strip_stereotype(labels.get(bizzid, "?")), bbox=(x, y, x + w, y + h), kind=kind)
        starts[bizzid] = m.start()

        body_start, body_end = _find_body(content, bizzid, m.start())
        body = content[body_start:body_end]

        if kind == "enum":
            for lm in LITERAL_HEADER_RE.finditer(body):
                lit_id = lm.group(1)
                el.literals.append(labels.get(lit_id, "?"))
        else:
            for am in ATTR_HEADER_RE.finditer(body):
                attr_id = am.group(1)
                raw = labels.get(attr_id)
                if raw is None:
                    continue
                tm = ATTR_TEXT_RE.match(raw)
                if tm:
                    el.attributes.append((tm.group("name").strip(), tm.group("type").strip(), (tm.group("card") or "").strip()))
                else:
                    el.attributes.append((raw, "", ""))

        elements[bizzid] = el

    return elements, starts


# --------------------------------------------------------------------------
# "BIAN BOM" grouping box -> BianBom tag
# --------------------------------------------------------------------------

GROUP_BOX_RE = re.compile(
    r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="ViewGraphic" bizztype="node" bizzsymbol="rectangle">'
)


def mark_bian_bom(content: str, elements: Dict[str, Element], element_starts: Dict[str, int], labels: Dict[str, str]) -> None:
    """A "BIAN BOM" box is a plain ViewGraphic rectangle that -- unlike a BQ
    dogear note or a Helper/BOM Diagram box, both of which merely *point* at
    a class via a separate connector line -- literally *nests* the classes
    it groups as DOM children inside its own <g>...</g>. So membership is a
    string-position containment check against each box's own body span, not
    a geometric or edge-based match.
    """

    for m in GROUP_BOX_RE.finditer(content):
        box_id = m.group(1)
        if labels.get(box_id, "").strip() != "BIAN BOM":
            continue
        body_start, body_end = _find_body(content, box_id, m.start())
        for eid, pos in element_starts.items():
            if body_start <= pos < body_end:
                elements[eid].tags.append(("BianBom", "yes"))


# --------------------------------------------------------------------------
# Class border color -> Extensible tag (same convention as scripts/svg_to_puml)
# --------------------------------------------------------------------------

def parse_class_styles(content: str) -> Dict[str, Tuple[Optional[str], Optional[str]]]:
    style_re = re.compile(r"\.object(\d+)\s*\{([^}]*)\}")
    fill_re = re.compile(r"fill:\s*(#[0-9a-fA-F]{6})")
    stroke_re = re.compile(r"stroke:\s*(#[0-9a-fA-F]{6})")
    styles: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    for m in style_re.finditer(content):
        bizzid, body = m.groups()
        fill_m = fill_re.search(body)
        stroke_m = stroke_re.search(body)
        styles[bizzid] = (
            fill_m.group(1).lower() if fill_m else None,
            stroke_m.group(1).lower() if stroke_m else None,
        )
    return styles


def apply_extensible_tags(elements: Dict[str, Element], styles: Dict[str, Tuple[Optional[str], Optional[str]]]) -> None:
    for eid, el in elements.items():
        style = styles.get(eid)
        if style == EXTENSIBLE_STYLE:
            el.tags.append(("Extensible", "yes"))
        elif style == SEALED_STYLE:
            el.tags.append(("Extensible", "no"))


# --------------------------------------------------------------------------
# Dogear notes (BQ / AssetType / ControlRecord / GenericArtifact) and
# Helper/BOM Diagram boxes -- same conventions as scripts/svg_to_puml.
# --------------------------------------------------------------------------

DOGEAR_RE = re.compile(
    r'<g bizzid="(\d+)" bizzsemantic="\1" bizzconcept="ViewGraphic" bizztype="node" bizzsymbol="dogear">\s*'
    r'<g class="object\1">\s*<path[^>]*d="([^"]+)"'
)
DIAGRAM_BOX_RE = re.compile(
    r'<g bizzid="(\d+)" bizzsemantic="[^"]*" bizzconcept="UML_ClassDiagram" bizztype="node" bizzsymbol="rectangle">\s*'
    r'<g class="object\1">\s*<rect x="(-?[\d.]+)" y="(-?[\d.]+)" width="(-?[\d.]+)" height="(-?[\d.]+)"'
)
EDGE_RE = re.compile(
    # ViewEdge headers never carry bizzsemantic; UML_Association and
    # UML_Generalization headers always do -- make it optional so both
    # shapes match with one pattern.
    r'<g bizzid="(\d+)"(?: bizzsemantic="[^"]*")? bizzconcept="(ViewEdge|UML_Association|UML_Generalization)" bizztype="relation" bizzsymbol="link">\s*'
    r'<g>\s*<g class="object\1">\s*<path[^>]*d="([^"]+)"'
)

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


def _point_near_bbox(pt: Point, bbox: BBox, tol: float = 15.0) -> bool:
    x, y = pt
    x0, y0, x1, y1 = bbox
    return (x0 - tol) <= x <= (x1 + tol) and (y0 - tol) <= y <= (y1 + tol)


def _closest_element(pt: Point, elements: Dict[str, Element]) -> Tuple[Optional[str], float]:
    best, best_d = None, None
    for eid, el in elements.items():
        x0, y0, x1, y1 = el.bbox
        cx = min(max(pt[0], x0), x1)
        cy = min(max(pt[1], y0), y1)
        d = ((pt[0] - cx) ** 2 + (pt[1] - cy) ** 2) ** 0.5
        if best_d is None or d < best_d:
            best_d, best = d, eid
    return best, (best_d if best_d is not None else float("inf"))


def parse_notes_and_boxes(content: str, labels: Dict[str, str]) -> Tuple[Dict[str, SvgNode], Dict[str, SvgNode]]:
    notes: Dict[str, SvgNode] = {}
    for m in DOGEAR_RE.finditer(content):
        bizzid, d = m.groups()
        notes[bizzid] = SvgNode(bizzid, labels.get(bizzid, "?"), _bbox_from_points(_pts_from_path_d(d)))

    boxes: Dict[str, SvgNode] = {}
    for m in DIAGRAM_BOX_RE.finditer(content):
        bizzid, x, y, w, h = m.groups()
        x, y, w, h = float(x), float(y), float(w), float(h)
        boxes[bizzid] = SvgNode(bizzid, labels.get(bizzid, "?"), (x, y, x + w, y + h))

    return notes, boxes


def apply_note_and_box_tags(
    elements: Dict[str, Element],
    notes: Dict[str, SvgNode],
    boxes: Dict[str, SvgNode],
    edges: List[Tuple[str, str, List[Point]]],
    report: ExtractionReport,
) -> set:
    """Resolves BQ/AssetType/ControlRecord/GenericArtifact notes and
    HelperDiagram/BOMDiagram boxes exactly like scripts/svg_to_puml, tagging
    the matched Element in place. Returns the set of edge ids consumed this
    way, so the relationship pass below can skip them.
    """

    consumed = set()

    for note_id, note in notes.items():
        classified = classify_note(note.label)
        if classified is None:
            report.unclassified_notes.append(f"{note_id} {note.label!r}")
            continue
        kind, value = classified
        matched_any = False
        for edge_id, concept, pts in edges:
            if concept != "ViewEdge" or len(pts) < 2:
                continue
            start, end = pts[0], pts[-1]
            touches_start = _point_near_bbox(start, note.bbox)
            touches_end = _point_near_bbox(end, note.bbox)
            if not (touches_start or touches_end):
                continue
            other = end if touches_start else start
            eid, dist = _closest_element(other, elements)
            if eid is None or dist > 30:
                continue
            matched_any = True
            consumed.add(edge_id)
            elements[eid].tags.append((kind, value))
        if not matched_any:
            report.unmatched_notes.append(f"{note_id} {note.label!r}")

    name_lookup = {el.label.strip().lower(): eid for eid, el in elements.items()}
    for box_id, box in boxes.items():
        label = box.label
        if label.endswith(" Helper Diagram"):
            kind, base_name = "HelperDiagram", label[: -len(" Helper Diagram")].strip()
        elif label.endswith(" BOM Diagram"):
            kind, base_name = "BOMDiagram", label[: -len(" BOM Diagram")].strip()
        else:
            report.unclassified_diagram_boxes.append(f"{box_id} {label!r}")
            continue

        eid = name_lookup.get(base_name.lower())
        if eid is None:
            x0, y0, x1, y1 = box.bbox
            eid, dist = _closest_element(((x0 + x1) / 2, y1), elements)
            if eid is None:
                continue
            report.proximity_matches.append(f"{box_id} {label!r} -> {elements[eid].label!r} (dist={dist:.1f})")
        elements[eid].tags.append((kind, label))

    return consumed


# --------------------------------------------------------------------------
# Relationships: UML_Association / UML_Generalization / class-to-class ViewEdge
# --------------------------------------------------------------------------

def _edge_body(content: str, bizzid: str, start: int) -> str:
    body_start, body_end = _find_body(content, bizzid, start)
    return content[body_start:body_end]


def _loose_texts(body: str) -> List[Tuple[str, Point]]:
    """Every free-floating <text x="X" y="Y">value</text> directly inside an
    edge's own body (role names and cardinality labels sit here as plain
    siblings, not inside their own bizzid-tagged sub-element)."""

    out = []
    for tm in re.finditer(r'<text x="(-?[\d.]+)" y="(-?[\d.]+)"[^>]*>([^<]*)</text>', body):
        x, y, text = tm.groups()
        text = html.unescape(text).strip()
        if not text or text in ("+", "-", "#", "~"):
            continue
        out.append((text, (float(x), float(y))))
    return out


def _dist(a: Point, b: Point) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def parse_relationships(
    content: str,
    elements: Dict[str, Element],
    edges: List[Tuple[str, str, List[Point]]],
    consumed: set,
    report: ExtractionReport,
) -> List[Relationship]:
    rels: List[Relationship] = []
    edge_starts = {}
    for m in EDGE_RE.finditer(content):
        edge_starts[m.group(1)] = m.start()

    for edge_id, concept, pts in edges:
        if edge_id in consumed or len(pts) < 2:
            continue
        start, end = pts[0], pts[-1]
        from_id, from_dist = _closest_element(start, elements)
        to_id, to_dist = _closest_element(end, elements)

        if concept == "ViewEdge":
            # A plain ViewEdge only becomes a relationship when BOTH ends
            # land on a real class/datatype/enum; otherwise it was meant for
            # a note/box and has already been consumed above (or, if it
            # matched neither, it's simply not something we can place).
            if from_id is None or to_id is None or from_dist > 30 or to_dist > 30:
                report.unresolved_edges.append(f"{edge_id} ViewEdge start={start} end={end}")
                continue
            rels.append(Relationship("plain", from_id, to_id))
            continue

        if from_id is None or to_id is None:
            report.unresolved_edges.append(f"{edge_id} {concept} start={start} end={end}")
            continue

        if concept == "UML_Generalization":
            rels.append(Relationship("generalization", from_id, to_id))
            continue

        # UML_Association: gather every loose text in the edge's body and
        # split it between the two ends by which endpoint it sits closer to,
        # preserving document order at each end (matches the existing
        # puml-bom convention, e.g. `"Registered / Party / 0..1"`).
        body = _edge_body(content, edge_id, edge_starts.get(edge_id, 0))
        from_tokens: List[str] = []
        to_tokens: List[str] = []
        for text, pt in _loose_texts(body):
            if _dist(pt, start) <= _dist(pt, end):
                from_tokens.append(text)
            else:
                to_tokens.append(text)
        rels.append(
            Relationship(
                "association",
                from_id,
                to_id,
                from_label=" / ".join(from_tokens),
                to_label=" / ".join(to_tokens),
            )
        )

    # Two distinct edge ids occasionally resolve to the exact same
    # (kind, from, to, labels) tuple -- e.g. a class with more than one
    # attribute typed against the same enum can get two connector lines in
    # the source SVG. Rendering both adds no information, so collapse exact
    # duplicates while keeping first-seen order.
    seen = set()
    deduped: List[Relationship] = []
    for r in rels:
        key = (r.kind, r.from_id, r.to_id, r.from_label, r.to_label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


# --------------------------------------------------------------------------
# PlantUML rendering
# --------------------------------------------------------------------------

KIND_ORDER = ["BianBom", "Extensible", "BQ", "AssetType", "ControlRecord", "GenericArtifact", "HelperDiagram", "BOMDiagram"]


def render_tag_lines(tags: List[Tuple[str, str]]) -> List[str]:
    def sort_key(t: Tuple[str, str]) -> Tuple[int, str]:
        kind, value = t
        return (KIND_ORDER.index(kind) if kind in KIND_ORDER else len(KIND_ORDER), value)

    return [f"{kind}: {value}" for kind, value in sorted(set(tags), key=sort_key)]


def render_attribute(name: str, type_: str, card: str) -> str:
    if not type_:
        return f"  + {name}"
    suffix = f"[{card}]" if card else ""
    return f"  + {name} : {type_}{suffix}"


def render_puml(service_domain: str, source_url: Optional[str], elements: Dict[str, Element], rels: List[Relationship]) -> str:
    lines = ["@startuml", f"title {service_domain} Control Record - BIAN UML"]
    lines.append("' Generated from BIAN Control Record diagram for machine-readable context")
    lines.append(f"' Service Domain: {service_domain}")
    if source_url:
        lines.append(f"' Source: {source_url}")
    lines.append("' Extraction: SVG semantic extraction (svg_to_puml_control_record)")
    lines.append(LEGEND.rstrip("\n"))
    lines.append("hide methods")
    lines.append("skinparam classAttributeIconSize 0")
    lines.append("left to right direction")
    lines.append("")

    for eid, el in sorted(elements.items(), key=lambda kv: kv[0]):
        alias = f"N{eid}"
        if el.kind == "enum":
            lines.append(f'enum "{el.label}" as {alias} {{')
            for lit in el.literals:
                lines.append(f"  {lit}")
            lines.append("}")
        else:
            stereotype = " <<datatype>>" if el.kind == "datatype" else ""
            lines.append(f'class "{el.label}" as {alias}{stereotype} {{')
            for name, type_, card in el.attributes:
                lines.append(render_attribute(name, type_, card))
            lines.append("}")

        tag_lines = render_tag_lines(el.tags)
        if tag_lines:
            lines.append(f"note right of {alias}")
            for t in tag_lines:
                lines.append(f"  {t}")
            lines.append("end note")
        lines.append("")

    if rels:
        lines.append("' Relationships")
        for r in rels:
            a, b = f"N{r.from_id}", f"N{r.to_id}"
            if r.kind == "generalization":
                lines.append(f"{b} <|-- {a}")
            elif r.kind == "plain":
                lines.append(f"{a} -- {b}")
            else:
                left = f' "{r.from_label}"' if r.from_label else ""
                right = f' "{r.to_label}"' if r.to_label else ""
                lines.append(f"{a}{left} --{right} {b}")
        lines.append("")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def process_svg(svg_path: Path, service_domain: str, source_url: Optional[str]) -> Tuple[str, ExtractionReport]:
    content = svg_path.read_text(encoding="utf-8")
    report = ExtractionReport(svg_file=svg_path.name)

    labels = parse_labels(content)
    elements, element_starts = parse_elements(content, labels)
    mark_bian_bom(content, elements, element_starts, labels)
    styles = parse_class_styles(content)
    apply_extensible_tags(elements, styles)

    notes, boxes = parse_notes_and_boxes(content, labels)
    edges: List[Tuple[str, str, List[Point]]] = []
    for m in EDGE_RE.finditer(content):
        bizzid, concept, d = m.groups()
        edges.append((bizzid, concept, _pts_from_path_d(d)))

    consumed = apply_note_and_box_tags(elements, notes, boxes, edges, report)
    rels = parse_relationships(content, elements, edges, consumed, report)

    report.classes = sum(1 for e in elements.values() if e.kind == "class")
    report.datatypes = sum(1 for e in elements.values() if e.kind == "datatype")
    report.enums = sum(1 for e in elements.values() if e.kind == "enum")
    report.attributes = sum(len(e.attributes) for e in elements.values())
    report.relationships = len(rels)
    report.bian_bom_elements = sum(1 for e in elements.values() if any(k == "BianBom" for k, _ in e.tags))

    puml = render_puml(service_domain, source_url, elements, rels)
    return puml, report


def load_catalog(catalog_path: Path) -> Dict[str, dict]:
    if not catalog_path.exists():
        return {}
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return {entry["service_domain"]: entry for entry in data}


def slug_to_name_guess(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-dir", type=Path, default=DEFAULT_SVG_DIR)
    parser.add_argument("--puml-dir", type=Path, default=DEFAULT_PUML_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="bian-view-catalog.json, para resolver nombre de SD y URL fuente")
    parser.add_argument("--only", help="Procesar solo el archivo cuyo nombre base (sin extension) coincida")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    by_name = load_catalog(args.catalog)
    by_slug = {}
    for name, entry in by_name.items():
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        by_slug[slug] = entry

    svg_paths = sorted(args.svg_dir.glob("*.svg"))
    if args.only:
        svg_paths = [p for p in svg_paths if p.stem == args.only]
        if not svg_paths:
            print(f"No se encontro {args.only}.svg en {args.svg_dir}", file=sys.stderr)
            return 1

    args.puml_dir.mkdir(parents=True, exist_ok=True)

    all_reports = []
    for svg_path in svg_paths:
        slug = svg_path.stem
        entry = by_slug.get(slug)
        service_domain = entry["service_domain"] if entry else slug_to_name_guess(slug)
        source_url = entry["control_record_diagram_url"] if entry else None

        puml, report = process_svg(svg_path, service_domain, source_url)
        all_reports.append(report.to_dict())

        status = "DRY-RUN" if args.dry_run else "OK"
        print(
            f"[{status}] {slug}: {report.classes} clases, {report.datatypes} datatypes, "
            f"{report.enums} enums, {report.attributes} atributos, {report.relationships} relaciones, "
            f"{report.bian_bom_elements} en BIAN BOM"
        )
        if report.unresolved_edges:
            print(f"    edges sin resolver: {report.unresolved_edges}")
        if report.unmatched_notes:
            print(f"    notas sin clase asociada: {report.unmatched_notes}")
        if report.unclassified_notes:
            print(f"    notas con texto no reconocido: {report.unclassified_notes}")
        if report.unclassified_diagram_boxes:
            print(f"    recuadros de diagrama sin patron Helper/BOM: {report.unclassified_diagram_boxes}")
        if report.proximity_matches:
            print(f"    asociados por cercania geometrica (revisar): {report.proximity_matches}")

        if not args.dry_run:
            (args.puml_dir / f"{slug}.puml").write_text(puml, encoding="utf-8")

    if args.report:
        args.report.write_text(json.dumps(all_reports, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Reporte JSON escrito en {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
