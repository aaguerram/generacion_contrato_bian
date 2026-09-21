import { useEffect, useRef } from 'react'

/**
 * Ejecuta `tarea` cada `ms` mientras `activo` sea cierto.
 *
 * Existe porque la ejecución del pipeline NO tiene límite de tiempo: el servidor devuelve 202 y
 * la interfaz pregunta por el estado. Mantener una petición abierta durante minutos sería pedir
 * que algún intermediario la corte.
 *
 * El intervalo se reprograma DESPUÉS de que la tarea termina, no en paralelo: si una consulta
 * tarda más que el intervalo, no se apilan.
 */
export function usePoll(tarea: () => Promise<void> | void, ms: number, activo: boolean): void {
  const ref = useRef(tarea)
  ref.current = tarea

  useEffect(() => {
    if (!activo) return
    let vivo = true
    let id: ReturnType<typeof setTimeout>

    const ciclo = async () => {
      try {
        await ref.current()
      } catch {
        /* un fallo puntual de red no debe detener el seguimiento */
      }
      if (vivo) id = setTimeout(ciclo, ms)
    }
    id = setTimeout(ciclo, ms)
    return () => {
      vivo = false
      clearTimeout(id)
    }
  }, [ms, activo])
}
