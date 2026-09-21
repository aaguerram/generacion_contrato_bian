import { NavLink, Outlet } from 'react-router-dom'
import './layout.css'

const enlaces = [
  { a: '/intentos', texto: 'Intentos' },
  { a: '/intentos/nuevo', texto: 'Nuevo intento' },
]

export function Layout() {
  return (
    <div className="app">
      <header className="cabecera">
        <div className="cabecera__inner">
          <NavLink to="/intentos" className="marca">
            <span className="marca__punto" aria-hidden="true" />
            <span className="marca__texto">
              Contratos <strong>BIAN</strong>
            </span>
          </NavLink>
          <nav className="nav">
            {enlaces.map((e) => (
              <NavLink
                key={e.a}
                to={e.a}
                end={e.a === '/intentos'}
                className={({ isActive }) => `nav__enlace${isActive ? ' nav__enlace--activo' : ''}`}
              >
                {e.texto}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="contenido">
        <Outlet />
      </main>

      <footer className="pie">
        Mapeo de Historias de Usuario a BIAN Service Domains · Service Landscape R14
      </footer>
    </div>
  )
}
