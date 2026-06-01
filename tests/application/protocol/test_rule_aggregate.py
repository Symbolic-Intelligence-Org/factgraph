from __future__ import annotations

import unittest

from factgraph.application.protocol import Rule, RuleValidationError
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, Const, PredAtom, Var


class RuleAggregateTests(unittest.TestCase):
    def test_content_digest_serializes_aggregate_term(self) -> None:
        u = Var("$u")
        order = Var("$order")
        aggregate = AggregateAtom(
            "count",
            None,
            [PredAtom("Order", [order, u])],
        )
        rule = Rule(
            id="order_count",
            when=(
                PredAtom("User:exists", [u]),
                CmpAtom("eq", Var("$count"), aggregate),
            ),
            ports={"user": u, "count": Var("$count")},
        )

        self.assertEqual(len(rule.content_digest), 64)

    def test_filter_local_var_cannot_be_port(self) -> None:
        u = Var("$u")
        order = Var("$order")
        aggregate = AggregateAtom(
            "count",
            None,
            [PredAtom("Order", [order, u])],
        )

        with self.assertRaises(RuleValidationError):
            Rule(
                id="order_count",
                when=(PredAtom("User:exists", [u]), CmpAtom("eq", Var("$count"), aggregate)),
                ports={"order": order},
            )

    def test_target_var_is_collected_for_ports_even_if_only_in_aggregate_target(self) -> None:
        amount = Var("$amount")
        order = Var("$order")
        aggregate = AggregateAtom(
            "sum",
            amount,
            [PredAtom("OrderAmount", [order, amount])],
        )

        rule = Rule(
            id="amount_sum",
            when=(CmpAtom("eq", Const(10), aggregate),),
            ports={"amount": amount},
        )

        self.assertIs(rule.ports["amount"], amount)


if __name__ == "__main__":
    unittest.main()
