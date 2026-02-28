from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factpy_kernel.authoring.rules import compile_authoring_rule_v1
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.schema.schema_ir import schema_digest
from factpy_kernel.sdk import Entity, Field, Identity, SDKRegistry
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.service.runtime_v1 import reset_runtime_sessions_for_tests

try:
    from fastapi.testclient import TestClient

    from factpy_kernel.service.app_v1 import app

    _FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover - service extra not installed in core-only environments
    TestClient = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    name: str = Field(cardinality="multi", pred_id="person:name")


@unittest.skipUnless(_FASTAPI_AVAILABLE, "service extra dependencies are not installed")
class ServiceRuntimeV1RoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.client = TestClient(app)  # type: ignore[arg-type]
        self.schema_ir = compile_schema_from_classes([Person])
        self.person_ref = encode_idref_v1("Person", [("source_id", "string", "u1")])

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def test_runtime_session_schema_ir_write_query_export_close_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            open_body = open_resp.json()
            self.assertTrue(open_body["ok"])
            session_id = open_body["session"]["session_id"]
            self.assertEqual(open_body["session"]["counts"]["claims"], 0)
            self.assertEqual(open_body["session"]["schema_digest"], schema_digest(self.schema_ir))

            set_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                    "meta": {"source": "seed"},
                },
            )
            self.assertEqual(set_resp.status_code, 200)
            self.assertTrue(set_resp.json()["ok"])

            add_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/add",
                json={
                    "pred_id": "person:name",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "Alice"]],
                    "meta": {"source": "seed"},
                },
            )
            self.assertEqual(add_resp.status_code, 200)
            self.assertTrue(add_resp.json()["ok"])

            claims_resp = self.client.get(
                f"/v1/runtime/sessions/{session_id}/claims",
                params={"include_meta": "true", "include_args": "true"},
            )
            self.assertEqual(claims_resp.status_code, 200)
            claims_body = claims_resp.json()
            self.assertTrue(claims_body["ok"])
            self.assertEqual(len(claims_body["claims"]), 2)
            country_rows = [row for row in claims_body["claims"] if row["pred_id"] == "person:country"]
            self.assertEqual(len(country_rows), 1)
            self.assertEqual(country_rows[0]["rest_terms"], [["string", "de"]])
            self.assertEqual(country_rows[0]["claim_args"][0]["val_atom"], "de")
            self.assertTrue(any(meta["key"] == "ingest_key" for meta in country_rows[0]["meta_rows"]))

            rule_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/rules/run",
                json={
                    "rule": {
                        "rule_id": "q_country_rows",
                        "version": "1.0.0",
                        "select": ["e", "c"],
                        "where": [["pred", "person:country", ["$e", "$c"]]],
                        "expose": True,
                    }
                },
            )
            self.assertEqual(rule_resp.status_code, 200)
            rule_body = rule_resp.json()
            self.assertTrue(rule_body["ok"])
            self.assertEqual(rule_body["result"]["rows"], [[self.person_ref, "de"]])

            package_dir = str(Path(tmp) / "pkg")
            export_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/packages/export",
                json={"out_dir": package_dir, "package_kind": "audit"},
            )
            self.assertEqual(export_resp.status_code, 200)
            export_body = export_resp.json()
            self.assertTrue(export_body["ok"])
            self.assertTrue(Path(export_body["package"]["manifest_path"]).exists())

            close_resp = self.client.delete(f"/v1/runtime/sessions/{session_id}")
            self.assertEqual(close_resp.status_code, 200)
            self.assertTrue(close_resp.json()["ok"])

            closed_get_resp = self.client.get(f"/v1/runtime/sessions/{session_id}")
            self.assertEqual(closed_get_resp.status_code, 200)
            closed_get_body = closed_get_resp.json()
            self.assertFalse(closed_get_body["ok"])
            self.assertEqual(closed_get_body["errors"][0]["kind"], "runtime_session_not_found")

    def test_registry_routes_and_runtime_rule_ref_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_root = Path(tmp) / "registry"
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")

            registry = SDKRegistry(root_dir=registry_root)
            registry.apply_schema_classes([Person], apply_request_id="apply-1")
            registry.register_rule_spec(
                compile_authoring_rule_v1(
                    {
                        "rule_id": "q_country_rows",
                        "version": "1.0.0",
                        "select": ["e", "c"],
                        "where": [("pred", "person:country", ["$e", "$c"])],
                        "expose": True,
                    },
                    schema_ir=self.schema_ir,
                )
            )

            manifest_resp = self.client.post("/v1/registry/manifest", json={"root_dir": str(registry_root)})
            self.assertEqual(manifest_resp.status_code, 200)
            manifest_body = manifest_resp.json()
            self.assertTrue(manifest_body["ok"])
            self.assertIn("schema", manifest_body["manifest"])

            schema_resp = self.client.post("/v1/registry/schema/read", json={"root_dir": str(registry_root)})
            self.assertEqual(schema_resp.status_code, 200)
            schema_body = schema_resp.json()
            self.assertTrue(schema_body["ok"])
            self.assertEqual(schema_digest(schema_body["schema_ir"]), schema_digest(self.schema_ir))

            assets_resp = self.client.post("/v1/registry/assets/list", json={"root_dir": str(registry_root)})
            self.assertEqual(assets_resp.status_code, 200)
            assets_body = assets_resp.json()
            self.assertTrue(assets_body["ok"])
            self.assertEqual(assets_body["registry"]["rule_ids"], ["q_country_rows"])
            self.assertIn("apply-1", assets_body["registry"]["apply_run_ids"])

            read_rule_resp = self.client.post(
                "/v1/registry/rules/read",
                json={"root_dir": str(registry_root), "rule_id": "q_country_rows"},
            )
            self.assertEqual(read_rule_resp.status_code, 200)
            read_rule_body = read_rule_resp.json()
            self.assertTrue(read_rule_body["ok"])
            self.assertEqual(read_rule_body["rule_spec"]["rule_id"], "q_country_rows")

            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"registry_root": str(registry_root), "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            open_body = open_resp.json()
            self.assertTrue(open_body["ok"])
            session_id = open_body["session"]["session_id"]
            self.assertEqual(open_body["session"]["registry_root"], str(registry_root))

            set_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                    "meta": {"source": "seed"},
                },
            )
            self.assertEqual(set_resp.status_code, 200)
            self.assertTrue(set_resp.json()["ok"])

            rule_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/rules/run",
                json={
                    "registry_root": str(registry_root),
                    "rule": {
                        "rule_id": "q_country_passthrough",
                        "version": "1.0.0",
                        "select": ["e", "c"],
                        "where": [["ruleref", "q_country_rows", "1.0.0", ["$e", "$c"]]],
                        "expose": True,
                    },
                },
            )
            self.assertEqual(rule_resp.status_code, 200)
            rule_body = rule_resp.json()
            self.assertTrue(rule_body["ok"])
            self.assertEqual(rule_body["result"]["rows"], [[self.person_ref, "de"]])


if __name__ == "__main__":
    unittest.main()
