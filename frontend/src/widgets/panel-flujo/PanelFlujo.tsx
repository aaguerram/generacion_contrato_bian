import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  apiFlujo,
  resumirPorNodo,
  type Grafo,
  type NodoGrafo,
  type PasoNodo,
} from '@entities/flujo'
import { estaVivo, type Generacion } from '@entities/generacion'
import { AccionEjecutar } from '@features/ejecutar-generacion/AccionEjecutar'
import { AvisoRelanzada } from '@features/relanzar-generacion/AvisoRelanzada'
import { useFlujoEnVivo } from '@features/seguir-flujo/useFlujoEnVivo'
import { Aviso, Boton, Tarjeta } from '@shared/ui'
import { colocar } from './layout'
import { ModalNodo } from './ModalNodo'
import { NodoFlujo, type DatosNodo } from './NodoFlujo'
import './flujo.css'

const TIPOS = { bian: NodoFlujo }

/**
 * La cámara del lienzo: encuadra al cargar y sigue al nodo que está corriendo.
 *
 * Dos cosas que hay que hacer y ninguna sale gratis:
 *
 * 1. El `fitView` de la primera carga se ejecuta antes de que el contenedor tenga su tamaño real
 *    (la pestaña acaba de montarse), así que encuadra contra una caja de cero y el grafo aparece
 *    fuera de vista. Medido: el lienzo quedaba en `translate(-881px, 193px)` con el primer nodo
 *    en x=-550. Por eso se reencuadra un cuadro después, cuando ya midió.
 * 2. El flujo entero cabe, pero a escala 0.3: sirve para ver la forma de la red, no para leer un
 *    nodo. Mientras hay una corrida, la cámara va detrás del nodo activo con zoom legible, que es
 *    lo que uno quiere mirar. En cuanto termina, vuelve la vista completa.
 */
function Camara({ cuantos, activo, vivo }: { cuantos: number; activo: string | null; vivo: boolean }) {
  const { fitView, getNode, setCenter } = useReactFlow()

  useEffect(() => {
    if (cuantos === 0) return
    const id = requestAnimationFrame(() => fitView({ padding: 0.12, duration: 300 }))
    return () => cancelAnimationFrame(id)
  }, [cuantos, fitView])

  useEffect(() => {
    if (!vivo || !activo) return
    const n = getNode(activo)
    if (!n) return
    const ancho = (n.measured?.width ?? 176) / 2
    const alto = (n.measured?.height ?? 58) / 2
    setCenter(n.position.x + ancho, n.position.y + alto, { zoom: 0.85, duration: 450 })
  }, [activo, vivo, getNode, setCenter])

  // Al acabar la corrida, la vista vuelve al conjunto: el recorrido entero es el resumen.
  useEffect(() => {
    if (vivo || cuantos === 0) return
    const id = setTimeout(() => fitView({ padding: 0.12, duration: 500 }), 300)
    return () => clearTimeout(id)
  }, [vivo, cuantos, fitView])

  return null
}

export function PanelFlujo({
  generacion,
  onCambio,
}: {
  generacion: Generacion
  onCambio: (g: Generacion) => void
}) {
  const [grafo, setGrafo] = useState<Grafo | null>(null)
  const [error, setError] = useState('')
  const [abierto, setAbierto] = useState<NodoGrafo | null>(null)
  const vivo = estaVivo(generacion)
  const { pasos, conectado } = useFlujoEnVivo(generacion.id, generacion.corrida, vivo)
  const [errorEjecutar, setErrorEjecutar] = useState('')

  useEffect(() => {
    const ac = new AbortController()
    apiFlujo
      .grafo(ac.signal)
      .then(setGrafo)
      .catch((e) => setError(e instanceof Error ? e.message : 'No se pudo leer el grafo'))
    return () => ac.abort()
  }, [])

  const cortadoEn = generacion.estado === 'detenido' ? generacion.opciones.detener_en : null
  const resumen = useMemo(() => resumirPorNodo(pasos, cortadoEn), [pasos, cortadoEn])
  const base = useMemo(() => (grafo ? colocar(grafo) : { nodos: [], aristas: [] }), [grafo])

  const nodos: Node[] = useMemo(
    () =>
      base.nodos.map((n) => {
        const info = n.data as unknown as NodoGrafo
        const r = resumen.get(info.id)
        return {
          ...n,
          data: {
            ...info,
            estadoVisual: r?.estado ?? 'apagado',
            repeticiones: r?.pasos.length ?? 0,
            ms: r?.ms ?? 0,
            esCorte: generacion.opciones.detener_en === info.id,
          } satisfies DatosNodo as unknown as Record<string, unknown>,
        }
      }),
    [base.nodos, resumen, generacion.opciones.detener_en],
  )

  // Una arista se ilumina cuando su ORIGEN ya corrió: así el camino recorrido se ve de un vistazo.
  const aristas: Edge[] = useMemo(
    () =>
      base.aristas.map((a) => {
        const origen = resumen.get(a.source)
        const activa = origen != null && origen.estado !== 'apagado'
        const puente = Boolean((a.data as { puente?: boolean } | undefined)?.puente)
        return {
          ...a,
          animated: origen?.estado === 'en_curso',
          className: [activa ? 'arista--activa' : 'arista--apagada', puente ? 'arista--puente' : '']
            .filter(Boolean)
            .join(' '),
        }
      }),
    [base.aristas, resumen],
  )

  // El último nodo que entró en ejecución. Es a donde mira la cámara mientras la corrida avanza.
  const enCurso = useMemo(() => {
    for (let i = pasos.length - 1; i >= 0; i--) {
      if (pasos[i].estado === 'en_curso') return pasos[i].nodo
    }
    return null
  }, [pasos])

  const porNodo = useCallback(
    (id: string): PasoNodo[] => resumen.get(id)?.pasos ?? [],
    [resumen],
  )

  const abrir = useCallback(
    (id: string) => {
      const info = grafo?.nodos.find((n) => n.id === id)
      if (info && info.tipo === 'nodo') setAbierto(info)
    },
    [grafo],
  )

  const marcarCorte = async (id: string) => {
    const info = grafo?.nodos.find((n) => n.id === id)
    if (!info || info.tipo !== 'nodo' || vivo) return
    const detener_en = generacion.opciones.detener_en === id ? null : id
    const { apiGeneraciones } = await import('@entities/generacion')
    onCambio(
      await apiGeneraciones.actualizar(generacion.id, {
        nombre: generacion.nombre,
        historias: generacion.historias,
        funcionalidad: generacion.funcionalidad,
        opciones: { ...generacion.opciones, detener_en },
      }),
    )
  }

  const corte = generacion.opciones.detener_en

  return (
    <Tarjeta
      titulo="Flujo de ejecución"
      sub={
        vivo
          ? conectado
            ? 'en vivo'
            : 'reconectando…'
          : `${pasos.length} paso(s) de la última corrida`
      }
      acciones={
        <>
          {corte && (
            <Boton variante="fantasma" pequeno onClick={() => void marcarCorte(corte)}>
              Quitar el corte
            </Boton>
          )}
          <AccionEjecutar
            generacion={generacion}
            onCambio={onCambio}
            onError={setErrorEjecutar}
            etiquetaEjecutar={corte ? `Ejecutar hasta ${corte}` : 'Ejecutar'}
            pequeno
          />
        </>
      }
    >
      {error && <Aviso tipo="error">{error}</Aviso>}
      {errorEjecutar && <Aviso tipo="error">{errorEjecutar}</Aviso>}
      <AvisoRelanzada generacion={generacion} />

      <p className="pb-campo__ayuda" style={{ marginTop: 0 }}>
        La red del flujo se ve entera desde el principio, apagada. Cada nodo se enciende cuando la
        corrida entra en él. Pulsa en un nodo para ver sus datos de entrada y salida.{' '}
        {vivo ? (
          <strong>Hay una corrida en curso: el corte no se puede cambiar ahora.</strong>
        ) : (
          <>
            Desde ahí también puedes pedir que la corrida <strong>se detenga</strong> al terminar
            ese nodo.
          </>
        )}
      </p>

      {corte && (
        <Aviso tipo="info">
          La próxima ejecución se detendrá al terminar <strong>{corte}</strong>. Lo que venga
          después no se ejecuta.
        </Aviso>
      )}
      {generacion.estado === 'detenido' && (
        <Aviso tipo="info">{generacion.error || 'Corrida detenida a petición.'}</Aviso>
      )}

      <div className="flujo">
        {grafo ? (
          <ReactFlowProvider>
          <ReactFlow
            nodes={nodos}
            edges={aristas}
            nodeTypes={TIPOS}
            onNodeClick={(_, n) => abrir(n.id)}
            fitView
            // El zoom mínimo por defecto de React Flow es 0.5, y el flujo entero en horizontal
            // mide más del doble del ancho del panel: con ese suelo, `fitView` no podía alejarse
            // lo suficiente y el grafo se salía del lienzo. Medido: 17 nodos, 7 visibles.
            minZoom={0.15}
            maxZoom={1.6}
            proOptions={{ hideAttribution: false }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
          >
            <Background gap={18} size={1} />
            <Controls showInteractive={false} />
            {/* Sin `nodeColor` el minimapa pinta los nodos con su color por defecto sobre fondo
                claro y se ve un rectángulo en blanco. Aquí además sirve de resumen: se ve por
                dónde va la corrida sin mirar el lienzo. */}
            <MiniMap
              pannable
              zoomable
              className="flujo__mapa"
              nodeStrokeWidth={2}
              nodeColor={(n) => {
                const e = (n.data as { estadoVisual?: string } | undefined)?.estadoVisual
                if (e === 'en_curso') return '#69be28'
                if (e === 'completado') return '#00693c'
                if (e === 'fallido') return '#b3261e'
                if (e === 'cortado') return '#b45309'
                if (e === 'interrumpido') return '#9a9a9a'
                return '#d9d9d9'
              }}
            />
            <Camara cuantos={nodos.length} activo={enCurso} vivo={vivo} />
          </ReactFlow>
          </ReactFlowProvider>
        ) : (
          <p className="pb-campo__ayuda">Cargando el grafo…</p>
        )}
      </div>

      <div className="flujo-leyenda">
        <span><i className="ap" /> sin ejecutar</span>
        <span><i className="ec" /> en curso</span>
        <span><i className="co" /> completado</span>
        <span><i className="fa" /> fallido</span>
        <span><i className="cr" /> corte</span>
        <span>Columna izquierda: el flujo principal. Columna derecha: el subgrafo de una historia.</span>
      </div>

      <ModalNodo
        nodo={abierto}
        pasos={abierto ? porNodo(abierto.id) : []}
        abierto={abierto !== null}
        esCorte={abierto?.id === corte}
        puedeCortar={!vivo}
        onCorte={(id) => {
          void marcarCorte(id)
          setAbierto(null)
        }}
        onCerrar={() => setAbierto(null)}
      />
    </Tarjeta>
  )
}
