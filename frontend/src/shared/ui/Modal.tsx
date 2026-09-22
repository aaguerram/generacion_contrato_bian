import { useEffect, useRef, type ReactNode } from 'react'
import './modal.css'

/**
 * Diálogo modal sobre el `<dialog>` del navegador.
 *
 * Se usa el elemento nativo y no un `div` flotante porque trae gratis lo que cuesta hacer bien a
 * mano: el foco queda atrapado dentro, Escape cierra, y el resto de la página queda inerte para
 * un lector de pantalla. Lo único que hay que añadir es cerrar al pulsar fuera.
 */
export function Modal({
  abierto,
  titulo,
  onCerrar,
  children,
  pie,
  ancho = false,
}: {
  abierto: boolean
  titulo: string
  onCerrar: () => void
  children: ReactNode
  pie?: ReactNode
  /** Caja ancha (72rem) para contenido que se lee en árbol o tabla. */
  ancho?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (abierto && !d.open) {
      d.showModal()
      // `showModal()` pone el foco en el primer elemento enfocable, que es el botón de cerrar:
      // abrir un formulario con el foco en "cerrar" obliga a tabular para empezar a escribir.
      d.querySelector<HTMLElement>('.modal__cuerpo input, .modal__cuerpo textarea, .modal__cuerpo select')?.focus()
    }
    if (!abierto && d.open) d.close()
  }, [abierto])

  if (!abierto) return null

  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={(e) => {
        // Escape: cerrar lo decide React, no el navegador, o el estado se queda desincronizado.
        e.preventDefault()
        onCerrar()
      }}
      onClick={(e) => {
        // Pulsar el fondo cierra. El propio <dialog> ES el fondo: dentro está el contenido.
        if (e.target === ref.current) onCerrar()
      }}
    >
      <div className={`modal__caja${ancho ? ' modal__caja--ancha' : ''}`}>
        <header className="modal__cab">
          <h2>{titulo}</h2>
          <button className="modal__cerrar" onClick={onCerrar} aria-label="Cerrar">
            ×
          </button>
        </header>
        <div className="modal__cuerpo">{children}</div>
        {pie && <footer className="modal__pie">{pie}</footer>}
      </div>
    </dialog>
  )
}
