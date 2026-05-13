"""IRBodyWalker tests for B Phase 1."""

from __future__ import annotations

import unittest

import factgraph.application.walker.ir as ir_module
from factgraph.application.walker import (
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

    def test_traverse_twice_yields_equal_but_new_view_sequence(self) -> None:
        walker = IRBodyWalker(
            [
                ("pred", "Person:age", ["$p", "$age"]),
                ("eq", "$age", 40),
            ]
        )

        first = list(walker)
        second = list(walker)

        self.assertEqual(first, second)
        self.assertIsNot(first[0], second[0])

    def test_view_objects_are_created_lazily_on_iteration(self) -> None:
        calls: list[tuple[int, int]] = []
        original = ir_module._build_atom_view

        def counting_build(atom, *, branch_index, atom_index):
            calls.append((branch_index, atom_index))
            return original(atom, branch_index=branch_index, atom_index=atom_index)

        ir_module._build_atom_view = counting_build
        try:
            walker = IRBodyWalker(
                [
                    ("pred", "Person:age", ["$p", "$age"]),
                    ("eq", "$age", 40),
                ]
            )
            self.assertEqual(calls, [])
            self.assertEqual(next(iter(walker)).key, "b0.a0:Person:age")
            self.assertEqual(calls, [(0, 0)])
        finally:
            ir_module._build_atom_view = original


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

    def test_snapshot_rejects_empty_pred_id_and_ruleref_ids(self) -> None:
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("pred", "", [])])
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("ruleref", "", "1.0", [])])
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("ruleref", "adult.rule", "", [])])

    def test_snapshot_freezes_sets_and_rejects_unhashable_leaves(self) -> None:
        shared = {"tags": {"vip", "active"}}
        walker = IRBodyWalker([("pred", "Person:tags", [shared, shared])])
        atom = next(iter(walker))

        self.assertEqual(atom.args, ((("tags", ("active", "vip")),), (("tags", ("active", "vip")),)))
        self.assertIsInstance(hash(atom), int)

        class MutableLeaf:
            __hash__ = None

        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("pred", "Person:bad", [MutableLeaf()])])

        recursive: list[object] = []
        recursive.append(recursive)
        with self.assertRaises(WalkerSnapshotError):
            IRBodyWalker([("pred", "Person:recursive", recursive)])


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
        from factgraph.application import IRAtomView as AppIRAtomView
        from factgraph.application import IRBodyWalker as AppIRBodyWalker

        self.assertIs(AppIRAtomView, IRAtomView)
        self.assertIs(AppIRBodyWalker, IRBodyWalker)

    def test_view_is_frozen_and_has_only_underlying_escape_hatch(self) -> None:
        atom = next(iter(IRBodyWalker([("pred", "Person:exists", ["$p"])])))

        with self.assertRaises(WalkerFrozenError):
            atom.kind = "eq"  # type: ignore[misc]

        self.assertFalse(hasattr(atom, "source"))
        self.assertFalse(hasattr(atom, "carrier"))
        self.assertFalse(hasattr(atom, "raw"))

    def test_walker_instance_is_frozen(self) -> None:
        walker = IRBodyWalker([("pred", "Person:exists", ["$p"])])

        with self.assertRaises(WalkerFrozenError):
            walker._branches = ()  # type: ignore[misc]
        with self.assertRaises(WalkerFrozenError):
            walker.extra = "nope"  # type: ignore[attr-defined]

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
