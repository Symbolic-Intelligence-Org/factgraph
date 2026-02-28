from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.audit import AuditQuery, load_audit_package
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class AuditQueryV1Tests(unittest.TestCase):
    def test_load_audit_package_reads_ledgers(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        mention = "idref_v1:Person:auditq-load"
        asrt_id = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_primary")],
            meta={
                "source": "derivation.accept",
                "source_loc": "rule:v1",
                "trace_id": "run-auditq-1",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "run_id": "run-auditq-1",
                "materialize_id": "mat-auditq-1",
                "key_tuple_digest": "sha256:" + ("1" * 64),
                "cand_key_digest": "sha256:" + ("2" * 64),
                "support_digest": "sha256:" + ("3" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(store, asrt_id, 123)

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            data = load_audit_package(pkg_dir)

        self.assertEqual(data.manifest["package_kind"], "audit")
        self.assertIsNone(data.run_manifest)
        self.assertEqual(len(data.run_ledger), 1)
        self.assertEqual(len(data.candidate_ledger), 1)
        self.assertEqual(len(data.materialize_ledger), 1)
        self.assertEqual(len(data.decision_log), 2)
        self.assertEqual(len(data.accept_failed), 0)
        self.assertIsInstance(data.mapping_resolution, dict)
        self.assertEqual(data.run_ledger[0]["run_id"], "run-auditq-1")

    def test_audit_query_run_bundle_and_filters(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        mention = "idref_v1:Person:auditq-bundle"
        asrt_id = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_primary")],
            meta={
                "source": "derivation.accept",
                "source_loc": "rule:v1",
                "run_id": "run-auditq-2",
                "materialize_id": "mat-auditq-2",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "key_tuple_digest": "sha256:" + ("4" * 64),
                "cand_key_digest": "sha256:" + ("5" * 64),
                "support_digest": "sha256:" + ("6" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(store, asrt_id, 456)

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            data = load_audit_package(pkg_dir)

        query = AuditQuery(data)
        runs = query.list_runs()
        self.assertEqual([row["run_id"] for row in runs], ["run-auditq-2"])

        bundle = query.get_run_bundle("run-auditq-2")
        self.assertEqual(bundle["run"]["run_id"], "run-auditq-2")
        self.assertEqual(len(bundle["materializations"]), 1)
        self.assertEqual(len(bundle["candidates"]), 1)
        self.assertEqual(len(bundle["decisions"]), 2)
        self.assertEqual(len(bundle["failures"]), 0)

        mapping_decisions = query.list_decisions(run_id="run-auditq-2", event_source="mapping")
        self.assertEqual(len(mapping_decisions), 1)
        self.assertEqual(mapping_decisions[0]["event_kind"], "mapping_decision")
        accept_decisions = query.list_decisions(event_kind="accept_write")
        self.assertEqual(len(accept_decisions), 1)
        self.assertEqual(accept_decisions[0]["run_id"], "run-auditq-2")

    def test_audit_query_failures_for_mapping_conflict(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break=None))
        mention = "idref_v1:Person:auditq-conflict"
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_a")],
            meta={"source": "hr", "source_loc": "row-1", "run_id": "run-auditq-3"},
        )
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_b")],
            meta={"source": "crm", "source_loc": "row-2", "run_id": "run-auditq-3"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            data = load_audit_package(pkg_dir)

        query = AuditQuery(data)
        failures = query.list_failures(run_id="run-auditq-3")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["error_class"], "mapping_conflict")
        self.assertEqual(failures[0]["event_kind"], "mapping_conflict")

        bundle = query.get_run_bundle("run-auditq-3")
        self.assertEqual(len(bundle["failures"]), 1)
        self.assertEqual(bundle["run"]["error_count"], 1)
        self.assertTrue(bundle["run"]["has_failures"])

        mapping_rows = query.get_mapping_resolution(pred_id="er:canon_of")
        self.assertEqual(len(mapping_rows), 1)
        self.assertEqual(mapping_rows[0]["status"], "conflict")

    def test_audit_query_authoring_apply_runs(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            export_package(store, pkg_dir, ExportOptions(package_kind="audit", policy_mode="edb"))
            _write_authoring_apply_events(
                pkg_dir,
                [
                    {
                        "kind": "authoring_apply_execute_action",
                        "apply_request_id": "req-a",
                        "action_id": "schema-1",
                        "section": "schema_preflight",
                        "status": "applied",
                    },
                    {
                        "kind": "authoring_apply_execute_run",
                        "apply_request_id": "req-a",
                        "status": "ok",
                        "ok": True,
                        "idempotency": {"apply_request_id": "req-a", "plan_digest": "sha256:x", "replayed": False},
                        "transaction": {"policy": "best_effort_no_rollback_v1", "prevalidate_before_write": True, "partial_apply": False},
                        "summary": {"applied_count": 1},
                    },
                    {
                        "kind": "authoring_apply_execute_run",
                        "apply_request_id": "req-b",
                        "status": "warning",
                        "ok": True,
                        "summary": {"noop_count": 1},
                    },
                ],
            )
            data = load_audit_package(pkg_dir)

        query = AuditQuery(data)
        runs = query.list_authoring_apply_runs()
        self.assertEqual([row["apply_request_id"] for row in runs], ["req-a", "req-b"])
        self.assertEqual(query.get_authoring_apply_run("req-b")["status"], "warning")
        bundle = query.get_authoring_apply_bundle("req-a")
        self.assertEqual(bundle["run"]["kind"], "authoring_apply_execute_run")
        self.assertEqual(bundle["summary"]["event_count"], 2)
        self.assertEqual(bundle["run"]["idempotency"]["apply_request_id"], "req-a")
        self.assertTrue(bundle["run"]["transaction"]["prevalidate_before_write"])
        self.assertEqual(len(query.list_authoring_apply_events(status="applied")), 1)


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
                "identity_fields": [
                    {"name": "source_id", "type_domain": "string"},
                ],
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
    path = pkg_dir / "authoring_apply_events.jsonl"
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
