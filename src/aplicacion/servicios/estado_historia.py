"""Estado del subgrafo que procesa UNA Historia de Usuario.

El outer graph hace fan-out por HU (`Send`) a `procesar_historia`, que invoca este subgrafo.
El subgrafo hace su propio fan-out por candidato (`Send`) al nodo `evaluar_candidato`.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from src.dominio.historias import (
    CandidatosHistoriaLLM,
    EvaluacionCandidatoLLM,
    FuncionalidadMacro,
    HistoriaConServiceDomains,
    HistoriaUsuario,
    IntencionHistoriaLLM,
    MetadatosPrompt,
    PaqueteEvidenciaCandidato,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
    ServiceDomainOmitido,
    ServiceDomainsDeHistoria,
)
from src.dominio.modelos import EntradaCatalogo


class EstadoHistoria(TypedDict, total=False):
    # entrada (la pasa el outer graph)
    historia: HistoriaUsuario
    funcionalidad: FuncionalidadMacro
    catalogo: list[EntradaCatalogo]
    # nodos LLM
    intencion: IntencionHistoriaLLM
    candidatos: CandidatosHistoriaLLM
    revision_completitud: RevisionCompletitudLLM
    # preparación determinista + fan-out por candidato
    a_evaluar: list[PaqueteEvidenciaCandidato]
    omitidos: list[ServiceDomainOmitido]
    evaluaciones: Annotated[list[EvaluacionCandidatoLLM], operator.add]
    # clasificación + revisión adversarial deterministas/LLM
    grupos: ServiceDomainsDeHistoria
    revision_adversarial: RevisionAdversarialLLM
    bloqueos_hu: list[str]
    # acumuladores
    incidencias: Annotated[list[dict], operator.add]
    huellas: Annotated[list[MetadatosPrompt], operator.add]
    # salida
    resultado: HistoriaConServiceDomains
