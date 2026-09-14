"""Completa IN-PLACE `docs/BIAN_Service_Landscape_V14.0_Matrix_View.json`, la fuente ÚNICA de
información de Service Domains del runtime.

El Matrix View manda: es el archivo que lee `CatalogoJson`. Este script solo le rellena los
huecos con `docs/SD.json` (columnas L..V del `BIANv14.xlsm`), sin crear un archivo derivado ni un
segundo parser.

Regla de nombres — un dato, un nombre, el del landscape
-------------------------------------------------------
Antes de completar nada, el script EMPAREJA los campos de SD.json con los del landscape
**comparando valores**, no nombres: si el mismo dato ya existe en el landscape bajo otro nombre,
prevalece el nombre del landscape y NO se añade un campo duplicado. Con las fuentes actuales los
once campos de SD.json ya tienen equivalente (coincidencia de valor entre 94% y 100%):

    Service Domain        -> name                    Functional Pattern    -> functional_pattern
    Service Role          -> role_definition         Asset Type            -> asset_type
    Examples of Use       -> example_of_use          Generic Artifact Type -> generic_artifact_type
    Executive Summary     -> executive_summary       Control Record <...>  -> control_record
    Features              -> key_features            Registration Status   -> registration_status
    Documentation         -> documentation

Si en el futuro un campo de SD.json no empareja con ninguno, se añade con su nombre en
snake_case y el script lo reporta: nunca se duplica un dato bajo dos nombres.

Regla de valores — solo se completa lo que falta
------------------------------------------------
- Landscape vacío y SD.json con valor  -> se completa.
- Landscape truncado (SD.json lo contiene literalmente) -> se completa con el texto entero.
- Ambos con valor y textos distintos   -> NO se toca: manda el landscape, y queda anotado como
  incidencia para que la discrepancia sea visible en vez de resolverse en silencio.

Idempotente: correrlo dos veces no cambia nada. Deja constancia en el bloque `enrichment` de la
raíz del documento (fuentes con sha256, qué se completó y qué discrepa).

Uso:
    .venv/bin/python scripts/enrich_service_landscape/enrich_service_landscape.py
    .venv/bin/python scripts/enrich_service_landscape/enrich_service_landscape.py --verificar
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
DOCS = RAIZ / "docs"
LANDSCAPE = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"
SD_JSON = DOCS / "SD.json"

# Umbral de coincidencia de valor para considerar que dos campos son EL MISMO dato.
_UMBRAL_EQUIVALENCIA = 0.5


def _texto(valor: Any) -> str:
    """Los vacíos que traen las fuentes ("", "None", null) cuentan como ausencia."""
    if valor is None:
        return ""
    s = " ".join(str(valor).split()).strip()
    return "" if s == "None" else s


def _snake(cabecera: str) -> str:
    limpio = "".join(c if c.isalnum() else " " for c in cabecera)
    return "_".join(limpio.split()).lower()


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _service_domains(nodos: list[dict]):
    """Los Service Domain del árbol Business Area -> Business Domain (anidable)."""
    for nodo in nodos:
        for hijo in nodo.get("business_domains", []):
            yield from _service_domains([hijo])
        yield from nodo.get("service_domains", [])


def emparejar_campos(landscape_sd: dict[str, dict], sd_json: dict[str, dict]) -> dict[str, str]:
    """{cabecera de SD.json -> campo del landscape que YA tiene ese dato}.

    Empareja por valor: dos campos son el mismo dato si coinciden en al menos la mitad de los
    Service Domain donde SD.json tiene algo que decir. Así el nombre del landscape prevalece sin
    depender de que las cabeceras se parezcan.
    """
    comunes = set(landscape_sd) & set(sd_json)
    campos_land = sorted({k for v in landscape_sd.values() for k in v})
    mapa: dict[str, str] = {}
    for cabecera in sorted({k for v in sd_json.values() for k in v}):
        con_valor = [n for n in comunes if _texto(sd_json[n].get(cabecera))]
        if not con_valor:
            continue
        mejor, mejor_ratio = None, 0.0
        for campo in campos_land:
            iguales = sum(
                1
                for n in con_valor
                if _texto(sd_json[n][cabecera]) == _texto(landscape_sd[n].get(campo))
            )
            ratio = iguales / len(con_valor)
            if ratio > mejor_ratio:
                mejor, mejor_ratio = campo, ratio
        mapa[cabecera] = (
            mejor if mejor and mejor_ratio >= _UMBRAL_EQUIVALENCIA else _snake(cabecera)
        )
    return mapa


def enriquecer(doc: dict, sd_json: dict[str, dict]) -> dict:
    """Completa el documento en memoria y devuelve el informe de lo que hizo."""
    landscape_sd = {sd["name"]: sd for sd in _service_domains(doc.get("business_areas", []))}
    mapa = emparejar_campos(landscape_sd, sd_json)

    completados: dict[str, int] = {}
    discrepancias: list[dict] = []
    campos_nuevos = sorted(set(mapa.values()) - {k for v in landscape_sd.values() for k in v})

    for nombre, sd in landscape_sd.items():
        fila = sd_json.get(nombre)
        if not fila:
            continue
        for cabecera, campo in mapa.items():
            nuevo = _texto(fila.get(cabecera))
            if not nuevo:
                continue
            actual = _texto(sd.get(campo))
            if not actual:
                sd[campo] = nuevo  # hueco: se completa
                completados[campo] = completados.get(campo, 0) + 1
            elif actual != nuevo:
                if nuevo.startswith(actual) or actual in nuevo:
                    sd[campo] = nuevo  # el landscape estaba truncado: se completa entero
                    completados[campo] = completados.get(campo, 0) + 1
                else:
                    # Textos distintos: manda el landscape. Se anota para que se vea.
                    discrepancias.append(
                        {
                            "service_domain": nombre,
                            "campo": campo,
                            "chars_landscape": len(actual),
                            "chars_sd_json": len(nuevo),
                        }
                    )

    doc["enrichment"] = {
        "enriquecido_por": "scripts/enrich_service_landscape/enrich_service_landscape.py",
        "fecha": dt.date.today().isoformat(),
        "fuentes": [{"file": f"docs/{SD_JSON.name}", "sha256": _sha256(SD_JSON)}],
        "mapeo_de_campos": mapa,
        "campos_agregados": campos_nuevos,
        "valores_completados": dict(sorted(completados.items())),
        "discrepancias_no_aplicadas": discrepancias,
    }
    return doc["enrichment"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--verificar",
        action="store_true",
        help="No escribe: falla si el landscape aún tiene huecos que SD.json puede completar.",
    )
    args = p.parse_args(argv)

    doc = json.loads(LANDSCAPE.read_text(encoding="utf-8"))
    sd_json = {
        str(f.get("Service Domain", "")).strip(): f
        for f in json.loads(SD_JSON.read_text(encoding="utf-8"))
        if str(f.get("Service Domain", "")).strip()
    }
    antes = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    informe = enriquecer(doc, sd_json)
    texto = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"

    print(f"Service Domains        : {len(list(_service_domains(doc['business_areas'])))}")
    print(
        f"campos agregados       : {informe['campos_agregados'] or 'ninguno (todos ya existían)'}"
    )
    print(f"valores completados    : {informe['valores_completados'] or 'ninguno'}")
    if informe["discrepancias_no_aplicadas"]:
        print(f"discrepancias (manda el landscape): {len(informe['discrepancias_no_aplicadas'])}")
        for d in informe["discrepancias_no_aplicadas"][:5]:
            print(
                f"   - {d['service_domain']}.{d['campo']}: {d['chars_landscape']} vs {d['chars_sd_json']} chars"
            )

    if args.verificar:
        cambio = json.dumps(doc, ensure_ascii=False, sort_keys=True) != antes
        # `enrichment` se reescribe siempre (lleva la fecha): lo que importa es si cambió algún SD.
        pendientes = sum(informe["valores_completados"].values())
        if pendientes:
            print(
                f"PENDIENTE: {pendientes} valores por completar; correr el script sin --verificar"
            )
            return 1
        print("OK: el landscape no tiene huecos que SD.json pueda completar")
        return 0 if not cambio or not pendientes else 1

    LANDSCAPE.write_text(texto, encoding="utf-8")
    print(f"escrito {LANDSCAPE.relative_to(RAIZ)} ({len(texto) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
