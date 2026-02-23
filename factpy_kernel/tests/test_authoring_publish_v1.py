from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringPublishError,
    build_authoring_apply_dry_run_result_dto,
    build_authoring_publish_plan_dto,
    build_authoring_session_dto,
)
from factpy_kernel.authoring.diagnostic_codes import (
    CODE_APPLY_BLOCKED_ACTION,
    AUTHORING_DIAGNOSTIC_CODES_V1,
    AUTHORING_DIAGNOSTIC_PHASES_V1,
    CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
    CODE_APPLY_SKIPPED_ACTION,
    CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
    CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION,
    CODE_PUBLISH_BLOCKED_SECTION_ERROR,
    CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION,
    PHASE_PUBLISH_APPLY,
    PHASE_PUBLISH_PLAN,
)
from factpy_kernel.evidence.write_protocol import set_field
from factpy_kernel.store.api import Store


class AuthoringPublishV1Tests(unittest.TestCase):
    def test_build_publish_plan_all_ok(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:pub-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        session = build_authoring_session_dto(
            store=store,
            schema_ir=_schema(),
            rule_request={
                "rule_spec_payload": {
                    "rule_id": "rules.country_rows",
                    "version": "v1",
                    "select_vars": ["$E", "$C"],
                    "where": [("pred", "person:country", ["$E", "$C"])],
                }
            },
            derivation_request={
                "derivation_id": "drv.country",
                "version": "v1",
                "target_pred_id": "person:country",
                "head_vars": ["$E", "$C"],
                "where": [("pred", "person:country", ["$E", "$C"])],
                "mode": "python",
            },
        )
        plan = build_authoring_publish_plan_dto(session)
        self.assertEqual(plan["authoring_publish_plan_dto_version"], "authoring_publish_plan_dto_v1")
        self.assertEqual(plan["kind"], "authoring_publish_plan")
        self.assertEqual(plan["mode"], "dry_run_only")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["diagnostics_contract"]["codes"], list(AUTHORING_DIAGNOSTIC_CODES_V1))
        self.assertEqual(plan["diagnostics_contract"]["phases"], list(AUTHORING_DIAGNOSTIC_PHASES_V1))
        self.assertEqual(plan["source"]["session_status"], "ok")
        self.assertEqual([a["section"] for a in plan["actions"]], ["schema_preflight", "rule_preflight", "derivation_preview"])
        self.assertTrue(all(a["status"] == "planned" for a in plan["actions"]))
        self.assertEqual(plan["actions"][0]["action"], "upsert_schema_ir")
        self.assertTrue(str(plan["actions"][0]["payload_summary"]["schema_digest"]).startswith("sha256:"))
        self.assertEqual(plan["actions"][1]["payload_summary"]["rule_id"], "rules.country_rows")
        self.assertEqual(plan["actions"][2]["payload_summary"]["candidate_count"], 1)
        self.assertEqual(plan["summary"]["planned_count"], 3)
        self.assertEqual(plan["summary"]["blocked_count"], 0)
        self.assertEqual(plan["diagnostics"], [])
        self.assertEqual(plan["warnings"], [])
        self.assertEqual(plan["summary"]["diagnostic_count"], 0)
        self.assertEqual(plan["summary"]["warning_count"], 0)

    def test_build_publish_plan_warning_is_non_blocking(self) -> None:
        schema = _schema()
        schema["predicates"] = []
        schema["projection"] = {"entities": [], "predicates": []}
        session = build_authoring_session_dto(schema_ir=schema)
        self.assertEqual(session["status"], "warning")

        plan = build_authoring_publish_plan_dto(session)
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["status"], "warning")
        self.assertEqual(plan["summary"]["planned_count"], 1)
        self.assertEqual(plan["summary"]["blocked_count"], 0)
        self.assertEqual(plan["actions"][0]["section"], "schema_preflight")
        self.assertEqual(plan["actions"][0]["status"], "planned")
        self.assertGreaterEqual(plan["actions"][0]["counts"]["warning_count"], 1)
        self.assertEqual(plan["diagnostics"], [])
        self.assertEqual(plan["warnings"], [])

    def test_build_apply_dry_run_result_all_ok(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:pub-2",
            rest_terms=[("string", "fr")],
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
        plan = build_authoring_publish_plan_dto(session)
        result = build_authoring_apply_dry_run_result_dto(plan)
        self.assertEqual(result["authoring_apply_result_dto_version"], "authoring_apply_result_dto_v1")
        self.assertEqual(result["kind"], "authoring_apply_result")
        self.assertEqual(result["mode"], "dry_run_only")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["would_apply_count"], result["summary"]["action_count"])
        self.assertEqual(result["summary"]["blocked_count"], 0)
        self.assertEqual(result["summary"]["skipped_count"], 0)
        self.assertTrue(all(a["status"] == "would_apply" for a in result["actions"]))
        self.assertEqual(result["diagnostics_contract"]["codes"], list(AUTHORING_DIAGNOSTIC_CODES_V1))
        self.assertEqual(result["diagnostics_contract"]["phases"], list(AUTHORING_DIAGNOSTIC_PHASES_V1))
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(result["warnings"], [])
        self.assertTrue(all(a["diagnostics"] == [] for a in result["actions"]))
        self.assertTrue(all(a["warnings"] == [] for a in result["actions"]))

    def test_build_apply_dry_run_result_preserves_blocked_and_warning(self) -> None:
        session = {
            "authoring_session_dto_version": "authoring_session_dto_v1",
            "kind": "authoring_session",
            "ok": False,
            "status": "error",
            "order": ["custom_section", "rule_preflight"],
            "sections": {
                "custom_section": {"ok": True, "status": "ok", "diagnostics": [], "warnings": []},
                "rule_preflight": {"ok": False, "status": "error", "diagnostics": [], "warnings": []},
            },
        }
        plan = build_authoring_publish_plan_dto(session)
        result = build_authoring_apply_dry_run_result_dto(plan)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["summary"]["would_apply_count"], 0)
        self.assertEqual(result["summary"]["blocked_count"], 1)
        self.assertEqual(result["summary"]["skipped_count"], 1)
        self.assertEqual(result["summary"]["diagnostic_count"], 2)
        self.assertEqual(result["summary"]["warning_count"], 2)
        self.assertEqual(result["actions"][0]["status"], "skipped")
        self.assertEqual(result["actions"][0]["reason_code"], CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION)
        self.assertEqual(result["actions"][1]["status"], "blocked")
        self.assertEqual(result["actions"][1]["reason_code"], CODE_PUBLISH_BLOCKED_SECTION_ERROR)
        self.assertIn(CODE_APPLY_SKIPPED_ACTION, {w["code"] for w in result["actions"][0]["warnings"]})
        self.assertIn(CODE_APPLY_BLOCKED_ACTION, {d["code"] for d in result["actions"][1]["diagnostics"]})
        self.assertEqual({w["phase"] for w in result["actions"][0]["warnings"]}, {PHASE_PUBLISH_PLAN, PHASE_PUBLISH_APPLY})
        self.assertEqual({d["phase"] for d in result["actions"][1]["diagnostics"]}, {PHASE_PUBLISH_PLAN, PHASE_PUBLISH_APPLY})
        self.assertEqual({d["phase"] for d in result["diagnostics"]}, {PHASE_PUBLISH_PLAN, PHASE_PUBLISH_APPLY})
        self.assertEqual({w["phase"] for w in result["warnings"]}, {PHASE_PUBLISH_PLAN, PHASE_PUBLISH_APPLY})
        self.assertIn(CODE_APPLY_BLOCKED_ACTIONS_PRESENT, {d["code"] for d in result["diagnostics"]})
        self.assertIn(CODE_APPLY_SKIPPED_ACTIONS_PRESENT, {w["code"] for w in result["warnings"]})

    def test_build_publish_plan_blocks_error_sections(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(
            store=store,
            rule_request={
                "rule_spec_payload": {
                    "rule_id": "rules.bad",
                    "version": "v1",
                    "select_vars": ["$E"],
                    "where": [("pred", "missing:pred", ["$E"])],
                }
            },
        )
        self.assertEqual(session["status"], "error")

        plan = build_authoring_publish_plan_dto(session)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["status"], "error")
        self.assertEqual(plan["summary"]["action_count"], 1)
        self.assertEqual(plan["summary"]["blocked_count"], 1)
        self.assertEqual(plan["actions"][0]["status"], "blocked")
        self.assertEqual(plan["actions"][0]["reason_code"], CODE_PUBLISH_BLOCKED_SECTION_ERROR)
        self.assertEqual(plan["actions"][0]["reason"], "section_error")
        self.assertEqual(plan["actions"][0]["action"], "register_rule_spec")
        self.assertEqual(plan["summary"]["diagnostic_count"], 1)
        self.assertEqual(plan["summary"]["warning_count"], 0)
        self.assertEqual(plan["diagnostics"][0]["code"], CODE_PUBLISH_BLOCKED_SECTION_ERROR)
        self.assertEqual(plan["diagnostics"][0]["phase"], PHASE_PUBLISH_PLAN)
        self.assertEqual(plan["diagnostics"][0]["path"], "$.sections.rule_preflight")
        self.assertEqual(plan["warnings"], [])

    def test_publish_plan_skips_unsupported_section_with_warning(self) -> None:
        session = {
            "authoring_session_dto_version": "authoring_session_dto_v1",
            "kind": "authoring_session",
            "ok": True,
            "status": "ok",
            "order": ["custom_section"],
            "sections": {"custom_section": {"ok": True, "status": "ok", "diagnostics": [], "warnings": []}},
        }
        plan = build_authoring_publish_plan_dto(session)
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["status"], "warning")
        self.assertEqual(plan["actions"][0]["status"], "skipped")
        self.assertEqual(plan["actions"][0]["reason_code"], CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION)
        self.assertEqual(plan["summary"]["skipped_count"], 1)
        self.assertEqual(plan["summary"]["warning_count"], 1)
        self.assertEqual(plan["warnings"][0]["code"], CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION)
        self.assertEqual(plan["warnings"][0]["phase"], PHASE_PUBLISH_PLAN)

    def test_publish_plan_blocks_missing_section_with_structured_reason(self) -> None:
        session = {
            "authoring_session_dto_version": "authoring_session_dto_v1",
            "kind": "authoring_session",
            "ok": False,
            "status": "error",
            "order": ["rule_preflight"],
            "sections": {},
        }
        plan = build_authoring_publish_plan_dto(session)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["status"], "error")
        self.assertEqual(plan["actions"][0]["status"], "blocked")
        self.assertEqual(plan["actions"][0]["reason_code"], CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION)
        self.assertEqual(plan["diagnostics"][0]["code"], CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION)
        self.assertEqual(plan["diagnostics"][0]["phase"], PHASE_PUBLISH_PLAN)

    def test_reject_invalid_session_payload(self) -> None:
        with self.assertRaises(AuthoringPublishError):
            build_authoring_publish_plan_dto({"authoring_session_dto_version": "x"})

    def test_reject_invalid_publish_plan_payload_for_apply(self) -> None:
        with self.assertRaises(AuthoringPublishError):
            build_authoring_apply_dry_run_result_dto({"authoring_publish_plan_dto_version": "x"})

    def test_contract_doc_canonical_publish_plan_snippet(self) -> None:
        contract_doc = _docs_root() / "Authoring 层契约.md"
        text = contract_doc.read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            text,
            "Canonical `authoring_publish_plan_dto_v1` 片段（dry-run only，最小必备字段，v1，已实装）：",
        )
        self.assertEqual(
            snippet,
            {
                "authoring_publish_plan_dto_version": "authoring_publish_plan_dto_v1",
                "kind": "authoring_publish_plan",
                "mode": "dry_run_only",
                "status": "warning",
                "summary": {
                    "action_count": 1,
                    "planned_count": 1,
                    "blocked_count": 0,
                    "skipped_count": 0,
                },
            },
        )

    def test_contract_doc_canonical_apply_result_snippet(self) -> None:
        contract_doc = _docs_root() / "Authoring 层契约.md"
        text = contract_doc.read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            text,
            "Canonical `authoring_apply_result_dto_v1` 片段（dry-run only，最小必备字段，v1，已实装）：",
        )
        self.assertEqual(
            snippet,
            {
                "authoring_apply_result_dto_version": "authoring_apply_result_dto_v1",
                "kind": "authoring_apply_result",
                "mode": "dry_run_only",
                "status": "warning",
                "summary": {
                    "action_count": 1,
                    "would_apply_count": 1,
                    "blocked_count": 0,
                    "skipped_count": 0,
                },
            },
        )

    def test_fixtures_doc_publish_and_apply_examples_have_expected_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        publish_example = self._extract_json_code_block_after_header(
            text,
            "### F5-D publish plan DTO（dry-run only，基于 session DTO）",
        )
        apply_example = self._extract_json_code_block_after_header(
            text,
            "### F5-E apply result DTO（dry-run only，基于 publish plan DTO）",
        )
        self.assertEqual(publish_example["authoring_publish_plan_dto_version"], "authoring_publish_plan_dto_v1")
        self.assertEqual(publish_example["kind"], "authoring_publish_plan")
        self.assertEqual(publish_example["mode"], "dry_run_only")
        self.assertIn("action_count", publish_example["summary"])
        self.assertIn("planned_count", publish_example["summary"])
        self.assertIn("blocked_count", publish_example["summary"])

        self.assertEqual(apply_example["authoring_apply_result_dto_version"], "authoring_apply_result_dto_v1")
        self.assertEqual(apply_example["kind"], "authoring_apply_result")
        self.assertEqual(apply_example["mode"], "dry_run_only")
        self.assertIn("action_count", apply_example["summary"])
        self.assertIn("would_apply_count", apply_example["summary"])
        self.assertIn("blocked_count", apply_example["summary"])
        self.assertIn("skipped_count", apply_example["summary"])

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
    return Path(__file__).resolve().parents[2] / "docs"


if __name__ == "__main__":
    unittest.main()
