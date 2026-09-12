# Plan de implementación: recuperación y decisión BIAN híbrida

## 1. Resultado esperado

Para la historia **“Notificar actualización de datos”**, el pipeline debe recuperar y evaluar, como mínimo:

- Service Domain: `Correspondence`.
- Control Record padre: `CorrespondenceOperatingSession`.
- Behavior Qualifier: `Outbound`.
- Operación: `InitiateOutbound`.
- Método HTTP: `POST`.
- Path oficial BIAN R14: `/Correspondence/{correspondenceid}/Outbound/Initiate`.

La regresión E2E 1 de datos personales debe continuar validando de forma independiente:

- `Party Reference Data Directory` como `OWNED_CONTRACT` y no `REJECTED`.
- `RetrieveReference` o `UpdateReference`.
- exclusión de `RetrieveDemographics`.

## 2. Diagnóstico confirmado

La falla observada no es principalmente ausencia de datos BIAN ni falta de LangGraph:

1. `Correspondence` sí fue generado y evaluado en la corrida `salida/2026-09-11_17-59-40`.
2. La evidencia cacheada contiene `InitiateOutbound`, método `POST`, tipo `BQ`, grupo `Outbound` y padre `CorrespondenceOperatingSession`.
3. El evaluador LLM clasificó `Correspondence` como `CONSUMED_DEPENDENCY`, aunque la HU ordena directamente **enviar notificaciones**.
4. `clasificar_service_domains()` penaliza los roles no owned, los limita por debajo del umbral directo y los marca contractualmente `REJECTED`.
5. El score resultante de `Correspondence` fue `0.5033`, menor que `umbral_tentativo=0.63`, por lo que terminó en `candidatos_descartados`.
6. `_h_operaciones()` sólo procesa `candidatos_directos`. En consecuencia, una operación oficial correctamente recuperada no puede publicarse si el error de ownership ocurre antes.
7. El segundo pase léxico de omitidos sólo compara señales en español contra nombre y Service Role mayormente en inglés; además se ejecuta después de preparar la lista a evaluar y sólo reporta omitidos, no reinyecta candidatos al fan-out.

Por tanto, añadir únicamente embeddings, un reranker o una base vectorial no corrige la causa inmediata. Esas piezas mejoran el recall, pero el falso negativo actual ocurre en las etapas de **ownership, scoring, elegibilidad de operación y contrato de salida**.

## 3. Principios de la solución

1. Separar cuatro conceptos hoy parcialmente mezclados:
   - candidato recuperado;
   - candidato aplicable;
   - rol contractual (`OWNED`, `CONSUMED`, `RELATED`);
   - operación BIAN soportada por evidencia.
2. El LLM propone y explica; reglas deterministas verifican nombres, jerarquía, operaciones, métodos, schemas y contradicciones.
3. Ningún candidato razonable desaparece silenciosamente: toda etapa conserva score, rango, motivo y evidencia.
4. No codificar reglas específicas para `Correspondence`; usar verbos de ciclo de vida, objetos y operaciones oficiales aplicables a cualquier Service Domain.
5. Mantener la arquitectura hexagonal y LangGraph actuales; extender puertos y nodos sin acoplar dominio a Qdrant, PostgreSQL o un proveedor de modelos.

## 4. Arquitectura objetivo consolidada

```text
HU + funcionalidad
        |
        v
Requirement Analyzer
  - acciones, objetos, outcomes, actores
  - acción directa vs precondición/dependencia
  - términos ES y equivalentes BIAN EN
        |
        v
Hybrid Candidate Retriever
  - exact/alias + BM25
  - vector search
  - filtros de metadata
  - expansión por grafo BIAN
        |
        v
Fusion (RRF) -> top 20
        |
        v
Cross-encoder reranker -> top 5-8
        |
        v
Evidence Pack Builder
  - Service Role / Functional Pattern
  - CR/BQ/operations/OpenAPI schemas
  - PUML classes/attributes/relations
        |
        v
Candidate Reasoner (fan-out LangGraph)
        |
        v
Deterministic Ownership + Score Judge
        |
        v
Operation Resolver + Evidence Validator
        |
        v
Adversarial Judge / Reconciliation
        |
        v
Resultado estructurado + trazabilidad
```

## 5. Modelo canónico de conocimiento BIAN

No se deben indexar archivos crudos como chunks indiferenciados. La ingestión debe producir nodos normalizados y fragmentos derivados de esos nodos.

Entidades mínimas:

- `ServiceDomain`
- `BusinessCapability`
- `FunctionalPattern`
- `ControlRecord`
- `BehaviorQualifier`
- `Operation`
- `Endpoint`
- `Schema`
- `BusinessObject`
- `Field`
- `Relationship`
- `SourceEvidence`

Relaciones mínimas:

- `ServiceDomain HAS_CONTROL_RECORD ControlRecord`
- `ControlRecord HAS_BQ BehaviorQualifier`
- `ServiceDomain HAS_OPERATION Operation`
- `Operation TARGETS BehaviorQualifier|ControlRecord`
- `Operation IMPLEMENTED_BY Endpoint`
- `Operation ACCEPTS Schema`
- `Operation RETURNS Schema`
- `Schema HAS_FIELD Field`
- `ServiceDomain MANAGES BusinessObject`
- `ServiceDomain DEPENDS_ON ServiceDomain`
- todo nodo `SUPPORTED_BY SourceEvidence`

Cada registro debe incluir `bian_release`, URL/fichero fuente, commit, SHA-256, parser/version de esquema e instante de ingestión.

## 6. Estrategia técnica recomendada

### 6.1 Embeddings

Crear un puerto `EmbeddingProviderPort` y hacer el modelo configurable. `Qwen3-Embedding-8B` es una opción válida para español, inglés técnico y estructuras de código, pero no debe quedar hardcodeado.

Configuración inicial propuesta:

```yaml
retrieval:
  strategy: hybrid
  embedding_model: Qwen/Qwen3-Embedding-8B
  embedding_dimensions: 2048
  dense_top_k: 30
  lexical_top_k: 30
  fused_top_k: 20
```

Antes de fijar dimensión o modelo se debe ejecutar un benchmark con el corpus y las HUs doradas. La decisión de producción se toma por Recall@K, MRR/nDCG, latencia, costo y restricciones de despliegue, no por leaderboard general.

### 6.2 Recuperación híbrida

Combinar:

- coincidencia exacta y aliases deterministas;
- BM25 sobre nombre, propósito, Service Role, CR, BQ, operationId, resumen y campos;
- búsqueda densa sobre documentos canónicos multilingües;
- filtros por `bian_release`, tipo de nodo, Business Area/Domain y disponibilidad de evidencia;
- expansión de uno o dos saltos por relaciones `HAS_BQ`, `HAS_OPERATION`, `MANAGES` y `DEPENDS_ON`.

Fusionar rankings con Reciprocal Rank Fusion. Esto evita que escalas incompatibles de BM25 y cosine similarity produzcan un score artificial.

### 6.3 Reranker

Aplicar un cross-encoder multilingüe sobre pares `(intención de HU, paquete compacto del candidato)`. Debe rerankear, no decidir ownership ni crear operaciones.

Persistir por candidato:

- posición por canal;
- score denso;
- score BM25;
- score fusionado;
- score del reranker;
- razones/filtros de inclusión y exclusión.

### 6.4 Vector store

Implementar primero el puerto `KnowledgeIndexPort` y dos adaptadores posibles:

- **Qdrant**, recomendado para el piloto: operación vectorial directa, filtros de payload y despliegue separado sencillo.
- **PostgreSQL + pgvector**, recomendado si la plataforma ya opera PostgreSQL y se priorizan transacciones, gobierno y menor cantidad de componentes.

No implementar ambos en la primera entrega. Ejecutar una ADR con benchmark y escoger uno; el dominio no debe depender de la selección.

### 6.5 LangGraph

LangGraph ya existe y debe evolucionar, no sustituirse. Nodos propuestos:

1. `extraer_intencion`
2. `normalizar_intencion_bilingue`
3. `recuperar_candidatos_hibridos`
4. `fusionar_y_rerankear`
5. `expandir_evidencia_grafo`
6. `evaluar_candidato` en fan-out
7. `resolver_ownership_determinista`
8. `clasificar`
9. `seleccionar_operaciones`
10. `validar_operaciones`
11. `revisar_adversarial`
12. `reconciliar`
13. `publicar`

## 7. Cambio funcional prioritario antes del RAG avanzado

### 7.1 Corregir la semántica de ownership

Agregar una estructura determinista `DirectActionEvidence`:

```json
{
  "action": "enviar",
  "business_object": "notificación",
  "direct_responsibility": true,
  "scenario_refs": ["Escenario 1", "Escenario 2", "Escenario 3"],
  "matched_operation": "InitiateOutbound",
  "matched_lifecycle_verb": "Initiate",
  "evidence_refs": ["BQ:Outbound", "operation:InitiateOutbound"]
}
```

Regla general:

- si la HU ejecuta directamente acción+objeto;
- una operación oficial inicia/ejecuta ese ciclo de vida;
- existe trazabilidad a escenarios;
- y el Service Role no contradice la acción;

entonces una salida LLM `CONSUMED_DEPENDENCY` genera `OWNERSHIP_CONFLICT`. El sistema no debe descartarla silenciosamente. Puede:

1. corregir a `OWNED_CONTRACT` cuando la evidencia determinista supera el umbral fuerte; o
2. dejarla `UNRESOLVED` y bloquear publicación cuando la evidencia sea ambigua.

Para este caso, `enviar notificación` + `InitiateOutbound POST` + Service Role de generación automatizada de correspondencia constituye evidencia fuerte.

### 7.2 Desacoplar operaciones de `candidatos_directos`

Crear `candidatos_operacion_elegibles`, compuesto por candidatos con evidencia oficial y correspondencia acción/objeto suficiente. La selección de operaciones no debe depender exclusivamente de que el ownership ya haya sido clasificado correctamente.

Esto permite reportar una dependencia consumida con su operación oficial sin convertirla automáticamente en contrato owned.

### 7.3 Reinyectar candidatos omitidos

Mover la recuperación determinista/híbrida antes de `_h_preparar` y unir:

- candidatos del LLM;
- candidatos léxicos;
- candidatos vectoriales;
- candidatos por grafo;
- candidatos sugeridos por completitud.

Después resolver nombres, deduplicar, fusionar rankings y recién entonces aplicar `max_candidatos_hu`. Los omitidos actuales deben dejar de ser sólo un reporte posterior.

### 7.4 Score por etapas

No usar un único score para resolver recall, ownership y contrato. Introducir:

- `retrieval_score`: pertinencia para ser evaluado;
- `applicability_score`: relación negocio/evidencia;
- `ownership_confidence`: responsabilidad directa;
- `operation_support_score`: operación respaldada por OpenAPI/BOM;
- `decision`: resultado de reglas y umbrales separados.

El output debe conservar todos los componentes y la versión de la política.

## 8. Normalización e ingestión

Crear durante la fase de implementación:

```text
scripts/
  ingest_bian/
    README.md
    ingest.py
  rebuild_index/
    README.md
    rebuild.py
  evaluate_retrieval/
    README.md
    evaluate.py
  migrate_index/
    README.md
    migrate.py
```

Cada README debe documentar propósito, entradas, salidas, variables, ejemplos, idempotencia, rollback y validaciones.

Flujo de ingestión:

1. Parsear `SD.json` y jerarquía BIAN.
2. Parsear OpenAPI y extraer CR/BQ, operación, método, path, request/response schema.
3. Parsear PUML y extraer clases, atributos, enums y asociaciones.
4. Resolver identidades canónicas y aliases.
5. Validar referencias y generar un manifiesto de errores; no indexar relaciones inválidas.
6. Generar documentos de recuperación por entidad y por relación, con texto español/inglés controlado.
7. Calcular embeddings por lotes.
8. Upsert idempotente por `release + entity_type + canonical_id + source_sha`.
9. Construir índices lexical/vectorial y relaciones de grafo.
10. Ejecutar smoke tests contra consultas doradas.

## 9. Plan incremental de entrega

### Fase 0 — Línea base y observabilidad

- Congelar corpus de HUs doradas y resultados esperados.
- Añadir `run_id`, versiones de prompt/modelo/parser/política e índices usados.
- Registrar candidatos en cada frontera del pipeline.
- Crear métricas: Recall@5/10/20, candidate drop rate, ownership conflict rate, operation grounding rate y E2E pass rate.

Criterio: se puede explicar exactamente en qué nodo se perdió cada candidato.

### Fase 1 — Corrección determinista del falso negativo

- Introducir señales de acción directa y conflicto de ownership.
- Separar elegibilidad de operación de candidato directo.
- Reinyectar recuperación determinista antes del fan-out.
- Añadir E2E 2 aislada para notificaciones.
- Mantener E2E 1 sin cambios semánticos.

Criterio: la nueva HU produce `Correspondence / Outbound / POST / InitiateOutbound`; E2E 1 permanece verde.

### Fase 2 — Modelo canónico y parsers

- Normalizar JSON/OpenAPI/PUML al modelo BIAN.
- Versionar parsers y manifiestos.
- Validar integridad, duplicados, dangling refs y cobertura de operaciones/schemas.

Criterio: el 100% de operaciones cacheadas tiene SD, CR/BQ, método, path y fuente; las excepciones quedan reportadas.

### Fase 3 — Hybrid RAG

- Implementar BM25 + embeddings + filtros + RRF.
- Implementar puerto de índice y un adaptador de persistencia.
- Crear benchmark de retrieval usando casos positivos y hard negatives.

Criterio: Recall@10 >= 0.95 en el conjunto dorado y ningún caso actual retrocede.

### Fase 4 — Reranker y Graph RAG

- Rerank top 20 a top 5-8.
- Expandir sólo relaciones BIAN verificadas.
- Evitar que la expansión por grafo promueva dependencias temáticas sin evidencia directa.

Criterio: mejora de MRR/nDCG frente a Fase 3, sin reducir Recall@10 ni aumentar falsos owned.

### Fase 5 — Endurecimiento operativo

- Cache por hash de entrada/modelo/índice.
- Circuit breakers, timeouts, failover y presupuestos de llamadas.
- Modo reproducible con modelos fijados.
- Canary/shadow contra el pipeline actual.
- Rollback por feature flags: `legacy`, `hybrid`, `hybrid_graph`.

## 10. Estrategia de pruebas

### Unitarias

- equivalencias ES↔BIAN EN (`notificar/send/generate/correspondence`);
- parser OpenAPI para `InitiateOutbound` y jerarquía CR/BQ;
- RRF y deduplicación;
- ownership directo vs dependencia;
- operación elegible aunque el rol esté `UNRESOLVED`;
- filtros por release y evidencia;
- serialización completa de scores y provenance.

### Integración determinista sin red

- corpus BIAN cacheado real;
- embeddings fake reproducibles;
- reranker fake con orden conocido;
- índice efímero o contenedor controlado;
- pipeline LangGraph completo con respuestas LLM guionadas.

### E2E 1 — Datos personales (existente)

- usar exclusivamente `tests/resources/datos_personales`;
- conservar las aserciones actuales;
- no depender de `./HU` ni `./ejemplos`.

### E2E 2 — Notificaciones (nueva)

Crear `tests/resources/notificacion_actualizacion/` y `tests/test_e2e_notificacion_actualizacion.py` con estas aserciones:

1. `Correspondence` fue recuperado y evaluado.
2. No quedó `REJECTED` por `RELATED_NOT_OWNED` ni por un falso `CONSUMED_DEPENDENCY` incompatible con acción directa.
3. `InitiateOutbound` está en operaciones seleccionadas.
4. La operación tiene `method=POST`, `tipo=BQ`, `grupo=Outbound`.
5. `InitiateOutboundWithResponse` no sustituye a `InitiateOutbound` salvo evidencia explícita de respuesta esperada.
6. El resultado contiene fuentes, scores por etapa y trazabilidad a escenarios.

### Prueba anti-regresión de retrieval

Una tabla dorada de consultas debe incluir positivos y hard negatives. Para notificaciones:

- positivo: `Correspondence`;
- hard negatives: `Party Reference Data Directory`, `Fraud Evaluation`, `Customer Event History`, `Party Authentication`;
- `Party Reference Data Directory` puede aparecer como dependencia del cambio de datos, pero no debe desplazar a `Correspondence` para la acción principal de envío.

## 11. Gates de aceptación

No desplegar si falla cualquiera:

- suite offline completa;
- E2E 1;
- E2E 2;
- Recall@10 mínimo;
- operación oficial verificable;
- ninguna operación inventada;
- toda decisión `SELECTED` tiene evidencia oficial y trazabilidad;
- todo `OWNERSHIP_CONFLICT` queda resuelto o bloquea publicación;
- comparación shadow sin regresión en casos dorados existentes.

## 12. Riesgos y mitigaciones

- **LLM no determinista:** reglas verificables, modelos/versiones fijados y E2E repetida varias veces.
- **Embeddings no corrigen ownership:** separar retrieval de decisión y medir ambos.
- **Graph expansion introduce ruido:** sólo aristas con fuente y límite de saltos.
- **Cambios de BIAN:** índices separados por release y reconstrucción por manifiesto.
- **Costo/latencia:** cache, batch, shortlist y reranking sólo del top fusionado.
- **Vendor lock-in:** puertos para embeddings, reranker e índice.
- **Datos enviados a terceros:** clasificación de datos, redacción y aprobación explícita antes de E2E reales.

## 13. Orden recomendado de implementación

1. Fase 0 y E2E 2.
2. Corrección determinista de ownership/elegibilidad/reinyección.
3. Modelo canónico y parsers.
4. Benchmark de retrieval.
5. BM25 + embeddings + RRF.
6. Reranker.
7. Persistencia Qdrant o pgvector según ADR.
8. Expansión Graph RAG.
9. Shadow, gates y rollout gradual.

Este orden corrige primero el defecto comprobado y usa Hybrid/Graph RAG donde aporta valor real: cobertura, ranking, trazabilidad y navegación de evidencia, sin esperar que el vector search resuelva por sí solo una decisión contractual incorrecta.
