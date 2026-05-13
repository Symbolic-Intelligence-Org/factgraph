"""Cross-cutting walker invariant tests for B Phase 6.

Pickling / cross-process serialization is not part of the walker contract.
Callers who need serialization should use `.underlying` and serialize the
raw DTO through its owning layer.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

import kernel.application.walker as walker_package
from kernel.application.protocol.common import WarningDTO
from kernel.application.protocol.proofframe import ProofFrameAtomVerdict, ProofFrameRecheckResult
from kernel.application.walker import (
    AssertionView,
    FrozenTupleView,
    IRBodyWalker,
    ProofFrameDiffView,
    ProofFrameView,
    SupportArtifactView,
    WalkerFrozenError,
)
from kernel.application.walker.keys import parse_atom_key
from kernel.audit.proof_frame_diff import (
    AtomDelta,
    EventReference,
    FrameDelta,
    FrameIdentity,
    FrameStatusChange,
    ProofFrameDiff,
)
from kernel.core.store._support import NonFactStep, PredWitness, SupportArtifact
from kernel.core.store.ledger import Claim


def _claim() -> Claim:
    return Claim("a1", "Person:age", "person:alice", [("value", 40)])


def _support_artifact() -> SupportArtifact:
    return SupportArtifact(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=(("$p", "person:alice"),),
        pred_witnesses=(
            PredWitness(pred_atom_key="b0.a0:Person:age", asrt_ids=("a1",)),
        ),
        non_fact_steps=(
            NonFactStep(step_key="b0.a1:eq", kind="eq", status="satisfied"),
        ),
    )


def _proof_frame_result() -> ProofFrameRecheckResult:
    return ProofFrameRecheckResult(
        status="invalidated",
        binding_items=(("$p", "person:alice"),),
        atom_verdicts=(
            ProofFrameAtomVerdict(
                atom_key="b0.a0:Person:age",
                verdict="invalidated",
                affected_action_indices=(0,),
            ),
        ),
    )


def _proof_frame_diff() -> ProofFrameDiff:
    return ProofFrameDiff(
        round_a_id="round-a",
        round_b_id="round-b",
        frame_deltas=(
            FrameDelta(
                frame_identity=FrameIdentity(
                    support_digest="support:alice",
                    binding_items=(("$attrs", {"tags": ["vip"]}),),
                ),
                source_a=EventReference("round-a", 1),
                source_b=EventReference("round-b", 1),
                frame_status_change=FrameStatusChange(before="still_valid", after="invalidated"),
                atom_deltas=(
                    AtomDelta(
                        atom_key="b0.a0:Person:age",
                        kind="atom_verdict_changed",
                        before_verdict="still_valid",
                        after_verdict="invalidated",
                    ),
                ),
            ),
        ),
        warnings=(
            WarningDTO(
                "RULE_REFS_UNSUPPORTED",
                "rule refs skipped",
                details={"markers": ["rule_refs_unsupported"]},
            ),
        ),
    )


def _view_fixtures() -> tuple[tuple[str, object], ...]:
    support = _support_artifact()
    claim = _claim()
    proof_frame = _proof_frame_result()
    proof_diff = _proof_frame_diff()
    walker = IRBodyWalker([("pred", "Person:age", ["$p", "$age"])])
    atom = next(iter(walker))

    return (
        ("IRBodyWalker", walker),
        ("IRAtomView", atom),
        ("FrozenTupleView", FrozenTupleView((atom,))),
        ("AtomKeyView", parse_atom_key("b0.a0:Person:age")),
        ("SupportArtifactView", SupportArtifactView(support, {"a1": claim})),
        ("AssertionView", AssertionView("a1", {"a1": claim})),
        ("ProofFrameView", ProofFrameView(proof_frame)),
        ("ProofFrameDiffView", ProofFrameDiffView(proof_diff)),
    )


class WalkerInvariantTests(unittest.TestCase):
    def test_all_view_instances_are_frozen_for_set_and_delete(self) -> None:
        for name, instance in _view_fixtures():
            with self.subTest(view=name, action="set"):
                with self.assertRaises(WalkerFrozenError):
                    instance._phase6_mutation_probe = "blocked"  # type: ignore[attr-defined]
            with self.subTest(view=name, action="delete"):
                with self.assertRaises(WalkerFrozenError):
                    del instance.underlying  # type: ignore[misc]

    def test_all_view_instances_expose_underlying_escape_hatch(self) -> None:
        for name, instance in _view_fixtures():
            with self.subTest(view=name):
                self.assertTrue(hasattr(instance, "underlying"))

    def test_no_forbidden_aliases_or_legacy_accessors(self) -> None:
        forbidden = ("source", "carrier", "raw", "get", "at")
        for name, instance in _view_fixtures():
            for attr in forbidden:
                with self.subTest(view=name, attr=attr):
                    self.assertFalse(callable(getattr(instance, attr, None)))
                    self.assertFalse(hasattr(instance, attr))

    def test_source_id_is_limited_to_expected_source_aware_views(self) -> None:
        allowed = {"IRBodyWalker", "FrozenTupleView", "SupportArtifactView"}
        for name, instance in _view_fixtures():
            with self.subTest(view=name):
                self.assertEqual(hasattr(instance, "source_id"), name in allowed)

    def test_no_stats_attribute(self) -> None:
        for name, instance in _view_fixtures():
            with self.subTest(view=name):
                self.assertFalse(hasattr(instance, "stats"))

    def test_walker_package_does_not_import_sdk(self) -> None:
        for path, source in _walker_sources().items():
            with self.subTest(path=path.name):
                self.assertNotIn("kernel.sdk", source)
                self.assertNotIn("from kernel import sdk", source)
                self.assertNotIn("import sdk", source)

    def test_unbounded_stream_error_has_no_b1_b2_raise_site(self) -> None:
        for path, source in _walker_sources().items():
            if path.name == "errors.py":
                continue
            with self.subTest(path=path.name):
                self.assertNotIn("raise UnboundedStreamError", source)
                self.assertNotIn("UnboundedStreamError(", source)

    def test_same_input_instances_have_deterministic_observable_surface(self) -> None:
        first = dict(_view_fixtures())
        second = dict(_view_fixtures())

        for name in first:
            with self.subTest(view=name):
                first_surface = _deterministic_surface(first[name])
                second_surface = _deterministic_surface(second[name])

                self.assertEqual(first_surface, second_surface)
                self.assertEqual(hash(first_surface), hash(second_surface))

    def test_module_docstring_records_single_thread_contract(self) -> None:
        doc = walker_package.__doc__ or ""

        self.assertIn("single-thread", doc)
        self.assertIn("share frozen source DTOs", doc)

    def test_module_docstring_records_b3_future_only_contract(self) -> None:
        doc = walker_package.__doc__ or ""

        self.assertIn("B3", doc)
        self.assertIn("future-only", doc)
        self.assertIn("no raise site", doc)


def _walker_sources() -> dict[Path, str]:
    walker_dir = Path(walker_package.__file__).parent
    return {
        path: path.read_text(encoding="utf-8")
        for path in walker_dir.rglob("*.py")
    }


def _deterministic_surface(instance: object) -> Any:
    if isinstance(instance, IRBodyWalker):
        return tuple(instance)
    if isinstance(instance, SupportArtifactView):
        return (
            instance.pred_witnesses.underlying,
            instance.non_fact_steps.underlying,
            instance.lookup_assertion("a1"),
        )
    return instance


if __name__ == "__main__":
    unittest.main()
