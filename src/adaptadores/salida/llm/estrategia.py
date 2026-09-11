"""Interfaz del patrón Strategy. Una estrategia = un proveedor = (chat model + embeddings)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

_PRESUPUESTO = {"low": 512, "medium": 4096, "high": 24576}


@dataclass(frozen=True)
class ConfiguracionProveedor:
    chat_model: str
    embeddings_model: str
    api_key: str | None
    temperature: float
    esfuerzo: str  # low | medium | high
    seed: int | None = None  # reproducibilidad del chat (si el proveedor lo soporta)
    base_url: str | None = None  # p.ej. OpenRouter
    structured_method: str | None = None  # json_schema | function_calling | json_mode | None

    @property
    def presupuesto_pensamiento(self) -> int:
        return _PRESUPUESTO.get(self.esfuerzo, _PRESUPUESTO["high"])


class ProveedorLLMStrategy(ABC):
    nombre: str = "base"

    def __init__(self, config: ConfiguracionProveedor) -> None:
        self._config = config

    @abstractmethod
    def crear_chat_model(self) -> BaseChatModel: ...

    @abstractmethod
    def crear_embeddings(self) -> Embeddings: ...

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} nombre={self.nombre!r}>"
