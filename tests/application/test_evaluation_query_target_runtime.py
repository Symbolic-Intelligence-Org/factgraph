from __future__ import annotations

import unittest
from dataclasses import replace

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_targeted_evaluation_query,
    manage_rule_occurrence,
    resolve_evaluation_query_target,
)
from factgraph.application.evaluation_query_target_runtime import EvaluationQueryTargetError
from factgraph.application.protocol.evaluation_query import EvaluationQueryError
from factgraph.application.protocol import (
    EvaluationQueryBinding,
    EvaluationQuerySelection,
    Policy,
    PolicyOccurrence,
    SemanticPortAddress,
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _index():
    return build_schema_index(
        compile_schema_from_classes([Person], generated_at="2026-08-13T00:00:00Z")
    )


def _bundle(index=None):
    index = _index() if index is None else index
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
        schema_index=index,
    )


class EvaluationQueryTargetRuntimeTests(unittest.TestCase):
    def test_resolved_rule_lift_has_exact_target_topology_and_identity(self) -> None:
        target = resolve_evaluation_query_target(_bundle())

        self.assertEqual(target.compiled_policy.policy_id, "__factgraph_rule_lift__:person_age")
        self.assertEqual(target.compiled_policy.policy_version, "1")
        self.assertEqual(tuple(pin.occurrence_alias for pin in target.compiled_policy.rule_pins), ("target",))
        self.assertEqual(target.run_target.original_target_kind, "rule")
        self.assertEqual(target.run_target.normalization_kind, "rule_lift_v0")
        self.assertEqual(target.run_target.target_id, "person_age")
        self.assertEqual(target.run_target.rule_pins[0].rule_content_digest, _bundle().rule.content_digest)

    def test_direct_policy_preserves_identity_and_requires_exact_address_space(self) -> None:
        index, bundle = _index(), _bundle()
        space = SemanticAddressSpace((manage_rule_occurrence(bundle, "person"),))
        policy = Policy("people", PolicyOccurrence("person"), version="2")
        target = resolve_evaluation_query_target(policy, address_space=space)

        self.assertEqual(target.run_target.original_target_kind, "policy")
        self.assertEqual(target.run_target.normalization_kind, "policy_direct_v0")
        self.assertEqual(
            (target.run_target.target_id, target.run_target.target_version), ("people", "2")
        )
        with self.assertRaisesRegex(EvaluationQueryTargetError, "address_space"):
            resolve_evaluation_query_target(policy)
        with self.assertRaisesRegex(EvaluationQueryTargetError, "internal Rule-lift"):
            resolve_evaluation_query_target(
                Policy("__factgraph_rule_lift__:bad", PolicyOccurrence("person")),
                address_space=space,
            )
        self.assertEqual(index.schema_digest, target.run_target.schema_digest)

    def test_bare_rule_and_rule_address_space_are_rejected(self) -> None:
        bundle = _bundle()
        with self.assertRaisesRegex(EvaluationQueryTargetError, "bare Rules"):
            resolve_evaluation_query_target(bundle.rule)
        with self.assertRaisesRegex(EvaluationQueryTargetError, "internally"):
            resolve_evaluation_query_target(
                bundle,
                address_space=SemanticAddressSpace((manage_rule_occurrence(bundle, "other"),)),
            )

    def test_targeted_compiled_query_seals_underlying_query_and_target_identity(self) -> None:
        index, target = _index(), resolve_evaluation_query_target(_bundle())
        compiled = compile_targeted_evaluation_query(
            target,
            bindings=(),
            selections=(EvaluationQuerySelection("age", SemanticPortAddress("target", "age")),),
            schema_index=index,
        )
        self.assertTrue(compiled.wrapper_digest.startswith("sha256:"))
        with self.assertRaisesRegex(EvaluationQueryTargetError, "integrity seal"):
            replace(compiled, wrapper_digest="sha256:" + "0" * 64)
        direct = resolve_evaluation_query_target(
            Policy("__not_a_lift__", PolicyOccurrence("target")),
            address_space=target.address_space,
        )
        with self.assertRaisesRegex(EvaluationQueryTargetError, "does not match"):
            replace(compiled, target=direct)
        other_space = SemanticAddressSpace((manage_rule_occurrence(_bundle(index), "other"),))
        with self.assertRaisesRegex(EvaluationQueryTargetError, "address space"):
            replace(target, address_space=other_space)

    def test_compilation_remains_existing_direct_port_contract(self) -> None:
        index, target = _index(), resolve_evaluation_query_target(_bundle())
        compiled = compile_targeted_evaluation_query(
            target,
            bindings=(EvaluationQueryBinding(SemanticPortAddress("target", "age"), 22),),
            selections=(EvaluationQuerySelection("age", SemanticPortAddress("target", "age")),),
            schema_index=index,
        )
        self.assertEqual(compiled.compiled_query.bindings[0].normalized_value, 22)
        self.assertEqual(compiled.compiled_query.selections[0].address.port_name, "age")
        with self.assertRaisesRegex(EvaluationQueryError, "unknown semantic port") as ctx:
            compile_targeted_evaluation_query(
                target,
                bindings=(),
                selections=(EvaluationQuerySelection("age", SemanticPortAddress("target", "missing")),),
                schema_index=index,
            )
        self.assertEqual(ctx.exception.code, "UNRESOLVED_QUERY_ADDRESS")
