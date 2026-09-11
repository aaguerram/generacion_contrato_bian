# CLAUDE.md — generacion_contrato_ia_v2

Dos casos de uso sobre BIAN Service Domains (**LangGraph + LLM multi-proveedor**, arquitectura hexagonal).
**Toda la evidencia BIAN vive dentro de `generacion_contrato_ia_v2/docs/`** (nunca se lee del
proyecto hermano `architecture/`):
- `SD.json` = 341 SD del Service Landscape v14 · `bian-business-areas.json` = jerarquía Business Area/Domain
- `bian-operation-catalogs.json` = fallback legado (9 SD con operaciones CR/BQ)
- `bian-cache/release14.0.0/<SD>.json` = **cache-first del OpenAPI oficial** por SD (`cache_version: 2`):
  operaciones CR **y** BQ (`parent_control_record`), `schemas` (nombres) + `schemas_detalle`
  (cuerpo: properties/`$ref`/enum values), `request_schema`/`response_schema` por operación,
  vista estructurada `catalog: {control_records, behavior_qualifiers}`, y `evidence`
  (`source_url` + `source_commit_sha` + `content_sha256` + `retrieved_at`).
- `bian-puml/<slug>.puml` = 272 diagramas BOM UML BIAN R14 → modelo de clases (atributos tipados
  con cardinalidad, enums, asociaciones), complementa a los schemas de la API.

El pipeline es cache-first: consulta la fuente oficial (`bian-official/public` en GitHub) solo
para candidatos ausentes; no usa Internet ni memoria del modelo como evidencia directa.
`--actualizar-cache-bian` refresca entradas existentes (y sube `.json` de shape viejo a `cache_version: 2`).

1. **`validar-sd`** (`python -m src --service-domain ...`): ¿un nombre de SD existe en SD.json?
   Grafo lineal: exacto → RAG léxico → LLM solo en la franja gris.
2. **`mapear-historias`** (`python -m src mapear-historias ...`): mapea un lote de HU a sus SD.
   (detalle abajo)

## Configuración: `config.yaml` + `.env`

- **`.env`** = SOLO API keys (`GROQ_API_KEY`, `GOOGLE_API_KEY`, `HF_TOKEN`,
  `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LANGSMITH_API_KEY`). NADA más. No se versiona.
- **`config.yaml`** (versionado, sin secretos) = proveedores, modelos, orden de failover, umbrales,
  rutas, observabilidad. Se carga en `src/configuracion/config_yaml.py` -> `Config`;
  `src/configuracion/settings.py` compone `.env` + `config.yaml` (`cargar_settings()` devuelve un `Config`).
- **Failover** (`src/adaptadores/salida/llm/failover.py` · `ChatConFailover`): recorre
  `routing.llm_priority` y, dentro de cada proveedor, `providers.<n>.llm.models` **en orden**.
  429 / 402 / "no disponible" / salida no parseable -> siguiente modelo; 503 / timeout ->
  reintenta el mismo (`llm.reintentos_transitorios`, `backoff_*`) y luego avanza; error real -> propaga.
  Si se agota todo -> `TodosLosModelosAgotados`. `--proveedor <n>` restringe la cadena a UN proveedor (con failover entre sus modelos);
  `--proveedor fake` la evita (chat determinista, sin API). Los adaptadores reciben algo que solo
  necesita `.with_structured_output(schema)` (`SoportaStructured`): lo cumplen `BaseChatModel` y `ChatConFailover`.
- Proveedor LLM nuevo -> `src/adaptadores/salida/llm/` + registrar en `factory.py` + entrada en `config.yaml`.

## `mapear-historias` (detalle)

   Dado un directorio de Historias de Usuario + un JSON `{funcionalidad_macro, detalle}`, mapea
   **cada HU a sus Service Domains**. **Outer graph** map-reduce (`Send` por HU) →
   `procesar_historia` invoca un **subgrafo por HU** con **fan-out por candidato** → `reconciliar`
   (1 vez, ve todas las HU) → `publicar`. Nodos LLM del subgrafo (uno por prompt, en
   `adaptadores/salida/prompts_mapeo.py::SPECS`, todos genéricos — **prohibido hardcodear una
   funcionalidad o SD**):

   1. `extraer_intencion` → `IntencionHistoriaLLM` (resumen, `business_actions`/`objects`,
      `outcomes`, `external_dependencies`, `traceability_ids` HU-/SC-/BR-, `assumptions`, `gaps`).
      **No nombra ningún SD.**
   2. `generar_candidatos` → `CandidatosHistoriaLLM` (nombres del catálogo; **pista, no exhaustiva**).
   3. `revisar_completitud` → `RevisionCompletitudLLM` (usa el índice global BIAN como hint:
      `missing_candidates` / `unsupported_candidates` / `ownership_conflicts` /
      `duplicated_responsibilities` / `coverage_gaps` / `blocking_codes` `BIAN-SCOPE-009`).
   4. `preparar_candidatos` **[determinista]**: resuelve nombres LLM ∪ `missing_candidates` contra
      `SD.json`, tope `max_candidatos_hu`, `CatalogoBianCache.asegurar(...)` (cache-first en
      `docs/bian-cache/release14.0.0`; descarga solo ausentes; `GITHUB_TOKEN` opcional), arma **un
      `PaqueteEvidenciaCandidato` cerrado por SD**: Service Role + CR/BQ + operaciones (con
      `request_schema`/`response_schema` y `parent_control_record`) + `schemas_detalle` (cuerpo de
      cada schema de la Semantic API) + `bom_modelo` (clases/atributos/asociaciones del PUML
      `docs/bian-puml/`, `CatalogoBomPuml`) + URL/commit/SHA-256. `deteccion_omitidos.py` corre
      sobre lo NO evaluado → `service_domains_omitidos`.
   5. `evaluar_candidato` (**`Send` por candidato — 1 llamada aislada por SD**) → `EvaluacionCandidatoLLM`:
      **solo señales ordinales 0-3** (`match_action`, `match_business_object`, `match_service_role`,
      `evidence_quality`), `ambiguity` NONE/LOW/HIGH, `rol_contractual`, **`ownership_traceability`
      vs `dependency_traceability` separadas** (nunca reusar dependency como ownership),
      `reason_codes`, `assumptions`, `gaps`, `blocking_codes`. **No devuelve confianza.**
   6. `clasificar` **[determinista]** (`scoring_bian.py` + `clasificacion_historias.py`): proyecta
      cada evaluación a `ServiceDomainPropuestoLLM` (`desde_evaluacion`) y calcula **score
      determinista** (la confianza libre del LLM NO entra) → 30% acción (Service Role +
      operationId/summary/grupo CR-BQ + `match_action`) · 25% objeto/schema BOM · 20% ownership ·
      15% trazabilidad · 10% jerarquía · ±0.05 evidencia BOM · penaliza `ambiguity=HIGH` y
      `evidence_quality=1`. Luego **tope por rol** (un no-OWNED nunca es "directo") y **dos ejes**:
      `grupo` ∈ {directo ≥0.90, tentativo 0.63–0.90, descartado <0.63} y `decision_contractual`
      ∈ {SELECTED, UNRESOLVED, REJECTED} con `motivo_decision` ∈ {OWNED_SELECTED, TENTATIVE_SCORE,
      NO_OFFICIAL_BIAN_EVIDENCE, CONSUMED_DEPENDENCY, RELATED_NOT_OWNED, OUT_OF_SCOPE, NAME_UNRESOLVED}.
   7. `revisar_adversarial` → `RevisionAdversarialLLM` (**prompt independiente**; no vio la
      hipótesis formarse). `HallazgoAdversarial.tipo` ∈ {ACCION_DIRECTA_COMO_DEPENDENCIA,
      OBJETO_SIN_PROPIETARIO, DIRECTO_SIN_SERVICE_ROLE, DEPENDENCIA_PROMOVIDA_A_CONTRATO,
      CANDIDATO_OMITIDO, EXCESO_DE_CONTRATOS} + `reason_codes` (`BIAN-SCOPE-002/003`).
   8. `aplicar_adversarial` **[determinista]** (`aplicar_hallazgos_adversariales`): **solo degrada**
      (`SELECTED`→`UNRESOLVED`) y anota `reason_codes`/`blocking_codes`; nunca promueve.
   9. `seleccionar_operaciones` (si `paso2_operaciones`) → `MapeoOperacionesLLM` para los SD
      directos: `operationId` literal, conjunto mínimo suficiente, `traceability` por operación,
      `bq_seed` (1 fragmento → ≤1 op, sin cartesianos), `BIAN-SCOPE-008` si una semilla queda sin
      cubrir, gap si ninguna operación es inequívoca. **BQ personalizado**: un Control Record no
      se edita — si un campo que la historia necesita no está en ningún CR/BQ oficial, el prompt
      recibe también el BOM del SD (`schemas_bom` + `modelo_bom_puml`) y puede proponer
      `bq_personalizados` (nombre + verbo BIAN + `clase_bom`/`atributo_bom` citados). El código
      (`_bom_respalda`) **verifica la cita contra la evidencia real** (schemas_detalle o clases
      del PUML, incl. clases asociadas fuera del objeto raíz del CR) antes de anclarlo como
      `BqPersonalizadoAplicado` (`operationId=Verbo+NombreBQ`, `path=/{SD}/{id}/{NombreBQ}/{Verbo}`).
      **Nunca** se mezcla con `operaciones_bian`/`selected_operations`: vive en
      `bq_personalizados_propuestos` / `custom_bq_candidates`, `estado: CUSTOM_BQ_CANDIDATE`,
      pendiente de revisión BIAN.
   10. `reconciliar_funcionalidad` (1 llamada, ve todas las HU) → `ReconciliacionFuncionalidadLLM`
      (**asesor**: `functionality_role`, `supporting/contradicting_stories`, `recommended_status`).
      `_consolidar` **[determinista]** decide el estado final; la reconciliación solo aporta rol de
      funcionalidad + `reason_codes`.

   **El LLM nunca decide `SELECTED/UNRESOLVED/REJECTED`**: `scoring_bian` + `clasificacion_historias`
   + `_consolidar` son el árbitro. Cada llamada LLM persiste su huella (`MetadatosPrompt`:
   `prompt_id`/`prompt_version`/`prompt_sha256`/`model`/`temperature`/`catalog_sha256`/
   `evidence_snapshot_id`) en `huellas_prompts` del JSON de salida (reproducibilidad).

   Coste: por corrida ≈ `HU * (3 + n_candidatos_evaluados + 2) + 1` llamadas LLM. `concurrencia`
   (HU en paralelo) × `concurrencia_candidatos` (candidatos en paralelo por HU) = llamadas
   simultáneas — con free tiers pequeños usa `--proveedor` pinneado o baja `max_candidatos_hu`.

   Toda la evidencia BIAN vive en **`generacion_contrato_ia_v2/docs/`** (ver cabecera de este
   archivo). La red solo completa ausentes o refresca explícitamente; la memoria del modelo nunca
   es evidencia.
   Salida: `<--directorio>/<AAAA-MM-DD_HH-MM-SS>/mapeo-historias-service-domains.json` — el CLI
   crea una subcarpeta con fecha-hora por ejecución para no pisar corridas anteriores
   (`--sin-timestamp` escribe directo en `<--directorio>`).
   - Puertos: `LectorHistoriasPort`, `AnalistaMapeoBianPort` (6 métodos, 1 por nodo LLM),
     `PublicadorMapeoPort`, `CatalogoOperacionesBianPort` (+`schemas_detalle_de`/`catalogo_estructurado_de`),
     `CatalogoBomPort` (PUML), `MapeadorOperacionesBianPort`, `MapearHistoriasUseCase`.
   - `python -m src mapear-historias --directorio-hu ./HU --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json --directorio ./salida [--proveedor fake|groq|gemini|huggingface|openrouter] [--config <ruta>] [--umbral-directo 0.9] [--umbral-tentativo 0.63] [--concurrencia 2] [--sin-operaciones] [--sin-timestamp] [--actualizar-cache-bian]`

## REGLA OBLIGATORIA para cualquier cambio en `src/`

Respeta las fronteras de capa de [`ARQUITECTURA.md`](ARQUITECTURA.md). Prohibido:

- que `src/dominio/**` o `src/aplicacion/**` importen `langchain*`, `langchain_google_genai`,
  `numpy` o un adaptador;
- que `src/aplicacion/**` importe `src/adaptadores/**` o `src/configuracion/**`
  (solo `src.dominio`, `src.aplicacion`, `langgraph`);
- que el grafo llame directo a un modelo/vectorstore en vez de a un puerto
  (`Generador... no`, aquí: `RecuperadorSemanticoPort` / `AdjudicadorLLMPort`).

Proveedor nuevo → `src/adaptadores/salida/llm/`.
Otra fuente RAG / catálogo / salida → nuevo adaptador del puerto correspondiente.
Regla de negocio → solo `src/dominio/`.

## Antes de terminar cualquier cambio

```bash
cd generacion_contrato_ia_v2
.venv/Scripts/python -m unittest discover -s tests -v
```

`tests/test_arquitectura_hexagonal.py` falla si un import cruza una frontera. No lo relajes:
mueve el código a la capa correcta o introduce un puerto.

## Comandos

```bash
# validar-sd  (nodo 1: ¿existe el SD?)
.venv/Scripts/python -m src --service-domain "Current Account" --directorio ./salida/run
.venv/Scripts/python -m src --sd "Isued Device Admin" --dir ./salida/run --proveedor fake   # sin API

# mapear-historias  (HU -> Service Domains; subgrafo por HU con fan-out por candidato; evidencia local en docs/)
# escribe en ./salida/<AAAA-MM-DD_HH-MM-SS>/mapeo-historias-service-domains.json (una subcarpeta por corrida)
.venv/Scripts/python -m src mapear-historias --directorio-hu ./HU \
  --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json --directorio ./salida
.venv/Scripts/python -m src mapear-historias --hu ./HU --func ./ejemplos/funcionalidad-actualizacion-datos-personales.json \
  --dir ./salida --proveedor fake --sin-timestamp     # sin API + escribe directo en ./salida
```

## Datos verificados (sept-2026)

- Cadena de failover por defecto (`config.yaml → routing.llm_priority`): **`groq → gemini → huggingface → openrouter`**.
  OpenRouter free: `nvidia/nemotron-3-super-120b-a12b:free`, `nvidia/nemotron-3.5-lightning:free`,
  `google/gemma-4-31b-it:free` (a veces 429), `openrouter/free` (auto-router). Gemini pinneado:
  `gemini-3.6-flash` (free tier **20 req/día**), `gemini-3.5-flash`, `gemini-3.5-flash-lite`.
  Los `gemini-2.x` y los `:free` clásicos de OpenRouter están retirados (404).
- Modelos **pinneados** (nunca `-latest`), salvo `openrouter/free`.
- API keys SOLO en `.env` (`OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, …). `.env` NO pisa una var ya
  presente en la sesión.
- **Reproducibilidad `validar-sd`**: el LLM solo decide la **franja gris** (`similitud_nombre` entre
  `validar_sd.rag_umbral_bajo` y `rag_umbral_alto`). `alta` y `baja` son deterministas (código, 0 API).
  En la franja gris: `llm.temperature=0`, `llm.esfuerzo=low`, `llm.seed`.
- `similitud_nombre` = `token_sort_ratio` (estricta); `score` = `WRatio` (recuperación). Nunca
  mezclarlas: retrieval con `score`, banda con `similitud_nombre`.
- **RAG por defecto = léxico (`rapidfuzz`)** → sin API de embeddings. `validar_sd.rag_estrategia: vectorial`
  activa el índice vectorial con `EmbeddingsConFailover` (`src/adaptadores/salida/embeddings_failover.py`):
  cadena por **precisión** = `routing.embedding_priority` × `providers.<n>.embedding.models`, prueba
  cada uno y baja al siguiente si agota cuota. Por defecto **Cohere** free-tier
  (`embed-v4.0` → `embed-multilingual-v3.0` → `embed-english-v3.0` → `*-light-v3.0`) → Gemini → OpenRouter.
  `COHERE_API_KEY` (trial) = SOLO embeddings; el proveedor `cohere` no aporta chat. El índice se cachea
  en `.cache/` por el modelo **activo** (no por la lista) para no mezclar dimensiones tras un failover.
- `docs/SD.json` = 341 Service Domains (Service Landscape), columnas L..V de `docs/BIANv14.xlsm`.
  `docs/bian-business-areas.json` = misma jerarquía (semilla copiada de `architecture/context/`).
  `docs/bian-operation-catalogs.json` = fallback legado, operaciones CR/BQ de 9 SD (semilla).
  `docs/bian-cache/release14.0.0/<SD>.json` = cache-first del OpenAPI oficial por SD
  (`cache_version: 2`: operaciones CR+BQ con `parent_control_record`/`request_schema`/`response_schema`,
  `schemas_detalle` con cuerpo, `catalog` estructurado, `evidence` con commit+SHA-256). ~41 SD sembrados;
  `--actualizar-cache-bian` descarga/actualiza el resto de `bian-official/public`.
  `docs/bian-puml/<slug>.puml` = 272 diagramas BOM UML BIAN R14 (semilla; modelo de clases/atributos).
  **Nada de esto se lee de `../architecture/` en runtime — son copias semilla dentro de `docs/`.**
