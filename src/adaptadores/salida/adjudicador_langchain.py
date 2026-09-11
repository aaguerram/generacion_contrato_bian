"""Adaptador: adjudica con un chat model de LangChain + salida estructurada."""

from __future__ import annotations

from src.adaptadores.salida.llm.failover import SoportaStructured
from src.adaptadores.salida.prompts import PROMPT_ADJUDICADOR
from src.aplicacion.puertos.adjudicador import AdjudicadorLLMPort
from src.dominio.modelos import CandidatoSD, VeredictoLLM


def _formatear_candidatos(candidatos: list[CandidatoSD]) -> str:
    lineas = []
    for i, c in enumerate(candidatos, 1):
        detalle = c.service_role or ""
        if c.functional_pattern:
            detalle = f"[{c.functional_pattern}] {detalle}"
        lineas.append(f'{i}. "{c.service_domain}"  (similitud {c.score:.2f})\n   {detalle}'.rstrip())
    return "\n".join(lineas) if lineas else "(sin candidatos)"


class AdjudicadorLangChain(AdjudicadorLLMPort):
    def __init__(self, chat_model: SoportaStructured) -> None:
        self._cadena = PROMPT_ADJUDICADOR | chat_model.with_structured_output(VeredictoLLM)

    def adjudicar(self, consulta: str, candidatos: list[CandidatoSD]) -> VeredictoLLM:
        veredicto: VeredictoLLM = self._cadena.invoke(
            {"consulta": consulta, "candidatos": _formatear_candidatos(candidatos)}
        )
        # Compone `razonamiento` desde las partes verificables si el modelo no lo sintetizó.
        if not veredicto.razonamiento.strip():
            partes = [p for p in (
                f"A favor: {veredicto.evidence}" if veredicto.evidence else "",
                f"En contra: {veredicto.counter_evidence}" if veredicto.counter_evidence else "",
                f"[{', '.join(veredicto.reason_codes)}]" if veredicto.reason_codes else "",
            ) if p]
            if partes:
                veredicto = veredicto.model_copy(update={"razonamiento": " ".join(partes)})
        # Blindaje anti-alucinación: el canónico debe estar entre los candidatos.
        nombres = {c.service_domain for c in candidatos}
        if veredicto.existe and veredicto.service_domain_canonico not in nombres:
            return veredicto.model_copy(
                update={
                    "existe": False,
                    "service_domain_canonico": None,
                    "confianza": min(veredicto.confianza, 0.4),
                    "razonamiento": veredicto.razonamiento
                    + "\n[descartado: el nombre canónico propuesto no está entre los candidatos]",
                }
            )
        return veredicto
