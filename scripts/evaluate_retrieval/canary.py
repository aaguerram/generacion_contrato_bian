"""Compara DOS configuraciones del pipeline sobre el mismo lote de HU (canary / shadow).

El flag `retrieval_hibrido_habilitado` -y ahora también `graph_rag_habilitado` y
`reranker_habilitado`- ya son el mecanismo de rollback; lo que faltaba era el proceso de
comparación: correr la configuración candidata en paralelo a la actual sobre las MISMAS historias
y diferenciar el resultado antes de cambiar un default.

Qué compara, por historia:
  - los Service Domain consolidados (altas y bajas respecto a la corrida base),
  - su decisión contractual (un SD que pasa de SELECTED a UNRESOLVED es una regresión aunque siga
    en la lista),
  - las operaciones ancladas,
  - y las métricas de la corrida (`ownership_conflict_rate`, `operation_grounding_rate`,
    `candidate_drop_rate`), que es donde se ve si el cambio ayudó de verdad o solo movió candidatos.

Consume cuota de LLM: son dos corridas completas. Con `--proveedor fake` no consume nada, pero
entonces solo valida el cableado, no la calidad.

Uso:
    .venv/bin/python scripts/evaluate_retrieval/canary.py \
        --hu ./HU --funcionalidad ./ejemplos/funcionalidad-actualizacion-datos-personales.json \
        --base config.yaml --candidata mi-config-con-graph.yaml --proveedor ollama
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _correr(config: str, hu: str, func: str, proveedor: str, destino: Path) -> dict:
    cmd = [
        str(RAIZ / ".venv/bin/python"),
        "-m",
        "src",
        "mapear-historias",
        "--directorio-hu",
        hu,
        "--funcionalidad",
        func,
        "--directorio",
        str(destino),
        "--sin-timestamp",
        "--config",
        config,
    ]
    if proveedor:
        cmd += ["--proveedor", proveedor]
    print(f"  $ {' '.join(cmd[2:])}")
    subprocess.run(cmd, cwd=RAIZ, check=True, capture_output=True, text=True)
    return json.loads(
        (destino / "mapeo-historias-service-domains.json").read_text(encoding="utf-8")
    )


def _por_historia(resultado: dict) -> dict[str, dict[str, str]]:
    """{archivo HU -> {service_domain -> 'decision/motivo'}} de los SD consolidados."""
    salida: dict[str, dict[str, str]] = {}
    for h in resultado.get("historias", []):
        sd = h.get("service_domains", {})
        fila = {}
        for grupo in ("candidatos_directos", "candidatos_tentativos", "candidatos_descartados"):
            for c in sd.get(grupo, []):
                fila[c["service_domain"]] = (
                    f"{c.get('decision_contractual')}/{c.get('motivo_decision')}"
                )
        salida[h.get("archivo") or h.get("titulo", "?")] = fila
    return salida


def diferencias(base: dict, candidata: dict) -> dict:
    a, b = _por_historia(base), _por_historia(candidata)
    informe: dict[str, dict] = {}
    for hu in sorted(set(a) | set(b)):
        fa, fb = a.get(hu, {}), b.get(hu, {})
        cambios = {
            sd: {"base": fa.get(sd, "(ausente)"), "candidata": fb.get(sd, "(ausente)")}
            for sd in sorted(set(fa) | set(fb))
            if fa.get(sd) != fb.get(sd)
        }
        if cambios:
            informe[hu] = cambios
    return informe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--hu", required=True)
    p.add_argument("--funcionalidad", required=True)
    p.add_argument("--base", default="config.yaml")
    p.add_argument("--candidata", required=True)
    p.add_argument("--proveedor", default="fake")
    args = p.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        print("corrida BASE:")
        base = _correr(args.base, args.hu, args.funcionalidad, args.proveedor, raiz / "base")
        print("corrida CANDIDATA:")
        cand = _correr(args.candidata, args.hu, args.funcionalidad, args.proveedor, raiz / "cand")

    print("\n=== métricas ===")
    mb, mc = base.get("metricas", {}), cand.get("metricas", {})
    for clave in sorted(set(mb) | set(mc)):
        vb, vc = mb.get(clave), mc.get(clave)
        marca = "" if vb == vc else "   <-- cambia"
        print(f"  {clave:34s} base={vb!s:>8}  candidata={vc!s:>8}{marca}")

    dif = diferencias(base, cand)
    print(f"\n=== decisiones que cambian: {sum(len(v) for v in dif.values())} ===")
    for hu, cambios in dif.items():
        print(f"  {hu}")
        for sd, v in cambios.items():
            print(f"     {sd:38s} {v['base']}  ->  {v['candidata']}")
    if not dif:
        print("  ninguna: la candidata no altera el resultado de negocio en este lote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
