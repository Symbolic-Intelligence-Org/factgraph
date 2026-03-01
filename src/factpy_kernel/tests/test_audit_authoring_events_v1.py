from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factpy_kernel.audit import load_authoring_apply_events, summarize_authoring_apply_events
from factpy_kernel.authoring import (
    FileAuthoringRegistry,
    build_authoring_publish_workflow_apply_bundle_dto,
)
from factpy_kernel.core.store.api import Store


class AuditAuthoringEventsV1Tests(unittest.TestCase):
    def test_load_and_summarize_authoring_apply_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = FileAuthoringRegistry(tmpdir)
            bundle = build_authoring_publish_workflow_apply_bundle_dto(
                registry=registry,
                store=Store(schema_ir=_schema()),
                schema_ir=_schema(),
                derivation_request=_derivation_request(),
            )
            self.assertTrue(bundle["apply_execute"]["summary"]["applied_count"] >= 2)

            events = load_authoring_apply_events(tmpdir)
            self.assertGreaterEqual(len(events), 2)
            run_events = [row for row in events if row.raw.get("kind") == "authoring_apply_execute_run"]
            self.assertEqual(len(run_events), 1)
            self.assertIn("idempotency", run_events[0].raw)
            self.assertIn("transaction", run_events[0].raw)
            summary = summarize_authoring_apply_events(events)
            self.assertEqual(summary["event_count"], len(events))
            self.assertIn("applied", summary["status_counts"])
            self.assertIn("schema_preflight", summary["section_counts"])

    def test_missing_authoring_apply_events_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            events = load_authoring_apply_events(tmpdir)
            self.assertEqual(events, [])
            self.assertEqual(summarize_authoring_apply_events(events)["event_count"], 0)

    def test_runtime_blocked_action_event_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "authoring_apply_events.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "kind": "authoring_apply_execute_action",
                                "apply_request_id": "req-rt-1",
                                "action_id": "action:1:rule_preflight",
                                "section": "rule_preflight",
                                "status": "blocked",
                                "reason_code": "apply_blocked_action",
                                "diagnostics_summary": {"count": 1, "codes": ["apply_blocked_action"]},
                                "diagnostics": [{"code": "apply_blocked_action"}],
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "kind": "authoring_apply_execute_run",
                                "apply_request_id": "req-rt-1",
                                "status": "error",
                                "ok": False,
                                "partial_apply": True,
                                "transaction": {"failure_phase": "write"},
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            events = load_authoring_apply_events(tmpdir)
            self.assertEqual(len(events), 2)
            action = [row.raw for row in events if row.raw.get("kind") == "authoring_apply_execute_action"][0]
            self.assertEqual(action["status"], "blocked")
            self.assertEqual(action["reason_code"], "apply_blocked_action")
            self.assertEqual(action["diagnostics_summary"]["codes"], ["apply_blocked_action"])


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


def _derivation_request() -> dict:
    return {
        "derivation_id": "drv.country",
        "version": "v1",
        "target_pred_id": "person:country",
        "head_vars": ["$E", "$C"],
        "where": [("pred", "person:country", ["$E", "$C"])],
        "mode": "python",
        "temporal_view": "active",
    }


if __name__ == "__main__":
    unittest.main()
