/**
 * Cliente HTTP. Una sola puerta de salida: si algún día la API cambia de origen o hay que añadir
 * una cabecera, se toca aquí y ningún otro archivo se entera.
 *
 * `signal` viaja hasta `fetch` y NO hay timeout por defecto a propósito: una ejecución del
 * pipeline tarda minutos, y el arranque de esa ejecución ya devuelve 202 al instante. Poner un
 * timeout genérico solo serviría para cortar una petición legítima.
 */

export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
  ) {
    super(mensaje)
    this.name = 'ErrorApi'
  }
}

const BASE = '/api'

async function leerError(res: Response): Promise<string> {
  try {
    const cuerpo = (await res.json()) as { detail?: unknown }
    if (typeof cuerpo?.detail === 'string') return cuerpo.detail
    if (cuerpo?.detail) return JSON.stringify(cuerpo.detail)
  } catch {
    /* la respuesta no era JSON: nos quedamos con el texto de estado */
  }
  return `${res.status} ${res.statusText}`
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${ruta}`, {
    ...init,
    headers:
      init?.body instanceof FormData
        ? init?.headers
        : { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) throw new ErrorApi(res.status, await leerError(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const http = {
  get: <T>(ruta: string, signal?: AbortSignal) => pedir<T>(ruta, { method: 'GET', signal }),
  post: <T>(ruta: string, cuerpo?: unknown, signal?: AbortSignal) =>
    pedir<T>(ruta, {
      method: 'POST',
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
      signal,
    }),
  put: <T>(ruta: string, cuerpo: unknown, signal?: AbortSignal) =>
    pedir<T>(ruta, { method: 'PUT', body: JSON.stringify(cuerpo), signal }),
  del: <T>(ruta: string, signal?: AbortSignal) => pedir<T>(ruta, { method: 'DELETE', signal }),
  subir: <T>(ruta: string, archivo: File, campo = 'archivo') => {
    const datos = new FormData()
    datos.append(campo, archivo)
    return pedir<T>(ruta, { method: 'POST', body: datos })
  },
}
