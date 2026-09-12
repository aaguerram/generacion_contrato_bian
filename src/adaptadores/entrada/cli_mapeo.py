"""CLI: mapear-historias  --directorio-hu <dir> --funcionalidad <f.json> --directorio <out>

Mapea cada Historia de Usuario a sus BIAN Service Domains (rol contractual + confianza +
operaciones) usando SOLO la evidencia local de docs/. LangGraph: subgrafo por HU con fan-out
por candidato + failover multi-proveedor/multi-modelo definido en config.yaml.

Cada ejecución escribe en `<--directorio>/<AAAA-MM-DD_HH-MM-SS>/` para no pisar corridas
anteriores (`--sin-timestamp` escribe directamente en `<--directorio>`).

Se invoca como subcomando:  python -m src mapear-historias ...
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import logging
import sys
from pathlib import Path

from src.adaptadores.salida.llm.factory import estrategias_disponibles
from src.configuracion.contenedor import crear_caso_uso_mapeo
from src.configuracion.observabilidad import configurar_langsmith
from src.configuracion.settings import cargar_settings

logger = logging.getLogger("generacion_contrato_ia_v2.cli.mapeo")


def _forzar_utf8() -> None:
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def _parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mapear-historias",
        description="Mapea Historias de Usuario a BIAN Service Domains (rol contractual + confianza + "
        "operaciones) usando evidencia BIAN cache-first dentro de docs/. LangGraph: subgrafo por HU con "
        "fan-out por candidato, failover multi-proveedor (config.yaml).",
    )
    p.add_argument("--directorio-hu", "--hu", required=True, type=Path,
                   help="Directorio con las Historias de Usuario (.txt / .md).")
    p.add_argument("--funcionalidad", "--func", required=True, type=Path,
                   help='JSON con { "funcionalidad_macro": "...", "detalle": "..." }.')
    p.add_argument("--directorio", "--dir", required=True, type=Path,
                   help="Directorio de salida. Cada ejecución crea dentro una subcarpeta "
                   "<AAAA-MM-DD_HH-MM-SS>/ con mapeo-historias-service-domains.json.")
    p.add_argument("--sin-timestamp", action="store_true",
                   help="Escribe directamente en --directorio (sin subcarpeta con fecha-hora).")
    p.add_argument("--config", default=None, type=Path, help="Ruta a config.yaml (por defecto: raíz del paquete).")
    p.add_argument("--proveedor", default=None,
                   help=f"Fuerza un único proveedor ({', '.join(estrategias_disponibles())}); "
                   "por defecto usa el failover de routing.llm_priority en config.yaml.")
    p.add_argument("--esfuerzo", default=None, choices=["low", "medium", "high"])
    p.add_argument("--umbral-directo", type=float, default=None, help="Pisa mapear_historias.umbral_directo.")
    p.add_argument("--umbral-tentativo", type=float, default=None, help="Pisa mapear_historias.umbral_tentativo.")
    p.add_argument("--concurrencia", type=int, default=None, help="Pisa mapear_historias.concurrencia.")
    p.add_argument("--sin-operaciones", action="store_true", help="Desactiva el paso 2 (operaciones oficiales).")
    p.add_argument("--actualizar-cache-bian", action="store_true",
                   help="Actualiza desde la fuente oficial incluso si el candidato ya existe en cache.")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def _directorio_run(base: Path, *, sin_timestamp: bool, ahora: dt.datetime | None = None) -> Path:
    """`<base>/<AAAA-MM-DD_HH-MM-SS>/` por ejecución (o `<base>` con --sin-timestamp)."""
    if sin_timestamp:
        return base
    marca = (ahora or dt.datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    return base / marca


def _resumen(resultado) -> None:
    _ROL = {"OWNED_CONTRACT": "OWNED", "CONSUMED_DEPENDENCY": "CONSUMED", "RELATED_NOT_OWNED": "RELATED"}
    print("\n" + "=" * 72)
    print(f"Funcionalidad macro : {resultado.funcionalidad_macro}")
    print(f"Historias           : {resultado.total_historias}")
    u = resultado.parametros
    print(f"Cadena LLM          : {u.get('cadena_llm')}")
    print(f"Umbrales            : directo >= {u.get('umbral_directo')}  |  "
          f"tentativo {u.get('umbral_tentativo')}..{u.get('umbral_directo')}")
    for h in resultado.historias:
        print("-" * 72)
        print(f"HU  {h.titulo}   ({h.archivo})")
        print(f"    directos={h.total_directos}  tentativos={h.total_tentativos}  descartados={h.total_descartados}")
        for etq, grupo in (("D", h.service_domains.candidatos_directos),
                           ("T", h.service_domains.candidatos_tentativos)):
            for a in grupo:
                area = f"  · {a.business_area}" if a.business_area else ""
                print(f"    [{etq} {a.confianza_pct:3d}%] {a.service_domain}  "
                      f"({_ROL.get(a.rol_contractual, a.rol_contractual)}){area}")
                for op in a.operaciones_bian:
                    print(f"            op: {op.method} {op.operation_id}  [{op.tipo} {op.grupo}]")
                for bq in a.bq_personalizados_propuestos:
                    print(f"            op personalizada (NO oficial, revisar): {bq.operation_id}  "
                          f"[grupo existente: {bq.grupo_existente}]  {bq.path_propuesto}  "
                          f"<- {bq.clase_bom}.{bq.atributo_bom}")
    print("=" * 72)


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

    reemplazos: dict = {}
    if args.umbral_directo is not None:
        reemplazos["umbral_directo"] = args.umbral_directo
    if args.umbral_tentativo is not None:
        reemplazos["umbral_tentativo"] = args.umbral_tentativo
    if args.concurrencia is not None:
        reemplazos["concurrencia"] = args.concurrencia
    if args.sin_operaciones:
        reemplazos["paso2_operaciones"] = False
    if reemplazos:
        config = dataclasses.replace(
            config, mapear_historias=dataclasses.replace(config.mapear_historias, **reemplazos)
        )

    ls = configurar_langsmith(config)
    print(f"LangSmith: {'activo — proyecto ' + config.observabilidad.langsmith_project if ls else 'inactivo'}")

    try:
        caso_uso = crear_caso_uso_mapeo(config, proveedor=args.proveedor,
                                        actualizar_cache_bian=args.actualizar_cache_bian)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 2

    mh = config.mapear_historias
    dir_run = _directorio_run(args.directorio, sin_timestamp=args.sin_timestamp)
    print(f">> proveedor = {args.proveedor or 'failover'}  |  esfuerzo = {config.llm.esfuerzo}  |  "
          f"concurrencia = {mh.concurrencia}  |  paso2 = {mh.paso2_operaciones}")
    print(f">> salida    = {dir_run}")

    try:
        resultado = caso_uso.ejecutar(
            str(args.directorio_hu), str(args.funcionalidad), str(dir_run)
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        logger.error("%s", exc)
        return 2

    _resumen(resultado)

    ruta = dir_run / "mapeo-historias-service-domains.json"
    if ruta.is_file():
        print(f"detalle: {ruta}")

    con_sd = sum(1 for h in resultado.historias if h.total_directos or h.total_tentativos)
    return 0 if con_sd else 1


if __name__ == "__main__":
    sys.exit(main())
