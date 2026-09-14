"""Modelo canónico BIAN: expansión por grafo acotada y auditable.

La expansión ingenua no sirve: sobre el grafo real, desde `Correspondence` se alcanzan 157 de los
341 Service Domains en dos saltos, porque clases genéricas del BOM (`Party` la modelan 125 SD)
conectan casi todo con casi todo. Estos tests fijan las defensas: se ignoran los puentes muy
compartidos, se puntúa por rareza y cada candidato dice por dónde se llegó.

Deterministas y sin red: un grafo mínimo construido a mano, más el grafo real si está ingestado.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from src.dominio.grafo_bian import (
    MAX_SD_POR_PUENTE,
    AristaBian,
    GrafoBian,
    NodoBian,
    id_nodo,
)

GRAFO_REAL = Path(__file__).resolve().parents[2] / "docs/bian-graph/release14.0.0/grafo.json"
_ORIGEN = "docs/test"


def _sd(nombre: str) -> NodoBian:
    return NodoBian(
        id=id_nodo("SERVICE_DOMAIN", nombre),
        tipo="SERVICE_DOMAIN",
        nombre=nombre,
        service_domain=nombre,
        origen=_ORIGEN,
    )


def _clase(nombre: str) -> NodoBian:
    return NodoBian(
        id=id_nodo("BOM_CLASS", nombre), tipo="BOM_CLASS", nombre=nombre, origen=_ORIGEN
    )


def _modela(sd: str, clase: str) -> AristaBian:
    return AristaBian(
        desde=id_nodo("SERVICE_DOMAIN", sd),
        hasta=id_nodo("BOM_CLASS", clase),
        tipo="MODELA",
        origen=_ORIGEN,
    )


class TestExpansionAcotada(unittest.TestCase):
    def _grafo_con_hub(self, n_sd_en_hub: int) -> GrafoBian:
        """Un SD 'A' y otro 'B' unidos solo por una clase que modelan `n_sd_en_hub` SD."""
        nodos = [_clase("ClasePuente")]
        aristas = []
        for i in range(n_sd_en_hub):
            nombre = f"SD {i}"
            nodos.append(_sd(nombre))
            aristas.append(_modela(nombre, "ClasePuente"))
        return GrafoBian(nodos=nodos, aristas=aristas)

    def test_un_puente_especifico_si_propone_candidatos(self):
        g = self._grafo_con_hub(2)
        candidatos = g.service_domains_alcanzables("SD 0")
        self.assertEqual([c.service_domain for c in candidatos], ["SD 1"])
        self.assertEqual(candidatos[0].puentes, ["ClasePuente"])
        self.assertGreater(candidatos[0].score, 0)

    def test_un_puente_compartido_por_medio_catalogo_no_propone_nada(self):
        g = self._grafo_con_hub(MAX_SD_POR_PUENTE + 5)
        self.assertEqual(g.service_domains_alcanzables("SD 0"), [])

    def test_compartir_varios_puentes_raros_puntua_mas(self):
        nodos = [_sd("A"), _sd("B"), _sd("C"), _clase("X"), _clase("Y"), _clase("Z")]
        aristas = [
            _modela("A", "X"),
            _modela("B", "X"),  # A y B comparten 1 puente
            _modela("A", "Y"),
            _modela("C", "Y"),
            _modela("A", "Z"),
            _modela("C", "Z"),  # A y C comparten 2
        ]
        candidatos = GrafoBian(nodos=nodos, aristas=aristas).service_domains_alcanzables("A")
        self.assertEqual(candidatos[0].service_domain, "C", "más puentes compartidos = más score")

    def test_la_jerarquia_no_es_camino_de_expansion(self):
        """Compartir Business Area no dice nada sobre ownership."""
        ba = NodoBian(
            id=id_nodo("BUSINESS_AREA", "BA"), tipo="BUSINESS_AREA", nombre="BA", origen=_ORIGEN
        )
        g = GrafoBian(
            nodos=[_sd("A"), _sd("B"), ba],
            aristas=[
                AristaBian(
                    desde=id_nodo("SERVICE_DOMAIN", "A"),
                    hasta=ba.id,
                    tipo="PERTENECE_A",
                    origen=_ORIGEN,
                ),
                AristaBian(
                    desde=id_nodo("SERVICE_DOMAIN", "B"),
                    hasta=ba.id,
                    tipo="PERTENECE_A",
                    origen=_ORIGEN,
                ),
            ],
        )
        self.assertEqual(g.service_domains_alcanzables("A"), [])

    def test_sd_desconocido_no_revienta(self):
        self.assertEqual(GrafoBian().service_domains_alcanzables("No Existe"), [])


@unittest.skipUnless(GRAFO_REAL.is_file(), "grafo no ingestado: scripts/ingest_bian/")
class TestGrafoRealIngestado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = GrafoBian.model_validate_json(GRAFO_REAL.read_text(encoding="utf-8"))

    def test_toda_arista_tiene_origen(self):
        sin_origen = [a for a in self.g.aristas if not a.origen]
        self.assertEqual(
            sin_origen, [], "una relación sin procedencia no debería haberse ingestado"
        )

    def test_los_341_service_domains_estan_en_el_grafo(self):
        sd = [n for n in self.g.nodos if n.tipo == "SERVICE_DOMAIN"]
        self.assertEqual(len(sd), 341)

    def test_la_expansion_real_no_devuelve_medio_catalogo(self):
        candidatos = self.g.service_domains_alcanzables("Correspondence")
        self.assertLessEqual(len(candidatos), 10)
        self.assertTrue(
            all(c.puentes or c.camino for c in candidatos), "cada candidato es auditable"
        )


if __name__ == "__main__":
    unittest.main()
