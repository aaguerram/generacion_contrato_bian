"""Propiedad de clases del BOM BIAN (`src/dominio/entidades_bian.py`). Determinista, sin red.

Los datos de prueba reproducen la forma REAL de `docs/entity.json` para el caso que motivó el
canal: `Party` definida en Party Reference Data Directory e importada en Location Data Management,
y `Electronic Address` / `Phone Address` al revés.
"""

from __future__ import annotations

import unittest

from src.dominio.entidades_bian import (
    AtributoClase,
    ClaseBian,
    OcurrenciaClase,
    candidatos_por_propiedad,
    clases_requeridas,
    tokenizar_consulta,
    valores_por_enum,
)

PRDD = "Party Reference Data Directory"
LDM = "Location Data Management"


def _catalogo() -> tuple[dict[str, ClaseBian], frozenset[str]]:
    clases = {
        "Party": ClaseBian(
            "Party",
            (
                OcurrenciaClase(
                    service_domain=PRDD,
                    bq="Reference",
                    asset_type="Party Reference Data",
                    atributos=(
                        AtributoClase("Party Name", "Name"),
                        AtributoClase("Party Identification", "Identifier"),
                        AtributoClase("Party Legal Structure Type", "PartyLegalStructureTypeValues"),
                    ),
                ),
                # La misma clase en OTRO Service Domain: importada, vacía y con puntero al dueño.
                OcurrenciaClase(
                    service_domain=LDM,
                    extensible="no",
                    bom_de="Party Reference Data Directory BOM Diagram",
                ),
            ),
        ),
        "Contact Point": ClaseBian(
            "Contact Point",
            (
                OcurrenciaClase(
                    service_domain=PRDD,
                    bq="Reference",
                    atributos=(AtributoClase("Contact Point Type", "ContactPointTypeValues"),),
                ),
            ),
        ),
        "Phone Address": ClaseBian(
            "Phone Address",
            (
                OcurrenciaClase(
                    service_domain=LDM,
                    atributos=(
                        AtributoClase("Phone Address Type", "PhoneAddressTypeValues"),
                        AtributoClase("Phone Number", "PhoneNumber"),
                    ),
                ),
            ),
        ),
        "Location": ClaseBian(
            "Location",
            (
                OcurrenciaClase(service_domain=LDM, asset_type="Location",
                                atributos=(AtributoClase("Location Identification", "Identifier"),)),
                OcurrenciaClase(service_domain=PRDD, extensible="yes"),
            ),
        ),
        "ContactPointTypeValues": ClaseBian(
            "ContactPointTypeValues",
            (
                OcurrenciaClase(
                    service_domain=PRDD,
                    kind="enum",
                    valores_enum=("Electronic Address", "Postal Address", "Phone Number"),
                ),
            ),
        ),
        "PhoneAddressTypeValues": ClaseBian(
            "PhoneAddressTypeValues",
            (
                OcurrenciaClase(
                    service_domain=LDM,
                    kind="enum",
                    valores_enum=("PhoneNumber", "FaxNumber", "MobileNumber"),
                ),
            ),
        ),
        "PartyLegalStructureTypeValues": ClaseBian(
            "PartyLegalStructureTypeValues",
            (OcurrenciaClase(service_domain=PRDD, kind="enum", valores_enum=("Individual",)),),
        ),
    }
    enums = frozenset(
        n for n, c in clases.items() if any(o.kind == "enum" for o in c.ocurrencias)
    )
    return clases, enums


class TestPropiedadDeClase(unittest.TestCase):
    def test_el_dueno_es_el_que_no_marca_extensible(self) -> None:
        clases, _ = _catalogo()
        self.assertEqual([o.service_domain for o in clases["Party"].duenos()], [PRDD])
        self.assertEqual(clases["Party"].importada_en(), [LDM])

    def test_la_regla_es_simetrica(self) -> None:
        """`Location` es de Location Data Management: en PRDD lleva `Extensible: yes`."""
        clases, _ = _catalogo()
        self.assertEqual([o.service_domain for o in clases["Location"].duenos()], [LDM])
        self.assertEqual(clases["Location"].importada_en(), [PRDD])

    def test_una_ocurrencia_de_control_record_nunca_es_dueno(self) -> None:
        """`Extensible` no existe en los diagramas de CR: aceptarlos colaría cualquier clase."""
        o = OcurrenciaClase(service_domain=PRDD, diagrama="control_record")
        self.assertFalse(o.es_dueno)


class TestConsulta(unittest.TestCase):
    def test_un_termino_del_negocio_abre_varias_formas_del_bom(self) -> None:
        q = tokenizar_consulta(["correo electrónico del cliente", "número celular"])
        self.assertIn("email", q)  # el corpus dice `eMail Address`, no `mail`
        self.assertIn("cell", q)
        self.assertIn("party", q)  # un cliente se modela con la clase Party

    def test_valores_por_enum(self) -> None:
        clases, _ = _catalogo()
        self.assertIn("MobileNumber", valores_por_enum(clases)["PhoneAddressTypeValues"])


class TestCandidatos(unittest.TestCase):
    def test_gana_el_dueno_de_la_clase_del_cliente(self) -> None:
        clases, enums = _catalogo()
        consulta = tokenizar_consulta(["datos del cliente", "correo electrónico", "teléfono"])
        req = clases_requeridas(consulta, clases, nombres_enum=enums)
        candidatos = candidatos_por_propiedad(req, clases, nombres_enum=enums)
        self.assertEqual(candidatos[0].service_domain, PRDD)
        self.assertIn("Reference", candidatos[0].bqs())
        # Location Data Management sigue siendo candidato -posee las clases de dirección-, pero
        # nunca por la clase del cliente.
        segundos = [c.service_domain for c in candidatos[1:]]
        self.assertIn(LDM, segundos)
        clases_ldm = {
            e.clase for c in candidatos if c.service_domain == LDM for e in c.evidencias
        }
        self.assertNotIn("Party", clases_ldm)

    def test_un_enum_no_es_candidato_por_si_mismo(self) -> None:
        """`ContactPointTypeValues` no es un objeto de negocio: cuenta como evidencia de su clase."""
        clases, enums = _catalogo()
        req = clases_requeridas(tokenizar_consulta(["contacto"]), clases, nombres_enum=enums)
        self.assertNotIn("ContactPointTypeValues", [r.clase for r in req])
        self.assertIn("Contact Point", [r.clase for r in req])

    def test_nota_distingue_tipificar_de_guardar_el_valor(self) -> None:
        """La señal que usa el paso 3: el enum TIPIFICA; los atributos extra GUARDAN el valor."""
        clases, enums = _catalogo()
        consulta = tokenizar_consulta(["correo electrónico", "teléfono", "contacto"])
        req = clases_requeridas(consulta, clases, nombres_enum=enums)
        candidatos = candidatos_por_propiedad(req, clases, nombres_enum=enums)
        evidencias = {e.clase: e for c in candidatos for e in c.evidencias}

        contacto = evidencias["Contact Point"]
        self.assertEqual(contacto.enum, "ContactPointTypeValues")
        self.assertEqual(contacto.atributos_adicionales, [])
        self.assertIn("SOLO tipifica", contacto.nota)

        telefono = evidencias["Phone Address"]
        self.assertEqual(telefono.atributos_adicionales, ["Phone Number"])
        self.assertIn("guarda", telefono.nota)

    def test_sin_dueno_no_hay_candidato(self) -> None:
        solo_importada = {
            "Party": ClaseBian("Party", (OcurrenciaClase(service_domain=LDM, extensible="no"),))
        }
        req = clases_requeridas(tokenizar_consulta(["cliente"]), solo_importada)
        self.assertEqual(req, [])
        self.assertEqual(candidatos_por_propiedad(req, solo_importada), [])


if __name__ == "__main__":
    unittest.main()
