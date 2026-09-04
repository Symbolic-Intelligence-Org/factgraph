from __future__ import annotations

import unittest

from factgraph.application.protocol import Rule
from factgraph.core.rules.where_ast import BuiltinAtom, CmpAtom, Const, PredAtom
from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.dsl import DSLToApplicationRuleError, Pred, build_application_rule, vars
from factgraph.sdk.dsl.expr import RuleRefAtom


class User(Entity):
    user_id: str = Identity()
    status: str = Field()
    name: str = Field()


class LivesIn(Entity):
    edge_id: str = Identity()
    user: str = Field()
    country: str = Field()


def _pred_ids(rule: Rule) -> list[str]:
    return [atom.pred_id for atom in rule.when if isinstance(atom, PredAtom)]


def _pred(rule: Rule, pred_id: str) -> PredAtom:
    for atom in rule.when:
        if isinstance(atom, PredAtom) and atom.pred_id == pred_id:
            return atom
    raise AssertionError(f"missing pred atom: {pred_id}")


class BuildApplicationRuleUnifiedFormsTests(unittest.TestCase):
    def test_bare_existence(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="active_user",
                when=[User(u)],
                ports={"user": u},
            )

        self.assertIsInstance(rule, Rule)
        self.assertEqual(_pred_ids(rule), ["User:exists"])
        self.assertEqual(rule.ports["user"], _pred(rule, "User:exists").terms[0])

    def test_identity_literal_equality_emits_existence_pred(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="user_by_id",
                when=[User(u).user_id == "u-2"],
                ports={"user": u},
            )

        self.assertEqual(_pred_ids(rule), ["User:exists", "user:user_id"])
        self.assertEqual(_pred(rule, "user:user_id").terms[0], rule.ports["user"])
        self.assertEqual(_pred(rule, "user:user_id").terms[1], Const("u-2", _pred(rule, "user:user_id").terms[1].origin))

    def test_field_literal_equality_emits_existence_pred(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="active_user",
                when=[User(u).status == "active"],
                ports={"user": u},
            )

        self.assertEqual(_pred_ids(rule), ["User:exists", "user:status"])

    def test_ellipsis_anonymous_field_equality_does_not_require_port(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="named_users_exist",
                when=[User(u), User(...).name == "alice"],
                ports={"user": u},
            )

        self.assertEqual(_pred_ids(rule), ["User:exists", "User:exists", "user:name"])
        self.assertNotEqual(rule.when[0].terms[0], rule.when[1].terms[0])

    def test_cross_entity_ref_emits_both_existence_preds(self) -> None:
        with vars("li", "u") as (li, u):
            rule = build_application_rule(
                id="lives_in_user",
                when=[LivesIn(li).user == User(u)],
                ports={"edge": li, "user": u},
            )

        self.assertEqual(_pred_ids(rule), ["LivesIn:exists", "User:exists", "livesin:user"])
        self.assertEqual(_pred(rule, "livesin:user").terms[0], rule.ports["edge"])
        self.assertEqual(_pred(rule, "livesin:user").terms[1], rule.ports["user"])

    def test_field_to_named_var_equality(self) -> None:
        with vars("li", "country") as (li, country):
            rule = build_application_rule(
                id="lives_in_country",
                when=[LivesIn(li).country == country],
                ports={"edge": li, "country": country},
            )

        self.assertEqual(_pred_ids(rule), ["LivesIn:exists", "livesin:country"])
        self.assertEqual(_pred(rule, "livesin:country").terms[1], rule.ports["country"])


class BuildApplicationRuleRejectTests(unittest.TestCase):
    def test_rejects_bare_attr_ref_compare(self) -> None:
        with vars("u") as (u,), self.assertRaises(DSLToApplicationRuleError):
            build_application_rule(
                id="legacy_bare_attr",
                when=[u.status == "active"],
                ports={"user": u},
            )

    def test_rejects_two_line_legacy_form(self) -> None:
        with vars("u") as (u,), self.assertRaises(DSLToApplicationRuleError):
            build_application_rule(
                id="legacy_two_line",
                when=[User(u), u.status == "active"],
                ports={"user": u},
            )

    def test_rejects_raw_pred(self) -> None:
        with vars("u") as (u,), self.assertRaises(DSLToApplicationRuleError):
            build_application_rule(
                id="legacy_pred",
                when=[Pred("User:exists", u)],
                ports={"user": u},
            )

    def test_rejects_rule_ref_atom(self) -> None:
        with vars("u") as (u,), self.assertRaises(DSLToApplicationRuleError):
            build_application_rule(
                id="legacy_rule_ref",
                when=[RuleRefAtom("other", "v1", (u,))],
                ports={"user": u},
            )

    def test_rejects_or_shape(self) -> None:
        with vars("u", "v") as (u, v), self.assertRaises(DSLToApplicationRuleError):
            build_application_rule(
                id="or_shape",
                when=[[User(u)], [User(v)]],
                ports={"user": u},
            )

    def test_rejects_anonymous_port(self) -> None:
        anon = User(...).var
        with self.assertRaises(DSLToApplicationRuleError):
            build_application_rule(
                id="anonymous_port",
                when=[User(...).status == "active"],
                ports={"user": anon},
            )


class BuildApplicationRuleIdentityTests(unittest.TestCase):
    def test_content_digest_and_repr_render_are_available(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="active_user",
                when=[User(u).status == "active"],
                ports={"user": u},
                repr="active user %user",
            )

        self.assertIsInstance(rule.content_digest, str)
        self.assertEqual(rule.render_repr(), "active user <user>")
        self.assertEqual(rule.render_repr({"user": "u-1"}), "active user u-1")

    def test_application_rule_from_bridge_supports_occurrence_alias(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="active_user",
                when=[User(u).status == "active"],
                ports={"user": u},
            )

        occurrence = rule.as_("a")
        self.assertEqual(occurrence.alias, "a")
        self.assertEqual(occurrence.user.port_name, "user")


class BuildApplicationRuleArithmeticTests(unittest.TestCase):
    def test_logic_var_add_constant_lowers_to_addc_builtin(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="user_plus_one",
                when=[(u + 1) == 3],
                ports={"user": u},
            )

        self.assertEqual([type(atom) for atom in rule.when], [BuiltinAtom, CmpAtom])
        builtin = rule.when[0]
        compare = rule.when[1]
        self.assertIsInstance(builtin, BuiltinAtom)
        self.assertIsInstance(compare, CmpAtom)
        self.assertEqual(builtin.op, "addc")
        self.assertEqual(compare.op, "eq")

    def test_logic_var_mul_constant_lowers_to_mulc_builtin(self) -> None:
        with vars("u") as (u,):
            rule = build_application_rule(
                id="user_times_two",
                when=[(u * 2) == 6],
                ports={"user": u},
            )

        builtin = rule.when[0]
        self.assertIsInstance(builtin, BuiltinAtom)
        self.assertEqual(builtin.op, "mulc")


if __name__ == "__main__":
    unittest.main()
