import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiIntentos, type Intento } from '@entities/intento'
import { Aviso, Boton, Insignia, Tarjeta, Vacio } from '@shared/ui'
import { duracion, fecha, plural } from '@shared/lib/formato'
import { usePoll } from '@shared/lib/usePoll'
import './lista.css'

export function ListaIntentosPage() {
  const navegar = useNavigate()
  const [intentos, setIntentos] = useState<Intento[] | null>(null)
  const [error, setError] = useState('')

  const cargar = useCallback(async (signal?: AbortSignal) => {
    try {
      const r = await apiIntentos.listar(signal)
      setIntentos(r.intentos)
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo leer la lista de intentos')
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    void cargar(ac.signal)
    return () => ac.abort()
  }, [cargar])

  // Mientras haya una corrida viva, la lista se refresca sola: el estado cambia en el servidor.
  const hayVivos = (intentos ?? []).some((i) => i.estado === 'ejecutando')
  usePoll(() => cargar(), 4000, hayVivos)

  const borrar = async (i: Intento) => {
    if (!window.confirm(`¿Borrar "${i.nombre}"? Se pierde su resultado y su registro.`)) return
    try {
      await apiIntentos.borrar(i.id)
      void cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo borrar el intento')
    }
  }

  return (
    <>
      <div className="pagina__cab">
        <div>
          <h1>Intentos</h1>
          <p>
            Cada intento guarda un lote de Historias de Usuario con su funcionalidad macro. Guardar
            no ejecuta nada; ejecutar lanza el mapeo a Service Domains.
          </p>
        </div>
        <Boton variante="acento" onClick={() => navegar('/intentos/nuevo')}>
          Nuevo intento
        </Boton>
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}

      {intentos === null && !error && <p className="pb-campo__ayuda">Cargando…</p>}

      {intentos?.length === 0 && (
        <Tarjeta>
          <Vacio>
            Todavía no hay intentos. Crea el primero con las Historias de Usuario que quieras
            mapear.
          </Vacio>
        </Tarjeta>
      )}

      <div className="rejilla">
        {intentos?.map((i) => (
          <article key={i.id} className="fila">
            <Link to={`/intentos/${i.id}`} className="fila__principal">
              <h2 className="fila__nombre">{i.nombre}</h2>
              <p className="fila__func">{i.funcionalidad.label || 'Sin funcionalidad'}</p>
              <div className="fila__datos">
                <span>{plural(i.historias_detectadas.length, 'historia', 'historias')}</span>
                <span>{fecha(i.creado_en)}</span>
                {i.segundos != null && <span>{duracion(i.segundos)}</span>}
                {i.tiene_validacion && <span>con validación</span>}
              </div>
            </Link>
            <div className="fila__lado">
              <Insignia estado={i.estado} />
              <Boton variante="peligro" pequeno onClick={() => void borrar(i)}>
                Borrar
              </Boton>
            </div>
          </article>
        ))}
      </div>
    </>
  )
}
