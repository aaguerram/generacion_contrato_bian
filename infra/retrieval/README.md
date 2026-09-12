# Infra de retrieval (OPCIONAL, diferida a Fase 3)

Este directorio existe para cuando el plan de recuperación híbrida llegue a la fase de
`KnowledgeIndexPort` con un backend externo. **Hoy no hace falta arrancar nada de esto**: el
falso negativo de "Notificar actualización de datos" (Correspondence descartado por
`CONSUMED_DEPENDENCY`) es un bug de reglas de ownership/scoring, no de recall — el candidato ya
se recupera y evalúa correctamente con el `RecuperadorLexico` / `RecuperadorVectorial`
(`InMemoryVectorStore` en memoria, persistido a disco) que ya existen en
`src/adaptadores/salida/`.

## Cuándo usar esto

Solo tras:
1. Construir el corpus canónico completo (SD + CR + BQ + operaciones + schemas + campos) — Fase 2.
2. Correr `scripts/evaluate_retrieval/` contra el `InMemoryVectorStore` actual con la tabla dorada
   de consultas (positivos + hard negatives).
3. Que el benchmark muestre que el índice en memoria no alcanza (recall, latencia de carga en
   frío, o tamaño de corpus) para justificar operar un servicio externo.
4. Una ADR corta que registre esa decisión (no las dos a la vez — ver plan, sección 6.4).

Si el benchmark pasa con el índice en memoria, **no se levanta nada de aquí** y este directorio
se puede borrar.

## Uso

```bash
# Elegir UN perfil (nunca los dos en la primera entrega):
docker compose -f infra/retrieval/docker-compose.yml --profile qdrant up -d
docker compose -f infra/retrieval/docker-compose.yml --profile pgvector up -d

# Apagar y borrar el volumen (reindexar desde cero):
docker compose -f infra/retrieval/docker-compose.yml --profile qdrant down -v
docker compose -f infra/retrieval/docker-compose.yml --profile pgvector down -v
```

Qdrant queda en `http://localhost:6333` (dashboard en `/dashboard`). Postgres+pgvector queda en
`localhost:5432` (`bian_knowledge_index` / `bian_rag` / `bian_rag_local_only` — solo para uso
local; estas credenciales nunca deben copiarse a un `.env` real).

## Por qué no ambos, y por qué no ahora

- El proyecto es hoy 100% offline / sin servidor (CLI batch + caché en `docs/`, ver
  `CLAUDE.md` del repo). Añadir un servicio externo es un cambio de naturaleza operativa, no
  solo de código: introduce arranque, red, volúmenes y un modo de fallo nuevo (`GEN-RUN-LOCK-001`
  no tiene equivalente aquí — habría que definir qué pasa si el índice no responde).
- `requirements.txt` no tiene `qdrant-client` ni `psycopg`/`pgvector` — son dependencias nuevas,
  no algo que ya esté a medio instalar.
- El corpus es pequeño para estándares de vector DB (341 Service Domains; incluso expandido a
  CR+BQ+operaciones+schemas+campos son unos pocos miles de nodos). Un `InMemoryVectorStore`
  cacheado en disco por modelo de embeddings (patrón ya usado en `validar-sd`) es routinariamente
  suficiente a ese tamaño.
- Mantener ambos adaptadores desde el día uno duplica trabajo de implementación y de pruebas de
  integración sin evidencia de que se necesite ninguno todavía.

`src/aplicacion/puertos/` seguirá definiendo `KnowledgeIndexPort` de forma agnóstica al backend,
así que activar uno de estos servicios más adelante es añadir un adaptador nuevo, no reabrir el
dominio.
