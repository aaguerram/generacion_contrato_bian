import { useEffect, useState } from 'react'
import { apiFlujo, type DetallePaso, type NodoGrafo, type PasoNodo } from '@entities/flujo'
import { Aviso, Boton } from '@shared/ui'
import { Modal } from '@shared/ui/Modal'
import { VisorJson } from '@shared/ui/VisorJson'
import { duracion } from '@shared/lib/formato'

type Pestana = 'entrada' | 'salida'

/**
 * Lo que hizo un nodo, en grande.
 *
 * Los datos de entrada y salida se piden AQUÍ y no con la lista de pasos: el estado de un nodo
 * incluye el catálogo de 341 Service Domains, así que traerlos todos para pintar colores serían
 * megabytes por corrida. El servidor además los resume antes de guardarlos, y lo que recorta lo
 * deja dicho en el propio dato.
 */
export function ModalNodo({
  nodo,
  pasos,
  abierto,
  esCorte,
  puedeCortar,
  onCorte,
  onCerrar,
}: {
  nodo: NodoGrafo | null
  pasos: PasoNodo[]
  abierto: boolean
  /** Este nodo es donde se ha pedido cortar la corrida. */
  esCorte: boolean
  /** Se puede cambiar el corte: no con una corrida en marcha. */
  puedeCortar: boolean
  onCorte: (id: string) => void
  onCerrar: () => void
}) {
  const [pestana, setPestana] = useState<Pestana>('salida')
  const [indice, setIndice] = useState(0)
  const [detalle, setDetalle] = useState<DetallePaso | null>(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    if (abierto) setIndice(0)
  }, [abierto, nodo?.id])

  const paso = pasos[indice]

  useEffect(() => {
    if (!abierto || !paso) {
      setDetalle(null)
      return
    }
    const ac = new AbortController()
    setCargando(true)
    setError('')
    apiFlujo
      .paso(paso.id, ac.signal)
      .then(setDetalle)
      .catch((e) => setError(e instanceof Error ? e.message : 'No se pudo leer el paso'))
      .finally(() => setCargando(false))
    return () => ac.abort()
  }, [abierto, paso?.id, paso])

  if (!nodo) return null

  return (
    <Modal
      abierto={abierto}
      ancho
      titulo={nodo.etiqueta}
      onCerrar={onCerrar}
      pie={
        <>
          {/* El corte se pone AQUÍ y no en el lienzo: mientras este diálogo está abierto el resto
              de la página queda inerte -- es lo que hace un `<dialog>` modal --, así que un doble
              clic sobre el nodo no llegaría nunca. */}
          {puedeCortar && (
            <Boton
              variante={esCorte ? 'peligro' : 'secundario'}
              onClick={() => onCorte(nodo.id)}
            >
              {esCorte ? 'Quitar el corte' : 'Detener la corrida aquí'}
            </Boton>
          )}
          <Boton variante="fantasma" onClick={onCerrar}>
            Cerrar
          </Boton>
          <span className="pb-campo__ayuda" style={{ marginLeft: 'auto' }}>
            {nodo.llm ? 'Este nodo llama al modelo.' : 'Nodo determinista: no llama al modelo.'}
          </span>
        </>
      }
    >
      {nodo.descripcion && <p className="nf-desc">{nodo.descripcion}</p>}

      {pasos.length === 0 ? (
        <Aviso tipo="info">Este nodo todavía no se ha ejecutado en esta corrida.</Aviso>
      ) : (
        <>
          {pasos.length > 1 && (
            <div className="nf-instancias">
              <span className="pb-campo__label">
                {pasos.length} ejecuciones de este nodo (abanico)
              </span>
              <div className="nf-instancias__lista">
                {pasos.map((p, i) => (
                  <button
                    key={p.id}
                    className={`nf-chip${i === indice ? ' nf-chip--activa' : ''}${p.estado === 'fallido' ? ' nf-chip--error' : ''}`}
                    onClick={() => setIndice(i)}
                  >
                    {p.instancia || `#${i + 1}`}
                  </button>
                ))}
              </div>
            </div>
          )}

          {paso && (
            <dl className="nf-meta">
              <div>
                <dt>Estado</dt>
                <dd>{paso.estado}</dd>
              </div>
              <div>
                <dt>Duración</dt>
                <dd>{paso.ms == null ? 'en curso' : duracion(paso.ms / 1000)}</dd>
              </div>
              <div>
                <dt>Modelo</dt>
                <dd>{paso.modelo ? `${paso.proveedor} · ${paso.modelo}` : '—'}</dd>
              </div>
              <div>
                <dt>Prompt</dt>
                <dd>{paso.prompt_id || '—'}</dd>
              </div>
            </dl>
          )}

          {paso?.error && <Aviso tipo="error">{paso.error}</Aviso>}
          {error && <Aviso tipo="error">{error}</Aviso>}

          <div className="nf-pestanas" role="tablist">
            {(['entrada', 'salida'] as Pestana[]).map((p) => (
              <button
                key={p}
                role="tab"
                aria-selected={pestana === p}
                className={`nf-pestanas__btn${pestana === p ? ' nf-pestanas__btn--activa' : ''}`}
                onClick={() => setPestana(p)}
              >
                {p === 'entrada' ? 'Datos de entrada' : 'Datos de salida'}
              </button>
            ))}
          </div>

          {cargando && !detalle ? (
            <p className="pb-campo__ayuda">Cargando el detalle…</p>
          ) : (
            // `key` por pestaña y paso: el árbol guarda qué nodos abrió el usuario, y ese estado es
            // de ESTE dato; al cambiar de pestaña o de ejecución se empieza de cero.
            <VisorJson
              key={`${paso?.id}-${pestana}`}
              valor={pestana === 'entrada' ? detalle?.entrada : detalle?.salida}
              nombreRaiz={pestana}
            />
          )}
        </>
      )}
    </Modal>
  )
}
