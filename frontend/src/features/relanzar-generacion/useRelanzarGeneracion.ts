import { useCallback, useState } from 'react'
import { apiGeneraciones, type Generacion } from '@entities/generacion'

/**
 * Prepara la siguiente versión de una generación ya ejecutada.
 *
 * No ejecuta nada: el servidor archiva la versión actual con la fecha de su corrida pegada al
 * nombre y devuelve una COPIA con el nombre limpio, las mismas historias y la misma definición
 * funcional. Ejecutarla es el paso siguiente, y lo decide quien mira.
 */
export function useRelanzarGeneracion() {
  const [relanzando, setRelanzando] = useState(false)
  const [error, setError] = useState('')

  const relanzar = useCallback(async (id: string): Promise<Generacion | null> => {
    setRelanzando(true)
    setError('')
    try {
      return await apiGeneraciones.relanzar(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo preparar la nueva versión')
      return null
    } finally {
      setRelanzando(false)
    }
  }, [])

  return { relanzar, relanzando, error }
}
