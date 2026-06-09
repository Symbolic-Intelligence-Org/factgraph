from __future__ import annotations

import unittest

import factgraph.application.explain.prober as prober_module
from factgraph.application import build_schema_index, entity_info, field_predicate
from factgraph.application.explain import EvidenceJoin, Holds, NotReached, probe_native
from factgraph.application.schema_runtime import encode_entity_ref
from factgraph.application.protocol import EntityRef, Rule
from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule, _lower_rule_expr
from factgraph.core.rules.where_ast import CmpAtom, Const, InAtom, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


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

    def test_fact_repr_baking_uses_schema_template_and_entity_renderer(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="user_country",
            when=(PredAtom("display_user:country", [user, country]),),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = EntityRef("DisplayUser", {"user_id": "u-1"})
        calls: list[tuple[str, dict[str, object]]] = []
        original = prober_module.schema_runtime.render_entity_repr

        def spy_render_entity_repr(index, entity_type, identity_values):  # type: ignore[no-untyped-def]
            calls.append((entity_type, dict(identity_values)))
            return original(index, entity_type, identity_values)

        prober_module.schema_runtime.render_entity_repr = spy_render_entity_repr
        try:
            result = probe_native(
                plan,
                {},
                {"display_user:country": [(user_ref, "US")]},
                schema_index=schema_index,
            )
        finally:
            prober_module.schema_runtime.render_entity_repr = original

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "User u-1 lives in US")
        self.assertEqual(calls, [("DisplayUser", {"user_id": "u-1"})])

    def test_fact_repr_baking_recovers_bound_idref_identity_from_visible_facts(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="user_country",
            when=(PredAtom("display_user:country", [user, country]),),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        identity_pred_id = entity_info(schema_index, "DisplayUser").identity_predicates["user_id"].pred_id
        country_pred_id = field_predicate(schema_index, "DisplayUser", "country").pred_id

        result = probe_native(
            plan,
            {},
            {
                identity_pred_id: [(user_ref, "u-1")],
                country_pred_id: [(user_ref, "US")],
            },
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, "User u-1 lives in US")
        self.assertNotIn(user_ref, atom.repr_text or "")

    def test_fact_repr_baking_falls_back_when_bound_idref_identity_is_not_visible(self) -> None:
        class DisplayUser(Entity):
            class Meta:
                repr = "User %user_id"

            user_id: str = Identity()
            country: str = Field(repr="%ENT lives in %FLD")

        user = Var("$user")
        country = Var("$country")
        rule = Rule(
            id="user_country",
            when=(PredAtom("display_user:country", [user, country]),),
            ports={"user": user, "country": country},
        )
        plan = _lower_application_rule(rule, head=rule)
        schema_index = build_schema_index(compile_schema_from_classes([DisplayUser]))
        user_ref = encode_entity_ref(EntityRef("DisplayUser", {"user_id": "u-1"}), index=schema_index)
        country_pred_id = field_predicate(schema_index, "DisplayUser", "country").pred_id

        result = probe_native(
            plan,
            {},
            {country_pred_id: [(user_ref, "US")]},
            schema_index=schema_index,
        )

        atom = result.paths[0].rules[1].atoms[0]
        self.assertEqual(atom.repr_text, f"{user_ref} lives in US")

    def test_repr_baking_has_fallbacks_for_fact_compare_and_builtin(self) -> None:
        x = Var("$x")
        rule = Rule(
            id="fallbacks",
            when=(
                PredAtom("p", [x]),
                CmpAtom("gt", x, Const(1)),
                InAtom(x, [Const(2), Const(3)]),
            ),
            ports={"x": x},
        )
        plan = _lower_application_rule(rule, head=rule)

        result = probe_native(plan, {}, {"p": [(2,)]}, schema_index=None)

        atoms = result.paths[0].rules[1].atoms
        self.assertEqual(atoms[0].repr_text, "p(2)")
        self.assertEqual(atoms[1].repr_text, "2 > 1")
        self.assertEqual(atoms[2].repr_text, "2 is in (2, 3)")


if __name__ == "__main__":
    unittest.main()
