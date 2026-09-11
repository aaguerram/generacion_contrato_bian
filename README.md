# generacion_contrato_ia_v2

## Pipeline BIAN verificable

`mapear-historias` ejecuta, **por Historia de Usuario**, un subgrafo de 10 pasos (6 nodos LLM +
4 deterministas) con **fan-out interno por candidato** — cada Service Domain a evaluar recibe su
propia llamada LLM aislada contra un paquete de evidencia cerrado (anti-contaminación cruzada
entre candidatos): extracción de intención/acción/objeto → generación de candidatos → revisión de
completitud → preparación determinista del conjunto a evaluar → evaluación aislada por candidato →
scoring y clasificación deterministas → revisión adversarial de ownership → aplicación determinista
de hallazgos → selección de operaciones oficiales (+ propuesta de BQ no oficiales anclados a BOM) →
ensamblado. Un grafo externo hace map-reduce sobre las HU y cierra con una reconciliación global y
la publicación auditable de seleccionados, no resueltos, rechazados, omitidos e incidencias.

La evidencia queda autocontenida en `docs/bian-cache/release14.0.0/`. Por defecto una entrada
existente nunca se descarga otra vez; únicamente se consultan candidatos ausentes. Para forzar
actualización de los candidatos evaluados use `--actualizar-cache-bian`. Si la red falla y no hay
caché, la decisión se conserva como `BIAN_EVIDENCE_UNAVAILABLE`, nunca como falso “no aplica”.

```powershell
python -m src mapear-historias --hu ./HU --func ./funcionalidad.json --dir ./salida
python -m src mapear-historias --hu ./HU --func ./funcionalidad.json --dir ./salida --actualizar-cache-bian
```

Dos casos de uso sobre `docs/SD.json` (341 SD del Service Landscape v14), con evidencia local
cache-first y acceso oficial bajo demanda únicamente para candidatos ausentes:

1. **`validar-sd`** — ¿un nombre de Service Domain existe en SD.json? (`python -m src --service-domain …`)
2. **`mapear-historias`** — mapea un lote de Historias de Usuario a sus Service Domains, con
   **rol contractual** (OWNED / CONSUMED_DEPENDENCY / RELATED), justificación, confianza,
   operaciones oficiales y — cuando ningún CR/BQ oficial cubre un campo real de la historia —
   propuestas de **BQ no oficiales** ancladas a evidencia BOM, en 3 grupos (directo / tentativo /
   descartado). Evidencia BIAN íntegra en `docs/`, sin Internet.
   (`python -m src mapear-historias …`) · ver [sección dedicada](#mapear-historias--historias-de-usuario--service-domains).

- **LangGraph** orquesta el grafo · **LangSmith** para observabilidad (opcional).
- **Configuración**: `config.yaml` (versionado) tiene proveedores, modelos, orden de failover,
  umbrales y rutas. `.env` **solo** lleva API keys (`GROQ_API_KEY`, `GOOGLE_API_KEY`,
  `HF_TOKEN`, `OPENROUTER_API_KEY`, …).
- **Failover multi-proveedor / multi-modelo**: se recorre `routing.llm_priority`; dentro de cada
  proveedor, sus `llm.models` en orden. Si un modelo no tiene cuota (429 / sin créditos / no
  disponible) se pasa al siguiente; si un proveedor se agota, al siguiente proveedor. Reintento
  hasta recorrer todo. 503/timeout se reintenta en el mismo modelo antes de avanzar.
- `validar-sd`: `coincidencia exacta` → si falla → `RAG` → `LLM adjudicador`.
- **RAG por defecto: léxico (`rapidfuzz`), sin API de embeddings**. Opcional: RAG vectorial
  (`validar_sd.rag_estrategia: vectorial` en config.yaml).
- Arquitectura **hexagonal** (ver [ARQUITECTURA.md](ARQUITECTURA.md)).

## El grafo

```mermaid
sequenceDiagram
    autonumber
    actor U as consola
    participant UC as ValidarServiceDomainService (LangGraph)
    participant CAT as CatalogoJson (SD.json)
    participant RAG as RecuperadorLexico (rapidfuzz)  /  RecuperadorVectorial
    participant LLM as AdjudicadorLangChain (Gemini)
    participant OUT as validacion-service-domain.json

    U->>UC: --service-domain "<nombre>" --directorio <ruta>
    UC->>CAT: buscar_exacto(nombre)   (normaliza mayúsculas/espacios/PascalCase)
    alt coincide exacto
        CAT-->>UC: coincidencia_exacta · confianza 1.0   (0 API)
    else no coincide
        UC->>RAG: recuperar(nombre, k=6)
        RAG-->>UC: top-6 con score (WRatio) y similitud_nombre (token_sort_ratio)
        alt similitud_nombre >= 0.90
            Note over UC: similitud_alta · existe=true   (0 API, determinista)
        else similitud_nombre < 0.60
            Note over UC: similitud_baja · existe=false  (0 API, determinista)
        else franja gris 0.60..0.90
            UC->>LLM: adjudicar(consulta, candidatos)   (temp 0, esfuerzo low, seed)
            LLM-->>UC: {razonamiento, existe, canonico, confianza}   · metodo=rag_llm
        end
    end
    UC->>OUT: escribe el resultado en <directorio>
    UC-->>U: exit 0 si existe, 1 si no
```

## Cómo decide  —  y cómo se garantiza la reproducibilidad

```
exacto  →  RAG (2 scores)  →  banda por similitud_nombre  →  { alta | baja } determinista
                                                              { gris }         → LLM
```

| Método | Cuándo | Quién decide | Coste API | ¿Reproducible? |
|---|---|---|---|---|
| `coincidencia_exacta` | el nombre está en SD.json salvo forma (caso/espacios/PascalCase) | código | **0** | **100%** |
| `similitud_alta` | `similitud_nombre` ≥ `RAG_UMBRAL_ALTO` (0.90) — erratas, orden de palabras | código | **0** | **100%** |
| `similitud_baja` | `similitud_nombre` < `RAG_UMBRAL_BAJO` (0.60) — nombre incompleto / ajeno | código | **0** | **100%** |
| `rag_llm` | franja gris (0.60–0.90) | LLM | 1 chat | temp 0 · esfuerzo `low` · seed · modelo pinneado |

El **RAG léxico** calcula **dos scores** por candidato:
- `score` (`WRatio`, permisivo) → **ordena el shortlist** (mete el candidato correcto aunque la consulta esté incompleta);
- `similitud_nombre` (`token_sort_ratio`, estricto) → **decide la banda** (penaliza palabras que faltan).

Ejemplo: `saving` → `WRatio` mete `Savings Account` en el shortlist, pero `similitud_nombre ≈ 0.57 < 0.60` → **`similitud_baja` determinista**, sin LLM, igual en Gemini 3.5 / 3.6 / 4.x y para siempre. `Savings Acount` (errata) → `0.97 ≥ 0.90` → **`similitud_alta`**, también sin LLM.

Solo la franja gris (`Card Auth`, `payment initiation`…) llega al LLM. Ahí: `LLM` adjudica con
los 6 candidatos en contexto (CAG) y **solo puede** devolver un nombre de la lista
(anti-alucinación). Ajusta `RAG_UMBRAL_*` para mover cuánto delega al LLM.

`validar_sd.rag_estrategia: vectorial` usa embeddings + `InMemoryVectorStore` para la recuperación
(la banda se sigue calculando con `similitud_nombre`). Los embeddings tienen **failover
multi-modelo en orden de precisión** (`EmbeddingsConFailover`): recorre `routing.embedding_priority`
× `providers.<n>.embedding.models`, prueba cada uno y se queda con el primero disponible (baja al
siguiente si agota cuota). Cadena por defecto: **Cohere** (`embed-v4.0` → `embed-multilingual-v3.0`
→ `embed-english-v3.0` → los `-light` 384d) → Gemini → OpenRouter. El índice se cachea en `.cache/`
por el modelo **activo** (no por la lista), así un failover no carga un índice de otra dimensión.
`COHERE_API_KEY` (free-tier / trial) solo sirve para embeddings.

## Instalación

```powershell
cd generacion_contrato_ia_v2
./setup.ps1                     # venv + últimas versiones + requirements.lock.txt
```

### Configuración: `config.yaml` + `.env`

- **`.env`** (copia de [.env.example](.env.example)) — SOLO API keys, una por proveedor:
  ```ini
  GROQ_API_KEY=gsk_...
  GOOGLE_API_KEY=AIza...          # o AQ.Ab8...
  HF_TOKEN=hf_...
  OPENROUTER_API_KEY=sk-or-v1-...
  # ANTHROPIC_API_KEY=  /  OPENAI_API_KEY=  /  LANGSMITH_API_KEY=
  ```
  Una var ya presente en el entorno del SO NO se pisa por el `.env`.
- **[config.yaml](config.yaml)** (versionado, sin secretos) — todo lo demás:
  - `routing.llm_priority` / `embedding_priority` — orden de failover entre proveedores.
  - `providers.<nombre>` — `enabled`, `api_key_env`, `base_url`, y `llm.models` / `embedding.models`
    **en orden** (el 1º que responda gana; los siguientes son el failover por cuota).
  - `llm` — `temperature`, `seed`, `esfuerzo`, `reintentos_transitorios`, `backoff_*`.
  - `observabilidad` — `langsmith_tracing`, `langsmith_project`.
  - `validar_sd` / `mapear_historias` — umbrales y rutas de cada subcomando.

### LangSmith (observabilidad)

`config.yaml → observabilidad.langsmith_tracing: true` + `LANGSMITH_API_KEY` en `.env` → LangGraph
traza cada nodo, la búsqueda RAG y la llamada al LLM bajo el proyecto `observabilidad.langsmith_project`.

## Uso

```powershell
# existe (coincidencia exacta, sin API)
.\.venv\Scripts\python.exe -m src --service-domain "current account" --directorio .\salida\run

# errata -> RAG + LLM (failover groq -> gemini -> huggingface -> openrouter según config.yaml)
.\.venv\Scripts\python.exe -m src --sd "Isued Device Administraton" --dir .\salida\run -v

# forzar un único proveedor / usar otro config.yaml
.\.venv\Scripts\python.exe -m src --sd "Card Case" --dir .\salida\run --proveedor gemini
.\.venv\Scripts\python.exe -m src --sd "Card Case" --dir .\salida\run --config .\mi-config.yaml
```

| Flag | |
|---|---|
| `--service-domain` / `--sd` | nombre del Service Domain a validar (obligatorio) |
| `--directorio` / `--dir` | carpeta donde se escribe `validacion-service-domain.json` (obligatorio) |
| `--proveedor` | fuerza un único proveedor (`groq` \| `gemini` \| `huggingface` \| `openrouter` \| `anthropic` \| `openai` \| `fake`) — restringe la cadena a ese proveedor; por defecto usa el failover completo de `config.yaml` |
| `--config` | ruta a `config.yaml` (por defecto: raíz del paquete) |
| `--esfuerzo` | `low` \| `medium` \| `high` (pisa `llm.esfuerzo`) |
| `-v` | log DEBUG |

Exit code: `0` existe · `1` no existe · `2` error de configuración.

### Salida (`validacion-service-domain.json`)

```json
{
  "service_domain_consultado": "Isued Device Administraton",
  "existe": true,
  "service_domain_canonico": "Issued Device Administration",
  "metodo": "rag_llm",
  "confianza": 0.98,
  "razonamiento": "La consulta contiene una errata... hace referencia inequívoca a ...",
  "candidatos": [ { "service_domain": "...", "score": 0.75, "service_role": "..." }, ... ],
  "generado_en": "2026-09-08T21:21:23Z"
}
```

## `mapear-historias` — Historias de Usuario → Service Domains

Segundo caso de uso (subcomando). Dado **un directorio de Historias de Usuario** (`.txt` / `.md`)
y **un JSON de funcionalidad macro**, mapea cada HU a los BIAN Service Domains que la implementan.
**Toda la evidencia BIAN vive en `docs/`** — sin Internet, sin conocimiento externo del modelo:

| Archivo/carpeta en `docs/` | Qué aporta |
|---|---|
| `SD.json` | 341 Service Domains R14: Service Role, Examples of Use, Functional Pattern, Asset Type |
| `bian-business-areas.json` | jerarquía **Business Area → Business Domain → Service Domain** (mismos 341) |
| `bian-operation-catalogs.json` | operaciones oficiales (Control Record / Behavior Qualifier) de los Service Domains materializados |
| `bian-cache/release14.0.0/` | caché **cache-first** del OpenAPI oficial por SD (CR + BQ + `schemas_detalle`, `cache_version: 2`) — solo se descarga lo ausente |
| `bian-puml/` | **272 diagramas PlantUML** del modelo de clases BOM BIAN R14 (clases/atributos/enums/asociaciones), uno por Service Domain; complementa los schemas de la Semantic API y respalda la anti-alucinación de los **BQ personalizados** (`mapear_historias.bom_puml_habilitado`) |

Cada corrida escribe en `<--directorio>/<AAAA-MM-DD_HH-MM-SS>/` (para no pisar corridas previas);
`--sin-timestamp` escribe directo en `<--directorio>`.

```powershell
.\.venv\Scripts\python.exe -m src mapear-historias `
  --directorio-hu .\HU `
  --funcionalidad .\ejemplos\funcionalidad-actualizacion-datos-personales.json `
  --directorio .\salida\mapeo
# sin API (verificación de cableado; selección estable pero no semántica):
.\.venv\Scripts\python.exe -m src mapear-historias --hu .\HU --func .\ejemplos\funcionalidad-actualizacion-datos-personales.json --dir .\salida\mapeo --proveedor fake
# sin el paso de operaciones (no mapea operaciones ni BQ personalizados) · forzar un proveedor:
.\.venv\Scripts\python.exe -m src mapear-historias --hu .\HU --func <f.json> --dir .\salida\mapeo --sin-operaciones --proveedor gemini
# escribir directo en --directorio (sin subcarpeta de fecha-hora):
.\.venv\Scripts\python.exe -m src mapear-historias --hu .\HU --func <f.json> --dir .\salida\mapeo --sin-timestamp
```

| Flag | |
|---|---|
| `--directorio-hu` / `--hu` | directorio con las HU (`.txt`/`.md`), obligatorio |
| `--funcionalidad` / `--func` | JSON `{ "funcionalidad_macro": "...", "detalle": "..." }`, obligatorio |
| `--directorio` / `--dir` | directorio base de salida, obligatorio (ver subcarpeta con fecha-hora arriba) |
| `--sin-timestamp` | escribe directo en `--directorio`, sin subcarpeta `<fecha-hora>` |
| `--proveedor` | fuerza un único proveedor; por defecto usa el failover completo de `config.yaml` |
| `--config` | ruta a `config.yaml` alterno |
| `--esfuerzo` | `low` \| `medium` \| `high` (pisa `llm.esfuerzo`) |
| `--umbral-directo` / `--umbral-tentativo` | pisan `mapear_historias.umbral_directo` / `umbral_tentativo` |
| `--concurrencia` | pisa `mapear_historias.concurrencia` (HU en paralelo, outer graph) |
| `--sin-operaciones` | desactiva el paso de operaciones oficiales (y de BQ personalizados) |
| `--actualizar-cache-bian` | refresca desde la fuente oficial aunque el candidato ya esté en caché |
| `-v` | log DEBUG |

> **Cuota / failover:** `mapear-historias` hace **≈ HU × (3 + n_candidatos + 2) + 1** llamadas por
> corrida — 3 por HU (intención + candidatos + completitud) + 1 evaluación aislada por cada
> candidato a evaluar (tope `mapear_historias.max_candidatos_hu`, 14 por defecto) + 2 por HU
> (adversarial + operaciones) + 1 reconciliación global al final. `concurrencia_candidatos`
> controla cuántas evaluaciones de candidato corren en paralelo dentro de una HU (subgrafo);
> `concurrencia`, cuántas HU corren en paralelo (outer graph). El chat es un **failover** definido
> en `config.yaml`: recorre `routing.llm_priority` (por defecto
> `groq → gemini → huggingface → openrouter`) y, dentro de cada proveedor, sus `llm.models` en orden. Si un modelo
> da 429 / sin créditos / no disponible / prompt-demasiado-grande, salta al siguiente; si el
> proveedor se agota, al siguiente proveedor. `validar-sd` usa la misma cadena.
> `--proveedor <n>` la restringe a un proveedor.
>
> **Groq** (LPU, muy rápido, free) va primero pero su free tier limita ~15k tokens/min: sirve
> `validar-sd` (prompts pequeños) pero da **413** en `mapear-historias` (catálogo BIAN ~26k tokens),
> así que ahí el failover pasa a Gemini automáticamente.

### El grafo — outer map-reduce + subgrafo por HU con fan-out por candidato

`procesar_historia` invoca, por cada HU, un SUBGRAFO con su propio fan-out por candidato. Nodos
en azul = LLM (failover multi-proveedor); nodos en verde = deterministas (código, 0 API).

#### Modelo de nodos (LangGraph)

```mermaid
flowchart TD
    START(["START"]) --> cargar["cargar · det<br/>lee HU + funcionalidad + catálogo 341 SD"]
    cargar -->|"Send × HU"| procesar["procesar_historia<br/>invoca el subgrafo, una vez por HU"]

    subgraph SUB["subgrafo por HU — fan-out interno por candidato"]
        direction TB
        n1["extraer_intencion · LLM<br/>intención de negocio (acciones/objetos/outcomes),<br/>sin nombrar BIAN todavía"]
        n2["generar_candidatos · LLM<br/>propone nombres de SD candidatos<br/>sobre los 341 SD (pista, no exhaustiva)"]
        n3["revisar_completitud · LLM<br/>detecta candidatos faltantes,<br/>sin evidencia o en conflicto de ownership"]
        n4["preparar_candidatos · det<br/>resuelve nombres contra SD.json,<br/>arma UN paquete de evidencia cerrado por candidato"]
        n5["evaluar_candidato ×N · LLM<br/>1 llamada AISLADA por candidato:<br/>solo ve SU paquete de evidencia"]
        n6["clasificar · det<br/>scoring_bian determinista +<br/>tope de confianza por rol contractual"]
        n7["revisar_adversarial · LLM<br/>prompt independiente: contrasta<br/>la hipótesis ya clasificada"]
        n8["aplicar_adversarial · det<br/>aplica hallazgos — SOLO degrada,<br/>nunca promueve un SD"]
        n9["seleccionar_operaciones · LLM<br/>operationId oficiales +<br/>propone BQ no oficiales anclados a BOM"]
        n10["ensamblar · det<br/>arma el resultado final de la HU"]

        n1 --> n2 --> n3 --> n4
        n4 -->|"Send × candidato"| n5
        n5 --> n6 --> n7 --> n8 --> n9 --> n10
    end

    procesar --> n1
    n10 --> reconciliar["reconciliar · LLM (1 vez)<br/>asesor global: ve todas las HU ya clasificadas"]
    reconciliar --> publicar["publicar · det<br/>_consolidar + escribe<br/>mapeo-historias-service-domains.json"]
    publicar --> END(["END"])

    classDef llm fill:#e8eeff,stroke:#5b6fd8,color:#1c2440;
    classDef det fill:#eaf7ee,stroke:#3f9a5c,color:#123018;
    class n1,n2,n3,n5,n7,n9,reconciliar llm;
    class cargar,n4,n6,n8,n10,publicar det;
```

El LLM **nunca** decide el estado final (`SELECTED`/`UNRESOLVED`/`REJECTED`): cada nodo LLM
devuelve señales ordinales, trazabilidad citada, supuestos y gaps; `scoring_bian` +
`clasificacion_historias` + `_consolidar` (código) son el árbitro. `reconciliar` (1 sola llamada,
ve todas las HU ya clasificadas) es un asesor a nivel de funcionalidad — no revierte decisiones,
solo aporta `functionality_role`, historias de apoyo/contra y `reason_codes` a `_consolidar`.

#### Flujo temporal (secuencia)

```mermaid
sequenceDiagram
    autonumber
    actor CLI as consola (mapear-historias)
    participant Outer as outer graph (map-reduce)
    participant Sub as subgrafo (por HU)
    participant LLM as LLM (failover multi-proveedor)
    participant EV as evidencia BIAN (docs/)
    participant OUT as mapeo-historias-service-domains.json

    CLI->>Outer: --directorio-hu / --funcionalidad / --directorio
    Outer->>EV: cargar HU + funcionalidad + catálogo (341 SD)
    EV-->>Outer: historias + catálogo

    loop Send × HU (concurrencia)
        Outer->>Sub: procesar_historia(historia, funcionalidad, catalogo)
        Sub->>LLM: extraer_intencion(historia, funcionalidad)
        LLM-->>Sub: intención (acciones/objetos/outcomes)
        Sub->>LLM: generar_candidatos(intención, catálogo)
        LLM-->>Sub: candidatos SD (pista)
        Sub->>LLM: revisar_completitud(candidatos, índice global)
        LLM-->>Sub: missing_candidates / conflictos
        Sub->>EV: preparar_candidatos (resuelve nombres + arma evidencia)
        EV-->>Sub: paquete de evidencia cerrado × candidato

        loop Send × candidato (concurrencia_candidatos)
            Sub->>LLM: evaluar_candidato(paquete)
            LLM-->>Sub: rol_contractual + rúbricas 0-3
        end

        Sub->>Sub: clasificar (scoring_bian, determinista)
        Sub->>LLM: revisar_adversarial(clasificación)
        LLM-->>Sub: hallazgos (solo degradan)
        Sub->>Sub: aplicar_adversarial (determinista)
        Sub->>LLM: seleccionar_operaciones(SD directos)
        LLM-->>Sub: operationId oficiales + BQ personalizados
        Sub->>Sub: ensamblar (determinista)
        Sub-->>Outer: resultado de la HU
    end

    Outer->>LLM: reconciliar_funcionalidad(todas las HU clasificadas)
    LLM-->>Outer: functionality_role / reason_codes (asesor)
    Outer->>Outer: _consolidar (determinista)
    Outer->>OUT: publicar JSON
    Outer-->>CLI: exit 0 / 1 / 2
```

**Rol contractual** (taxonomía BIAN business-alignment) — clasifica *por qué* aplica el SD:

| rol | significado | tope |
|---|---|---|
| `OWNED_CONTRACT` | la historia **administra/ejecuta** la capacidad y su ciclo de vida | puede ser `directo` |
| `CONSUMED_DEPENDENCY` | solo **consulta/valida/consume** (guard de auth, permisos, auditoría, notificación, riesgo, proveedor externo); lleva `dependency_kind` | **nunca `directo`** (confianza topada `< umbral_directo`) |
| `RELATED_NOT_OWNED` | relación temática, no necesaria para implementar la historia | **nunca `directo`** |

**Dos ejes de decisión** — el `score` es determinista (`scoring_bian`), calculado sobre la
**evaluación aislada** de `evaluar_candidato` (1 candidato ve solo su propio paquete de evidencia):
30% correspondencia con la acción oficial (Service Role + operationId/summary/grupo CR-BQ, con
tokenización camelCase) · 25% objeto/schema BOM · 20% ownership · 15% trazabilidad a escenarios ·
10% coherencia Business Area/Domain; con bonificación/penalización adicional según la rúbrica
`evidence_quality` (0-3) y el `ambiguity` (NONE/LOW/HIGH) que reporta esa evaluación, y ±0.05 según
haya o no evidencia BOM verificable (`CACHED_VERIFIED`/`VERIFIED`). **La confianza libre del LLM no
entra al score** (solo se guarda en `confianza_llm`); el LLM aporta rúbricas enteras 0-3 y señales
ordinales, nunca el veredicto final.

| eje | valores |
|---|---|
| grupo (aplicabilidad) | `directo` ≥ 0.90 · `tentativo` 0.63–0.90 · `descartado` < 0.63 |
| `decision_contractual` | `SELECTED` / `UNRESOLVED` / `REJECTED` |
| `motivo_decision` | `OWNED_SELECTED` · `TENTATIVE_SCORE` · `NO_OFFICIAL_BIAN_EVIDENCE` · `CONSUMED_DEPENDENCY` · `RELATED_NOT_OWNED` · `OUT_OF_SCOPE` · `NAME_UNRESOLVED` |

`SELECTED` exige `grupo = directo`, `rol = OWNED_CONTRACT` y evidencia BOM verificable. Falta de
evidencia con score suficiente → `UNRESOLVED / NO_OFFICIAL_BIAN_EVIDENCE` (nunca "no aplica"); score
por debajo de la banda tentativa → `REJECTED / OUT_OF_SCOPE` aunque falte evidencia. Una dependencia
consumida nunca genera contrato → `REJECTED / CONSUMED_DEPENDENCY` (el grupo/score sigue mostrando lo
requerida que está).

**Anti-alucinación (determinista):** `service_domain` se resuelve contra `SD.json` — match normalizado
exacto, o subcadena única (recupera el canónico), o se descarta (`AMBIGUOUS` / `NOT_FOUND`). El nombre
canónico, `rol_bian`, `business_area` y `business_domain` se copian **desde `docs/`, nunca del LLM**.
En el paso 2, los `operation_id` que no estén en el catálogo local se descartan.

**Principio de conjunto mínimo suficiente + revisión adversarial acción/objeto:** el prompt exige
elegir el mínimo de SD `OWNED_CONTRACT`, y contrastar el verbo+objeto de la historia contra el
Service Role antes de fijar el rol.

### BQ personalizados (no oficiales) — cuando el BOM respalda un campo sin cubrir

Un Control Record no se puede editar. Si una historia necesita un campo que **ningún** CR ni BQ
oficial del SD expone, `seleccionar_operaciones` puede proponer un **Behavior Qualifier no oficial**
— pero solo citando una clase/atributo real del BOM del Service Domain (`schemas_detalle` de la
Semantic API, o el modelo de clases de `docs/bian-puml/`). El código (`_anclar_bq_personalizados`,
determinista) ancla la propuesta solo si:

1. el campo **no** está ya cubierto por una operación oficial,
2. el nombre del BQ **no** colisiona con un CR/BQ oficial existente del SD, y
3. la clase/atributo BOM citados **existen de verdad** (se verifica contra la evidencia, nunca se
   "arregla" una cita floja).

El resultado vive separado de `operaciones_bian` en un campo propio
(`bq_personalizados_propuestos` / `custom_bq_candidates`), con `estado: "CUSTOM_BQ_CANDIDATE"`, para
que nunca se confunda con una operación oficial BIAN — queda marcado como pendiente de revisión de
gobierno antes de tratarse como endpoint real.

### JSON de entrada (`--funcionalidad`)

```json
{
  "funcionalidad_macro": "Actualización de datos personales",
  "detalle": "Permitir que el cliente actualice su número celular y correo electrónico desde la app, usando validaciones existentes y Smart Token, con trazabilidad y notificación de los cambios."
}
```

Alias tolerados: `funcionalidad` / `nombre` / `macro` para el nombre; `descripcion` / `detail` /
`contexto` para el detalle.

### Salida (`mapeo-historias-service-domains.json`)

```json
{
  "funcionalidad_macro": "…", "detalle": "…", "total_historias": 6,
  "parametros": { "cadena_llm": "gemini:…", "umbral_directo": 0.9, "umbral_tentativo": 0.63,
                  "concurrencia": 1, "concurrencia_candidatos": 2, "max_candidatos_hu": 14,
                  "paso2_operaciones": true, "top_n_omitidos": 5 },
  "historias": [
    {
      "archivo": "HU-Actualizar correo electrónico.txt",
      "titulo": "Actualizar correo electrónico",
      "razonamiento": "capacidades / conjunto mínimo suficiente / dependencias consumidas",
      "business_actions": ["update"], "business_objects": ["email address"],
      "assumptions": [], "gaps": [], "unresolved_questions": [], "blocking_codes": [],
      "total_directos": 1, "total_tentativos": 4, "total_descartados": 2,
      "service_domains": {
        "candidatos_directos": [
          {
            "service_domain": "Party Reference Data Directory", "resolucion": "MATCH",
            "rol_contractual": "OWNED_CONTRACT", "dependency_kind": null,
            "confianza": 0.95, "confianza_pct": 95, "confianza_llm": 0.9, "grupo": "directo",
            "decision_contractual": "SELECTED", "motivo_decision": "OWNED_SELECTED",
            "accion_objeto": "actualizar correo electrónico del cliente",
            "escenarios_hu": ["Escenario 2. Edición del correo electrónico"],
            "business_area": "Sales and Service", "business_domain": "Party Reference Data",
            "rol_bian": "The party reference data directory service domain maintains …",
            "desglose_score": { "accion_oficial": 0.8, "objeto_bom": 0.75, "ownership_outcome": 1.0,
                                "trazabilidad_escenarios": 1.0, "coherencia_jerarquia": 0.3, "penalizacion": -0.05, "total": 0.95 },
            "evidencia_bian": { "estado": "CACHED_VERIFIED", "source_commit_sha": "b58bf4c…", "content_sha256": "…", "source_url": "https://raw.githubusercontent.com/bian-official/public/…" },
            "operaciones_bian": [],
            "bq_personalizados_propuestos": [
              { "nombre_bq": "PreferredContactChannel", "operation_id": "UpdatePreferredContactChannel",
                "verbo": "Update", "path_propuesto": "/PartyReferenceDataDirectory/{id}/PreferredContactChannel/Update",
                "campo_no_cubierto": "canal de contacto preferido", "clase_bom": "ContactPreference",
                "atributo_bom": "preferredChannel", "estado": "CUSTOM_BQ_CANDIDATE" }
            ]
          }
        ],
        "candidatos_tentativos": [ … ],
        "candidatos_descartados": [ … ]
      },
      "service_domains_omitidos": [
        { "service_domain": "Contact/Correspondence Dialogue", "score_lexico": 0.42, "señales": ["notify", "email"], "business_area": "…" }
      ]
    }
  ],
  "service_domains_consolidados": [
    { "service_domain": "Party Reference Data Directory", "decision": "SELECTED", "motivo": "OWNED_SELECTED",
      "contract_role": "OWNED_CONTRACT", "score": 0.95, "historias": ["HU-…txt"], "traceability": ["Escenario 2…"],
      "selected_operations": ["Update"], "custom_bq_candidates": [], "evidence": { "…": "…" } }
  ],
  "service_domains_omitidos": [ { "service_domain": "Contact/Correspondence Dialogue", "score_lexico": 0.42, "…": "…" } ],
  "reconciliacion": { "service_domains": [], "gaps": [], "blocking_codes": [] },
  "huellas_prompts": [ { "prompt_id": "…", "nodo": "evaluar_candidato", "historia": "HU-…txt", "model": "gemini:…", "prompt_sha256": "…" } ],
  "incidencias": [],
  "generado_en": "2026-09-10T…Z"
}
```

`operaciones_bian` (solo SD directos con catálogo local): `{operation_id, method, path, tipo (CR/BQ), grupo, escenarios_hu, justificacion}`.
`bq_personalizados_propuestos` / `custom_bq_candidates`: BQ **no oficiales** anclados a evidencia BOM real (ver [sección dedicada](#bq-personalizados-no-oficiales--cuando-el-bom-respalda-un-campo-sin-cubrir)); nunca cuentan como `selected_operations`.
`service_domains_consolidados` reconcilia el mismo SD entre HU (una lo consume, otra lo posee).
`service_domains_omitidos` = 2º pase léxico sobre los 341 SD (candidatos que el LLM no propuso; no deciden nada, marcan revisión).
`reconciliacion` = salida cruda del asesor de funcionalidad (1 llamada LLM, ve todas las HU ya clasificadas).
`huellas_prompts` = huella reproducible (`prompt_id`/`prompt_sha256`/`model`/`catalog_sha256`/`evidence_snapshot_id`) de cada llamada LLM del run — nunca participa en la decisión, solo auditoría.

Exit code: `0` si al menos una HU obtuvo ≥1 SD (directo/tentativo) · `1` si ninguna · `2` error.

## Tests (no consumen API)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Incluye `test_arquitectura_hexagonal.py`, que **hace cumplir** las fronteras de capa.

## Modelos y reproducibilidad (verificado sept-2026)

- La cadena de failover por defecto (`config.yaml → routing.llm_priority`) es
  **`groq → gemini → huggingface → openrouter`**:
  - Groq (LPU, ~1-2s, free): `openai/gpt-oss-120b`, `openai/gpt-oss-20b`. Structured OK.
    Free tier ~15k tok/min → sirve `validar-sd`, da 413 en `mapear-historias`.
  - Gemini: `gemini-3.6-flash` (free tier **20 req/día**), `gemini-3.5-flash`, `gemini-3.5-flash-lite`.
  - Hugging Face (router de Inference Providers): `deepseek-ai/DeepSeek-V4-Flash`,
    `openai/gpt-oss-120b`, `meta-llama/Llama-3.3-70B-Instruct`. Modelos fuertes pero el free tier
    es un crédito mensual pequeño (~$0.10) → al agotarse da 402 y el failover pasa a OpenRouter.
  - OpenRouter: `nvidia/nemotron-3-super-120b-a12b:free`, `nvidia/nemotron-3.5-lightning:free`,
    `google/gemma-4-31b-it:free`, `openrouter/free`. Lentos con prompts grandes.
  - Retirados en este repo: `gemini-2.x`, `llama-3.x`/`:free` clásicos de OpenRouter.
- Modelos **pinneados** (nunca `-latest`) salvo `openrouter/free` (auto-router, último recurso).
  `llm.temperature: 0`, `llm.seed`, `llm.esfuerzo: low` reducen la varianza; entre modelos
  distintos no hay garantía dura → por eso `validar-sd` mantiene la franja gris estrecha
  (`validar_sd.rag_umbral_*`) y `mapear-historias` ancla todo a la evidencia local.
- El failover clasifica: 429 / 402 / "no disponible" / salida no parseable → **siguiente modelo**;
  503 / timeout / overloaded → **reintento** del mismo modelo (`llm.reintentos_transitorios`,
  `backoff_*`) antes de avanzar; un error real (bug, config) → se propaga.
- RAG por defecto **léxico** → no usa embeddings. `validar_sd.rag_estrategia: vectorial` activa
  el índice vectorial. Cadena de embeddings por **precisión** (`routing.embedding_priority` ×
  `providers.<n>.embedding.models`): **Cohere** free-tier (`embed-v4.0` multilingüe 128k →
  `embed-multilingual-v3.0` → `embed-english-v3.0` → `*-light-v3.0` 384d) → Gemini
  (`gemini-embedding-001`) → OpenRouter (`text-embedding-3-small`). `EmbeddingsConFailover` prueba
  en orden y baja al siguiente si agota cuota (429/402); `EmbeddingsResiliente` reintenta 429/5xx
  dentro de cada modelo. Índice cacheado en `.cache/` por el modelo **activo**. `COHERE_API_KEY`
  = solo embeddings.

## Estructura

```
src/
├── dominio/            modelos · normalizacion · decision_similitud (umbrales)          (puro)
│                       historias · clasificacion_historias (resolución + tope de rol + umbrales)
├── aplicacion/
│   ├── puertos/        entrada · catalogo · recuperador · adjudicador · publicador
│   │                   entrada_mapeo · lector_historias · clasificador_historias · publicador_mapeo
│   │                   catalogo_operaciones_bian · mapeador_operaciones
│   └── servicios/      validar_service_domain.py            (grafo lineal)
│                       mapear_historias_service_domain.py   (outer map-reduce Send-por-HU +
│                                                             subgrafo por HU con Send-por-candidato)
├── adaptadores/
│   │                   embeddings_failover (cadena de embeddings por precisión) · embeddings_resiliente
│   ├── entrada/        cli.py (validar-sd) · cli_mapeo.py (mapear-historias)
│   └── salida/         catalogo_json (SD.json + jerarquía) · recuperador_lexico · recuperador_vectorial
│                       · adjudicador_langchain · publicador_json · embeddings_resiliente
│                       · lector_historias_fs · clasificador_historias_langchain · publicador_mapeo_json
│                       · catalogo_operaciones_bian_json · mapeador_operaciones_langchain
│                       · catalogo_bom_puml (modelo de clases BOM desde docs/bian-puml/)
│                       · prompts · prompts_mapeo
│                       · llm/  gemini · openrouter · anthropic · openai · fake (Strategy)
│                       ·       failover.py  (ChatConFailover: multi-proveedor / multi-modelo)
└── configuracion/      config_yaml (carga config.yaml) · settings (compone .env + config.yaml)
                        · observabilidad (LangSmith) · contenedor (composition root)

config.yaml             proveedores · modelos · orden de failover · umbrales · rutas   (versionado)
.env                    SOLO API keys                                                 (NO versionado)
docs/                   SD.json · bian-business-areas.json · bian-operation-catalogs.json
                        · bian-cache/release14.0.0/ (OpenAPI oficial cache-first, CR+BQ+schemas)
                        · bian-puml/ (272 PlantUML del modelo de clases BOM R14)             (evidencia BIAN local)
```

El subcomando se enruta en `src/__main__.py`: `python -m src mapear-historias …` va a
`cli_mapeo`; cualquier otra invocación mantiene el CLI original `validar-sd`.
