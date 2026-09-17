"""Carga y valida `config.yaml` — toda la configuración movible del proyecto.

El `.env` solo aporta API keys; aquí vive el resto (modelos, orden de failover,
umbrales, rutas). Este módulo NO lee variables de entorno salvo las `api_key_env`
declaradas por cada proveedor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_RAIZ = Path(__file__).resolve().parents[2]  # .../generacion_contrato_ia_v2
_ESFUERZOS = ("low", "medium", "high")
_TOKENIZADORES = ("caracteres", "tiktoken")


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
    # {nombre del modelo: tokens de ENTRADA que admite}. Solo los modelos que lo declaran; el
    # resto se llama sin comprobación previa, como siempre. Ver `max_input_tokens` en
    # `providers.<n>.llm.models[]` y `ChatConFailover`.
    llm_max_input_tokens: dict[str, int] = field(default_factory=dict)

    def max_input_tokens(self, modelo: str) -> int | None:
        """Presupuesto de entrada declarado para `modelo`, o `None` si no declara ninguno."""
        return self.llm_max_input_tokens.get(modelo)

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
    # Orden de proveedores DISTINTO para nodos concretos, por `prompt_id` (mapeo.operaciones,
    # mapeo.evaluacion, ...). Los 7 nodos LLM no tienen la misma dificultad ni el mismo tamaño de
    # prompt: `mapeo.intencion` lo resuelve cualquier modelo, y `mapeo.operaciones` -que debe
    # devolver un operationId literal entre decenas- es el que se rompe primero con un modelo
    # debil. Sin esta entrada, todos los nodos comparten `llm_priority`, que es el default.
    llm_priority_por_nodo: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMConfig:
    temperature: float = 0.0
    seed: int | None = 42
    esfuerzo: str = "low"
    reintentos_transitorios: int = 4
    backoff_inicial_seg: float = 2.0
    backoff_max_seg: float = 30.0
    # Cómo se mide un prompt contra `max_input_tokens` (ver `adaptadores/salida/llm/tokens.py`).
    # `caracteres` (por defecto) = len/chars_por_token: sin dependencias y sin red.
    # `tiktoken` = tokenización real; más preciso, pero descarga el vocabulario la primera vez.
    tokenizador: str = "caracteres"
    # Razón del estimador por caracteres. 4.0 es la regla con la que ya se dimensionaba el
    # catálogo BIAN en la documentación del proyecto.
    chars_por_token: float = 4.0

    def __post_init__(self) -> None:
        if self.esfuerzo not in _ESFUERZOS:
            raise ValueError(f"llm.esfuerzo='{self.esfuerzo}' inválido; use {_ESFUERZOS}.")
        if self.tokenizador not in _TOKENIZADORES:
            raise ValueError(
                f"llm.tokenizador='{self.tokenizador}' inválido; use {_TOKENIZADORES}."
            )
        if self.chars_por_token <= 0:
            raise ValueError(
                f"llm.chars_por_token={self.chars_por_token} inválido; debe ser > 0."
            )


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
    # Documento BIAN ÚNICO del runtime (generado por scripts/build_bian_landscape/).
    ruta_catalogo_bian: str = "docs/BIAN_Service_Landscape_V14.0_Matrix_View.json"


@dataclass(frozen=True)
class MapearHistoriasConfig:
    umbral_directo: float = 0.90
    umbral_tentativo: float = 0.63
    concurrencia: int = 1
    concurrencia_candidatos: int = 2
    max_candidatos_hu: int = 14
    paso2_operaciones: bool = True
    rol_max_chars: int = 600
    top_n_omitidos: int = 5
    # Routing jerárquico: parte el paso de candidatos en 2a (elige Business Domains sobre la
    # taxonomía, 36 vías con la documentación completa) + 2b (ve solo los SD de esos dominios,
    # pero con el texto ENTERO: rol sin recortar + examples_of_use + features). Medido sobre el
    # landscape real: 41.1k tokens -> ~11.4k, y deja de hacer falta la escalera de degradación.
    # El default de la dataclass es False para que un `Config` construido a mano (tests) se
    # comporte como siempre; `config.yaml` lo enciende.
    routing_jerarquico_habilitado: bool = False
    # Flags de retrieval, INDEPENDIENTES: se puede tener híbrido sin grafo, grafo sin reranker,
    # o los tres. Un solo interruptor que mezclara las tres cosas impediría aislar qué aporta cada
    # una cuando se comparan corridas.
    graph_rag_habilitado: bool = False
    graph_rag_max_inyectados: int = 3
    # `memoria` = InMemoryVectorStore (por defecto, sin infraestructura); `qdrant` = índice
    # externo de infra/retrieval/docker-compose.yml. Ver docs/adr/0001-vector-store.md.
    vector_store: str = "memoria"
    qdrant_url: str = "http://localhost:6333"
    qdrant_coleccion: str = "bian_service_domains"
    reranker_habilitado: bool = False
    reranker_modelo: str = "BAAI/bge-reranker-v2-m3"
    ruta_grafo_bian: str = "docs/bian-graph/release14.0.0/grafo.json"
    presupuesto_segundos_hu: float = 0.0  # 0 = sin límite
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
    # ── Canal disperso y fusión (ver scripts/evaluate_retrieval/) ──
    # `rapidfuzz` compara la consulta contra el NOMBRE del Service Domain (que es lo correcto para
    # validar-sd, donde la consulta ES un nombre). `bm25` indexa el texto completo del SD y pesa
    # los términos por IDF, que es lo que pide mapear-historias (la consulta es lenguaje natural).
    retrieval_canal_lexico: str = "rapidfuzz"
    # RRF: `k` amortigua el peso del top-1. 60 es el valor del paper, calibrado para corpus de
    # miles de documentos; con 341 SD y top-20 un k menor diferencia más. Los pesos permiten que
    # la fusión deje de tratar por igual a un canal que acierta 0.29 y a otro que acierta 0.86.
    rrf_k: int = 60
    rrf_peso_lexico: float = 1.0
    rrf_peso_vectorial: float = 1.0
    # ── CAG (Cache-Augmented Generation) escalonado ──
    # El catálogo entero cabe en contexto (~93k tokens con el tope actual de texto por SD), así
    # que el recall de recuperación es un problema OPCIONAL a esta escala. `cag_chars_por_sd`
    # fija el escalón: 0 = índice de siempre (nombre + rol a 90 chars, ~10k tokens).
    cag_habilitado: bool = False
    cag_chars_por_sd: int = 300
    # ── Señales de grafo para el revisor adversarial (deterministas, no las decide el LLM) ──
    grafo_senales_adversarial: bool = False
    # ── CRAG: una sola vuelta correctiva cuando la evidencia del lote sale vacía/débil ──
    crag_reintento_habilitado: bool = False
    # ── Caché de nodos LangGraph y durabilidad ──
    cache_nodos_habilitado: bool = False
    cache_nodos_ruta: str = ".cache/nodos-langgraph"
    cache_nodos_ttl: int = 0  # segundos; 0 = sin expiración
    durabilidad: str = "exit"  # exit | sync | async (sync/async exigen checkpointer)
    # Base del checkpointer persistente. Vive bajo `.cache/` (gitignored) y se CREA si no existe.
    # Solo se abre cuando `durabilidad != exit`.
    checkpoint_ruta: str = ".cache/checkpoints/mapeo.sqlite"


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
    def ruta_catalogo_bian(self) -> str:
        return self._abs(self.validar_sd.ruta_catalogo_bian)

    @property
    def ruta_grafo_bian(self) -> str:
        return self._abs(self.mapear_historias.ruta_grafo_bian)

    @property
    def ruta_operaciones(self) -> str:
        return self._abs(self.mapear_historias.ruta_operaciones)

    @property
    def ruta_cache_bian(self) -> str:
        return self._abs(self.mapear_historias.ruta_cache_bian)

    @property
    def ruta_bian_puml(self) -> str:
        return self._abs(self.mapear_historias.ruta_bian_puml)

    @property
    def ruta_cache_nodos(self) -> str:
        return self._abs(self.mapear_historias.cache_nodos_ruta)

    @property
    def ruta_checkpoints(self) -> str:
        return self._abs(self.mapear_historias.checkpoint_ruta)

    # ── orden de proveedores para failover ──
    def orden_llm(
        self, proveedor_forzado: str | None = None, nodo: str | None = None
    ) -> list[ProveedorConfig]:
        """Orden de proveedores para un nodo. `--proveedor X` sigue mandando sobre todo: pinnear
        la cadena es una decisión del operador y no la puede pisar una entrada de config."""
        prioridad = self.routing.llm_priority
        if nodo and not proveedor_forzado:
            prioridad = self.routing.llm_priority_por_nodo.get(nodo, prioridad)
        return self._orden(prioridad, "usable_llm", proveedor_forzado)

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


def _entero_positivo(valor, donde: str) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f"{donde}: '{valor}' no es un entero de tokens válido.") from None
    if n <= 0:
        raise ValueError(f"{donde}: {n} inválido; max_input_tokens debe ser > 0.")
    return n


def _modelos_llm(nombre: str, llm: dict) -> tuple[tuple[str, ...], dict[str, int]]:
    """Lee `providers.<n>.llm.models` aceptando DOS formas por elemento.

    La de siempre (solo el nombre) y la que declara su presupuesto de entrada::

        models:
          - openai/gpt-oss-120b                 # sin presupuesto declarado
          - name: openai/gpt-oss-20b
            max_input_tokens: 12000

    `providers.<n>.llm.max_input_tokens` sirve de valor por defecto para los modelos del
    proveedor que no declaren el suyo: casi siempre el límite lo pone el plan (el free tier de
    Groq, por ejemplo), no el modelo. El presupuesto es de ENTRADA -- debe dejar sitio para la
    respuesta dentro de la ventana de contexto.
    """
    por_defecto = llm.get("max_input_tokens")
    if por_defecto is not None:
        por_defecto = _entero_positivo(por_defecto, f"providers.{nombre}.llm.max_input_tokens")

    modelos: list[str] = []
    limites: dict[str, int] = {}
    for i, m in enumerate(llm.get("models") or []):
        if isinstance(m, dict):
            crudo = m.get("name") or m.get("model") or m.get("nombre")
            if not crudo:
                raise ValueError(
                    f"providers.{nombre}.llm.models[{i}]: un modelo en forma de objeto necesita "
                    "'name'."
                )
            modelo = str(crudo).strip()
            declarado = m.get("max_input_tokens", por_defecto)
        else:
            modelo = str(m).strip()
            declarado = por_defecto
        if not modelo:
            continue
        modelos.append(modelo)
        if declarado is not None:
            limites[modelo] = _entero_positivo(
                declarado, f"providers.{nombre}.llm.models[{i}].max_input_tokens"
            )
    return tuple(modelos), limites


def _proveedor(nombre: str, raw: dict) -> ProveedorConfig:
    api_key_env = str(raw.get("api_key_env") or "").strip()
    llm = raw.get("llm") or {}
    emb = raw.get("embedding") or {}
    llm_models, llm_max_input_tokens = _modelos_llm(nombre, llm)
    return ProveedorConfig(
        nombre=nombre,
        enabled=bool(raw.get("enabled", True)),
        api_key_env=api_key_env,
        api_key=(os.getenv(api_key_env) or None) if api_key_env else None,
        base_url=raw.get("base_url") or None,
        structured_method=raw.get("structured_method") or None,
        llm_models=llm_models,
        embedding_models=tuple(str(m) for m in (emb.get("models") or []) if m),
        llm_max_input_tokens=llm_max_input_tokens,
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
        llm_priority_por_nodo={
            str(nodo): tuple(str(x) for x in (lista or []))
            for nodo, lista in (r.get("llm_priority_por_nodo") or {}).items()
            if lista
        },
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
        tokenizador=str(lc.get("tokenizador", "caracteres")).strip().lower(),
        chars_por_token=float(lc.get("chars_por_token", 4.0)),
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
        # `ruta_sd_json` era la clave de cuando el catálogo eran dos archivos cruzados:
        # se sigue aceptando para no romper configs viejas, pero apunta al documento único.
        ruta_catalogo_bian=str(
            vs.get("ruta_catalogo_bian")
            or vs.get("ruta_sd_json")
            or "docs/BIAN_Service_Landscape_V14.0_Matrix_View.json"
        ),
    )

    mh = raw.get("mapear_historias") or {}
    mapear_historias = MapearHistoriasConfig(
        umbral_directo=float(mh.get("umbral_directo", 0.90)),
        umbral_tentativo=float(mh.get("umbral_tentativo", 0.63)),
        concurrencia=int(mh.get("concurrencia", 1)),
        concurrencia_candidatos=int(mh.get("concurrencia_candidatos", 2)),
        max_candidatos_hu=int(mh.get("max_candidatos_hu", 14)),
        paso2_operaciones=bool(mh.get("paso2_operaciones", True)),
        rol_max_chars=int(mh.get("rol_max_chars", 600)),
        top_n_omitidos=int(mh.get("top_n_omitidos", 5)),
        graph_rag_habilitado=bool(mh.get("graph_rag_habilitado", False)),
        graph_rag_max_inyectados=int(mh.get("graph_rag_max_inyectados", 3)),
        vector_store=str(mh.get("vector_store", "memoria")).strip().lower(),
        qdrant_url=str(mh.get("qdrant_url", "http://localhost:6333")),
        qdrant_coleccion=str(mh.get("qdrant_coleccion", "bian_service_domains")),
        reranker_habilitado=bool(mh.get("reranker_habilitado", False)),
        reranker_modelo=str(mh.get("reranker_modelo", "BAAI/bge-reranker-v2-m3")),
        ruta_grafo_bian=str(mh.get("ruta_grafo_bian", "docs/bian-graph/release14.0.0/grafo.json")),
        presupuesto_segundos_hu=float(mh.get("presupuesto_segundos_hu", 0.0)),
        ruta_operaciones=str(mh.get("ruta_operaciones", "docs/bian-operation-catalogs.json")),
        ruta_cache_bian=str(mh.get("ruta_cache_bian", "docs/bian-cache")),
        ruta_bian_puml=str(mh.get("ruta_bian_puml", "docs/bian-diagrams/puml-bom")),
        release_bian=str(mh.get("release_bian", "14.0.0")),
        descargar_faltantes=bool(mh.get("descargar_faltantes", True)),
        bom_puml_habilitado=bool(mh.get("bom_puml_habilitado", True)),
        retrieval_hibrido_habilitado=bool(mh.get("retrieval_hibrido_habilitado", False)),
        retrieval_top_k=int(mh.get("retrieval_top_k", 20)),
        retrieval_max_inyectados=int(mh.get("retrieval_max_inyectados", 5)),
        retrieval_canal_lexico=str(mh.get("retrieval_canal_lexico", "rapidfuzz")).strip().lower(),
        rrf_k=int(mh.get("rrf_k", 60)),
        rrf_peso_lexico=float(mh.get("rrf_peso_lexico", 1.0)),
        rrf_peso_vectorial=float(mh.get("rrf_peso_vectorial", 1.0)),
        routing_jerarquico_habilitado=bool(mh.get("routing_jerarquico_habilitado", False)),
        cag_habilitado=bool(mh.get("cag_habilitado", False)),
        cag_chars_por_sd=int(mh.get("cag_chars_por_sd", 300)),
        grafo_senales_adversarial=bool(mh.get("grafo_senales_adversarial", False)),
        crag_reintento_habilitado=bool(mh.get("crag_reintento_habilitado", False)),
        cache_nodos_habilitado=bool(mh.get("cache_nodos_habilitado", False)),
        cache_nodos_ruta=str(mh.get("cache_nodos_ruta", ".cache/nodos-langgraph")),
        cache_nodos_ttl=int(mh.get("cache_nodos_ttl", 0)),
        durabilidad=str(mh.get("durabilidad", "exit")).strip().lower(),
        checkpoint_ruta=str(mh.get("checkpoint_ruta", ".cache/checkpoints/mapeo.sqlite")),
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
