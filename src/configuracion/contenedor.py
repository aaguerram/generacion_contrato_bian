"""Composition root: cablea adaptadores concretos a los puertos y devuelve el caso de uso.

El chat LLM es un `ChatConFailover` construido desde `config.yaml`: recorre
`routing.llm_priority` y, dentro de cada proveedor, sus `llm.models` en orden.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from src.adaptadores.salida.adjudicador_langchain import AdjudicadorLangChain
from src.adaptadores.salida.analista_mapeo_langchain import AnalistaMapeoBianLangChain
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.catalogo_operaciones_bian_json import CatalogoOperacionesBianJson
from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml
from src.adaptadores.salida.embeddings_failover import EmbeddingsConFailover
from src.adaptadores.salida.embeddings_resiliente import EmbeddingsResiliente
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.llm.estrategia import ConfiguracionProveedor
from src.adaptadores.salida.llm.factory import crear_estrategia
from src.adaptadores.salida.llm.failover import ChatConFailover, EntradaModelo
from src.adaptadores.salida.mapeador_operaciones_langchain import MapeadorOperacionesLangChain
from src.adaptadores.salida.publicador_json import PublicadorJson
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.adaptadores.salida.recuperador_lexico import RecuperadorLexico
from src.adaptadores.salida.recuperador_vectorial import RecuperadorVectorial
from src.aplicacion.puertos.entrada import ValidarServiceDomainUseCase
from src.aplicacion.puertos.entrada_mapeo import MapearHistoriasUseCase
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.aplicacion.servicios.validar_service_domain import ValidarServiceDomainService
from src.configuracion.config_yaml import Config, ProveedorConfig
from src.dominio.clasificacion_historias import UmbralesMapeo
from src.dominio.decision_similitud import Umbrales

logger = logging.getLogger("generacion_contrato_ia_v2.contenedor")


def _cfg_proveedor(config: Config, prov: ProveedorConfig, modelo: str, modelo_emb: str) -> ConfiguracionProveedor:
    return ConfiguracionProveedor(
        chat_model=modelo,
        embeddings_model=modelo_emb,
        api_key=prov.api_key,
        temperature=config.llm.temperature,
        esfuerzo=config.llm.esfuerzo,
        seed=config.llm.seed,
        base_url=prov.base_url,
        structured_method=prov.structured_method,
    )


def _entradas_llm(config: Config, proveedor_forzado: str | None) -> list[EntradaModelo]:
    entradas: list[EntradaModelo] = []
    for prov in config.orden_llm(proveedor_forzado):
        emb = prov.embedding_models[0] if prov.embedding_models else ""
        for modelo in prov.llm_models:
            cfg = _cfg_proveedor(config, prov, modelo, emb or modelo)
            try:
                chat = crear_estrategia(prov.nombre, cfg).crear_chat_model()
            except (RuntimeError, ValueError, ImportError) as exc:
                logger.warning("omito %s:%s — %s", prov.nombre, modelo, exc)
                continue
            entradas.append(EntradaModelo(prov.nombre, modelo, chat, prov.structured_method))
    return entradas


def crear_chat_failover(config: Config, *, proveedor: str | None = None) -> ChatConFailover:
    nombre = (proveedor or "").strip().lower()
    if nombre == "fake":
        cfg = ConfiguracionProveedor("fake", "fake", None, config.llm.temperature, config.llm.esfuerzo)
        return ChatConFailover([EntradaModelo("fake", "fake", crear_estrategia("fake", cfg).crear_chat_model())])

    entradas = _entradas_llm(config, nombre or None)
    if not entradas:
        raise RuntimeError(
            "No hay ningún proveedor LLM utilizable (revisa las API keys del .env y "
            "`providers.*.enabled` en config.yaml), o usa --proveedor fake."
        )
    logger.info("cadena de failover LLM: %s", " -> ".join(e.etiqueta() for e in entradas))
    return ChatConFailover(
        entradas,
        reintentos_transitorios=config.llm.reintentos_transitorios,
        backoff_inicial_seg=config.llm.backoff_inicial_seg,
        backoff_max_seg=config.llm.backoff_max_seg,
    )


def _candidatos_embedding(config: Config, proveedor: str | None) -> list[tuple[str, str, EmbeddingsResiliente]]:
    """Lista ordenada por precisión: proveedores de `embedding_priority` × sus `embedding.models`."""
    salida: list[tuple[str, str, EmbeddingsResiliente]] = []
    for prov in config.orden_embedding(proveedor):
        for modelo in prov.embedding_models:
            cfg = _cfg_proveedor(config, prov, modelo, modelo)
            try:
                emb = crear_estrategia(prov.nombre, cfg).crear_embeddings()
            except (RuntimeError, ValueError, ImportError) as exc:
                logger.warning("omito embeddings %s:%s — %s", prov.nombre, modelo, exc)
                continue
            salida.append((prov.nombre, modelo, EmbeddingsResiliente(emb)))
    return salida


def _embeddings(config: Config, proveedor: str | None):
    nombre = (proveedor or "").strip().lower()
    candidatos = _candidatos_embedding(config, nombre or None)
    if not candidatos:
        raise RuntimeError(
            "No hay proveedor de embeddings utilizable para RAG vectorial (revisa las API keys "
            "del .env y `providers.*.embedding.models` + `routing.embedding_priority` en config.yaml)."
        )
    failover = EmbeddingsConFailover(candidatos)
    prov, modelo = failover.resolver()  # fija el modelo activo (probe) antes de tocar la caché
    logger.info("embeddings activo: %s:%s  (cadena por precisión: %s)", prov, modelo, failover.descripcion)
    return failover, modelo


# ── validar-sd ──────────────────────────────────────────────────────────────
def crear_caso_uso(config: Config, *, proveedor: str | None = None) -> ValidarServiceDomainUseCase:
    vs = config.validar_sd
    catalogo = CatalogoJson(config.ruta_sd_json)

    recuperador: RecuperadorSemanticoPort
    if vs.rag_estrategia == "vectorial":
        emb, modelo_emb = _embeddings(config, proveedor)
        recuperador = RecuperadorVectorial(catalogo, emb, modelo_embeddings=modelo_emb)
    else:
        recuperador = RecuperadorLexico(catalogo)

    adjudicador = AdjudicadorLangChain(crear_chat_failover(config, proveedor=proveedor))

    return ValidarServiceDomainService(
        catalogo,
        recuperador,
        adjudicador,
        PublicadorJson(),
        rag_top_k=vs.rag_top_k,
        umbrales=Umbrales(alto=vs.rag_umbral_alto, bajo=vs.rag_umbral_bajo),
    )


# ── mapear-historias ────────────────────────────────────────────────────────
def _sha256_archivo(ruta: str) -> str:
    try:
        return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()
    except OSError:
        return ""


def _recuperadores_hibridos(
    config: Config, catalogo: CatalogoJson, proveedor: str | None
) -> list[RecuperadorSemanticoPort]:
    """Léxico (siempre, sin API) + vectorial (best-effort: si no hay proveedor de embeddings
    utilizable, se sigue solo con léxico -- nunca rompe la corrida por esto, igual que
    `_h_preparar` degrada a "sin retrieval híbrido" si la lista queda vacía)."""
    recuperadores: list[RecuperadorSemanticoPort] = [RecuperadorLexico(catalogo)]
    try:
        emb, modelo_emb = _embeddings(config, proveedor)
        recuperadores.append(RecuperadorVectorial(catalogo, emb, modelo_embeddings=modelo_emb))
    except RuntimeError as exc:
        logger.warning(
            "retrieval híbrido: sin proveedor de embeddings utilizable (%s); sigo solo con "
            "recuperación léxica (rapidfuzz)", exc,
        )
    return recuperadores


def crear_caso_uso_mapeo(config: Config, *, proveedor: str | None = None,
                         actualizar_cache_bian: bool = False) -> MapearHistoriasUseCase:
    mh = config.mapear_historias
    chat = crear_chat_failover(config, proveedor=proveedor)
    catalog_sha = _sha256_archivo(config.ruta_sd_json)

    catalogo = CatalogoJson(config.ruta_sd_json, config.ruta_jerarquia)
    catalogo_operaciones = CatalogoBianCache(
        config.ruta_operaciones, config.ruta_cache_bian, mh.release_bian,
        permitir_descargas=mh.descargar_faltantes,
    )
    catalogo_bom = CatalogoBomPuml(config.ruta_bian_puml) if mh.bom_puml_habilitado else None
    recuperadores = (
        _recuperadores_hibridos(config, catalogo, proveedor) if mh.retrieval_hibrido_habilitado else []
    )

    analista = AnalistaMapeoBianLangChain(
        chat, modelo_desc=chat.descripcion, temperature=config.llm.temperature,
        catalog_sha256=catalog_sha, rol_max_chars=mh.rol_max_chars,
    )
    mapeador = MapeadorOperacionesLangChain(
        chat, modelo_desc=chat.descripcion, temperature=config.llm.temperature, catalog_sha256=catalog_sha,
    )

    return MapearHistoriasServiceDomainsService(
        catalogo,
        LectorHistoriasFilesystem(),
        analista,
        PublicadorMapeoJson(),
        catalogo_operaciones,
        mapeador,
        catalogo_bom=catalogo_bom,
        umbrales=UmbralesMapeo(directo=mh.umbral_directo, tentativo=mh.umbral_tentativo),
        concurrencia=mh.concurrencia,
        concurrencia_candidatos=mh.concurrencia_candidatos,
        max_candidatos_hu=mh.max_candidatos_hu,
        mapear_operaciones=mh.paso2_operaciones,
        parametros_base={
            "cadena_llm": chat.descripcion,
            "esfuerzo": config.llm.esfuerzo,
            "catalog_sha256": catalog_sha,
            "evidencia_bian": "docs/SD.json + docs/bian-business-areas.json + docs/bian-operation-catalogs.json + docs/bian-cache",
        },
        actualizar_cache_bian=actualizar_cache_bian,
        top_n_omitidos=mh.top_n_omitidos,
        recuperadores=recuperadores,
        retrieval_top_k=mh.retrieval_top_k,
        retrieval_max_inyectados=mh.retrieval_max_inyectados,
    )
