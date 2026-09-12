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

Trabajo pendiente (Fases 3-5 del plan de recuperación híbrida: modelo canónico + ingestión, ADR
Qdrant/pgvector, reranker, Graph RAG, endurecimiento operativo) documentado con problema/ventaja/
justificación/pasos en [`implementacion_pendiente.md`](implementacion_pendiente.md) — léelo antes
de tocar retrieval, el modelo canónico BIAN, o `infra/retrieval/`.

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
   4. `preparar_candidatos` **[determinista]**: resuelve nombres LLM ∪ `missing_candidates` ∪
      **retrieval híbrido** (opcional, ver abajo) contra `SD.json`, tope `max_candidatos_hu` —
      lo que exceda el tope NO desaparece en silencio: queda como incidencia
      `TRUNCATED_BY_MAX_CANDIDATOS_HU` —, `CatalogoBianCache.asegurar(...)` (cache-first en
      `docs/bian-cache/release14.0.0`; descarga solo ausentes; `GITHUB_TOKEN` opcional), arma **un
      `PaqueteEvidenciaCandidato` cerrado por SD**: Service Role + CR/BQ + operaciones (con
      `request_schema`/`response_schema` y `parent_control_record`) + `schemas_detalle` (cuerpo de
      cada schema de la Semantic API) + `bom_modelo` (clases/atributos/asociaciones del PUML
      `docs/bian-puml/`, `CatalogoBomPuml`) + URL/commit/SHA-256. `deteccion_omitidos.py` corre
      sobre lo NO evaluado → `service_domains_omitidos` (solo reporta; el retrieval híbrido de
      abajo sí reinyecta).

      **Retrieval híbrido** (`mapear_historias.retrieval_hibrido_habilitado`, **OFF por
      defecto**): antes de resolver, `_candidatos_retrieval_hibrido` consulta los
      `RecuperadorSemanticoPort` configurados (léxico `RecuperadorLexico` siempre + vectorial
      `RecuperadorVectorial` si hay embeddings utilizables — mismos adaptadores que `validar-sd`,
      en memoria, sin Qdrant/pgvector) con la consulta = `business_actions/objects` +
      `capacidades_funcionales` + `outcomes` de `intencion`, fusiona con RRF
      (`src/dominio/fusion_rrf.py`) y añade hasta `retrieval_max_inyectados` candidatos que el LLM
      NO propuso (`origen_candidato="retrieval_hibrido"`, `desglose_score.retrieval_score` = score
      de fusión). Nunca reemplaza un candidato LLM/completitud. Ver `implementacion_pendiente.md`
      (Fase 3) para el estado de la ADR sobre un índice externo.
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
   8. `aplicar_adversarial` **[determinista]**: tres movimientos, ninguno decidido por el LLM
      solo — cada uno exige que una señal calculada por separado confirme el hallazgo, nunca se
      reclasifica solo porque el revisor lo dijo. **Degrada** (`aplicar_hallazgos_adversariales`,
      `SELECTED`→`UNRESOLVED`, catch-all conservador cuando ninguna reclasificación de abajo
      calificó) en `DEPENDENCIA_PROMOVIDA_A_CONTRATO`/`DIRECTO_SIN_SERVICE_ROLE`. **Degrada
      reclasificando** (`determinar_degradaciones` + `propuestos_degradados`)
      `OWNED_CONTRACT`→`CONSUMED_DEPENDENCY` cuando hay un hallazgo `DEPENDENCIA_PROMOVIDA_A_CONTRATO`
      para ese SD Y el `accion_objeto` que citó no tiene NINGÚN token en común con
      `intencion.business_actions` (las acciones que la propia historia declaró en
      `extraer_intencion`, antes de proponer ningún SD) — sin esa confirmación independiente,
      queda solo en el degrade conservador de arriba (`UNRESOLVED`, bloqueado para revisión
      humana, nunca reclasificado a ciegas). Al reclasificar, `dependency_kind=SUPPORTING_LOOKUP`
      (precondición consultada antes de actuar) y `_decidir` ya garantiza
      `REJECTED`/`CONSUMED_DEPENDENCY` sin importar el score, apenas `rol_contractual` deja de ser
      `OWNED_CONTRACT`. Caso real: "Notificar actualización de datos" (funcionalidad
      "Actualización de datos personales") → "Party Reference Data Directory" fue evaluado
      `OWNED_CONTRACT` citando `accion_objeto="actualizar número de celular o correo electrónico"`
      — la actualización es una precondición ya ocurrida ("cuando el usuario actualiza..."), la
      historia solo notifica; `intencion.business_actions` nunca incluyó "actualizar". Antes de
      este fix quedaba `UNRESOLVED` bloqueado (mejor que `SELECTED`, pero sin resolver);
      ahora `REJECTED/CONSUMED_DEPENDENCY` directo. Regresión determinista en
      `tests/test_grafo_mapeo.py::TestGrafoMapeoDegradacionOwnership` y
      `tests/test_clasificacion_historias.py::TestDeterminarDegradaciones`. **Promueve**
      (`determinar_promociones` + `propuestos_promovidos`, ambos en `clasificacion_historias.py`)
      `CONSUMED_DEPENDENCY`→`OWNED_CONTRACT` cuando: hay un hallazgo
      `ACCION_DIRECTA_COMO_DEPENDENCIA` para ese SD SIN que el propio revisor también haya marcado
      `DIRECTO_SIN_SERVICE_ROLE` para el mismo SD, `dependency_kind == AUDIT_OR_NOTIFICATION` (el
      SD es la salida/resultado que la historia produce, no una precondición tipo
      SECURITY_GUARD/SUPPORTING_LOOKUP/EXTERNAL_PROVIDER/RISK_INPUT), hay
      `dependency_traceability` + `evidence_refs` no vacíos, Y `desglose_score.objeto_bom >=
      OBJETO_BOM_MINIMO_PROMOCION` (0.15). Esta última condición existe porque `evidence_refs` no
      vacío NO basta: `operacion_evidencia_verificable` acepta citar el propio nombre del
      Control Record/`operation_id` como cita válida, así que el LLM puede satisfacer "hay
      evidencia" señalando CUALQUIER operación real del SD sin que tenga relación con el objeto de
      negocio de la historia — caso real: "Party Authentication" fue promovido citando su propio
      CR `PartyAuthenticationAssessment` para una historia de "enviar notificación" (evidencia
      real, pero de identidad/autenticación, no de mensajería); `objeto_bom` dio 0.0 exacto (ni la
      rúbrica `match_objeto_negocio` ni el texto de operaciones/BOM encontraron nada en común). Al
      promover se **recalcula el score completo** (`clasificar_service_domains` de nuevo, nunca se
      parcha solo la etiqueta) y se anota `reason_codes += ["OWNERSHIP_PROMOTED_BY_ADVERSARIAL"]`.
      El score léxico crudo hereda rúbricas (`match_action`/`match_objeto_negocio`/etc.) que el LLM
      calificó bajo mientras todavía enmarcaba el SD como dependencia, así que casi siempre
      recalcula en banda tentativa (a veces incluso descartada) — la barra de promoción (hallazgo
      independiente + evidencia + trazabilidad + objeto_bom + sin contradicción de rol) ya es más
      estricta que ese umbral numérico. Por eso `aplicar_hallazgos_adversariales` **finaliza** la
      promoción: si la evidencia BIAN del SD es oficial y verificada (`VERIFIED`/`CACHED_VERIFIED`),
      lo mueve a `candidatos_directos` con `decision_contractual=SELECTED`/
      `motivo_decision=OWNED_SELECTED` **aunque su `grupo` numérico no llegara a 0.90** (simétrico
      en sentido inverso al tope que ya aplica a los no-owned). Sin evidencia oficial verificada, se
      anota la promoción pero NO se fuerza "directo" — queda donde la reclasificación lo dejó
      (típicamente `REJECTED/OUT_OF_SCOPE` o `UNRESOLVED/NO_OFFICIAL_BIAN_EVIDENCE`; nunca se
      inventa un contrato sobre evidencia inexistente). Un `ACCION_DIRECTA_COMO_DEPENDENCIA` que no
      califica para promoción (sin `dependency_kind` de salida, sin trazabilidad/evidencia,
      `objeto_bom` insuficiente, o contradicho por `DIRECTO_SIN_SERVICE_ROLE`) queda como
      incidencia `OWNERSHIP_CONFLICT_UNRESOLVED` (nunca se pierde en silencio; ver
      `metricas.ownership_*` en la salida). Caso real que motivó la promoción:
      "Notificar actualización de datos" → Correspondence quedaba REJECTED/CONSUMED_DEPENDENCY
      pese a citar `InitiateOutbound` (`salida/2026-09-11_17-59-40/`). Caso real que motivó el piso
      `objeto_bom`: la misma historia promovía también a "Party Authentication" sin base real
      (`salida/2026-09-12_*/`). Regresión determinista en
      `tests/test_grafo_mapeo.py::TestGrafoMapeoPromocionOwnership` y
      `tests/test_clasificacion_historias.py::TestDeterminarPromociones`.
   9. `seleccionar_operaciones` (si `paso2_operaciones`) → `MapeoOperacionesLLM` para los SD
      **elegibles** (`candidatos_operacion_elegibles`: `OWNED_CONTRACT` directo O tentativo — YA NO
      solo "directo"; un SD correctamente identificado como propietario con confianza tentativa
      igual tiene una operación oficial real que documentar, sin que la confianza global de la
      historia decida si esa operación existe): `operationId` literal, conjunto mínimo suficiente, `traceability` por operación,
      `bq_seed` (1 fragmento → ≤1 op, sin cartesianos — esto NO impide que VARIOS fragmentos
      distintos apunten a la MISMA operación: p.ej. "notificar al contacto anterior" y "notificar
      al contacto nuevo" son dos escenarios que ambos resuelven con `InitiateOutbound`; el código
      (`fusionar_propuestas_de_operacion` en `cobertura_operaciones.py`) fusiona todas las citas de
      la MISMA operación de un SD en una sola entrada de `operaciones_bian` — unión sin duplicados
      de `escenarios_hu`/`traceability`/`evidence_refs`/`reason_codes`, `justificacion`/`bq_seed`
      distintas concatenadas con "; " — antes de esto una historia con 4 escenarios notificando por
      el mismo canal generaba 4 entradas idénticas de `InitiateOutbound` en vez de una; ver
      `tests/test_grafo_mapeo.py::TestGrafoMapeoOperacionesDuplicadas`), `BIAN-SCOPE-008` si una
      semilla queda sin cubrir, gap si ninguna operación es inequívoca. Cada operación de `<operaciones_disponibles>`
      trae inline `campos_respuesta={...}` (propiedades reales de su `response_schema`, resueltas
      desde `schemas_detalle` — sin cruzar mentalmente el bloque de operaciones con un dump de
      schemas aparte, y sin depender de un corte alfabético que pueda excluir en silencio el
      schema que decide el caso); el prompt exige citar en `evidence_refs` un campo real de ahí
      cuando el escenario pide un dato concreto. El código (`operacion_evidencia_verificable`)
      verifica esa cita contra `schemas_detalle`: si no hay evidencia real, la operación se ancla
      igual pero con `reason_codes += ["OPERATION_EVIDENCE_UNVERIFIED"]` (nunca se descarta en
      silencio). El anclaje es estricto por Service Domain (índice por nombre normalizado, sin
      fallback a otro SD) — pero tolerante al FORMATO del `operationId`: modelos más débiles del
      failover a veces devuelven `"METODO /path/completo"` en vez del literal exacto que pide el
      prompt (observado en producción: `"POST /Correspondence/{id}/Outbound/Initiate"` en vez de
      `"InitiateOutbound"`). `resolver_operation_id` (`src/dominio/cobertura_operaciones.py`, usado
      tanto por el blindaje anti-alucinación del adaptador `mapeador_operaciones_langchain.py` como
      por el anclaje de `_asignar_operaciones`) lo reconstruye desde el `path`/`method` REALES de
      una operación ya presente en el catálogo de ESE SD — nunca inventa una operación ni cruza a
      otro Service Domain, solo tolera un formato de cita distinto; cuando reconstruye así (no
      match exacto) anota `reason_codes += ["OPERATION_ID_RECONSTRUCTED_FROM_PATH"]`, y si de plano
      no resuelve ninguna forma, queda como incidencia `OPERATION_ID_UNRESOLVED` en vez de
      perderse en un log. **Operación personalizada**: un Control Record no se edita — si un
      campo que la historia necesita no está en ningún `campos_respuesta` oficial (CR ni BQ), el
      prompt recibe también el BOM del SD (`schemas_bom` + `modelo_bom_puml`) y puede proponer
      `bq_personalizados` (`grupo_existente` + verbo BIAN + `clase_bom`/`atributo_bom` citados).
      `grupo_existente` DEBE ser un CR/BQ que YA aparece en `<operaciones_disponibles>` de ese SD —
      **nunca crea un tag/grupo nuevo**; el código valida la cita, descarta si el grupo no existe o
      si el `operationId` resultante (`Verbo+NombreDelGrupo`) ya es oficial, y (`_bom_respalda`)
      **verifica la cita contra la evidencia real** (schemas_detalle o clases del PUML, incl.
      clases asociadas fuera del objeto raíz del CR) antes de anclarlo como `BqPersonalizadoAplicado`
      con `path_propuesto` derivado del path REAL de una operación existente de ese grupo (mismo
      prefijo e id-param, solo cambia el verbo final — nunca un `/{id}` genérico inventado).
      **Nunca** se mezcla con `operaciones_bian`/`selected_operations`: vive en
      `bq_personalizados_propuestos` / `custom_bq_candidates`, `estado: CUSTOM_BQ_CANDIDATE`,
      pendiente de revisión BIAN.

      **`finalizar_por_operacion_solida`** **[determinista, corre justo después de anclar
      operaciones]**: un SD ya `OWNED_CONTRACT` desde la primera evaluación (sin haber pasado por
      `determinar_promociones`) puede igual quedar en `tentativo` porque las rúbricas de
      acción/objeto vinieron bajas — mismo problema estructural que motiva la promoción, pero sin
      hallazgo adversarial que lo dispare. Si tiene evidencia BIAN oficial verificada, `objeto_bom
      >= OBJETO_BOM_MINIMO_PROMOCION` (mismo piso y misma razón que la promoción — evita el mismo
      falso positivo tipo "Party Authentication") Y al menos una operación anclada sin
      `OPERATION_EVIDENCE_UNVERIFIED` (la única reserva que sí refleja incertidumbre real sobre la
      cita; `OPERATION_ID_RECONSTRUCTED_FROM_PATH` no descalifica — ahí la operación quedó resuelta
      con certeza estructural contra el path/method reales, `resolver_operation_id`, el único
      caveat es el formato en que el LLM la citó), se finaliza igual que una promoción: se mueve a
      `candidatos_directos` con `SELECTED`/`OWNED_SELECTED` y
      `reason_codes += ["OWNED_FINALIZED_BY_OPERATION_EVIDENCE"]`, sin importar el score léxico
      agregado. Caso real que lo motivó: en una corrida con LLM real, Correspondence salió
      `OWNED_CONTRACT` directo (nada que promover) pero con score 0.6733 (idéntico al caso de
      promoción) — sin este paso quedaba en tentativo pese a tener `InitiateOutbound` ya anclado y
      verificado. Ver `tests/test_grafo_mapeo.py::TestGrafoMapeoFinalizacionPorOperacion`.
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

   **Observabilidad (Fase 0)**: cada `ResultadoMapeoHistorias.parametros` trae `run_id` (uuid4,
   único por corrida) y `retrieval_hibrido_activo`/`retrieval_top_k`/`retrieval_max_inyectados`.
   `ResultadoMapeoHistorias.metricas` trae, derivado solo de lo que la propia corrida ya registra
   (sin golden set — eso es Recall@K de Fase 3): `candidate_drop_rate` (candidatos resueltos que
   `TRUNCATED_BY_MAX_CANDIDATOS_HU` cortó, sobre el total), `ownership_promovidos` /
   `ownership_degradados` (reclasificaciones deterministas en cada dirección) y
   `ownership_conflict_rate` (hallazgos `ACCION_DIRECTA_COMO_DEPENDENCIA`/
   `DEPENDENCIA_PROMOVIDA_A_CONTRATO` que NO calificaron para ninguna reclasificación, sobre
   promovidos+degradados+sin-resolver — quedan `UNRESOLVED` bloqueados, no reclasificados a
   ciegas), `operation_grounding_rate` (operaciones ancladas sin `OPERATION_EVIDENCE_UNVERIFIED`, sobre el
   total ancladas), `operation_id_no_resuelto` (incidencias `OPERATION_ID_UNRESOLVED`) y
   `finalizados_por_operacion_solida` (`OWNED_FINALIZED_BY_OPERATION_EVIDENCE`, ver paso 9).
   `desglose_score` de cada SD también trae `retrieval_score` (origen retrieval híbrido) y
   `operation_support_score` (fracción de sus operaciones verificadas) — aditivos, nunca entran a
   `total`.

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

### Pruebas de integración/E2E — solo bajo demanda

La suite de arriba es 100% determinista y sin red (`--proveedor fake` o evidencia local). Las
pruebas que hacen llamadas LLM reales (consumen cuota, tardan segundos-minutos) viven igual en
`tests/`, pero **decoradas con `@unittest.skipUnless(os.environ.get("EJECUTAR_E2E") == "1", ...)`**
para que `discover -s tests` las salte por defecto. Se corren explícitamente cuando el usuario lo
pide, nunca de forma automática:

```bash
EJECUTAR_E2E=1 .venv/Scripts/python -m unittest discover -s tests -p "test_e2e_*.py" -v
```

(`discover -s tests`, no un path con puntos: `tests/` no tiene `__init__.py`, así que un dotted
path como `python -m unittest tests.test_e2e_x` no resuelve `support.py`.)

**Estructura de recursos, pensada para que sigan sumándose casos.** La carpeta de recursos se
llama IGUAL que el caso de prueba (sin el prefijo `test_e2e_`), para identificarla entre las demás
a simple vista:

```
tests/
  resources/
    datos_personales/     <- entradas (HU + funcionalidad) Y salida de test_e2e_datos_personales.py
    <otro_caso>/          <- entradas Y salida de test_e2e_<otro_caso>.py (futura)
  e2e_support.py                    <- RESOURCES, requiere_e2e, ejecutar_caso(carpeta, funcionalidad)
  test_e2e_datos_personales.py      <- ejecutar_caso("datos_personales", ...)
  test_e2e_<otro_caso>.py           <- ejecutar_caso("<otro_caso>", ...)
```

Cada `resources/<caso>/` es autocontenida: trae su(s) HU (`.txt`), su JSON de funcionalidad, y
`ejecutar_caso()` (en `tests/e2e_support.py`) escribe ahí mismo `mapeo-historias-service-domains.json`
como salida -se sobreescribe en cada corrida, queda como artefacto inspeccionable, no un tempdir
que se borra-. **Nunca** apuntar a las carpetas compartidas `./HU` / `./ejemplos` de la raíz: son
para pruebas manuales del CLI, cambian de contenido libremente, y ya rompieron una prueba E2E por
eso. Una prueba E2E nueva es mecánica: crear `tests/resources/<caso>/` con sus datos y, en
`tests/test_e2e_<caso>.py`, `ejecutar_caso("<caso>", "<funcionalidad>.json")` bajo `@requiere_e2e`.

Ejemplo: `tests/test_e2e_datos_personales.py` + `tests/resources/datos_personales/` — replica
`mapear-historias` sobre su propia HU "Crear pantalla de datos personales" y valida la regresión
(debe anclar `RetrieveReference`/`UpdateReference`, nunca `RetrieveDemographics`; ver
`src/dominio/cobertura_operaciones.py`).

Segundo ejemplo: `tests/test_e2e_datos_personales_notificacion.py` +
`tests/resources/datos_personales_notificacion/` — HU "Notificar actualización de datos" bajo la
funcionalidad macro "Actualización de datos personales" (la misma que usa el primer ejemplo) —
replica el comando manual real usado para validar la corrección de ownership de Correspondence
(`--directorio-hu ./HU --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json`).
Valida que Correspondence quede `OWNED_CONTRACT` (nunca `REJECTED`) con `InitiateOutbound` anclado
(POST, BQ, grupo Outbound). Su equivalente determinista SIN LLM (corre siempre, no gateado) es
`tests/test_grafo_mapeo.py::TestGrafoMapeoPromocionOwnership` /
`TestGrafoMapeoFinalizacionPorOperacion`. El framing de la funcionalidad cambia el score que el
LLM le da al candidato (0.5033 / 0.6733 / 0.98 observados en corridas reales según el contexto y
qué modelo del failover respondió) — la regresión determinista es la que fija ese caso sin
depender de qué framing use la E2E.

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
