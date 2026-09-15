"""Adaptadores del `RerankerPort`: cross-encoder local, con respaldos seguros.

Por qué local y no otra llamada LLM: el proyecto ya tiene un problema de cuota documentado —Groq
devuelve 413 con los catálogos grandes, Gemini agota sus 20 req/día a mitad de corrida—, así que
sumar una llamada LLM por historia empeoraría justo lo que se quiere aliviar. Un cross-encoder
corre en el host sin cuota ni red.

Dos implementaciones:

- `RerankerCrossEncoder`: `sentence-transformers` con un cross-encoder multilingüe. Es la buena,
  pero arrastra torch, así que la dependencia es OPCIONAL: se importa perezosamente y, si no está
  instalada o el modelo no se puede cargar, se degrada al respaldo en vez de tumbar la corrida.
- `RerankerNulo`: conserva el orden que ya traía. Es el respaldo por defecto cuando el
  cross-encoder no está disponible, y NO es una elección perezosa: medido con
  `scripts/evaluate_retrieval/`, reordenar con el léxico hundía Recall@10 de 0.71 a **0.14**,
  porque compara tokens de una consulta en español contra el catálogo BIAN en inglés. Un
  reranker que empeora es peor que ninguno, así que el respaldo no reordena.
- `RerankerLexico`: solapamiento de tokens. Se conserva porque es determinista y sirve para
  probar el cableado sin descargar un modelo, pero **no debe usarse en el camino de retrieval**
  por lo dicho arriba.

Ninguno decide nada: reordenan y recortan (ver `RerankerPort`).
"""

from __future__ import annotations

import logging
import re

from src.aplicacion.puertos.reranker import RerankerPort

logger = logging.getLogger(__name__)

# Multilingüe, que es el requisito real: las HU están en español y el catálogo BIAN en inglés.
# 568M de parámetros = **2,2 GB en disco** en fp32 (medido en `~/.cache/hf-local`), no 560 MB.
# Se descarga una vez; cargarlo cuesta ~18 s por proceso y reordenar 10 candidatos ~0,4 s en GPU.
MODELO_POR_DEFECTO = "BAAI/bge-reranker-v2-m3"

_TOKEN = re.compile(r"[a-z0-9áéíóúñü]+")


def _tokens(texto: str) -> set[str]:
    return {t for t in _TOKEN.findall((texto or "").lower()) if len(t) > 2}


class RerankerNulo(RerankerPort):
    """No reordena: devuelve el orden recibido. El respaldo seguro."""

    def reordenar(
        self, consulta: str, documentos: list[tuple[str, str]], *, tope: int
    ) -> list[tuple[str, float]]:
        return [(clave, 0.0) for clave, _ in documentos[:tope]]


class RerankerLexico(RerankerPort):
    """Respaldo determinista: Jaccard de tokens. Sin red, sin modelo, sin sorpresas."""

    def reordenar(
        self, consulta: str, documentos: list[tuple[str, str]], *, tope: int
    ) -> list[tuple[str, float]]:
        q = _tokens(consulta)
        if not q:
            return [(clave, 0.0) for clave, _ in documentos[:tope]]
        puntuados = []
        for clave, texto in documentos:
            d = _tokens(texto)
            score = len(q & d) / len(q | d) if d else 0.0
            puntuados.append((clave, round(score, 6)))
        puntuados.sort(key=lambda x: (-x[1], x[0]))
        return puntuados[:tope]


class RerankerCrossEncoder(RerankerPort):
    """Cross-encoder local vía `sentence-transformers`, con degradación a NO reordenar.

    Cachea por (modelo, consulta, conjunto de candidatos): dentro de una funcionalidad varias
    historias comparten intención y candidatos, y el cross-encoder es determinista, así que
    recalcular es puro gasto. Mismo patrón que el cache por modelo activo del
    `RecuperadorVectorial`, pero en memoria: el índice tiene sentido persistirlo entre corridas;
    un reranking de diez candidatos, no.
    """

    def __init__(self, modelo: str = MODELO_POR_DEFECTO, *, respaldo: RerankerPort | None = None) -> None:
        self._nombre = modelo
        self._respaldo = respaldo or RerankerNulo()
        self._modelo = None
        self._fallido = False
        self._cache: dict[tuple, list[tuple[str, float]]] = {}

    def _cargar(self):
        if self._modelo is not None or self._fallido:
            return self._modelo
        try:
            from sentence_transformers import CrossEncoder  # import perezoso: torch pesa
        except ImportError:
            logger.warning(
                "sentence-transformers no está instalado; reranker degradado a léxico "
                "(pip install sentence-transformers para activar '%s')",
                self._nombre,
            )
            self._fallido = True
            return None
        try:
            self._modelo = CrossEncoder(self._nombre)
        except Exception as exc:  # modelo no descargable, sin espacio, sin permisos…
            logger.warning("No se pudo cargar el reranker '%s' (%s); no se reordenará", self._nombre, exc)
            self._fallido = True
        return self._modelo

    def reordenar(
        self, consulta: str, documentos: list[tuple[str, str]], *, tope: int
    ) -> list[tuple[str, float]]:
        if not documentos:
            return []
        clave_cache = (self._nombre, consulta, tuple(sorted(c for c, _ in documentos)), tope)
        en_cache = self._cache.get(clave_cache)
        if en_cache is not None:
            return en_cache
        modelo = self._cargar()
        if modelo is None:
            return self._respaldo.reordenar(consulta, documentos, tope=tope)
        try:
            scores = modelo.predict([(consulta, texto) for _, texto in documentos])
        except Exception as exc:  # OOM, tensor mal formado, modelo corrupto…
            logger.warning("Reranker '%s' falló en predict (%s); no se reordenará", self._nombre, exc)
            self._fallido = True
            return self._respaldo.reordenar(consulta, documentos, tope=tope)
        puntuados = [(clave, float(score)) for (clave, _), score in zip(documentos, scores, strict=True)]
        puntuados.sort(key=lambda x: (-x[1], x[0]))
        salida = puntuados[:tope]
        self._cache[clave_cache] = salida
        return salida
