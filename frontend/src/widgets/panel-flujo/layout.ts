import dagre from '@dagrejs/dagre'
import type { Edge, Node } from '@xyflow/react'
import type { AmbitoGrafo, Grafo } from '@entities/flujo'

export const ANCHO_NODO = 176
export const ALTO_NODO = 58
const SEPARACION_FILAS = 130

/** Una fila por ámbito: el flujo principal arriba, el subgrafo de una historia debajo. */
function colocarAmbito(grafo: Grafo, ambito: AmbitoGrafo) {
  const nodos = grafo.nodos.filter((n) => n.grafo === ambito)
  const ids = new Set(nodos.map((n) => n.id))
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 22, ranksep: 54, marginx: 16, marginy: 16 })
  for (const n of nodos) g.setNode(n.id, { width: ANCHO_NODO, height: ALTO_NODO })
  for (const a of grafo.aristas) {
    if (ids.has(a.origen) && ids.has(a.destino)) g.setEdge(a.origen, a.destino)
  }
  dagre.layout(g)
  const alto = (g.graph().height as number) ?? 0
  return { nodos, g, alto }
}

/**
 * Coloca el grafo en capas de izquierda a derecha, con un ámbito por fila.
 *
 * Dos filas y no una: `procesar_historia` invoca el subgrafo de la historia, así que encadenarlos
 * produce una serpiente de 19 capas que, al caber entera en el panel, queda a escala 0.16 y no se
 * lee nada. Separados, cada fila tiene la mitad de capas y el dibujo además cuenta la verdad: son
 * dos grafos, uno dentro del otro.
 *
 * El aspecto de red sale del propio flujo. El abanico de `Send` -- una rama por historia, por
 * grupo y por candidato -- es lo que dibuja el haz de conexiones entre capas.
 */
export function colocar(grafo: Grafo): { nodos: Node[]; aristas: Edge[] } {
  const principal = colocarAmbito(grafo, 'principal')
  const historia = colocarAmbito(grafo, 'historia')
  const desplazamiento = principal.alto + SEPARACION_FILAS

  const posicionar = (fila: ReturnType<typeof colocarAmbito>, dy: number): Node[] =>
    fila.nodos.map((n) => {
      const pos = fila.g.node(n.id)
      return {
        id: n.id,
        type: 'bian',
        // dagre da el CENTRO del nodo; React Flow espera la esquina superior izquierda.
        position: { x: pos.x - ANCHO_NODO / 2, y: pos.y - ALTO_NODO / 2 + dy },
        data: { ...n },
        draggable: false,
      }
    })

  const nodos = [...posicionar(principal, 0), ...posicionar(historia, desplazamiento)]

  const aristas: Edge[] = grafo.aristas.map((a) => {
    const puente =
      grafo.nodos.find((n) => n.id === a.origen)?.grafo !==
      grafo.nodos.find((n) => n.id === a.destino)?.grafo
    return {
      id: `${a.origen}->${a.destino}`,
      source: a.origen,
      target: a.destino,
      type: 'smoothstep',
      // Una arista condicional no siempre se recorre; una de puente salta entre los dos grafos.
      style: a.condicional ? { strokeDasharray: '5 4' } : undefined,
      data: { condicional: a.condicional, puente },
    }
  })

  return { nodos, aristas }
}
