/**
 * El flujo de LangGraph y su avance.
 *
 * La topología la manda el servidor leída del grafo REAL, no está escrita aquí: un dibujo
 * mantenido a mano se desincroniza del código en cuanto alguien añade un nodo.
 */

export type AmbitoGrafo = 'principal' | 'historia'
export type TipoNodo = 'nodo' | 'inicio' | 'fin'

export interface NodoGrafo {
  id: string
  etiqueta: string
  grafo: AmbitoGrafo
  tipo: TipoNodo
  llm: boolean
  abanico: boolean
  descripcion: string
}

export interface AristaGrafo {
  origen: string
  destino: string
  condicional: boolean
}

export interface Grafo {
  nodos: NodoGrafo[]
  aristas: AristaGrafo[]
}

export interface PasoNodo {
  id: number
  nodo: string
  instancia: string
  /** 'interrumpido' = el nodo estaba a mitad cuando la corrida terminó. */
  estado: 'en_curso' | 'completado' | 'fallido' | 'interrumpido'
  proveedor: string
  modelo: string
  prompt_id: string
  ms: number | null
  iniciado_en: string
  terminado_en: string | null
  error: string
}

export interface DetallePaso extends PasoNodo {
  entrada: unknown
  salida: unknown
}

/**
 * Cómo se pinta un nodo. `apagado` es el estado inicial de todos: la red del flujo se ve entera
 * antes de ejecutar nada, y la corrida la va encendiendo.
 */
export type EstadoVisual =
  | 'apagado'
  | 'en_curso'
  | 'completado'
  | 'fallido'
  | 'cortado'
  | 'interrumpido'

export interface ResumenNodo {
  estado: EstadoVisual
  pasos: PasoNodo[]
  /** Suma de los tiempos de todas las repeticiones del nodo. Con abanico corren en paralelo. */
  ms: number
  modelos: string[]
}

/** Agrupa los pasos por nodo: el dibujo tiene un nodo por TIPO, aunque el abanico lo repita. */
export function resumirPorNodo(pasos: PasoNodo[], cortadoEn?: string | null): Map<string, ResumenNodo> {
  const mapa = new Map<string, ResumenNodo>()
  for (const p of pasos) {
    const r = mapa.get(p.nodo) ?? { estado: 'apagado' as EstadoVisual, pasos: [], ms: 0, modelos: [] }
    r.pasos.push(p)
    r.ms += p.ms ?? 0
    const modelo = p.modelo ? `${p.proveedor}:${p.modelo}` : ''
    if (modelo && !r.modelos.includes(modelo)) r.modelos.push(modelo)
    mapa.set(p.nodo, r)
  }
  for (const [nodo, r] of mapa) {
    // Un solo paso fallido tiñe el nodo: es lo que hay que mirar primero.
    if (r.pasos.some((p) => p.estado === 'fallido')) r.estado = 'fallido'
    else if (r.pasos.some((p) => p.estado === 'en_curso')) r.estado = 'en_curso'
    else if (r.pasos.every((p) => p.estado === 'interrumpido')) r.estado = 'interrumpido'
    else r.estado = nodo === cortadoEn ? 'cortado' : 'completado'
  }
  return mapa
}
