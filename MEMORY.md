# Memory — generacion-contrato-ia-v2

> Generated: 2026-09-20 09:12:24  
> Total memories: **68**  
> Breakdown: instruction: 3, fact: 17, decision: 21, goal: 3, commitment: 1, context: 3, learning: 19, artifact: 1

---

## Instructions

*Standing rules, constraints, and guidelines to always follow.*

### Un corpus de evaluacion de recuperacion debe tener...

> Un corpus de evaluacion de recuperacion debe tener CAPAS declaradas y sus metricas NO se promedian entre si. Medido en generacion_contrato_bian el 2026-09-14: el canal lexico por nombre daba Recall@10 0.95 GLOBAL y 0.17 en la capa de negocio, porque 91 de los 97 casos eran consultas-nombre generadas; promediar convertia al peor canal para mapear-historias en el mejor del informe. Capas: hu_real (Historia real -> su Service Domain propietario; mide mapear-historias; SOLO se amplia con etiquetado humano, hoy 6 y no se fabrican), nombre_canonico (la consulta ES el nombre exacto, positivo por definicion) y nombre_deformado (nombre con deformacion sintetica declarada); las dos ultimas las genera scripts/evaluate_retrieval/generar_casos_nombre.py de forma determinista e idempotente y son regresion objetiva de validar-sd, NO poder estadistico sobre el negocio. Tres antipatrones que invalidan el corpus: (1) inventar consultas de negocio -mide lo bien que escribe consultas quien ya sabe la respuesta-; (2) usar como consulta el texto que el sistema indexa (role_definition/examples_of_use/features): es circular y sale inflado; (3) presentar el conteo total como si fuera cobertura del problema de negocio. El protocolo completo vive en la skill de proyecto .claude/skills/corpus-dorado-bian/SKILL.md.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T01:00:02 | Tags: `benchmark`, `corpus-dorado`, `metodologia`, `evaluacion`, `bian`*

### Doctrina de observabilidad de generacion_contrato_...

> Doctrina de observabilidad de generacion_contrato_bian, destilada de cinco agujeros reales encontrados el 2026-09-14/15 (commit d3375ba): UNA METRICA QUE DA VERDE PORQUE NO SE HIZO NADA ES PEOR QUE NO TENERLA, y una division vacia es el sitio donde se esconde. Los cinco eran el MISMO error de forma a distintos niveles: (1) operation_grounding_rate = verificadas/ancladas devolvia 1.0 cuando ancladas era 0 -medido: corrida real con operaciones_ancladas 0 y grounding 1.0-; ahora 0.0 si habia SD elegibles y null si no los habia. (2) La misma trampa un nivel arriba: una historia con CERO Service Domains SELECTED mostraba cobertura 1.0 y grounding 1.0 porque sin elegibles no habia nada que anclar; ahora deja incidencia HISTORIA_SIN_CONTRATO nombrando al mejor candidato con su rol, motivo y confianza. (3) Un bucle que no se ejecuta no reporta: _asignar_operaciones recorria mapeo.operaciones y si venia vacio devolvia sin incidencias, asi que un SD elegible sin operaciones era invisible -> OPERATION_MAPPING_EMPTY. (4) Un descarte que solo existe en un logger.warning es un descarte perdido: el blindaje anti-alucinacion tiraba citas con un log, y 'el modelo se invento TODAS las operaciones' quedaba indistinguible de 'no propuso ninguna' -> viajan en MapeoOperacionesLLM.citas_descartadas y se registran como OPERATION_ID_UNRESOLVED. (5) Una tasa de exito necesita su tasa de COBERTURA al lado: grounding dice 'de lo que ancle, cuanto esta fundamentado' y no puede distinguir 'ancle poco y bien' de 'no ancle nada' -> operation_coverage_rate = SD elegibles que anclaron alguna / SD elegibles. Regla practica al anadir cualquier metrica nueva: preguntar que valor toma cuando el denominador es cero, y si ese valor se lee como exito, es un bug. Ninguno de los cinco lo encontro una revision de codigo: los encontro medir corridas reales y mirar por que el JSON pintaba bien.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T04:56:11 | Tags: `observabilidad`, `metricas`, `incidencias`, `bian`, `calidad`*

### Regla estadistica para juzgar corridas E2E en gene...

> Regla estadistica para juzgar corridas E2E en generacion_contrato_bian, fijada el 2026-09-15: UNA TANDA EN VERDE NO ES UNA MEJORA. La varianza medida de la suite E2E con los flags encendidos es de 3 fallos en 11 corridas (27%) con el MISMO modelo respondiendo el nodo critico -varianza del modelo, no degradacion de proveedor, comprobado por provider_used/model_used de las huellas-. Bajo esa tasa, ver 6 corridas seguidas en verde tiene ~15% de probabilidad POR AZAR: es exactamente lo que ocurrio tras implementar los arreglos de ownership, y por eso NO se declaro ninguna mejora. Para distinguir una mejora real del ruido hacen falta del orden de 15-20 corridas por configuracion.
>
> Consecuencia practica implementada: `E2E_REPETICIONES=N` (1 por defecto) corre cada caso N veces y exige MAYORIA ESTRICTA, reportando el marcador ('2/3 corridas cumplieron') y los motivos de las que fallaron. Todas las corridas se ejecutan siempre -parar al alcanzar mayoria escondería cuantas fallaron, que es el dato que interesa-. Uso recomendado: 3 repeticiones como gate diario, 15+ para decidir si un flag se enciende por defecto.
>
> Corolario que aplica a cualquier medicion de este proyecto: antes de atribuir un cambio de resultado a un cambio de codigo, calcular que probabilidad tenia ese resultado bajo la varianza ya conocida. Si sale por encima de ~10%, la unica afirmacion honesta es 'compatible con una mejora', no 'mejoro'.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T13:04:13 | Tags: `e2e`, `varianza`, `estadistica`, `metodologia`, `bian`*

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

### BIAN landscape: documentation del SD es redundante, la de area/domain se descarta

> En el BIAN Service Landscape Matrix View (docs/BIAN_Service_Landscape_V14.0_Matrix_View.json) el campo 'documentation' de cada Service Domain NO aporta informacion nueva: es la concatenacion literal de los 4 campos que ya se parsean por separado (** 1. Role ** = service_role, ** 2. Examples of use ** = examples_of_use, ** 3. Executive Summary ** = executive_summary, ** 4. Key Features ** = features). Verificado 2026-09-16 sobre Party Reference Data Directory. Cuesta 305.706 chars (~76k tokens sobre 341 SD) por cero informacion nueva, asi que NUNCA debe meterse en un prompt; el unico uso legitimo es como relleno de ultimo recurso en texto_para_indexar(). En cambio SI existe informacion valiosa que el runtime descarta hoy: el landscape trae 'documentation' por Business Area (5) y por Business Domain (36) -11.690 chars ~2.9k tokens en total, enviables UNA vez como bloque de cabecera, no repetidos por SD- y CatalogoJson._aplanar solo toma el 'name' de esos nodos, asi que ni siquiera se cargan (EntradaCatalogo no tiene campo para ellos). Dato relacionado: rol_max_chars=240 recorta el service_role de 219 de los 341 SD (64%), descartando ~10.7k tokens de la fuente mas discriminante.

*Confidence: 1.0 | Status: active | Created: 2026-09-17T03:11:31 | Tags: `bian`, `landscape`, `prompts`, `catalogo`, `tokens`*

### Mapa de los 5 puntos donde el grafo LangGraph de m...

> Mapa de los 5 puntos donde el grafo LangGraph de mapear-historias consume los JSON de docs/bian-cache/release14.0.0/<SD>.json, con el campo exacto que lee cada uno (checklist para migrar la fuente de contratos BIAN): (1) nodo cargar, mapear_historias_service_domain.py:456, service_domains_con_catalogo() -> solo la clave service_domain de cada archivo, solo para el log. (2) nodo revisar_completitud, :526, evidencia_de(sd) -> solo el bloque evidence -> estado VERIFIED/CACHED_VERIFIED que entra al prompt como disponibilidad. (3) nodo preparar_candidatos, :725-745, el uso pesado: asegurar() + operaciones_de() -> operations[] completo + esquemas_de() -> schemas[] + schemas_detalle_de() -> schemas_detalle[]; todo se empaqueta en PaqueteEvidenciaCandidato via _paquete_de, que ademas DERIVA control_records/behavior_qualifiers del campo grupo de las operaciones. Mismo bloque duplicado en _vuelta_correctiva (CRAG) :828-842. (4) nodo clasificar via _reclasificar :886-893, pasa operations/schemas/evidencia a calcular_score: texto_ops (operation_id+summary+description+grupo) da el 30% de accion, grupos CR/BQ + nombres de schema dan el 25% de objeto, evidencia.estado da el +-0.05 y los topes. (5) nodo seleccionar_operaciones via _asignar_operaciones :1203, operaciones_de() otra vez solo para los elegibles -> lista numerada con campos_respuesta derivados de response_schema + schemas_detalle. HALLAZGO: el campo catalog del JSON (control_records/behavior_qualifiers estructurados) NO lo consume nadie en el flujo; catalogo_estructurado_de solo se llama desde su test. El grafo reconstruye esa vista desde operations[].grupo.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T20:43:47 | Tags: `bian`, `cache-json`, `puntos-consumo`, `langgraph`, `migracion`*

### Los trabajos LLM largos en este host se ejecutan c...

> Los trabajos LLM largos en este host se ejecutan contra el Ollama local (http://localhost:11434, modelo qwen3.8:27b-q8_0) en lugar de free tiers con cuota diaria; para que sobrevivan al cierre de la sesion SSH se lanzan con 'setsid nohup ... > log 2>&1 < /dev/null &' y sus logs viven en /home/super/graphify-runs/ (symlink latest.log + latest.pid).

*Confidence: 0.9 | Status: active | Created: 2026-09-14T01:53:44 | Tags: `ollama`, `background-jobs`, `ssh`, `graphify`, `infraestructura`*

### En el BIAN Service Landscape v14 dos invariantes e...

> En el BIAN Service Landscape v14 dos invariantes estructurales sustituyen a juicios manuales, ambos verificados el 2026-09-14 y fijados por tests deterministas: (1) el campo documentation de un Service Domain es su ficha estructurada (** 1. Role ** / ** 2. Examples of use ** / ** 3. Executive Summary ** / ...) y su seccion 1 debe decir EXACTAMENTE lo mismo que role_definition de ese mismo SD -coinciden 338/338 de los que traen ambos campos; una definicion de capability, que es otro artefacto BIAN, no lo cumple, y asi se detectaron Partner Management y Brand Management-; los 3 no comparables son Card Transaction Tracking (sin documentation), Operational Risk Models y Sales Planning (sin role_definition). (2) bom_diagram.puml_path que declaran 265 de los 341 SD coincide al 100% con el slug kebab-case del nombre, las 265 rutas existen, ninguno de los 76 SD sin bom_diagram tiene PUML alcanzable por convencion, y bian_source_url del landscape es identico al comentario ' BIAN source: del propio .puml (de donde ya salia ModeloBomPuml.source_url); quedan 7 .puml huerfanos (ach-operations, correspondent-bank-operations, direct-debit-collection, direct-debits-service, payment-execution, payment-instruction, payment-order) que ningun SD de v14 referencia. Consecuencia de diseno: preferir la ruta declarada sobre la convencion NO mueve ningun resultado hoy; su unico valor es que una regeneracion del landscape o de los diagramas que cambie el criterio de nombres falle en tests/unit_test/test_catalogo_bom_puml.py en vez de dejar el paquete de evidencia sin BOM en silencio (objeto_bom 0.0, sin error ni log).

*Confidence: 1.0 | Status: active | Created: 2026-09-15T00:27:47 | Tags: `bian`, `landscape`, `bom-puml`, `invariantes`, `tests`*

### El host de desarrollo (Ubuntu 24.04 aarch64, acces...

> El host de desarrollo (Ubuntu 24.04 aarch64, acceso por SSH, sudo con password) no permite instalar paquetes del sistema: todo el toolchain de usuario se instala sin root bajo ~/.local (binarios en ~/.local/bin, tarballs desplegados en ~/.local/opt, ya en PATH via .bashrc y .profile). Asi estan Neovim 0.12.5 + LazyVim (config en ~/.config/nvim, extras python/json/yaml/toml/markdown, LSP y formatters via Mason en ~/.local/share/nvim/mason), ripgrep, fd, fzf, lazygit y Node 24 LTS.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T16:58:48 | Tags: `entorno`, `neovim`, `lazyvim`, `toolchain`, `sin-root`, `aarch64`*

### BIAN R14 publica OpenAPI para solo 258 de los 341 ...

> BIAN R14 publica OpenAPI para solo 258 de los 341 Service Domains del Service Landscape (verificado 2026-09-16 contra el arbol de bian-official/public, commit b58bf4c2c3, ruta release14.0.0/semantic-apis/oas3 /yamls/). La brecha de 83 SD es ESTRUCTURAL, no un hueco de descarga: la cache local docs/bian-cache/release14.0.0 ya tiene los 258 publicados y cero pendientes, asi que --actualizar-cache-bian nunca llenara esos 83. Evidencia disponible para los 83 sin OpenAPI: los 341 SD traen control_record en el landscape (el NOMBRE del Control Record, p.ej. Building Maintenance -> Building Maintenance Arrangement) y textos (service_role/examples_of_use/key_features), pero solo 7 de los 83 tienen diagrama BOM PUML. No hay operaciones ni schemas para ellos. Consecuencia de diseno: para esos SD no se puede anclar una operacion oficial; el entregable tendria que ser un contrato PROPUESTO, analogo al precedente bq_personalizados_propuestos con estado CUSTOM_BQ_CANDIDATE.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T21:21:46 | Tags: `bian`, `openapi`, `brecha-83-sd`, `landscape`, `contratos-propuestos`*

### El test acotado del 2026-08-28 sobre los filtros d...

> El test acotado del 2026-08-28 sobre los filtros de riesgo de trade-executor quedo CERRADO el 2026-09-16 con el release pro-v0.1.149: MAX_SPREAD_TO_REWARD_RATIO volvio de 2.0 a 0.15 y MIN_RISK_REWARD_RATIO de 0.2 a 1.0. Los otros dos parametros del mismo test se MANTIENEN deliberadamente y no son un revert olvidado: RISK_PERCENT_PER_TRADE sigue en 0.1 (techo de riesgo bajo mientras el P&L acumulado sea negativo) y TARGET_HEIGHT_FRACTION en 0.34 (un objetivo mas lejano es lo que puede hacer que alguna ruptura cumpla el R:R minimo restaurado). DAILY_LOSS_LIMIT_ENFORCE sigue en false. Consecuencia esperada y aceptada: con R:R minimo 1.0 el executor rechaza la enorme mayoria de las rupturas, porque la geometria real de la familia da ~0.2.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T20:43:00 | Tags: `trade-executor`, `riesgo`, `revert`, `gates`, `pro-v2`*

### En los servidores de plataforma_trader el desplieg...

> En los servidores de plataforma_trader el despliegue vive en /opt/plataforma-trader/ con 'current' como symlink al release activo (releases/vX.Y.Z) y un shared/.env aparte; las credenciales CAPITAL_* (CAPITAL_API_KEY, CAPITAL_IDENTIFIER, CAPITAL_PASSWORD, CAPITAL_DEMO, a veces CAPITAL_EPIC) estan duplicadas en cuatro .env por servicio: capital-publisher, history-service, trade-executor y risk-monitor (market-metadata-poller reusa capital-publisher/.env). Cambiar credenciales de Capital.com exige editar los cuatro archivos, no uno. Acceso a prueba_v2_app: ssh -i ~/.ssh/id_ed25519_aaguerram ubuntu@52.49.23.177.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T02:12:40 | Tags: `plataforma-trader`, `capital-com`, `despliegue`, `prueba-v2`, `credenciales`*

### En BIAN R14, un dato de una HU puede necesitar var...

> En BIAN R14, un dato de una HU puede necesitar varios Behavior Qualifier del MISMO Service Domain: en Party Reference Data Directory, el BQ Reference expone los datos personales y de contacto (PartyNameSalutation, CellPhoneNumber, eMailAddress) y el BQ Associations expone la relacion entre dos Party (AssociateReference, AssociateType, ProxyRepresentativePowerofAttorneyReference), que es el que corresponde cuando la HU pide recuperar el tutor/representante de un menor. Elegir el Service Domain correcto no basta: hay que cubrir cada dato con SU BQ.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T21:17:15 | Tags: `bian`, `party-reference-data-directory`, `behavior-qualifier`, `associations`, `cuentas-menores`*

### En runtime, generacion_contrato_bian lee la eviden...

> En runtime, generacion_contrato_bian lee la evidencia de operaciones BIAN de archivos JSON de cache (docs/bian-cache/release14.0.0/<SD>.json, cache_version 2, 258 de 341 SD sembrados): operations CR+BQ, schemas, schemas_detalle con cuerpo, catalog estructurado y evidence (source_url + commit_sha + content_sha256). El OpenAPI YAML oficial de bian-official/public (release{R}/semantic-apis/oas3 /yamls/{SD}.yaml) es SOLO formato de transporte de la descarga: se parsea en memoria con yaml.safe_load en CatalogoBianCache._recuperar, _normalizar lo convierte a JSON y el YAML se descarta; docs/ no contiene ningun .yaml. yaml.safe_load sobre un contrato BIAN solo corre en dos casos frios: un Service Domain ausente de la cache con descargar_faltantes=true, o --actualizar-cache-bian. Los unicos YAML que el proyecto lee de disco son config.yaml (cada corrida), scripts/evaluate_retrieval/corpus_dorado.yaml (solo el benchmark) e infra/retrieval/docker-compose.yml (solo Docker). Consecuencia: cambiar la fuente de contratos BIAN toca _normalizar y el shape del JSON cacheado, no el grafo LangGraph.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T17:02:19 | Tags: `bian`, `cache-json`, `openapi-yaml`, `evidencia`, `catalogo-operaciones`*

---

## Decisions

*Architectural choices, approach selections, and their rationale.*

### Decisiones de diseño del retrieval avanzado en gen...

> Decisiones de diseño del retrieval avanzado en generacion_contrato_bian (commits ff87107, e32df4c, 175669c, 4112f93 y c4bbda8; ultima revision 2026-09-14, todo en origin/main). Las ocho primeras vienen de la primera iteracion y siguen vigentes; las siete siguientes son de la iteracion de los 6 puntos.
>
> (1) TODAS las piezas nuevas quedan OFF por defecto y con flags INDEPENDIENTES en config.yaml -retrieval_hibrido_habilitado, graph_rag_habilitado, reranker_habilitado, vector_store, y ahora tambien retrieval_canal_lexico, cag_habilitado, grafo_senales_adversarial, crag_reintento_habilitado, cache_nodos_habilitado, durabilidad- para poder medir que aporta cada una por separado en vez de encender todo junto; un default solo se mueve tras el canary con LLM real. (2) vector_store=memoria es el default y pgvector NO se implementa (ADR docs/adr/0001-vector-store.md): Qdrant esta implementado y probado pero no compra calidad a esta escala. (3) el respaldo del cross-encoder es NO reordenar (RerankerNulo), nunca el lexico, porque un reranker que empeora es peor que ninguno. (4) la expansion por grafo filtra nodos puente compartidos por mas de 8 SD y puntua por rareza (1/frecuencia), y cada candidato lleva sus puentes para ser auditable -una arista sin origen no se ingesta-. (5) el grafo canonico (19 MB, 26.044 nodos) es artefacto DERIVADO y no se versiona: .gitignore + scripts/ingest_bian/. (6) el reranker se aplica ANTES del recorte por max_candidatos_hu, que es donde ahorraria llamadas. (7) las tres etapas opcionales de retrieval comparten un presupuesto de tiempo por HU que se comprueba ANTES de cada etapa y la salta con aviso, en vez de cortar a media ejecucion. (8) sentence-transformers y qdrant-client son dependencias OPCIONALES con import perezoso.
>
> (9) UN CANAL DISPERSO POR CASO DE USO, no un unico canal "lexico": rapidfuzz compara NOMBRES y se queda en validar-sd; BM25 compara TEXTO con IDF y es el de mapear-historias. La eleccion esta medida por capas del corpus, no supuesta. (10) el puente ES->EN vive en UN solo sitio (src/dominio/vocabulario_bian.py): EQUIVALENCIAS_BASE es el mapa que scoring_bian ya usaba y EQUIVALENCIAS_RETRIEVAL lo extiende solo para recuperacion, para no mover el scoring, que tiene su propia regresion. (11) fusion_rrf acepta k y un peso por canal; peso 0 apaga un canal sin recablear nada. (12) UN INDICE Y UN RERANKER NO COMPARTEN TEXTO: el indice quiere cobertura de vocabulario (texto_para_indexar), el cross-encoder quiere prosa que se lea (EntradaCatalogo.texto_prosa). El pipeline pasa ya 'prosa' al reordenar aunque el flag siga en false, para que encenderlo no reparta ademas el peor texto posible. (13) EL GRAFO TIENE DOS USOS DISTINTOS Y DOS FLAGS DISTINTOS: expandir candidatos (graph_rag_habilitado) y CONFIRMAR un conflicto de ownership ya afirmado por el revisor (grafo_senales_adversarial). El segundo no reclasifica nada: cambia el motivo de la incidencia y alimenta una tasa paralela. (14) CRAG es UNA vuelta, no un lazo: se dispara solo si el lote de evidencia no sostiene nada, reescribe la consulta desde gaps/unresolved_questions y solo añade candidatos. Un ciclo agentico abierto romperia la reproducibilidad por huellas y el coste predecible por HU. (15) la CACHE DE NODOS solo cubre los 7 nodos LLM; los deterministas se recalculan siempre, porque cuestan milisegundos y una entrada vieja podria fijar una decision que el codigo ya cambio. La clave de cada nodo sale de SUS entradas semanticas mas la firma de la corrida (cadena de modelos + catalog_sha256): ni otro modelo ni otra evidencia reutilizan nada.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T23:10:11 | Tags: `retrieval`, `arquitectura`, `flags`, `adr`, `graph-rag`, `reranker`*

### Decision: para generacion_contrato_ia_v2 se usa el...

> Decision: para generacion_contrato_ia_v2 se usa el agente/namespace MEMANTO 'generacion-contrato-ia-v2' (namespace Moorcheh memanto_agent_generacion-contrato-ia-v2) sobre el servidor on-prem compartido de Produbanco (100.102.221.79:8080, Tailscale). Reproducible en otra maquina con: python scripts/setup_memanto.py

*Confidence: 1.0 | Status: active | Created: 2026-09-13T03:01:32*

### Taxonomia BIAN deduplicada en el prompt de candidatos + rol_max_chars 600

> En generacion_contrato_bian, el prompt del paso 2 (mapeo.candidatos, subido a v1.1.0 el 2026-09-16) recibe ahora un bloque <taxonomia_bian> con la documentacion de las 5 Business Areas y los 36 Business Domains del landscape, DEDUPLICADA y enviada una sola vez (~3.3k tokens; inline por SD costaria ~23k por la misma informacion). Regla general: un dato que se repite entre Service Domains va como bloque de cabecera, nunca inline en las 341 lineas del catalogo. Ademas rol_max_chars subio de 240 a 600 (con 240 se recortaba el service_role de 219 de los 341 SD). Como eso sube el SUELO del prompt, los escalones de degradacion dejaron de ser solo el CAG y pasaron a ser pares (chars_negocio, rol_max_chars) en _escalones_catalogo: primero se sacrifica el vocabulario de negocio y solo al final el rol, y el ultimo escalon es siempre (0, 240). Coste total medido del paso 2: de ~26.6k a ~39.7k tokens (+49%). Tests: tests/unit_test/test_taxonomia_bian.py y TestEscalonesDeDegradacion en test_cag_catalogo.py; suite completa 339 tests en verde.

*Confidence: 1.0 | Status: active | Created: 2026-09-17T03:39:48 | Tags: `bian`, `prompts`, `candidatos`, `tokens`, `degradacion`*

### Arquitectura de mapear-historias: outer graph con ...

> Arquitectura de mapear-historias: outer graph con Send por HU -> subgrafo por HU con fan-out Send por candidato -> reconciliar (nodo defer=True: ve TODAS las HU) -> publicar. Nodos LLM genericos en prompts_mapeo.py::SPECS (PROHIBIDO hardcodear funcionalidad/SD en el codigo productivo).
>
> 14 nodos en total, 7 de ellos LLM. Subgrafo (10): extraer_intencion -> generar_candidatos -> revisar_completitud -> [det] preparar_candidatos -> evaluar_candidato (1 llamada aislada por SD, solo senales ordinales 0-3, sin confianza libre) -> [det] clasificar -> revisar_adversarial (prompt independiente) -> [det] aplicar_adversarial -> seleccionar_operaciones -> [det] ensamblar. Outer (4): cargar -> procesar_historia -> reconciliar_funcionalidad (asesor) -> publicar. El arbitro es determinista: scoring_bian + clasificacion_historias + _consolidar; el LLM nunca decide SELECTED/UNRESOLVED/REJECTED.
>
> CORRECCION sobre la version anterior de esta memoria: aplicar_hallazgos_adversariales NO "solo degrada". Mueve en las dos direcciones, y cada movimiento exige una señal calculada aparte que confirme el hallazgo -nunca se reclasifica solo porque el revisor lo dijo-: degrada SELECTED->UNRESOLVED como catch-all conservador, degrada reclasificando OWNED_CONTRACT->CONSUMED_DEPENDENCY (determinar_degradaciones) cuando la accion citada no tiene ningun token en comun con intencion.business_actions, y PROMUEVE CONSUMED_DEPENDENCY->OWNED_CONTRACT (determinar_promociones) con hallazgo ACCION_DIRECTA_COMO_DEPENDENCIA no contradicho, dependency_kind=AUDIT_OR_NOTIFICATION, trazabilidad + evidence_refs y objeto_bom >= 0.15. Al promover se recalcula el score completo, nunca se parchea la etiqueta. Ademas, tras anclar operaciones, finalizar_por_operacion_solida mueve a directo un OWNED_CONTRACT con evidencia oficial verificada y una operacion anclada sin reservas, sin importar el score lexico agregado.
>
> Donde se engancha cada tecnica: CAG en generar_candidatos y revisar_completitud (son los unicos que reciben el catalogo completo); RAG hibrido, Graph RAG, reranker y CRAG viven TODOS en preparar_candidatos y son deterministas -aportan candidatos, no deciden-; la señal de grafo que confirma conflictos de ownership vive en aplicar_adversarial (uso distinto del Graph RAG y con flag distinto); la cache de nodos cubre exactamente los 7 nodos LLM.
>
> Puertos: AnalistaMapeoBianPort (6 metodos, uno por nodo LLM del subgrafo) + MapeadorOperacionesBianPort, adaptadores analista_mapeo_langchain.py y mapeador_operaciones_langchain.py.

*Confidence: 0.95 | Status: active | Created: 2026-09-13T03:10:16*

### Scoring determinista de mapear-historias (scoring_...

> Scoring determinista de mapear-historias (scoring_bian.calcular_score, dominio puro): 30% accion oficial (tokenizacion camelCase) + 25% objeto/schema BOM + 20% ownership + 15% trazabilidad + 10% coherencia Business Area/Domain + hasta +-0.05 segun evidencia. Dos ejes de decision: grupo (directo>=0.90 / tentativo / descartado) y decision_contractual (SELECTED/UNRESOLVED/REJECTED) con motivo_decision tipado (OWNED_SELECTED, TENTATIVE_SCORE, NO_OFFICIAL_BIAN_EVIDENCE, CONSUMED_DEPENDENCY, RELATED_NOT_OWNED, OUT_OF_SCOPE, NAME_UNRESOLVED). Umbrales configurables en config.yaml (mapear_historias.umbral_*) o flags --umbral-directo/--umbral-tentativo.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:17*

### Creados en generacion_contrato_ia_v2/scripts/ (sep...

> Creados en generacion_contrato_ia_v2/scripts/ (sept-2026): generate_entities (arma docs/entity.json: por cada clase BIAN BOM, en que Service Domains/diagramas BOM+Control Record aparece, con descripcion+propiedades de docs/BIANBOM4XMI.xlsx), bian_object_catalog (arma docs/bian-object-catalog.json: resuelve nombre->object_id/url/documentacion en bian.org para Service Domains+clases+Business Areas+Business Domains, cache de shards ~142MB en generacion_contrato_ia_v2/descarga/bian-object-catalog-shards/, gitignored), generate_matrix_view (arma docs/BIAN_Service_Landscape_V14.0_Matrix_View.json: arbol Business Area->Business Domain->Service Domain desde BIANv14.xlsm+SD.json+entity.json+bian-object-catalog.json). generate_matrix_view y bian_object_catalog tienen dependencia circular: correr generate_matrix_view -> bian_object_catalog -> generate_matrix_view de nuevo para que Business Areas/Domains queden con object_url+documentacion (Service Domains no la tienen, se resuelven aparte contra bian-view-catalog.json).

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:41*

### Decisiones de decision contractual anadidas a gene...

> Decisiones de decision contractual anadidas a generacion_contrato_bian el 2026-09-14/15 (commit d3375ba), las dos deterministas y simetricas: (1) finalizar_por_operacion_solida RECORRE LOS TRES GRUPOS, incluido `directo`. Estar en el grupo directo (score >= 0.90) NO implica estar SELECTED: aplicar_hallazgos_adversariales degrada la DECISION sin mover el candidato de grupo, asi que un propietario con evidencia solida se quedaba sin contrato solo por estar ya en directo. Caso medido: Party Reference Data Directory con confianza 0.9650, objeto_bom 1.0, evidencia CACHED_VERIFIED y RetrieveReference anclada sin reservas, y aun asi UNRESOLVED/TENTATIVE_SCORE. Era ademas una incoherencia: un tentativo degradado si se rescataba y un directo degradado no. (2) degradar_sin_operacion_anclada: un SELECTED que no ancla NINGUNA de las operaciones oficiales de su Service Domain pasa a UNRESOLVED/NO_OPERATION_ANCHORED con reason_code DOWNGRADED_NO_OPERATION_ANCHORED, porque el entregable del pipeline es 'que operacion BIAN implementa esta historia' y sin operacion no hay nada que implementar. Como el resto del modulo exige una senal calculada aparte: solo aplica si ese SD SI tenia operaciones oficiales en el catalogo -si no trae ninguna, o el paso 2 esta apagado con --sin-operaciones, no hay nada que reprochar-, y degrada la decision sin mover de grupo. Caso medido: en 2 de 3 corridas PRDD salia SELECTED junto a Correspondence, promovido por el revisor adversarial con confianza 0.965 (mas alta que su propio score), con 17 operaciones disponibles y cero ancladas. Leccion que generaliza: cuando existe un movimiento que SUBE por evidencia fuerte, hay que preguntarse si falta el simetrico que BAJA por ausencia de esa misma evidencia; sin el, el pipeline solo sabe premiar.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T04:56:28 | Tags: `clasificacion`, `ownership`, `operaciones`, `bian`, `determinismo`*

### En generacion_contrato_bian el prompt de candidato...

> En generacion_contrato_bian el prompt de candidatos (mapeo.candidatos, _HUM_CANDIDATOS) coloca el bloque estatico grande (taxonomia + catalogo de 341 SD, ~39.7k tokens) AL FINAL y la parte variable (funcionalidad/HU/intencion) al principio. Ese orden es el peor posible en los dos ejes: impide cualquier cache de prefijo del proveedor (el prefijo identico entre HU queda detras de texto variable) y deja la HU lejos de la posicion de recencia. Invertirlo (estatico primero, HU al final) es un win en ambos ejes y cuesta solo subir prompt_version. Alternativa medida al dump completo: routing jerarquico de dos etapas apoyado en la taxonomia ya implementada — etapa 1 elige Business Domains sobre 41 lineas (~3.3k tok), etapa 2 manda solo los SD de esos dominios con el texto COMPLETO (27 SD medianos = ~4.4k tok; 52 SD de los dominios mas grandes = ~11.3k tok), total ~7.7-14.6k frente a 36.4k hoy con el rol recortado o 64.4k con todo. Distribucion real: 5 areas, 36 dominios, 341 SD, mediana 9 SD por dominio, max 20.

*Confidence: 0.95 | Status: active | Created: 2026-09-17T12:08:41 | Tags: `bian`, `prompts`, `candidatos`, `tokens`, `routing-jerarquico`, `cache-prefijo`*

### Regla de negocio de BQ personalizado: un Control R...

> Regla de negocio de BQ personalizado: un Control Record oficial NO se edita nunca. Si una HU necesita un campo que ningun CR/BQ oficial expone, seleccionar_operaciones puede proponer bq_personalizados citando clase/atributo BOM real, verificado contra schemas_detalle/bom_modelo ANTES de anclar (se descarta con warning si la cita es falsa o el campo ya esta cubierto). Vive SIEMPRE separado de las operaciones oficiales (bq_personalizados_propuestos / custom_bq_candidates, estado CUSTOM_BQ_CANDIDATE), nunca en operaciones_bian/selected_operations. Convencion de nombres verificada contra BIAN real: operationId=Verbo+NombreBQ (PascalCase), path=/{SD}/{id}/{NombreBQ}/{Verbo}.

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:19*

### Routing jerarquico: el nodo 2 partido en 2a enrutar_dominios + 2b candidatos

> En generacion_contrato_bian el paso de candidatos de mapear-historias esta partido en DOS nodos (routing jerarquico, flag mapear_historias.routing_jerarquico_habilitado, ON en config.yaml y False por defecto en la dataclass para que config_test() y los tests viejos sigan igual): 2a enrutar_dominios (prompt mapeo.enrutamiento v1.0.0, elige Business Domains sobre la taxonomia de 41 lineas, separa business_domains de dependency_domains) y 2b generar_candidatos (ve solo los SD de esos dominios pero con texto_completo=True: rol sin recortar + examples_of_use + features, ~189 tok/SD). La tesis NO es filtrar sino MOSTRAR TODO de los que quedan: hoy nadie ve nunca examples_of_use/features y 26 roles van cortados a 600. Medido con la HU real de cuentas_menores: 41.108 tok en un nodo -> 4.686 (2a) + 9.152 (2b, 3 dominios/30 SD) = 13.838; con 5 dominios/55 SD son 18.567. A ese tamano Groq (max_input_tokens 12000) vuelve a caber, cuando con los 341 estaba estructuralmente excluido (suelo 31.363 tok). Riesgo nuevo: un dominio no elegido es invisible. Evidencia medida sobre los 3 casos E2E: los candidatos reales de una HU abarcan 3, 4 y 5 Business Domains y hasta 4 Business Areas, y las dependencias (auth/logs/fraude) viven en OTRO dominio y hasta otra area que el propietario. Tres redes ACTIVAS: (1) el prompt de 2a exige dependency_domains y minimo 3 dominios; (2) _filtrar_por_dominios es determinista y desconfiado -- nombre que no resuelve = incidencia ROUTING_DOMINIO_NO_RESUELTO y no filtra nada; ninguno resuelto = catalogo COMPLETO + ROUTING_SIN_DOMINIOS; (3) preparar_candidatos sigue resolviendo contra los 341 y el nodo 3 sigue viendo el indice global, asi que un SD de un dominio no enrutado entra igual. Cuarta red NO implementada a proposito (inyeccion por retrieval de los top-K fuera de los dominios elegidos) documentada en implementacion_pendiente.md seccion 10 con boceto, flags propios y como decidir si hace falta -- abrirla SOLO si HISTORIA_SIN_CONTRATO sube o un E2E pierde su SD. Metricas nuevas: routing_dominios_por_hu, routing_sd_visibles_por_hu, routing_dominios_no_resueltos, routing_fallback_catalogo_completo, y parametros.routing_jerarquico_activo. El escalon sin recorte se antepone a la escalera de siempre, que queda debajo como red. Tuve que hacer el stub fake independiente del tamano del catalogo (antes tomaba 1 de cada 40 SD; con 27 visibles la demo offline acababa sin ningun SD y el CLI salia con exit 1). Tests: tests/unit_test/test_routing_jerarquico.py (12) + 2 en test_cag_catalogo.py. Suite: 369 OK. PENDIENTE: no se ha corrido ni una E2E con LLM real contra el routing; el gate acordado son los 3 expected-result.json y E2E_REPETICIONES=15 por la varianza del 27%.

*Confidence: 1.0 | Status: active | Created: 2026-09-17T18:49:54 | Tags: `bian`, `routing-jerarquico`, `nodo2`, `tokens`, `taxonomia`, `recall`*

### Implementado el canal determinista de propiedad de...

> Implementado el canal determinista de propiedad de clases BOM en el nodo 2a de generacion_contrato_bian (2026-09-17, flag mapear_historias.entidades_bom_habilitado, OFF por defecto): src/dominio/entidades_bian.py (puro: tokenizar_consulta / clases_requeridas / candidatos_por_propiedad / valores_por_enum), puerto CatalogoEntidadesBianPort, adaptador CatalogoEntidadesJson sobre docs/entity.json, modelos EvidenciaClaseBom y CandidatoClaseBom en historias.py, campo candidatos_por_clase en HistoriaConServiceDomains y en EstadoHistoria, e incidencia ROUTING_PROPIETARIO_DE_CLASE_BOM cuando el canal anade un propietario cuyo Business Domain el router por LLM no eligio (anade el SD, nunca el dominio entero). Decisiones clave: un ENUM no es candidato, solo evidencia de la clase que lo usa; el peso de una clase que se llama como su propio SD va a la mitad (_PESO_CLASE_ECO) porque emparejarla es emparejar el nombre del SD; y cada EvidenciaClaseBom lleva atributos_adicionales + nota que distingue 'SOLO tipifica con el enum' de 'tipifica Y guarda el valor' -Contact Point vs Phone Address-, que es la senal que el paso 3 necesita para decidir. Vocabulario nuevo: CLASES_BOM_POR_TERMINO en vocabulario_bian.py, 1:N y con el mapeo cliente/usuario/persona/menor/tutor -> party, que es lo que hace funcionar el canal. Tests: tests/unit_test/test_entidades_bian.py (9) + TestPropiedadDeClaseRescataAlPropietario en test_routing_jerarquico.py; suite completa 381 OK. Veredicto tecnico sobre las tecnicas evaluadas: esto es un JOIN determinista sobre un archivo local, las unicas de la lista que aportan son query rewriting (critico, ya implementado), BM25 para el paso de 'que clases pide la HU', Recall@K para decidir si se enciende, y el tracing que ya existe; RAG/GraphRAG/reranking/agentes/ReAct/LLM-as-judge no aportan, y MoE/KV cache/speculative decoding/continuous batching son de la capa de serving del proveedor, no del pipeline.

*Confidence: 0.95 | Status: active | Created: 2026-09-18T01:44:22 | Tags: `bian`, `nodo2a`, `entity-json`, `ownership`, `implementacion`, `flags`*

### Regla de diseno para nodos LLM fragiles en generac...

> Regla de diseno para nodos LLM fragiles en generacion_contrato_bian (commit 36e8eae): AL PASO MAS FRAGIL SE LE PIDE UNA COSA A LA VEZ Y SE LE DEJA CITAR DE LA FORMA MAS FACIL QUE SIGA SIENDO VERIFICABLE. `seleccionar_operaciones` es el unico nodo cuyo fallo deja la historia sin contrato, y se le pedia lo mas dificil posible: TODOS los Service Domains elegibles en una sola llamada y un operationId literal copiado entre decenas. Dos cambios: (1) UNA LLAMADA POR SERVICE DOMAIN -cada llamada ve un solo catalogo y toma una sola decision-; los elegibles son 1-2 en la practica, asi que cuesta 0-1 llamadas extra por HU y la cache de nodos las absorbe al repetir. Cada llamada deja SU huella: el numero de huellas ES el numero de llamadas LLM, y dejarlo en 1 con N llamadas haria mentir al conteo de coste. (2) CITA POR INDICE: las operaciones van numeradas en el prompt y resolver_operation_id acepta 7, [7], #7. Elegir un numero de una lista es mucho mas facil para un modelo pequeno que reproducir InitiateOutbound, y NO relaja el anclaje: el indice se resuelve contra la MISMA lista que se mostro y uno fuera de rango no resuelve nada, igual que un operationId inventado. Es la misma tolerancia que ya existia para 'METODO /path': otro FORMATO de cita, nunca otro contenido.
>
> Resultado medido: la corrida E2E posterior da un resultado de negocio IDENTICO al de antes. Era de esperar -estos cambios atacan la economia del fallo y el espacio de error del modelo debil, no la calidad cuando el modelo responde bien-, y con 25% de varianza una sola pasada tampoco distinguiria una mejora moderada del ruido. Caso que NO se arreglo y esta bien asi: Party Reference Data Directory siguio sin anclar operacion en la HU de notificacion incluso con su llamada dedicada, porque ninguna de sus 17 operaciones (consulta/actualizacion de datos) implementa 'notificar'; el modelo declina, degradar_sin_operacion_anclada lo marca, y 'arreglarlo' habria sido inventar un contrato.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T10:11:08 | Tags: `prompts`, `operaciones`, `modelos-debiles`, `bian`, `anclaje`*

### BOM extendido: CatalogoBianCache._normalizar usa c...

> BOM extendido: CatalogoBianCache._normalizar usa cache_version:2 (request_schema/response_schema resueltos via $ref + parent_control_record en los BQ + schemas_detalle con el cuerpo real de cada schema). PUML BOM en docs/bian-puml/ (272 archivos, copia de architecture/BIAN_PUML/) parseado por src/dominio/puml_bom.py::parsear_puml_bom (puro) -> ModeloBomPuml; puerto CatalogoBomPort / adaptador CatalogoBomPuml. Regla de prompt fija: functional_object sale SIEMPRE del objeto de negocio real, nunca del wrapper Control Record.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:18*

### Presupuesto de tokens por modelo antes de llamar + tiktoken cuelga sin red

> En generacion_contrato_bian cada modelo declara su presupuesto de ENTRADA en config.yaml (providers.<n>.llm.models[].max_input_tokens, o providers.<n>.llm.max_input_tokens como default del proveedor; models acepta string o {name, max_input_tokens}). ChatConFailover estima el tamano del prompt ANTES de llamar y salta sin gastar round-trip a todo modelo cuyo presupuesto no lo admita; si ninguno lo admite lanza PeticionDemasiadoGrande -- la misma senal que el 413 real --, asi que _invocar_reduciendo baja de escalon de catalogo sin haber quemado ninguna llamada. Convive con el filtro aprendido del 413 (el declarado es a priori; el aprendido cubre al modelo cuyo limite real es menor). Medido con la cadena por defecto groq->gemini->huggingface->openrouter->ollama y el catalogo de 341 SD: en el escalon (0,600) el prompt de mapeo.candidatos son ~39.7k tokens estimados y se saltan 4 modelos (los 2 de groq, gemma-4-31b:free y openrouter/free) = 4 round-trips menos por nodo grande y por corrida; con el escalon CAG (300,600), ~60.6k tokens y 6 modelos saltados. LECCION DE ENTORNO IMPORTANTE: tiktoken.get_encoding('o200k_base') DESCARGA el vocabulario la primera vez y en esta maquina (sin salida a Internet) se queda colgado indefinidamente -- colgo una corrida de tests hasta el timeout. Por eso llm.tokenizador='caracteres' (len/llm.chars_por_token, 4.0) es el DEFAULT y 'tiktoken' es opt-in, y aun activado la carga va en un hilo daemon con plazo de 20s que degrada al heuristico en vez de bloquear. Codigo: src/adaptadores/salida/llm/tokens.py (nuevo), failover.py, config_yaml.py (_modelos_llm), contenedor.py. Tests: tests/unit_test/test_failover.py::TestPresupuestoDeclaradoPorModelo / TestEstimacionDeTokens / TestPresupuestoDesdeConfig, incluida una regresion que falla si un modelo de la cadena por defecto se queda sin max_input_tokens. Suite: 355 tests OK.

*Confidence: 1.0 | Status: active | Created: 2026-09-17T17:57:43 | Tags: `bian`, `failover`, `tokens`, `config`, `tiktoken`, `eficiencia`*

### Asimetria estructural del ownership en generacion_...

> Asimetria estructural del ownership en generacion_contrato_bian y como se cerro (commit 2e1c5c7, 2026-09-15): un OWNED_CONTRACT mal clasificado tenia TRES redes -promocion adversarial, finalizacion por operacion solida, degradacion controlada- y un CONSUMED_DEPENDENCY mal clasificado tenia UNA, `determinar_promociones`, que ademas exige que el revisor adversarial TAMBIEN lo detecte: o sea que DOS juicios del LLM coincidan. Si el revisor no lo marcaba no habia salida, porque `_decidir` fuerza REJECTED sin mirar el score y `candidatos_operacion_elegibles` excluye a los no-owned -el paso de operaciones ni se ejecuta, y ningun rescate por evidencia de operacion puede actuar-. Caso real medido: Party Reference Data Directory quedo CONSUMED_DEPENDENCY con confianza 0.795 en una historia de consultar y mostrar datos personales, y la HU acabo sin ningun contrato.
>
> `determinar_promociones_por_accion` es el espejo exacto de `determinar_degradaciones`: aquella BAJA cuando la accion citada no comparte NINGUN token con intencion.business_actions, esta SUBE cuando si los comparte. Sin hallazgo adversarial que lo respalde exige ademas objeto_bom >= 0.50 (contra 0.15 de la promocion con hallazgo) y evidencia BIAN verificada.
>
> EL DETALLE DE DISENO QUE LO HACE SEGURO, y que generaliza a cualquier regla de este pipeline: NO decide el contrato. Solo devuelve el rol a OWNED_CONTRACT, lo que unicamente ABRE LA PUERTA al paso de operaciones; de ahi en adelante manda la evidencia -finalizar_por_operacion_solida sube si hay operacion oficial verificada, degradar_sin_operacion_anclada baja si no se ancla ninguna-. Por eso el piso puede ser exigente sin ser paranoico: el veredicto final lo da la operacion, no la reclasificacion. Regla que se lleva: cuando una regla nueva podria crear falsos positivos, hacer que habilite una COMPROBACION posterior en vez de emitir el veredicto.
>
> Leccion adicional del mismo trabajo: cuando existe un movimiento que sube por evidencia fuerte, hay que preguntarse si falta el simetrico que baja por ausencia de esa evidencia, Y si el que sube depende de que dos juicios del LLM coincidan -si depende, no es una red, es una loteria-.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T13:03:59 | Tags: `ownership`, `asimetria`, `clasificacion`, `bian`, `determinismo`*

### Enrutado de modelos por nodo en generacion_contrat...

> Enrutado de modelos por nodo en generacion_contrato_bian (routing.llm_priority_por_nodo, commit d50dc9d, vacio por defecto): un nodo LLM concreto puede tener otro orden de proveedores que el global, con clave su prompt_id (mapeo.intencion, mapeo.evaluacion, mapeo.operaciones, ...). Razon medida: los 7 nodos no tienen la misma dificultad ni el mismo tamano de prompt -mapeo.intencion lo resuelve cualquier modelo; mapeo.operaciones, que debe citar una operacion concreta entre decenas, es el primero en romperse con uno debil y el unico cuyo fallo deja la historia sin contrato-. Cada nodo con override recibe su propia ChatConFailover construida una vez, y la huella pregunta al chat que REALMENTE resolvio ese nodo (si no, un nodo con cadena propia reportaria el proveedor de otro). --proveedor X sigue mandando sobre el yaml: pinnear la cadena es decision del operador.
>
> TRATO DEL 413 (commit 85ce8e0): es su PROPIA categoria, no 'sin cuota'. La cuota vuelve sola y el tamano no, y esa diferencia se paga dos veces: (a) ChatConFailover recuerda el menor tamano que cada modelo rechazo y se lo salta SIN LLAMARLO para un prompt igual o mayor -antes gastaba dos round-trips de Groq en cada nodo grande, corrida tras corrida-; (b) si NINGUN modelo acepta el tamano lanza PeticionDemasiadoGrande en vez de TodosLosModelosAgotados, y AnalistaMapeoBianLangChain reintenta reduciendo el catalogo por escalones CAG decrecientes hasta 0. Cambiar de modelo no arregla un prompt que no cabe en ninguno; lo unico que lo arregla es mandar menos, y quien sabe como mandar menos es quien armo el prompt, no el failover.
>
> PROPIEDAD DEL FAILOVER QUE NO HAY QUE ROMPER, afinada por el trato del 413: lo que se recuerda es el TAMANO, no el modelo. Cada llamada recorre su cadena desde el PRIMER modelo, sin latch que recuerde cual funciono, asi que un prompt MAS PEQUENO vuelve a intentar al proveedor que rechazo uno grande -observado: con CAG encendido Groq falla en generar_candidatos con ~48k tokens y responde 6-7 llamadas de los nodos pequenos de la misma corrida-; uno igual o mayor se salta sin gastar la llamada. Fijado en tests/unit_test/test_failover.py::TestFailoverReintentaLaCadenaEnCadaLlamada, con tamanos explicitos, para que anadir un latch por MODELO falle ahi.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T04:57:11 | Tags: `failover`, `routing`, `llm`, `nodos`, `bian`*

### Checkpointer persistente de generacion_contrato_bi...

> Checkpointer persistente de generacion_contrato_bian (commit 1fc3a7d): `durabilidad: sync|async` abre una base SQLite en `checkpoint_ruta` (por defecto .cache/checkpoints/mapeo.sqlite) via crear_checkpointer, adaptador inyectado por el contenedor igual que la cache de nodos -la persistencia es infraestructura y la capa de aplicacion no decide donde vive un archivo-. La base y sus directorios SE CREAN si no existen, setup() es idempotente, y solo se abre cuando durabilidad != exit (una corrida normal no deja un archivo SQLite sin que nadie lo pida). NUNCA se versiona: .gitignore excluye .cache/ y ademas *.sqlite, *.sqlite3, *.sqlite-journal, *.sqlite-wal y *.sqlite-shm por si alguien apunta checkpoint_ruta fuera de .cache/, con un test que lo comprueba. Si no se puede abrir degrada a InMemorySaver CON AVISO: perder la persistencia cuesta una re-ejecucion, tumbar la corrida las cuesta todas. check_same_thread=False porque LangGraph ejecuta HU y candidatos en varios hilos y SqliteSaver serializa con su propio lock.
>
> DISTINCION QUE HAY QUE TENER CLARA, son mecanismos distintos y no se sustituyen: la CACHE DE NODOS evita RE-PAGAR las llamadas LLM al re-ejecutar la misma corrida, y funciona aunque el estado se pierda; el CHECKPOINTER deja REANUDAR donde se quedo y habilita interrupt/human-in-the-loop, que es lo que pide el estado UNRESOLVED 'bloqueado para revision humana' que ya existe en el dominio.
>
> AVISO OPERATIVO MEDIDO: una corrida de UNA sola historia dejo 18 checkpoints, 87 writes y ~19 MB de base, porque el estado incluye el catalogo de 341 Service Domains serializado por superstep. La base crece rapido; borrarla entre campanas es seguro porque es desechable por definicion. Dependencia: langgraph-checkpoint-sqlite, ya en requirements.txt.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T10:24:29 | Tags: `checkpointer`, `durabilidad`, `langgraph`, `sqlite`, `persistencia`*

### El nodo seleccionar_operaciones de mapear-historia...

> El nodo seleccionar_operaciones de mapear-historias recibe el checklist de datos requeridos (intencion.business_objects, numerado) y debe cerrar cada dato: cubrirlo en datos_cubiertos, proponer un bq_personalizado, o declararlo en datos_no_cubiertos+gaps. El reparto lo verifica cobertura_datos_requeridos de forma determinista: dato callado = incidencia DATO_REQUERIDO_NO_EVALUADO, dato declarado = DATO_REQUERIDO_SIN_OPERACION, y la tasa es data_coverage_rate. Sin ese checklist el nodo solo ve la HU cruda y la regla 'conjunto minimo suficiente' lo hace parar en la primera operacion del escenario principal, dejando datos reales sin cubrir con todas las metricas en verde.

*Confidence: 1.0 | Status: active | Created: 2026-09-15T21:17:07 | Tags: `bian`, `mapear-historias`, `operaciones`, `cobertura`, `datos-requeridos`*

### A escala de 341 Service Domains el recall de recup...

> A escala de 341 Service Domains el recall de recuperacion es un problema OPCIONAL, no una restriccion: medido el 2026-09-14, el indice global compacto que ya recibe revisar_completitud (nombre + rol recortado a 90 chars) pesa 39.979 chars = ~10k tokens, el catalogo entero con texto_para_indexar y el tope actual de 1.195 chars pesa ~93k tokens, y sin tope ~154k tokens. Es decir: el catalogo COMPLETO cabe en el contexto de los modelos de contexto largo, asi que generar candidatos con todo el catalogo en prompt (CAG) hace Recall@K estructuralmente 1.0 y elimina la clase entera de fallo que el benchmark mide. Regla de decision: CAG gana cuando el corpus es pequeno, estatico (release BIAN fijo), compartido entre todas las consultas y auditable -las cuatro se cumplen aqui-; RAG se reserva para lo grande, fresco o por tenant. Antes de invertir mas en ponderar la fusion RRF hay que medir CAG contra retrieval en el mismo corpus dorado. Salvedad de costo: el ahorro por prompt caching depende del proveedor (Gemini y Anthropic cachean prefijos; Groq no), y en Ollama local sobre el GB10 el contexto largo es gratis en dinero pero no en latencia ni memoria.

*Confidence: 0.9 | Status: active | Created: 2026-09-15T00:28:00 | Tags: `cag`, `retrieval`, `bian`, `contexto-largo`, `benchmark`*

### El estilo Python de generacion_contrato_bian lo fi...

> El estilo Python de generacion_contrato_bian lo fija ruff desde [tool.ruff] del pyproject.toml: line-length 100, target-version py311, select E4/E7/E9/F/I/UP/B (E501 deliberadamente fuera porque el formatter ya corta lo que puede y los strings de prompt largos no deben ensuciar el diagnostico), isort con known-first-party src/tests/unit_test/e2e (unit_test y e2e son los nombres con que los tests se importan entre si porque discover -s tests inserta tests/ como top_level_dir), extend-exclude .venv/docs/salida/graphify-out. El alcance formateado es src/ + tests/ + scripts/ (87 archivos), normalizado de una vez en main y verificado con 'ruff check' y 'ruff format --check'. El editor formatea al guardar con el MISMO ruff del .venv, nunca con reglas propias del editor.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T17:16:42 | Tags: `ruff`, `estilo`, `formateo`, `pyproject`, `python`*

### El regimen bull/bear de Bulkowski NO debe escalars...

> El regimen bull/bear de Bulkowski NO debe escalarse al timeframe operado: su separacion es un rango historico fijo del S&P 500 (marzo 2000-octubre 2002) y todas las tablas del libro estan segmentadas por esa escala secular. Medido el 2026-09-16 sobre el historico real del US500: la etiqueta cambia 0,02 veces por dia con EMA-200 diaria (lo actual) contra 2,15 en 15m, 7,13 en 5m y 36,11 en 1m, y el reparto bull/bear converge a ~55/45 al bajar la escala. El contexto de corto plazo entra como COLUMNA APARTE (benchmarkShortTrend, strategy-engine/benchmark_short.go), publicada pero que ningun criterio/measure rule/Kelly lee, para medirla en los modelos custom_. Que el regimen deje de ser constante se resuelve con MAS HISTORIA, no con menos escala: los eventos en vivo son 40.304 bull y CERO bear, mientras 11 epics ya replayados 2020-2026 aportan 3.533 bear sobre 37.469.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T19:49:12 | Tags: `regimen`, `benchmark`, `us500`, `strategy-engine`, `escala`*

---

## Goals

*Objectives, targets, and milestones to track progress.*

### Retrieval hibrido RRF (src/dominio/fusion_rrf.py, ...

> Estado del retrieval de generacion_contrato_bian al 2026-09-14 (sustituye a la version que decia "Fases 3-5 pendientes": esas fases se implementaron el 2026-09-14 y estan en origin/main).
>
> Implementado y probado, TODO OFF por defecto: retrieval hibrido RRF (src/dominio/fusion_rrf.py, ahora con k y un peso por canal) sobre dos canales dispersos intercambiables -RecuperadorLexico (rapidfuzz, por NOMBRE, el de validar-sd) y RecuperadorBM25 (por TEXTO con IDF y puente ES->EN, el de mapear-historias)- mas el canal denso en memoria; modelo canonico BIAN (scripts/ingest_bian/, 26.044 nodos) con expansion Graph RAG y con el grafo tambien como confirmacion determinista de conflictos de ownership; reranker cross-encoder local; adaptador Qdrant; benchmark y canary en scripts/evaluate_retrieval/; CAG escalonado; CRAG de una vuelta; cache de nodos LangGraph en disco.
>
> Por que siguen OFF: encender un flag exige el canary con LLM real, no solo recall. Qdrant/pgvector siguen sin arrancar por defecto (infra/retrieval/docker-compose.yml): 341 Service Domains es poco volumen y Qdrant empata en calidad con el InMemoryVectorStore (ADR docs/adr/0001-vector-store.md). El reranker sigue en false por medicion EN CONTRA, no por falta de medicion.
>
> Lo que queda pendiente ya no son fases de implementacion sino decisiones que necesitan datos o cuota: ver la memoria de pendientes (canary flag por flag, ampliar la capa hu_real del corpus, medir CAG con LLM real).

*Confidence: 1.0 | Status: active | Created: 2026-09-13T03:10:24*

### PENDIENTE ABIERTO al 2026-09-17 en generacion_cont...

> PENDIENTE ABIERTO al 2026-09-17 en generacion_contrato_bian, en este orden exacto y cada paso decide si el siguiente vale la pena: (1) medir el corpus traducido -- correr scripts/evaluate_retrieval/evaluate.py --tipo hu_real apuntando validar_sd.ruta_catalogo_bian al nuevo docs/BIAN_Service_Landscape_V14.0_Matrix_View.es.json, y comparar contra la corrida en ingles; ese delta es la respuesta a cuanto del gap de recuperacion era IDIOMA y no es circular porque la consulta es una HU real escrita por un humano. (2) Probar embeddings multilingues DE ESTANTERIA (BGE-m3, multilingual-e5) sobre el corpus ya en espanol, como linea base sin entrenar: si un modelo entrenado por terceros con millones de pares ES-EN no le gana a la cadena actual, un fine-tune propio con pares sinteticos del lado ingles tampoco. (3) Solo si (1) y (2) mueven la aguja, fine-tune de un bi-encoder con hard negatives sacados del grafo (hermanos del mismo Business Domain, mediana 9 SD, y los 125 SD que comparten Party); material disponible sin etiquetar: 4.580 operaciones, 63.712 propiedades de schema, 3.475 aristas MODELA, 761 BQ, 239 CR. Gate SIEMPRE por capa hu_real, nunca por el promedio global (el canal lexico mide 0.95 global y 0.17 en hu_real). (4) El techo de todo esto siguen siendo 6 consultas hu_real etiquetadas: con 6, un acierto mueve el MRR 0.17 y no se distingue una mejora real de la suerte; ampliar a ~100 sigue siendo el prerrequisito. Recordatorio incomodo medido: en el caso real el SD correcto ya volvia top-1 y la corrida terminaba UNRESOLVED por el revisor adversarial, asi que mejorar el paso 2 al 100% no cambia ese resultado -- esto es una mejora de COSTE y arquitectura (quita el dump de 36k tokens y el diccionario a mano vocabulario_bian.py), no la cura de la precision final.
>  Ya NO queda pendiente de commit: todo ese trabajo (src/, tests/, config.yaml, el landscape .es.json y docs/_respaldo/) se commiteo y pusheo a origin/main el 2026-09-17 en los commits 8329f7f (datos requeridos + taxonomia deduplicada + rol_max_chars 600) y 134822b (landscape traducido), con 339 tests OK.

*Confidence: 1.0 | Status: active | Created: 2026-09-17T14:11:03 | Tags: `bian`, `retrieval`, `bi-encoder`, `traduccion-es`, `pendiente`, `hu-etiquetadas`*

### Pendiente en generacion_contrato_bian para retomar...

> PUNTO DE RETOMA de generacion_contrato_bian (2026-09-15, todo en origin/main hasta 2e1c5c7; 315 tests en verde, sin red y sin LLM). El trabajo pendiente YA NO ES ESCRIBIR CODIGO: son tres decisiones que necesitan datos que hoy no existen. Se retoma cuando haya mas Historias de Usuario etiquetadas del banco. El protocolo paso a paso, con los comandos, esta en implementacion_pendiente.md, seccion 'Retomar aqui cuando haya mas HU etiquetadas'.
>
> ESTADO: nueve funcionalidades implementadas y TODAS APAGADAS por defecto (retrieval hibrido con BM25 + puente ES->EN + RRF ponderado, CAG escalonado, Graph RAG, senales de grafo para el adversarial, CRAG de una vuelta, reranker -este descartado por medicion EN CONTRA-, cache de nodos, durabilidad con checkpointer SQLite persistente + --reanudar, orden de modelos por nodo). Mas los arreglos que si estan siempre activos porque son correcciones, no features: visibilidad de operaciones (OPERATION_MAPPING_EMPTY, coverage_rate, HISTORIA_SIN_CONTRATO, citas descartadas registradas), las dos decisiones contractuales simetricas, la promocion por accion declarada, el trato del 413 y el rediseno del nodo de operaciones (una llamada por SD + cita por indice).
>
> PASO 0 (lo unico que no se automatiza): meter las HU nuevas en la capa hu_real del corpus dorado. Hoy son 6 consultas de negocio; los otros 91 casos son consultas-nombre generadas que miden validar-sd, NO el problema de negocio. Protocolo en la skill corpus-dorado-bian. Con ~30 ya se puede decidir el canal disperso y los pesos de la fusion (hoy el mejor punto medido -k=20, peso 0.25, MRR 0.608- esta sobreajustado a 6 casos, donde un acierto mueve 0.17).
>
> PASO 1: `evaluate.py --tipo hu_real` y `--barrido rrf-bm25 --tipo hu_real`. NUNCA el promedio global: el canal lexico mide 0.95 de Recall@10 global y 0.17 en hu_real.
>
> PASO 2: canary con LLM real (--proveedor ollama, sin cuota), flag por flag y REPETIDO. Barato por la cache de nodos.
>
> PASO 3: E2E con E2E_REPETICIONES (3 como gate diario, 15+ para decidir un default). Ver la memoria de la regla estadistica: bajo 27% de varianza, 6 verdes seguidos tienen ~15% de probabilidad por azar.
>
> QUE MIRAR ademas del verde/rojo, todo ya en el JSON de cada corrida: historias_sin_contrato, operation_coverage_rate, operation_mapping_empty, ownership_conflict_rate_respaldado, y los reason_codes OWNERSHIP_PROMOTED_BY_DECLARED_ACTION (la red de seguridad del ownership actuando) y DOWNGRADED_NO_OPERATION_ANCHORED (el modelo reclamando contratos que no sostiene con una operacion).
>
> PENDIENTE MENOR: encadenar el enriquecedor a generate_matrix_view; ownership_conflict_rate mete descartados en el denominador; interrupt/human-in-the-loop para el UNRESOLVED bloqueado (base tecnica lista, falta decidir el protocolo del CLI); entrenar modelo propio descartado hasta tener el corpus; pgvector no mientras la ADR no cambie.
>
> ENTORNO: exportar HF_HOME=~/.cache/hf-local (la cache global de HuggingFace es de root). Ollama local sirve qwen3.8:27b-q8_0 (chat, 262k contexto) y qwen3-embedding:8b. git push necesita `git -c credential.helper='!gh auth git-credential' push`; `gh auth setup-git` lo dejaria permanente. E2E contra otra config: EJECUTAR_E2E=1 MAPEO_CONFIG=/ruta/config.yaml. La base del checkpointer crece ~19 MB por HU y es desechable.

*Confidence: 1.0 | Status: active | Created: 2026-09-14T23:10:27 | Tags: `pendientes`, `roadmap`, `retrieval`, `continuar`*

---

## Commitments

*Promises, obligations, and TODOs that need follow-through.*

### PENDIENTE ABIERTO al 2026-09-16: completar el repl...

> PENDIENTE ABIERTO al 2026-09-16: completar el replay historico 2020-2026 de los 122 epics que faltan (solo 11 de 133 hechos). Se corre desde la MAQUINA LOCAL contra el Postgres remoto con scripts/run-replay-historico.sh (ver la memoria de como correrlo). Es el unico camino identificado para que el analisis deje de seleccionar ruido: la mediana de muestra por celda (estrategia x epic x temporalidad x direccion) es 1 sobre 3.922 celdas, y el regimen es una CONSTANTE en los datos en vivo (40.304 bull, CERO bear) mientras los 11 epics ya replayados aportan 3.533 bear sobre 37.469. Ademas es el prerrequisito para RE-MEDIR la columna benchmarkShortTrend, que sobre los 8.344 cierres actuales no muestra senal detectable. Prerrequisitos ya cumplidos: (1) pro-v0.1.150 dejo desplegada la imagen con benchmarkShortTrend, asi que la pasada unica la captura; (2) el US500 semanal ya tiene 351 velas sin huecos desde 2020-01-06, de sobra para las 200 de la EMA -- no hay que construirlo agregando diarias.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T20:42:54 | Tags: `replay`, `pendiente`, `dataset`, `regimen`, `muestra`*

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

### PUNTO DE CONTINUACION de generacion_contrato_bian ...

> PUNTO DE CONTINUACION de generacion_contrato_bian al cierre del 2026-09-17: queda implementado y en verde el canal determinista de propiedad de clases BOM en el nodo 2a (src/dominio/entidades_bian.py + puerto CatalogoEntidadesBianPort + adaptador CatalogoEntidadesJson sobre docs/entity.json + modelos EvidenciaClaseBom/CandidatoClaseBom + CLASES_BOM_POR_TERMINO + integracion en _h_enrutar con la incidencia ROUTING_PROPIETARIO_DE_CLASE_BOM), con el flag mapear_historias.entidades_bom_habilitado en false, suite completa 381 OK y NADA COMMITEADO. Lo siguiente, acordado pero sin empezar: etiquetar las tres HU de tests/resources como casos hu_real del corpus dorado (skill corpus-dorado-bian) y medir Recall@K con scripts/evaluate_retrieval/ ANTES de encender el flag; la pregunta abierta literal fue '¿preparo el caso etiquetado en el corpus dorado para esas tres HU y lo mido?'. Lo que hay que recordar para retomar: el canal acierta en el eje del OBJETO (Party Reference Data Directory sale #1 en datos_personales y cuentas_menores citando Contact Point [BQ Reference] y Party_Party Relationship [BQ Associations]) y es ciego al eje de la ACCION (Correspondence no aparece en la HU de notificacion porque su evidencia es la operacion InitiateOutbound); entity.json y el Service Landscape NO tienen operaciones, asi que el canal llega a 'Service Domain + Behavior Qualifier' y el operationId sigue saliendo de docs/bian-cache en el paso 9; y la dependencia critica es el mapeo cliente/usuario/persona -> Party, sin el cual gana Location Data Management. Si el usuario pregunta 'donde nos quedamos en la sesion anterior', esto es la respuesta.

*Confidence: 1.0 | Status: active | Created: 2026-09-18T01:56:47 | Tags: `punto-de-continuacion`, `nodo2a`, `entity-json`, `ownership`, `corpus-dorado`, `pendiente`*

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

### Medicion del nodo 2a (enrutar_dominios) con LLM re...

> Medicion del nodo 2a (enrutar_dominios) con LLM real sobre tests/resources/datos_personales (HU 'Crear pantalla de datos personales', groq openai/gpt-oss-120b, 2 corridas identicas): el router elige business_domains [Channel Specific, Customer Management, IT Management] + dependency_domains [Cross Channel] -> 56 de 341 SD visibles. Falla en las DOS direcciones: (a) pierde 2 de los 7 candidatos de la corrida de referencia, Correspondence (Business Support > Document Management and Archive) y Operations Log (Reference Data > External Agency); (b) 30 de los 56 SD visibles son ruido porque elige Channel Specific e IT Management por el VOCABULARIO DE UI de la HU ('pantalla', 'avatar', 'iconos') en vez de por los objetos de negocio -- el propio rationale lo admite ('IT Management cubre la generacion y presentacion de los elementos UI'). Dato a favor de la red 2 de implementacion_pendiente.md §10: BM25 sobre las senales de intencion pone Correspondence en el puesto 2, o sea rescataria 1 de las 2 perdidas sin ninguna llamada extra; Operations Log queda fuera del top-20. Location Data Management NO aparece y es correcto: vive en Reference Data > Market Data (asset_type Location, CR Location Directory Entry, es el directorio de ubicaciones/domicilios), la HU no maneja domicilio, cero ocurrencias en los tres expected-result.json, y ni BM25 ni RecuperadorLexico lo suben al top-20 pese al falso amigo 'direccion de correo' vs 'location address'.

*Confidence: 0.9 | Status: active | Created: 2026-09-18T00:21:08 | Tags: `bian`, `routing-jerarquico`, `nodo2a`, `medicion`, `recall`, `bm25`*

### El reranker cross-encoder BAAI/bge-reranker-v2-m3 ...

> El reranker cross-encoder BAAI/bge-reranker-v2-m3 NO se justifica en generacion_contrato_bian, medido el 2026-09-14 sobre la capa hu_real con el canal disperso ya arreglado: baja R@1 de 0.50 a 0.17, MRR de 0.573 a 0.300 y sube los hard_negatives por delante del positivo de 1 a 4, a cambio de subir R@10 de 0.67 a 0.83. Su numero bueno anterior (R@10 0.71->0.86) era RESCATE de la fusion rota, no merito propio: cuando la fusion mejoro, el reranker paso de rescate a lastre. Regla de decision que generaliza: en este pipeline cada candidato por delante del correcto cuesta una llamada LLM con ~16k tokens de evidencia, asi que la CABEZA del ranking (R@1/MRR/negativos delante) vale mas que la COLA (R@10) -y cualquier componente que intercambie cabeza por cola es una perdida neta-. Causa probable del mal rendimiento: los documentos que se le pasan son texto_para_indexar(), un volcado de metadatos del catalogo, no prosa; los scores salen todos en ~0.003 (el modelo no ve ningun emparejamiento bueno). Reabrirlo exige antes darle a cada SD un texto escrito para leerse. Detalles operativos verificados: el modelo pesa 2,2 GB en disco (568M parametros fp32, NO los 560 MB que decia el comentario del codigo), ya esta descargado en ~/.cache/hf-local, carga en ~18 s por proceso y reordena 10 candidatos en ~430 ms en la GPU (NVIDIA GB10, cuda:0); requiere export HF_HOME=~/.cache/hf-local porque ~/.cache/huggingface es de root. Ademas, con max_candidatos_hu=14 y ~11 candidatos por HU no se trunca nada, asi que hoy el reranker no cambiaria ni una evaluacion aunque se encendiera.

*Confidence: 0.95 | Status: active | Created: 2026-09-15T01:13:57 | Tags: `reranker`, `cross-encoder`, `retrieval`, `benchmark`, `bian`*

### Causa raiz de un falso negativo real encontrado en...

> Causa raiz de un falso negativo real encontrado en produccion (HU 'Notificar actualizacion de datos' -> Service Domain Correspondence quedaba REJECTED sin operaciones pese a tener evidencia BIAN valida): eran las reglas de ownership/scoring/elegibilidad de operacion, NO un problema de retrieval. Fix: promocion determinista CONSUMED_DEPENDENCY->OWNED_CONTRACT solo si el hallazgo adversarial es ACCION_DIRECTA_COMO_DEPENDENCIA + dependency_kind=AUDIT_OR_NOTIFICATION (salida/resultado, no precondicion) + trazabilidad + evidence_refs, y ademas objeto_bom del score >= 0.15 (este ultimo umbral evito un falso positivo real: Party Authentication fue promovido citando su propio CR para un objeto de negocio ajeno, objeto_bom=0.0 exacto).

*Confidence: 0.9 | Status: active | Created: 2026-09-13T03:10:21*

### Causa raiz del canal lexico debil en generacion_co...

> Causa raiz del canal lexico debil en generacion_contrato_bian, medida el 2026-09-14: NO era falta de pesos en la fusion RRF sino un problema de IDIOMA. Las Historias de Usuario estan en espanol y el catalogo BIAN completo (nombre, role_definition, key_features, schemas, PUML) esta en ingles, asi que un canal disperso (BM25 o rapidfuzz) no comparte NI UN termino con el corpus y recupera literalmente cero; el canal denso no lo sufria porque los embeddings son multilingues. La solucion es un puente lexico ES->EN (src/dominio/vocabulario_bian.py, EQUIVALENCIAS_BASE que ya usaba scoring_bian + EQUIVALENCIAS_RETRIEVAL extendida). Regla al ampliar ese mapa: la traduccion es LINGUISTICA, no de respuesta -'correo'->'mail' es legitimo, 'correo'->'correspondence' seria colar la respuesta esperada en el traductor y convertiria el benchmark en profecia autocumplida-. Segunda conclusion medida: cada caso de uso quiere su propio canal disperso, y por eso NO debe haber un unico canal 'lexico': rapidfuzz compara NOMBRES y es intocable para validar-sd (MRR 1.000 en nombres exactos, 0.945 con erratas, donde BM25 se hunde a 0.636 porque una errata cambia letras, no terminos); BM25 compara TEXTO con IDF y es el de mapear-historias (MRR 0.281 vs 0.083 del lexico, y fusionado con el denso 0.573 vs 0.342 del denso solo). La fusion es un INTERCAMBIO, no una mejora libre: gana la cabeza del ranking (R@1 0.17->0.50) y pierde profundidad (R@10 0.83->0.67); aqui la cabeza vale mas porque cada candidato de mas cuesta una llamada LLM.

*Confidence: 0.95 | Status: active | Created: 2026-09-15T00:59:50 | Tags: `retrieval`, `bm25`, `idioma`, `bian`, `fusion-rrf`*

### Benchmark de recuperacion BIAN medido el 2026-09-1...

> MEDICION HISTORICA, SUPERADA: benchmark de recuperacion BIAN del 2026-09-14 ANTES de arreglar el canal disperso. Se conserva porque explica de donde salieron varias decisiones, pero sus numeros y dos de sus conclusiones YA NO DESCRIBEN EL SISTEMA. Los vigentes estan en la memoria de causa raiz del canal lexico y en la del veredicto del reranker.
>
> Lo medido entonces (corpus de 7 consultas sin capas, 341 SD, qwen3-embedding:8b en Ollama local, bge-reranker-v2-m3 en GPU): lexico R@10 0.29 / MRR 0.214 | vectorial 0.86 / 0.436 / 2 negativos | Qdrant 0.86 / 0.434 | RRF 0.71 / 0.370 / 2 | RRF+graph 0.71 / 0.370 | RRF+graph+rerank 0.86 / 0.410 / 4.
>
> SIGUE VIGENTE: (2) Qdrant empata exactamente con el InMemoryVectorStore a esta escala; (3) la expansion por grafo ingenua alcanzaba 157 de 341 SD en dos saltos porque Party la modelan 125 SD y Arrangement 88, y hay que filtrar por especificidad del nodo puente; (4) un reranker lexico como respaldo hundia R@10 de 0.71 a 0.14; (5bis) el gate 'Recall@10 >= 0.95' del plan se aprueba solo porque mide recuperacion, no decision.
>
> QUEDO DESMENTIDO: (1) "la fusion RRF empeora porque mete el lexico con el mismo peso" -el diagnostico era incompleto: el canal disperso no fallaba por peso sino por IDIOMA (consultas en español contra un catalogo integramente en ingles, cero terminos en comun). Con el puente ES->EN y BM25, la fusion SUPERA al mejor canal individual en la capa de negocio (MRR 0.573 vs 0.342). (5) "el cross-encoder rescata lo que la fusion rompe (0.71->0.86)" -ese rescate existia solo porque la fusion estaba rota; con la fusion arreglada el reranker pasa a ser un lastre (MRR 0.573 -> 0.300, y de 1 a 4 hard_negatives delante). Y la conclusion final de entonces -"la mejor configuracion es vectorial a secas"- ya no se sostiene: hoy es RRF(BM25 + denso).
>
> Leccion que generaliza: un componente medido contra una cadena rota puede parecer util solo porque compensa el defecto de otro. Al arreglar el defecto hay que RE-MEDIR todo lo que se justificaba con el, no dar por buena la medicion anterior.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T22:46:11 | Tags: `retrieval`, `benchmark`, `rrf`, `qdrant`, `graph-rag`, `reranker`, `bian`*

### Hipotesis probada y refutada en generacion_contrat...

> Hipotesis probada y refutada en generacion_contrato_bian el 2026-09-14: darle PROSA al cross-encoder BAAI/bge-reranker-v2-m3 en vez del volcado de metadatos de texto_para_indexar() mejora mucho pero NO alcanza. Barrido de 10 variantes de texto (EntradaCatalogo.texto_prosa, medido con evaluate.py --barrido-texto sobre la capa hu_real): la mejor es 'prosa' (nombre + service_role + examples_of_use + executive_summary, ~644 chars) con MRR 0.417 y 2 hard_negatives delante, frente a 0.300 y 4 del texto del indice -o sea el texto SI importaba, +39% de MRR y la mitad de negativos-; pero no reordenar sigue ganando (MRR 0.573, 1 negativo). Forma clara en los datos, util para cualquier futuro reranker: los textos cortos son los peores (executive_summary 129 chars -> MRR 0.108; examples_of_use 159 -> 0.238; features 158 -> 0.141, y ademas features es una lista de vinetas, no prosa) porque el modelo se queda sin contexto para juzgar, y pasar de ~650 chars tampoco ayuda (prosa_features 799 -> 0.297, documentation 891 -> 0.285): el optimo es prosa de longitud MEDIA. Decision: reranker_habilitado sigue en false, pero el pipeline ya pasa 'prosa' en _reordenar_candidatos para que encender el flag no reparta ademas el peor texto posible. Reabrirlo exige otra via (otro modelo, o texto escrito a mano por SD), no otra variante de lo que el landscape publica. Leccion metodologica del mismo barrido: la primera pasada dio 10 filas IDENTICAS porque el reranker no se construia si el canal solo venia en --barrido-texto (medi 'sin rerank' diez veces sin saberlo); un barrido cuyas filas salen todas iguales es sintoma de que el componente barrido no se esta ejecutando, no de un empate.

*Confidence: 0.95 | Status: active | Created: 2026-09-15T01:21:08 | Tags: `reranker`, `cross-encoder`, `texto-prosa`, `benchmark`, `bian`*

### Regla de ownership por clase en docs/entity.json (...

> Regla de ownership por clase en docs/entity.json (validada 2026-09-17 sobre los 3 casos E2E): el razonamiento NO es filtrar entidades, es DISCRIMINAR POR CLASE. Una clase que la HU necesita aparece en N Service Domains; en los SD donde la ocurrencia del BOM lleva notes.Extensible ese SD solo la IMPORTA del modelo generico y se descarta; el SD donde la ocurrencia NO la lleva es el DUENO y es el candidato. Caso canonico: modelar un cliente exige como minimo la clase Party -> Party aparece en 132 ocurrencias, es dueno solo en Party Reference Data Directory (notes {BQ: Reference, AssetType: Party Reference Data}, 6 atributos) y Legal Entity Directory, y queda descartada en 129 SD; en Location Data Management su nota es {Extensible: no, BOMDiagram: 'Party Reference Data Directory BOM Diagram'} con 0 atributos, o sea el propio archivo apunta al dueno. La regla es simetrica: la clase Location lleva Extensible: yes en Party Reference Data Directory y es dueno Location Data Management (14 atributos, AssetType: Location). Dos corolarios medidos: el dueno lleva atributos y el que importa suele traer 0; y solo sirven los diagramas BOM porque Extensible NO existe en los de control record (1.463 ocurrencias CR sin la propiedad, entrarian gratis). Resultado del prototipo por clase: Party Reference Data Directory sale #1 en datos_personales (12.0, via Party + Party Reference Data Directory Entry + Contact Point) y en cuentas_menores (13.0, incluye Party_Party Relationship, que es justo la relacion menor-tutor del BQ Associations); Location Data Management cae a #8 y #3. Dos dependencias criticas: (1) hace falta el mapeo cliente/usuario/persona -> Party en vocabulario_bian, sin el PRDD se cae del top-4 y gana Location Data Management; (2) parte del score viene de clases que se llaman igual que el SD (eco del nombre): quitandolas PRDD sigue #1 en datos_personales (7 vs 6) pero baja al #3 en cuentas_menores. El canal sigue ciego al eje de la ACCION: Correspondence no aparece en la HU de notificacion.

*Confidence: 0.95 | Status: active | Created: 2026-09-18T01:09:55 | Tags: `bian`, `entity-json`, `ownership`, `extensible`, `candidatos`, `validado`*

### En el pipeline mapear-historias el cuello de botel...

> En el pipeline mapear-historias el cuello de botella de precision NO es la recuperacion sino la decision: medido el 2026-09-14 sobre dos corridas E2E reales, ownership_conflict_rate=1.0 y operation_grounding_rate=0.0 en ambas, mientras el SD correcto se recuperaba siempre como top-1 con gran margen (score 1.0 y 0.6733 frente a <=0.36 del resto) y con rol OWNED_CONTRACT bien asignado; el revisor adversarial lo bloqueaba despues dejandolo UNRESOLVED. Coste por HU: 10-12 llamadas LLM (6 fijas + 1 por candidato) con ~16k tokens de mediana por paquete de evidencia, de ahi el 413 de Groq (peso del prompt, no numero de llamadas). Orden de trabajo acordado: (1) correr en Ollama local para eliminar cuota, (2) arreglar el bloqueo adversarial y el grounding de operaciones, (3) enriquecer texto_para_indexar que hoy descarta Documentation/Examples of Use/Executive Summary/Features, (4) corpus dorado que mida la decision final y no solo Recall@K, (5) reranker local solo al encender retrieval hibrido, (6) no entrenar modelo: solo hay 6 HU etiquetadas.

*Confidence: 0.9 | Status: active | Created: 2026-09-14T19:24:28 | Tags: `mapeo-historias`, `precision`, `adversarial`, `retrieval`, `coste-llm`, `diagnostico`*

### entity.json (2.668 entidades BIAN BOM/CR, 5.734 oc...

> docs/entity.json (2.668 clases BIAN BOM/CR, 5.734 ocurrencias) funciona como canal DETERMINISTA de candidatos si se usa la regla correcta: ELEGIBLE = la ocurrencia de la clase en el BOM de ESE Service Domain NO tiene la propiedad 'Extensible' dentro de notes. Medido: 3.895 de 5.734 ocurrencias (68%) son elegibles; las clases elegibles tienen MEDIANA 1 SD (media 1,46) frente a mediana 2 / media 6,2 de las que si llevan Extensible. Es decir: la AUSENCIA de Extensible marca el SD que DEFINE/POSEE la clase, y la presencia marca una clase importada del modelo generico -- normalmente acompanada de HelperDiagram o de BOMDiagram con el nombre del diagrama del dueno (559 de 634 ocurrencias con nota BOMDiagram apuntan justo al SD donde la clase es elegible, 88%). Ejemplos: Party es elegible solo en Legal Entity Directory y Party Reference Data Directory; Transaction solo en Transaction Authorization y Direct Debit Collection; Device solo en Issued Device Administration. Por eso es tambien una senal de OWNERSHIP, no solo de recuperacion. Medicion sobre los 3 casos E2E con la intencion real (match por nombre de clase + nombre de atributo, IDF sobre los 272 SD): E2E1 datos_personales -> #1 Party Reference Data Directory (BQ Reference Instance Record.Cell/Phone Number, Contact Point [BQ Reference], Party.Party Identification) y #2 Location Data Management (clases Electronic Address y Phone Address, ambas con notes {}); cuentas_menores -> mismo top-2; datos_personales_notificacion -> #1 PRDD, #2 LDM y Correspondence solo en el puesto 21, porque su evidencia es la operacion InitiateOutbound y no un nombre de clase/atributo. Requisito previo: dos entradas en vocabulario_bian, el corpus dice 'email' y 'cell/phone' mientras el puente traduce correo->mail y celular->mobile; sin eso PRDD cae al puesto 8. Extras utiles: notes.BQ y notes.ControlRecord etiquetan la clase con su Behavior Qualifier / Control Record (Contact Point lleva BQ 'Reference' -> RetrieveReference), y cada entidad trae bian_bom con descripcion ISO20022 y propiedades tipadas. Limites: 76 de los 341 SD no tienen ninguna clase en entity.json y 7 nombres de SD del archivo no resuelven contra el landscape.

*Confidence: 0.95 | Status: active | Created: 2026-09-18T00:43:00 | Tags: `bian`, `entity-json`, `candidatos`, `retrieval`, `extensible`, `vocabulario`*

### Mecanismo simetrico a la promocion: determinar_deg...

> Mecanismo simetrico a la promocion: determinar_degradaciones reclasifica OWNED_CONTRACT -> CONSUMED_DEPENDENCY (dependency_kind=SUPPORTING_LOOKUP) cuando el revisor adversarial marca DEPENDENCIA_PROMOVIDA_A_CONTRATO y la accion citada no comparte NINGUN token con business_actions (extraidos en extraer_intencion, antes de proponer el SD). Caso real: 'Party Reference Data Directory' evaluado OWNED_CONTRACT citando 'actualizar...' para una HU donde actualizar era precondicion, no accion propia.

*Confidence: 0.85 | Status: active | Created: 2026-09-13T03:10:22*

### docs/BIANv14.xlsm hoja 'Service Domains' tiene 2 t...

> docs/BIANv14.xlsm hoja 'Service Domains' tiene 2 taxonomias de Business Area/Domain INCOMPATIBLES para el mismo Service Domain: columnas 'm...' (modelo, 5 Business Areas oficiales: Business Support, Operations and Execution, Reference Data, Risk and Compliance, Sales and Service; soporta Business Domain anidado via mBusiness Domain parent) vs columnas 'v...' (vista, usada para navegacion del sitio bian.org, SIEMPRE plana). Verificado: un mismo mBusiness Area se reparte hasta en 6 vBusiness Area distintos segun el Service Domain -no son la misma jerarquia simplificada, son ejes cruzados independientes-. NUNCA usar vista como fallback de modelo fila por fila: mezclaria 2 ejes y produce un arbol incorrecto (bug real cometido y corregido en generacion_contrato_ia_v2/scripts/generate_matrix_view/, ver su README seccion 'De donde sale esto').

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:39*

### El replay historico de strategy-engine debe correr...

> El replay historico de strategy-engine se corre desde la MAQUINA LOCAL conectada al Postgres remoto, no en el servidor: asi se hizo la pasada del 2026-09-15 y es sensiblemente mas rapido, porque el cuello de botella es CPU (33 detectores x 8 temporalidades por vela) y no la latencia contra la base, y la instancia Lightsail ademas esta atendiendo el stack en vivo. Dos reglas mas: (1) correrlo DESPUES de desplegar la imagen que ya trae las columnas deseadas y una sola vez, porque inserta con 'on conflict (event_id) do nothing' y un evento escrito por una imagen vieja NUNCA se actualiza en una segunda pasada; (2) lanzarlo desacoplado de la terminal -- el intento del 2026-09-15 corrio los 133 epics atado a la sesion y murio con 'context canceled' tras 11 epics. Usar scripts/run-replay-historico.sh (lotes de 8, reanudable via epics-hechos.txt) con REPLAY_NETWORK=host y scripts/replay.env.example.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T19:49:15 | Tags: `replay`, `strategy-engine`, `idempotencia`, `ssh`, `operacion`*

### Al fijar el interprete de un venv para pyright en ...

> Al fijar el interprete de un venv para pyright en Neovim, la configuracion debe entregarse en on_init (mutando client.settings antes de que el servidor pida su configuracion), no en on_attach seguido de un notify workspace/didChangeConfiguration: reconfigurar despues hace que pyright descarte los diagnosticos del buffer ya abierto y no vuelva a publicarlos hasta la siguiente edicion.

*Confidence: 0.9 | Status: active | Created: 2026-09-14T17:16:44 | Tags: `neovim`, `lsp`, `pyright`, `venv`, `diagnosticos`*

### El usuario de este proyecto verifica activamente l...

> El usuario de este proyecto verifica activamente los JSON generados (entity.json, bian-object-catalog.json, BIAN_Service_Landscape_V14.0_Matrix_View.json) contra las paginas REALES de bian.org (capturas de pantalla, URLs abiertas en el navegador) en vez de confiar ciegamente en la extraccion local. Esa verificacion encontro y corrigio varios bugs reales en la misma sesion: (1) documentation tomaba la seccion equivocada (Role Definition en vez de la seccion homonima, casi siempre vacia), (2) 2 Service Domains quedaban mal clasificados por confundir eje modelo/vista, (3) sd_overview_url duplicado en 2 sub-objetos en vez de vivir 1 sola vez en la raiz. Leccion: antes de dar por buena una extraccion de datos BIAN, cruzar al menos 1-2 casos contra la pagina real de bian.org, no asumir que el pipeline de extraccion es correcto solo porque corre sin errores.

*Confidence: 0.95 | Status: active | Created: 2026-09-13T22:14:43*

### El link de bian.org a la pagina de un objeto tiene...

> El link de bian.org a la pagina de un objeto tiene la forma object_<N>.html?object=<id>. <N> NO es un tipo semantico (Service Domain, Class, etc) sino el numero de shard de almacenamiento interno del sitio (data/all_objects_data_<N>.js, 47 shards, ~127.000 objetos totales, mapeo en data/all_objects_data_mapping.js). Un mismo object_id aparece fisicamente duplicado (identico) en varios shards a la vez -no son objetos distintos-, asi que hay que dedupear por object_id (no por (object_id, shard)) y usar siempre el shard CANONICO del mapping.js. Ademas, cada vez que una clase se dibuja en un diagrama, bian.org le crea un objeto tipo 'Class' extra que es un duplicado posicional (coincide con el alias N<numero> que usan los .puml locales) -hay que preferir tipos mas especificos (Business object, Capability, Grouping segun la categoria) para desambiguar el objeto canonico real. Implementado en generacion_contrato_ia_v2/scripts/bian_object_catalog/.

*Confidence: 1.0 | Status: active | Created: 2026-09-13T22:14:37*

### En la shell que expone Claude Code en este host, '...

> En la shell que expone Claude Code en este host, 'rg' es una FUNCION de shell que redirige a el binario de claude, no ripgrep real; 'command -v rg' devuelve 'rg' y enmascara que ripgrep no esta instalado en el sistema. Al verificar dependencias para otras herramientas (Neovim/snacks, telescope, etc.) hay que comprobar con 'type rg' o buscar el binario real, no confiar en command -v.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T16:58:52 | Tags: `shell`, `claude-code`, `ripgrep`, `verificacion-dependencias`*

### Patron de fallo confirmado en mapear-historias: cu...

> Patron de fallo confirmado en mapear-historias: cuando una metrica de calidad del LLM esta clavada en 0.0 o 1.0, la causa suele ser una desalineacion determinista entre lo que el codigo MUESTRA al modelo y lo que luego VERIFICA, no un fallo del modelo. Dos casos reales corregidos el 2026-09-14: (1) revisar_adversarial recibia el Service Role recortado a 120 chars mientras evaluar_candidato lo recibia a 900, y el revisor emite DIRECTO_SIN_SERVICE_ROLE contra la decision del evaluador -el corte alcanzaba al 90% de los 341 SD, mediana 309 chars-; (2) operacion_evidencia_verificable normalizaba la evidence_ref entera mientras el prompt renderiza los campos como campos_respuesta={Campo:Tipo} y pide citar el nombre exacto, asi que 'CorrespondenceAddressee:Address' nunca empataba con el campo real. Ambas degradaban EN SILENCIO (UNRESOLVED, OPERATION_EVIDENCE_UNVERIFIED) pareciendo comportamiento correcto. Metodo: reproducir con un test que capture el prompt renderizado y comprobar que ese test FALLA con el codigo viejo antes de dar el fix por bueno.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T19:31:28 | Tags: `mapeo-historias`, `prompts`, `verificacion`, `debugging`, `metricas`*

### Leccion metodologica confirmada dos veces en gener...

> Leccion metodologica confirmada dos veces en generacion_contrato_bian el 2026-09-14: al comparar dos fuentes JSON nunca inferir el esquema del PRIMER registro -asi se concluyo erroneamente que al BIAN Service Landscape le faltaban cinco campos de clasificacion que en realidad ya tenia-, sino usar la union de claves de todos los registros y emparejar los campos por VALOR (porcentaje de coincidencia registro a registro), no por parecido de nombre. Ese emparejamiento por valor es lo que despues permitio consolidar dos fuentes sin duplicar un solo atributo y detectar que los 11 campos de SD.json ya existian en el landscape con coincidencia del 94-100%.

*Confidence: 0.95 | Status: active | Created: 2026-09-14T21:53:11 | Tags: `metodologia`, `comparacion-fuentes`, `json`, `bian`*

### El 'default irlanda' de la columna source_server (...

> El 'default irlanda' de la columna source_server (trade_orders y trade_closures en prueba_v2) existe SOLO en la base, nunca en el script versionado scripts/migracion-londres-a-irlanda/migrar-historial.sh, que unicamente hace 'add column if not exists source_server text' + un update puntual. Consecuencia verificada el 2026-09-16: en prueba_v2 esas dos tablas se autoetiquetan (0 nulos con ordenes creandose en vivo) pero shadow_tick_trials (6730/446389) y trade_realized_transactions (101/8440) acumulan nulos por no tener default, y en pro_v2 la columna directamente NO existe porque ese par nacio de un snapshot y no del script. Antes de usar source_server como filtro de analisis hay que verificar por servidor que la columna existe y tiene default, nunca asumirlo desde el repo.

*Confidence: 1.0 | Status: active | Created: 2026-09-16T17:04:55 | Tags: `source-server`, `migracion`, `schema-drift`, `pro-v2`, `prueba-v2`*

---

## Observations

*Patterns noticed, behavioral notes, and recurring themes.*

*No memories of this type.*

---

## Artifacts

*Tool outputs, files, reports, and external references.*

### En generacion_contrato_bian existe docs/BIAN_Servi...

> En generacion_contrato_bian existe docs/BIAN_Service_Landscape_V14.0_Matrix_View.es.json: el Service Landscape BIAN V14 con los 341 Service Domains traducidos al espanol A MANO por Claude (sin script ni llamadas a la API del proyecto, 2026-09-17). Se traducen role_definition/example_of_use/executive_summary/key_features, los 4 general_comment, la documentation de las 5 Business Areas y los 38 Business Domains, y documentation se REGENERA desde los 4 campos con marcadores en espanol. Quedan INTACTOS en ingles por ser claves de join del pipeline: name del SD, nombres de area/dominio, functional_pattern, asset_type, generic_artifact_type, control_record, registration_status, URLs y rutas de diagramas; tambien se conservan en ingles los nombres de otros SD citados dentro de la prosa. El archivo declara idioma=es y un bloque traduccion con la nota de que vale como INDICE DE RECUPERACION y NO como evidencia BIAN: la evidencia sigue siendo el archivo en ingles. El original no se modifico (MD5 6eefb924363847e5d05af8569b837365, respaldo en docs/_respaldo/). Las traducciones fuente por lotes quedan en docs/_respaldo/traduccion_es/ con ensamblar.py, que se niega a escribir si falta un SD o un campo. Consecuencia: NO es reproducible por script; si scripts/generate_matrix_view/ regenera el landscape ingles, el .es.json queda desincronizado. Se valido que CatalogoJson lo carga (341 SD, area_doc/domain_doc en 341) y la suite sigue en 339 tests OK.

*Confidence: 1.0 | Status: active | Created: 2026-09-17T14:08:58 | Tags: `bian`, `landscape`, `traduccion-es`, `indice-recuperacion`, `evidencia`*

---

## Errors

*Failure records, bugs, and lessons learned from mistakes.*

*No memories of this type.*

---

*End of memory export.*
