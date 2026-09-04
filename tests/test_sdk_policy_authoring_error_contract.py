"""``PolicyDraft.all(...)`` rejects wrong-typed children as ``PolicyAuthoringError``.

``PolicyDraft.all`` documents ``Raises: PolicyAuthoringError: If the group is
empty or crosses drafts``.  ``_owned_nodes`` calls ``_require_owned`` first, so
any non-handle argument leaves through that typed SDK rejection; the trailing
``raise AssertionError("unreachable")`` is a defensive invariant marker for a
branch ``_require_owned`` already forecloses (it is marked ``# pragma: no
cover``).  Turning it into ``TypeError`` would advertise a public exception
class the façade never raises.  These tests pin the reachable contract.
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
