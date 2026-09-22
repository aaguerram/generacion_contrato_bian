import { useEffect, useRef, useState } from 'react'
import { apiGeneraciones, estaVivo, type Generacion } from '@entities/generacion'
import { AccionEjecutar } from '@features/ejecutar-generacion/AccionEjecutar'
import { AvisoRelanzada } from '@features/relanzar-generacion/AvisoRelanzada'
import { Aviso, Insignia, Tarjeta } from '@shared/ui'
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
  generacion,
  onCambio,
}: {
  generacion: Generacion
  onCambio: (g: Generacion) => void
}) {
  const [error, setError] = useState('')
  const [log, setLog] = useState<string[]>([])
  const [transcurrido, setTranscurrido] = useState(0)
  const finLog = useRef<HTMLDivElement>(null)
  const vivo = estaVivo(generacion)

  // Cronómetro local: el servidor solo da la duración al terminar, y ver el tiempo correr es lo
  // que distingue "sigue trabajando" de "se colgó".
  useEffect(() => {
    if (!vivo || !generacion.iniciado_en) return
    const desde = new Date(generacion.iniciado_en).getTime()
    const id = setInterval(() => setTranscurrido((Date.now() - desde) / 1000), 1000)
    return () => clearInterval(id)
  }, [vivo, generacion.iniciado_en])

  usePoll(
    async () => {
      const e = await apiGeneraciones.estado(generacion.id)
      setLog(e.lineas_log)
      if (e.estado !== generacion.estado) onCambio(await apiGeneraciones.obtener(generacion.id))
    },
    2000,
    vivo,
  )

  useEffect(() => {
    finLog.current?.scrollIntoView({ block: 'nearest' })
  }, [log.length])

  // Al abrir una generación ya terminada, recupera el log de su última corrida.
  useEffect(() => {
    if (vivo) return
    apiGeneraciones
      .estado(generacion.id)
      .then((e) => setLog(e.lineas_log))
      .catch(() => undefined)
  }, [generacion.id, vivo])

  // La corrida nueva empieza con el panel en limpio: el log y el cronómetro que se ven son los
  // de la anterior y confundirían durante los primeros segundos.
  const alLanzar = (g: Generacion) => {
    setLog([])
    setTranscurrido(0)
    onCambio(g)
  }

  return (
    <Tarjeta
      titulo="Ejecución"
      sub={<Insignia estado={generacion.estado} />}
      acciones={
        <AccionEjecutar generacion={generacion} onCambio={alLanzar} onError={setError} />
      }
    >
      {error && <Aviso tipo="error">{error}</Aviso>}
      <AvisoRelanzada generacion={generacion} />
      {generacion.estado === 'fallido' && generacion.error && (
        <Aviso tipo="error">
          <strong>La corrida falló.</strong> {generacion.error}
        </Aviso>
      )}
      {generacion.estado === 'completado' && (
        <Aviso tipo="ok">Completado en {duracion(generacion.segundos)}.</Aviso>
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
