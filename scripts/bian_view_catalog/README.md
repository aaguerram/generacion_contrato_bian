# bian_view_catalog

Genera un JSON con, para cada BIAN Service Domain, los 3 links a bian.org que
pediste: la pagina "SD Overview", el "BOM Diagram" y el "Control Record
Diagram".

## Como se encontro esto

Cada Service Domain en `https://bian.org/servicelandscape-14-0-0/views/` tiene
(hasta) 3 paginas distintas, con `view_id` internos **sin ninguna relacion
numerica entre si** (no son consecutivos ni derivables unos de otros):

| Pagina | Ejemplo (Correspondence) |
|---|---|
| SD Overview (lista y enlaza a las otras dos) | `view_54378.html` |
| BOM Diagram | `view_38944.html` |
| Control Record Diagram | `view_47457.html` |

La pagina "SD Overview" SI trae, en su HTML, texto de los 3 enlaces
("Correspondence BOM Diagram", "Correspondence Control Record Diagram"), pero
el sitio esta armado con Backbone/Marionette + Handlebars: el HTML es una
plantilla vacia y el contenido real (incluidos los `href`) se inyecta en
tiempo de ejecucion desde archivos `data/view_<id>_data.js` — por eso un fetch
"de texto" (o WebFetch) del HTML crudo no muestra los links, solo su texto.

En vez de rastrear pagina por pagina (habria que resolver 1 archivo `_data.js`
por cada una de las ~350 paginas "SD Overview"), el sitio publica un archivo
**global** que ya trae el catalogo completo de vistas:

```
https://bian.org/servicelandscape-14-0-0/data/all_objects_on_views.js
```

Este archivo declara dos variables JS seguidas; la segunda,
`var insiteViews = {...}`, es un diccionario `view_id -> {id, name}` con
**2285 vistas** de todo el sitio (no solo Service Domains — tambien incluye
diagramas de casos de uso, modelos internos de BIAN, etc.). Filtrando por el
sufijo del `name` se separan los 3 tipos que nos interesan:

- `"<Nombre> SD Overview"` -> 350 vistas
- `"<Nombre> BOM Diagram"` -> 285 vistas
- `"<Nombre> Control Record Diagram"` -> 272 vistas

El script cruza estas 3 listas por el nombre del Service Domain (el texto
antes del sufijo) y arma un solo JSON.

## Como ejecutar

Desde cualquier ubicacion (el default de `--output` resuelve siempre a
`docs/bian-view-catalog.json` en la raiz de `generacion_contrato_ia_v2`,
sin importar el directorio actual):

```bash
cd generacion_contrato_ia_v2/scripts/bian_view_catalog

# Descarga el catalogo fresco de bian.org y escribe docs/bian-view-catalog.json
python bian_view_catalog.py

# Ruta de salida custom
python bian_view_catalog.py --output mi_catalogo.json

# Usar un all_objects_on_views.js ya descargado (para no pegarle a bian.org)
python bian_view_catalog.py --source /ruta/a/all_objects_on_views.js
```

El resultado versionado en el repo vive en
[`docs/bian-view-catalog.json`](../../docs/bian-view-catalog.json).

## Formato de salida

Un array con un objeto por Service Domain (ordenado alfabeticamente):

```json
{
  "service_domain": "Correspondence",
  "sd_overview_url": "https://bian.org/servicelandscape-14-0-0/views/view_54378.html",
  "bom_diagram_url": "https://bian.org/servicelandscape-14-0-0/views/view_38944.html",
  "control_record_diagram_url": "https://bian.org/servicelandscape-14-0-0/views/view_47457.html"
}
```

`bom_diagram_url` y/o `control_record_diagram_url` quedan en `null` cuando esa
Service Domain no tiene esa pagina publicada (pasa con ~76 SDs de "back
office"/direccion interna — p.ej. Corporate Strategy, Employee Payroll And
Incentives — que en BIAN 14 no llegan a tener BOM ni Control Record
modelados, solo la entrada de "SD Overview").

Corrida de referencia: 348 Service Domains con SD Overview, 272 con BOM
Diagram resuelto, 271 con Control Record Diagram resuelto, 271 con los 3
links completos.

## Nota

Esto es **independiente** de `scripts/svg_to_puml/`: ese otro script trabaja
sobre los `.svg`/`.puml` ya descargados en este repo (272 Service Domains);
este script consulta bian.org en vivo y cubre las 350 Service Domains que el
sitio publica como "SD Overview" (un universo mas amplio, aunque sin SVG
local para todas).
