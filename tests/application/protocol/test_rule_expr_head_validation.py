from __future__ import annotations

import unittest
import warnings

from factgraph.application.protocol import Rule, RuleExprError, RuleValidationError
from factgraph.application.protocol.rule_expr_lowering import (
    _declared_ports_for_rule_expr_plan,
    _lower_application_rule,
    _lower_rule_expr,
    _validate_rule_expr_head_foundation,
)
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var


def _person_exists_rule(rule_id: str = "person_exists", *, version: str | None = None) -> Rule:
    person = Var("$person")
    return Rule(
        id=rule_id,
        version=version,
        when=(PredAtom("Person:exists", [person]),),
        ports={"person": person},
    )


def _person_region_rule(rule_id: str = "person_region") -> Rule:
    person = Var("$person")
    region = Var("$region")
    return Rule(
        id=rule_id,
        when=(PredAtom("Person:exists", [person]), PredAtom("Person:region", [person, region])),
        ports={"person": person, "region": region},
    )


def _person_named_rule(rule_id: str = "person_named") -> Rule:
    name = Var("$name")
    return Rule(
        id=rule_id,
        when=(CmpAtom("eq", name, Const("alice")),),
        ports={"name": name},
    )


def _person_value_rule(rule_id: str = "person_value") -> Rule:
    value = Var("$value")
    return Rule(
        id=rule_id,
        when=(CmpAtom("eq", value, Const("alice")),),
        ports={"person": value},
    )


class RuleExprHeadValidationTests(unittest.TestCase):
    def test_inline_head_validates_and_preserves_occurrence_version(self) -> None:
        rule = _person_exists_rule(version="v1")
        plan = _lower_application_rule(rule, head=rule)

        validation = _validate_rule_expr_head_foundation(plan)

        self.assertEqual(validation.identity_state, "inline")
        self.assertEqual(validation.matched_occurrence_alias, rule.id)
        self.assertEqual(plan.occurrence_map[0].rule_version, "v1")
        self.assertEqual(tuple(port.name for port in validation.declared_ports), ("person",))

    def test_version_mismatch_warns_once_and_proceeds(self) -> None:
        body = _person_exists_rule(version="v1")
        head = _person_exists_rule(version="v2")
        plan = _lower_application_rule(body, head=head)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            validation = _validate_rule_expr_head_foundation(plan)

        self.assertEqual(validation.identity_state, "version-warning")
        self.assertTrue(validation.version_warning_emitted)
        # Filter by category/message rather than counting all caught warnings:
        # under simplefilter("always") unrelated GC ResourceWarnings (leaked
        # sqlite connections from other tests) are nondeterministically caught
        # here too and would otherwise make this count brittle.
        version_warnings = [
            w for w in caught
            if issubclass(w.category, UserWarning) and "different version" in str(w.message)
        ]
        self.assertEqual(len(version_warnings), 1)

    def test_same_id_different_digest_rejects_before_external_head_path(self) -> None:
        body = _person_exists_rule()
        head = _person_region_rule("person_exists")
        plan = _lower_application_rule(body, head=head)

        with self.assertRaisesRegex(RuleExprError, "different content digest"):
            _validate_rule_expr_head_foundation(plan)

    def test_duplicate_same_id_same_digest_rejects_as_ambiguous_inline_head(self) -> None:
        rule = _person_exists_rule()
        expr = rule.as_("left") & rule.as_("right")

        with self.assertRaisesRegex(RuleExprError, "multiple inline occurrences"):
            _lower_rule_expr(expr, head=rule)

    def test_head_port_must_be_declared_in_every_branch(self) -> None:
        left = _person_exists_rule("left")
        right = _person_named_rule("right")
        head = _person_exists_rule("head")
        plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=head)

        with self.assertRaisesRegex(RuleExprError, "only declared in some RuleExpr branches"):
            _validate_rule_expr_head_foundation(plan)

    def test_truly_undeclared_head_port_rejects(self) -> None:
        body = _person_exists_rule("body")
        unknown = Var("$unknown")
        head = Rule(
            id="head",
            when=(PredAtom("Unknown:exists", [unknown]),),
            ports={"unknown": unknown},
        )
        plan = _lower_application_rule(body, head=head)

        with self.assertRaisesRegex(RuleExprError, "is not declared by the RuleExpr"):
            _validate_rule_expr_head_foundation(plan)

    def test_same_name_ambiguity_rejects_without_explicit_join(self) -> None:
        left = _person_exists_rule("left")
        right = _person_exists_rule("right")
        plan = _lower_rule_expr(left.as_("left") & right.as_("right"), head=left)

        with self.assertRaisesRegex(RuleExprError, "ambiguous across occurrences"):
            _declared_ports_for_rule_expr_plan(plan)

    def test_explicit_eq_join_permits_same_name_declared_port(self) -> None:
        left = _person_exists_rule("left")
        right = _person_exists_rule("right")
        expr = (left.as_("left") & right.as_("right")).join(left.as_("left").person.eq(right.as_("right").person))
        plan = _lower_rule_expr(expr, head=left)

        declared = _declared_ports_for_rule_expr_plan(plan)

        self.assertEqual(tuple(port.name for port in declared), ("person",))
        self.assertEqual(declared[0].branch_sources[0].occurrence_alias, "left")

    def test_join_by_ports_permits_same_name_declared_port(self) -> None:
        left = _person_exists_rule("left")
        right = _person_exists_rule("right")
        expr = (left.as_("left") & right.as_("right")).join_by_ports("person")
        plan = _lower_rule_expr(expr, head=left)

        validation = _validate_rule_expr_head_foundation(plan)

        self.assertEqual(validation.identity_state, "inline")
        self.assertEqual(tuple(port.name for port in validation.declared_ports), ("person",))

    def test_transitive_same_name_join_chain_permits_declared_port(self) -> None:
        left = _person_exists_rule("left")
        middle = _person_exists_rule("middle")
        right = _person_exists_rule("right")
        expr = (left.as_("left") & middle.as_("middle") & right.as_("right")).join(
            left.as_("left").person.eq(middle.as_("middle").person),
            middle.as_("middle").person.eq(right.as_("right").person),
        )
        plan = _lower_rule_expr(expr, head=left)

        declared = _declared_ports_for_rule_expr_plan(plan)

        self.assertEqual(tuple(port.name for port in declared), ("person",))
        self.assertEqual(declared[0].branch_sources[0].occurrence_alias, "left")

    def test_same_name_port_type_mismatch_rejects(self) -> None:
        left = _person_exists_rule("left")
        right = _person_value_rule("right")
        plan = _lower_rule_expr(left.as_("left") & right.as_("right"), head=left)

        with self.assertRaisesRegex(RuleExprError, "incompatible same-name port types"):
            _validate_rule_expr_head_foundation(plan)

    def test_projection_construction_rejects_invalid_arguments(self) -> None:
        with self.assertRaisesRegex(RuleValidationError, "at least one"):
            Rule.projection()
        with self.assertRaisesRegex(RuleValidationError, "non-empty string"):
            Rule.projection("person", "")
        with self.assertRaisesRegex(RuleValidationError, "non-empty string"):
            Rule.projection("person", 1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuleValidationError, "duplicate"):
            Rule.projection("person", "person")

    def test_projection_head_validates_against_declared_ports_not_placeholder_types(self) -> None:
        rule = _person_region_rule()
        head = Rule.projection("region", "person")
        plan = _lower_application_rule(rule, head=head)

        validation = _validate_rule_expr_head_foundation(plan)

        self.assertEqual(plan.head_binding.kind, "projection")
        self.assertEqual(validation.identity_state, "projection")
        self.assertEqual(tuple(head.ports), ("region", "person"))
        self.assertEqual(tuple(port.name for port in validation.declared_ports), ("person", "region"))

    def test_projection_subset_validates_against_declared_ports(self) -> None:
        rule = _person_region_rule()
        plan = _lower_application_rule(rule, head=Rule.projection("region"))

        validation = _validate_rule_expr_head_foundation(plan)

        self.assertEqual(validation.identity_state, "projection")
        self.assertEqual(tuple(plan.head.ports), ("region",))

    def test_projection_undeclared_port_rejects(self) -> None:
        rule = _person_exists_rule()
        plan = _lower_application_rule(rule, head=Rule.projection("unknown"))

        with self.assertRaisesRegex(RuleExprError, "is not declared by the RuleExpr"):
            _validate_rule_expr_head_foundation(plan)


if __name__ == "__main__":
    unittest.main()
