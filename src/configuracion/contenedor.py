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
from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.cache_nodos_archivo import CacheNodosArchivo
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml
from src.adaptadores.salida.catalogo_entidades_json import CatalogoEntidadesJson
from src.adaptadores.salida.checkpointer_sqlite import crear_checkpointer
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.embeddings_failover import EmbeddingsConFailover
from src.adaptadores.salida.embeddings_resiliente import EmbeddingsResiliente
from src.adaptadores.salida.grafo_bian_json import GrafoBianJson
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.llm.estrategia import ConfiguracionProveedor
from src.adaptadores.salida.llm.factory import crear_estrategia
from src.adaptadores.salida.llm.failover import ChatConFailover, EntradaModelo
from src.adaptadores.salida.mapeador_operaciones_langchain import MapeadorOperacionesLangChain
from src.adaptadores.salida.publicador_json import PublicadorJson
from src.adaptadores.salida.prompts_mapeo import SPEC_OPERACIONES
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.adaptadores.salida.recuperador_bm25 import RecuperadorBM25
from src.adaptadores.salida.recuperador_clases_bm25 import RecuperadorClasesBM25
from src.adaptadores.salida.recuperador_clases_vectorial import RecuperadorClasesVectorial
from src.adaptadores.salida.recuperador_lexico import RecuperadorLexico
from src.adaptadores.salida.recuperador_qdrant import RecuperadorQdrant
from src.adaptadores.salida.recuperador_vectorial import RecuperadorVectorial
from src.adaptadores.salida.reranker_local import RerankerCrossEncoder
from src.aplicacion.puertos.entrada import ValidarServiceDomainUseCase
from src.aplicacion.puertos.entrada_mapeo import MapearHistoriasUseCase
from src.aplicacion.puertos.recuperador import RecuperadorSemanticoPort
from src.aplicacion.puertos.recuperador_clases import RecuperadorClasesPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.aplicacion.servicios.validar_service_domain import ValidarServiceDomainService
from src.configuracion.config_yaml import Config, ProveedorConfig
from src.dominio.clasificacion_historias import UmbralesMapeo
from src.dominio.decision_similitud import Umbrales

logger = logging.getLogger("generacion_contrato_ia_v2.contenedor")


def _cfg_proveedor(
    config: Config, prov: ProveedorConfig, modelo: str, modelo_emb: str
) -> ConfiguracionProveedor:
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


def _entradas_llm(
    config: Config, proveedor_forzado: str | None, nodo: str | None = None
) -> list[EntradaModelo]:
    entradas: list[EntradaModelo] = []
    for prov in config.orden_llm(proveedor_forzado, nodo=nodo):
        emb = prov.embedding_models[0] if prov.embedding_models else ""
        for modelo in prov.llm_models:
            cfg = _cfg_proveedor(config, prov, modelo, emb or modelo)
            try:
                chat = crear_estrategia(prov.nombre, cfg).crear_chat_model()
            except (RuntimeError, ValueError, ImportError) as exc:
                logger.warning("omito %s:%s — %s", prov.nombre, modelo, exc)
                continue
            entradas.append(
                EntradaModelo(
                    prov.nombre,
                    modelo,
                    chat,
                    prov.structured_method,
                    max_input_tokens=prov.max_input_tokens(modelo),
                )
            )
    return entradas


def crear_chat_failover(
    config: Config, *, proveedor: str | None = None, nodo: str | None = None
) -> ChatConFailover:
    """Cadena de failover. `nodo` (un `prompt_id`) permite darle a un nodo concreto otro orden de
    proveedores -ver `routing.llm_priority_por_nodo`-; sin él, todos comparten `llm_priority`."""
    nombre = (proveedor or "").strip().lower()
    if nombre == "fake":
        cfg = ConfiguracionProveedor(
            "fake", "fake", None, config.llm.temperature, config.llm.esfuerzo
        )
        return ChatConFailover(
            [EntradaModelo("fake", "fake", crear_estrategia("fake", cfg).crear_chat_model())]
        )

    entradas = _entradas_llm(config, nombre or None, nodo)
    if not entradas:
        raise RuntimeError(
            "No hay ningún proveedor LLM utilizable (revisa las API keys del .env y "
            "`providers.*.enabled` en config.yaml), o usa --proveedor fake."
        )
    logger.info(
        "cadena de failover LLM%s: %s",
        f" [{nodo}]" if nodo else "",
        # Con el presupuesto de entrada a la vista: es lo que decide si un modelo se llega a
        # llamar siquiera para los nodos de prompt grande.
        " -> ".join(
            e.etiqueta() + (f"(<={e.max_input_tokens} tok)" if e.max_input_tokens else "")
            for e in entradas
        ),
    )
    return ChatConFailover(
        entradas,
        reintentos_transitorios=config.llm.reintentos_transitorios,
        backoff_inicial_seg=config.llm.backoff_inicial_seg,
        backoff_max_seg=config.llm.backoff_max_seg,
        chars_por_token=config.llm.chars_por_token,
        tokenizador=config.llm.tokenizador,
    )


def _candidatos_embedding(
    config: Config, proveedor: str | None
) -> list[tuple[str, str, EmbeddingsResiliente]]:
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
    logger.info(
        "embeddings activo: %s:%s  (cadena por precisión: %s)", prov, modelo, failover.descripcion
    )
    return failover, modelo


# ── validar-sd ──────────────────────────────────────────────────────────────
def crear_caso_uso(config: Config, *, proveedor: str | None = None) -> ValidarServiceDomainUseCase:
    vs = config.validar_sd
    catalogo = CatalogoJson(config.ruta_catalogo_bian)

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
    # El canal disperso se elige por caso de uso: rapidfuzz compara NOMBRES (validar-sd), BM25
    # indexa el TEXTO del SD con IDF y traduce ES->EN (mapear-historias). Ver
    # `scripts/evaluate_retrieval/` para los números que sostienen la elección.
    recuperadores: list[RecuperadorSemanticoPort] = [
        RecuperadorBM25(catalogo)
        if config.mapear_historias.retrieval_canal_lexico == "bm25"
        else RecuperadorLexico(catalogo)
    ]
    try:
        emb, modelo_emb = _embeddings(config, proveedor)
        if config.mapear_historias.vector_store == "qdrant":
            # El índice externo NO reemplaza al léxico: se suma como otro recuperador, igual que
            # el vectorial en memoria, y si Qdrant no responde ese canal devuelve vacío.
            recuperadores.append(
                RecuperadorQdrant(
                    emb,
                    url=config.mapear_historias.qdrant_url,
                    coleccion=config.mapear_historias.qdrant_coleccion,
                )
            )
        else:
            recuperadores.append(RecuperadorVectorial(catalogo, emb, modelo_embeddings=modelo_emb))
    except RuntimeError as exc:
        logger.warning(
            "retrieval híbrido: sin proveedor de embeddings utilizable (%s); sigo solo con "
            "recuperación léxica (rapidfuzz)",
            exc,
        )
    return recuperadores


def _recuperadores_clases(
    config: Config, catalogo_entidades: CatalogoEntidadesJson, proveedor: str | None
) -> list[RecuperadorClasesPort]:
    """Canales del paso 1 del canal de propiedad de clases BOM, según `entidades_canales`.

    `diccionario` no es un recuperador (lo aplica el servicio); `bm25` no necesita red; `vectorial`
    es best-effort: sin proveedor de embeddings utilizable se sigue sin ese canal, con aviso.
    """
    canales = set(config.mapear_historias.entidades_canales)
    salida: list[RecuperadorClasesPort] = []
    if "bm25" in canales:
        salida.append(RecuperadorClasesBM25(catalogo_entidades))
    if "vectorial" in canales:
        try:
            emb, modelo_emb = _embeddings(config, proveedor)
            salida.append(
                RecuperadorClasesVectorial(catalogo_entidades, emb, modelo_embeddings=modelo_emb)
            )
        except RuntimeError as exc:
            logger.warning(
                "canal vectorial de clases BOM: sin proveedor de embeddings utilizable (%s); "
                "sigo con los demás canales",
                exc,
            )
    desconocidos = canales - {"diccionario", "bm25", "vectorial"}
    if desconocidos:
        logger.warning("entidades_canales desconocidos, ignorados: %s", sorted(desconocidos))
    return salida


def crear_caso_uso_mapeo(
    config: Config, *, proveedor: str | None = None, actualizar_cache_bian: bool = False
) -> MapearHistoriasUseCase:
    mh = config.mapear_historias
    chat = crear_chat_failover(config, proveedor=proveedor)
    # Una cadena propia por cada nodo que la pida en `routing.llm_priority_por_nodo`. Se construye
    # una sola vez por nodo y se reutiliza; cada LLAMADA vuelve a recorrer su cadena desde el
    # principio (ver ChatConFailover), así que un proveedor que falló por tamaño de prompt en un
    # nodo grande se vuelve a intentar en el siguiente nodo, que quizá sí le cabe.
    chats_por_nodo = {
        nodo: crear_chat_failover(config, proveedor=proveedor, nodo=nodo)
        for nodo in config.routing.llm_priority_por_nodo
    }
    catalog_sha = _sha256_archivo(config.ruta_catalogo_bian)

    catalogo = CatalogoJson(config.ruta_catalogo_bian)
    catalogo_operaciones = CatalogoBianCache(
        config.ruta_operaciones,
        config.ruta_cache_bian,
        mh.release_bian,
        permitir_descargas=mh.descargar_faltantes,
    )
    catalogo_bom = (
        CatalogoBomPuml(config.ruta_bian_puml, catalogo.rutas_bom_puml())
        if mh.bom_puml_habilitado
        else None
    )
    recuperadores = (
        _recuperadores_hibridos(config, catalogo, proveedor)
        if mh.retrieval_hibrido_habilitado
        else []
    )
    catalogo_entidades = (
        CatalogoEntidadesJson(config.ruta_entidades) if mh.entidades_bom_habilitado else None
    )
    recuperadores_clases = (
        _recuperadores_clases(config, catalogo_entidades, proveedor)
        if catalogo_entidades is not None
        else []
    )

    analista = AnalistaMapeoBianLangChain(
        chat,
        modelo_desc=chat.descripcion,
        temperature=config.llm.temperature,
        catalog_sha256=catalog_sha,
        rol_max_chars=mh.rol_max_chars,
        cag_chars_por_sd=mh.cag_chars_por_sd if mh.cag_habilitado else 0,
        chats_por_nodo=chats_por_nodo,
    )
    chat_operaciones = chats_por_nodo.get(SPEC_OPERACIONES.id, chat)
    mapeador = MapeadorOperacionesLangChain(
        chat_operaciones,
        modelo_desc=chat_operaciones.descripcion,
        temperature=config.llm.temperature,
        catalog_sha256=catalog_sha,
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
            "evidencia_bian": "docs/BIAN_Service_Landscape_V14.0_Matrix_View.json + docs/bian-operation-catalogs.json + docs/bian-cache",
        },
        actualizar_cache_bian=actualizar_cache_bian,
        top_n_omitidos=mh.top_n_omitidos,
        routing_jerarquico=mh.routing_jerarquico_habilitado,
        catalogo_entidades=catalogo_entidades,
        entidades_max_candidatos=mh.entidades_max_candidatos,
        recuperadores_clases=recuperadores_clases,
        entidades_canal_diccionario="diccionario" in mh.entidades_canales,
        entidades_top_k_clases=mh.entidades_top_k_clases,
        entidades_rrf_k=mh.entidades_rrf_k,
        evidencia_bom_en_candidatos=mh.evidencia_bom_en_candidatos,
        candidatos_por_dominio=mh.candidatos_por_dominio_habilitado,
        candidatos_grupo_min_sd=mh.candidatos_grupo_min_sd,
        entidades_min_score_rescate=mh.entidades_min_score_rescate,
        entidades_min_canales_rescate=mh.entidades_min_canales_rescate,
        recuperadores=recuperadores,
        retrieval_top_k=mh.retrieval_top_k,
        retrieval_max_inyectados=mh.retrieval_max_inyectados,
        rrf_k=mh.rrf_k,
        rrf_pesos=[mh.rrf_peso_lexico, mh.rrf_peso_vectorial],
        # El grafo se carga si lo pide CUALQUIERA de sus dos usos (expandir candidatos o
        # confirmar conflictos); `graph_rag_max_inyectados=0` deja solo el segundo.
        grafo=GrafoBianJson(config.ruta_grafo_bian)
        if (mh.graph_rag_habilitado or mh.grafo_senales_adversarial)
        else None,
        graph_rag_max_inyectados=mh.graph_rag_max_inyectados if mh.graph_rag_habilitado else 0,
        senales_grafo_adversarial=mh.grafo_senales_adversarial,
        crag_reintento=mh.crag_reintento_habilitado,
        reranker=RerankerCrossEncoder(mh.reranker_modelo) if mh.reranker_habilitado else None,
        presupuesto_segundos_hu=mh.presupuesto_segundos_hu,
        cache_nodos=CacheNodosArchivo(config.ruta_cache_nodos)
        if mh.cache_nodos_habilitado
        else None,
        cache_nodos_ttl=mh.cache_nodos_ttl,
        durabilidad=mh.durabilidad,
        # La base se abre (y se crea) solo si se pidió durabilidad: una corrida normal no debe
        # dejar un archivo SQLite por ahí sin que nadie lo haya pedido.
        checkpointer=crear_checkpointer(config.ruta_checkpoints)
        if mh.durabilidad != "exit"
        else None,
    )
