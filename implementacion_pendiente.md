# Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)

> Para quien retome esto en otra sesión: este documento asume que ya leíste
> [`CLAUDE.md`](CLAUDE.md) (arquitectura hexagonal + LangGraph del proyecto). Aquí solo se
> documenta lo que **falta**, con el contexto necesario para no tener que re-descubrirlo: qué
> problema resuelve, qué ventaja aporta, por qué se decidió así y cómo implementarlo paso a paso.

## 0. Estado al 2026-09-14 (leer esto primero)

Las Fases 3-5 se implementaron en esta iteración. Lo que sigue pendiente está al final, en la
sección 9, y es bastante distinto de lo que este documento suponía: **medir cambió el plan**.

| Pieza | Estado |
|---|---|
| Corpus dorado + benchmark | ✅ `scripts/evaluate_retrieval/` (7 consultas, con procedencia) |
| Modelo canónico BIAN | ✅ `src/dominio/grafo_bian.py` + `scripts/ingest_bian/` (26.044 nodos, 58.226 aristas) |
| Reconstrucción/migración de índice | ✅ `scripts/rebuild_index/`, `scripts/migrate_index/` |
| ADR vector store | ✅ `docs/adr/0001-vector-store.md` — gana `memoria`; Qdrant implementado y probado |
| Adaptador Qdrant | ✅ `src/adaptadores/salida/recuperador_qdrant.py` + volumen persistente |
| Reranker | ✅ `RerankerPort` + cross-encoder local con degradación segura |
| Graph RAG | ✅ expansión acotada por especificidad, con puentes auditables |
| Endurecimiento operativo | ✅ flags separados, presupuesto por HU, cache de reranking, canary |
| Texto indexado enriquecido | ✅ `texto_para_indexar()` pasa de ~370 a ~1.195 chars |

### Lo que la medición desmintió de este documento

1. **El gate "Recall@10 ≥ 0.95" no sirve como criterio único.** Se aprueba solo: en el caso real
   el SD correcto se recuperaba SIEMPRE como top-1 y la corrida terminaba en `UNRESOLVED` porque
   el revisor adversarial lo bloqueaba. El cuello no estaba en recuperar, sino en decidir.
2. **La fusión RRF empeora el recall** (0.71) frente al vectorial solo (0.86): mete el canal
   léxico —que en lenguaje natural acierta 0.29— con el mismo peso. Encender
   `retrieval_hibrido_habilitado` sin más sería una regresión.
3. **Un vector store externo no compra calidad** a esta escala: Qdrant da exactamente el mismo
   recall que el `InMemoryVectorStore`.
4. **La expansión por grafo ingenua es inservible**: 157 de 341 SD alcanzables en dos saltos,
   porque `Party` la modelan 125 SD. Hubo que filtrar por especificidad del nodo puente.
5. **Un reranker malo es peor que ninguno**: el respaldo léxico hundía Recall@10 de 0.71 a 0.14.
6. **El cross-encoder real no basta para justificar la cadena**: `bge-reranker-v2-m3` sube la
   cadena RRF de 0.71 a 0.86 de Recall@10 (MRR 0.370 -> 0.410), o sea rescata lo que la fusión
   rompió, pero el vectorial a secas sigue mejor (MRR 0.436, la mitad de `hard_negatives`
   delante). Arreglar la fusión va antes que añadir un modelo.

## 0-bis. Qué ya estaba resuelto antes de esta iteración (no reabrir sin motivo)

Del plan original de "recuperación y decisión BIAN híbrida", esto ya está implementado, probado y
en `main` (Fases 0-2 + una versión mínima de Fase 3):

- **Ownership determinista** (`src/dominio/clasificacion_historias.py::determinar_promociones` /
  `propuestos_promovidos` + finalización en `aplicar_hallazgos_adversariales`): un
  `CONSUMED_DEPENDENCY` con `dependency_kind=AUDIT_OR_NOTIFICATION` + evidencia fuerte se promueve
  a `OWNED_CONTRACT` cuando el revisor adversarial detecta `ACCION_DIRECTA_COMO_DEPENDENCIA` y no
  lo contradice con `DIRECTO_SIN_SERVICE_ROLE`. Al recalcular el score, casi siempre queda en
  banda tentativa (o incluso descartada) porque hereda rúbricas que el LLM calificó bajo mientras
  todavía enmarcaba el SD como dependencia — por eso, si la evidencia BIAN es oficial y verificada,
  la promoción se **finaliza** moviendo el SD a `candidatos_directos` con
  `SELECTED`/`OWNED_SELECTED` sin importar el score léxico crudo (la barra de promoción ya es más
  estricta que el umbral numérico de 0.90). Sin evidencia verificada, NO se fuerza "directo" — se
  anota la promoción pero se deja donde cayó (nunca se inventa un contrato sobre evidencia
  inexistente). Corrige el falso negativo real de "Notificar actualización de datos"
  (Correspondence/`InitiateOutbound`, que además terminaba en "tentativo" hasta que se agregó esta
  finalización). Regresión determinista: `tests/test_grafo_mapeo.py::TestGrafoMapeoPromocionOwnership`
  + `tests/test_clasificacion_historias.py::TestAplicarAdversarial` (casos con/sin evidencia
  verificada). E2E real (gateada): `tests/test_e2e_notificacion_actualizacion.py`.
- **Elegibilidad de operaciones desacoplada** (`candidatos_operacion_elegibles`): `OWNED_CONTRACT`
  directo O tentativo, no solo "directo" — sigue siendo útil como red de seguridad para el caso
  (más raro tras la finalización de arriba) de un SD promovido que se queda en tentativo por falta
  de evidencia BIAN verificada: aun así puede tener una operación oficial real que documentar.
- **Retrieval híbrido EN MEMORIA** (`_candidatos_retrieval_hibrido` en
  `mapear_historias_service_domain.py` + `src/dominio/fusion_rrf.py`): RRF sobre
  `RecuperadorLexico` (rapidfuzz, siempre) + `RecuperadorVectorial` (embeddings, si hay proveedor
  utilizable) — los mismos adaptadores que ya usaba `validar-sd`, ahora también disponibles para
  `mapear-historias`. Reinyecta candidatos que el LLM no propuso, antes del fan-out. **OFF por
  defecto** (`mapear_historias.retrieval_hibrido_habilitado: false` en `config.yaml`) — ver
  la sección 1 de este documento para la condición de encenderlo.
- **Observabilidad Fase 0**: `run_id` por corrida, `TRUNCATED_BY_MAX_CANDIDATOS_HU` /
  `OWNERSHIP_CONFLICT_UNRESOLVED` como incidencias explícitas (nada desaparece en silencio),
  `ResultadoMapeoHistorias.metricas` (`candidate_drop_rate`, `ownership_conflict_rate`,
  `operation_grounding_rate`), `desglose_score.retrieval_score` / `.operation_support_score`.
- **`infra/retrieval/docker-compose.yml`** (perfiles `qdrant` / `pgvector`, ninguno arranca por
  defecto) + su `README.md` — preparado para cuando la Fase 3 completa (benchmark) lo justifique.
  Ver la sección 3 de este documento.

Todo esto es aditivo: la suite completa (`'.venv/Scripts/python -m unittest discover -s tests'`,
140 tests) sigue en verde, incluida `test_arquitectura_hexagonal.py`.

## 1. Fase 3 — Hybrid RAG "de verdad" (validar y, si corresponde, encender por defecto)

### Problema

El retrieval híbrido de la sección 0 es una implementación honesta pero **no validada con
métricas**: no sabemos su Recall@K real sobre un corpus de consultas doradas, ni si el modelo de
embeddings por defecto (el que gane el failover de `routing.embedding_priority`: hoy Cohere →
Gemini → OpenRouter) es siquiera adecuado para este dominio (nombres BIAN + texto de negocio
ES/EN). Por eso quedó **OFF por defecto**: encenderlo sin medir es repetir el mismo error que el
plan original señaló — "los embeddings no arreglan una decisión de ownership", y tampoco se debe
asumir que arreglan recall sin medirlo.

### Ventaja de resolverlo

- Cobertura: candidatos que ni el LLM ni el 2º pase léxico (`deteccion_omitidos.py`) encuentran,
  especialmente en historias con vocabulario indirecto o sinónimos no cubiertos por
  `scoring_bian._EQUIVALENCIAS`.
- Una vez medido, se puede **encender por defecto con confianza** (hoy cualquiera que lo active
  vía `retrieval_hibrido_habilitado: true` lo hace a ciegas).
- Sienta la base objetiva para decidir si vale la pena un índice externo (Fase 3 completa) o si el
  `InMemoryVectorStore` ya alcanza (ver sección 3).

### Justificación de la secuencia

El plan original ya advertía: "Antes de fijar dimensión o modelo se debe ejecutar un benchmark con
el corpus y las HUs doradas. La decisión de producción se toma por Recall@K, MRR/nDCG, latencia,
costo y restricciones de despliegue, no por leaderboard general." Eso sigue sin hacerse.

### Pasos

1. **Corpus dorado de consultas** (`scripts/evaluate_retrieval/` — crear, con su propio
   `README.md`: propósito, entradas, salidas, idempotencia). Formato sugerido (YAML o JSON):
   ```yaml
   - hu: "Notificar actualización de datos"
     positivo: "Correspondence"
     hard_negatives: ["Party Reference Data Directory", "Fraud Evaluation", "Party Authentication"]
   - hu: "Crear pantalla de datos personales"
     positivo: "Party Reference Data Directory"
     hard_negatives: ["Customer Event History"]
   ```
   Arrancar con las HU que ya existen en `tests/resources/*/` (ya tienen su SD esperado
   documentado en el test E2E correspondiente) y sumar 10-15 más representativas de
   `HU - copia/` o de funcionalidades reales del banco.
2. **Script de evaluación** (`scripts/evaluate_retrieval/evaluate.py`): para cada entrada del
   corpus, corre `RecuperadorLexico`, `RecuperadorVectorial` (con cada modelo de
   `routing.embedding_priority` que tenga API key disponible) y la fusión RRF; calcula Recall@5,
   Recall@10, Recall@20, MRR. Sin llamadas LLM (no necesita evaluar candidatos, solo recuperarlos)
   — rápido y barato de correr repetidamente.
3. **Comparar modelos de embeddings** con datos, no con la tabla de "mejor MTEB" del comentario en
   `config.yaml`. Cohere `embed-v4.0` es la opción actual por defecto — puede seguir siéndolo si
   gana el benchmark, o no.
4. **Umbral de aceptación**: Recall@10 ≥ 0.95 sobre el corpus dorado, con CERO regresiones en los
   casos que ya pasan hoy sin retrieval híbrido (correrlo con y sin la fusión, comparar). Si pasa:
   - Cambiar el default de `retrieval_hibrido_habilitado` a `true` en `config.yaml`.
   - Actualizar `tests/support.py::config_test()` si algún test empieza a depender del nuevo
     default (revisar `test_grafo_mapeo.py` — hoy asume OFF por defecto en varias aserciones).
5. **Filtros adicionales** que el plan original pedía y aún no existen: por `bian_release`,
   Business Area/Domain, disponibilidad de evidencia. Hoy `RecuperadorLexico`/`RecuperadorVectorial`
   no filtran nada — recuperan sobre los 341 SD siempre. Es una extensión de
   `RecuperadorSemanticoPort.recuperar(consulta, k)` (añadir `filtros: dict | None = None` al
   puerto, opcional y con default `None` para no romper compat).

## 2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión

### Problema

Hoy la evidencia BIAN vive en varios formatos ad-hoc dentro de `docs/` (`SD.json`,
`bian-business-areas.json`, `bian-cache/*.json` con su propio `cache_version`, `bian-diagrams/puml-bom/*.puml`)
que cada adaptador (`CatalogoJson`, `CatalogoBianCache`, `CatalogoBomPuml`) parsea por su cuenta.
Funciona, pero no hay un modelo de nodos/relaciones unificado sobre el que:
- expandir por grafo (Fase 4: `HAS_BQ`, `HAS_OPERATION`, `MANAGES`, `DEPENDS_ON`);
- indexar de forma consistente para retrieval (hoy cada adaptador decide su propio
  `texto_para_indexar()`);
- auditar de dónde vino cada dato con un formato de procedencia uniforme (hoy cada fuente tiene su
  propio `evidence`/`EvidenciaBian` con campos parecidos pero no idénticos).

### Ventaja

- Prerrequisito real de la Fase 4 (Graph RAG): sin nodos/relaciones explícitos no hay grafo que
  expandir, solo heurísticas ad-hoc.
- Un solo lugar para validar integridad (schemas duplicados, referencias colgantes, cobertura de
  operaciones) en vez de que cada adaptador tolere silenciosamente huecos.
- Manifiesto de ingestión versionado = reproducibilidad real entre releases BIAN.

### Justificación

Plan original, sección 5 (entidades: `ServiceDomain`, `BusinessCapability`, `FunctionalPattern`,
`ControlRecord`, `BehaviorQualifier`, `Operation`, `Endpoint`, `Schema`, `BusinessObject`, `Field`,
`Relationship`, `SourceEvidence`) y sección 8 (scripts de ingestión).

### Pasos

1. Definir el modelo canónico como **dataclasses/pydantic puros en `src/dominio/`** (no una base
   de datos todavía) — sigue la regla de arquitectura hexagonal del proyecto: el dominio no conoce
   adaptadores. Un buen punto de partida: extender `ModeloBomPuml`/`SchemaBom`/`OperacionBian`
   (ya existen en `src/dominio/historias.py`) en vez de crear un modelo paralelo — son subconjuntos
   parciales del mismo grafo, no algo distinto.
2. `scripts/ingest_bian/` (README + `ingest.py`): parsea `SD.json` + `bian-business-areas.json` +
   `bian-cache/*.json` + `bian-diagrams/puml-bom/*.puml`, resuelve identidades canónicas (ya existe
   `normalizar()` en `src/dominio/normalizacion.py` — reusar, no reinventar), valida referencias
   (BQ sin CR padre, operación sin schema, etc.) y genera un **manifiesto de errores** (nunca
   indexar una relación inválida en silencio). Idempotente: mismo input -> mismo output, upsert
   por `release + entity_type + canonical_id + source_sha` (los `source_sha256`/`source_commit_sha`
   YA existen en `EvidenciaBian` y en el `cache_version: 2` de `bian-cache/` — reusar esos hashes
   como clave de idempotencia, no inventar otro esquema de versionado).
3. `scripts/rebuild_index/` (README + `rebuild.py`): reconstruye el índice de retrieval (léxico +
   vectorial, y el índice de grafo cuando exista) desde el modelo canónico. Debe poder correr sin
   red (todo ya está en `docs/`).
4. `scripts/migrate_index/` (README + `migrate.py`): mueve un índice de una release BIAN a otra
   sin perder metadatos de procedencia. Puede esperar hasta que haya más de una release en juego —
   hoy todo es `14.0.0`.
5. Documentar en cada README: propósito, entradas, salidas, variables de entorno, ejemplo de uso,
   idempotencia, rollback (cómo revertir un `rebuild`/`migrate` fallido) y validaciones que corre.

## 3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide

### Problema

El plan original proponía Qdrant o pgvector desde el diseño. La validación de esta implementación
concluyó que, a esta escala (341 SD; unos pocos miles de nodos con el modelo canónico completo),
**no hay evidencia de que un `InMemoryVectorStore` sea insuficiente** — es el mismo patrón que ya
usa `validar-sd` en producción. Introducir un servicio externo antes de medir sería pagar
complejidad operativa (arrancar un contenedor, gestionar conexión, un modo de fallo nuevo) sin
saber si compra algo.

### Ventaja de resolverlo (condicional)

Si el corpus canónico crece mucho (todas las relaciones de la Fase 2, todos los campos, todas las
releases BIAN en paralelo) o si se necesita compartir el índice entre procesos/máquinas (no solo
una corrida CLI local), un vector store externo sí aporta: filtros de payload más ricos (Qdrant) o
transacciones y menos piezas nuevas si ya hay Postgres en la plataforma (pgvector).

### Justificación

Plan original, sección 6.4: "No implementar ambos en la primera entrega. Ejecutar una ADR con
benchmark y escoger uno." Esto NO se ha hecho todavía porque el benchmark de la sección 1 de este
documento (prerrequisito) tampoco se ha hecho.

### Pasos

1. Correr el benchmark de la sección 1 sobre el corpus canónico completo (post Fase 3, sección 2)
   y medir: tamaño del índice, latencia de carga en frío del `InMemoryVectorStore`, Recall@10.
2. Si (y solo si) hay una razón medible para no seguir en memoria, escribir una ADR corta
   (`docs/adr/00XX-vector-store.md` o donde el proyecto guarde decisiones) comparando Qdrant vs.
   pgvector con los criterios reales (no genéricos): latencia, huella operativa, si la plataforma
   ya opera Postgres, filtros necesarios.
3. Implementar **un solo** adaptador (`RecuperadorQdrant` o `RecuperadorPgvector`) del puerto ya
   existente `RecuperadorSemanticoPort` (`src/aplicacion/puertos/recuperador.py`) — el dominio y la
   aplicación no cambian, es exactamente el mismo puerto que hoy cumplen `RecuperadorLexico` y
   `RecuperadorVectorial`.
4. Levantar el motor elegido con `infra/retrieval/docker-compose.yml` (ya existe, con perfiles
   `qdrant` y `pgvector` — ver su `README.md` para el comando exacto). Añadir la dependencia nueva
   (`qdrant-client` o `psycopg[binary]`/`pgvector`) a `requirements.txt` SOLO del adaptador elegido.
5. Tests de integración del adaptador nuevo pueden usar el compose directamente (no hace falta
   testcontainers para un proyecto de este tamaño) — levantar el servicio en CI, correr contra él,
   apagarlo. Mantener la suite principal (`unittest discover -s tests`) sin dependencia del
   contenedor: el adaptador nuevo se prueba aparte, igual que hoy `test_embeddings_failover.py` no
   depende de red real.
6. Wiring en `contenedor.py`: nuevo config `mapear_historias.vector_store: memoria|qdrant|pgvector`
   (default `memoria`), rama en `_recuperadores_hibridos` — el resto del pipeline no se entera.

## 4. Fase 4 — Reranker + Graph RAG

### Problema

RRF sobre léxico+vectorial da un top-K razonable pero no reordena por relevancia semántica fina
(dos candidatos con score de fusión parecido pueden estar muy lejos en relevancia real). Tampoco
hay expansión por grafo: un SD relacionado por `DEPENDS_ON`/`MANAGES` a un candidato fuerte nunca
aparece si ni el LLM ni el retrieval directo lo mencionan.

### Ventaja

- Reranker: mejora precisión (MRR/nDCG) en el top-5-8 que realmente llega a `evaluar_candidato`
  (cada slot cuesta una llamada LLM — mejor precisión ahí es directamente menos costo desperdiciado
  evaluando candidatos irrelevantes).
- Graph RAG: encuentra candidatos que NINGÚN canal léxico/vectorial/LLM iba a proponer porque la
  relación es estructural (p. ej. una dependencia declarada en el propio BOM BIAN), no textual.

### Justificación

Plan original, secciones 6.3 y 6.5 (parte de Graph RAG), y riesgo ya identificado: "Graph expansion
introduce ruido: sólo aristas con fuente y límite de saltos" — la expansión debe ser sobre
relaciones YA verificadas del modelo canónico (Fase 3, sección 2), nunca inferida por similitud
temática, para no repetir el error de origen (confundir "recuperable" con "aplicable").

### Pasos

1. **Requiere la Fase 3 sección 2 (modelo canónico) terminada** — sin relaciones tipadas y con
   fuente, no hay grafo que expandir de forma segura.
2. **Reranker**: preferir un cross-encoder local (p. ej. vía `sentence-transformers`, sin API) o el
   endpoint de rerank de Cohere (ya hay `COHERE_API_KEY` en el proyecto, solo para embeddings hoy —
   revisar límites del trial). **Evitar** usar otro LLM del failover como reranker: el proyecto ya
   tiene problemas de cuota documentados (Groq 413 en catálogos grandes, Gemini 20 req/día,
   HF ~$0.10/mes) — sumar otra llamada LLM por historia empeora eso, no lo mejora.
   - Nuevo puerto `RerankerPort` (`aplicacion/puertos/`) + adaptador; se aplica DESPUÉS de la
     fusión RRF, ANTES de construir `PaqueteEvidenciaCandidato` en `_h_preparar`.
   - Reordena, nunca decide ownership ni crea operaciones — mismo principio que ya rige todo el
     pipeline (el reranker es otro "recuperador", no otro "juez").
3. **Graph RAG**: expansión de 1-2 saltos sobre relaciones del modelo canónico
   (`HAS_BQ`, `HAS_OPERATION`, `MANAGES`, `DEPENDS_ON`) a partir de los candidatos ya recuperados.
   Cada arista expandida se marca con su propio `origen_candidato` (añadir `"graph_rag"` al
   `Literal` `OrigenCandidato` en `src/dominio/historias.py`, mismo patrón que
   `"retrieval_hibrido"`) para que quede trazable de dónde vino.
4. **Criterio de aceptación** (igual que el plan original): mejora de MRR/nDCG sobre la Fase 3
   medida, sin reducir Recall@10 ni aumentar falsos `OWNED_CONTRACT` — correr
   `scripts/evaluate_retrieval/evaluate.py` antes/después y comparar explícitamente.

## 5. Fase 5 — Endurecimiento operativo

### Problema

Una vez que retrieval híbrido (y, eventualmente, un vector store externo + reranker) esté en el
camino por defecto, el pipeline tiene nuevos modos de fallo que hoy no existen: un proveedor de
embeddings caído a mitad de corrida, un índice desactualizado respecto a `bian-cache/`, latencia
variable del reranker.

### Ventaja

Producción segura: la corrida no se cae ni produce resultados silenciosamente degradados cuando
una pieza nueva falla; se puede comparar contra el comportamiento anterior antes de confiar en el
nuevo por defecto.

### Justificación

Plan original, sección 9 Fase 5, y sección 12 (riesgos) — "Costo/latencia" y "Vendor lock-in" ya
están parcialmente mitigados por diseño (puertos `RecuperadorSemanticoPort` desde el día uno), pero
falta lo operativo.

### Pasos

1. **Cache por hash de entrada/modelo/índice**: `RecuperadorVectorial` ya cachea el índice por
   modelo activo (`_ruta_cache` en `recuperador_vectorial.py`) — extender el mismo patrón a
   resultados de reranking si se implementa (Fase 4).
2. **Circuit breakers / timeouts / presupuestos de llamadas**: hoy el failover LLM
   (`ChatConFailover`) ya maneja reintentos transitorios y agotamiento de proveedores — el
   retrieval híbrido y el reranker deben degradar con la MISMA filosofía ya usada en
   `_recuperadores_hibridos` (si un componente falla, seguir con lo que quede, nunca abortar la
   corrida completa por un proveedor de embeddings caído). Formalizar un presupuesto de tiempo
   máximo por HU para que un proveedor lento no dispare la latencia total.
3. **Modo reproducible con modelos fijados**: ya existe para LLM (`llm.seed`, `--proveedor`
   pinneado) — extenderlo a embeddings/reranker: permitir fijar explícitamente el modelo de
   embeddings en vez de dejar que gane el failover por precisión, para benchmarks reproducibles.
4. **Canary/shadow contra el pipeline actual**: correr `retrieval_hibrido_habilitado: true` en
   paralelo al comportamiento actual (`false`) sobre el mismo lote de HU, diffear
   `service_domains_consolidados`, y solo entonces decidir el rollout. El propio flag
   `retrieval_hibrido_habilitado` YA es el mecanismo de rollback — no hace falta construir uno
   nuevo, solo el proceso de comparación (puede vivir como otro modo de
   `scripts/evaluate_retrieval/`).
5. **Feature flags legacy / hybrid / hybrid_graph**: hoy solo existe el flag binario
   `retrieval_hibrido_habilitado`. Si la Fase 4 (Graph RAG) se implementa, añadir un tercer estado
   (p. ej. `mapear_historias.graph_rag_habilitado`, independiente del híbrido) en vez de una sola
   bandera que mezcle ambas cosas — permite activar retrieval híbrido sin grafo, o ambos.

## 6. Gates de aceptación (heredados del plan original, aplican a partir de aquí)

No avanzar de fase sin:
- Suite offline completa en verde (`unittest discover -s tests`).
- `test_e2e_datos_personales.py` Y `test_e2e_notificacion_actualizacion.py` en verde (correr con
  `EJECUTAR_E2E=1` antes de cualquier cambio que toque `clasificacion_historias.py`,
  `scoring_bian.py`, o retrieval).
- Recall@10 ≥ 0.95 en el corpus dorado (Fase 3) antes de cambiar cualquier default.
- Ninguna operación inventada (`operacion_evidencia_verificable` ya lo verifica — no relajarlo).
- Toda promoción de ownership queda anotada (`OWNERSHIP_PROMOTED_BY_ADVERSARIAL`) o bloqueada
  (`OWNERSHIP_CONFLICT_UNRESOLVED`) — nunca silenciosa.
- Comparación shadow sin regresión en los casos dorados existentes antes de cambiar un default.

## 7. Dónde quedó cada pieza (referencia rápida)

| Pieza | Archivo | Estado |
|---|---|---|
| Promoción de ownership | `src/dominio/clasificacion_historias.py` | ✅ hecho |
| Elegibilidad de operaciones | `src/dominio/clasificacion_historias.py::candidatos_operacion_elegibles` | ✅ hecho |
| Fusión RRF | `src/dominio/fusion_rrf.py` | ✅ hecho |
| Reinyección híbrida (servicio) | `src/aplicacion/servicios/mapear_historias_service_domain.py::_candidatos_retrieval_hibrido` | ✅ hecho, OFF por defecto |
| Wiring del flag | `src/configuracion/contenedor.py::_recuperadores_hibridos`, `config.yaml` | ✅ hecho |
| Observabilidad Fase 0 | `_resultado_mapeo` / `_metricas` en el servicio | ✅ hecho |
| Corpus dorado + benchmark | `scripts/evaluate_retrieval/` | ❌ pendiente — sección 1 |
| Modelo canónico + ingestión | `scripts/ingest_bian/`, `scripts/rebuild_index/`, `scripts/migrate_index/` | ❌ pendiente — sección 2 |
| ADR + adaptador vector store externo | nuevo adaptador de `RecuperadorSemanticoPort` | ❌ pendiente, condicional al benchmark — sección 3 |
| `infra/retrieval/docker-compose.yml` | perfiles `qdrant`/`pgvector` | ✅ preparado, sin usar todavía |
| Reranker | nuevo `RerankerPort` | ❌ pendiente — sección 4 |
| Graph RAG | expansión sobre modelo canónico | ❌ pendiente, requiere sección 2 — sección 4 |
| Endurecimiento operativo | cache/circuit breakers/canary | ❌ pendiente — sección 5 |


## 9. Pendiente de verdad (2026-09-14, revisado tras implementar los 6 puntos)

### Hecho en esta iteración

| # | Qué | Dónde | Estado por defecto |
|---|---|---|---|
| 1 | Caché de nodos en disco + `defer` + durabilidad | `CacheNodosArchivo`, `cache_policy` en los 7 nodos LLM | OFF (`cache_nodos_habilitado`) |
| 2 | Canal disperso BM25 con puente ES->EN + RRF con `k` y pesos | `src/dominio/bm25.py`, `vocabulario_bian.py`, `fusion_rrf.py` | OFF (`retrieval_canal_lexico: rapidfuzz`, pesos 1.0) |
| 3 | CAG escalonado (catálogo completo en el prompt) | `formatear_catalogo(..., chars_negocio)` | OFF (`cag_habilitado`) |
| 4 | Corpus por capas + generador determinista + skill de etiquetado | `corpus_dorado.yaml`, `generar_casos_nombre.py`, `.claude/skills/corpus-dorado-bian/` | n/a |
| 5 | Grafo como confirmación determinista del conflicto de ownership | `GrafoBian.objetos_compartidos`, `confirmar_conflictos_por_grafo` | OFF (`grafo_senales_adversarial`) |
| 6 | CRAG: una vuelta correctiva si el lote de evidencia es débil | `_vuelta_correctiva` | OFF (`crag_reintento_habilitado`) |

Lo que la medición de esta iteración añadió al diagnóstico:

- **El canal disperso no fallaba por pesos, fallaba por idioma.** HU en español, catálogo BIAN
  íntegramente en inglés: sin puente ES->EN, BM25 recupera CERO. Con él, `hu_real` pasa de 0.083 a
  0.281 de MRR, y fusionado con el denso a 0.573 — por encima del mejor canal individual (0.342),
  que es lo que la fusión prometía y nunca cumplía.
- **Cada caso de uso quiere su canal disperso**: rapidfuzz gana en nombres (MRR 1.000 exacto /
  0.945 con erratas), BM25 gana en lenguaje natural. Un único canal "léxico" para los dos era el
  error de fondo.
- **La fusión es un intercambio**: +MRR y −1 `hard_negative` por delante, a cambio de un positivo
  que se cae del top-10 (R@10 0.83 -> 0.67).
- **El promedio global del corpus engañaba**: el canal léxico mide 0.95 de Recall@10 global y 0.17
  en `hu_real`. Por eso el corpus ahora tiene capas y el informe las reporta por separado.

### Retomar aquí cuando haya más HU etiquetadas (protocolo, 2026-09-15)

Todo lo implementado está en `origin/main` y **apagado por defecto**. Lo que falta no es código:
son tres decisiones que necesitan datos que hoy no existen. Este es el orden exacto para cuando
lleguen más Historias de Usuario del banco.

**Paso 0 — meter las HU nuevas en el corpus** (lo único que no se puede automatizar). Protocolo
completo en la skill `corpus-dorado-bian`. Resumen de lo que NO vale: inventar consultas, usar
como consulta el texto que el sistema indexa (`role_definition`/`examples_of_use`/`features` — es
circular), o presentar el total de 97 casos como cobertura de negocio (91 son consultas-nombre
generadas). El positivo se confirma con evidencia —una corrida validada, un `expected-result.json`
curado, o el Service Landscape + la Semantic API—, nunca de memoria. Cada caso lleva su
`procedencia`.

```bash
# 1. Cuántas consultas de negocio hay realmente (hoy: 6)
.venv/bin/python -c "import yaml,collections;c=yaml.safe_load(open('scripts/evaluate_retrieval/corpus_dorado.yaml'));print(collections.Counter(x['tipo'] for x in c['casos']))"

# 2. Recuperación por capa — nunca el promedio global (el canal léxico mide 0.95 global y 0.17 en hu_real)
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --tipo hu_real
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --barrido rrf-bm25 --tipo hu_real
```

**Paso 1 — decidir el canal disperso y los pesos de la fusión.** Con ~30 consultas `hu_real` ya
se puede: hoy el mejor punto medido (`k=20`, peso disperso `0.25`, MRR 0.608) está sobreajustado
a 6 casos, donde un acierto mueve 0.17. Si el barrido confirma la forma con más datos, cambiar
`retrieval_canal_lexico: bm25` + pesos en `config.yaml` deja de ser una apuesta.

**Paso 2 — canary con LLM real, flag por flag y REPETIDO.** Un canary de una pasada mide ruido:
la varianza medida es de 3 fallos en 11 corridas (27%) con el MISMO modelo. Es barato porque la
caché de nodos solo repaga lo que cambió.

```bash
.venv/bin/python scripts/evaluate_retrieval/canary.py --hu ./HU \
    --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json \
    --base config.yaml --candidata candidata.yaml --proveedor ollama
```

**Paso 3 — E2E como medición, no como sorteo.** `E2E_REPETICIONES=N` corre cada caso N veces y
exige mayoría, reportando el marcador.

```bash
EJECUTAR_E2E=1 E2E_REPETICIONES=3 MAPEO_CONFIG=/ruta/candidata.yaml \
    .venv/bin/python -m unittest discover -s tests -p "test_e2e_*.py" -v
```

Cuántas repeticiones hacen falta, con los números que ya tenemos: bajo una tasa de fallo del 27%,
**6 corridas en verde tienen ~15% de probabilidad por azar** — que es exactamente lo que pasó el
2026-09-15 y por eso NO se declaró ninguna mejora. Para distinguir una mejora real del ruido hacen
falta del orden de **15-20 corridas** por configuración. Con 3 repeticiones la E2E sirve de gate
diario; con 15+, sirve para decidir si un flag se enciende por defecto.

**Qué mirar además del verde/rojo** (todo sale del JSON de cada corrida, sin instrumentar nada):
`historias_sin_contrato`, `operation_coverage_rate`, `operation_mapping_empty`,
`ownership_conflict_rate_respaldado` y los `reason_codes`
`OWNERSHIP_PROMOTED_BY_DECLARED_ACTION` / `DOWNGRADED_NO_OPERATION_ANCHORED` — si el primero
aparece, la red de seguridad del ownership está actuando; si el segundo aparece mucho, el modelo
está reclamando contratos que no puede sostener con una operación.

### Lo que sigue pendiente

1. **Correr el canary con LLM real** (`canary.py --proveedor ollama`) flag por flag —ahora barato,
   porque la caché de nodos solo repaga lo que cambió— y solo entonces cambiar un default. Ningún
   flag de esta iteración se enciende sin eso.
2. **Ampliar la capa `hu_real` a ~100 consultas etiquetadas.** Sigue siendo el cuello: son 6 y no
   se fabrican. Protocolo en la skill `corpus-dorado-bian`. Las capas `nombre_canonico` /
   `nombre_deformado` (91 casos) son regresión objetiva de `validar-sd`, NO poder estadístico
   sobre el problema de negocio.
3. ~~Volver a medir el reranker~~ **HECHO (2026-09-14)**: re-medido sobre `hu_real` con el canal
   disperso ya arreglado, el cross-encoder **empeora**: R@1 0.50 -> 0.17, MRR 0.573 -> 0.300 y de
   1 a 4 `hard_negatives` por delante, a cambio de R@10 0.67 -> 0.83. Su número bueno anterior
   (0.71 -> 0.86) era rescate de la fusión rota. Como cada candidato por delante cuesta una
   llamada LLM, la cabeza del ranking vale más que la cola: **`reranker_habilitado` se queda en
   `false`**. Se probó además la hipótesis del texto (`--barrido-texto`, 10 variantes de
   `texto_prosa()`): la prosa sube el MRR de 0.300 a 0.417 y baja los negativos de 4 a 2, pero
   **ninguna variante llega a 0.573 / 1 negativo de no reordenar**. El pipeline pasa ya `prosa` en
   vez del volcado del índice, para que encender el flag no reparta además el peor texto. Reabrir
   el reranker exigiría otra vía (otro modelo, o texto escrito a mano por SD), no otra variante de
   lo que el landscape ya publica.
4. **Medir CAG contra retrieval en la capa `hu_real`** con LLM real: el coste en tokens está
   medido (~27k -> ~48k -> ~54k), el efecto en la decisión no.
5. **Encadenar el enriquecedor del landscape a `scripts/generate_matrix_view/`**, que hoy lo
   pisaría al regenerar.
6. **`ownership_conflict_rate`** sigue metiendo en el denominador hallazgos sobre SD ya
   descartados. La señal de grafo da una tasa paralela que descuenta el ruido
   (`ownership_conflict_rate_respaldado`), pero no arregla el denominador.
7. **Entrenar un modelo propio** sigue descartado: 6 HU etiquetadas. El punto 2 es el
   prerrequisito.
8. **pgvector** no se implementa mientras la ADR no cambie.
9. ~~Checkpointer persistente~~ **HECHO (2026-09-15)**: `durabilidad: sync|async` abre una base
   SQLite que se crea si no existe y nunca se versiona, y `--reanudar <thread_id>` continúa una
   corrida muerta desde su último checkpoint sin repetir lo hecho. Coste medido: disco (~19 MB por
   HU), no latencia. **Lo que falta de aquí**: el `interrupt`/human-in-the-loop para el
   `UNRESOLVED` bloqueado — la base técnica está, pero exige decidir antes un protocolo (cómo para
   la corrida, cómo responde el humano, cómo se reanuda con esa decisión), y eso cambia el
   contrato del CLI.
10. **Decidir qué exigirle a la E2E como gate**: `E2E_REPETICIONES` ya permite medir en vez de
    sortear, pero cuántas repeticiones se exigen en cada contexto (diario vs. decisión de default)
    sigue sin fijarse.

### Cerrados el 2026-09-14 (los dos "extras menores" que quedaban anotados)

- **`bom_diagram` del landscape en vez de deducir la ruta por convención.** `CatalogoJson.rutas_bom_puml()`
  expone la `bom_diagram.puml_path` que declaran 265 de los 341 SD, y `CatalogoBomPuml` la prefiere,
  con el slug kebab-case solo como respaldo. **No mueve ningún resultado**: se verificó que las dos
  formas coinciden en los 265 casos, que las 265 rutas existen, que ninguno de los 76 SD sin
  `bom_diagram` tiene un PUML que la convención encontrara, y que `bian_source_url` del landscape es
  idéntico al `' BIAN source:` que ya trae cada `.puml` (de donde sale hoy `ModeloBomPuml.source_url`).
  Lo que compra es que una regeneración del landscape o de los diagramas que cambie el criterio de
  nombres falle en `tests/unit_test/test_catalogo_bom_puml.py` en vez de dejar al paquete de evidencia
  sin BOM en silencio (`objeto_bom` a 0.0, sin error ni log). Quedan 7 `.puml` huérfanos
  (`ach-operations`, `correspondent-bank-operations`, `direct-debit-collection`, `direct-debits-service`,
  `payment-execution`, `payment-instruction`, `payment-order`): ningún SD de v14 los referencia ni los
  alcanzaría por convención — son diagramas de nombres que el release renombró, no una pérdida.
- **Las dos `documentation` de `Partner Management` y `Brand Management`.** El criterio BIAN que las
  resuelve es estructural, no un juicio caso a caso: `documentation` es la ficha del Service Domain
  (`** 1. Role ** / ** 2. Examples of use ** / ...`), así que su sección 1 tiene que decir lo mismo que
  el `role_definition` de ese SD. El valor que aplicó el enriquecedor cumple; el que traía el landscape
  era la definición de una *capability* —otro artefacto BIAN—. Hoy coinciden **338/338** de los SD que
  traen ambos campos, y lo fija
  `test_catalogo_bian_unico.py::test_la_documentacion_describe_al_service_domain_y_no_a_otra_cosa`.
  Los 3 no comparables (`Card Transaction Tracking` sin `documentation`; `Operational Risk Models` y
  `Sales Planning` sin `role_definition`) no los publica ninguna de las dos fuentes oficiales.

---

## 10. Red 2 del routing jerárquico — inyección por retrieval (NO implementada, a propósito)

> **Cuándo abrir esto:** solo si `metricas.routing_*` o los E2E muestran que el nodo 2a está
> perdiendo candidatos. Mientras no ocurra, implementarlo es añadir una pieza que no arregla nada
> — exactamente el error que este documento ya cometió una vez con la fusión RRF.

### El riesgo que introdujo el routing

Partir el paso de candidatos en `enrutar_dominios` (2a) + `generar_candidatos` (2b) creó **un modo
de fallo que antes no existía**: un Business Domain que 2a no elige es invisible para 2b, así que
ningún Service Domain de ese dominio puede proponerse. Con el catálogo completo eso era imposible
por construcción.

Medido sobre los tres casos E2E, los candidatos reales de una HU abarcan **3, 4 y 5 Business
Domains** y hasta **4 Business Areas**. El patrón: el **propietario** cae en 1-2 dominios
(`Customer Management`, `Document Management and Archive`), pero las **dependencias** —auth,
permisos, riesgo, auditoría, notificación— viven dispersas en `Cross Channel`, `External Agency` y
`Account Management`. Un router que solo persiga al propietario las pierde todas.

### Las tres redes que SÍ están activas

1. **En el prompt de 2a**: exige `dependency_domains` (uno por cada `external_dependency`) y un
   mínimo de 3 Business Domains, con la instrucción explícita de que el error caro es excluir.
2. **En el filtrado determinista** (`_filtrar_por_dominios`): un nombre que no resuelve contra la
   taxonomía real **no filtra nada** (incidencia `ROUTING_DOMINIO_NO_RESUELTO`), y si no resuelve
   ninguno se usa el **catálogo completo** (`ROUTING_SIN_DOMINIOS`). Degradar, no morir.
3. **Aguas abajo**: `revisar_completitud` (nodo 3) sigue viendo el índice global de los **341**
   nombres y puede devolver `missing_candidates`; y `preparar_candidatos` resuelve nombres contra
   los 341, no contra el recorte. Un SD de un dominio no enrutado que nombre el nodo 3 entra igual.
   Lo fija `tests/unit_test/test_routing_jerarquico.py::test_un_candidato_de_otro_dominio_se_resuelve_igual`.

### La red 2, si hiciera falta

Correr los recuperadores ya implementados (`RecuperadorBM25` / `RecuperadorLexico`, en memoria,
sin API ni Qdrant) sobre los **341** SD con la consulta que ya usa el retrieval híbrido
(`business_actions` + `business_objects` + `capacidades_funcionales` + `outcomes` de `intencion`),
y **forzar la inclusión en el catálogo de 2b** de los top-K cuyo Business Domain no fue elegido.

Por qué encaja aquí y no antes: con el catálogo completo el retrieval **solo puede empatar** — el
candidato correcto ya estaba en el prompt, así que inyectarlo no añade nada (por eso
`retrieval_hibrido_habilitado` sigue en `false` y medirlo no lo justificó). Con routing pasa a
cubrir el único fallo nuevo, que es justo lo que un canal disperso sabe hacer: encontrar por
vocabulario algo que la taxonomía descartó.

Boceto:

```python
# en _h_enrutar, después de _filtrar_por_dominios
rescatados = self._rescate_por_retrieval(estado, filtrado)   # top-K fuera de los dominios elegidos
filtrado += rescatados
# incidencia por cada uno: DOMINIO_DESCARTADO_CON_SENAL (qué SD, qué dominio, qué score)
```

Puntos a respetar si se implementa:

- **Tope propio** (`routing_rescate_max`), no reutilizar `retrieval_max_inyectados`: son dos
  presupuestos distintos y hay que poder medirlos por separado.
- **Presupuesto de tiempo**: reutilizar `_Presupuesto`, como el resto del retrieval opcional.
- **Flag propio** (`routing_rescate_habilitado`), OFF por defecto, para poder comparar corridas
  con y sin red.
- **Incidencia siempre**, aunque el rescate esté apagado: saber *cuántas veces habría rescatado*
  es el dato que dice si hace falta. Esa parte —medir sin inyectar— es más barata que la red y
  debería ir primero.
- El coste en tokens es real: cada SD rescatado son ~189 tokens con el texto completo.

### Cómo decidir si hace falta

Sin corpus dorado no hay tasa de acierto del router. Lo que sí se puede medir hoy:

| Señal | Dónde | Qué significa |
|---|---|---|
| `routing_fallback_catalogo_completo` > 0 | `metricas` | el router no resolvió nada; no es pérdida, es coste |
| `routing_dominios_no_resueltos` alto | `metricas` | el modelo inventa nombres de dominio → revisar el prompt de 2a, no añadir red |
| `HISTORIA_SIN_CONTRATO` sube al encender routing | `incidencias` | **esta es la señal de alarma real** |
| Un E2E deja de encontrar su SD | `tests/e2e/` | idem, y con caso reproducible |

Regla estadística del proyecto: una tanda en verde no es una mejora, y una en rojo tampoco es una
regresión. La varianza medida de la suite E2E es del 27%; hacen falta 15-20 corridas por
configuración para distinguir señal de ruido (`E2E_REPETICIONES=15`).
