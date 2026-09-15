"""CRAG: una sola vuelta correctiva, y solo cuando el lote de evidencia no sostiene nada.

El patrón Corrective RAG (calificar lo recuperado, reescribir la consulta, reintentar) encaja aquí
solo en su versión acotada, porque este pipeline ya tiene calificadores deterministas
(`operacion_evidencia_verificable`, `objeto_bom`) y dos propiedades que un lazo agéntico abierto
rompería: reproducibilidad (`huellas_prompts`) y coste predecible por HU.

Lo que se fija:

1. La condición de disparo es ESTRICTA: sin candidatos, o ninguno con operaciones oficiales ni
   modelo BOM. Un lote con evidencia real nunca reintenta (si no, se duplicaría el coste de todas
   las historias para arreglar unas pocas).
2. Apagado (por defecto) no hay reintento nunca.
3. Lo reinyectado se distingue: `origen="crag"` + incidencia `CRAG_RETRY_APPLIED`; no reemplaza a
   ningún candidato del LLM.
4. Un candidato que sigue sin evidencia no se reinyecta: gastaría otra llamada LLM para acabar en
   `NO_OFFICIAL_BIAN_EVIDENCE`.

Sin red y sin LLM.
"""

from __future__ import annotations

import unittest

from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService as Servicio,
)
from src.dominio.historias import (
    ModeloBomPuml,
    OperacionBian,
    PaqueteEvidenciaCandidato,
)


def _paquete(nombre: str, *, con_ops: bool = False, con_bom: bool = False):
    return PaqueteEvidenciaCandidato(
        service_domain=nombre,
        operations=[
            OperacionBian(
                operation_id="RetrieveX", method="GET", path="/x", tipo="CR", grupo="X"
            )
        ]
        if con_ops
        else [],
        bom_modelo=ModeloBomPuml(service_domain=nombre) if con_bom else None,
    )


class TestCondicionDeDisparo(unittest.TestCase):
    def test_lote_vacio_es_debil(self):
        self.assertEqual(Servicio._lote_debil([]), "sin candidatos resueltos")

    def test_lote_sin_operaciones_ni_bom_es_debil(self):
        motivo = Servicio._lote_debil([_paquete("A"), _paquete("B")])
        self.assertIn("ningún candidato", motivo)

    def test_un_solo_candidato_con_operaciones_ya_no_es_debil(self):
        self.assertEqual(Servicio._lote_debil([_paquete("A"), _paquete("B", con_ops=True)]), "")

    def test_un_solo_candidato_con_bom_ya_no_es_debil(self):
        self.assertEqual(Servicio._lote_debil([_paquete("A", con_bom=True)]), "")


class TestVueltaCorrectiva(unittest.TestCase):
    """La vuelta completa, con dobles mínimos: no hace falta el grafo entero para fijar la regla."""

    class _Reloj:
        def queda(self, _etapa: str) -> bool:
            return True

    class _Recuperador:
        def __init__(self, nombres):
            self._nombres = nombres

        def recuperar(self, consulta, k):
            from src.dominio.modelos import CandidatoSD

            self.consulta = consulta
            return [CandidatoSD(service_domain=n, score=1.0) for n in self._nombres[:k]]

    class _Catalogo:
        """Devuelve operaciones solo para los SD que declare `con_evidencia`."""

        def __init__(self, con_evidencia):
            self._con = set(con_evidencia)

        def asegurar(self, nombres, actualizar=False):
            from src.dominio.historias import EvidenciaBian

            return {n: EvidenciaBian(estado="CACHED_VERIFIED") for n in nombres}

        def operaciones_de(self, sd):
            return (
                [OperacionBian(operation_id="RetrieveX", method="GET", path="/x", tipo="CR", grupo="X")]
                if sd in self._con
                else []
            )

        def esquemas_de(self, sd):
            return []

        def schemas_detalle_de(self, sd):
            return []

    def _servicio(self, *, crag: bool, con_evidencia=()):
        s = Servicio.__new__(Servicio)  # sin construir el grafo: aquí se prueba UN método
        s._crag_reintento = crag
        s._recuperadores = [self._Recuperador(["Correspondence", "Party Authentication"])]
        s._retrieval_top_k = 5
        s._retrieval_max_inyectados = 2
        s._rrf_k = 60
        s._rrf_pesos = None
        s._catalogo_operaciones = self._Catalogo(con_evidencia)
        s._catalogo_bom = None
        s._actualizar_cache_bian = False
        return s

    def _estado(self):
        from src.dominio.historias import HistoriaUsuario, IntencionHistoriaLLM

        return {
            "historia": HistoriaUsuario(archivo="HU-01.txt", titulo="Notificar", contenido="..."),
            "intencion": IntencionHistoriaLLM(
                gaps=["no se indica el canal de notificación"],
                capacidades_funcionales=["enviar aviso al cliente"],
            ),
        }

    def _indice(self, nombres):
        from src.dominio.modelos import EntradaCatalogo
        from src.dominio.normalizacion import normalizar

        return {normalizar(n): EntradaCatalogo(service_domain=n) for n in nombres}

    def test_apagado_no_reintenta_nunca(self):
        servicio = self._servicio(crag=False)
        nuevos, incidencia = servicio._vuelta_correctiva(
            self._estado(), [], self._indice(["Correspondence"]), self._Reloj()
        )
        self.assertEqual((nuevos, incidencia), ([], None))

    def test_encendido_reinyecta_con_origen_crag_y_deja_incidencia(self):
        servicio = self._servicio(crag=True, con_evidencia=["Correspondence"])
        nuevos, incidencia = servicio._vuelta_correctiva(
            self._estado(),
            [_paquete("Party Reference Data Directory")],
            self._indice(["Correspondence", "Party Authentication"]),
            self._Reloj(),
        )
        self.assertEqual([p.service_domain for p in nuevos], ["Correspondence"])
        self.assertEqual(nuevos[0].origen, "crag")
        self.assertEqual(incidencia["motivo"], "CRAG_RETRY_APPLIED")

    def test_la_consulta_se_reescribe_con_lo_que_quedo_sin_resolver(self):
        servicio = self._servicio(crag=True, con_evidencia=["Correspondence"])
        servicio._vuelta_correctiva(
            self._estado(),
            [_paquete("Otro")],
            self._indice(["Correspondence"]),
            self._Reloj(),
        )
        consulta = servicio._recuperadores[0].consulta
        self.assertIn("no se indica el canal", consulta)
        self.assertIn("Notificar", consulta)

    def test_no_reinyecta_lo_que_sigue_sin_evidencia(self):
        servicio = self._servicio(crag=True, con_evidencia=[])
        nuevos, _ = servicio._vuelta_correctiva(
            self._estado(), [_paquete("Otro")], self._indice(["Correspondence"]), self._Reloj()
        )
        self.assertEqual(nuevos, [])

    def test_no_duplica_un_candidato_que_ya_estaba(self):
        servicio = self._servicio(crag=True, con_evidencia=["Correspondence"])
        nuevos, _ = servicio._vuelta_correctiva(
            self._estado(),
            [_paquete("Correspondence")],
            self._indice(["Correspondence", "Party Authentication"]),
            self._Reloj(),
        )
        self.assertEqual([p.service_domain for p in nuevos], [])


if __name__ == "__main__":
    unittest.main()
