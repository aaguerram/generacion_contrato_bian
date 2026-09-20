"""Factory + registro de estrategias de proveedor."""

from __future__ import annotations

from .aclide import AclideStrategy
from .anthropic import AnthropicStrategy
from .blaze import BlazeStrategy
from .cohere import CohereStrategy
from .dreamprompting import DreamPromptingStrategy
from .estrategia import ConfiguracionProveedor, ProveedorLLMStrategy
from .fake import FakeStrategy
from .freellmapi import FreeLLMAPIStrategy
from .gemini import GeminiStrategy
from .groq import GroqStrategy
from .huggingface import HuggingFaceStrategy
from .ollama import OllamaStrategy
from .openai import OpenAIStrategy
from .openrouter import OpenRouterStrategy

_REGISTRO: dict[str, type[ProveedorLLMStrategy]] = {
    OllamaStrategy.nombre: OllamaStrategy,
    FreeLLMAPIStrategy.nombre: FreeLLMAPIStrategy,
    DreamPromptingStrategy.nombre: DreamPromptingStrategy,
    BlazeStrategy.nombre: BlazeStrategy,
    AclideStrategy.nombre: AclideStrategy,
    GroqStrategy.nombre: GroqStrategy,
    GeminiStrategy.nombre: GeminiStrategy,
    HuggingFaceStrategy.nombre: HuggingFaceStrategy,
    OpenRouterStrategy.nombre: OpenRouterStrategy,
    CohereStrategy.nombre: CohereStrategy,
    AnthropicStrategy.nombre: AnthropicStrategy,
    OpenAIStrategy.nombre: OpenAIStrategy,
    FakeStrategy.nombre: FakeStrategy,
}


def registrar_estrategia(clase: type[ProveedorLLMStrategy]) -> None:
    if not getattr(clase, "nombre", None) or clase.nombre == "base":
        raise ValueError("La estrategia debe definir un `nombre` propio.")
    _REGISTRO[clase.nombre] = clase


def estrategias_disponibles() -> list[str]:
    return sorted(_REGISTRO)


def crear_estrategia(nombre: str, config: ConfiguracionProveedor) -> ProveedorLLMStrategy:
    clave = nombre.strip().lower()
    try:
        return _REGISTRO[clave](config)
    except KeyError:
        raise ValueError(
            f"Proveedor '{clave}' desconocido. Disponibles: {', '.join(estrategias_disponibles())}"
        ) from None
