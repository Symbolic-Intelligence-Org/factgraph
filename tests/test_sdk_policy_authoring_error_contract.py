"""Characterize current ``PolicyDraft.all(...)`` input rejection.

The signature and Args accept owned nodes or constraints, not bare port/field
handles. Non-handles and foreign handles raise ``PolicyAuthoringError``. Owned
port/field handles pass the ownership check but are invalid children; they
currently reach ``AssertionError("unreachable")``. Recording that inherited
behavior does not endorse it as the correct public error contract or make
those inputs supported. Valid use composes a constraint before passing it to
``all``; changing the rejection behavior requires a separate decision.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application import build_resolved_rule, build_schema_index
from factgraph.application.protocol import SemanticRulePort, entity_identity
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, PolicyAuthoringError, SDKStore


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()


def _identity_bundle(graph: SDKStore):
    person = Var("$person")
    return build_resolved_rule(
        id="person_identity",
        version="1",
        when=(PredAtom("Person:exists", [person]),),
        ports={"person": SemanticRulePort(person, entity_identity("Person"))},
        schema_index=build_schema_index(graph.schema_ir),
    )


@pytest.mark.parametrize("item", [None, "people", 1, object(), ("people",), {"node": 1}])
def test_policy_all_rejects_non_handle_child_with_policy_authoring_error(item):
    graph = SDKStore([Person])
    draft = graph.policy("wrong-type-child", version="1")
    message = "Policy all must use values from this Policy draft"
    with pytest.raises(PolicyAuthoringError, match=re.escape(message)) as caught:
        draft.all(item)
    assert type(caught.value) is PolicyAuthoringError
    assert not isinstance(caught.value, (AssertionError, TypeError))
    assert caught.value.code == "POLICY_CROSS_DRAFT_HANDLE"
    assert str(caught.value) == message


def test_policy_all_rejects_handle_from_another_draft_with_policy_authoring_error():
    graph = SDKStore([Person])
    other = graph.policy("other-draft", version="1")
    foreign = other.use(_identity_bundle(graph), as_="people")
    draft = graph.policy("owning-draft", version="1")
    with pytest.raises(PolicyAuthoringError) as caught:
        draft.all(foreign)
    assert type(caught.value) is PolicyAuthoringError
    assert caught.value.code == "POLICY_CROSS_DRAFT_HANDLE"


def test_policy_all_accepts_owned_handle():
    graph = SDKStore([Person])
    draft = graph.policy("owned-handle", version="1")
    people = draft.use(_identity_bundle(graph), as_="people")
    node = draft.all(people)
    assert node is not None
    assert type(node).__name__ == "PolicyNodeHandle"


@pytest.mark.parametrize("kind", ["entity_port", "field"])
def test_policy_all_owned_non_node_input_retains_existing_assertion_error(kind):
    graph = SDKStore([Person])
    draft = graph.policy("owned-invalid-child", version="1")
    people = draft.use(_identity_bundle(graph), as_="people")
    port = people.port("person")
    child = port if kind == "entity_port" else port.field("age")

    with pytest.raises(AssertionError) as caught:
        draft.all(child)

    assert type(caught.value) is AssertionError
    assert str(caught.value) == "unreachable"
    assert caught.value.args == ("unreachable",)
    # Rejection does not prevent building the same draft with valid children.
    target = draft.build(draft.all(people, port.field("age") >= 18))
    assert target.policy.id == "owned-invalid-child"


@pytest.mark.parametrize("kind", ["entity_port", "field"])
def test_policy_all_foreign_non_node_input_is_rejected_by_ownership_first(kind):
    graph = SDKStore([Person])
    other = graph.policy("foreign-child", version="1")
    people = other.use(_identity_bundle(graph), as_="people")
    port = people.port("person")
    child = port if kind == "entity_port" else port.field("age")
    draft = graph.policy("owning-draft", version="1")

    with pytest.raises(PolicyAuthoringError) as caught:
        draft.all(child)

    assert type(caught.value) is PolicyAuthoringError
    assert caught.value.code == "POLICY_CROSS_DRAFT_HANDLE"
    assert str(caught.value) == "Policy all must use values from this Policy draft"
