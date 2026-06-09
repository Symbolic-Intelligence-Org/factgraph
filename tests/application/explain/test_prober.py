from __future__ import annotations

import unittest

from factgraph.application.explain import EvidenceJoin, Holds, NotReached, probe_native
from factgraph.application.protocol import Rule
from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule, _lower_rule_expr
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var


def _status(result: object) -> str:
    paths = getattr(result, "paths")
    assert len(paths) == 1
    return paths[0].status


class NativeProberTests(unittest.TestCase):
    def test_monotonic_witness_backtracking_keeps_later_successful_env(self) -> None:
        x = Var("$x")
        rule = Rule(
            id="positive_p",
            when=(PredAtom("p", [x]), CmpAtom("gt", x, Const(1))),
            ports={"x": x},
        )
        plan = _lower_application_rule(rule, head=rule)

        only_true = probe_native(plan, {}, {"p": [(2,)]})
        false_then_true = probe_native(plan, {}, {"p": [(1,), (2,)]})

        self.assertEqual(_status(only_true), "holds")
        self.assertEqual(_status(false_then_true), "holds")

    def test_structure_preserves_head_body_occurrences_and_join_materialization(self) -> None:
        left_person = Var("$p")
        left_region = Var("$region")
        right_person = Var("$q")
        right_region = Var("$region")
        left = Rule(
            id="left_region",
            when=(PredAtom("Person:region", [left_person, left_region]),),
            ports={"person": left_person, "region": left_region},
        )
        right = Rule(
            id="right_region",
            when=(PredAtom("Person:region", [right_person, right_region]),),
            ports={"person": right_person, "region": right_region},
        )
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").region.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        result = probe_native(plan, {}, {"Person:region": [("alice", "US"), ("bob", "US")]})

        self.assertEqual(len(result.paths), 1)
        path = result.paths[0]
        self.assertEqual(path.status, "holds")
        head_rules = [rule for rule in path.rules if rule.role == "head"]
        body_rules = [rule for rule in path.rules if rule.role == "body"]
        self.assertEqual(tuple(rule.occurrence_alias for rule in head_rules), ("left_region",))
        self.assertEqual({rule.occurrence_alias for rule in body_rules}, {"left", "right"})
        self.assertNotIn("branch:0", {rule.occurrence_alias for rule in body_rules})
        self.assertTrue(path.joins)
        self.assertTrue(all(isinstance(join, EvidenceJoin) for join in path.joins))
        self.assertEqual(path.joins[0].left.rule_occurrence_alias, "left")
        self.assertEqual(path.joins[0].right.rule_occurrence_alias, "right")

    def test_not_reached_is_only_unbound_dependency(self) -> None:
        x = Var("$x")
        rule = Rule(id="needs_x", when=(CmpAtom("gt", x, Const(1)),), ports={"x": x})
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(plan, {}, {})

        atom = result.paths[0].rules[1].atoms[0]
        self.assertIsInstance(atom.verdict, NotReached)
        self.assertEqual(atom.verdict.blocked_by, "$needs_x__x")

    def test_or_branches_are_exhaustive_paths(self) -> None:
        x = Var("$x")
        left = Rule(id="left", when=(PredAtom("left_p", [x]),), ports={"x": x})
        right = Rule(id="right", when=(PredAtom("right_p", [x]),), ports={"x": x})
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=left)

        result = probe_native(plan, {}, {"left_p": [(1,)], "right_p": []})

        self.assertEqual(tuple(path.status for path in result.paths), ("holds", "fails"))
        self.assertIsInstance(result.paths[0].rules[1].atoms[0].verdict, Holds)


if __name__ == "__main__":
    unittest.main()
