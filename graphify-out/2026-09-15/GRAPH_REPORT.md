# Graph Report - generacion_contrato_bian  (2026-09-15)

## Corpus Check
- 458 files · ~6,082,403 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 547 file(s) not represented in the graph (top: .puml 543, .example 1, (none) 1)

## Summary
- 2275 nodes · 5340 edges · 155 communities (127 shown, 21 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 470 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7f4649a7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- clasificar
- ProveedorLLMStrategy
- operacion_evidencia_verificable
- test_arquitectura_hexagonal.py
- CatalogoBianCache
- failover.py
- HistoriaUsuario
- EntradaCatalogo
- setup.sh script
- entrada/__init__.py
- adaptadores/__init__.py
- aplicacion/__init__.py
- puertos/__init__.py
- servicios/__init__.py
- configuracion/__init__.py
- dominio/__init__.py
- src/__init__.py
- generacion-contrato-ia-v2
- cli_mapeo.py
- fake.py
- CatalogoBomPuml
- AnalistaMapeoBianLangChain
- historias.py
- modelos.py
- Plan de implementación: recuperación y decisión BIAN híbrida
- MapearHistoriasServiceDomainsService
- ServiceDomainsDeHistoria
- CandidatoSD
- Config
- ValidarServiceDomainService
- generacion_contrato_ia_v2
- EmbeddingsResiliente
- RerankerCrossEncoder
- EvidenciaBian
- IntencionHistoriaLLM
- salida/__init__.py
- ResultadoMapeoHistorias
- normalizar
- _Response
- contenedor.py
- svg_to_puml_control_record.py
- clasificacion_historias.py
- bian_object_catalog.py
- SoportaStructured
- support.py
- TestAgnosticismoPrompts
- EvaluacionCandidatoLLM
- svg_to_puml.py
- crear_caso_uso
- ServiceDomainAsignado
- OperacionBian
- fusion_rrf
- bian-cache/README.md
- CLAUDE.md — generacion_contrato_ia_v2
- TestVueltaCorrectiva
- crear_caso_uso_mapeo
- Memory — generacion-contrato-ia-v2
- formato_bom.py
- Grafos LangGraph del proyecto
- mapear_historias_service_domain.py
- Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)
- Arquitectura hexagonal — reglas
- `mapear-historias` — Historias de Usuario → Service Domains
- e2e_common.py
- Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1
- 1. Fase 3 — Hybrid RAG "de verdad" (validar y, si corresponde, encender por defecto)
- 2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión
- 3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide
- 4. Fase 4 — Reranker + Graph RAG
- ADR 0001 — Índice vectorial: en memoria por defecto, Qdrant disponible
- RecuperadorSemanticoPort
- EmbeddingsConFailover
- MEMANTO Memory Skill
- setup_memanto.py
- _entrada
- PaqueteEvidenciaCandidato
- resolver_operation_id
- factory.py
- crear_checkpointer
- TestDeterminarPromociones
- generate_entities.py
- fusionar_propuestas_de_operacion
- _FakeChat
- download_svg_control_record.py
- svg_to_puml
- CLAUDE.md
- bian_view_catalog.py
- _FakeEmbeddings
- MEMANTO - Your Active Memory Companion
- bian_view_catalog
- download_svg_control_record
- test_normalizacion_y_catalogo.py
- BIAN UML / PlantUML extraction
- TestE2EDatosPersonales
- ChatConFailover
- _ChatGuion
- test_bm25_y_fusion.py
- RevisionAdversarialLLM
- TestCatalogoBianUnico
- cargar_settings
- NodoBian
- determinar_promociones_por_accion
- generate_matrix_view.py
- session_start.py
- enrich_service_landscape.py
- test_senales_grafo.py
- _AnalistaQueRevienta
- _ejecutar
- RecuperadorLexico
- Decisions
- Learnings
- formatear_catalogo
- GrafoBianPort
- ingest_bian.py
- GrafoBian
- Facts
- generate_entities
- generate_matrix_view
- notify.py
- Convenciones del SVG (Bizzdesign) y como se mapean
- TestTextoProsa
- ._cargar
- _grafo_con_clase_compartida
- bian_object_catalog
- evaluate_retrieval
- GrafoBianJson
- enrich_service_landscape
- canary.py
- rebuild.py
- analista_mapeo_langchain.py
- cohere.py
- EntradaModelo
- OpenAIStrategy
- .texto_prosa
- test_smart_token_regresion.py
- Ampliar el corpus dorado BIAN
- ingest_bian
- TestPrioridadPorNodo
- TestGrafoRealIngestado
- TestE2EDatosPersonalesNotificacion
- 9. Pendiente de verdad (2026-09-14, revisado tras implementar los 6 puntos)
- graphify-ollama.sh
- Instructions
- _CadenaMedida
- Goals
- prompts_mapeo.py
- migrate_index/README.md
- .__init__

## God Nodes (most connected - your core abstractions)
1. `MapearHistoriasServiceDomainsService` - 98 edges
2. `normalizar()` - 82 edges
3. `CatalogoBianCache` - 74 edges
4. `CatalogoJson` - 73 edges
5. `IntencionHistoriaLLM` - 56 edges
6. `EntradaCatalogo` - 54 edges
7. `RevisionAdversarialLLM` - 52 edges
8. `EvidenciaBian` - 49 edges
9. `ServiceDomainsDeHistoria` - 49 edges
10. `HistoriaUsuario` - 46 edges

## Surprising Connections (you probably didn't know these)
- `_Constructor` --uses--> `GrafoBian`  [INFERRED]
  scripts/ingest_bian/ingest_bian.py → src/dominio/grafo_bian.py
- `_Constructor` --uses--> `NodoBian`  [INFERRED]
  scripts/ingest_bian/ingest_bian.py → src/dominio/grafo_bian.py
- `ingestar()` --uses--> `GrafoBian`  [INFERRED]
  scripts/ingest_bian/ingest_bian.py → src/dominio/grafo_bian.py
- `TestCatalogoBianCache` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_catalogo_bian_cache.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestFormatoDeCitaEnEvidenceRefs` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_cobertura_evidencia_formato_cita.py → src/adaptadores/salida/catalogo_bian_cache.py

## Import Cycles
- None detected.

## Communities (155 total, 21 thin omitted)

### Community 0 - "clasificar"
Cohesion: 0.19
Nodes (10): Banda, clasificar(), mejor_candidato(), Regla de dominio: clasifica el resultado del RAG en bandas por similitud…, El candidato con mayor similitud léxica estricta (no el mejor de recuperación)., Umbrales, _cand(), Regla de dominio: bandas por similitud (sin API, sin frameworks). (+2 more)

### Community 1 - "ProveedorLLMStrategy"
Cohesion: 0.11
Nodes (16): AnthropicStrategy, BaseChatModel, Embeddings, Estrategia Anthropic (opcional). `pip install langchain-anthropic`. Nota: usa…, ProveedorLLMStrategy, ABC, BaseChatModel, Embeddings (+8 more)

### Community 2 - "operacion_evidencia_verificable"
Cohesion: 0.08
Nodes (14): campos_alcanzables(), _formas_citables(), operacion_evidencia_verificable(), Nombres de propiedad (normalizados) del schema raíz, 1 nivel — el mismo alcance…, Formas normalizadas de una `evidence_ref` que cuentan como la misma cita. El…, ¿Alguna `evidence_ref` citada por el LLM coincide con un campo real alcanzable…, Regresión: una cita `Campo:Tipo` es válida — es el formato en que el prompt…, TestFormatoDeCitaEnEvidenceRefs (+6 more)

### Community 3 - "test_arquitectura_hexagonal.py"
Cohesion: 0.23
Nodes (11): AST, ImportFrom, _capa(), _modulo(), _objetivos(), _paquete(), _permitido(), Path (+3 more)

### Community 4 - "CatalogoBianCache"
Cohesion: 0.08
Nodes (30): CatalogoBianCache, CatalogoJson, Path, LectorHistoriasFilesystem, PublicadorMapeoJson, Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como…, UmbralesMapeo, La caché de nodos convierte una re-ejecución en "solo lo que falta" — sin… (+22 more)

### Community 5 - "failover.py"
Cohesion: 0.15
Nodes (19): Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.…, _invocar(), _corto(), degradar_a_siguiente(), es_transitorio(), no_cabe(), PeticionDemasiadoGrande, BaseException (+11 more)

### Community 6 - "HistoriaUsuario"
Cohesion: 0.07
Nodes (29): Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad…, _titulo_desde_nombre(), MapeadorOperacionesLangChain, AnalistaMapeoBianPort, Nodo 1: interpreta la historia. Sin nombres de Service Domain, sin decisiones…, Nodo 2: propone nombres de Service Domain del catálogo. Es una PISTA, no…, Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes…, Nodo 4: evalúa UN candidato contra SU paquete de evidencia oficial cerrado.… (+21 more)

### Community 7 - "EntradaCatalogo"
Cohesion: 0.11
Nodes (13): Adaptador: carga los Service Domains desde la fuente ÚNICA del runtime,…, Adaptador RAG **disperso** (BM25 sobre el texto del Service Domain) — sin API…, CatalogoServiceDomainsPort, ABC, Puerto driven: acceso al catálogo de Service Domains (BIAN Service Landscape)., Todas las entradas del catálogo., Coincidencia exacta tras normalizar (case/espacios/PascalCase). None si no…, EntradaCatalogo (+5 more)

### Community 20 - "cli_mapeo.py"
Cohesion: 0.12
Nodes (21): datetime, _forzar_utf8(), main(), _directorio_run(), _forzar_utf8(), main(), _parse(), Namespace (+13 more)

### Community 21 - "fake.py"
Cohesion: 0.33
Nodes (13): _archivo_hu(), _bloque(), Any, Estrategia 'fake': chat y embeddings deterministas, sin API. Para tests y demo…, _responder_adversarial(), _responder_candidatos(), _responder_completitud(), _responder_evaluacion() (+5 more)

### Community 22 - "CatalogoBomPuml"
Cohesion: 0.06
Nodes (26): FullKey, SerializerProtocol, CacheNodosArchivo, Namespace, Path, Adaptador: caché de nodos de LangGraph persistida en archivos. Sin dependencias…, `BaseCache` de LangGraph sobre el sistema de archivos. Tolerante a fallos: si…, _segmento() (+18 more)

### Community 23 - "AnalistaMapeoBianLangChain"
Cohesion: 0.27
Nodes (7): NamedTuple, AnalistaMapeoBianLangChain, _lista(), Escalones decrecientes del catálogo, para reintentar cuando la petición no…, Invoca el nodo y, si NINGÚN modelo acepta la petición por tamaño, la reduce y…, PromptSpec, Prompt + su huella reproducible (id + versión + texto para SHA-256).

### Community 24 - "historias.py"
Cohesion: 0.10
Nodes (30): Adaptador: lee los PUML BOM de `docs/bian-diagrams/puml-bom/` y los parsea a…, CatalogoBomPort, ABC, Puerto driven: modelo estructural BOM (clases/enums/asociaciones) por Service…, Modelo de clases del PUML BOM del Service Domain, o None si no hay `.puml`…, Slugs de los Service Domains que tienen `.puml` local., AsociacionBom, AtributoBom (+22 more)

### Community 25 - "modelos.py"
Cohesion: 0.15
Nodes (16): PublicadorJson, Adaptador de persistencia: escribe el resultado como JSON en el directorio del…, ABC, Puerto driving: la API que ofrece la aplicación., Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en…, ValidarServiceDomainUseCase, PublicadorResultadoPort, ABC (+8 more)

### Community 26 - "Plan de implementación: recuperación y decisión BIAN híbrida"
Cohesion: 0.06
Nodes (34): 10. Estrategia de pruebas, 11. Gates de aceptación, 12. Riesgos y mitigaciones, 13. Orden recomendado de implementación, 1. Resultado esperado, 2. Diagnóstico confirmado, 3. Principios de la solución, 4. Arquitectura objetivo consolidada (+26 more)

### Community 27 - "MapearHistoriasServiceDomainsService"
Cohesion: 0.06
Nodes (28): EstadoHistoria, TypedDict, EstadoMapeo, TypedDict, _canonico(), _huellas(), MapearHistoriasServiceDomainsService, _paquete_de() (+20 more)

### Community 28 - "ServiceDomainsDeHistoria"
Cohesion: 0.20
Nodes (14): degradar_sin_operacion_anclada(), finalizar_por_operacion_solida(), Se llama DESPUÉS de anclar operaciones (`_asignar_operaciones`). Un candidato…, Se llama DESPUÉS de anclar operaciones y de `finalizar_por_operacion_solida`.…, Los Service Domains de una historia repartidos en 3 grupos por confianza (post-…, ServiceDomainsDeHistoria, _op(), Un contrato sin operación no es un contrato, y un propietario con operación… (+6 more)

### Community 29 - "CandidatoSD"
Cohesion: 0.22
Nodes (13): AdjudicadorLangChain, _formatear_candidatos(), Adaptador: adjudica con un chat model de LangChain + salida estructurada., Prompt del adjudicador. Técnicas: rol explícito, descomposición de la tarea,…, AdjudicadorLLMPort, ABC, Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)., Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`. (+5 more)

### Community 30 - "Config"
Cohesion: 0.24
Nodes (3): Config, Path, Orden de proveedores para un nodo. `--proveedor X` sigue mandando sobre todo:…

### Community 31 - "ValidarServiceDomainService"
Cohesion: 0.28
Nodes (3): EstadoGrafo, TypedDict, ValidarServiceDomainService

### Community 32 - "generacion_contrato_ia_v2"
Cohesion: 0.15
Nodes (13): Configuración: `config.yaml` + `.env`, Cómo decide  —  y cómo se garantiza la reproducibilidad, El grafo, Estructura, generacion_contrato_ia_v2, Instalación, LangSmith (observabilidad), MEMANTO (memoria de agentes) (+5 more)

### Community 33 - "EmbeddingsResiliente"
Cohesion: 0.29
Nodes (6): _delay_sugerido(), EmbeddingsResiliente, _es_transitorio(), Embeddings, Exception, Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el…

### Community 34 - "RerankerCrossEncoder"
Cohesion: 0.10
Nodes (17): Adaptadores del `RerankerPort`: cross-encoder local, con respaldos seguros. Por…, No reordena: devuelve el orden recibido. El respaldo seguro., Respaldo determinista: Jaccard de tokens. Sin red, sin modelo, sin sorpresas., Cross-encoder local vía `sentence-transformers`, con degradación a NO…, RerankerCrossEncoder, RerankerLexico, RerankerNulo, _tokens() (+9 more)

### Community 35 - "EvidenciaBian"
Cohesion: 0.18
Nodes (11): candidatos_operacion_elegibles(), clasificar_service_domains(), _decidir(), (decision_contractual, motivo_decision) a partir de los dos ejes. Determinista., Convierte la lista cruda del LLM en los 3 grupos, anclando cada SD a la…, SD con base suficiente para intentar anclar operaciones oficiales:…, EvidenciaBian, _p() (+3 more)

### Community 36 - "IntencionHistoriaLLM"
Cohesion: 0.32
Nodes (7): detectar_omitidos(), `ya_propuestos` = nombres de SD (normalizados) que el LLM ya evaluo (en…, IntencionHistoriaLLM, Interpretación funcional de la historia. Sin nombres de Service Domain., _cat(), 2º pase determinista: detección léxica de Service Domains que el LLM no propuso., TestDetectarOmitidos

### Community 38 - "ResultadoMapeoHistorias"
Cohesion: 0.31
Nodes (6): PublicadorMapeoPort, ABC, Puerto driven: persiste el resultado del mapeo Historias -> Service Domains., Escribe el resultado en `directorio` y devuelve la ruta del archivo., Documento final: la funcionalidad macro y la lista de historias con sus Service…, ResultadoMapeoHistorias

### Community 39 - "normalizar"
Cohesion: 0.17
Nodes (17): barrido(), evaluar(), main(), _qdrant(), _ranking(), Mide la recuperación de Service Domains sobre el corpus dorado. Sin llamadas…, Rejilla `k` x peso del canal disperso sobre UN canal fusionado. AVISO…, El vectorial es opcional: sin proveedor de embeddings utilizable se omite ese… (+9 more)

### Community 41 - "contenedor.py"
Cohesion: 0.18
Nodes (14): ConfiguracionProveedor, crear_estrategia(), MapearHistoriasUseCase, ABC, Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains., Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea…, _candidatos_embedding(), _cfg_proveedor() (+6 more)

### Community 42 - "svg_to_puml_control_record.py"
Cohesion: 0.10
Nodes (40): Point, apply_extensible_tags(), apply_note_and_box_tags(), _bbox_from_points(), classify_note(), _clean_label(), _closest_element(), _dist() (+32 more)

### Community 43 - "clasificacion_historias.py"
Cohesion: 0.11
Nodes (23): propuestos_degradados(), propuestos_promovidos(), Regla de dominio: ancla los Service Domains propuestos por el LLM a la…, Copia `propuestos_por_sd` con los SD de `promovidos` reescritos a…, Copia `propuestos_por_sd` con los SD de `degradados` reescritos a…, Tokens normalizados y traducidos al inglés, para cruzar catálogo con texto del…, Términos compartidos entre el nodo del catálogo y el objeto que el conflicto…, _tokens_comparables() (+15 more)

### Community 44 - "bian_object_catalog.py"
Cohesion: 0.14
Nodes (27): build_name_index(), _clean_html(), _col_to_idx(), _extract_documentation_sections(), _extract_js_object(), _fetch_text(), load_bian_bom_class_names(), load_business_area_names() (+19 more)

### Community 45 - "SoportaStructured"
Cohesion: 0.33
Nodes (3): Protocol, Lo mínimo que los adaptadores necesitan de un chat: `with_structured_output`.…, SoportaStructured

### Community 46 - "support.py"
Cohesion: 0.22
Nodes (12): cargar_config(), LLMConfig, MapearHistoriasConfig, ObservabilidadConfig, _proveedor(), ProveedorConfig, Carga y valida `config.yaml` — toda la configuración movible del proyecto. El…, Lee `config.yaml` (o `ruta`). Falla si no existe o es inválido. (+4 more)

### Community 48 - "EvaluacionCandidatoLLM"
Cohesion: 0.07
Nodes (19): ABC, Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`. Un solo…, CandidatoServiceDomainLLM, CandidatosHistoriaLLM, EvaluacionCandidatoLLM, Evaluación de UN candidato contra su paquete de evidencia. Señales ordinales,…, Proyecta la evaluación aislada de un candidato al registro de entrada del…, ReconciliacionFuncionalidadLLM (+11 more)

### Community 49 - "svg_to_puml.py"
Cohesion: 0.12
Nodes (28): _bbox_from_points(), classify_class_styles(), classify_note(), _clean_label(), _closest_class(), ensure_legend(), ExtractionReport, find_pairs() (+20 more)

### Community 50 - "crear_caso_uso"
Cohesion: 0.39
Nodes (3): crear_caso_uso(), Grafo completo sin API (proveedor 'fake'): camino exacto y camino RAG (léxico)…, TestGrafo

### Community 51 - "ServiceDomainAsignado"
Cohesion: 0.12
Nodes (10): DesgloseScore, Un Service Domain ya clasificado y enriquecido con evidencia de docs/ (Service…, ServiceDomainAsignado, _asignado(), _ChatEspia, Regresión: el revisor adversarial debe ver el MISMO Service Role que el…, Captura el prompt YA RENDERIZADO (lo que vería el modelo), sin llamar a…, TestServiceRoleEnRevisionAdversarial (+2 more)

### Community 52 - "OperacionBian"
Cohesion: 0.07
Nodes (25): _descargar(), Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh…, GET con reintentos + backoff sobre 429/5xx y errores de red transitorios., `#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el…, _ref_name(), _resolver_wrapper(), _schema_bom(), _schema_ref_de() (+17 more)

### Community 53 - "fusion_rrf"
Cohesion: 0.18
Nodes (6): fusion_rrf(), Reciprocal Rank Fusion: combina varios rankings (léxico, vectorial, ...) en uno…, Cada ranking es una lista de nombres YA ordenada por relevancia desc (mejor…, TestFusionPonderada, Reciprocal Rank Fusion: puro, sin API., TestFusionRRF

### Community 56 - "CLAUDE.md — generacion_contrato_ia_v2"
Cohesion: 0.25
Nodes (8): Antes de terminar cualquier cambio, CLAUDE.md — generacion_contrato_ia_v2, Comandos, Configuración: `config.yaml` + `.env`, Datos verificados (sept-2026), `mapear-historias` (detalle), Pruebas de integración/E2E — solo bajo demanda, REGLA OBLIGATORIA para cualquier cambio en `src/`

### Community 57 - "TestVueltaCorrectiva"
Cohesion: 0.14
Nodes (8): _Catalogo, _paquete(), La vuelta completa, con dobles mínimos: no hace falta el grafo entero para…, Devuelve operaciones solo para los SD que declare `con_evidencia`., _Recuperador, _Reloj, TestCondicionDeDisparo, TestVueltaCorrectiva

### Community 58 - "crear_caso_uso_mapeo"
Cohesion: 0.33
Nodes (7): crear_caso_uso_mapeo(), Léxico (siempre, sin API) + vectorial (best-effort: si no hay proveedor de…, _recuperadores_hibridos(), config_test(), Config determinista para tests: único proveedor `fake`, rutas reales de docs/., _entrada(), TestGrafoMapeo

### Community 59 - "Memory — generacion-contrato-ia-v2"
Cohesion: 0.17
Nodes (11): Artifacts, Commitments, Context, Errors, Estado del repo generacion_contrato_ia_v2 al 2026-..., Events, Memory — generacion-contrato-ia-v2, Namespace de MEMANTO para este proyecto configurad... (+3 more)

### Community 60 - "formato_bom.py"
Cohesion: 0.20
Nodes (8): formatear_schemas_bom(), _ordenar_priorizado(), Formateo compartido del BOM (schemas de la Semantic API + modelo de clases…, Reordena `elementos` (no los descarta) para que los que calzan `priorizar`…, `formatear_schemas_bom` truncaba en orden alfabético sin criterio de…, ¿Aparece `nombre` como CABECERA de schema (línea ` Nombre: {...}`)? Un `in`…, TestFormatearSchemasBomPriorizado, _tiene_schema()

### Community 61 - "Grafos LangGraph del proyecto"
Cohesion: 0.33
Nodes (5): 1. `validar-sd` — ¿existe este Service Domain?, 2. `mapear-historias` — grafo externo (map-reduce sobre las Historias de Usuario), 3. `mapear-historias` — subgrafo por Historia de Usuario (fan-out por candidato), Correspondencia nodo → código, Grafos LangGraph del proyecto

### Community 62 - "mapear_historias_service_domain.py"
Cohesion: 0.07
Nodes (39): MapeadorOperacionesBianPort, ABC, Puerto driven: paso 6 del mapeo — asigna operaciones oficiales BIAN a una…, _bom_respalda(), _es_transitorio(), _fusionar_mapeos(), _pascal(), Exception (+31 more)

### Community 63 - "Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)"
Cohesion: 0.18
Nodes (11): 0-bis. Qué ya estaba resuelto antes de esta iteración (no reabrir sin motivo), 0. Estado al 2026-09-14 (leer esto primero), 5. Fase 5 — Endurecimiento operativo, 6. Gates de aceptación (heredados del plan original, aplican a partir de aquí), 7. Dónde quedó cada pieza (referencia rápida), Implementación pendiente — recuperación híbrida BIAN (Fases 3-5), Justificación, Lo que la medición desmintió de este documento (+3 more)

### Community 64 - "Arquitectura hexagonal — reglas"
Cohesion: 0.25
Nodes (6): Arquitectura hexagonal — reglas, Cómo cambiar cosas sin romper la regla, El grafo (`aplicacion/servicios/validar_service_domain.py`), Puertos y adaptadores, Regla (se verifica en CI), Umbrales (`RAG_UMBRAL_ALTO` / `RAG_UMBRAL_BAJO`)

### Community 65 - "`mapear-historias` — Historias de Usuario → Service Domains"
Cohesion: 0.29
Nodes (7): El grafo — outer map-reduce + subgrafo por HU con fan-out por candidato, Flujo temporal (secuencia), JSON de entrada (`--funcionalidad`), `mapear-historias` — Historias de Usuario → Service Domains, Modelo de nodos (LangGraph), Operaciones personalizadas (no oficiales) — cuando el BOM respalda un campo sin cubrir, Salida (`mapeo-historias-service-domains.json`)

### Community 66 - "e2e_common.py"
Cohesion: 0.14
Nodes (19): _FirmaOperacion, TestCase, _candidatos_por_sd(), cargar_esperado(), ejecutar_caso(), _firma_operaciones(), _funcionalidad_de(), Path (+11 more)

### Community 67 - "Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1, Source Nodes

### Community 68 - "1. Fase 3 — Hybrid RAG "de verdad" (validar y, si corresponde, encender por defecto)"
Cohesion: 0.40
Nodes (5): 1. Fase 3 — Hybrid RAG "de verdad" (validar y, si corresponde, encender por defecto), Justificación de la secuencia, Pasos, Problema, Ventaja de resolverlo

### Community 69 - "2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión"
Cohesion: 0.40
Nodes (5): 2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión, Justificación, Pasos, Problema, Ventaja

### Community 70 - "3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide"
Cohesion: 0.40
Nodes (5): 3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide, Justificación, Pasos, Problema, Ventaja de resolverlo (condicional)

### Community 71 - "4. Fase 4 — Reranker + Graph RAG"
Cohesion: 0.40
Nodes (5): 4. Fase 4 — Reranker + Graph RAG, Justificación, Pasos, Problema, Ventaja

### Community 72 - "ADR 0001 — Índice vectorial: en memoria por defecto, Qdrant disponible"
Cohesion: 0.13
Nodes (12): ADR 0001 — Índice vectorial: en memoria por defecto, Qdrant disponible, Consecuencia inesperada del benchmark, Contexto, Decisión, Medición, infra/retrieval — índice vectorial externo (opcional), pgvector (no implementado), Qdrant (el implementado) (+4 more)

### Community 74 - "RecuperadorSemanticoPort"
Cohesion: 0.12
Nodes (14): InMemoryVectorStore, Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings. Dos scores por…, Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que…, similitud_nombre(), Adaptador `RecuperadorSemanticoPort` sobre Qdrant (índice externo, opcional).…, RecuperadorQdrant, Embeddings, Path (+6 more)

### Community 75 - "EmbeddingsConFailover"
Cohesion: 0.12
Nodes (12): _corto(), EmbeddingsConFailover, BaseException, Embeddings, RuntimeError, Fija el candidato activo probándolos en orden. Idempotente., TodosLosEmbeddingsAgotados, _Emb (+4 more)

### Community 76 - "MEMANTO Memory Skill"
Cohesion: 0.13
Nodes (14): After Important Work, Choosing Between recall and answer, Command Reference, Confidence Levels, MEMANTO Memory Skill, Memory Types: Decision Matrix, Patterns, Pitfalls to Avoid (+6 more)

### Community 77 - "setup_memanto.py"
Cohesion: 0.28
Nodes (12): CompletedProcess, configure_backend(), configure_onprem_state(), connect_codex(), create_or_activate_agent(), ensure_memanto_installed(), main(), Deploy AGENTS.md + skill so Codex CLI also knows to use MEMANTO. Idempotent:… (+4 more)

### Community 79 - "PaqueteEvidenciaCandidato"
Cohesion: 0.19
Nodes (9): _campos_respuesta(), _formatear(), _formatear_bom(), Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia…, `campos_respuesta={eMailAddress:ContactPoint, CellPhoneNumber:ContactPoint,…, PaqueteEvidenciaCandidato, Todo lo que el LLM ve para evaluar UN candidato. Se arma en código desde la…, Regresión directa del bug: el bloque `<operaciones_disponibles>` que arma… (+1 more)

### Community 80 - "resolver_operation_id"
Cohesion: 0.16
Nodes (6): Ancla un `operationId` propuesto por el LLM contra el catálogo REAL de…, resolver_operation_id(), Regresión del caso real observado en producción (corrida CLI real, failover a…, TestResolverOperationId, Un numero inventado se trata igual que un operationId inventado., TestCitaPorIndice

### Community 81 - "factory.py"
Cohesion: 0.14
Nodes (15): Factory + registro de estrategias de proveedor., GroqStrategy, Estrategia Groq — API compatible OpenAI, inferencia LPU muy rápida, free tier…, HuggingFaceStrategy, Estrategia Hugging Face — router de Inference Providers, API compatible OpenAI.…, OllamaStrategy, Embeddings, Estrategia Ollama — servidor propio (docker), API compatible OpenAI vía `/v1`.… (+7 more)

### Community 82 - "crear_checkpointer"
Cohesion: 0.12
Nodes (16): BaseCheckpointSaver, _clases_del_dominio(), crear_checkpointer(), Path, Adaptador: checkpointer persistente de LangGraph sobre SQLite. `durabilidad:…, Serializador con los modelos del dominio declarados como permitidos (o el de…, Checkpointer SQLite en `ruta`, creando la base y sus directorios si no existen., _serde() (+8 more)

### Community 83 - "TestDeterminarPromociones"
Cohesion: 0.21
Nodes (9): determinar_degradaciones(), determinar_promociones(), Nombres normalizados de SD que pasan de `CONSUMED_DEPENDENCY` a…, Nombres normalizados de SD que pasan de `OWNED_CONTRACT` a…, `determinar_promociones` / `propuestos_promovidos`: el caso real de "Notificar…, Reconstruye el dict que necesita `propuestos_promovidos` a partir del…, `determinar_degradaciones` / `propuestos_degradados`: el caso real de…, TestDeterminarDegradaciones (+1 more)

### Community 84 - "generate_entities.py"
Cohesion: 0.19
Nodes (22): build_bian_bom_catalog(), build_entities(), _clean_text(), _col_to_idx(), _extract_body(), _extract_reference(), _iter_diagram_files(), load_object_catalog() (+14 more)

### Community 85 - "fusionar_propuestas_de_operacion"
Cohesion: 0.40
Nodes (4): fusionar_propuestas_de_operacion(), Fusiona 2+ propuestas que YA se sabe que resuelven a la MISMA operación oficial…, Regresión del caso real: el LLM citó `InitiateOutbound` 4 veces para "Notificar…, TestFusionarPropuestasDeOperacion

### Community 86 - "_FakeChat"
Cohesion: 0.29
Nodes (4): ChatResult, _FakeChat, BaseChatModel, Runnable

### Community 87 - "download_svg_control_record.py"
Cohesion: 0.36
Nodes (7): extract_svg(), fetch(), main(), Descarga el SVG del "Control Record Diagram" de cada BIAN Service Domain…, Same convention already used by every file in docs/bian-diagrams/svg_bom/:…, The BIAN view pages are NOT rendered client-side for the diagram itself (only…, slugify()

### Community 88 - "svg_to_puml"
Cohesion: 0.25
Nodes (7): Alcance real del corpus, Como ejecutar, Extensible (color del borde de la clase), Por que existe, Que hace, paso a paso, Recomendacion antes de correrlo sobre todo el corpus, svg_to_puml

### Community 89 - "CLAUDE.md"
Cohesion: 0.29
Nodes (4): Cómo escribir una prueba E2E nueva, Pruebas E2E (LLM real, sin mocks), Qué compara `verificar_candidatos_y_operaciones()`, Regla obligatoria para toda prueba E2E nueva

### Community 90 - "bian_view_catalog.py"
Cohesion: 0.38
Nodes (6): build_catalog(), fetch_insite_views(), main(), Path, Genera un catalogo JSON {Service Domain -> link SD Overview, BOM Diagram,…, Returns {view_id: {"id": view_id, "name": "<title>"}} for every view published…

### Community 91 - "_FakeEmbeddings"
Cohesion: 0.36
Nodes (4): _FakeEmbeddings, FakeStrategy, Embeddings, Vector determinista por bolsa de trigramas hasheados. No es semántico, pero es…

### Community 92 - "MEMANTO - Your Active Memory Companion"
Cohesion: 0.33
Nodes (5): Command Reference, MEMANTO - Your Active Memory Companion, Memory Operations — Use the Right One, NON-NEGOTIABLE RULES, When to Call `remember` (Examples — Run Immediately)

### Community 93 - "bian_view_catalog"
Cohesion: 0.33
Nodes (5): bian_view_catalog, Como ejecutar, Como se encontro esto, Formato de salida, Nota

### Community 94 - "download_svg_control_record"
Cohesion: 0.33
Nodes (5): Como ejecutar, download_svg_control_record, Nombre de archivo, Por que funciona con un simple fetch (sin ejecutar JavaScript), Resultado

### Community 95 - "test_normalizacion_y_catalogo.py"
Cohesion: 0.20
Nodes (3): Normalización + carga real del catálogo BIAN único…, TestCatalogoJson, TestNormalizacion

### Community 96 - "BIAN UML / PlantUML extraction"
Cohesion: 0.40
Nodes (4): AI-oriented conventions, BIAN UML / PlantUML extraction, Counts, Extraction modes

### Community 97 - "TestE2EDatosPersonales"
Cohesion: 0.33
Nodes (4): requiere_e2e, Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks):…, Réplica del comando real de `mapear-historias` sobre…, TestE2EDatosPersonales

### Community 98 - "ChatConFailover"
Cohesion: 0.21
Nodes (5): ChatConFailover, Devuelve el modelo efectivo de la última llamada realizada en el hilo actual., Cada llamada arranca en el PRIMER modelo de la cadena — con una excepción por…, `PeticionDemasiadoGrande` existe para que quien armó el prompt pueda mandar…, TestFailoverReintentaLaCadenaEnCadaLlamada

### Community 99 - "_ChatGuion"
Cohesion: 0.33
Nodes (3): _ChatGuion, Runnable, Chat de mentira: `with_structured_output` devuelve un runnable que reproduce…

### Community 103 - "test_bm25_y_fusion.py"
Cohesion: 0.13
Nodes (11): RecuperadorBM25, IndiceBM25, BM25 Okapi sobre el catálogo BIAN. Puro: solo stdlib. Por qué existe, si ya…, Minúsculas, sin acentos, alfanumérico, sin palabras vacías, y **traducido al…, Índice invertido inmutable. Se construye una vez por catálogo y se consulta N…, `documentos` = [(identificador, texto)]. El identificador se devuelve tal cual., Top-k `(identificador, score)` desc. Los documentos sin ningún término de la…, tokenizar() (+3 more)

### Community 104 - "RevisionAdversarialLLM"
Cohesion: 0.19
Nodes (10): aplicar_hallazgos_adversariales(), _orden(), _finalizar_como_directo(), motivos_no_promocion(), Por QUÉ no calificó cada promoción que el revisor adversarial sí pidió.…, Mueve `objetivo` a `directos` (mutando las tres listas in-place) y fija…, Aplica la revisión adversarial de forma determinista. El revisor adversarial…, HallazgoAdversarial (+2 more)

### Community 105 - "TestCatalogoBianUnico"
Cohesion: 0.12
Nodes (10): La información de Service Domains sale de UN solo archivo: el BIAN Service…, `documentation` abre con `** 1. Role **`, y ese rol es el del propio Service…, SD.json es autoritativo en el valor; el landscape solo aporta el nombre del…, Un dato, un nombre: si dos campos traen lo mismo, sobra uno., Si `documentation` y `role_definition` dicen lo mismo, uno de los dos no aporta…, _service_domains(), TestCatalogoBianUnico, t() (+2 more)

### Community 106 - "cargar_settings"
Cohesion: 0.15
Nodes (17): _deformar(), generar(), main(), Genera, de forma determinista y reproducible, las capas del corpus dorado cuya…, Deformación determinista y declarada: abrevia la última palabra o quita una…, Muestreo repartido por TODO el catálogo (paso fijo), no los N primeros: si solo…, _slug(), _vecinos() (+9 more)

### Community 107 - "NodoBian"
Cohesion: 0.21
Nodes (12): id_nodo(), NodoBian, Identidad canónica de un nodo: estable entre corridas y entre releases., Una entidad del catálogo BIAN, identificada de forma canónica y estable., _clase(), _modela(), Modelo canónico BIAN: expansión por grafo acotada y auditable. La expansión…, Un SD 'A' y otro 'B' unidos solo por una clase que modelan `n_sd_en_hub` SD. (+4 more)

### Community 108 - "determinar_promociones_por_accion"
Cohesion: 0.25
Nodes (10): determinar_promociones_por_accion(), `CONSUMED_DEPENDENCY` -> `OWNED_CONTRACT` cuando el candidato se contradice a…, _grupos(), Cerrar la asimetria: un CONSUMED_DEPENDENCY mal clasificado tenia UNA salida, y…, Las dos reglas miran lo MISMO -- el cruce entre la accion citada y las acciones…, El caso legitimo de dependencia: la historia notifica, el SD actualiza., Sin hallazgo adversarial que respalde, el objeto de negocio tiene que coincidir…, _sd() (+2 more)

### Community 109 - "generate_matrix_view.py"
Cohesion: 0.22
Nodes (17): build_matrix_tree(), bd_node(), sd_node(), _clean(), _col_to_idx(), load_object_catalog_section(), load_sd_diagram_info(), load_sd_metadata() (+9 more)

### Community 110 - "session_start.py"
Cohesion: 0.21
Nodes (16): _claim(), install_statusline(), main(), _out(), _project_dir(), Path, Refresh MEMORY.md. Returns a one-line summary, or None if unavailable., Add our statusLine to the user's settings once. Never overwrite theirs. (+8 more)

### Community 111 - "enrich_service_landscape.py"
Cohesion: 0.20
Nodes (16): emparejar_campos(), enriquecer(), main(), Any, Path, Completa IN-PLACE `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`, la…, Completa el documento en memoria y devuelve el informe de lo que hizo., Un texto descriptivo no debe aparecer en dos atributos del mismo Service… (+8 more)

### Community 112 - "test_senales_grafo.py"
Cohesion: 0.21
Nodes (9): confirmar_conflictos_por_grafo(), ¿El catálogo BIAN respalda el conflicto de ownership que afirmó el revisor…, ObjetoCompartido, Un nodo del catálogo que MÁS DE UN Service Domain candidato toca, con su…, `True` si el nodo discrimina (mismo umbral que la expansión:…, El grafo canónico como señal DETERMINISTA para el conflicto de ownership. Hasta…, El caso real que obligó a añadir la tercera condición. Con 11 candidatos, la…, El nodo viene del catálogo en inglés y el objeto en disputa lo escribe el LLM… (+1 more)

### Community 113 - "_AnalistaQueRevienta"
Cohesion: 0.21
Nodes (5): _AnalistaQueRevienta, _entrada(), Path, Delega en el guion, pero revienta en `revisar_adversarial` mientras `caido` sea…, TestReanudarCorrida

### Community 114 - "_ejecutar"
Cohesion: 0.17
Nodes (8): _AnalistaSinPropietario, _ejecutar(), _MapeadorVacio, El peor resultado posible no puede ser el que mejor pinta en el JSON., El modelo respondio, pero no propuso ninguna operacion., Ningun candidato es propietario: la historia no produce contrato., TestHistoriaSinContrato, TestVisibilidadDeOperaciones

### Community 115 - "RecuperadorLexico"
Cohesion: 0.14
Nodes (4): RecuperadorLexico, La evidencia del punto 1: el término español NO existe en el corpus, su…, TestRecuperadorBM25, TestRecuperadorLexico

### Community 116 - "Decisions"
Cohesion: 0.13
Nodes (15): A escala de 341 Service Domains el recall de recup..., Arquitectura de mapear-historias: outer graph con ..., Asimetria estructural del ownership en generacion_..., BOM extendido: CatalogoBianCache._normalizar usa c..., Checkpointer persistente de generacion_contrato_bi..., Creados en generacion_contrato_ia_v2/scripts/ (sep..., Decision: para generacion_contrato_ia_v2 se usa el..., Decisiones de decision contractual anadidas a gene... (+7 more)

### Community 117 - "Learnings"
Cohesion: 0.13
Nodes (15): Al fijar el interprete de un venv para pyright en ..., Benchmark de recuperacion BIAN medido el 2026-09-1..., Causa raiz de un falso negativo real encontrado en..., Causa raiz del canal lexico debil en generacion_co..., docs/BIANv14.xlsm hoja 'Service Domains' tiene 2 t..., El link de bian.org a la pagina de un objeto tiene..., El reranker cross-encoder BAAI/bge-reranker-v2-m3 ..., El usuario de este proyecto verifica activamente l... (+7 more)

### Community 118 - "formatear_catalogo"
Cohesion: 0.19
Nodes (7): formatear_catalogo(), _formatear_indice_global(), Índice global compacto (nombre + rol muy recortado) para el hint de…, Una línea por SD: - "Nombre" · Area > Domain · [Patrón/AssetType] :: rol…, CAG escalonado: el catálogo del prompt como fuente completa, no como índice. A…, La afirmación que sostiene todo el enfoque, medida y no supuesta., TestCagCatalogo

### Community 119 - "GrafoBianPort"
Cohesion: 0.22
Nodes (9): Adaptador: expansión por el grafo canónico BIAN ingestado en `docs/bian-…, GrafoBianPort, ABC, Puerto driven: expansión de candidatos por el grafo canónico BIAN., Service Domains relacionados con los dados por relaciones VERIFICADAS del…, Objetos del catálogo que tocan dos o más de esos Service Domains, con…, CandidatoGrafo, Modelo canónico BIAN: nodos y relaciones tipadas, con procedencia. Hasta ahora… (+1 more)

### Community 120 - "ingest_bian.py"
Cohesion: 0.26
Nodes (9): _Constructor, ingestar(), _ingestar_bom(), _ingestar_operaciones(), main(), Construye el modelo canónico BIAN (`GrafoBian`) desde las fuentes de `docs/`.…, AristaBian, BaseModel (+1 more)

### Community 121 - "GrafoBian"
Cohesion: 0.23
Nodes (7): GrafoBian, El catálogo BIAN como grafo. Inmutable en la práctica: se reconstruye, no se…, Vecinos directos en ambos sentidos: una asociación del BOM no tiene dirección…, Nodos del catálogo que tocan DOS O MÁS de los `service_domains` dados. Dos…, En cuántos Service Domain aparece cada nodo compartido (clases del BOM, sobre…, Otros SD conectados a este por el propio BOM de BIAN, ordenados por…, TipoArista

### Community 122 - "Facts"
Cohesion: 0.17
Nodes (12): 7 Service Domains (ACH Operations, Correspondent B..., Conectividad validada el 2026-09-12: MEMANTO agent..., Configuracion del proyecto: .env = SOLO API keys (..., docs/BIAN_Service_Landscape_V14.0_Matrix_View.json..., docs/SD.json y docs/BIAN_Service_Landscape_V14.0_M..., El host de desarrollo (Ubuntu 24.04 aarch64, acces..., En el BIAN Service Landscape v14 dos invariantes e..., En los servidores de plataforma_trader el desplieg... (+4 more)

### Community 123 - "generate_entities"
Cohesion: 0.17
Nodes (11): 1. Los `.puml` ya extraidos en `docs/bian-diagrams/`, 2. `docs/BIANBOM4XMI.xlsx`, hoja **"BIAN BOM"**, 3. `docs/bian-view-catalog.json`, 4. (Opcional) `docs/bian-object-catalog.json`, Como ejecutar, Corrida de referencia, Decisiones de diseno / limitaciones conocidas, Formato de `entity.json` (+3 more)

### Community 124 - "generate_matrix_view"
Cohesion: 0.17
Nodes (11): `bom_diagram` / `control_record_diagram` / `sd_overview_url` (de `docs/entity.json`), Como ejecutar, Corrida de referencia, De donde sale esto (100% local, sin red), Formato de salida, `functional_pattern` / `asset_type` / `generic_artifact_type` / `control_record` / `registration_status` (de `docs/SD.json`), generate_matrix_view, Los 2 escenarios de anidamiento (+3 more)

### Community 125 - "notify.py"
Cohesion: 0.31
Nodes (10): _claim(), describe(), _emit(), _flag(), _int_after(), main(), _plain(), MEMANTO PostToolUse hook — turn raw CLI calls into a readable line. Without… (+2 more)

### Community 126 - "Convenciones del SVG (Bizzdesign) y como se mapean"
Cohesion: 0.18
Nodes (10): Atributos y su cardinalidad, Cardinalidad y rol de una relacion, Como ejecutar, Convenciones del SVG (Bizzdesign) y como se mapean, El estereotipo `«datatype»`/`«enumeration»` ya viene en el SVG, El recuadro "BIAN BOM" -> tag `BianBom: yes`, En que se diferencia de scripts/svg_to_puml, Que se descarta (a proposito) (+2 more)

### Community 127 - "TestTextoProsa"
Cohesion: 0.18
Nodes (3): Ni los 3 SD a los que el landscape no les publica algún campo., Si el documento no dice de qué SD habla, el cross-encoder compite a ciegas., TestTextoProsa

### Community 128 - "._cargar"
Cohesion: 0.24
Nodes (5): Any, Ruta del PUML BOM que el propio landscape declara por Service Domain…, Los vacíos del landscape ("", "None", null) se normalizan a None., Recorre Business Area -> Business Domain (anidable) -> Service Domain., _texto()

### Community 129 - "_grafo_con_clase_compartida"
Cohesion: 0.24
Nodes (4): _grafo_con_clase_compartida(), Dos SD que modelan la misma clase BOM, más `total_sd - 2` SD de relleno que…, Los dos casos reales del proyecto: ningún objeto ESPECÍFICO en común. Es el…, TestObjetosCompartidos

### Community 130 - "bian_object_catalog"
Cohesion: 0.22
Nodes (8): bian_object_catalog, Como ejecutar, Corrida de referencia, Desambiguacion, El problema: `<N>` no es un "tipo", es un shard, Formato de `bian-object-catalog.json`, Integracion con `scripts/generate_entities/`, Integracion con `scripts/generate_matrix_view/`

### Community 131 - "evaluate_retrieval"
Cohesion: 0.22
Nodes (8): Barrido de `k` y pesos, El corpus tiene capas, y NO se promedian, evaluate_retrieval, Lo que este benchmark NO mide, Lo que estos números dicen, Nota de entorno: caché de HuggingFace, Resultados actuales (97 consultas, 341 SD, `qwen3-embedding:8b`, 2026-09-14), Sobre el tamaño del corpus

### Community 132 - "GrafoBianJson"
Cohesion: 0.33
Nodes (3): GrafoBianJson, Path, TestGrafoBianJsonSinArchivo

### Community 133 - "enrich_service_landscape"
Cohesion: 0.25
Nodes (7): Cuándo volver a correrlo, enrich_service_landscape, Regla de nombres: un dato, un nombre, el del landscape, Regla de valores: en los campos emparejados manda SD.json, Rollback, Uso, Valores repetidos entre atributos

### Community 134 - "canary.py"
Cohesion: 0.39
Nodes (7): _correr(), diferencias(), main(), _por_historia(), Path, Compara DOS configuraciones del pipeline sobre el mismo lote de HU (canary /…, {archivo HU -> {service_domain -> 'decision/motivo'}} de los SD consolidados.

### Community 135 - "rebuild.py"
Cohesion: 0.43
Nodes (7): _id_determinista(), main(), Reconstruye el índice de recuperación desde las fuentes locales de `docs/`.…, Qdrant acepta enteros o UUID; un hash estable del nombre hace la carga…, _reconstruir_memoria(), _reconstruir_qdrant(), _embeddings()

### Community 136 - "analista_mapeo_langchain.py"
Cohesion: 0.39
Nodes (6): _formatear_operaciones(), Adaptador: el analista BIAN LLM del mapeo Historias -> Service Domains. Un…, Nombres normalizados de request/response schema de `operaciones` — para que…, _recortar(), _schemas_de_operaciones(), formatear_bom_puml()

### Community 137 - "cohere.py"
Cohesion: 0.29
Nodes (5): _api_key(), CohereStrategy, BaseChatModel, Embeddings, Estrategia Cohere — SOLO embeddings (retrieval multilingüe ES↔EN). `pip install…

### Community 139 - "OpenAIStrategy"
Cohesion: 0.32
Nodes (4): OpenAIStrategy, BaseChatModel, Embeddings, Estrategia OpenAI (opcional). `pip install langchain-openai`.

### Community 140 - ".texto_prosa"
Cohesion: 0.25
Nodes (6): _frase(), _limpiar_documentacion(), Une los trozos que existan en una sola frase legible, sin puntos dobles., `** 1. Role ** texto ** 2. Examples of use ** ...` -> `Role: texto. Examples of…, Texto del SD para el índice semántico. Incluye TODO lo que el Service Landscape…, Texto del Service Domain en PROSA, para un cross-encoder (no para un índice).…

### Community 141 - "test_smart_token_regresion.py"
Cohesion: 0.46
Nodes (3): _prop(), Regresión SMART_TOKEN: contra el catálogo real (341 SD) + la caché BIAN real…, TestSmartTokenRegresion

### Community 142 - "Ampliar el corpus dorado BIAN"
Cohesion: 0.29
Nodes (6): Ampliar el corpus dorado BIAN, Añadir un caso `hu_real` (el único que justifica cambiar un default), Lo primero: qué NO cuenta como ampliar el corpus, Qué mirar al terminar, Regenerar las capas objetivas, Si además hay que fijar el caso como regresión E2E

### Community 143 - "ingest_bian"
Cohesion: 0.29
Nodes (6): Cuándo regenerar, Entradas y salida, ingest_bian, Por qué, Reglas que no se relajan, Uso

### Community 144 - "TestPrioridadPorNodo"
Cohesion: 0.43
Nodes (3): `routing.llm_priority_por_nodo` da otro orden de proveedores a un nodo concreto., `--proveedor X` es una decisión del operador: no la puede pisar una entrada del…, TestPrioridadPorNodo

### Community 146 - "TestE2EDatosPersonalesNotificacion"
Cohesion: 0.33
Nodes (4): requiere_e2e, Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks):…, Réplica del comando real de `mapear-historias` usado para validar esta…, TestE2EDatosPersonalesNotificacion

### Community 147 - "9. Pendiente de verdad (2026-09-14, revisado tras implementar los 6 puntos)"
Cohesion: 0.40
Nodes (5): 9. Pendiente de verdad (2026-09-14, revisado tras implementar los 6 puntos), Cerrados el 2026-09-14 (los dos "extras menores" que quedaban anotados), Hecho en esta iteración, Lo que sigue pendiente, Retomar aquí cuando haya más HU etiquetadas (protocolo, 2026-09-15)

### Community 148 - "graphify-ollama.sh"
Cohesion: 0.40
Nodes (4): OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL, graphify-ollama.sh script

### Community 149 - "Instructions"
Cohesion: 0.50
Nodes (4): Doctrina de observabilidad de generacion_contrato_..., Instructions, Regla estadistica para juzgar corridas E2E en gene..., Un corpus de evaluacion de recuperacion debe tener...

### Community 151 - "Goals"
Cohesion: 0.67
Nodes (3): Goals, Pendiente en generacion_contrato_bian para retomar..., Retrieval hibrido RRF (src/dominio/fusion_rrf.py, ...

## Knowledge Gaps
- **249 isolated node(s):** `generacion-contrato-ia-v2`, `graphify-ollama.sh script`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_API_KEY` (+244 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 850 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CatalogoBianCache` connect `CatalogoBianCache` to `operacion_evidencia_verificable`, `EvidenciaBian`, `crear_caso_uso_mapeo`, `_Response`, `contenedor.py`, `test_smart_token_regresion.py`, `PaqueteEvidenciaCandidato`, `resolver_operation_id`, `_ejecutar`, `OperacionBian`, `CatalogoBomPuml`, `ingest_bian.py`, `historias.py`, `.__init__`, `formato_bom.py`, `mapear_historias_service_domain.py`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `normalizar()` connect `normalizar` to `._cargar`, `operacion_evidencia_verificable`, `CatalogoBianCache`, `EntradaCatalogo`, `analista_mapeo_langchain.py`, `rebuild.py`, `historias.py`, `MapearHistoriasServiceDomainsService`, `ServiceDomainsDeHistoria`, `EvidenciaBian`, `IntencionHistoriaLLM`, `clasificacion_historias.py`, `ServiceDomainAsignado`, `OperacionBian`, `TestVueltaCorrectiva`, `formato_bom.py`, `mapear_historias_service_domain.py`, `e2e_common.py`, `PaqueteEvidenciaCandidato`, `resolver_operation_id`, `TestDeterminarPromociones`, `test_normalizacion_y_catalogo.py`, `RevisionAdversarialLLM`, `cargar_settings`, `NodoBian`, `determinar_promociones_por_accion`, `test_senales_grafo.py`, `GrafoBianPort`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `CatalogoJson` connect `CatalogoBianCache` to `._cargar`, `rebuild.py`, `EntradaCatalogo`, `test_smart_token_regresion.py`, `CatalogoBomPuml`, `normalizar`, `contenedor.py`, `crear_caso_uso`, `crear_caso_uso_mapeo`, `mapear_historias_service_domain.py`, `test_normalizacion_y_catalogo.py`, `test_bm25_y_fusion.py`, `TestCatalogoBianUnico`, `cargar_settings`, `_ejecutar`, `RecuperadorLexico`, `formatear_catalogo`, `ingest_bian.py`, `TestTextoProsa`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 39 inferred relationships involving `MapearHistoriasServiceDomainsService` (e.g. with `AnalistaMapeoBianPort` and `CatalogoBomPort`) actually correct?**
  _`MapearHistoriasServiceDomainsService` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `CatalogoBianCache` (e.g. with `EvidenciaBian` and `OperacionBian`) actually correct?**
  _`CatalogoBianCache` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `CatalogoJson` (e.g. with `EntradaCatalogo` and `_recuperadores_hibridos()`) actually correct?**
  _`CatalogoJson` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `IntencionHistoriaLLM` (e.g. with `AnalistaMapeoBianLangChain` and `AnalistaMapeoBianPort`) actually correct?**
  _`IntencionHistoriaLLM` has 16 INFERRED edges - model-reasoned connections that need verification._