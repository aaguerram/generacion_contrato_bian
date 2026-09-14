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

## Regla de valores: solo se completa lo que falta

| Situación | Qué hace |
|---|---|
| Landscape vacío, SD.json con valor | completa |
| Landscape truncado (SD.json lo contiene literalmente) | completa con el texto entero |
| Ambos con valor y textos distintos | **no toca**: manda el landscape, y lo anota como discrepancia |

Última corrida: 12 valores completados (`documentation` 4, `example_of_use` 2,
`executive_summary` 2, `key_features` 2, `role_definition` 2) y 17 discrepancias respetadas —
15 son diferencias de un carácter (un espacio final) y 2 son textos genuinamente distintos
(`Partner Management` y `Brand Management`, donde el landscape define la capability y SD.json trae
la documentación estructurada `** 1. Role ** …`).

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
