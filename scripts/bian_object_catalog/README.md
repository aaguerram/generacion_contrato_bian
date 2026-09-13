# bian_object_catalog

Genera [`docs/bian-object-catalog.json`](../../docs/bian-object-catalog.json):
para cada **Service Domain** (348) y cada **clase/enum/data type del BIAN
BOM** (~2300, los mismos nombres que usa `scripts/generate_entities/`), el
link directo a su **pagina de objeto** en bian.org — la pagina con la
documentacion en prosa a la que se llega haciendo click en una clase dentro
de un diagrama, o en un Service Domain desde su listado. Formato de esa
pagina: `https://bian.org/servicelandscape-14-0-0/object_<N>.html?object=<id>`.

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
3. Resuelve contra ese indice:
   - Los 348 Service Domains de `docs/bian-view-catalog.json`.
   - Los nombres distintos de la columna "Business Object" de la hoja "BIAN
     BOM" en `docs/BIANBOM4XMI.xlsx` (mismo universo de nombres que usa
     `scripts/generate_entities/`).
4. Escribe `docs/bian-object-catalog.json`.

Flags: `--cache-dir`, `--force-refresh`, `--view-catalog`, `--xlsx`,
`--output`. No requiere dependencias externas, solo la libreria estandar.

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
    "service_domains": { "total": 348, "resolved": 340, "ambiguous": 2, "unresolved": 6 },
    "bian_bom_classes": { "total": 2320, "resolved": ..., "ambiguous": ..., "unresolved": ... }
  },
  "service_domains": {
    "Customer Product and Service Directory": {
      "object_id": 31128,
      "shard": 14,
      "matched_type": "Capability",
      "url": "https://bian.org/servicelandscape-14-0-0/object_14.html?object=31128"
    }
  },
  "bian_bom_classes": {
    "Product Agreement": {
      "object_id": 31805,
      "shard": 8,
      "matched_type": "Business object",
      "url": "https://bian.org/servicelandscape-14-0-0/object_8.html?object=31805"
    }
  },
  "unresolved": { "service_domains": [...], "bian_bom_classes": [...] }
}
```

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

## Corrida de referencia

```
126911 objetos indexados en 47 shards (data/all_objects_data_<N>.js), 36703 nombres distintos
Service Domains:    {'total': 348,  'resolved': 333,  'ambiguous': 15,  'unresolved': 0}
Clases BIAN BOM:    {'total': 2320, 'resolved': 1842, 'ambiguous': 473, 'unresolved': 5}
```

Los `unresolved` (0 Service Domains, 5 clases) son nombres que no aparecen
con ese texto exacto en ningun shard del sitio.
