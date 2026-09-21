"""Convierte el estado de un nodo del grafo en algo que se pueda guardar y enseñar.

El estado que circula por LangGraph no es JSON: son modelos del dominio, dataclasses y, sobre
todo, el catálogo entero de 341 Service Domains con su evidencia. Guardarlo tal cual por cada uno
de los ~16 nodos y por cada repetición del abanico llenaría la base de copias del mismo catálogo
y dejaría la interfaz intentando pintar megabytes.

Así que se resume, con tres reglas y ninguna sorpresa:
  - las claves pesadas se sustituyen por un marcador que dice qué había y cuánto ocupaba, en vez
    de desaparecer en silencio;
  - los textos y las listas largas se recortan, siempre dejando dicho cuánto se recortó;
  - lo que no se sabe convertir acaba en su `repr`, que informa más que un hueco.
"""

from __future__ import annotations

import dataclasses
from typing import Any

# El catálogo y la evidencia viajan en el estado de casi todos los nodos y son enormes. Lo que
# importa de ellos es que estaban y de qué tamaño, no su contenido repetido 200 veces.
CLAVES_RESUMIDAS = frozenset(
    {"catalogo", "catalogo_bom", "schemas_detalle", "bom_modelo", "documentation"}
)
MAX_TEXTO = 3000
MAX_ITEMS = 30
MAX_PROFUNDIDAD = 6


def _es_modelo(v: Any) -> bool:
    return hasattr(v, "model_dump") and callable(v.model_dump)


def _marcador(v: Any) -> dict[str, Any]:
    if isinstance(v, (list, tuple, set)):
        return {"_resumido": f"{len(v)} elemento(s)", "_tipo": type(v).__name__}
    if isinstance(v, dict):
        return {"_resumido": f"{len(v)} clave(s)", "_tipo": "dict"}
    texto = str(v)
    return {"_resumido": f"{len(texto)} caracteres", "_tipo": type(v).__name__}


def resumir(valor: Any, profundidad: int = 0) -> Any:
    """Versión JSON-serializable y acotada de cualquier cosa que circule por el grafo."""
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor

    if isinstance(valor, str):
        return valor if len(valor) <= MAX_TEXTO else valor[:MAX_TEXTO] + f"… (+{len(valor) - MAX_TEXTO} car.)"

    if profundidad >= MAX_PROFUNDIDAD:
        return _marcador(valor)

    if _es_modelo(valor):
        try:
            return resumir(valor.model_dump(), profundidad)
        except Exception:
            return _marcador(valor)

    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        try:
            return resumir(dataclasses.asdict(valor), profundidad)
        except Exception:
            return _marcador(valor)

    if isinstance(valor, dict):
        salida: dict[str, Any] = {}
        for i, (k, v) in enumerate(valor.items()):
            clave = str(k)
            if clave in CLAVES_RESUMIDAS:
                salida[clave] = _marcador(v)
            elif i >= MAX_ITEMS:
                salida["_recortado"] = f"+{len(valor) - MAX_ITEMS} clave(s) más"
                break
            else:
                salida[clave] = resumir(v, profundidad + 1)
        return salida

    if isinstance(valor, (list, tuple, set)):
        items = list(valor)
        recorte = [resumir(v, profundidad + 1) for v in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            recorte.append({"_recortado": f"+{len(items) - MAX_ITEMS} elemento(s) más"})
        return recorte

    return resumir(repr(valor), profundidad)


def huella_del_nodo(salida: Any) -> tuple[str, str, str]:
    """`(proveedor, modelo, prompt_id)` de la llamada LLM que hizo el nodo, si la hubo.

    Sale de `MetadatosPrompt`, la huella que el pipeline ya adjunta a cada respuesta del modelo
    para poder reproducirla. Un nodo determinista no deja huella y devuelve tres cadenas vacías.
    """
    for huella in _huellas(salida):
        prov = str(huella.get("provider_used") or "")
        modelo = str(huella.get("model_used") or "")
        if prov or modelo:
            return prov, modelo, str(huella.get("prompt_id") or "")
    return "", "", ""


def _huellas(valor: Any, profundidad: int = 0) -> list[dict]:
    """Busca diccionarios con pinta de `MetadatosPrompt` dentro de la salida de un nodo."""
    if profundidad > 4:
        return []
    if _es_modelo(valor):
        try:
            valor = valor.model_dump()
        except Exception:
            return []
    if isinstance(valor, dict):
        if "prompt_id" in valor and ("model_used" in valor or "model" in valor):
            return [valor]
        fuera: list[dict] = []
        for v in valor.values():
            fuera += _huellas(v, profundidad + 1)
        return fuera
    if isinstance(valor, (list, tuple)):
        fuera = []
        for v in valor:
            fuera += _huellas(v, profundidad + 1)
        return fuera
    return []
