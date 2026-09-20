# evaluate_retrieval

Mide la **recuperación** de Service Domains sobre un corpus dorado, sin llamadas LLM, y compara
dos configuraciones del pipeline completo (canary).

```bash
.venv/bin/python scripts/evaluate_retrieval/evaluate.py
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --canales lexico,vectorial,qdrant
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --tipo hu_real --canales rrf-bm25,bom-rrf,rrf-bm25+bom-rrf
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --json salida/retrieval.json

.venv/bin/python scripts/evaluate_retrieval/canary.py --hu ./HU \
    --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json \
    --base config.yaml --candidata otra-config.yaml --proveedor ollama
```

## El corpus tiene capas, y NO se promedian

| capa | n | qué mide | se puede ampliar |
|---|---|---|---|
| `hu_real` | 6 | Historia de Usuario real -> su Service Domain propietario (`mapear-historias`) | solo con etiquetado humano (skill `corpus-dorado-bian`) |
| `nombre_canonico` | 61 | la consulta ES el nombre exacto (`validar-sd`) | sí, generado |
| `nombre_deformado` | 30 | el nombre con una deformación declarada (abreviatura, letra menos) | sí, generado |

Las dos capas de nombre las genera `generar_casos_nombre.py` (determinista e idempotente; nunca
toca los casos manuales). **No son poder estadístico sobre el problema de negocio**: son la
regresión objetiva de `validar-sd` y el control de que mejorar un caso de uso no rompa el otro.

Por qué importa la separación, con los números en la mano: el canal léxico por nombre mide
**Recall@10 0.95 global** y **0.17 en `hu_real`**. Promediar las capas convertiría el peor canal
para mapear historias en el mejor del informe.

## Resultados actuales (97 consultas, 341 SD, `qwen3-embedding:8b`, 2026-09-14)

`hu_real` (n=6) — el caso de uso `mapear-historias`:

| canal | R@1 | R@5 | R@10 | MRR |
|---|---|---|---|---|
| léxico (rapidfuzz, por nombre) | 0.00 | 0.17 | 0.17 | 0.083 |
| BM25 (por texto, con puente ES->EN) | 0.17 | 0.33 | 0.50 | 0.281 |
| vectorial en memoria | 0.17 | 0.67 | **0.83** | 0.342 |
| RRF (léxico + vectorial) | 0.17 | 0.33 | 0.67 | 0.265 |
| **RRF (BM25 + vectorial)** | **0.50** | 0.67 | 0.67 | **0.573** |

`nombre_canonico` (n=61) y `nombre_deformado` (n=30) — el caso de uso `validar-sd`:

| canal | MRR canónico | MRR deformado |
|---|---|---|
| **léxico (rapidfuzz)** | **1.000** | **0.945** |
| BM25 | 0.965 | 0.636 |
| vectorial | 0.913 | 0.687 |
| RRF (léxico + vectorial) | 0.989 | 0.889 |
| RRF (BM25 + vectorial) | 0.975 | 0.790 |

### Lo que estos números dicen

1. **El canal léxico no fallaba por falta de pesos: fallaba por idioma.** Las HU están en español
   y el catálogo BIAN entero en inglés, así que la consulta y el corpus no compartían ni un
   término. Con el puente ES->EN (`src/dominio/vocabulario_bian.py`), el canal disperso pasa de
   0.083 a 0.281 de MRR en `hu_real`, y fusionado con el denso llega a 0.573 — **más que el mejor
   canal individual** (vectorial, 0.342), que es lo que la fusión prometía y no cumplía.
2. **Cada caso de uso quiere su canal disperso.** rapidfuzz (comparar NOMBRES) es intocable para
   `validar-sd`: 1.000 de MRR en nombres exactos y 0.945 con deformaciones, donde BM25 se hunde a
   0.636 —una errata no cambia los términos, cambia las letras—. BM25 (comparar TEXTO) es el de
   `mapear-historias`. Un solo canal "léxico" para los dos casos era el error de fondo.
3. **La fusión es un intercambio, no una mejora libre:** RRF+BM25 gana en la cabeza del ranking
   (R@1 0.50 vs 0.17) y pierde en profundidad (R@10 0.67 vs 0.83). Cuál importa depende de qué
   hace el pipeline después — y aquí cada candidato de más cuesta una llamada LLM, así que la
   cabeza del ranking vale más que la cola.
4. **Qdrant sigue sin comprar calidad** a esta escala -> `docs/adr/0001-vector-store.md`.
5. **El reranker cross-encoder pasó de rescate a lastre.** Su número bueno (R@10 0.71 -> 0.86)
   se midió contra la fusión ROTA, donde había mucho que rescatar. Re-medido sobre `hu_real` con
   el canal disperso ya arreglado (`BAAI/bge-reranker-v2-m3` en GPU):

   | canal | R@1 | R@5 | R@10 | MRR | negativos delante |
   |---|---|---|---|---|---|
   | `rrf-bm25` | **0.50** | **0.67** | 0.67 | **0.573** | **1** |
   | `rrf-bm25+rerank` | 0.17 | 0.33 | **0.83** | 0.300 | 4 |
   | `rrf+graph+rerank` | 0.17 | 0.33 | **0.83** | 0.311 | 4 |

   Recupera profundidad (R@10 0.67 -> 0.83) y **destroza la cabeza**: R@1 0.50 -> 0.17, MRR
   0.573 -> 0.300, y cuadruplica los `hard_negatives` por delante del positivo (1 -> 4). En este
   pipeline cada candidato por delante es una llamada LLM con ~16k tokens de evidencia, así que
   la cabeza vale más que la cola: **el reranker sigue sin justificarse**. Se ve en un caso
   suelto: para "notificar al cliente por correo y SMS...", BM25 pone `Correspondence` en el
   puesto 1 y el cross-encoder lo baja al 5, con todos los scores en ~0.003.

   **¿Y si el problema era el texto?** Se probó: `--barrido-texto` mide las 10 variantes de
   `EntradaCatalogo.texto_prosa()` sobre `hu_real`, con el mismo canal y el mismo modelo.

   | texto que lee el cross-encoder | chars | R@1 | R@5 | R@10 | MRR | neg. delante |
   |---|---|---|---|---|---|---|
   | *(sin reranker: `rrf-bm25`)* | — | **0.50** | **0.67** | 0.67 | **0.573** | **1** |
   | `indice` (el que se usaba) | 1093 | 0.17 | 0.33 | **0.83** | 0.300 | 4 |
   | `rol` | 333 | 0.17 | 0.33 | 0.67 | 0.265 | 2 |
   | `nombre_rol` | 357 | 0.17 | 0.33 | 0.67 | 0.320 | 2 |
   | `resumen` | 129 | 0.00 | 0.17 | 0.33 | 0.108 | 3 |
   | `ejemplos` | 159 | 0.17 | 0.17 | 0.33 | 0.238 | 3 |
   | `features` | 158 | 0.00 | 0.33 | 0.67 | 0.141 | 4 |
   | **`prosa`** (nombre + rol + ejemplo + resumen) | 644 | **0.33** | **0.50** | 0.50 | **0.417** | **2** |
   | `prosa_features` | 799 | 0.17 | 0.33 | 0.83 | 0.297 | 3 |
   | `documentacion` | 891 | 0.17 | 0.33 | 0.67 | 0.285 | 3 |
   | `documentacion_limpia` | 880 | 0.17 | 0.33 | 0.83 | 0.299 | 3 |

   El diagnóstico era correcto y **no basta**: darle prosa sube el MRR un 39% (0.300 -> 0.417) y
   le quita la mitad de los `hard_negatives` (4 -> 2) respecto al volcado del índice, así que sí,
   el texto importaba. Pero **ninguna variante alcanza a no reordenar** (0.573 / 1 negativo). Hay
   además una forma clara en los datos: los textos cortos (`resumen` 129 chars, `ejemplos` 159)
   son los peores —el modelo se queda sin contexto para juzgar— y pasar de ~650 chars tampoco
   ayuda; el óptimo es prosa de longitud media. El pipeline pasa `prosa` cuando se reordena, para
   que encender el flag no reparta además el peor texto, pero el flag sigue en `false`.

### Canal de propiedad de clases BOM (`bom-*`, nodo 2a) — 2026-09-20

Los canales de arriba recuperan el Service Domain por su **texto**. Los `bom-*` llegan por otro
camino: la consulta recupera **clases** de `docs/entity.json` (1.190 clases con dueño, excluidas
las 40 cajas del metamodelo `X_SD_Operations`/`X_Instantiation`/...) y el SD sale de **quién la
define** (la ocurrencia sin `notes.Extensible`). Paso 1 = recuperación (diccionario ES->EN,
BM25 sobre el documento de la clase, embeddings `qwen3-embedding:8b` sobre la HU en español, o su
fusión RRF k=20 sobre top-12 clases); pasos 2-4 = propiedad + Behavior Qualifier + nota del enum,
siempre iguales. `hu_real` (n=6):

| canal | paso 1 | R@1 | R@5 | R@10 | MRR | neg. delante |
|---|---|---|---|---|---|---|
| `rrf-bm25` *(referencia: texto del SD)* | — | **0.50** | 0.67 | 0.67 | 0.573 | 1 |
| `bom-dic` | diccionario | 0.17 | 0.83 | 0.83 | 0.372 | 3 |
| `bom-bm25` | BM25 clases | 0.17 | 0.50 | 0.83 | 0.378 | 3 |
| `bom-vec` | embeddings clases | 0.17 | 0.83 | 0.83 | 0.339 | 1 |
| **`bom-rrf`** | BM25 + embeddings | **0.50** | 0.67 | **1.00** | 0.569 | 1 |
| `bom-rrf3` | diccionario + BM25 + embeddings | 0.33 | 0.83 | 0.83 | 0.517 | 1 |
| `bm25+bom` *(sin embeddings)* | SD-BM25 ⊕ (dic + BM25 clases) | 0.17 | 0.67 | 1.00 | 0.376 | 2 |
| `rrf-bm25+bom` | SD-texto ⊕ `bom-rrf3` | 0.33 | **1.00** | **1.00** | 0.547 | 1 |
| **`rrf-bm25+bom-rrf`** | SD-texto ⊕ `bom-rrf` | **0.50** | 0.67 | **1.00** | **0.639** | 1 |

Posición del positivo por consulta (`crear-pantalla · notificar · actualizar-correo ·
actualizar-celular · smart-token · cuentas-menores`):

| canal | posiciones |
|---|---|
| `rrf-bm25` | 1 · 1 · **29** · **14** · 1 · 3 |
| `bom-dic` | 5 · **0** · 5 · 3 · 1 · 2 |
| `bom-vec` | 4 · 4 · 5 · **0** · 1 · 3 |
| `bom-rrf` | 1 · 5 · 9 · 10 · 1 · 1 |
| `rrf-bm25+bom-rrf` | 1 · 1 · 6 · 6 · 1 · 2 |

Lo que dicen:

1. **El canal de propiedad recupera lo que el texto del SD no.** Las dos HU de "actualizar
   correo/celular" están en los puestos 29 y 14 por texto y en 5-10 por propiedad: la HU nombra
   el DATO (`Electronic Address`, `MobileNumber`, valores de enum de `Contact Point`), no el
   rol del SD. Fusionados, todo positivo queda en top-6 y el MRR sube de 0.573 a 0.639.
2. **Es ciego al eje de la acción, como se predijo, pero menos de lo previsto.** El diccionario
   y BM25 no encuentran `Correspondence` para "notificar..." (posición 0): su evidencia es la
   operación `InitiateOutbound`, no una clase. El canal vectorial sí llega (puesto 4) por la
   clase `Correspondence Management Function`, cuya definición habla de "outbound correspondence".
3. **El diccionario resta en la fusión.** Solo, es el mejor en R@5 (0.83); fusionado con los
   otros dos baja el MRR de 0.569 a 0.517: mete `Party` por "cliente" en TODAS las HU y aplana
   el ranking. Por eso el default de `entidades_canales` es `[bm25, vectorial]`.
4. **Los artefactos del metamodelo eran la mitad del ruido del canal denso.** Antes de excluir
   `X_SD_Operations`/`X_Instantiation`/`X_Invocation`/`X_Reporting`/`X_ Analytics Object` (40
   clases con dueño, cero atributos, cero descripción), `bom-vec` ponía `Customer Consent` #1 en
   "actualizar celular" por cuatro cajas `Customer Mandate Agreement_*`; `bom-rrf` pasó de MRR
   0.489 a 0.569 solo con ese filtro.
5. **Para el nodo 2a lo que importa es el tope, no el MRR.** El canal AÑADE propietarios al
   catálogo enrutado; con `entidades_max_candidatos: 10` los 6 positivos entran (con 5, cuatro).
   Cada SD añadido cuesta ~189 tokens en 2b.

Aviso estadístico de siempre: seis consultas; un acierto mueve 0.17 de recall. La FORMA
(propiedad complementa a texto; diccionario estorba en fusión; metamodelo fuera) es robusta; los
decimales no.

### Barrido de `k` y pesos

```bash
.venv/bin/python scripts/evaluate_retrieval/evaluate.py --barrido rrf-bm25 --tipo hu_real
```

Medido sobre `hu_real` (n=6):

| k | peso disperso | R@5 | R@10 | MRR | negativos delante |
|---|---|---|---|---|---|
| 10-60 | 0.00 (solo denso) | 0.67 | **0.83** | 0.342 | 2 |
| 10 | 0.25 | 0.67 | 0.67 | 0.581 | 1 |
| **20** | **0.25** | 0.67 | 0.67 | **0.608** | **1** |
| 60 | 0.25 | 0.67 | 0.67 | 0.608 | 1 |
| 10-60 | 1.00 | 0.67 | 0.67 | 0.573 | 1 |

`k` (10/20/60) apenas mueve nada; el peso del canal disperso sí, y siempre en la misma dirección:
más MRR y un `hard_negative` menos por delante, a cambio de un positivo que se cae del top-10. **Con 6 consultas de negocio, un
acierto mueve 0.17 de recall**: la rejilla sirve para ver la forma de la superficie, no para fijar
un default. Por eso los valores por defecto siguen siendo los de siempre (`rapidfuzz`, pesos 1.0,
`k=60`) y el híbrido sigue OFF: cambiar un default exige el canary con LLM real.

## Lo que este benchmark NO mide

Que el pipeline acierte. Recall@10 puede ser 1.0 y la corrida terminar en `UNRESOLVED`: es lo que
pasó el 2026-09-14, con el SD correcto recuperado siempre como top-1 y bloqueado después por el
revisor adversarial. **El gate "Recall@10 ≥ 0.95" se aprueba solo y no basta**: hay que mirar
`ownership_conflict_rate` y `operation_grounding_rate` de una corrida real, que es justo lo que
compara `canary.py`.

## Sobre el tamaño del corpus

El corpus tiene 97 casos y **sigue teniendo 6 consultas de negocio**. Las 91 restantes son las dos
capas de nombre, objetivas y generadas. Para comparar modelos de embeddings o justificar un
default de `mapear-historias` hacen falta del orden de 100 consultas **de la capa `hu_real`**, y
esas solo salen de etiquetar HU reales: el protocolo está en la skill `corpus-dorado-bian`.
Rellenar el corpus con consultas de negocio inventadas no daría poder estadístico, daría ruido con
aspecto de dato.

Cada caso declara su `procedencia` y sus `hard_negatives` salen de candidatos que el pipeline
propuso de verdad (o, en las capas generadas, de los nombres más parecidos del propio catálogo).


## Nota de entorno: caché de HuggingFace

En este host `~/.cache/huggingface` pertenece a **root** (la creó algún proceso con sudo), así que
el cross-encoder no puede descargarse con el usuario normal y el reranker degrada a "no reordenar"
con un aviso en el log. Solución sin root: apuntar la caché a una ruta propia.

```bash
export HF_HOME=~/.cache/hf-local
```
