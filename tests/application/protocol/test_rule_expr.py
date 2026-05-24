from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest
from typing import get_type_hints

import factgraph.sdk as sdk
from factgraph.application.protocol import ExplicitBoolError, Rule, RuleExpr, RuleExprError, RuleJoinConstraint
from factgraph.application.protocol.rule_expr import (
    _AndGroup,
    _OrGroup,
    _RuleExpr,
    _RuleOperand,
    _coerce_rule_expr_operand,
)
from factgraph.application.protocol.rule import PortType, RulePortRef
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk.dsl.errors import SDKDSLError


def _rule(rule_id: str, *, var_name: str = "u") -> Rule:
    var = Var(var_name)
    return Rule(id=rule_id, where=(PredAtom("User:exists", [var]),), ports={"user": var})


def _rule_with_two_ports(rule_id: str) -> Rule:
    user = Var("u")
    region = Var("r")
    return Rule(
        id=rule_id,
        where=(PredAtom("User:exists", [user]), PredAtom("Region:exists", [region])),
        ports={"user": user, "region": region},
    )


class RuleExprExportTests(unittest.TestCase):
    def test_sdk_exports_public_ruleexpr_names(self) -> None:
        self.assertIs(sdk.RuleExpr, RuleExpr)
        self.assertIs(sdk.RuleExprError, RuleExprError)
        self.assertIs(sdk.ExplicitBoolError, ExplicitBoolError)
        self.assertIs(sdk.RuleJoinConstraint, RuleJoinConstraint)
        self.assertIn("RuleExpr", sdk.__all__)
        self.assertIn("RuleExprError", sdk.__all__)
        self.assertIn("ExplicitBoolError", sdk.__all__)
        self.assertIn("RuleJoinConstraint", sdk.__all__)

    def test_sdk_does_not_export_internal_or_module_level_factory_names(self) -> None:
        self.assertNotIn("_RuleExpr", sdk.__all__)
        self.assertNotIn("_AndGroup", sdk.__all__)
        self.assertNotIn("_OrGroup", sdk.__all__)
        self.assertFalse(hasattr(sdk, "_RuleExpr"))
        self.assertFalse(hasattr(sdk, "_AndGroup"))
        self.assertFalse(hasattr(sdk, "_OrGroup"))
        self.assertFalse(hasattr(sdk, "all"))
        self.assertFalse(hasattr(sdk, "any"))

    def test_error_hierarchy_uses_sdk_dsl_bucket(self) -> None:
        self.assertTrue(issubclass(RuleExprError, SDKDSLError))
        self.assertTrue(issubclass(ExplicitBoolError, RuleExprError))


class RuleExprOperatorTests(unittest.TestCase):
    def test_application_rule_operators_and_factories_produce_ruleexpr_values(self) -> None:
        left = _rule("left")
        right = _rule("right", var_name="r")

        self.assertIsInstance(left & right, _RuleExpr)
        self.assertIsInstance(left | right, _RuleExpr)
        self.assertEqual(RuleExpr.all(left, right), left & right)
        self.assertEqual(RuleExpr.any(left, right), left | right)

    def test_factories_are_ruleexpr_class_attributes_not_sdk_functions(self) -> None:
        self.assertTrue(callable(RuleExpr.all))
        self.assertTrue(callable(RuleExpr.any))
        self.assertFalse(hasattr(sdk, "all"))
        self.assertFalse(hasattr(sdk, "any"))

    def test_same_kind_groups_flatten_and_are_commutative(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")
        c = _rule("c", var_name="c")

        self.assertEqual((a & b) & c, a & (b & c))
        self.assertEqual((a | b) | c, a | (b | c))
        self.assertEqual(a & b, b & a)
        self.assertEqual(a | b, b | a)
        self.assertEqual(hash(a & b), hash(b & a))
        self.assertNotEqual(a & b, a | b)

    def test_duplicate_operands_preserve_multiplicity(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")

        a1 = a.as_("a1")
        a2 = a.as_("a2")

        self.assertEqual(a1 & a2 & b, b & a1 & a2)
        self.assertNotEqual(a1 & b, a1 & a2 & b)

    def test_rule_occurrence_operands_are_accepted(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")

        expr = a.as_("left") & b.as_("right")

        self.assertIsInstance(expr, _RuleExpr)
        self.assertEqual(expr, RuleExpr.all(a.as_("left"), b.as_("right")))
        self.assertNotEqual(expr, a.as_("other") & b.as_("right"))

    def test_repeated_same_rule_requires_all_explicit_aliases(self) -> None:
        a = _rule("a")

        with self.assertRaisesRegex(RuleExprError, "multiple times without explicit aliases"):
            _ = a & a
        with self.assertRaisesRegex(RuleExprError, "multiple times without explicit aliases"):
            _ = a & a.as_("other")

        self.assertIsInstance(a.as_("one") & a.as_("two"), _RuleExpr)

    def test_duplicate_aliases_are_rejected(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")

        with self.assertRaisesRegex(RuleExprError, "duplicate alias 'same'"):
            _ = a.as_("same") & b.as_("same")

    def test_expression_scope_diagnostics_are_aggregated_and_stable(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")

        with self.assertRaises(RuleExprError) as ctx:
            RuleExpr.all(a, a.as_("a2"), b.as_("a"))

        message = str(ctx.exception)
        self.assertIn("duplicate alias 'a'", message)
        self.assertIn("rule 'a' appears multiple times without explicit aliases", message)
        self.assertLess(message.index("duplicate alias 'a'"), message.index("rule 'a'"))

    def test_bare_rule_default_alias_must_be_identifier_shaped(self) -> None:
        rule = _rule("bad-rule")

        with self.assertRaisesRegex(RuleExprError, r"use \.as_\(\.\.\.\)"):
            _ = rule & _rule("other", var_name="o")

    def test_factories_apply_expression_scope_validation(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")

        self.assertEqual(RuleExpr.all(a.as_("a1"), a.as_("a2"), b), a.as_("a1") & a.as_("a2") & b)
        with self.assertRaisesRegex(RuleExprError, "duplicate alias 'same'"):
            RuleExpr.any(a.as_("same"), b.as_("same"))

    def test_rule_operand_type_precision_and_alias_metadata(self) -> None:
        rule = _rule("a")
        bare = _coerce_rule_expr_operand(rule)
        explicit = _coerce_rule_expr_operand(rule.as_("explicit"))

        self.assertIsInstance(bare, _RuleOperand)
        self.assertIsInstance(explicit, _RuleOperand)
        self.assertIs(bare.rule, rule)
        self.assertEqual(bare.alias, "a")
        self.assertFalse(bare.explicit_alias)
        self.assertEqual(explicit.alias, "explicit")
        self.assertTrue(explicit.explicit_alias)

        from factgraph.application.protocol.rule import Rule as ApplicationRule

        self.assertIs(get_type_hints(_RuleOperand)["rule"], ApplicationRule)
        self.assertEqual(ApplicationRule.__and__.__annotations__["return"], "_RuleExpr")
        self.assertEqual(ApplicationRule.__or__.__annotations__["return"], "_RuleExpr")

    def test_ruleexpr_values_are_immutable(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")
        atom = _coerce_rule_expr_operand(a)
        and_group = a & b
        or_group = a | b

        with self.assertRaises(FrozenInstanceError):
            atom.rule = b  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            atom.alias = "other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            and_group.children = (atom,)  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            or_group.children = (atom,)  # type: ignore[misc]
        self.assertIsInstance(and_group, _AndGroup)
        self.assertIsInstance(or_group, _OrGroup)
        self.assertIsInstance(hash(and_group), int)


class RuleExprBoolAndCoercionTests(unittest.TestCase):
    def test_bool_guards_raise_explicit_bool_error(self) -> None:
        rule = _rule("a")

        with self.assertRaisesRegex(ExplicitBoolError, "use & or \\|"):
            bool(rule)
        with self.assertRaisesRegex(ExplicitBoolError, "use & or \\|"):
            bool(rule & _rule("b", var_name="b"))

    def test_legacy_sdk_rule_truthiness_is_unchanged(self) -> None:
        legacy = sdk.Rule(id="legacy", version="v1", select=["$u"], where=[("pred", "User:exists", ["$u"])])

        self.assertNotIn("__bool__", sdk.Rule.__dict__)
        self.assertTrue(bool(legacy))

    def test_coerce_accepts_application_rule_and_ruleexpr_values(self) -> None:
        rule = _rule("a")
        expr = rule & _rule("b", var_name="b")

        self.assertIsInstance(_coerce_rule_expr_operand(rule), _RuleExpr)
        self.assertIs(_coerce_rule_expr_operand(expr), expr)

    def test_coerce_rejects_legacy_sdk_rule_and_arbitrary_objects(self) -> None:
        legacy = sdk.Rule(id="legacy", version="v1", select=["$u"], where=[("pred", "User:exists", ["$u"])])

        with self.assertRaisesRegex(RuleExprError, "legacy SDK Rule"):
            _coerce_rule_expr_operand(legacy)
        with self.assertRaisesRegex(RuleExprError, "application protocol Rule or RuleExpr"):
            _coerce_rule_expr_operand(object())

    def test_legacy_sdk_rule_operands_are_rejected_with_guidance(self) -> None:
        legacy = sdk.Rule(id="legacy", version="v1", select=["$u"], where=[("pred", "User:exists", ["$u"])])

        with self.assertRaisesRegex(RuleExprError, "build_application_rule"):
            _ = _rule("a") & legacy

    def test_application_rule_equality_and_hash_do_not_cross_compare_ruleexpr(self) -> None:
        rule = _rule("a")
        expr = rule & _rule("b", var_name="b")
        rule_eq = Rule.__eq__
        rule_hash = Rule.__hash__

        self.assertNotEqual(rule, expr)
        self.assertIs(Rule.__eq__, rule_eq)
        self.assertIs(Rule.__hash__, rule_hash)
        self.assertFalse(expr == object())

    def test_empty_factories_reject(self) -> None:
        with self.assertRaises(RuleExprError):
            RuleExpr.all()
        with self.assertRaises(RuleExprError):
            RuleExpr.any()


class RuleExprJoinTests(unittest.TestCase):
    def test_rule_port_ref_eq_returns_frozen_join_constraint(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        constraint = a.user.eq(b.user)

        self.assertEqual(constraint, RuleJoinConstraint(left=a.user, right=b.user))
        self.assertEqual(constraint.op, "eq")
        self.assertEqual(hash(constraint), hash(b.user.eq(a.user)))
        with self.assertRaises(FrozenInstanceError):
            constraint.left = b.user  # type: ignore[misc]

    def test_rule_port_ref_value_equality_is_preserved(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        self.assertIs(a.user == b.user, False)
        self.assertEqual(a.user, RulePortRef("a", "a", "user", Var("u"), PortType("entity_ref", "User")))

    def test_join_constraint_shape_validation_is_defensive(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "left must be RulePortRef"):
            RuleJoinConstraint(left=object(), right=b.user)  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuleExprError, "right must be RulePortRef"):
            RuleJoinConstraint(left=a.user, right=object())  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuleExprError, "op must be 'eq'"):
            RuleJoinConstraint(left=a.user, right=b.user, op="ne")  # type: ignore[arg-type]

    def test_same_occurrence_join_constraints_are_rejected(self) -> None:
        a = _rule_with_two_ports("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "distinct Rule occurrences"):
            a.user.eq(a.user)
        with self.assertRaisesRegex(RuleExprError, "distinct Rule occurrences"):
            a.user.eq(a.region)
        with self.assertRaisesRegex(RuleExprError, "distinct Rule occurrences"):
            (a & b).join(RuleJoinConstraint(left=a.user, right=a.region))

    def test_and_group_join_returns_new_immutable_group(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")
        expr = a & b
        constraint = a.user.eq(b.user)

        joined = expr.join(constraint)

        self.assertIsInstance(expr, _AndGroup)
        self.assertIsInstance(joined, _AndGroup)
        self.assertNotEqual(expr, joined)
        self.assertEqual(expr.joins, ())
        self.assertEqual(joined.joins, (constraint,))
        with self.assertRaises(FrozenInstanceError):
            joined.joins = ()  # type: ignore[misc]

    def test_join_symmetry_and_duplicate_normalization(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        left = (a & b).join(a.user.eq(b.user), a.user.eq(b.user))
        right = (b & a).join(b.user.eq(a.user))

        self.assertEqual(left, right)
        self.assertEqual(hash(left), hash(right))
        self.assertEqual(len(left.joins), 1)

    def test_flatten_merge_preserves_and_revalidates_joins(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")
        c = _rule("c", var_name="c").as_("c")

        left = (a & b).join(a.user.eq(b.user)) & c
        right = (c & b & a).join(b.user.eq(a.user))

        self.assertEqual(left, right)
        self.assertIsInstance(left, _AndGroup)
        self.assertEqual(len(left.children), 3)
        self.assertEqual(len(left.joins), 1)

    def test_join_reach_rejects_or_branch_endpoints(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")
        c = _rule("c", var_name="c").as_("c")

        with self.assertRaisesRegex(RuleExprError, "not reachable"):
            (a & (b | c)).join(a.user.eq(b.user))

        self.assertIsInstance((a & b).join(a.user.eq(b.user)) | c, _OrGroup)

    def test_join_is_and_only(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "at least one"):
            (a & b).join()
        with self.assertRaisesRegex(RuleExprError, "AND groups"):
            (a | b).join(a.user.eq(b.user))
        self.assertFalse(hasattr(_rule("r"), "join"))
        self.assertFalse(hasattr(a, "join"))

    def test_join_rejects_non_constraints_and_mismatched_endpoint_fields(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "RuleJoinConstraint"):
            (a & b).join(object())  # type: ignore[arg-type]

        mismatched = RulePortRef(
            occurrence_alias="a",
            rule_id="a",
            port_name="user",
            var=Var("not_the_rule_port"),
            port_type=a.user.port_type,
        )
        with self.assertRaisesRegex(RuleExprError, "Var does not match"):
            (a & b).join(RuleJoinConstraint(left=mismatched, right=b.user))


class RuleExprJoinByPortsTests(unittest.TestCase):
    def test_join_by_ports_matches_explicit_join(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        self.assertEqual((a & b).join_by_ports("user"), (a & b).join(a.user.eq(b.user)))

    def test_join_by_ports_pairwise_expands_more_than_two_occurrences(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")
        c = _rule("c", var_name="c").as_("c")

        joined = (a & b & c).join_by_ports("user")
        explicit = (c & b & a).join(c.user.eq(b.user), c.user.eq(a.user), b.user.eq(a.user))

        self.assertEqual(joined, explicit)
        self.assertEqual(hash(joined), hash(explicit))
        self.assertEqual(len(joined.joins), 3)

    def test_join_by_ports_reports_missing_and_fewer_than_two_names_in_stable_order(self) -> None:
        a = _rule_with_two_ports("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaises(RuleExprError) as ctx:
            (a & b).join_by_ports("region", "active")

        message = str(ctx.exception)
        self.assertIn("port 'active' is not present", message)
        self.assertIn("port 'region' is present on fewer than two", message)
        self.assertLess(message.index("port 'active'"), message.index("port 'region'"))

    def test_join_by_ports_rejects_duplicate_requested_names(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "duplicate requested port name 'user'"):
            (a & b).join_by_ports("user", "user")

    def test_join_by_ports_rejects_zero_empty_and_non_string_names(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "at least one"):
            (a & b).join_by_ports()
        with self.assertRaisesRegex(RuleExprError, "non-empty strings"):
            (a & b).join_by_ports("")
        with self.assertRaisesRegex(RuleExprError, "non-empty strings"):
            (a & b).join_by_ports(123)  # type: ignore[arg-type]

    def test_join_by_ports_is_and_only(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")

        with self.assertRaisesRegex(RuleExprError, "AND groups"):
            (a | b).join_by_ports("user")
        self.assertFalse(hasattr(_rule("r"), "join_by_ports"))
        self.assertFalse(hasattr(a, "join_by_ports"))

    def test_join_by_ports_does_not_reach_into_or_branches(self) -> None:
        a = _rule("a").as_("a")
        b = _rule("b", var_name="b").as_("b")
        c = _rule("c", var_name="c").as_("c")

        with self.assertRaisesRegex(RuleExprError, "fewer than two"):
            (a & (b | c)).join_by_ports("user")

    def test_join_by_ports_preserves_export_scope(self) -> None:
        self.assertNotIn("join_by_ports", sdk.__all__)
        self.assertFalse(hasattr(sdk, "join_by_ports"))


if __name__ == "__main__":
    unittest.main()
