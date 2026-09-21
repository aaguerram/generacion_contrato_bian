import { http } from '@shared/api/http'
import type { EstadoEjecucion, Intento, IntentoCrear, Proveedores } from './modelo'

/** Única superficie de acceso a los intentos. Las features llaman aquí, nunca a `fetch`. */
export const apiIntentos = {
  listar: (signal?: AbortSignal) =>
    http.get<{ total: number; intentos: Intento[] }>('/intentos', signal),

  obtener: (id: string, signal?: AbortSignal) => http.get<Intento>(`/intentos/${id}`, signal),

  crear: (datos: IntentoCrear) => http.post<Intento>('/intentos', datos),

  actualizar: (id: string, datos: IntentoCrear) => http.put<Intento>(`/intentos/${id}`, datos),

  borrar: (id: string) => http.del<void>(`/intentos/${id}`),

  /** Devuelve 202 al instante: la corrida sigue en el servidor sin límite de tiempo. */
  ejecutar: (id: string) => http.post<Intento>(`/intentos/${id}/ejecutar`),

  estado: (id: string, desde = 0, signal?: AbortSignal) =>
    http.get<EstadoEjecucion>(`/intentos/${id}/estado?desde=${desde}`, signal),

  resultado: (id: string, signal?: AbortSignal) =>
    http.get<Record<string, unknown>>(`/intentos/${id}/resultado`, signal),

  subirValidacion: (id: string, archivo: File) =>
    http.subir<Intento>(`/intentos/${id}/validacion`, archivo),

  quitarValidacion: (id: string) => http.del<Intento>(`/intentos/${id}/validacion`),

  proveedores: (signal?: AbortSignal) => http.get<Proveedores>('/proveedores', signal),
}
