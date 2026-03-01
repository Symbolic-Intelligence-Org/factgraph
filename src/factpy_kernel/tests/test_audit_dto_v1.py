from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.audit import (
    AuditDTOError,
    AuditQuery,
    build_authoring_apply_run_detail_dto,
    build_authoring_apply_run_list_dto,
    build_decision_detail_dto,
    build_run_detail_dto,
    build_run_list_dto,
    load_audit_package,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class AuditDTOV1Tests(unittest.TestCase):
    def test_build_run_list_dto(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        asrt_id = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditdto-list",
            rest_terms=[("entity_ref", "idref_v1:Person:c_list")],
            meta={
                "source": "derivation.accept",
                "run_id": "run-auditdto-1",
                "candidate_id": "cand_v2:auditdto_1",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "key_tuple_digest": "sha256:" + ("1" * 64),
                "cand_key_digest": "sha256:" + ("2" * 64),
                "support_digest": "sha256:" + ("3" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(store, asrt_id, 111)
        query = AuditQuery(_export_and_load(store))

        payload = build_run_list_dto(query)
        self.assertEqual(payload["audit_ui_dto_version"], "audit_ui_dto_v1")
        self.assertEqual(payload["kind"], "run_list")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["runs"][0]["run_id"], "run-auditdto-1")
        self.assertEqual(payload["runs"][0]["claim_count"], 1)
        self.assertEqual(payload["runs"][0]["has_failures"], False)
        self.assertEqual(payload["runs"][0]["candidate_ids"], ["cand_v2:auditdto_1"])

    def test_build_run_detail_dto_contains_timeline(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        asrt_id = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditdto-run",
            rest_terms=[("entity_ref", "idref_v1:Person:c_run")],
            meta={
                "source": "derivation.accept",
                "run_id": "run-auditdto-2",
                "candidate_id": "cand_v2:auditdto_2",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "key_tuple_digest": "sha256:" + ("4" * 64),
                "cand_key_digest": "sha256:" + ("5" * 64),
                "support_digest": "sha256:" + ("6" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(store, asrt_id, 222)
        query = AuditQuery(_export_and_load(store))

        payload = build_run_detail_dto(query, "run-auditdto-2")
        self.assertEqual(payload["kind"], "run_detail")
        self.assertEqual(payload["run_id"], "run-auditdto-2")
        self.assertEqual(payload["stats"]["accept_write_count"], 1)
        self.assertEqual(payload["stats"]["candidate_count"], 1)
        self.assertEqual(payload["stats"]["decision_count"], 2)
        self.assertEqual(payload["stats"]["failure_count"], 0)
        self.assertEqual(len(payload["timeline"]), 2)
        self.assertEqual([row["entry_kind"] for row in payload["timeline"]], ["decision", "decision"])
        self.assertEqual(sorted(payload["event_source_counts"].keys()), ["accept", "mapping"])

    def test_build_decision_detail_dto_accept_and_failure_links(self) -> None:
        accept_store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        asrt_id = set_field(
            accept_store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditdto-dec-accept",
            rest_terms=[("entity_ref", "idref_v1:Person:c_accept")],
            meta={
                "source": "derivation.accept",
                "run_id": "run-auditdto-3",
                "candidate_id": "cand_v2:auditdto_3",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "key_tuple_digest": "sha256:" + ("7" * 64),
                "cand_key_digest": "sha256:" + ("8" * 64),
                "support_digest": "sha256:" + ("9" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(accept_store, asrt_id, 333)
        accept_query = AuditQuery(_export_and_load(accept_store))
        accept_decision = accept_query.list_decisions(event_source="accept")[0]["decision_id"]
        accept_payload = build_decision_detail_dto(accept_query, accept_decision)
        self.assertEqual(accept_payload["kind"], "decision_detail")
        self.assertEqual(accept_payload["decision"]["event_kind"], "accept_write")
        self.assertEqual(len(accept_payload["accept_writes"]), 1)
        self.assertEqual(len(accept_payload["candidates"]), 1)
        self.assertEqual(len(accept_payload["failures"]), 0)
        self.assertEqual(accept_payload["related"]["run_ids"], ["run-auditdto-3"])
        self.assertEqual(accept_payload["related"]["candidate_ids"], ["cand_v2:auditdto_3"])

        conflict_store = Store(schema_ir=_mapping_schema(tie_break=None))
        set_field(
            conflict_store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditdto-conflict",
            rest_terms=[("entity_ref", "idref_v1:Person:c1")],
            meta={"source": "hr", "source_loc": "row-1", "run_id": "run-auditdto-4"},
        )
        set_field(
            conflict_store.ledger,
            pred_id="er:canon_of",
            e_ref="idref_v1:Person:auditdto-conflict",
            rest_terms=[("entity_ref", "idref_v1:Person:c2")],
            meta={"source": "crm", "source_loc": "row-2", "run_id": "run-auditdto-4"},
        )
        conflict_query = AuditQuery(_export_and_load(conflict_store))
        failure_decision = conflict_query.list_decisions(event_kind="mapping_conflict")[0]["decision_id"]
        failure_payload = build_decision_detail_dto(conflict_query, failure_decision)
        self.assertEqual(failure_payload["decision"]["event_kind"], "mapping_conflict")
        self.assertEqual(len(failure_payload["accept_writes"]), 0)
        self.assertEqual(len(failure_payload["candidates"]), 0)
        self.assertEqual(len(failure_payload["failures"]), 1)
        self.assertEqual(failure_payload["related"]["run_ids"], ["run-auditdto-4"])

    def test_build_decision_detail_missing_raises(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        query = AuditQuery(_export_and_load(store))
        with self.assertRaises(AuditDTOError):
            build_decision_detail_dto(query, "missing")

    def test_build_authoring_apply_run_dtos(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            _write_authoring_apply_events(
                pkg_dir,
                [
                    {
                        "kind": "authoring_apply_execute_action",
                        "apply_request_id": "req-dto-1",
                        "action_id": "act-1",
                        "section": "schema_preflight",
                        "status": "applied",
                    },
                    {
                        "kind": "authoring_apply_execute_run",
                        "apply_request_id": "req-dto-1",
                        "status": "ok",
                        "ok": True,
                        "idempotency": {
                            "apply_request_id": "req-dto-1",
                            "plan_digest": "sha256:abc",
                            "replayed": False,
                        },
                        "transaction": {
                            "policy": "best_effort_no_rollback_v1",
                            "prevalidate_before_write": True,
                            "partial_apply": False,
                        },
                        "summary": {"applied_count": 1, "noop_count": 0, "blocked_count": 0, "skipped_count": 0},
                    },
                ],
            )
            query = AuditQuery(load_audit_package(pkg_dir))

        run_list = build_authoring_apply_run_list_dto(query)
        self.assertEqual(run_list["kind"], "authoring_apply_run_list")
        self.assertEqual(run_list["count"], 1)
        self.assertEqual(run_list["runs"][0]["apply_request_id"], "req-dto-1")
        detail = build_authoring_apply_run_detail_dto(query, "req-dto-1")
        self.assertEqual(detail["kind"], "authoring_apply_run_detail")
        self.assertEqual(detail["summary"]["event_count"], 2)
        self.assertEqual(detail["stats"]["event_count"], 2)
        self.assertEqual(detail["idempotency"]["apply_request_id"], "req-dto-1")
        self.assertEqual(detail["transaction"]["policy"], "best_effort_no_rollback_v1")
        self.assertFalse(detail["classifications"]["replayed"])
        self.assertFalse(detail["classifications"]["prevalidate_blocked"])
        self.assertEqual(detail["execution_path"], "success")
        self.assertEqual(detail["execution_path_label"], "Success")
        self.assertEqual(detail["execution_path_counts"], {"success": 1})
        self.assertEqual(detail["action_stats"]["status_counts"]["applied"], 1)
        self.assertEqual(detail["action_stats"]["diagnostic_code_counts"], {})
        self.assertEqual(detail["failure_summary"]["first_failure_action_id"], None)
        self.assertEqual(detail["failure_summary"]["blocked_action_reason_codes"], [])
        self.assertEqual(detail["failure_summary"]["blocked_action_diagnostic_codes"], [])

    def test_build_authoring_apply_run_dto_uses_diagnostics_summary_for_failure_aggregation(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            _write_authoring_apply_events(
                pkg_dir,
                [
                    {
                        "kind": "authoring_apply_execute_action",
                        "apply_request_id": "req-dto-2",
                        "action_id": "act-2",
                        "section": "rule_preflight",
                        "status": "blocked",
                        "reason_code": "apply_blocked_action",
                        "diagnostics_summary": {"count": 1, "codes": ["apply_blocked_action"]},
                    },
                    {
                        "kind": "authoring_apply_execute_run",
                        "apply_request_id": "req-dto-2",
                        "status": "error",
                        "ok": False,
                        "idempotency": {"apply_request_id": "req-dto-2", "plan_digest": "sha256:def", "replayed": False},
                        "transaction": {
                            "policy": "best_effort_no_rollback_v1",
                            "prevalidate_before_write": True,
                            "prevalidate_status": "passed",
                            "writes_started": True,
                            "failure_phase": "write",
                            "partial_apply": False,
                        },
                        "summary": {"applied_count": 0, "noop_count": 0, "blocked_count": 1, "skipped_count": 0},
                    },
                ],
            )
            query = AuditQuery(load_audit_package(pkg_dir))

        detail = build_authoring_apply_run_detail_dto(query, "req-dto-2")
        self.assertEqual(detail["execution_path"], "runtime_partial")
        self.assertEqual(detail["execution_path_label"], "Runtime partial apply")
        self.assertEqual(detail["action_stats"]["diagnostic_code_counts"], {"apply_blocked_action": 1})
        self.assertEqual(detail["failure_summary"]["first_failure_action_id"], "act-2")
        self.assertEqual(detail["failure_summary"]["first_failure_section"], "rule_preflight")
        self.assertEqual(detail["failure_summary"]["blocked_action_reason_codes"], ["apply_blocked_action"])
        self.assertEqual(detail["failure_summary"]["blocked_action_diagnostic_codes"], ["apply_blocked_action"])

    def test_fixtures_doc_authoring_apply_run_detail_snippet_shape(self) -> None:
        fixtures_doc = Path(__file__).resolve().parents[3] / "docs" / "blueprint" / "Authoring 层契约 fixtures.md"
        text = fixtures_doc.read_text(encoding="utf-8")
        snippet = _extract_json_code_block_after_header(
            text,
            "`audit_ui_dto_v1` 中 `authoring_apply_run_detail` 最小片段（执行态摘要）：",
        )
        self.assertEqual(snippet["kind"], "authoring_apply_run_detail")
        self.assertEqual(snippet["apply_request_id"], "req-rt-1")
        self.assertEqual(snippet["execution_path"], "runtime_partial")
        self.assertEqual(snippet["execution_path_label"], "Runtime partial apply")
        self.assertEqual(snippet["execution_path_counts"], {"runtime_partial": 1})
        self.assertEqual(
            snippet["action_stats"]["diagnostic_code_counts"],
            {"apply_blocked_action": 1},
        )
        self.assertEqual(
            snippet["failure_summary"]["blocked_action_reason_codes"],
            ["apply_blocked_action"],
        )
        self.assertEqual(
            snippet["failure_summary"]["blocked_action_diagnostic_codes"],
            ["apply_blocked_action"],
        )


def _export_and_load(store: Store):
    with tempfile.TemporaryDirectory() as tmp:
        pkg_dir = Path(tmp) / "pkg"
        export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
        return load_audit_package(pkg_dir)


def _mapping_schema(tie_break: object) -> dict:
    predicate: dict[str, object] = {
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
    }
    if tie_break is not None:
        predicate["tie_break"] = tie_break
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "source_id", "type_domain": "string"}],
            }
        ],
        "predicates": [predicate],
        "projection": {"entities": [], "predicates": ["er:canon_of"]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _set_ingested_at(store: Store, asrt_id: str, epoch_nanos: int) -> None:
    replaced = False
    updated: list[MetaRow] = []
    for row in store.ledger.meta_rows:
        if row.asrt_id == asrt_id and row.key == "ingested_at":
            updated.append(MetaRow(asrt_id=row.asrt_id, key=row.key, kind="time", value=epoch_nanos))
            replaced = True
        else:
            updated.append(row)
    if not replaced:
        raise AssertionError(f"missing ingested_at for asrt_id={asrt_id}")
    store.ledger._force_replace_meta_rows(updated)
def _write_authoring_apply_events(pkg_dir: Path, rows: list[dict]) -> None:
    (pkg_dir / "authoring_apply_events.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _extract_json_code_block_after_header(text: str, header: str) -> dict:
    idx = text.find(header)
    if idx < 0:
        raise AssertionError(f"missing header: {header}")
    tail = text[idx:]
    import re

    match = re.search(r"```json\s*\n(.*?)\n```", tail, flags=re.S)
    if match is None:
        raise AssertionError(f"missing json code block after: {header}")
    return json.loads(match.group(1))


if __name__ == "__main__":
    unittest.main()
