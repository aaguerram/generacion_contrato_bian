import { useCallback, useState } from 'react'
import { apiGeneraciones, type Generacion, type GeneracionCrear } from '@entities/generacion'

/**
 * Guardar una generación. **Guardar no ejecuta nada**: deja el formulario persistido y habilita el
 * botón de ejecutar. Esa separación es deliberada — una corrida cuesta minutos y cuota de LLM, y
 * no debe dispararse por pulsar "guardar".
 */
export function useGuardarGeneracion() {
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const guardar = useCallback(
    async (datos: GeneracionCrear, id?: string): Promise<Generacion | null> => {
      setGuardando(true)
      setError('')
      try {
        return id ? await apiGeneraciones.actualizar(id, datos) : await apiGeneraciones.crear(datos)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'No se pudo guardar la generación')
        return null
      } finally {
        setGuardando(false)
      }
    },
    [],
  )

  return { guardar, guardando, error }
}
