import type { Generacion } from '@entities/generacion'
import { SubirValidacion } from '@features/subir-validacion/SubirValidacion'
import { Aviso, Tarjeta, Vacio } from '@shared/ui'
import './comparacion.css'

function Barra({ hechos, total, etiqueta }: { hechos: number; total: number; etiqueta: string }) {
  const p = total === 0 ? 0 : Math.round((hechos / total) * 100)
  return (
    <div className="barra">
      <div className="barra__cab">
        <span>{etiqueta}</span>
        <strong>
          {hechos} / {total}
        </strong>
      </div>
      <div className="barra__pista">
        <div
          className={`barra__relleno${p === 100 ? ' barra__relleno--completo' : ''}`}
          style={{ width: `${p}%` }}
        />
      </div>
    </div>
  )
}

function Lista({ titulo, items, tono }: { titulo: string; items: string[]; tono: string }) {
  if (items.length === 0) return null
  return (
    <div className={`lista lista--${tono}`}>
      <h4>
        {titulo} ({items.length})
      </h4>
      <ul>
        {items.map((i, n) => (
          <li key={n}>{i}</li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Compara la corrida contra el archivo de validación que subió el usuario.
 *
 * La comparación es informativa, nunca bloquea: lo "inesperado" puede ser cobertura nueva y no un
 * error. Solo lo FALTANTE señala una regresión.
 */
export function PanelComparacion({
  generacion,
  onCambio,
}: {
  generacion: Generacion
  onCambio: (g: Generacion) => void
}) {
  const c = generacion.comparacion

  return (
    <Tarjeta titulo="Validación">
      <SubirValidacion generacion={generacion} onCambio={onCambio} />

      {generacion.tiene_validacion && !c && (
        <Vacio>
          Hay archivo de validación pero todavía no hay comparación. Ejecuta la generación para
          contrastar el resultado.
        </Vacio>
      )}

      {c && (
        <div className="comparacion">
          <Aviso
            tipo={
              c.service_domains_coincidentes === c.service_domains_esperados &&
              c.operaciones_coincidentes === c.operaciones_esperadas
                ? 'ok'
                : 'info'
            }
          >
            {c.detalle}
          </Aviso>

          <div className="comparacion__barras">
            <Barra
              etiqueta="Service Domains esperados encontrados"
              hechos={c.service_domains_coincidentes}
              total={c.service_domains_esperados}
            />
            <Barra
              etiqueta="Operaciones esperadas encontradas"
              hechos={c.operaciones_coincidentes}
              total={c.operaciones_esperadas}
            />
          </div>

          <p className="comparacion__nota">
            {c.historias_comparadas} historia(s) comparada(s). Se contrastan Service Domains
            directos y tentativos, y sus operaciones por identificador, método, path, tipo y grupo.
            Lo narrativo se ignora a propósito porque cambia entre corridas.
          </p>

          <Lista titulo="Faltan en el resultado" items={c.faltantes} tono="error" />
          <Lista titulo="Operaciones que faltan" items={c.operaciones_faltantes} tono="error" />
          <Lista titulo="Aparecen de más" items={c.inesperados} tono="info" />
        </div>
      )}
    </Tarjeta>
  )
}
