"""Proveedor BIAN R14 autocontenido: cache local content-addressed + refresh explicito.

Cache-first: si el candidato ya existe localmente no toca la red. Solo descarga los ausentes
(salvo `permitir_descargas=False`) o cuando se pide `actualizar=True`. Cada entrada guarda
URL oficial, commit SHA, SHA-256 del contenido, fecha de recuperacion, operaciones y schemas.
Una falla de red sin evidencia previa produce `BIAN_EVIDENCE_UNAVAILABLE`, nunca un rechazo falso.

Mismo contrato de fuente que `architecture/scripts/sources/official_bian_bom_provider.py`
(repo `bian-official/public`, arbol `release{R}/semantic-apis/oas3 /yamls/{SD}.yaml`).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from src.adaptadores.salida.catalogo_operaciones_bian_json import CatalogoOperacionesBianJson
from src.dominio.historias import EvidenciaBian, OperacionBian, PropiedadSchema, SchemaBom

logger = logging.getLogger(__name__)

# Sube al cambiar el shape del registro cacheado -> `_asegurar` re-descarga los .json viejos.
_CACHE_VERSION = 2

_API_COMMIT = "https://api.github.com/repos/bian-official/public/commits/main"
_RAW = (
    "https://raw.githubusercontent.com/bian-official/public/{commit}"
    "/release{release}/semantic-apis/oas3%20/yamls/{name}.yaml"
)


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1] if ref else ""


def _resolver_wrapper(doc: dict, seccion: str, ref: str) -> str:
    """`#/components/requestBodies/Foo` -> nombre del schema que envuelve (o el wrapper si no resuelve)."""
    nombre = _ref_name(ref)
    obj = (doc.get("components", {}).get(seccion, {}) or {}).get(nombre)
    if not isinstance(obj, dict):
        return nombre
    for media in (obj.get("content", {}) or {}).values():
        s = (media or {}).get("schema", {}) or {}
        r = s.get("$ref") or (s.get("items", {}) or {}).get("$ref")
        if r:
            return _ref_name(r)
    return nombre


def _schema_ref_de(nodo: dict, doc: dict, seccion: str) -> str:
    if not isinstance(nodo, dict):
        return ""
    if nodo.get("$ref"):
        return _resolver_wrapper(doc, seccion, nodo["$ref"])
    for media in (nodo.get("content", {}) or {}).values():
        s = (media or {}).get("schema", {}) or {}
        r = s.get("$ref") or (s.get("items", {}) or {}).get("$ref")
        if r:
            return _ref_name(r)
    return ""


def _schema_bom(nombre: str, cuerpo) -> dict:
    if not isinstance(cuerpo, dict):
        return {"name": nombre, "kind": "value"}
    desc = str(cuerpo.get("description", ""))
    if cuerpo.get("enum"):
        return {"name": nombre, "kind": "enum", "description": desc,
                "enum_values": [str(v) for v in cuerpo["enum"]]}
    tipo = cuerpo.get("type", "object")
    if tipo == "array":
        ref = _ref_name((cuerpo.get("items", {}) or {}).get("$ref", ""))
        return {"name": nombre, "kind": "array", "description": desc,
                "properties": [{"name": "items", "type": "array", "ref": ref}]}
    props = []
    for pn, pv in (cuerpo.get("properties") or {}).items():
        if not isinstance(pv, dict):
            continue
        ref = _ref_name(pv.get("$ref", "") or (pv.get("items", {}) or {}).get("$ref", ""))
        props.append({"name": pn, "type": pv.get("type", "") or ("object" if ref else ""), "ref": ref})
    return {"name": nombre, "kind": "object" if (props or tipo == "object") else "value",
            "description": desc, "properties": props}
_REINTENTOS = 3
_BACKOFF_SEG = 2.0
_REINTENTABLES = {429, 500, 502, 503, 504}
_ERRORES_RED = (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError)
_ERRORES_PARSE = (ValueError, yaml.YAMLError)


def _descargar(url: str, headers: dict[str, str], timeout: int) -> bytes:
    """GET con reintentos + backoff sobre 429/5xx y errores de red transitorios."""
    ultimo: Exception | None = None
    for intento in range(1, _REINTENTOS + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            ultimo = exc
            if exc.code not in _REINTENTABLES or intento == _REINTENTOS:
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ultimo = exc
            if intento == _REINTENTOS:
                raise
        time.sleep(_BACKOFF_SEG * intento)
    raise ultimo if ultimo else RuntimeError("descarga fallida")  # pragma: no cover


class CatalogoBianCache(CatalogoOperacionesBianJson):
    def __init__(
        self,
        ruta_legacy: str | Path,
        cache_root: str | Path,
        release: str = "14.0.0",
        permitir_descargas: bool = True,
    ) -> None:
        super().__init__(ruta_legacy)
        self._cache_root = Path(cache_root) / f"release{release}"
        self._release = release
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._commit: str | None = None
        self._permitir_descargas = permitir_descargas
        self._token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""

    # ── E/S de la cache ─────────────────────────────────────────────────────
    def _archivo(self, sd: str):
        return self._cache_root / f"{re.sub(r'[^A-Za-z0-9]', '', sd)}.json"

    def _leer(self, sd: str) -> dict | None:
        p = self._archivo(sd)
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        except (OSError, ValueError):
            return None

    # ── API del puerto ─────────────────────────────────────────────────────
    def asegurar(self, service_domains: list[str], *, actualizar: bool = False) -> dict[str, EvidenciaBian]:
        return {sd: self._asegurar(sd, actualizar) for sd in dict.fromkeys(service_domains)}

    def _asegurar(self, sd: str, actualizar: bool) -> EvidenciaBian:
        with self._lock:
            anterior = self._leer(sd)
            if anterior and not actualizar:
                # Un .json de shape viejo (sin `cache_version` o < _CACHE_VERSION) se sigue usando:
                # `schemas_detalle_de` / `catalogo_estructurado_de` degradan solos. Para enriquecerlo
                # hay que pedir refresh explícito (`--actualizar-cache-bian`).
                if int(anterior.get("cache_version", 1)) < _CACHE_VERSION:
                    logger.info("cache %s en shape v%s (<v%s); usa --actualizar-cache-bian para el BOM extendido",
                                sd, anterior.get("cache_version", 1), _CACHE_VERSION)
                return self._evidencia(anterior, "CACHED_VERIFIED")
            if not self._permitir_descargas and not actualizar:
                return EvidenciaBian(
                    release=self._release,
                    cache_path=str(self._archivo(sd)),
                    error="Descarga de faltantes desactivada",
                )
            try:
                registro = self._recuperar(sd)
            except (_ERRORES_RED + _ERRORES_PARSE) as exc:
                if anterior:
                    return self._evidencia(anterior, "CACHED_VERIFIED")
                logger.warning("evidencia BIAN no disponible para %s: %s", sd, exc)
                return EvidenciaBian(
                    release=self._release, cache_path=str(self._archivo(sd)), error=str(exc)
                )
            self._persistir(sd, registro)
            return self._evidencia(registro, "VERIFIED")

    def _recuperar(self, sd: str) -> dict:
        if self._commit is None:
            headers = {"Accept": "application/vnd.github+json", "User-Agent": "generacion-contrato-ia-v2"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._commit = json.loads(_descargar(_API_COMMIT, headers, 20).decode())["sha"]
        commit = self._commit
        nombre = re.sub(r"[^A-Za-z0-9]", "", sd)
        url = _RAW.format(commit=commit, release=self._release, name=nombre)
        raw = _descargar(url, {"User-Agent": "generacion-contrato-ia-v2"}, 30)
        doc = yaml.safe_load(raw.decode("utf-8")) or {}
        return self._normalizar(sd, doc, url, commit, hashlib.sha256(raw).hexdigest())

    def _persistir(self, sd: str, registro: dict) -> None:
        destino = self._archivo(sd)
        temporal = destino.with_suffix(".json.tmp")
        temporal.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(destino)

    # ── normalizacion BOM -> registro ──────────────────────────────────────
    def _normalizar(self, sd: str, doc: dict, url: str, commit: str, sha: str) -> dict:
        ops = []
        for path, item in (doc.get("paths") or {}).items():
            for method, op in (item or {}).items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(op, dict):
                    continue
                tag = str((op.get("tags") or ["CR"])[0])
                tipo = "BQ" if tag.startswith("BQ") else "CR"
                ops.append(
                    {
                        "operation_id": str(op.get("operationId", "")),
                        "method": method.upper(),
                        "path": path,
                        "tipo": tipo,
                        "grupo": tag.split("-", 1)[-1].strip(),
                        "request_schema": _schema_ref_de(op.get("requestBody"), doc, "requestBodies"),
                        "response_schema": _schema_ref_de(
                            (op.get("responses", {}) or {}).get("200"), doc, "responses"
                        ),
                        "summary": str(op.get("summary", "")),
                        "description": str(op.get("description", "")),
                    }
                )
        ops = [o for o in ops if o["operation_id"]]

        # Control Record principal (BIAN publica uno por Service Domain) -> parent de los BQ.
        cr_principal = next((o["grupo"] for o in ops if o["tipo"] == "CR"), "")
        for o in ops:
            if o["tipo"] == "BQ":
                o["parent_control_record"] = cr_principal

        schemas_raw = doc.get("components", {}).get("schemas", {}) or {}
        schemas_detalle = [_schema_bom(n, c) for n, c in sorted(schemas_raw.items())]

        crs = sorted({o["grupo"] for o in ops if o["tipo"] == "CR"})
        bqs = sorted({o["grupo"] for o in ops if o["tipo"] == "BQ"})
        catalogo = {
            "control_records": [
                {"name": g, "operations": [o["operation_id"] for o in ops if o["tipo"] == "CR" and o["grupo"] == g]}
                for g in crs
            ],
            "behavior_qualifiers": [
                {"name": g, "parent_control_record": cr_principal,
                 "operations": [o["operation_id"] for o in ops if o["tipo"] == "BQ" and o["grupo"] == g]}
                for g in bqs
            ],
        }
        return {
            "service_domain": sd,
            "release": self._release,
            "cache_version": _CACHE_VERSION,
            "operations": ops,
            "schemas": sorted(schemas_raw.keys()),
            "schemas_detalle": schemas_detalle,
            "catalog": catalogo,
            "evidence": {
                "source_url": url,
                "source_commit_sha": commit,
                "content_sha256": sha,
                "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            },
        }

    def _evidencia(self, d: dict, estado: str) -> EvidenciaBian:
        e = d.get("evidence") or {}
        sd = str(d.get("service_domain", ""))
        return EvidenciaBian(
            estado=estado,
            release=str(d.get("release", self._release)),
            source_url=str(e.get("source_url", "")),
            source_commit_sha=str(e.get("source_commit_sha", "")),
            content_sha256=str(e.get("content_sha256", "")),
            cache_path=str(self._archivo(sd)),
            recuperado_en=str(e.get("retrieved_at", "")),
        )

    def evidencia_de(self, service_domain: str) -> EvidenciaBian:
        d = self._leer(service_domain)
        return self._evidencia(d, "CACHED_VERIFIED") if d else EvidenciaBian(release=self._release)

    def esquemas_de(self, service_domain: str) -> list[str]:
        d = self._leer(service_domain)
        return [str(s) for s in (d.get("schemas") or [])] if d else []

    def schemas_detalle_de(self, service_domain: str) -> list[SchemaBom]:
        d = self._leer(service_domain)
        if not d:
            return []
        crudos = d.get("schemas_detalle") or [{"name": n, "kind": "value"} for n in (d.get("schemas") or [])]
        salida: list[SchemaBom] = []
        for s in crudos:
            try:
                props = [PropiedadSchema(**p) for p in (s.get("properties") or [])]
                salida.append(SchemaBom(
                    name=str(s.get("name", "")), kind=str(s.get("kind", "object")),  # type: ignore[arg-type]
                    description=str(s.get("description", "")), properties=props,
                    enum_values=[str(v) for v in (s.get("enum_values") or [])],
                ))
            except (TypeError, ValueError):  # pragma: no cover
                continue
        return salida

    def catalogo_estructurado_de(self, service_domain: str) -> dict:
        d = self._leer(service_domain)
        return dict(d.get("catalog") or {}) if d else {}

    def operaciones_de(self, service_domain: str) -> list[OperacionBian] | None:
        d = self._leer(service_domain)
        if d:
            return [OperacionBian(**o) for o in d.get("operations", [])]
        return super().operaciones_de(service_domain)

    def service_domains_con_catalogo(self) -> set[str]:
        out = set(super().service_domains_con_catalogo())
        for p in self._cache_root.glob("*.json"):
            try:
                out.add(str(json.loads(p.read_text(encoding="utf-8")).get("service_domain", p.stem)))
            except (OSError, ValueError):
                pass
        return out
