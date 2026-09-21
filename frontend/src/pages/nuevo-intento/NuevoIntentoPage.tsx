import { useNavigate } from 'react-router-dom'
import type { IntentoCrear } from '@entities/intento'
import { useGuardarIntento } from '@features/guardar-intento/useGuardarIntento'
import { FormularioIntento } from '@widgets/formulario-intento/FormularioIntento'

export function NuevoIntentoPage() {
  const navegar = useNavigate()
  const { guardar, guardando, error } = useGuardarIntento()

  const onGuardar = async (datos: IntentoCrear) => {
    const i = await guardar(datos)
    // Guardar no ejecuta: lleva al detalle, que es donde aparece el botón de ejecutar.
    if (i) navegar(`/intentos/${i.id}`)
  }

  return (
    <>
      <div className="pagina__cab">
        <div>
          <h1>Nuevo intento</h1>
          <p>
            Pega todas las Historias de Usuario en una sola caja y describe la funcionalidad macro.
            Es la misma información que pide la consola.
          </p>
        </div>
      </div>
      <FormularioIntento guardando={guardando} error={error} onGuardar={(d) => void onGuardar(d)} />
    </>
  )
}
