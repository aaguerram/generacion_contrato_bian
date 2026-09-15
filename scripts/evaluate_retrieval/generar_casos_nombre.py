"""Genera, de forma determinista y reproducible, las capas del corpus dorado cuya etiqueta NO
requiere juicio de negocio: consultas que son un NOMBRE de Service Domain.

Por qué existen estas capas y por qué van separadas de las HU reales:

- La capa que de verdad justifica un default de recuperación es `hu_real` (una Historia de Usuario
  con su Service Domain propietario confirmado). Esa **no se puede fabricar**: hoy hay 6 HU
  etiquetadas y punto. Rellenar el corpus con consultas de negocio inventadas no daría poder
  estadístico, daría ruido con aspecto de dato.
- Lo que sí se puede etiquetar sin juicio es el caso de uso `validar-sd`, donde la consulta ES un
  nombre: el positivo es el propio Service Domain, por definición. Sirve como regresión del canal
  por nombre — exactamente el que NO hay que romper al cambiar el canal disperso de
  `mapear-historias`.

Dos capas:
  `nombre_canonico`  — el nombre exacto del SD (muestreo repartido por todo el catálogo).
  `nombre_deformado` — el mismo nombre con una deformación sintética y declarada (abreviatura de
                       la última palabra, o una letra menos), como los nombres que llegan de un
                       inventario a medio escribir ("Isued Device Admin").

Los `hard_negatives` de cada caso son los nombres MÁS parecidos del propio catálogo (rapidfuzz):
no son plausibles "a ojo", son los que de verdad compiten en el ranking.

Uso:
    .venv/bin/python scripts/evaluate_retrieval/generar_casos_nombre.py            # imprime YAML
    .venv/bin/python scripts/evaluate_retrieval/generar_casos_nombre.py --escribir # actualiza el corpus
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402
from rapidfuzz import fuzz, process, utils  # noqa: E402

from src.adaptadores.salida.catalogo_json import CatalogoJson  # noqa: E402
from src.configuracion.settings import cargar_settings  # noqa: E402

CORPUS = Path(__file__).parent / "corpus_dorado.yaml"
N_CANONICOS = 60
N_DEFORMADOS = 30
MARCA = "generado por scripts/evaluate_retrieval/generar_casos_nombre.py"


def _slug(nombre: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in nombre.lower()).strip("-")


def _deformar(nombre: str) -> tuple[str, str]:
    """Deformación determinista y declarada: abrevia la última palabra o quita una letra."""
    palabras = nombre.split()
    if len(palabras) > 1 and len(palabras[-1]) > 5:
        return " ".join(palabras[:-1] + [palabras[-1][:5]]), "última palabra abreviada"
    plano = nombre.replace(" ", "")
    corte = next((i for i, c in enumerate(nombre) if i > 2 and c.isalpha()), 3)
    return nombre[:corte] + nombre[corte + 1 :], f"falta la letra '{nombre[corte]}'" if plano else ""


def _vecinos(nombre: str, nombres: list[str], n: int = 3) -> list[str]:
    hits = process.extract(
        nombre, nombres, scorer=fuzz.WRatio, processor=utils.default_process, limit=n + 1
    )
    return [h[0] for h in hits if h[0] != nombre][:n]


def generar(nombres: list[str]) -> list[dict]:
    """Muestreo repartido por TODO el catálogo (paso fijo), no los N primeros: si solo se tomara
    el principio, se mediría un Business Area y no el catálogo."""
    casos = []
    paso = max(1, len(nombres) // N_CANONICOS)
    for nombre in nombres[::paso][:N_CANONICOS]:
        casos.append(
            {
                "id": f"nombre-{_slug(nombre)}",
                "tipo": "nombre_canonico",
                "hu": f"(validar-sd) {nombre}",
                "consulta": nombre,
                "positivo": nombre,
                "hard_negatives": _vecinos(nombre, nombres),
                "procedencia": MARCA,
            }
        )
    paso_def = max(1, len(nombres) // N_DEFORMADOS)
    for nombre in nombres[1::paso_def][:N_DEFORMADOS]:
        consulta, como = _deformar(nombre)
        if consulta == nombre:
            continue
        casos.append(
            {
                "id": f"deformado-{_slug(nombre)}",
                "tipo": "nombre_deformado",
                "hu": f"(validar-sd) {consulta}",
                "consulta": consulta,
                "positivo": nombre,
                "hard_negatives": _vecinos(nombre, nombres),
                "procedencia": f"{MARCA} ({como})",
            }
        )
    return casos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--escribir", action="store_true", help="Actualiza corpus_dorado.yaml.")
    args = p.parse_args(argv)

    catalogo = CatalogoJson(cargar_settings().ruta_catalogo_bian).cargar()
    nombres = sorted(e.service_domain for e in catalogo)
    casos = generar(nombres)

    if not args.escribir:
        print(yaml.safe_dump(casos, allow_unicode=True, sort_keys=False))
        return 0

    corpus = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
    # Idempotente: se reemplazan SOLO las capas generadas; las HU reales nunca se tocan.
    manuales = [c for c in corpus["casos"] if MARCA not in str(c.get("procedencia", ""))]
    corpus["casos"] = manuales + casos
    CORPUS.write_text(
        yaml.safe_dump(corpus, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    print(f"corpus: {len(manuales)} casos manuales + {len(casos)} generados = {len(corpus['casos'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
