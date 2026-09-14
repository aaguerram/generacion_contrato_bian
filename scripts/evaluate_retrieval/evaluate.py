"""Mide la recuperación de Service Domains sobre el corpus dorado. Sin llamadas LLM.

Compara, sobre las mismas consultas, cada canal por separado y sus combinaciones:

    lexico | vectorial | rrf(lexico+vectorial) | +graph | +rerank

y reporta Recall@1/5/10, MRR y la posición del positivo, más cuántos `hard_negatives` se colaron
por delante — que en este dominio es la métrica que duele: el problema no es que falte el
candidato correcto, es que llegan acompañados de plausibles que cuestan una llamada LLM cada uno.

Lo que este script NO puede decirte (y el documento de fases sí daba por bueno): que el pipeline
acierta. Recall@10 puede ser 1.0 y la corrida terminar en UNRESOLVED, que es exactamente lo que
pasó el 2026-09-14 — el SD correcto se recuperaba siempre como top-1 y el revisor adversarial lo
bloqueaba después. Por eso el gate "Recall@10 >= 0.95" se aprueba solo y no basta: hay que mirar
también `ownership_conflict_rate` y `operation_grounding_rate` de una corrida real.

Uso:
    .venv/bin/python scripts/evaluate_retrieval/evaluate.py
    .venv/bin/python scripts/evaluate_retrieval/evaluate.py --canales lexico,rrf,rrf+graph
    .venv/bin/python scripts/evaluate_retrieval/evaluate.py --json salida/retrieval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from src.adaptadores.salida.catalogo_json import CatalogoJson  # noqa: E402
from src.adaptadores.salida.grafo_bian_json import GrafoBianJson  # noqa: E402
from src.adaptadores.salida.recuperador_lexico import RecuperadorLexico  # noqa: E402
from src.adaptadores.salida.reranker_local import RerankerCrossEncoder  # noqa: E402
from src.configuracion.settings import cargar_settings  # noqa: E402
from src.dominio.fusion_rrf import fusion_rrf  # noqa: E402
from src.dominio.normalizacion import normalizar  # noqa: E402

CORPUS = Path(__file__).parent / "corpus_dorado.yaml"
CANALES_POR_DEFECTO = ("lexico", "vectorial", "qdrant", "rrf", "rrf+graph", "rrf+graph+rerank")
TOP_K = 20


def _vectorial(config, catalogo):
    """El vectorial es opcional: sin proveedor de embeddings utilizable se omite ese canal."""
    try:
        from src.adaptadores.salida.recuperador_vectorial import RecuperadorVectorial
        from src.configuracion.contenedor import _embeddings

        emb, modelo = _embeddings(config, None)
        return RecuperadorVectorial(catalogo, emb, modelo_embeddings=modelo)
    except Exception as exc:
        print(f"  (canal vectorial omitido: {exc})")
        return None


def _qdrant(config):
    """Canal Qdrant: solo si el índice externo está levantado y poblado."""
    try:
        from src.adaptadores.salida.recuperador_qdrant import RecuperadorQdrant
        from src.configuracion.contenedor import _embeddings

        emb, _ = _embeddings(config, None)
        return RecuperadorQdrant(
            emb,
            url=config.mapear_historias.qdrant_url,
            coleccion=config.mapear_historias.qdrant_coleccion,
        )
    except Exception as exc:
        print(f"  (canal qdrant omitido: {exc})")
        return None


def _ranking(canal: str, consulta: str, ctx: dict) -> list[str]:
    lex = [c.service_domain for c in ctx["lexico"].recuperar(consulta, TOP_K)]
    vec = (
        [c.service_domain for c in ctx["vectorial"].recuperar(consulta, TOP_K)]
        if ctx.get("vectorial")
        else []
    )
    if canal == "lexico":
        return lex
    if canal == "vectorial":
        return vec
    if canal == "qdrant":
        return (
            [c.service_domain for c in ctx["qdrant"].recuperar(consulta, TOP_K)]
            if ctx.get("qdrant")
            else []
        )
    base = [n for n, _ in fusion_rrf([r for r in (lex, vec) if r])]
    if canal == "rrf":
        return base
    if canal.startswith("rrf+graph"):
        expandidos = ctx["grafo"].expandir(base[:5], tope=5) if ctx.get("grafo") else []
        vistos = {normalizar(n) for n in base}
        base = base + [
            c.service_domain for c in expandidos if normalizar(c.service_domain) not in vistos
        ]
    if canal.endswith("rerank") and ctx.get("reranker"):
        docs = [(n, ctx["textos"].get(normalizar(n), n)) for n in base]
        base = [n for n, _ in ctx["reranker"].reordenar(consulta, docs, tope=len(docs))]
    return base


def evaluar(casos: list[dict], canales: tuple[str, ...], ctx: dict) -> dict:
    resultados: dict[str, dict] = {}
    for canal in canales:
        filas = []
        for caso in casos:
            ranking = [normalizar(n) for n in _ranking(canal, caso["consulta"], ctx)]
            positivo = normalizar(caso["positivo"])
            pos = ranking.index(positivo) + 1 if positivo in ranking else 0
            negativos = {normalizar(n) for n in caso.get("hard_negatives", [])}
            delante = sum(1 for n in ranking[: pos - 1 if pos else TOP_K] if n in negativos)
            filas.append({"id": caso["id"], "posicion": pos, "negativos_delante": delante})
        n = len(filas) or 1
        resultados[canal] = {
            "recall@1": round(sum(1 for f in filas if f["posicion"] == 1) / n, 4),
            "recall@5": round(sum(1 for f in filas if 0 < f["posicion"] <= 5) / n, 4),
            "recall@10": round(sum(1 for f in filas if 0 < f["posicion"] <= 10) / n, 4),
            "mrr": round(sum(1 / f["posicion"] for f in filas if f["posicion"]) / n, 4),
            "negativos_delante": sum(f["negativos_delante"] for f in filas),
            "no_recuperados": [f["id"] for f in filas if not f["posicion"]],
            "detalle": filas,
        }
    return resultados


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--canales", default=",".join(CANALES_POR_DEFECTO))
    p.add_argument("--json", default="", help="Escribe el informe completo en este archivo.")
    p.add_argument("--corpus", default=str(CORPUS))
    args = p.parse_args(argv)

    corpus = yaml.safe_load(Path(args.corpus).read_text(encoding="utf-8"))
    casos = corpus["casos"]
    config = cargar_settings()
    catalogo = CatalogoJson(config.ruta_catalogo_bian)
    entradas = catalogo.cargar()

    canales = tuple(c.strip() for c in args.canales.split(",") if c.strip())
    reranker = RerankerCrossEncoder(config.mapear_historias.reranker_modelo)
    ctx = {
        "lexico": RecuperadorLexico(catalogo),
        "vectorial": _vectorial(config, catalogo)
        if any("vectorial" in c or c.startswith("rrf") for c in canales)
        else None,
        "grafo": GrafoBianJson(config.ruta_grafo_bian),
        "qdrant": _qdrant(config) if "qdrant" in canales else None,
        "reranker": reranker if any(c.endswith("rerank") for c in canales) else None,
        "textos": {normalizar(e.service_domain): e.texto_para_indexar() for e in entradas},
    }

    print(f"corpus: {len(casos)} consultas · catálogo: {len(entradas)} SD\n")
    resultados = evaluar(casos, canales, ctx)

    print(f"{'canal':22s} {'R@1':>6s} {'R@5':>6s} {'R@10':>6s} {'MRR':>6s} {'neg.delante':>12s}")
    for canal, r in resultados.items():
        print(
            f"  {canal:20s} {r['recall@1']:6.2f} {r['recall@5']:6.2f} {r['recall@10']:6.2f} "
            f"{r['mrr']:6.3f} {r['negativos_delante']:12d}"
            + (f"   ✗ sin recuperar: {r['no_recuperados']}" if r["no_recuperados"] else "")
        )

    print(
        "\nRecall alto NO implica que el pipeline acierte: mide recuperación, no decisión. "
        "Contrastar con ownership_conflict_rate y operation_grounding_rate de una corrida real."
    )

    if args.json:
        destino = Path(args.json)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(
                {"corpus": args.corpus, "resultados": resultados}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        print(f"informe: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
