"""The compiled Policy seal keeps its ValueError runtime-type rejection.

``CompiledPolicyV0.__post_init__`` is the trust seal every downstream compiler
re-runs.  ``evaluation_query_target_runtime`` compiles Policies inside an
``except (SemanticPortResolutionError, ValueError)`` -- no ``TypeError`` -- and
maps the family onto ``QUERY_POLICY_TARGET_INVALID`` / ``QUERY_RULE_TARGET_STALE``.
The case below reaches the ``raise ValueError`` site with a wrong-type field
value and pins the exact message.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from factgraph.application.policy_runtime import CompiledPolicyV0
from tests._t3_error_contract_fixtures import build_fixture

_INDEX, _SPACE, _POLICY, _QUERY = build_fixture()

_MESSAGE = "compiled Policy structure has invalid runtime types"


@pytest.mark.parametrize(
    "field_name", ["policy_structure", "rule_expr", "lineage", "_body_plan"]
)
@pytest.mark.parametrize("value", ["structure", None, object()])
def test_compiled_policy_rejects_invalid_runtime_types_as_value_error(field_name, value):
    with pytest.raises(ValueError, match=re.escape(_MESSAGE)) as caught:
        dataclasses.replace(_POLICY, **{field_name: value})
    assert type(caught.value) is ValueError
    assert str(caught.value) == _MESSAGE


def test_compiled_policy_accepts_its_own_runtime_types():
    rebuilt = dataclasses.replace(_POLICY)
    assert isinstance(rebuilt, CompiledPolicyV0)
    assert rebuilt.policy_digest == _POLICY.policy_digest
