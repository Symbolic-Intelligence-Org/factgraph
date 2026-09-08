"""EvaluationRun target/anchor argument rejections stay ValueError.

``build_evaluation_run_target_v0`` is exported in
``evaluation_run_runtime.__all__`` and rejects every malformed argument with
``ValueError``; ``evaluation_query_target_runtime`` compiles targets inside an
``except (SemanticPortResolutionError, ValueError)`` that maps the family onto
``QUERY_POLICY_TARGET_INVALID`` / ``QUERY_RULE_TARGET_STALE``.
``_assert_anchor_target_matches_query`` runs under
``store._build_evaluate_result``, whose handler re-wraps into ``SDKStoreError``.
Every case below reaches one ``raise ValueError`` site with a wrong-type input
and pins the exact message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application.evaluation_run_runtime import (
    _assert_anchor_target_matches_query,
    build_evaluation_run_target_v0,
)
from factgraph.application.protocol.evaluation_run import EvaluationRunTargetV0
from tests._t3_error_contract_fixtures import build_fixture

_INDEX, _SPACE, _POLICY, _QUERY = build_fixture()
_SCHEMA_DIGEST = _INDEX.schema_digest


def _build_target(compiled_policy):
    return build_evaluation_run_target_v0(
        compiled_policy=compiled_policy,
        schema_digest=_SCHEMA_DIGEST,
        original_target_kind="policy",
        target_id=_POLICY.policy_id,
        target_version=_POLICY.policy_version,
    )


# --- "compiled_policy must be trusted CompiledPolicyV0" ---


@pytest.mark.parametrize("compiled_policy", ["people", None, object(), _QUERY])
def test_build_run_target_rejects_untrusted_policy_as_value_error(compiled_policy):
    message = "compiled_policy must be trusted CompiledPolicyV0"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _build_target(compiled_policy)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_build_run_target_accepts_the_compiled_policy():
    target = _build_target(_POLICY)
    assert isinstance(target, EvaluationRunTargetV0)
    assert target.policy_digest == _POLICY.policy_digest


# --- "EvaluationRun source target is invalid" ---


@pytest.mark.parametrize("target", ["target", None, object(), _POLICY])
def test_anchor_target_guard_rejects_foreign_object_as_value_error(target):
    message = "EvaluationRun source target is invalid"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _assert_anchor_target_matches_query(target, _QUERY)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_anchor_target_guard_accepts_the_matching_target():
    assert _assert_anchor_target_matches_query(_build_target(_POLICY), _QUERY) is None
