"""La información de Service Domains sale de UN solo archivo: el BIAN Service Landscape.

`docs/BIAN_Service_Landscape_V14.0_Matrix_View.json` es la fuente única del runtime y sustituye al
par `SD.json` + `bian-business-areas.json` que `CatalogoJson` cruzaba en cada carga. `SD.json`
sigue en `docs/` solo como insumo para completarle huecos fuera de línea
(`scripts/enrich_service_landscape/`).

Este test fija lo que hace segura esa consolidación:

1. Cobertura: los 341 Service Domains, con la clasificación funcional (`functional_pattern` llega
   al prompt de evaluación y al recuperador léxico; `asset_type`, al paquete de evidencia) y con
   la jerarquía Business Area / Business Domain.
2. Un dato, un nombre y un valor: ningún texto descriptivo se repite en dos atributos del mismo
   Service Domain, y el landscape está al día con SD.json — que manda en el VALOR de los campos
   emparejados (si no lo estuviera, falta correr el enriquecedor).
3. Un solo parser: el formato de SD.json (lista plana) no se acepta en silencio.

Sin red y sin LLM.
"""

from __future__ import annotations

import json
import re
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

    def test_ningun_texto_se_repite_en_dos_atributos_del_mismo_sd(self):
        """Si `documentation` y `role_definition` dicen lo mismo, uno de los dos no aporta nada.

        Los campos de clasificación quedan fuera: BIAN los hace coincidir legítimamente (el
        Control Record se nombra `<AssetType><ArtifactType>`, así que en "Legal Advisory" el CR se
        llama igual que su asset type, y así viene en las DOS fuentes oficiales).
        """
        campos = (
            "role_definition",
            "example_of_use",
            "executive_summary",
            "key_features",
            "documentation",
        )
        repetidos = []
        for nombre, sd in self.crudos.items():
            vistos = {}
            for campo in campos:
                valor = " ".join(str(sd.get(campo) or "").split())
                if not valor or valor == "None":
                    continue
                if valor in vistos:
                    repetidos.append(f"{nombre}: {vistos[valor]} == {campo}")
                vistos.setdefault(valor, campo)
        self.assertEqual(repetidos, [], "textos duplicados entre atributos del mismo SD")

    def test_la_documentacion_describe_al_service_domain_y_no_a_otra_cosa(self):
        """`documentation` abre con `** 1. Role **`, y ese rol es el del propio Service Domain.

        Criterio BIAN: `documentation` es la ficha estructurada del Service Domain
        (`** 1. Role ** / ** 2. Examples of use ** / ** 3. Executive Summary ** / ...`), así que su
        sección 1 tiene que decir exactamente lo mismo que `role_definition` de ese SD. Es lo que
        resuelve las dos discrepancias que el enriquecedor sobrescribió: en `Partner Management` y
        `Brand Management` el landscape traía en `documentation` la definición de una *capability*
        —otro artefacto BIAN, con otro rol— y SD.json la ficha del Service Domain. Con esta
        comprobación la discrepancia deja de ser un juicio manual: hoy coinciden 338/338 de los SD
        que traen los dos campos, y cualquier reaparición del texto equivocado falla aquí.

        Los 3 SD que no traen uno de los dos campos (`Card Transaction Tracking` sin
        `documentation`; `Operational Risk Models` y `Sales Planning` sin `role_definition`) no son
        comparables: ninguna de las dos fuentes oficiales publica el que falta.
        """
        seccion_rol = re.compile(r"\*\*\s*1\.\s*Role\s*\*\*(.*?)(?=\*\*\s*\d|\Z)", re.S | re.I)

        def t(valor) -> str:
            return "" if _vacio(valor) else " ".join(str(valor).split()).rstrip(". ").lower()

        sin_seccion, desalineados, comparables = [], [], 0
        for nombre, sd in self.crudos.items():
            doc, rol = sd.get("documentation"), sd.get("role_definition")
            if _vacio(doc) or _vacio(rol):
                continue
            encontrada = seccion_rol.search(str(doc))
            if not encontrada:
                sin_seccion.append(nombre)
                continue
            comparables += 1
            if t(encontrada.group(1)) != t(rol):
                desalineados.append(nombre)

        self.assertEqual(sin_seccion, [], "`documentation` sin la sección `** 1. Role **`")
        self.assertEqual(comparables, _TOTAL_SD - 3)
        self.assertEqual(
            desalineados,
            [],
            "la `documentation` de estos SD describe otro artefacto BIAN: correr "
            "scripts/enrich_service_landscape/enrich_service_landscape.py",
        )

    def test_el_valor_de_sd_json_manda_en_los_campos_emparejados(self):
        """SD.json es autoritativo en el valor; el landscape solo aporta el nombre del campo."""
        sd_json = {
            str(f.get("Service Domain", "")).strip(): f
            for f in json.loads((DOCS / "SD.json").read_text(encoding="utf-8"))
        }
        mapeo = self.doc["enrichment"]["mapeo_de_campos"]

        def t(v):
            return "" if _vacio(v) else " ".join(str(v).split())

        desalineados = [
            f"{nombre}.{campo}"
            for nombre, sd in self.crudos.items()
            for cabecera, campo in mapeo.items()
            if t(sd_json.get(nombre, {}).get(cabecera))
            and t(sd.get(campo)) != t(sd_json[nombre][cabecera])
        ]
        self.assertEqual(
            desalineados,
            [],
            "correr scripts/enrich_service_landscape/enrich_service_landscape.py",
        )

    def test_el_formato_de_sd_json_no_se_acepta_en_silencio(self):
        with self.assertRaises(ValueError) as ctx:
            CatalogoJson(DOCS / "SD.json").cargar()
        self.assertIn("Matrix View", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
