import { Component, type ErrorInfo, type ReactNode } from 'react'

/**
 * Corta la caída de una pantalla en el componente que falló.
 *
 * El resultado del pipeline es un JSON grande que evoluciona con el pipeline: un campo que cambia
 * de forma no debe dejar la página en blanco, porque entonces ni siquiera se puede navegar a la
 * pestaña que sí funciona ni descargar el JSON para ver qué pasó.
 */
export class LimiteDeError extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Fallo al renderizar', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="pb-aviso pb-aviso--error" role="alert">
        <strong>No se pudo dibujar esta sección.</strong> {this.state.error.message}
        <div style={{ marginTop: '.6rem' }}>
          <button className="pb-btn pb-btn--secundario pb-btn--sm" onClick={() => this.setState({ error: null })}>
            Reintentar
          </button>
        </div>
      </div>
    )
  }
}
