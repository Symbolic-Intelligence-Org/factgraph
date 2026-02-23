from __future__ import annotations

import io
import json
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from factpy_kernel.audit.static_ui import render_audit_static_site
from factpy_kernel.authoring import AuthoringRegistryFSError, FileAuthoringRegistry
from factpy_kernel.authoring.cli import main
from factpy_kernel.authoring.schema_compile import compile_authoring_schema_v1
from factpy_kernel.export.package import ExportOptions, export_package
from factpy_kernel.store.api import Store


class AuthoringCLIV1Tests(unittest.TestCase):
    def test_preflight_command_outputs_session_dto(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "authoring_schema.json"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            code, out, err = _run_cli(["preflight", "--authoring-schema", str(schema_path)])
        self.assertEqual(code, 0, msg=err)
        payload = json.loads(out)
        self.assertEqual(payload["authoring_session_dto_version"], "authoring_session_dto_v1")
        self.assertIn("schema_preflight", payload["sections"])

    def test_workflow_dry_run_command_outputs_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "authoring_schema.json"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            code, out, err = _run_cli(["workflow-dry-run", "--authoring-schema", str(schema_path)])
        self.assertEqual(code, 0, msg=err)
        payload = json.loads(out)
        self.assertEqual(
            payload["authoring_publish_workflow_bundle_dto_version"],
            "authoring_publish_workflow_bundle_dto_v1",
        )
        self.assertEqual(payload["kind"], "authoring_publish_workflow_bundle")

    def test_apply_execute_command_writes_registry_and_returns_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "authoring_schema.json"
            registry_dir = Path(tmpdir) / "registry"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--apply-request-id",
                    "cli-req-1",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(
                payload["authoring_publish_workflow_apply_bundle_dto_version"],
                "authoring_publish_workflow_apply_bundle_dto_v1",
            )
            self.assertEqual(payload["apply_execute"]["idempotency"]["apply_request_id"], "cli-req-1")
            self.assertTrue(payload["apply_execute"]["transaction"]["prevalidate_before_write"])
            self.assertTrue((registry_dir / "registry_manifest.json").exists())
            self.assertTrue((registry_dir / "authoring_apply_events.jsonl").exists())

    def test_apply_execute_command_accepts_explicit_v1_transaction_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "authoring_schema.json"
            registry_dir = Path(tmpdir) / "registry"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--transaction-policy",
                    "best_effort_no_rollback_v1",
                ]
            )
        self.assertEqual(code, 0, msg=err)
        payload = json.loads(out)
        self.assertEqual(payload["apply_execute"]["transaction"]["policy"], "best_effort_no_rollback_v1")

    def test_apply_execute_command_supports_v2_transaction_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "authoring_schema.json"
            registry_dir = Path(tmpdir) / "registry"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--transaction-policy",
                    "prevalidate_no_partial_strict_v2",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["apply_execute"]["status"], "ok")
            self.assertEqual(payload["apply_execute"]["transaction"]["policy"], "prevalidate_no_partial_strict_v2")
            self.assertEqual(payload["apply_execute"]["transaction"]["prevalidate_status"], "passed")
            self.assertTrue((registry_dir / "registry_manifest.json").exists())
            self.assertTrue((registry_dir / "authoring_apply_events.jsonl").exists())

    def test_apply_execute_command_rejects_unknown_transaction_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "authoring_schema.json"
            registry_dir = Path(tmpdir) / "registry"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--transaction-policy",
                    "unknown_policy_x",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["apply_execute"]["status"], "error")
            self.assertEqual(payload["apply_execute"]["transaction"]["policy"], "unknown_policy_x")
            self.assertEqual(
                payload["apply_execute"]["transaction"]["prevalidate_status"],
                "skipped_transaction_policy_unsupported",
            )
            self.assertFalse((registry_dir / "registry_manifest.json").exists())
            self.assertFalse((registry_dir / "authoring_apply_events.jsonl").exists())

    def test_registry_list_and_show_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            registry_dir = tmp_root / "registry"
            registry = FileAuthoringRegistry(registry_dir)
            registry.upsert_schema_ir(compile_authoring_schema_v1(_authoring_schema()))
            registry.register_rule_spec(_rule_spec())
            registry.register_derivation_spec(_derivation_request())
            registry.append_apply_event(
                {
                    "kind": "authoring_apply_execute_run",
                    "apply_request_id": "cli-registry-1",
                    "status": "ok",
                    "ok": True,
                }
            )

            code, out, err = _run_cli(["registry-list", "--registry-dir", str(registry_dir), "--kind", "rule_ids"])
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["kind"], "authoring_registry_list_result")
            self.assertEqual(payload["list_kind"], "rule_ids")
            self.assertEqual(payload["items"], ["rules.country_rows"])

            code, out, err = _run_cli(
                [
                    "registry-list",
                    "--registry-dir",
                    str(registry_dir),
                    "--kind",
                    "rule_versions",
                    "--id",
                    "rules.country_rows",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["items"][0]["version"], "v1")

            code, out, err = _run_cli(["registry-show", "--registry-dir", str(registry_dir), "--kind", "schema"])
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["kind"], "authoring_registry_show_result")
            self.assertEqual(payload["show_kind"], "schema")
            self.assertEqual(payload["item"]["path"], "schema/schema_ir.json")

            code, out, err = _run_cli(
                [
                    "registry-show",
                    "--registry-dir",
                    str(registry_dir),
                    "--kind",
                    "rule",
                    "--id",
                    "rules.country_rows",
                    "--latest",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["item"]["rule_id"], "rules.country_rows")
            self.assertEqual(payload["item"]["version"], "v1")

            code, out, err = _run_cli(
                [
                    "registry-list",
                    "--registry-dir",
                    str(registry_dir),
                    "--kind",
                    "derivation_ids",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["items"], ["drv.country"])

            code, out, err = _run_cli(
                [
                    "registry-list",
                    "--registry-dir",
                    str(registry_dir),
                    "--kind",
                    "apply_run_ids",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["items"], ["cli-registry-1"])

            code, out, err = _run_cli(
                [
                    "registry-show",
                    "--registry-dir",
                    str(registry_dir),
                    "--kind",
                    "derivation",
                    "--id",
                    "drv.country",
                    "--latest",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["item"]["derivation_id"], "drv.country")

            code, out, err = _run_cli(
                [
                    "registry-show",
                    "--registry-dir",
                    str(registry_dir),
                    "--kind",
                    "apply-run",
                    "--id",
                    "cli-registry-1",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["show_kind"], "apply-run")
            self.assertEqual(payload["item"]["apply_request_id"], "cli-registry-1")

    def test_fixtures_doc_cli_registry_show_apply_run_snippet_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        snippet = _extract_json_code_block_after_header(
            text,
            "`registry-show` 输出最小字段片段（JSON stdout，apply-run）：",
        )
        self.assertEqual(snippet["kind"], "authoring_registry_show_result")
        self.assertEqual(snippet["show_kind"], "apply-run")
        self.assertEqual(snippet["id"], "req-001")
        self.assertEqual(snippet["item"]["kind"], "authoring_apply_execute_run")
        self.assertEqual(snippet["item"]["apply_request_id"], "req-001")
        self.assertEqual(snippet["item"]["idempotency"]["apply_request_id"], "req-001")
        self.assertRegex(snippet["item"]["idempotency"]["plan_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(snippet["item"]["transaction"]["prevalidate_before_write"])
        self.assertEqual(snippet["item"]["transaction"]["failure_phase"], "none")
        self.assertFalse(snippet["item"]["transaction"]["partial_apply"])

    def test_fixtures_doc_cli_apply_execute_v2_success_snippet_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        snippet = _extract_json_code_block_after_header(
            text,
            "`apply-execute --transaction-policy prevalidate_no_partial_strict_v2` 成功输出最小字段片段（v2 最小实现）：",
        )
        self.assertEqual(snippet["kind"], "authoring_publish_workflow_apply_bundle")
        apply_execute = snippet["apply_execute"]
        self.assertEqual(apply_execute["status"], "ok")
        self.assertEqual(apply_execute["transaction"]["policy"], "prevalidate_no_partial_strict_v2")
        self.assertTrue(apply_execute["transaction"]["prevalidate_before_write"])
        self.assertEqual(apply_execute["transaction"]["prevalidate_status"], "passed")
        self.assertTrue(apply_execute["transaction"]["writes_started"])
        self.assertEqual(apply_execute["transaction"]["failure_phase"], "none")
        self.assertFalse(apply_execute["transaction"]["partial_apply"])
        self.assertEqual(apply_execute["diagnostics"], [])

    def test_fixtures_doc_cli_apply_execute_unknown_policy_error_snippet_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        snippet = _extract_json_code_block_after_header(
            text,
            "`apply-execute --transaction-policy unknown_policy_x` 错误输出最小字段片段（未知策略）：",
        )
        self.assertEqual(snippet["kind"], "authoring_publish_workflow_apply_bundle")
        apply_execute = snippet["apply_execute"]
        self.assertEqual(apply_execute["status"], "error")
        self.assertEqual(apply_execute["transaction"]["policy"], "unknown_policy_x")
        self.assertFalse(apply_execute["transaction"]["prevalidate_before_write"])
        self.assertEqual(apply_execute["transaction"]["prevalidate_status"], "skipped_transaction_policy_unsupported")
        self.assertFalse(apply_execute["transaction"]["writes_started"])
        self.assertEqual(apply_execute["transaction"]["failure_phase"], "prevalidate")
        self.assertFalse(apply_execute["transaction"]["partial_apply"])
        self.assertEqual(apply_execute["diagnostics"][0]["path"], "$.apply_execute_options.transaction_policy")
        self.assertEqual(apply_execute["diagnostics"][0]["details"]["requested_policy"], "unknown_policy_x")
        self.assertEqual(apply_execute["diagnostics"][0]["details"]["supported_policies"], ["best_effort_no_rollback_v1"])
        self.assertFalse(apply_execute["diagnostics"][0]["details"]["v2_reserved_not_implemented"])

    def test_registry_commands_validate_required_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            code, _out, err = _run_cli(
                ["registry-list", "--registry-dir", str(Path(tmpdir) / "registry"), "--kind", "rule_versions"]
            )
            self.assertEqual(code, 2)
            self.assertIn("--id is required for --kind rule_versions", err)

            code, _out, err = _run_cli(
                ["registry-show", "--registry-dir", str(Path(tmpdir) / "registry"), "--kind", "rule", "--id", "r1"]
            )
            self.assertEqual(code, 2)
            self.assertIn("--version is required for --kind rule when --latest is not set", err)

            code, _out, err = _run_cli(
                ["registry-show", "--registry-dir", str(Path(tmpdir) / "registry"), "--kind", "apply-run", "--id", "req-1", "--latest"]
            )
            self.assertEqual(code, 2)
            self.assertIn("--latest is not supported for --kind apply-run", err)

    def test_registry_show_apply_run_cli_fixture_snippet_matches_shape(self) -> None:
        fixtures_doc = _docs_root() / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        self.assertIn("registry-list --registry-dir ./registry --kind apply_run_ids", text)
        self.assertIn("`registry-list apply_run_ids` 返回按 `apply_request_id` 排序", text)
        list_snippet = _extract_json_code_block_after_header(
            text,
            "`registry-list` 输出最小字段片段（JSON stdout，apply_run_ids）：",
        )
        self.assertEqual(list_snippet["kind"], "authoring_registry_list_result")
        self.assertEqual(list_snippet["list_kind"], "apply_run_ids")
        self.assertEqual(list_snippet["count"], 2)
        self.assertEqual(list_snippet["items"], ["req-001", "req-002"])
        snippet = _extract_json_code_block_after_header(
            text,
            "`registry-show` 输出最小字段片段（JSON stdout，apply-run）：",
        )
        self.assertEqual(snippet["kind"], "authoring_registry_show_result")
        self.assertEqual(snippet["show_kind"], "apply-run")
        self.assertEqual(snippet["id"], "req-001")
        item = snippet["item"]
        self.assertEqual(item["kind"], "authoring_apply_execute_run")
        self.assertEqual(item["apply_request_id"], "req-001")
        self.assertRegex(item["idempotency"]["plan_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(item["transaction"]["prevalidate_before_write"])
        self.assertEqual(item["transaction"]["failure_phase"], "none")
        self.assertFalse(item["transaction"]["partial_apply"])

    def test_preflight_command_supports_schema_dsl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dsl_path = Path(tmpdir) / "schema.py"
            schema_dsl_path.write_text(_schema_dsl_source(), encoding="utf-8")
            code, out, err = _run_cli(["preflight", "--schema-dsl", str(schema_dsl_path)])
        self.assertEqual(code, 0, msg=err)
        payload = json.loads(out)
        self.assertEqual(payload["authoring_session_dto_version"], "authoring_session_dto_v1")
        self.assertEqual(payload["sections"]["schema_preflight"]["status"], "ok")

    def test_workflow_dry_run_safe_supports_dsl_parse_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rule_dsl_path = Path(tmpdir) / "rule.py"
            rule_dsl_path.write_text("Rule(where=[Foo(\"x\")])\n", encoding="utf-8")
            code, out, err = _run_cli(["workflow-dry-run", "--rule-dsl", str(rule_dsl_path), "--safe"])
        self.assertEqual(code, 0, msg=err)
        payload = json.loads(out)
        self.assertEqual(payload["status"], "error")
        diag = payload["session"]["sections"]["rule_preflight"]["diagnostics"][0]
        self.assertEqual(diag["phase"], "rule.dsl_parse")
        self.assertEqual(diag["dsl_error_kind"], "structure")
        self.assertEqual(diag["details"]["dsl_error_detail_code"], "unsupported_helper")

    def test_apply_execute_command_supports_schema_dsl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dsl_path = Path(tmpdir) / "schema.py"
            registry_dir = Path(tmpdir) / "registry"
            schema_dsl_path.write_text(_schema_dsl_source(), encoding="utf-8")
            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--schema-dsl",
                    str(schema_dsl_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--apply-request-id",
                    "cli-dsl-req-1",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["apply_execute"]["idempotency"]["apply_request_id"], "cli-dsl-req-1")
            self.assertTrue((registry_dir / "registry_manifest.json").exists())

    def test_apply_execute_rejects_safe_with_dsl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            schema_dsl_path = Path(tmpdir) / "schema.py"
            registry_dir = Path(tmpdir) / "registry"
            schema_dsl_path.write_text(_schema_dsl_source(), encoding="utf-8")
            code, _out, err = _run_cli(
                [
                    "apply-execute",
                    "--schema-dsl",
                    str(schema_dsl_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--safe",
                ]
            )
        self.assertEqual(code, 2)
        self.assertIn("--safe is not supported for apply-execute", err)

    def test_missing_input_returns_cli_error(self) -> None:
        code, _out, err = _run_cli(["workflow-dry-run"])
        self.assertEqual(code, 2)
        self.assertIn("requires at least one payload input", err)

    def test_cli_apply_execute_events_are_visible_in_audit_static_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            schema_dsl_path = tmp_root / "schema.py"
            registry_dir = tmp_root / "registry"
            pkg_dir = tmp_root / "pkg"
            site_dir = tmp_root / "site"
            schema_dsl_path.write_text(_schema_dsl_source(), encoding="utf-8")
            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--schema-dsl",
                    str(schema_dsl_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--apply-request-id",
                    "cli-ui-req-1",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["apply_execute"]["idempotency"]["apply_request_id"], "cli-ui-req-1")
            schema_ir = compile_authoring_schema_v1(_authoring_schema())
            export_package(Store(schema_ir=schema_ir), pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            shutil.copyfile(registry_dir / "authoring_apply_events.jsonl", pkg_dir / "authoring_apply_events.jsonl")
            render_audit_static_site(pkg_dir, site_dir)
            detail_html = (site_dir / "authoring_apply_runs" / "cli-ui-req-1.html").read_text(encoding="utf-8")
            self.assertIn("Authoring Apply Run cli-ui-req-1", detail_html)
            self.assertIn("prevalidate_before_write=True", detail_html)
            self.assertIn("Idempotency", detail_html)

    def test_cli_apply_execute_runtime_failure_is_visible_in_audit_static_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            schema_path = tmp_root / "authoring_schema.json"
            registry_dir = tmp_root / "registry"
            pkg_dir = tmp_root / "pkg"
            site_dir = tmp_root / "site"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")

            def _boom_upsert_schema_ir(self, _payload):  # noqa: ANN001
                raise AuthoringRegistryFSError(
                    "simulated runtime write failure",
                    code="registry_schema_write_failed",
                    path="$.schema",
                )

            with mock.patch.object(FileAuthoringRegistry, "upsert_schema_ir", _boom_upsert_schema_ir):
                code, out, err = _run_cli(
                    [
                        "apply-execute",
                        "--authoring-schema",
                        str(schema_path),
                        "--registry-dir",
                        str(registry_dir),
                        "--apply-request-id",
                        "cli-ui-req-runtime",
                    ]
                )
            self.assertEqual(code, 0, msg=err)
            payload = json.loads(out)
            self.assertEqual(payload["apply_execute"]["status"], "error")
            self.assertFalse(payload["apply_execute"]["transaction"]["partial_apply"])
            self.assertEqual(payload["apply_execute"]["transaction"]["failure_phase"], "write")

            schema_ir = compile_authoring_schema_v1(_authoring_schema())
            export_package(Store(schema_ir=schema_ir), pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            shutil.copyfile(registry_dir / "authoring_apply_events.jsonl", pkg_dir / "authoring_apply_events.jsonl")
            render_audit_static_site(pkg_dir, site_dir)
            detail_html = (site_dir / "authoring_apply_runs" / "cli-ui-req-runtime.html").read_text(encoding="utf-8")
            self.assertIn("execution_path=runtime_partial", detail_html)
            self.assertIn("execution_path_label=Runtime partial apply", detail_html)
            self.assertIn("apply_blocked_action", detail_html)
            self.assertIn("failure_phase=write", detail_html)
            self.assertIn("failure_summary.blocked_action_diagnostic_codes=[&quot;apply_blocked_action&quot;]", detail_html)
            self.assertIn("action_stats.diagnostic_code_counts={&quot;apply_blocked_action&quot;: 1}", detail_html)

    def test_cli_apply_execute_matrix_replay_conflict_prevalidate_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            schema_path = tmp_root / "authoring_schema.json"
            schema_alt_path = tmp_root / "authoring_schema_alt.json"
            registry_dir = tmp_root / "registry"
            pkg_dir = tmp_root / "pkg"
            site_dir = tmp_root / "site"
            schema_path.write_text(json.dumps(_authoring_schema()), encoding="utf-8")
            schema_alt_path.write_text(json.dumps(_authoring_schema_alt()), encoding="utf-8")

            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--apply-request-id",
                    "cli-matrix-success",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            success_payload = json.loads(out)
            self.assertEqual(success_payload["apply_execute"]["status"], "ok")
            self.assertFalse(success_payload["apply_execute"]["idempotency"]["replayed"])
            first_log_lines = (registry_dir / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines()

            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--apply-request-id",
                    "cli-matrix-success",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            replay_payload = json.loads(out)
            self.assertTrue(replay_payload["apply_execute"]["idempotency"]["replayed"])
            self.assertEqual(
                (registry_dir / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines(),
                first_log_lines,
            )

            code, out, err = _run_cli(
                [
                    "apply-execute",
                    "--authoring-schema",
                    str(schema_alt_path),
                    "--registry-dir",
                    str(registry_dir),
                    "--apply-request-id",
                    "cli-matrix-success",
                ]
            )
            self.assertEqual(code, 0, msg=err)
            conflict_payload = json.loads(out)
            self.assertEqual(conflict_payload["apply_execute"]["status"], "error")
            self.assertTrue(conflict_payload["apply_execute"]["idempotency"]["conflict"])
            self.assertEqual(conflict_payload["apply_execute"]["transaction"]["failure_phase"], "idempotency_conflict")
            self.assertEqual(
                (registry_dir / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines(),
                first_log_lines,
            )

            def _boom_preview_upsert_schema_ir(self, _payload):  # noqa: ANN001
                raise AuthoringRegistryFSError(
                    "simulated prevalidate schema conflict",
                    code="registry_schema_preview_conflict",
                    path="$.schema",
                )

            with mock.patch.object(FileAuthoringRegistry, "preview_upsert_schema_ir", _boom_preview_upsert_schema_ir):
                code, out, err = _run_cli(
                    [
                        "apply-execute",
                        "--authoring-schema",
                        str(schema_path),
                        "--registry-dir",
                        str(registry_dir),
                        "--apply-request-id",
                        "cli-matrix-prevalidate",
                    ]
                )
            self.assertEqual(code, 0, msg=err)
            prevalidate_payload = json.loads(out)
            self.assertEqual(prevalidate_payload["apply_execute"]["status"], "error")
            self.assertEqual(prevalidate_payload["apply_execute"]["transaction"]["failure_phase"], "prevalidate")
            self.assertFalse(prevalidate_payload["apply_execute"]["transaction"]["partial_apply"])
            self.assertEqual(
                (registry_dir / "authoring_apply_events.jsonl").read_text(encoding="utf-8").splitlines(),
                first_log_lines,
            )

            schema_ir = compile_authoring_schema_v1(_authoring_schema())
            export_package(Store(schema_ir=schema_ir), pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            shutil.copyfile(registry_dir / "authoring_apply_events.jsonl", pkg_dir / "authoring_apply_events.jsonl")
            render_audit_static_site(pkg_dir, site_dir)
            self.assertTrue((site_dir / "authoring_apply_runs" / "cli-matrix-success.html").exists())
            self.assertFalse((site_dir / "authoring_apply_runs" / "cli-matrix-prevalidate.html").exists())
            events_html = (site_dir / "authoring_apply_events.html").read_text(encoding="utf-8")
            self.assertIn("cli-matrix-success", events_html)
            self.assertNotIn("cli-matrix-prevalidate", events_html)


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue().strip(), stderr.getvalue().strip()


def _extract_json_code_block_after_header(text: str, header: str) -> dict:
    idx = text.find(header)
    if idx < 0:
        raise AssertionError(f"missing header: {header}")
    tail = text[idx:]
    match = re.search(r"```json\s*\n(.*?)\n```", tail, flags=re.S)
    if match is None:
        raise AssertionError(f"missing json code block after: {header}")
    return json.loads(match.group(1))


def _authoring_schema() -> dict:
    return {
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "source_id", "type_domain": "string"}],
                "fields": [
                    {
                        "py_name": "country",
                        "name": "country",
                        "type_domain": "string",
                        "cardinality": "functional",
                        "pred_id": "person:country",
                    }
                ],
            }
        ]
    }


def _authoring_schema_alt() -> dict:
    payload = _authoring_schema()
    payload["entities"][0]["fields"][0] = dict(payload["entities"][0]["fields"][0])
    payload["entities"][0]["fields"][0]["pred_id"] = "person:country_alt"
    return payload


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs"


def _rule_request() -> dict:
    return {
        "rule_spec_payload": _rule_spec()
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


def _rule_spec() -> dict:
    return {
        "rule_id": "rules.country_rows",
        "version": "v1",
        "select_vars": ["$E", "$C"],
        "where": [("pred", "person:country", ["$E", "$C"])],
        "expose": True,
    }


def _schema_dsl_source() -> str:
    return """
class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
""".strip() + "\n"


def _rule_dsl_source() -> str:
    return """
country_rows = Rule(
    version="v1",
    select_vars=["$E", "$C"],
    where=[Pred("person:country", "$E", "$C")],
    public=True,
)
""".strip() + "\n"


def _rule_dsl_conflict_source() -> str:
    return """
country_rows = Rule(
    version="v1",
    select_vars=["$E"],
    where=[Pred("person:country", "$E", "de")],
    public=True,
)
""".strip() + "\n"


if __name__ == "__main__":
    unittest.main()
