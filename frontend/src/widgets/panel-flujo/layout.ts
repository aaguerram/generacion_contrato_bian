import dagre from '@dagrejs/dagre'
import type { Edge, Node } from '@xyflow/react'
import type { AmbitoGrafo, Grafo } from '@entities/flujo'

export const ANCHO_NODO = 190
export const ALTO_NODO = 58
const SEPARACION_COLUMNAS = 150

/** Una columna por ámbito: el flujo principal a la izquierda, el subgrafo de una historia al lado. */
function colocarAmbito(grafo: Grafo, ambito: AmbitoGrafo) {
  const nodos = grafo.nodos.filter((n) => n.grafo === ambito)
  const ids = new Set(nodos.map((n) => n.id))
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  // De arriba abajo: el flujo se lee como se lee una página.
  //
  // `nodesep` alto y `ranksep` bajo a propósito: en vertical, lo que limita el zoom es el ALTO, y
  // en un monitor ancho sobra sitio a los lados. Separar más en horizontal y apretar en vertical
  // sube la escala a la que cabe todo, que es lo que decide si las etiquetas se leen.
  g.setGraph({ rankdir: 'TB', nodesep: 64, ranksep: 34, marginx: 16, marginy: 16 })
  for (const n of nodos) g.setNode(n.id, { width: ANCHO_NODO, height: ALTO_NODO })
  for (const a of grafo.aristas) {
    if (ids.has(a.origen) && ids.has(a.destino)) g.setEdge(a.origen, a.destino)
  }
  dagre.layout(g)
  return { nodos, g, ancho: (g.graph().width as number) ?? 0 }
}

/**
 * Coloca el grafo en capas de arriba abajo, con un ámbito por columna.
 *
 * Dos columnas y no una: `procesar_historia` invoca el subgrafo de la historia, así que
 * encadenarlos produce una sola columna del doble de alto que no cabe en pantalla. Separados,
 * cada columna tiene la mitad de capas y el dibujo además cuenta la verdad: son dos grafos, uno
 * dentro del otro.
 *
 * El aspecto de red sale del propio flujo. El abanico de `Send` -- una rama por historia, por
 * grupo y por candidato -- es lo que dibuja el haz de conexiones entre capas.
 */
export function colocar(grafo: Grafo): { nodos: Node[]; aristas: Edge[] } {
  const principal = colocarAmbito(grafo, 'principal')
  const historia = colocarAmbito(grafo, 'historia')
  const desplazamiento = principal.ancho + SEPARACION_COLUMNAS

  const posicionar = (col: ReturnType<typeof colocarAmbito>, dx: number): Node[] =>
    col.nodos.map((n) => {
      const pos = col.g.node(n.id)
      return {
        id: n.id,
        type: 'bian',
        // dagre da el CENTRO del nodo; React Flow espera la esquina superior izquierda.
        position: { x: pos.x - ANCHO_NODO / 2 + dx, y: pos.y - ALTO_NODO / 2 },
        // Declaradas y no medidas: son las MISMAS que reserva dagre, así que el hueco calculado y
        // la caja pintada coinciden. Además el minimapa necesita el tamaño para dibujar el nodo;
        // sin él salía un recuadro en blanco.
        width: ANCHO_NODO,
        height: ALTO_NODO,
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
