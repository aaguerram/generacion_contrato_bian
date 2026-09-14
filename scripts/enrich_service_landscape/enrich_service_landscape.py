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

Regla de valores — en los campos emparejados manda SD.json
-----------------------------------------------------------
El NOMBRE es el del landscape; el VALOR lo pone SD.json siempre que tenga algo que decir (es la
fuente del `BIANv14.xlsm`, con la documentación estructurada "** 1. Role ** ..."). Si SD.json no
trae valor para ese campo, se respeta el del landscape. Todo reemplazo sobre un valor que ya
existía queda listado en `valores_sobrescritos`.

Además se comprueba que ningún valor quede repetido en dos atributos del mismo Service Domain
(`valores_repetidos_entre_atributos`): si dos campos dicen lo mismo, uno no aporta nada.

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
    sobrescritos: list[dict] = []
    campos_nuevos = sorted(set(mapa.values()) - {k for v in landscape_sd.values() for k in v})

    for nombre, sd in landscape_sd.items():
        fila = sd_json.get(nombre)
        if not fila:
            continue
        for cabecera, campo in mapa.items():
            nuevo = _texto(fila.get(cabecera))
            if not nuevo:
                continue  # SD.json no aporta: se respeta lo que tenga el landscape
            actual = _texto(sd.get(campo))
            if actual == nuevo:
                continue
            sd[campo] = nuevo
            if not actual:
                completados[campo] = completados.get(campo, 0) + 1
            else:
                sobrescritos.append(
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
        "valores_sobrescritos": sobrescritos,
        "valores_repetidos_entre_atributos": _valores_repetidos(landscape_sd),
    }
    return doc["enrichment"]


# Campos de TEXTO descriptivo: si dos de ellos dicen exactamente lo mismo, uno no aporta nada.
# Los de clasificación (`asset_type`, `control_record`, `functional_pattern`,
# `generic_artifact_type`, `registration_status`) quedan fuera a propósito: son identificadores
# cortos y BIAN los hace coincidir legítimamente — el Control Record se nombra
# `<AssetType><ArtifactType>`, así que en "Legal Advisory" (asset type "Legal Advice", artifact
# type "Advice") el CR se llama "Legal Advice", igual que su asset type. Eso viene idéntico en las
# DOS fuentes oficiales; "corregirlo" sería inventar un dato que BIAN no publica.
_CAMPOS_DE_TEXTO = (
    "role_definition",
    "example_of_use",
    "executive_summary",
    "key_features",
    "documentation",
)


def _valores_repetidos(landscape_sd: dict[str, dict]) -> list[dict]:
    """Un texto descriptivo no debe aparecer en dos atributos del mismo Service Domain.

    Si `documentation` y `role_definition` acaban con el mismo texto, uno de los dos no aporta
    nada y el catálogo aparenta saber más de lo que sabe. Se reporta en vez de resolverse solo:
    cuál sobra es una decisión de contenido.
    """
    repetidos = []
    for nombre, sd in landscape_sd.items():
        vistos: dict[str, str] = {}
        for campo in _CAMPOS_DE_TEXTO:
            valor = _texto(sd.get(campo))
            if not valor:
                continue
            if valor in vistos:
                repetidos.append(
                    {
                        "service_domain": nombre,
                        "campos": [vistos[valor], campo],
                        "chars": len(valor),
                    }
                )
            else:
                vistos[valor] = campo
    return repetidos


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
    informe = enriquecer(doc, sd_json)
    texto = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"

    print(f"Service Domains        : {len(list(_service_domains(doc['business_areas'])))}")
    print(
        f"campos agregados       : {informe['campos_agregados'] or 'ninguno (todos ya existían)'}"
    )
    print(f"valores completados    : {informe['valores_completados'] or 'ninguno'}")
    if informe["valores_sobrescritos"]:
        print(f"valores sobrescritos   : {len(informe['valores_sobrescritos'])} (manda SD.json)")
        for d in informe["valores_sobrescritos"][:5]:
            print(
                f"   - {d['service_domain']}.{d['campo']}: "
                f"{d['chars_landscape']} -> {d['chars_sd_json']} chars"
            )
    repetidos = informe["valores_repetidos_entre_atributos"]
    print(f"valores repetidos entre atributos: {len(repetidos) or 'ninguno'}")
    for r in repetidos[:5]:
        print(
            f"   - {r['service_domain']}: {r['campos'][0]} == {r['campos'][1]} ({r['chars']} chars)"
        )

    if args.verificar:
        # `enrichment` se reescribe siempre (lleva la fecha): lo que importa es si quedó algo por
        # aplicar sobre los Service Domain o si hay valores repetidos entre atributos.
        pendientes = sum(informe["valores_completados"].values()) + len(
            informe["valores_sobrescritos"]
        )
        if pendientes:
            print(f"PENDIENTE: {pendientes} valores por aplicar; correr el script sin --verificar")
            return 1
        if repetidos:
            print("PENDIENTE: hay valores repetidos entre atributos (ver arriba)")
            return 1
        print("OK: el landscape está al día con SD.json y sin valores repetidos")
        return 0

    LANDSCAPE.write_text(texto, encoding="utf-8")
    print(f"escrito {LANDSCAPE.relative_to(RAIZ)} ({len(texto) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
