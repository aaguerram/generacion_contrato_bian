import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiGeneraciones, type Generacion } from '@entities/generacion'
import { Aviso, Boton, Insignia, Tarjeta, Vacio } from '@shared/ui'
import { duracion, fecha, plural } from '@shared/lib/formato'
import { usePoll } from '@shared/lib/usePoll'
import './lista.css'

export function ListaGeneracionesPage() {
  const navegar = useNavigate()
  const [generaciones, setGeneraciones] = useState<Generacion[] | null>(null)
  const [error, setError] = useState('')

  const cargar = useCallback(async (signal?: AbortSignal) => {
    try {
      const r = await apiGeneraciones.listar(signal)
      setGeneraciones(r.generaciones)
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo leer la lista de generaciones')
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    void cargar(ac.signal)
    return () => ac.abort()
  }, [cargar])

  // Mientras haya una corrida viva, la lista se refresca sola: el estado cambia en el servidor.
  const hayVivos = (generaciones ?? []).some((g) => g.estado === 'ejecutando')
  usePoll(() => cargar(), 4000, hayVivos)

  const borrar = async (g: Generacion) => {
    if (!window.confirm(`¿Borrar "${g.nombre}"? Se pierde su resultado y su registro.`)) return
    try {
      await apiGeneraciones.borrar(g.id)
      void cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo borrar la generación')
    }
  }

  return (
    <>
      <div className="pagina__cab">
        <div>
          <h1>Generaciones</h1>
          <p>
            Cada generación guarda un lote de Historias de Usuario con su funcionalidad macro. Guardar
            no ejecuta nada; ejecutar lanza el mapeo a Service Domains.
          </p>
        </div>
        <Boton variante="acento" onClick={() => navegar('/generaciones/nueva')}>
          Nueva generación
        </Boton>
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}

      {generaciones === null && !error && <p className="pb-campo__ayuda">Cargando…</p>}

      {generaciones?.length === 0 && (
        <Tarjeta>
          <Vacio>
            Todavía no hay generaciones. Crea la primera con las Historias de Usuario que quieras
            mapear.
          </Vacio>
        </Tarjeta>
      )}

      <div className="rejilla">
        {generaciones?.map((g) => (
          // Una versión archivada se lee igual pero pesa menos: el ojo va a las vivas, que son
          // las que se pueden ejecutar. Se atenúa la fila entera menos la etiqueta que explica
          // por qué, porque una fila apagada sin motivo parece un error de carga.
          <article key={g.id} className={`fila${g.relanzada_como ? ' fila--archivada' : ''}`}>
            <Link to={`/generaciones/${g.id}`} className="fila__principal">
              <h2 className="fila__nombre">
                {g.nombre}
                {g.relanzada_como && <span className="fila__etiqueta">archivada</span>}
              </h2>
              <p className="fila__func">{g.funcionalidad.label || 'Sin funcionalidad'}</p>
              <div className="fila__datos">
                <span>{plural(g.historias_detectadas.length, 'historia', 'historias')}</span>
                <span>{fecha(g.creado_en)}</span>
                {g.segundos != null && <span>{duracion(g.segundos)}</span>}
                {g.tiene_validacion && <span>con validación</span>}
              </div>
            </Link>
            <div className="fila__lado">
              <Insignia estado={g.estado} />
              <Boton variante="peligro" pequeno onClick={() => void borrar(g)}>
                Borrar
              </Boton>
            </div>
          </article>
        ))}
      </div>
    </>
  )
}
