"""CLI:  validar-sd --service-domain "<nombre>" --directorio <ruta>

Nodo 1 del pipeline: valida si el Service Domain existe en SD.json (exacto -> RAG -> LLM).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.adaptadores.salida.llm.factory import estrategias_disponibles
from src.configuracion.contenedor import crear_caso_uso
from src.configuracion.observabilidad import configurar_langsmith
from src.configuracion.settings import cargar_settings

logger = logging.getLogger("generacion_contrato_ia_v2.cli")


def _forzar_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="validar-sd",
        description="Valida si un BIAN Service Domain existe en SD.json (LangGraph + RAG + LLM).",
    )
    p.add_argument(
        "--service-domain", "--sd", required=True, help="Nombre del Service Domain a validar."
    )
    p.add_argument(
        "--directorio",
        "--dir",
        required=True,
        type=Path,
        help="Directorio de trabajo donde se escribe validacion-service-domain.json.",
    )
    p.add_argument(
        "--proveedor",
        default=None,
        help=f"Fuerza un único proveedor LLM ({', '.join(estrategias_disponibles())}); "
        "por defecto usa el failover de routing.llm_priority en config.yaml.",
    )
    p.add_argument(
        "--config",
        default=None,
        type=Path,
        help="Ruta a config.yaml (por defecto: raíz del paquete).",
    )
    p.add_argument("--esfuerzo", default=None, choices=["low", "medium", "high"])
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _forzar_utf8()
    args = _parse(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )

    try:
        config = cargar_settings(ruta_config=args.config, esfuerzo=args.esfuerzo)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)
        return 2

    ls = configurar_langsmith(config)
    print(
        f"LangSmith: {'activo — proyecto ' + config.observabilidad.langsmith_project if ls else 'inactivo'}"
    )

    try:
        caso_uso = crear_caso_uso(config, proveedor=args.proveedor)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 2

    print(
        f">> proveedor = {args.proveedor or 'failover'}  |  esfuerzo = {config.llm.esfuerzo}  |  "
        f"RAG top-k = {config.validar_sd.rag_top_k}"
    )

    resultado = caso_uso.ejecutar(args.service_domain, str(args.directorio))

    print("\n" + "=" * 64)
    print(f"Service Domain consultado : {resultado.service_domain_consultado}")
    print(f"¿Existe en BIAN R14?      : {'SÍ' if resultado.existe else 'NO'}")
    if resultado.service_domain_canonico:
        print(f"Nombre canónico           : {resultado.service_domain_canonico}")
    print(f"Método                    : {resultado.metodo}   (confianza {resultado.confianza:.2f})")
    if resultado.candidatos and not resultado.existe:
        print("Candidatos más cercanos   :  (similitud de nombre)")
        for c in resultado.candidatos[:5]:
            print(f"   - {c.service_domain}  ({c.similitud_nombre:.2f})")
    print("=" * 64)

    ruta = Path(args.directorio) / "validacion-service-domain.json"
    if ruta.is_file():
        print(f"detalle: {ruta}")

    return 0 if resultado.existe else 1


if __name__ == "__main__":
    sys.exit(main())
