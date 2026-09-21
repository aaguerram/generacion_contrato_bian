import { RouterProvider } from 'react-router-dom'
import { LimiteDeError } from '@shared/ui/LimiteDeError'
import { router } from './router'
import './styles/global.css'

export function App() {
  return (
    <LimiteDeError>
      <RouterProvider router={router} />
    </LimiteDeError>
  )
}
