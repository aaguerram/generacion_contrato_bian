"""Puerto para observar la ejecución del grafo nodo a nodo.

Existe porque una corrida dura de minutos a decenas de minutos y, desde fuera, es una caja negra:
o termina o no termina. Quien la lanza necesita ver POR DÓNDE va, qué entró y qué salió de cada
nodo, y poder pararla en un punto concreto sin matar el proceso.

Es un puerto y no un `logger` porque lo que viaja son DATOS (el estado de entrada, la salida del
nodo, cuánto tardó, qué modelo respondió), no texto. Un adaptador los guarda en una base y los
publica a una interfaz; otro podría no hacer nada. La capa de aplicación no sabe cuál hay detrás,
y sin observador el grafo se comporta exactamente como siempre.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


class EjecucionDetenida(Exception):
    """El observador pidió parar después de `nodo`. No es un error: es lo que se pidió.

    Se usa una excepción y no un valor de retorno porque hay que cortar en medio de un grafo con
    abanico y concurrencia, donde el nodo que termina no controla quién se ejecuta después. Quien
    lanza la corrida la distingue de un fallo real por su tipo, y la trata como final legítimo.
    """

    def __init__(self, nodo: str) -> None:
        super().__init__(f"ejecución detenida a petición, después del nodo '{nodo}'")
        self.nodo = nodo


@runtime_checkable
class ObservadorEjecucionPort(Protocol):
    """Recibe un aviso al entrar y al salir de cada nodo del grafo.

    `instancia` distingue las repeticiones de un mismo nodo: con el abanico de `Send`,
    `evaluar_candidato` corre una vez por candidato y `procesar_historia` una vez por historia.
    Cadena vacía = el nodo corre una sola vez.

    Ninguna implementación debe lanzar: un fallo observando no puede tumbar la corrida observada.
    """

    def nodo_inicia(self, nodo: str, instancia: str, entrada: Mapping[str, Any]) -> None: ...

    def nodo_termina(self, nodo: str, instancia: str, salida: Any, ms: float) -> None: ...

    def nodo_falla(self, nodo: str, instancia: str, error: str, ms: float) -> None: ...

    def detener_tras(self, nodo: str) -> bool:
        """¿Hay que parar la corrida entera al terminar este nodo?"""
        ...
