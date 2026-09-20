"""Reanudar una corrida muerta a mitad: el checkpointer deja de ser solo almacenamiento.

Persistir el estado no sirve de nada si nadie lo lee. Lo que mata estas corridas es que el proceso
termine a mitad -cuota agotada, Ctrl-C, ~300 s que se cortan-, y hasta ahora la unica salida era
volver a empezar. `--reanudar <thread_id>` continua desde el ultimo checkpoint.

Lo que se fija aqui:

1. Una corrida que revienta a mitad se reanuda y TERMINA, sin rehacer el trabajo ya hecho: los
   nodos que ya corrieron no vuelven a llamar al LLM.
2. Reanudar entrega `None` como entrada al grafo. Mandar la entrada otra vez lo reiniciaria desde
   `cargar` y tiraria el trabajo -- seria un "reanudar" que en realidad reempieza.
3. El `thread_id` sale en `parametros`: sin publicarlo, reanudar exigiria leerlo de un log.
4. Sin durabilidad se RECHAZA en vez de re-ejecutar en silencio: es preferible decirlo a repetir
   entera una corrida que el usuario creia que iba a continuar.

Sin red y sin LLM: el analista es el guion determinista de `test_grafo_mapeo`, envuelto en uno que
falla la primera vez.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.checkpointer_sqlite import crear_checkpointer
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.dominio.clasificacion_historias import UmbralesMapeo
from unit_test.support import DOCS
from unit_test.test_grafo_mapeo import _AnalistaGuion, _MapeadorGuion

HU = "Como cliente quiero autorizar una transacción con Smart Token.\nEscenario 1. Autorización"


class _AnalistaQueRevienta(AnalistaMapeoBianPort):
    """Delega en el guion, pero revienta en `revisar_adversarial` mientras `caido` sea True.

    Simula una corrida que muere a mitad: los nodos anteriores ya dejaron su checkpoint.
    """

    def __init__(self) -> None:
        self._interno = _AnalistaGuion()
        self.caido = True
        self.llamadas: list[str] = []

    def _reg(self, nombre, *a):
        self.llamadas.append(nombre)
        return getattr(self._interno, nombre)(*a)

    def extraer_intencion(self, *a):
        return self._reg("extraer_intencion", *a)

    def generar_candidatos(self, *a):
        return self._reg("generar_candidatos", *a)

    def revisar_completitud(self, *a, **kw):
        return self._reg("revisar_completitud", *a)

    def evaluar_candidato(self, *a):
        return self._reg("evaluar_candidato", *a)

    def revisar_adversarial(self, *a):
        if self.caido:
            raise RuntimeError("429 cuota agotada a mitad de la corrida")
        return self._reg("revisar_adversarial", *a)

    def reconciliar_funcionalidad(self, *a):
        return self._reg("reconciliar_funcionalidad", *a)


def _entrada(raiz: Path) -> tuple[str, str]:
    (raiz / "HU").mkdir(exist_ok=True)
    (raiz / "HU" / "HU-01.txt").write_text(HU, encoding="utf-8")
    func = raiz / "f.json"
    func.write_text(json.dumps({"funcionalidad_macro": "Autorización"}), encoding="utf-8")
    return str(raiz / "HU"), str(func)


def _servicio(analista, checkpointer, *, durabilidad="sync"):
    return MapearHistoriasServiceDomainsService(
        CatalogoJson(str(DOCS / "BIAN_Service_Landscape_V14.0_Matrix_View.json")),
        LectorHistoriasFilesystem(),
        analista,
        PublicadorMapeoJson(),
        CatalogoBianCache(
            str(DOCS / "bian-operation-catalogs.json"),
            str(DOCS / "bian-cache"),
            "14.0.0",
            permitir_descargas=False,
        ),
        _MapeadorGuion(),
        catalogo_bom=CatalogoBomPuml(str(DOCS / "bian-diagrams" / "puml-bom")),
        umbrales=UmbralesMapeo(),
        concurrencia=1,
        durabilidad=durabilidad,
        checkpointer=checkpointer,
    )


class TestReanudarCorrida(unittest.TestCase):
    def test_una_corrida_caida_se_reanuda_y_termina_sin_rehacer_lo_hecho(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            checkpointer = crear_checkpointer(raiz / "chk" / "mapeo.sqlite")

            analista = _AnalistaQueRevienta()
            servicio = _servicio(analista, checkpointer)
            with self.assertRaises(Exception):
                servicio.ejecutar(hu, func, str(raiz / "out"))

            hechas_antes = list(analista.llamadas)
            self.assertIn("extraer_intencion", hechas_antes)
            self.assertIn("evaluar_candidato", hechas_antes)

            # El proceso "vuelve a arrancar": servicio nuevo, mismo checkpointer, mismo thread.
            analista.caido = False
            analista.llamadas.clear()
            reanudado = _servicio(analista, checkpointer)
            resultado = reanudado.ejecutar(
                hu, func, str(raiz / "out"), reanudar=servicio._thread_id
            )

            self.assertTrue(resultado.historias, "la corrida reanudada debe terminar")
            self.assertNotIn(
                "extraer_intencion",
                analista.llamadas,
                "no debe rehacer los nodos que ya tenían checkpoint",
            )
            self.assertNotIn("evaluar_candidato", analista.llamadas)
            self.assertIn("revisar_adversarial", analista.llamadas, "sí debe hacer lo que faltaba")

    def test_el_thread_id_se_publica_para_poder_reanudar(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            servicio = _servicio(
                _AnalistaGuion(), crear_checkpointer(raiz / "chk" / "m.sqlite")
            )
            resultado = servicio.ejecutar(hu, func, str(raiz / "out"))
            self.assertTrue(resultado.parametros.get("thread_id"))
            self.assertEqual(resultado.parametros["durabilidad"], "sync")

    def test_sin_durabilidad_no_se_publica_thread_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            resultado = _servicio(_AnalistaGuion(), None, durabilidad="exit").ejecutar(
                hu, func, str(raiz / "out")
            )
            self.assertEqual(resultado.parametros["thread_id"], "")

    def test_reanudar_sin_durabilidad_falla_en_vez_de_reejecutar_en_silencio(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            servicio = _servicio(_AnalistaGuion(), None, durabilidad="exit")
            with self.assertRaises(ValueError) as ctx:
                servicio.ejecutar(hu, func, str(raiz / "out"), reanudar="abc123")
            self.assertIn("durabilidad", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
