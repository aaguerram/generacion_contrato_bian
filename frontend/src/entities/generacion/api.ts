import { http } from '@shared/api/http'
import type { EstadoEjecucion, Generacion, GeneracionCrear, Proveedores } from './modelo'

/** Única superficie de acceso a las generaciones. Las features llaman aquí, nunca a `fetch`. */
export const apiGeneraciones = {
  listar: (signal?: AbortSignal) =>
    http.get<{ total: number; generaciones: Generacion[] }>('/generaciones', signal),

  obtener: (id: string, signal?: AbortSignal) => http.get<Generacion>(`/generaciones/${id}`, signal),

  crear: (datos: GeneracionCrear) => http.post<Generacion>('/generaciones', datos),

  actualizar: (id: string, datos: GeneracionCrear) => http.put<Generacion>(`/generaciones/${id}`, datos),

  borrar: (id: string) => http.del<void>(`/generaciones/${id}`),

  /** Devuelve 202 al instante: la corrida sigue en el servidor sin límite de tiempo. */
  ejecutar: (id: string) => http.post<Generacion>(`/generaciones/${id}/ejecutar`),

  /**
   * Archiva esta generación y devuelve la COPIA que hereda su nombre. No ejecuta nada: deja la
   * siguiente versión lista, y es a ella a donde hay que navegar.
   */
  relanzar: (id: string) => http.post<Generacion>(`/generaciones/${id}/relanzar`),

  estado: (id: string, desde = 0, signal?: AbortSignal) =>
    http.get<EstadoEjecucion>(`/generaciones/${id}/estado?desde=${desde}`, signal),

  resultado: (id: string, signal?: AbortSignal) =>
    http.get<Record<string, unknown>>(`/generaciones/${id}/resultado`, signal),

  subirValidacion: (id: string, archivo: File) =>
    http.subir<Generacion>(`/generaciones/${id}/validacion`, archivo),

  quitarValidacion: (id: string) => http.del<Generacion>(`/generaciones/${id}/validacion`),

  proveedores: (signal?: AbortSignal) => http.get<Proveedores>('/proveedores', signal),
}
