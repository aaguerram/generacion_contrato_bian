/**
 * Vista MÍNIMA del `ResultadoMapeoHistorias` que publica el pipeline.
 *
 * A propósito no replica el modelo del dominio: la página solo lee lo que enseña, y todo lo demás
 * viaja en el JSON crudo que se puede descargar. Así un campo nuevo en el pipeline no rompe la
 * interfaz.
 */

export interface OperacionBian {
  operation_id: string
  method: string
  path: string
  tipo: string
  grupo: string
  justificacion?: string
  escenarios_hu?: string[]
  reason_codes?: string[]
}

export interface BqPersonalizado {
  operation_id?: string
  grupo_existente?: string
  clase_bom?: string
  atributo_bom?: string
  estado?: string
  justificacion?: string
}

export interface ServiceDomainAsignado {
  service_domain: string
  rol_contractual?: string
  dependency_kind?: string
  confianza?: number
  confianza_pct?: number
  grupo?: string
  decision_contractual?: string
  motivo_decision?: string
  business_area?: string
  business_domain?: string
  accion_objeto?: string
  justificacion?: string
  origen_candidato?: string
  operaciones_bian?: OperacionBian[]
  bq_personalizados_propuestos?: BqPersonalizado[]
  reason_codes?: string[]
  gaps?: string[]
}

/**
 * Una incidencia del pipeline. NO es una cadena: trae el motivo, a qué Service Domain se refiere y
 * qué se decidió. Tratarla como texto es lo que hacía reventar el render.
 */
export interface Incidencia {
  motivo?: string
  detalle?: string
  decision?: string
  resolucion?: string
  historia?: string
  service_domain_propuesto?: string
  [k: string]: unknown
}

export interface HistoriaResultado {
  archivo: string
  titulo?: string
  total_directos?: number
  total_tentativos?: number
  total_descartados?: number
  gaps?: string[]
  blocking_codes?: string[]
  incidencias?: Incidencia[]
  service_domains?: {
    candidatos_directos?: ServiceDomainAsignado[]
    candidatos_tentativos?: ServiceDomainAsignado[]
    candidatos_descartados?: ServiceDomainAsignado[]
  }
  service_domains_omitidos?: unknown[]
}

export interface ResultadoMapeo {
  funcionalidad_macro?: string
  detalle?: string
  total_historias?: number
  generado_en?: string
  parametros?: Record<string, unknown>
  metricas?: Record<string, unknown>
  incidencias?: Incidencia[]
  historias?: HistoriaResultado[]
  [k: string]: unknown
}

/** Los tres grupos, en el orden en que se leen. La clave es la del JSON. */
export const GRUPOS = [
  { clave: 'candidatos_directos', titulo: 'Directos', tono: 'ok' },
  { clave: 'candidatos_tentativos', titulo: 'Tentativos', tono: 'aviso' },
  { clave: 'candidatos_descartados', titulo: 'Descartados', tono: 'neutro' },
] as const

/** Métricas que merecen estar arriba, con su etiqueta en español. El resto va en la tabla larga. */
export const METRICAS_CLAVE: Array<[string, string]> = [
  ['operation_coverage_rate', 'Cobertura de operaciones'],
  ['operation_grounding_rate', 'Operaciones con evidencia'],
  ['data_coverage_rate', 'Datos requeridos cubiertos'],
  ['ownership_conflict_rate', 'Conflictos de propiedad'],
  ['candidate_drop_rate', 'Candidatos truncados'],
]

export function esTasa(clave: string): boolean {
  return clave.endsWith('_rate')
}

export function formatearMetrica(clave: string, valor: unknown): string {
  if (valor === null || valor === undefined) return 'no aplica'
  if (typeof valor === 'number') return esTasa(clave) ? `${(valor * 100).toFixed(0)} %` : String(valor)
  if (typeof valor === 'boolean') return valor ? 'sí' : 'no'
  if (typeof valor === 'string') return valor
  // Listas y objetos existen de verdad en `parametros` (la cadena de modelos, por ejemplo).
  // `String(objeto)` daría "[object Object]", que no informa de nada.
  if (Array.isArray(valor)) return valor.map((v) => formatearMetrica(clave, v)).join(' · ')
  try {
    return JSON.stringify(valor)
  } catch {
    return String(valor)
  }
}
