from __future__ import annotations

import copy
import re
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from factpy_kernel.authoring import FileAuthoringRegistry
from factpy_kernel.authoring.rules import compile_authoring_rule_v1
from factpy_kernel.core.derivation.accept import AcceptResult
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
    country_copy: str = Field(cardinality="functional", pred_id="person:country_copy")
    name: str = Field(cardinality="multi", pred_id="person:name")


class ServiceRouteLayerBoundaryV1Tests(unittest.TestCase):
    def test_app_route_layer_imports_only_service_modules(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "service" / "app_v1.py"
        import_line = re.compile(r"^\s*(from|import)\s+(factpy_kernel\.[A-Za-z0-9_\.]+)")
        offenders: list[str] = []
        for line in app_path.read_text(encoding="utf-8").splitlines():
            match = import_line.match(line)
            if match is None:
                continue
            module_name = match.group(2)
            if not module_name.startswith("factpy_kernel.service"):
                offenders.append(module_name)
        self.assertEqual(offenders, [])


@unittest.skipUnless(_FASTAPI_AVAILABLE, "service extra dependencies are not installed")
class ServiceRuntimeV1RoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()
        self.client = TestClient(app)  # type: ignore[arg-type]
        self.schema_ir = compile_schema_from_classes([Person])
        self.person_ref = encode_idref_v1("Person", [("source_id", "string", "u1")])

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def test_runtime_session_schema_digest_remains_stable_across_operations(self) -> None:
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
            expected_digest = open_body["session"]["schema_digest"]
            self.assertEqual(expected_digest, schema_digest(self.schema_ir))

            get_initial_resp = self.client.get(f"/v1/runtime/sessions/{session_id}")
            self.assertEqual(get_initial_resp.status_code, 200)
            self.assertEqual(get_initial_resp.json()["session"]["schema_digest"], expected_digest)

            set_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
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
                },
            )
            self.assertEqual(add_resp.status_code, 200)
            self.assertTrue(add_resp.json()["ok"])

            get_after_write_resp = self.client.get(f"/v1/runtime/sessions/{session_id}")
            self.assertEqual(get_after_write_resp.status_code, 200)
            self.assertEqual(get_after_write_resp.json()["session"]["schema_digest"], expected_digest)

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
            self.assertTrue(rule_resp.json()["ok"])

            package_dir = str(Path(tmp) / "pkg")
            export_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/packages/export",
                json={"out_dir": package_dir, "package_kind": "audit"},
            )
            self.assertEqual(export_resp.status_code, 200)
            self.assertTrue(export_resp.json()["ok"])

            get_after_export_resp = self.client.get(f"/v1/runtime/sessions/{session_id}")
            self.assertEqual(get_after_export_resp.status_code, 200)
            self.assertEqual(get_after_export_resp.json()["session"]["schema_digest"], expected_digest)

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

    def test_derivation_evaluate_and_accept_fact_candidate_roundtrip(self) -> None:
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

            evaluate_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/derivations/evaluate",
                json={
                    "derivation": {
                        "derivation_id": "drv.country_copy",
                        "version": "1.0.0",
                        "target": "person:country_copy",
                        "head_vars": ["$E", "$C"],
                        "where": [["pred", "person:country", ["$E", "$C"]]],
                        "mode": "python",
                        "temporal_view": "record",
                        "materialize_as": "fact",
                    }
                },
            )
            self.assertEqual(evaluate_resp.status_code, 200)
            evaluate_body = evaluate_resp.json()
            self.assertTrue(evaluate_body["ok"])
            self.assertEqual(evaluate_body["meta"]["mode"], "python")
            self.assertEqual(evaluate_body["meta"]["temporal_view"], "record")
            self.assertEqual(evaluate_body["meta"]["candidate_count"], 1)
            self.assertEqual(evaluate_body["meta"]["returned_count"], 1)
            self.assertFalse(evaluate_body["meta"]["truncated"])
            self.assertNotIn("materialize_as", evaluate_body["meta"])
            self.assertEqual(evaluate_body["evaluation"]["derivation_id"], "drv.country_copy")
            self.assertEqual(evaluate_body["evaluation"]["version"], "1.0.0")
            self.assertEqual(evaluate_body["evaluation"]["target_pred_id"], "person:country_copy")

            candidate = evaluate_body["evaluation"]["candidates"][0]
            self.assertEqual(candidate["payload"]["e_ref"], self.person_ref)
            self.assertEqual(candidate["payload"]["rest_terms"], [["string", "de"]])

            accept_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/derivations/accept",
                json={
                    "candidate": candidate,
                    "options": {"approved_by": "alice", "note": "ok"},
                },
            )
            self.assertEqual(accept_resp.status_code, 200)
            accept_body = accept_resp.json()
            self.assertTrue(accept_body["ok"])
            self.assertFalse(accept_body["meta"]["dry_run"])
            self.assertFalse(accept_body["meta"]["terminal"])
            self.assertEqual(accept_body["accept"]["accepted_count"], 1)
            self.assertEqual(accept_body["accept"]["skipped_count"], 0)
            self.assertEqual(accept_body["accept"]["diagnostics_contract_version"], 1)
            self.assertEqual(accept_body["accept"]["skipped_reason_counts"], {})
            self.assertEqual(accept_body["accept"]["written_assertions"][0]["pred_id"], "person:country_copy")

            claims_resp = self.client.get(
                f"/v1/runtime/sessions/{session_id}/claims",
                params={"pred_id": "person:country_copy"},
            )
            self.assertEqual(claims_resp.status_code, 200)
            claims_body = claims_resp.json()
            self.assertTrue(claims_body["ok"])
            self.assertEqual(len(claims_body["claims"]), 1)
            self.assertEqual(claims_body["claims"][0]["rest_terms"], [["string", "de"]])

    def test_derivation_accept_rejects_clipped_candidate_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            set_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                },
            )
            self.assertEqual(set_resp.status_code, 200)
            self.assertTrue(set_resp.json()["ok"])

            evaluate_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/derivations/evaluate",
                json={
                    "derivation": {
                        "derivation_id": "drv.country_copy",
                        "version": "1.0.0",
                        "target": "person:country_copy",
                        "head_vars": ["$E", "$C"],
                        "where": [["pred", "person:country", ["$E", "$C"]]],
                    }
                },
            )
            self.assertEqual(evaluate_resp.status_code, 200)
            candidate = evaluate_resp.json()["evaluation"]["candidates"][0]
            del candidate["payload"]["terms"]
            del candidate["payload"]["rest_terms"]

            accept_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/derivations/accept",
                json={"candidate": candidate},
            )
            self.assertEqual(accept_resp.status_code, 200)
            accept_body = accept_resp.json()
            self.assertFalse(accept_body["ok"])
            self.assertEqual(accept_body["errors"][0]["kind"], "shape")
            self.assertEqual(accept_body["errors"][0]["path"], "$.candidate.payload.rest_terms")

    def test_derivation_accept_marks_aborted_result_as_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            set_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                },
            )
            self.assertEqual(set_resp.status_code, 200)
            self.assertTrue(set_resp.json()["ok"])

            evaluate_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/derivations/evaluate",
                json={
                    "derivation": {
                        "derivation_id": "drv.country_copy",
                        "version": "1.0.0",
                        "target": "person:country_copy",
                        "head_vars": ["$E", "$C"],
                        "where": [["pred", "person:country", ["$E", "$C"]]],
                    }
                },
            )
            self.assertEqual(evaluate_resp.status_code, 200)
            candidate = evaluate_resp.json()["evaluation"]["candidates"][0]

            with patch(
                "factpy_kernel.core.store.runtime.Store.accept",
                return_value=AcceptResult(
                    materialize_id="mat_v1:aborted",
                    run_id="run-aborted",
                    accepted_count=0,
                    skipped_count=1,
                    written_assertions=[],
                    skipped_reason_counts={"aborted": 1},
                    diagnostics=[
                        {
                            "code": "RECORD_REJECT_ABORTED",
                            "severity": "error",
                            "path": "$.accept.record",
                            "message": "record accept is aborted and cannot be retried",
                            "data": {},
                        }
                    ],
                ),
            ):
                accept_resp = self.client.post(
                    f"/v1/runtime/sessions/{session_id}/derivations/accept",
                    json={"candidate": candidate},
                )
            self.assertEqual(accept_resp.status_code, 200)
            accept_body = accept_resp.json()
            self.assertTrue(accept_body["ok"])
            self.assertTrue(accept_body["meta"]["terminal"])
            self.assertEqual(accept_body["accept"]["skipped_reason_counts"], {"aborted": 1})

    def test_runtime_query_explain_fact_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            set_country_de = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                    "meta": {"source": "seed-a"},
                },
            )
            self.assertEqual(set_country_de.status_code, 200)
            self.assertTrue(set_country_de.json()["ok"])

            explain_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/explain-fact",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "val_atoms": ["de"],
                },
            )
            self.assertEqual(explain_resp.status_code, 200)
            explain_body = explain_resp.json()
            self.assertTrue(explain_body["ok"])
            self.assertEqual(explain_body["meta"], {"pred_id": "person:country", "e_ref": self.person_ref})
            self.assertEqual(explain_body["explain"]["pred_id"], "person:country")
            self.assertEqual(explain_body["explain"]["e_ref"], self.person_ref)
            self.assertEqual(len(explain_body["explain"]["active_claims"]), 1)
            self.assertEqual(explain_body["explain"]["active_claims"][0]["args"], [self.person_ref, "de"])
            self.assertEqual(
                explain_body["explain"]["chosen_asrt_id"],
                explain_body["explain"]["active_claims"][0]["asrt_id"],
            )

            set_country_fr = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "fr"]],
                    "meta": {"source": "seed-b"},
                },
            )
            self.assertEqual(set_country_fr.status_code, 200)
            self.assertTrue(set_country_fr.json()["ok"])

            conflicts_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/conflicts",
                json={"pred_id": "person:country", "e_ref": self.person_ref},
            )
            self.assertEqual(conflicts_resp.status_code, 200)
            conflicts_body = conflicts_resp.json()
            self.assertTrue(conflicts_body["ok"])
            self.assertEqual(conflicts_body["meta"], {"pred_id": "person:country", "e_ref": self.person_ref})
            self.assertEqual(conflicts_body["conflicts"]["pred_id"], "person:country")
            self.assertEqual(conflicts_body["conflicts"]["e_ref"], self.person_ref)
            self.assertEqual(len(conflicts_body["conflicts"]["active_asrt_ids"]), 2)
            self.assertIn(
                conflicts_body["conflicts"]["chosen_asrt_id"],
                conflicts_body["conflicts"]["active_asrt_ids"],
            )

    def test_runtime_query_resolve_mapping_serializes_mapping_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            mapping_schema_ir = _schema_ir_with_mapping(
                self.schema_ir,
                tie_break="latest_by_ingested_at_then_min_assertion_id",
            )
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": mapping_schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            mention_ref = encode_idref_v1("Person", [("source_id", "string", "m1")])
            canon_ref = encode_idref_v1("Person", [("source_id", "string", "c1")])

            write_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "er:canon_of",
                    "e_ref": mention_ref,
                    "rest_terms": [["entity_ref", canon_ref]],
                    "meta": {"source": "seed"},
                },
            )
            self.assertEqual(write_resp.status_code, 200)
            self.assertTrue(write_resp.json()["ok"])

            mapping_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/resolve-mapping",
                json={"pred_id": "er:canon_of"},
            )
            self.assertEqual(mapping_resp.status_code, 200)
            mapping_body = mapping_resp.json()
            self.assertTrue(mapping_body["ok"])
            self.assertEqual(mapping_body["meta"], {"pred_id": "er:canon_of"})
            self.assertEqual(mapping_body["mapping"]["pred_id"], "er:canon_of")
            self.assertEqual(
                mapping_body["mapping"]["chosen_map"],
                [{"key_tuple": [mention_ref], "value_tuple": [canon_ref]}],
            )
            self.assertEqual(len(mapping_body["mapping"]["candidates"]), 1)
            self.assertEqual(mapping_body["mapping"]["candidates"][0]["key_tuple"], [mention_ref])
            self.assertEqual(mapping_body["mapping"]["candidates"][0]["value_tuple"], [canon_ref])
            self.assertEqual(len(mapping_body["mapping"]["decisions"]), 1)
            self.assertEqual(mapping_body["mapping"]["decisions"][0]["chosen_value_tuple"], [canon_ref])
            self.assertEqual(mapping_body["mapping"]["conflicts"], [])

    def test_runtime_query_resolve_mapping_rejects_non_mapping_predicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            mapping_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/resolve-mapping",
                json={"pred_id": "person:country"},
            )
            self.assertEqual(mapping_resp.status_code, 200)
            mapping_body = mapping_resp.json()
            self.assertFalse(mapping_body["ok"])
            self.assertEqual(mapping_body["errors"][0]["kind"], "shape")
            self.assertEqual(mapping_body["errors"][0]["path"], "$.pred_id")

    def test_runtime_query_resolve_mapping_reports_mapping_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            mapping_schema_ir = _schema_ir_with_mapping(self.schema_ir)
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": mapping_schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            mention_ref = encode_idref_v1("Person", [("source_id", "string", "m2")])
            canon_a_ref = encode_idref_v1("Person", [("source_id", "string", "ca")])
            canon_b_ref = encode_idref_v1("Person", [("source_id", "string", "cb")])

            write_a = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "er:canon_of",
                    "e_ref": mention_ref,
                    "rest_terms": [["entity_ref", canon_a_ref]],
                    "meta": {"source": "seed-a"},
                },
            )
            self.assertEqual(write_a.status_code, 200)
            self.assertTrue(write_a.json()["ok"])

            write_b = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "er:canon_of",
                    "e_ref": mention_ref,
                    "rest_terms": [["entity_ref", canon_b_ref]],
                    "meta": {"source": "seed-b"},
                },
            )
            self.assertEqual(write_b.status_code, 200)
            self.assertTrue(write_b.json()["ok"])

            mapping_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/resolve-mapping",
                json={"pred_id": "er:canon_of"},
            )
            self.assertEqual(mapping_resp.status_code, 200)
            mapping_body = mapping_resp.json()
            self.assertFalse(mapping_body["ok"])
            self.assertEqual(mapping_body["meta"], {"pred_id": "er:canon_of"})
            self.assertEqual(mapping_body["errors"][0]["kind"], "mapping_conflict")
            self.assertEqual(mapping_body["errors"][0]["path"], "$.pred_id")
            self.assertEqual(mapping_body["errors"][0]["details"]["conflicts"][0]["key_tuple"], [mention_ref])

    def test_runtime_query_view_facts_projects_rows_without_audit_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            country_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                },
            )
            self.assertEqual(country_resp.status_code, 200)
            self.assertTrue(country_resp.json()["ok"])

            name_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/add",
                json={
                    "pred_id": "person:name",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "Alice"]],
                },
            )
            self.assertEqual(name_resp.status_code, 200)
            self.assertTrue(name_resp.json()["ok"])

            view_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/view-facts",
                json={"temporal_view": "record", "legacy_record_visibility": "allow"},
            )
            self.assertEqual(view_resp.status_code, 200)
            view_body = view_resp.json()
            self.assertTrue(view_body["ok"])
            self.assertEqual(
                view_body["meta"],
                {
                    "temporal_view": "record",
                    "legacy_record_visibility": "allow",
                    "pred_count": 4,
                    "total_tuple_count": 2,
                },
            )
            self.assertEqual(view_body["view"]["facts"]["person:country"], [[self.person_ref, "de"]])
            self.assertEqual(view_body["view"]["facts"]["person:name"], [[self.person_ref, "Alice"]])
            self.assertEqual(view_body["view"]["facts"]["person:country_copy"], [])
            self.assertNotIn("audit", view_body["view"])

    def test_runtime_query_view_facts_can_include_audit_with_active_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            country_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
                },
            )
            self.assertEqual(country_resp.status_code, 200)
            self.assertTrue(country_resp.json()["ok"])

            view_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/view-facts",
                json={"temporal_view": "active", "include_audit": True},
            )
            self.assertEqual(view_resp.status_code, 200)
            view_body = view_resp.json()
            self.assertTrue(view_body["ok"])
            self.assertEqual(view_body["meta"]["temporal_view"], "active")
            self.assertEqual(view_body["meta"]["legacy_record_visibility"], "allow")
            self.assertEqual(view_body["meta"]["pred_count"], 4)
            self.assertEqual(view_body["meta"]["total_tuple_count"], 1)
            self.assertEqual(view_body["view"]["facts"]["person:country"], [[self.person_ref, "de"]])
            self.assertEqual(
                view_body["view"]["audit"],
                {
                    "contract_version": 1,
                    "legacy_record_total": 0,
                    "legacy_record_by_pred": {},
                    "legacy_exists_without_roles_total": 0,
                    "legacy_exists_without_roles_by_pred": {},
                    "marker_conflict_total": 0,
                    "marker_conflict_by_reason": {},
                    "committed_hidden_count_mismatch_total": 0,
                    "committed_hidden_count_mismatch_by_pred": {},
                },
            )

    def test_runtime_query_view_facts_rejects_invalid_legacy_record_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")
            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"schema_ir": self.schema_ir, "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            session_id = open_resp.json()["session"]["session_id"]

            view_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/queries/view-facts",
                json={"legacy_record_visibility": "visible"},
            )
            self.assertEqual(view_resp.status_code, 200)
            view_body = view_resp.json()
            self.assertFalse(view_body["ok"])
            self.assertEqual(view_body["errors"][0]["kind"], "shape")
            self.assertEqual(view_body["errors"][0]["path"], "$.legacy_record_visibility")

    def test_registry_read_routes_do_not_trigger_registry_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_root = Path(tmp) / "registry"
            _build_registry(
                registry_root,
                schema_ir=self.schema_ir,
                apply_request_id="apply-1",
                rule_id="q_country_rows",
                pred_id="person:country",
                derivation_id="drv.country_copy",
            )

            with ExitStack() as stack:
                for method_name in (
                    "upsert_schema_ir",
                    "register_rule_spec",
                    "register_derivation_spec",
                    "append_apply_event",
                    "_save_manifest",
                    "_write_if_changed",
                ):
                    stack.enter_context(
                        patch.object(
                            FileAuthoringRegistry,
                            method_name,
                            autospec=True,
                            side_effect=AssertionError(f"unexpected registry write via {method_name}"),
                        )
                    )

                manifest_resp = self.client.post("/v1/registry/manifest", json={"root_dir": str(registry_root)})
                self.assertEqual(manifest_resp.status_code, 200)
                self.assertTrue(manifest_resp.json()["ok"])

                schema_resp = self.client.post("/v1/registry/schema/read", json={"root_dir": str(registry_root)})
                self.assertEqual(schema_resp.status_code, 200)
                self.assertTrue(schema_resp.json()["ok"])

                assets_resp = self.client.post("/v1/registry/assets/list", json={"root_dir": str(registry_root)})
                self.assertEqual(assets_resp.status_code, 200)
                self.assertTrue(assets_resp.json()["ok"])

                rule_resp = self.client.post(
                    "/v1/registry/rules/read",
                    json={"root_dir": str(registry_root), "rule_id": "q_country_rows"},
                )
                self.assertEqual(rule_resp.status_code, 200)
                self.assertTrue(rule_resp.json()["ok"])

                derivation_resp = self.client.post(
                    "/v1/registry/derivations/read",
                    json={"root_dir": str(registry_root), "derivation_id": "drv.country_copy"},
                )
                self.assertEqual(derivation_resp.status_code, 200)
                self.assertTrue(derivation_resp.json()["ok"])

    def test_registry_routes_and_runtime_rule_ref_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_root = Path(tmp) / "registry"
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")

            _build_registry(
                registry_root,
                schema_ir=self.schema_ir,
                apply_request_id="apply-1",
                rule_id="q_country_rows",
                pred_id="person:country",
                derivation_id="drv.country_copy",
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

    def test_runtime_rule_uses_override_registry_root_when_explicitly_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry_root_country = Path(tmp) / "registry_country"
            registry_root_name = Path(tmp) / "registry_name"
            ledger_path = str(Path(tmp) / "runtime" / "ledger.db")

            _build_registry(
                registry_root_country,
                schema_ir=self.schema_ir,
                apply_request_id="apply-country",
                rule_id="q_base_rows",
                pred_id="person:country",
            )
            _build_registry(
                registry_root_name,
                schema_ir=self.schema_ir,
                apply_request_id="apply-name",
                rule_id="q_base_rows",
                pred_id="person:name",
            )

            open_resp = self.client.post(
                "/v1/runtime/sessions/open",
                json={"registry_root": str(registry_root_country), "ledger_path": ledger_path},
            )
            self.assertEqual(open_resp.status_code, 200)
            open_body = open_resp.json()
            self.assertTrue(open_body["ok"])
            session_id = open_body["session"]["session_id"]

            set_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/writes/set",
                json={
                    "pred_id": "person:country",
                    "e_ref": self.person_ref,
                    "rest_terms": [["string", "de"]],
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
                },
            )
            self.assertEqual(add_resp.status_code, 200)
            self.assertTrue(add_resp.json()["ok"])

            default_rule_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/rules/run",
                json={
                    "rule": {
                        "rule_id": "q_passthrough",
                        "version": "1.0.0",
                        "select": ["e", "v"],
                        "where": [["ruleref", "q_base_rows", "1.0.0", ["$e", "$v"]]],
                        "expose": True,
                    }
                },
            )
            self.assertEqual(default_rule_resp.status_code, 200)
            self.assertTrue(default_rule_resp.json()["ok"])
            self.assertEqual(default_rule_resp.json()["result"]["rows"], [[self.person_ref, "de"]])

            override_rule_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/rules/run",
                json={
                    "override_registry_root": str(registry_root_name),
                    "rule": {
                        "rule_id": "q_passthrough",
                        "version": "1.0.0",
                        "select": ["e", "v"],
                        "where": [["ruleref", "q_base_rows", "1.0.0", ["$e", "$v"]]],
                        "expose": True,
                    }
                },
            )
            self.assertEqual(override_rule_resp.status_code, 200)
            self.assertTrue(override_rule_resp.json()["ok"])
            self.assertEqual(override_rule_resp.json()["result"]["rows"], [[self.person_ref, "Alice"]])

            conflict_resp = self.client.post(
                f"/v1/runtime/sessions/{session_id}/rules/run",
                json={
                    "registry_root": str(registry_root_country),
                    "override_registry_root": str(registry_root_name),
                    "rule": {
                        "rule_id": "q_passthrough",
                        "version": "1.0.0",
                        "select": ["e", "v"],
                        "where": [["ruleref", "q_base_rows", "1.0.0", ["$e", "$v"]]],
                        "expose": True,
                    },
                },
            )
            self.assertEqual(conflict_resp.status_code, 200)
            conflict_body = conflict_resp.json()
            self.assertFalse(conflict_body["ok"])
            self.assertEqual(conflict_body["errors"][0]["path"], "$")

def _build_registry(
    root_dir: Path,
    *,
    schema_ir: dict[str, object],
    apply_request_id: str,
    rule_id: str,
    pred_id: str,
    derivation_id: str | None = None,
) -> SDKRegistry:
    registry = SDKRegistry(root_dir=root_dir)
    registry.apply_schema_classes([Person], apply_request_id=apply_request_id)
    registry.register_rule_spec(
        compile_authoring_rule_v1(
            {
                "rule_id": rule_id,
                "version": "1.0.0",
                "select": ["e", "v"],
                "where": [("pred", pred_id, ["$e", "$v"])],
                "expose": True,
            },
            schema_ir=schema_ir,
        )
    )
    if derivation_id is not None:
        registry.register_derivation_spec(
            {
                "derivation_id": derivation_id,
                "version": "1.0.0",
                "target": "person:country",
                "head_vars": ["$E", "$V"],
                "where": [("pred", pred_id, ["$E", "$V"])],
                "materialize_as": "fact",
                "mode": "python",
                "temporal_view": "record",
            }
        )
    return registry


def _schema_ir_with_mapping(
    base_schema_ir: dict[str, object],
    *,
    tie_break: object | None = None,
) -> dict[str, object]:
    schema_ir = copy.deepcopy(base_schema_ir)
    predicates = schema_ir.setdefault("predicates", [])
    assert isinstance(predicates, list)
    predicates.append(
        {
            "pred_id": "er:canon_of",
            "arg_specs": [
                {"name": "mention", "type_domain": "entity_ref"},
                {"name": "canonical", "type_domain": "entity_ref"},
            ],
            "group_key_indexes": [0],
            "cardinality": "functional",
            "is_mapping": True,
            "mapping_kind": "single_valued",
            "mapping_key_positions": [0],
            "mapping_value_positions": [1],
            **({"tie_break": tie_break} if tie_break is not None else {}),
        }
    )
    projection = schema_ir.setdefault("projection", {})
    assert isinstance(projection, dict)
    projection_predicates = projection.setdefault("predicates", [])
    assert isinstance(projection_predicates, list)
    if "er:canon_of" not in projection_predicates:
        projection_predicates.append("er:canon_of")
    return schema_ir


if __name__ == "__main__":
    unittest.main()
