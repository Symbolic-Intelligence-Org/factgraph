"""Shared compiled Policy/Query fixtures for the T3 ValueError contract tests.

This module is imported by the ``tests/test_*_error_contract.py`` modules that
pin the exact exception class of the application-runtime wrong-type rejections.
It is intentionally not a ``test_`` module: it only builds inputs.
"""

from __future__ import annotations

from factgraph.application import (
    SemanticAddressSpace,
    build_resolved_rule,
    build_schema_index,
    compile_evaluation_query,
    compile_policy,
    manage_rule_occurrence,
)
from factgraph.application.protocol import (
    EvaluationQuery,
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


def address(port: str) -> SemanticPortAddress:
    return SemanticPortAddress("person", port)


def build_fixture():
    """Return ``(schema_index, address_space, compiled_policy, compiled_query)``."""

    index = build_schema_index(
        compile_schema_from_classes([Person], generated_at="2026-08-13T00:00:00Z")
    )
    person, age = Var("$person"), Var("$age")
    bundle = build_resolved_rule(
        id="person_age",
        version="1",
        when=(PredAtom("Person:exists", [person]), PredAtom("person:age", [person, age])),
        ports={
            "person": SemanticRulePort(person, entity_identity("Person")),
            "age": SemanticRulePort(age, field_endpoint("Person", "age")),
        },
        schema_index=index,
    )
    space = SemanticAddressSpace((manage_rule_occurrence(bundle, "person"),))
    policy = compile_policy(Policy("people", PolicyOccurrence("person")), address_space=space)
    query = compile_evaluation_query(
        EvaluationQuery(policy.policy_digest, (EvaluationQuerySelection("age", address("age")),)),
        compiled_policy=policy,
        address_space=space,
        schema_index=index,
    )
    return index, space, policy, query
