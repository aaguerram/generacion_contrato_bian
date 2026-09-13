# svg_to_puml_v2

Genera, **desde cero**, un `.puml` por cada SVG de Control Record en
[`docs/bian-diagrams/svg_control_record/`](../../docs/bian-diagrams/svg_control_record/)
y lo deja en
[`docs/bian-diagrams/puml-control-record/`](../../docs/bian-diagrams/puml-control-record/).

## En que se diferencia de scripts/svg_to_puml

`scripts/svg_to_puml` (v1) **enriquece** un `.puml` que ya existe (el de
`docs/bian-diagrams/puml-bom/`, con sus clases/atributos/relaciones ya extraidos por otro
proceso) agregandole notas (`BQ`, `AssetType`, `HelperDiagram`, etc.).

Para los Control Record no hay ningun `.puml` previo -- `docs/bian-diagrams/puml-bom/`
solo cubre el BOM completo de cada Service Domain, nunca su Control Record.
`svg_to_puml_v2` no enriquece nada: **reconstruye el diagrama entero** leyendo
directamente el SVG -- clases, `<<datatype>>`, enums (con sus literales),
atributos (con su cardinalidad), relaciones (con cardinalidad y rol en cada
extremo), y las mismas anotaciones de v1 (`BQ`, `AssetType`, `ControlRecord`,
`GenericArtifact`, `HelperDiagram`, `BOMDiagram`, `Extensible`), mas una
nueva: `BianBom`.

## Convenciones del SVG (Bizzdesign) y como se mapean

Cada forma trae su tipo en el atributo `bizzconcept`. Los que le importan a
este script:

| `bizzconcept` | Que es | Como se renderiza |
|---|---|---|
| `UML_Class` | Clase normal | `class "Nombre" as N<id> { ... }` |
| `UML_DataType` | Datatype | `class "Nombre" as N<id> <<datatype>> { ... }` |
| `UML_Enumeration` | Enum | `enum "Nombre" as N<id> { literal1 ... }` |
| `UML_Attribute` | Un atributo, anidado dentro de una clase/datatype | una linea `+ Nombre : Tipo[cardinalidad]` |
| `UML_EnumerationLiteral` | Un valor de enum, anidado dentro del enum | una linea dentro del `enum { }` |
| `UML_Association` | Relacion con cardinalidad/rol en los extremos | `N<a> "rol / card" -- "card" N<b>` |
| `UML_Generalization` | Herencia | `N<parent> <|-- N<child>` |
| `ViewEdge` (generico) | Segun a que conecte: ver abajo | -- |

**Ojo con el `bizzsemantic`**: los headers de `ViewEdge` normal nunca traen
el atributo `bizzsemantic`, pero `UML_Association` y `UML_Generalization`
siempre lo traen (`bizzid="X" bizzsemantic="Y" bizzconcept="UML_Association"
...`). El regex de deteccion de edges lo trata como opcional -- si algun dia
alguien "simplifica" ese regex quitando el `?`, vuelve a perder todas las
asociaciones con cardinalidad silenciosamente (paso por ese bug al escribir
el script: sin el `?` el conteo de relaciones bajaba de 9 a 6 en el archivo
piloto sin ningun error visible, solo datos incompletos).

### Cardinalidad y rol de una relacion

Un `UML_Association` no guarda el texto de cardinalidad/rol en un atributo:
lo tiene como `<text x=".." y="..">` sueltos, sentados como hermanos directos
dentro del mismo `<g>` de la relacion (junto a un par de `<rect>` invisibles
y un par de `<ellipse>` decorativos en cada punta). El script:

1. Junta todos esos `<text>` sueltos del bloque de la relacion.
2. Descarta los que son solo `+`/`-`/`#`/`~` (marcador de visibilidad UML).
3. Para cada uno, mide la distancia a cada extremo del path (`M x1 y1 L x2
   y2`) y lo asigna al extremo mas cercano.
4. Por cada extremo, une los textos asignados con `" / "`, preservando el
   orden en que aparecen en el SVG.

Esto reproduce exactamente la convencion que ya usan los `.puml` de
`docs/bian-diagrams/puml-bom/` (por ejemplo `"Registered / Party / 0..1"`, donde
"Registered" y "Party" eran dos `<text>` de una etiqueta de rol de dos
lineas, y "0..1" la cardinalidad, las tres mas cerca de ese extremo).

### Atributos y su cardinalidad

Cada `UML_Attribute` trae su texto ya armado como `"Nombre : Tipo"` o
`"Nombre : Tipo[cardinalidad]"` en un unico `<text>` -- a diferencia de una
relacion, aqui no hay que reconstruir nada, solo separar con una regex. En
los Control Record es comun que la cardinalidad este ausente (implica
exactamente 1); cuando el SVG la trae, se preserva igual.

### El estereotipo `«datatype»`/`«enumeration»` ya viene en el SVG

La etiqueta de un `UML_DataType`/`UML_Enumeration` trae, ANTES del nombre,
una linea con el estereotipo literal codificado como entidades HTML:
`&#xab;datatype&#xbb;&#xa;` (`&#xab;`/`&#xbb;` son `«`/`»`, `&#xa;` es un
salto de linea). El script decodifica esas entidades (`html.unescape`) y
luego recorta ese prefijo `«...»` antes de usar el texto como nombre de la
clase -- si no se hiciera esto el nombre saldria literalmente
`"«datatype» InvolvedParty"`. El estereotipo en si no se pierde: se vuelve a
agregar como `<<datatype>>` en la clase (los enums no necesitan esto, la
palabra clave `enum` de PlantUML ya renderiza `«enumeration»` sola).

### El recuadro "BIAN BOM" -> tag `BianBom: yes`

Pediste identificar, en el `.puml`, que clases estaban dentro del recuadro
punteado "BIAN BOM" del SVG (ver la imagen de referencia: un recuadro grande
con «datatype» `InvolvedParty` y varios enums/clases adentro). A diferencia
de una nota BQ (que solo *apunta* a su clase con una linea, sin contenerla),
este recuadro es un `bizzconcept="ViewGraphic" bizzsymbol="rectangle"` con
label exactamente `"BIAN BOM"` que **anida literalmente como hijos del DOM**
a las clases/enums/datatypes que agrupa, dentro de su propio `<g
bizzid="...">...</g>`. La deteccion entonces no es geometrica ni por edge:
es un chequeo de posicion de texto -- se ubica donde abre y donde cierra
(`#object<id>-lvl`) el recuadro "BIAN BOM", y toda forma cuyo tag de apertura
caiga en ese rango de caracteres se marca con:

```plantuml
note right of N<id>
  BianBom: yes
end note
```

Un mismo SVG puede tener mas de un recuadro "BIAN BOM" (el archivo piloto,
`party-reference-data-directory`, tiene dos); el script los procesa todos.
Solo 8 de los 271 SVG traen este recuadro -- para el resto, simplemente no
aparece el tag `BianBom` en ningun lado (no aplica).

### Que se descarta (a proposito)

Un `ViewEdge` generico (no `UML_Association`/`UML_Generalization`) se usa
para dos cosas muy distintas en el SVG, y el script las trata distinto:

- Si un extremo toca una nota BQ/AssetType/ControlRecord/GenericArtifact o
  un recuadro Helper/BOM Diagram -> es una **anotacion** (igual que en v1):
  se convierte en una linea dentro de `note right of ...`, NO en una relacion
  del diagrama.
- Si ambos extremos caen sobre una clase/datatype/enum real -> es una
  **relacion sin cardinalidad** (`N<a> -- N<b>`), tipicamente una referencia
  de tipo (ej. un atributo cuyo tipo es un enum/datatype dibujado aparte).
- Si ninguno de los dos aplica (no calza con ninguna nota/caja conocida ni
  con una clase a menos de 30 unidades) se reporta en `unresolved_edges`, no
  se inventa nada.

Dos edges distintos que resuelven exactamente al mismo `(origen, destino,
etiquetas)` se deduplican al renderizar (pasa cuando una clase tiene mas de
un atributo apuntando al mismo enum/datatype).

## Como ejecutar

```bash
cd generacion_contrato_ia_v2/scripts/svg_to_puml_v2

# Un solo Service Domain, sin escribir nada (para probar)
python svg_to_puml_v2.py --only party-reference-data-directory --dry-run

# Aplicarlo a ese mismo Service Domain
python svg_to_puml_v2.py --only party-reference-data-directory

# Dry-run de todo el corpus (271 SVG) + reporte JSON para revisar antes de escribir
python svg_to_puml_v2.py --dry-run --report reporte.json

# Generar todos los .puml (default: docs/bian-diagrams/puml-control-record/)
python svg_to_puml_v2.py
```

Flags: `--svg-dir`, `--puml-dir`, `--catalog` (default
`docs/bian-view-catalog.json`, de donde saca el nombre "oficial" del Service
Domain y la URL fuente para el comentario de cabecera; si un slug no aparece
ahi cae a un nombre derivado del propio nombre de archivo), `--only`,
`--dry-run`, `--report`.

Por archivo imprime algo como:

```
[OK] party-reference-data-directory: 9 clases, 1 datatypes, 4 enums, 63 atributos, 9 relaciones, 8 en BIAN BOM
```

y, si aplica, listas para revisar a mano (nunca bloquean la corrida):
`edges sin resolver`, `notas sin clase asociada`, `notas con texto no
reconocido`, `recuadros de diagrama sin patron Helper/BOM`, `asociados por
cercania geometrica (revisar)`.

**Idempotente**: correrlo dos veces sobre el mismo archivo produce
exactamente el mismo `.puml` (no hay estado previo que preservar, como en
v1 -- cada corrida reconstruye el archivo entero desde el SVG).

## Resultado de la corrida de referencia (271 SVG)

- 1432 clases, 9 datatypes, 22 enums, 10098 atributos, 920 relaciones.
- 23 elementos marcados `BianBom: yes` (en los 8 SVG que traen ese recuadro).
- 0 edges sin resolver, 0 notas sin clasificar, 0 notas sin clase asociada,
  0 recuadros de diagrama sin reconocer -- corpus completo sin cabos sueltos.
- 13 asociaciones Helper/BOM Diagram resueltas por cercania geometrica (sin
  coincidencia exacta de nombre) -- vale la pena revisarlas a mano si se van
  a usar esas anotaciones puntuales.
- 6 SVG sin ningun elemento (los mismos Service Domain "stub" ya conocidos
  de `scripts/download_svg_control_record`, reconstruidos desde PNG de baja
  resolucion: su Control Record Diagram real es solo un link a la API, sin
  clases) -- el `.puml` generado para esos queda con la cabecera y
  `@enduml`, sin clases, y no es un error.
- Verificado: todos los 271 `.puml` generados tienen `{`/`}` balanceados y
  exactamente un `@startuml`/`@enduml`.
