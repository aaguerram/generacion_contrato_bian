# evaluate_retrieval

Mide la **recuperación** de Service Domains sobre un corpus dorado, sin llamadas LLM, y compara
dos configuraciones del pipeline completo (canary).

```bash
.venv/bin/python scripts/evaluate_retrieval/evaluate.py
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --canales lexico,vectorial,qdrant
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --json salida/retrieval.json

.venv/bin/python scripts/evaluate_retrieval/canary.py --hu ./HU \
    --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json \
    --base config.yaml --candidata otra-config.yaml --proveedor ollama
```

## Resultados actuales (7 consultas, 341 SD, `qwen3-embedding:8b`)

| canal | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| léxico (rapidfuzz) | 0.14 | 0.29 | 0.29 | 0.214 |
| vectorial en memoria | 0.29 | 0.71 | **0.86** | 0.436 |
| Qdrant | 0.29 | 0.71 | **0.86** | 0.434 |
| RRF (léxico+vectorial) | 0.29 | 0.43 | 0.71 | 0.370 |
| RRF + graph | 0.29 | 0.43 | 0.71 | 0.370 |

Tres cosas que estos números ya cambiaron:

1. **La fusión RRF empeora**: mete el léxico —que en lenguaje natural acierta 0.29— con el mismo
   peso que el vectorial. El léxico es el canal correcto para `validar-sd` (ahí la consulta ES un
   nombre), no para `mapear-historias`.
2. **El reranker léxico era dañino** (0.14) y por eso el respaldo del cross-encoder pasó a NO
   reordenar.
3. **Qdrant no aporta calidad** a esta escala → `docs/adr/0001-vector-store.md`.

## Lo que este benchmark NO mide

Que el pipeline acierte. Recall@10 puede ser 1.0 y la corrida terminar en `UNRESOLVED`: es lo que
pasó el 2026-09-14, con el SD correcto recuperado siempre como top-1 y bloqueado después por el
revisor adversarial. **El gate "Recall@10 ≥ 0.95" se aprueba solo y no basta**: hay que mirar
`ownership_conflict_rate` y `operation_grounding_rate` de una corrida real, que es justo lo que
compara `canary.py`.

## Sobre el tamaño del corpus

7 consultas **no** son un corpus estadísticamente útil; sirven como regresión y como esqueleto.
Cada caso declara su `procedencia` (los dos casos E2E y las HU reales de `HU - copia/`) y sus
`hard_negatives` salen de candidatos que el pipeline propuso de verdad. Para comparar modelos de
embeddings con criterio harían falta del orden de 100 consultas etiquetadas.
