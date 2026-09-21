import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { EstadoVisual, NodoGrafo } from '@entities/flujo'

export interface DatosNodo extends NodoGrafo {
  estadoVisual: EstadoVisual
  repeticiones: number
  ms: number
  esCorte: boolean
  seleccionable: boolean
}

const ICONO: Record<EstadoVisual, string> = {
  apagado: '',
  en_curso: '',
  completado: '✓',
  fallido: '!',
  cortado: '■',
  interrumpido: '×',
}

/**
 * Un nodo del flujo. Apagado por defecto: la red entera se ve antes de ejecutar, y la corrida la
 * va encendiendo. El estado es una clase CSS, que es justo la razón de usar React Flow: el nodo
 * es un componente, no un dibujo.
 */
export function NodoFlujo({ data }: NodeProps) {
  const d = data as unknown as DatosNodo
  if (d.tipo !== 'nodo') {
    return (
      <div className={`nf-extremo nf-extremo--${d.tipo}`}>
        <Handle type="target" position={Position.Top} className="nf-handle" />
        {d.tipo === 'inicio' ? 'Inicio' : 'Fin'}
        {d.grafo === 'historia' && <em> historia</em>}
        <Handle type="source" position={Position.Bottom} className="nf-handle" />
      </div>
    )
  }

  return (
    <div
      className={[
        'nf',
        `nf--${d.estadoVisual}`,
        d.llm ? 'nf--llm' : '',
        d.esCorte ? 'nf--corte' : '',
        d.seleccionable ? 'nf--seleccionable' : '',
      ].join(' ')}
    >
      <Handle type="target" position={Position.Top} className="nf-handle" />
      <div className="nf__fila">
        <span className="nf__nombre">{d.etiqueta}</span>
        {ICONO[d.estadoVisual] && <span className="nf__icono">{ICONO[d.estadoVisual]}</span>}
      </div>
      <div className="nf__pie">
        {d.llm && <span className="nf__tag nf__tag--llm">LLM</span>}
        {d.abanico && <span className="nf__tag">abanico</span>}
        {d.repeticiones > 0 && <span className="nf__tag nf__tag--n">×{d.repeticiones}</span>}
        {d.ms > 0 && <span className="nf__ms">{(d.ms / 1000).toFixed(1)} s</span>}
        {d.esCorte && <span className="nf__tag nf__tag--corte">parar aquí</span>}
      </div>
      <Handle type="source" position={Position.Bottom} className="nf-handle" />
    </div>
  )
}
