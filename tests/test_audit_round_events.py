from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from factgraph.application.protocol.derivation_diagnose import DiagnoseAtomLocator
from factgraph.audit import AuditQuery, load_audit_package
from factgraph.audit.round_events import (
    RoundEventError,
    RoundRecorder,
    finalize_round,
    project_check_event_payload,
    project_diagnose_event_payload,
    project_fact_overlay_event_payload,
    project_proof_frame_event_payload,
    project_why_not_event_payload,
    record_round_event,
    start_round,
)
from factgraph.core.store._support import normalize_binding_items


class AuditRoundEventTests(unittest.TestCase):
    def test_recorder_writes_optional_round_events_and_query_round_trips(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir)
            recorder = start_round("round-1", event_ts=100)
            record_round_event(
                recorder,
                kind="check_result",
                payload={
                    "request": {
                        "plan_digest": "sha256:" + ("1" * 64),
                        "binding": [["$p", "alice"]],
                        "engine": "native",
                    },
                    "result": {
                        "status": "passed",
                        "requested_binding": [["$p", "alice"]],
                        "matched_count": 1,
                        "matched_binding": [["$p", "alice"]],
                        "evidence_envelope": None,
                    },
                    "errors": [],
                    "warnings": [],
                },
                event_ts=101,
            )
            path = finalize_round(recorder, package_dir, event_ts=102)

            self.assertEqual(path, package_dir / "audit" / "round_events.jsonl")
            manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["paths"]["audit_files"]["round_events"],
                "audit/round_events.jsonl",
            )

            package = load_audit_package(package_dir)
            query = AuditQuery(package)
            self.assertEqual(query.list_rounds(), ("round-1",))
            self.assertEqual(
                [event.kind for event in query.list_round_events("round-1")],
                ["round_started", "check_result", "round_finalized"],
            )
            self.assertEqual(query.get_round_event("round-1", 1).kind, "check_result")
            summary = query.get_round_summary("round-1")
            self.assertIsNotNone(summary)
            self.assertTrue(summary.is_finalized)
            self.assertEqual(summary.event_count, 1)
            self.assertEqual(summary.kind_counts["check_result"], 1)
            self.assertEqual(summary.sequence_gaps, ())

    def test_old_package_without_round_events_loads_empty(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir)
            package = load_audit_package(package_dir)
            self.assertEqual(package.round_events, ())
            self.assertEqual(package.round_event_warnings, ())
            self.assertEqual(AuditQuery(package).list_rounds(), ())

    def test_lenient_reader_handles_malformed_duplicate_unknown_and_gaps(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir, include_round_events=True)
            rows = [
                {"not": "valid"},
                {
                    "round_id": "round-1",
                    "sequence": 0,
                    "event_ts": 100,
                    "kind": "round_started",
                    "schema_version": "1.0",
                    "payload": {"started_at": 100},
                },
                {
                    "round_id": "round-1",
                    "sequence": 0,
                    "event_ts": 101,
                    "kind": "round_started",
                    "schema_version": "1.0",
                    "payload": {"started_at": 101},
                },
                {
                    "round_id": "round-1",
                    "sequence": 2,
                    "event_ts": 102,
                    "kind": "future_kind",
                    "schema_version": "1.0",
                    "payload": {"raw": True},
                },
            ]
            round_events_path = package_dir / "audit" / "round_events.jsonl"
            round_events_path.write_text(
                "{bad json}\n"
                + "\n".join(json.dumps(row, sort_keys=True) for row in rows)
                + "\n",
                encoding="utf-8",
            )

            package = load_audit_package(package_dir)
            query = AuditQuery(package)
            self.assertEqual(
                [warning.code for warning in query.list_round_event_warnings()],
                [
                    "ROUND_EVENT_MALFORMED",
                    "ROUND_EVENT_MALFORMED",
                    "ROUND_EVENT_DUPLICATE",
                ],
            )
            self.assertEqual(
                [event.kind for event in query.list_round_events("round-1")],
                ["round_started", "future_kind"],
            )
            summary = query.get_round_summary("round-1")
            self.assertIsNotNone(summary)
            self.assertFalse(summary.is_finalized)
            self.assertEqual(summary.sequence_gaps, (1,))

    def test_recorder_rejects_empty_round_and_lifecycle_order_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "round_id"):
            start_round("")

        recorder = RoundRecorder("round-1")
        with self.assertRaisesRegex(ValueError, "started"):
            record_round_event(recorder, kind="check_result", payload={})

        recorder.start(event_ts=100)
        with self.assertRaisesRegex(ValueError, "lifecycle"):
            record_round_event(recorder, kind="round_finalized", payload={})

    def test_finalize_is_atomic_and_writes_only_at_finalize(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir)
            recorder = start_round("round-1", event_ts=100)
            record_round_event(recorder, kind="proof_frame_result", payload={}, event_ts=101)
            self.assertFalse((package_dir / "audit" / "round_events.jsonl").exists())
            finalize_round(recorder, package_dir, event_ts=102)
            self.assertTrue((package_dir / "audit" / "round_events.jsonl").exists())

    def test_projection_helpers_emit_stable_json_shape(self) -> None:
        binding = normalize_binding_items((("$p", "alice"), ("$age", 30)))
        plan = SimpleNamespace(
            derivation_id="drv",
            version="1.0",
            body_ir=[("pred", "Person:age", ["$p", "$age"])],
            heads=(
                SimpleNamespace(target_pred_id="Eligible", head_var_names=("$p",)),
            ),
        )
        request = SimpleNamespace(plan=plan, binding=binding, engine="native")
        result = SimpleNamespace(
            status="passed",
            requested_binding=binding,
            matched_count=1,
            matched_binding=binding,
            evidence_envelope=None,
            errors=(),
            warnings=(),
        )
        payload = project_check_event_payload(request, result)
        self.assertEqual(payload["request"]["binding"], [["$age", 30], ["$p", "alice"]])
        self.assertEqual(payload["result"]["status"], "passed")
        self.assertTrue(payload["request"]["plan_digest"].startswith("sha256:"))

        diagnose_payload = project_diagnose_event_payload(
            request,
            SimpleNamespace(
                status="failed",
                requested_binding=binding,
                matched_count=0,
                matched_binding=None,
                failure_kind="atom_localized",
                diagnostic_payload=DiagnoseAtomLocator(
                    branch_index=0,
                    failed_atom_index=1,
                    attempted_binding=binding,
                ),
                errors=(),
                warnings=(),
            ),
        )
        self.assertEqual(
            diagnose_payload["result"]["diagnostic_payload"],
            {
                "branch_index": 0,
                "failed_atom_index": 1,
                "attempted_binding": [["$age", 30], ["$p", "alice"]],
            },
        )

        fact_overlay_payload = project_fact_overlay_event_payload(
            SimpleNamespace(plan=plan, binding=binding, overlay=("opaque",), engine="native"),
            SimpleNamespace(
                status="passed",
                requested_binding=binding,
                before=SimpleNamespace(status="passed", matched_binding=binding),
                after=SimpleNamespace(status="failed", matched_binding=None),
                diff=SimpleNamespace(
                    status_changed=True,
                    matched_count_delta=-1,
                    bindings_added=(),
                    bindings_removed=(binding,),
                ),
                errors=(),
                warnings=(),
            ),
        )
        self.assertEqual(
            fact_overlay_payload["result"]["diff"]["bindings_removed"],
            [[["$age", 30], ["$p", "alice"]]],
        )

        why_not_payload = project_why_not_event_payload(
            SimpleNamespace(plan=plan, candidate_universe=(binding,), engine="native"),
            SimpleNamespace(
                status="completed",
                requested_universe=(binding,),
                green=(),
                red=(
                    SimpleNamespace(
                        binding=binding,
                        diagnostic=SimpleNamespace(
                            status="failed",
                            failure_kind="atom_localized",
                            diagnostic_granularity="atom_localized",
                            atom_locator=SimpleNamespace(
                                branch_index=0,
                                failed_atom_index=1,
                                attempted_binding=binding,
                            ),
                            errors=(),
                            warnings=(),
                        ),
                    ),
                ),
                errors=(),
                warnings=(),
            ),
        )
        self.assertEqual(
            why_not_payload["result"]["red"][0]["diagnostic"]["atom_locator"]["failed_atom_index"],
            1,
        )

        proof_frame_payload = project_proof_frame_event_payload(
            SimpleNamespace(support_artifact=None, overlay=("opaque",)),
            SimpleNamespace(
                status="invalidated",
                binding_items=binding,
                atom_verdicts=(
                    SimpleNamespace(
                        atom_key="b0.add0:gt",
                        verdict="invalidated",
                        affected_action_indices=(0,),
                    ),
                ),
            ),
        )
        self.assertEqual(
            proof_frame_payload["result"]["atom_verdicts"],
            [
                {
                    "atom_key": "b0.add0:gt",
                    "verdict": "invalidated",
                    "affected_action_indices": [0],
                }
            ],
        )

    def test_application_runtimes_do_not_import_audit(self) -> None:
        app_dir = Path(__file__).resolve().parents[1] / "application"
        offenders: list[str] = []
        for path in app_dir.glob("*runtime*.py"):
            text = path.read_text(encoding="utf-8")
            if "factgraph.audit" in text or "from factgraph import audit" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_full_first_slice_round_trip_with_lifecycle_consistency(self) -> None:
        """T1/T2/T9/T15: all 5 capability kinds + lifecycle round-trip with schema_version + event_count consistency."""
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir)
            recorder = start_round("round-full", event_ts=100)
            kinds = [
                "check_result",
                "diagnose_result",
                "fact_overlay_result",
                "why_not_result",
                "proof_frame_result",
            ]
            for offset, kind in enumerate(kinds, start=1):
                record_round_event(
                    recorder,
                    kind=kind,
                    payload={"placeholder": kind},
                    event_ts=100 + offset,
                )
            finalize_round(recorder, package_dir, event_ts=200)

            package = load_audit_package(package_dir)
            query = AuditQuery(package)
            events = query.list_round_events("round-full")
            self.assertEqual(
                [event.kind for event in events],
                ["round_started", *kinds, "round_finalized"],
            )
            for event in events:
                self.assertEqual(event.schema_version, "1.0")
            finalized = events[-1]
            self.assertEqual(finalized.kind, "round_finalized")
            self.assertEqual(finalized.payload["event_count"], 5)
            self.assertEqual(
                dict(finalized.payload["kind_counts"]),
                {kind: 1 for kind in kinds},
            )
            summary = query.get_round_summary("round-full")
            self.assertIsNotNone(summary)
            self.assertEqual(summary.event_count, 5)
            self.assertTrue(summary.is_finalized)

    def test_finalize_is_retry_safe_on_write_failure(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir)
            recorder = start_round("round-1", event_ts=100)
            record_round_event(recorder, kind="check_result", payload={}, event_ts=101)
            (package_dir / "manifest.json").unlink()
            with self.assertRaises(RoundEventError):
                finalize_round(recorder, package_dir, event_ts=102)
            self.assertEqual(len(recorder.events), 2)
            self.assertFalse(any(e.kind == "round_finalized" for e in recorder.events))
            manifest = {
                "package_kind": "audit",
                "paths": {"audit_files": {"run_ledger": "audit/run_ledger.jsonl"}},
            }
            (package_dir / "manifest.json").write_text(
                json.dumps(manifest, sort_keys=True), encoding="utf-8"
            )
            path = finalize_round(recorder, package_dir, event_ts=102)
            self.assertTrue(path.exists())
            self.assertTrue(any(e.kind == "round_finalized" for e in recorder.events))

    def test_multi_round_packages_preserve_prior_rounds(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir)
            recorder1 = start_round("round-1", event_ts=100)
            record_round_event(recorder1, kind="check_result", payload={}, event_ts=101)
            finalize_round(recorder1, package_dir, event_ts=102)
            recorder2 = start_round("round-2", event_ts=200)
            record_round_event(recorder2, kind="diagnose_result", payload={}, event_ts=201)
            finalize_round(recorder2, package_dir, event_ts=202)

            package = load_audit_package(package_dir)
            query = AuditQuery(package)
            self.assertEqual(set(query.list_rounds()), {"round-1", "round-2"})
            round1 = query.list_round_events("round-1")
            round2 = query.list_round_events("round-2")
            self.assertEqual(
                [e.kind for e in round1],
                ["round_started", "check_result", "round_finalized"],
            )
            self.assertEqual(
                [e.kind for e in round2],
                ["round_started", "diagnose_result", "round_finalized"],
            )

    def test_v2_schema_rows_treated_as_unknown_kind(self) -> None:
        with TemporaryDirectory() as tmpdir:
            package_dir = _minimal_audit_package(tmpdir, include_round_events=True)
            rows = [
                {
                    "round_id": "round-1",
                    "sequence": 0,
                    "event_ts": 100,
                    "kind": "check_result",
                    "schema_version": "2.0",
                    "payload": {"new_v2_shape": True},
                }
            ]
            (package_dir / "audit" / "round_events.jsonl").write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )
            package = load_audit_package(package_dir)
            query = AuditQuery(package)
            self.assertEqual(query.list_round_events("round-1", kind="check_result"), ())
            all_events = query.list_round_events("round-1")
            self.assertEqual(len(all_events), 1)
            self.assertNotEqual(all_events[0].kind, "check_result")
            self.assertTrue(all_events[0].kind.startswith("future:"))


def _minimal_audit_package(
    tmpdir: str,
    *,
    include_round_events: bool = False,
) -> Path:
    package_dir = Path(tmpdir) / "audit_pkg"
    audit_dir = package_dir / "audit"
    audit_dir.mkdir(parents=True)
    audit_files = {
        "run_ledger": "audit/run_ledger.jsonl",
        "candidate_ledger": "audit/candidate_ledger.jsonl",
        "accept_write_ledger": "audit/accept_write_ledger.jsonl",
        "accept_failed": "audit/accept_failed.jsonl",
        "mapping_resolution": "audit/mapping_resolution.json",
        "decision_log": "audit/decision_log.jsonl",
    }
    if include_round_events:
        audit_files["round_events"] = "audit/round_events.jsonl"
    for key, rel in audit_files.items():
        path = package_dir / rel
        if key == "mapping_resolution":
            path.write_text("{}", encoding="utf-8")
        elif key != "round_events":
            path.write_text("", encoding="utf-8")
    manifest = {
        "package_kind": "audit",
        "paths": {
            "audit_files": audit_files,
        },
    }
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True),
        encoding="utf-8",
    )
    return package_dir


if __name__ == "__main__":
    unittest.main()
