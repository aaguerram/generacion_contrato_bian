/**
 * Tipos del dominio de la interfaz. Espejo de `api/modelos.py`, no del dominio del pipeline: la
 * página no debe acoplarse a la forma interna del mapeo.
 */

// 'detenido' no es un fallo: es el corte que se pidió antes de ejecutar.
export type EstadoGeneracion = 'guardado' | 'ejecutando' | 'completado' | 'fallido' | 'detenido'

/**
 * Una Historia de Usuario del formulario. Es una LISTA, no un texto pegado: cada historia tiene
 * su título y su detalle en campos propios, así que el servidor no tiene que adivinar dónde
 * empieza ninguna. El detalle puede llevar guiones o encabezados Markdown sin partir nada.
 */
export interface HistoriaEntrada {
  titulo: string
  detalle: string
}

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
  /** Nodo del grafo TRAS el cual se corta la corrida entera. `null` = flujo completo. */
  detener_en: string | null
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

export interface Generacion {
  id: string
  nombre: string
  creado_en: string
  actualizado_en: string
  estado: EstadoGeneracion
  historias: HistoriaEntrada[]
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
  /** Identificador de la última ejecución: los pasos del grafo se guardan por corrida. */
  corrida: string
  /** Id de la copia que heredó el nombre al relanzar. Con esto puesto, esta versión es historia. */
  relanzada_como: string
}

export interface GeneracionCrear {
  nombre: string
  historias: HistoriaEntrada[]
  funcionalidad: Funcionalidad
  opciones: OpcionesEjecucion
}

export interface EstadoEjecucion {
  id: string
  estado: EstadoGeneracion
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
  detener_en: null,
}

/** Una generación en curso es el único estado en el que la interfaz debe seguir preguntando. */
export const estaVivo = (g: Pick<Generacion, 'estado'>): boolean => g.estado === 'ejecutando'

/**
 * Qué acción admite una generación. Es UNA sola en cada momento, y de ahí sale qué botón se
 * pinta: una generación ejecutada no se vuelve a ejecutar encima de su propio resultado, y una
 * que ya cedió su nombre a una copia no admite nada, porque es un archivo histórico.
 */
export type AccionGeneracion = 'ejecutar' | 'relanzar' | 'ninguna'

export const accionDe = (g: Pick<Generacion, 'estado' | 'relanzada_como'>): AccionGeneracion =>
  g.relanzada_como ? 'ninguna' : g.estado === 'guardado' ? 'ejecutar' : 'relanzar'
