"""Reconstruye el índice de recuperación desde las fuentes locales de `docs/`.

Backends:
  - `memoria`  (por defecto): reconstruye el cache del `RecuperadorVectorial` en `.cache/`, que es
    el que usa el pipeline sin infraestructura externa. Sirve para precalentar antes de una
    corrida y para comprobar que los embeddings responden.
  - `qdrant`: sube los 341 Service Domains a la colección de Qdrant que levanta
    `infra/retrieval/docker-compose.yml` (perfil `qdrant`), con su payload para filtrar.

Lo que se indexa por Service Domain es `EntradaCatalogo.texto_para_indexar()`: nombre, jerarquía,
clasificación, rol, ejemplo de uso, features, resumen y documentación. El payload lleva además
Business Area/Domain y el patrón funcional, para poder filtrar por release o área sin volver a
consultar el catálogo.

Sin red salvo la del proveedor de embeddings. Idempotente: recrear la colección deja el mismo
contenido (los ids son deterministas, derivados del nombre canónico del SD).

Uso:
    .venv/bin/python scripts/rebuild_index/rebuild.py                      # memoria (.cache/)
    .venv/bin/python scripts/rebuild_index/rebuild.py --backend qdrant     # Qdrant local
    .venv/bin/python scripts/rebuild_index/rebuild.py --backend qdrant --snapshot
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from src.adaptadores.salida.catalogo_json import CatalogoJson  # noqa: E402
from src.adaptadores.salida.recuperador_qdrant import COLECCION_POR_DEFECTO  # noqa: E402
from src.configuracion.contenedor import _embeddings  # noqa: E402
from src.configuracion.settings import cargar_settings  # noqa: E402
from src.dominio.normalizacion import normalizar  # noqa: E402


def _id_determinista(service_domain: str) -> int:
    """Qdrant acepta enteros o UUID; un hash estable del nombre hace la carga idempotente."""
    return int(hashlib.sha256(normalizar(service_domain).encode()).hexdigest()[:15], 16)


def _reconstruir_memoria(config, catalogo) -> int:
    from src.adaptadores.salida.recuperador_vectorial import RecuperadorVectorial

    emb, modelo = _embeddings(config, None)
    recuperador = RecuperadorVectorial(catalogo, emb, modelo_embeddings=modelo)
    # Una consulta cualquiera fuerza la construcción y el volcado del cache en `.cache/`.
    recuperador.recuperar("calentar indice", 1)
    print(f"índice en memoria reconstruido con embeddings '{modelo}' (cache en .cache/)")
    return 0


def _reconstruir_qdrant(config, catalogo, url: str, coleccion: str, snapshot: bool) -> int:
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams
    except ImportError:
        print("Falta qdrant-client: .venv/bin/python -m pip install qdrant-client")
        return 1

    entradas = catalogo.cargar()
    emb, modelo = _embeddings(config, None)
    textos = [e.texto_para_indexar() for e in entradas]
    print(f"generando embeddings de {len(textos)} Service Domains con '{modelo}'…")
    vectores = emb.embed_documents(textos)
    dim = len(vectores[0])

    cliente = QdrantClient(url=url, timeout=30.0)
    # Recrear en vez de actualizar: el índice es derivado, y así un cambio de modelo (otra
    # dimensión) no deja mezclados vectores de dos espacios distintos.
    if cliente.collection_exists(coleccion):
        cliente.delete_collection(coleccion)
    cliente.create_collection(
        collection_name=coleccion,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    cliente.upsert(
        collection_name=coleccion,
        points=[
            PointStruct(
                id=_id_determinista(e.service_domain),
                vector=v,
                payload={
                    "service_domain": e.service_domain,
                    "service_role": e.service_role,
                    "functional_pattern": e.functional_pattern,
                    "business_area": e.business_area,
                    "business_domain": e.business_domain,
                    "release": config.mapear_historias.release_bian,
                    "modelo_embeddings": modelo,
                },
            )
            for e, v in zip(entradas, vectores, strict=True)
        ],
    )
    total = cliente.count(coleccion).count
    print(f"colección '{coleccion}' en {url}: {total} puntos, dim {dim}, modelo '{modelo}'")

    if snapshot:
        info = cliente.create_snapshot(collection_name=coleccion)
        print(f"snapshot creado en el servidor: {info.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--backend", choices=("memoria", "qdrant"), default="memoria")
    p.add_argument("--url", default="http://localhost:6333")
    p.add_argument("--coleccion", default=COLECCION_POR_DEFECTO)
    p.add_argument("--snapshot", action="store_true", help="Qdrant: crea un snapshot al terminar.")
    args = p.parse_args(argv)

    config = cargar_settings()
    catalogo = CatalogoJson(config.ruta_catalogo_bian)
    if args.backend == "memoria":
        return _reconstruir_memoria(config, catalogo)
    return _reconstruir_qdrant(config, catalogo, args.url, args.coleccion, args.snapshot)


if __name__ == "__main__":
    sys.exit(main())
