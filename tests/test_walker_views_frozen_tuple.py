"""FrozenTupleView tests for B Phase 2."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from factgraph.application.walker import (
    FrozenTupleView,
    WalkerFrozenError,
    WalkerLookupError,
    frozen_collection,
)


@dataclass(frozen=True)
class Row:
    key: str
    kind: str
    value: int


@dataclass(frozen=True)
class PredWitnessLike:
    pred_condition_key: str
    status: str


@dataclass(frozen=True)
class IdLike:
    id: str
    value: int


class FrozenTupleViewConstructionTests(unittest.TestCase):
    def test_constructs_only_from_tuple_and_exposes_underlying(self) -> None:
        source = (Row("a", "pred", 1), Row("b", "eq", 2))
        view = FrozenTupleView(source, source_id="rows")

        self.assertEqual(tuple(view), source)
        self.assertEqual(view.underlying, source)
        self.assertEqual(view.source_id, "rows")
        self.assertEqual(len(view), 2)
        self.assertIs(view[0], source[0])

    def test_helper_constructs_view(self) -> None:
        source = (1, 2, 3)

        view = frozen_collection(source)

        self.assertIsInstance(view, FrozenTupleView)
        self.assertEqual(tuple(view), source)

    def test_rejects_non_tuple_source(self) -> None:
        with self.assertRaises(TypeError):
            FrozenTupleView([1, 2, 3])  # type: ignore[arg-type]


class FrozenTupleViewFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.view = FrozenTupleView(
            (
                Row("a", "pred", 1),
                Row("b", "eq", 2),
                Row("c", "pred", 3),
            )
        )

    def test_filter_by_predicate_eagerly_returns_new_view(self) -> None:
        filtered = self.view.filter(lambda row: row.kind == "pred")

        self.assertIsInstance(filtered, FrozenTupleView)
        self.assertIsNot(filtered, self.view)
        self.assertEqual([row.key for row in filtered], ["a", "c"])
        self.assertEqual(filtered.underlying, (self.view[0], self.view[2]))

    def test_filter_by_attribute_kwargs(self) -> None:
        filtered = self.view.filter(kind="pred", value=3)

        self.assertEqual([row.key for row in filtered], ["c"])

    def test_filter_combines_predicate_and_kwargs(self) -> None:
        filtered = self.view.filter(lambda row: row.value > 1, kind="pred")

        self.assertEqual([row.key for row in filtered], ["c"])


class FrozenTupleViewLookupTests(unittest.TestCase):
    def test_find_and_first_return_none_on_miss_or_empty(self) -> None:
        view = FrozenTupleView((Row("a", "pred", 1), Row("b", "eq", 2)))

        self.assertEqual(view.find(lambda row: row.kind == "eq").key, "b")
        self.assertEqual(view.find(kind="eq").key, "b")
        self.assertEqual(view.find(lambda row: row.value > 1, kind="eq").key, "b")
        self.assertIsNone(view.find(lambda row: row.kind == "missing"))
        self.assertIsNone(view.find(kind="missing"))
        self.assertEqual(view.first().key, "a")
        self.assertIsNone(FrozenTupleView(()).first())

    def test_traverse_twice_yields_identical_sequence(self) -> None:
        view = FrozenTupleView((Row("a", "pred", 1), Row("b", "eq", 2)))

        self.assertEqual(tuple(view), tuple(view))

    def test_require_position_raises_on_miss(self) -> None:
        view = FrozenTupleView((Row("a", "pred", 1),))

        self.assertEqual(view.require_position(0).key, "a")
        with self.assertRaises(WalkerLookupError):
            view.require_position(1)
        with self.assertRaises(WalkerLookupError):
            view.require_position(-1)

    def test_require_key_uses_default_key_attribute_fallback(self) -> None:
        view = FrozenTupleView(
            (
                PredWitnessLike("c0.c0:Person:age", "active"),
                IdLike("row-2", 2),
            )
        )

        self.assertEqual(view.require_key("c0.c0:Person:age").status, "active")
        self.assertEqual(view.require_key("row-2").value, 2)
        with self.assertRaises(WalkerLookupError):
            view.require_key("missing")

    def test_require_key_accepts_extractor_override(self) -> None:
        view = FrozenTupleView((Row("a", "pred", 1), Row("b", "eq", 2)))

        self.assertEqual(view.require_key(2, key=lambda row: row.value).key, "b")

    def test_require_key_reports_no_key_like_attribute(self) -> None:
        view = FrozenTupleView((object(),))

        with self.assertRaises(WalkerLookupError):
            view.require_key("anything")


class FrozenTupleViewContractTests(unittest.TestCase):
    def test_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        view = FrozenTupleView((Row("a", "pred", 1),))

        with self.assertRaises(WalkerFrozenError):
            view.anything = 1  # type: ignore[attr-defined]

        self.assertFalse(hasattr(view, "source"))
        self.assertFalse(hasattr(view, "carrier"))
        self.assertFalse(hasattr(view, "raw"))

    def test_equality_and_hash_are_structural_over_underlying_tuple(self) -> None:
        a = FrozenTupleView((Row("a", "pred", 1),))
        b = FrozenTupleView((Row("a", "pred", 1),))
        c = FrozenTupleView((Row("b", "eq", 2),))

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, c)

    def test_phase_2_types_reexport_from_application_package(self) -> None:
        from factgraph.application import FrozenTupleView as AppFrozenTupleView
        from factgraph.application import frozen_collection as app_frozen_collection

        self.assertIs(AppFrozenTupleView, FrozenTupleView)
        self.assertIs(app_frozen_collection, frozen_collection)


if __name__ == "__main__":
    unittest.main()
