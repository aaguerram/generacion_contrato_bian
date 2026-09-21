import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiIntentos, type Intento, type IntentoCrear } from '@entities/intento'
import { useGuardarIntento } from '@features/guardar-intento/useGuardarIntento'
import { FormularioIntento } from '@widgets/formulario-intento/FormularioIntento'
import { PanelComparacion } from '@widgets/panel-comparacion/PanelComparacion'
import { PanelEjecucion } from '@widgets/panel-ejecucion/PanelEjecucion'
import { PanelResultado } from '@widgets/panel-resultado/PanelResultado'
import { Aviso, Boton, Insignia, Tarjeta } from '@shared/ui'
import { LimiteDeError } from '@shared/ui/LimiteDeError'
import { fecha, plural } from '@shared/lib/formato'
import './detalle.css'

type Pestana = 'ejecucion' | 'resultado' | 'validacion' | 'editar'

const PESTANAS: Array<[Pestana, string]> = [
  ['ejecucion', 'Ejecución'],
  ['resultado', 'Resultado'],
  ['validacion', 'Validación'],
  ['editar', 'Editar'],
]

export function DetalleIntentoPage() {
  const { id = '' } = useParams()
  const navegar = useNavigate()
  const [intento, setIntento] = useState<Intento | null>(null)
  const [error, setError] = useState('')
  const [pestana, setPestana] = useState<Pestana>('ejecucion')
  const { guardar, guardando, error: errorGuardar } = useGuardarIntento()

  const cargar = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setIntento(await apiIntentos.obtener(id, signal))
        setError('')
      } catch (e) {
        setError(e instanceof Error ? e.message : 'No se pudo abrir el intento')
      }
    },
    [id],
  )

  useEffect(() => {
    const ac = new AbortController()
    void cargar(ac.signal)
    return () => ac.abort()
  }, [cargar])

  const onGuardar = async (datos: IntentoCrear) => {
    const i = await guardar(datos, id)
    if (i) {
      setIntento(i)
      setPestana('ejecucion')
    }
  }

  if (error) {
    return (
      <>
        <Aviso tipo="error">{error}</Aviso>
        <Link to="/intentos">Volver a la lista</Link>
      </>
    )
  }
  if (!intento) return <p className="pb-campo__ayuda">Cargando…</p>

  return (
    <>
      <div className="pagina__cab">
        <div>
          <Link to="/intentos" className="volver">
            ← Intentos
          </Link>
          <h1>{intento.nombre}</h1>
          <p>
            {intento.funcionalidad.label || 'Sin funcionalidad'} ·{' '}
            {plural(intento.historias_detectadas.length, 'historia', 'historias')} · creado el{' '}
            {fecha(intento.creado_en)}
          </p>
        </div>
        <Insignia estado={intento.estado} />
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
            {clave === 'validacion' && intento.tiene_validacion && <span className="punto" />}
            {clave === 'resultado' && intento.tiene_resultado && <span className="punto" />}
          </button>
        ))}
      </nav>

      {pestana === 'ejecucion' && (
        <>
          <PanelEjecucion intento={intento} onCambio={setIntento} />
          <Tarjeta titulo="Historias de este intento">
            <ul className="historias">
              {intento.historias_detectadas.map((h) => (
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

      {pestana === 'resultado' && (
        <LimiteDeError>
          <PanelResultado intento={intento} />
        </LimiteDeError>
      )}
      {pestana === 'validacion' && <PanelComparacion intento={intento} onCambio={setIntento} />}
      {pestana === 'editar' && (
        <>
          {intento.estado === 'ejecutando' && (
            <Aviso tipo="info">
              Hay una corrida en curso. Los cambios que guardes se aplicarán a la siguiente
              ejecución.
            </Aviso>
          )}
          <FormularioIntento
            inicial={intento}
            guardando={guardando}
            error={errorGuardar}
            onGuardar={(d) => void onGuardar(d)}
          />
          <Tarjeta titulo="Zona peligrosa">
            <Boton
              variante="peligro"
              onClick={async () => {
                if (!window.confirm('¿Borrar este intento y su resultado?')) return
                await apiIntentos.borrar(intento.id)
                navegar('/intentos')
              }}
            >
              Borrar intento
            </Boton>
          </Tarjeta>
        </>
      )}
    </>
  )
}
