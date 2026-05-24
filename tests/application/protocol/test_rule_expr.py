from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

import factgraph.sdk as sdk
from factgraph.application.protocol import ExplicitBoolError, Rule, RuleExpr, RuleExprError
from factgraph.application.protocol.rule_expr import _AndGroup, _OrGroup, _RuleExpr, _coerce_rule_expr_operand
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk.dsl.errors import SDKDSLError


def _rule(rule_id: str, *, var_name: str = "u") -> Rule:
    var = Var(var_name)
    return Rule(id=rule_id, where=(PredAtom("User:exists", [var]),), ports={"user": var})


class RuleExprExportTests(unittest.TestCase):
    def test_sdk_exports_public_ruleexpr_names(self) -> None:
        self.assertIs(sdk.RuleExpr, RuleExpr)
        self.assertIs(sdk.RuleExprError, RuleExprError)
        self.assertIs(sdk.ExplicitBoolError, ExplicitBoolError)
        self.assertIn("RuleExpr", sdk.__all__)
        self.assertIn("RuleExprError", sdk.__all__)
        self.assertIn("ExplicitBoolError", sdk.__all__)

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

        self.assertEqual(a & a & b, b & a & a)
        self.assertNotEqual(a & b, a & a & b)

    def test_ruleexpr_values_are_immutable(self) -> None:
        a = _rule("a")
        b = _rule("b", var_name="b")
        atom = _coerce_rule_expr_operand(a)
        and_group = a & b
        or_group = a | b

        with self.assertRaises(FrozenInstanceError):
            atom.rule = b  # type: ignore[misc]
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


if __name__ == "__main__":
    unittest.main()
