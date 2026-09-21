/**
 * Tipos del dominio de la interfaz. Espejo de `api/modelos.py`, no del dominio del pipeline: la
 * página no debe acoplarse a la forma interna del mapeo.
 */

export type EstadoIntento = 'guardado' | 'ejecutando' | 'completado' | 'fallido'

export interface Funcionalidad {
  label: string
  detalle: string
}

export interface OpcionesEjecucion {
  proveedor: string | null
  umbral_directo: number | null
  umbral_tentativo: number | null
  concurrencia: number | null
  sin_operaciones: boolean
  actualizar_cache_bian: boolean
}

export interface HistoriaDetectada {
  archivo: string
  titulo: string
  caracteres: number
}

export interface ResumenComparacion {
  disponible: boolean
  historias_comparadas: number
  service_domains_esperados: number
  service_domains_coincidentes: number
  faltantes: string[]
  inesperados: string[]
  operaciones_esperadas: number
  operaciones_coincidentes: number
  operaciones_faltantes: string[]
  detalle: string
}

export interface Intento {
  id: string
  nombre: string
  creado_en: string
  actualizado_en: string
  estado: EstadoIntento
  historias: string
  funcionalidad: Funcionalidad
  opciones: OpcionesEjecucion
  historias_detectadas: HistoriaDetectada[]
  tiene_validacion: boolean
  nombre_validacion: string
  iniciado_en: string | null
  terminado_en: string | null
  segundos: number | null
  error: string
  tiene_resultado: boolean
  comparacion: ResumenComparacion | null
}

export interface IntentoCrear {
  nombre: string
  historias: string
  funcionalidad: Funcionalidad
  opciones: OpcionesEjecucion
}

export interface EstadoEjecucion {
  id: string
  estado: EstadoIntento
  segundos: number | null
  error: string
  lineas_log: string[]
}

export interface Proveedores {
  disponibles: string[]
  cadena_por_defecto: string[]
}

export const OPCIONES_POR_DEFECTO: OpcionesEjecucion = {
  proveedor: null,
  umbral_directo: null,
  umbral_tentativo: null,
  concurrencia: null,
  sin_operaciones: false,
  actualizar_cache_bian: false,
}

/** Un intento en curso es el único estado en el que la interfaz debe seguir preguntando. */
export const estaVivo = (i: Pick<Intento, 'estado'>): boolean => i.estado === 'ejecutando'
