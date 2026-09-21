"""Módulo API — capa de entrada HTTP para el pipeline de generación de contratos BIAN.

**Aislado a propósito.** Este paquete consume `MapearHistoriasUseCase` a través del contenedor,
exactamente igual que lo hace el CLI (`src/adaptadores/entrada/cli_mapeo.py`), y NO añade ni
modifica nada de `src/`: ni un import de `api` dentro de `src`, ni una regla de negocio aquí.
Si algo de lo que hay en este paquete acaba siendo necesario para el mapeo, su sitio es `src/`.

Lo que sí es responsabilidad de esta capa:
  - materializar en disco lo que el CLI recibe como rutas (las HU y el JSON de funcionalidad);
  - guardar intentos para poder repetirlos y compararlos;
  - ejecutar el mapeo SIN límite de tiempo, en un hilo aparte, y dejar que el cliente pregunte
    por el estado (una corrida real tarda minutos y ninguna petición HTTP debe esperar tanto).
"""
