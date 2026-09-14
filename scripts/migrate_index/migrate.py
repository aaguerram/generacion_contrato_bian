"""Migra el índice de retrieval de una release BIAN a otra sin perder procedencia.

Una release nueva no invalida la anterior: puede haber corridas en curso, comparaciones históricas
o Service Domains retirados que aún aparecen en resultados ya publicados. Por eso migrar NO es
"borrar y reindexar": se crea la colección de la release destino, conviven las dos y se **reporta
explícitamente** qué SD se añadieron, cuáles desaparecieron y cuáles siguen, en vez de que la
diferencia se descubra en producción. El rollback es apuntar la configuración a la anterior.

Los vectores de la release nueva se generan desde su propio catálogo con `rebuild_index`: copiar
embeddings viejos sobre textos nuevos sería justo el tipo de dato inventado que este pipeline
evita en todo lo demás.

Uso:
    .venv/bin/python scripts/migrate_index/migrate.py --desde 14.0.0 --hasta 15.0.0
    .venv/bin/python scripts/migrate_index/migrate.py --desde 14.0.0 --hasta 15.0.0 \
        --catalogo-destino docs/BIAN_Service_Landscape_V15.0_Matrix_View.json --aplicar
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.adaptadores.salida.catalogo_json import CatalogoJson  # noqa: E402
from src.configuracion.settings import cargar_settings  # noqa: E402
from src.dominio.normalizacion import normalizar  # noqa: E402


def nombre_coleccion(base: str, release: str) -> str:
    """Una colección por release: conviven, y el rollback es cambiar de nombre."""
    return f"{base}_r{release.replace('.', '_')}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--desde", required=True, help="Release origen, p.ej. 14.0.0")
    p.add_argument("--hasta", required=True, help="Release destino, p.ej. 15.0.0")
    p.add_argument("--catalogo-destino", default="", help="Landscape de la release destino.")
    p.add_argument("--url", default="")
    p.add_argument("--aplicar", action="store_true", help="Sin esto solo informa (dry-run).")
    args = p.parse_args(argv)

    config = cargar_settings()
    url = args.url or config.mapear_historias.qdrant_url
    base = config.mapear_historias.qdrant_coleccion
    origen, destino = nombre_coleccion(base, args.desde), nombre_coleccion(base, args.hasta)

    catalogo_origen = CatalogoJson(config.ruta_catalogo_bian).cargar()
    actuales = {normalizar(e.service_domain): e.service_domain for e in catalogo_origen}
    if args.catalogo_destino:
        nuevos = {
            normalizar(e.service_domain): e.service_domain
            for e in CatalogoJson(args.catalogo_destino).cargar()
        }
    else:
        print(f"(sin --catalogo-destino: se asume el mismo catálogo para {args.hasta})")
        nuevos = dict(actuales)

    altas = sorted(nuevos[k] for k in nuevos.keys() - actuales.keys())
    bajas = sorted(actuales[k] for k in actuales.keys() - nuevos.keys())

    print(f"origen : {origen}  ({len(actuales)} SD)")
    print(f"destino: {destino}  ({len(nuevos)} SD)")
    print(f"  comunes: {len(actuales.keys() & nuevos.keys())}")
    print(f"  altas  : {len(altas)}  {altas[:5]}")
    print(f"  bajas  : {len(bajas)}  {bajas[:5]}")
    if bajas:
        print(
            "  ^ esos SD desaparecen del catálogo nuevo, pero los resultados ya publicados los "
            "siguen citando: la colección origen NO se borra."
        )

    if not args.aplicar:
        print("\ndry-run: nada escrito. Repetir con --aplicar.")
        return 0

    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("Falta qdrant-client: .venv/bin/python -m pip install qdrant-client")
        return 1

    cliente = QdrantClient(url=url, timeout=30.0)
    if not cliente.collection_exists(origen):
        print(f"\nLa colección origen '{origen}' no existe en {url}: nada que conservar.")
    else:
        print(f"\n'{origen}' se conserva intacta para rollback y comparación.")
    print(
        f"Siguiente paso — poblar la release destino desde SU catálogo:\n"
        f"  .venv/bin/python scripts/rebuild_index/rebuild.py --backend qdrant "
        f"--coleccion {destino}\n"
        f"y luego apuntar `mapear_historias.qdrant_coleccion: {destino}` en config.yaml."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
