import { useEffect, useRef, useState } from 'react'
import { apiIntentos, estaVivo, type Intento } from '@entities/intento'
import { useEjecutarIntento } from '@features/ejecutar-intento/useEjecutarIntento'
import { Aviso, Boton, Insignia, Tarjeta } from '@shared/ui'
import { duracion } from '@shared/lib/formato'
import { usePoll } from '@shared/lib/usePoll'
import './ejecucion.css'

/**
 * Lanza la corrida y la sigue preguntando por su estado.
 *
 * No hay barra de progreso porque el pipeline no expone porcentaje: lo honesto es enseñar el log
 * real y el tiempo transcurrido. Una corrida puede tardar minutos y eso no es un error.
 */
export function PanelEjecucion({
  intento,
  onCambio,
}: {
  intento: Intento
  onCambio: (i: Intento) => void
}) {
  const { ejecutar, lanzando, error } = useEjecutarIntento()
  const [log, setLog] = useState<string[]>([])
  const [transcurrido, setTranscurrido] = useState(0)
  const finLog = useRef<HTMLDivElement>(null)
  const vivo = estaVivo(intento)

  // Cronómetro local: el servidor solo da la duración al terminar, y ver el tiempo correr es lo
  // que distingue "sigue trabajando" de "se colgó".
  useEffect(() => {
    if (!vivo || !intento.iniciado_en) return
    const desde = new Date(intento.iniciado_en).getTime()
    const id = setInterval(() => setTranscurrido((Date.now() - desde) / 1000), 1000)
    return () => clearInterval(id)
  }, [vivo, intento.iniciado_en])

  usePoll(
    async () => {
      const e = await apiIntentos.estado(intento.id)
      setLog(e.lineas_log)
      if (e.estado !== intento.estado) onCambio(await apiIntentos.obtener(intento.id))
    },
    2000,
    vivo,
  )

  useEffect(() => {
    finLog.current?.scrollIntoView({ block: 'nearest' })
  }, [log.length])

  // Al abrir un intento ya terminado, recupera el log de su última corrida.
  useEffect(() => {
    if (vivo) return
    apiIntentos
      .estado(intento.id)
      .then((e) => setLog(e.lineas_log))
      .catch(() => undefined)
  }, [intento.id, vivo])

  const lanzar = async () => {
    const i = await ejecutar(intento.id)
    if (i) {
      setLog([])
      setTranscurrido(0)
      onCambio(i)
    }
  }

  return (
    <Tarjeta
      titulo="Ejecución"
      sub={<Insignia estado={intento.estado} />}
      acciones={
        <Boton variante="acento" onClick={() => void lanzar()} cargando={lanzando} disabled={vivo}>
          {intento.estado === 'guardado' ? 'Ejecutar' : 'Volver a ejecutar'}
        </Boton>
      }
    >
      {error && <Aviso tipo="error">{error}</Aviso>}
      {intento.estado === 'fallido' && intento.error && (
        <Aviso tipo="error">
          <strong>La corrida falló.</strong> {intento.error}
        </Aviso>
      )}
      {intento.estado === 'completado' && (
        <Aviso tipo="ok">Completado en {duracion(intento.segundos)}.</Aviso>
      )}
      {vivo && (
        <Aviso tipo="info">
          En curso desde hace {duracion(transcurrido)}. El proceso no tiene límite de tiempo: puedes
          cerrar esta página y volver, la corrida sigue en el servidor.
        </Aviso>
      )}

      {log.length > 0 ? (
        <div className="log" role="log" aria-live="polite">
          {log.map((l, i) => (
            <div key={i} className={`log__linea${/ERROR|FAILED|Traceback/.test(l) ? ' log__linea--error' : /WARNING/.test(l) ? ' log__linea--aviso' : ''}`}>
              {l}
            </div>
          ))}
          <div ref={finLog} />
        </div>
      ) : (
        <p className="pb-campo__ayuda" style={{ margin: 0 }}>
          {vivo ? 'Esperando las primeras líneas…' : 'Sin registro de ejecución todavía.'}
        </p>
      )}
    </Tarjeta>
  )
}
