"""Modelos del dominio."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Tope del texto indexado por Service Domain. Con 1200 chars entra el 100% de nombre + jerarquía
# + clasificación + rol + ejemplo de uso + features (la parte con vocabulario de negocio) en los
# 341 SD, y se recorta solo la cola de `documentation`, que repite el rol.
_MAX_CHARS_INDICE = 1200

MetodoValidacion = Literal[
    "coincidencia_exacta",  # el nombre está en el Landscape salvo forma  (determinista, existe=True)
    "similitud_alta",  # similitud léxica del nombre >= umbral alto   (determinista, existe=True)
    "similitud_baja",  # similitud léxica del nombre <  umbral bajo   (determinista, existe=False)
    "rag_llm",  # franja gris: lo decidió el LLM adjudicador   (existe True o False)
]


class EntradaCatalogo(BaseModel):
    """Un BIAN Service Domain leído del Service Landscape (fuente única, 341 SD).

    `CatalogoJson` lo carga de `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`, que ya trae
    textos, clasificación funcional y la jerarquía `business_area` / `business_domain`.
    """

    service_domain: str
    service_role: str | None = None
    examples_of_use: str | None = None
    executive_summary: str | None = None
    features: str | None = None
    functional_pattern: str | None = None
    asset_type: str | None = None
    generic_artifact_type: str | None = None
    control_record: str | None = None
    registration_status: str | None = None
    business_area: str | None = None
    business_domain: str | None = None
    documentation: str | None = None

    def texto_para_indexar(self, *, max_chars: int = _MAX_CHARS_INDICE) -> str:
        """Texto del SD para el índice semántico.

        Incluye TODO lo que el Service Landscape dice del Service Domain, no solo su nombre y su
        rol: una historia de usuario rara vez repite el rol formal, pero sí menciona el escenario
        (`examples_of_use`) o una capacidad concreta (`features`). Indexar solo nombre +
        clasificación + rol dejaba fuera la mitad del vocabulario con el que la historia habla.

        El orden va de lo más discriminante a lo más redundante, porque el recorte se aplica al
        final: nombre, jerarquía y clasificación (términos cortos y únicos), rol, ejemplo de uso,
        features, resumen ejecutivo y, si queda sitio, la documentación -que repite el rol al
        principio, así que es la primera en sobrar-.
        """
        clasif = " / ".join(
            p for p in (self.functional_pattern, self.asset_type, self.generic_artifact_type) if p
        )
        jerarquia = " / ".join(p for p in (self.business_area, self.business_domain) if p)
        partes = (
            self.service_domain,
            jerarquia,
            clasif,
            self.control_record,
            self.service_role,
            self.examples_of_use,
            self.features,
            self.executive_summary,
            self.documentation,
        )
        texto = ". ".join(" ".join(str(p).split()) for p in partes if p and str(p).strip())
        if len(texto) <= max_chars:
            return texto
        return texto[:max_chars].rsplit(" ", 1)[0] + "…"


class CandidatoSD(BaseModel):
    """Un candidato recuperado por el RAG."""

    service_domain: str
    score: float = Field(description="Score de recuperación 0..1 (ranking del shortlist).")
    similitud_nombre: float = Field(
        default=0.0,
        description="Similitud léxica estricta 0..1 entre la consulta y este nombre "
        "(penaliza palabras que faltan). Es la que decide la banda.",
    )
    service_role: str | None = None
    functional_pattern: str | None = None


class VeredictoLLM(BaseModel):
    """Salida estructurada del adjudicador LLM.

    Justificación breve y verificable (no "razonamiento paso a paso"): la evidencia a favor y
    en contra por separado + una síntesis corta. Más barato en tokens y más estable/auditable.
    """

    evidence: str = Field(
        default="",
        description="Evidencia CONCRETA de que la consulta designa un candidato (1-2 frases).",
    )
    counter_evidence: str = Field(
        default="", description="Evidencia CONCRETA en contra / de ambigüedad (1-2 frases)."
    )
    reason_codes: list[str] = Field(
        default_factory=list,
        description="Códigos de razón: NAME_VARIATION, DIFFERENT_SERVICE_DOMAIN, RELATED_NOT_SAME, AMBIGUOUS.",
    )
    razonamiento: str = Field(
        default="", description="Síntesis verificable de 1-2 frases. NO enumeres pasos."
    )
    existe: bool = Field(
        description="True solo si la consulta designa el MISMO Service Domain que uno de los candidatos."
    )
    service_domain_canonico: str | None = Field(
        default=None,
        description="Nombre EXACTO del candidato coincidente (copiado literal). null si existe=False.",
    )
    confianza: float = Field(ge=0.0, le=1.0, description="Certeza de la decisión.")


class ResultadoValidacion(BaseModel):
    """Resultado final del nodo de validación."""

    service_domain_consultado: str
    existe: bool
    service_domain_canonico: str | None
    metodo: MetodoValidacion
    confianza: float
    razonamiento: str
    candidatos: list[CandidatoSD] = Field(default_factory=list)
