import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFlujo, type PasoNodo } from '@entities/flujo'

/**
 * Sigue el avance del grafo por el canal de eventos del servidor.
 *
 * Se usa `EventSource` y no un socket bidireccional porque la comunicación es de UNA sola
 * dirección: el servidor cuenta por qué nodo va y el cliente escucha. Eso deja menos superficie
 * expuesta y trae reconexión automática de serie.
 *
 * Al reconectar se pide `desde` el último paso visto y el servidor lo rellena desde la base, así
 * que perder la conexión no cuesta la corrida: el estado no vive en esta pestaña.
 */
export function useFlujoEnVivo(idGeneracion: string, corrida: string, activo: boolean) {
  const [pasos, setPasos] = useState<PasoNodo[]>([])
  const [conectado, setConectado] = useState(false)
  const ultimo = useRef(0)

  /** Reemplaza la lista con lo que diga el servidor. Es la versión buena, no un parche encima. */
  const recargar = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const lista = await apiFlujo.pasos(idGeneracion, signal)
        setPasos(lista)
        ultimo.current = lista.length ? Math.max(...lista.map((p) => p.id)) : 0
      } catch {
        /* si falla, se queda lo que ya había; el canal lo volverá a intentar */
      }
    },
    [idGeneracion],
  )

  const recordar = useCallback((nuevos: PasoNodo[]) => {
    if (nuevos.length === 0) return
    setPasos((previos) => {
      // Un paso se abre (`en_curso`) y luego se cierra: la segunda noticia REEMPLAZA a la primera.
      const porId = new Map(previos.map((p) => [p.id, p]))
      for (const p of nuevos) porId.set(p.id, p)
      return [...porId.values()].sort((a, b) => a.id - b.id)
    })
    ultimo.current = Math.max(ultimo.current, ...nuevos.map((p) => p.id))
  }, [])

  /**
   * Carga completa cuando no hay corrida viva.
   *
   * Cubre tres momentos y por eso depende de los tres valores: abrir la pantalla, cambiar de
   * corrida (volver a ejecutar) y, sobre todo, el FINAL de una corrida. Al terminar, la página
   * marca la generación como completada y esta pestaña cierra el canal; si los últimos avisos aún
   * venían de camino, se pierden y los nodos que estaban a mitad se quedarían girando para
   * siempre. Medido: 3 nodos en curso con la base diciendo que los 60 pasos estaban completos.
   */
  useEffect(() => {
    if (activo) return
    const ac = new AbortController()
    void recargar(ac.signal)
    return () => ac.abort()
  }, [idGeneracion, corrida, activo, recargar])

  // Lo que va pasando, mientras pasa.
  useEffect(() => {
    if (!activo) {
      setConectado(false)
      return
    }
    const fuente = new EventSource(`/api/generaciones/${idGeneracion}/eventos?desde=${ultimo.current}`)
    fuente.onopen = () => setConectado(true)
    fuente.addEventListener('paso', (e) => {
      try {
        recordar([JSON.parse((e as MessageEvent).data) as PasoNodo])
      } catch {
        /* un mensaje suelto ilegible no puede cortar el seguimiento */
      }
    })
    fuente.addEventListener('fin', () => {
      fuente.close()
      setConectado(false)
    })
    fuente.onerror = () => setConectado(false)
    return () => {
      fuente.close()
      setConectado(false)
    }
  }, [idGeneracion, corrida, activo, recordar])

  return { pasos, conectado }
}
