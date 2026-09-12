# Graph Report - generacion_contrato_ia_v2  (2026-09-11)

## Corpus Check
- 161 files · ~576,556 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 983 nodes · 2519 edges · 64 communities (48 shown, 16 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 250 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3c8d8fbf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- clasificar
- factory.py
- test_cobertura_operaciones.py
- test_arquitectura_hexagonal.py
- CatalogoJson
- EmbeddingsConFailover
- LectorHistoriasFilesystem
- CatalogoServiceDomainsPort
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
- MapearHistoriasServiceDomainsService
- HistoriaUsuario
- historias.py
- ResultadoValidacion
- CatalogoBianCache
- test_smart_token_regresion.py
- EntradaCatalogo
- modelos.py
- Config
- ValidarServiceDomainService
- generacion_contrato_ia_v2
- EmbeddingsResiliente
- mapear_historias_service_domain.py
- MapeadorOperacionesLangChain
- failover.py
- salida/__init__.py
- contenedor.py
- ._delegar
- SchemaBom
- EntradaModelo
- TestChatConFailover
- normalizar
- RecuperadorVectorial
- SoportaStructured
- support.py
- EvaluacionCandidatoLLM
- BIAN UML / PlantUML extraction
- cargar_settings
- crear_caso_uso
- ReconciliacionFuncionalidadLLM
- _Response
- _ChatGuion
- bian-cache/README.md
- _directorio_run
- catalogo_bian_cache.py
- crear_caso_uso_mapeo
- UmbralesMapeo
- test_mapeador_operaciones_langchain.py
- Grafos LangGraph del proyecto
- TestAgnosticismoPrompts

## God Nodes (most connected - your core abstractions)
1. `MapearHistoriasServiceDomainsService` - 60 edges
2. `CatalogoBianCache` - 45 edges
3. `normalizar()` - 43 edges
4. `EntradaCatalogo` - 42 edges
5. `HistoriaUsuario` - 40 edges
6. `FuncionalidadMacro` - 39 edges
7. `OperacionBian` - 36 edges
8. `EvidenciaBian` - 32 edges
9. `IntencionHistoriaLLM` - 32 edges
10. `clasificar_service_domains()` - 28 edges

## Surprising Connections (you probably didn't know these)
- `TestCatalogoBianCache` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_catalogo_bian_cache.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestFormatearSchemasBomPriorizado` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_formato_bom.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoSeleccionReal` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestFormatearOperacionesConCamposDeRespuesta` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_mapeador_operaciones_langchain.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestSmartTokenRegresion` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_smart_token_regresion.py → src/adaptadores/salida/catalogo_bian_cache.py

## Import Cycles
- None detected.

## Communities (64 total, 16 thin omitted)

### Community 0 - "clasificar"
Cohesion: 0.20
Nodes (10): Banda, clasificar(), mejor_candidato(), Regla de dominio: clasifica el resultado del RAG en bandas por similitud…, El candidato con mayor similitud léxica estricta (no el mejor de recuperación)., Umbrales, _cand(), Regla de dominio: bandas por similitud (sin API, sin frameworks). (+2 more)

### Community 1 - "factory.py"
Cohesion: 0.05
Nodes (43): AnthropicStrategy, BaseChatModel, Embeddings, Estrategia Anthropic (opcional). `pip install langchain-anthropic`. Nota: usa…, _api_key(), CohereStrategy, BaseChatModel, Embeddings (+35 more)

### Community 2 - "test_cobertura_operaciones.py"
Cohesion: 0.10
Nodes (16): campos_alcanzables(), derivar_path_grupo(), operacion_evidencia_verificable(), operation_id_en_uso(), Reglas de dominio deterministas para verificar cobertura de campos por…, Nombres de propiedad (normalizados) del schema raíz, 1 nivel — el mismo alcance…, ¿Alguna `evidence_ref` citada por el LLM coincide con un campo real alcanzable…, Path para una operación NUEVA dentro de un CR/BQ ya existente: toma el `path`… (+8 more)

### Community 3 - "test_arquitectura_hexagonal.py"
Cohesion: 0.23
Nodes (11): AST, ImportFrom, _capa(), _modulo(), _objetivos(), _paquete(), _permitido(), Path (+3 more)

### Community 4 - "CatalogoJson"
Cohesion: 0.18
Nodes (4): CatalogoJson, Path, { nombre_normalizado -> (business_area, business_domain) }., TestCatalogoJson

### Community 5 - "EmbeddingsConFailover"
Cohesion: 0.19
Nodes (7): EmbeddingsConFailover, Embeddings, _Emb, Embeddings, Exception, Failover de embeddings multi-modelo, en orden de precisión (sin API)., TestEmbeddingsConFailover

### Community 6 - "LectorHistoriasFilesystem"
Cohesion: 0.12
Nodes (12): LectorHistoriasFilesystem, Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad…, _titulo_desde_nombre(), LectorHistoriasPort, ABC, Puerto driven: lee las Historias de Usuario y la funcionalidad macro de la…, Todas las Historias de Usuario del `directorio`, ordenadas por nombre de…, La funcionalidad macro + detalle desde un archivo JSON. (+4 more)

### Community 7 - "CatalogoServiceDomainsPort"
Cohesion: 0.11
Nodes (13): Adaptador: carga el catálogo desde SD.json (columnas L..V) y lo enriquece con…, Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings. Dos scores por…, Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que…, RecuperadorLexico, similitud_nombre(), Adaptador RAG: índice vectorial en memoria sobre el catálogo (langchain-core…, CatalogoServiceDomainsPort, ABC (+5 more)

### Community 20 - "cli_mapeo.py"
Cohesion: 0.19
Nodes (14): _forzar_utf8(), main(), _forzar_utf8(), main(), _parse(), Namespace, CLI: mapear-historias --directorio-hu <dir> --funcionalidad <f.json>…, _resumen() (+6 more)

### Community 21 - "fake.py"
Cohesion: 0.12
Nodes (21): Any, ChatResult, _archivo_hu(), _bloque(), _FakeChat, _FakeEmbeddings, BaseChatModel, Embeddings (+13 more)

### Community 22 - "MapearHistoriasServiceDomainsService"
Cohesion: 0.10
Nodes (18): EstadoHistoria, TypedDict, EstadoMapeo, TypedDict, _huellas(), MapearHistoriasServiceDomainsService, Reconcilia el mismo SD entre HU (determinista). Si alguna HU lo posee y quedó…, DecisionServiceDomainConsolidada (+10 more)

### Community 23 - "HistoriaUsuario"
Cohesion: 0.16
Nodes (22): NamedTuple, AnalistaMapeoBianLangChain, formatear_catalogo(), _formatear_indice_global(), _formatear_operaciones(), _lista(), Adaptador: el analista BIAN LLM del mapeo Historias -> Service Domains. Un…, Una línea por SD: - "Nombre" · Area > Domain · [Patrón/AssetType] :: rol… (+14 more)

### Community 24 - "historias.py"
Cohesion: 0.05
Nodes (50): CatalogoBomPuml, Path, Adaptador: lee los PUML BOM de `docs/bian-puml/` y los parsea a…, slug_service_domain(), Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia…, PublicadorMapeoJson, Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como…, CatalogoBomPort (+42 more)

### Community 25 - "ResultadoValidacion"
Cohesion: 0.23
Nodes (9): PublicadorJson, Adaptador de persistencia: escribe el resultado como JSON en el directorio del…, Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en…, PublicadorResultadoPort, ABC, Puerto driven: persistencia del resultado en el directorio del run., Escribe el resultado en `directorio` y devuelve la ruta del archivo., Resultado final del nodo de validación. (+1 more)

### Community 26 - "CatalogoBianCache"
Cohesion: 0.25
Nodes (3): CatalogoBianCache, Path, PropiedadSchema

### Community 27 - "test_smart_token_regresion.py"
Cohesion: 0.46
Nodes (3): _prop(), Regresión SMART_TOKEN: contra el catálogo real (341 SD) + la caché BIAN real…, TestSmartTokenRegresion

### Community 28 - "EntradaCatalogo"
Cohesion: 0.17
Nodes (14): AnalistaMapeoBianPort, ABC, Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`. Un solo…, Nodo 2: propone nombres de Service Domain del catálogo. Es una PISTA, no…, Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes…, Nodo 5: prompt DISTINTO que revisa la hipótesis ya clasificada (acción directa…, Estado del subgrafo que procesa UNA Historia de Usuario. El outer graph hace…, CandidatosHistoriaLLM (+6 more)

### Community 29 - "modelos.py"
Cohesion: 0.19
Nodes (14): AdjudicadorLangChain, _formatear_candidatos(), Adaptador: adjudica con un chat model de LangChain + salida estructurada., Prompt del adjudicador. Técnicas: rol explícito, descomposición de la tarea,…, AdjudicadorLLMPort, ABC, Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)., Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`. (+6 more)

### Community 30 - "Config"
Cohesion: 0.19
Nodes (6): Config, ProveedorConfig, Path, _candidatos_embedding(), _embeddings(), Lista ordenada por precisión: proveedores de `embedding_priority` × sus…

### Community 31 - "ValidarServiceDomainService"
Cohesion: 0.26
Nodes (3): EstadoGrafo, TypedDict, ValidarServiceDomainService

### Community 32 - "generacion_contrato_ia_v2"
Cohesion: 0.06
Nodes (33): Arquitectura hexagonal — reglas, Cómo cambiar cosas sin romper la regla, El grafo (`aplicacion/servicios/validar_service_domain.py`), Puertos y adaptadores, Regla (se verifica en CI), Umbrales (`RAG_UMBRAL_ALTO` / `RAG_UMBRAL_BAJO`), Antes de terminar cualquier cambio, CLAUDE.md — generacion_contrato_ia_v2 (+25 more)

### Community 33 - "EmbeddingsResiliente"
Cohesion: 0.29
Nodes (6): _delay_sugerido(), EmbeddingsResiliente, _es_transitorio(), Embeddings, Exception, Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el…

### Community 34 - "mapear_historias_service_domain.py"
Cohesion: 0.23
Nodes (10): _bom_respalda(), _es_transitorio(), _paquete_de(), _pascal(), Exception, Caso de uso `MapearHistoriasUseCase` orquestado con LangGraph. Outer graph…, ¿`paquete` (schemas_detalle + bom_modelo) tiene de verdad esa clase/atributo?…, Determinista: una operación personalizada SOLO se ancla si (a)… (+2 more)

### Community 35 - "MapeadorOperacionesLangChain"
Cohesion: 0.08
Nodes (17): CatalogoOperacionesBianJson, Path, Adaptador: catálogo local de operaciones oficiales por Service Domain. Fuente:…, FakeStrategy, MapeadorOperacionesLangChain, CatalogoOperacionesBianPort, ABC, Puerto driven: catálogo local de operaciones oficiales por Service Domain… (+9 more)

### Community 36 - "failover.py"
Cohesion: 0.23
Nodes (11): Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.…, _corto(), degradar_a_siguiente(), es_transitorio(), BaseException, RuntimeError, Chat con failover multi-proveedor / multi-modelo. Se recorre una lista ordenada…, TodosLosModelosAgotados (+3 more)

### Community 38 - "contenedor.py"
Cohesion: 0.19
Nodes (11): ABC, Puerto driving: la API que ofrece la aplicación., ValidarServiceDomainUseCase, ABC, Puerto driven: recuperación semántica (RAG) sobre el catálogo., Top-k Service Domains más parecidos a la consulta, ordenados por similitud desc., RecuperadorSemanticoPort, _es_transitorio() (+3 more)

### Community 39 - "._delegar"
Cohesion: 0.24
Nodes (5): _corto(), BaseException, RuntimeError, Fija el candidato activo probándolos en orden. Idempotente., TodosLosEmbeddingsAgotados

### Community 40 - "SchemaBom"
Cohesion: 0.16
Nodes (12): formatear_bom_puml(), formatear_schemas_bom(), _ordenar_priorizado(), Formateo compartido del BOM (schemas de la Semantic API + modelo de clases…, Reordena `elementos` (no los descarta) para que los que calzan `priorizar`…, _formatear_bom(), Un schema de `components.schemas` del OpenAPI oficial, con su cuerpo (no solo…, SchemaBom (+4 more)

### Community 41 - "EntradaModelo"
Cohesion: 0.22
Nodes (3): ChatConFailover, EntradaModelo, Runnable

### Community 43 - "normalizar"
Cohesion: 0.05
Nodes (48): _campos_respuesta(), _formatear(), `campos_respuesta={eMailAddress:ContactPoint, CellPhoneNumber:ContactPoint,…, aplicar_hallazgos_adversariales(), clasificar_service_domains(), _decidir(), Regla de dominio: ancla los Service Domains propuestos por el LLM a la…, Convierte la lista cruda del LLM en los 3 grupos, anclando cada SD a la… (+40 more)

### Community 44 - "RecuperadorVectorial"
Cohesion: 0.36
Nodes (4): InMemoryVectorStore, Embeddings, Path, RecuperadorVectorial

### Community 45 - "SoportaStructured"
Cohesion: 0.33
Nodes (3): Protocol, Lo mínimo que los adaptadores necesitan de un chat: `with_structured_output`.…, SoportaStructured

### Community 46 - "support.py"
Cohesion: 0.27
Nodes (13): cargar_config(), LLMConfig, MapearHistoriasConfig, ObservabilidadConfig, _proveedor(), Carga y valida `config.yaml` — toda la configuración movible del proyecto. El…, Lee `config.yaml` (o `ruta`). Falla si no existe o es inválido., RoutingConfig (+5 more)

### Community 47 - "EvaluacionCandidatoLLM"
Cohesion: 0.21
Nodes (7): Prompts del mapeo Historia de Usuario -> BIAN Service Domains. Un prompt por…, _spec(), EvaluacionCandidatoLLM, Evaluación de UN candidato contra su paquete de evidencia. Señales ordinales,…, Proyecta la evaluación aislada de un candidato al registro de entrada del…, Regresión de prompts: agnosticismo (sin hardcode de funcionalidad) + huella…, TestProyeccionEvaluacion

### Community 48 - "BIAN UML / PlantUML extraction"
Cohesion: 0.40
Nodes (4): AI-oriented conventions, BIAN UML / PlantUML extraction, Counts, Extraction modes

### Community 49 - "cargar_settings"
Cohesion: 0.21
Nodes (9): skipUnless, _asegurar_env(), cargar_settings(), Path, Punto de entrada de configuración: carga el `.env` (solo API keys) y…, Carga la configuración efectiva. `esfuerzo` (opcional) pisa `llm.esfuerzo` del…, Prueba de integración END-TO-END real (sin `--proveedor fake`, sin mocks):…, Réplica exacta del comando real de `mapear-historias` sobre `./HU` + la… (+1 more)

### Community 50 - "crear_caso_uso"
Cohesion: 0.39
Nodes (3): crear_caso_uso(), Grafo completo sin API (proveedor 'fake'): camino exacto y camino RAG (léxico)…, TestGrafo

### Community 51 - "ReconciliacionFuncionalidadLLM"
Cohesion: 0.18
Nodes (5): Nodo 7 (1 sola vez): ve todas las historias y propone el rol de cada SD a nivel…, Estado del grafo (outer) de mapeo Historias de Usuario -> Service Domains., ReconciliacionFuncionalidadLLM, _AnalistaGuion, Analista scriptado: TA propietario directo, Fraud Evaluation dependencia de…

### Community 53 - "_ChatGuion"
Cohesion: 0.40
Nodes (3): _ChatGuion, Runnable, Chat de mentira: `with_structured_output` devuelve un runnable que reproduce…

### Community 56 - "_directorio_run"
Cohesion: 0.29
Nodes (6): datetime, _directorio_run(), Path, `<base>/<AAAA-MM-DD_HH-MM-SS>/` por ejecución (o `<base>` con --sin-timestamp)., CLI mapear-historias: resolución del directorio de salida por ejecución., TestDirectorioRun

### Community 57 - "catalogo_bian_cache.py"
Cohesion: 0.31
Nodes (8): _descargar(), Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh…, GET con reintentos + backoff sobre 429/5xx y errores de red transitorios., `#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el…, _ref_name(), _resolver_wrapper(), _schema_bom(), _schema_ref_de()

### Community 58 - "crear_caso_uso_mapeo"
Cohesion: 0.40
Nodes (4): crear_caso_uso_mapeo(), _sha256_archivo(), _entrada(), TestGrafoMapeo

### Community 59 - "UmbralesMapeo"
Cohesion: 0.29
Nodes (4): UmbralesMapeo, TestUmbralesMapeo, Camino directo real (SELECTED + operaciones) usando la caché BIAN sembrada de…, TestGrafoMapeoSeleccionReal

### Community 61 - "Grafos LangGraph del proyecto"
Cohesion: 0.33
Nodes (5): 1. `validar-sd` — ¿existe este Service Domain?, 2. `mapear-historias` — grafo externo (map-reduce sobre las Historias de Usuario), 3. `mapear-historias` — subgrafo por Historia de Usuario (fan-out por candidato), Correspondencia nodo → código, Grafos LangGraph del proyecto

## Knowledge Gaps
- **35 isolated node(s):** `generacion-contrato-ia-v2`, `setup.sh script`, `Regla (se verifica en CI)`, `Puertos y adaptadores`, `El grafo (`aplicacion/servicios/validar_service_domain.py`)` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CatalogoBianCache` connect `CatalogoBianCache` to `test_cobertura_operaciones.py`, `MapeadorOperacionesLangChain`, `CatalogoJson`, `contenedor.py`, `SchemaBom`, `test_smart_token_regresion.py`, `normalizar`, `_Response`, `historias.py`, `catalogo_bian_cache.py`, `crear_caso_uso_mapeo`, `UmbralesMapeo`, `test_mapeador_operaciones_langchain.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `MapearHistoriasServiceDomainsService` connect `MapearHistoriasServiceDomainsService` to `mapear_historias_service_domain.py`, `MapeadorOperacionesLangChain`, `LectorHistoriasFilesystem`, `CatalogoServiceDomainsPort`, `contenedor.py`, `normalizar`, `ReconciliacionFuncionalidadLLM`, `HistoriaUsuario`, `historias.py`, `crear_caso_uso_mapeo`, `UmbralesMapeo`, `EntradaCatalogo`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `EmbeddingsConFailover` connect `EmbeddingsConFailover` to `failover.py`, `Config`, `contenedor.py`, `._delegar`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `MapearHistoriasServiceDomainsService` (e.g. with `AnalistaMapeoBianPort` and `CatalogoBomPort`) actually correct?**
  _`MapearHistoriasServiceDomainsService` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `CatalogoBianCache` (e.g. with `EvidenciaBian` and `OperacionBian`) actually correct?**
  _`CatalogoBianCache` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `EntradaCatalogo` (e.g. with `AnalistaMapeoBianLangChain` and `formatear_catalogo()`) actually correct?**
  _`EntradaCatalogo` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `HistoriaUsuario` (e.g. with `AnalistaMapeoBianLangChain` and `LectorHistoriasFilesystem`) actually correct?**
  _`HistoriaUsuario` has 10 INFERRED edges - model-reasoned connections that need verification._