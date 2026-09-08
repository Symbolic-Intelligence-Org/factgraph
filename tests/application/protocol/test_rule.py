from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from types import MappingProxyType

from factgraph.application.protocol import Rule, RuleOccurrence, RulePortRef, RuleValidationError
from factgraph.application.protocol.rule import PortType
from factgraph.core.rules.where_ast import (
    AndExpr,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    RuleRefAtom,
    Var,
)
from factgraph.sdk.dsl.expr import ExistsAtom as SDKExistsAtom
from factgraph.sdk.dsl.expr import LogicVar as SDKLogicVar


class RuleConstructionTests(unittest.TestCase):
    def test_rule_requires_non_empty_id(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(id="", when=(PredAtom("User:exists", [u]),), ports={"user": u})

    def test_rule_requires_non_empty_tuple_where(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(id="r1", when=(), ports={"user": u})

    def test_rule_requires_var_ports(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(
                id="r1",
                when=(PredAtom("User:exists", [u]),),
                ports={"user": Const("u")},  # type: ignore[dict-item]
            )


class AtomKindAllowlistTests(unittest.TestCase):
    def test_five_core_atom_kinds_are_allowed(self) -> None:
        u = Var("u")
        atoms = (
            PredAtom("User:exists", [u]),
            CmpAtom("eq", u, Const("u-1")),
            InAtom(u, [Const("u-1"), Const("u-2")]),
            BuiltinAtom("add", [u, Const(1)]),
            NotAtom(AndExpr([CmpAtom("ne", u, Const("blocked"))])),
        )
        rule = Rule(id="r1", when=atoms, ports={"user": u})
        self.assertEqual(rule.when, atoms)

    def test_rule_ref_atom_is_rejected(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(id="r1", when=(RuleRefAtom("other", "v1", [u]),), ports={"user": u})

    def test_sdk_dsl_types_are_rejected(self) -> None:
        u = SDKLogicVar("u")
        with self.assertRaises(RuleValidationError):
            Rule(
                id="r1",
                when=(SDKExistsAtom("User", u),),  # type: ignore[arg-type]
                ports={"user": Var("u")},
            )


class PortValidationTests(unittest.TestCase):
    def test_port_var_must_appear_in_where(self) -> None:
        u = Var("u")
        region = Var("region")
        with self.assertRaises(RuleValidationError):
            Rule(id="r1", when=(PredAtom("User:exists", [u]),), ports={"region": region})

    def test_port_types_infer_entity_ref_and_value(self) -> None:
        u = Var("u")
        status = Var("status")
        rule = Rule(
            id="r1",
            when=(
                PredAtom("User:exists", [u]),
                CmpAtom("eq", status, Const("active")),
            ),
            ports={"user": u, "status": status},
        )
        self.assertEqual(rule.port_types["user"], PortType(kind="entity_ref", entity_type="User"))
        self.assertEqual(rule.port_types["status"], PortType(kind="value"))


class ReprRenderTests(unittest.TestCase):
    def test_render_repr_uses_placeholders_for_unbound_ports(self) -> None:
        u = Var("u")
        rule = Rule(
            id="r1",
            when=(PredAtom("User:exists", [u]),),
            ports={"user": u},
            repr="user %user is active",
        )
        self.assertEqual(rule.render_repr(), "user <user> is active")
        self.assertEqual(rule.render_repr({"user": "u-1"}), "user u-1 is active")

    def test_repr_rejects_undeclared_port(self) -> None:
        u = Var("u")
        with self.assertRaises(RuleValidationError):
            Rule(
                id="r1",
                when=(PredAtom("User:exists", [u]),),
                ports={"user": u},
                repr="user %missing",
            )


class RuleIdentityTests(unittest.TestCase):
    def test_atom_ids_are_positional(self) -> None:
        u = Var("u")
        rule = Rule(
            id="active_user",
            when=(PredAtom("User:exists", [u]), CmpAtom("eq", u, Const("u-1"))),
            ports={"user": u},
        )
        self.assertEqual(rule.atom_ids, ("active_user:atom_0", "active_user:atom_1"))

    def test_content_digest_is_deterministic_and_order_sensitive(self) -> None:
        u = Var("u")
        a = PredAtom("User:exists", [u])
        b = CmpAtom("eq", u, Const("u-1"))
        first = Rule(id="r1", when=(a, b), ports={"user": u})
        same = Rule(id="r2", when=(a, b), ports={"user": u})
        same_with_repr = Rule(id="r1", when=(a, b), ports={"user": u}, repr="user %user")
        reordered = Rule(id="r1", when=(b, a), ports={"user": u})
        self.assertEqual(first.content_digest, same.content_digest)
        self.assertEqual(first.content_digest, same_with_repr.content_digest)
        self.assertNotEqual(first.content_digest, reordered.content_digest)


class ImmutabilityTests(unittest.TestCase):
    def test_rule_container_is_shallow_immutable(self) -> None:
        u = Var("u")
        rule = Rule(id="r1", when=(PredAtom("User:exists", [u]),), ports={"user": u})
        with self.assertRaises(FrozenInstanceError):
            rule.id = "other"  # type: ignore[misc]
        self.assertIsInstance(rule.ports, MappingProxyType)
        with self.assertRaises(TypeError):
            rule.ports["other"] = u  # type: ignore[index]
        with self.assertRaises(AttributeError):
            rule.when.append(PredAtom("User:exists", [u]))  # type: ignore[attr-defined]


class RuleOccurrenceTests(unittest.TestCase):
    def _rule(self, *, rule_id: str = "active_user", var_name: str = "u") -> Rule:
        user = Var(var_name)
        return Rule(
            id=rule_id,
            when=(PredAtom("User:exists", [user]),),
            ports={"user": user},
        )

    def test_as_default_alias_uses_rule_id(self) -> None:
        rule = self._rule()
        occurrence = rule.as_()

        self.assertEqual(occurrence, RuleOccurrence(rule=rule, alias="active_user"))
        self.assertEqual(occurrence.alias, "active_user")
        self.assertIs(occurrence.rule, rule)

    def test_as_explicit_alias_returns_occurrence(self) -> None:
        rule = self._rule()
        occurrence = rule.as_("a")

        self.assertEqual(occurrence.alias, "a")
        self.assertIs(occurrence.rule, rule)

    def test_repeated_alias_calls_use_value_equality_not_interning(self) -> None:
        rule = self._rule()
        first = rule.as_("a")
        second = rule.as_("a")

        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_invalid_aliases_raise(self) -> None:
        rule = self._rule()
        for alias in ("", "1a", "_a", "a-b"):
            with self.subTest(alias=alias), self.assertRaises(RuleValidationError):
                rule.as_(alias)

    def test_non_identifier_rule_id_default_alias_raises(self) -> None:
        rule = self._rule(rule_id="bad-rule")

        with self.assertRaises(RuleValidationError):
            rule.as_()

        self.assertEqual(rule.as_("good_alias").alias, "good_alias")

    def test_port_reference_exposes_occurrence_port_details(self) -> None:
        rule = self._rule()
        occurrence = rule.as_("a")

        ref = occurrence.port("user")
        self.assertEqual(
            ref,
            RulePortRef(
                occurrence_alias="a",
                rule_id="active_user",
                port_name="user",
                var=rule.ports["user"],
                port_type=PortType(kind="entity_ref", entity_type="User"),
            ),
        )
        self.assertEqual(occurrence.user, ref)

    def test_missing_port_errors_follow_explicit_vs_attribute_conventions(self) -> None:
        occurrence = self._rule().as_("a")

        with self.assertRaises(RuleValidationError):
            occurrence.port("missing")
        with self.assertRaises(AttributeError):
            _ = occurrence.missing
        with self.assertRaises(AttributeError):
            _ = occurrence.__private

    def test_occurrence_and_port_ref_are_frozen_and_hashable(self) -> None:
        occurrence = self._rule().as_("a")
        ref = occurrence.user

        with self.assertRaises(FrozenInstanceError):
            occurrence.alias = "b"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            ref.port_name = "other"  # type: ignore[misc]
        self.assertIsInstance(hash(occurrence), int)
        self.assertIsInstance(hash(ref), int)

    def test_content_digest_is_alias_independent(self) -> None:
        rule = self._rule()
        before = rule.content_digest

        _ = rule.as_("a")
        _ = rule.as_("b")

        self.assertEqual(rule.content_digest, before)

    def test_same_port_name_with_different_internal_vars_preserves_port_contract(self) -> None:
        left = self._rule(rule_id="left_rule", var_name="u")
        right = self._rule(rule_id="right_rule", var_name="uid")

        left_ref = left.as_("left").user
        right_ref = right.as_("right").user

        self.assertEqual(left_ref.port_name, right_ref.port_name)
        self.assertNotEqual(left_ref.var, right_ref.var)


if __name__ == "__main__":
    unittest.main()
