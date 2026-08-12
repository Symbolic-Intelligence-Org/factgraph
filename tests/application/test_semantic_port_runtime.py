from __future__ import annotations

from types import MappingProxyType
import unittest

from factgraph.application import (
    SemanticPortResolutionError,
    assert_rule_contract_current,
    build_resolved_rule,
    build_schema_index,
    resolve_rule_contract,
)
from factgraph.application.protocol import (
    EntityIdentityEndpoint,
    FieldEndpoint,
    FieldPath,
    Rule,
    SemanticPortShapeError,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.core.rules.where_ast import AndExpr, CmpAtom, NotAtom, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Company(Entity):
    company_id: str = Identity()


class Person(Entity):
    employee_id: str = Identity()
    tenant_id: str = Identity()
    age: int = Field()
    score: int = Field()
    employer: Company = Field()


class Unrelated(Entity):
    code: str = Identity()


def _index(*, include_unrelated: bool = False):
    classes = [Company, Person]
    if include_unrelated:
        classes.append(Unrelated)
    return build_schema_index(
        compile_schema_from_classes(classes, generated_at="2026-08-12T00:00:00Z")
    )


def _person_age_rule() -> tuple[Rule, Var, Var]:
    person, age = Var("$person"), Var("$age")
    return (
        Rule(
            id="person_age",
            version="1",
            when=(
                PredAtom("Person:exists", [person]),
                PredAtom("person:age", [person, age]),
            ),
            ports={"person": person, "age": age},
        ),
        person,
        age,
    )


def _bindings(person: Var, value: Var, *, field: str = "age"):
    return {
        "person": SemanticRulePort(person, entity_identity("Person")),
        "age": SemanticRulePort(value, field_endpoint("Person", field)),
    }


class SemanticPortProtocolTests(unittest.TestCase):
    def test_identity_bundle_and_identity_field_are_distinct_coordinates(self) -> None:
        identity = entity_identity("Person")
        field = field_endpoint("Person", "employee_id")

        self.assertEqual(identity, EntityIdentityEndpoint("Person"))
        self.assertEqual(field, FieldEndpoint(FieldPath("Person", "employee_id")))
        self.assertNotEqual(identity, field)

    def test_protocol_values_reject_wrong_runtime_types(self) -> None:
        with self.assertRaises(SemanticPortShapeError):
            EntityIdentityEndpoint("")
        with self.assertRaises(SemanticPortShapeError):
            FieldEndpoint("Person.age")  # type: ignore[arg-type]
        with self.assertRaises(SemanticPortShapeError):
            SemanticRulePort("$person", entity_identity("Person"))  # type: ignore[arg-type]

    def test_contract_digest_is_derived_and_ports_are_frozen_copies(self) -> None:
        rule, person, age = _person_age_rule()
        authored = _bindings(person, age)
        contract = resolve_rule_contract(rule, authored, schema_index=_index())
        original_digest = contract.semantic_contract_digest

        authored.clear()

        self.assertIsInstance(contract.ports, MappingProxyType)
        self.assertEqual(set(contract.ports), {"person", "age"})
        self.assertEqual(contract.semantic_contract_digest, original_digest)
        with self.assertRaises(TypeError):
            type(contract)(
                rule_id=contract.rule_id,
                rule_version=contract.rule_version,
                rule_content_digest=contract.rule_content_digest,
                schema_digest=contract.schema_digest,
                ports=contract.ports,
                semantic_contract_digest="0" * 64,  # type: ignore[call-arg]
            )


class SemanticPortResolutionTests(unittest.TestCase):
    def test_builder_preserves_legacy_rule_and_exact_three_coordinates(self) -> None:
        legacy, person, age = _person_age_rule()
        bundle = build_resolved_rule(
            id=legacy.id,
            version=legacy.version,
            when=legacy.when,
            ports=_bindings(person, age),
            schema_index=_index(),
        )

        self.assertEqual(bundle.rule, legacy)
        self.assertEqual(bundle.rule.content_digest, legacy.content_digest)
        self.assertIs(bundle.rule.ports["person"], person)
        self.assertEqual(bundle.contract.ports["person"].endpoint, entity_identity("Person"))
        self.assertEqual(
            bundle.contract.ports["age"].endpoint,
            field_endpoint("Person", "age"),
        )

    def test_binding_keys_must_exactly_cover_rule_ports(self) -> None:
        rule, person, age = _person_age_rule()
        complete = _bindings(person, age)
        cases = (
            {"person": complete["person"]},
            {**complete, "extra": SemanticRulePort(age, field_endpoint("Person", "age"))},
        )
        for bindings in cases:
            with self.subTest(keys=tuple(bindings)):
                with self.assertRaises(SemanticPortResolutionError) as ctx:
                    resolve_rule_contract(rule, bindings, schema_index=_index())
                self.assertEqual(ctx.exception.code, "PORT_COVERAGE_MISMATCH")

    def test_equal_var_is_canonicalized_to_rule_owned_var_but_mismatch_fails(self) -> None:
        rule, person, age = _person_age_rule()
        equal_person, equal_age = Var("$person"), Var("$age")
        contract = resolve_rule_contract(
            rule,
            _bindings(equal_person, equal_age),
            schema_index=_index(),
        )
        self.assertIs(contract.ports["person"].var, person)
        self.assertIs(contract.ports["age"].var, age)

        mismatched = _bindings(person, Var("$other"))
        with self.assertRaises(SemanticPortResolutionError) as ctx:
            resolve_rule_contract(rule, mismatched, schema_index=_index())
        self.assertEqual(ctx.exception.code, "PORT_VAR_MISMATCH")

    def test_unknown_entity_and_field_have_typed_failures(self) -> None:
        rule, person, age = _person_age_rule()
        cases = (
            {
                "person": SemanticRulePort(person, entity_identity("Ghost")),
                "age": SemanticRulePort(age, field_endpoint("Person", "age")),
            },
            {
                "person": SemanticRulePort(person, entity_identity("Person")),
                "age": SemanticRulePort(age, field_endpoint("Person", "missing")),
            },
        )
        for bindings in cases:
            with self.subTest(endpoint=bindings):
                with self.assertRaises(SemanticPortResolutionError) as ctx:
                    resolve_rule_contract(rule, bindings, schema_index=_index())
                self.assertEqual(ctx.exception.code, "SEMANTIC_ENDPOINT_NOT_FOUND")

    def test_execution_type_mismatches_fail(self) -> None:
        rule, person, age = _person_age_rule()
        cases = (
            {
                "person": SemanticRulePort(person, entity_identity("Person")),
                "age": SemanticRulePort(age, entity_identity("Person")),
            },
            {
                "person": SemanticRulePort(person, field_endpoint("Person", "age")),
                "age": SemanticRulePort(age, field_endpoint("Person", "age")),
            },
        )
        for bindings in cases:
            with self.subTest(bindings=bindings):
                with self.assertRaises(SemanticPortResolutionError) as ctx:
                    resolve_rule_contract(rule, bindings, schema_index=_index())
                self.assertEqual(ctx.exception.code, "PORT_EXECUTION_TYPE_MISMATCH")

    def test_wrong_position_and_negative_only_witnesses_fail(self) -> None:
        person, age = Var("$person"), Var("$age")
        wrong_position = Rule(
            id="wrong_position",
            when=(
                PredAtom("Person:exists", [person]),
                PredAtom("person:age", [age, person]),
            ),
            ports={"person": person, "age": age},
        )
        with self.assertRaises(SemanticPortResolutionError) as wrong_ctx:
            resolve_rule_contract(
                wrong_position,
                _bindings(person, age),
                schema_index=_index(),
            )
        self.assertEqual(wrong_ctx.exception.code, "SEMANTIC_VAR_POSITION_MISMATCH")

        negative_person = Var("$negative_person")
        negative_only = Rule(
            id="negative_only",
            when=(NotAtom(AndExpr([PredAtom("Person:exists", [negative_person])])),),
            ports={"person": negative_person},
        )
        with self.assertRaises(SemanticPortResolutionError) as negative_ctx:
            resolve_rule_contract(
                negative_only,
                {"person": SemanticRulePort(negative_person, entity_identity("Person"))},
                schema_index=_index(),
            )
        self.assertEqual(negative_ctx.exception.code, "SEMANTIC_VAR_POSITION_MISMATCH")

    def test_entity_reference_fields_are_explicitly_unsupported(self) -> None:
        person, company = Var("$person"), Var("$company")
        rule = Rule(
            id="employment",
            when=(
                PredAtom("Person:exists", [person]),
                PredAtom("person:employer", [person, company]),
            ),
            ports={"person": person, "company": company},
        )
        with self.assertRaises(SemanticPortResolutionError) as ctx:
            resolve_rule_contract(
                rule,
                {
                    "person": SemanticRulePort(person, entity_identity("Person")),
                    "company": SemanticRulePort(
                        company,
                        field_endpoint("Person", "employer"),
                    ),
                },
                schema_index=_index(),
            )
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_ENTITY_REF_FIELD")

    def test_same_endpoint_does_not_merge_vars_or_change_the_rule(self) -> None:
        person1, person2 = Var("$person1"), Var("$person2")
        rule = Rule(
            id="two_people",
            when=(
                PredAtom("Person:exists", [person1]),
                PredAtom("Person:exists", [person2]),
                CmpAtom("ne", person1, person2),
            ),
            ports={"person1": person1, "person2": person2},
        )
        before_when, before_digest = rule.when, rule.content_digest
        contract = resolve_rule_contract(
            rule,
            {
                "person1": SemanticRulePort(person1, entity_identity("Person")),
                "person2": SemanticRulePort(person2, entity_identity("Person")),
            },
            schema_index=_index(),
        )

        self.assertIs(rule.when, before_when)
        self.assertEqual(rule.content_digest, before_digest)
        self.assertIs(contract.ports["person1"].var, person1)
        self.assertIs(contract.ports["person2"].var, person2)
        self.assertNotEqual(contract.ports["person1"].var, contract.ports["person2"].var)

    def test_one_var_cannot_claim_conflicting_endpoints(self) -> None:
        value = Var("$value")
        rule = Rule(
            id="ambiguous_value",
            when=(
                PredAtom("Person:exists", [value]),
                PredAtom("person:age", [value, value]),
            ),
            ports={"identity": value, "age": value},
        )
        with self.assertRaises(SemanticPortResolutionError) as ctx:
            resolve_rule_contract(
                rule,
                {
                    "identity": SemanticRulePort(value, entity_identity("Person")),
                    "age": SemanticRulePort(value, field_endpoint("Person", "age")),
                },
                schema_index=_index(),
            )
        self.assertEqual(ctx.exception.code, "VAR_ENDPOINT_CONFLICT")


class SemanticContractIdentityTests(unittest.TestCase):
    def test_digest_is_order_stable_and_whole_schema_conservative(self) -> None:
        rule, person, age = _person_age_rule()
        normal = _bindings(person, age)
        reversed_order = {"age": normal["age"], "person": normal["person"]}
        first = resolve_rule_contract(rule, normal, schema_index=_index())
        second = resolve_rule_contract(rule, reversed_order, schema_index=_index())
        extended = resolve_rule_contract(
            rule,
            normal,
            schema_index=_index(include_unrelated=True),
        )

        self.assertEqual(first.semantic_contract_digest, second.semantic_contract_digest)
        self.assertNotEqual(first.schema_digest, extended.schema_digest)
        self.assertNotEqual(first.semantic_contract_digest, extended.semantic_contract_digest)

    def test_endpoint_rebinding_changes_contract_digest(self) -> None:
        person, value = Var("$person"), Var("$value")
        rule = Rule(
            id="measure",
            when=(
                PredAtom("Person:exists", [person]),
                PredAtom("person:age", [person, value]),
                PredAtom("person:score", [person, value]),
            ),
            ports={"person": person, "value": value},
        )
        shared = {"person": SemanticRulePort(person, entity_identity("Person"))}
        age = resolve_rule_contract(
            rule,
            {**shared, "value": SemanticRulePort(value, field_endpoint("Person", "age"))},
            schema_index=_index(),
        )
        score = resolve_rule_contract(
            rule,
            {**shared, "value": SemanticRulePort(value, field_endpoint("Person", "score"))},
            schema_index=_index(),
        )
        self.assertNotEqual(age.semantic_contract_digest, score.semantic_contract_digest)

    def test_stale_guard_catches_rule_drift_and_adapts_invalid_ast(self) -> None:
        for replacement in (Var("$changed"), object()):
            rule, person, age = _person_age_rule()
            contract = resolve_rule_contract(
                rule,
                _bindings(person, age),
                schema_index=_index(),
            )
            rule.when[1].terms[1] = replacement  # type: ignore[list-item]
            with self.subTest(replacement=type(replacement).__name__):
                with self.assertRaises(SemanticPortResolutionError) as ctx:
                    assert_rule_contract_current(rule, contract)
                self.assertEqual(ctx.exception.code, "RULE_CONTRACT_STALE")

    def test_legacy_rule_digest_and_shape_remain_unchanged(self) -> None:
        user = Var("u")
        rule = Rule(
            id="r1",
            when=(PredAtom("User:exists", [user]),),
            ports={"user": user},
        )

        self.assertEqual(
            rule.content_digest,
            "64380f3ca84358344500e38a3391187f4d26a4a6257bccb12e53bfd5476fc78f",
        )
        self.assertFalse(hasattr(rule, "semantic_ports"))
        self.assertFalse(hasattr(rule, "semantic_contract"))


if __name__ == "__main__":
    unittest.main()
