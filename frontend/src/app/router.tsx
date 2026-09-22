import { createBrowserRouter, Navigate } from 'react-router-dom'
import { DetalleGeneracionPage } from '@pages/detalle-generacion/DetalleGeneracionPage'
import { ListaGeneracionesPage } from '@pages/lista-generaciones/ListaGeneracionesPage'
import { NuevaGeneracionPage } from '@pages/nueva-generacion/NuevaGeneracionPage'
import { Layout } from '@widgets/layout/Layout'

/**
 * Rutas de la aplicación. `/generaciones/nueva` va ANTES que `/generaciones/:id` porque si no "nueva" se
 * leería como un identificador.
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/generaciones" replace /> },
      { path: 'generaciones', element: <ListaGeneracionesPage /> },
      { path: 'generaciones/nueva', element: <NuevaGeneracionPage /> },
      { path: 'generaciones/:id', element: <DetalleGeneracionPage /> },
      { path: '*', element: <Navigate to="/generaciones" replace /> },
    ],
  },
])
