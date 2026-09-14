"""Catálogo local de operaciones BIAN + paso 2 (mapeador) sin API."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.adaptadores.salida.catalogo_operaciones_bian_json import CatalogoOperacionesBianJson
from src.adaptadores.salida.llm.estrategia import ConfiguracionProveedor
from src.adaptadores.salida.llm.fake import FakeStrategy
from src.adaptadores.salida.mapeador_operaciones_langchain import MapeadorOperacionesLangChain
from src.dominio.historias import FuncionalidadMacro, HistoriaUsuario

DOCS = Path(__file__).resolve().parents[2] / "docs"
OPS = str(DOCS / "bian-operation-catalogs.json")


def _fake_chat():
    cfg = ConfiguracionProveedor(
        chat_model="fake", embeddings_model="fake", api_key=None, temperature=0.0, esfuerzo="low"
    )
    return FakeStrategy(cfg).crear_chat_model()


class TestCatalogoOperaciones(unittest.TestCase):
    def setUp(self):
        self.cat = CatalogoOperacionesBianJson(OPS)

    def test_resuelve_nombre_con_espacios(self):
        ops = self.cat.operaciones_de(
            "Party Authentication"
        )  # SD.json usa espacios; el JSON, compacto
        self.assertIsNotNone(ops)
        ids = {o.operation_id for o in ops}
        self.assertIn("Evaluate", ids)
        self.assertTrue(any(o.tipo == "BQ" for o in ops))
        self.assertTrue(all(o.method and o.path for o in ops))

    def test_sd_sin_catalogo_devuelve_none(self):
        self.assertIsNone(self.cat.operaciones_de("Savings Account"))

    def test_lista_de_sd_con_catalogo(self):
        sds = self.cat.service_domains_con_catalogo()
        self.assertEqual(len(sds), 9)
        self.assertIn("TransactionAuthorization", sds)

    def test_archivo_ausente_no_rompe(self):
        vacio = CatalogoOperacionesBianJson(str(DOCS / "no-existe.json"))
        self.assertIsNone(vacio.operaciones_de("Party Authentication"))
        self.assertEqual(vacio.service_domains_con_catalogo(), set())


class TestMapeadorOperaciones(unittest.TestCase):
    def test_solo_devuelve_operaciones_del_catalogo_provisto(self):
        cat = CatalogoOperacionesBianJson(OPS)
        ops = cat.operaciones_de("Transaction Authorization")
        mapeador = MapeadorOperacionesLangChain(_fake_chat())
        historia = HistoriaUsuario(
            archivo="HU-x.txt",
            titulo="x",
            contenido="Escenario 1. Autorizar transacción con Smart Token",
        )
        r = mapeador.mapear(
            historia,
            FuncionalidadMacro(funcionalidad_macro="F", detalle="d"),
            {"Transaction Authorization": ops},
            {},
        )
        validos = {o.operation_id for o in ops}
        self.assertGreater(len(r.operaciones), 0)
        for op in r.operaciones:
            self.assertEqual(op.service_domain, "Transaction Authorization")
            self.assertIn(op.operation_id, validos)

    def test_sin_sds_no_llama(self):
        mapeador = MapeadorOperacionesLangChain(_fake_chat())
        r = mapeador.mapear(
            HistoriaUsuario(archivo="a", titulo="a", contenido="a"),
            FuncionalidadMacro(funcionalidad_macro="F"),
            {},
            {},
        )
        self.assertEqual(r.operaciones, [])


if __name__ == "__main__":
    unittest.main()
