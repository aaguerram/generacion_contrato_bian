# Arquitectura hexagonal — reglas

`src/` = puertos y adaptadores. El núcleo (dominio + aplicación) no conoce LangChain,
Gemini, InMemoryVectorStore ni el formato de salida.

## Regla (se verifica en CI)

> **Ningún módulo importa fuera de lo permitido para su capa.**
> La hace cumplir [`tests/test_arquitectura_hexagonal.py`](tests/test_arquitectura_hexagonal.py)
> (análisis estático con `ast`). Si falla, el cambio no se acepta.

| Capa (`src/…`) | Puede importar | Nunca |
|---|---|---|
| `dominio/` | stdlib · `pydantic` | aplicación, adaptadores, configuración, frameworks |
| `aplicacion/` | + `src.aplicacion` · `langgraph` | `src.adaptadores`, `src.configuracion`, `langchain*`, SDKs |
| `adaptadores/` | `src.dominio` · `src.aplicacion` · `src.adaptadores` · `src.configuracion` · libs externas | — |
| `configuracion/` | `src.dominio` · `src.aplicacion` · `src.adaptadores.salida` · externas | `src.adaptadores.entrada` |

`langgraph` está permitido en `aplicacion/` (motor de orquestación).
`langchain*`, `langchain-google-genai`, `rapidfuzz`, `numpy` → solo `adaptadores/salida/`.
`langsmith` → solo `configuracion/`.

## Puertos y adaptadores

| Puerto (`aplicacion/puertos`) | Adaptador (`adaptadores/salida`) | Tecnología |
|---|---|---|
| `ValidarServiceDomainUseCase` (driving) | `aplicacion/servicios/ValidarServiceDomainService` | grafo LangGraph |
| `CatalogoServiceDomainsPort` | `CatalogoJson` | lee `SD.json`, índice exacto normalizado |
| `RecuperadorSemanticoPort` (RAG) | `RecuperadorLexico` (default) · `RecuperadorVectorial` | `rapidfuzz` sobre nombres · o `InMemoryVectorStore` + embeddings (`RAG_ESTRATEGIA`) |
| `AdjudicadorLLMPort` | `AdjudicadorLangChain` | prompt + `with_structured_output(VeredictoLLM)` |
| `PublicadorResultadoPort` | `PublicadorJson` | escribe el JSON en `--directorio` |

El proveedor LLM está detrás de otro patrón (Strategy) dentro del adaptador:
`adaptadores/salida/llm/` — `ProveedorLLMStrategy` da `crear_chat_model()` + `crear_embeddings()`;
`gemini.py` / `anthropic.py` / `openai.py` / `fake.py`; `factory.py` los registra.

## El grafo (`aplicacion/servicios/validar_service_domain.py`)

```
START -> coincidencia_exacta --(existe?)------------------> publicar -> END
                              \--(no)--> recuperar --(banda)--┬ alta/baja -> resolver_umbral -> publicar
                                                              └ gris      -> adjudicar (LLM)  -> publicar
```

- `coincidencia_exacta`, la regla de bandas (`dominio/decision_similitud.py`) y `resolver_umbral`
  son **deterministas, sin LLM**.
- Solo la banda **gris** llega a `adjudicar` (LLM). Con RAG léxico, ese es el único punto que
  toca la API, y solo para consultas ambiguas.
- `recuperar` y `adjudicar` llaman a **puertos**; el grafo no sabe qué RAG ni qué proveedor hay detrás.
- `adjudicar` tiene `RetryPolicy` (429/5xx). Con RAG vectorial, `EmbeddingsResiliente` reintenta
  y cachea el índice, así que `recuperar` no se reintenta entero.

## Umbrales (`RAG_UMBRAL_ALTO` / `RAG_UMBRAL_BAJO`)

`similitud_nombre` = `token_sort_ratio(consulta, nombre_candidato)` — estricta (penaliza palabras
que faltan), distinta del `score` de recuperación (`WRatio`, permisivo). La banda se calcula con
la MAYOR `similitud_nombre` del shortlist:

| `similitud_nombre` (máx) | banda | resultado |
|---|---|---|
| ≥ `alto` (0.90) | alta | `existe=true` · `metodo=similitud_alta` · sin LLM |
| < `bajo` (0.60) | baja | `existe=false` · `metodo=similitud_baja` · sin LLM |
| entre ambos | gris | lo decide el LLM · `metodo=rag_llm` |

Subir `bajo` / bajar `alto` = delegar más al LLM. `alto=1.0, bajo=0.0` = todo al LLM.

## Cómo cambiar cosas sin romper la regla

| Quiero… | Toco… |
|---|---|
| otro proveedor LLM | nueva `XStrategy(ProveedorLLMStrategy)` + `registrar_estrategia` |
| otra fuente de catálogo (BD, API) | nuevo adaptador de `CatalogoServiceDomainsPort` + cablearlo en `contenedor.py` |
| otro motor RAG (FAISS, Chroma, pgvector) | nuevo adaptador de `RecuperadorSemanticoPort` |
| otra salida (BD, evento, stdout) | nuevo adaptador de `PublicadorResultadoPort` |
| regla de negocio nueva | `dominio/` |
| otra entrada (HTTP, cola) | `adaptadores/entrada/` llamando a `ValidarServiceDomainUseCase` |
| nuevos nodos del pipeline | `aplicacion/servicios/` — solo puertos |

Antes de terminar cualquier cambio en `src/`:

```bash
.venv/Scripts/python -m unittest discover -s tests
```
