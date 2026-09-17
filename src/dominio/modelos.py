"""Modelos del dominio."""

from __future__ import annotations

import re
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


def _frase(*partes) -> str:
    """Une los trozos que existan en una sola frase legible, sin puntos dobles."""
    limpias = [" ".join(str(p).split()) for p in partes if p and str(p).strip()]
    return " ".join(t if t.endswith((".", "!", "?", ":")) else f"{t}." for t in limpias)


def _limpiar_documentacion(documentacion: str | None) -> str:
    """`** 1. Role ** texto ** 2. Examples of use ** ...` -> `Role: texto. Examples of use: ...`."""
    if not documentacion:
        return ""
    # El número es opcional: además de `** 1. Role **`, el landscape trae `** General comment **`.
    texto = re.sub(r"\*\*\s*(?:\d+\s*\.?\s*)?([^*]+?)\s*\*\*", r" \1: ", str(documentacion))
    return " ".join(texto.split()).strip()


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
    # Qué significan `business_area` / `business_domain`, no solo cómo se llaman: el landscape
    # documenta cada nodo de la jerarquía y hasta ahora se descartaba al aplanar. Se repiten entre
    # los SD del mismo nodo a propósito -- el prompt los deduplica y los manda UNA vez como
    # taxonomía (5 areas + 36 dominios ~ 2.9k tokens), nunca inline por SD (~23k tokens).
    business_area_doc: str | None = None
    business_domain_doc: str | None = None

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

    def texto_prosa(self, variante: str = "prosa") -> str:
        """Texto del Service Domain en PROSA, para un cross-encoder (no para un índice).

        Un índice y un reranker quieren cosas distintas y por eso no comparten texto. El índice
        (`texto_para_indexar`) quiere **cobertura de vocabulario**: cuantos más términos reales
        del SD entren, más probable es que alguno coincida con la consulta, y da igual que el
        resultado se lea como un volcado —jerarquía, patrón funcional, tipo de activo, nombre del
        Control Record, todo pegado—. Un cross-encoder, en cambio, **lee** el par (consulta,
        documento) como texto: la clasificación y la jerarquía no le dicen nada, le añaden ruido y
        le gastan ventana. Medido: con el texto del índice, el reranker puntúa todos los
        candidatos en ~0.003 (no ve ningún emparejamiento) y hunde R@1 de 0.50 a 0.17.

        Variantes (`VARIANTES_TEXTO_SD`), de menos a más contenido:

        - `indice`: el texto del índice, tal cual. Es la línea base con la que comparar.
        - `rol` / `resumen` / `ejemplos` / `features`: un solo campo del landscape.
        - `nombre_rol`: el nombre seguido de su rol — lo mínimo que se lee como una frase.
        - `prosa`: nombre + rol + ejemplo de uso + resumen ejecutivo. Todo lo redactado, sin
          clasificación ni jerarquía.
        - `prosa_features`: lo anterior más las capacidades (que son una lista, no prosa).
        - `documentacion`: la ficha estructurada del landscape tal cual (`** 1. Role ** ...`).
        - `documentacion_limpia`: la misma ficha con los marcadores convertidos en encabezados
          legibles, que es como la leería una persona.

        Cuál usar no se decide por intuición: lo elige el barrido
        `evaluate.py --barrido-texto`.
        """
        nombre = self.service_domain or ""
        campos = {
            "rol": self.service_role,
            "resumen": self.executive_summary,
            "ejemplos": self.examples_of_use,
            "features": self.features,
            "documentacion": self.documentation,
        }
        if variante == "indice":
            return self.texto_para_indexar()
        if variante in campos:
            return " ".join(str(campos[variante] or "").split()) or nombre
        if variante == "nombre_rol":
            return _frase(nombre, self.service_role)
        if variante == "prosa":
            return _frase(nombre, self.service_role, self.examples_of_use, self.executive_summary)
        if variante == "prosa_features":
            return _frase(
                nombre,
                self.service_role,
                self.examples_of_use,
                self.executive_summary,
                self.features,
            )
        if variante == "documentacion_limpia":
            # El nombre va delante como en el resto de variantes en prosa: sin él, esta sería la
            # única que compite sin decir de qué Service Domain habla, y la comparación mentiría.
            limpia = _limpiar_documentacion(self.documentation)
            return _frase(nombre, limpia) if limpia else _frase(nombre, self.service_role)
        raise ValueError(
            f"variante de texto desconocida: '{variante}' (esperaba una de {VARIANTES_TEXTO_SD})"
        )


VARIANTES_TEXTO_SD = (
    "indice",
    "rol",
    "nombre_rol",
    "resumen",
    "ejemplos",
    "features",
    "prosa",
    "prosa_features",
    "documentacion",
    "documentacion_limpia",
)


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
