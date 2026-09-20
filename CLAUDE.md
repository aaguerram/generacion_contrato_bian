# CLAUDE.md — generacion_contrato_ia_v2

Dos casos de uso sobre BIAN Service Domains (**LangGraph + LLM multi-proveedor**, arquitectura hexagonal).
**Toda la evidencia BIAN vive dentro de `generacion_contrato_ia_v2/docs/`** (nunca se lee del
proyecto hermano `architecture/`):
- `BIAN_Service_Landscape_V14.0_Matrix_View.json` = **fuente ÚNICA de Service Domains** (341 SD):
  textos (`role_definition`/`example_of_use`/`executive_summary`/`key_features`/`documentation`),
  clasificación (`functional_pattern`/`asset_type`/`generic_artifact_type`/`control_record`/
  `registration_status`) y jerarquía Business Area/Domain, todo en un archivo y un parser
  (`CatalogoJson`). `SD.json` y `bian-business-areas.json` YA NO se leen en runtime: SD.json
  solo sirve para completarle huecos al landscape con `scripts/enrich_service_landscape/`
  (empareja por VALOR, así que si un dato ya existe con otro nombre manda el del landscape).
- `bian-operation-catalogs.json` = fallback legado (9 SD con operaciones CR/BQ)
- `bian-cache/release14.0.0/<SD>.json` = **cache-first del OpenAPI oficial** por SD (`cache_version: 2`):
  operaciones CR **y** BQ (`parent_control_record`), `schemas` (nombres) + `schemas_detalle`
  (cuerpo: properties/`$ref`/enum values), `request_schema`/`response_schema` por operación,
  vista estructurada `catalog: {control_records, behavior_qualifiers}`, y `evidence`
  (`source_url` + `source_commit_sha` + `content_sha256` + `retrieved_at`).
- `bian-diagrams/puml-bom/<slug>.puml` = 272 diagramas BOM UML BIAN R14 → modelo de clases (atributos tipados
  con cardinalidad, enums, asociaciones), complementa a los schemas de la API.

El pipeline es cache-first: consulta la fuente oficial (`bian-official/public` en GitHub) solo
para candidatos ausentes; no usa Internet ni memoria del modelo como evidencia directa.
`--actualizar-cache-bian` refresca entradas existentes (y sube `.json` de shape viejo a `cache_version: 2`).

1. **`validar-sd`** (`python -m src --service-domain ...`): ¿un nombre de SD existe en el Service Landscape?
   Grafo lineal: exacto → RAG léxico → LLM solo en la franja gris.
2. **`mapear-historias`** (`python -m src mapear-historias ...`): mapea un lote de HU a sus SD.
   (detalle abajo)

- `bian-graph/release14.0.0/grafo.json` = **modelo canónico** (26.044 nodos / 58.226 aristas con
  procedencia) que genera `scripts/ingest_bian/`; lo consume la expansión Graph RAG.

Retrieval avanzado, todo **OFF por defecto** y con flags INDEPENDIENTES en `config.yaml`
(`retrieval_hibrido_habilitado`, `graph_rag_habilitado`, `reranker_habilitado`, `vector_store`,
`retrieval_canal_lexico`, `cag_habilitado`, `grafo_senales_adversarial`,
`crag_reintento_habilitado`, `cache_nodos_habilitado`, `durabilidad`):
Graph RAG (`GrafoBianPort`), reranker cross-encoder local (`RerankerPort`) e índice Qdrant
(`infra/retrieval/`, volumen persistente). Antes de encender cualquiera, medir con
`scripts/evaluate_retrieval/` (benchmark + canary) — el estado real, lo que la medición desmintió
del plan original y lo que queda pendiente están en
[`implementacion_pendiente.md`](implementacion_pendiente.md) §0 y §9. Decisión del backend
vectorial: [`docs/adr/0001-vector-store.md`](docs/adr/0001-vector-store.md).

**Un canal disperso por caso de uso** (medido, ver el README del benchmark): `RecuperadorLexico`
(rapidfuzz) compara la consulta con el **nombre** del SD y es el de `validar-sd` (MRR 1.000 en
nombres exactos, 0.945 con erratas); `RecuperadorBM25` indexa el **texto** del SD con IDF y es el
de `mapear-historias`. BM25 solo funciona porque traduce: las HU están en español y el catálogo
BIAN entero en inglés, así que sin el puente `src/dominio/vocabulario_bian.py` la consulta y el
corpus no comparten ni un término y el canal recupera **cero**. Esa —y no la falta de pesos— era
la causa del 0.29 histórico. `fusion_rrf` acepta `k` y un peso por canal (`rrf_k`,
`rrf_peso_lexico`, `rrf_peso_vectorial`).

Los escalones de degradación del paso 2 son `(chars_negocio, rol_max_chars)`
(`_escalones_catalogo`), no solo el CAG: primero se sacrifica el vocabulario de negocio y solo al
final el Service Role, y el último es siempre `(0, 240)` — el índice mínimo con el que el prompt
siempre cupo. Subir `rol_max_chars` sube el SUELO del prompt, así que sin ese escalón un catálogo
que no cabe en ningún modelo dejaría la HU sin candidatos en vez de degradarse.

**CAG escalonado** (`cag_habilitado` + `cag_chars_por_sd`): a 341 Service Domains el catálogo
entero cabe en contexto (~27k tokens hoy, ~48k con 300 chars de negocio por SD, ~54k con todo lo
que publica el landscape), así que el Recall@K de la recuperación es una **elección**, no una
restricción. El escalón añade `examples_of_use`/`features` al catálogo del prompt de candidatos y
al índice del de completitud.

**Caché de nodos y durabilidad** (`cache_nodos_habilitado`, `cache_nodos_ruta`, `cache_nodos_ttl`,
`durabilidad`): `CacheNodosArchivo` (`BaseCache` de LangGraph sobre disco) cachea los nodos LLM
con `cache_policy`; la clave la calcula el `key_func` de cada nodo desde sus entradas semánticas
más la firma de la corrida (cadena de modelos + `catalog_sha256`), así que ni un modelo distinto
ni una evidencia distinta reutilizan nada. Re-ejecutar tras un fallo de cuota paga **solo lo que
falta**, y medir flag por flag deja de repagar todas las llamadas. `reconciliar` es además un nodo
`defer=True` (ve todas las HU). `durabilidad: sync|async` activa un **checkpointer persistente
SQLite** (`crear_checkpointer`, `checkpoint_ruta`, por defecto `.cache/checkpoints/mapeo.sqlite`):
la base y sus directorios **se crean si no existen**, `setup()` es idempotente, y nunca se
versiona (`.gitignore` excluye `.cache/` y `*.sqlite*`). Si no se puede abrir, degrada a
`InMemorySaver` **con aviso** — perder la persistencia cuesta una re-ejecución; tumbar la corrida
las cuesta todas.

No confundir los dos mecanismos: la **caché de nodos** evita re-pagar las llamadas LLM al
RE-EJECUTAR (y funciona aunque el estado se pierda); el **checkpointer** deja *reanudar* donde se
quedó y habilita `interrupt`/human-in-the-loop, que es lo que pide el `UNRESOLVED` "bloqueado para
revisión humana" del dominio.

**Reanudar** (`--reanudar <thread_id>`): con durabilidad, `parametros.thread_id` sale en el JSON y
el CLI lo imprime al terminar. Continuar entrega `None` como entrada al grafo — mandar la entrada
otra vez lo reiniciaría desde `cargar` y tiraría el trabajo hecho; medido, una corrida caída en
`revisar_adversarial` se reanuda sin repetir `extraer_intencion` ni ninguna `evaluar_candidato`.
Sin durabilidad se **rechaza** en vez de re-ejecutar en silencio. Los modelos del dominio van
declarados en el allowlist de deserialización del serializador (`_clases_del_dominio`, por
reflexión): un tipo fuera de esa lista NO falla, vuelve como `dict` y revienta mucho después y en
otro sitio (visto: `AttributeError: 'dict' object has no attribute 'candidatos_directos'` dentro
de `determinar_promociones`), así que la lista no se escribe a mano y hay un test que la cubre. Coste medido de activarla: **disco, no latencia**. Una corrida de 1 HU deja
18 checkpoints / 87 writes y **~19 MB** —el estado incluye el catálogo de 341 SD serializado por
superstep, así que la base crece rápido y conviene borrarla entre campañas, que es seguro porque
es desechable por definición—, pero el tiempo no se mueve: 1,37 s con durabilidad frente a 1,56 s
sin ella (`--proveedor fake`, misma HU; la diferencia es ruido). Si una corrida con durabilidad
tarda más, la causa está en el failover, no en el checkpointer.

## Configuración: `config.yaml` + `.env`

- **`.env`** = SOLO API keys (`GROQ_API_KEY`, `GOOGLE_API_KEY`, `HF_TOKEN`,
  `OPENROUTER_API_KEY`, `FREELLMAPI_API_KEY`, `DREAMPROMPTING_API_KEY`, `BLAZE_API_KEY`, `ACLIDE_API_KEY`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `LANGSMITH_API_KEY`). NADA más. No se versiona. `FREELLMAPI_API_KEY` es la clave unificada del
  router local FreeLLMAPI (`~/Desktop/claude_cli/freellmapi`, Docker en `100.102.221.79:3011`):
  una clave, todos los free tiers que el router tenga configurados; proveedor `freellmapi` en
  `config.yaml`, estrategia `src/adaptadores/salida/llm/freellmapi.py` (OpenAI-compatible).
- **`config.yaml`** (versionado, sin secretos) = proveedores, modelos, orden de failover, umbrales,
  rutas, observabilidad. Se carga en `src/configuracion/config_yaml.py` -> `Config`;
  `src/configuracion/settings.py` compone `.env` + `config.yaml` (`cargar_settings()` devuelve un `Config`).
- **Orden de modelos POR NODO** (`routing.llm_priority_por_nodo`, vacío por defecto): los 7 nodos
  LLM no tienen la misma dificultad ni el mismo tamaño de prompt — `mapeo.intencion` lo resuelve
  cualquier modelo y `mapeo.operaciones`, que debe devolver un `operationId` literal entre
  decenas, es el primero en romperse con uno débil. La clave es el `prompt_id`. `--proveedor X`
  sigue mandando sobre esto. Ojo con lo que **no** hace falta configurar: cada LLAMADA ya recorre
  su cadena desde el principio, así que un proveedor que devolvió 413 en un nodo de prompt grande
  se vuelve a intentar en el siguiente nodo **si el prompt es más pequeño**
  (`test_failover.py::TestFailoverReintentaLaCadenaEnCadaLlamada`).
- **413 es su propia categoría**, no "sin cuota": la cuota vuelve sola y el tamaño no.
  `ChatConFailover` recuerda el menor tamaño que cada modelo rechazó y **se salta ese modelo sin
  llamarlo** para un prompt igual o mayor — antes gastaba un round-trip por modelo en cada nodo
  grande, corrida tras corrida. Lo que recuerda es el TAMAÑO, no el modelo: un prompt más pequeño
  lo vuelve a intentar primero. Si NINGÚN modelo acepta el tamaño lanza `PeticionDemasiadoGrande`
  en vez de `TodosLosModelosAgotados`, y `AnalistaMapeoBianLangChain` reintenta **reduciendo el
  catálogo** por escalones CAG decrecientes hasta 0 — cambiar de modelo no arregla un prompt que
  no cabe en ninguno; lo único que lo arregla es mandar menos.
- **Presupuesto de entrada declarado por modelo** (`providers.<n>.llm.models[].max_input_tokens`,
  o `providers.<n>.llm.max_input_tokens` como default del proveedor): el paso anterior aprendía el
  límite **del 413**, así que la primera llamada fallida se paga igual en cada proceso nuevo.
  Declarándolo, `ChatConFailover` estima el tamaño del prompt **antes** de llamar y salta sin
  gastar nada a todo modelo cuyo presupuesto no lo admita; si ninguno lo admite lanza
  `PeticionDemasiadoGrande` —la misma señal que el 413 real—, así que el escalón de catálogo se
  reduce sin haber quemado una sola llamada. Los dos filtros conviven: el declarado es a priori,
  el aprendido cubre al modelo cuyo límite real es menor que el declarado. Medido con la cadena
  por defecto y el catálogo de 341 SD (~39.7k tokens estimados en el escalón `(0,600)`): se saltan
  los 2 modelos de Groq y 2 de OpenRouter, o sea **4 round-trips menos por cada nodo de prompt
  grande y por corrida**; con el escalón CAG `(300,600)` (~60.6k) son 6. Un modelo SIN presupuesto
  declarado se llama como siempre. `llm.tokenizador` elige cómo se mide: `caracteres`
  (`len/llm.chars_por_token`, **el default**: sin dependencias ni red) o `tiktoken` (real, pero
  **descarga el vocabulario la primera vez y sin red se cuelga** — por eso es opt-in y su carga
  tiene plazo). La estimación es aproximada a propósito: pasarse de generoso solo devuelve al 413
  de siempre, que sigue funcionando.
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
      **`datos`** —los datos concretos que la HU muestra/captura/cambia, uno por elemento, prompt
      `mapeo.intencion` 1.1.0; son la consulta del canal de propiedad de clases BOM de 2a, porque
      `business_objects` varía entre corridas en cómo AGRUPA ("número celular; correo electrónico"
      vs "información de contacto del cliente") y solo la forma desagregada llega a las clases del
      dato—, `outcomes`, `external_dependencies`, `traceability_ids` HU-/SC-/BR-, `assumptions`,
      `gaps`). **No nombra ningún SD.**
   2a. `enrutar_dominios` → `EnrutamientoDominiosLLM` (**routing jerárquico**,
      `routing_jerarquico_habilitado`, **ON** en `config.yaml`): elige **Business Domains** sobre
      `<taxonomia_bian>` antes de ver ningún SD, y separa `business_domains` (por la acción/objeto)
      de `dependency_domains` (uno por cada `external_dependency`). **No nombra ningún SD.** La
      ganancia NO es filtrar: es que el paso siguiente pueda mostrar el texto **entero** de los que
      quedan. Hoy, con 341 SD en un prompt, el rol va recortado a 600 chars y `examples_of_use` /
      `features` **no se mandan nunca** — justo el vocabulario con el que habla una HU. Medido con
      la HU real de `cuentas_menores`: **41.1k tokens → 4.7k (2a) + 9.2k (2b) = 13.8k** con 3
      dominios (18.6k con 5, que es el caso más ancho de los tres E2E). A ese tamaño **Groq vuelve
      a caber** — con el prompt de 341 SD está estructuralmente excluido. El recorte lo hace código
      determinista, no el LLM: un nombre que no resuelve contra la taxonomía real queda como
      incidencia `ROUTING_DOMINIO_NO_RESUELTO` y no filtra nada, y si no resuelve **ninguno** se
      sigue con el catálogo completo (`ROUTING_SIN_DOMINIOS`) — enrutar mal cuesta tokens, nunca
      candidatos. `preparar_candidatos` sigue resolviendo nombres contra los **341**, así que un SD
      de un dominio no enrutado que nombre el nodo 3 entra igual. Ver `metricas.routing_*` y, si
      empieza a perder candidatos, la red pendiente en `implementacion_pendiente.md` §10.
      **Canal de propiedad de clases BOM** (`entidades_bom_habilitado`, **OFF**; `entidades_canales`,
      `entidades_max_candidatos`, `entidades_top_k_clases`, `entidades_rrf_k`): la red determinista
      para ese modo de fallo, en el mismo nodo y sin LLM. `docs/entity.json` (2.668 clases de los
      diagramas BOM/CR) distingue, por clase, el SD que la **define** (ocurrencia sin
      `notes.Extensible`) de los que solo la importan (`Extensible` + `BOMDiagram` apuntando al
      dueño; `Party` se define en Party Reference Data Directory y se importa en otros 129 SD).
      Paso 1, **qué clases pide la HU**, es recuperación híbrida (`RecuperadorClasesPort`: BM25
      sobre el documento de la clase —nombre + definición + atributos + valores de enum, con el
      camelCase separado (`EmailAddress` → `Email Address`, `separar_camel`)— con la consulta
      traducida, y embeddings multilingües con la consulta en español; el diccionario
      `CLASES_BOM_POR_TERMINO` es un canal más, fusión RRF en `clases_requeridas_desde_rankings`).
      La consulta son los `datos` del nodo 1 (o `business_objects` si no hay). Pasos 2-4, **quién
      la define, con qué Behavior Qualifier, y si el enum solo tipifica o la clase guarda el
      valor** (`_nota_de_enum`), los responde el modelo BIAN (`candidatos_por_propiedad`), nunca
      un ranking: cada clase vota con su peso ENTERO por cada dueño **efectivo**
      (`duenos_efectivos`: una ocurrencia sin `Extensible` pero sin atributos/BQ/CR es una caja
      vacía y no cuenta si otro dueño sí define algo — 488 de 909 ocurrencias dueñas de clases
      compartidas son así), y la ambigüedad queda en `compartida_con`. Los propietarios se AÑADEN
      al catálogo enrutado (`_rescatar_propietarios`, incidencia `ROUTING_PROPIETARIO_DE_CLASE_BOM`,
      lista en `sd_rescatados`) **si pasan el umbral** (`entidades_min_score_rescate` 1.0 **o**
      `entidades_min_canales_rescate` 2 canales; si no, `ROUTING_PROPIETARIO_NO_RESCATADO` — los
      rescates ruidosos medidos venían de un solo canal denso en posición 5-6) con su rastro
      (`candidatos_por_clase`: clase, BQ, canal y posición que la propuso). La consulta resuelve
      FRASES antes que palabras (`FRASES_BOM_POR_TERMINO`: "datos de contacto" → Contact Point +
      `*Address`, sin `contact`, que es el centro de contacto). Da `SD + BQ`, nunca una operación:
      eso sigue siendo el paso 9.
      Fuera del corpus las 40 cajas del metamodelo (`X_SD_Operations`, `X_Instantiation`, ...,
      `es_artefacto_del_metamodelo`): tienen dueño pero no son objetos de negocio y eran la mitad
      del ruido del canal denso. Medido (`scripts/evaluate_retrieval/README.md`, hu_real n=6):
      bm25+vectorial solo, Recall@10 1.00 / MRR 0.569 frente a 0.67 / 0.573 del texto del SD;
      fusionados 1.00 / 0.639. El diccionario **resta** en la fusión, por eso no va en el default.
      Ciego al eje de la acción salvo por el canal vectorial (Correspondence llega #4 en la HU de
      notificación por `Correspondence Management Function`).
   2b. `generar_candidatos` → `CandidatosHistoriaLLM` (nombres del catálogo; **pista, no exhaustiva**).
      **En fan-out** (`candidatos_por_dominio_habilitado`, ON): con routing, una llamada `Send`
      por Business Domain enrutado (~15 SD, ~4k tokens: cabe en Groq y va en paralelo) + una para
      los propietarios rescatados por el canal de 2a, y `fusionar_candidatos` **[determinista]**
      une (`src/dominio/fusion_candidatos.py`: etiqueta gaps con `[grupo]` y descarta las notas de
      un grupo que no propuso nada). Cada grupo usa el prompt `mapeo.candidatos` **1.3.0** (o
      1.3.1 con evidencia): le dice que ve UN grupo, que vacío es respuesta válida y que lo ausente
      no es gap — sin eso cada grupo proponía "lo menos irrelevante" (12-14 candidatos) y reportaba
      como hueco el dueño del dato que estaba en otro grupo. Dominios con < `candidatos_grupo_min_sd`
      (3) SD se juntan. Medido con UNA llamada: 80-88 SD, 19-21k tokens,
      Groq fuera por presupuesto y 43-99 s por HU en 503 de Gemini. El grupo de rescatados es el
      ÚNICO que ve `<propietarios_bom>` (`evidencia_bom_en_candidatos`, OFF: prompt
      `mapeo.candidatos` 1.2.0 con la evidencia del canal —clase, BQ, "solo tipifica / guarda el
      valor", `compartida_con`— redactada como hechos del modelo, sin recomendación; medido sin el
      bloque 2b propuso 0 de 4 rescatados, con él 1 de 3 pero el que no tenía sustancia). La
      taxonomía dice `(N de M SD visibles)` cuando 2a abrió un dominio a medias por un rescate.
      Métrica: `bom_rescatados_propuestos_rate`. `llm_priority_por_nodo.mapeo.candidatos` deja a
      Ollama al final: probado segundo, dos llamadas concurrentes al 27B remoto tardaron >10 min.
      Ve el catálogo formateado (`formatear_catalogo`: nombre · Area > Domain · [patrón/asset] ::
      `service_role` recortado a `rol_max_chars`, **600** — con 240 se recortaba el rol de 219 de
      los 341 SD) **más `<taxonomia_bian>`** (`formatear_taxonomia`): qué cubre cada Business Area
      (5) y Business Domain (36) según el propio landscape, **deduplicado y enviado una vez**
      (~3.3k tokens; inline por SD costaría ~23k por la misma información). Antes esa jerarquía
      viajaba como etiqueta sin definir aunque pesa un 10% del score. Con routing ambos bloques
      llegan **acotados a los dominios elegidos** y **sin recortar** (`texto_completo`: rol entero
      + `examples_of_use` + `features`, ~189 tokens por SD), y la escalera de degradación queda
      debajo solo como red. `documentation` del SD NO se manda **nunca**: es la concatenación
      literal de `service_role` + `examples_of_use` + `executive_summary` + `features`, ~76k
      tokens por cero información nueva.
   3. `revisar_completitud` → `RevisionCompletitudLLM` (prompt `mapeo.completitud` **1.1.0**): el
      ÚNICO paso que sigue viendo los 341 después del routing. Ve el índice global **sin los ya
      propuestos** (su trabajo es encontrar ausencias), los candidatos actuales con su
      `service_role` **completo** (para juzgar solapes), y **`<propietarios_bom>`** — la evidencia
      de clases del nodo 2a, que es con lo que se decide un `ownership_conflicts`: quién DEFINE la
      clase y si **solo tipifica** el dato o **guarda el valor**. `unsupported_candidates` lo
      escribe el CÓDIGO desde la caché de evidencia, no el LLM. Medido en el E2E 1: con el prompt
      1.0.0 devolvía **cero en todos los campos**; con 1.1.0 detecta el conflicto real
      (Location Data Management vs Party Reference Data Directory vs Legal Entity Directory sobre
      Contact Point / Phone Address / Electronic Address), el duplicado eBranch
      Management/Operations y 3 `missing_candidates`, por +1.6k tokens. De su salida **solo
      `missing_candidates` cambia el flujo** (entra al nodo 4 con `origen="completitud"`); el resto
      es documental. Métricas `completitud_candidatos_aportados` / `_seleccionados` /
      `_conflictos_detectados`. **Pendiente**: el bloque lleva TODO `candidatos_por_clase`, así que
      el nodo 3 repesca candidatos que el umbral de rescate del 2a había filtrado (3 en la corrida
      medida) — ver `node_info/03-revisar-completitud-v1.md` §4.
   4. `preparar_candidatos` **[determinista]**: resuelve nombres LLM ∪ `missing_candidates` ∪
      **retrieval híbrido** (opcional, ver abajo) contra el Service Landscape, tope `max_candidatos_hu` —
      lo que exceda el tope NO desaparece en silencio: queda como incidencia
      `TRUNCATED_BY_MAX_CANDIDATOS_HU` —, `CatalogoBianCache.asegurar(...)` (cache-first en
      `docs/bian-cache/release14.0.0`; descarga solo ausentes; `GITHUB_TOKEN` opcional), arma **un
      `PaqueteEvidenciaCandidato` cerrado por SD**: Service Role + CR/BQ + operaciones (con
      `request_schema`/`response_schema` y `parent_control_record`) + `schemas_detalle` (cuerpo de
      cada schema de la Semantic API) + `bom_modelo` (clases/atributos/asociaciones del PUML
      `docs/bian-diagrams/puml-bom/`, `CatalogoBomPuml`) + URL/commit/SHA-256. `deteccion_omitidos.py` corre
      sobre lo NO evaluado → `service_domains_omitidos` (solo reporta; el retrieval híbrido de
      abajo sí reinyecta).

      **Retrieval híbrido** (`mapear_historias.retrieval_hibrido_habilitado`, **OFF por
      defecto**): antes de resolver, `_candidatos_retrieval_hibrido` consulta los
      `RecuperadorSemanticoPort` configurados (canal disperso — `RecuperadorLexico` por nombre o
      `RecuperadorBM25` por texto según `retrieval_canal_lexico` — siempre + vectorial
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
      `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoDegradacionOwnership` y
      `tests/unit_test/test_clasificacion_historias.py::TestDeterminarDegradaciones`. **Promueve**
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
      incidencia `OWNERSHIP_CONFLICT_UNRESOLVED` — que además dice **qué condición** bloqueó la
      promoción (`motivos_no_promocion`: el `dependency_kind`, la trazabilidad que falta o el
      `objeto_bom` con su valor); sin eso, diagnosticar una corrida obligaba a repetirla con LLM
      real. **`determinar_promociones_por_accion`** cierra la asimetría de fondo: un
      `OWNED_CONTRACT` mal clasificado tiene tres redes, y un `CONSUMED_DEPENDENCY` mal clasificado
      solo tenía la promoción adversarial, que exige que DOS juicios del LLM coincidan —si el
      revisor no lo marca, `_decidir` fuerza `REJECTED` y `candidatos_operacion_elegibles` lo
      excluye, así que el paso de operaciones ni corre y ningún rescate por evidencia puede actuar
      (caso real: Party Reference Data Directory, `CONSUMED_DEPENDENCY` con confianza 0.795 en una
      historia de consultar/mostrar datos personales, HU sin ningún contrato). Es el espejo de
      `determinar_degradaciones`: sube `CONSUMED`→`OWNED` cuando la `accion_objeto` citada SÍ
      comparte tokens con `intencion.business_actions`, y como no hay hallazgo que lo respalde
      exige `objeto_bom >= 0.50` (muy por encima del 0.15 de la promoción con hallazgo) y evidencia
      verificada. **No decide el contrato**: solo devuelve el rol a `OWNED_CONTRACT` para abrir la
      puerta al paso de operaciones — de ahí en adelante manda la evidencia
      (`finalizar_por_operacion_solida` sube, `degradar_sin_operacion_anclada` baja). Por eso el
      piso puede ser exigente sin ser paranoico. Ver `metricas.ownership_*` en la salida. Con `grafo_senales_adversarial` (**OFF por defecto**)
      ese conflicto deja de ser solo la palabra del revisor: `GrafoBianPort.objetos_compartidos`
      busca qué nodo REAL del catálogo comparten los candidatos y `confirmar_conflictos_por_grafo`
      aplica la misma regla de especificidad que la expansión — compartir `Party` (125 SD) o
      `Document` (27 SD) no es contender por un objeto, es el andamiaje de BIAN. El veredicto no
      reclasifica nada: cambia el motivo a `OWNERSHIP_CONFLICT_CONFIRMED_BY_GRAPH` o
      `..._NOT_BACKED_BY_GRAPH` y alimenta `ownership_conflict_rate_respaldado`, que es la misma
      tasa descontando el ruido. Confirmar exige **tres** cosas, no dos: que exista un nodo real
      compartido, que ese nodo **discrimine**, y que **tenga que ver con el objeto en disputa**
      (el `accion_objeto` que la clasificación ya atribuyó a ese candidato). La tercera se añadió
      tras medirla: con 11 candidatos la señal confirmaba 6 conflictos apoyándose en objetos sin
      relación con lo disputado (`Access Arrangement` entre Correspondence y Customer Access
      Entitlement para un conflicto sobre "enviar notificación"). Sin ella la regla responde
      "¿comparte este candidato algo específico con ALGÚN otro?", cuya probabilidad crece con el
      número de candidatos, en vez de "¿respalda el catálogo ESTE conflicto?". Caso real que motivó la promoción:
      "Notificar actualización de datos" → Correspondence quedaba REJECTED/CONSUMED_DEPENDENCY
      pese a citar `InitiateOutbound` (`salida/2026-09-11_17-59-40/`). Caso real que motivó el piso
      `objeto_bom`: la misma historia promovía también a "Party Authentication" sin base real
      (`salida/2026-09-12_*/`). Regresión determinista en
      `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoPromocionOwnership` y
      `tests/unit_test/test_clasificacion_historias.py::TestDeterminarPromociones`.
   9. `seleccionar_operaciones` (si `paso2_operaciones`) → **UNA llamada por Service Domain
      elegible**, no una con todos: es el nodo más frágil y el único cuyo fallo deja la historia
      sin contrato, así que cada llamada ve un solo catálogo y toma una sola decisión (los
      elegibles son 1-2 en la práctica, y cada llamada deja SU huella — el nº de huellas ES el nº
      de llamadas LLM). Las operaciones van **numeradas** en el prompt y `resolver_operation_id`
      acepta el índice (`7`, `[7]`, `#7`): elegir un número de una lista es mucho más fácil para un
      modelo pequeño que reproducir un `operationId` camelCase entre decenas, y sigue siendo una
      cita al catálogo REAL — un índice fuera de rango no resuelve nada, igual que un operationId
      inventado. El prompt recibe además `<datos_requeridos>`: el checklist NUMERADO de
      `intencion.business_objects` —los datos que la propia HU declaró en `extraer_intencion`—,
      y cada dato tiene que acabar en uno de tres sitios: `datos_cubiertos` de la operación que lo
      expone (citado por número o literal; `resolver_dato_requerido` lo ancla contra esa misma
      lista cerrada, igual que el `operationId`), `bq_personalizados`, o `datos_no_cubiertos` +
      una línea en `gaps`. "Conjunto mínimo suficiente" se mide contra ESOS datos, no contra el nº
      de operaciones: si dos datos viven en CR/BQ distintos del MISMO SD, hacen falta las dos
      operaciones. Sin esto el nodo solo veía la HU cruda y el "mínimo" lo empujaba a parar en la
      primera operación que resolvía el escenario principal — caso real 2026-09-15, HU "Actualizar
      cuentas de menores": la intención llevaba "Nombre del tutor" ("el nombre del tutor será
      enviado por BE"), el mapeo ancló solo `RetrieveReference` y la corrida terminó en verde
      (`operation_coverage_rate` 1.0) dejando fuera `RetrieveAssociations`, el único BQ de
      `Party Reference Data Directory` que expone la relación entre dos Party
      (`AssociateReference`/`AssociateType`). El reparto lo hace `cobertura_datos_requeridos`
      **[determinista]**: un dato que nadie cubrió NI declaró es incidencia
      `DATO_REQUERIDO_NO_EVALUADO`; uno declarado sin operación, `DATO_REQUERIDO_SIN_OPERACION`
      (resultado legítimo — hay datos de UI —, pero visible). "Cubierto" gana a "declarado": cada
      llamada ve UN Service Domain y declara solo por él. Los `gaps`/`blocking_codes` del nodo
      (incluido `BIAN-SCOPE-008`) ya no se tiran en `_fusionar_mapeos`: salen como
      `OPERATION_GAP_DECLARED`. Regresión determinista en
      `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoCoberturaDatosRequeridos`; E2E real en
      `tests/e2e/test_e2e_cuentas_menores.py`. Devuelve `MapeoOperacionesLLM` para los SD **elegibles** (`candidatos_operacion_elegibles`: `OWNED_CONTRACT` directo O tentativo — YA NO
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
      `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoOperacionesDuplicadas`), `BIAN-SCOPE-008` si una
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
      agregado. **Recorre los TRES grupos, incluido `directo`**: estar en el grupo `directo`
      (score ≥ 0.90) NO implica estar `SELECTED`, porque `aplicar_hallazgos_adversariales` degrada
      la DECISIÓN sin mover de grupo — antes el bucle solo miraba tentativos/descartados y un
      propietario con evidencia sólida se quedaba sin contrato solo por estar ya en `directo`
      (caso real: Party Reference Data Directory, confianza 0.9650, `objeto_bom` 1.0, evidencia
      `CACHED_VERIFIED` y `RetrieveReference` anclada sin reservas, y aun así
      `UNRESOLVED/TENTATIVE_SCORE`).
      **`degradar_sin_operacion_anclada`** es el movimiento simétrico y corre justo después: un
      `SELECTED` que no ancló NINGUNA de las operaciones oficiales de su SD pasa a
      `UNRESOLVED`/`NO_OPERATION_ANCHORED` (+ `DOWNGRADED_NO_OPERATION_ANCHORED`), porque el
      entregable es "qué operación BIAN implementa esta historia" y sin operación no hay nada que
      implementar. Solo aplica si ese SD **sí tenía** operaciones oficiales en el catálogo: si no
      trae ninguna, o el paso está apagado (`--sin-operaciones`), no hay nada que reprochar. Caso
      real: en 2 de 3 corridas, Party Reference Data Directory salía `SELECTED` junto a
      Correspondence, promovido por el revisor adversarial, con 17 operaciones disponibles y cero
      ancladas. Caso real que lo motivó: en una corrida con LLM real, Correspondence salió
      `OWNED_CONTRACT` directo (nada que promover) pero con score 0.6733 (idéntico al caso de
      promoción) — sin este paso quedaba en tentativo pese a tener `InitiateOutbound` ya anclado y
      verificado. Ver `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoFinalizacionPorOperacion`.
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
   total ancladas — **0.0, no 1.0, cuando había SD elegibles y no se ancló ninguna**: antes esa
   división vacía marcaba verde justo en el peor caso, medido en una corrida real con
   `operaciones_ancladas: 0`), `operation_coverage_rate` (SD elegibles que lograron anclar alguna,
   sobre el total de elegibles — distingue "anclé poco y bien" de "no anclé nada"),
   `operation_mapping_empty` (incidencias `OPERATION_MAPPING_EMPTY`: un SD elegible que salió con
   cero operaciones; antes era invisible porque el bucle de anclaje ni se ejecutaba),
   `historias_sin_contrato` (incidencias `HISTORIA_SIN_CONTRATO`: una HU que no dejó NINGÚN SD
   `SELECTED`, con el mejor candidato nombrado y —diagnóstico sin coste— **cuántas operaciones
   oficiales tenía ese candidato que nadie llegó a evaluar**, que es la diferencia entre "no había
   nada que anclar" y "había 17 y no se miraron"; medido en una corrida real, ese peor caso posible mostraba cobertura 1.0 y
   grounding 1.0 porque sin elegibles no había nada que anclar — ahora las dos tasas son `null`
   = "no aplica" cuando no hay elegibles, y la alarma la lleva este contador),
   `operation_id_no_resuelto` (incidencias `OPERATION_ID_UNRESOLVED`, que ahora incluyen las citas
   que el blindaje anti-alucinación del adaptador descarta — antes solo vivían en un
   `logger.warning`, así que "el modelo se inventó todo" era indistinguible de "no propuso nada") y
   `data_coverage_rate` (datos requeridos cubiertos por alguna operación, sobre los de las HU que
   SÍ tuvieron SD elegibles — `null` = no aplica, misma convención que las dos tasas de arriba;
   sus crudos son `datos_requeridos_evaluables` / `datos_requeridos_sin_operacion` /
   `datos_requeridos_no_evaluados`), `operation_gaps_declarados` (`OPERATION_GAP_DECLARED`),
   `finalizados_por_operacion_solida` (`OWNED_FINALIZED_BY_OPERATION_EVIDENCE`, ver paso 9),
   `ownership_conflict_rate_respaldado` + `ownership_conflictos_confirmados_por_grafo` /
   `ownership_conflictos_sin_respaldo_de_grafo` (paso 8).
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
     `CatalogoBomPort` (PUML), `MapeadorOperacionesBianPort` (recibe la `intencion`: sus
     `business_objects` son el checklist de datos requeridos del paso 9), `MapearHistoriasUseCase`.
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

Las pruebas deterministas (unittest, sin red, sin LLM) viven en `tests/unit_test/` (incluye
`support.py`: `config_test()` para un `Config` de un único proveedor `fake`). Las E2E reales viven
en `tests/e2e/` (ver la sección siguiente). `discover -s tests` recorre ambas carpetas igual.

`tests/unit_test/test_arquitectura_hexagonal.py` falla si un import cruza una frontera. No lo relajes:
mueve el código a la capa correcta o introduce un puerto.

### Pruebas de integración/E2E — solo bajo demanda

La suite de arriba es 100% determinista y sin red (`--proveedor fake` o evidencia local). Las
pruebas que hacen llamadas LLM reales (consumen cuota, tardan segundos-minutos) viven igual en
`tests/`, pero **decoradas con `@unittest.skipUnless(os.environ.get("EJECUTAR_E2E") == "1", ...)`**
para que `discover -s tests` las salte por defecto. Se corren explícitamente cuando el usuario lo
pide, nunca de forma automática:

```bash
EJECUTAR_E2E=1 .venv/Scripts/python -m unittest discover -s tests -p "test_e2e_*.py" -v

# N corridas por caso, exigiendo MAYORÍA (medido: 27% de fallo por varianza del modelo sobre 11
# corridas de la misma configuración — con una sola pasada, un rojo no distingue "rompiste algo"
# de "mala suerte"). Por defecto 1, que es la prueba de siempre.
EJECUTAR_E2E=1 E2E_REPETICIONES=3 .venv/Scripts/python -m unittest discover -s tests -p "test_e2e_*.py" -v
```

(`discover -s tests`, no un path con puntos: `discover -s tests` inserta `tests/` en `sys.path`
como `top_level_dir`, que es lo que permite los imports absolutos `from e2e.shared.e2e_common
import ...` / `from unit_test.support import ...` dentro de los tests. Un path con puntos como
`python -m unittest tests.e2e.test_e2e_x` NO inserta `tests/` en `sys.path` -solo el cwd, vía
`-m`- así que esos imports fallan con `ModuleNotFoundError: No module named 'e2e'`.)

**Toda prueba E2E vive en `tests/e2e/`; lo compartido, en `tests/e2e/shared/`.** Ver
[`tests/e2e/README.md`](tests/e2e/README.md) para la regla completa (esquema de
`expected-result.json`, cómo escribir un caso nuevo). Resumen:

```
tests/
  e2e/
    shared/
      e2e_common.py    <- RESOURCES, requiere_e2e, ejecutar_caso(carpeta), cargar_esperado(carpeta),
                          verificar_candidatos_y_operaciones(testcase, resultado, esperado)
    README.md          <- la regla completa
    test_e2e_datos_personales.py
    test_e2e_datos_personales_notificacion.py
  resources/
    datos_personales/            <- autocontenida (ver abajo)
    datos_personales_notificacion/
    <otro_caso>/                 <- futura
```

**Prohibido hardcodear valores de negocio esperados en el `.py` del test** (nombre de Service
Domain, operaciones, etc.). Cada `resources/<caso>/` trae SIEMPRE tres archivos: HU (`.txt`),
`funcionalidad-*.json` (autodescubierto, debe haber exactamente uno) y **`expected-result.json`**
— una corrida de referencia **completa** (la MISMA forma que `mapeo-historias-service-domains.json`,
un `ResultadoMapeoHistorias` serializado; normalmente se arma copiando una corrida real ya
validada), curada a mano. El test la carga con `cargar_esperado()` y compara el resultado en
memoria contra ella con `verificar_candidatos_y_operaciones()`, que exige: (1) los mismos Service
Domain candidatos por historia (unión de directos/tentativos/descartados) y (2) para cada uno,
las mismas `operaciones_bian` comparadas por `(operation_id, method, path, tipo, grupo)` — ignora
a propósito lo narrativo (razonamiento, justificacion, scores, evidence_refs...), que varía de
corrida a corrida aunque el resultado de negocio sea el mismo. El pipeline real sigue escribiendo
su salida completa (`mapeo-historias-service-domains.json`) en la misma carpeta en cada corrida
-se sobreescribe, es el artefacto **actual** inspeccionable, deliberadamente distinto del
`expected-result.json` **estático** de arriba: si el test comparara contra un archivo que el
propio pipeline acaba de escribir, nunca podría fallar tras la primera corrida-. **Nunca** apuntar
a las carpetas compartidas `./HU` / `./ejemplos` de la raíz: son para pruebas manuales del CLI,
cambian de contenido libremente, y ya rompieron una prueba E2E por eso.

Ejemplo: `tests/e2e/test_e2e_datos_personales.py` + `tests/resources/datos_personales/` — replica
`mapear-historias` sobre su propia HU "Crear pantalla de datos personales" y valida la regresión
(debe anclar `RetrieveReference`/`UpdateReference`, nunca `RetrieveDemographics`; ver
`src/dominio/cobertura_operaciones.py`).

Segundo ejemplo: `tests/e2e/test_e2e_datos_personales_notificacion.py` +
`tests/resources/datos_personales_notificacion/` — HU "Notificar actualización de datos" bajo la
funcionalidad macro "Actualización de datos personales" (la misma que usa el primer ejemplo) —
replica el comando manual real usado para validar la corrección de ownership de Correspondence
(`--directorio-hu ./HU --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json`).
Valida que Correspondence quede `OWNED_CONTRACT` (nunca `REJECTED`) con `InitiateOutbound` anclado
(POST, BQ, grupo Outbound). Su equivalente determinista SIN LLM (corre siempre, no gateado) es
`tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoPromocionOwnership` /
`TestGrafoMapeoFinalizacionPorOperacion`. El framing de la funcionalidad cambia el score que el
LLM le da al candidato (0.5033 / 0.6733 / 0.98 observados en corridas reales según el contexto y
qué modelo del failover respondió) — la regresión determinista es la que fija ese caso sin
depender de qué framing use la E2E.

Tercer ejemplo: `tests/e2e/test_e2e_cuentas_menores.py` + `tests/resources/cuentas_menores/` — HU
"Actualizar cuentas de menores" bajo la misma funcionalidad macro. Fija el caso de los DOS datos
en DOS Behavior Qualifier del MISMO Service Domain: `Party Reference Data Directory` debe anclar
`RetrieveReference` (BQ `Reference`: celular/correo) **y** `RetrieveAssociations` (BQ
`Associations`: la relación menor↔tutor, `AssociateReference`). Su equivalente determinista SIN
LLM es `tests/unit_test/test_grafo_mapeo.py::TestGrafoMapeoCoberturaDatosRequeridos`.

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

- Cadena de failover por defecto (`config.yaml → routing.llm_priority`), ordenada por POTENCIA y
  con el proveedor local al final: **`freellmapi → groq → gemini → dreamprompting → huggingface →
  openrouter → ollama`**. Excepción documentada: el nodo 2b (`mapeo.candidatos`) pone Groq primero
  porque son 5-7 llamadas en paralelo por HU y ahí manda la latencia.
  - `freellmapi` = router local de free tiers (`~/Desktop/claude_cli/freellmapi`, Docker en
    `100.102.221.79:3011`, clave unificada `FREELLMAPI_API_KEY`). Un slug servido por varias
    plataformas AGREGA su cuota ("unify"). Sirve `kimi-k3`, `glm-5.3` (1.31M), `deepseek-v4-pro`,
    `glm-5.2`, `deepseek-v4-flash`, `gemini-3.8-flash`, `minimax-m3`, `minimax-m2.5`,
    `qwen3-coder` y `gpt-oss-120b`.
  - `dreamprompting` = meta-router propio (`DREAMPROMPTING_API_KEY`): 9 modelos verificados
    (Nemotron 3 Super 120B, Command A, Mistral Large, Gemini 3.1/2.5 Flash, Llama 3.3 70B...), en
    1-6 s. Va como proveedor aparte porque el adaptador de DreamPrompting del router valida la
    identidad del modelo y este servicio la reescribe: por el router pasaban 2 de 10, en directo 10.
  - **No honran `response_format`**: `qwen3.5-397b` y `nemotron-3-ultra` (vía router), las rutas de
    ElectronHub de `deepseek-v4-flash`/`minimax-m3` (rompieron slugs que funcionaban y se dieron de
    baja), y `claude-sonnet-5`/`minimax-m3` en Experiential Labs.
  - `blaze` = BlazeAPI (`BLAZE_API_KEY`): 200k tokens/día sobre DeepSeek, 10 rpm. Su free tier
    solo responde tras verificar la cuenta en su **Discord** (`discord.gg/cmPGdhXYxp`: entrar,
    pulsar Verify y vincular en `blazeapi.org/settings`); sin eso, 403 en `chat/completions`
    aunque `/usage` y `/models` contesten. Va al final del tramo remoto.
  - `aclide` = ACLIDE (`ACLIDE_API_KEY`): **los modelos frontera del pool** — Claude Opus 5,
    Claude Sonnet 5, GPT-6 Astra, GPT-5.6 (sol/terra/luna), Claude Haiku 4.5 — todos verificados
    en 7-10 s. Dos particularidades que obligan a su propia estrategia (`llm/aclide.py`): no
    expone Chat Completions (usa `/v1/responses`, `use_responses_api=True`) e **ignora
    `response_format`** (con `json_schema` devuelve markdown; con `function_calling` responde
    bien, de ahí su `structured_method`). Su free tier son 20 EUR/mes de créditos COMPARTIDOS y
    cada llamada gasta 1.8-3.2, así que **no se lista en `llm_priority`**: queda el último de la
    cadena, inalcanzable en la práctica, y se usa con `--proveedor aclide` o pinneado por nodo.
  - **Inutilizables hoy**: Cerebras (402 Payment Required), GitHub Models (410, en migración),
    Experiential Labs (exige verificación de tarjeta de 1 USD), ElectronHub premium (402).
  - **El router local rechaza DreamPrompting y ACLIDE** aunque sus claves funcionen: su adaptador
    valida que la respuesta traiga el mismo identificador de modelo y ambos servicios lo
    reescriben ("returned a different or missing model identity"). Por eso van como proveedores
    propios y no como modelos de `freellmapi`.
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
- `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` = 341 Service Domains, **la única fuente**
  que lee el runtime (`config.yaml → validar_sd.ruta_catalogo_bian`). `docs/SD.json` (columnas
  L..V de `docs/BIANv14.xlsm`) y `docs/bian-business-areas.json` quedan como insumo/semilla; el
  primero se usa solo desde `scripts/enrich_service_landscape/` para completar huecos del
  landscape (última corrida: 12 valores, 0 campos nuevos).
  `docs/bian-operation-catalogs.json` = fallback legado, operaciones CR/BQ de 9 SD (semilla).
  `docs/bian-cache/release14.0.0/<SD>.json` = cache-first del OpenAPI oficial por SD
  (`cache_version: 2`: operaciones CR+BQ con `parent_control_record`/`request_schema`/`response_schema`,
  `schemas_detalle` con cuerpo, `catalog` estructurado, `evidence` con commit+SHA-256). ~41 SD sembrados;
  `--actualizar-cache-bian` descarga/actualiza el resto de `bian-official/public`.
  `docs/bian-diagrams/puml-bom/<slug>.puml` = 272 diagramas BOM UML BIAN R14 (semilla; modelo de clases/atributos).
  **Nada de esto se lee de `../architecture/` en runtime — son copias semilla dentro de `docs/`.**
