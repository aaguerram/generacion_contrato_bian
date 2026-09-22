import { useCallback, useState } from 'react'
import { apiGeneraciones, type Generacion } from '@entities/generacion'

/**
 * Lanza la corrida. El servidor responde 202 de inmediato y sigue trabajando: el seguimiento lo
 * hace `PanelEjecucion` preguntando por el estado. Aquí NO se espera al resultado.
 */
export function useEjecutarGeneracion() {
  const [lanzando, setLanzando] = useState(false)
  const [error, setError] = useState('')

  const ejecutar = useCallback(async (id: string): Promise<Generacion | null> => {
    setLanzando(true)
    setError('')
    try {
      return await apiGeneraciones.ejecutar(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar la ejecución')
      return null
    } finally {
      setLanzando(false)
    }
  }, [])

  return { ejecutar, lanzando, error }
}
