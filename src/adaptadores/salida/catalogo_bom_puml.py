"""Adaptador: lee los PUML BOM de `docs/bian-puml/` y los parsea a `ModeloBomPuml`.

Slug = nombre del Service Domain en kebab-case (`Transaction Authorization` ->
`transaction-authorization.puml`). Cache-first en memoria; sin red.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

from src.aplicacion.puertos.catalogo_bom import CatalogoBomPort
from src.dominio.historias import ModeloBomPuml
from src.dominio.puml_bom import parsear_puml_bom

logger = logging.getLogger(__name__)


def slug_service_domain(nombre: str) -> str:
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")


class CatalogoBomPuml(CatalogoBomPort):
    def __init__(self, raiz_puml: str | Path) -> None:
        self._raiz = Path(raiz_puml)
        self._cache: dict[str, ModeloBomPuml | None] = {}

    def _archivo(self, slug: str) -> Path:
        return self._raiz / f"{slug}.puml"

    def modelo_de(self, service_domain: str) -> ModeloBomPuml | None:
        slug = slug_service_domain(service_domain)
        if slug in self._cache:
            return self._cache[slug]
        p = self._archivo(slug)
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
