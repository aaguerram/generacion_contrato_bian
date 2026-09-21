import { useCallback, useState } from 'react'
import { apiIntentos, type Intento } from '@entities/intento'

/**
 * Lanza la corrida. El servidor responde 202 de inmediato y sigue trabajando: el seguimiento lo
 * hace `PanelEjecucion` preguntando por el estado. Aquí NO se espera al resultado.
 */
export function useEjecutarIntento() {
  const [lanzando, setLanzando] = useState(false)
  const [error, setError] = useState('')

  const ejecutar = useCallback(async (id: string): Promise<Intento | null> => {
    setLanzando(true)
    setError('')
    try {
      return await apiIntentos.ejecutar(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar la ejecución')
      return null
    } finally {
      setLanzando(false)
    }
  }, [])

  return { ejecutar, lanzando, error }
}
