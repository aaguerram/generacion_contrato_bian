"""REGLA DE ARQUITECTURA HEXAGONAL — ejecutable como test (análisis estático de imports)."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
_STDLIB = set(sys.stdlib_module_names) | {"__future__"}

# capa -> (prefijos "src.*" permitidos, terceros permitidos | None = cualquiera)
_REGLAS: dict[str, tuple[set[str], set[str] | None]] = {
    "dominio": ({"src.dominio"}, {"pydantic"}),
    "aplicacion": ({"src.dominio", "src.aplicacion"}, {"pydantic", "langgraph"}),
    "adaptadores": (
        {"src.dominio", "src.aplicacion", "src.adaptadores", "src.configuracion"},
        None,
    ),
    "configuracion": (
        {"src.dominio", "src.aplicacion", "src.adaptadores.salida", "src.configuracion"},
        None,
    ),
    "raiz": ({"src.adaptadores.entrada", "src.configuracion"}, set()),
}


def _modulo(archivo: Path) -> str:
    partes = list(archivo.relative_to(SRC).with_suffix("").parts)
    if partes and partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(["src", *partes]) if partes else "src"


def _capa(modulo: str) -> str:
    p = modulo.split(".")
    if len(p) < 2 or p[1] == "__main__":
        return "raiz"
    return p[1] if p[1] in _REGLAS else "raiz"


def _paquete(archivo: Path, modulo: str) -> str:
    if archivo.name == "__init__.py":
        return modulo
    return modulo.rsplit(".", 1)[0] if "." in modulo else modulo


def _resolver_rel(nodo: ast.ImportFrom, paquete: str) -> str:
    partes = paquete.split(".")
    if nodo.level > 1:
        partes = partes[: -(nodo.level - 1)]
    base = ".".join(partes)
    return f"{base}.{nodo.module}" if nodo.module else base


def _objetivos(arbol: ast.AST, paquete: str) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            out.add(_resolver_rel(n, paquete) if n.level else (n.module or ""))
    return {o for o in out if o}


def _permitido(objetivo: str, capa: str) -> bool:
    prefijos, terceros = _REGLAS[capa]
    if objetivo == "src" or objetivo.startswith("src."):
        return any(objetivo == p or objetivo.startswith(p + ".") for p in prefijos)
    raiz = objetivo.split(".")[0]
    return raiz in _STDLIB or terceros is None or raiz in terceros


class TestArquitecturaHexagonal(unittest.TestCase):
    def test_capas_existen(self):
        for r in ("dominio", "aplicacion/puertos", "aplicacion/servicios",
                  "adaptadores/entrada", "adaptadores/salida/llm", "configuracion"):
            self.assertTrue((SRC / r).is_dir(), f"falta src/{r}")

    def test_ningun_import_cruza_su_capa(self):
        fallos = []
        for f in sorted(SRC.rglob("*.py")):
            modulo = _modulo(f)
            capa = _capa(modulo)
            arbol = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for obj in sorted(_objetivos(arbol, _paquete(f, modulo))):
                if not _permitido(obj, capa):
                    fallos.append(f"{f.relative_to(SRC.parent).as_posix()}  [{capa}]  ->  '{obj}'")
        self.assertEqual(fallos, [], "\n\nViolaciones (ver ARQUITECTURA.md):\n  - " + "\n  - ".join(fallos))

    def test_dominio_sin_frameworks(self):
        prohibidos = {"langchain", "langchain_core", "langgraph", "langchain_google_genai", "langsmith"}
        for f in sorted((SRC / "dominio").rglob("*.py")):
            arbol = ast.parse(f.read_text(encoding="utf-8"))
            raices = {o.split(".")[0] for o in _objetivos(arbol, _modulo(f))}
            self.assertEqual(raices & prohibidos, set(), f"{f.name} importa {raices & prohibidos}")


if __name__ == "__main__":
    unittest.main()
