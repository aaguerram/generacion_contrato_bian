---
name: corpus-dorado-bian
description: Protocolo para añadir un caso ETIQUETADO al corpus dorado de recuperación BIAN (scripts/evaluate_retrieval/corpus_dorado.yaml) o un caso E2E en tests/resources/. Úsala cuando haya que ampliar el corpus, etiquetar una HU nueva, elegir hard_negatives, o cuando alguien proponga "subir el Recall@K" del benchmark.
---

# Ampliar el corpus dorado BIAN

El cuello de botella de todo el trabajo de recuperación **no es código**: es que solo hay 6
Historias de Usuario etiquetadas. Esta skill fija cómo se añade la séptima sin contaminar la
medición.

## Lo primero: qué NO cuenta como ampliar el corpus

- **Inventar consultas de negocio.** Una consulta escrita por quien ya sabe la respuesta mide lo
  bien que esa persona escribe consultas, no lo bien que recupera el sistema.
- **Usar como consulta el texto que el sistema indexa** (`role_definition`, `examples_of_use`,
  `features`). Es circular: el canal denso y BM25 indexan justo eso, y el resultado sale inflado.
- **Promediar capas distintas.** `hu_real` mide `mapear-historias`; `nombre_canonico` y
  `nombre_deformado` miden `validar-sd`. Un promedio global tapa que una mejora rompió la otra.
- **Subir el número de casos con las capas generadas** (`generar_casos_nombre.py`) y presentarlo
  como "ya tenemos ~100 consultas". Esas capas son regresión objetiva, no poder estadístico sobre
  el problema de negocio.

## Añadir un caso `hu_real` (el único que justifica cambiar un default)

1. **Parte de una HU real** del banco: `HU/`, `HU - copia/` o un archivo que traiga el usuario.
   Nunca un enunciado redactado para el benchmark.
2. **El positivo se confirma con evidencia, no de memoria.** Vale como confirmación cualquiera de:
   - una corrida real ya validada con el humano (`salida/<fecha>/mapeo-historias-service-domains.json`),
   - un `expected-result.json` curado en `tests/resources/<caso>/`,
   - el Service Landscape + la Semantic API del SD (`docs/bian-cache/release14.0.0/<SD>.json`):
     el SD tiene que ser **propietario** del objeto de negocio de la historia (`OWNED_CONTRACT`),
     no una dependencia que la historia consume. Si la historia solo *notifica* que algo pasó, el
     propietario es el SD de la notificación, no el del dato que cambió.
3. **`consulta`**: el enunciado de la historia en el vocabulario del usuario (español, como
   llega). No lo traduzcas ni le metas términos BIAN: el puente ES->EN es responsabilidad del
   sistema (`src/dominio/vocabulario_bian.py`), y si lo haces tú mides el puente dos veces.
4. **`hard_negatives`**: los candidatos que **el pipeline propuso de verdad** y no son la
   respuesta — salen de `candidatos_descartados`/`candidatos_tentativos` de una corrida real. No
   inventes negativos "plausibles a ojo": los que duelen son los que ya compitieron.
5. **`procedencia`**: la ruta exacta del archivo o corrida que sostiene el caso. Un caso sin
   procedencia verificable no entra.
6. Corre el benchmark **por capa** y comprueba que no rompiste la otra:
   ```bash
   .venv/bin/python scripts/evaluate_retrieval/evaluate.py --tipo hu_real
   .venv/bin/python scripts/evaluate_retrieval/evaluate.py --tipo nombre_canonico
   ```

## Regenerar las capas objetivas

```bash
.venv/bin/python scripts/evaluate_retrieval/generar_casos_nombre.py            # ver
.venv/bin/python scripts/evaluate_retrieval/generar_casos_nombre.py --escribir # aplicar
```

Es idempotente y **solo** reemplaza los casos cuya `procedencia` lleva su marca: los casos
manuales no se tocan nunca.

## Si además hay que fijar el caso como regresión E2E

Sigue `tests/e2e/README.md`: carpeta propia en `tests/resources/<caso>/` con la HU, **un**
`funcionalidad-*.json` y un `expected-result.json` curado a mano (una corrida real ya validada).
Prohibido hardcodear nombres de Service Domain u operaciones en el `.py` del test, y prohibido
apuntar a `./HU` o `./ejemplos` de la raíz (cambian de contenido y ya rompieron una E2E).

## Qué mirar al terminar

El benchmark mide **recuperación**, no acierto. Un Recall@10 de 1.0 es compatible con una corrida
que termina en `UNRESOLVED` — pasó el 2026-09-14. Antes de declarar una mejora, contrasta con
`ownership_conflict_rate` y `operation_grounding_rate` de una corrida real (`canary.py`).
