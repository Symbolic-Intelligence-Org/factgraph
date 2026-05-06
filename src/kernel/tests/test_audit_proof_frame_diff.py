from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import unittest

from kernel.audit import AuditPackageData, AuditQuery, AuditQueryError
from kernel.audit.proof_frame_diff import (
    AtomDelta,
    EventReference,
    FrameIdentity,
    ProofFrameDiff,
)
from kernel.audit.round_events import RoundEvent


class AuditProofFrameDiffTests(unittest.TestCase):
    def test_identical_rounds_omit_deltas_and_are_deterministic(self) -> None:
        package = _package(
            [
                *_round("round-a", [_proof_payload()]),
                *_round("round-b", [_proof_payload()]),
            ]
        )
        query = AuditQuery(package)

        first = query.diff_proof_frames("round-a", "round-b")
        second = query.diff_proof_frames("round-a", "round-b")

        self.assertEqual(first.frame_deltas, ())
        self.assertEqual(first, second)
        self.assertNotIn("generated_at_ns", {field.name for field in fields(ProofFrameDiff)})
        self.assertNotIn("affected_action_indices", {field.name for field in fields(AtomDelta)})

    def test_frame_added_removed_and_event_reference_sources(self) -> None:
        package = _package(
            [
                *_round("round-a", [_proof_payload(support_digest="sha256:a")]),
                *_round("round-b", [_proof_payload(support_digest="sha256:b")]),
            ]
        )
        diff = AuditQuery(package).diff_proof_frames("round-a", "round-b")

        self.assertEqual(len(diff.frame_deltas), 2)
        removed, added = diff.frame_deltas
        self.assertIsInstance(removed.source_a, EventReference)
        self.assertIsNone(removed.source_b)
        self.assertIsNone(added.source_a)
        self.assertIsInstance(added.source_b, EventReference)
        self.assertEqual(removed.frame_identity.support_digest, "sha256:a")
        self.assertEqual(added.frame_identity.support_digest, "sha256:b")

    def test_status_and_atom_verdict_changes_same_support_digest(self) -> None:
        package = _package(
            [
                *_round(
                    "round-a",
                    [
                        _proof_payload(
                            status="still_valid",
                            atoms={"b0.a0:pred": "still_valid"},
                        )
                    ],
                ),
                *_round(
                    "round-b",
                    [
                        _proof_payload(
                            status="invalidated",
                            atoms={"b0.a0:pred": "invalidated"},
                        )
                    ],
                ),
            ]
        )
        diff = AuditQuery(package).diff_proof_frames("round-a", "round-b")

        self.assertEqual(len(diff.frame_deltas), 1)
        delta = diff.frame_deltas[0]
        self.assertIsNotNone(delta.frame_status_change)
        self.assertEqual(delta.frame_status_change.before, "still_valid")
        self.assertEqual(delta.frame_status_change.after, "invalidated")
        self.assertEqual(len(delta.atom_deltas), 1)
        self.assertEqual(delta.atom_deltas[0].kind, "atom_verdict_changed")
        self.assertEqual(delta.atom_deltas[0].before_verdict, "still_valid")
        self.assertEqual(delta.atom_deltas[0].after_verdict, "invalidated")

    def test_atom_set_diff_reports_added_and_removed(self) -> None:
        package = _package(
            [
                *_round("round-a", [_proof_payload(atoms={"b0.a0:pred": "still_valid"})]),
                *_round("round-b", [_proof_payload(atoms={"b0.a1:gt": "still_valid"})]),
            ]
        )
        diff = AuditQuery(package).diff_proof_frames("round-a", "round-b")

        kinds = {delta.kind for delta in diff.frame_deltas[0].atom_deltas}
        self.assertEqual(kinds, {"atom_added", "atom_removed"})
        by_kind = {delta.kind: delta for delta in diff.frame_deltas[0].atom_deltas}
        self.assertEqual(by_kind["atom_removed"].atom_key, "b0.a0:pred")
        self.assertEqual(by_kind["atom_added"].atom_key, "b0.a1:gt")

    def test_rule_ref_degenerate_frames_are_marked_without_atom_deltas(self) -> None:
        for payloads, expected_status_change in (
            (
                (
                    _proof_payload(status="unknown", atoms={}),
                    _proof_payload(status="unknown", atoms={}),
                ),
                None,
            ),
            (
                (
                    _proof_payload(status="unknown", atoms={}),
                    _proof_payload(status="still_valid", atoms={"b0.a0:pred": "still_valid"}),
                ),
                ("unknown", "still_valid"),
            ),
        ):
            with self.subTest(payloads=payloads):
                package = _package(
                    [
                        *_round("round-a", [payloads[0]]),
                        *_round("round-b", [payloads[1]]),
                    ]
                )
                diff = AuditQuery(package).diff_proof_frames("round-a", "round-b")

                self.assertEqual(len(diff.frame_deltas), 1)
                delta = diff.frame_deltas[0]
                self.assertEqual(delta.markers, ("rule_refs_unsupported",))
                self.assertEqual(delta.atom_deltas, ())
                if expected_status_change is None:
                    self.assertIsNone(delta.frame_status_change)
                else:
                    self.assertIsNotNone(delta.frame_status_change)
                    self.assertEqual(delta.frame_status_change.before, expected_status_change[0])
                    self.assertEqual(delta.frame_status_change.after, expected_status_change[1])

    def test_partial_round_policy_default_rejects_and_opt_in_warns(self) -> None:
        package = _package(
            [
                *_round("round-a", [_proof_payload()]),
                *_round("round-b", [_proof_payload()], finalized=False),
            ]
        )
        query = AuditQuery(package)

        with self.assertRaisesRegex(AuditQueryError, "round-b is not finalized"):
            query.diff_proof_frames("round-a", "round-b")

        diff = query.diff_proof_frames("round-a", "round-b", include_partial=True)
        self.assertEqual([warning.code for warning in diff.warnings], ["DIFF_INCLUDES_PARTIAL_ROUND"])
        self.assertEqual(diff.warnings[0].details["round_id"], "round-b")

    def test_future_proof_frame_rows_are_skipped_with_warning(self) -> None:
        package = _package(
            [
                *_round("round-a", [_proof_payload()]),
                *_round(
                    "round-b",
                    [_proof_payload()],
                    extra_events=[
                        RoundEvent(
                            round_id="round-b",
                            sequence=2,
                            event_ts=102,
                            kind="future:proof_frame_result",
                            schema_version="2.0",
                            payload={"future": True},
                        )
                    ],
                    finalize_sequence=3,
                ),
            ]
        )

        diff = AuditQuery(package).diff_proof_frames("round-a", "round-b")

        self.assertEqual([warning.code for warning in diff.warnings], ["DIFF_FUTURE_KIND_SKIPPED"])
        self.assertEqual(diff.warnings[0].details["round_id"], "round-b")
        self.assertEqual(diff.warnings[0].details["skipped_count"], 1)

    def test_include_unchanged_emits_unchanged_frame(self) -> None:
        package = _package(
            [
                *_round("round-a", [_proof_payload()]),
                *_round("round-b", [_proof_payload()]),
            ]
        )

        diff = AuditQuery(package).diff_proof_frames(
            "round-a",
            "round-b",
            include_unchanged=True,
        )

        self.assertEqual(len(diff.frame_deltas), 1)
        delta = diff.frame_deltas[0]
        self.assertIsNone(delta.frame_status_change)
        self.assertEqual(delta.atom_deltas, ())
        self.assertEqual(delta.markers, ())

    def test_missing_round_raises_query_error(self) -> None:
        package = _package([*_round("round-a", [_proof_payload()])])
        with self.assertRaisesRegex(AuditQueryError, "round missing not found"):
            AuditQuery(package).diff_proof_frames("round-a", "missing")

    def test_existing_round_query_methods_stay_stable(self) -> None:
        package = _package([*_round("round-a", [_proof_payload()])])
        query = AuditQuery(package)

        self.assertEqual(query.list_rounds(), ("round-a",))
        self.assertEqual(
            [event.kind for event in query.list_round_events("round-a")],
            ["round_started", "proof_frame_result", "round_finalized"],
        )
        self.assertEqual(query.get_round_event("round-a", 1).kind, "proof_frame_result")
        self.assertTrue(query.get_round_summary("round-a").is_finalized)

    def test_application_runtimes_do_not_import_audit(self) -> None:
        app_dir = Path(__file__).resolve().parents[1] / "application"
        offenders: list[str] = []
        for path in app_dir.glob("*runtime*.py"):
            text = path.read_text(encoding="utf-8")
            if "kernel.audit" in text or "from kernel import audit" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_frame_identity_is_canonical_binding_json(self) -> None:
        identity = FrameIdentity(
            support_digest="sha256:support",
            binding_items=(("$p", "alice"), ("$age", 30)),
        )
        self.assertEqual(identity.binding_items, (("$age", 30), ("$p", "alice")))


def _package(events: list[RoundEvent]) -> AuditPackageData:
    return AuditPackageData(
        package_dir=Path("/tmp/audit_pkg"),
        manifest={},
        run_manifest=None,
        run_ledger=[],
        candidate_ledger=[],
        accept_write_ledger=[],
        decision_log=[],
        accept_failed=[],
        mapping_resolution=None,
        support_artifacts=[],
        rule_trace_artifacts=[],
        authoring_apply_events=[],
        certainty_summaries={},
        provenance_trees={},
        provenance_statuses={},
        evidence_graphs={},
        assertion_annotations=[],
        provenance_timelines={},
        round_events=tuple(events),
        round_event_warnings=(),
    )


def _round(
    round_id: str,
    proof_payloads: list[dict],
    *,
    finalized: bool = True,
    extra_events: list[RoundEvent] | None = None,
    finalize_sequence: int | None = None,
) -> list[RoundEvent]:
    events = [
        RoundEvent(
            round_id=round_id,
            sequence=0,
            event_ts=100,
            kind="round_started",
            schema_version="1.0",
            payload={"started_at": 100},
        )
    ]
    sequence = 1
    for payload in proof_payloads:
        events.append(
            RoundEvent(
                round_id=round_id,
                sequence=sequence,
                event_ts=100 + sequence,
                kind="proof_frame_result",
                schema_version="1.0",
                payload=payload,
            )
        )
        sequence += 1
    if extra_events:
        events.extend(extra_events)
        sequence = max(event.sequence for event in events) + 1
    if finalized:
        events.append(
            RoundEvent(
                round_id=round_id,
                sequence=finalize_sequence if finalize_sequence is not None else sequence,
                event_ts=200,
                kind="round_finalized",
                schema_version="1.0",
                payload={"finalized_at": 200, "event_count": len(proof_payloads), "kind_counts": {}},
            )
        )
    return events


def _proof_payload(
    *,
    support_digest: str = "sha256:support",
    binding: list[list[object]] | None = None,
    status: str = "still_valid",
    atoms: dict[str, str] | None = None,
) -> dict:
    if binding is None:
        binding = [["$p", "alice"]]
    if atoms is None:
        atoms = {"b0.a0:pred": "still_valid"}
    return {
        "request": {
            "support_digest": support_digest,
            "overlay_digest": "sha256:overlay",
        },
        "result": {
            "status": status,
            "binding_items": binding,
            "atom_verdicts": [
                {
                    "atom_key": atom_key,
                    "verdict": verdict,
                    "affected_action_indices": [0],
                }
                for atom_key, verdict in atoms.items()
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
