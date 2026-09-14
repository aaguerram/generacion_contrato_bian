"""La información de Service Domains sale de UN solo archivo: el BIAN Service Landscape.

`docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` es la fuente única del runtime y sustituye al
par `SD.json` + `bian-business-areas.json` que `CatalogoJson` cruzaba en cada carga. `SD.json`
sigue en `docs/` solo como insumo para completarle huecos fuera de línea
(`scripts/enrich_service_landscape/`).

Este test fija lo que hace segura esa consolidación:

1. Cobertura: los 341 Service Domains, con la clasificación funcional (`functional_pattern` llega
   al prompt de evaluación y al recuperador léxico; `asset_type`, al paquete de evidencia) y con
   la jerarquía Business Area / Business Domain.
2. Un dato, un nombre: ningún campo del landscape duplica a otro con distinto nombre, y el
   landscape no tiene huecos que SD.json pudiera llenar (si los tuviera, falta correr el script).
3. Un solo parser: el formato de SD.json (lista plana) no se acepta en silencio.

Sin red y sin LLM.
"""

from __future__ import annotations

import json
import unittest

from src.adaptadores.salida.catalogo_json import CatalogoJson
from unit_test.support import DOCS

CATALOGO = DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json"
_TOTAL_SD = 341


def _vacio(valor) -> bool:
    return valor is None or str(valor).strip() in ("", "None")


def _service_domains(nodos):
    for nodo in nodos:
        for hijo in nodo.get("business_domains", []):
            yield from _service_domains([hijo])
        yield from nodo.get("service_domains", [])


class TestCatalogoBianUnico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entradas = CatalogoJson(CATALOGO).cargar()
        cls.doc = json.loads(CATALOGO.read_text(encoding="utf-8"))
        cls.crudos = {sd["name"]: sd for sd in _service_domains(cls.doc["business_areas"])}

    def test_estan_los_341_service_domains(self):
        self.assertEqual(len(self.entradas), _TOTAL_SD)

    def test_trae_la_clasificacion_funcional(self):
        for campo in ("functional_pattern", "asset_type", "control_record"):
            faltan = [e.service_domain for e in self.entradas if not getattr(e, campo)]
            self.assertEqual(faltan, [], f"{len(faltan)} SD sin '{campo}'")

    def test_trae_la_jerarquia(self):
        faltan = [e.service_domain for e in self.entradas if not e.business_area]
        self.assertEqual(faltan, [], f"{len(faltan)} SD sin Business Area")

    def test_trae_los_textos(self):
        sin_rol = [e.service_domain for e in self.entradas if not e.service_role]
        # Dos SD del catálogo BIAN R14 no publican Service Role en ninguna de las fuentes.
        self.assertLessEqual(len(sin_rol), 2, f"SD sin Service Role: {sin_rol}")

    def test_ningun_campo_duplica_a_otro_con_distinto_nombre(self):
        """Un dato, un nombre: si dos campos traen lo mismo, sobra uno."""
        campos = sorted({k for sd in self.crudos.values() for k in sd})
        for i, a in enumerate(campos):
            for b in campos[i + 1 :]:
                pares = [
                    (sd.get(a), sd.get(b))
                    for sd in self.crudos.values()
                    if not _vacio(sd.get(a)) and not _vacio(sd.get(b))
                ]
                if len(pares) < _TOTAL_SD // 2:
                    continue
                iguales = sum(1 for x, y in pares if str(x).strip() == str(y).strip())
                self.assertLess(
                    iguales / len(pares),
                    0.5,
                    f"'{a}' y '{b}' llevan el mismo dato en {iguales}/{len(pares)} SD",
                )

    def test_sin_huecos_que_sd_json_pueda_completar(self):
        """Si SD.json tiene algo donde el landscape no, falta correr el enriquecedor."""
        sd_json = {
            str(f.get("Service Domain", "")).strip(): f
            for f in json.loads((DOCS / "SD.json").read_text(encoding="utf-8"))
        }
        mapeo = self.doc["enrichment"]["mapeo_de_campos"]
        huecos = [
            f"{nombre}.{campo}"
            for nombre, sd in self.crudos.items()
            for cabecera, campo in mapeo.items()
            if _vacio(sd.get(campo)) and not _vacio(sd_json.get(nombre, {}).get(cabecera))
        ]
        self.assertEqual(
            huecos,
            [],
            "correr scripts/enrich_service_landscape/enrich_service_landscape.py",
        )

    def test_el_formato_de_sd_json_no_se_acepta_en_silencio(self):
        with self.assertRaises(ValueError) as ctx:
            CatalogoJson(DOCS / "SD.json").cargar()
        self.assertIn("Matrix View", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
