"""La caché de nodos convierte una re-ejecución en "solo lo que falta" — sin llamar al LLM.

Lo que se fija aquí:

1. Re-ejecutar la MISMA corrida con la caché encendida no hace ni una llamada LLM y da el mismo
   resultado de negocio. Es el mecanismo que abarata medir flag por flag (`canary.py`) y el que
   hoy sustituye al checkpointer persistente cuando una corrida muere a mitad por cuota agotada.
2. Cambiar la entrada semántica de un nodo (el texto de la HU) invalida su entrada de caché: la
   clave la calcula el `key_func` de cada nodo, no el estado entero.
3. La caché nunca cruza cadenas de LLM ni catálogos distintos: la firma de la corrida
   (`cadena_llm` + `esfuerzo` + `catalog_sha256`) entra en la clave.
4. Apagada (por defecto) el grafo se comporta exactamente como antes.

Sin red y sin LLM: el analista es el guion determinista de `test_grafo_mapeo`.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.adaptadores.salida.cache_nodos_archivo import CacheNodosArchivo
from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache
from src.adaptadores.salida.catalogo_bom_puml import CatalogoBomPuml
from src.adaptadores.salida.catalogo_json import CatalogoJson
from src.adaptadores.salida.lector_historias_fs import LectorHistoriasFilesystem
from src.adaptadores.salida.publicador_mapeo_json import PublicadorMapeoJson
from src.aplicacion.puertos.analista_mapeo import AnalistaMapeoBianPort
from src.aplicacion.servicios.mapear_historias_service_domain import (
    MapearHistoriasServiceDomainsService,
)
from src.dominio.clasificacion_historias import UmbralesMapeo
from unit_test.support import DOCS
from unit_test.test_grafo_mapeo import _AnalistaGuion, _MapeadorGuion

HU_ORIGINAL = "Como cliente quiero autorizar una transacción con Smart Token.\nEscenario 1. Autorización"


class _AnalistaContador(AnalistaMapeoBianPort):
    """Cuenta cada llamada LLM delegando en el guion determinista."""

    def __init__(self) -> None:
        self._interno = _AnalistaGuion()
        self.llamadas: list[str] = []

    def _registrar(self, nombre, *args, **kwargs):
        self.llamadas.append(nombre)
        return getattr(self._interno, nombre)(*args, **kwargs)

    def extraer_intencion(self, *a):
        return self._registrar("extraer_intencion", *a)

    def generar_candidatos(self, *a):
        return self._registrar("generar_candidatos", *a)

    def revisar_completitud(self, *a, **kw):
        return self._registrar("revisar_completitud", *a)

    def evaluar_candidato(self, *a):
        return self._registrar("evaluar_candidato", *a)

    def revisar_adversarial(self, *a):
        return self._registrar("revisar_adversarial", *a)

    def reconciliar_funcionalidad(self, *a):
        return self._registrar("reconciliar_funcionalidad", *a)


def _entrada(raiz: Path, texto_hu: str = HU_ORIGINAL) -> tuple[str, str]:
    (raiz / "HU").mkdir(exist_ok=True)
    (raiz / "HU" / "HU-01.txt").write_text(texto_hu, encoding="utf-8")
    func = raiz / "f.json"
    func.write_text(
        json.dumps({"funcionalidad_macro": "Autorización de transacciones"}), encoding="utf-8"
    )
    return str(raiz / "HU"), str(func)


def _servicio(analista, cache, *, firma: str = "fake:fake"):
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
        parametros_base={"cadena_llm": firma, "esfuerzo": "low", "catalog_sha256": "sha-test"},
        cache_nodos=cache,
    )


def _seleccionados(resultado) -> list[str]:
    return [c.service_domain for c in resultado.service_domains_consolidados if c.decision == "SELECTED"]


class TestCacheNodos(unittest.TestCase):
    def test_la_segunda_corrida_no_llama_al_llm_y_da_el_mismo_resultado(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            cache = CacheNodosArchivo(raiz / "cache")

            a1 = _AnalistaContador()
            r1 = _servicio(a1, cache).ejecutar(hu, func, str(raiz / "out1"))
            self.assertTrue(a1.llamadas, "la primera corrida sí llama al LLM")

            a2 = _AnalistaContador()
            r2 = _servicio(a2, cache).ejecutar(hu, func, str(raiz / "out2"))
            self.assertEqual(a2.llamadas, [], "la segunda corrida debe salir entera de la caché")
            self.assertEqual(_seleccionados(r1), _seleccionados(r2))
            self.assertEqual(_seleccionados(r2), ["Transaction Authorization"])

    def test_cambiar_el_texto_de_la_hu_invalida_la_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            cache = CacheNodosArchivo(raiz / "cache")
            _servicio(_AnalistaContador(), cache).ejecutar(hu, func, str(raiz / "out1"))

            _entrada(raiz, HU_ORIGINAL + "\nEscenario 2. Reintento tras rechazo")
            a2 = _AnalistaContador()
            _servicio(a2, cache).ejecutar(hu, func, str(raiz / "out2"))
            self.assertIn("extraer_intencion", a2.llamadas)

    def test_otra_cadena_de_modelos_no_reutiliza_la_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            cache = CacheNodosArchivo(raiz / "cache")
            _servicio(_AnalistaContador(), cache, firma="groq:a").ejecutar(hu, func, str(raiz / "o1"))

            a2 = _AnalistaContador()
            _servicio(a2, cache, firma="gemini:b").ejecutar(hu, func, str(raiz / "o2"))
            self.assertIn("extraer_intencion", a2.llamadas)

    def test_sin_cache_todas_las_corridas_llaman_al_llm(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            _servicio(_AnalistaContador(), None).ejecutar(hu, func, str(raiz / "o1"))
            a2 = _AnalistaContador()
            _servicio(a2, None).ejecutar(hu, func, str(raiz / "o2"))
            self.assertIn("extraer_intencion", a2.llamadas)

    def test_una_entrada_corrupta_degrada_a_fallo_de_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            hu, func = _entrada(raiz)
            cache = CacheNodosArchivo(raiz / "cache")
            _servicio(_AnalistaContador(), cache).ejecutar(hu, func, str(raiz / "o1"))
            for archivo in (raiz / "cache").rglob("*.json"):
                archivo.write_text("{ esto no es json valido", encoding="utf-8")

            a2 = _AnalistaContador()
            r2 = _servicio(a2, cache).ejecutar(hu, func, str(raiz / "o2"))
            self.assertIn("extraer_intencion", a2.llamadas)
            self.assertEqual(_seleccionados(r2), ["Transaction Authorization"])


if __name__ == "__main__":
    unittest.main()
