# Graph Report - generacion_contrato_ia_v2  (2026-09-10)

## Corpus Check
- 146 files · ~166,196 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 855 nodes · 2245 edges · 38 communities (26 shown, 12 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 228 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b544d6ac`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- clasificar
- factory.py
- historias.py
- test_arquitectura_hexagonal.py
- EntradaCatalogo
- EmbeddingsConFailover
- HistoriaUsuario
- contenedor.py
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
- Config
- fake.py
- MapearHistoriasServiceDomainsService
- analista_mapeo_langchain.py
- CatalogoBomPuml
- ResultadoValidacion
- CatalogoBianCache
- EvidenciaBian
- test_grafo_mapeo.py
- modelos.py
- ResultadoMapeoHistorias
- ValidarServiceDomainService
- EvaluacionCandidatoLLM
- EmbeddingsResiliente
- EstadoHistoria
- RecuperadorVectorial
- TestAgnosticismoPrompts
- salida/__init__.py

## God Nodes (most connected - your core abstractions)
1. `MapearHistoriasServiceDomainsService` - 58 edges
2. `EntradaCatalogo` - 42 edges
3. `HistoriaUsuario` - 40 edges
4. `FuncionalidadMacro` - 39 edges
5. `CatalogoBianCache` - 35 edges
6. `IntencionHistoriaLLM` - 32 edges
7. `EvidenciaBian` - 29 edges
8. `clasificar_service_domains()` - 28 edges
9. `OperacionBian` - 28 edges
10. `normalizar()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `TestGrafoMapeoSeleccionReal` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestSmartTokenRegresion` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_smart_token_regresion.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoSeleccionReal` --uses--> `CatalogoJson`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_json.py
- `TestSmartTokenRegresion` --uses--> `CatalogoJson`  [INFERRED]
  tests/test_smart_token_regresion.py → src/adaptadores/salida/catalogo_json.py
- `TestGrafoMapeoSeleccionReal` --uses--> `LectorHistoriasFilesystem`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/lector_historias_fs.py

## Import Cycles
- None detected.

## Communities (38 total, 12 thin omitted)

### Community 0 - "clasificar"
Cohesion: 0.19
Nodes (10): Banda, clasificar(), mejor_candidato(), Regla de dominio: clasifica el resultado del RAG en bandas por similitud…, El candidato con mayor similitud léxica estricta (no el mejor de recuperación)., Umbrales, _cand(), Regla de dominio: bandas por similitud (sin API, sin frameworks). (+2 more)

### Community 1 - "factory.py"
Cohesion: 0.05
Nodes (44): AnthropicStrategy, BaseChatModel, Embeddings, Estrategia Anthropic (opcional). `pip install langchain-anthropic`. Nota: usa…, _api_key(), CohereStrategy, BaseChatModel, Embeddings (+36 more)

### Community 2 - "historias.py"
Cohesion: 0.16
Nodes (19): Estado del subgrafo que procesa UNA Historia de Usuario. El outer graph hace…, _es_transitorio(), _paquete_de(), Exception, Caso de uso `MapearHistoriasUseCase` orquestado con LangGraph. Outer graph…, DecisionServiceDomainConsolidada, MetadatosPrompt, OperacionBianAplicada (+11 more)

### Community 3 - "test_arquitectura_hexagonal.py"
Cohesion: 0.23
Nodes (11): AST, ImportFrom, _capa(), _modulo(), _objetivos(), _paquete(), _permitido(), Path (+3 more)

### Community 4 - "EntradaCatalogo"
Cohesion: 0.06
Nodes (27): CatalogoJson, Path, Adaptador: carga el catálogo desde SD.json (columnas L..V) y lo enriquece con…, { nombre_normalizado -> (business_area, business_domain) }., Adaptador: catálogo local de operaciones oficiales por Service Domain. Fuente:…, Todas las entradas del catálogo., Coincidencia exacta tras normalizar (case/espacios/PascalCase). None si no…, detectar_omitidos() (+19 more)

### Community 5 - "EmbeddingsConFailover"
Cohesion: 0.06
Nodes (31): _corto(), EmbeddingsConFailover, BaseException, Embeddings, RuntimeError, Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.…, Fija el candidato activo probándolos en orden. Idempotente., TodosLosEmbeddingsAgotados (+23 more)

### Community 6 - "HistoriaUsuario"
Cohesion: 0.07
Nodes (35): CatalogoOperacionesBianJson, Path, LectorHistoriasFilesystem, Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad…, _titulo_desde_nombre(), _formatear(), MapeadorOperacionesLangChain, Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia.… (+27 more)

### Community 7 - "contenedor.py"
Cohesion: 0.17
Nodes (15): Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings. Dos scores por…, Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que…, RecuperadorLexico, similitud_nombre(), Adaptador RAG: índice vectorial en memoria sobre el catálogo (langchain-core…, CatalogoServiceDomainsPort, ABC, Puerto driven: acceso al catálogo de Service Domains (SD.json). (+7 more)

### Community 20 - "Config"
Cohesion: 0.05
Nodes (51): datetime, _forzar_utf8(), main(), _directorio_run(), _forzar_utf8(), main(), _parse(), Namespace (+43 more)

### Community 21 - "fake.py"
Cohesion: 0.11
Nodes (23): Any, ChatResult, _archivo_hu(), _bloque(), _FakeChat, _FakeEmbeddings, BaseChatModel, Embeddings (+15 more)

### Community 22 - "MapearHistoriasServiceDomainsService"
Cohesion: 0.18
Nodes (8): EstadoMapeo, TypedDict, Estado del grafo (outer) de mapeo Historias de Usuario -> Service Domains., MapearHistoriasServiceDomainsService, Reconcilia el mismo SD entre HU (determinista). Si alguna HU lo posee y quedó…, HistoriaConServiceDomains, Resultado del mapeo para una historia., ReconciliacionFuncionalidadLLM

### Community 23 - "analista_mapeo_langchain.py"
Cohesion: 0.13
Nodes (19): NamedTuple, Protocol, AnalistaMapeoBianLangChain, _formatear_bom_puml(), formatear_catalogo(), _formatear_indice_global(), _formatear_operaciones(), _formatear_schemas_bom() (+11 more)

### Community 24 - "CatalogoBomPuml"
Cohesion: 0.11
Nodes (20): CatalogoBomPuml, Path, Adaptador: lee los PUML BOM de `docs/bian-puml/` y los parsea a…, slug_service_domain(), CatalogoBomPort, ABC, Puerto driven: modelo estructural BOM (clases/enums/asociaciones) por Service…, Modelo de clases del PUML BOM del Service Domain, o None si no hay `.puml`… (+12 more)

### Community 25 - "ResultadoValidacion"
Cohesion: 0.18
Nodes (12): PublicadorJson, Adaptador de persistencia: escribe el resultado como JSON en el directorio del…, ABC, Puerto driving: la API que ofrece la aplicación., Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en…, ValidarServiceDomainUseCase, PublicadorResultadoPort, ABC (+4 more)

### Community 26 - "CatalogoBianCache"
Cohesion: 0.06
Nodes (23): CatalogoBianCache, _descargar(), Path, Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh…, GET con reintentos + backoff sobre 429/5xx y errores de red transitorios., `#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el…, _ref_name(), _resolver_wrapper() (+15 more)

### Community 27 - "EvidenciaBian"
Cohesion: 0.07
Nodes (33): clasificar_service_domains(), _decidir(), Regla de dominio: ancla los Service Domains propuestos por el LLM a la…, Convierte la lista cruda del LLM en los 3 grupos, anclando cada SD a la…, Resuelve `nombre` contra el índice normalizado del catálogo. Devuelve (entrada,…, (decision_contractual, motivo_decision) a partir de los dos ejes. Determinista., resolver_nombre_sd(), UmbralesMapeo (+25 more)

### Community 28 - "test_grafo_mapeo.py"
Cohesion: 0.14
Nodes (17): AnalistaMapeoBianPort, ABC, Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`. Un solo…, Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes…, Nodo 5: prompt DISTINTO que revisa la hipótesis ya clasificada (acción directa…, Nodo 7 (1 sola vez): ve todas las historias y propone el rol de cada SD a nivel…, aplicar_hallazgos_adversariales(), Aplica la revisión adversarial de forma determinista. El revisor adversarial es… (+9 more)

### Community 29 - "modelos.py"
Cohesion: 0.17
Nodes (15): AdjudicadorLangChain, _formatear_candidatos(), Adaptador: adjudica con un chat model de LangChain + salida estructurada., Prompt del adjudicador. Técnicas: rol explícito, descomposición de la tarea,…, AdjudicadorLLMPort, ABC, Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)., Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`. (+7 more)

### Community 30 - "ResultadoMapeoHistorias"
Cohesion: 0.14
Nodes (14): PublicadorMapeoJson, Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como…, MapearHistoriasUseCase, ABC, Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains., Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea…, PublicadorMapeoPort, ABC (+6 more)

### Community 31 - "ValidarServiceDomainService"
Cohesion: 0.28
Nodes (3): EstadoGrafo, TypedDict, ValidarServiceDomainService

### Community 32 - "EvaluacionCandidatoLLM"
Cohesion: 0.21
Nodes (6): Nodo 4: evalúa UN candidato contra SU paquete de evidencia oficial cerrado.…, EvaluacionCandidatoLLM, Evaluación de UN candidato contra su paquete de evidencia. Señales ordinales,…, Proyecta la evaluación aislada de un candidato al registro de entrada del…, Regresión de prompts: agnosticismo (sin hardcode de funcionalidad) + huella…, TestProyeccionEvaluacion

### Community 33 - "EmbeddingsResiliente"
Cohesion: 0.29
Nodes (6): _delay_sugerido(), EmbeddingsResiliente, _es_transitorio(), Embeddings, Exception, Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el…

### Community 34 - "EstadoHistoria"
Cohesion: 0.24
Nodes (3): EstadoHistoria, TypedDict, _huellas()

### Community 35 - "RecuperadorVectorial"
Cohesion: 0.36
Nodes (4): InMemoryVectorStore, Embeddings, Path, RecuperadorVectorial

## Knowledge Gaps
- **2 isolated node(s):** `generacion-contrato-ia-v2`, `setup.sh script`
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MapearHistoriasServiceDomainsService` connect `MapearHistoriasServiceDomainsService` to `EvaluacionCandidatoLLM`, `historias.py`, `EstadoHistoria`, `EntradaCatalogo`, `HistoriaUsuario`, `contenedor.py`, `Config`, `CatalogoBomPuml`, `CatalogoBianCache`, `EvidenciaBian`, `test_grafo_mapeo.py`, `ResultadoMapeoHistorias`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `CatalogoBianCache` connect `CatalogoBianCache` to `HistoriaUsuario`, `contenedor.py`, `Config`, `EvidenciaBian`, `test_grafo_mapeo.py`, `ResultadoMapeoHistorias`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Why does `EmbeddingsConFailover` connect `EmbeddingsConFailover` to `Config`, `contenedor.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `MapearHistoriasServiceDomainsService` (e.g. with `AnalistaMapeoBianPort` and `CatalogoBomPort`) actually correct?**
  _`MapearHistoriasServiceDomainsService` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `EntradaCatalogo` (e.g. with `AnalistaMapeoBianLangChain` and `formatear_catalogo()`) actually correct?**
  _`EntradaCatalogo` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `HistoriaUsuario` (e.g. with `AnalistaMapeoBianLangChain` and `LectorHistoriasFilesystem`) actually correct?**
  _`HistoriaUsuario` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `FuncionalidadMacro` (e.g. with `AnalistaMapeoBianLangChain` and `LectorHistoriasFilesystem`) actually correct?**
  _`FuncionalidadMacro` has 10 INFERRED edges - model-reasoned connections that need verification._