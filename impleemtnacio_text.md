

en tu analisa y detecta mejora de promts y dle proceso de langgraph en el pipeline del generador_contrato_iz_v2 en base a los skill, agents, instructions, promtes y copilot-instructions.md y promt_maestro_target_architectura_smart_token_v9.md que se pueda utilizar para mejroa la ejecucion de los nodos en langgraph que usan llm

ya se implementaronlas siguientes mejroas peor si hay algo me mejorar has todos los cambios que se necesiten. aplica las ulitmas y mejores tecnicas de promt engeniering del a industria y de lso estandares.

Primeras mejoras detectadas a confirmar si son correctas:
mejoras importantes de prompting que no quedaron incorporadas en el análisis anterior. La implementación actual reforzó caché, evidencia y scoring, pero la arquitectura de los nodos LLM continúa demasiado concentrada en un único prompt.

Las brechas principales son estas:

1. Separar extracción, descubrimiento y evaluación

El nodo actual mezcla en una sola llamada:

- Interpretación de la historia.
- Extracción de acciones y objetos.
- Selección de candidatos BIAN.
- Clasificación contractual.
- Confianza.
- Revisión adversarial.

Esto aparece en [prompts_mapeo.py](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/generacion_contrato_ia_v2/src/adaptadores/salida/prompts_mapeo.py:18).

Conviene dividirlo en nodos LLM especializados:

```text
extract_intent
    ↓
generate_candidates
    ↓
evaluate_candidate (uno por SD)
    ↓
review_completeness
    ↓
select_operations
    ↓
reconcile_functionality
```

Así cada candidato se evalúa contra evidencia oficial concreta, en lugar de comparar simultáneamente contra un catálogo resumido de cientos de Service Domains.

2. La propuesta inicial del LLM no puede considerarse exhaustiva

El prompt maestro v9 establece explícitamente que la lista inicial del LLM no demuestra completitud y exige un gate adicional ([PROMPT_MAESTRO_TARGET_ARCHITECTURE_SMART_TOKEN_V9.md](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/PROMPT_MAESTRO_TARGET_ARCHITECTURE_SMART_TOKEN_V9.md:104)).

El prompt actual pide normalmente entre 3 y 8 candidatos. Eso puede excluir un SD razonable antes de evaluarlo.

Debe agregarse un nodo `review_completeness` que reciba:

- Intención funcional normalizada.
- Acciones y objetos.
- Candidatos propuestos.
- Índice BIAN global.
- Evidencia disponible de cada candidato.

Y devuelva:

- `missing_candidates`
- `unsupported_candidates`
- `ownership_conflicts`
- `duplicated_responsibilities`
- `coverage_gaps`
- `blocking_codes`

El índice global debe servir como pista; la confirmación debe realizarse con el catálogo oficial en caché.

3. Evaluación individual con evidencia oficial

El prompt actual usa principalmente el `Service Role` resumido del catálogo. Cada evaluación debería recibir un paquete cerrado por candidato:

```yaml
candidate:
  service_domain:
  business_area:
  service_role:
  control_record:
  behavior_qualifiers:
  operations:
  schemas:
  source_url:
  source_commit:
  content_sha256:
  retrieved_at:
```

El LLM debe evaluar únicamente ese candidato y devolver:

```yaml
status: DIRECTO | TENTATIVO | DESCARTADO | NO_RESUELTO
contract_role: OWNED_CONTRACT | CONSUMED_DEPENDENCY | RELATED
match_action:
match_business_object:
match_service_role:
evidence_refs:
reason_codes:
assumptions:
gaps:
```

Eso convierte la respuesta en una evaluación auditable y reduce alucinaciones.

4. Trazabilidad diferente para ownership y dependencia

Los agentes exigen que un SD directo tenga `ownership_traceability`, mientras que una dependencia debe usar `dependency_traceability` y `dependency_kind` ([01-bian-business-alignment.agent.md](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/.github/agents/01-bian-business-alignment.agent.md:117)).

El prompt actual solo devuelve fragmentos de escenarios. Debe obligar a usar identificadores:

```yaml
ownership_traceability:
  - HU-001/SC-03
  - BR-012

dependency_traceability:
  - HU-001/SC-05

dependency_kind: authorization | validation | notification | data_lookup
```

Nunca debe reutilizarse evidencia de dependencia para demostrar ownership.

5. La confianza final no debe decidirla el LLM

Actualmente el LLM devuelve `confianza` y el consolidado selecciona el resultado con mayor valor en [mapear_historias_service_domain.py](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/generacion_contrato_ia_v2/src/aplicacion/servicios/mapear_historias_service_domain.py:289).

Eso permite que una cifra subjetiva del modelo domine la decisión. El prompt debería devolver señales ordinales:

```yaml
match_action: 0..3
match_business_object: 0..3
match_service_role: 0..3
evidence_quality: 0..3
ambiguity: NONE | LOW | HIGH
```

La aplicación calcula determinísticamente:

- Score.
- Confianza.
- Clasificación directo/tentativo/descartado.
- Bloqueo por evidencia insuficiente.

El skill además exige que los resultados de baja confianza queden sin resolver, no que se acepten silenciosamente ([SKILL.md](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/.github/skills/bian-service-domain-evaluator/SKILL.md:123)).

6. Supuestos y gaps explícitos

Las instrucciones Copilot dicen:

- Escribir supuestos explícitamente.
- Cuando falta evidencia, registrar un gap.
- No inventar información.

Esto está en [.github/copilot-instructions.md](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/.github/copilot-instructions.md:26).

Todos los nodos deberían poder devolver:

```yaml
assumptions: []
gaps: []
unresolved_questions: []
blocking_codes: []
```

Si falta Service Role, operación o catálogo oficial, la salida correcta es `NO_RESUELTO`, no una clasificación aproximada.

7. Revisión adversarial independiente

La revisión actual se solicita dentro de la misma llamada que produjo la decisión. El mismo modelo termina validando su propia hipótesis.

Debe existir un nodo posterior con un prompt diferente que revise:

- Acciones directas clasificadas como dependencia.
- Objetos funcionales sin SD propietario.
- SD directos sin Service Role compatible.
- Dependencias promovidas a contratos propios.
- Candidatos omitidos.
- Cantidad excesiva de contratos.

Si una clasificación `CONSUMED_DEPENDENCY` contradice la acción y objeto directos, debe emitir `BIAN-SCOPE-002`, como ordena el prompt maestro ([PROMPT_MAESTRO_TARGET_ARCHITECTURE_SMART_TOKEN_V9.md](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/PROMPT_MAESTRO_TARGET_ARCHITECTURE_SMART_TOKEN_V9.md:121)).

8. Mejorar el prompt de selección de operaciones

El segundo prompt actualmente solo pide seleccionar `operationId` existentes ([prompts_mapeo.py](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/generacion_contrato_ia_v2/src/adaptadores/salida/prompts_mapeo.py:140)).

Debe incorporar:

- Coincidencia entre acción, objeto y Service Role.
- `operationId` literal.
- Trazabilidad de cada operación a HU/escenario/regla.
- Conjunto mínimo suficiente.
- Prohibición de seleccionar el catálogo completo.
- Un fragmento BQ por semilla, sin combinaciones cartesianas.
- `BIAN-SCOPE-008` cuando una semilla BQ no queda cubierta.
- Gap explícito si ninguna operación es inequívoca.
- Separación entre wrapper técnico del Control Record y objeto funcional.

9. Reconciliación a nivel de funcionalidad

La decisión no puede cerrarse únicamente historia por historia. Un SD puede parecer dependencia en una HU, pero quedar demostrado como propiedad directa en otra.

Se necesita un nodo final que vea todas las historias y consolide:

```yaml
service_domain:
functionality_role:
supporting_stories:
contradicting_stories:
final_status:
decision_reason:
```

La decisión final debe basarse en el conjunto completo, no simplemente en escoger la asignación con mayor `confianza`.

10. Eliminar reglas específicas de Smart Token de prompts productivos

El prompt actual contiene ejemplos y reglas específicas de Smart Token/OTP ([prompts_mapeo.py](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/generacion_contrato_ia_v2/src/adaptadores/salida/prompts_mapeo.py:46)).

Esto contradice la invariante del agente que prohíbe hardcodear funcionalidades o Service Domains en reglas productivas ([01-bian-business-alignment.agent.md](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/.github/agents/01-bian-business-alignment.agent.md:87)).

Los ejemplos específicos deben vivir en tests de regresión. El prompt productivo debe usar formulaciones genéricas.

11. Sustituir “razonamiento paso a paso”

El adjudicador solicita explícitamente “razonamiento paso a paso” en [prompts.py](/C:/Users/TL/Documents/Copia_Documentos/produbanco/NEW-VERSION-poc-bian-spec-feature-valdiacion/generacion_contrato_ia_v2/src/adaptadores/salida/prompts.py:32).

Es preferible solicitar una justificación breve y verificable:

```yaml
decision:
evidence:
counter_evidence:
reason_codes:
```

Esto reduce tokens, evita razonamientos extensos difíciles de auditar y hace que la salida sea más estable.

12. Versionado y reproducibilidad de prompts

Cada ejecución debería persistir:

```yaml
prompt_id:
prompt_version:
prompt_sha256:
model:
temperature:
catalog_sha256:
evidence_snapshot_id:
```

Así se puede reproducir por qué dos ejecuciones produjeron resultados diferentes.

En conclusión: la implementación anterior quedó incompleta en la parte de prompting. Las mejoras más importantes no consisten solo en reescribir el texto del prompt, sino en reemplazar el nodo monolítico por extracción → candidatos → evaluación individual → revisión adversarial → operaciones → reconciliación, dejando scoring, thresholds y gates finales en código determinista.