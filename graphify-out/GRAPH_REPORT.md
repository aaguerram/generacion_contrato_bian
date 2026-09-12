# Graph Report - generacion_contrato_ia_v2  (2026-09-11)

## Corpus Check
- 173 files · ~593,298 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1134 nodes · 2827 edges · 74 communities (60 shown, 14 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 297 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bec1164b`
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
- modelos.py
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
- EntradaCatalogo
- historias.py
- validar_service_domain.py
- Plan de implementación: recuperación y decisión BIAN híbrida
- EstadoMapeo
- AnalistaMapeoBianPort
- CandidatoSD
- Config
- ValidarServiceDomainService
- generacion_contrato_ia_v2
- EmbeddingsResiliente
- mapear_historias_service_domain.py
- CatalogoOperacionesBianPort
- detectar_omitidos
- salida/__init__.py
- ResultadoMapeoHistorias
- normalizar
- CatalogoBianCache
- contenedor.py
- IntencionHistoriaLLM
- OperacionBian
- RecuperadorVectorial
- SoportaStructured
- support.py
- EvaluacionCandidatoLLM
- BIAN UML / PlantUML extraction
- cargar_settings
- crear_caso_uso
- HistoriaUsuario
- CatalogoOperacionesBianJson
- fusion_rrf
- bian-cache/README.md
- CLAUDE.md — generacion_contrato_ia_v2
- ._anclar_bq_personalizados
- crear_caso_uso_mapeo
- derivar_path_grupo
- PaqueteEvidenciaCandidato
- Grafos LangGraph del proyecto
- TestAgnosticismoPrompts
- Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)
- Arquitectura hexagonal — reglas
- `mapear-historias` — Historias de Usuario → Service Domains
- campos_alcanzables
- Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1
- 1. Fase 3 — Hybrid RAG "de verdad" (validar y, si corresponde, encender por defecto)
- 2. Fase 3 (continuación) — Modelo canónico BIAN + ingestión
- 3. Fase 3 (continuación) — Vector store externo: Qdrant o pgvector, SOLO si el benchmark lo pide
- 4. Fase 4 — Reranker + Graph RAG
- Infra de retrieval (OPCIONAL, diferida a Fase 3)

## God Nodes (most connected - your core abstractions)
1. `MapearHistoriasServiceDomainsService` - 68 edges
2. `CatalogoBianCache` - 49 edges
3. `normalizar()` - 48 edges
4. `EntradaCatalogo` - 42 edges
5. `HistoriaUsuario` - 40 edges
6. `FuncionalidadMacro` - 39 edges
7. `OperacionBian` - 36 edges
8. `IntencionHistoriaLLM` - 36 edges
9. `RevisionAdversarialLLM` - 33 edges
10. `EvidenciaBian` - 32 edges

## Surprising Connections (you probably didn't know these)
- `TestGrafoMapeoPromocionOwnership` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoRetrievalHibrido` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestGrafoMapeoSeleccionReal` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_grafo_mapeo.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestFormatearOperacionesConCamposDeRespuesta` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_mapeador_operaciones_langchain.py → src/adaptadores/salida/catalogo_bian_cache.py
- `TestSmartTokenRegresion` --uses--> `CatalogoBianCache`  [INFERRED]
  tests/test_smart_token_regresion.py → src/adaptadores/salida/catalogo_bian_cache.py

## Import Cycles
- None detected.

## Communities (74 total, 14 thin omitted)

### Community 0 - "clasificar"
Cohesion: 0.20
Nodes (10): Banda, clasificar(), mejor_candidato(), Regla de dominio: clasifica el resultado del RAG en bandas por similitud…, El candidato con mayor similitud léxica estricta (no el mejor de recuperación)., Umbrales, _cand(), Regla de dominio: bandas por similitud (sin API, sin frameworks). (+2 more)

### Community 1 - "factory.py"
Cohesion: 0.05
Nodes (38): AnthropicStrategy, BaseChatModel, Embeddings, Estrategia Anthropic (opcional). `pip install langchain-anthropic`. Nota: usa…, _api_key(), CohereStrategy, BaseChatModel, Embeddings (+30 more)

### Community 2 - "test_cobertura_operaciones.py"
Cohesion: 0.24
Nodes (6): operacion_evidencia_verificable(), ¿Alguna `evidence_ref` citada por el LLM coincide con un campo real alcanzable…, _cache(), _operacion(), Regresión directa del caso real: `RetrieveDemographics` fue elegido para…, TestOperacionEvidenciaVerificable

### Community 3 - "test_arquitectura_hexagonal.py"
Cohesion: 0.23
Nodes (11): AST, ImportFrom, _capa(), _modulo(), _objetivos(), _paquete(), _permitido(), Path (+3 more)

### Community 4 - "CatalogoJson"
Cohesion: 0.12
Nodes (9): CatalogoJson, Path, RecuperadorLexico, Fase 3 (en memoria): si el LLM no propone ningún candidato, el retrieval…, TestGrafoMapeoRetrievalHibrido, Normalización + carga real de SD.json (sin API)., TestCatalogoJson, TestNormalizacion (+1 more)

### Community 5 - "EmbeddingsConFailover"
Cohesion: 0.06
Nodes (30): _corto(), EmbeddingsConFailover, BaseException, Embeddings, RuntimeError, Embeddings con failover multi-proveedor / multi-modelo, en orden de PRECISIÓN.…, Fija el candidato activo probándolos en orden. Idempotente., TodosLosEmbeddingsAgotados (+22 more)

### Community 6 - "LectorHistoriasFilesystem"
Cohesion: 0.14
Nodes (11): LectorHistoriasFilesystem, Adaptador: lee las Historias de Usuario de un directorio y la funcionalidad…, _titulo_desde_nombre(), LectorHistoriasPort, ABC, Puerto driven: lee las Historias de Usuario y la funcionalidad macro de la…, Todas las Historias de Usuario del `directorio`, ordenadas por nombre de…, La funcionalidad macro + detalle desde un archivo JSON. (+3 more)

### Community 7 - "modelos.py"
Cohesion: 0.18
Nodes (11): Adaptador: carga el catálogo desde SD.json (columnas L..V) y lo enriquece con…, Adaptador RAG **léxico** (rapidfuzz) — sin API de embeddings. Dos scores por…, Adaptador RAG: índice vectorial en memoria sobre el catálogo (langchain-core…, CatalogoServiceDomainsPort, ABC, Puerto driven: acceso al catálogo de Service Domains (SD.json)., Todas las entradas del catálogo., Coincidencia exacta tras normalizar (case/espacios/PascalCase). None si no… (+3 more)

### Community 20 - "cli_mapeo.py"
Cohesion: 0.12
Nodes (21): datetime, _forzar_utf8(), main(), _directorio_run(), _forzar_utf8(), main(), _parse(), Namespace (+13 more)

### Community 21 - "fake.py"
Cohesion: 0.12
Nodes (21): Any, ChatResult, _archivo_hu(), _bloque(), _FakeChat, _FakeEmbeddings, BaseChatModel, Embeddings (+13 more)

### Community 22 - "MapearHistoriasServiceDomainsService"
Cohesion: 0.16
Nodes (7): EstadoHistoria, TypedDict, _huellas(), MapearHistoriasServiceDomainsService, _paquete_de(), RRF sobre los recuperadores configurados (léxico + vectorial, en memoria — ver…, `elegibles` = `candidatos_operacion_elegibles(grupos)`: OWNED_CONTRACT, directo…

### Community 23 - "EntradaCatalogo"
Cohesion: 0.14
Nodes (17): NamedTuple, formatear_catalogo(), _formatear_indice_global(), _formatear_operaciones(), Adaptador: el analista BIAN LLM del mapeo Historias -> Service Domains. Un…, Una línea por SD: - "Nombre" · Area > Domain · [Patrón/AssetType] :: rol…, Índice global compacto (solo nombre + rol muy recortado) para el hint de…, Nombres normalizados de request/response schema de `operaciones` — para que… (+9 more)

### Community 24 - "historias.py"
Cohesion: 0.07
Nodes (44): CatalogoBomPuml, Path, Adaptador: lee los PUML BOM de `docs/bian-puml/` y los parsea a…, slug_service_domain(), CatalogoBomPort, ABC, Puerto driven: modelo estructural BOM (clases/enums/asociaciones) por Service…, Modelo de clases del PUML BOM del Service Domain, o None si no hay `.puml`… (+36 more)

### Community 25 - "validar_service_domain.py"
Cohesion: 0.16
Nodes (15): PublicadorJson, Adaptador de persistencia: escribe el resultado como JSON en el directorio del…, ABC, Puerto driving: la API que ofrece la aplicación., Valida si `service_domain` existe en el catálogo BIAN y publica el resultado en…, ValidarServiceDomainUseCase, PublicadorResultadoPort, ABC (+7 more)

### Community 26 - "Plan de implementación: recuperación y decisión BIAN híbrida"
Cohesion: 0.06
Nodes (34): 10. Estrategia de pruebas, 11. Gates de aceptación, 12. Riesgos y mitigaciones, 13. Orden recomendado de implementación, 1. Resultado esperado, 2. Diagnóstico confirmado, 3. Principios de la solución, 4. Arquitectura objetivo consolidada (+26 more)

### Community 27 - "EstadoMapeo"
Cohesion: 0.13
Nodes (9): EstadoMapeo, TypedDict, Fase 0: nada debe perderse sin poder explicar en qué etapa se perdió. Tasas…, Reconcilia el mismo SD entre HU (determinista). Si alguna HU lo posee y quedó…, DecisionServiceDomainConsolidada, HistoriaConServiceDomains, Un Service Domain del catálogo que la evaluación LLM NO propuso pero cuyas…, Resultado del mapeo para una historia. (+1 more)

### Community 28 - "AnalistaMapeoBianPort"
Cohesion: 0.10
Nodes (16): AnalistaMapeoBianPort, ABC, Puerto driven: el analista BIAN LLM del caso de uso `mapear-historias`. Un solo…, Nodo 3: usa el índice global BIAN como hint para detectar candidatos faltantes…, Nodo 5: prompt DISTINTO que revisa la hipótesis ya clasificada (acción directa…, Nodo 7 (1 sola vez): ve todas las historias y propone el rol de cada SD a nivel…, Estado del subgrafo que procesa UNA Historia de Usuario. El outer graph hace…, CandidatosHistoriaLLM (+8 more)

### Community 29 - "CandidatoSD"
Cohesion: 0.18
Nodes (14): AdjudicadorLangChain, _formatear_candidatos(), Adaptador: adjudica con un chat model de LangChain + salida estructurada., Prompt del adjudicador. Técnicas: rol explícito, descomposición de la tarea,…, AdjudicadorLLMPort, ABC, Puerto driven: adjudicación por LLM (¿la consulta es uno de los candidatos?)., Decide si `consulta` designa el mismo Service Domain que alguno de `candidatos`. (+6 more)

### Community 31 - "ValidarServiceDomainService"
Cohesion: 0.22
Nodes (4): EstadoGrafo, TypedDict, Estado del grafo de LangGraph., ValidarServiceDomainService

### Community 32 - "generacion_contrato_ia_v2"
Cohesion: 0.17
Nodes (12): Configuración: `config.yaml` + `.env`, Cómo decide  —  y cómo se garantiza la reproducibilidad, El grafo, Estructura, generacion_contrato_ia_v2, Instalación, LangSmith (observabilidad), Modelos y reproducibilidad (verificado sept-2026) (+4 more)

### Community 33 - "EmbeddingsResiliente"
Cohesion: 0.29
Nodes (6): _delay_sugerido(), EmbeddingsResiliente, _es_transitorio(), Embeddings, Exception, Decorador de `Embeddings`: reintenta 429 / 5xx con backoff (respeta el…

### Community 34 - "mapear_historias_service_domain.py"
Cohesion: 0.24
Nodes (7): MapearHistoriasUseCase, ABC, Puerto driving: mapear un lote de Historias de Usuario a BIAN Service Domains., Lee las HU de `directorio_hu` + la funcionalidad de `ruta_funcionalidad`, mapea…, _es_transitorio(), Exception, Caso de uso `MapearHistoriasUseCase` orquestado con LangGraph. Outer graph…

### Community 35 - "CatalogoOperacionesBianPort"
Cohesion: 0.14
Nodes (10): CatalogoOperacionesBianPort, ABC, Puerto driven: catálogo local de operaciones oficiales por Service Domain…, Nombres de schema / objetos BOM del Service Domain, o lista vacía si no hay…, Schemas de la Semantic API con cuerpo (properties / enum values), o lista vacía., Vista `control_records` / `behavior_qualifiers` (con parent_control_record), o…, Operaciones oficiales (CR + BQ) del Service Domain, o None si no hay catálogo…, Nombres canónicos de los Service Domains que tienen catálogo de operaciones… (+2 more)

### Community 36 - "detectar_omitidos"
Cohesion: 0.16
Nodes (11): detectar_omitidos(), Segundo pase determinista: detecta Service Domains que el LLM NO propuso. No…, `ya_propuestos` = nombres de SD (normalizados) que el LLM ya evaluo (en…, `IssuedDeviceAdministration` / `partyAuth3` -> tokens separables., _sim(), _split_camel(), _tokens(), _cat() (+3 more)

### Community 38 - "ResultadoMapeoHistorias"
Cohesion: 0.19
Nodes (10): PublicadorMapeoJson, Adaptador de persistencia: escribe el mapeo Historias -> Service Domains como…, PublicadorMapeoPort, ABC, Puerto driven: persiste el resultado del mapeo Historias -> Service Domains., Escribe el resultado en `directorio` y devuelve la ruta del archivo., Documento final: la funcionalidad macro y la lista de historias con sus Service…, ResultadoMapeoHistorias (+2 more)

### Community 39 - "normalizar"
Cohesion: 0.21
Nodes (8): { nombre_normalizado -> (business_area, business_domain) }., Adaptador: catálogo local de operaciones oficiales por Service Domain. Fuente:…, Reglas de dominio deterministas para verificar cobertura de campos por…, construir_indice_exacto(), normalizar(), Normalización de nombres de Service Domain para la coincidencia exacta., Issued Device Administration', 'IssuedDeviceAdministration',…, { nombre_normalizado -> nombre_canónico }.

### Community 40 - "CatalogoBianCache"
Cohesion: 0.07
Nodes (20): CatalogoBianCache, _descargar(), Path, Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh…, GET con reintentos + backoff sobre 429/5xx y errores de red transitorios., `#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el…, _ref_name(), _resolver_wrapper() (+12 more)

### Community 41 - "contenedor.py"
Cohesion: 0.21
Nodes (13): ConfiguracionProveedor, crear_estrategia(), EntradaModelo, _candidatos_embedding(), _cfg_proveedor(), crear_chat_failover(), _embeddings(), _entradas_llm() (+5 more)

### Community 42 - "IntencionHistoriaLLM"
Cohesion: 0.48
Nodes (4): AnalistaMapeoBianLangChain, _lista(), IntencionHistoriaLLM, Interpretación funcional de la historia. Sin nombres de Service Domain.

### Community 43 - "OperacionBian"
Cohesion: 0.06
Nodes (42): aplicar_hallazgos_adversariales(), candidatos_operacion_elegibles(), clasificar_service_domains(), _decidir(), determinar_promociones(), propuestos_promovidos(), Regla de dominio: ancla los Service Domains propuestos por el LLM a la…, (decision_contractual, motivo_decision) a partir de los dos ejes. Determinista. (+34 more)

### Community 44 - "RecuperadorVectorial"
Cohesion: 0.24
Nodes (6): InMemoryVectorStore, Similitud léxica estricta 0..1 (orden de palabras tolerante, palabras que…, similitud_nombre(), Embeddings, Path, RecuperadorVectorial

### Community 45 - "SoportaStructured"
Cohesion: 0.33
Nodes (3): Protocol, Lo mínimo que los adaptadores necesitan de un chat: `with_structured_output`.…, SoportaStructured

### Community 46 - "support.py"
Cohesion: 0.22
Nodes (12): cargar_config(), LLMConfig, MapearHistoriasConfig, ObservabilidadConfig, _proveedor(), ProveedorConfig, Carga y valida `config.yaml` — toda la configuración movible del proyecto. El…, Lee `config.yaml` (o `ruta`). Falla si no existe o es inválido. (+4 more)

### Community 47 - "EvaluacionCandidatoLLM"
Cohesion: 0.20
Nodes (7): EvaluacionCandidatoLLM, Evaluación de UN candidato contra su paquete de evidencia. Señales ordinales,…, Proyecta la evaluación aislada de un candidato al registro de entrada del…, _AnalistaGuion, Analista scriptado: TA propietario directo, Fraud Evaluation dependencia de…, Regresión de prompts: agnosticismo (sin hardcode de funcionalidad) + huella…, TestProyeccionEvaluacion

### Community 48 - "BIAN UML / PlantUML extraction"
Cohesion: 0.40
Nodes (4): AI-oriented conventions, BIAN UML / PlantUML extraction, Counts, Extraction modes

### Community 49 - "cargar_settings"
Cohesion: 0.11
Nodes (16): _asegurar_env(), cargar_settings(), Path, Punto de entrada de configuración: carga el `.env` (solo API keys) y…, Carga la configuración efectiva. `esfuerzo` (opcional) pisa `llm.esfuerzo` del…, ejecutar_caso(), Helper compartido por las pruebas E2E (integración real, LLM real, bajo…, Ejecuta `mapear-historias` (LLM real, failover de `config.yaml`) sobre… (+8 more)

### Community 50 - "crear_caso_uso"
Cohesion: 0.39
Nodes (3): crear_caso_uso(), Grafo completo sin API (proveedor 'fake'): camino exacto y camino RAG (léxico)…, TestGrafo

### Community 51 - "HistoriaUsuario"
Cohesion: 0.13
Nodes (16): MapeadorOperacionesLangChain, Nodo 1: interpreta la historia. Sin nombres de Service Domain, sin decisiones…, Nodo 2: propone nombres de Service Domain del catálogo. Es una PISTA, no…, Nodo 4: evalúa UN candidato contra SU paquete de evidencia oficial cerrado.…, Devuelve, por Service Domain, las operaciones oficiales que implementan la…, Estado del grafo (outer) de mapeo Historias de Usuario -> Service Domains., FuncionalidadMacro, HistoriaUsuario (+8 more)

### Community 52 - "CatalogoOperacionesBianJson"
Cohesion: 0.23
Nodes (3): CatalogoOperacionesBianJson, Path, TestCatalogoOperaciones

### Community 53 - "fusion_rrf"
Cohesion: 0.26
Nodes (5): fusion_rrf(), Reciprocal Rank Fusion: combina varios rankings (léxico, vectorial, ...) en uno…, Cada ranking es una lista de nombres YA ordenada por relevancia desc (mejor…, Reciprocal Rank Fusion: puro, sin API., TestFusionRRF

### Community 56 - "CLAUDE.md — generacion_contrato_ia_v2"
Cohesion: 0.20
Nodes (8): Antes de terminar cualquier cambio, CLAUDE.md — generacion_contrato_ia_v2, Comandos, Configuración: `config.yaml` + `.env`, Datos verificados (sept-2026), `mapear-historias` (detalle), Pruebas de integración/E2E — solo bajo demanda, REGLA OBLIGATORIA para cualquier cambio en `src/`

### Community 57 - "._anclar_bq_personalizados"
Cohesion: 0.22
Nodes (7): _bom_respalda(), _pascal(), ¿`paquete` (schemas_detalle + bom_modelo) tiene de verdad esa clase/atributo?…, Determinista: una operación personalizada SOLO se ancla si (a)…, operation_id_en_uso(), ¿Ya existe ese operationId como operación OFICIAL real del Service Domain?…, TestOperationIdEnUso

### Community 58 - "crear_caso_uso_mapeo"
Cohesion: 0.42
Nodes (5): crear_caso_uso_mapeo(), config_test(), Config determinista para tests: único proveedor `fake`, rutas reales de docs/., _entrada(), TestGrafoMapeo

### Community 59 - "derivar_path_grupo"
Cohesion: 0.33
Nodes (3): derivar_path_grupo(), Path para una operación NUEVA dentro de un CR/BQ ya existente: toma el `path`…, TestDerivarPathGrupo

### Community 60 - "PaqueteEvidenciaCandidato"
Cohesion: 0.20
Nodes (10): formatear_bom_puml(), _campos_respuesta(), _formatear(), _formatear_bom(), Adaptador: paso 6 del mapeo — asigna operaciones oficiales BIAN a una historia…, `campos_respuesta={eMailAddress:ContactPoint, CellPhoneNumber:ContactPoint,…, PaqueteEvidenciaCandidato, Todo lo que el LLM ve para evaluar UN candidato. Se arma en código desde la… (+2 more)

### Community 61 - "Grafos LangGraph del proyecto"
Cohesion: 0.33
Nodes (5): 1. `validar-sd` — ¿existe este Service Domain?, 2. `mapear-historias` — grafo externo (map-reduce sobre las Historias de Usuario), 3. `mapear-historias` — subgrafo por Historia de Usuario (fan-out por candidato), Correspondencia nodo → código, Grafos LangGraph del proyecto

### Community 63 - "Implementación pendiente — recuperación híbrida BIAN (Fases 3-5)"
Cohesion: 0.22
Nodes (9): 0. Qué ya está resuelto (no reabrir sin motivo), 5. Fase 5 — Endurecimiento operativo, 6. Gates de aceptación (heredados del plan original, aplican a partir de aquí), 7. Dónde quedó cada pieza (referencia rápida), Implementación pendiente — recuperación híbrida BIAN (Fases 3-5), Justificación, Pasos, Problema (+1 more)

### Community 64 - "Arquitectura hexagonal — reglas"
Cohesion: 0.25
Nodes (6): Arquitectura hexagonal — reglas, Cómo cambiar cosas sin romper la regla, El grafo (`aplicacion/servicios/validar_service_domain.py`), Puertos y adaptadores, Regla (se verifica en CI), Umbrales (`RAG_UMBRAL_ALTO` / `RAG_UMBRAL_BAJO`)

### Community 65 - "`mapear-historias` — Historias de Usuario → Service Domains"
Cohesion: 0.29
Nodes (7): El grafo — outer map-reduce + subgrafo por HU con fan-out por candidato, Flujo temporal (secuencia), JSON de entrada (`--funcionalidad`), `mapear-historias` — Historias de Usuario → Service Domains, Modelo de nodos (LangGraph), Operaciones personalizadas (no oficiales) — cuando el BOM respalda un campo sin cubrir, Salida (`mapeo-historias-service-domains.json`)

### Community 66 - "campos_alcanzables"
Cohesion: 0.43
Nodes (3): campos_alcanzables(), Nombres de propiedad (normalizados) del schema raíz, 1 nivel — el mismo alcance…, TestCamposAlcanzables

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

### Community 72 - "Infra de retrieval (OPCIONAL, diferida a Fase 3)"
Cohesion: 0.40
Nodes (4): Cuándo usar esto, Infra de retrieval (OPCIONAL, diferida a Fase 3), Por qué no ambos, y por qué no ahora, Uso

## Knowledge Gaps
- **93 isolated node(s):** `generacion-contrato-ia-v2`, `setup.sh script`, `Regla (se verifica en CI)`, `Puertos y adaptadores`, `El grafo (`aplicacion/servicios/validar_service_domain.py`)` (+88 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MapearHistoriasServiceDomainsService` connect `MapearHistoriasServiceDomainsService` to `mapear_historias_service_domain.py`, `CatalogoOperacionesBianPort`, `CatalogoJson`, `LectorHistoriasFilesystem`, `modelos.py`, `ResultadoMapeoHistorias`, `contenedor.py`, `OperacionBian`, `PaqueteEvidenciaCandidato`, `HistoriaUsuario`, `EntradaCatalogo`, `historias.py`, `._anclar_bq_personalizados`, `crear_caso_uso_mapeo`, `EstadoMapeo`, `AnalistaMapeoBianPort`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `CatalogoBianCache` connect `CatalogoBianCache` to `test_cobertura_operaciones.py`, `CatalogoOperacionesBianPort`, `CatalogoJson`, `ResultadoMapeoHistorias`, `contenedor.py`, `OperacionBian`, `CatalogoOperacionesBianJson`, `historias.py`, `crear_caso_uso_mapeo`, `derivar_path_grupo`, `PaqueteEvidenciaCandidato`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `normalizar()` connect `normalizar` to `mapear_historias_service_domain.py`, `campos_alcanzables`, `test_cobertura_operaciones.py`, `detectar_omitidos`, `CatalogoJson`, `modelos.py`, `CatalogoBianCache`, `derivar_path_grupo`, `OperacionBian`, `CatalogoOperacionesBianJson`, `MapearHistoriasServiceDomainsService`, `EntradaCatalogo`, `._anclar_bq_personalizados`, `EstadoMapeo`, `PaqueteEvidenciaCandidato`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `MapearHistoriasServiceDomainsService` (e.g. with `AnalistaMapeoBianPort` and `CatalogoBomPort`) actually correct?**
  _`MapearHistoriasServiceDomainsService` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `CatalogoBianCache` (e.g. with `EvidenciaBian` and `OperacionBian`) actually correct?**
  _`CatalogoBianCache` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `EntradaCatalogo` (e.g. with `AnalistaMapeoBianLangChain` and `formatear_catalogo()`) actually correct?**
  _`EntradaCatalogo` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `HistoriaUsuario` (e.g. with `AnalistaMapeoBianLangChain` and `LectorHistoriasFilesystem`) actually correct?**
  _`HistoriaUsuario` has 10 INFERRED edges - model-reasoned connections that need verification._