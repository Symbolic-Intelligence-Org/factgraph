from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringWorkflowError,
    build_authoring_publish_workflow_dry_run_bundle_dto,
    build_authoring_session_dto,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.api import Store


class AuthoringWorkflowV1Tests(unittest.TestCase):
    def test_build_workflow_bundle_all_ok(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:wf-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        session = build_authoring_session_dto(
            store=store,
            schema_ir=_schema(),
            derivation_request={
                "derivation_id": "drv.country",
                "version": "v1",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "python",
            },
        )
        bundle = build_authoring_publish_workflow_dry_run_bundle_dto(session)
        self.assertEqual(
            bundle["authoring_publish_workflow_bundle_dto_version"],
            "authoring_publish_workflow_bundle_dto_v1",
        )
        self.assertEqual(bundle["kind"], "authoring_publish_workflow_bundle")
        self.assertEqual(bundle["mode"], "dry_run_only")
        self.assertTrue(bundle["ok"])
        self.assertEqual(bundle["status"], "ok")
        self.assertEqual(bundle["session"]["kind"], "authoring_session")
        self.assertEqual(bundle["publish_plan"]["kind"], "authoring_publish_plan")
        self.assertEqual(bundle["apply_result"]["kind"], "authoring_apply_result")
        self.assertEqual(bundle["summary"]["session_status"], "ok")
        self.assertEqual(bundle["summary"]["publish_plan_status"], "ok")
        self.assertEqual(bundle["summary"]["apply_result_status"], "ok")
        self.assertEqual(bundle["summary"]["publish_action_count"], bundle["publish_plan"]["summary"]["action_count"])

    def test_build_workflow_bundle_preserves_warning_error_path(self) -> None:
        session = {
            "authoring_session_dto_version": "authoring_session_dto_v1",
            "kind": "authoring_session",
            "ok": False,
            "status": "error",
            "order": ["custom_section", "rule_preflight"],
            "diagnostics_contract": {"diagnostics_contract_version": "authoring_diagnostics_contract_v1"},
            "sections": {
                "custom_section": {"ok": True, "status": "ok", "diagnostics": [], "warnings": []},
                "rule_preflight": {"ok": False, "status": "error", "diagnostics": [], "warnings": []},
            },
            "summary": {"section_count": 2},
        }
        bundle = build_authoring_publish_workflow_dry_run_bundle_dto(session)
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["status"], "error")
        self.assertEqual(bundle["summary"]["publish_plan_status"], "error")
        self.assertEqual(bundle["summary"]["apply_result_status"], "error")
        self.assertEqual(bundle["publish_plan"]["summary"]["blocked_count"], 1)
        self.assertEqual(bundle["apply_result"]["summary"]["blocked_count"], 1)
        self.assertEqual(bundle["apply_result"]["summary"]["skipped_count"], 1)

    def test_reject_invalid_session_payload(self) -> None:
        with self.assertRaises(AuthoringWorkflowError):
            build_authoring_publish_workflow_dry_run_bundle_dto({"authoring_session_dto_version": "x"})

    def test_fixtures_doc_workflow_bundle_example_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            text,
            "### F5-F publish workflow bundle DTO（dry-run only，session → plan → apply 聚合）",
        )
        self.assertEqual(
            snippet["authoring_publish_workflow_bundle_dto_version"],
            "authoring_publish_workflow_bundle_dto_v1",
        )
        self.assertEqual(snippet["kind"], "authoring_publish_workflow_bundle")
        self.assertEqual(snippet["mode"], "dry_run_only")
        self.assertIn("session_status", snippet["summary"])
        self.assertIn("publish_plan_status", snippet["summary"])
        self.assertIn("apply_result_status", snippet["summary"])

    def test_contract_doc_workflow_bundle_canonical_snippet(self) -> None:
        contract_doc = _docs_root() / "Authoring 层契约.md"
        text = contract_doc.read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            text,
            "Canonical `authoring_publish_workflow_bundle_dto_v1` 片段（dry-run only，session→plan→apply 聚合，v1，已实装）：",
        )
        self.assertEqual(
            snippet,
            {
                "authoring_publish_workflow_bundle_dto_version": "authoring_publish_workflow_bundle_dto_v1",
                "kind": "authoring_publish_workflow_bundle",
                "mode": "dry_run_only",
                "status": "warning",
                "summary": {
                    "session_status": "warning",
                    "publish_plan_status": "warning",
                    "apply_result_status": "warning",
                },
            },
        )

    def _extract_json_code_block_after_header(self, text: str, header: str) -> dict:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        tail = text[idx:]
        match = re.search(r"```json\s*\n(.*?)\n```", tail, flags=re.S)
        self.assertIsNotNone(match, f"missing json code block after: {header}")
        return json.loads(match.group(1))


def _schema() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [{"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]}],
        "predicates": [
            {
                "pred_id": "person:country",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "functional",
            }
        ],
        "projection": {"entities": [], "predicates": ["person:country"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs"


if __name__ == "__main__":
    unittest.main()
