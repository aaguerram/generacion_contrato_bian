import { useEffect, useState } from 'react'
import {
  apiIntentos,
  OPCIONES_POR_DEFECTO,
  type HistoriaEntrada,
  type Intento,
  type IntentoCrear,
  type OpcionesEjecucion,
  type Proveedores,
} from '@entities/intento'
import { ModalHistoria } from '@features/editar-historia/ModalHistoria'
import { Aviso, AreaTexto, Boton, Campo, Entrada, Tarjeta, Vacio } from '@shared/ui'
import { plural } from '@shared/lib/formato'
import './formulario.css'

/**
 * Pide exactamente lo mismo que la consola para UNA ejecución:
 *   --directorio-hu   → la lista de historias (una por elemento, con su título y su detalle)
 *   --funcionalidad   → label + detalle, que es el JSON que espera el CLI
 *   el resto de flags → el bloque de opciones avanzadas
 *
 * Las historias son una LISTA y se editan de una en una en un modal. La alternativa -- un solo
 * textarea con todo pegado y un separador -- obligaba a adivinar dónde empieza cada historia, y
 * partía por la mitad cualquiera cuyo detalle llevara una línea de guiones o un encabezado
 * Markdown, que es justo como se escribe una historia.
 */

/** Primera línea del detalle, para que la lista diga algo de cada historia sin abrirla. */
function resumen(h: HistoriaEntrada): string {
  const linea = h.detalle.split('\n').find((l) => l.trim())
  return linea ? linea.trim().slice(0, 120) : 'Sin detalle'
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
  const [historias, setHistorias] = useState<HistoriaEntrada[]>(inicial?.historias ?? [])
  // `null` = cerrado · `-1` = agregando · `n >= 0` = editando esa posición.
  const [editando, setEditando] = useState<number | null>(null)
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

  const faltaHistorias = historias.length === 0
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

  const guardarHistoria = (h: HistoriaEntrada) => {
    setHistorias((hs) => (editando != null && editando >= 0
      ? hs.map((x, i) => (i === editando ? h : x))
      : [...hs, h]))
    setEditando(null)
  }

  const borrarHistoria = (i: number) => {
    if (!window.confirm(`¿Quitar "${historias[i].titulo}" de la lista?`)) return
    setHistorias((hs) => hs.filter((_, n) => n !== i))
  }

  const mover = (i: number, salto: number) => {
    const j = i + salto
    if (j < 0 || j >= historias.length) return
    setHistorias((hs) => {
      const copia = [...hs]
      ;[copia[i], copia[j]] = [copia[j], copia[i]]
      return copia
    })
  }

  const set = <K extends keyof OpcionesEjecucion>(k: K, v: OpcionesEjecucion[K]) =>
    setOpciones((o) => ({ ...o, [k]: v }))

  const numero = (v: string): number | null => (v.trim() === '' ? null : Number(v))

  return (
    <form onSubmit={enviar} noValidate>
      {error && <Aviso tipo="error">{error}</Aviso>}

      <Tarjeta
        titulo="Historias de Usuario"
        sub={plural(historias.length, 'historia', 'historias')}
        acciones={
          <Boton type="button" variante="acento" pequeno onClick={() => setEditando(-1)}>
            Agregar historia
          </Boton>
        }
      >
        {historias.length === 0 ? (
          <Vacio>
            Todavía no hay historias. Pulsa <strong>Agregar historia</strong> y escribe su título y
            su detalle.
          </Vacio>
        ) : (
          <ol className="hu-lista">
            {historias.map((h, i) => (
              <li key={i} className="hu">
                <span className="hu__n">{i + 1}</span>
                <button
                  type="button"
                  className="hu__texto"
                  onClick={() => setEditando(i)}
                  title="Editar esta historia"
                >
                  <strong>{h.titulo}</strong>
                  <span>{resumen(h)}</span>
                </button>
                <div className="hu__acciones">
                  <button
                    type="button"
                    className="hu__icono"
                    onClick={() => mover(i, -1)}
                    disabled={i === 0}
                    aria-label={`Subir ${h.titulo}`}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="hu__icono"
                    onClick={() => mover(i, 1)}
                    disabled={i === historias.length - 1}
                    aria-label={`Bajar ${h.titulo}`}
                  >
                    ↓
                  </button>
                  <Boton type="button" variante="fantasma" pequeno onClick={() => setEditando(i)}>
                    Editar
                  </Boton>
                  <Boton type="button" variante="peligro" pequeno onClick={() => borrarHistoria(i)}>
                    Quitar
                  </Boton>
                </div>
              </li>
            ))}
          </ol>
        )}
        {tocado && faltaHistorias && (
          <p className="pb-campo__error">Agrega al menos una historia.</p>
        )}
      </Tarjeta>

      <ModalHistoria
        abierto={editando !== null}
        inicial={editando != null && editando >= 0 ? historias[editando] : undefined}
        indice={editando ?? undefined}
        onGuardar={guardarHistoria}
        onCerrar={() => setEditando(null)}
      />

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
