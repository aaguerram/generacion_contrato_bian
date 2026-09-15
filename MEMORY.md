# Memory — generacion-contrato-ia-v2

> Generated: 2026-09-14 20:34:09  
> Total memories: **39**  
> Breakdown: instruction: 1, fact: 11, decision: 9, goal: 2, context: 2, learning: 14

---

## Instructions

*Standing rules, constraints, and guidelines to always follow.*

### Un corpus de evaluacion de recuperacion debe tener...

> Un corpus de evaluacion de recuperacion debe tener CAPAS declaradas y sus metricas NO se promedian entre si. Medido en generacion_contrato_bian el 2026-09-14: el canal lexico por nombre daba Recall@10 0.95 GLOBAL y 0.17 en la capa de negocio, porque 91 de los 97 casos eran consultas-nombre generadas; promediar convertia al peor canal para mapear-historias en el mejor del informe. Capas: hu_real (Historia real -> su Service Domain propietario; mide mapear-historias; SOLO se amplia con etiquetado humano, hoy 6 y no se fabrican), nombre_canonico (la consulta ES el nombre exacto, positivo por definicion) y nombre_deformado (nombre con deformacion sintetica declarada); las dos ultimas las genera scripts/evaluate_retrieval/generar_casos_nombre.py de forma determinista e idempotente y son regresion objetiva de validar-sd, NO poder estadistico sobre el negocio. Tres antipatrones que invalidan el corpus: (1) inventar consultas de negocio -mide lo bien que escribe consultas quien ya sabe la respuesta-; (2) usar como consulta el texto que el sistema indexa (role_definition/examples_of_use/features): es circular y sale inflado; (3) presentar el conteo total como si fuera cobertura del problema de negocio. El protocolo completo vive en la skill de proyecto .claude/skills/corpus-dorado-bian/SKILL.md.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T01:00:02 | Tags: `benchmark`, `corpus-dorado`, `metodologia`, `evaluacion`, `bian`*

---

## Facts

*Verified information, project status, and established truths.*

### Conectividad validada el 2026-09-12: MEMANTO agent...

> Conectividad validada el 2026-09-12: MEMANTO agente generacion-contrato-ia-v2 activado y recall remoto exitoso; Graphify respondió consultas sobre graphify-out/graph.json con 3416 nodos.

*Confidence: 1.0 | Status: active | Created: 2026-09-13T04:05:05 | Tags: `memanto`, `graphify`, `connectivity`*

### 7 Service Domains (ACH Operations, Correspondent B...

> 7 Service Domains (ACH Operations, Correspondent Bank Operations, Direct Debit Collection, Direct Debits Service, Payment Execution, Payment Instruction, Payment Order) tienen diagramas .puml/.svg extraidos localmente en docs/bian-diagrams/ y pagina propia en bian.org, pero estan marcados 'Registration Status: Obsolete' en su ficha de objeto (retirados desde BIAN release 13.0.0 -sus links de API portal apuntan a BIAN-13.0.0-*, no 14.0.0-). Por eso faltan (correctamente) en docs/BIANv14.xlsm hoja 'Service Domains', docs/SD.json (341, no 348) y en el diagrama oficial 'Matrix View' (view_54081.html, 0 coincidencias de sus object_id en el HTML). generacion_contrato_ia_v2/scripts/generate_matrix_view/ los excluye deliberadamente del arbol por esta razon -no es un bug ni un hueco de mapeo, es el comportamiento correcto.

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:40*

### Configuracion del proyecto: .env = SOLO API keys (...

> Configuracion del proyecto: .env = SOLO API keys (GROQ_API_KEY, GOOGLE_API_KEY, HF_TOKEN, OPENROUTER_API_KEY, COHERE_API_KEY solo para embeddings); config.yaml (versionado, sin secretos) define proveedores/modelos/orden de failover/umbrales/rutas/observabilidad. Estado real verificado en config.yaml al 2026-09-12: routing.llm_priority = [groq, gemini, huggingface, openrouter, ollama] (ollama self-hosted queda de ultimo fallback para LLM); routing.embedding_priority = [ollama, cohere, gemini, openrouter] (ollama primero para embeddings). ChatConFailover recorre proveedores y, dentro de cada uno, sus modelos en orden; 429/402/cuota/salida no parseable -> siguiente modelo, 503/timeout -> reintenta y avanza.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:26*

### docs/SD.json y docs/BIAN_Service_Landscape_V14.0_M...

> docs/SD.json y docs/BIAN_Service_Landscape_V14.0_Matrix_View.json son la MISMA fuente de Service Domains: mismos 341 nombres exactos, cobertura y longitud mediana identicas campo a campo (rol 99%/310 chars, ejemplos de uso 100%/130, executive summary 77%/137, features 76%/178, documentation 100%/875) y Documentation identica en 335/341 -en los 6 que difieren SD.json trae MAS texto-. SD.json aporta ademas Functional Pattern, Asset Type, Generic Artifact Type, Control Record y Registration Status, que el landscape no tiene; el landscape solo aporta object_url/sd_overview_url y la jerarquia Business Area/Domain embebida (ya disponible en docs/bian-business-areas.json). Cambiar de fuente no aporta informacion nueva: lo que falta es indexar lo que SD.json ya trae, porque texto_para_indexar en src/dominio/modelos.py solo usa nombre + clasificacion + service_role recortado a 320 chars.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T19:24:39 | Tags: `bian`, `sd-json`, `service-landscape`, `retrieval`, `indexacion`*

### Proyecto generacion_contrato_ia_v2 (hexagonal + La...

> Proyecto generacion_contrato_ia_v2 (hexagonal + LangGraph) tiene 2 casos de uso CLI: validar-sd y mapear-historias (python -m src mapear-historias --directorio-hu <dir> --funcionalidad <json> --directorio <out>). Evidencia BIAN offline en docs/: SD.json (341 SD), bian-business-areas.json, bian-operation-catalogs.json, bian-cache/ (cache_version 2 con schemas_detalle+parent_control_record), bian-puml/ (272 .puml BOM). Sin acceso a Internet en runtime normal.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:15*

### Fixes de robustez sobre el pipeline de operaciones...

> Fixes de robustez sobre el pipeline de operaciones (src/dominio/cobertura_operaciones.py y clasificacion_historias.py): (1) finalizar_por_operacion_solida — si el SD ya es OWNED_CONTRACT con evidencia BIAN verificada y al menos una operacion anclada sin reservas, se finaliza a directo/SELECTED aunque el score lexico sea bajo (antes quedaba varado en tentativo con el mismo LLM que ya acerto el rol). (2) resolver_operation_id — reconstruye el operationId real desde path+method de una operacion YA existente en el catalogo de ESE SD cuando el LLM devuelve algo no literal (p.ej. 'POST /Correspondence/{id}/Outbound/Initiate' en vez de 'InitiateOutbound'); nunca inventa ni cruza SD, y si no resuelve genera incidencia OPERATION_ID_UNRESOLVED en vez de perderse en un log. (3) fusionar_propuestas_de_operacion agrupa por (SD, operationId real) ANTES de anclar para evitar entradas duplicadas de la misma operacion citada por varios escenarios de una HU.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:23*

### docs/BIAN_Service_Landscape_V14.0_Matrix_View.json...

> docs/BIAN_Service_Landscape_V14.0_Matrix_View.json es la fuente UNICA de Service Domains del runtime de generacion_contrato_bian (commits 9cb7284 + c2b3f28, en origin/main): 341 SD con textos, clasificacion funcional, jerarquia Business Area/Domain y rutas a los diagramas BOM/Control Record, todo en un archivo y un parser (CatalogoJson, que aplana el arbol); SD.json y bian-business-areas.json siguen en docs/ pero ya NO se leen en ejecucion. REGLA DE FUSION en scripts/enrich_service_landscape/ (in-place, idempotente, sin red): el emparejamiento de campos se hace por VALOR y no por nombre -si el dato ya existe en el landscape con otro nombre prevalece el NOMBRE del landscape, cero campos agregados-, pero el VALOR lo manda SD.json siempre que aporte algo (es la fuente del BIANv14.xlsm con la documentacion estructurada '** 1. Role ** ...'); el landscape conserva su valor solo donde SD.json no dice nada. Se aplicaron 29 valores: 12 huecos/truncados y 17 sobrescrituras. Ademas se valida que ningun texto descriptivo (role_definition/example_of_use/executive_summary/key_features/documentation) se repita en dos atributos del mismo SD; los campos de clasificacion quedan fuera porque BIAN los hace coincidir legitimamente (Control Record = <AssetType><ArtifactType>, asi que en Legal Advisory el CR se llama igual que su asset_type, identico en ambas fuentes: tocarlo seria inventar dato).

*Confidence: 1.0 | Status: active | Created: 2026-09-14T20:51:07 | Tags: `bian`, `service-landscape`, `fuente-unica`, `catalogo`, `leccion`*

### Los trabajos LLM largos en este host se ejecutan c...

> Los trabajos LLM largos en este host se ejecutan contra el Ollama local (http://localhost:11434, modelo qwen3.8:27b-q8_0) en lugar de free tiers con cuota diaria; para que sobrevivan al cierre de la sesion SSH se lanzan con 'setsid nohup ... > log 2>&1 < /dev/null &' y sus logs viven en /home/super/graphify-runs/ (symlink latest.log + latest.pid).

*Confidence: 0.9 | Status: active | Created: 2026-09-14T01:53:44 | Tags: `ollama`, `background-jobs`, `ssh`, `graphify`, `infraestructura`*

### En el BIAN Service Landscape v14 dos invariantes e...

> En el BIAN Service Landscape v14 dos invariantes estructurales sustituyen a juicios manuales, ambos verificados el 2026-09-14 y fijados por tests deterministas: (1) el campo documentation de un Service Domain es su ficha estructurada (** 1. Role ** / ** 2. Examples of use ** / ** 3. Executive Summary ** / ...) y su seccion 1 debe decir EXACTAMENTE lo mismo que role_definition de ese mismo SD -coinciden 338/338 de los que traen ambos campos; una definicion de capability, que es otro artefacto BIAN, no lo cumple, y asi se detectaron Partner Management y Brand Management-; los 3 no comparables son Card Transaction Tracking (sin documentation), Operational Risk Models y Sales Planning (sin role_definition). (2) bom_diagram.puml_path que declaran 265 de los 341 SD coincide al 100% con el slug kebab-case del nombre, las 265 rutas existen, ninguno de los 76 SD sin bom_diagram tiene PUML alcanzable por convencion, y bian_source_url del landscape es identico al comentario ' BIAN source: del propio .puml (de donde ya salia ModeloBomPuml.source_url); quedan 7 .puml huerfanos (ach-operations, correspondent-bank-operations, direct-debit-collection, direct-debits-service, payment-execution, payment-instruction, payment-order) que ningun SD de v14 referencia. Consecuencia de diseno: preferir la ruta declarada sobre la convencion NO mueve ningun resultado hoy; su unico valor es que una regeneracion del landscape o de los diagramas que cambie el criterio de nombres falle en tests/unit_test/test_catalogo_bom_puml.py en vez de dejar el paquete de evidencia sin BOM en silencio (objeto_bom 0.0, sin error ni log).

*Confidence: 1.0 | Status: active | Created: 2026-09-15T00:27:47 | Tags: `bian`, `landscape`, `bom-puml`, `invariantes`, `tests`*

### El host de desarrollo (Ubuntu 24.04 aarch64, acces...

> El host de desarrollo (Ubuntu 24.04 aarch64, acceso por SSH, sudo con password) no permite instalar paquetes del sistema: todo el toolchain de usuario se instala sin root bajo ~/.local (binarios en ~/.local/bin, tarballs desplegados en ~/.local/opt, ya en PATH via .bashrc y .profile). Asi estan Neovim 0.12.5 + LazyVim (config en ~/.config/nvim, extras python/json/yaml/toml/markdown, LSP y formatters via Mason en ~/.local/share/nvim/mason), ripgrep, fd, fzf, lazygit y Node 24 LTS.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T16:58:48 | Tags: `entorno`, `neovim`, `lazyvim`, `toolchain`, `sin-root`, `aarch64`*

### En los servidores de plataforma_trader el desplieg...

> En los servidores de plataforma_trader el despliegue vive en /opt/plataforma-trader/ con 'current' como symlink al release activo (releases/vX.Y.Z) y un shared/.env aparte; las credenciales CAPITAL_* (CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_DEMO, a veces CAPITAL_EPIC) estan duplicadas en cuatro .env por servicio: capital-publisher, history-service, trade-executor y risk-monitor (market-metadata-poller reusa capital-publisher/.env). Cambiar credenciales de Capital.com exige editar los cuatro archivos, no uno. Acceso a prueba_v2_app: ssh -i ~/.ssh/id_ed25519_aaguerram ubuntu@52.49.23.177.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T02:12:40 | Tags: `plataforma-trader`, `capital-com`, `despliegue`, `prueba-v2`, `credenciales`*

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

### Creados en generacion_contrato_ia_v2/scripts/ (sep...

> Creados en generacion_contrato_ia_v2/scripts/ (sept-2026): generate_entities (arma docs/entity.json: por cada clase BIAN BOM, en que Service Domains/diagramas BOM+Control Record aparece, con descripcion+propiedades de docs/BIANBOM4XMI.xlsx), bian_object_catalog (arma docs/bian-object-catalog.json: resuelve nombre->object_id/url/documentacion en bian.org para Service Domains+clases+Business Areas+Business Domains, cache de shards ~142MB en generacion_contrato_ia_v2/descarga/bian-object-catalog-shards/, gitignored), generate_matrix_view (arma docs/BIAN_Service_Landscape_V14.0_Matrix_View.json: arbol Business Area->Business Domain->Service Domain desde BIANv14.xlsm+SD.json+entity.json+bian-object-catalog.json). generate_matrix_view y bian_object_catalog tienen dependencia circular: correr generate_matrix_view -> bian_object_catalog -> generate_matrix_view de nuevo para que Business Areas/Domains queden con object_url+documentacion (Service Domains no la tienen, se resuelven aparte contra bian-view-catalog.json).

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:41*

### Regla de negocio de BQ personalizado: un Control R...

> Regla de negocio de BQ personalizado: un Control Record oficial NO se edita nunca. Si una HU necesita un campo que ningun CR/BQ oficial expone, seleccionar_operaciones puede proponer bq_personalizados citando clase/atributo BOM real, verificado contra schemas_detalle/bom_modelo ANTES de anclar (se descarta con warning si la cita es falsa o el campo ya esta cubierto). Vive SIEMPRE separado de las operaciones oficiales (bq_personalizados_propuestos / custom_bq_candidates, estado CUSTOM_BQ_CANDIDATE), nunca en operaciones_bian/selected_operations. Convencion de nombres verificada contra BIAN real: operationId=Verbo+NombreBQ (PascalCase), path=/{SD}/{id}/{NombreBQ}/{Verbo}.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:19*

### Decisiones de diseño del retrieval avanzado en gen...

> Decisiones de diseño del retrieval avanzado en generacion_contrato_bian (commits ff87107 y e32df4c, 2026-09-14): (1) TODAS las piezas nuevas quedan OFF por defecto y con flags INDEPENDIENTES en config.yaml -retrieval_hibrido_habilitado, graph_rag_habilitado, reranker_habilitado, vector_store: memoria|qdrant- para poder medir que aporta cada una por separado en vez de encender todo junto; (2) vector_store=memoria es el default y pgvector NO se implementa (ADR docs/adr/0001-vector-store.md): Qdrant esta implementado y probado pero no compra calidad a esta escala; (3) el respaldo del cross-encoder es NO reordenar (RerankerNulo), nunca el lexico, porque un reranker que empeora es peor que ninguno; (4) la expansion por grafo filtra nodos puente compartidos por mas de 8 SD y puntua por rareza (1/frecuencia), y cada candidato expuesto lleva sus puentes para ser auditable -una arista sin origen no se ingesta-; (5) el grafo canonico (19 MB, 26.044 nodos) es artefacto DERIVADO y no se versiona: esta en .gitignore y se regenera con scripts/ingest_bian/; (6) el reranker se aplica ANTES del recorte por max_candidatos_hu, que es donde ahorra llamadas; (7) las tres etapas opcionales de retrieval comparten un presupuesto de tiempo por HU que comprueba ANTES de cada etapa y la salta con aviso, en vez de cortar a media ejecucion; (8) sentence-transformers y qdrant-client son dependencias OPCIONALES con import perezoso.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T23:10:11 | Tags: `retrieval`, `arquitectura`, `flags`, `adr`, `graph-rag`, `reranker`*

### BOM extendido: CatalogoBianCache._normalizar usa c...

> BOM extendido: CatalogoBianCache._normalizar usa cache_version:2 (request_schema/response_schema resueltos via $ref + parent_control_record en los BQ + schemas_detalle con el cuerpo real de cada schema). PUML BOM en docs/bian-puml/ (272 archivos, copia de architecture/BIAN_PUML/) parseado por src/dominio/puml_bom.py::parsear_puml_bom (puro) -> ModeloBomPuml; puerto CatalogoBomPort / adaptador CatalogoBomPuml. Regla de prompt fija: functional_object sale SIEMPRE del objeto de negocio real, nunca del wrapper Control Record.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:18*

### A escala de 341 Service Domains el recall de recup...

> A escala de 341 Service Domains el recall de recuperacion es un problema OPCIONAL, no una restriccion: medido el 2026-09-14, el indice global compacto que ya recibe revisar_completitud (nombre + rol recortado a 90 chars) pesa 39.979 chars = ~10k tokens, el catalogo entero con texto_para_indexar y el tope actual de 1.195 chars pesa ~93k tokens, y sin tope ~154k tokens. Es decir: el catalogo COMPLETO cabe en el contexto de los modelos de contexto largo, asi que generar candidatos con todo el catalogo en prompt (CAG) hace Recall@K estructuralmente 1.0 y elimina la clase entera de fallo que el benchmark mide. Regla de decision: CAG gana cuando el corpus es pequeno, estatico (release BIAN fijo), compartido entre todas las consultas y auditable -las cuatro se cumplen aqui-; RAG se reserva para lo grande, fresco o por tenant. Antes de invertir mas en ponderar la fusion RRF hay que medir CAG contra retrieval en el mismo corpus dorado. Salvedad de costo: el ahorro por prompt caching depende del proveedor (Gemini y Anthropic cachean prefijos; Groq no), y en Ollama local sobre el GB10 el contexto largo es gratis en dinero pero no en latencia ni memoria.

*Confidence: 0.9 | Status: active | Created: 2026-09-15T00:28:00 | Tags: `cag`, `retrieval`, `bian`, `contexto-largo`, `benchmark`*

### El estilo Python de generacion_contrato_bian lo fi...

> El estilo Python de generacion_contrato_bian lo fija ruff desde [tool.ruff] del pyproject.toml: line-length 100, target-version py311, select E4/E7/E9/F/I/UP/B (E501 deliberadamente fuera porque el formatter ya corta lo que puede y los strings de prompt largos no deben ensuciar el diagnostico), isort con known-first-party src/tests/unit_test/e2e (unit_test y e2e son los nombres con que los tests se importan entre si porque discover -s tests inserta tests/ como top_level_dir), extend-exclude .venv/docs/salida/graphify-out. El alcance formateado es src/ + tests/ + scripts/ (87 archivos), normalizado de una vez en main y verificado con 'ruff check' y 'ruff format --check'. El editor formatea al guardar con el MISMO ruff del .venv, nunca con reglas propias del editor.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T17:16:42 | Tags: `ruff`, `estilo`, `formateo`, `pyproject`, `python`*

---

## Goals

*Objectives, targets, and milestones to track progress.*

### Retrieval hibrido RRF (src/dominio/fusion_rrf.py, ...

> Retrieval hibrido RRF (src/dominio/fusion_rrf.py, sobre RecuperadorLexico+RecuperadorVectorial ya existentes de validar-sd) esta implementado EN MEMORIA pero mapear_historias.retrieval_hibrido_habilitado = false por DEFAULT: no hay benchmark de recall que justifique encenderlo todavia. Qdrant/pgvector (infra/retrieval/docker-compose.yml, perfiles qdrant/pgvector) estan preparados pero NINGUNO arranca por defecto -- decision explicita de no anadir un servicio externo sin medir primero (341 Service Domains es poco volumen para justificarlo). Fases 3-5 quedan pendientes y documentadas en implementacion_pendiente.md: benchmark de recall, modelo canonico BIAN + scripts de ingestion, ADR de vector store externo, reranker, Graph RAG, endurecimiento operativo.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:24*

### Pendiente en generacion_contrato_bian para retomar...

> Pendiente en generacion_contrato_bian para retomar despues del 2026-09-14 (todo lo implementado esta en main local, commits ff87107 y e32df4c SIN PUSHEAR). Por orden: (1) ARREGLAR LA PONDERACION DE LA FUSION RRF antes que nada: hoy trata igual al lexico y al vectorial y por eso baja el recall de 0.86 a 0.71 en mapear-historias; medir con pesos o elegir canales por caso de uso -el lexico se queda en validar-sd-; (2) ampliar el corpus dorado de 7 a ~100 consultas etiquetadas: con 7 solo se detectan regresiones, no se puede comparar modelos de embeddings ni justificar un default, y es tambien el prerrequisito de cualquier entrenamiento propio (hoy solo hay 6 HU etiquetadas); (3) correr scripts/evaluate_retrieval/canary.py con LLM real (--proveedor ollama, sin cuota) flag por flag antes de cambiar ningun default, comparando ownership_conflict_rate y operation_grounding_rate y no solo recall; (4) encadenar scripts/enrich_service_landscape/ al final de scripts/generate_matrix_view/, que hoy pisaria los 29 valores completados al regenerar el landscape; (5) ownership_conflict_rate mete en el denominador hallazgos sobre SD ya descartados y con uno solo salta a 1.0: excluirlos; (6) aprovechar bom_diagram/control_record_diagram del landscape en CatalogoBomPuml en vez de deducir rutas por convencion de nombre; (7) revisar las 2 discrepancias de documentation (Partner Management y Brand Management) con criterio BIAN. Entorno: ~/.cache/huggingface pertenece a root, hay que exportar HF_HOME=~/.cache/hf-local para que el cross-encoder descargue; Qdrant quedo levantado con su volumen poblado (cd infra/retrieval && docker compose --profile qdrant down para pararlo conservando datos).

*Confidence: 1.0 | Status: active | Created: 2026-09-14T23:10:27 | Tags: `pendientes`, `roadmap`, `retrieval`, `continuar`*

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

### Benchmark de recuperacion BIAN medido el 2026-09-1...

> Benchmark de recuperacion BIAN (scripts/evaluate_retrieval/, corpus dorado de 7 consultas, 341 SD, embeddings qwen3-embedding:8b en Ollama local, cross-encoder bge-reranker-v2-m3 en GPU). Resultados finales 2026-09-14: lexico R@10=0.29 MRR 0.214 | vectorial en memoria 0.86 / 0.436 / 2 negativos delante | Qdrant 0.86 / 0.434 | RRF(lexico+vectorial) 0.71 / 0.370 / 2 | RRF+graph 0.71 / 0.370 | RRF+graph+rerank 0.86 / 0.410 / 4. Cinco conclusiones: (1) la fusion RRF EMPEORA frente al vectorial solo porque mete el lexico -que en lenguaje natural acierta 0.29- con el mismo peso; el lexico sirve para validar-sd donde la consulta ES un nombre, no para mapear-historias; (2) Qdrant empata exactamente con el InMemoryVectorStore a esta escala; (3) la expansion por grafo ingenua alcanzaba 157 de 341 SD en dos saltos porque Party la modelan 125 SD y Arrangement 88: hay que filtrar por especificidad del nodo puente; (4) un reranker lexico como respaldo hundia R@10 de 0.71 a 0.14 comparando español contra ingles; (5) el cross-encoder REAL rescata lo que la fusion rompe (0.71->0.86) pero NO supera al vectorial solo: peor MRR (0.410 vs 0.436) y el doble de hard_negatives colados (4 vs 2), y cada negativo cuesta una llamada LLM de ~16k tokens. La mejor configuracion medida sigue siendo vectorial a secas, sin fusion y sin reranker. El gate 'Recall@10 >= 0.95' del plan se aprueba solo: mide recuperacion, no decision.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T22:46:11 | Tags: `retrieval`, `benchmark`, `rrf`, `qdrant`, `graph-rag`, `reranker`, `bian`*

### El reranker cross-encoder BAAI/bge-reranker-v2-m3 ...

> El reranker cross-encoder BAAI/bge-reranker-v2-m3 NO se justifica en generacion_contrato_bian, medido el 2026-09-14 sobre la capa hu_real con el canal disperso ya arreglado: baja R@1 de 0.50 a 0.17, MRR de 0.573 a 0.300 y sube los hard_negatives por delante del positivo de 1 a 4, a cambio de subir R@10 de 0.67 a 0.83. Su numero bueno anterior (R@10 0.71->0.86) era RESCATE de la fusion rota, no merito propio: cuando la fusion mejoro, el reranker paso de rescate a lastre. Regla de decision que generaliza: en este pipeline cada candidato por delante del correcto cuesta una llamada LLM con ~16k tokens de evidencia, asi que la CABEZA del ranking (R@1/MRR/negativos delante) vale mas que la COLA (R@10) -y cualquier componente que intercambie cabeza por cola es una perdida neta-. Causa probable del mal rendimiento: los documentos que se le pasan son texto_para_indexar(), un volcado de metadatos del catalogo, no prosa; los scores salen todos en ~0.003 (el modelo no ve ningun emparejamiento bueno). Reabrirlo exige antes darle a cada SD un texto escrito para leerse. Detalles operativos verificados: el modelo pesa 2,2 GB en disco (568M parametros fp32, NO los 560 MB que decia el comentario del codigo), ya esta descargado en ~/.cache/hf-local, carga en ~18 s por proceso y reordena 10 candidatos en ~430 ms en la GPU (NVIDIA GB10, cuda:0); requiere export HF_HOME=~/.cache/hf-local porque ~/.cache/huggingface es de root. Ademas, con max_candidatos_hu=14 y ~11 candidatos por HU no se trunca nada, asi que hoy el reranker no cambiaria ni una evaluacion aunque se encendiera.

*Confidence: 0.95 | Status: active | Created: 2026-09-15T01:13:57 | Tags: `reranker`, `cross-encoder`, `retrieval`, `benchmark`, `bian`*

### Causa raiz de un falso negativo real encontrado en...

> Causa raiz de un falso negativo real encontrado en produccion (HU 'Notificar actualizacion de datos' -> Service Domain Correspondence quedaba REJECTED sin operaciones pese a tener evidencia BIAN valida): eran las reglas de ownership/scoring/elegibilidad de operacion, NO un problema de retrieval. Fix: promocion determinista CONSUMED_DEPENDENCY->OWNED_CONTRACT solo si el hallazgo adversarial es ACCION_DIRECTA_COMO_DEPENDENCIA + dependency_kind=AUDIT_OR_NOTIFICATION (salida/resultado, no precondicion) + trazabilidad + evidence_refs, y ademas objeto_bom del score >= 0.15 (este ultimo umbral evito un falso positivo real: Party Authentication fue promovido citando su propio CR para un objeto de negocio ajeno, objeto_bom=0.0 exacto).

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:21*

### Causa raiz del canal lexico debil en generacion_co...

> Causa raiz del canal lexico debil en generacion_contrato_bian, medida el 2026-09-14: NO era falta de pesos en la fusion RRF sino un problema de IDIOMA. Las Historias de Usuario estan en espanol y el catalogo BIAN completo (nombre, role_definition, key_features, schemas, PUML) esta en ingles, asi que un canal disperso (BM25 o rapidfuzz) no comparte NI UN termino con el corpus y recupera literalmente cero; el canal denso no lo sufria porque los embeddings son multilingues. La solucion es un puente lexico ES->EN (src/dominio/vocabulario_bian.py, EQUIVALENCIAS_BASE que ya usaba scoring_bian + EQUIVALENCIAS_RETRIEVAL extendida). Regla al ampliar ese mapa: la traduccion es LINGUISTICA, no de respuesta -'correo'->'mail' es legitimo, 'correo'->'correspondence' seria colar la respuesta esperada en el traductor y convertiria el benchmark en profecia autocumplida-. Segunda conclusion medida: cada caso de uso quiere su propio canal disperso, y por eso NO debe haber un unico canal 'lexico': rapidfuzz compara NOMBRES y es intocable para validar-sd (MRR 1.000 en nombres exactos, 0.945 con erratas, donde BM25 se hunde a 0.636 porque una errata cambia letras, no terminos); BM25 compara TEXTO con IDF y es el de mapear-historias (MRR 0.281 vs 0.083 del lexico, y fusionado con el denso 0.573 vs 0.342 del denso solo). La fusion es un INTERCAMBIO, no una mejora libre: gana la cabeza del ranking (R@1 0.17->0.50) y pierde profundidad (R@10 0.83->0.67); aqui la cabeza vale mas porque cada candidato de mas cuesta una llamada LLM.

*Confidence: 0.95 | Status: active | Created: 2026-09-15T00:59:50 | Tags: `retrieval`, `bm25`, `idioma`, `bian`, `fusion-rrf`*

### Hipotesis probada y refutada en generacion_contrat...

> Hipotesis probada y refutada en generacion_contrato_bian el 2026-09-14: darle PROSA al cross-encoder BAAI/bge-reranker-v2-m3 en vez del volcado de metadatos de texto_para_indexar() mejora mucho pero NO alcanza. Barrido de 10 variantes de texto (EntradaCatalogo.texto_prosa, medido con evaluate.py --barrido-texto sobre la capa hu_real): la mejor es 'prosa' (nombre + service_role + examples_of_use + executive_summary, ~644 chars) con MRR 0.417 y 2 hard_negatives delante, frente a 0.300 y 4 del texto del indice -o sea el texto SI importaba, +39% de MRR y la mitad de negativos-; pero no reordenar sigue ganando (MRR 0.573, 1 negativo). Forma clara en los datos, util para cualquier futuro reranker: los textos cortos son los peores (executive_summary 129 chars -> MRR 0.108; examples_of_use 159 -> 0.238; features 158 -> 0.141, y ademas features es una lista de vinetas, no prosa) porque el modelo se queda sin contexto para juzgar, y pasar de ~650 chars tampoco ayuda (prosa_features 799 -> 0.297, documentation 891 -> 0.285): el optimo es prosa de longitud MEDIA. Decision: reranker_habilitado sigue en false, pero el pipeline ya pasa 'prosa' en _reordenar_candidatos para que encender el flag no reparta ademas el peor texto posible. Reabrirlo exige otra via (otro modelo, o texto escrito a mano por SD), no otra variante de lo que el landscape publica. Leccion metodologica del mismo barrido: la primera pasada dio 10 filas IDENTICAS porque el reranker no se construia si el canal solo venia en --barrido-texto (medi 'sin rerank' diez veces sin saberlo); un barrido cuyas filas salen todas iguales es sintoma de que el componente barrido no se esta ejecutando, no de un empate.

*Confidence: 0.95 | Status: active | Created: 2026-09-15T01:21:08 | Tags: `reranker`, `cross-encoder`, `texto-prosa`, `benchmark`, `bian`*

### En el pipeline mapear-historias el cuello de botel...

> En el pipeline mapear-historias el cuello de botella de precision NO es la recuperacion sino la decision: medido el 2026-09-14 sobre dos corridas E2E reales, ownership_conflict_rate=1.0 y operation_grounding_rate=0.0 en ambas, mientras el SD correcto se recuperaba siempre como top-1 con gran margen (score 1.0 y 0.6733 frente a <=0.36 del resto) y con rol OWNED_CONTRACT bien asignado; el revisor adversarial lo bloqueaba despues dejandolo UNRESOLVED. Coste por HU: 10-12 llamadas LLM (6 fijas + 1 por candidato) con ~16k tokens de mediana por paquete de evidencia, de ahi el 413 de Groq (peso del prompt, no numero de llamadas). Orden de trabajo acordado: (1) correr en Ollama local para eliminar cuota, (2) arreglar el bloqueo adversarial y el grounding de operaciones, (3) enriquecer texto_para_indexar que hoy descarta Documentation/Examples of Use/Executive Summary/Features, (4) corpus dorado que mida la decision final y no solo Recall@K, (5) reranker local solo al encender retrieval hibrido, (6) no entrenar modelo: solo hay 6 HU etiquetadas.

*Confidence: 0.9 | Status: active | Created: 2026-09-14T19:24:28 | Tags: `mapeo-historias`, `precision`, `adversarial`, `retrieval`, `coste-llm`, `diagnostico`*

### Mecanismo simetrico a la promocion: determinar_deg...

> Mecanismo simetrico a la promocion: determinar_degradaciones reclasifica OWNED_CONTRACT -> CONSUMED_DEPENDENCY (dependency_kind=SUPPORTING_LOOKUP) cuando el revisor adversarial marca DEPENDENCIA_PROMOVIDA_A_CONTRATO y la accion citada no comparte NINGUN token con business_actions (extraidos en extraer_intencion, antes de proponer el SD). Caso real: 'Party Reference Data Directory' evaluado OWNED_CONTRACT citando 'actualizar...' para una HU donde actualizar era precondicion, no accion propia.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:22*

### docs/BIANv14.xlsm hoja 'Service Domains' tiene 2 t...

> docs/BIANv14.xlsm hoja 'Service Domains' tiene 2 taxonomias de Business Area/Domain INCOMPATIBLES para el mismo Service Domain: columnas 'm...' (modelo, 5 Business Areas oficiales: Business Support, Operations and Execution, Reference Data, Risk and Compliance, Sales and Service; soporta Business Domain anidado via mBusiness Domain parent) vs columnas 'v...' (vista, usada para navegacion del sitio bian.org, SIEMPRE plana). Verificado: un mismo mBusiness Area se reparte hasta en 6 vBusiness Area distintos segun el Service Domain -no son la misma jerarquia simplificada, son ejes cruzados independientes-. NUNCA usar vista como fallback de modelo fila por fila: mezclaria 2 ejes y produce un arbol incorrecto (bug real cometido y corregido en generacion_contrato_ia_v2/scripts/generate_matrix_view/, ver su README seccion 'De donde sale esto').

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:39*

### Al fijar el interprete de un venv para pyright en ...

> Al fijar el interprete de un venv para pyright en Neovim, la configuracion debe entregarse en on_init (mutando client.settings antes de que el servidor pida su configuracion), no en on_attach seguido de un notify workspace/didChangeConfiguration: reconfigurar despues hace que pyright descarte los diagnosticos del buffer ya abierto y no vuelva a publicarlos hasta la siguiente edicion.

*Confidence: 0.9 | Status: active | Created: 2026-09-14T17:16:44 | Tags: `neovim`, `lsp`, `pyright`, `venv`, `diagnosticos`*

### El link de bian.org a la pagina de un objeto tiene...

> El link de bian.org a la pagina de un objeto tiene la forma object_<N>.html?object=<id>. <N> NO es un tipo semantico (Service Domain, Class, etc) sino el numero de shard de almacenamiento interno del sitio (data/all_objects_data_<N>.js, 47 shards, ~127.000 objetos totales, mapeo en data/all_objects_data_mapping.js). Un mismo object_id aparece fisicamente duplicado (identico) en varios shards a la vez -no son objetos distintos-, asi que hay que dedupear por object_id (no por (object_id, shard)) y usar siempre el shard CANONICO del mapping.js. Ademas, cada vez que una clase se dibuja en un diagrama, bian.org le crea un objeto tipo 'Class' extra que es un duplicado posicional (coincide con el alias N<numero> que usan los .puml locales) -hay que preferir tipos mas especificos (Business object, Capability, Grouping segun la categoria) para desambiguar el objeto canonico real. Implementado en generacion_contrato_ia_v2/scripts/bian_object_catalog/.

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:37*

### El usuario de este proyecto verifica activamente l...

> El usuario de este proyecto verifica activamente los JSON generados (entity.json, bian-object-catalog.json, BIAN_Service_Landscape_V14.0_Matrix_View.json) contra las paginas REALES de bian.org (capturas de pantalla, URLs abiertas en el navegador) en vez de confiar ciegamente en la extraccion local. Esa verificacion encontro y corrigio varios bugs reales en la misma sesion: (1) documentation tomaba la seccion equivocada (Role Definition en vez de la seccion homonima, casi siempre vacia), (2) 2 Service Domains quedaban mal clasificados por confundir eje modelo/vista, (3) sd_overview_url duplicado en 2 sub-objetos en vez de vivir 1 sola vez en la raiz. Leccion: antes de dar por buena una extraccion de datos BIAN, cruzar al menos 1-2 casos contra la pagina real de bian.org, no asumir que el pipeline de extraccion es correcto solo porque corre sin errores.

*Confidence: 0.95 | Status: active | Created: 2026-09-13T22:14:43*

### En la shell que expone Claude Code en este host, '...

> En la shell que expone Claude Code en este host, 'rg' es una FUNCION de shell que redirige a el binario de claude, no ripgrep real; 'command -v rg' devuelve 'rg' y enmascara que ripgrep no esta instalado en el sistema. Al verificar dependencias para otras herramientas (Neovim/snacks, telescope, etc.) hay que comprobar con 'type rg' o buscar el binario real, no confiar en command -v.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T16:58:52 | Tags: `shell`, `claude-code`, `ripgrep`, `verificacion-dependencias`*

### Patron de fallo confirmado en mapear-historias: cu...

> Patron de fallo confirmado en mapear-historias: cuando una metrica de calidad del LLM esta clavada en 0.0 o 1.0, la causa suele ser una desalineacion determinista entre lo que el codigo MUESTRA al modelo y lo que luego VERIFICA, no un fallo del modelo. Dos casos reales corregidos el 2026-09-14: (1) revisar_adversarial recibia el Service Role recortado a 120 chars mientras evaluar_candidato lo recibia a 900, y el revisor emite DIRECTO_SIN_SERVICE_ROLE contra la decision del evaluador -el corte alcanzaba al 90% de los 341 SD, mediana 309 chars-; (2) operacion_evidencia_verificable normalizaba la evidence_ref entera mientras el prompt renderiza los campos como campos_respuesta={Campo:Tipo} y pide citar el nombre exacto, asi que 'CorrespondenceAddressee:Address' nunca empataba con el campo real. Ambas degradaban EN SILENCIO (UNRESOLVED, OPERATION_EVIDENCE_UNVERIFIED) pareciendo comportamiento correcto. Metodo: reproducir con un test que capture el prompt renderizado y comprobar que ese test FALLA con el codigo viejo antes de dar el fix por bueno.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T19:31:28 | Tags: `mapeo-historias`, `prompts`, `verificacion`, `debugging`, `metricas`*

### Leccion metodologica confirmada dos veces en gener...

> Leccion metodologica confirmada dos veces en generacion_contrato_bian el 2026-09-14: al comparar dos fuentes JSON nunca inferir el esquema del PRIMER registro -asi se concluyo erroneamente que al BIAN Service Landscape le faltaban cinco campos de clasificacion que en realidad ya tenia-, sino usar la union de claves de todos los registros y emparejar los campos por VALOR (porcentaje de coincidencia registro a registro), no por parecido de nombre. Ese emparejamiento por valor es lo que despues permitio consolidar dos fuentes sin duplicar un solo atributo y detectar que los 11 campos de SD.json ya existian en el landscape con coincidencia del 94-100%.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T21:53:11 | Tags: `metodologia`, `comparacion-fuentes`, `json`, `bian`*

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
