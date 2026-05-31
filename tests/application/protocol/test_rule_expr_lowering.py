from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector, Rule, RuleExprError
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprEvaluationTrace,
    RuleExprHeadBinding,
    RuleExprHeadPortLinkMaterialization,
    RuleExprLoweringBranch,
    RuleExprLoweringPlan,
    _evaluate_rule_expr_native_for_tests,
    _lower_application_rule,
    _lower_rule_expr,
    _materialize_native_derivation_plan,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, PredAtom, Var
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    region: str = Field()


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Person])
    return Store(schema_ir), build_schema_index(schema_ir)


def _seed_person(store: Store, index: object, name: str, region: str = "us") -> str:
    ref = resolve_selector(EntitySelector(entity_type="Person", identity={"name": name}), index=index)
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(store.ledger, info.identity_predicates["name"].pred_id, encoded, [("string", name)])
    set_field(store.ledger, field_predicate(index, "Person", "region").pred_id, encoded, [("string", region)])
    return encoded


def _person_exists_rule() -> Rule:
    person = Var("$p")
    return Rule(
        id="Person:exists",
        when=(PredAtom("Person:exists", [person]),),
        ports={"person": person},
    )


def _person_region_rule() -> Rule:
    person = Var("$p")
    region = Var("$region")
    return Rule(
        id="person_region",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("Person:region", [person, region]),
        ),
        ports={"person": person, "region": region},
    )


class RuleExprLoweringPlanTests(unittest.TestCase):
    def test_application_rule_lowers_to_private_plan(self) -> None:
        rule = Rule(id="user_rule", when=(PredAtom("User:exists", [Var("$u")]),), ports={"user": Var("$u")})

        plan = _lower_application_rule(rule, head=rule)

        self.assertIsInstance(plan, RuleExprLoweringPlan)
        self.assertEqual(plan.source_kind, "rule")
        self.assertEqual(plan.head_binding.kind, "inline")
        self.assertEqual(plan.head_binding.projection_occurrence_alias, "user_rule")
        self.assertEqual(len(plan.branches), 1)
        self.assertEqual(plan.branches[0].branch_id, "b0")
        self.assertEqual(plan.branches[0].occurrence_aliases, ("user_rule",))

    def test_dtos_are_frozen_and_not_public_exports(self) -> None:
        rule = Rule(id="user_rule", when=(PredAtom("User:exists", [Var("$u")]),), ports={"user": Var("$u")})
        plan = _lower_application_rule(rule, head=rule)

        with self.assertRaises(FrozenInstanceError):
            plan.source_kind = "other"  # type: ignore[misc]

        import factgraph.application.protocol as protocol
        import factgraph.sdk as sdk

        self.assertFalse(hasattr(protocol, "RuleExprLoweringPlan"))
        self.assertFalse(hasattr(sdk, "RuleExprLoweringPlan"))

    def test_dto_invariants_reject_invalid_shapes(self) -> None:
        rule = Rule(id="user_rule", when=(PredAtom("User:exists", [Var("$u")]),), ports={"user": Var("$u")})
        head_binding = RuleExprHeadBinding(
            kind="inline",
            head_rule_id=rule.id,
            head_content_digest=rule.content_digest,
            projection_occurrence_alias=rule.id,
        )

        with self.assertRaisesRegex(RuleExprError, "external/projection head binding"):
            RuleExprHeadBinding(
                kind="external",
                head_rule_id=rule.id,
                head_content_digest=rule.content_digest,
                projection_occurrence_alias=rule.id,
            )
        with self.assertRaisesRegex(RuleExprError, "external/projection head binding"):
            RuleExprHeadBinding(
                kind="projection",
                head_rule_id=rule.id,
                head_content_digest=rule.content_digest,
                projection_occurrence_alias=rule.id,
            )
        with self.assertRaisesRegex(RuleExprError, "inline head binding"):
            RuleExprHeadBinding(kind="inline", head_rule_id=rule.id, head_content_digest=rule.content_digest)
        with self.assertRaisesRegex(RuleExprError, "body_atoms"):
            RuleExprLoweringBranch(branch_id="b0", path=(), occurrence_aliases=(rule.id,), body_atoms=())
        with self.assertRaisesRegex(RuleExprError, "branches"):
            RuleExprLoweringPlan(
                source_kind="rule",
                head=rule,
                head_binding=head_binding,
                branches=(),
                occurrence_map=(),
                canonical_key=("rule", rule.content_digest),
            )

    def test_alias_local_variables_prevent_private_name_collisions(self) -> None:
        left = Rule(id="left", when=(PredAtom("User:exists", [Var("$u")]),), ports={"user": Var("$u")})
        right = Rule(id="right", when=(PredAtom("User:exists", [Var("$u")]),), ports={"user": Var("$u")})

        plan = _lower_rule_expr(left.as_("a") & right.as_("b"), head=left)

        bindings = {
            (occ.alias, binding.port_name): binding.alias_local_execution_var.name
            for occ in plan.occurrence_map
            for binding in occ.port_bindings
        }
        self.assertEqual(bindings[("a", "user")], "$a__u")
        self.assertEqual(bindings[("b", "user")], "$b__u")
        self.assertNotEqual(bindings[("a", "user")], bindings[("b", "user")])

    def test_and_or_lowers_to_deterministic_branch_alternatives(self) -> None:
        a = Rule(id="a", when=(PredAtom("A", [Var("$a")]),), ports={"a": Var("$a")})
        b = Rule(id="b", when=(PredAtom("B", [Var("$b")]),), ports={"b": Var("$b")})
        c = Rule(id="c", when=(PredAtom("C", [Var("$c")]),), ports={"c": Var("$c")})

        plan = _lower_rule_expr((a.as_("a") & b.as_("b")) | c.as_("c"), head=a)

        self.assertEqual(tuple(branch.branch_id for branch in plan.branches), ("b0", "b1"))
        self.assertEqual(tuple(branch.occurrence_aliases for branch in plan.branches), (("a", "b"), ("c",)))


class RuleExprJoinMaterializationTests(unittest.TestCase):
    def test_join_materializes_to_eq_atom_after_body_atoms(self) -> None:
        left = _person_region_rule()
        right = Rule(
            id="right_region",
            when=(PredAtom("Person:region", [Var("$q"), Var("$region")]),),
            ports={"person": Var("$q"), "region": Var("$region")},
        )
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").region.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(compiled.body_ir[-1][0], "eq")
        self.assertEqual(compiled.body_ir[-1][1:], ("$left__region", "$right__region"))
        self.assertEqual(traces[0].join_materializations[0].materialized_condition_index, len(compiled.body_ir) - 1)
        self.assertEqual(traces[0].join_materializations[0].left_occurrence_alias, "left")

    def test_join_rejects_incompatible_port_types(self) -> None:
        left = _person_region_rule()
        right = Rule(
            id="right_value",
            when=(PredAtom("Person:region", [Var("$person"), Var("$region")]),),
            ports={"region": Var("$region")},
        )
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").person.eq(right.as_("right").region))
        plan = _lower_rule_expr(expr, head=left)

        with self.assertRaisesRegex(RuleExprError, "port types are incompatible"):
            _materialize_native_derivation_plan(plan)

    def test_duplicate_joins_materialize_once(self) -> None:
        left = _person_region_rule()
        right = Rule(
            id="right_region",
            when=(PredAtom("Person:region", [Var("$q"), Var("$region")]),),
            ports={"person": Var("$q"), "region": Var("$region")},
        )
        join = left.as_("left").region.eq(right.as_("right").region)
        expr = (left.as_("left") & right.as_("right")).join(join, join)
        plan = _lower_rule_expr(expr, head=left)

        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(sum(1 for atom in compiled.body_ir if atom[0] == "eq"), 1)
        self.assertEqual(len(traces[0].join_materializations), 1)

    def test_external_head_body_and_links_materialize_after_expression_and_joins(self) -> None:
        body = _person_region_rule()
        head = _person_exists_rule()
        plan = _lower_rule_expr(body & Rule(id="other", when=(PredAtom("Other", [Var("$o")]),), ports={"other": Var("$o")}), head=head)

        self.assertEqual(plan.head_binding.kind, "external")
        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(compiled.body_ir[0][0], "pred")
        self.assertEqual(compiled.body_ir[-1], ("eq", "$__head__p", "$person_region__p"))
        self.assertEqual(compiled.heads[0].head_var_names, ("$__head__p",))
        self.assertEqual(len(traces[0].head_port_link_materializations), 1)
        self.assertIsInstance(traces[0].head_port_link_materializations[0], RuleExprHeadPortLinkMaterialization)
        self.assertEqual(traces[0].head_port_link_materializations[0].head_port_name, "person")

    def test_external_head_body_applies_to_every_or_branch_without_var_collision(self) -> None:
        left = Rule(id="left", when=(PredAtom("Person:exists", [Var("$person")]),), ports={"person": Var("$person")})
        right = Rule(id="right", when=(PredAtom("Person:exists", [Var("$person")]),), ports={"person": Var("$person")})
        head = Rule(
            id="head",
            when=(PredAtom("Person:exists", [Var("$person")]), PredAtom("Allowed", [Var("$person")])),
            ports={"person": Var("$person")},
        )
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=head)

        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(len(compiled.body_ir), 2)
        for branch in compiled.body_ir:
            self.assertIn(("pred", "Allowed", ["$__head__person"]), branch)
            self.assertEqual(branch[-1][0], "eq")
        self.assertEqual(compiled.body_ir[0][-1], ("eq", "$__head__person", "$left__person"))
        self.assertEqual(compiled.body_ir[1][-1], ("eq", "$__head__person", "$right__person"))
        self.assertEqual(tuple(len(trace.head_port_link_materializations) for trace in traces), (1, 1))

    def test_external_head_links_by_public_port_name_not_internal_var_name(self) -> None:
        source = Rule(id="source", when=(PredAtom("Person:exists", [Var("$p")]),), ports={"person": Var("$p")})
        head = Rule(id="head", when=(PredAtom("Person:exists", [Var("$different")]),), ports={"person": Var("$different")})
        plan = _lower_application_rule(source, head=head)

        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(compiled.body_ir[-1], ("eq", "$__head__different", "$source__p"))
        self.assertEqual(traces[0].head_port_link_materializations[0].source_port_name, "person")

    def test_projection_head_links_without_materializing_placeholder_atoms(self) -> None:
        body = _person_region_rule()
        head = Rule.projection("region", "person")
        plan = _lower_application_rule(body, head=head)

        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(plan.head_binding.kind, "projection")
        self.assertEqual(compiled.heads[0].head_var_names, ("$__projection_0", "$__projection_1"))
        self.assertNotIn("__factgraph_projection_placeholder", repr(compiled.body_ir))
        self.assertEqual(compiled.body_ir[-2], ("eq", "$__projection_1", "$person_region__p"))
        self.assertEqual(compiled.body_ir[-1], ("eq", "$__projection_0", "$person_region__region"))
        self.assertEqual(
            tuple(link.head_port_name for link in traces[0].head_port_link_materializations),
            ("person", "region"),
        )

    def test_aggregate_atom_survives_native_materialization(self) -> None:
        amount = Var("$amount")
        order = Var("$order")
        aggregate = AggregateAtom("sum", amount, [PredAtom("OrderAmount", [order, amount])])
        rule = Rule(
            id="amount_sum",
            when=(CmpAtom("eq", Var("$total"), aggregate),),
            ports={"total": Var("$total")},
        )

        compiled, _traces = _materialize_native_derivation_plan(_lower_application_rule(rule, head=rule))

        self.assertEqual(
            compiled.body_ir,
            [
                (
                    "eq",
                    "$amount_sum__total",
                    ("sum", "$amount_sum__amount", [("pred", "OrderAmount", ["$amount_sum__order", "$amount_sum__amount"])]),
                )
            ],
        )


class RuleExprNativeExecutionTests(unittest.TestCase):
    def test_private_native_execution_returns_candidate_sets(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice")
        rule = _person_exists_rule()
        copy = Rule(id="person_exists_copy", when=(PredAtom("Person:exists", [Var("$q")]),), ports={"person": Var("$q")})

        candidates = _evaluate_rule_expr_native_for_tests(
            rule.as_("exists") & copy.as_("copy"),
            head=rule,
            store=store,
        )

        self.assertTrue(candidates)
        self.assertTrue(all(isinstance(candidate, CandidateSet) for candidate in candidates))
        self.assertIn(encoded, str(candidates[0].payload))

    def test_trace_tuple_is_per_branch(self) -> None:
        rule = _person_exists_rule()
        other = Rule(id="Other:exists", when=(PredAtom("Other:exists", [Var("$o")]),), ports={"other": Var("$o")})
        plan = _lower_rule_expr(rule.as_("a") | other.as_("b"), head=rule)

        compiled, traces = _materialize_native_derivation_plan(plan)

        self.assertEqual(len(traces), 2)
        self.assertEqual(tuple(trace.runtime_case_index for trace in traces), (0, 1))
        self.assertEqual(tuple(trace.branch_id for trace in traces), ("b0", "b1"))
        self.assertEqual(compiled.body_ir[0][0][0], "pred")
        self.assertIsInstance(traces[0], RuleExprEvaluationTrace)


if __name__ == "__main__":
    unittest.main()
