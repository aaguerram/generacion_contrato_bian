from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from src.adaptadores.salida.catalogo_bian_cache import CatalogoBianCache


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class TestCatalogoBianCache(unittest.TestCase):
    def test_cache_existente_no_toca_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "ops.json"
            legacy.write_text('{"service_domains":{}}', encoding="utf-8")
            cache = root / "cache" / "release14.0.0"
            cache.mkdir(parents=True)
            (cache / "PartyAuthentication.json").write_text(
                json.dumps(
                    {
                        "service_domain": "Party Authentication",
                        "release": "14.0.0",
                        "operations": [],
                        "evidence": {"content_sha256": "abc"},
                    }
                ),
                encoding="utf-8",
            )
            cat = CatalogoBianCache(legacy, root / "cache")
            with patch("urllib.request.urlopen", side_effect=AssertionError("red no esperada")):
                ev = cat.asegurar(["Party Authentication"])["Party Authentication"]
            self.assertEqual(ev.estado, "CACHED_VERIFIED")

    def test_descarga_ausente_y_refresh_explicito(self):
        oas = b"""openapi: 3.0.1\npaths:\n  /PartyAuthentication/Evaluate:\n    post:\n      tags: ["CR - PartyAuthenticationAssessment"]\n      operationId: Evaluate\n      summary: Evaluate authentication\ncomponents:\n  schemas:\n    PartyAuthentication: {type: object}\n"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "ops.json"
            legacy.write_text('{"service_domains":{}}', encoding="utf-8")
            cat = CatalogoBianCache(legacy, root / "cache")
            calls = [_Response(b'{"sha":"deadbeef"}'), _Response(oas)]
            with patch("urllib.request.urlopen", side_effect=calls):
                ev = cat.asegurar(["Party Authentication"])["Party Authentication"]
            self.assertEqual(ev.estado, "VERIFIED")
            self.assertEqual(cat.operaciones_de("Party Authentication")[0].operation_id, "Evaluate")
            self.assertEqual(cat.esquemas_de("Party Authentication"), ["PartyAuthentication"])
            self.assertTrue(ev.content_sha256 and ev.source_commit_sha == "deadbeef")
            with patch("urllib.request.urlopen", return_value=_Response(oas)):
                refreshed = cat.asegurar(["Party Authentication"], actualizar=True)
            self.assertEqual(refreshed["Party Authentication"].estado, "VERIFIED")

    def test_reintenta_sobre_503_y_luego_descarga(self):
        oas = b"openapi: 3.0.1\npaths: {}\ncomponents: {schemas: {}}\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "ops.json"
            legacy.write_text('{"service_domains":{}}', encoding="utf-8")
            cat = CatalogoBianCache(legacy, root / "cache")
            err = urllib.error.HTTPError("u", 503, "busy", {}, None)
            seq = [_Response(b'{"sha":"c0ffee"}'), err, _Response(oas)]
            with patch("time.sleep"), patch("urllib.request.urlopen", side_effect=seq):
                ev = cat.asegurar(["Party Authentication"])["Party Authentication"]
            self.assertEqual(ev.estado, "VERIFIED")

    def test_sin_red_ni_cache_es_evidencia_no_disponible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "ops.json"
            legacy.write_text('{"service_domains":{}}', encoding="utf-8")
            cat = CatalogoBianCache(legacy, root / "cache")
            with (
                patch("time.sleep"),
                patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")),
            ):
                ev = cat.asegurar(["Party Authentication"])["Party Authentication"]
            self.assertEqual(ev.estado, "BIAN_EVIDENCE_UNAVAILABLE")

    _OAS_V2 = (
        b"openapi: 3.0.1\n"
        b"paths:\n"
        b"  /PartyAuthentication/Evaluate:\n"
        b"    post:\n"
        b'      tags: ["CR - PartyAuthenticationAssessment"]\n'
        b"      operationId: Evaluate\n"
        b"      requestBody: {$ref: '#/components/requestBodies/PartyAuthentication'}\n"
        b"      responses:\n"
        b"        '200': {$ref: '#/components/responses/PartyAuthentication'}\n"
        b"  /PartyAuthentication/pid/Password/Evaluate:\n"
        b"    post:\n"
        b'      tags: ["BQ - Password"]\n'
        b"      operationId: EvaluatePassword\n"
        b"components:\n"
        b"  requestBodies:\n"
        b"    PartyAuthentication:\n"
        b"      content: {application/json: {schema: {$ref: '#/components/schemas/PartyAuthentication'}}}\n"
        b"  responses:\n"
        b"    PartyAuthentication:\n"
        b"      content: {application/json: {schema: {$ref: '#/components/schemas/PartyAuthentication'}}}\n"
        b"  schemas:\n"
        b"    PartyAuthentication:\n"
        b"      type: object\n"
        b"      properties:\n"
        b"        PartyAuthenticationResult: {$ref: '#/components/schemas/Resultvalues'}\n"
        b"        PartyReference: {type: string}\n"
        b"    Resultvalues: {type: string, enum: [Pass, Fail]}\n"
    )

    def test_v2_extrae_schemas_con_cuerpo_request_response_y_catalogo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "ops.json"
            legacy.write_text('{"service_domains":{}}', encoding="utf-8")
            cat = CatalogoBianCache(legacy, root / "cache")
            with patch(
                "urllib.request.urlopen",
                side_effect=[_Response(b'{"sha":"c0ffee"}'), _Response(self._OAS_V2)],
            ):
                cat.asegurar(["Party Authentication"])
            ops = {o.operation_id: o for o in cat.operaciones_de("Party Authentication")}
            self.assertEqual(ops["Evaluate"].request_schema, "PartyAuthentication")
            self.assertEqual(ops["Evaluate"].response_schema, "PartyAuthentication")
            self.assertEqual(ops["EvaluatePassword"].tipo, "BQ")
            self.assertEqual(
                ops["EvaluatePassword"].parent_control_record, "PartyAuthenticationAssessment"
            )

            det = {s.name: s for s in cat.schemas_detalle_de("Party Authentication")}
            self.assertEqual(det["Resultvalues"].kind, "enum")
            self.assertEqual(det["Resultvalues"].enum_values, ["Pass", "Fail"])
            props = {p.name: p for p in det["PartyAuthentication"].properties}
            self.assertEqual(props["PartyAuthenticationResult"].ref, "Resultvalues")

            catlg = cat.catalogo_estructurado_de("Party Authentication")
            self.assertEqual(
                [c["name"] for c in catlg["control_records"]], ["PartyAuthenticationAssessment"]
            )
            self.assertEqual(
                catlg["behavior_qualifiers"][0]["parent_control_record"],
                "PartyAuthenticationAssessment",
            )


if __name__ == "__main__":
    unittest.main()
