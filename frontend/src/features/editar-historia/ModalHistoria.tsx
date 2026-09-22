import { useEffect, useState } from 'react'
import type { HistoriaEntrada } from '@entities/generacion'
import { AreaTexto, Boton, Campo, Entrada } from '@shared/ui'
import { Modal } from '@shared/ui/Modal'

const VACIA: HistoriaEntrada = { titulo: '', detalle: '' }

/**
 * Alta y edición de UNA Historia de Usuario. El mismo modal para las dos cosas: lo único que
 * cambia es si llega una historia inicial.
 */
export function ModalHistoria({
  abierto,
  inicial,
  indice,
  onGuardar,
  onCerrar,
}: {
  abierto: boolean
  /** La historia a editar, o nada para añadir una nueva. */
  inicial?: HistoriaEntrada
  /** Posición en la lista, solo para el título del diálogo. */
  indice?: number
  onGuardar: (h: HistoriaEntrada) => void
  onCerrar: () => void
}) {
  const [historia, setHistoria] = useState<HistoriaEntrada>(inicial ?? VACIA)
  const [tocado, setTocado] = useState(false)

  // Al abrirlo se recarga: si no, editar una historia y luego añadir otra arrastraría el texto.
  useEffect(() => {
    if (abierto) {
      setHistoria(inicial ?? VACIA)
      setTocado(false)
    }
  }, [abierto, inicial])

  const faltaTitulo = !historia.titulo.trim()

  const guardar = () => {
    setTocado(true)
    if (faltaTitulo) return
    onGuardar({ titulo: historia.titulo.trim(), detalle: historia.detalle })
  }

  return (
    <Modal
      abierto={abierto}
      titulo={inicial ? `Editar historia ${indice != null ? indice + 1 : ''}`.trim() : 'Agregar historia'}
      onCerrar={onCerrar}
      pie={
        <>
          <Boton variante="acento" onClick={guardar}>
            {inicial ? 'Guardar cambios' : 'Agregar'}
          </Boton>
          <Boton variante="fantasma" onClick={onCerrar}>
            Cancelar
          </Boton>
          <span className="pb-campo__ayuda" style={{ marginLeft: 'auto' }}>
            Esto solo edita la lista. La generación se guarda con su propio botón.
          </span>
        </>
      }
    >
      <Campo
        label="Título"
        ayuda="Cómo se reconoce la historia en la lista. También encabeza el archivo que lee el pipeline."
        error={tocado && faltaTitulo ? 'El título es obligatorio.' : ''}
      >
        <Entrada
          value={historia.titulo}
          maxLength={200}
          placeholder="Crear pantalla de datos personales"
          onChange={(e) => setHistoria((h) => ({ ...h, titulo: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              guardar()
            }
          }}
        />
      </Campo>

      <Campo
        label="Detalle"
        ayuda="El cuerpo de la historia, tal cual. Puede llevar guiones, viñetas o Markdown: aquí no se parte nada."
      >
        <AreaTexto
          rows={12}
          value={historia.detalle}
          placeholder={'Como usuario autenticado en la APP\nQuiero…\nPara…\n\nCriterios de aceptación:\n- …'}
          onChange={(e) => setHistoria((h) => ({ ...h, detalle: e.target.value }))}
        />
      </Campo>
    </Modal>
  )
}
