import { http } from '@shared/api/http'
import type { DetallePaso, Grafo, PasoNodo } from './modelo'

export const apiFlujo = {
  /** La topología no cambia entre corridas, así que se pide una vez y se guarda. */
  grafo: (signal?: AbortSignal) => http.get<Grafo>('/grafo', signal),

  /** Los pasos ya registrados, sin datos: es para pintar colores, no para leer contenidos. */
  pasos: (idIntento: string, signal?: AbortSignal) =>
    http.get<PasoNodo[]>(`/intentos/${idIntento}/pasos`, signal),

  /** Un paso CON su entrada y su salida. Se pide solo cuando alguien abre un nodo. */
  paso: (idPaso: number, signal?: AbortSignal) => http.get<DetallePaso>(`/pasos/${idPaso}`, signal),
}
