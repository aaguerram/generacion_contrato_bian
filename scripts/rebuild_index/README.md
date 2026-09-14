# rebuild_index

Reconstruye el índice de recuperación desde `docs/`. Dos backends:

```bash
.venv/bin/python scripts/rebuild_index/rebuild.py                    # memoria -> cache en .cache/
.venv/bin/python scripts/rebuild_index/rebuild.py --backend qdrant   # índice externo
.venv/bin/python scripts/rebuild_index/rebuild.py --backend qdrant --snapshot
```

Lo que se indexa por Service Domain es `EntradaCatalogo.texto_para_indexar()` — nombre, jerarquía,
clasificación, rol, ejemplo de uso, features, resumen y documentación (~1.200 chars). El payload
lleva Business Area/Domain, patrón funcional, release y modelo de embeddings, para poder filtrar
sin volver al catálogo.

**Idempotente**: el id de cada punto es un hash estable del nombre canónico del SD. La colección se
recrea en vez de actualizarse, para que un cambio de modelo de embeddings (otra dimensión) no deje
mezclados vectores de dos espacios distintos.

## Qdrant

Levantar primero el motor (ver `infra/retrieval/README.md`):

```bash
cd infra/retrieval && docker compose --profile qdrant up -d
```

Última corrida real: 341 puntos, dim 4096, embeddings `qwen3-embedding:8b` (Ollama local).
El resultado de recuperación es **idéntico** al índice en memoria — ver
[`docs/adr/0001-vector-store.md`](../../docs/adr/0001-vector-store.md), que por eso deja
`vector_store: memoria` como valor por defecto.

## Rollback

El índice es derivado: borrar la colección y volver a correr el script la reconstruye. Con
`--backend memoria`, borrar `.cache/`.
