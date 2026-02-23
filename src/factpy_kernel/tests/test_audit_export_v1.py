from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class AuditExportV1Tests(unittest.TestCase):
    def test_audit_package_writes_required_ledgers(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id"))
        mention = "idref_v1:Person:m-ledger"
        asrt_id = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_primary")],
            meta={
                "source": "derivation.accept",
                "source_loc": "rule:v1",
                "trace_id": "run-ledger-1",
                "derived_rule_id": "rule.accept",
                "derived_rule_version": "v1",
                "run_id": "run-ledger-1",
                "materialize_id": "mat-ledger-1",
                "key_tuple_digest": "sha256:" + ("1" * 64),
                "cand_key_digest": "sha256:" + ("2" * 64),
                "support_digest": "sha256:" + ("3" * 64),
                "support_kind": "none",
            },
        )
        _set_ingested_at(store, asrt_id, 123456789)

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = export_package(
                store,
                Path(tmp) / "pkg",
                ExportOptions(package_kind="audit", policy_mode="edb"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            audit_files = manifest["paths"]["audit_files"]

            required_keys = {
                "run_ledger",
                "candidate_ledger",
                "materialize_ledger",
                "accept_failed",
                "mapping_resolution",
                "decision_log",
            }
            self.assertTrue(required_keys.issubset(set(audit_files.keys())))

            run_ledger_path = Path(tmp) / "pkg" / audit_files["run_ledger"]
            candidate_ledger_path = Path(tmp) / "pkg" / audit_files["candidate_ledger"]
            materialize_ledger_path = Path(tmp) / "pkg" / audit_files["materialize_ledger"]
            accept_failed_path = Path(tmp) / "pkg" / audit_files["accept_failed"]
            decision_log_path = Path(tmp) / "pkg" / audit_files["decision_log"]
            for path in [run_ledger_path, candidate_ledger_path, materialize_ledger_path, accept_failed_path, decision_log_path]:
                self.assertTrue(path.exists())

            run_rows = [
                json.loads(line)
                for line in run_ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(run_rows), 1)
            self.assertEqual(run_rows[0]["run_id"], "run-ledger-1")
            self.assertEqual(run_rows[0]["claim_count"], 1)
            self.assertEqual(run_rows[0]["materialize_ids"], ["mat-ledger-1"])
            self.assertEqual(run_rows[0]["pred_ids"], ["er:canon_of"])
            self.assertEqual(len(run_rows[0]["decision_ids"]), 2)
            self.assertEqual(run_rows[0]["decision_count"], 2)
            self.assertEqual(run_rows[0]["event_source_counts"], {"accept": 1, "mapping": 1})
            self.assertEqual(
                run_rows[0]["event_kind_counts"],
                {"accept_write": 1, "mapping_decision": 1},
            )
            self.assertEqual(run_rows[0]["error_count"], 0)
            self.assertEqual(run_rows[0]["error_class_counts"], {})
            self.assertEqual(run_rows[0]["error_event_kind_counts"], {})
            self.assertEqual(run_rows[0]["failed_decision_ids"], [])
            self.assertIsNone(run_rows[0]["last_error_ts"])
            self.assertIsNone(run_rows[0]["failed_event_ts_min"])
            self.assertIsNone(run_rows[0]["failed_event_ts_max"])
            self.assertIsNone(run_rows[0]["last_failure_class"])
            self.assertIsNone(run_rows[0]["last_failure_decision_id"])
            self.assertIsNone(run_rows[0]["last_failure_message"])
            self.assertFalse(run_rows[0]["has_failures"])
            self.assertTrue(
                any(value.startswith("accept_write:") for value in run_rows[0]["decision_ids"])
            )
            self.assertTrue(
                any(value.startswith("mapping_decision:") for value in run_rows[0]["decision_ids"])
            )
            self.assertEqual(run_rows[0]["event_ts_min"], 123456789)
            self.assertEqual(run_rows[0]["event_ts_max"], 123456789)

            materialize_rows = [
                json.loads(line)
                for line in materialize_ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(materialize_rows), 1)
            self.assertEqual(materialize_rows[0]["asrt_id"], asrt_id)
            self.assertEqual(materialize_rows[0]["materialize_id"], "mat-ledger-1")
            self.assertEqual(materialize_rows[0]["run_id"], "run-ledger-1")
            self.assertEqual(materialize_rows[0]["ingested_at"], 123456789)

            decision_rows = [
                json.loads(line)
                for line in decision_log_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(decision_rows), 2)
            self.assertEqual(decision_rows[0]["event_kind"], "accept_write")
            self.assertEqual(decision_rows[1]["event_kind"], "mapping_decision")
            self.assertEqual(decision_rows[0]["event_source"], "accept")
            self.assertEqual(decision_rows[1]["event_source"], "mapping")
            self.assertTrue(decision_rows[0]["decision_id"].startswith("accept_write:"))
            self.assertTrue(decision_rows[1]["decision_id"].startswith("mapping_decision:"))
            self.assertEqual(decision_rows[1]["run_ids"], ["run-ledger-1"])
            self.assertEqual(decision_rows[1]["materialize_ids"], ["mat-ledger-1"])
            self.assertEqual(decision_rows[0]["event_ts"], 123456789)
            self.assertEqual(decision_rows[1]["event_ts"], 123456789)

            candidate_rows = [
                json.loads(line)
                for line in candidate_ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(candidate_rows), 1)
            self.assertEqual(candidate_rows[0]["state"], "accepted")
            self.assertEqual(candidate_rows[0]["asrt_id"], asrt_id)
            self.assertEqual(candidate_rows[0]["decision_id"], decision_rows[0]["decision_id"])
            self.assertEqual(candidate_rows[0]["event_source"], "accept")
            self.assertEqual(candidate_rows[0]["event_kind"], "accept_write")
            self.assertEqual(candidate_rows[0]["event_ts"], 123456789)
            self.assertEqual(accept_failed_path.read_text(encoding="utf-8"), "")

    def test_run_ledger_failure_counts_when_run_ids_present(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break=None))
        mention = "idref_v1:Person:m-fail"
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_a")],
            meta={"source": "hr", "source_loc": "row-1", "run_id": "run-fail-1"},
        )
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_b")],
            meta={"source": "crm", "source_loc": "row-2", "run_id": "run-fail-1"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = export_package(
                store,
                Path(tmp) / "pkg",
                ExportOptions(package_kind="audit", policy_mode="edb"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            run_rows = [
                json.loads(line)
                for line in (Path(tmp) / "pkg" / manifest["paths"]["audit_files"]["run_ledger"]).read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(run_rows), 1)
            self.assertEqual(run_rows[0]["run_id"], "run-fail-1")
            self.assertEqual(run_rows[0]["error_count"], 1)
            self.assertEqual(run_rows[0]["error_class_counts"], {"mapping_conflict": 1})
            self.assertEqual(run_rows[0]["error_event_kind_counts"], {"mapping_conflict": 1})
            self.assertEqual(len(run_rows[0]["failed_decision_ids"]), 1)
            self.assertTrue(run_rows[0]["failed_decision_ids"][0].startswith("mapping_conflict:"))
            self.assertIsInstance(run_rows[0]["last_error_ts"], int)
            self.assertIsInstance(run_rows[0]["failed_event_ts_min"], int)
            self.assertIsInstance(run_rows[0]["failed_event_ts_max"], int)
            self.assertEqual(run_rows[0]["failed_event_ts_min"], run_rows[0]["failed_event_ts_max"])
            self.assertEqual(run_rows[0]["last_error_ts"], run_rows[0]["failed_event_ts_max"])
            self.assertEqual(run_rows[0]["last_failure_class"], "mapping_conflict")
            self.assertTrue(
                isinstance(run_rows[0]["last_failure_decision_id"], str)
                and run_rows[0]["last_failure_decision_id"].startswith("mapping_conflict:")
            )
            self.assertTrue(
                isinstance(run_rows[0]["last_failure_message"], str)
                and run_rows[0]["last_failure_message"].startswith("mapping conflict for er:canon_of:")
            )
            self.assertTrue(run_rows[0]["has_failures"])

    def test_audit_package_writes_mapping_conflicts(self) -> None:
        store = Store(schema_ir=_mapping_schema(tie_break=None))
        mention = "idref_v1:Person:m1"
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_a")],
            meta={"source": "hr", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_b")],
            meta={"source": "crm", "source_loc": "row-2"},
        )

        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = export_package(
                store,
                Path(tmp) / "pkg",
                ExportOptions(package_kind="audit", policy_mode="edb"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            mapping_rel = manifest["paths"]["audit_files"]["mapping_resolution"]
            decision_rel = manifest["paths"]["audit_files"]["decision_log"]
            accept_failed_rel = manifest["paths"]["audit_files"]["accept_failed"]
            mapping_path = Path(tmp) / "pkg" / mapping_rel
            decision_path = Path(tmp) / "pkg" / decision_rel
            accept_failed_path = Path(tmp) / "pkg" / accept_failed_rel
            self.assertTrue(mapping_path.exists())
            payload = json.loads(mapping_path.read_text(encoding="utf-8"))
            decision_rows = [
                json.loads(line)
                for line in decision_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            accept_failed_rows = [
                json.loads(line)
                for line in accept_failed_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(payload["mapping_audit_version"], "mapping_audit_v1")
        pred_rows = [row for row in payload["predicates"] if row["pred_id"] == "er:canon_of"]
        self.assertEqual(len(pred_rows), 1)
        self.assertEqual(pred_rows[0]["status"], "conflict")
        self.assertGreaterEqual(len(pred_rows[0]["conflicts"]), 1)
        self.assertEqual([row["event_kind"] for row in decision_rows], ["mapping_conflict"])
        self.assertEqual([row["event_source"] for row in decision_rows], ["mapping"])
        self.assertEqual([row["error_class"] for row in accept_failed_rows], ["mapping_conflict"])
        self.assertEqual([row["event_kind"] for row in accept_failed_rows], ["mapping_conflict"])
        self.assertEqual([row["event_source"] for row in accept_failed_rows], ["mapping"])
        self.assertEqual(decision_rows[0]["decision_id"], accept_failed_rows[0]["decision_id"])
        self.assertTrue(decision_rows[0]["decision_id"].startswith("mapping_conflict:"))
        self.assertEqual(decision_rows[0]["run_ids"], [])
        self.assertEqual(decision_rows[0]["materialize_ids"], [])
        self.assertEqual(accept_failed_rows[0]["run_ids"], [])
        self.assertEqual(accept_failed_rows[0]["materialize_ids"], [])
        self.assertIsInstance(decision_rows[0]["event_ts"], int)
        self.assertEqual(accept_failed_rows[0]["event_ts"], decision_rows[0]["event_ts"])

    def test_audit_package_logs_resolved_and_idb_rejection(self) -> None:
        schema = _mapping_schema(tie_break="latest_by_ingested_at_then_min_assertion_id")
        store = Store(schema_ir=schema)
        mention = "idref_v1:Person:m2"
        asrt_old = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_old")],
            meta={"source": "hr", "source_loc": "row-1"},
        )
        asrt_new = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", "idref_v1:Person:c_new")],
            meta={"source": "crm", "source_loc": "row-2"},
        )
        _set_ingested_at(store, asrt_old, 100)
        _set_ingested_at(store, asrt_new, 200)

        with tempfile.TemporaryDirectory() as tmp:
            edb_manifest = export_package(
                store,
                Path(tmp) / "pkg_edb",
                ExportOptions(package_kind="audit", policy_mode="edb"),
            )
            edb_payload = json.loads(
                (Path(tmp) / "pkg_edb" / "audit" / "mapping_resolution.json").read_text(
                    encoding="utf-8"
                )
            )
            edb_decision_rows = [
                json.loads(line)
                for line in (Path(tmp) / "pkg_edb" / "audit" / "decision_log.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            edb_accept_failed_rows = [
                json.loads(line)
                for line in (Path(tmp) / "pkg_edb" / "audit" / "accept_failed.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(json.loads(edb_manifest.read_text(encoding="utf-8"))["policy_mode"], "edb")

            idb_manifest = export_package(
                store,
                Path(tmp) / "pkg_idb",
                ExportOptions(package_kind="audit", policy_mode="idb"),
            )
            idb_payload = json.loads(
                (Path(tmp) / "pkg_idb" / "audit" / "mapping_resolution.json").read_text(
                    encoding="utf-8"
                )
            )
            idb_decision_rows = [
                json.loads(line)
                for line in (Path(tmp) / "pkg_idb" / "audit" / "decision_log.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            idb_accept_failed_rows = [
                json.loads(line)
                for line in (Path(tmp) / "pkg_idb" / "audit" / "accept_failed.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(json.loads(idb_manifest.read_text(encoding="utf-8"))["policy_mode"], "idb")

        edb_row = [row for row in edb_payload["predicates"] if row["pred_id"] == "er:canon_of"][0]
        self.assertEqual(edb_row["status"], "resolved")
        self.assertEqual(
            edb_row["chosen"],
            [
                {
                    "key_tuple": [mention],
                    "value_tuple": ["idref_v1:Person:c_new"],
                }
            ],
        )

        idb_row = [row for row in idb_payload["predicates"] if row["pred_id"] == "er:canon_of"][0]
        self.assertEqual(idb_row["status"], "error")
        self.assertIn("policy_mode='edb'", idb_row["error"])
        self.assertEqual(edb_accept_failed_rows, [])
        self.assertEqual([row["event_kind"] for row in edb_decision_rows], ["mapping_decision"])
        self.assertEqual([row["event_source"] for row in edb_decision_rows], ["mapping"])
        self.assertEqual(edb_decision_rows[0]["event_ts"], 200)
        self.assertEqual([row["error_class"] for row in idb_accept_failed_rows], ["mapping_error"])
        self.assertEqual([row["event_kind"] for row in idb_accept_failed_rows], ["mapping_error"])
        self.assertEqual([row["event_source"] for row in idb_accept_failed_rows], ["mapping"])
        self.assertEqual([row["event_kind"] for row in idb_decision_rows], ["mapping_error"])
        self.assertEqual([row["event_source"] for row in idb_decision_rows], ["mapping"])
        self.assertEqual(idb_accept_failed_rows[0]["decision_id"], idb_decision_rows[0]["decision_id"])
        self.assertEqual(idb_decision_rows[0]["run_ids"], [])
        self.assertEqual(idb_decision_rows[0]["materialize_ids"], [])
        self.assertEqual(idb_accept_failed_rows[0]["run_ids"], [])
        self.assertEqual(idb_accept_failed_rows[0]["materialize_ids"], [])
        self.assertIsNone(idb_decision_rows[0]["event_ts"])
        self.assertIsNone(idb_accept_failed_rows[0]["event_ts"])


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
        "projection": {
            "entities": [],
            "predicates": ["er:canon_of"],
        },
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
    for row in store.ledger._meta_rows:
        if row.asrt_id == asrt_id and row.key == "ingested_at":
            updated.append(
                MetaRow(
                    asrt_id=row.asrt_id,
                    key=row.key,
                    kind="time",
                    value=epoch_nanos,
                )
            )
            replaced = True
        else:
            updated.append(row)
    if not replaced:
        raise AssertionError(f"missing ingested_at for asrt_id={asrt_id}")
    store.ledger._meta_rows = updated
    store.ledger.rebuild_indexes()
if __name__ == "__main__":
    unittest.main()
