import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { accionDe, estaVivo, type Generacion } from '@entities/generacion'
import { Boton } from '@shared/ui'
import { useEjecutarGeneracion } from './useEjecutarGeneracion'
import { useRelanzarGeneracion } from '@features/relanzar-generacion/useRelanzarGeneracion'

/**
 * El botón de ejecutar, con sus dos caras, en un solo sitio.
 *
 * Son dos acciones distintas y NO una que cambie de etiqueta: **Ejecutar** lanza la corrida de una
 * generación que nunca se ejecutó, y **Volver a ejecutar** no ejecuta nada — archiva esta versión
 * con la fecha de su corrida y abre una copia limpia que hereda el nombre. Una vez archivada, la
 * versión vieja no muestra ningún botón: su resultado es la prueba de aquella corrida y no se
 * machaca.
 *
 * Vive aquí y no en cada panel porque las pestañas Ejecución y Flujo tienen el mismo botón: dos
 * copias de esta regla se habrían separado a la primera.
 */
export function AccionEjecutar({
  generacion,
  onCambio,
  onError,
  etiquetaEjecutar = 'Ejecutar',
  pequeno = false,
}: {
  generacion: Generacion
  /** Se llama con la generación ACTUALIZADA cuando se lanza la corrida. */
  onCambio: (g: Generacion) => void
  /** Para el caso "Ejecutar hasta <nodo>" del panel de flujo. */
  etiquetaEjecutar?: string
  pequeno?: boolean
  /** El fallo se pinta donde el panel ya pinta los suyos: un botón no es sitio para un aviso. */
  onError?: (mensaje: string) => void
}) {
  const navegar = useNavigate()
  const { ejecutar, lanzando, error: errorEjecutar } = useEjecutarGeneracion()
  const { relanzar, relanzando, error: errorRelanzar } = useRelanzarGeneracion()
  const accion = accionDe(generacion)
  const vivo = estaVivo(generacion)

  const fallo = errorEjecutar || errorRelanzar
  useEffect(() => {
    if (fallo) onError?.(fallo)
  }, [fallo, onError])

  if (accion === 'ninguna') return null

  const lanzar = async () => {
    const g = await ejecutar(generacion.id)
    if (g) onCambio(g)
  }

  // La copia es la que se ejecuta, así que la página se va con ella. Quedarse en la vieja sería
  // mirar un archivo histórico con un botón que ya no hace nada.
  const abrirCopia = async () => {
    const copia = await relanzar(generacion.id)
    if (copia) navegar(`/generaciones/${copia.id}`)
  }

  return accion === 'ejecutar' ? (
    <Boton
      variante="acento"
      pequeno={pequeno}
      cargando={lanzando}
      disabled={vivo}
      onClick={() => void lanzar()}
    >
      {etiquetaEjecutar}
    </Boton>
  ) : (
    <Boton
      variante="secundario"
      pequeno={pequeno}
      cargando={relanzando}
      disabled={vivo}
      onClick={() => void abrirCopia()}
      title="Archiva esta versión con la fecha de su corrida y abre una copia lista para ejecutar"
    >
      Volver a ejecutar
    </Boton>
  )
}
