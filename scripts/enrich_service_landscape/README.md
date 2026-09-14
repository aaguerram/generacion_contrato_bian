# enrich_service_landscape

Completa **in-place** `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` con lo que le falte de
`docs/SD.json`.

El Matrix View es la **fuente única** de información de Service Domains: es el único archivo que
lee el runtime (`CatalogoJson`) y el único parser que existe. `SD.json` (columnas L..V de
`BIANv14.xlsm`) ya no se lee en ejecución; queda solo como insumo de este script.

## Regla de nombres: un dato, un nombre, el del landscape

Antes de completar nada, el script empareja los campos de las dos fuentes **comparando valores**,
no nombres. Si un dato ya existe en el landscape bajo otro nombre, prevalece el nombre del
landscape y no se añade un campo duplicado. Con las fuentes actuales los once campos de SD.json
ya tienen equivalente (coincidencia de valor del 94% al 100%):

| SD.json | landscape | coincidencia |
|---|---|---|
| `Service Domain` | `name` | 100% |
| `Service Role` | `role_definition` | 99% |
| `Examples of Use` | `example_of_use` | 99% |
| `Executive Summary` | `executive_summary` | 98% |
| `Features` | `key_features` | 94% |
| `Documentation` | `documentation` | 98% |
| `Functional Pattern` | `functional_pattern` | 100% |
| `Asset Type` | `asset_type` | 100% |
| `Generic Artifact Type` | `generic_artifact_type` | 100% |
| `Control Record <AssetType><ArtifactType>` | `control_record` | 100% |
| `Registration Status` | `registration_status` | 100% |

Por eso la última corrida reporta **`campos agregados: ninguno`**. Si en el futuro apareciera un
campo sin equivalente, se añadiría con su nombre en snake_case y el script lo diría.

## Regla de valores: en los campos emparejados manda SD.json

El **nombre** es el del landscape; el **valor** lo pone SD.json siempre que tenga algo que decir
—es la fuente del `BIANv14.xlsm`, con la documentación estructurada `** 1. Role ** …`—. Si SD.json
no trae valor para ese campo, se respeta el del landscape. Cada reemplazo sobre un valor que ya
existía queda listado en `valores_sobrescritos`.

En total se aplicaron 29 valores: 12 huecos que el landscape tenía vacíos o truncados
(`Brand Management` y `Partner Management` estaban sin `role_definition`, `example_of_use`,
`executive_summary` ni `key_features`; `Financial Accounting`, `Collateral Asset Administration`,
`Bank Guarantee` y `Service Directory` tenían la `documentation` cortada) y 17 sobrescrituras
—14 diferencias de un espacio final, `Virtual Account.key_features`, y las dos `documentation`
de `Partner Management` y `Brand Management`, donde el landscape traía una definición de
capability en vez de la documentación del Service Domain—.

## Valores repetidos entre atributos

El script comprueba que ningún **texto descriptivo** (`role_definition`, `example_of_use`,
`executive_summary`, `key_features`, `documentation`) se repita en dos atributos del mismo Service
Domain: si dos campos dicen lo mismo, uno no aporta nada. Hoy: ninguno.

Los campos de **clasificación** quedan fuera de esa comprobación a propósito. BIAN los hace
coincidir de forma legítima: el Control Record se nombra `<AssetType><ArtifactType>`, así que en
`Legal Advisory` (asset type "Legal Advice", artifact type "Advice") el CR se llama "Legal Advice",
igual que su asset type. Pasa en 4 SD (`Legal Advisory`, `Consumer Advisory Services`,
`Corporate Tax Advisory`, `Sales Product Agreement`) y viene **idéntico en las dos fuentes
oficiales** — "corregirlo" sería inventar un dato que BIAN no publica.

## Uso

```bash
.venv/bin/python scripts/enrich_service_landscape/enrich_service_landscape.py             # completa
.venv/bin/python scripts/enrich_service_landscape/enrich_service_landscape.py --verificar # no escribe; falla si quedan huecos
```

- **Sin red**: todo sale de `docs/`.
- **Idempotente**: correrlo dos veces no cambia ningún Service Domain.
- Deja constancia en el bloque `enrichment` de la raíz del documento: fuentes con `sha256`,
  `mapeo_de_campos`, `campos_agregados`, `valores_completados` y `discrepancias_no_aplicadas`.

## Cuándo volver a correrlo

Cuando cambie `SD.json` (release BIAN nueva, `BIANv14.xlsm` actualizado) o cuando se regenere el
Matrix View con `scripts/generate_matrix_view/` — esa regeneración parte de bian.org y no conoce
las columnas del Excel, así que el enriquecimiento hay que reaplicarlo.

`tests/unit_test/test_catalogo_bian_unico.py` falla si el landscape tiene huecos que SD.json
podría llenar, así que la suite avisa sola.

## Rollback

`git checkout -- docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`.
