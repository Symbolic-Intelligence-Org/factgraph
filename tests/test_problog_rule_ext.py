"""Tests for ProbLog rule extensions and branch-probability helpers."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from factgraph.adapters.problog.rule_ext import (
    ProbLogRuleExt,
    branch_count_for_where,
    materialize_problog_branch_probabilities,
    resolve_problog_engine_ext,
)
from factgraph.core.store.types import EngineExtBase


@dataclass(frozen=True)
class DummyProbLogExt(EngineExtBase):
    flag: int = 1


class ProbLogRuleExtTests(unittest.TestCase):
    def test_defaults_to_none(self) -> None:
        ext = ProbLogRuleExt()
        self.assertIsNone(ext.branch_probabilities)

    def test_normalizes_list_to_tuple(self) -> None:
        ext = ProbLogRuleExt(branch_probabilities=[0.8, 0.6])
        self.assertEqual(ext.branch_probabilities, (0.8, 0.6))

    def test_rejects_empty_branch_probabilities(self) -> None:
        with self.assertRaises(ValueError):
            ProbLogRuleExt(branch_probabilities=())

    def test_rejects_out_of_range_branch_probability(self) -> None:
        with self.assertRaises(ValueError):
            ProbLogRuleExt(branch_probabilities=(1.2,))

    def test_materialize_defaults_to_deterministic_branches(self) -> None:
        where = [[("pred", "user:name", ["$u", "Alice"])], [("pred", "user:name", ["$u", "Bob"])]]
        self.assertEqual(
            materialize_problog_branch_probabilities(where=where, engine_ext=None),
            (1.0, 1.0),
        )

    def test_branch_count_for_where_collapses_single_branch_form(self) -> None:
        where = [("pred", "user:name", ["$u", "Alice"])]
        self.assertEqual(branch_count_for_where(where), 1)

    def test_resolve_bridges_legacy_body_confidences(self) -> None:
        where = [[("pred", "user:name", ["$u", "Alice"])]]
        resolved = resolve_problog_engine_ext(
            where=where,
            engine_ext=None,
            legacy_body_confidences=[0.7],
        )
        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.7,))

    def test_resolve_rejects_other_engine_ext(self) -> None:
        where = [[("pred", "user:name", ["$u", "Alice"])]]
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=where,
                engine_ext=DummyProbLogExt(),
            )
        self.assertIn("ProbLog engine_ext must be ProbLogRuleExt", str(ctx.exception))

    def test_resolve_rejects_conflicting_legacy_probabilities(self) -> None:
        where = [[("pred", "user:name", ["$u", "Alice"])]]
        with self.assertRaises(ValueError) as ctx:
            resolve_problog_engine_ext(
                where=where,
                engine_ext=ProbLogRuleExt(branch_probabilities=(0.8,)),
                legacy_body_confidences=[0.6],
            )
        self.assertIn("Conflicting ProbLog branch probabilities", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
