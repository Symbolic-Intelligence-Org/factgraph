from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.adapters.problog.problog_export import export_problog
from factgraph.adapters.souffle.where_compile import _normalize_where_subset, compile_where_to_query_dl
from factgraph.application.protocol import Rule
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprAdapterSupport,
    _classify_pyreason_rule_expr_support,
    _lower_application_rule,
    _lower_rule_expr,
    _materialize_adapter_derivation_plan,
)
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, SDKStore


def _schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {"pred_id": "Person:exists", "arg_specs": [{"name": "person", "type_domain": "Person"}]},
            {
                "pred_id": "Person:region",
                "arg_specs": [
                    {"name": "person", "type_domain": "Person"},
                    {"name": "region", "type_domain": "string"},
                ],
            },
            {"pred_id": "Order:exists", "arg_specs": [{"name": "order", "type_domain": "Order"}]},
            {
                "pred_id": "OrderAmount",
                "arg_specs": [
                    {"name": "order", "type_domain": "Order"},
                    {"name": "amount", "type_domain": "int"},
                ],
            },
        ]
    }


class PersonEntity(Entity):
    name: str = Identity(primary_key=True)
    region: str = Field(cardinality="single")


def _person_exists_rule(rule_id: str = "person_exists") -> Rule:
    person = Var("$person")
    return Rule(id=rule_id, where=(PredAtom("Person:exists", [person]),), ports={"person": person})


def _person_region_rule(rule_id: str = "person_region") -> Rule:
    person = Var("$person")
    region = Var("$region")
    return Rule(
        id=rule_id,
        where=(PredAtom("Person:exists", [person]), PredAtom("Person:region", [person, region])),
        ports={"person": person, "region": region},
    )


def _aggregate_rule() -> Rule:
    total = Var("$total")
    amount = Var("$amount")
    order = Var("$order")
    aggregate = AggregateAtom("sum", amount, [PredAtom("OrderAmount", [order, amount])])
    return Rule(
        id="amount_sum",
        where=(CmpAtom("eq", total, aggregate),),
        ports={"total": total},
    )


def _export_problog_program(where: list[object]) -> str:
    store = SDKStore([PersonEntity]).store
    rule_spec = {
        "derivation_id": "drv.ruleexpr.adapter",
        "version": "v1",
        "target_pred_id": "Person:exists",
        "head_vars": ["$person"],
        "where": where,
        "query_pred": "answer",
    }
    with TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "query.pl"
        export_problog(store, rule_spec, out_path)
        return out_path.read_text(encoding="utf-8")


class RuleExprSouffleMaterializationTests(unittest.TestCase):
    def test_branch_list_materializes_to_souffle_compatible_or_body(self) -> None:
        left = _person_exists_rule("left_exists")
        right = _person_exists_rule("right_exists")
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=left)

        compiled, traces = _materialize_adapter_derivation_plan(plan, engine="souffle")
        branches = _normalize_where_subset(compiled.body_ir)

        self.assertEqual(tuple(trace.engine for trace in traces), ("souffle", "souffle"))
        self.assertEqual(len(branches), 2)
        self.assertTrue(all(branch[0][0] == "pred" for branch in branches))

    def test_join_equality_compiles_through_souffle_eq(self) -> None:
        left = _person_region_rule("left_region")
        right = _person_region_rule("right_region")
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").region.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        compiled, traces = _materialize_adapter_derivation_plan(plan, engine="souffle")
        dl = compile_where_to_query_dl(schema_ir=_schema_ir(), where=compiled.body_ir, query_rel="Q")

        self.assertEqual(traces[0].join_materializations[0].materialized_atom_index, len(compiled.body_ir) - 1)
        self.assertIn(" = ", dl)

    def test_aggregate_rule_preserves_souffle_aggregate_support(self) -> None:
        rule = _aggregate_rule()
        plan = _lower_application_rule(rule, head=rule)

        compiled, traces = _materialize_adapter_derivation_plan(plan, engine="souffle")
        dl = compile_where_to_query_dl(schema_ir=_schema_ir(), where=compiled.body_ir, query_rel="Q")

        self.assertEqual(traces[0].engine, "souffle")
        self.assertIn("sum to_number", dl)


class RuleExprProbLogMaterializationTests(unittest.TestCase):
    def test_branch_list_exports_to_multiple_problog_rule_bodies(self) -> None:
        left = _person_exists_rule("left_exists")
        right = _person_exists_rule("right_exists")
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=left)

        compiled, traces = _materialize_adapter_derivation_plan(plan, engine="problog")
        program = _export_problog_program(compiled.body_ir)

        self.assertEqual(tuple(trace.engine for trace in traces), ("problog", "problog"))
        self.assertIn("rule_body_0", program)
        self.assertIn("rule_body_1", program)

    def test_join_equality_exports_through_problog_eq(self) -> None:
        left = _person_region_rule("left_region")
        right = _person_region_rule("right_region")
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").region.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        compiled, traces = _materialize_adapter_derivation_plan(plan, engine="problog")
        program = _export_problog_program(compiled.body_ir)

        self.assertEqual(traces[0].join_materializations[0].materialized_atom_index, len(compiled.body_ir) - 1)
        self.assertIn("V_LEFT__REGION = V_RIGHT__REGION", program)

    def test_aggregate_rule_exports_through_problog_aggregate_support(self) -> None:
        rule = _aggregate_rule()
        plan = _lower_application_rule(rule, head=rule)

        compiled, traces = _materialize_adapter_derivation_plan(plan, engine="problog")
        program = _export_problog_program(compiled.body_ir)

        self.assertEqual(traces[0].engine, "problog")
        self.assertIn(":- use_module(library(lists)).", program)
        self.assertIn("sum_list", program)


class RuleExprPyReasonClassifierTests(unittest.TestCase):
    def test_pyreason_classifier_accepts_pred_only_branches(self) -> None:
        rule = _person_exists_rule()
        plan = _lower_application_rule(rule, head=rule)

        support = _classify_pyreason_rule_expr_support(plan)

        self.assertEqual(support, RuleExprAdapterSupport(engine="pyreason", supported=True))

    def test_pyreason_classifier_rejects_ruleexpr_join_eq(self) -> None:
        left = _person_region_rule("left_region")
        right = _person_region_rule("right_region")
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").region.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        support = _classify_pyreason_rule_expr_support(plan)

        self.assertFalse(support.supported)
        self.assertEqual(support.unsupported_feature, "eq")
        self.assertEqual(support.rejection_source, "ruleexpr-join")
        self.assertEqual(support.alternative_engines, ("native", "souffle", "problog"))

    def test_pyreason_classifier_rejects_source_non_pred_atom(self) -> None:
        person = Var("$person")
        rule = Rule(
            id="source_eq",
            where=(PredAtom("Person:exists", [person]), CmpAtom("eq", person, Const("person:alice"))),
            ports={"person": person},
        )
        plan = _lower_application_rule(rule, head=rule)

        support = _classify_pyreason_rule_expr_support(plan)

        self.assertFalse(support.supported)
        self.assertEqual(support.unsupported_feature, "eq")
        self.assertEqual(support.rejection_source, "source-rule-grammar")

    def test_pyreason_classifier_rejects_aggregate_branch(self) -> None:
        rule = _aggregate_rule()
        plan = _lower_application_rule(rule, head=rule)

        support = _classify_pyreason_rule_expr_support(plan)

        self.assertFalse(support.supported)
        self.assertEqual(support.unsupported_feature, "aggregate")
        self.assertEqual(support.rejection_source, "aggregate")

    def test_pyreason_classifier_rejects_aggregate_external_head_body(self) -> None:
        total = Var("$total")
        body = Rule(id="total_source", where=(PredAtom("TotalValue", [total]),), ports={"total": total})
        head = _aggregate_rule()
        plan = _lower_application_rule(body, head=head)

        support = _classify_pyreason_rule_expr_support(plan)

        self.assertFalse(support.supported)
        self.assertEqual(support.unsupported_feature, "aggregate")
        self.assertEqual(support.rejection_source, "aggregate")


if __name__ == "__main__":
    unittest.main()
