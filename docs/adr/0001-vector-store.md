# ADR 0001 — Índice vectorial: en memoria por defecto, Qdrant disponible

**Estado**: aceptada · **Fecha**: 2026-09-14 · **Decide**: backend del retrieval vectorial

## Contexto

El plan original proponía Qdrant o pgvector desde el diseño. La validación pedía no elegir sin
medir: *"No implementar ambos en la primera entrega. Ejecutar una ADR con benchmark y escoger
uno."* Hasta ahora no se había ejecutado ese benchmark.

## Medición

`scripts/evaluate_retrieval/evaluate.py` sobre el corpus dorado (7 consultas, catálogo de 341
Service Domains, embeddings `qwen3-embedding:8b` en Ollama local, dim 4096):

| canal | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| léxico (rapidfuzz) | 0.14 | 0.29 | 0.29 | 0.214 |
| vectorial en memoria | 0.29 | 0.71 | **0.86** | 0.436 |
| **Qdrant** | 0.29 | 0.71 | **0.86** | 0.434 |
| RRF (léxico + vectorial) | 0.29 | 0.43 | 0.71 | 0.370 |

Qdrant y el `InMemoryVectorStore` dan **el mismo resultado** (la diferencia de MRR es redondeo):
mismos vectores, misma métrica de distancia. A esta escala el índice externo no compra calidad.

Coste operativo medido: levantar el contenedor y poblar 341 puntos toma segundos, pero añade un
servicio, un volumen, una dependencia (`qdrant-client`) y un modo de fallo nuevo (Qdrant caído o
colección vacía). El índice en memoria se reconstruye en la propia corrida y no tiene ninguno.

## Decisión

**`vector_store: memoria` es el valor por defecto.** Qdrant queda implementado y probado
(`RecuperadorQdrant` + `infra/retrieval/docker-compose.yml` + `scripts/rebuild_index/`), a un
cambio de configuración de distancia, para cuando aparezca una razón real:

- compartir el índice entre procesos o máquinas (no una corrida CLI local);
- un corpus que crezca más allá de los 341 SD — por ejemplo indexar también operaciones, schemas
  y campos del modelo canónico, que ya son ~26.000 nodos;
- necesitar filtros de payload por release/Business Area sobre un índice grande.

**pgvector no se implementa.** Descartarlo ahora evita mantener dos adaptadores sin evidencia de
que ninguno haga falta; si algún día la plataforma ya opera Postgres, el puerto
(`RecuperadorSemanticoPort`) es el mismo y el adaptador es del tamaño del de Qdrant.

## Consecuencia inesperada del benchmark

El dato que sí cambia el diseño no fue el backend, sino la **fusión**: RRF de léxico + vectorial
(0.71) rinde **peor que el vectorial solo** (0.86), porque mete con el mismo peso un canal que en
consultas en lenguaje natural acierta 0.29 — el léxico compara contra el NOMBRE del Service
Domain, y una HU en español no repite el nombre en inglés del SD. El léxico sigue siendo el
adecuado para `validar-sd` (ahí la consulta ES un nombre), pero para `mapear-historias` conviene
medir antes de encender `retrieval_hibrido_habilitado`.

Anotado como pendiente: ponderar la fusión o elegir canales por caso de uso.
