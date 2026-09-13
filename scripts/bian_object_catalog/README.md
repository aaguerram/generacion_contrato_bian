# bian_object_catalog

Genera [`docs/bian-object-catalog.json`](../../docs/bian-object-catalog.json):
para cada **Service Domain** (348), cada **clase/enum/data type del BIAN
BOM** (~2300, los mismos nombres que usa `scripts/generate_entities/`), cada
**Business Area** (5) y cada **Business Domain** (38, las de
`scripts/generate_matrix_view/`), el link directo a su **pagina de objeto**
en bian.org — la pagina con la documentacion en prosa a la que se llega
haciendo click en una clase dentro de un diagrama, en un Service Domain
desde su listado, o en una Business Area/Domain desde el Matrix View — **mas
esa documentacion ya extraida como texto plano** (sin las etiquetas HTML/RTF
sueltas que trae el dato crudo del sitio). Formato de esa pagina:
`https://bian.org/servicelandscape-14-0-0/object_<N>.html?object=<id>`.

## El problema: `<N>` no es un "tipo", es un shard

La primera hipotesis razonable, mirando 2 ejemplos sueltos
(`object_14.html?object=31128` = Customer Product and Service Directory,
`object_8.html?object=31805` = Product Agreement), es que `<N>` fuera un
codigo de tipo fijo (14 = Service Domain, 8 = Clase, etc.) y que alcanzara
con "adivinarlo". **Es falso.** Verificado navegando bian.org en vivo:

- El sitio (motor "InSite" de BiZZdesign) parte su base de **~127.000
  objetos** en **47 archivos** `data/all_objects_data_<N>.js` (N de 1 a 47,
  ~1-16 MB cada uno, ~142 MB en total). `<N>` es simplemente en cual de esos
  47 archivos vive ese objeto — un shard de almacenamiento, no una
  clasificacion semantica.
- `data/all_objects_data_mapping.js` trae `{object_id: N}` para saber, dado
  un id, en que shard buscarlo — pero **no** trae el nombre, asi que no sirve
  para ir de "nombre" a "id" directamente.
- Un mismo shard mezcla objetos de todo tipo: el shard 14 tiene 3495
  objetos, de los cuales **solo 243 de los 348 Service Domains conocidos
  estan ahi** — el resto de los Service Domains (y las clases del BOM) estan
  repartidos en otros shards, sin ningun patron por nombre o por tipo que
  permita predecir cual.

**Conclusion:** la unica forma confiable de resolver "nombre -> URL" es
descargar los 47 shards completos, indexar `{nombre -> [candidatos]}` con
TODOS los objetos del sitio, y recien ahi buscar los nombres que interesan
(Service Domains + clases BIAN BOM). Eso es lo que hace este script.

## Como ejecutar

```bash
cd generacion_contrato_ia_v2/scripts/bian_object_catalog
python bian_object_catalog.py
```

Esto:

1. Descarga `data/all_objects_data_mapping.js` + los 47
   `data/all_objects_data_<N>.js` (~142 MB la primera vez) y los cachea en
   [`descarga/bian-object-catalog-shards/`](../../descarga/bian-object-catalog-shards/)
   en la raiz de `generacion_contrato_ia_v2` (ignorada por git via la regla
   `/descarga/` del `.gitignore` del repo: son datos crudos externos, no
   codigo ni un artefacto versionable — si la carpeta no existe se vuelve a
   descargar sola). Corridas siguientes reusan la cache sin volver a pegarle
   a bian.org — usar `--force-refresh` para forzar una descarga nueva si
   bian.org publica una actualizacion, o `--cache-dir` para usar otra ruta.
2. Arma el indice combinado `{nombre -> [{object_id, shard, type}, ...]}`
   con los ~127.000 objetos.
3. Resuelve contra ese indice, y para el ganador de cada nombre extrae ademas
   su documentacion (categoria `"documentation"` del objeto, HTML/RTF
   limpiado a texto plano):
   - Los 348 Service Domains de `docs/bian-view-catalog.json`.
   - Los nombres distintos de la columna "Business Object" de la hoja "BIAN
     BOM" en `docs/BIANBOM4XMI.xlsx` (mismo universo de nombres que usa
     `scripts/generate_entities/`).
   - Las Business Area reales (`is_unclassified: false`) y todos los Business
     Domain (de primer nivel y anidados) de
     `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` (si ese archivo no
     existe todavia, se omiten estas 2 categorias — correr
     `scripts/generate_matrix_view/` primero).
4. Escribe `docs/bian-object-catalog.json`.

Flags: `--cache-dir`, `--force-refresh`, `--view-catalog`, `--xlsx`,
`--matrix-view`, `--output`. No requiere dependencias externas, solo la
libreria estandar.

**Costo:** la primera corrida baja ~142 MB y tarda unos minutos (dominado
por la red, no por CPU). Corridas siguientes son casi instantaneas gracias a
la cache. No hace falta volver a correrlo salvo que BIAN publique una nueva
release del sitio o que `docs/bian-view-catalog.json` / `BIANBOM4XMI.xlsx`
cambien con nombres nuevos que valga la pena resolver.

## Desambiguacion

Un nombre matchea **muchos** objetos en el indice — no es un caso raro.
Motivo principal (verificado): cada vez que una clase se dibuja dentro de un
diagrama, bian.org le da su propio objeto de tipo `"Class"` (el equivalente
exacto al alias posicional que ya vimos en los `.puml` locales: el
candidato `Class`/`81615` de "Product Agreement" es LITERALMENTE el mismo id
que el alias `N81615` que `svg_to_puml` extrajo del SVG para esa clase en el
diagrama de Customer Product and Service Directory). Con ~2300 clases
dibujadas en cientos de diagramas, la enorme mayoria de nombres termina con
varios candidatos `"Class"` (uno por diagrama donde aparece) + 1 candidato
con un tipo mas especifico que SI es la definicion canonica.

Por eso la desambiguacion prueba una lista de tipos **en orden de
prioridad** y se queda con el primero que matchee **exactamente 1**
candidato (los `"Class"` sueltos no cuentan salvo que sea el unico tipo
presente):

- Service Domains: `("Capability",)` — asi tipifica bian.org un Service
  Domain. Resultado: 333/348 (96%) resueltos sin ambiguedad.
- Clases BIAN BOM: `("Business object", "Enumeration", "Data type",
  "Primitive type")` — en ese orden. Resultado: 1842/2320 (79%) resueltos.
- Business Areas: `("Grouping",)` — asi tipifica bian.org una Business Area
  (confirmado con "Reference Data": `stereotype: BusinessArea`). Resultado:
  5/5 (100%) resueltos sin ambiguedad.
- Business Domains: `("Capability",)` — mismo `type` que un Service Domain,
  pero con `stereotype: BusinessDomain` (confirmado con "Party": object_id
  216846). Resultado: 36/38 (95%) resueltos sin ambiguedad (ambiguos:
  "Customer Management", "Product Management" — nombres genericos que
  tambien existen como otro tipo de objeto en el sitio).

Cuando ni con la prioridad alcanza a bajar a 1 candidato (pasa cuando el
mismo nombre tiene 2+ definiciones canonicas genuinas — se comprobo: p.ej.
"Product Agreement" tiene 2 objetos `"Business object"` distintos, ids
31805 y 58014, probablemente definido en mas de un Service Domain de forma
independiente en el modelo), se deja el primer candidato como mejor
estimacion pero se marca con `ambiguous_candidates` (la lista completa de
candidatos vistos) para poder revisar a mano o resolverlo con una senal
adicional en el futuro (p.ej. cruzando contenido de documentacion contra la
descripcion ya conocida por `BIANBOM4XMI.xlsx`).

## Formato de `bian-object-catalog.json`

```jsonc
{
  "source": { "mapping_url": "...", "shard_url_template": "...", "object_url_template": "..." },
  "stats": {
    "service_domains": { "total": 348, "resolved": 333, "ambiguous": 15, "unresolved": 0 },
    "bian_bom_classes": { "total": 2320, "resolved": 1842, "ambiguous": 473, "unresolved": 5 },
    "business_areas": { "total": 5, "resolved": 5, "ambiguous": 0, "unresolved": 0 },
    "business_domains": { "total": 38, "resolved": 36, "ambiguous": 2, "unresolved": 0 }
  },
  "service_domains": {
    "Card Authorization": {
      "object_id": 41757,
      "shard": 14,
      "matched_type": "Capability",
      "url": "https://bian.org/servicelandscape-14-0-0/object_14.html?object=41757",
      "documentation": null,
      "documentation_sections": {
        "role_definition": "The proposed card transaction is requested by a merchant and routed through the Acquirer and Card Network to the Issuer. ...",
        "example_of_use": "A credit card customer makes a large purchase, the card authorization triggers a verbal check of the customer details for security and the authorization is given",
        "executive_summary": "This service domain is responsible for the real time card authorization decisions for credit/charge cards.",
        "key_features": "Card device verification checks\nCard member identity verification\nCredit checks\nFraud detection checks",
        "documentation": null
      }
    }
  },
  "bian_bom_classes": {
    "Product Agreement": {
      "object_id": 31805,
      "shard": 31,
      "matched_type": "Business object",
      "url": "https://bian.org/servicelandscape-14-0-0/object_31.html?object=31805",
      "documentation": "..."
    }
  },
  "business_areas": {
    "Reference Data": {
      "object_id": 216783,
      "shard": 17,
      "matched_type": "Grouping",
      "url": "https://bian.org/servicelandscape-14-0-0/object_17.html?object=216783",
      "documentation": "The Business Area Reference Data contains all categories of managed business reference information, covering subjects including customer details, business partner details and product details. In the case of products it includes aspects of product design, development and quality assurance. It also covers market data feeds for general research and analysis and the range of more specialized trading support market information feeds. This reference information is widely accessed across other activities of the landscape."
    }
  },
  "business_domains": {
    "Party": {
      "object_id": 216846,
      "shard": 17,
      "matched_type": "Capability",
      "url": "https://bian.org/servicelandscape-14-0-0/object_17.html?object=216846",
      "documentation": "This Business Domain covers the different party/customer reference information that is maintained by the bank for its institutional, corporate and consumer customers."
    }
  },
  "unresolved": { "service_domains": [...], "bian_bom_classes": [...], "business_areas": [...], "business_domains": [...] }
}
```

Cada entrada trae ademas `documentation_sections` (no mostrado arriba por
brevedad): `{slug -> texto}` con **todas** las categorias `type:
"documentation"` del objeto, HTML/RTF limpiado a texto plano (etiquetas de
bloque `<p>`/`<br>`/`<div>` -> salto de linea, el resto -> espacio,
`html.unescape` para entidades como `&nbsp;`).

**Bug encontrado y corregido:** un objeto de Service Domain en bian.org NO
trae 1 sola categoria de documentacion — trae varias, numeradas ("1. Role
Definition", "2. Example of Use", "3. Executive Summary", "4. Key
Features"), MAS una generica titulada literalmente `"documentation"` que en
muchos casos viene **vacia** en el propio dato del sitio (verificado con
"Card Authorization", object_id 41757: bian.org le muestra esa seccion
vacia). Una version anterior de este script tomaba la PRIMERA categoria de
documentacion que encontraba — para un Service Domain, eso terminaba siendo
"1. Role Definition" en vez de la seccion realmente titulada
"documentation", asi que el campo `documentation` mostraba texto (el de Role
Definition) donde la pagina real muestra vacio. Ahora `documentation`
siempre sale especificamente de la seccion titulada `"documentation"` (por
eso queda `null` para muchos Service Domains — es correcto, coincide con lo
que muestra bian.org), y las otras secciones quedan disponibles, cada una
con su propio slug, en `documentation_sections`.

`scripts/generate_matrix_view/` es quien consume `documentation_sections`
para agregarlas como atributos propios de cada Service Domain
(`role_definition`, `example_of_use`, `executive_summary`, `key_features`,
`documentation`) dentro de `BIAN_Service_Landscape_V14.0_Matrix_View.json` —
ver su README.

Un nombre en `unresolved` significa que no aparece con ese texto exacto en
ningun shard (puede ser una variante de mayusculas/minusculas, un nombre
retirado en una revision del sitio, o un Service Domain que en 14.0.0 no
llego a tener su propia pagina de objeto — igual que pasa con
`bom_diagram_url`/`control_record_diagram_url` en `bian-view-catalog.json`).

## Integracion con `scripts/generate_entities/`

`generate_entities.py` acepta `--object-catalog` (default
`docs/bian-object-catalog.json`) y, si el archivo existe, agrega:

- `bian_bom.object_url` en cada entidad (el link canonico y estable a la
  pagina de esa clase en bian.org — a diferencia del alias `N<numero>` que
  trae cada `occurrences[]`, que **no** es estable: la misma clase tiene un
  alias distinto en cada diagrama donde aparece, porque ese alias sale de un
  ID posicional del SVG, no del ID publico del objeto).
- `sd_object_url` en cada aparicion (`occurrences[]`), con el link de
  objeto del Service Domain de esa aparicion.

Es opcional: si `bian-object-catalog.json` no existe (todavia no se corrio
este script, o se corrio sin red), `generate_entities.py` sigue funcionando
igual, solo que esos 2 campos quedan en `null`.

## Integracion con `scripts/generate_matrix_view/`

`generate_matrix_view.py` acepta `--object-catalog` (default
`docs/bian-object-catalog.json`) y, si el archivo existe, agrega a cada
Business Area REAL (nunca al bucket sentinela `is_unclassified: true`), a
cada Business Domain y a cada Service Domain su `object_url` y su
`documentation` (el mismo texto que se ve en la seccion "Documentation" de
la pagina de ese elemento en bian.org).

**Orden de corrida** (hay una dependencia circular aparente para Business
Areas/Domains, se resuelve corriendo cada script 2 veces; los Service
Domains no la tienen, salen completos desde el primer paso porque este
script los resuelve contra `bian-view-catalog.json`, no contra el arbol):
`generate_matrix_view.py` necesita existir primero (aunque sea sin
`object_url`/`documentation` en Areas/Domains) para que este script sepa que
nombres de Business Area/Domain resolver; y este script necesita correr
para que `generate_matrix_view.py` los pueda inyectar:

```bash
cd generacion_contrato_ia_v2/scripts
python generate_matrix_view/generate_matrix_view.py   # 1. arma el arbol (Service Domains ya completos)
python bian_object_catalog/bian_object_catalog.py      # 2. resuelve Service Domains + clases + Business Areas/Domains
python generate_matrix_view/generate_matrix_view.py   # 3. re-arma el arbol, ahora TODO con object_url/documentation
```

Es opcional: si `BIAN_Service_Landscape_V14.0_Matrix_View.json` no existe
todavia cuando corre este script, simplemente se omiten las categorias
`business_areas`/`business_domains` (0 resueltos) sin fallar.

## Corrida de referencia

```
126911 objetos indexados en 47 shards (data/all_objects_data_<N>.js), 36703 nombres distintos
Service Domains:    {'total': 348,  'resolved': 333,  'ambiguous': 15,  'unresolved': 0}
Clases BIAN BOM:    {'total': 2320, 'resolved': 1842, 'ambiguous': 473, 'unresolved': 5}
Business Areas:     {'total': 5,    'resolved': 5,    'ambiguous': 0,   'unresolved': 0}
Business Domains:   {'total': 38,   'resolved': 36,   'ambiguous': 2,   'unresolved': 0}
```

Los `unresolved` (0 Service Domains, 5 clases, 0 Business Areas, 0 Business
Domains) son nombres que no aparecen con ese texto exacto en ningun shard
del sitio.
