from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringRegistryFSError,
    FileAuthoringRegistry,
    build_authoring_apply_execute_result_dto,
    build_authoring_publish_plan_dto,
    build_authoring_publish_workflow_apply_bundle_dto,
    build_authoring_session_dto,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.store.api import Store


class AuthoringApplyExecuteV1Tests(unittest.TestCase):
    def test_apply_execute_result_writes_registry_for_planned_actions(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:ae-1",
            rest_terms=[("string", "de")],
            meta={"source": "seed"},
        )
        session = build_authoring_session_dto(
            store=store,
            schema_ir=_schema(),
            rule_request={"rule_spec_payload": _rule_spec()},
            derivation_request=_derivation_request(),
        )
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            result = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={
                    "schema_preflight": _schema(),
                    "rule_preflight": _rule_spec(),
                    "derivation_preview": _derivation_request(),
                },
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "ok")
            self.assertTrue(result["idempotency"]["plan_digest"].startswith("sha256:"))
            self.assertEqual(result["transaction"]["policy"], "best_effort_no_rollback_v1")
            self.assertFalse(result["transaction"]["rollback_supported"])
            self.assertTrue(result["transaction"]["prevalidate_before_write"])
            self.assertFalse(result["transaction"]["partial_apply"])
            self.assertEqual(result["summary"]["applied_count"], 3)
            self.assertEqual(result["summary"]["noop_count"], 0)
            self.assertEqual({a["status"] for a in result["actions"]}, {"applied"})
            self.assertTrue((Path(tmpdir) / "registry_manifest.json").exists())
            manifest = json.loads((Path(tmpdir) / "registry_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["rules"]), 1)
            self.assertEqual(len(manifest["derivations"]), 1)
            apply_lines = (Path(tmpdir) / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(apply_lines), 4)
            parsed_events = [json.loads(line) for line in apply_lines]
            self.assertEqual(parsed_events[-1]["kind"], "authoring_apply_execute_run")
            self.assertTrue(all(row["kind"] == "authoring_apply_execute_action" for row in parsed_events[:-1]))
            self.assertEqual(parsed_events[-1]["idempotency"]["apply_request_id"], parsed_events[-1]["apply_request_id"])
            self.assertTrue(parsed_events[-1]["transaction"]["prevalidate_before_write"])

    def test_apply_execute_reapply_same_plan_becomes_noop(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, schema_ir=_schema())
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            first = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
            )
            second = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
            )
            self.assertEqual(first["summary"]["applied_count"], 1)
            self.assertEqual(second["summary"]["noop_count"], 1)
            self.assertEqual(second["actions"][0]["status"], "noop")
            self.assertEqual(second["status"], "ok")

    def test_apply_execute_same_request_id_replays_without_reexecution(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, schema_ir=_schema())
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            first = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-1",
            )
            second = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-1",
            )
            self.assertFalse(first["idempotency"]["replayed"])
            self.assertTrue(first["idempotency"]["plan_digest"].startswith("sha256:"))
            self.assertFalse(first["transaction"]["partial_apply"])
            self.assertTrue(second["idempotency"]["replayed"])
            self.assertEqual(second["transaction"]["policy"], "best_effort_no_rollback_v1")
            self.assertTrue(second["transaction"]["prevalidate_before_write"])
            self.assertEqual(second["actions"], [])
            self.assertEqual(second["summary"]["applied_count"], first["summary"]["applied_count"])
            lines = (Path(tmpdir) / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines()
            parsed = [json.loads(line) for line in lines]
            action_events = [row for row in parsed if row.get("kind") == "authoring_apply_execute_action"]
            run_events = [row for row in parsed if row.get("kind") == "authoring_apply_execute_run"]
            self.assertEqual(len(run_events), 1)
            self.assertEqual(run_events[0]["plan_digest"], first["idempotency"]["plan_digest"])
            self.assertEqual(action_events[0]["apply_request_id"], "req-1")
            self.assertFalse(run_events[0]["idempotency"]["replayed"])

    def test_apply_execute_same_request_id_different_plan_digest_conflicts(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, schema_ir=_schema())
        plan = build_authoring_publish_plan_dto(session)
        changed_plan = json.loads(json.dumps(plan))
        changed_plan["summary"]["action_count"] = 999
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            first = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-conflict",
            )
            second = build_authoring_apply_execute_result_dto(
                changed_plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-conflict",
            )
            self.assertTrue(first["ok"])
            self.assertFalse(second["ok"])
            self.assertEqual(second["status"], "error")
            self.assertTrue(second["idempotency"]["conflict"])
            self.assertTrue(second["transaction"]["prevalidate_before_write"])
            self.assertEqual(second["transaction"]["prevalidate_status"], "skipped_idempotency_conflict")
            self.assertEqual(second["transaction"]["failure_phase"], "idempotency_conflict")
            self.assertFalse(second["transaction"]["writes_started"])
            self.assertFalse(second["transaction"]["partial_apply"])
            self.assertEqual(second["idempotency"]["apply_request_id"], "req-conflict")
            self.assertNotEqual(
                second["idempotency"]["prior_plan_digest"],
                second["idempotency"]["plan_digest"],
            )
            self.assertEqual(second["actions"], [])
            self.assertEqual(second["diagnostics"][0]["path"], "$.idempotency.apply_request_id")

    def test_apply_execute_supports_v2_transaction_policy_minimally(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, schema_ir=_schema())
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            result = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-v2-1",
                transaction_policy="prevalidate_no_partial_strict_v2",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["idempotency"]["apply_request_id"], "req-v2-1")
            self.assertTrue(result["idempotency"]["plan_digest"].startswith("sha256:"))
            self.assertEqual(result["transaction"]["policy"], "prevalidate_no_partial_strict_v2")
            self.assertTrue(result["transaction"]["prevalidate_before_write"])
            self.assertEqual(result["transaction"]["prevalidate_status"], "passed")
            self.assertTrue(result["transaction"]["writes_started"])
            self.assertEqual(result["transaction"]["failure_phase"], "none")
            self.assertFalse(result["transaction"]["partial_apply"])
            self.assertEqual(result["summary"]["applied_count"], 1)
            self.assertEqual(result["actions"][0]["status"], "applied")
            self.assertEqual(result["diagnostics"], [])
            lines = (Path(tmpdir) / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            run_event = json.loads(lines[-1])
            self.assertEqual(run_event["kind"], "authoring_apply_execute_run")
            self.assertEqual(run_event["transaction"]["policy"], "prevalidate_no_partial_strict_v2")

    def test_apply_execute_rejects_unknown_transaction_policy(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, schema_ir=_schema())
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            result = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                transaction_policy="unknown_policy_x",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["transaction"]["policy"], "unknown_policy_x")
            self.assertEqual(
                result["transaction"]["prevalidate_status"],
                "skipped_transaction_policy_unsupported",
            )
            self.assertEqual(
                result["diagnostics"][0]["path"],
                "$.apply_execute_options.transaction_policy",
            )
            self.assertFalse(result["diagnostics"][0]["details"]["v2_reserved_not_implemented"])
            self.assertFalse((Path(tmpdir) / "authoring_apply_events.jsonl").exists())

    def test_apply_execute_same_request_id_same_plan_but_different_transaction_policy_conflicts(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, schema_ir=_schema())
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            first = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-policy-conflict",
                transaction_policy="best_effort_no_rollback_v1",
            )
            second = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema()},
                apply_request_id="req-policy-conflict",
                transaction_policy="prevalidate_no_partial_strict_v2",
            )
            self.assertTrue(first["ok"])
            self.assertFalse(second["ok"])
            self.assertEqual(second["status"], "error")
            self.assertEqual(
                second["diagnostics"][0]["path"],
                "$.apply_execute_options.transaction_policy",
            )
            self.assertIn("different transaction policy", second["diagnostics"][0]["message"])
            details = second["diagnostics"][0]["details"]
            self.assertEqual(details["prior_transaction_policy"], "best_effort_no_rollback_v1")
            self.assertEqual(details["current_transaction_policy"], "prevalidate_no_partial_strict_v2")
            self.assertEqual(second["transaction"]["policy"], "prevalidate_no_partial_strict_v2")
            self.assertEqual(second["transaction"]["failure_phase"], "idempotency_conflict")

    def test_apply_execute_blocks_registry_conflict_with_details(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(store=store, rule_request={"rule_spec_payload": _rule_spec()})
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            self.assertTrue(
                build_authoring_apply_execute_result_dto(
                    plan,
                    registry=registry,
                    section_payloads={"rule_preflight": _rule_spec()},
                )["ok"]
            )
            changed = _rule_spec()
            changed["select_vars"] = ["$E"]
            changed["where"] = [("pred", "person:country", ["$E", "de"])]
            second = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"rule_preflight": changed},
            )
            self.assertFalse(second["ok"])
            self.assertEqual(second["status"], "error")
            self.assertFalse(second["transaction"]["partial_apply"])
            self.assertTrue(second["transaction"]["prevalidate_before_write"])
            self.assertEqual(second["transaction"]["prevalidate_status"], "blocked")
            self.assertEqual(second["transaction"]["failure_phase"], "prevalidate")
            self.assertFalse(second["transaction"]["writes_started"])
            blocked = [a for a in second["actions"] if a["status"] == "blocked"]
            self.assertEqual(len(blocked), 1)
            self.assertEqual(blocked[0]["diagnostics"][-1]["code"], "apply_prevalidate_blocked_action")
            details = blocked[0]["diagnostics"][-1].get("details", {})
            self.assertEqual(details.get("registry_error_code"), "registry_rule_version_conflict")
            self.assertEqual(details.get("prevalidate"), True)
            self.assertEqual(second["diagnostics"][-1]["code"], "apply_prevalidate_blocked_actions_present")

    def test_apply_execute_partial_apply_is_explicit_when_later_action_blocks(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(
            store=store,
            schema_ir=_schema(),
            rule_request={"rule_spec_payload": _rule_spec()},
        )
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            registry.register_rule_spec(_rule_spec())
            changed = _rule_spec()
            changed["select_vars"] = ["$E"]
            changed["where"] = [("pred", "person:country", ["$E", "de"])]
            result = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema(), "rule_preflight": changed},
                apply_request_id="req-partial-1",
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "error")
            self.assertFalse(result["transaction"]["partial_apply"])
            self.assertTrue(result["transaction"]["prevalidate_before_write"])
            self.assertEqual(result["transaction"]["prevalidate_status"], "blocked")
            self.assertEqual(result["transaction"]["failure_phase"], "prevalidate")
            self.assertFalse(result["transaction"]["writes_started"])
            self.assertFalse((Path(tmpdir) / "schema" / "schema_ir.json").exists())
            self.assertEqual(result["summary"]["applied_count"], 0)
            self.assertEqual(result["summary"]["blocked_count"], 1)
            self.assertEqual(result["diagnostics"][-1]["path"], "$.prevalidate")
            apply_log = Path(tmpdir) / "authoring_apply_events.jsonl"
            if apply_log.exists():
                lines = [json.loads(line) for line in apply_log.read_text(encoding="utf-8").splitlines()]
                run_events = [row for row in lines if row.get("kind") == "authoring_apply_execute_run"]
                action_events = [row for row in lines if row.get("kind") == "authoring_apply_execute_action"]
                self.assertEqual(run_events, [])
                self.assertEqual(action_events, [])
            else:
                self.assertFalse(apply_log.exists())

    def test_apply_execute_partial_apply_is_explicit_on_runtime_failure_after_prevalidate(self) -> None:
        store = Store(schema_ir=_schema())
        session = build_authoring_session_dto(
            store=store,
            schema_ir=_schema(),
            rule_request={"rule_spec_payload": _rule_spec()},
        )
        plan = build_authoring_publish_plan_dto(session)
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            original_register_rule_spec = registry.register_rule_spec

            def _boom_register_rule_spec(_payload):
                raise AuthoringRegistryFSError(
                    "simulated runtime write failure",
                    code="registry_rule_write_failed",
                    path="$.rules[rules.country_rows@v1]",
                )

            registry.register_rule_spec = _boom_register_rule_spec  # type: ignore[assignment]
            result = build_authoring_apply_execute_result_dto(
                plan,
                registry=registry,
                section_payloads={"schema_preflight": _schema(), "rule_preflight": _rule_spec()},
                apply_request_id="req-partial-runtime",
            )
            registry.register_rule_spec = original_register_rule_spec  # type: ignore[assignment]
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "error")
            self.assertTrue(result["transaction"]["partial_apply"])
            self.assertTrue(result["transaction"]["prevalidate_before_write"])
            self.assertEqual(result["transaction"]["prevalidate_status"], "passed")
            self.assertEqual(result["transaction"]["failure_phase"], "write")
            self.assertTrue(result["transaction"]["writes_started"])
            self.assertEqual(result["summary"]["applied_count"], 1)
            self.assertEqual(result["summary"]["blocked_count"], 1)
            lines = [json.loads(line) for line in (Path(tmpdir) / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines()]
            action_events = [row for row in lines if row.get("kind") == "authoring_apply_execute_action"]
            run_event = [row for row in lines if row.get("kind") == "authoring_apply_execute_run"][-1]
            self.assertEqual(len(action_events), 2)
            self.assertEqual(action_events[-1]["status"], "blocked")
            self.assertEqual(action_events[-1]["apply_request_id"], "req-partial-runtime")
            self.assertEqual(action_events[-1]["reason_code"], "apply_blocked_action")
            self.assertEqual(action_events[-1]["diagnostics"][0]["code"], "apply_blocked_action")
            self.assertEqual(action_events[-1]["diagnostics_summary"]["count"], 1)
            self.assertEqual(action_events[-1]["diagnostics_summary"]["codes"], ["apply_blocked_action"])
            self.assertEqual(lines[-1]["kind"], "authoring_apply_execute_run")
            self.assertTrue(run_event["partial_apply"])

    def test_workflow_apply_bundle_executes_and_persists(self) -> None:
        store = Store(schema_ir=_schema())
        set_field(
            store.ledger,
            pred_id="person:country",
            e_ref="idref_v1:Person:ae-2",
            rest_terms=[("string", "fr")],
            meta={"source": "seed"},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            bundle = build_authoring_publish_workflow_apply_bundle_dto(
                registry=registry,
                store=store,
                schema_ir=_schema(),
                derivation_request=_derivation_request(),
                apply_request_id="bundle-1",
            )
            self.assertEqual(
                bundle["authoring_publish_workflow_apply_bundle_dto_version"],
                "authoring_publish_workflow_apply_bundle_dto_v1",
            )
            self.assertEqual(bundle["kind"], "authoring_publish_workflow_apply_bundle")
            self.assertEqual(bundle["mode"], "apply_execute_v1")
            self.assertTrue(bundle["ok"])
            self.assertFalse(bundle["summary"]["apply_execute_partial_apply"])
            self.assertEqual(bundle["apply_execute"]["kind"], "authoring_apply_execute_result")
            self.assertGreaterEqual(bundle["apply_execute"]["summary"]["applied_count"], 2)
            self.assertEqual(bundle["apply_execute"]["idempotency"]["apply_request_id"], "bundle-1")
            self.assertTrue((Path(tmpdir) / "schema" / "schema_ir.json").exists())

    def test_workflow_apply_bundle_blocks_and_does_not_write_invalid_rule(self) -> None:
        store = Store(schema_ir=_schema())
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            bundle = build_authoring_publish_workflow_apply_bundle_dto(
                registry=registry,
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
            self.assertFalse(bundle["ok"])
            self.assertEqual(bundle["status"], "error")
            self.assertEqual(bundle["apply_execute"]["status"], "error")
            self.assertEqual(bundle["apply_execute"]["summary"]["applied_count"], 0)
            self.assertFalse((Path(tmpdir) / "registry_manifest.json").exists())

    def test_contract_doc_canonical_apply_execute_snippet(self) -> None:
        contract_doc = _docs_root() / "Authoring 层契约.md"
        text = contract_doc.read_text(encoding="utf-8")
        self.assertIn("prevalidate_no_partial_strict_v2", text)
        self.assertIn("v2 为显式 opt-in", text)
        self.assertIn("不得 silent 升级替换 v1", text)
        self.assertIn("apply_v2_prevalidate_blocked_actions_present", text)
        self.assertIn("apply_execute_options.transaction_policy", text)
        self.assertIn("apply_request_id`/`plan_digest` 幂等与 replay/conflict 判定规则保持不变", text)
        self.assertIn("不得把上述预留 codes 加入 canonical `code` 列表", text)
        self.assertIn('phase="publish.apply"', text)
        snippet = self._extract_json_code_block_after_header(
            text,
            "Canonical `authoring_apply_execute_result_dto_v1` 片段（apply execute，最小必备字段，v1，已实装）：",
        )
        self.assertEqual(
            snippet,
            {
                "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
                "kind": "authoring_apply_execute_result",
                "mode": "apply_execute_v1",
                "status": "warning",
                "idempotency": {
                    "apply_request_id": "req-123",
                    "plan_digest": "sha256:" + ("0" * 64),
                    "replayed": False,
                },
                "transaction": {
                    "policy": "best_effort_no_rollback_v1",
                    "rollback_supported": False,
                    "rollback_attempted": False,
                    "prevalidate_before_write": True,
                    "prevalidate_status": "passed",
                    "writes_started": True,
                    "failure_phase": "none",
                    "partial_apply": False,
                },
                "summary": {
                    "action_count": 2,
                    "applied_count": 1,
                    "noop_count": 1,
                    "blocked_count": 0,
                    "skipped_count": 0,
                },
            },
        )

    def test_contract_doc_canonical_workflow_apply_bundle_snippet(self) -> None:
        contract_doc = _docs_root() / "Authoring 层契约.md"
        text = contract_doc.read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            text,
            "Canonical `authoring_publish_workflow_apply_bundle_dto_v1` 片段（session→plan→apply dry-run→apply execute 聚合，v1，已实装）：",
        )
        self.assertEqual(
            snippet,
            {
                "authoring_publish_workflow_apply_bundle_dto_version": "authoring_publish_workflow_apply_bundle_dto_v1",
                "kind": "authoring_publish_workflow_apply_bundle",
                "mode": "apply_execute_v1",
                "status": "warning",
                "summary": {
                    "session_status": "warning",
                    "publish_plan_status": "warning",
                    "apply_dry_run_status": "warning",
                    "apply_execute_status": "warning",
                    "apply_execute_partial_apply": False,
                },
            },
        )

    def test_fixtures_doc_apply_execute_and_registry_examples_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        apply_execute_example = self._extract_json_code_block_after_header(
            text,
            "### F5-K apply execute result DTO（真实执行最小版，registry fs backend）",
        )
        workflow_apply_example = self._extract_json_code_block_after_header(
            text,
            "### F5-L publish workflow apply bundle DTO（session → plan → apply dry-run → apply execute）",
        )
        manifest_example = self._extract_json_code_block_after_header(
            text,
            "`registry_manifest.json` 最小示例：",
        )
        blocked_action_event_example = self._extract_json_code_block_after_header(
            text,
            "`authoring_apply_events.jsonl` 中 runtime blocked action event 最小片段（v1，已实装）：",
        )
        v2_reserved_example = self._extract_json_code_block_after_header(
            text,
            "事务语义 v2（spec-only，未实装）预留片段（用于 docs 对齐校验；非 canonical runtime 输出）：",
        )
        self.assertEqual(
            apply_execute_example["authoring_apply_execute_result_dto_version"],
            "authoring_apply_execute_result_dto_v1",
        )
        self.assertEqual(apply_execute_example["mode"], "apply_execute_v1")
        self.assertEqual(apply_execute_example["registry"]["backend"], "file_registry_fs_v1")
        self.assertIn("idempotency", apply_execute_example)
        self.assertIn("transaction", apply_execute_example)
        self.assertRegex(apply_execute_example["idempotency"]["plan_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(apply_execute_example["transaction"]["policy"], "best_effort_no_rollback_v1")
        self.assertEqual(apply_execute_example["transaction"]["prevalidate_before_write"], True)
        self.assertEqual(apply_execute_example["transaction"]["rollback_attempted"], False)
        self.assertEqual(apply_execute_example["transaction"]["prevalidate_status"], "passed")
        self.assertEqual(apply_execute_example["transaction"]["writes_started"], True)
        self.assertEqual(apply_execute_example["transaction"]["failure_phase"], "none")

        self.assertEqual(
            workflow_apply_example["authoring_publish_workflow_apply_bundle_dto_version"],
            "authoring_publish_workflow_apply_bundle_dto_v1",
        )
        self.assertEqual(workflow_apply_example["mode"], "apply_execute_v1")
        self.assertIn("apply_execute_status", workflow_apply_example["summary"])
        self.assertIn("apply_execute_partial_apply", workflow_apply_example["summary"])

        self.assertEqual(manifest_example["authoring_registry_fs_version"], "authoring_registry_fs_v1")
        self.assertIn("rules", manifest_example)
        self.assertIn("derivations", manifest_example)
        self.assertIn('"kind":"authoring_apply_execute_run"', text)
        self.assertEqual(blocked_action_event_example["kind"], "authoring_apply_execute_action")
        self.assertEqual(blocked_action_event_example["status"], "blocked")
        self.assertEqual(blocked_action_event_example["reason_code"], "apply_blocked_action")
        self.assertEqual(blocked_action_event_example["diagnostics_summary"]["count"], 1)
        self.assertEqual(
            blocked_action_event_example["diagnostics_summary"]["codes"],
            ["apply_blocked_action"],
        )
        self.assertEqual(v2_reserved_example["kind"], "authoring_apply_transaction_policy_v2_reserved")
        self.assertEqual(v2_reserved_example["transaction_policy"], "prevalidate_no_partial_strict_v2")
        self.assertEqual(v2_reserved_example["spec_status"], "reserved_not_implemented")
        self.assertEqual(v2_reserved_example["phase"], "publish.apply")
        self.assertEqual(v2_reserved_example["opt_in_required"], True)
        self.assertEqual(v2_reserved_example["silent_upgrade_from_v1_forbidden"], True)
        self.assertEqual(
            v2_reserved_example["reserved_diagnostics_codes"],
            [
                "apply_v2_prevalidate_blocked_actions_present",
                "apply_v2_partial_apply_forbidden",
                "apply_v2_transaction_policy_unsupported",
            ],
        )
        self.assertEqual(v2_reserved_example["compatibility"]["idempotency_replay_same_as_v1"], True)
        self.assertEqual(v2_reserved_example["compatibility"]["prevalidate_failure_phase"], "prevalidate")
        self.assertEqual(v2_reserved_example["compatibility"]["writes_started_when_prevalidate_blocked"], False)
        self.assertEqual(v2_reserved_example["compatibility"]["partial_apply_forbidden"], True)

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


def _rule_spec() -> dict:
    return {
        "rule_id": "rules.country_rows",
        "version": "v1",
        "select_vars": ["$E", "$C"],
        "where": [("pred", "person:country", ["$E", "$C"])],
        "expose": True,
    }


def _derivation_request() -> dict:
    return {
        "derivation_id": "drv.country",
        "version": "v1",
        "target_pred_id": "person:country",
        "head_vars": ["$E", "$C"],
        "where": [("pred", "person:country", ["$E", "$C"])],
        "mode": "python",
        "temporal_view": "record",
    }


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "blueprint"


if __name__ == "__main__":
    unittest.main()
