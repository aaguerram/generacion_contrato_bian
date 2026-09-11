# Graph Report - generacion_contrato_ia_v2  (2026-09-10)

## Corpus Check
- 147 files · ~559,881 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 868 nodes · 2300 edges · 56 communities (43 shown, 13 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 237 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b544d6ac`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- clasificar
- factory.py
- PaqueteEvidenciaCandidato
- test_arquitectura_hexagonal.py
- EntradaCatalogo
- EmbeddingsConFailover
- FuncionalidadMacro
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
- cli.py
- fake.py
- MapearHistoriasServiceDomainsService
- HistoriaUsuario
- historias.py
- validar_service_domain.py
- CatalogoBianCache
- test_clasificacion_historias.py
- mapear_historias_service_domain.py
- modelos.py
- ResultadoMapeoHistorias
- ValidarServiceDomainService
- test_prompts_mapeo.py
- EmbeddingsResiliente
- ._anclar_bq_personalizados
- OperacionBian
- cli_mapeo.py
- salida/__init__.py
- IntencionHistoriaLLM
- support.py
- analista_mapeo_langchain.py
- contenedor.py
- UmbralesMapeo
- ServiceDomainPropuestoLLM
- EvidenciaBian
- CatalogoBomPuml
- crear_caso_uso_mapeo
- Config
- calcular_score
- _FakeChat
- crear_caso_uso
- _FakeEmbeddings
- TestCatalogoJson
- ServiceDomainsDeHistoria
- MetadatosPrompt
- clasificacion_historias.py

## God Nodes (most connected - your core abstractions)
1. `MapearHistoriasServiceDomainsService` - 60 edges
2. `EntradaCatalogo` - 42 edges
3. `HistoriaUsuario` - 40 edges
4. `FuncionalidadMacro` - 39 edges
5. `CatalogoBianCache` - 35 edges
6. `IntencionHistoriaLLM` - 32 edges
7. `normalizar()` - 31 edges
8. `EvidenciaBian` - 29 edges
9. `clasificar_service_domains()` - 28 edges
10. `OperacionBian` - 28 edges

## Surprising Connections (you probably didn't know these)
- `TestGrafoMapeoSeleccionReal` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestSmartTokenRegresion` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_smart_token_regresion.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoSeleccionReal` --uses--> `CatalogoJson`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_json.py
- `TestCatalogoJson` --uses--> `CatalogoJson`  [INFERRED]
  tests/test_normalizacion_y_catalogo.py → src/adaptadores/salida/catalogo_json.py
- `TestSmartTokenRegresion` --uses--> `CatalogoJson`  [INFERRED]
  tests/test_smart_token_regresion.py → src/adaptadores/salida/catalogo_json.py

## Import Cycles
- None detected.

## Communities (56 total, 13 thin omitted)

### Community 0 - "clasificar"
Cohesion: 0.20
Nodes (10): Banda, clasificar(), mejor_candidato(), Regla de dominio: clasifica el resultado del RAG en bandas por similitud…, El candidato con mayor similitud léxica estricta (no el mejor de recuperación)., Umbrales, _cand(), Regla de dominio: bandas por similitud (sin API, sin frameworks). (+2 more)

### Community 1 - "factory.py"
Cohesion: 0.05
Nodes (38): AnthropicStrategy, BaseChatModel, Embeddings, Estrategia Anthropic (opcional). `pip install langchain-anthropic`. Nota: usa…, _api_key(), CohereStrategy, BaseChatModel, Embeddings (+30 more)

### Community 2 - "PaqueteEvidenciaCandidato"
Cohesion: 0.16
Nodes (16): MapeadorOperacionesBianPort, ABC, Puerto driven: paso 6 del mapeo — asigna operaciones oficiales BIAN a una…, Devuelve, por Service Domain, las operaciones oficiales que implementan la…, _bom_respalda(), _paquete_de(), ¿`paquete` (schemas_detalle + bom_modelo) tiene de verdad esa clase/atributo?…, BqPersonalizadoPropuestoLLM (+8 more)

### Community 3 - "test_arquitectura_hexagonal.py"
Cohesion: 0.23
Nodes (11): AST, ImportFrom, _capa(), _modulo(), _objetivos(), _paquete(), _permitido(), Path (+3 more)

### Community 4 - "EntradaCatalogo"
Cohesion: 0.09
Nodes (17): CatalogoJson, Path, Adaptador: carga el catálogo desde SD.json (columnas L..V) y lo enriquece con…, { nombre_normalizado -> (business_area, business_domain) }., Todas las entradas del catálogo., Coincidencia exacta tras normalizar (case/espacios/PascalCase). None si no…, EntradaCatalogo, Un BIAN Service Domain leído de SD.json (columnas L..V). `business_area` /… (+9 more)

### Community 5 - "EmbeddingsConFailover"
Cohesion: 0.06
Nodes (30): _corto(), EmbeddingsConFailover, BaseException, Embeddings, RuntimeError, Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.…, Fija el candidato activo probándolos en orden. Idempotente., TodosLosEmbeddingsAgotados (+22 more)

### Community 6 - "FuncionalidadMacro"
Cohesion: 0.13
Nodes (14): LectorHistoriasFilesystem, Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad…, _titulo_desde_nombre(), LectorHistoriasPort, ABC, Puerto driven: lee las Historias de Usuario y la funcionalidad macro de la…, Todas las Historias de Usuario del `directorio`, ordenadas por nombre de…, La funcionalidad macro + detalle desde un archivo JSON. (+6 more)

### Community 7 - "CatalogoServiceDomainsPort"
Cohesion: 0.13
Nodes (16): InMemoryVectorStore, Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings. Dos scores por…, Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que…, RecuperadorLexico, similitud_nombre(), Embeddings, Path, Adaptador RAG: índice vectorial en memoria sobre el catálogo (langchain-core… (+8 more)

### Community 20 - "cli.py"
Cohesion: 0.17
Nodes (14): _forzar_utf8(), main(), _parse(), Namespace, CLI: validar-sd --service-domain "<nombre>" --directorio <ruta> Nodo 1 del…, estrategias_disponibles(), configurar_langsmith(), Activa el trazado de LangSmith desde `config.yaml` (observabilidad) +… (+6 more)

### Community 21 - "fake.py"
Cohesion: 0.33
Nodes (13): Any, _archivo_hu(), _bloque(), Estrategia 'fake': chat y embeddings deterministas, sin API. Para tests y demo…, _responder_adversarial(), _responder_candidatos(), _responder_completitud(), _responder_evaluacion() (+5 more)

### Community 22 - "MapearHistoriasServiceDomainsService"
Cohesion: 0.12
Nodes (12): EstadoHistoria, TypedDict, EstadoMapeo, TypedDict, _huellas(), MapearHistoriasServiceDomainsService, Reconcilia el mismo SD entre HU (determinista). Si alguna HU lo posee y quedó…, DecisionServiceDomainConsolidada (+4 more)

### Community 23 - "HistoriaUsuario"
Cohesion: 0.27
Nodes (10): AnalistaMapeoBianLangChain, formatear_catalogo(), _formatear_indice_global(), _formatear_operaciones(), _lista(), Una línea por SD: - "Nombre" · Area > Domain · [Patrón/AssetType] :: rol…, Índice global compacto (solo nombre + rol muy recortado) para el hint de…, _recortar() (+2 more)

### Community 24 - "historias.py"
Cohesion: 0.13
Nodes (22): Adaptador: lee los PUML BOM de `docs/bian-puml/` y los parsea a…, slug_service_domain(), CatalogoBomPort, ABC, Puerto driven: modelo estructural BOM (clases/enums/asociaciones) por Service…, Modelo de clases del PUML BOM del Service Domain, o None si no hay `.puml`…, Slugs de los Service Domains que tienen `.puml` local., AsociacionBom (+14 more)

### Community 25 - "validar_service_domain.py"
Cohesion: 0.16
Nodes (15): PublicadorJson, Adaptador de persistencia: escribe el resultado como JSON en el directorio del…, ABC, Puerto driving: la API que ofrece la aplicación., Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en…, ValidarServiceDomainUseCase, PublicadorResultadoPort, ABC (+7 more)

### Community 26 - "CatalogoBianCache"
Cohesion: 0.10
Nodes (12): CatalogoBianCache, _descargar(), Path, Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh…, GET con reintentos + backoff sobre 429/5xx y errores de red transitorios., `#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el…, _ref_name(), _resolver_wrapper() (+4 more)

### Community 27 - "test_clasificacion_historias.py"
Cohesion: 0.21
Nodes (9): aplicar_hallazgos_adversariales(), Aplica la revisión adversarial de forma determinista. El revisor adversarial es…, Resuelve `nombre` contra el índice normalizado del catálogo. Devuelve (entrada,…, resolver_nombre_sd(), HallazgoAdversarial, _cat(), Regla de dominio: resolución, tope por rol contractual y reparto en 3 grupos…, TestAplicarAdversarial (+1 more)

### Community 28 - "mapear_historias_service_domain.py"
Cohesion: 0.14
Nodes (20): AnalistaMapeoBianPort, ABC, Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`. Un solo…, Nodo 2: propone nombres de Service Domain del catálogo. Es una PISTA, no…, Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes…, Nodo 7 (1 sola vez): ve todas las historias y propone el rol de cada SD a nivel…, Estado del subgrafo que procesa UNA Historia de Usuario. El outer graph hace…, _es_transitorio() (+12 more)

### Community 29 - "modelos.py"
Cohesion: 0.22
Nodes (13): AdjudicadorLangChain, _formatear_candidatos(), Adaptador: adjudica con un chat model de LangChain + salida estructurada., AdjudicadorLLMPort, ABC, Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)., Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`., Estado del grafo de LangGraph. (+5 more)

### Community 30 - "ResultadoMapeoHistorias"
Cohesion: 0.17
Nodes (12): PublicadorMapeoJson, Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como…, MapearHistoriasUseCase, ABC, Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains., Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea…, PublicadorMapeoPort, ABC (+4 more)

### Community 31 - "ValidarServiceDomainService"
Cohesion: 0.26
Nodes (3): EstadoGrafo, TypedDict, ValidarServiceDomainService

### Community 32 - "test_prompts_mapeo.py"
Cohesion: 0.17
Nodes (5): Prompt del adjudicador. Técnicas: rol explícito, descomposición de la tarea,…, Proyecta la evaluación aislada de un candidato al registro de entrada del…, Regresión de prompts: agnosticismo (sin hardcode de funcionalidad) + huella…, TestAgnosticismoPrompts, TestProyeccionEvaluacion

### Community 33 - "EmbeddingsResiliente"
Cohesion: 0.29
Nodes (6): _delay_sugerido(), EmbeddingsResiliente, _es_transitorio(), Embeddings, Exception, Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el…

### Community 34 - "._anclar_bq_personalizados"
Cohesion: 0.20
Nodes (8): _pascal(), Determinista: un BQ personalizado SOLO se ancla si (a) el campo no está ya…, BqPersonalizadoAplicado, OperacionBianAplicada, Un BQ personalizado anclado a evidencia BOM real. NUNCA es una operación…, Una operación oficial asignada a la historia, anclada al catálogo local., Un Service Domain ya clasificado y enriquecido con evidencia de docs/ (SD.json…, ServiceDomainAsignado

### Community 35 - "OperacionBian"
Cohesion: 0.07
Nodes (23): Protocol, CatalogoOperacionesBianJson, Path, Adaptador: catálogo local de operaciones oficiales por Service Domain. Fuente:…, Lo mínimo que los adaptadores necesitan de un chat: `with_structured_output`.…, SoportaStructured, _formatear(), MapeadorOperacionesLangChain (+15 more)

### Community 36 - "cli_mapeo.py"
Cohesion: 0.19
Nodes (12): datetime, _directorio_run(), _forzar_utf8(), main(), _parse(), Namespace, Path, CLI: mapear-historias --directorio-hu <dir> --funcionalidad <f.json>… (+4 more)

### Community 38 - "IntencionHistoriaLLM"
Cohesion: 0.19
Nodes (9): Nodo 1: interpreta la historia. Sin nombres de Service Domain, sin decisiones…, Nodo 4: evalúa UN candidato contra SU paquete de evidencia oficial cerrado.…, detectar_omitidos(), `ya_propuestos` = nombres de SD (normalizados) que el LLM ya evaluo (en…, IntencionHistoriaLLM, Interpretación funcional de la historia. Sin nombres de Service Domain., _cat(), 2º pase determinista: detección léxica de Service Domains que el LLM no propuso. (+1 more)

### Community 39 - "support.py"
Cohesion: 0.22
Nodes (12): cargar_config(), LLMConfig, MapearHistoriasConfig, ObservabilidadConfig, _proveedor(), ProveedorConfig, Carga y valida `config.yaml` — toda la configuración movible del proyecto. El…, Lee `config.yaml` (o `ruta`). Falla si no existe o es inválido. (+4 more)

### Community 40 - "analista_mapeo_langchain.py"
Cohesion: 0.17
Nodes (12): NamedTuple, Adaptador: el analista BIAN LLM del mapeo Historias -> Service Domains. Un…, formatear_bom_puml(), formatear_schemas_bom(), Formateo compartido del BOM (schemas de la Semantic API + modelo de clases…, _formatear_bom(), PromptSpec, Prompts del mapeo Historia de Usuario -> BIAN Service Domains. Un prompt por… (+4 more)

### Community 41 - "contenedor.py"
Cohesion: 0.25
Nodes (10): ConfiguracionProveedor, crear_estrategia(), EntradaModelo, _candidatos_embedding(), _cfg_proveedor(), crear_chat_failover(), _embeddings(), _entradas_llm() (+2 more)

### Community 42 - "UmbralesMapeo"
Cohesion: 0.23
Nodes (5): UmbralesMapeo, TestUmbralesMapeo, _prop(), Regresión SMART_TOKEN: contra el catálogo real (341 SD) + la caché BIAN real…, TestSmartTokenRegresion

### Community 43 - "ServiceDomainPropuestoLLM"
Cohesion: 0.22
Nodes (10): Segundo pase determinista: detecta Service Domains que el LLM NO propuso. No…, Registro de entrada del scoring determinista para UN Service Domain. Se…, ServiceDomainPropuestoLLM, Scoring y revision adversarial deterministas para decisiones BIAN. El score NO…, `IssuedDeviceAdministration` / `partyAuth3` -> tokens separables., _sim(), _split_camel(), _tokens() (+2 more)

### Community 44 - "EvidenciaBian"
Cohesion: 0.38
Nodes (5): clasificar_service_domains(), Convierte la lista cruda del LLM en los 3 grupos, anclando cada SD a la…, EvidenciaBian, _p(), TestClasificar

### Community 45 - "CatalogoBomPuml"
Cohesion: 0.23
Nodes (5): CatalogoBomPuml, Path, Camino directo real (SELECTED + operaciones) usando la caché BIAN sembrada de…, TestGrafoMapeoSeleccionReal, TestCatalogoBomPuml

### Community 46 - "crear_caso_uso_mapeo"
Cohesion: 0.38
Nodes (6): crear_caso_uso_mapeo(), _sha256_archivo(), config_test(), Config determinista para tests: único proveedor `fake`, rutas reales de docs/., _entrada(), TestGrafoMapeo

### Community 48 - "calcular_score"
Cohesion: 0.44
Nodes (3): calcular_score(), _p(), TestCalcularScore

### Community 49 - "_FakeChat"
Cohesion: 0.29
Nodes (4): ChatResult, _FakeChat, BaseChatModel, Runnable

### Community 50 - "crear_caso_uso"
Cohesion: 0.39
Nodes (3): crear_caso_uso(), Grafo completo sin API (proveedor 'fake'): camino exacto y camino RAG (léxico)…, TestGrafo

### Community 51 - "_FakeEmbeddings"
Cohesion: 0.43
Nodes (3): _FakeEmbeddings, Embeddings, Vector determinista por bolsa de trigramas hasheados. No es semántico, pero es…

### Community 53 - "ServiceDomainsDeHistoria"
Cohesion: 0.50
Nodes (3): Nodo 5: prompt DISTINTO que revisa la hipótesis ya clasificada (acción directa…, Los Service Domains de una historia repartidos en 3 grupos por confianza (post-…, ServiceDomainsDeHistoria

### Community 54 - "MetadatosPrompt"
Cohesion: 0.50
Nodes (3): Estado del grafo (outer) de mapeo Historias de Usuario -> Service Domains., MetadatosPrompt, Huella reproducible de una llamada LLM; nunca participa en la decisión.

### Community 55 - "clasificacion_historias.py"
Cohesion: 0.50
Nodes (3): _decidir(), Regla de dominio: ancla los Service Domains propuestos por el LLM a la…, (decision_contractual, motivo_decision) a partir de los dos ejes. Determinista.

## Knowledge Gaps
- **2 isolated node(s):** `generacion-contrato-ia-v2`, `setup.sh script`
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MapearHistoriasServiceDomainsService` connect `MapearHistoriasServiceDomainsService` to `PaqueteEvidenciaCandidato`, `OperacionBian`, `._anclar_bq_personalizados`, `EntradaCatalogo`, `FuncionalidadMacro`, `CatalogoServiceDomainsPort`, `contenedor.py`, `UmbralesMapeo`, `ServiceDomainPropuestoLLM`, `EvidenciaBian`, `CatalogoBomPuml`, `crear_caso_uso_mapeo`, `MetadatosPrompt`, `HistoriaUsuario`, `historias.py`, `mapear_historias_service_domain.py`, `ResultadoMapeoHistorias`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `CatalogoBianCache` connect `CatalogoBianCache` to `OperacionBian`, `analista_mapeo_langchain.py`, `contenedor.py`, `UmbralesMapeo`, `EvidenciaBian`, `CatalogoBomPuml`, `crear_caso_uso_mapeo`, `historias.py`, `mapear_historias_service_domain.py`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `EmbeddingsConFailover` connect `EmbeddingsConFailover` to `contenedor.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `MapearHistoriasServiceDomainsService` (e.g. with `AnalistaMapeoBianPort` and `CatalogoBomPort`) actually correct?**
  _`MapearHistoriasServiceDomainsService` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `EntradaCatalogo` (e.g. with `AnalistaMapeoBianLangChain` and `formatear_catalogo()`) actually correct?**
  _`EntradaCatalogo` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `HistoriaUsuario` (e.g. with `AnalistaMapeoBianLangChain` and `LectorHistoriasFilesystem`) actually correct?**
  _`HistoriaUsuario` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `FuncionalidadMacro` (e.g. with `AnalistaMapeoBianLangChain` and `LectorHistoriasFilesystem`) actually correct?**
  _`FuncionalidadMacro` has 10 INFERRED edges - model-reasoned connections that need verification._