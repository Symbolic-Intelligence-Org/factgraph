"""IRBodyWalker tests for B Phase 1."""

from __future__ import annotations

import unittest

from kernel.application.walker import (
    IRAtomView,
    IRBodyWalker,
    WalkerFrozenError,
    WalkerLookupError,
    WalkerSnapshotError,
)


class IRBodyWalkerTraversalTests(unittest.TestCase):
    def test_iterates_flat_and_body_with_branch_positions(self) -> None:
        walker = IRBodyWalker(
            [
                ("pred", "Person:age", ["$p", "$age"]),
                ("eq", "$age", 40),
            ],
            source_id="rule-1",
        )

        atoms = list(walker)

        self.assertEqual([atom.kind for atom in atoms], ["pred", "eq"])
        self.assertEqual(atoms[0].pred_id, "Person:age")
        self.assertEqual(atoms[0].args, ("$p", "$age"))
        self.assertEqual(atoms[0].branch_index, 0)
        self.assertEqual(atoms[0].atom_index, 0)
        self.assertEqual(atoms[0].key, "b0.a0:Person:age")
        self.assertEqual(atoms[1].pred_id, None)
        self.assertEqual(atoms[1].args, ("$age", 40))
        self.assertEqual(atoms[1].key, "b0.a1:eq")
        self.assertEqual(walker.source_id, "rule-1")

    def test_iterates_or_of_and_with_branch_positions(self) -> None:
        walker = IRBodyWalker(
            [
                [("pred", "Person:age", ["$p", "$age"])],
                [("pred", "Person:region", ["$p", "$region"]), ("eq", "$region", "us")],
            ]
        )

        atoms = list(walker)

        self.assertEqual(
            [(atom.kind, atom.branch_index, atom.atom_index) for atom in atoms],
            [("pred", 0, 0), ("pred", 1, 0), ("eq", 1, 1)],
        )
        self.assertEqual(atoms[2].key, "b1.a1:eq")

    def test_constructs_from_tuple_source(self) -> None:
        walker = IRBodyWalker((("pred", "Person:exists", ["$p"]),))

        self.assertEqual([atom.key for atom in walker], ["b0.a0:Person:exists"])


class IRBodyWalkerSnapshotTests(unittest.TestCase):
    def test_snapshot_is_immune_to_top_level_and_nested_mutation(self) -> None:
        terms = ["$p", "$age"]
        source = [("pred", "Person:age", terms)]
        walker = IRBodyWalker(source)

        source.append(("eq", "$age", 40))
        terms.append("$late")

        atoms = list(walker)
        self.assertEqual(len(atoms), 1)
        self.assertEqual(atoms[0].args, ("$p", "$age"))
        self.assertEqual(atoms[0].underlying, ("pred", "Person:age", ("$p", "$age")))

    def test_snapshot_rejects_non_sequence_source(self) -> None:
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker(object())

    def test_snapshot_rejects_mixed_top_level_shape(self) -> None:
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("pred", "Person:exists", ["$p"]), [("eq", "$p", "p1")]])

    def test_snapshot_rejects_empty_or_branch(self) -> None:
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([[], [("pred", "Person:exists", ["$p"])]])

    def test_snapshot_rejects_malformed_pred_atom(self) -> None:
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("pred", "Person:exists")])


class IRBodyWalkerLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.walker = IRBodyWalker(
            [
                ("pred", "Person:age", ["$p", "$age"]),
                ("eq", "$age", 40),
                ("ruleref", "adult.rule", "1.0", ["$p"]),
            ]
        )

    def test_find_returns_match_or_none(self) -> None:
        found = self.walker.find(kind="pred", pred_id="Person:age")
        self.assertIsInstance(found, IRAtomView)
        self.assertEqual(found.key, "b0.a0:Person:age")

        self.assertIsNone(self.walker.find(kind="pred", pred_id="Missing"))
        self.assertIsNone(self.walker.find(branch_index=9, atom_index=0))

    def test_require_position_raises_on_miss(self) -> None:
        self.assertEqual(
            self.walker.require_position(branch_index=0, atom_index=1).key,
            "b0.a1:eq",
        )

        with self.assertRaises(WalkerLookupError):
            self.walker.require_position(branch_index=9, atom_index=0)

    def test_require_key_raises_on_miss(self) -> None:
        self.assertEqual(
            self.walker.require_key("b0.a2:ruleref").args,
            ("adult.rule", "1.0", ("$p",)),
        )

        with self.assertRaises(WalkerLookupError):
            self.walker.require_key("b0.a9:eq")


class IRAtomViewContractTests(unittest.TestCase):
    def test_phase_1_types_reexport_from_application_package(self) -> None:
        from kernel.application import IRAtomView as AppIRAtomView
        from kernel.application import IRBodyWalker as AppIRBodyWalker

        self.assertIs(AppIRAtomView, IRAtomView)
        self.assertIs(AppIRBodyWalker, IRBodyWalker)

    def test_view_is_frozen_and_has_only_underlying_escape_hatch(self) -> None:
        atom = next(iter(IRBodyWalker([("pred", "Person:exists", ["$p"])])))

        with self.assertRaises(WalkerFrozenError):
            atom.kind = "eq"  # type: ignore[misc]

        self.assertFalse(hasattr(atom, "source"))
        self.assertFalse(hasattr(atom, "carrier"))
        self.assertFalse(hasattr(atom, "raw"))

    def test_structural_equality_and_hash_exclude_underlying(self) -> None:
        a = IRAtomView(
            kind="pred",
            pred_id="Person:exists",
            args=("$p",),
            branch_index=0,
            atom_index=0,
            key="b0.a0:Person:exists",
            underlying=("pred", "Person:exists", ("$p",)),
        )
        b = IRAtomView(
            kind="pred",
            pred_id="Person:exists",
            args=("$p",),
            branch_index=0,
            atom_index=0,
            key="b0.a0:Person:exists",
            underlying=("different", "raw"),
        )

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))


if __name__ == "__main__":
    unittest.main()
