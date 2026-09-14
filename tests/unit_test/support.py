"""Helpers de test: construir un `Config` sin depender del entorno."""

from __future__ import annotations

from pathlib import Path

from src.configuracion.config_yaml import (
    Config,
    LLMConfig,
    MapearHistoriasConfig,
    ObservabilidadConfig,
    ProveedorConfig,
    RoutingConfig,
    ValidarSdConfig,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"


def _proveedor_fake() -> ProveedorConfig:
    return ProveedorConfig(
        nombre="fake",
        enabled=True,
        api_key_env="",
        api_key=None,
        base_url=None,
        structured_method=None,
        llm_models=("fake",),
        embedding_models=("fake",),
    )


def config_test(
    *, validar_sd: dict | None = None, mapear_historias: dict | None = None, llm: dict | None = None
) -> Config:
    """Config determinista para tests: único proveedor `fake`, rutas reales de docs/."""
    return Config(
        ruta=RAIZ / "config.yaml",
        routing=RoutingConfig(llm_priority=("fake",), embedding_priority=("fake",)),
        proveedores={"fake": _proveedor_fake()},
        llm=LLMConfig(
            **{
                "temperature": 0.0,
                "seed": 42,
                "esfuerzo": "low",
                "reintentos_transitorios": 2,
                "backoff_inicial_seg": 0.0,
                "backoff_max_seg": 0.0,
                **(llm or {}),
            }
        ),
        observabilidad=ObservabilidadConfig(),
        validar_sd=ValidarSdConfig(
            **{
                "rag_estrategia": "lexico",
                "rag_top_k": 6,
                "rag_umbral_alto": 0.90,
                "rag_umbral_bajo": 0.60,
                "ruta_catalogo_bian": str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"),
                **(validar_sd or {}),
            }
        ),
        mapear_historias=MapearHistoriasConfig(
            **{
                "umbral_directo": 0.90,
                "umbral_tentativo": 0.63,
                "concurrencia": 2,
                "paso2_operaciones": True,
                "rol_max_chars": 240,
                "top_n_omitidos": 5,
                "ruta_operaciones": str(DOCS / "bian-operation-catalogs.json"),
                "ruta_cache_bian": str(DOCS / "bian-cache"),
                "descargar_faltantes": False,
                **(mapear_historias or {}),
            }
        ),
    )
