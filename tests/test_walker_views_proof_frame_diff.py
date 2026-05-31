"""ProofFrameDiffView tests for B Phase 5."""

from __future__ import annotations

import unittest

from factgraph.application.protocol.common import WarningDTO
from factgraph.application.walker import (
    FrozenTupleView,
    ProofFrameDiffView,
    WalkerFrozenError,
)
from factgraph.audit.proof_frame_diff import (
    AtomDelta,
    EventReference,
    FrameDelta,
    FrameIdentity,
    FrameStatusChange,
    ProofFrameDiff,
)


def _event(round_id: str, sequence: int) -> EventReference:
    return EventReference(round_id=round_id, sequence=sequence)


def _identity(name: str) -> FrameIdentity:
    return FrameIdentity(
        support_digest=f"support:{name}",
        binding_items=(("$p", f"person:{name}"),),
    )


def _nested_identity(name: str) -> FrameIdentity:
    return FrameIdentity(
        support_digest=f"support:{name}",
        binding_items=(("$attrs", {"tags": ["vip", "active"]}),),
    )


def _status_changed_frame() -> FrameDelta:
    return FrameDelta(
        frame_identity=_identity("alice"),
        source_a=_event("round-a", 1),
        source_b=_event("round-b", 1),
        frame_status_change=FrameStatusChange(before="still_valid", after="invalidated"),
        atom_deltas=(
            AtomDelta(
                condition_key="c0.c0:Person:age",
                kind="atom_verdict_changed",
                before_verdict="still_valid",
                after_verdict="invalidated",
            ),
        ),
    )


def _atom_added_frame() -> FrameDelta:
    return FrameDelta(
        frame_identity=_identity("bob"),
        source_a=None,
        source_b=_event("round-b", 2),
        frame_status_change=None,
        atom_deltas=(
            AtomDelta(
                condition_key="c0.c1:Person:status",
                kind="atom_added",
                before_verdict=None,
                after_verdict="still_valid",
            ),
        ),
    )


def _marker_frame() -> FrameDelta:
    return FrameDelta(
        frame_identity=_identity("carol"),
        source_a=_event("round-a", 3),
        source_b=_event("round-b", 3),
        frame_status_change=None,
        markers=("rule_refs_unsupported",),
    )


def _proof_frame_diff() -> ProofFrameDiff:
    return ProofFrameDiff(
        round_a_id="round-a",
        round_b_id="round-b",
        frame_deltas=(
            _status_changed_frame(),
            _atom_added_frame(),
            _marker_frame(),
        ),
        warnings=(
            WarningDTO(
                code="RULE_REFS_UNSUPPORTED",
                message="rule refs skipped",
                path=("frames", "2"),
                details={"markers": ["rule_refs_unsupported"]},
            ),
        ),
    )


class ProofFrameDiffViewTests(unittest.TestCase):
    def test_wraps_proof_frame_diff_fields(self) -> None:
        diff = _proof_frame_diff()
        view = ProofFrameDiffView(diff)

        self.assertIs(view.underlying, diff)
        self.assertEqual(view.round_a_id, "round-a")
        self.assertEqual(view.round_b_id, "round-b")
        self.assertIsInstance(view.frame_deltas, FrozenTupleView)
        self.assertIsInstance(view.warnings, FrozenTupleView)
        self.assertIs(view.frame_deltas[0], diff.frame_deltas[0])
        self.assertIs(view.warnings[0], diff.warnings[0])

    def test_constructor_requires_proof_frame_diff(self) -> None:
        with self.assertRaises(TypeError):
            ProofFrameDiffView(object())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            ProofFrameDiffView(_proof_frame_diff(), source_id="diff-1")  # type: ignore[call-arg]

    def test_frames_with_status_change_returns_changed_frames(self) -> None:
        view = ProofFrameDiffView(_proof_frame_diff())

        changed = view.frames_with_status_change()

        self.assertIsInstance(changed, FrozenTupleView)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed.first().frame_identity.support_digest, "support:alice")

    def test_iter_atom_deltas_returns_all_or_kind_filtered(self) -> None:
        view = ProofFrameDiffView(_proof_frame_diff())

        all_deltas = tuple(view.iter_atom_deltas())
        changed = tuple(view.iter_atom_deltas(kind="atom_verdict_changed"))
        added = tuple(view.iter_atom_deltas(kind="atom_added"))

        self.assertEqual([delta.kind for delta in all_deltas], ["atom_verdict_changed", "atom_added"])
        self.assertEqual([delta.condition_key for delta in changed], ["c0.c0:Person:age"])
        self.assertEqual([delta.condition_key for delta in added], ["c0.c1:Person:status"])

    def test_frames_with_atom_verdict_changes_returns_changed_atom_frames(self) -> None:
        view = ProofFrameDiffView(_proof_frame_diff())

        frames = view.frames_with_atom_verdict_changes()

        self.assertIsInstance(frames, FrozenTupleView)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames.first().frame_identity.support_digest, "support:alice")

    def test_frame_deltas_support_generic_filter_find_and_require_key(self) -> None:
        view = ProofFrameDiffView(_proof_frame_diff())

        marker_frames = view.frame_deltas.filter(markers=("rule_refs_unsupported",))
        found = view.frame_deltas.find(frame_identity=_identity("bob"))
        required = view.frame_deltas.require_key(_identity("alice"), key=lambda frame: frame.frame_identity)

        self.assertEqual(len(marker_frames), 1)
        self.assertEqual(found.source_b.round_id, "round-b")
        self.assertEqual(required.frame_status_change.after, "invalidated")

    def test_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        view = ProofFrameDiffView(_proof_frame_diff())

        with self.assertRaises(WalkerFrozenError):
            view.round_a_id = "other"  # type: ignore[misc]

        self.assertFalse(hasattr(view, "source"))
        self.assertFalse(hasattr(view, "carrier"))
        self.assertFalse(hasattr(view, "raw"))
        self.assertFalse(hasattr(view, "source_id"))

    def test_equality_and_hash_exclude_underlying_and_freeze_warning_surface(self) -> None:
        a = ProofFrameDiffView(_proof_frame_diff())
        b = ProofFrameDiffView(_proof_frame_diff())
        c = ProofFrameDiffView(
            ProofFrameDiff(
                round_a_id="round-a",
                round_b_id="round-c",
                frame_deltas=(_status_changed_frame(),),
                warnings=(),
            )
        )

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertIsInstance(hash(a), int)
        self.assertNotEqual(a, c)

    def test_hash_with_nested_json_binding_values(self) -> None:
        diff = ProofFrameDiff(
            round_a_id="round-a",
            round_b_id="round-b",
            frame_deltas=(
                FrameDelta(
                    frame_identity=_nested_identity("alice"),
                    source_a=_event("round-a", 1),
                    source_b=None,
                    frame_status_change=None,
                ),
            ),
        )
        same = ProofFrameDiffView(diff)
        equal = ProofFrameDiffView(diff)

        diff.frame_deltas[0].frame_identity.binding_items[0][1]["tags"].append("late")

        self.assertEqual(same, equal)
        self.assertEqual(hash(same), hash(equal))
        self.assertIsInstance(hash(same), int)

    def test_phase_5_type_reexports_from_application_package(self) -> None:
        from factgraph.application import ProofFrameDiffView as AppProofFrameDiffView

        self.assertIs(AppProofFrameDiffView, ProofFrameDiffView)


if __name__ == "__main__":
    unittest.main()
