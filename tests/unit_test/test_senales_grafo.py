"""El grafo canónico como señal DETERMINISTA para el conflicto de ownership.

Hasta ahora un `ownership_conflict` era solo la afirmación del revisor adversarial: quedaba como
incidencia `OWNERSHIP_CONFLICT_UNRESOLVED` sin nada que la confirmara ni la desmintiera, y por eso
`ownership_conflict_rate` saltaba a 1.0 con un solo hallazgo. El grafo sí puede comprobarla, con
la misma regla de especificidad que ya gobierna la expansión: dos Service Domains contienden por
un objeto solo si comparten un nodo REAL del catálogo que además **discrimina**. Compartir `Party`
(125 SD) o `Document` (27 SD) no es un conflicto, es el andamiaje del modelo BIAN.

Igual que el resto del módulo, la señal **no reclasifica nada**: separa el conflicto accionable
del ruido anotado, y eso se ve en las métricas (`ownership_conflict_rate_respaldado`).

Sin red y sin LLM: el grafo real de `docs/bian-graph/` más grafos mínimos construidos a mano.
"""

from __future__ import annotations

import unittest

from src.adaptadores.salida.grafo_bian_json import GrafoBianJson
from src.dominio.clasificacion_historias import (
    CONFLICTO_CONFIRMADO_POR_GRAFO,
    CONFLICTO_SIN_RESPALDO_DE_GRAFO,
    confirmar_conflictos_por_grafo,
)
from src.dominio.grafo_bian import AristaBian, GrafoBian, NodoBian, ObjetoCompartido
from src.dominio.normalizacion import normalizar
from unit_test.support import RAIZ

GRAFO_REAL = RAIZ / "docs" / "bian-graph" / "release14.0.0" / "grafo.json"


def _grafo_con_clase_compartida(total_sd: int) -> GrafoBian:
    """Dos SD que modelan la misma clase BOM, más `total_sd - 2` SD de relleno que también la
    modelan: así se controla la especificidad del objeto compartido."""
    nodos = [NodoBian(id="bom_class:x", tipo="BOM_CLASS", nombre="Contact Point", origen="test")]
    aristas = []
    for i in range(total_sd):
        sd = f"SD {i}"
        nodos.append(
            NodoBian(id=f"sd:{i}", tipo="SERVICE_DOMAIN", nombre=sd, service_domain=sd, origen="test")
        )
        aristas.append(AristaBian(desde=f"sd:{i}", hasta="bom_class:x", tipo="MODELA", origen="test"))
    return GrafoBian(nodos=nodos, aristas=aristas)


class TestObjetosCompartidos(unittest.TestCase):
    def test_detecta_la_clase_bom_que_ambos_modelan(self):
        grafo = _grafo_con_clase_compartida(2)
        objetos = grafo.objetos_compartidos(["SD 0", "SD 1"])
        self.assertEqual([o.nombre for o in objetos], ["Contact Point"])
        self.assertEqual(objetos[0].service_domains, ["SD 0", "SD 1"])
        self.assertTrue(objetos[0].especifico)

    def test_un_objeto_que_medio_catalogo_modela_no_es_especifico(self):
        grafo = _grafo_con_clase_compartida(40)
        objetos = grafo.objetos_compartidos(["SD 0", "SD 1"])
        self.assertEqual(objetos[0].total_service_domains, 40)
        self.assertFalse(objetos[0].especifico)

    def test_con_un_solo_service_domain_no_hay_nada_que_comparar(self):
        self.assertEqual(_grafo_con_clase_compartida(3).objetos_compartidos(["SD 0"]), [])

    def test_sobre_el_grafo_real_los_candidatos_conocidos_solo_comparten_genericos(self):
        """Los dos casos reales del proyecto: ningún objeto ESPECÍFICO en común.

        Es el resultado que da sentido a la señal: los conflictos que el revisor adversarial
        marcaba sobre estos candidatos no los respalda el catálogo.
        """
        if not GRAFO_REAL.is_file():
            self.skipTest("grafo canónico no ingestado (scripts/ingest_bian/)")
        grafo = GrafoBianJson(GRAFO_REAL)
        objetos = grafo.objetos_compartidos(
            ["Correspondence", "Party Reference Data Directory", "Party Authentication"]
        )
        self.assertTrue(objetos, "deberían compartir al menos objetos genéricos")
        self.assertEqual([o.nombre for o in objetos if o.especifico], [])

    def test_una_implementacion_que_solo_expande_sigue_siendo_valida(self):
        from src.aplicacion.puertos.grafo_bian import GrafoBianPort

        class SoloExpande(GrafoBianPort):
            def expandir(self, service_domains, *, tope):
                return []

        self.assertEqual(SoloExpande().objetos_compartidos(["a", "b"]), [])


class TestConfirmacionDeConflictos(unittest.TestCase):
    def _objeto(self, total: int, sds: list[str]) -> ObjetoCompartido:
        return ObjetoCompartido(
            nodo="bom_class:x",
            tipo="BOM_CLASS",
            nombre="Contact Point",
            service_domains=sds,
            total_service_domains=total,
        )

    def test_confirma_cuando_el_objeto_compartido_discrimina_Y_es_el_disputado(self):
        veredictos = confirmar_conflictos_por_grafo(
            {"A": "actualizar el punto de contacto"}, [self._objeto(2, ["A", "B"])]
        )
        motivo, detalle = veredictos[normalizar("A")]
        self.assertEqual(motivo, CONFLICTO_CONFIRMADO_POR_GRAFO)
        self.assertIn("Contact Point", detalle)
        self.assertIn("B", detalle)
        self.assertIn("contact", detalle)  # el término que ambos comparten, auditable

    def test_no_respalda_cuando_solo_comparten_andamiaje(self):
        veredictos = confirmar_conflictos_por_grafo(
            {"A": "actualizar el punto de contacto"}, [self._objeto(125, ["A", "B"])]
        )
        motivo, detalle = veredictos[normalizar("A")]
        self.assertEqual(motivo, CONFLICTO_SIN_RESPALDO_DE_GRAFO)
        self.assertIn("Contact Point", detalle)

    def test_no_respalda_cuando_el_objeto_compartido_no_es_el_disputado(self):
        """El caso real que obligó a añadir la tercera condición.

        Con 11 candidatos, la señal confirmaba 6 conflictos apoyándose en objetos sin relación con
        lo disputado: `Access Arrangement` entre Correspondence y Customer Access Entitlement para
        un conflicto sobre "enviar notificación". Un objeto compartido y específico NO es respaldo
        si no tiene nada que ver con el objeto en disputa; si no, la regla responde "¿comparte algo
        con ALGÚN otro candidato?", cuya probabilidad crece con el número de candidatos.
        """
        objeto = ObjetoCompartido(
            nodo="bom_class:acc",
            tipo="BOM_CLASS",
            nombre="Access Arrangement",
            service_domains=["Correspondence", "Customer Access Entitlement"],
            total_service_domains=2,
        )
        veredictos = confirmar_conflictos_por_grafo({"Correspondence": "enviar notificación"}, [objeto])
        motivo, detalle = veredictos[normalizar("Correspondence")]
        self.assertEqual(motivo, CONFLICTO_SIN_RESPALDO_DE_GRAFO)
        self.assertIn("no tienen nada que ver", detalle)

    def test_el_puente_es_en_funciona_en_la_comparacion(self):
        """El nodo viene del catálogo en inglés y el objeto en disputa lo escribe el LLM en
        español: sin traducir, ninguna confirmación sería posible nunca."""
        objeto = ObjetoCompartido(
            nodo="bom_class:n",
            tipo="BOM_CLASS",
            nombre="Notification Record",
            service_domains=["A", "B"],
            total_service_domains=2,
        )
        veredictos = confirmar_conflictos_por_grafo({"A": "enviar notificación"}, [objeto])
        self.assertEqual(veredictos[normalizar("A")][0], CONFLICTO_CONFIRMADO_POR_GRAFO)

    def test_sin_grafo_no_emite_veredicto_y_todo_sigue_como_antes(self):
        self.assertEqual(confirmar_conflictos_por_grafo({"A": "x"}, []), {})
        self.assertEqual(confirmar_conflictos_por_grafo({}, [self._objeto(2, ["A", "B"])]), {})


if __name__ == "__main__":
    unittest.main()
