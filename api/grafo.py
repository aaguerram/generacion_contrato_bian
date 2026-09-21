"""La topología del flujo de LangGraph, leída del grafo REAL.

No se escribe a mano. Se compila el caso de uso y se le pregunta al grafo por sus nodos y aristas,
porque un dibujo escrito aparte se desincroniza del código en cuanto alguien añade un nodo, y un
diagrama que miente sobre el flujo es peor que no tener diagrama.

Se compila con `--proveedor fake`: construir el grafo no llama a ningún modelo, solo necesita el
catálogo, así que preguntar por la forma del flujo no gasta cuota.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from api.modelos import AristaGrafo, Grafo, NodoGrafo

logger = logging.getLogger("api.grafo")

# Los nodos que hacen una llamada al modelo. Se marcan para que la interfaz los distinga: son los
# caros, los lentos y los únicos cuya salida depende de qué proveedor respondió.
_NODOS_LLM = frozenset({
    "extraer_intencion", "enrutar_dominios", "generar_candidatos", "generar_candidatos_grupo",
    "revisar_completitud", "evaluar_candidato", "revisar_adversarial", "seleccionar_operaciones",
    "reconciliar",
})

# Los que se repiten por el abanico de `Send`: una vez por historia, por grupo o por candidato.
_NODOS_ABANICO = frozenset({
    "procesar_historia", "generar_candidatos_grupo", "evaluar_candidato",
})

_DESCRIPCIONES = {
    "cargar": "Lee las Historias de Usuario y el catálogo BIAN, y reparte una rama por historia.",
    "procesar_historia": "Ejecuta el subgrafo completo para UNA historia.",
    "reconciliar": "Ve todas las historias juntas y opina sobre la funcionalidad. Es asesor: no decide.",
    "publicar": "Escribe el JSON del mapeo.",
    "extraer_intencion": "Qué pide la historia: acciones, objetos, datos y dependencias. No nombra ningún Service Domain.",
    "enrutar_dominios": "Elige Business Domains sobre la taxonomía, antes de ver ningún Service Domain.",
    "generar_candidatos": "Propone Service Domains del catálogo. Es una pista, no una lista cerrada.",
    "generar_candidatos_grupo": "Lo mismo, pero una llamada por grupo de dominios enrutados.",
    "fusionar_candidatos": "Une lo que propuso cada grupo. Determinista.",
    "revisar_completitud": "Busca ausencias, solapes y conflictos de propiedad sobre el índice global.",
    "preparar_candidatos": "Resuelve nombres contra el catálogo y arma la evidencia oficial de cada candidato.",
    "evaluar_candidato": "Una llamada aislada por Service Domain. Solo señales ordinales, nunca confianza.",
    "clasificar": "Calcula el score y decide grupo y decisión contractual. Determinista.",
    "revisar_adversarial": "Revisa la hipótesis sin haberla visto formarse.",
    "aplicar_adversarial": "Promueve o degrada, pero solo si una señal independiente lo confirma. Determinista.",
    "seleccionar_operaciones": "Ancla la operación BIAN oficial de cada Service Domain elegible.",
    "ensamblar": "Junta el resultado de la historia. Determinista.",
}

_cache: Grafo | None = None
_cerrojo = threading.Lock()


def _etiqueta(nodo: str) -> str:
    return nodo.replace("_", " ").capitalize()


def _tipo(nodo: str) -> str:
    if nodo == "__start__":
        return "inicio"
    if nodo == "__end__":
        return "fin"
    return "nodo"


def _volcar(compilado: Any, ambito: str, nodos: list[NodoGrafo], aristas: list[AristaGrafo]) -> None:
    g = compilado.get_graph()
    sufijo = "" if ambito == "principal" else "__hu"
    for nombre in g.nodes:
        # El inicio y el fin del subgrafo son los del subgrafo: se distinguen con un sufijo para
        # que no se confundan con los del grafo principal.
        ident = f"{nombre}{sufijo}" if nombre.startswith("__") else nombre
        nodos.append(
            NodoGrafo(
                id=ident,
                etiqueta=_etiqueta(nombre),
                grafo=ambito,
                tipo=_tipo(nombre),
                llm=nombre in _NODOS_LLM,
                abanico=nombre in _NODOS_ABANICO,
                descripcion=_DESCRIPCIONES.get(nombre, ""),
            )
        )
    for arista in g.edges:
        o = f"{arista.source}{sufijo}" if arista.source.startswith("__") else arista.source
        d = f"{arista.target}{sufijo}" if arista.target.startswith("__") else arista.target
        aristas.append(AristaGrafo(origen=o, destino=d, condicional=bool(arista.conditional)))


def topologia() -> Grafo:
    """Nodos y aristas del flujo. Se calcula una vez: la forma del grafo no cambia en caliente."""
    global _cache
    with _cerrojo:
        if _cache is not None:
            return _cache
        from src.configuracion.contenedor import crear_caso_uso_mapeo
        from src.configuracion.settings import cargar_settings

        caso = crear_caso_uso_mapeo(cargar_settings(), proveedor="fake")
        nodos: list[NodoGrafo] = []
        aristas: list[AristaGrafo] = []
        _volcar(caso._grafo, "principal", nodos, aristas)
        _volcar(caso._subgrafo, "historia", nodos, aristas)
        # El puente entre los dos grafos: `procesar_historia` invoca el subgrafo con `.invoke()`,
        # así que esa arista no existe en ninguno de los dos y hay que declararla para que el
        # dibujo sea un flujo y no dos islas.
        aristas.append(AristaGrafo(origen="procesar_historia", destino="__start____hu", condicional=False))
        aristas.append(AristaGrafo(origen="__end____hu", destino="reconciliar", condicional=False))
        _cache = Grafo(nodos=nodos, aristas=aristas)
        logger.info("topología del grafo: %d nodos, %d aristas", len(nodos), len(aristas))
        return _cache
