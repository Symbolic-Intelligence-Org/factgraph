from __future__ import annotations

import unittest

from factgraph.application.protocol import RuleValidationError
from factgraph.core.rules.where_ast import AggregateAtom, AndExpr, CmpAtom, lower_ast_to_where_ir
from factgraph.core.rules.where_eval import evaluate_where
from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.dsl import (
    DSLToApplicationRuleError,
    SDKDSLError,
    Pred,
    agg_count,
    agg_max,
    agg_mean,
    agg_min,
    agg_sum,
    build_application_rule,
    vars,
)
from factgraph.sdk.dsl.expr import lower_where


class User(Entity):
    user_id: str = Identity()
    status: str = Field()


class Order(Entity):
    order_id: str = Identity()
    buyer: str = Field()
    amount: int = Field()


def _count_pred(raw_filter: list[object], pred_id: str, first_term: str) -> int:
    return sum(
        1
        for atom in raw_filter
        if isinstance(atom, tuple)
        and len(atom) == 3
        and atom[0] == "pred"
        and atom[1] == pred_id
        and atom[2][0] == first_term
    )


class AggregateHelperLoweringTests(unittest.TestCase):
    def test_all_helpers_create_comparable_aggregate_refs(self) -> None:
        with vars("u", "o", "n") as (u, o, n):
            aggregates = [
                agg_count(where=[Order(o).buyer == u]),
                agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
                agg_min(Order(o).amount, where=[Order(o).buyer == u]),
                agg_max(Order(o).amount, where=[Order(o).buyer == u]),
                agg_mean(Order(o).amount, where=[Order(o).buyer == u]),
            ]
            lowered = lower_where([n == aggregate for aggregate in aggregates])

        self.assertEqual([atom[0] for atom in lowered], ["eq", "eq", "eq", "eq", "eq"])
        self.assertEqual([atom[2][0] for atom in lowered], ["count", "sum", "min", "max", "mean"])

    def test_target_attr_ref_lowering_injects_target_field_predicate(self) -> None:
        with vars("u", "o", "total") as (u, o, total):
            lowered = lower_where(
                [
                    total
                    == agg_sum(
                        Order(o).amount,
                        where=[Order(o).buyer == u],
                    )
                ]
            )

        aggregate = lowered[0][2]
        self.assertEqual(aggregate[0], "sum")
        self.assertEqual(aggregate[1], "$_agg1")
        self.assertEqual(
            aggregate[2],
            [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:buyer", ["$o", "$u"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ],
        )
        self.assertEqual(_count_pred(aggregate[2], "Order:exists", "$o"), 1)

    def test_filter_bound_target_attr_ref_does_not_duplicate_existence(self) -> None:
        with vars("o", "total") as (o, total):
            aggregate = lower_where(
                [total == agg_sum(Order(o).amount, where=[Order(o)])]
            )[0][2]

        self.assertEqual(
            aggregate[2],
            [
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ],
        )
        self.assertEqual(_count_pred(aggregate[2], "Order:exists", "$o"), 1)

    def test_target_attr_ref_self_ensures_when_filter_does_not_bind_record(self) -> None:
        with vars("u", "o", "total") as (u, o, total):
            aggregate = lower_where(
                [total == agg_sum(Order(o).amount, where=[User(u)])]
            )[0][2]

        self.assertEqual(
            aggregate[2],
            [
                ("pred", "User:exists", ["$u"]),
                ("pred", "Order:exists", ["$o"]),
                ("pred", "order:amount", ["$o", "$_agg1"]),
            ],
        )
        self.assertEqual(_count_pred(aggregate[2], "Order:exists", "$o"), 1)

    def test_filter_local_self_ensured_target_var_does_not_leak_outer_bindings(self) -> None:
        with vars("u", "o", "total") as (u, o, total):
            with self.assertRaises(SDKDSLError):
                lower_where(
                    [
                        total == agg_sum(Order(o).amount, where=[User(u)]),
                        o.amount == 7,
                    ]
                )


class AggregateApplicationBridgeTests(unittest.TestCase):
    def test_bridge_builds_rule_and_python_eval_runs_correlated_aggregate(self) -> None:
        with vars("u", "o", "total") as (u, o, total):
            rule = build_application_rule(
                id="user_order_total",
                when=[
                    User(u),
                    total == agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
                    total > 4,
                ],
                ports={"user": u, "total": total},
            )

        aggregate_atom = rule.when[1]
        self.assertIsInstance(aggregate_atom, CmpAtom)
        self.assertIsInstance(aggregate_atom.rhs, AggregateAtom)
        raw_where = lower_ast_to_where_ir(AndExpr(list(rule.when)))
        rows = evaluate_where(
            {
                "User:exists": [("u-1",), ("u-2",)],
                "Order:exists": [("o-1",), ("o-2",), ("o-3",)],
                "order:buyer": [("o-1", "u-1"), ("o-2", "u-1"), ("o-3", "u-2")],
                "order:amount": [("o-1", 2), ("o-2", 3), ("o-3", 1)],
            },
            raw_where,
        )

        self.assertEqual(rows, [{"$total": 5, "$u": "u-1"}])

    def test_bridge_validator_rejects_unbound_aggregate_target_var(self) -> None:
        with vars("o", "amount", "total") as (o, amount, total):
            with self.assertRaises(DSLToApplicationRuleError):
                build_application_rule(
                    id="invalid_sum",
                    when=[total == agg_sum(amount, where=[Order(o)])],
                    ports={"total": total},
                )

    def test_bridge_rejects_bare_attr_ref_target(self) -> None:
        with vars("o", "total") as (o, total):
            with self.assertRaises(DSLToApplicationRuleError):
                build_application_rule(
                    id="legacy_aggregate_target",
                    when=[total == agg_sum(o.amount, where=[Order(o)])],
                    ports={"total": total},
                )

    def test_bridge_rejects_legacy_pred_in_aggregate_filter(self) -> None:
        with vars("u", "n") as (u, n):
            with self.assertRaises(DSLToApplicationRuleError):
                build_application_rule(
                    id="legacy_aggregate_filter",
                    when=[n == agg_count(where=[Pred("User:exists", u)])],
                    ports={"count": n},
                )

    def test_application_rule_rejects_aggregate_filter_local_port(self) -> None:
        with vars("u", "o", "total") as (u, o, total):
            with self.assertRaises(RuleValidationError):
                build_application_rule(
                    id="aggregate_local_port",
                    when=[
                        User(u),
                        total == agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
                    ],
                    ports={"user": u, "order": o},
                )


if __name__ == "__main__":
    unittest.main()
