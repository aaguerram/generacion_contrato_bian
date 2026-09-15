"""El nodo de operaciones es el mas fragil: se le pide UNA cosa a la vez y se le deja citar por numero.

`seleccionar_operaciones` es el unico paso cuyo fallo deja la historia sin contrato, y hasta ahora
se le pedia lo mas dificil posible: todos los Service Domains elegibles en una sola llamada, y un
`operationId` literal copiado entre decenas. Medido con LLM real, ese paso fallaba y dejaba SD
propietarios con cero operaciones ancladas.

Dos cambios que reducen el espacio de error sin relajar el anclaje:

1. UNA LLAMADA POR SERVICE DOMAIN. Cada llamada ve un solo catalogo y toma una sola decision. Los
   elegibles son 1-2 en la practica, asi que el coste extra es de 0-1 llamadas por HU, y la cache
   de nodos las absorbe al repetir. Cada llamada deja SU huella: el numero de huellas es el numero
   de llamadas LLM, y eso no puede mentir.
2. CITA POR INDICE. Las operaciones van numeradas en el prompt y `resolver_operation_id` acepta el
   numero. Elegir `7` de una lista numerada es mucho mas facil para un modelo pequeno que
   reproducir `InitiateOutbound`, y sigue siendo una cita al catalogo REAL: un indice fuera de
   rango no resuelve nada, igual que un operationId inventado.

Sin red y sin LLM.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.aplicacion.puertos.mapeador_operaciones import MapeadorOperacionesBianPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.dominio.clasificacion_historias import UmbralesMapeo
from src.dominio.cobertura_operaciones import resolver_operation_id
from src.dominio.historias import (
    MapeoOperacionesLLM,
    MetadatosPrompt,
    OperacionBian,
    OperacionPropuestaLLM,
)
from unit_test.support import DOCS
from unit_test.test_grafo_mapeo import _AnalistaGuion


def _ops(*ids) -> list[OperacionBian]:
    return [
        OperacionBian(operation_id=i, method="GET", path=f"/{i}", tipo="CR", grupo="G")
        for i in ids
    ]


class TestCitaPorIndice(unittest.TestCase):
    def setUp(self):
        self.catalogo = _ops("Retrieve", "Update", "InitiateOutbound")

    def test_el_numero_ancla_la_operacion_de_esa_posicion(self):
        self.assertEqual(resolver_operation_id("3", self.catalogo).operation_id, "InitiateOutbound")

    def test_tolera_los_adornos_del_numero(self):
        for cita in ("[2]", "#2", " 2 ", "(2)"):
            self.assertEqual(resolver_operation_id(cita, self.catalogo).operation_id, "Update", cita)

    def test_un_indice_fuera_de_rango_no_resuelve_nada(self):
        """Un numero inventado se trata igual que un operationId inventado."""
        for cita in ("0", "4", "99"):
            self.assertIsNone(resolver_operation_id(cita, self.catalogo), cita)

    def test_el_operationid_literal_sigue_funcionando(self):
        self.assertEqual(
            resolver_operation_id("InitiateOutbound", self.catalogo).operation_id,
            "InitiateOutbound",
        )


class _MapeadorContador(MapeadorOperacionesBianPort):
    """Ancla la PRIMERA operacion de cada SD que recibe, citandola por su indice."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, ...]] = []

    def mapear(self, historia, funcionalidad, operaciones_por_sd, paquetes_por_sd):
        self.llamadas.append(tuple(operaciones_por_sd))
        return MapeoOperacionesLLM(
            operaciones=[
                OperacionPropuestaLLM(service_domain=sd, operation_id="1", justificacion="x")
                for sd in operaciones_por_sd
            ],
            metadatos=MetadatosPrompt(
                prompt_id="mapeo.operaciones",
                prompt_version="1.2.0",
                prompt_sha256="0" * 64,
                nodo="seleccionar_operaciones",
            ),
        )


class TestUnaLlamadaPorServiceDomain(unittest.TestCase):
    def _ejecutar(self, mapeador):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "HU").mkdir()
            (raiz / "HU" / "HU-01.txt").write_text(
                "Como cliente quiero autorizar una transacción con Smart Token.\n"
                "Escenario 1. Autorización",
                encoding="utf-8",
            )
            func = raiz / "f.json"
            func.write_text(json.dumps({"funcionalidad_macro": "Autorización"}), encoding="utf-8")
            servicio = MapearHistoriasServiceDomainsService(
                CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")),
                LectorHistoriasFilesystem(),
                _AnalistaGuion(),
                PublicadorMapeoJson(),
                CatalogoBianCache(
                    str(DOCS / "bian-operation-catalogs.json"),
                    str(DOCS / "bian-cache"),
                    "14.0.0",
                    permitir_descargas=False,
                ),
                mapeador,
                catalogo_bom=CatalogoBomPuml(str(DOCS / "bian-diagrams" / "puml-bom")),
                umbrales=UmbralesMapeo(),
                concurrencia=1,
            )
            return servicio.ejecutar(str(raiz / "HU"), str(func), str(raiz / "out"))

    def test_cada_llamada_recibe_un_solo_service_domain(self):
        mapeador = _MapeadorContador()
        self._ejecutar(mapeador)
        self.assertTrue(mapeador.llamadas, "el nodo de operaciones debe haberse llamado")
        for recibidos in mapeador.llamadas:
            self.assertEqual(len(recibidos), 1, f"llamada con {len(recibidos)} SD: {recibidos}")

    def test_cada_llamada_deja_su_huella(self):
        """El numero de huellas ES el numero de llamadas LLM: no puede quedarse en una."""
        mapeador = _MapeadorContador()
        resultado = self._ejecutar(mapeador)
        huellas = [h for h in resultado.huellas_prompts if h.nodo == "seleccionar_operaciones"]
        self.assertEqual(len(huellas), len(mapeador.llamadas))

    def test_la_operacion_citada_por_indice_queda_anclada(self):
        resultado = self._ejecutar(_MapeadorContador())
        ancladas = [
            o.operation_id
            for h in resultado.historias
            for a in h.service_domains.candidatos_directos
            for o in a.operaciones_bian
        ]
        self.assertTrue(ancladas, "la cita por índice debería haber anclado una operación real")


if __name__ == "__main__":
    unittest.main()
