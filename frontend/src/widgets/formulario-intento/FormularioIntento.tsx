import { useEffect, useMemo, useState } from 'react'
import {
  apiIntentos,
  OPCIONES_POR_DEFECTO,
  type Intento,
  type IntentoCrear,
  type OpcionesEjecucion,
  type Proveedores,
} from '@entities/intento'
import { Aviso, AreaTexto, Boton, Campo, Entrada, Tarjeta } from '@shared/ui'
import { plural } from '@shared/lib/formato'
import './formulario.css'

/**
 * Pide exactamente lo mismo que la consola para UNA ejecución:
 *   --directorio-hu   → el textarea de historias (todas pegadas; el servidor las separa)
 *   --funcionalidad   → label + detalle, que es el JSON que espera el CLI
 *   el resto de flags → el bloque de opciones avanzadas
 */

const SEPARADORES = ['---', '## Título de la historia', 'HU-01: ...']

/** Mismo criterio que `api/historias.py`: solo separa un marcador EXPLÍCITO. */
function contarHistorias(texto: string): number {
  const t = texto.replace(/\r\n/g, '\n').trim()
  if (!t) return 0
  const re = /^[ \t]*(?:[-=_*]{3,}|#{1,2}[ \t]+\S.*|HU[ _-]?\d+[ \t]*[:.-].*)[ \t]*$/gim
  const cortes = [...t.matchAll(re)].map((m) => m.index ?? 0)
  if (cortes.length === 0) return 1
  const limites = [...new Set([0, ...cortes, t.length])].sort((a, b) => a - b)
  let n = 0
  for (let i = 0; i < limites.length - 1; i++) {
    const bloque = t.slice(limites[i], limites[i + 1])
    if (bloque.replace(/[-=_*#\s]/g, '')) n++
  }
  return n
}

export function FormularioIntento({
  inicial,
  guardando,
  error,
  onGuardar,
}: {
  inicial?: Intento
  guardando: boolean
  error?: string
  onGuardar: (datos: IntentoCrear) => void
}) {
  const [nombre, setNombre] = useState(inicial?.nombre ?? '')
  const [historias, setHistorias] = useState(inicial?.historias ?? '')
  const [label, setLabel] = useState(inicial?.funcionalidad.label ?? '')
  const [detalle, setDetalle] = useState(inicial?.funcionalidad.detalle ?? '')
  const [opciones, setOpciones] = useState<OpcionesEjecucion>(
    inicial?.opciones ?? OPCIONES_POR_DEFECTO,
  )
  const [avanzadas, setAvanzadas] = useState(false)
  const [proveedores, setProveedores] = useState<Proveedores | null>(null)
  const [tocado, setTocado] = useState(false)

  useEffect(() => {
    const ac = new AbortController()
    apiIntentos.proveedores(ac.signal).then(setProveedores).catch(() => setProveedores(null))
    return () => ac.abort()
  }, [])

  const nHistorias = useMemo(() => contarHistorias(historias), [historias])
  const faltaHistorias = !historias.trim()
  const faltaLabel = !label.trim()
  const invalido = faltaHistorias || faltaLabel

  const enviar = (e: React.FormEvent) => {
    e.preventDefault()
    setTocado(true)
    if (invalido) return
    onGuardar({
      nombre: nombre.trim(),
      historias,
      funcionalidad: { label: label.trim(), detalle },
      opciones,
    })
  }

  const set = <K extends keyof OpcionesEjecucion>(k: K, v: OpcionesEjecucion[K]) =>
    setOpciones((o) => ({ ...o, [k]: v }))

  const numero = (v: string): number | null => (v.trim() === '' ? null : Number(v))

  return (
    <form onSubmit={enviar} noValidate>
      {error && <Aviso tipo="error">{error}</Aviso>}

      <Tarjeta titulo="Historias de Usuario" sub={plural(nHistorias, 'historia', 'historias')}>
        <Campo
          label="Contenido de las historias"
          error={tocado && faltaHistorias ? 'Pega al menos una historia.' : undefined}
          ayuda={
            <>
              Pega todas las historias aquí. Para mandar varias, sepáralas con una línea{' '}
              {SEPARADORES.map((s, i) => (
                <span key={s}>
                  {i > 0 && ' o '}
                  <code>{s}</code>
                </span>
              ))}
              . Sin separador, todo el texto se trata como una sola historia.
            </>
          }
        >
          <AreaTexto
            value={historias}
            onChange={(e) => setHistorias(e.target.value)}
            rows={16}
            placeholder={'Como usuario autenticado…\nQuiero…\nPara…\n\n---\n\nComo usuario…'}
            spellCheck={false}
          />
        </Campo>
      </Tarjeta>

      <div style={{ height: '1rem' }} />

      <Tarjeta titulo="Funcionalidad macro" sub="El contexto común a todas las historias">
        <Campo
          label="Funcionalidad"
          error={tocado && faltaLabel ? 'La funcionalidad es obligatoria.' : undefined}
          ayuda="El nombre corto de la funcionalidad que agrupa estas historias."
        >
          <Entrada
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Actualización de datos personales"
          />
        </Campo>
        <Campo label="Detalle" ayuda="Descripción larga: qué permite hacer y con qué restricciones.">
          <AreaTexto
            value={detalle}
            onChange={(e) => setDetalle(e.target.value)}
            rows={4}
            placeholder="Permitir que el cliente actualice su número celular y correo electrónico…"
          />
        </Campo>
      </Tarjeta>

      <div style={{ height: '1rem' }} />

      <Tarjeta
        titulo="Opciones de ejecución"
        sub="Las mismas de la consola"
        acciones={
          <Boton type="button" variante="fantasma" pequeno onClick={() => setAvanzadas((v) => !v)}>
            {avanzadas ? 'Ocultar' : 'Mostrar'}
          </Boton>
        }
      >
        {avanzadas ? (
          <>
            <div className="form-grid">
              <Campo label="Proveedor LLM" ayuda="Vacío = la cadena de failover de config.yaml.">
                <select
                  className="pb-select"
                  value={opciones.proveedor ?? ''}
                  onChange={(e) => set('proveedor', e.target.value || null)}
                >
                  <option value="">
                    {proveedores?.cadena_por_defecto.length
                      ? `Cadena por defecto (${proveedores.cadena_por_defecto.join(' → ')})`
                      : 'Cadena por defecto'}
                  </option>
                  {(proveedores?.disponibles ?? []).map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo label="Concurrencia" ayuda="Historias en paralelo.">
                <Entrada
                  type="number"
                  min={1}
                  max={16}
                  value={opciones.concurrencia ?? ''}
                  onChange={(e) => set('concurrencia', numero(e.target.value))}
                  placeholder="config.yaml"
                />
              </Campo>
              <Campo label="Umbral directo" ayuda="Score mínimo para candidato directo.">
                <Entrada
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={opciones.umbral_directo ?? ''}
                  onChange={(e) => set('umbral_directo', numero(e.target.value))}
                  placeholder="0.90"
                />
              </Campo>
              <Campo label="Umbral tentativo" ayuda="Score mínimo para candidato tentativo.">
                <Entrada
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={opciones.umbral_tentativo ?? ''}
                  onChange={(e) => set('umbral_tentativo', numero(e.target.value))}
                  placeholder="0.63"
                />
              </Campo>
            </div>
            <label className="form-check">
              <input
                type="checkbox"
                checked={opciones.sin_operaciones}
                onChange={(e) => set('sin_operaciones', e.target.checked)}
              />
              <span>
                Sin operaciones <em>— omite el paso que ancla operaciones oficiales BIAN</em>
              </span>
            </label>
            <label className="form-check">
              <input
                type="checkbox"
                checked={opciones.actualizar_cache_bian}
                onChange={(e) => set('actualizar_cache_bian', e.target.checked)}
              />
              <span>
                Actualizar caché BIAN <em>— descarga de la fuente oficial aunque ya esté en caché</em>
              </span>
            </label>
          </>
        ) : (
          <p className="pb-campo__ayuda" style={{ margin: 0 }}>
            Se usará la configuración de <code>config.yaml</code>.
          </p>
        )}
      </Tarjeta>

      <div style={{ height: '1rem' }} />

      <Tarjeta titulo="Identificación" sub="Opcional">
        <Campo label="Nombre del intento" ayuda="Para reconocerlo en la lista. Si lo dejas vacío se usa la funcionalidad.">
          <Entrada
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder={label || 'Mi intento'}
          />
        </Campo>
      </Tarjeta>

      <div className="form-acciones">
        <Boton type="submit" cargando={guardando}>
          {inicial ? 'Guardar cambios' : 'Guardar intento'}
        </Boton>
        <span className="pb-campo__ayuda">
          Guardar no ejecuta nada. El botón de ejecutar aparece después de guardar.
        </span>
      </div>
    </form>
  )
}
