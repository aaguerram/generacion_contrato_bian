import { createBrowserRouter, Navigate } from 'react-router-dom'
import { DetalleIntentoPage } from '@pages/detalle-intento/DetalleIntentoPage'
import { ListaIntentosPage } from '@pages/lista-intentos/ListaIntentosPage'
import { NuevoIntentoPage } from '@pages/nuevo-intento/NuevoIntentoPage'
import { Layout } from '@widgets/layout/Layout'

/**
 * Rutas de la aplicación. `/intentos/nuevo` va ANTES que `/intentos/:id` porque si no "nuevo" se
 * leería como un identificador.
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/intentos" replace /> },
      { path: 'intentos', element: <ListaIntentosPage /> },
      { path: 'intentos/nuevo', element: <NuevoIntentoPage /> },
      { path: 'intentos/:id', element: <DetalleIntentoPage /> },
      { path: '*', element: <Navigate to="/intentos" replace /> },
    ],
  },
])
