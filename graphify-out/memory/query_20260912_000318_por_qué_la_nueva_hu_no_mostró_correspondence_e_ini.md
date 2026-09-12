---
type: "query"
date: "2026-09-12T00:03:18.064736+00:00"
question: "Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1"
contributor: "graphify"
outcome: "useful"
source_nodes: ["clasificar_service_domains()", "calcular_score()", "mapear_historias_service_domain.py", "CatalogoBianCache"]
---

# Q: Por qué la nueva HU no mostró Correspondence e InitiateOutbound y cómo mejorar el pipeline garantizando E2E 1

## Answer

Expanded from original query via graph vocab: [bian, candidato, candidatos, correspondence, correspondencia, historia, mapeo, operation, outbound, retrieval, retrieve, score]. La corrida sí recuperó Correspondence e identificó InitiateOutbound, pero el LLM lo clasificó CONSUMED_DEPENDENCY; la política determinista topó el score, lo dejó bajo el umbral tentativo y el nodo de operaciones sólo procesó candidatos directos. La propuesta separa retrieval, aplicabilidad, ownership y soporte de operación; reinyecta candidatos híbridos antes del fan-out; añade resolución determinista de conflictos de ownership y una E2E 2 aislada, manteniendo E2E 1.

## Outcome

- Signal: useful

## Source Nodes

- clasificar_service_domains()
- calcular_score()
- mapear_historias_service_domain.py
- CatalogoBianCache