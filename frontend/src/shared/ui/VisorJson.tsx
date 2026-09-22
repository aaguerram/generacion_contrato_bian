import { useMemo, useState } from 'react'
import { JsonEditor, type ExternalTriggers, type ThemeInput } from 'json-edit-react'
import './visor-json.css'

/** Hasta qué profundidad se abre el árbol al pintarlo. La raíz y su primer nivel bastan para
 *  orientarse; lo demás se abre a demanda. */
const PROFUNDIDAD_ABIERTA = 2

/** Una cadena más larga que esto se corta con "…" y se abre con un clic: un `service_role` o un
 *  prompt entero en una sola línea haría kilométrico el scroll horizontal. */
const CORTE_CADENAS = 200

/**
 * Los colores del árbol son variables del tema de la app, no valores fijos: así el modo oscuro
 * los cambia solo, igual que al resto de la interfaz. Los tokens `--json-*` viven en
 * `visor-json.css`.
 */
const TEMA: ThemeInput = {
  container: { backgroundColor: 'transparent', fontFamily: 'var(--mono)' },
  property: 'var(--json-clave)',
  bracket: { color: 'var(--texto-suave)', fontWeight: 600 },
  itemCount: { color: 'var(--texto-suave)', fontStyle: 'italic' },
  string: 'var(--json-cadena)',
  number: 'var(--json-numero)',
  boolean: { color: 'var(--json-booleano)', fontStyle: 'italic' },
  null: { color: 'var(--json-nulo)', fontStyle: 'italic' },
  iconCollection: 'var(--texto-suave)',
  iconCopy: 'var(--marca)',
  iconOk: 'var(--exito)',
  iconCancel: 'var(--error)',
  error: 'var(--error)',
}

/**
 * Visor de un JSON de solo lectura, en árbol plegable.
 *
 * Los datos de entrada y salida de un nodo del grafo pesan: el estado lleva la HU, la intención,
 * decenas de candidatos con su evidencia... Volcados como texto no se pueden recorrer, así que se
 * pintan con `json-edit-react` en modo lectura: cada objeto y lista se pliega y despliega (con Alt
 * pulsado, con todos sus hijos), el contador dice cuántos elementos esconde un nodo cerrado, y la
 * búsqueda filtra por clave o valor sin perder el contexto.
 *
 * El marco desplaza en los DOS ejes. Las cadenas no se parten por defecto (una línea por valor,
 * scroll a la derecha si no cabe) y se cortan a `CORTE_CADENAS`; "Ajustar líneas" las envuelve
 * para quien prefiera leer sin desplazarse.
 */
export function VisorJson({
  valor,
  nombreRaiz = '',
  altoMax,
}: {
  valor: unknown
  /** Etiqueta de la raíz; vacío = sin etiqueta. */
  nombreRaiz?: string
  /** Techo del marco con scroll (cualquier unidad CSS) fuera de un contenedor flex que ya le
   *  reparta el alto, como el cuerpo del modal ancho. Sin él, el marco crece con el árbol. */
  altoMax?: string
}) {
  const [busqueda, setBusqueda] = useState('')
  const [ajustar, setAjustar] = useState(false)
  const [copiado, setCopiado] = useState(false)
  // El disparador se consume por identidad: un objeto nuevo en cada clic, aunque el estado pedido
  // sea el mismo, o "plegar todo" dos veces seguidas no haría nada la segunda.
  const [disparador, setDisparador] = useState<ExternalTriggers | undefined>(undefined)

  const plegarTodo = (plegado: boolean) =>
    setDisparador({ collapse: { path: [], collapsed: plegado, includeChildren: true } })

  const texto = useMemo(() => JSON.stringify(valor, null, 2) ?? '', [valor])

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    } catch {
      /* sin portapapeles (http sin TLS, permisos): el botón simplemente no confirma */
    }
  }

  if (valor === null || valor === undefined) {
    return <p className="pb-campo__ayuda">Sin datos.</p>
  }

  const esColeccion = typeof valor === 'object'

  return (
    <div className="visor-json">
      <div className="visor-json__barra" role="toolbar" aria-label="Herramientas del JSON">
        <input
          type="search"
          className="visor-json__buscar"
          placeholder="Buscar clave o valor…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar en el JSON"
        />
        {esColeccion && (
          <>
            <button type="button" className="visor-json__btn" onClick={() => plegarTodo(false)}>
              Expandir todo
            </button>
            <button type="button" className="visor-json__btn" onClick={() => plegarTodo(true)}>
              Plegar todo
            </button>
          </>
        )}
        <label className="visor-json__check">
          <input type="checkbox" checked={ajustar} onChange={(e) => setAjustar(e.target.checked)} />
          Ajustar líneas
        </label>
        <button type="button" className="visor-json__btn" onClick={copiar}>
          {copiado ? 'Copiado ✓' : 'Copiar JSON'}
        </button>
        <span className="visor-json__tamano">{formatearTamano(texto.length)}</span>
      </div>

      <div
        className={`visor-json__marco${ajustar ? ' visor-json__marco--ajustar' : ''}`}
        style={altoMax ? { maxHeight: altoMax } : undefined}
      >
        <JsonEditor
          data={valor}
          viewOnly
          rootName={nombreRaiz}
          collapse={PROFUNDIDAD_ABIERTA}
          collapseAnimationTime={120}
          showCollectionCount="when-closed"
          showArrayIndices
          showStringQuotes
          stringTruncate={CORTE_CADENAS}
          enableClipboard
          showIconTooltips
          indent={2}
          rootFontSize="0.74rem"
          minWidth="100%"
          maxWidth="none"
          theme={TEMA}
          searchText={busqueda}
          searchFilter="all"
          externalTriggers={disparador}
          className="visor-json__arbol"
          translations={{
            ITEM_SINGLE: '{{count}} elemento',
            ITEMS_MULTIPLE: '{{count}} elementos',
            SHOW_LESS: '(mostrar menos)',
            EMPTY_STRING: '<cadena vacía>',
            TOOLTIP_COPY: 'Copiar al portapapeles',
          }}
        />
      </div>
    </div>
  )
}

function formatearTamano(caracteres: number): string {
  if (caracteres < 1024) return `${caracteres} car.`
  if (caracteres < 1024 * 1024) return `${(caracteres / 1024).toFixed(1)} KB`
  return `${(caracteres / (1024 * 1024)).toFixed(2)} MB`
}
