"""ProofFrameView tests for B Phase 4."""

from __future__ import annotations

import unittest

from kernel.application.protocol.proofframe import (
    ProofFrameAtomVerdict,
    ProofFrameRecheckResult,
)
from kernel.application.walker import (
    FrozenTupleView,
    ProofFrameView,
    WalkerFrozenError,
)


def _proof_frame_result() -> ProofFrameRecheckResult:
    return ProofFrameRecheckResult(
        status="invalidated",
        binding_items=(
            ("$attrs", {"tags": ["vip", "active"]}),
            ("$p", "person:alice"),
        ),
        atom_verdicts=(
            ProofFrameAtomVerdict(
                atom_key="b0.a0:Person:age",
                verdict="still_valid",
                affected_action_indices=(),
            ),
            ProofFrameAtomVerdict(
                atom_key="b0.a1:eq",
                verdict="invalidated",
                affected_action_indices=(0,),
            ),
        ),
    )


class ProofFrameViewTests(unittest.TestCase):
    def test_wraps_proof_frame_result_fields(self) -> None:
        result = _proof_frame_result()
        view = ProofFrameView(result)

        self.assertIs(view.underlying, result)
        self.assertEqual(view.status, "invalidated")
        self.assertEqual(
            view.binding_items,
            (
                ("$attrs", (("tags", ("vip", "active")),)),
                ("$p", "person:alice"),
            ),
        )
        self.assertIsInstance(view.atom_verdicts, FrozenTupleView)
        self.assertIs(view.atom_verdicts[0], result.atom_verdicts[0])

    def test_atom_verdicts_support_filter_find_and_require_key(self) -> None:
        view = ProofFrameView(_proof_frame_result())

        invalidated = view.atom_verdicts.filter(verdict="invalidated")

        self.assertEqual(len(invalidated), 1)
        self.assertEqual(invalidated.first().atom_key, "b0.a1:eq")
        found = view.atom_verdicts.find(atom_key="b0.a0:Person:age")
        required = view.atom_verdicts.require_key("b0.a1:eq")

        self.assertEqual(found.verdict, "still_valid")
        self.assertEqual(required.affected_action_indices, (0,))

    def test_binding_items_are_snapshot_frozen_at_construction(self) -> None:
        result = _proof_frame_result()
        view = ProofFrameView(result)

        result.binding_items[0][1]["tags"].append("late")  # type: ignore[index]

        self.assertEqual(view.binding_items[0][1], (("tags", ("vip", "active")),))
        self.assertIsInstance(hash(view), int)

    def test_constructor_requires_proof_frame_result(self) -> None:
        with self.assertRaises(TypeError):
            ProofFrameView(object())  # type: ignore[arg-type]

    def test_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        view = ProofFrameView(_proof_frame_result())

        with self.assertRaises(WalkerFrozenError):
            view.status = "still_valid"  # type: ignore[misc]

        self.assertFalse(hasattr(view, "source"))
        self.assertFalse(hasattr(view, "carrier"))
        self.assertFalse(hasattr(view, "raw"))

    def test_equality_and_hash_exclude_underlying(self) -> None:
        a = ProofFrameView(_proof_frame_result())
        b = ProofFrameView(_proof_frame_result())
        c = ProofFrameView(
            ProofFrameRecheckResult(
                status="still_valid",
                binding_items=(("$p", "person:alice"),),
                atom_verdicts=(
                    ProofFrameAtomVerdict(
                        atom_key="b0.a0:Person:age",
                        verdict="still_valid",
                        affected_action_indices=(),
                    ),
                ),
            )
        )

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, c)

    def test_phase_4_type_reexports_from_application_package(self) -> None:
        from kernel.application import ProofFrameView as AppProofFrameView

        self.assertIs(AppProofFrameView, ProofFrameView)


if __name__ == "__main__":
    unittest.main()
