import { useNavigate } from 'react-router-dom'
import type { GeneracionCrear } from '@entities/generacion'
import { useGuardarGeneracion } from '@features/guardar-generacion/useGuardarGeneracion'
import { FormularioGeneracion } from '@widgets/formulario-generacion/FormularioGeneracion'

export function NuevaGeneracionPage() {
  const navegar = useNavigate()
  const { guardar, guardando, error } = useGuardarGeneracion()

  const onGuardar = async (datos: GeneracionCrear) => {
    const g = await guardar(datos)
    // Guardar no ejecuta: lleva al detalle, que es donde aparece el botón de ejecutar.
    if (g) navegar(`/generaciones/${g.id}`)
  }

  return (
    <>
      <div className="pagina__cab">
        <div>
          <h1>Nueva generación</h1>
          <p>
            Pega todas las Historias de Usuario en una sola caja y describe la funcionalidad macro.
            Es la misma información que pide la consola.
          </p>
        </div>
      </div>
      <FormularioGeneracion guardando={guardando} error={error} onGuardar={(d) => void onGuardar(d)} />
    </>
  )
}
