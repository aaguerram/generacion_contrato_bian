# Caché BIAN oficial

Este directorio pertenece al proyecto y almacena evidencia normalizada por release y Service
Domain. `mapear-historias` reutiliza primero el contenido existente y descarga únicamente los
candidatos ausentes. `--actualizar-cache-bian` fuerza su actualización.

Cada JSON conserva URL oficial, commit, SHA-256, fecha de recuperación, operaciones y schemas.
Una falla de red sin evidencia previa produce `BIAN_EVIDENCE_UNAVAILABLE` y no un rechazo falso.
