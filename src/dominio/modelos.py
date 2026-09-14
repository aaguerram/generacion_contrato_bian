"""Modelos del dominio."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MetodoValidacion = Literal[
    "coincidencia_exacta",  # el nombre está en SD.json salvo forma       (determinista, existe=True)
    "similitud_alta",  # similitud léxica del nombre >= umbral alto   (determinista, existe=True)
    "similitud_baja",  # similitud léxica del nombre <  umbral bajo   (determinista, existe=False)
    "rag_llm",  # franja gris: lo decidió el LLM adjudicador   (existe True o False)
]


class EntradaCatalogo(BaseModel):
    """Un BIAN Service Domain leído de SD.json (columnas L..V).

    `business_area` / `business_domain` no están en SD.json: los rellena `CatalogoJson`
    cruzando con `docs/bian-business-areas.json` (misma release, mismos 341 SD).
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

    def texto_para_indexar(self) -> str:
        """Texto compacto para el índice RAG (nombre + clasificación + rol, recortado)."""
        clasif = " / ".join(
            p for p in (self.functional_pattern, self.asset_type, self.generic_artifact_type) if p
        )
        rol = (self.service_role or "").strip()
        if len(rol) > 320:
            rol = rol[:320].rsplit(" ", 1)[0] + "…"
        return f"{self.service_domain}. {clasif}. {rol}".strip()


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
