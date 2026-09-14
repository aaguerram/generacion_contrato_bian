"""Carga y valida `config.yaml` — toda la configuración movible del proyecto.

El `.env` solo aporta API keys; aquí vive el resto (modelos, orden de failover,
umbrales, rutas). Este módulo NO lee variables de entorno salvo las `api_key_env`
declaradas por cada proveedor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_RAIZ = Path(__file__).resolve().parents[2]  # .../generacion_contrato_ia_v2
_ESFUERZOS = ("low", "medium", "high")


@dataclass(frozen=True)
class ProveedorConfig:
    nombre: str
    enabled: bool
    api_key_env: str
    api_key: str | None  # resuelta desde el entorno / .env
    base_url: str | None
    structured_method: str | None  # "json_schema" | "function_calling" | "json_mode" | None
    llm_models: tuple[str, ...]
    embedding_models: tuple[str, ...]

    @property
    def usable_llm(self) -> bool:
        return (
            self.enabled and bool(self.llm_models) and (self.nombre == "fake" or bool(self.api_key))
        )

    @property
    def usable_embedding(self) -> bool:
        return (
            self.enabled
            and bool(self.embedding_models)
            and (self.nombre == "fake" or bool(self.api_key))
        )


@dataclass(frozen=True)
class RoutingConfig:
    llm_priority: tuple[str, ...]
    embedding_priority: tuple[str, ...]


@dataclass(frozen=True)
class LLMConfig:
    temperature: float = 0.0
    seed: int | None = 42
    esfuerzo: str = "low"
    reintentos_transitorios: int = 4
    backoff_inicial_seg: float = 2.0
    backoff_max_seg: float = 30.0

    def __post_init__(self) -> None:
        if self.esfuerzo not in _ESFUERZOS:
            raise ValueError(f"llm.esfuerzo='{self.esfuerzo}' inválido; use {_ESFUERZOS}.")


@dataclass(frozen=True)
class ObservabilidadConfig:
    langsmith_tracing: bool = False
    langsmith_project: str = "generacion-contrato-ia-v2"
    langsmith_endpoint: str | None = None
    langsmith_api_key: str | None = None  # resuelta desde LANGSMITH_API_KEY


@dataclass(frozen=True)
class ValidarSdConfig:
    rag_estrategia: str = "lexico"
    rag_top_k: int = 6
    rag_umbral_alto: float = 0.90
    rag_umbral_bajo: float = 0.60
    ruta_sd_json: str = "docs/SD.json"


@dataclass(frozen=True)
class MapearHistoriasConfig:
    umbral_directo: float = 0.90
    umbral_tentativo: float = 0.63
    concurrencia: int = 1
    concurrencia_candidatos: int = 2
    max_candidatos_hu: int = 14
    paso2_operaciones: bool = True
    rol_max_chars: int = 240
    top_n_omitidos: int = 5
    ruta_jerarquia: str = "docs/bian-business-areas.json"
    ruta_operaciones: str = "docs/bian-operation-catalogs.json"
    ruta_cache_bian: str = "docs/bian-cache"
    ruta_bian_puml: str = "docs/bian-diagrams/puml-bom"
    release_bian: str = "14.0.0"
    descargar_faltantes: bool = True
    bom_puml_habilitado: bool = True
    # Retrieval híbrido (RRF léxico+vectorial en memoria, Fase 3 del plan de recuperación híbrida).
    # Por defecto OFF: es aditivo y ya tiene tests propios, pero encenderlo por defecto cambia qué
    # candidatos se evalúan en corridas existentes -- eso debe decidirlo un benchmark de recall
    # (ver implementacion_pendiente.md), no un valor por defecto silencioso.
    retrieval_hibrido_habilitado: bool = False
    retrieval_top_k: int = 20
    retrieval_max_inyectados: int = 5


@dataclass(frozen=True)
class Config:
    ruta: Path
    routing: RoutingConfig
    proveedores: dict[str, ProveedorConfig]
    llm: LLMConfig
    observabilidad: ObservabilidadConfig
    validar_sd: ValidarSdConfig
    mapear_historias: MapearHistoriasConfig

    # ── resolución de rutas relativas contra la raíz del paquete ──
    def _abs(self, ruta: str) -> str:
        p = Path(ruta)
        return str(p if p.is_absolute() else _RAIZ / p)

    @property
    def ruta_sd_json(self) -> str:
        return self._abs(self.validar_sd.ruta_sd_json)

    @property
    def ruta_jerarquia(self) -> str:
        return self._abs(self.mapear_historias.ruta_jerarquia)

    @property
    def ruta_operaciones(self) -> str:
        return self._abs(self.mapear_historias.ruta_operaciones)

    @property
    def ruta_cache_bian(self) -> str:
        return self._abs(self.mapear_historias.ruta_cache_bian)

    @property
    def ruta_bian_puml(self) -> str:
        return self._abs(self.mapear_historias.ruta_bian_puml)

    # ── orden de proveedores para failover ──
    def orden_llm(self, proveedor_forzado: str | None = None) -> list[ProveedorConfig]:
        return self._orden(self.routing.llm_priority, "usable_llm", proveedor_forzado)

    def orden_embedding(self, proveedor_forzado: str | None = None) -> list[ProveedorConfig]:
        return self._orden(self.routing.embedding_priority, "usable_embedding", proveedor_forzado)

    def _orden(
        self, prioridad: tuple[str, ...], attr: str, forzado: str | None
    ) -> list[ProveedorConfig]:
        if forzado:
            nombres = [
                forzado
            ]  # `--proveedor X` restringe la cadena a X (con failover entre SUS modelos)
        else:
            nombres = list(prioridad)
            # proveedores habilitados no listados en el priority, al final
            for n in self.proveedores:
                if n not in nombres:
                    nombres.append(n)
        return [
            self.proveedores[n]
            for n in nombres
            if n in self.proveedores and getattr(self.proveedores[n], attr)
        ]


def _proveedor(nombre: str, raw: dict) -> ProveedorConfig:
    api_key_env = str(raw.get("api_key_env") or "").strip()
    llm = raw.get("llm") or {}
    emb = raw.get("embedding") or {}
    return ProveedorConfig(
        nombre=nombre,
        enabled=bool(raw.get("enabled", True)),
        api_key_env=api_key_env,
        api_key=(os.getenv(api_key_env) or None) if api_key_env else None,
        base_url=raw.get("base_url") or None,
        structured_method=raw.get("structured_method") or None,
        llm_models=tuple(str(m) for m in (llm.get("models") or []) if m),
        embedding_models=tuple(str(m) for m in (emb.get("models") or []) if m),
    )


def cargar_config(ruta: str | Path | None = None) -> Config:
    """Lee `config.yaml` (o `ruta`). Falla si no existe o es inválido."""
    p = Path(ruta) if ruta else _RAIZ / "config.yaml"
    if not p.is_file():
        raise FileNotFoundError(
            f"No se encontró config.yaml en {p}. Copia config.yaml.example o pásalo con --config."
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}

    r = raw.get("routing") or {}
    routing = RoutingConfig(
        llm_priority=tuple(str(x) for x in (r.get("llm_priority") or [])),
        embedding_priority=tuple(str(x) for x in (r.get("embedding_priority") or [])),
    )
    proveedores = {n: _proveedor(n, v or {}) for n, v in (raw.get("providers") or {}).items()}

    lc = raw.get("llm") or {}
    seed = lc.get("seed", 42)
    llm = LLMConfig(
        temperature=float(lc.get("temperature", 0.0)),
        seed=int(seed) if seed not in (None, "", "null") else None,
        esfuerzo=str(lc.get("esfuerzo", "low")).strip().lower(),
        reintentos_transitorios=int(lc.get("reintentos_transitorios", 4)),
        backoff_inicial_seg=float(lc.get("backoff_inicial_seg", 2.0)),
        backoff_max_seg=float(lc.get("backoff_max_seg", 30.0)),
    )

    oc = raw.get("observabilidad") or {}
    observabilidad = ObservabilidadConfig(
        langsmith_tracing=str(oc.get("langsmith_tracing", "")).strip().lower()
        in ("1", "true", "yes")
        or oc.get("langsmith_tracing") is True,
        langsmith_project=str(oc.get("langsmith_project", "generacion-contrato-ia-v2")),
        langsmith_endpoint=oc.get("langsmith_endpoint") or None,
        langsmith_api_key=os.getenv("LANGSMITH_API_KEY") or None,
    )

    vs = raw.get("validar_sd") or {}
    validar_sd = ValidarSdConfig(
        rag_estrategia=str(vs.get("rag_estrategia", "lexico")).strip().lower(),
        rag_top_k=int(vs.get("rag_top_k", 6)),
        rag_umbral_alto=float(vs.get("rag_umbral_alto", 0.90)),
        rag_umbral_bajo=float(vs.get("rag_umbral_bajo", 0.60)),
        ruta_sd_json=str(vs.get("ruta_sd_json", "docs/SD.json")),
    )

    mh = raw.get("mapear_historias") or {}
    mapear_historias = MapearHistoriasConfig(
        umbral_directo=float(mh.get("umbral_directo", 0.90)),
        umbral_tentativo=float(mh.get("umbral_tentativo", 0.63)),
        concurrencia=int(mh.get("concurrencia", 1)),
        concurrencia_candidatos=int(mh.get("concurrencia_candidatos", 2)),
        max_candidatos_hu=int(mh.get("max_candidatos_hu", 14)),
        paso2_operaciones=bool(mh.get("paso2_operaciones", True)),
        rol_max_chars=int(mh.get("rol_max_chars", 240)),
        top_n_omitidos=int(mh.get("top_n_omitidos", 5)),
        ruta_jerarquia=str(mh.get("ruta_jerarquia", "docs/bian-business-areas.json")),
        ruta_operaciones=str(mh.get("ruta_operaciones", "docs/bian-operation-catalogs.json")),
        ruta_cache_bian=str(mh.get("ruta_cache_bian", "docs/bian-cache")),
        ruta_bian_puml=str(mh.get("ruta_bian_puml", "docs/bian-diagrams/puml-bom")),
        release_bian=str(mh.get("release_bian", "14.0.0")),
        descargar_faltantes=bool(mh.get("descargar_faltantes", True)),
        bom_puml_habilitado=bool(mh.get("bom_puml_habilitado", True)),
        retrieval_hibrido_habilitado=bool(mh.get("retrieval_hibrido_habilitado", False)),
        retrieval_top_k=int(mh.get("retrieval_top_k", 20)),
        retrieval_max_inyectados=int(mh.get("retrieval_max_inyectados", 5)),
    )

    return Config(
        ruta=p,
        routing=routing,
        proveedores=proveedores,
        llm=llm,
        observabilidad=observabilidad,
        validar_sd=validar_sd,
        mapear_historias=mapear_historias,
    )
