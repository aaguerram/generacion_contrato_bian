"""BM25 Okapi sobre el catálogo BIAN. Puro: solo stdlib.

Por qué existe, si ya había un canal "léxico": `RecuperadorLexico` (rapidfuzz) compara la consulta
contra el **nombre** del Service Domain con una métrica de parecido de cadenas. Eso es lo correcto
para `validar-sd`, donde la consulta ES un nombre — y es justo lo que no sirve en
`mapear-historias`, donde la consulta es lenguaje natural: sin IDF, "the customer wants to be
notified" no pesa más `Correspondence` que `Customer`, y medido sobre el corpus dorado ese canal
acierta 0.29 mientras el vectorial acierta 0.86, arrastrando la fusión RRF a 0.71.

BM25 indexa el TEXTO del Service Domain (`texto_para_indexar()`: rol, ejemplos, key features,
clasificación) y pesa cada término por su rareza en el catálogo, que es lo que este dominio pide:
los términos que deciden ("correspondence", "collateral", "entitlement") son raros; los que
confunden ("customer", "party", "management") están en cientos de Service Domains.

Fórmula estándar (Robertson/Sparck Jones), con los parámetros habituales `k1=1.5`, `b=0.75`:

    score(q, d) = Σ_t  IDF(t) · (f(t,d)·(k1+1)) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))
    IDF(t)      = ln( 1 + (N − n(t) + 0.5) / (n(t) + 0.5) )
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from src.dominio.vocabulario_bian import EQUIVALENCIAS_RETRIEVAL

_K1 = 1.5
_B = 0.75
_TOKEN = re.compile(r"[a-z0-9]+")
# Palabras que no discriminan nada en este corpus: aparecen en el texto de casi cualquier Service
# Domain (o son conectores del español/inglés de las HU). Quitarlas no cambia el ranking -su IDF
# ya es mínimo-, pero abarata el índice y evita empates por ruido.
_VACIAS = frozenset(
    """a al algo ante antes como con contra cual cuando de del desde donde dos el ella ellas ellos
    en entre era eran es esa ese eso esta este esto ha han hasta hay la las le les lo los mas me mi
    mucho muy no nos o os otra otro para pero poco por porque que quien se sea segun ser si sin
    sobre solo son su sus te ti tu tus un una uno unos y ya
    a an and are as at be been but by for from has have he her his how i if in into is it its of on
    or she that the their them then there these they this to was were what when where which who
    will with would you your""".split()
)


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sin acentos, alfanumérico, sin palabras vacías, y **traducido al inglés**.

    Sin el último paso BM25 es inútil aquí: las HU están en español y el catálogo BIAN entero en
    inglés, así que consulta y corpus no comparten ni un término (ver `vocabulario_bian`).
    """
    plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return [
        EQUIVALENCIAS_RETRIEVAL.get(t, t)
        for t in _TOKEN.findall(plano.lower())
        if t not in _VACIAS and len(t) > 1
    ]


class IndiceBM25:
    """Índice invertido inmutable. Se construye una vez por catálogo y se consulta N veces."""

    def __init__(self, documentos: list[tuple[str, str]]) -> None:
        """`documentos` = [(identificador, texto)]. El identificador se devuelve tal cual."""
        self._ids = [ident for ident, _ in documentos]
        frecuencias = [Counter(tokenizar(texto)) for _, texto in documentos]
        self._longitudes = [sum(f.values()) for f in frecuencias]
        total = len(documentos)
        self._media = (sum(self._longitudes) / total) if total else 0.0
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for i, frec in enumerate(frecuencias):
            for termino, veces in frec.items():
                self._postings.setdefault(termino, []).append((i, veces))
        self._idf = {
            termino: math.log(1 + (total - len(post) + 0.5) / (len(post) + 0.5))
            for termino, post in self._postings.items()
        }

    def __len__(self) -> int:
        return len(self._ids)

    def buscar(self, consulta: str, k: int) -> list[tuple[str, float]]:
        """Top-k `(identificador, score)` desc. Los documentos sin ningún término de la consulta
        no aparecen: BM25 no inventa un orden entre documentos que no comparten nada."""
        acumulado: dict[int, float] = {}
        for termino in tokenizar(consulta):
            post = self._postings.get(termino)
            if not post:
                continue
            idf = self._idf[termino]
            for i, veces in post:
                norma = 1 - _B + _B * (self._longitudes[i] / self._media if self._media else 1.0)
                acumulado[i] = acumulado.get(i, 0.0) + idf * (veces * (_K1 + 1)) / (
                    veces + _K1 * norma
                )
        mejores = sorted(acumulado.items(), key=lambda kv: (-kv[1], self._ids[kv[0]]))[: max(0, k)]
        return [(self._ids[i], round(score, 6)) for i, score in mejores]
