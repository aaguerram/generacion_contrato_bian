import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiGeneraciones, type Generacion, type GeneracionCrear } from '@entities/generacion'
import { useGuardarGeneracion } from '@features/guardar-generacion/useGuardarGeneracion'
import { FormularioGeneracion } from '@widgets/formulario-generacion/FormularioGeneracion'
import { PanelComparacion } from '@widgets/panel-comparacion/PanelComparacion'
import { PanelEjecucion } from '@widgets/panel-ejecucion/PanelEjecucion'
import { PanelFlujo } from '@widgets/panel-flujo/PanelFlujo'
import { PanelResultado } from '@widgets/panel-resultado/PanelResultado'
import { Aviso, Boton, Insignia, Tarjeta } from '@shared/ui'
import { LimiteDeError } from '@shared/ui/LimiteDeError'
import { fecha, plural } from '@shared/lib/formato'
import { usePoll } from '@shared/lib/usePoll'
import './detalle.css'

type Pestana = 'ejecucion' | 'flujo' | 'resultado' | 'validacion' | 'editar'

const PESTANAS: Array<[Pestana, string]> = [
  ['ejecucion', 'Ejecución'],
  ['flujo', 'Flujo'],
  ['resultado', 'Resultado'],
  ['validacion', 'Validación'],
  ['editar', 'Editar'],
]

export function DetalleGeneracionPage() {
  const { id = '' } = useParams()
  const navegar = useNavigate()
  const [generacion, setGeneracion] = useState<Generacion | null>(null)
  const [error, setError] = useState('')
  const [pestana, setPestana] = useState<Pestana>('ejecucion')
  const { guardar, guardando, error: errorGuardar } = useGuardarGeneracion()

  const cargar = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setGeneracion(await apiGeneraciones.obtener(id, signal))
        setError('')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'No se pudo abrir la generación')
      }
    },
    [id],
  )

  useEffect(() => {
    const ac = new AbortController()
    void cargar(ac.signal)
    return () => ac.abort()
  }, [cargar])

  // Mientras hay una corrida, el estado se refresca AQUÍ y no dentro de una pestaña: si el
  // seguimiento viviera en la pestaña de ejecución, mirar el flujo mientras corre dejaría a la
  // página sin enterarse de que terminó.
  usePoll(
    async () => {
      const g = await apiGeneraciones.obtener(id)
      setGeneracion((previo) =>
        previo && g.estado === previo.estado && g.corrida === previo.corrida ? previo : g,
      )
    },
    3000,
    generacion?.estado === 'ejecutando',
  )

  const onGuardar = async (datos: GeneracionCrear) => {
    const g = await guardar(datos, id)
    if (g) {
      setGeneracion(g)
      setPestana('ejecucion')
    }
  }

  if (error) {
    return (
      <>
        <Aviso tipo="error">{error}</Aviso>
        <Link to="/generaciones">Volver a la lista</Link>
      </>
    )
  }
  if (!generacion) return <p className="pb-campo__ayuda">Cargando…</p>

  return (
    <>
      <div className="pagina__cab">
        <div>
          <Link to="/generaciones" className="volver">
            ← Generaciones
          </Link>
          <h1>{generacion.nombre}</h1>
          <p>
            {generacion.funcionalidad.label || 'Sin funcionalidad'} ·{' '}
            {plural(generacion.historias_detectadas.length, 'historia', 'historias')} · creado el{' '}
            {fecha(generacion.creado_en)}
          </p>
        </div>
        <Insignia estado={generacion.estado} />
      </div>

      <nav className="pestanas" role="tablist">
        {PESTANAS.map(([clave, texto]) => (
          <button
            key={clave}
            role="tab"
            aria-selected={pestana === clave}
            className={`pestanas__btn${pestana === clave ? ' pestanas__btn--activa' : ''}`}
            onClick={() => setPestana(clave)}
          >
            {texto}
            {clave === 'validacion' && generacion.tiene_validacion && <span className="punto" />}
            {clave === 'resultado' && generacion.tiene_resultado && <span className="punto" />}
          </button>
        ))}
      </nav>

      {pestana === 'ejecucion' && (
        <>
          <PanelEjecucion generacion={generacion} onCambio={setGeneracion} />
          <Tarjeta titulo="Historias de esta generación">
            <ul className="historias">
              {generacion.historias_detectadas.map((h) => (
                <li key={h.archivo}>
                  <strong>{h.titulo}</strong>
                  <span>
                    {h.archivo} · {h.caracteres} caracteres
                  </span>
                </li>
              ))}
            </ul>
            <p className="pb-campo__ayuda">
              Un archivo por historia, en el orden de la lista. Es lo que el pipeline lee como
              directorio de Historias de Usuario. Para cambiarlas, usa la pestaña de editar.
            </p>
          </Tarjeta>
        </>
      )}

      {pestana === 'flujo' && (
        <LimiteDeError>
          <PanelFlujo generacion={generacion} onCambio={setGeneracion} />
        </LimiteDeError>
      )}

      {pestana === 'resultado' && (
        <LimiteDeError>
          <PanelResultado generacion={generacion} />
        </LimiteDeError>
      )}
      {pestana === 'validacion' && <PanelComparacion generacion={generacion} onCambio={setGeneracion} />}
      {pestana === 'editar' && (
        <>
          {generacion.estado === 'ejecutando' && (
            <Aviso tipo="info">
              Hay una corrida en curso. Los cambios que guardes se aplicarán a la siguiente
              ejecución.
            </Aviso>
          )}
          <FormularioGeneracion
            inicial={generacion}
            guardando={guardando}
            error={errorGuardar}
            onGuardar={(d) => void onGuardar(d)}
          />
          <Tarjeta titulo="Zona peligrosa">
            <Boton
              variante="peligro"
              onClick={async () => {
                if (!window.confirm('¿Borrar esta generación y su resultado?')) return
                await apiGeneraciones.borrar(generacion.id)
                navegar('/generaciones')
              }}
            >
              Borrar generación
            </Boton>
          </Tarjeta>
        </>
      )}
    </>
  )
}
