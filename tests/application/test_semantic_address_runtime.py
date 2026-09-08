from __future__ import annotations

import unittest

from factgraph.application import (
    ManagedRuleOccurrence,
    SemanticAddressResolutionError,
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    manage_rule_occurrence,
)
from factgraph.application.protocol import (
    Rule,
    SemanticAddressShapeError,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.core.rules.where_ast import CmpAtom, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, RuleExpr, compile_schema_from_classes


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _index():
    return build_schema_index(
        compile_schema_from_classes([Person], generated_at="2026-08-12T00:00:00Z")
    )


def _person_age_bundle():
    person, age = Var("$person"), Var("$age")
    return build_resolved_rule(
        id="person_age",
        version="1",
        when=(
            PredAtom("Person:exists", [person]),
            PredAtom("person:age", [person, age]),
        ),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        },
        schema_index=_index(),
    )


def _two_people_bundle():
    person1, person2 = Var("$person1"), Var("$person2")
    return build_resolved_rule(
        id="two_people",
        when=(
            PredAtom("Person:exists", [person1]),
            PredAtom("Person:exists", [person2]),
            CmpAtom("ne", person1, person2),
        ),
        ports={
            "person1": SemanticRulePort(person1, entity_identity("Person")),
            "person2": SemanticRulePort(person2, entity_identity("Person")),
        },
        schema_index=_index(),
    )


class SemanticAddressProtocolTests(unittest.TestCase):
    def test_address_is_structured_and_does_not_parse_dots(self) -> None:
        address = SemanticPortAddress("pair", "person.name")

        self.assertEqual(address.occurrence_alias, "pair")
        self.assertEqual(address.port_name, "person.name")
        with self.assertRaises(SemanticAddressShapeError):
            SemanticPortAddress("", "person")

class ManagedOccurrenceAddressTests(unittest.TestCase):
    def test_same_rule_under_two_aliases_has_distinct_addresses(self) -> None:
        bundle = _person_age_bundle()
        pair1 = manage_rule_occurrence(bundle, "pair1")
        pair2 = manage_rule_occurrence(bundle, "pair2")
        space = SemanticAddressSpace((pair2, pair1))

        left = space.resolve(SemanticPortAddress("pair1", "person"))
        right = space.resolve(SemanticPortAddress("pair2", "person"))

        self.assertNotEqual(left.address, right.address)
        self.assertEqual(left.semantic_contract_digest, right.semantic_contract_digest)
        self.assertNotEqual(left.execution_ref.occurrence_alias, right.execution_ref.occurrence_alias)
        self.assertEqual(left.execution_ref.var, right.execution_ref.var)

    def test_resolution_returns_exact_rule_var_endpoint_and_contract(self) -> None:
        bundle = _person_age_bundle()
        managed = manage_rule_occurrence(bundle, "pair")
        resolved = SemanticAddressSpace((managed,)).resolve(
            SemanticPortAddress("pair", "age")
        )

        self.assertIs(resolved.execution_ref.var, bundle.rule.ports["age"])
        self.assertEqual(resolved.endpoint, field_endpoint("Person", "age"))
        self.assertEqual(
            resolved.semantic_contract_digest,
            bundle.contract.semantic_contract_digest,
        )

    def test_same_endpoint_different_vars_remain_separate(self) -> None:
        bundle = _two_people_bundle()
        before_when, before_digest = bundle.rule.when, bundle.rule.content_digest
        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "pair"),))
        first = space.resolve(SemanticPortAddress("pair", "person1"))
        second = space.resolve(SemanticPortAddress("pair", "person2"))
        expression = RuleExpr.all(bundle.rule.as_("left"), bundle.rule.as_("right"))

        self.assertEqual(first.endpoint, second.endpoint)
        self.assertNotEqual(first.execution_ref.var, second.execution_ref.var)
        self.assertIs(bundle.rule.when, before_when)
        self.assertEqual(bundle.rule.content_digest, before_digest)
        self.assertEqual(expression.joins, ())

    def test_duplicate_alias_and_unknown_coordinates_fail_distinctly(self) -> None:
        bundle = _person_age_bundle()
        pair = manage_rule_occurrence(bundle, "pair")
        with self.assertRaises(SemanticAddressResolutionError) as duplicate:
            SemanticAddressSpace((pair, manage_rule_occurrence(bundle, "pair")))
        self.assertEqual(duplicate.exception.code, "DUPLICATE_OCCURRENCE_ALIAS")

        space = SemanticAddressSpace((pair,))
        cases = (
            (SemanticPortAddress("missing", "person"), "UNKNOWN_OCCURRENCE_ALIAS"),
            (SemanticPortAddress("pair", "missing"), "UNKNOWN_SEMANTIC_PORT"),
        )
        for address, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(SemanticAddressResolutionError) as ctx:
                    space.resolve(address)
                self.assertEqual(ctx.exception.code, code)

    def test_space_copies_input_and_digest_is_order_stable_and_alias_sensitive(self) -> None:
        bundle = _person_age_bundle()
        pair1 = manage_rule_occurrence(bundle, "pair1")
        pair2 = manage_rule_occurrence(bundle, "pair2")
        caller_values = [pair2, pair1]
        first = SemanticAddressSpace(caller_values)
        caller_values.clear()
        second = SemanticAddressSpace((pair1, pair2))
        renamed = SemanticAddressSpace((pair1, manage_rule_occurrence(bundle, "other")))

        self.assertEqual(tuple(item.occurrence.alias for item in first.occurrences), ("pair1", "pair2"))
        self.assertEqual(first.address_space_digest, second.address_space_digest)
        self.assertNotEqual(first.address_space_digest, renamed.address_space_digest)
        with self.assertRaises(TypeError):
            type(first)(
                occurrences=first.occurrences,
                address_space_digest="0" * 64,  # type: ignore[call-arg]
            )

    def test_occurrence_contract_splicing_rejects_at_construction(self) -> None:
        left = _person_age_bundle()
        other_person = Var("$other_person")
        right = build_resolved_rule(
            id="person_exists",
            when=(PredAtom("Person:exists", [other_person]),),
            ports={
                "person": SemanticRulePort(other_person, entity_identity("Person")),
            },
            schema_index=_index(),
        )

        with self.assertRaises(SemanticAddressResolutionError) as ctx:
            ManagedRuleOccurrence(
                occurrence=right.rule.as_("pair"),
                contract=left.contract,
            )
        self.assertEqual(ctx.exception.code, "OCCURRENCE_CONTRACT_MISMATCH")

    def test_resolution_rechecks_stale_rule_content(self) -> None:
        bundle = _person_age_bundle()
        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "pair"),))
        bundle.rule.when[1].terms[1] = Var("$changed")

        with self.assertRaises(SemanticAddressResolutionError) as ctx:
            space.resolve(SemanticPortAddress("pair", "age"))
        self.assertEqual(ctx.exception.code, "OCCURRENCE_CONTRACT_MISMATCH")

    def test_legacy_ruleexpr_needs_no_managed_address_space(self) -> None:
        value = Var("$value")
        legacy = Rule(
            id="legacy",
            when=(PredAtom("legacy:value", [value]),),
            ports={"value": value},
        )
        expr = RuleExpr.all(legacy.as_("left"), legacy.as_("right"))

        self.assertIsNotNone(expr)
        self.assertFalse(hasattr(legacy, "semantic_contract"))


if __name__ == "__main__":
    unittest.main()
