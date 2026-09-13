# Pruebas E2E (LLM real, sin mocks)

Bajo demanda (nunca en la suite por defecto — llamadas LLM reales, consumen cuota):

```bash
EJECUTAR_E2E=1 .venv/Scripts/python -m unittest discover -s tests -p "test_e2e_*.py" -v
```

## Regla obligatoria para toda prueba E2E nueva

1. **Todos los archivos de test E2E viven en `tests/e2e/`** (este directorio). Todo lo compartido
   entre pruebas vive en `tests/e2e/shared/` (hoy: `e2e_common.py`).
2. **Prohibido hardcodear valores de negocio esperados en el `.py` del test** (nombre de Service
   Domain, operaciones, etc.). Esos valores viven en una corrida de referencia completa,
   `tests/resources/<caso>/expected-result.json`, curada a mano por quien arma el caso.
3. Cada `tests/resources/<caso>/` es autocontenida y trae **siempre estos 3 archivos**:
   - `<algo>.txt` / `.md` / `.markdown` — la(s) Historia(s) de Usuario del caso.
   - `funcionalidad-*.json` — la funcionalidad macro. Debe haber **exactamente uno** por carpeta
     (`ejecutar_caso()` lo autodescubre con un glob; si hay 0 o 2+, falla fuerte).
   - `expected-result.json` — una corrida de referencia **completa** (la MISMA forma que
     `mapeo-historias-service-domains.json`, es decir, un `ResultadoMapeoHistorias` serializado).
     Normalmente se arma copiando una corrida real ya validada como correcta. **Nunca lo escribe
     el pipeline.**
4. El pipeline real sigue escribiendo su salida completa
   (`mapeo-historias-service-domains.json`) en la misma carpeta en cada corrida — es el artefacto
   **actual**, inspeccionable, se sobreescribe. Es deliberadamente un archivo *distinto* del
   `expected-result.json` de arriba: comparar el resultado en memoria de la corrida contra un
   archivo que el mismo pipeline acaba de escribir sería una tautología (el test nunca podría
   fallar una vez que el pipeline corrió una sola vez).
5. Nunca apuntar a las carpetas compartidas `./HU` / `./ejemplos` de la raíz del proyecto: son
   para pruebas manuales del CLI, cambian de contenido libremente.

## Qué compara `verificar_candidatos_y_operaciones()`

Compara la corrida actual contra `expected-result.json` en dos ejes, e ignora deliberadamente todo
lo narrativo (razonamiento, justificacion, scores, escenarios_hu, evidence_refs, ...) que puede
variar de corrida a corrida (o de modelo a modelo) aunque el resultado de negocio sea el mismo:

1. **Los Service Domain relevantes por historia** — cada candidato directo o tentativo de la
   referencia debe seguir directo o tentativo. No se comparan los descartados porque son
   hipótesis negativas variables entre modelos del failover.
2. **Para cada Service Domain relevante, las operaciones requeridas** — cada operación de la
   referencia debe estar presente por `(operation_id, method, path, tipo, grupo)`. Se permite que
   la corrida actual ancle operaciones adicionales válidas.

Si la corrida real pierde un candidato relevante o una operación requerida, la prueba falla con
un mensaje que muestra requerido vs. actual.

## Cómo escribir una prueba E2E nueva

1. Crear `tests/resources/<caso>/` con su HU y su `funcionalidad-*.json`.
2. Correr el caso una vez con el failover real (`EJECUTAR_E2E=1` sobre esa carpeta), revisar que
   el `mapeo-historias-service-domains.json` resultante sea correcto, y copiarlo tal cual como
   `expected-result.json` en la misma carpeta — esa es la corrida de referencia.
3. Crear `tests/e2e/test_e2e_<caso>.py`:

   ```python
   from __future__ import annotations

   import unittest

   from e2e.shared.e2e_common import (
       cargar_esperado,
       ejecutar_caso,
       requiere_e2e,
       verificar_candidatos_y_operaciones,
   )

   _CARPETA = "<caso>"


   @requiere_e2e
   class TestE2E<Caso>(unittest.TestCase):
       def test_mismos_candidatos_y_operaciones_que_la_corrida_de_referencia(self):
           resultado = ejecutar_caso(_CARPETA)
           esperado = cargar_esperado(_CARPETA)
           verificar_candidatos_y_operaciones(self, resultado, esperado)
   ```

4. Si el caso necesita una verificación adicional que `verificar_candidatos_y_operaciones()` no
   cubre (p. ej. un campo de negocio puntual), agregarla **después** de llamarla, usando
   `resultado`/`esperado` directamente — no dupliques la lógica común, extiéndela en
   `e2e_common.py` si aplica a más de un caso.
