import { Link } from 'react-router-dom'
import type { Generacion } from '@entities/generacion'
import { Aviso } from '@shared/ui'

/**
 * Por qué esta generación ya no tiene botón de ejecutar.
 *
 * Sin esto, una versión archivada se ve igual que cualquier otra pero sin acciones, y no hay
 * forma de saber si falta algo o si es a propósito. El enlace lleva a la copia que heredó el
 * nombre, que es donde continúa el trabajo.
 */
export function AvisoRelanzada({ generacion }: { generacion: Generacion }) {
  if (!generacion.relanzada_como) return null
  return (
    <Aviso tipo="info">
      Esta versión quedó <strong>archivada</strong> con la fecha de su corrida. Su resultado se
      conserva tal cual y ya no se vuelve a ejecutar.{' '}
      <Link to={`/generaciones/${generacion.relanzada_como}`}>Abrir la versión nueva</Link>.
    </Aviso>
  )
}
