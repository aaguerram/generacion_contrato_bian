# Graph Report - generacion_contrato_ia_v2  (2026-09-13)

## Corpus Check
- 401 files · ~5,174,683 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1427 nodes · 3432 edges · 103 communities (88 shown, 15 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 367 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e36751f5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- clasificar
- factory.py
- test_cobertura_operaciones.py
- test_arquitectura_hexagonal.py
- UmbralesMapeo
- failover.py
- FuncionalidadMacro
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
- .__init__
- analista_mapeo_langchain.py
- historias.py
- modelos.py
- Plan de implementación: recuperación y decisión BIAN híbrida
- MapearHistoriasServiceDomainsService
- AnalistaMapeoBianPort
- CandidatoSD
- Config
- ValidarServiceDomainService
- generacion_contrato_ia_v2
- EmbeddingsResiliente
- MapearHistoriasUseCase
- CatalogoOperacionesBianPort
- IntencionHistoriaLLM
- salida/__init__.py
- ResultadoMapeoHistorias
- normalizar
- CatalogoBianCache
- contenedor.py
- svg_to_puml_v2.py
- RevisionAdversarialLLM
- RecuperadorVectorial
- SoportaStructured
- support.py
- EvaluacionCandidatoLLM
- ReconciliacionFuncionalidadLLM
- svg_to_puml.py
- crear_caso_uso
- mapear_historias_service_domain.py
- OperacionBian
- fusion_rrf
- bian-cache/README.md
- CLAUDE.md — generacion_contrato_ia_v2
- ._anclar_bq_personalizados
- crear_caso_uso_mapeo
- Memory — generacion-contrato-ia-v2
- mapeador_operaciones_langchain.py
- Grafos LangGraph del proyecto
- test_grafo_mapeo.py
- 5. Fase 5 — Endurecimiento operativo
- Arquitectura hexagonal — reglas
- `mapear-historias` — Historias de Usuario → Service Domains
- e2e_common.py
- Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1
- Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)
- 2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión
- 3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide
- 4. Fase 4 — Reranker + Graph RAG
- Infra de retrieval (OPCIONAL, diferida a Fase 3)
- RecuperadorSemanticoPort
- EmbeddingsConFailover
- MEMANTO Memory Skill
- setup_memanto.py
- TestChatConFailover
- PaqueteEvidenciaCandidato
- resolver_operation_id
- Convenciones del SVG (Bizzdesign) y como se mapean
- catalogo_bian_cache.py
- _directorio_run
- ._delegar
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
- TestCatalogoJson
- BIAN UML / PlantUML extraction
- TestE2EDatosPersonales
- .ultimo_uso
- _ChatGuion

## God Nodes (most connected - your core abstractions)
1. `MapearHistoriasServiceDomainsService` - 75 edges
2. `CatalogoBianCache` - 59 edges
3. `normalizar()` - 54 edges
4. `IntencionHistoriaLLM` - 45 edges
5. `RevisionAdversarialLLM` - 42 edges
6. `EntradaCatalogo` - 42 edges
7. `HistoriaUsuario` - 40 edges
8. `FuncionalidadMacro` - 39 edges
9. `OperacionBian` - 37 edges
10. `EvidenciaBian` - 37 edges

## Surprising Connections (you probably didn't know these)
- `TestResolverOperationId` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_cobertura_operaciones.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestFormatearSchemasBomPriorizado` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_formato_bom.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoDegradacionOwnership` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoFinalizacionPorOperacion` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoOperacionesDuplicadas` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/unit_test/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py

## Import Cycles
- None detected.

## Communities (103 total, 15 thin omitted)

### Community 0 - "clasificar"
Cohesion: 0.20
Nodes (10): Banda, clasificar(), mejor_candidato(), Regla de dominio: clasifica el resultado del RAG en bandas por similitud…, El candidato con mayor similitud léxica estricta (no el mejor de recuperación)., Umbrales, _cand(), Regla de dominio: bandas por similitud (sin API, sin frameworks). (+2 more)

### Community 1 - "factory.py"
Cohesion: 0.05
Nodes (40): AnthropicStrategy, BaseChatModel, Embeddings, Estrategia Anthropic (opcional). `pip install langchain-anthropic`. Nota: usa…, _api_key(), CohereStrategy, BaseChatModel, Embeddings (+32 more)

### Community 2 - "test_cobertura_operaciones.py"
Cohesion: 0.13
Nodes (13): derivar_path_grupo(), operacion_evidencia_verificable(), operation_id_en_uso(), Reglas de dominio deterministas para verificar cobertura de campos por…, ¿Alguna `evidence_ref` citada por el LLM coincide con un campo real alcanzable…, Path para una operación NUEVA dentro de un CR/BQ ya existente: toma el `path`…, ¿Ya existe ese operationId como operación OFICIAL real del Service Domain?…, _cache() (+5 more)

### Community 3 - "test_arquitectura_hexagonal.py"
Cohesion: 0.23
Nodes (11): AST, ImportFrom, _capa(), _modulo(), _objetivos(), _paquete(), _permitido(), Path (+3 more)

### Community 4 - "UmbralesMapeo"
Cohesion: 0.11
Nodes (18): CatalogoJson, Path, PublicadorMapeoJson, UmbralesMapeo, TestUmbralesMapeo, Regresión determinista (sin LLM real, caché BIAN real) del caso real observado…, Regresión determinista (sin LLM real) del bug de "Notificar actualización de…, Regresión determinista del caso real posterior a la corrección de promoción: un… (+10 more)

### Community 5 - "failover.py"
Cohesion: 0.23
Nodes (11): Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.…, _corto(), degradar_a_siguiente(), es_transitorio(), BaseException, RuntimeError, Chat con failover multi-proveedor / multi-modelo. Se recorre una lista ordenada…, TodosLosModelosAgotados (+3 more)

### Community 6 - "FuncionalidadMacro"
Cohesion: 0.17
Nodes (10): LectorHistoriasFilesystem, Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad…, _titulo_desde_nombre(), La funcionalidad macro + detalle desde un archivo JSON., FuncionalidadMacro, La funcionalidad macro a implementar y su detalle (contexto transversal a todas…, Construye desde un dict tolerando alias de claves (funcionalidad_macro/detalle…, Lectura de HU (.txt) y de la funcionalidad macro (JSON) desde el sistema de… (+2 more)

### Community 7 - "EntradaCatalogo"
Cohesion: 0.19
Nodes (10): Adaptador: carga el catálogo desde SD.json (columnas L..V) y lo enriquece con…, CatalogoServiceDomainsPort, ABC, Puerto driven: acceso al catálogo de Service Domains (SD.json)., Todas las entradas del catálogo., Coincidencia exacta tras normalizar (case/espacios/PascalCase). None si no…, EntradaCatalogo, Un BIAN Service Domain leído de SD.json (columnas L..V). `business_area` /… (+2 more)

### Community 20 - "cli_mapeo.py"
Cohesion: 0.15
Nodes (20): _forzar_utf8(), main(), _forzar_utf8(), main(), _parse(), Namespace, CLI: mapear-historias --directorio-hu <dir> --funcionalidad <f.json>…, _resumen() (+12 more)

### Community 21 - "fake.py"
Cohesion: 0.33
Nodes (13): Any, _archivo_hu(), _bloque(), Estrategia 'fake': chat y embeddings deterministas, sin API. Para tests y demo…, _responder_adversarial(), _responder_candidatos(), _responder_completitud(), _responder_evaluacion() (+5 more)

### Community 22 - ".__init__"
Cohesion: 0.20
Nodes (5): CatalogoBomPort, ABC, Puerto driven: modelo estructural BOM (clases/enums/asociaciones) por Service…, Modelo de clases del PUML BOM del Service Domain, o None si no hay `.puml`…, Slugs de los Service Domains que tienen `.puml` local.

### Community 23 - "analista_mapeo_langchain.py"
Cohesion: 0.15
Nodes (16): NamedTuple, AnalistaMapeoBianLangChain, _CadenaMedida, formatear_catalogo(), _formatear_indice_global(), _formatear_operaciones(), _lista(), Adaptador: el analista BIAN LLM del mapeo Historias -> Service Domains. Un… (+8 more)

### Community 24 - "historias.py"
Cohesion: 0.13
Nodes (22): CatalogoBomPuml, Path, Adaptador: lee los PUML BOM de `docs/bian-diagrams/puml-bom/` y los parsea a…, slug_service_domain(), AsociacionBom, AtributoBom, BqPersonalizadoAplicado, ClaseBom (+14 more)

### Community 25 - "modelos.py"
Cohesion: 0.15
Nodes (16): PublicadorJson, Adaptador de persistencia: escribe el resultado como JSON en el directorio del…, ABC, Puerto driving: la API que ofrece la aplicación., Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en…, ValidarServiceDomainUseCase, PublicadorResultadoPort, ABC (+8 more)

### Community 26 - "Plan de implementación: recuperación y decisión BIAN híbrida"
Cohesion: 0.06
Nodes (34): 10. Estrategia de pruebas, 11. Gates de aceptación, 12. Riesgos y mitigaciones, 13. Orden recomendado de implementación, 1. Resultado esperado, 2. Diagnóstico confirmado, 3. Principios de la solución, 4. Arquitectura objetivo consolidada (+26 more)

### Community 27 - "MapearHistoriasServiceDomainsService"
Cohesion: 0.12
Nodes (14): EstadoHistoria, TypedDict, EstadoMapeo, TypedDict, _huellas(), MapearHistoriasServiceDomainsService, RRF sobre los recuperadores configurados (léxico + vectorial, en memoria — ver…, Fase 0: nada debe perderse sin poder explicar en qué etapa se perdió. Tasas… (+6 more)

### Community 28 - "AnalistaMapeoBianPort"
Cohesion: 0.15
Nodes (10): AnalistaMapeoBianPort, ABC, Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`. Un solo…, Nodo 1: interpreta la historia. Sin nombres de Service Domain, sin decisiones…, Nodo 2: propone nombres de Service Domain del catálogo. Es una PISTA, no…, Nodo 4: evalúa UN candidato contra SU paquete de evidencia oficial cerrado.…, Nodo 5: prompt DISTINTO que revisa la hipótesis ya clasificada (acción directa…, Nodo 7 (1 sola vez): ve todas las historias y propone el rol de cada SD a nivel… (+2 more)

### Community 29 - "CandidatoSD"
Cohesion: 0.26
Nodes (12): AdjudicadorLangChain, _formatear_candidatos(), Adaptador: adjudica con un chat model de LangChain + salida estructurada., AdjudicadorLLMPort, ABC, Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)., Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`., CandidatoSD (+4 more)

### Community 31 - "ValidarServiceDomainService"
Cohesion: 0.26
Nodes (3): EstadoGrafo, TypedDict, ValidarServiceDomainService

### Community 32 - "generacion_contrato_ia_v2"
Cohesion: 0.15
Nodes (13): Configuración: `config.yaml` + `.env`, Cómo decide  —  y cómo se garantiza la reproducibilidad, El grafo, Estructura, generacion_contrato_ia_v2, Instalación, LangSmith (observabilidad), MEMANTO (memoria de agentes) (+5 more)

### Community 33 - "EmbeddingsResiliente"
Cohesion: 0.29
Nodes (6): _delay_sugerido(), EmbeddingsResiliente, _es_transitorio(), Embeddings, Exception, Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el…

### Community 34 - "MapearHistoriasUseCase"
Cohesion: 0.40
Nodes (4): MapearHistoriasUseCase, ABC, Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains., Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea…

### Community 35 - "CatalogoOperacionesBianPort"
Cohesion: 0.14
Nodes (10): CatalogoOperacionesBianPort, ABC, Puerto driven: catálogo local de operaciones oficiales por Service Domain…, Nombres de schema / objetos BOM del Service Domain, o lista vacía si no hay…, Schemas de la Semantic API con cuerpo (properties / enum values), o lista vacía., Vista `control_records` / `behavior_qualifiers` (con parent_control_record), o…, Operaciones oficiales (CR + BQ) del Service Domain, o None si no hay catálogo…, Nombres canónicos de los Service Domains que tienen catálogo de operaciones… (+2 more)

### Community 36 - "IntencionHistoriaLLM"
Cohesion: 0.31
Nodes (7): detectar_omitidos(), Segundo pase determinista: detecta Service Domains que el LLM NO propuso. No…, `ya_propuestos` = nombres de SD (normalizados) que el LLM ya evaluo (en…, IntencionHistoriaLLM, Interpretación funcional de la historia. Sin nombres de Service Domain., 2º pase determinista: detección léxica de Service Domains que el LLM no propuso., TestDetectarOmitidos

### Community 38 - "ResultadoMapeoHistorias"
Cohesion: 0.27
Nodes (7): Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como…, PublicadorMapeoPort, ABC, Puerto driven: persiste el resultado del mapeo Historias -> Service Domains., Escribe el resultado en `directorio` y devuelve la ruta del archivo., Documento final: la funcionalidad macro y la lista de historias con sus Service…, ResultadoMapeoHistorias

### Community 39 - "normalizar"
Cohesion: 0.17
Nodes (10): Nombres normalizados de request/response schema de `operaciones` — para que…, _schemas_de_operaciones(), { nombre_normalizado -> (business_area, business_domain) }., Adaptador: catálogo local de operaciones oficiales por Service Domain. Fuente:…, construir_indice_exacto(), normalizar(), Normalización de nombres de Service Domain para la coincidencia exacta., Issued Device Administration', 'IssuedDeviceAdministration',… (+2 more)

### Community 40 - "CatalogoBianCache"
Cohesion: 0.12
Nodes (6): CatalogoBianCache, Path, _Response, TestCatalogoBianCache, Camino directo real (SELECTED + operaciones) usando la caché BIAN sembrada de…, TestGrafoMapeoSeleccionReal

### Community 41 - "contenedor.py"
Cohesion: 0.23
Nodes (12): ConfiguracionProveedor, crear_estrategia(), EntradaModelo, _candidatos_embedding(), _cfg_proveedor(), crear_chat_failover(), _embeddings(), _entradas_llm() (+4 more)

### Community 42 - "svg_to_puml_v2.py"
Cohesion: 0.11
Nodes (40): Point, apply_extensible_tags(), apply_note_and_box_tags(), _bbox_from_points(), classify_note(), _clean_label(), _closest_element(), _dist() (+32 more)

### Community 43 - "RevisionAdversarialLLM"
Cohesion: 0.05
Nodes (48): aplicar_hallazgos_adversariales(), candidatos_operacion_elegibles(), clasificar_service_domains(), _decidir(), determinar_degradaciones(), determinar_promociones(), _finalizar_como_directo(), propuestos_degradados() (+40 more)

### Community 44 - "RecuperadorVectorial"
Cohesion: 0.36
Nodes (4): InMemoryVectorStore, Embeddings, Path, RecuperadorVectorial

### Community 45 - "SoportaStructured"
Cohesion: 0.20
Nodes (4): Protocol, Runnable, Lo mínimo que los adaptadores necesitan de un chat: `with_structured_output`.…, SoportaStructured

### Community 46 - "support.py"
Cohesion: 0.22
Nodes (12): cargar_config(), LLMConfig, MapearHistoriasConfig, ObservabilidadConfig, _proveedor(), ProveedorConfig, Carga y valida `config.yaml` — toda la configuración movible del proyecto. El…, Lee `config.yaml` (o `ruta`). Falla si no existe o es inválido. (+4 more)

### Community 47 - "EvaluacionCandidatoLLM"
Cohesion: 0.10
Nodes (9): Prompt del adjudicador. Técnicas: rol explícito, descomposición de la tarea,…, EvaluacionCandidatoLLM, Evaluación de UN candidato contra su paquete de evidencia. Señales ordinales,…, Proyecta la evaluación aislada de un candidato al registro de entrada del…, _AnalistaSinCandidatos, El LLM no propone NADA (ni candidatos ni missing_candidates): el único origen…, Regresión de prompts: agnosticismo (sin hardcode de funcionalidad) + huella…, TestAgnosticismoPrompts (+1 more)

### Community 48 - "ReconciliacionFuncionalidadLLM"
Cohesion: 0.11
Nodes (13): Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes…, CandidatoServiceDomainLLM, CandidatosHistoriaLLM, ReconciliacionFuncionalidadLLM, RevisionCompletitudLLM, _AnalistaActualizacionMalClasificada, _AnalistaGuion, _AnalistaNotificacion (+5 more)

### Community 49 - "svg_to_puml.py"
Cohesion: 0.13
Nodes (28): _bbox_from_points(), classify_class_styles(), classify_note(), _clean_label(), _closest_class(), ensure_legend(), ExtractionReport, find_pairs() (+20 more)

### Community 50 - "crear_caso_uso"
Cohesion: 0.39
Nodes (3): crear_caso_uso(), Grafo completo sin API (proveedor 'fake'): camino exacto y camino RAG (léxico)…, TestGrafo

### Community 51 - "mapear_historias_service_domain.py"
Cohesion: 0.11
Nodes (21): LectorHistoriasPort, ABC, Puerto driven: lee las Historias de Usuario y la funcionalidad macro de la…, Todas las Historias de Usuario del `directorio`, ordenadas por nombre de…, Estado del subgrafo que procesa UNA Historia de Usuario. El outer graph hace…, Estado del grafo (outer) de mapeo Historias de Usuario -> Service Domains., _es_transitorio(), _paquete_de() (+13 more)

### Community 52 - "OperacionBian"
Cohesion: 0.15
Nodes (10): CatalogoOperacionesBianJson, Path, FakeStrategy, MapeadorOperacionesLangChain, OperacionBian, Una operación oficial de un Service Domain (Control Record o Behavior…, _fake_chat(), Catálogo local de operaciones BIAN + paso 2 (mapeador) sin API. (+2 more)

### Community 53 - "fusion_rrf"
Cohesion: 0.26
Nodes (5): fusion_rrf(), Reciprocal Rank Fusion: combina varios rankings (léxico, vectorial, ...) en uno…, Cada ranking es una lista de nombres YA ordenada por relevancia desc (mejor…, Reciprocal Rank Fusion: puro, sin API., TestFusionRRF

### Community 56 - "CLAUDE.md — generacion_contrato_ia_v2"
Cohesion: 0.25
Nodes (8): Antes de terminar cualquier cambio, CLAUDE.md — generacion_contrato_ia_v2, Comandos, Configuración: `config.yaml` + `.env`, Datos verificados (sept-2026), `mapear-historias` (detalle), Pruebas de integración/E2E — solo bajo demanda, REGLA OBLIGATORIA para cualquier cambio en `src/`

### Community 57 - "._anclar_bq_personalizados"
Cohesion: 0.21
Nodes (7): _bom_respalda(), _pascal(), ¿`paquete` (schemas_detalle + bom_modelo) tiene de verdad esa clase/atributo?…, Determinista: una operación personalizada SOLO se ancla si (a)…, campos_alcanzables(), Nombres de propiedad (normalizados) del schema raíz, 1 nivel — el mismo alcance…, TestCamposAlcanzables

### Community 58 - "crear_caso_uso_mapeo"
Cohesion: 0.37
Nodes (6): crear_caso_uso_mapeo(), _sha256_archivo(), config_test(), Config determinista para tests: único proveedor `fake`, rutas reales de docs/., _entrada(), TestGrafoMapeo

### Community 59 - "Memory — generacion-contrato-ia-v2"
Cohesion: 0.07
Nodes (27): Arquitectura de mapear-historias: outer graph con ..., Artifacts, BOM extendido: CatalogoBianCache._normalizar usa c..., Causa raiz de un falso negativo real encontrado en..., Commitments, Configuracion del proyecto: .env = SOLO API keys (..., Context, Decision: para generacion_contrato_ia_v2 se usa el... (+19 more)

### Community 60 - "mapeador_operaciones_langchain.py"
Cohesion: 0.17
Nodes (11): formatear_bom_puml(), formatear_schemas_bom(), _ordenar_priorizado(), Formateo compartido del BOM (schemas de la Semantic API + modelo de clases…, Reordena `elementos` (no los descarta) para que los que calzan `priorizar`…, _formatear_bom(), Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia…, `formatear_schemas_bom` truncaba en orden alfabético sin criterio de… (+3 more)

### Community 61 - "Grafos LangGraph del proyecto"
Cohesion: 0.33
Nodes (5): 1. `validar-sd` — ¿existe este Service Domain?, 2. `mapear-historias` — grafo externo (map-reduce sobre las Historias de Usuario), 3. `mapear-historias` — subgrafo por Historia de Usuario (fan-out por candidato), Correspondencia nodo → código, Grafos LangGraph del proyecto

### Community 62 - "test_grafo_mapeo.py"
Cohesion: 0.17
Nodes (18): MapeadorOperacionesBianPort, ABC, Puerto driven: paso 6 del mapeo — asigna operaciones oficiales BIAN a una…, Devuelve, por Service Domain, las operaciones oficiales que implementan la…, BqPersonalizadoPropuestoLLM, MapeoOperacionesLLM, OperacionPropuestaLLM, Una operación oficial que el LLM asigna a una historia dentro de un Service… (+10 more)

### Community 63 - "5. Fase 5 — Endurecimiento operativo"
Cohesion: 0.40
Nodes (5): 5. Fase 5 — Endurecimiento operativo, Justificación, Pasos, Problema, Ventaja

### Community 64 - "Arquitectura hexagonal — reglas"
Cohesion: 0.25
Nodes (6): Arquitectura hexagonal — reglas, Cómo cambiar cosas sin romper la regla, El grafo (`aplicacion/servicios/validar_service_domain.py`), Puertos y adaptadores, Regla (se verifica en CI), Umbrales (`RAG_UMBRAL_ALTO` / `RAG_UMBRAL_BAJO`)

### Community 65 - "`mapear-historias` — Historias de Usuario → Service Domains"
Cohesion: 0.29
Nodes (7): El grafo — outer map-reduce + subgrafo por HU con fan-out por candidato, Flujo temporal (secuencia), JSON de entrada (`--funcionalidad`), `mapear-historias` — Historias de Usuario → Service Domains, Modelo de nodos (LangGraph), Operaciones personalizadas (no oficiales) — cuando el BOM respalda un campo sin cubrir, Salida (`mapeo-historias-service-domains.json`)

### Community 66 - "e2e_common.py"
Cohesion: 0.11
Nodes (19): _FirmaOperacion, TestCase, _candidatos_por_sd(), cargar_esperado(), ejecutar_caso(), _firma_operaciones(), _funcionalidad_de(), Path (+11 more)

### Community 67 - "Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1, Source Nodes

### Community 68 - "Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)"
Cohesion: 0.22
Nodes (9): 0. Qué ya está resuelto (no reabrir sin motivo), 1. Fase 3 — Hybrid RAG "de verdad" (validar y, si corresponde, encender por defecto), 6. Gates de aceptación (heredados del plan original, aplican a partir de aquí), 7. Dónde quedó cada pieza (referencia rápida), Implementación pendiente — recuperación híbrida BIAN (Fases 3-5), Justificación de la secuencia, Pasos, Problema (+1 more)

### Community 69 - "2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión"
Cohesion: 0.40
Nodes (5): 2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión, Justificación, Pasos, Problema, Ventaja

### Community 70 - "3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide"
Cohesion: 0.40
Nodes (5): 3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide, Justificación, Pasos, Problema, Ventaja de resolverlo (condicional)

### Community 71 - "4. Fase 4 — Reranker + Graph RAG"
Cohesion: 0.40
Nodes (5): 4. Fase 4 — Reranker + Graph RAG, Justificación, Pasos, Problema, Ventaja

### Community 72 - "Infra de retrieval (OPCIONAL, diferida a Fase 3)"
Cohesion: 0.40
Nodes (4): Cuándo usar esto, Infra de retrieval (OPCIONAL, diferida a Fase 3), Por qué no ambos, y por qué no ahora, Uso

### Community 74 - "RecuperadorSemanticoPort"
Cohesion: 0.13
Nodes (11): Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings. Dos scores por…, Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que…, RecuperadorLexico, similitud_nombre(), Adaptador RAG: índice vectorial en memoria sobre el catálogo (langchain-core…, ABC, Puerto driven: recuperación semántica (RAG) sobre el catálogo., Top-k Service Domains más parecidos a la consulta, ordenados por similitud desc. (+3 more)

### Community 75 - "EmbeddingsConFailover"
Cohesion: 0.19
Nodes (7): EmbeddingsConFailover, Embeddings, _Emb, Embeddings, Exception, Failover de embeddings multi-modelo, en orden de precisión (sin API)., TestEmbeddingsConFailover

### Community 76 - "MEMANTO Memory Skill"
Cohesion: 0.13
Nodes (14): After Important Work, Choosing Between recall and answer, Command Reference, Confidence Levels, MEMANTO Memory Skill, Memory Types: Decision Matrix, Patterns, Pitfalls to Avoid (+6 more)

### Community 77 - "setup_memanto.py"
Cohesion: 0.25
Nodes (12): CompletedProcess, configure_backend(), configure_onprem_state(), connect_codex(), create_or_activate_agent(), ensure_memanto_installed(), main(), Deploy AGENTS.md + skill so Codex CLI also knows to use MEMANTO. Idempotent:… (+4 more)

### Community 78 - "TestChatConFailover"
Cohesion: 0.33
Nodes (3): ChatConFailover, _entrada(), TestChatConFailover

### Community 79 - "PaqueteEvidenciaCandidato"
Cohesion: 0.23
Nodes (7): _campos_respuesta(), _formatear(), `campos_respuesta={eMailAddress:ContactPoint, CellPhoneNumber:ContactPoint,…, PaqueteEvidenciaCandidato, Todo lo que el LLM ve para evaluar UN candidato. Se arma en código desde la…, Regresión directa del bug: el bloque `<operaciones_disponibles>` que arma…, TestFormatearOperacionesConCamposDeRespuesta

### Community 80 - "resolver_operation_id"
Cohesion: 0.26
Nodes (4): Ancla un `operationId` propuesto por el LLM contra el catálogo REAL de…, resolver_operation_id(), Regresión del caso real observado en producción (corrida CLI real, failover a…, TestResolverOperationId

### Community 81 - "Convenciones del SVG (Bizzdesign) y como se mapean"
Cohesion: 0.18
Nodes (10): Atributos y su cardinalidad, Cardinalidad y rol de una relacion, Como ejecutar, Convenciones del SVG (Bizzdesign) y como se mapean, El estereotipo `«datatype»`/`«enumeration»` ya viene en el SVG, El recuadro "BIAN BOM" -> tag `BianBom: yes`, En que se diferencia de scripts/svg_to_puml, Que se descarta (a proposito) (+2 more)

### Community 82 - "catalogo_bian_cache.py"
Cohesion: 0.29
Nodes (8): _descargar(), Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh…, GET con reintentos + backoff sobre 429/5xx y errores de red transitorios., `#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el…, _ref_name(), _resolver_wrapper(), _schema_bom(), _schema_ref_de()

### Community 83 - "_directorio_run"
Cohesion: 0.29
Nodes (6): datetime, _directorio_run(), Path, `<base>/<AAAA-MM-DD_HH-MM-SS>/` por ejecución (o `<base>` con --sin-timestamp)., CLI mapear-historias: resolución del directorio de salida por ejecución., TestDirectorioRun

### Community 84 - "._delegar"
Cohesion: 0.24
Nodes (5): _corto(), BaseException, RuntimeError, Fija el candidato activo probándolos en orden. Idempotente., TodosLosEmbeddingsAgotados

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
Cohesion: 0.43
Nodes (3): _FakeEmbeddings, Embeddings, Vector determinista por bolsa de trigramas hasheados. No es semántico, pero es…

### Community 92 - "MEMANTO - Your Active Memory Companion"
Cohesion: 0.33
Nodes (5): Command Reference, MEMANTO - Your Active Memory Companion, Memory Operations — Use the Right One, NON-NEGOTIABLE RULES, When to Call `remember` (Examples — Run Immediately)

### Community 93 - "bian_view_catalog"
Cohesion: 0.33
Nodes (5): bian_view_catalog, Como ejecutar, Como se encontro esto, Formato de salida, Nota

### Community 94 - "download_svg_control_record"
Cohesion: 0.33
Nodes (5): Como ejecutar, download_svg_control_record, Nombre de archivo, Por que funciona con un simple fetch (sin ejecutar JavaScript), Resultado

### Community 96 - "BIAN UML / PlantUML extraction"
Cohesion: 0.40
Nodes (4): AI-oriented conventions, BIAN UML / PlantUML extraction, Counts, Extraction modes

### Community 97 - "TestE2EDatosPersonales"
Cohesion: 0.40
Nodes (4): requiere_e2e, Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks):…, Réplica del comando real de `mapear-historias` sobre…, TestE2EDatosPersonales

### Community 98 - ".ultimo_uso"
Cohesion: 0.50
Nodes (3): Devuelve el modelo efectivo de la última llamada realizada en el hilo actual., Modelo que resolvió la invocación actual del hilo., UsoModelo

## Knowledge Gaps
- **155 isolated node(s):** `generacion-contrato-ia-v2`, `setup.sh script`, `Memory Types: Decision Matrix`, `Confidence Levels`, `Provenance Types` (+150 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CatalogoBianCache` connect `CatalogoBianCache` to `test_cobertura_operaciones.py`, `CatalogoOperacionesBianPort`, `UmbralesMapeo`, `contenedor.py`, `RevisionAdversarialLLM`, `PaqueteEvidenciaCandidato`, `resolver_operation_id`, `catalogo_bian_cache.py`, `OperacionBian`, `historias.py`, `crear_caso_uso_mapeo`, `mapeador_operaciones_langchain.py`, `test_grafo_mapeo.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `MapearHistoriasServiceDomainsService` connect `MapearHistoriasServiceDomainsService` to `UmbralesMapeo`, `EntradaCatalogo`, `.__init__`, `historias.py`, `AnalistaMapeoBianPort`, `MapearHistoriasUseCase`, `CatalogoOperacionesBianPort`, `ResultadoMapeoHistorias`, `CatalogoBianCache`, `contenedor.py`, `RevisionAdversarialLLM`, `EvaluacionCandidatoLLM`, `ReconciliacionFuncionalidadLLM`, `mapear_historias_service_domain.py`, `._anclar_bq_personalizados`, `crear_caso_uso_mapeo`, `test_grafo_mapeo.py`, `RecuperadorSemanticoPort`, `PaqueteEvidenciaCandidato`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `EntradaCatalogo` connect `EntradaCatalogo` to `UmbralesMapeo`, `IntencionHistoriaLLM`, `normalizar`, `RevisionAdversarialLLM`, `ReconciliacionFuncionalidadLLM`, `mapear_historias_service_domain.py`, `analista_mapeo_langchain.py`, `modelos.py`, `MapearHistoriasServiceDomainsService`, `AnalistaMapeoBianPort`, `CandidatoSD`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `MapearHistoriasServiceDomainsService` (e.g. with `AnalistaMapeoBianPort` and `CatalogoBomPort`) actually correct?**
  _`MapearHistoriasServiceDomainsService` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `CatalogoBianCache` (e.g. with `EvidenciaBian` and `OperacionBian`) actually correct?**
  _`CatalogoBianCache` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `IntencionHistoriaLLM` (e.g. with `AnalistaMapeoBianLangChain` and `AnalistaMapeoBianPort`) actually correct?**
  _`IntencionHistoriaLLM` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `RevisionAdversarialLLM` (e.g. with `AnalistaMapeoBianLangChain` and `AnalistaMapeoBianPort`) actually correct?**
  _`RevisionAdversarialLLM` has 15 INFERRED edges - model-reasoned connections that need verification._