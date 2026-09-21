import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@app/App'

const raiz = document.getElementById('root')
if (!raiz) throw new Error('Falta el elemento #root en index.html')

createRoot(raiz).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
