import { useRef, useState } from 'react'
import { apiGeneraciones, type Generacion } from '@entities/generacion'
import { Aviso, Boton } from '@shared/ui'

/**
 * Archivo de validación opcional: el resultado esperado con el que se comparará la corrida.
 * Se puede subir antes o después de ejecutar; si ya hay resultado, la comparación se recalcula
 * en la siguiente ejecución.
 */
export function SubirValidacion({
  generacion,
  onCambio,
}: {
  generacion: Generacion
  onCambio: (g: Generacion) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState('')

  const subir = async (archivo: File) => {
    setOcupado(true)
    setError('')
    try {
      onCambio(await apiGeneraciones.subirValidacion(generacion.id, archivo))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo subir el archivo')
    } finally {
      setOcupado(false)
      if (input.current) input.current.value = ''
    }
  }

  const quitar = async () => {
    setOcupado(true)
    setError('')
    try {
      onCambio(await apiGeneraciones.quitarValidacion(generacion.id))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo quitar el archivo')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <input
        ref={input}
        type="file"
        accept="application/json,.json"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) void subir(f)
        }}
      />
      {generacion.tiene_validacion ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '.6rem', flexWrap: 'wrap' }}>
          <span className="pb-badge pb-badge--completado">{generacion.nombre_validacion}</span>
          <Boton variante="fantasma" pequeno onClick={() => input.current?.click()} cargando={ocupado}>
            Reemplazar
          </Boton>
          <Boton variante="peligro" pequeno onClick={() => void quitar()} cargando={ocupado}>
            Quitar
          </Boton>
        </div>
      ) : (
        <div>
          <Boton variante="secundario" onClick={() => input.current?.click()} cargando={ocupado}>
            Subir archivo de validación
          </Boton>
          <p className="pb-campo__ayuda" style={{ marginTop: '.5rem' }}>
            Opcional. Un <code>mapeo-historias-service-domains.json</code> de una corrida ya
            validada. Se compararán los Service Domains y sus operaciones.
          </p>
        </div>
      )}
    </div>
  )
}
