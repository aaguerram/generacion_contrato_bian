# ingest_bian

Construye el **modelo canónico BIAN** (`docs/bian-graph/release14.0.0/grafo.json`): los nodos y
relaciones tipadas que necesita la expansión por grafo.

## Por qué

Cada adaptador parseaba su fuente por su cuenta y el pipeline las cruzaba por nombre donde hacía
falta. Eso responde *"¿qué operaciones tiene este SD?"* pero no *"¿con qué otros SD se relaciona
según el propio BOM de BIAN?"* — sin relaciones explícitas solo quedan heurísticas.

## Entradas y salida

| Fuente | Aporta |
|---|---|
| `BIAN_Service_Landscape_V14.0_Matrix_View.json` | Service Domains y jerarquía |
| `bian-cache/release14.0.0/<SD>.json` | Control Records, Behavior Qualifiers, operaciones, schemas |
| `bian-diagrams/puml-bom/<slug>.puml` | clases y asociaciones del BOM |

Salida actual: **26.044 nodos** (341 SD, 239 CR, 761 BQ, 4.580 operaciones, 18.914 schemas, 1.168
clases BOM) y **58.226 aristas** (`PERTENECE_A`, `HAS_CR`, `HAS_BQ`, `HAS_OPERATION`,
`RESPONDE_CON`, `RECIBE`, `MODELA`, `ASOCIA`, `REFERENCIA`). ~19 MB.

## Reglas que no se relajan

- **Toda arista lleva su archivo de origen.** Una relación sin procedencia no se ingesta: expandir
  por una arista inventada es el mismo error que el pipeline evita en todo lo demás.
- **Las referencias colgantes no se silencian.** Un `response_schema` que no está en
  `schemas_detalle`, o una asociación del PUML hacia una clase que el diagrama no declara, quedan
  en `incidencias` dentro del propio JSON. Hoy son 9 (BQ sin `parent_control_record`).

## Uso

```bash
.venv/bin/python scripts/ingest_bian/ingest_bian.py              # genera el grafo
.venv/bin/python scripts/ingest_bian/ingest_bian.py --verificar  # falla si está desactualizado
.venv/bin/python scripts/ingest_bian/ingest_bian.py --solo "Correspondence"   # para depurar
```

Sin red, idempotente (nodos y aristas ordenados). Rollback: `git checkout -- docs/bian-graph/`.

## Cuándo regenerar

Cuando cambie cualquiera de las tres fuentes: release BIAN nueva, `--actualizar-cache-bian`, o
diagramas BOM nuevos.
