/** Formateo para la interfaz. Sin dependencias: son funciones puras sobre datos. */

export function fecha(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('es-EC', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Segundos legibles. Una corrida puede durar de 2 s a media hora, y "1834 s" no se lee. */
export function duracion(segundos: number | null | undefined): string {
  if (segundos == null) return '—'
  if (segundos < 60) return `${segundos.toFixed(1)} s`
  const m = Math.floor(segundos / 60)
  const s = Math.round(segundos % 60)
  return m < 60 ? `${m} min ${s} s` : `${Math.floor(m / 60)} h ${m % 60} min`
}

export function plural(n: number, singular: string, plural_: string): string {
  return `${n} ${n === 1 ? singular : plural_}`
}
