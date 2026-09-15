"""Adaptador: lee los PUML BOM de `docs/bian-diagrams/puml-bom/` y los parsea a `ModeloBomPuml`.

Qué archivo le toca a cada Service Domain, en orden:

1. La ruta que **declara el propio Service Landscape** en `bom_diagram.puml_path`
   (`CatalogoJson.rutas_bom_puml()`), que es el dato publicado.
2. Si el landscape no declara ninguna (76 de los 341 SD no tienen BOM), el slug kebab-case del
   nombre (`Transaction Authorization` -> `transaction-authorization.puml`), que es una
   suposición sobre cómo nombró los archivos `scripts/svg_to_puml_bom/`.

Hoy las dos coinciden en los 265 SD que declaran ruta, y `tests/unit_test/test_catalogo_bom_puml.py`
falla si dejan de coincidir — que es justo lo que pasaría si una regeneración del landscape o de
los diagramas cambiara el criterio de nombres: sin esto, el BOM desaparecería en silencio del
paquete de evidencia (`objeto_bom` a 0.0, sin error).

Cache-first en memoria; sin red.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path

from src.aplicacion.puertos.catalogo_bom import CatalogoBomPort
from src.dominio.historias import ModeloBomPuml
from src.dominio.puml_bom import parsear_puml_bom

logger = logging.getLogger(__name__)


def slug_service_domain(nombre: str) -> str:
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")


class CatalogoBomPuml(CatalogoBomPort):
    def __init__(
        self, raiz_puml: str | Path, rutas_declaradas: Mapping[str, str] | None = None
    ) -> None:
        self._raiz = Path(raiz_puml)
        self._declaradas = dict(rutas_declaradas or {})
        self._cache: dict[str, ModeloBomPuml | None] = {}

    def _archivo(self, service_domain: str, slug: str) -> Path:
        """La ruta declarada por el landscape manda; el slug es el respaldo."""
        declarada = self._declaradas.get(service_domain)
        if declarada:
            # El landscape la escribe relativa a la raíz del repo; si el proceso corre desde otro
            # sitio, el nombre de archivo declarado sigue valiendo bajo la raíz configurada.
            for candidata in (Path(declarada), self._raiz / Path(declarada).name):
                if candidata.is_file():
                    return candidata
        return self._raiz / f"{slug}.puml"

    def modelo_de(self, service_domain: str) -> ModeloBomPuml | None:
        slug = slug_service_domain(service_domain)
        if slug in self._cache:
            return self._cache[slug]
        p = self._archivo(service_domain, slug)
        modelo: ModeloBomPuml | None = None
        if p.is_file():
            try:
                modelo = parsear_puml_bom(
                    p.read_text(encoding="utf-8"), service_domain=service_domain, slug=slug
                )
            except (OSError, ValueError) as exc:  # pragma: no cover
                logger.warning("no se pudo parsear el PUML %s: %s", p, exc)
        self._cache[slug] = modelo
        return modelo

    def service_domains_con_bom(self) -> set[str]:
        if not self._raiz.is_dir():
            return set()
        return {p.stem for p in self._raiz.glob("*.puml")}
