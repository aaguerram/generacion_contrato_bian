# download_svg_control_record

Descarga el SVG del **Control Record Diagram** de cada BIAN Service Domain
listado en [`docs/bian-view-catalog.json`](../../docs/bian-view-catalog.json)
(generado por `scripts/bian_view_catalog/`) y lo guarda en
`docs/bian-diagrams/svg_control_record/<slug-del-service-domain>.svg`.

## Por que funciona con un simple fetch (sin ejecutar JavaScript)

A diferencia de la pagina "SD Overview" (armada con Backbone/Marionette +
Handlebars, donde el contenido se inyecta en runtime desde archivos
`data/view_<id>_data.js` — ver el README de `scripts/bian_view_catalog/`), la
pagina de un diagrama en si (`views/view_<id>.html`, sea BOM o Control
Record) **si** trae el diagrama completo como HTML estatico: el archivo
contiene literalmente

```html
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg version="1.1" xmlns="http://www.w3.org/2000/svg" ... bizzid="47457" ...>
  ...
</svg>
```

incrustado dentro del `<div id="main">` de la pagina — el mismo formato
Bizzdesign (`bizzid`, `bizzconcept="UML_Class"`, notas `dogear`, etc.) que ya
usan los archivos locales en `docs/bian-diagrams/svg/`. El script solo
necesita bajar el HTML y recortar ese bloque.

**Cuidado con un falso positivo**: el comentario de copyright que bian.org
pone al principio de cada pagina menciona literalmente el texto
`<svg></svg>` en una oracion ("excluding any data contained between
`<svg></svg>` elements..."). El script ancla la busqueda del inicio real en
`<svg version=` (como aparece el tag de verdad en todas las paginas
revisadas) para no confundirlo con esa frase.

## Nombre de archivo

El slug se arma igual que los archivos ya existentes en
`docs/bian-diagrams/svg/` (minusculas, todo lo que no sea alfanumerico pasa a
un solo guion): `"Correspondence"` -> `correspondence.svg`. Se verifico que
esta regla reproduce exactamente los 272 nombres de archivo ya presentes en
esa carpeta antes de escribir el script.

## Como ejecutar

```bash
cd generacion_contrato_ia_v2/scripts/download_svg_control_record

# Descarga todos los Control Record Diagram del catalogo (salta los que ya existen)
python download_svg_control_record.py

# Un solo Service Domain, para probar
python download_svg_control_record.py --only Correspondence

# Redescargar aunque el .svg ya exista
python download_svg_control_record.py --force

# Usar otro catalogo o carpeta de salida
python download_svg_control_record.py --catalog otro-catalogo.json --output-dir otra/carpeta

# Cambiar la pausa entre requests (default 2.5s -- bian.org devuelve 429 si se
# va mas rapido; no bajar esto salvo que sepas lo que haces)
python download_svg_control_record.py --delay 3
```

Si bian.org responde 429 (rate limit) el script espera automaticamente (usando
el header `Retry-After` si viene, o 20s/40s/60s si no) y reintenta hasta 3
veces antes de darlo por fallido para esa Service Domain puntual -- no frena
el resto de la corrida.

Por cada Service Domain imprime `OK <archivo> (<bytes>)`, `SKIP (ya existe)
<archivo>`, o `ERROR <Service Domain>: <motivo>` sin frenar el resto de la
corrida; al final resume cuantos se descargaron, cuantos ya existian y
cuantos fallaron (con el detalle de cada fallo). Termina con exit code 1 si
hubo al menos un fallo, para que se note en CI/scripts que lo encadenen.

Las Service Domains sin `control_record_diagram_url` en el catalogo (las
~76 de "back office" que BIAN 14 no llego a modelar con Control Record) se
cuentan y se omiten, no cuentan como fallo.

## Resultado

`docs/bian-diagrams/svg_control_record/` — un `.svg` por cada Service Domain
con Control Record publicado (271 en la corrida de referencia sobre el
catalogo actual), en el mismo formato que `docs/bian-diagrams/svg/` pero
mostrando el diagrama del Control Record en vez del BOM completo de la SD.
