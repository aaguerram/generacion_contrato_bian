"""Estrategia 'fake': chat y embeddings deterministas, sin API. Para tests y demo offline.

Cada responder parsea el prompt renderizado y devuelve una salida ESTRUCTURADA estable
(sembrada con md5 del archivo de la historia + el Service Domain). No es semántico; solo
sirve para cablear el grafo y comprobar invariantes sin llamar a ningún proveedor.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda

from src.dominio.historias import (
    CandidatoServiceDomainLLM,
    CandidatosHistoriaLLM,
    EnrutamientoDominiosLLM,
    EvaluacionCandidatoLLM,
    IntencionHistoriaLLM,
    MapeoOperacionesLLM,
    OperacionPropuestaLLM,
    ReconciliacionFuncionalidadLLM,
    RevisionAdversarialLLM,
    RevisionCompletitudLLM,
)
from src.dominio.modelos import VeredictoLLM

from .estrategia import ProveedorLLMStrategy

_DIM = 64


def _sem(*partes: str) -> int:
    return int(hashlib.md5("|".join(partes).encode()).hexdigest(), 16)


def _bloque(texto: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", texto, re.S)
    return m.group(1) if m else ""


def _archivo_hu(texto: str) -> str:
    return (re.search(r'<historia archivo="([^"]+)"', texto) or [None, ""])[1]


class _FakeEmbeddings(Embeddings):
    """Vector determinista por bolsa de trigramas hasheados. No es semántico, pero es estable."""

    def _vec(self, texto: str) -> list[float]:
        v = [0.0] * _DIM
        t = texto.lower()
        for i in range(max(len(t) - 2, 1)):
            h = int(hashlib.md5(t[i : i + 3].encode()).hexdigest(), 16)
            v[h % _DIM] += 1.0
        norma = sum(x * x for x in v) ** 0.5 or 1.0
        return [x / norma for x in v]

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in textos]

    def embed_query(self, texto: str) -> list[float]:
        return self._vec(texto)


class _FakeChat(BaseChatModel):
    @property
    def _llm_type(self) -> str:  # pragma: no cover
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # pragma: no cover
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    def with_structured_output(self, schema, **kwargs) -> Runnable:  # type: ignore[override]
        nombre = getattr(schema, "__name__", "")
        return RunnableLambda(_RESPONDERS.get(nombre, _responder_veredicto))


# ── responders deterministas ────────────────────────────────────────────────
def _responder_veredicto(entrada: Any) -> VeredictoLLM:
    texto = str(entrada)
    m = re.search(r"<consulta>(.*?)</consulta>", texto, re.S)
    consulta_norm = re.sub(r"[^a-z0-9]", "", (m.group(1) if m else "").lower())
    nombres = re.findall(r'\d+\.\s+"([^"]+)"', texto)
    match = next((n for n in nombres if re.sub(r"[^a-z0-9]", "", n.lower()) == consulta_norm), None)
    return VeredictoLLM(
        evidence="(fake) nombre normalizado idéntico a un candidato." if match else "",
        counter_evidence="" if match else "(fake) ningún candidato coincide tras normalizar.",
        reason_codes=["NAME_VARIATION"] if match else ["DIFFERENT_SERVICE_DOMAIN"],
        razonamiento="(fake) coincidencia por nombre normalizado contra los candidatos.",
        existe=match is not None,
        service_domain_canonico=match,
        confianza=0.95 if match else 0.2,
    )


def _responder_intencion(entrada: Any) -> IntencionHistoriaLLM:
    texto = str(entrada)
    cuerpo = _bloque(texto, "historia")
    palabras = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñ]{5,}", cuerpo)
    acciones = sorted({w.lower() for w in palabras if w.lower().endswith(("ar", "er", "ir"))})[:4]
    objetos = sorted({w.lower() for w in palabras if not w.lower().endswith(("ar", "er", "ir"))})[:4]
    escenarios = re.findall(r"Escenario\s+(\d+)", cuerpo)
    trace = [f"SC-{int(n):02d}" for n in dict.fromkeys(escenarios)]
    return IntencionHistoriaLLM(
        resumen_funcional=f"(fake) intención derivada de '{_archivo_hu(texto)}'.",
        capacidades_funcionales=objetos[:2],
        business_actions=acciones,
        business_objects=objetos,
        outcomes=[],
        external_dependencies=[],
        traceability_ids=trace,
    )


def _responder_enrutamiento(entrada: Any) -> EnrutamientoDominiosLLM:
    """Elige 3 Business Domains estables por HU. Deliberadamente NO elige uno solo: el fake tiene
    que ejercitar el camino en el que 2b ve varios dominios, que es el caso real."""
    texto = str(entrada)
    archivo = _archivo_hu(texto)
    dominios = re.findall(r'Business Domain "([^"]+)"', _bloque(texto, "taxonomia_bian"))
    if not dominios:
        return EnrutamientoDominiosLLM(rationale="(fake) taxonomía vacía; sin enrutar.")
    ordenados = sorted(dominios, key=lambda d: _sem(archivo, d))
    return EnrutamientoDominiosLLM(
        business_domains=ordenados[:2],
        dependency_domains=ordenados[2:3],
        rationale=f"(fake) enrutamiento estable para '{archivo}'.",
    )


def _responder_candidatos(entrada: Any) -> CandidatosHistoriaLLM:
    texto = str(entrada)
    archivo = _archivo_hu(texto)
    nombres = re.findall(r'-\s+"([^"]+)"', _bloque(texto, "catalogo_bian"))
    # Los N primeros al ordenar por hash(HU, nombre): estable por historia y, a diferencia de un
    # muestreo "1 de cada 40", INDEPENDIENTE del tamaño del catálogo. Importa desde el routing
    # jerárquico: el nodo 2b ve ~30 SD en vez de 341, y con la regla vieja el fake se quedaba
    # casi sin candidatos y la demo offline terminaba sin ningún Service Domain.
    elegidos = [
        CandidatoServiceDomainLLM(
            service_domain=nombre,
            rationale=f"(fake) candidato estable para '{archivo}'.",
            supporting_intent=[],
        )
        for nombre in sorted(nombres, key=lambda n: _sem(archivo, n))[:8]
    ]
    return CandidatosHistoriaLLM(candidatos=elegidos, coverage_notes=[], assumptions=[], gaps=[])


def _responder_completitud(entrada: Any) -> RevisionCompletitudLLM:
    return RevisionCompletitudLLM(review_summary="(fake) sin candidatos faltantes ni conflictos.")


def _responder_evaluacion(entrada: Any) -> EvaluacionCandidatoLLM:
    texto = str(entrada)
    archivo = _archivo_hu(texto)
    sd = (re.search(r'service_domain:\s*"([^"]+)"', texto) or [None, "?"])[1]
    estado_ev = (re.search(r"estado=(\w+)", texto) or [None, "BIAN_EVIDENCE_UNAVAILABLE"])[1]
    trace = re.findall(r"(HU-[\w/.-]+|SC-\d+|BR-[\w.-]+)", _bloque(texto, "intencion_funcional"))
    h = _sem(archivo, sd)
    rol = ["OWNED_CONTRACT", "CONSUMED_DEPENDENCY", "RELATED_NOT_OWNED"][h % 3]
    owned = rol == "OWNED_CONTRACT"
    verificada = estado_ev in ("VERIFIED", "CACHED_VERIFIED")
    eq = 3 if verificada else (0 if estado_ev == "BIAN_EVIDENCE_UNAVAILABLE" else 1)
    msr = (h % 4) if owned else (h % 2)
    return EvaluacionCandidatoLLM(
        service_domain=sd,
        estado="DIRECTO" if owned and msr >= 2 and eq >= 2 else "TENTATIVO" if owned else "DESCARTADO",
        rol_contractual=rol,
        dependency_kind=(["SECURITY_GUARD", "SUPPORTING_LOOKUP", "RISK_INPUT", "AUDIT_OR_NOTIFICATION"][h % 4]
                         if rol == "CONSUMED_DEPENDENCY" else None),
        accion_objeto=f"(fake) verbo objeto {sd}" if owned else "",
        functional_object=sd if owned else "",
        match_action=(h % 4) if owned else 0,
        match_business_object=((h // 7) % 4) if owned else 0,
        match_service_role=msr,
        evidence_quality=eq,
        ambiguity="NONE" if owned and msr == 3 else "LOW" if owned else "HIGH",
        ownership_traceability=(trace[:2] or ["SC-01"]) if owned else [],
        dependency_traceability=[] if owned else (trace[:1] or ["SC-01"]),
        evidence_refs=[],
        reason_codes=[] if verificada or not owned else ["NO_OFFICIAL_BIAN_EVIDENCE"],
        justification=f"(fake) evaluación estable de '{sd}' para '{archivo}'.",
    )


def _responder_adversarial(entrada: Any) -> RevisionAdversarialLLM:
    return RevisionAdversarialLLM(hallazgos=[], blocking_codes=[],
                                 resumen="(fake) sin contradicciones detectadas.")


def _responder_reconciliacion(entrada: Any) -> ReconciliacionFuncionalidadLLM:
    return ReconciliacionFuncionalidadLLM(service_domains=[], gaps=[], blocking_codes=[])


def _responder_operaciones(entrada: Any) -> MapeoOperacionesLLM:
    texto = str(entrada)
    cuerpo = _bloque(texto, "operaciones_disponibles")
    propuestas: list[OperacionPropuestaLLM] = []
    sd_actual = None
    vistos_por_sd: set[str] = set()
    for linea in re.split(r"\\n|\n", cuerpo):
        m_sd = re.search(r'Service Domain "([^"]+)"', linea)
        if m_sd:
            sd_actual = m_sd.group(1)
            continue
        m_op = re.match(r"\s*-\s+(\S+)\s+\(", linea)
        if m_op and sd_actual:
            op = m_op.group(1)
            h = _sem(sd_actual, op)
            if sd_actual not in vistos_por_sd or h % 3 == 0:
                vistos_por_sd.add(sd_actual)
                propuestas.append(OperacionPropuestaLLM(
                    service_domain=sd_actual, operation_id=op, escenarios_hu=[],
                    justificacion=f"(fake) {op} para {sd_actual}.", traceability=["SC-01"],
                ))
    return MapeoOperacionesLLM(operaciones=propuestas, gaps=[], blocking_codes=[])


_RESPONDERS = {
    "IntencionHistoriaLLM": _responder_intencion,
    "EnrutamientoDominiosLLM": _responder_enrutamiento,
    "CandidatosHistoriaLLM": _responder_candidatos,
    "RevisionCompletitudLLM": _responder_completitud,
    "EvaluacionCandidatoLLM": _responder_evaluacion,
    "RevisionAdversarialLLM": _responder_adversarial,
    "ReconciliacionFuncionalidadLLM": _responder_reconciliacion,
    "MapeoOperacionesLLM": _responder_operaciones,
    "VeredictoLLM": _responder_veredicto,
}


class FakeStrategy(ProveedorLLMStrategy):
    nombre = "fake"

    def crear_chat_model(self) -> BaseChatModel:
        return _FakeChat()

    def crear_embeddings(self) -> Embeddings:
        return _FakeEmbeddings()
