"""Mide la recuperación de Service Domains sobre el corpus dorado. Sin llamadas LLM.

Compara, sobre las mismas consultas, cada canal por separado y sus combinaciones:

    lexico | vectorial | rrf(lexico+vectorial) | +graph | +rerank
    bom-dic | bom-bm25 | bom-vec | bom-rrf | bom-rrf3 | rrf-bm25+bom | bm25+bom

Los `bom-*` son el canal de PROPIEDAD de clases del BOM (`docs/entity.json`, nodo 2a): la consulta
recupera CLASES (diccionario ES->EN, BM25 sobre el documento de la clase, embeddings sobre el texto
natural, o su fusión RRF) y el Service Domain sale de quién DEFINE cada clase (ocurrencia sin
`Extensible`), no de un ranking de texto del SD. `rrf-bm25+bom` fusiona a nivel de SD el mejor
canal de texto con `bom-rrf3`; `bm25+bom` es la variante sin embeddings (todo offline).

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

from src.adaptadores.salida.catalogo_entidades_json import CatalogoEntidadesJson  # noqa: E402
from src.adaptadores.salida.catalogo_json import CatalogoJson  # noqa: E402
from src.adaptadores.salida.grafo_bian_json import GrafoBianJson  # noqa: E402
from src.adaptadores.salida.recuperador_bm25 import RecuperadorBM25  # noqa: E402
from src.adaptadores.salida.recuperador_clases_bm25 import RecuperadorClasesBM25  # noqa: E402
from src.adaptadores.salida.recuperador_lexico import RecuperadorLexico  # noqa: E402
from src.adaptadores.salida.reranker_local import RerankerCrossEncoder  # noqa: E402
from src.configuracion.settings import cargar_settings  # noqa: E402
from src.dominio.entidades_bian import (  # noqa: E402
    ConsultaClases,
    candidatos_por_propiedad,
    clases_requeridas,
    clases_requeridas_desde_rankings,
)
from src.dominio.fusion_rrf import fusion_rrf  # noqa: E402
from src.dominio.modelos import VARIANTES_TEXTO_SD  # noqa: E402
from src.dominio.normalizacion import normalizar  # noqa: E402

CORPUS = Path(__file__).parent / "corpus_dorado.yaml"
CANALES_POR_DEFECTO = (
    "lexico",
    "bm25",
    "vectorial",
    "qdrant",
    "rrf",
    "rrf-bm25",
    "rrf+graph",
    "rrf+graph+rerank",
    "bom-dic",
    "bom-bm25",
    "bom-vec",
    "bom-rrf",
    "bom-rrf3",
    "bm25+bom",
    "rrf-bm25+bom",
    "rrf-bm25+bom-rrf",
)
CANALES_BOM = (
    "bom-dic", "bom-bm25", "bom-vec", "bom-rrf", "bom-rrf3", "bm25+bom", "rrf-bm25+bom", "rrf-bm25+bom-rrf",
)
TOP_K = 20
TOP_K_CLASES = 12
K_RRF_CLASES = 20
# Rejilla del barrido `--barrido`: k de RRF x peso del canal disperso (el denso queda fijo en 1.0).
KS_BARRIDO = (10, 20, 60)
PESOS_BARRIDO = (0.0, 0.25, 0.5, 1.0)


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


def _vectorial_clases(config, catalogo_entidades):
    try:
        from src.adaptadores.salida.recuperador_clases_vectorial import RecuperadorClasesVectorial
        from src.configuracion.contenedor import _embeddings

        emb, modelo = _embeddings(config, None)
        return RecuperadorClasesVectorial(catalogo_entidades, emb, modelo_embeddings=modelo)
    except Exception as exc:
        print(f"  (canal vectorial de clases omitido: {exc})")
        return None


def _ranking_bom(canal: str, consulta: str, ctx: dict) -> list[str]:
    """Service Domains vía propiedad de clases: paso 1 según el canal, pasos 2-4 siempre iguales."""
    bom = ctx.get("bom")
    if not bom:
        return []
    clases, enums = bom["clases"], bom["enums"]
    q = ConsultaClases.desde_textos([consulta])
    rankings: dict[str, list[str]] = {}
    quiere = {
        "bom-dic": {"diccionario"},
        "bom-bm25": {"bm25"},
        "bom-vec": {"vectorial"},
        "bom-rrf": {"bm25", "vectorial"},
        "bom-rrf3": {"diccionario", "bm25", "vectorial"},
    }[canal]
    if "diccionario" in quiere:
        rankings["diccionario"] = [
            r.clase for r in clases_requeridas(q.terminos, clases, nombres_enum=enums, tope=TOP_K_CLASES)
        ]
    if "bm25" in quiere and bom.get("bm25"):
        rankings["bm25"] = [c.clase for c in bom["bm25"].recuperar(q, TOP_K_CLASES)]
    if "vectorial" in quiere and bom.get("vectorial"):
        rankings["vectorial"] = [c.clase for c in bom["vectorial"].recuperar(q, TOP_K_CLASES)]
    if canal == "bom-dic":
        requeridas = clases_requeridas(q.terminos, clases, nombres_enum=enums, tope=TOP_K_CLASES)
    else:
        requeridas = clases_requeridas_desde_rankings(rankings, clases, k=K_RRF_CLASES, tope=TOP_K_CLASES)
    return [
        c.service_domain
        for c in candidatos_por_propiedad(requeridas, clases, nombres_enum=enums, tope=TOP_K)
    ]


def _ranking(canal: str, consulta: str, ctx: dict, *, k_rrf: int = 60, peso_disperso: float = 1.0) -> list[str]:
    if canal.startswith("bom-"):
        return _ranking_bom(canal, consulta, ctx)
    if canal == "bm25+bom":
        # Todo offline: BM25 sobre el texto del SD + propiedad de clases (diccionario + BM25).
        rankings = {}
        bom = ctx.get("bom") or {}
        if bom:
            q = ConsultaClases.desde_textos([consulta])
            rankings["diccionario"] = [
                r.clase for r in clases_requeridas(q.terminos, bom["clases"], nombres_enum=bom["enums"], tope=TOP_K_CLASES)
            ]
            if bom.get("bm25"):
                rankings["bm25"] = [c.clase for c in bom["bm25"].recuperar(q, TOP_K_CLASES)]
            requeridas = clases_requeridas_desde_rankings(rankings, bom["clases"], k=K_RRF_CLASES, tope=TOP_K_CLASES)
            via_bom = [c.service_domain for c in candidatos_por_propiedad(requeridas, bom["clases"], nombres_enum=bom["enums"], tope=TOP_K)]
        else:
            via_bom = []
        bm = [c.service_domain for c in ctx["bm25"].recuperar(consulta, TOP_K)] if ctx.get("bm25") else []
        canales = [r for r in (bm, via_bom) if r]
        return [n for n, _ in fusion_rrf(canales, k=k_rrf)]
    if canal in ("rrf-bm25+bom", "rrf-bm25+bom-rrf"):
        # Fusión a nivel de SD del mejor canal de texto con el canal de propiedad: con diccionario
        # (`bom-rrf3`) o sin él (`bom-rrf`), porque medido el diccionario resta en la fusión.
        base = _ranking("rrf-bm25", consulta, ctx, k_rrf=k_rrf, peso_disperso=peso_disperso)
        via_bom = _ranking_bom("bom-rrf3" if canal == "rrf-bm25+bom" else "bom-rrf", consulta, ctx)
        canales = [r for r in (base, via_bom) if r]
        return [n for n, _ in fusion_rrf(canales, k=k_rrf)]
    lex = [c.service_domain for c in ctx["lexico"].recuperar(consulta, TOP_K)]
    bm = [c.service_domain for c in ctx["bm25"].recuperar(consulta, TOP_K)] if ctx.get("bm25") else []
    vec = (
        [c.service_domain for c in ctx["vectorial"].recuperar(consulta, TOP_K)]
        if ctx.get("vectorial")
        else []
    )
    if canal == "lexico":
        return lex
    if canal == "bm25":
        return bm
    if canal == "vectorial":
        return vec
    if canal == "qdrant":
        return (
            [c.service_domain for c in ctx["qdrant"].recuperar(consulta, TOP_K)]
            if ctx.get("qdrant")
            else []
        )
    disperso = bm if canal.startswith("rrf-bm25") else lex
    canales = [r for r in (disperso, vec) if r]
    pesos = [peso_disperso, 1.0][: len(canales)] if len(canales) == 2 else None
    base = [n for n, _ in fusion_rrf(canales, k=k_rrf, pesos=pesos)]
    if canal in ("rrf", "rrf-bm25"):
        return base
    if canal.startswith("rrf+graph"):
        expandidos = ctx["grafo"].expandir(base[:5], tope=5) if ctx.get("grafo") else []
        vistos = {normalizar(n) for n in base}
        base = base + [
            c.service_domain for c in expandidos if normalizar(c.service_domain) not in vistos
        ]
    if canal.endswith("rerank") and ctx.get("reranker"):
        # Qué texto ve el cross-encoder es una decisión aparte de qué canal lo alimenta: un índice
        # quiere cobertura de vocabulario, un cross-encoder quiere algo que se lea. `--texto-rerank`
        # la hace explícita y `--barrido-texto` la mide en vez de suponerla.
        textos = ctx.get("textos_rerank") or ctx["textos"]
        docs = [(n, textos.get(normalizar(n), n)) for n in base]
        base = [n for n, _ in ctx["reranker"].reordenar(consulta, docs, tope=len(docs))]
    return base


def evaluar(
    casos: list[dict],
    canales: tuple[str, ...],
    ctx: dict,
    *,
    k_rrf: int = 60,
    peso_disperso: float = 1.0,
) -> dict:
    resultados: dict[str, dict] = {}
    for canal in canales:
        filas = []
        for caso in casos:
            ranking = [
                normalizar(n)
                for n in _ranking(
                    canal, caso["consulta"], ctx, k_rrf=k_rrf, peso_disperso=peso_disperso
                )
            ]
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


def barrido(casos: list[dict], ctx: dict, canal: str) -> list[dict]:
    """Rejilla `k` x peso del canal disperso sobre UN canal fusionado.

    AVISO estadístico: con 7 consultas, un solo acierto mueve 0.14 de recall, así que el mejor
    punto de esta rejilla está sobreajustado por construcción. Sirve para ver la FORMA de la
    superficie (¿el peso del disperso ayuda o estorba?, ¿k importa?), no para fijar un default.
    """
    filas = []
    for k in KS_BARRIDO:
        for peso in PESOS_BARRIDO:
            r = evaluar(casos, (canal,), ctx, k_rrf=k, peso_disperso=peso)[canal]
            filas.append(
                {
                    "canal": canal,
                    "k": k,
                    "peso_disperso": peso,
                    "recall@5": r["recall@5"],
                    "recall@10": r["recall@10"],
                    "mrr": r["mrr"],
                    "negativos_delante": r["negativos_delante"],
                }
            )
    return filas


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--canales", default=",".join(CANALES_POR_DEFECTO))
    p.add_argument("--json", default="", help="Escribe el informe completo en este archivo.")
    p.add_argument("--corpus", default=str(CORPUS))
    p.add_argument(
        "--barrido",
        default="",
        help="Canal fusionado sobre el que barrer k x peso_disperso (p. ej. rrf-bm25).",
    )
    p.add_argument(
        "--tipo", default="", help="Evalúa solo los casos del corpus con este `tipo` (ver README)."
    )
    p.add_argument(
        "--consulta",
        default="frase",
        choices=("frase", "intencion"),
        help="Qué texto se usa como consulta: `frase` (el enunciado curado del caso) o `intencion` "
        "(los `business_objects` REALES que el nodo 1 extrajo en una corrida validada, "
        "`consulta_intencion`; los casos sin ese campo se omiten). El nodo 2a consume la intención, "
        "no la frase: medir con la frase sobreestima el canal.",
    )
    p.add_argument(
        "--texto-rerank",
        default="indice",
        choices=list(VARIANTES_TEXTO_SD),
        help="Qué texto del Service Domain ve el cross-encoder (ver EntradaCatalogo.texto_prosa).",
    )
    p.add_argument(
        "--barrido-texto",
        default="",
        help="Canal con rerank sobre el que probar TODAS las variantes de texto (p. ej. "
        "rrf-bm25+rerank). Imprime una fila por variante.",
    )
    args = p.parse_args(argv)

    corpus = yaml.safe_load(Path(args.corpus).read_text(encoding="utf-8"))
    casos = corpus["casos"]
    if args.tipo:
        casos = [c for c in casos if c.get("tipo") == args.tipo]
        if not casos:
            print(f"ningún caso con tipo='{args.tipo}'")
            return 1
    if args.consulta == "intencion":
        con = [c for c in casos if c.get("consulta_intencion")]
        omitidos = [c["id"] for c in casos if not c.get("consulta_intencion")]
        casos = [dict(c, consulta=". ".join(c["consulta_intencion"])) for c in con]
        if omitidos:
            print(f"(--consulta intencion: {len(omitidos)} caso(s) sin intención real, omitidos: {omitidos})")
        if not casos:
            print("ningún caso con `consulta_intencion`")
            return 1
    config = cargar_settings()
    catalogo = CatalogoJson(config.ruta_catalogo_bian)
    entradas = catalogo.cargar()

    canales = tuple(c.strip() for c in args.canales.split(",") if c.strip())
    # Los canales que hay que poder construir incluyen los que solo aparecen en un barrido: si no,
    # `ctx["reranker"]` sería None y el barrido de texto mediría "sin rerank" en todas las filas
    # (diez filas idénticas y ninguna señal de que el modelo no llegó a cargarse).
    canales_activos = canales + tuple(
        c for c in (args.barrido, args.barrido_texto) if c
    )
    reranker = RerankerCrossEncoder(config.mapear_historias.reranker_modelo)
    entidades = CatalogoEntidadesJson(config.ruta_entidades)
    quiere_bom = any(c in CANALES_BOM for c in canales_activos)
    quiere_bom_vec = any(
        c in ("bom-vec", "bom-rrf", "bom-rrf3", "rrf-bm25+bom", "rrf-bm25+bom-rrf") for c in canales_activos
    )
    ctx = {
        "bom": {
            "clases": entidades.clases(),
            "enums": entidades.nombres_enum(),
            "bm25": RecuperadorClasesBM25(entidades),
            "vectorial": _vectorial_clases(config, entidades) if quiere_bom_vec else None,
        }
        if quiere_bom
        else None,
        "lexico": RecuperadorLexico(catalogo),
        "bm25": RecuperadorBM25(catalogo),
        "vectorial": _vectorial(config, catalogo)
        if any("vectorial" in c or c.startswith("rrf") for c in canales_activos)
        else None,
        "grafo": GrafoBianJson(config.ruta_grafo_bian),
        "qdrant": _qdrant(config) if "qdrant" in canales_activos else None,
        "reranker": reranker if any(c.endswith("rerank") for c in canales_activos) else None,
        "textos": {normalizar(e.service_domain): e.texto_para_indexar() for e in entradas},
        "textos_rerank": {
            normalizar(e.service_domain): e.texto_prosa(args.texto_rerank) for e in entradas
        },
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

    tipos = sorted({c.get("tipo", "sin_tipo") for c in casos})
    if len(tipos) > 1:
        # Las capas del corpus NO se promedian entre sí: `hu_real` mide el problema de negocio y
        # las capas de nombre miden `validar-sd`. Un número global las mezclaría y taparía justo
        # lo que interesa (que mejorar una no rompa la otra).
        print("\npor capa del corpus:")
        for tipo in tipos:
            subconjunto = [c for c in casos if c.get("tipo", "sin_tipo") == tipo]
            parcial = evaluar(subconjunto, canales, ctx)
            print(f"  [{tipo}] n={len(subconjunto)}")
            for canal, r in parcial.items():
                print(
                    f"    {canal:20s} R@1 {r['recall@1']:.2f}  R@5 {r['recall@5']:.2f}  "
                    f"R@10 {r['recall@10']:.2f}  MRR {r['mrr']:.3f}"
                )

    print(
        "\nRecall alto NO implica que el pipeline acierte: mide recuperación, no decisión. "
        "Contrastar con ownership_conflict_rate y operation_grounding_rate de una corrida real."
    )

    if args.barrido_texto:
        canal = args.barrido_texto
        if ctx.get("reranker") is None:
            print(f"\nbarrido de texto imposible: '{canal}' no activa ningún reranker")
            return 1
        print(f"\nbarrido de texto sobre '{canal}' (qué lee el cross-encoder):")
        print(f"{'variante':22s} {'chars':>7s} {'R@1':>6s} {'R@5':>6s} {'R@10':>6s} {'MRR':>6s} {'neg':>5s}")
        for variante in VARIANTES_TEXTO_SD:
            ctx["textos_rerank"] = {
                normalizar(e.service_domain): e.texto_prosa(variante) for e in entradas
            }
            if hasattr(ctx.get("reranker"), "_cache"):
                ctx["reranker"]._cache.clear()  # el cache es por (consulta, candidatos), no por texto
            r = evaluar(casos, (canal,), ctx)[canal]
            medio = sum(len(t) for t in ctx["textos_rerank"].values()) // max(1, len(entradas))
            print(
                f"{variante:22s} {medio:7d} {r['recall@1']:6.2f} {r['recall@5']:6.2f} "
                f"{r['recall@10']:6.2f} {r['mrr']:6.3f} {r['negativos_delante']:5d}"
            )

    if args.barrido:
        print(f"\nbarrido sobre '{args.barrido}' (k x peso del canal disperso):")
        print(f"{'k':>4s} {'peso':>6s} {'R@5':>6s} {'R@10':>6s} {'MRR':>6s} {'neg':>5s}")
        for fila in barrido(casos, ctx, args.barrido):
            print(
                f"{fila['k']:4d} {fila['peso_disperso']:6.2f} {fila['recall@5']:6.2f} "
                f"{fila['recall@10']:6.2f} {fila['mrr']:6.3f} {fila['negativos_delante']:5d}"
            )
        print(
            f"Con {len(casos)} consultas un acierto mueve {1 / len(casos):.2f} de recall: "
            "la rejilla muestra la FORMA de la superficie, no el default."
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
