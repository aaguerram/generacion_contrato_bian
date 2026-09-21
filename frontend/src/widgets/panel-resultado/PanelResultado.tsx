import { useEffect, useState } from 'react'
import { apiIntentos, type Intento } from '@entities/intento'
import {
  GRUPOS,
  METRICAS_CLAVE,
  formatearMetrica,
  type Incidencia,
  type ResultadoMapeo,
  type ServiceDomainAsignado,
} from '@entities/resultado'
import { Aviso, Boton, Tarjeta, Vacio } from '@shared/ui'
import './resultado.css'

function pct(v: number | undefined): string {
  return v === undefined ? '—' : `${(v * 100).toFixed(1)} %`
}

function ListaIncidencias({ titulo, items }: { titulo: string; items: Incidencia[] }) {
  if (items.length === 0) return null
  return (
    <details className="incidencias">
      <summary>{titulo}</summary>
      <table className="tabla">
        <thead>
          <tr>
            <th>Motivo</th>
            <th>Service Domain</th>
            <th>Detalle</th>
            <th>Decisión</th>
          </tr>
        </thead>
        <tbody>
          {items.map((i, n) => (
            <tr key={n}>
              <td><code>{i.motivo ?? '—'}</code></td>
              <td>{i.service_domain_propuesto ?? '—'}</td>
              <td>{i.detalle ?? '—'}</td>
              <td>{i.decision ?? i.resolucion ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

function FichaSd({ sd }: { sd: ServiceDomainAsignado }) {
  const [abierto, setAbierto] = useState(false)
  const ops = sd.operaciones_bian ?? []
  const custom = sd.bq_personalizados_propuestos ?? []

  return (
    <article className="sd">
      <button className="sd__cab" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto}>
        <span className="sd__flecha" aria-hidden="true">{abierto ? '▾' : '▸'}</span>
        <span className="sd__nombre">{sd.service_domain}</span>
        <span className="sd__conf">{pct(sd.confianza)}</span>
      </button>

      <div className="sd__meta">
        {sd.rol_contractual && <span className="chip">{sd.rol_contractual}</span>}
        {sd.decision_contractual && <span className="chip chip--dec">{sd.decision_contractual}</span>}
        {sd.motivo_decision && <span className="chip chip--tenue">{sd.motivo_decision}</span>}
        {sd.dependency_kind && <span className="chip chip--tenue">{sd.dependency_kind}</span>}
        {ops.length > 0 && <span className="chip chip--op">{ops.length} operación(es)</span>}
      </div>

      {abierto && (
        <div className="sd__cuerpo">
          {(sd.business_area || sd.business_domain) && (
            <p className="sd__ruta">
              {sd.business_area} › {sd.business_domain}
            </p>
          )}
          {sd.accion_objeto && (
            <p className="sd__linea">
              <strong>Acción / objeto:</strong> {sd.accion_objeto}
            </p>
          )}
          {sd.justificacion && <p className="sd__linea">{sd.justificacion}</p>}

          {ops.length > 0 && (
            <table className="tabla">
              <thead>
                <tr>
                  <th>Operación</th>
                  <th>Método</th>
                  <th>Path</th>
                  <th>Tipo</th>
                  <th>Grupo</th>
                </tr>
              </thead>
              <tbody>
                {ops.map((o, i) => (
                  <tr key={`${o.operation_id}-${i}`}>
                    <td><code>{o.operation_id}</code></td>
                    <td><span className={`verbo verbo--${(o.method || '').toLowerCase()}`}>{o.method}</span></td>
                    <td className="tabla__path"><code>{o.path}</code></td>
                    <td>{o.tipo}</td>
                    <td>{o.grupo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {custom.length > 0 && (
            <div className="sd__custom">
              <strong>Behavior Qualifier propuestos (pendientes de revisión BIAN)</strong>
              <ul>
                {custom.map((b, i) => (
                  <li key={i}>
                    <code>{b.operation_id ?? '—'}</code> sobre <code>{b.grupo_existente ?? '—'}</code>
                    {b.clase_bom && <> · BOM {b.clase_bom}{b.atributo_bom ? `.${b.atributo_bom}` : ''}</>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(sd.reason_codes?.length || sd.gaps?.length) ? (
            <div className="sd__codigos">
              {sd.reason_codes?.map((c) => (
                <span key={c} className="chip chip--tenue">{c}</span>
              ))}
              {sd.gaps?.map((g, i) => (
                <p key={i} className="sd__gap">{g}</p>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </article>
  )
}

export function PanelResultado({ intento }: { intento: Intento }) {
  const [datos, setDatos] = useState<ResultadoMapeo | null>(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    if (!intento.tiene_resultado) {
      setDatos(null)
      return
    }
    const ac = new AbortController()
    setCargando(true)
    apiIntentos
      .resultado(intento.id, ac.signal)
      .then((d) => setDatos(d as ResultadoMapeo))
      .catch((e) => setError(e instanceof Error ? e.message : 'No se pudo leer el resultado'))
      .finally(() => setCargando(false))
    return () => ac.abort()
  }, [intento.id, intento.tiene_resultado, intento.terminado_en])

  if (!intento.tiene_resultado) {
    return (
      <Tarjeta titulo="Resultado">
        <Vacio>Todavía no hay resultado. Ejecuta el intento para generarlo.</Vacio>
      </Tarjeta>
    )
  }

  const metricas = datos?.metricas ?? {}
  const historias = datos?.historias ?? []

  return (
    <Tarjeta
      titulo="Resultado"
      acciones={
        <Boton
          variante="secundario"
          pequeno
          onClick={() => window.open(`/api/intentos/${intento.id}/resultado`, '_blank')}
        >
          Ver JSON completo
        </Boton>
      }
    >
      {error && <Aviso tipo="error">{error}</Aviso>}
      {cargando && !datos && <p className="pb-campo__ayuda">Cargando el resultado…</p>}

      {datos && (
        <>
          <div className="metricas">
            {METRICAS_CLAVE.filter(([k]) => k in metricas).map(([k, etiqueta]) => (
              <div key={k} className="metrica">
                <span className="metrica__valor">{formatearMetrica(k, metricas[k])}</span>
                <span className="metrica__etiqueta">{etiqueta}</span>
              </div>
            ))}
          </div>

          <ListaIncidencias
            titulo={`${datos.incidencias?.length ?? 0} incidencia(s) de la corrida`}
            items={datos.incidencias ?? []}
          />

          {historias.map((h) => (
            <div key={h.archivo} className="historia">
              <h3 className="historia__titulo">{h.titulo || h.archivo}</h3>
              <p className="historia__archivo">{h.archivo}</p>

              {GRUPOS.map(({ clave, titulo }) => {
                const lista = (h.service_domains?.[clave] ?? []) as ServiceDomainAsignado[]
                if (lista.length === 0) return null
                return (
                  <div key={clave} className="grupo">
                    <h4 className={`grupo__titulo grupo__titulo--${clave.replace('candidatos_', '')}`}>
                      {titulo} ({lista.length})
                    </h4>
                    {lista.map((sd) => (
                      <FichaSd key={sd.service_domain} sd={sd} />
                    ))}
                  </div>
                )
              })}

              <ListaIncidencias
                titulo={`${h.incidencias?.length ?? 0} incidencia(s) de esta historia`}
                items={h.incidencias ?? []}
              />
            </div>
          ))}

          <details className="incidencias">
            <summary>Todas las métricas y parámetros de la corrida</summary>
            <table className="tabla">
              <tbody>
                {Object.entries({ ...datos.parametros, ...metricas }).map(([k, v]) => (
                  <tr key={k}>
                    <td><code>{k}</code></td>
                    <td>{formatearMetrica(k, v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </Tarjeta>
  )
}
