# Memory — generacion-contrato-ia-v2

> Generated: 2026-09-12 22:55:35  
> Total memories: **13**  
> Breakdown: fact: 3, decision: 5, goal: 1, context: 2, learning: 2

---

## Instructions

*Standing rules, constraints, and guidelines to always follow.*

*No memories of this type.*

---

## Facts

*Verified information, project status, and established truths.*

### Configuracion del proyecto: .env = SOLO API keys (...

> Configuracion del proyecto: .env = SOLO API keys (GROQ_API_KEY, GOOGLE_API_KEY, HF_TOKEN, OPENROUTER_API_KEY, COHERE_API_KEY solo para embeddings); config.yaml (versionado, sin secretos) define proveedores/modelos/orden de failover/umbrales/rutas/observabilidad. Estado real verificado en config.yaml al 2026-09-12: routing.llm_priority = [groq, gemini, huggingface, openrouter, ollama] (ollama self-hosted queda de ultimo fallback para LLM); routing.embedding_priority = [ollama, cohere, gemini, openrouter] (ollama primero para embeddings). ChatConFailover recorre proveedores y, dentro de cada uno, sus modelos en orden; 429/402/cuota/salida no parseable -> siguiente modelo, 503/timeout -> reintenta y avanza.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:26*

### Proyecto generacion_contrato_ia_v2 (hexagonal + La...

> Proyecto generacion_contrato_ia_v2 (hexagonal + LangGraph) tiene 2 casos de uso CLI: validar-sd y mapear-historias (python -m src mapear-historias --directorio-hu <dir> --funcionalidad <json> --directorio <out>). Evidencia BIAN offline en docs/: SD.json (341 SD), bian-business-areas.json, bian-operation-catalogs.json, bian-cache/ (cache_version 2 con schemas_detalle+parent_control_record), bian-puml/ (272 .puml BOM). Sin acceso a Internet en runtime normal.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:15*

### Fixes de robustez sobre el pipeline de operaciones...

> Fixes de robustez sobre el pipeline de operaciones (src/dominio/cobertura_operaciones.py y clasificacion_historias.py): (1) finalizar_por_operacion_solida — si el SD ya es OWNED_CONTRACT con evidencia BIAN verificada y al menos una operacion anclada sin reservas, se finaliza a directo/SELECTED aunque el score lexico sea bajo (antes quedaba varado en tentativo con el mismo LLM que ya acerto el rol). (2) resolver_operation_id — reconstruye el operationId real desde path+method de una operacion YA existente en el catalogo de ESE SD cuando el LLM devuelve algo no literal (p.ej. 'POST /Correspondence/{id}/Outbound/Initiate' en vez de 'InitiateOutbound'); nunca inventa ni cruza SD, y si no resuelve genera incidencia OPERATION_ID_UNRESOLVED en vez de perderse en un log. (3) fusionar_propuestas_de_operacion agrupa por (SD, operationId real) ANTES de anclar para evitar entradas duplicadas de la misma operacion citada por varios escenarios de una HU.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:23*

---

## Decisions

*Architectural choices, approach selections, and their rationale.*

### Decision: para generacion_contrato_ia_v2 se usa el...

> Decision: para generacion_contrato_ia_v2 se usa el agente/namespace MEMANTO 'generacion-contrato-ia-v2' (namespace Moorcheh memanto_agent_generacion-contrato-ia-v2) sobre el servidor on-prem compartido de Produbanco (100.102.221.79:8080, Tailscale). Reproducible en otra maquina con: python scripts/setup_memanto.py

*Confidence: 1.0 | Status: active | Created: 2026-09-13T03:01:32*

### Arquitectura de mapear-historias: outer graph con ...

> Arquitectura de mapear-historias: outer graph con Send por HU -> subgrafo por HU con fan-out Send por candidato -> reconciliar -> publicar. Nodos LLM genericos en prompts_mapeo.py::SPECS (PROHIBIDO hardcodear funcionalidad/SD en el codigo productivo): extraer_intencion -> generar_candidatos -> revisar_completitud -> [det] preparar_candidatos -> evaluar_candidato (1 llamada aislada por SD, solo senales ordinales 0-3, sin confianza libre) -> [det] clasificar -> revisar_adversarial (prompt independiente) -> [det] aplicar_hallazgos_adversariales (solo degrada) -> seleccionar_operaciones -> reconciliar_funcionalidad (asesor; _consolidar deterministico decide). Puerto unico AnalistaMapeoBianPort (6 metodos), adaptador analista_mapeo_langchain.py.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:16*

### Scoring determinista de mapear-historias (scoring_...

> Scoring determinista de mapear-historias (scoring_bian.calcular_score, dominio puro): 30% accion oficial (tokenizacion camelCase) + 25% objeto/schema BOM + 20% ownership + 15% trazabilidad + 10% coherencia Business Area/Domain + hasta +-0.05 segun evidencia. Dos ejes de decision: grupo (directo>=0.90 / tentativo / descartado) y decision_contractual (SELECTED/UNRESOLVED/REJECTED) con motivo_decision tipado (OWNED_SELECTED, TENTATIVE_SCORE, NO_OFFICIAL_BIAN_EVIDENCE, CONSUMED_DEPENDENCY, RELATED_NOT_OWNED, OUT_OF_SCOPE, NAME_UNRESOLVED). Umbrales configurables en config.yaml (mapear_historias.umbral_*) o flags --umbral-directo/--umbral-tentativo.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:17*

### Regla de negocio de BQ personalizado: un Control R...

> Regla de negocio de BQ personalizado: un Control Record oficial NO se edita nunca. Si una HU necesita un campo que ningun CR/BQ oficial expone, seleccionar_operaciones puede proponer bq_personalizados citando clase/atributo BOM real, verificado contra schemas_detalle/bom_modelo ANTES de anclar (se descarta con warning si la cita es falsa o el campo ya esta cubierto). Vive SIEMPRE separado de las operaciones oficiales (bq_personalizados_propuestos / custom_bq_candidates, estado CUSTOM_BQ_CANDIDATE), nunca en operaciones_bian/selected_operations. Convencion de nombres verificada contra BIAN real: operationId=Verbo+NombreBQ (PascalCase), path=/{SD}/{id}/{NombreBQ}/{Verbo}.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:19*

### BOM extendido: CatalogoBianCache._normalizar usa c...

> BOM extendido: CatalogoBianCache._normalizar usa cache_version:2 (request_schema/response_schema resueltos via $ref + parent_control_record en los BQ + schemas_detalle con el cuerpo real de cada schema). PUML BOM en docs/bian-puml/ (272 archivos, copia de architecture/BIAN_PUML/) parseado por src/dominio/puml_bom.py::parsear_puml_bom (puro) -> ModeloBomPuml; puerto CatalogoBomPort / adaptador CatalogoBomPuml. Regla de prompt fija: functional_object sale SIEMPRE del objeto de negocio real, nunca del wrapper Control Record.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:18*

---

## Goals

*Objectives, targets, and milestones to track progress.*

### Retrieval hibrido RRF (src/dominio/fusion_rrf.py, ...

> Retrieval hibrido RRF (src/dominio/fusion_rrf.py, sobre RecuperadorLexico+RecuperadorVectorial ya existentes de validar-sd) esta implementado EN MEMORIA pero mapear_historias.retrieval_hibrido_habilitado = false por DEFAULT: no hay benchmark de recall que justifique encenderlo todavia. Qdrant/pgvector (infra/retrieval/docker-compose.yml, perfiles qdrant/pgvector) estan preparados pero NINGUNO arranca por defecto -- decision explicita de no anadir un servicio externo sin medir primero (341 Service Domains es poco volumen para justificarlo). Fases 3-5 quedan pendientes y documentadas en implementacion_pendiente.md: benchmark de recall, modelo canonico BIAN + scripts de ingestion, ADR de vector store externo, reranker, Graph RAG, endurecimiento operativo.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:24*

---

## Commitments

*Promises, obligations, and TODOs that need follow-through.*

*No memories of this type.*

---

## Preferences

*User and entity preferences for personalization.*

*No memories of this type.*

---

## Relationships

*Entity connections, team context, and collaboration patterns.*

*No memories of this type.*

---

## Context

*Session summaries, status updates, and conversation state.*

### Namespace de MEMANTO para este proyecto configurad...

> Namespace de MEMANTO para este proyecto configurado como agente 'generacion-contrato-ia-v2' sobre el servidor on-prem compartido en 100.102.221.79 (Tailscale)

*Confidence: 1.0 | Status: active | Created: 2026-09-13T02:58:22*

### Estado del repo generacion_contrato_ia_v2 al 2026-...

> Estado del repo generacion_contrato_ia_v2 al 2026-09-12: el 'estado sin commitear de sesiones anteriores' que se menciono en notas previas (HU borradas, docs md, cambios en cli_mapeo.py/analista_mapeo_langchain.py/prompts_mapeo.py) YA fue commiteado (ver commits bce080e 'Commitea el trabajo pendiente de sesiones previas' y los siguientes: 1e20c88, 60c0f04, 7e5b5f7, 3175f7d 'Agrega proveedor Ollama (self-hosted)', 00dd321, 4cfe1da). git log/diff es la fuente autoritativa de 'que cambio' en el codigo; esta memoria MEMANTO documenta el 'por que' y los gotchas de diseno que no siempre son obvios leyendo el diff.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:27*

---

## Events

*Important conversations, milestones, and temporal occurrences.*

*No memories of this type.*

---

## Learnings

*Knowledge acquired from experience, corrections, and insights.*

### Causa raiz de un falso negativo real encontrado en...

> Causa raiz de un falso negativo real encontrado en produccion (HU 'Notificar actualizacion de datos' -> Service Domain Correspondence quedaba REJECTED sin operaciones pese a tener evidencia BIAN valida): eran las reglas de ownership/scoring/elegibilidad de operacion, NO un problema de retrieval. Fix: promocion determinista CONSUMED_DEPENDENCY->OWNED_CONTRACT solo si el hallazgo adversarial es ACCION_DIRECTA_COMO_DEPENDENCIA + dependency_kind=AUDIT_OR_NOTIFICATION (salida/resultado, no precondicion) + trazabilidad + evidence_refs, y ademas objeto_bom del score >= 0.15 (este ultimo umbral evito un falso positivo real: Party Authentication fue promovido citando su propio CR para un objeto de negocio ajeno, objeto_bom=0.0 exacto).

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:21*

### Mecanismo simetrico a la promocion: determinar_deg...

> Mecanismo simetrico a la promocion: determinar_degradaciones reclasifica OWNED_CONTRACT -> CONSUMED_DEPENDENCY (dependency_kind=SUPPORTING_LOOKUP) cuando el revisor adversarial marca DEPENDENCIA_PROMOVIDA_A_CONTRATO y la accion citada no comparte NINGUN token con business_actions (extraidos en extraer_intencion, antes de proponer el SD). Caso real: 'Party Reference Data Directory' evaluado OWNED_CONTRACT citando 'actualizar...' para una HU donde actualizar era precondicion, no accion propia.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:22*

---

## Observations

*Patterns noticed, behavioral notes, and recurring themes.*

*No memories of this type.*

---

## Artifacts

*Tool outputs, files, reports, and external references.*

*No memories of this type.*

---

## Errors

*Failure records, bugs, and lessons learned from mistakes.*

*No memories of this type.*

---

*End of memory export.*
