"""Estado del subgrafo que procesa UNA Historia de Usuario.

El outer graph hace fan-out por HU (`Send`) a `procesar_historia`, que invoca este subgrafo.
El subgrafo hace su propio fan-out por candidato (`Send`) al nodo `evaluar_candidato`.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from src.dominio.historias import (
    CandidatoClaseBom,
    CandidatosHistoriaLLM,
    EnrutamientoDominiosLLM,
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
    ServiceDomainPropuestoLLM,
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
    # Routing jerárquico (opcional): `enrutamiento` es lo que dijo el LLM y `catalogo_enrutado` el
    # subconjunto determinista que se le enseña al nodo de candidatos. `catalogo` sigue completo
    # a propósito: `preparar_candidatos` resuelve nombres contra los 341, no contra el recorte.
    enrutamiento: EnrutamientoDominiosLLM
    catalogo_enrutado: list[EntradaCatalogo]
    # Candidatos DETERMINISTAS del nodo 2a: Service Domains que definen en su BOM una clase que
    # la historia necesita (`entidades_bian`). Vacío si el canal está apagado.
    candidatos_por_clase: list[CandidatoClaseBom]
    candidatos: CandidatosHistoriaLLM
    revision_completitud: RevisionCompletitudLLM
    # preparación determinista + fan-out por candidato
    a_evaluar: list[PaqueteEvidenciaCandidato]
    omitidos: list[ServiceDomainOmitido]
    retrieval_scores: dict[str, float]  # clave normalizada; ver _candidatos_retrieval_hibrido
    evaluaciones: Annotated[list[EvaluacionCandidatoLLM], operator.add]
    # clasificación + revisión adversarial deterministas/LLM
    grupos: ServiceDomainsDeHistoria
    propuestos_por_sd: dict[str, ServiceDomainPropuestoLLM]  # clave normalizada; ver _h_clasificar
    revision_adversarial: RevisionAdversarialLLM
    bloqueos_hu: list[str]
    # acumuladores
    incidencias: Annotated[list[dict], operator.add]
    huellas: Annotated[list[MetadatosPrompt], operator.add]
    # salida
    resultado: HistoriaConServiceDomains
