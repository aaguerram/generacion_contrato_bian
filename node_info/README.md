# `node_info/` — cómo funciona cada nodo del pipeline, uno por archivo

Un `.md` por nodo del caso de uso **`mapear-historias`** (Historia de Usuario → BIAN Service
Domains). Cada archivo responde siempre a lo mismo, en este orden:

1. qué hace el nodo y qué **NO** hace;
2. dónde vive en el código (`archivo:línea`);
3. su **contrato de entrada/salida** campo a campo;
4. un **ejemplo real** de entrada y de salida (sacado de una corrida de verdad, no inventado);
5. el **paso a paso** de lo que ocurre en runtime;
6. un **diagrama de flujo Mermaid**;
7. el **prompt exacto** que se manda (si es un nodo LLM);
8. caché, reintentos y failover;
9. modos de fallo;
10. cómo ejecutarlo aislado y verificarlo.

## Estado de esta carpeta

| # | Nodo | Tipo | Archivo | Estado |
|---|------|------|---------|--------|
| 1 | `extraer_intencion` | LLM | [`01-extraer-intencion.md`](01-extraer-intencion.md) | ✅ escrito |
| 2 | `generar_candidatos` | LLM | [`02-generar-candidatos.md`](02-generar-candidatos.md) | ✅ escrito |
| 3 | `revisar_completitud` | LLM | `03-revisar-completitud.md` | ⏳ pendiente |
| 4 | `preparar_candidatos` | determinista | `04-preparar-candidatos.md` | ⏳ pendiente |
| 5 | `evaluar_candidato` | LLM (fan-out) | `05-evaluar-candidato.md` | ⏳ pendiente |
| 6 | `clasificar` | determinista | `06-clasificar.md` | ⏳ pendiente |
| 7 | `revisar_adversarial` | LLM | `07-revisar-adversarial.md` | ⏳ pendiente |
| 8 | `aplicar_adversarial` | determinista | `08-aplicar-adversarial.md` | ⏳ pendiente |
| 9 | `seleccionar_operaciones` | LLM (1 por SD) | `09-seleccionar-operaciones.md` | ⏳ pendiente |
| 10 | `ensamblar` | determinista | `10-ensamblar.md` | ⏳ pendiente |
| 11 | `cargar` / `procesar_historia` / `reconciliar` / `publicar` | outer graph | `11-outer-graph.md` | ⏳ pendiente |

## Los dos grafos

El pipeline son **dos** grafos de LangGraph anidados. El de fuera (*outer*) hace map-reduce
sobre las HU; el de dentro (*subgrafo*) procesa UNA historia y hace su propio fan-out por
candidato.

```mermaid
flowchart TD
    subgraph OUTER["Outer graph — EstadoMapeo — map-reduce sobre las HU"]
        S1(["START"]) --> C1["cargar<br/>lee HU + funcionalidad + catalogo de 341 SD"]
        C1 -->|"Send por cada HU"| P1["procesar_historia HU-1"]
        C1 -->|"Send"| P2["procesar_historia HU-2"]
        C1 -->|"Send"| PN["procesar_historia HU-N"]
        P1 --> R1["reconciliar_funcionalidad<br/>1 sola llamada, ve TODAS las HU<br/>defer=True"]
        P2 --> R1
        PN --> R1
        R1 --> PU["publicar<br/>escribe mapeo-historias-service-domains.json"]
        PU --> E1(["END"])
    end

    P1 -.->|"invoca el subgrafo"| SUB

    subgraph SUB["Subgrafo — EstadoHistoria — UNA historia"]
        S2(["START"]) --> N1["1. extraer_intencion<br/>LLM"]
        N1 --> N2["2. generar_candidatos<br/>LLM"]
        N2 --> N3["3. revisar_completitud<br/>LLM"]
        N3 --> N4["4. preparar_candidatos<br/>DETERMINISTA<br/>resuelve nombres + arma evidencia"]
        N4 -->|"Send por candidato"| N5A["5. evaluar_candidato SD-A<br/>LLM"]
        N4 -->|"Send"| N5B["5. evaluar_candidato SD-B<br/>LLM"]
        N5A --> N6["6. clasificar<br/>DETERMINISTA<br/>score + grupo + decision"]
        N5B --> N6
        N6 --> N7["7. revisar_adversarial<br/>LLM, prompt independiente"]
        N7 --> N8["8. aplicar_adversarial<br/>DETERMINISTA<br/>promueve / degrada"]
        N8 --> N9["9. seleccionar_operaciones<br/>LLM, 1 llamada por SD elegible"]
        N9 --> N10["10. ensamblar<br/>DETERMINISTA"]
        N10 --> E2(["END"])
    end

    classDef llm fill:#fde68a,stroke:#b45309,color:#1f2937
    classDef det fill:#bbf7d0,stroke:#15803d,color:#1f2937
    class N1,N2,N3,N5A,N5B,N7,N9,R1 llm
    class N4,N6,N8,N10,C1,PU det
```

**La regla que gobierna todo el diagrama:** los nodos amarillos (LLM) devuelven *señales*
—listas, rúbricas ordinales 0-3, trazabilidad, gaps—. Los verdes (deterministas) son los que
calculan el score y deciden `SELECTED` / `UNRESOLVED` / `REJECTED`. **El LLM nunca decide el
estado final.**

## Coste por corrida

```
llamadas_LLM ≈ HU * (3 + n_candidatos_evaluados + 2) + 1
                     │                │              │   └─ reconciliar_funcionalidad
                     │                │              └───── adversarial + operaciones
                     │                └──────────────────── nodo 5, una por candidato
                     └───────────────────────────────────── nodos 1, 2 y 3
```

## Convenciones de estos documentos

- **`[det]`** = nodo determinista: mismo input → mismo output, 0 llamadas LLM, 0 red.
- **`[LLM]`** = nodo que invoca el modelo a través de `ChatConFailover`.
- Los ejemplos vienen de `tests/resources/cuentas_menores/mapeo-historias-service-domains.json`
  (corrida real con proveedores reales). Cuando un campo del ejemplo **no** se persiste en el
  JSON de salida y hay que reconstruirlo, el documento lo dice explícitamente.
