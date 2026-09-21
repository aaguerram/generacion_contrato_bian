import type { ButtonHTMLAttributes, ReactNode, TextareaHTMLAttributes, InputHTMLAttributes } from 'react'
import './ui.css'

type Variante = 'primario' | 'acento' | 'secundario' | 'fantasma' | 'peligro'

export function Boton({
  variante = 'primario',
  cargando = false,
  pequeno = false,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante
  cargando?: boolean
  pequeno?: boolean
}) {
  return (
    <button
      {...props}
      disabled={props.disabled || cargando}
      className={`pb-btn pb-btn--${variante}${pequeno ? ' pb-btn--sm' : ''}`}
    >
      {cargando && <span className="pb-spinner" aria-hidden="true" />}
      {children}
    </button>
  )
}

export function Tarjeta({
  titulo,
  sub,
  acciones,
  children,
}: {
  titulo?: ReactNode
  sub?: ReactNode
  acciones?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="pb-card">
      {(titulo || acciones) && (
        <header className="pb-card__titulo">
          {titulo && <h2>{titulo}</h2>}
          {sub && <span className="pb-card__sub">{sub}</span>}
          {acciones && <div style={{ marginLeft: 'auto', display: 'flex', gap: '.5rem' }}>{acciones}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function Campo({
  label,
  ayuda,
  error,
  children,
}: {
  label: string
  ayuda?: ReactNode
  error?: string
  children: ReactNode
}) {
  return (
    <label className="pb-campo">
      <span className="pb-campo__label">{label}</span>
      {children}
      {error ? (
        <span className="pb-campo__error">{error}</span>
      ) : (
        ayuda && <span className="pb-campo__ayuda">{ayuda}</span>
      )}
    </label>
  )
}

export function Entrada(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className="pb-input" />
}

export function AreaTexto(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className="pb-textarea" />
}

const ETIQUETA: Record<string, string> = {
  guardado: 'Guardado',
  ejecutando: 'Ejecutando',
  completado: 'Completado',
  fallido: 'Fallido',
}

export function Insignia({ estado }: { estado: string }) {
  return (
    <span className={`pb-badge pb-badge--${estado}`}>
      {estado === 'ejecutando' && <span className="pb-spinner" aria-hidden="true" />}
      {ETIQUETA[estado] ?? estado}
    </span>
  )
}

export function Aviso({ tipo, children }: { tipo: 'error' | 'ok' | 'info'; children: ReactNode }) {
  return (
    <div className={`pb-aviso pb-aviso--${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

export function Vacio({ children }: { children: ReactNode }) {
  return <div className="pb-vacio">{children}</div>
}
