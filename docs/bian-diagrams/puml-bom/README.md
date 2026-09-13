# BIAN UML / PlantUML extraction

This package contains **272 independent PlantUML (`.puml`) files**, one per supplied BIAN image.

## Extraction modes

- **SVG semantic extraction:** 256 diagrams were reconstructed directly from the vector SVG semantic elements. Classes, attributes, enumerations, generalizations, associations and cardinalities are preserved where present.
- **RASTER_RECONSTRUCTED:** 16 diagrams had PNG only. Their visible BIAN structure was reconstructed as machine-readable PlantUML and normalized with explicit stereotype/relationship labels. These files are marked in `index.csv` and include an extraction note inside the PUML.

## AI-oriented conventions

- Every diagram is self-contained between `@startuml` and `@enduml`.
- Human-readable BIAN names remain in quotes.
- SVG-derived diagrams use stable internal aliases based on the source diagram IDs.
- Relationships are explicit and cardinalities are retained where available.
- Source image and BIAN source URL are included as comments in each file.
- Use `index.csv` to map service domain -> source image -> generated PUML and to distinguish extraction mode.

## Counts

- Total PUML files: 272
- SVG semantic extraction: 256
- Raster reconstruction: 16
- SVG relationships left unmapped: 0
