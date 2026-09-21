import { useCallback, useState } from 'react'
import { apiIntentos, type Intento, type IntentoCrear } from '@entities/intento'

/**
 * Guardar un intento. **Guardar no ejecuta nada**: deja el formulario persistido y habilita el
 * botón de ejecutar. Esa separación es deliberada — una corrida cuesta minutos y cuota de LLM, y
 * no debe dispararse por pulsar "guardar".
 */
export function useGuardarIntento() {
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const guardar = useCallback(
    async (datos: IntentoCrear, id?: string): Promise<Intento | null> => {
      setGuardando(true)
      setError('')
      try {
        return id ? await apiIntentos.actualizar(id, datos) : await apiIntentos.crear(datos)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'No se pudo guardar el intento')
        return null
      } finally {
        setGuardando(false)
      }
    },
    [],
  )

  return { guardar, guardando, error }
}
