# svg_to_puml

Enriquece los `.puml` de `docs/bian-puml/` con la informacion que en el `.svg`
fuente (`docs/bian-diagrams/svg_bom/`) esta representada visualmente pero la
extraccion original a `.puml` no capturo como texto: notas turquesa/gris
"pegadas" a una clase (**BQ** / Behavior Qualifier, **AssetType**,
**ControlRecord**, **GenericArtifact**, y las cajas de referencia
**"\<Clase\> Helper Diagram"** / **"\<Clase\> BOM Diagram"**), y tambien el
**color del borde de la clase**, que en BIAN codifica si esa clase se puede
extender o no (ver seccion "Extensible" mas abajo).

## Por que existe

Los `.puml` en `docs/bian-puml/` son una extraccion semantica de los `.svg`
BIAN (mismo `bizzid` numerico como alias de clase, p.ej. `N199916`), pero esa
extraccion original solo curo clases, atributos, enums y relaciones — dejo
fuera las notas satelite que en el `.svg` cuelgan de cada clase mediante una
linea conectora. Este script cierra esa brecha sin tocar nada mas del `.puml`
(ni atributos, ni relaciones, ni enums): solo agrega un bloque
`note right of N<id> ... end note` por clase, con una linea por cada dato
encontrado.

## Que hace, paso a paso

1. Parsea el `.svg` (formato Bizzdesign: cada nodo/edge tiene un `bizzid`
   numerico y termina con un `<use xlink:href="#object<id>-lvl">`):
   - **Clases** (`bizzconcept="UML_Class"`): id, nombre, bounding box.
   - **Notas turquesa/amarillas** (`bizzsymbol="dogear"`): id, texto completo
     (uniendo las multiples lineas `<text>` que a veces trae una sola nota,
     p.ej. `"ControlRecord: "` + `"Party Reference Data Directory Entry"`),
     bounding box.
   - **Cajas de diagrama** (`bizzconcept="UML_ClassDiagram"`): las cajas
     grises tipo `"Person Helper Diagram"` o `"Party Lifecycle Management BOM
     Diagram"`.
   - **Edges** (`bizzconcept="ViewEdge"`): la linea conectora entre una nota
     y su clase, como un segmento con dos puntos.
   - **Estilos de clase**: el bloque `<style>` del `.svg` trae una regla CSS
     `.object<id> {fill:...;stroke:...}` por cada nodo — de ahi se lee el
     color de fondo/borde de cada clase (ver seccion "Extensible").

### Extensible (color del borde de la clase)

En el `.svg` BIAN, la caja de una clase puede venir en 3 estilos (confirmado
identico en varios Service Domains — party-reference-data-directory,
transaction-authorization, session-dialogue, card-clearing,
letter-of-credit):

| Estilo visual | `fill` / `stroke` | Significado | Tag inyectado |
|---|---|---|---|
| Solo borde rojo, relleno gris claro | `#eae8e8` / `#c47474` | Esta clase pertenece a otro Service Domain, pero **se permite** traer sus atributos a este diagrama si se necesitan | `Extensible: yes` |
| Todo rojo (relleno y borde) | `#ff8080` / `#d91616` | Igual que el anterior, pero **no esta permitido** extenderla — se referencia tal cual, sin traer sus atributos | `Extensible: no` |
| Relleno blanco, borde gris | `#ffffff` / `#d9d9d9` | Clase normal, plenamente modelada en este diagrama (el caso por defecto) | *(sin tag: la distincion no aplica)* |

El script lee el `fill`/`stroke` de la regla `.object<id>` que corresponde al
`bizzid` de cada clase y clasifica segun la tabla de arriba. Solo se inyecta
el tag `Extensible` para los dos primeros casos — las clases "normales" (el
tercer caso, la gran mayoria) no llevan esta linea porque no aplica.

2. Asocia cada nota a su clase:
   - Clasifica el texto de la nota por prefijo: `BQ`, `AssetType:`,
     `ControlRecord:`, `GenericArtifact:`. Lo que no matchea ninguno se
     reporta como `unclassified_notes` (no se inventa una categoria).
   - Para encontrar la clase dueña, busca el edge cuyo extremo toca el
     bounding box de la nota, toma el otro extremo del edge y busca la clase
     mas cercana a ese punto. Una nota puede asociarse a mas de una clase si
     tiene mas de un edge saliendo de ella (p.ej. una unica nota "BQ
     Reference" que alimenta tanto a `Person` como a `Organisation`).
   - Si ninguna clase queda a menos de 30 unidades del extremo del edge, la
     nota se reporta como `unmatched_notes` en vez de asociarla a una clase
     lejana/incorrecta.

3. Asocia cada caja de diagrama a su clase:
   - Si el texto termina en `" Helper Diagram"` o `" BOM Diagram"`, quita el
     sufijo y busca una clase cuyo nombre coincida exactamente (insensible a
     mayusculas) — asi es como casi todas las cajas "Helper Diagram" se
     resuelven, porque nombran a la clase local que describen.
   - Si no hay clase local con ese nombre (caso tipico de `"BOM Diagram"`,
     que en vez de nombrar una clase local nombra **otro Service Domain**,
     p.ej. `"Party Lifecycle Management BOM Diagram"` sobre la clase `Party
     Relationship`), cae a la clase geometricamente mas cercana y lo marca en
     `proximity_matches` para que se pueda revisar a mano.
   - Texto que no termina en ninguno de esos dos sufijos (p.ej. una caja que
     solo dice `"Customer Relationship"`) se reporta en
     `unclassified_diagram_boxes` y no se inyecta nada.

4. Inyecta en el `.puml`, para cada clase con datos encontrados, un bloque:

   ```plantuml
   class "Person" as N199916 {
     + Person Identification : PersonIdentification[1..*]
     ...
   }
   note right of N199916
     BQ: Demographics
     BQ: Reference
     HelperDiagram: Person Helper Diagram
   end note
   ```

   Las lineas se ordenan siempre `Extensible, BQ, AssetType, ControlRecord,
   GenericArtifact, HelperDiagram, BOMDiagram` (y alfabeticamente dentro de
   cada categoria) para que la salida sea determinista entre corridas.

5. Si el `.puml` no trae aun la leyenda de cabecera que explica estas
   etiquetas, la agrega debajo de la linea `hide methods`. Si ya esta, no la
   duplica.

**Idempotente**: correrlo dos veces seguidas sobre el mismo par no cambia
nada en la segunda corrida (detecta y reemplaza el bloque `note right of
N<id> ... end note` que el mismo script dejo antes, en vez de duplicarlo).
Las relaciones, enums y atributos originales del `.puml` nunca se tocan.

## Alcance real del corpus

Esto aplica a los pares donde existen **ambos** archivos con el mismo nombre
base en `docs/bian-diagrams/svg_bom/<nombre>.svg` y `docs/bian-puml/<nombre>.puml`
(hoy son 272 pares). Un numero de esos `.svg` son placeholders vacios (un
canvas de 1x1 cm sin contenido, cuando el diagrama original solo existia como
PNG de baja resolucion) — el script los detecta como "0 clases" y no toca su
`.puml`, no es un error.

Esto **no** incluye los ~700 `.puml` de `architecture/BIAN_PUML/`: esa es una
carpeta distinta, sin `.svg` fuente, que pertenece al framework principal de
generacion de contratos y queda fuera del alcance de este script.

## Como ejecutar

Desde cualquier ubicacion (usa rutas por defecto relativas al repo:
`docs/bian-diagrams/svg_bom` y `docs/bian-puml`):

```bash
cd generacion_contrato_ia_v2/scripts/svg_to_puml

# 1) Probar un solo Service Domain sin escribir nada (recomendado primero)
python svg_to_puml.py --only party-reference-data-directory --dry-run

# 2) Aplicar los cambios a ese mismo Service Domain
python svg_to_puml.py --only party-reference-data-directory

# 3) Dry-run de TODO el corpus (272 pares) + reporte JSON para revisar antes
#    de aplicar nada de forma masiva
python svg_to_puml.py --dry-run --report reporte.json

# 4) Aplicar a todo el corpus una vez revisado el reporte
python svg_to_puml.py
```

Flags:

| Flag | Para que sirve |
|---|---|
| `--svg-dir` / `--puml-dir` | Cambiar las carpetas por defecto |
| `--only <nombre-base>` | Procesar un unico par (nombre de archivo sin extension) |
| `--dry-run` | Calcula y muestra el resultado pero no escribe ningun `.puml` |
| `--report <archivo.json>` | Vuelca un resumen por archivo (clases, anotadas, tags, y las listas `unmatched_notes` / `unclassified_notes` / `unclassified_diagram_boxes` / `proximity_matches` para revision manual) |

Por cada archivo procesado imprime en consola algo como:

```
[OK] party-reference-data-directory.svg: 18 clases, 16 anotadas, 29 tags
```

y, si aplica, listas de cosas para revisar a mano:

```
    notas sin clase asociada: [...]
    notas con texto no reconocido (BQ/AssetType/ControlRecord/GenericArtifact): [...]
    recuadros de diagrama sin patron Helper/BOM: [...]
    asociados por cercania geometrica (revisar): [...]
```

Ninguna de esas listas bloquea la corrida: el script nunca inventa una
asociacion cuando no esta razonablemente seguro, simplemente no anota esa
nota/caja y la deja reportada para que alguien la revise.

## Recomendacion antes de correrlo sobre todo el corpus

Al correr el corpus completo en dry-run (272 pares) se observo, a modo de
referencia:

- 3560 clases totales, 2493 anotadas con al menos un tag (4138 lineas de tag
  en total; el salto frente a la extraccion sin color se debe sobre todo al
  tag `Extensible`, que aparece en una parte importante del corpus).
- 16 `.svg` vacios (placeholders de diagramas que solo existian como PNG).
- ~420 notas con texto que no calza con ningun prefijo conocido y ~97 notas
  sin clase geometricamente cercana — ambas se reportan, no se descartan en
  silencio.
- ~677 asociaciones de "Helper/BOM Diagram" resueltas por cercania geometrica
  en vez de por coincidencia exacta de nombre (mayormente los `"BOM Diagram"`
  que apuntan a otro Service Domain) — vale la pena revisar una muestra antes
  de confiar en el corpus completo.

Por eso el flujo recomendado es siempre `--dry-run --report reporte.json`
primero, revisar ese JSON (o al menos las listas que imprime por consola), y
recien despues correr sin `--dry-run`.
