# generate_matrix_view

Genera [`docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`](../../docs/BIAN_Service_Landscape_V14.0_Matrix_View.json):
el arbol completo **Business Area -> Business Domain -> Service Domain** del
Service Landscape BIAN 14.0.0, tal como se ve en
https://bian.org/servicelandscape-14-0-0/views/view_54081.html ("BIAN
Service Landscape V14.0 Matrix View").

## Los 2 escenarios de anidamiento

Esa vista mezcla 2 formas de colgar un Service Domain de su Business Area:

1. **Anidado**: `Business Area > Business Domain > Business Domain > Service
   Domain`. Ejemplo real: `Operations and Execution > Cross Product
   Operations > Account Management > Account Reconciliation`.
2. **Plano**: `Business Area > Business Domain > Service Domain` (sin nivel
   intermedio).

## De donde sale esto (100% local, sin red)

Antes de escribir el script se navego bian.org en vivo para confirmar que
`view_54081.html` es una vista-diagrama mas (misma familia que las paginas de
`bian_object_catalog`), sin un JSON de arbol propio y facil de parsear — asi
que en vez de reconstruir el arbol desde el SVG/posiciones de esa vista
puntual, se busco el equivalente ya presente en un archivo local, y
**si esta**: `docs/BIANv14.xlsm`, hoja "Service Domains", trae 2 familias de
columnas paralelas:

- **Modelo** (`mBusiness Area` / `mBusiness Domain parent` / `mBusiness
  Domain`): la taxonomia formal BIAN — 5 Business Areas (`Business Support`,
  `Operations and Execution`, `Reference Data`, `Risk and Compliance`,
  `Sales and Service`). Da el escenario 1 cuando `mBusiness Domain parent`
  viene poblado (129 de 341 filas) y el escenario 2 cuando viene vacio (212
  de 341).
- **Vista** (`vBusiness Area` / `vBusinessDomain`): **NO es una version
  simplificada del modelo — es un eje de clasificacion aparte**, usado
  aparentemente para como bian.org organiza la navegacion/menus del sitio
  (`Resource Management`, `Channels`, `Customers`, `Business Development`,
  `Finance And Risk Management`, `Operations`, `Products`, `Business
  Management`). Se comprobo cruzando las 341 filas: un mismo `mBusiness
  Area` se reparte entre hasta 6 `vBusiness Area` distintos segun el
  Service Domain (p.ej. `Operations and Execution` cae bajo `Operations`,
  `Products`, `Customers`, `Channels`, `Business Development` o `Finance And
  Risk Management` segun el caso) — por eso **no se puede usar una como
  fallback de la otra sin mezclar 2 ejes incompatibles**.

Verificado antes de confiar en el eje de modelo:

- Los 3 roles de nombre de Business Domain (usado como **padre**, usado como
  **hoja plana**, usado como **hijo anidado**) son mutuamente excluyentes —
  ningun nombre cumple 2 roles.
- Un mismo par (padre, hijo) siempre cae bajo la misma Business Area (0
  inconsistencias en las 341 filas).
- Solo 2 Business Domain actuan de padre: `Cross Product Operations` (hijos:
  Account Management, Collateral Administration, Operational Services,
  Payments) y `Product Specific Fulfillment` (hijos: Cards, Consumer
  Services, Corporate Financing and Advisory Services, Investment
  Management, Loans and Deposits, Market Operations, Trade Banking,
  Wholesale Trading).

### Los 2 Service Domains sin dato de modelo (y como se resolvieron de verdad)

`Prospect Campaign Management` y `Trade Settlement` no traen NADA en las
columnas de modelo del xlsm (`mBusiness Area`/`mBusiness Domain` en blanco).
La primera version de este script los agrupaba en un bucket sentinela
separado usando su clasificacion de *vista* como pista — **pero la vista es
un eje distinto** (ver arriba), asi que ese bucket no reflejaba donde BIAN
realmente los ubica.

Para resolverlo de verdad se bajo la pagina oficial del Matrix View
(`view_54081.html`, 974 KB) y se parsearon las coordenadas SVG de cada caja
(`<path d="M x,y h w ... v h ...">`), calculando que caja mas grande
contiene geometricamente el centro de cada Service Domain:

- `Trade Settlement` (bizzsemantic/object_id `43346`) cae dentro de la caja
  de `Market Operations` (`216875`), que a su vez cae dentro de `Product
  Specific Fulfillment` (`216824`) — **el mismo Business Domain padre que
  ya existe en este arbol** (via otras 129 filas) bajo Business Area
  `Operations and Execution`, con `Market Operations` agrupando otros 11
  Service Domains de trading (`Trade Clearing`, `Trade Confirmation
  Matching`, `Trade and Price Reporting`, ...).
- `Prospect Campaign Management` (object_id `33231`) cae dentro de la caja
  de `Marketing` (`216774`) — que **ya existe** bajo Business Area `Sales
  and Service` agrupando otros 8 Service Domains de campanas/marketing
  (`Prospect Campaign Design`, `Customer Campaign Management`, ...).

No es una correccion inventada: ambos Business Domain destino ya existian en
el arbol (via otras filas) con hermanos tematicamente coherentes — solo se
completo, con la fuente oficial, un dato que 2 filas puntuales del xlsm
dejaron vacio. Esto vive hardcodeado en `KNOWN_MODEL_GAPS` (con la evidencia
completa en el comentario del codigo); si una futura version de
`BIANv14.xlsm` completa estas 2 filas, el diccionario queda sin efecto (solo
se consulta cuando la fila no trae `mBusiness Area`/`mBusiness Domain`).

Con este fix, `unclassified_in_model` queda vacio y el bucket sentinela
`UNCLASSIFIED_AREA` no aparece en la salida — se mantiene el mecanismo (por
las dudas de que una release futura de BIAN traiga un Service Domain
realmente sin Business Area, ninguno de los 2 conocidos ni geometricamente
verificable) pero hoy no lo dispara nada.

## Como ejecutar

```bash
cd generacion_contrato_ia_v2/scripts/generate_matrix_view
python generate_matrix_view.py
```

Lee `docs/BIANv14.xlsm` + `docs/SD.json` + `docs/entity.json` y escribe
`docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`. Flags: `--xlsm`,
`--object-catalog`, `--sd-json`, `--entity-json`, `--output`. No requiere red
ni dependencias externas — mismo lector `.xlsx`/`.xlsm` minimo (solo stdlib)
que ya usan `scripts/generate_entities/` y `scripts/bian_object_catalog/`.

### `object_url` + `documentation` en los 3 niveles (opcional)

Si `docs/bian-object-catalog.json` existe (generado por
`scripts/bian_object_catalog/`), cada Business Area real (nunca el bucket
sentinela), cada Business Domain (de primer nivel y anidado) y cada Service
Domain reciben:

- `object_url`: link a su pagina de objeto en bian.org
  (`object_<N>.html?object=<id>` — la misma URL a la que se llega haciendo
  click en ese elemento desde el Matrix View).
- `documentation`: el texto de la seccion literalmente titulada
  "Documentation" de esa pagina, ya extraido como texto plano (Business
  Area/Domain solo tienen esta — Service Domain tiene ademas las 4 de
  abajo).

Ademas, cada **Service Domain** trae las otras secciones numeradas que
bian.org le agrega a su pagina de objeto, cada una como su propio atributo:
`role_definition` ("1. Role Definition"), `example_of_use` ("2. Example of
Use"), `executive_summary` ("3. Executive Summary"), `key_features` ("4. Key
Features"). Las 4 estan siempre presentes (en `null` si esa pagina puntual
no trae alguna); si bian.org agrega a futuro una seccion numerada nueva que
este script todavia no conoce, se agrega igual con su propio nombre (ver
`KNOWN_SD_SECTION_KEYS` en el codigo) — nunca se pierde silenciosamente.

**Sobre `documentation` en un Service Domain:** la seccion homonima de
bian.org viene vacia para la enorme mayoria de Service Domains (verificado
con "Card Authorization", `object_14.html?object=41757`: la pagina real
tiene esa seccion vacia — una version anterior de este script devolvia ahi
el texto de "Role Definition" por error, tomaba la primera categoria de
documentacion que encontraba en vez de la correcta; ver el README de
`bian_object_catalog` para el detalle del bug y el fix). Por eso
`documentation` usa `docs/SD.json` como respaldo cuando bian.org no trajo
nada (ver la seccion de `SD.json` mas abajo) — 340/341 Service Domains
quedan con `documentation` lleno.

Por esto, cada `service_domains[]` ya no es una lista de strings — es una
lista de objetos `{name, object_url, role_definition, example_of_use,
executive_summary, key_features, documentation}` (ver formato abajo).

Como `bian_object_catalog.py` necesita el arbol ya armado (para saber que
nombres de Business Area/Domain resolver), hay que correr los 2 scripts en
este orden (el primero sin `object_url`/`documentation` en Areas/Domains, el
segundo los agrega — los Service Domains ya salen completos desde el primer
paso, porque `bian_object_catalog.py` los resuelve contra
`bian-view-catalog.json`, no contra este archivo):

```bash
cd generacion_contrato_ia_v2/scripts
python generate_matrix_view/generate_matrix_view.py   # 1. arma el arbol (Service Domains ya completos)
python bian_object_catalog/bian_object_catalog.py      # 2. resuelve Business Areas + Business Domains (y clases)
python generate_matrix_view/generate_matrix_view.py   # 3. re-arma el arbol, ahora TODO con object_url/documentation
```

Sin ese archivo, este script sigue funcionando igual — todos los
`object_url`/`documentation` quedan en `null`.

### `functional_pattern` / `asset_type` / `generic_artifact_type` / `control_record` / `registration_status` (de `docs/SD.json`)

`docs/SD.json` (341 Service Domains, columnas L..V de `docs/BIANv14.xlsm`
— ver `CLAUDE.md` de este proyecto) trae varios campos por Service Domain.
Antes de agregarlos se comparo cada uno contra lo que ya sale de bian.org
(arriba) para no duplicar el mismo dato con otro nombre:

| Campo en `SD.json` | Ya existe como | Coincide? |
|---|---|---|
| `Service Role` | `role_definition` | Si — mismo texto (verificado con "Card Authorization") |
| `Examples of Use` | `example_of_use` | Si — mismo texto |
| `Executive Summary` | `executive_summary` | Si — mismo texto |
| `Features` | `key_features` | Si — mismo texto |
| `Documentation` | `documentation` | Ver abajo (respaldo, no duplicado directo) |
| `Functional Pattern` | — | **Nuevo** -> `functional_pattern` |
| `Asset Type` | — | **Nuevo** -> `asset_type` |
| `Generic Artifact Type` | — | **Nuevo** -> `generic_artifact_type` |
| `Control Record <AssetType><ArtifactType>` | — | **Nuevo** -> `control_record` |
| `Registration Status` | — | **Nuevo** -> `registration_status` |

`Functional Pattern`/`Asset Type`/`Generic Artifact Type`/`Control
Record`/`Registration Status` se agregan directo (no tienen equivalente en
bian.org). Los primeros 4 (`Service Role`/`Examples of Use`/`Executive
Summary`/`Features`) NO se duplican — ya estan cubiertos por
`role_definition`/`example_of_use`/`executive_summary`/`key_features`.

**`documentation` es un caso especial: respaldo, no duplicado.** `Documentation`
en `SD.json` es la concatenacion de esos mismos 4 campos + una seccion
"General comment" al final — esa ultima seccion es EXACTAMENTE el
`documentation` que ya sale de bian.org (verificado texto por texto con los
3 unicos casos donde no viene vacia: Bank Guarantee, Collateral Asset
Administration, Financial Accounting). El problema es que bian.org deja esa
seccion vacia para la enorme mayoria de Service Domains (verificado
tambien con "Card Network Participant Facility": vacia ahi igual, no es un
bug de extraccion) — asi que antes de este fix `documentation` quedaba en
`null` para casi todos, aunque `SD.json` SI trae el campo completo siempre.
Ahora `documentation` usa el texto completo de `SD.json` como respaldo
**solo cuando bian.org no trajo nada** — nunca pisa un valor real de
bian.org cuando lo hay. Resultado: 340/341 Service Domains con
`documentation` lleno (el unico caso que queda en `null`,
`Card Transaction Tracking`, es porque `SD.json` mismo trae ese campo en
`null` para esa fila puntual — no un bug de este script).

`SD.json` cubre los 341 Service Domains con el mismo nombre exacto que usa
el resto del arbol (0 diferencias verificadas), asi que el cruce es directo
por nombre, sin ambiguedad.

Sin `docs/SD.json` (o si un Service Domain puntual no aparece ahi), los 5
campos nuevos quedan en `null` y `documentation` se queda con lo que haya
traido bian.org (tambien `null` en la mayoria de los casos) — no hace falta
ningun otro script para tener `SD.json` (ya existe en el repo, no se genera
ni se descarga).

### `bom_diagram` / `control_record_diagram` / `sd_overview_url` (de `docs/entity.json`)

`docs/entity.json` (generado por `scripts/generate_entities/`) trae, por
cada clase BIAN BOM, 1 "aparicion" por diagrama donde esa clase aparece
dibujada — cada aparicion incluye `puml_path`/`svg_path` (rutas locales) +
`bian_source_url` (el link de ESE diagrama en bian.org) + `sd_overview_url`.
Los primeros 3 son propiedades del **diagrama** (bom y control_record tienen
cada uno el suyo); `sd_overview_url` en cambio es un valor **general del
Service Domain** — el mismo en la aparicion bom y en la control_record de
un mismo SD (verificado: 0 inconsistencias en las 272 combinaciones Service
Domain+tipo-de-diagrama que trae `entity.json`). Por eso alcanza con leerlo
1 sola vez y quedarse con la primera aparicion de cada (Service Domain,
tipo de diagrama) — no hace falta cruzar entidad por entidad.

Cada Service Domain recibe, en su **raiz** (junto a `object_url`,
`asset_type`, etc. — no duplicado dentro de cada diagrama):

- `sd_overview_url`: link a la pagina "SD Overview" de ese Service Domain
  en bian.org.

Y ademas, 2 sub-objetos con solo lo que SI es propio de cada diagrama:

- `bom_diagram`: `{puml_path, svg_path, bian_source_url}` del diagrama BOM
  de ese Service Domain, o `null` si no tiene uno publicado localmente.
- `control_record_diagram`: lo mismo para el diagrama Control Record.

(Nombrados `..._diagram` — no `bom`/`control_record` a secas — para no
confundirse con el `control_record` de arriba, que es un string: el nombre
del Control Record segun `SD.json`, no un objeto con rutas/URL.)

**Cobertura real: 265/341 con `bom_diagram`, 258/341 con
`control_record_diagram`, 76/341 sin ninguno de los dos** (Service Domains
sin diagrama publicado en bian.org 14.0.0 — mismo universo que ya reportaba
`scripts/bian_view_catalog/`: ~76 SDs de "back office"/direccion interna no
llegan a tener BOM ni Control Record modelados).

**Investigado y resuelto — no son un hueco de datos, son 7 Service Domains
obsoletos.** `ACH Operations`, `Correspondent Bank Operations`, `Direct
Debit Collection`, `Direct Debits Service`, `Payment Execution`, `Payment
Instruction` y `Payment Order` SI tienen diagramas locales extraidos (BOM +
Control Record completos, `.puml` y `.svg`, en `docs/bian-diagrams/`) y SI
tienen su propia pagina de objeto en bian.org — pero **ninguno de los 7
aparece ni una sola vez en el HTML crudo del Matrix View oficial**
(`view_54081.html`; se busco su `object_id` literal en el archivo completo,
0 coincidencias en los 7 casos — no es un problema de parseo de este
script, bian.org directamente no los dibuja ahi).

La razon: su propia ficha de objeto en bian.org trae
`"BIAN Life Cycle": {"Registration Status": "Obsolete"}`, y su link
"API BIAN Portal" apunta a la release **13.0.0**, no 14.0.0 (ej.
`https://portal.bian.org/service-domain-api/BIAN-13.0.0-ACHOperations`).
Son Service Domains **retirados** de una release anterior que bian.org
mantiene accesibles por compatibilidad historica (pagina de objeto propia,
diagramas propios) pero que correctamente NO forman parte del modelo activo
14.0.0 — por eso tambien faltan en `docs/BIANv14.xlsm` (hoja "Service
Domains") y en `docs/SD.json` (341, no 348): esas 2 fuentes reflejan el
modelo 14.0.0 vigente, y estos 7 xa no lo son.

**Por eso este script NO los agrega al arbol** — incluirlos representaria
mal el Service Landscape 14.0.0 actual. Sus datos (`puml_path`/`svg_path`/
`bian_source_url`) siguen disponibles en `docs/entity.json` para quien
necesite consultar el modelo historico/13.0.0 de esos 7, pero fuera del
arbol de este archivo.

Sin `docs/entity.json`, estos 2 campos quedan en `null` para todos — no
hace falta correr nada mas para tenerlo (`scripts/generate_entities/` ya lo
genera de forma independiente, ver su propio README).

## Formato de salida

```jsonc
{
  "release": "14.0.0",
  "source_view": "https://bian.org/servicelandscape-14-0-0/views/view_54081.html",
  "source_file": "docs/BIANv14.xlsm (hoja 'Service Domains')",
  "stats": {
    "business_areas": 5,
    "root_business_domains": 26,
    "nested_business_domains": 12,
    "service_domains": 341,
    "service_domains_skipped": 0
  },
  "business_areas": [
    {
      "name": "Operations and Execution",
      "is_unclassified": false,
      "object_url": "https://bian.org/servicelandscape-14-0-0/object_17.html?object=216795",
      "documentation": "...",
      "business_domains": [
        {
          "name": "Product Specific Fulfillment",
          "object_url": "...",
          "documentation": "...",
          "business_domains": [
            {
              "name": "Cards",
              "object_url": "...",
              "documentation": "...",
              "business_domains": [],
              "service_domains": [
                {
                  "name": "Card Authorization",
                  "object_url": "https://bian.org/servicelandscape-14-0-0/object_14.html?object=41757",
                  "sd_overview_url": "https://bian.org/servicelandscape-14-0-0/views/view_54510.html",
                  "role_definition": "The proposed card transaction is requested by a merchant and routed through the Acquirer and Card Network to the Issuer. ...",
                  "example_of_use": "A credit card customer makes a large purchase, the card authorization triggers a verbal check of the customer details for security and the authorization is given",
                  "executive_summary": "This service domain is responsible for the real time card authorization decisions for credit/charge cards.",
                  "key_features": "Card device verification checks\nCard member identity verification\nCredit checks\nFraud detection checks",
                  "documentation": "** 1. Role **\nThe proposed card transaction is requested by a merchant and routed through the Acquirer and Card Network to the Issuer. ...\n\n** 2. Examples of use **\n...\n\n** 3.Executive Summary **\n...\n\n** 4. Key Features **\n...\n\n** General comment **",
                  "functional_pattern": "Assess",
                  "asset_type": "Credit Card Authorization",
                  "generic_artifact_type": "Assessment",
                  "control_record": "Credit Card Authorization Assessment",
                  "registration_status": "Registered",
                  "bom_diagram": {
                    "puml_path": "docs/bian-diagrams/puml-bom/card-authorization.puml",
                    "svg_path": "docs/bian-diagrams/svg_bom/card-authorization.svg",
                    "bian_source_url": "https://bian.org/servicelandscape-14-0-0/views/view_48502.html"
                  },
                  "control_record_diagram": {
                    "puml_path": "docs/bian-diagrams/puml-control-record/card-authorization.puml",
                    "svg_path": "docs/bian-diagrams/svg_control_record/card-authorization.svg",
                    "bian_source_url": "https://bian.org/servicelandscape-14-0-0/views/view_46061.html"
                  }
                }
              ]
            }
          ],
          "service_domains": []
        }
      ]
    }
  ],
  "unclassified_in_model": []
}
```

Cada `business_domains[]` trae SIEMPRE las 2 claves `business_domains`
(hijos anidados, escenario 1) y `service_domains` (hojas directas, escenario
2) — una de las 2 queda vacia segun el escenario real de ese dominio, para
que el codigo que lo consuma no tenga que chequear si la clave existe. Cada
Service Domain es un objeto `{name, object_url, documentation}` (no un
string suelto).

`stats.business_areas` es hoy 5 (las 5 reales del modelo BIAN); el bucket
sentinela `UNCLASSIFIED_AREA` (con `object_url`/`documentation` siempre en
`null`, por no ser un objeto real de bian.org) solo aparece si algun Service
Domain futuro no tiene ni dato de modelo ni entrada en `KNOWN_MODEL_GAPS`.

## Nota: por que no coincide con `docs/bian-business-areas.json`

Ese archivo (usado por `mapear-historias`, ver `CLAUDE.md` del proyecto)
tiene 5 Business Areas y suma los mismos 341 Service Domains — pero son 5
Business Areas de **vista** (`Resource Management`, `Channels`, etc.), un
eje totalmente distinto a las 5 Business Areas de **modelo** que arma este
script (`Business Support`, `Operations and Execution`, etc. — que
coincidan en cantidad, 5 y 5, es casualidad de este release, no una
correspondencia 1 a 1 entre nombres). Son 2 categorizaciones BIAN legitimas
y cruzadas dentro del mismo xlsm, no un error: este script arma la de
**modelo** especificamente porque es la unica que reproduce los 2 escenarios
de anidamiento que se ven en la pagina "Matrix View" pedida.

## Corrida de referencia

```
5 Business Areas (las 5 reales del modelo; el bucket sentinela no aparece)
26 Business Domains de primer nivel
12 Business Domains anidados (escenario 1)
341 Service Domains en total
0 en unclassified_in_model (los 2 huecos del xlsm se resolvieron via KNOWN_MODEL_GAPS,
  verificado geometricamente contra el Matrix View oficial)

Tras correr bian_object_catalog.py y re-generar (paso 3 de arriba):
5/5 Business Areas con object_url + documentation
36/38 Business Domains con object_url + documentation (2 ambiguos: Customer Management, Product Management)
348/348 Service Domains con object_url + role_definition/example_of_use/executive_summary/key_features
341/341 Service Domains con functional_pattern/asset_type/generic_artifact_type/control_record/registration_status (de docs/SD.json)
340/341 Service Domains con documentation lleno (bian.org cuando trae texto real, si no
  respaldo de docs/SD.json — el unico null, Card Transaction Tracking, es porque SD.json
  mismo trae ese campo vacio para esa fila)
265/341 Service Domains con bom_diagram, 258/341 con control_record_diagram (de docs/entity.json;
  76 sin ninguno de los dos = sin diagrama publicado en bian.org 14.0.0)
```

**Nota:** 7 Service Domains con diagrama local extraido (`ACH Operations`,
`Correspondent Bank Operations`, `Direct Debit Collection`, `Direct Debits
Service`, `Payment Execution`, `Payment Instruction`, `Payment Order`)
quedan deliberadamente fuera del arbol — estan marcados `Registration
Status: Obsolete` en bian.org (retirados desde BIAN 13.0.0, ver la seccion
de `bom_diagram`/`control_record_diagram` arriba para la evidencia
completa) — no cuentan en las cifras de esta corrida de referencia.
