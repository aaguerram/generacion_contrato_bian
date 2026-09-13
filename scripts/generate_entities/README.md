# generate_entities

Genera [`docs/entity.json`](../../docs/entity.json): un diccionario **{nombre
de clase/enum BIAN -> ficha}** que responde dos preguntas para cada entidad
del modelo BIAN:

1. **"En que diagramas aparece"** — en que Service Domain(s), si es dentro de
   su diagrama BOM o de su diagrama Control Record (o ambos), con que alias
   interno, y con la ruta local al `.puml`/`.svg` y el link a bian.org de ESE
   diagrama puntual.
2. **"Que es esta entidad"** — su descripcion oficial BIAN, sus propiedades
   (con su propia descripcion y tipo de dato), y — cuando bian.org la
   documenta — la referencia a un estandar externo (tipicamente ISO 20022,
   a veces UK Open Banking) con el link de vuelta a ese estandar.

## Motivacion / caso de uso original

Entrando a la pagina del Control Record de `Party Reference Data Directory`
(https://bian.org/servicelandscape-14-0-0/views/view_48517.html) aparece la
clase `Product Agreement`; haciendo click ahi bian.org lleva a la pagina de
esa clase, con su documentacion. Esa misma clase `Product Agreement` tambien
aparece en el diagrama BOM del Service Domain
`Customer Product and Service Directory`
(https://bian.org/servicelandscape-14-0-0/views/view_32427.html). `entity.json`
responde justamente eso para las ~2700 clases/enums del modelo: donde
aparece cada una y que es, sin tener que ir pagina por pagina en bian.org.

## Las fuentes (3 locales + 1 opcional que si pega contra bian.org)

### 1. Los `.puml` ya extraidos en `docs/bian-diagrams/`

- `puml-bom/*.puml` (272 archivos, uno por Service Domain con diagrama BOM
  publicado) — generados por `scripts/svg_to_puml/`.
- `puml-control-record/*.puml` (271 archivos) — generados por
  `scripts/svg_to_puml_control_record/`.

Cada archivo trae, en comentarios de cabecera, el Service Domain y la URL de
bian.org de la que salio (`' Service Domain: ...` / `' BIAN source: ...` en
BOM, `' Source: ...` en Control Record), y declara cada clase/enum del
diagrama como una caja PlantUML:

```plantuml
class "Product Agreement" as N81615 {
  + Product Agreement Type : ProductAgreementTypeValues
  + Product Agreement Identification : Identifier
}
note right of N81615
  BQ: Product
end note
```

El note opcional trae metadatos propios del recorte SVG (`Extensible`, `BQ`,
`AssetType`, `ControlRecord`, `GenericArtifact`, `HelperDiagram`,
`BOMDiagram`, `BianBom` — ver la leyenda al principio de cualquier `.puml`).
Esto da el "en que diagrama aparece" y "con que atributos se dibujo en ESE
diagrama puntual" (los atributos mostrados pueden variar segun cuales se
"jalaron" al diagrama; el catalogo BIAN BOM de abajo da la lista completa y
canonica).

Solo se cuentan como "aparicion" las clases/enums que estan **dibujados como
caja** en el diagrama (`class "X" as ALIAS { ... }` / `enum "X" as ALIAS {
... }`), no cualquier tipo mencionado de pasada como tipo de un atributo
(si no, "Text", "Date", etc. tendrian cientos de apariciones sin aportar
nada).

### 2. `docs/BIANBOM4XMI.xlsx`, hoja **"BIAN BOM"**

Es el export XMI del modelo BIAN completo (el mismo Enterprise Architect
model del que sale bian.org), con una fila por definicion de clase/enum/data
type/primitive type + una fila por cada uno de sus atributos o valores de
enum. Columnas relevantes: `UML Type`, `Business Object` (el nombre),
`Feature` (nombre del atributo o del enum literal — vacio en la fila de
definicion), `Description`, `Data Type`, y — cuando existe — `Reference
Type` / `Referenced Aspect` / `Reference Name` / `URL Reference`, que es
exactamente la seccion "4. Reference to External Aspect" que se ve en la
pagina de una clase en bian.org (p.ej. para `Agreement`: `Standard` /
`ISO20022 BM` / `Agreement` /
`https://www.iso20022.org/standardsrepository/type/Agreement`).

Se lee con un parser `.xlsx` minimo hecho a mano (`zipfile` +
`xml.etree.ElementTree`, sin `openpyxl`/`pandas`: el repo no trae esas
dependencias y no hace falta agregarlas solo para leer 1 hoja — un `.xlsx`
es un zip de XML, y alcanza con `sharedStrings.xml` + la hoja).

Esto da la ficha **canonica** de cada clase (no depende de que se haya
dibujado o no en tal o cual diagrama puntual).

`docs/BIANv14.xlsm` (el otro Excel en `docs/`) es un workbook distinto — 
catalogo de Service Domains / Business Areas / escenarios end-to-end /
glosario de negocio — **no se usa aca** porque no trae el modelo de clases
BOM; si en el futuro hace falta enriquecer alguna ficha con texto del
glosario de negocio, su hoja `Business Glossary` seria el punto de partida.

### 3. `docs/bian-view-catalog.json`

Generado por `scripts/bian_view_catalog/`. Da, por Service Domain, el link
"SD Overview" (el `.puml` ya trae el link de BOM o de Control Record segun
corresponda, pero no el de "SD Overview"). Se usa solo para completar ese
link extra en cada aparicion.

### 4. (Opcional) `docs/bian-object-catalog.json`

Generado por `scripts/bian_object_catalog/` — a diferencia de las 3 fuentes
de arriba, ESE script si pega contra bian.org (descarga ~142 MB la primera
vez, cacheados despues). Da, por nombre, el link a la **pagina de objeto**
de bian.org (`object_<N>.html?object=<id>`, la que trae la documentacion en
prosa de una clase o de un Service Domain — distinta de las paginas de
diagrama de arriba). Si el archivo existe, `generate_entities.py` agrega:

- `bian_bom.object_url` en cada entidad — link **estable** a la pagina de
  esa clase (a diferencia del `alias` de cada `occurrences[]`, que varia por
  diagrama: ver el README de `bian_object_catalog` para el detalle de por
  que ese alias no sirve como id estable).
- `sd_object_url` en cada aparicion, con el link de objeto del Service
  Domain de esa aparicion.

Si el archivo no existe (todavia no se corrio `bian_object_catalog`, o se
corrio sin red), `generate_entities.py` sigue funcionando igual: esos 2
campos quedan en `null`.

## Como ejecutar

Desde cualquier ubicacion (los defaults resuelven siempre contra la raiz de
`generacion_contrato_ia_v2`, sin importar el directorio actual):

```bash
cd generacion_contrato_ia_v2/scripts/generate_entities
python generate_entities.py
```

Esto lee `docs/BIANBOM4XMI.xlsx` + `docs/bian-diagrams/puml-{bom,control-record}/*.puml`
+ `docs/bian-view-catalog.json` (+ `docs/bian-object-catalog.json` si existe),
y escribe `docs/entity.json`. Flags para apuntar a otras rutas (util para
probar con un subconjunto o una copia): `--xlsx`, `--view-catalog`,
`--object-catalog`, `--bom-puml-dir`, `--cr-puml-dir`, `--bom-svg-dir`,
`--cr-svg-dir`, `--output`.

No requiere red ni dependencias externas — solo la libreria estandar de
Python 3. (La unica fuente que si requiere red es la opcional
`bian-object-catalog.json`, y esa se genera con un script aparte —
`scripts/bian_object_catalog/` — no corriendo este.)

## Formato de `entity.json`

```jsonc
{
  "release": "14.0.0",
  "sources": { "puml_bom_dir": "...", "bian_bom_xlsx": "...", ... },
  "stats": { "total_entities": 2668, "total_occurrences": 5734, ... },
  "entities": {
    "Product Agreement": {
      "name": "Product Agreement",
      "bian_bom": {
        "kind": "Class",
        "description": "An agreement with the subject matter of the product between Customer and Provider. ...",
        "reference": null,
        "object_url": "https://bian.org/servicelandscape-14-0-0/object_8.html?object=31805",
        "properties": [
          { "name": "Product Agreement Type", "description": null, "data_type": "ProductAgreementTypeValues", "reference": null },
          { "name": "Product Agreement Identification", "description": "A unique reference to product agreement or instance of product", "data_type": "Identifier", "reference": null }
        ],
        "enum_values": []
      },
      "occurrences": [
        {
          "service_domain": "Customer Product and Service Directory",
          "diagram_type": "bom",
          "diagram_title": "Customer Product and Service Directory - BIAN BOM UML",
          "puml_path": "docs/bian-diagrams/puml-bom/customer-product-and-service-directory.puml",
          "svg_path": "docs/bian-diagrams/svg_bom/customer-product-and-service-directory.svg",
          "bian_source_url": "https://bian.org/servicelandscape-14-0-0/views/view_32427.html",
          "sd_overview_url": "https://bian.org/servicelandscape-14-0-0/views/view_54543.html",
          "sd_object_url": "https://bian.org/servicelandscape-14-0-0/object_14.html?object=31128",
          "alias": "N81615",
          "kind": "class",
          "stereotype": null,
          "notes": { "BQ": "Product" },
          "attributes": [
            { "name": "Product Agreement Type", "type": "ProductAgreementTypeValues" },
            { "name": "Product Agreement Identification", "type": "Identifier" }
          ],
          "enum_values": []
        },
        { "service_domain": "Party Reference Data Directory", "diagram_type": "control_record", "notes": { "BianBom": "yes" }, "...": "..." }
      ]
    }
  }
}
```

`bian_bom` es `null` cuando el nombre no matchea ninguna definicion de la
hoja "BIAN BOM" del xlsx — pasa con las clases sintacticas propias de un
Control Record puntual (p.ej. `CR Party Reference Data Directory Entry
Instance Record`, `BQ Associations Instance Record`: son records compuestos
que arma ESE Control Record, no clases reusables del BOM).

`reference` (a nivel de clase o de propiedad) trae el estandar externo
cuando existe:

```json
{ "type": "Standard", "referenced_aspect": "ISO20022 BM", "reference_name": "Agreement", "url": "https://www.iso20022.org/standardsrepository/type/Agreement" }
```

## Decisiones de diseno / limitaciones conocidas

- **Se matchea por nombre, no por UID.** Los `.puml` usan el nombre humano
  BIAN ("Product Agreement") y el xlsx tambien (columna `Business Object`),
  asi que cruzarlos por nombre es directo y evita tener que resolver UIDs
  del modelo EA. Efecto secundario: 3 nombres (`Duty`, `Object`, `Token`)
  estan definidos dos veces en el xlsx con `kind` distinto (`Class` +
  `Data type`/`Primitive type`); la ficha se queda con el primer `kind` que
  aparece al recorrer la hoja. No afecta el resto (~2317 nombres).
- **~123 clases duplicadas en el xlsx.** El export XMI trae unas 123
  clases con su fila de definicion repetida dos veces (mismo nombre, UID
  distinto). Como se agrupa por nombre y se dedupea por nombre de
  atributo/enum-literal, esto no genera propiedades duplicadas en la ficha
  final.
- **Los atributos por aparicion vienen del `.puml`, no del xlsx.** Una
  misma clase puede mostrarse con distintos atributos "jalados" segun el
  diagrama (eso es lo que las notas `Extensible: yes/no` documentan). Si se
  necesita SIEMPRE la lista completa y canonica de atributos, usar
  `bian_bom.properties`, no `occurrences[].attributes`.
- **El `alias` de cada aparicion NO es un id estable.** Es un id posicional
  del SVG de ESE diagrama puntual (se comprobo: la misma clase "Party"
  aparece con 132 alias distintos en sus 132 apariciones). Para un link
  permanente a la pagina de esa clase en bian.org usar `bian_bom.object_url`
  (ver fuente 4 arriba), no armar una URL con el `alias`.
- **No hace llamadas de red por si solo.** Todo sale de
  `docs/BIANBOM4XMI.xlsx`, `docs/bian-diagrams/` y
  `docs/bian-view-catalog.json`, ya versionados en el repo. Si se quiere
  refrescar el catalogo de vistas o los `.puml`, correr antes
  `scripts/bian_view_catalog/` / `scripts/svg_to_puml*/` (ver sus propios
  README); si se quiere completar `object_url`/`sd_object_url`, correr
  `scripts/bian_object_catalog/` (esa si pega contra bian.org).
- **Tamano del resultado.** ~2700 entidades, ~5700 apariciones en total,
  `entity.json` resulta en unos 8 MB (no se trunca ni se resume nada:
  se prioriza tener la ficha completa por entidad).

## Corrida de referencia

```
2320 clases/enums/data types con ficha BIAN BOM (hoja "BIAN BOM" del xlsx)
348 Service Domains con links a bian.org (bian-view-catalog.json)
348 Service Domains y 2315 clases BIAN BOM con link de objeto en bian.org (bian-object-catalog.json, opcional)
2668 entidades distintas, 5734 apariciones en total
  1566 con ficha BIAN BOM (descripcion + propiedades), 1564 de ellas con object_url
  1542 solo en diagramas BOM, 1009 solo en Control Record, 117 en ambos
```
