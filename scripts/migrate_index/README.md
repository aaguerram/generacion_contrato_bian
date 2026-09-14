# migrate_index

Mueve el índice de una release BIAN a otra **sin perder procedencia**.

Migrar no es "borrar y reindexar": puede haber corridas en curso, comparaciones históricas y
Service Domains retirados que los resultados ya publicados siguen citando. Por eso cada release
vive en su propia colección (`bian_service_domains_r14_0_0`, `..._r15_0_0`), las dos conviven y el
rollback es apuntar la configuración a la anterior.

```bash
# dry-run: informa altas, bajas y comunes; no escribe nada
.venv/bin/python scripts/migrate_index/migrate.py --desde 14.0.0 --hasta 15.0.0 \
    --catalogo-destino docs/BIAN_Service_Landscape_V15.0_Matrix_View.json

# prepara el destino (la colección origen se conserva)
.venv/bin/python scripts/migrate_index/migrate.py --desde 14.0.0 --hasta 15.0.0 \
    --catalogo-destino docs/... --aplicar
```

Los vectores de la release nueva **se generan desde su propio catálogo** con `rebuild_index`, no se
copian: reusar embeddings viejos sobre textos nuevos sería justo el tipo de dato inventado que este
pipeline evita.

Hoy solo existe la release 14.0.0, así que el dry-run reporta 341 comunes y 0 altas/bajas.
