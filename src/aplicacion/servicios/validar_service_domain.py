"""Caso de uso `ValidarServiceDomainUseCase` orquestado con LangGraph.

    START
      -> coincidencia_exacta ──(existe)──────────────────────────────→ publicar
      -> (no) -> recuperar (RAG)
                   ├─ banda "alta"  → resolver_umbral  (existe=true,  determinista)
                   ├─ banda "baja"  → resolver_umbral  (existe=false, determinista)
                   └─ banda "gris"  → adjudicar (LLM)   → publicar
      -> END

El LLM solo decide en la franja gris; el resto es 100% reproducible.
Depende SOLO de: dominio, puertos y `langgraph`.
"""

from __future__ import annotations

import json
import logging

from langgraph.graph import END, START, StateGraph

try:
    from langgraph.types import RetryPolicy
except ImportError:  # pragma: no cover
    from langgraph.pregel import RetryPolicy  # type: ignore

from src.aplicacion.puertos.adjudicador import AdjudicadorLLMPort
from src.aplicacion.puertos.catalogo import CatalogoServiceDomainsPort
from src.aplicacion.puertos.entrada import ValidarServiceDomainUseCase
from src.aplicacion.puertos.publicador import PublicadorResultadoPort
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.aplicacion.servicios.estado import EstadoGrafo
from src.dominio.decision_similitud import Umbrales, clasificar, mejor_candidato
from src.dominio.modelos import ResultadoValidacion

logger = logging.getLogger("generacion_contrato_ia_v2.aplicacion")

_TRANSITORIOS = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE")


def _es_transitorio(exc: Exception) -> bool:
    t = str(exc).upper()
    return any(m in t for m in _TRANSITORIOS)


_RETRY = RetryPolicy(
    max_attempts=3, initial_interval=1.5, backoff_factor=2.0, max_interval=8.0, retry_on=_es_transitorio
)


class ValidarServiceDomainService(ValidarServiceDomainUseCase):
    def __init__(
        self,
        catalogo: CatalogoServiceDomainsPort,
        recuperador: RecuperadorSemanticoPort,
        adjudicador: AdjudicadorLLMPort,
        publicador: PublicadorResultadoPort,
        *,
        rag_top_k: int = 6,
        umbrales: Umbrales | None = None,
    ) -> None:
        self._catalogo = catalogo
        self._recuperador = recuperador
        self._adjudicador = adjudicador
        self._publicador = publicador
        self._k = rag_top_k
        self._umbrales = umbrales or Umbrales()
        self._grafo = self._compilar()

    def ejecutar(self, service_domain: str, directorio: str) -> ResultadoValidacion:
        estado = self._grafo.invoke(
            {"service_domain": service_domain, "directorio": directorio},
            config={"recursion_limit": 25},
        )
        return self._resultado(estado)

    # ── construcción del resultado ───────────────────────────────────────────
    @staticmethod
    def _resultado(estado: EstadoGrafo) -> ResultadoValidacion:
        return ResultadoValidacion(
            service_domain_consultado=estado["service_domain"],
            existe=bool(estado.get("existe")),
            service_domain_canonico=estado.get("service_domain_canonico"),
            metodo=estado.get("metodo", "similitud_baja"),
            confianza=float(estado.get("confianza", 0.0)),
            razonamiento=estado.get("razonamiento", ""),
            candidatos=list(estado.get("candidatos", [])),
        )

    # ── nodos ────────────────────────────────────────────────────────────────
    def _nodo_exacta(self, estado: EstadoGrafo) -> dict:
        entrada = self._catalogo.buscar_exacto(estado["service_domain"])
        if entrada is not None:
            logger.info("coincidencia exacta: %s", entrada.service_domain)
            return {
                "existe": True,
                "service_domain_canonico": entrada.service_domain,
                "confianza": 1.0,
                "metodo": "coincidencia_exacta",
                "razonamiento": "Coincidencia exacta en SD.json tras normalizar el nombre.",
                "candidatos": [],
            }
        return {"existe": False}

    def _nodo_recuperar(self, estado: EstadoGrafo) -> dict:
        candidatos = self._recuperador.recuperar(estado["service_domain"], self._k)
        banda = clasificar(candidatos, self._umbrales)
        mejor = mejor_candidato(candidatos)
        logger.info(
            "RAG -> banda=%s | mejor: %s (similitud_nombre %.2f)",
            banda,
            mejor.service_domain if mejor else "-",
            mejor.similitud_nombre if mejor else 0.0,
        )
        return {"candidatos": candidatos, "banda": banda}

    def _nodo_resolver_umbral(self, estado: EstadoGrafo) -> dict:
        mejor = mejor_candidato(estado["candidatos"])
        u = self._umbrales
        if estado["banda"] == "alta" and mejor is not None:
            logger.info("determinista ALTA: %s", mejor.service_domain)
            return {
                "existe": True,
                "service_domain_canonico": mejor.service_domain,
                "confianza": round(mejor.similitud_nombre, 2),
                "metodo": "similitud_alta",
                "razonamiento": (
                    f"Similitud léxica del nombre {mejor.similitud_nombre:.2f} ≥ umbral alto "
                    f"{u.alto:.2f}; coincidencia determinista sin adjudicación LLM."
                ),
            }
        s = mejor.similitud_nombre if mejor else 0.0
        logger.info("determinista BAJA (similitud %.2f < %.2f)", s, u.bajo)
        return {
            "existe": False,
            "service_domain_canonico": None,
            "confianza": round(1.0 - s, 2),
            "metodo": "similitud_baja",
            "razonamiento": (
                f"Mejor similitud léxica de nombre {s:.2f} < umbral bajo {u.bajo:.2f}; "
                f"sin coincidencia, sin adjudicación LLM."
            ),
        }

    def _nodo_adjudicar(self, estado: EstadoGrafo) -> dict:
        veredicto = self._adjudicador.adjudicar(estado["service_domain"], estado["candidatos"])
        logger.info(
            "LLM (franja gris): existe=%s canonico=%s confianza=%.2f",
            veredicto.existe,
            veredicto.service_domain_canonico,
            veredicto.confianza,
        )
        return {
            "existe": veredicto.existe,
            "service_domain_canonico": veredicto.service_domain_canonico,
            "confianza": veredicto.confianza,
            "razonamiento": veredicto.razonamiento,
            "metodo": "rag_llm",  # lo decidió el LLM (verdict True o False)
        }

    def _nodo_publicar(self, estado: EstadoGrafo) -> dict:
        ruta = self._publicador.publicar(self._resultado(estado), estado["directorio"])
        logger.info("resultado -> %s", ruta)
        return {"ruta_resultado": ruta}

    # ── enrutado ─────────────────────────────────────────────────────────────
    def _tras_exacta(self, estado: EstadoGrafo) -> str:
        return "publicar" if estado.get("existe") else "recuperar"

    def _tras_recuperar(self, estado: EstadoGrafo) -> str:
        return "adjudicar" if estado.get("banda") == "gris" else "resolver_umbral"

    # ── ensamblado ───────────────────────────────────────────────────────────
    def _compilar(self):
        g = StateGraph(EstadoGrafo)
        g.add_node("coincidencia_exacta", self._nodo_exacta)
        g.add_node("recuperar", self._nodo_recuperar)
        g.add_node("resolver_umbral", self._nodo_resolver_umbral)
        g.add_node("adjudicar", self._nodo_adjudicar, retry_policy=_RETRY)
        g.add_node("publicar", self._nodo_publicar)

        g.add_edge(START, "coincidencia_exacta")
        g.add_conditional_edges(
            "coincidencia_exacta",
            self._tras_exacta,
            {"publicar": "publicar", "recuperar": "recuperar"},
        )
        g.add_conditional_edges(
            "recuperar",
            self._tras_recuperar,
            {"resolver_umbral": "resolver_umbral", "adjudicar": "adjudicar"},
        )
        g.add_edge("resolver_umbral", "publicar")
        g.add_edge("adjudicar", "publicar")
        g.add_edge("publicar", END)
        return g.compile()
