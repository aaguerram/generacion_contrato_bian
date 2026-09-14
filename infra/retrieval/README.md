# infra/retrieval — índice vectorial externo (opcional)

Levanta el motor del índice de recuperación. **No hace falta para operar**: por defecto el
pipeline usa un `InMemoryVectorStore` que se reconstruye en la propia corrida
(`mapear_historias.vector_store: memoria`). Ver [`docs/adr/0001-vector-store.md`](../../docs/adr/0001-vector-store.md):
medido sobre el corpus dorado, Qdrant da **exactamente el mismo recall** que el índice en memoria
a esta escala (341 Service Domains).

Nada arranca con `docker compose up` a secas: cada motor vive en su propio perfil.

## Qdrant (el implementado)

```bash
cd infra/retrieval
docker compose --profile qdrant up -d          # levanta el motor
```

La data **vive en un volumen nombrado** (`retrieval_qdrant_data`), así que sobrevive a parar y
volver a levantar el contenedor — comprobado: tras `down` + `up` la colección seguía con sus 341
puntos, sin reindexar. Solo se pierde con `down -v`, que es justo lo que hay que usar para
reindexar desde cero.

Poblar el índice (desde el host, donde están el venv y el proveedor de embeddings):

```bash
cd ../..
.venv/bin/python scripts/rebuild_index/rebuild.py --backend qdrant
```

Y apuntar el pipeline al índice externo en `config.yaml`:

```yaml
mapear_historias:
  vector_store: qdrant
  qdrant_url: http://localhost:6333
  qdrant_coleccion: bian_service_domains
```

Si Qdrant está apagado o la colección vacía, el adaptador **no rompe la corrida**: avisa una vez y
ese canal devuelve vacío, igual que el vectorial cuando no hay proveedor de embeddings.

Dashboard: <http://localhost:6333/dashboard>. Solo escucha en `127.0.0.1`.

```bash
docker compose --profile qdrant down       # parar conservando la data
docker compose --profile qdrant down -v    # parar y BORRAR el volumen (reindexar desde cero)
```

## pgvector (no implementado)

El perfil existe y levanta Postgres+pgvector, pero **no hay adaptador**: la ADR decidió no
mantener dos backends sin evidencia de que ninguno haga falta. Si algún día la plataforma ya opera
Postgres, el puerto es el mismo (`RecuperadorSemanticoPort`) y el adaptador es del tamaño del de
Qdrant (`src/adaptadores/salida/recuperador_qdrant.py`, ~100 líneas).

## Versiones

`qdrant/qdrant:v1.15.1` — alineada con el `qdrant-client` del venv; una diferencia de más de una
minor hace que el cliente avise de incompatibilidad.
