"""Compiled EvaluationQuery seals and binding normalization stay ValueError.

Two contracts are pinned here:

* ``CompiledEvaluationQueryV0.__post_init__`` / ``_assert_compiled_evaluation_query_current``
  raise ``ValueError``, and ``factgraph.sdk.store`` catches exactly ``ValueError``
  around them (``SDKStoreError`` at the artifact seam, a re-raised ``ValueError``
  at the live-integrity seam).  A ``TypeError`` rewrite would escape both.
* ``_normalize_binding`` is wrapped by ``except (ValueError, SchemaResolutionError,
  FieldValueValidationError)`` -- again no ``TypeError`` -- which produces the
  ``QUERY_BINDING_TYPE_MISMATCH`` admission error.

Every case reaches one ``raise ValueError`` site with a wrong-type input and
pins the exact message.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from factgraph.application.evaluation_query_runtime import (
    _assert_compiled_evaluation_query_current,
    _normalize_binding,
)
from factgraph.application.protocol import (
    EvaluationQueryBinding,
    EvaluationQueryError,
    FunctionValueEndpointV1,
    field_endpoint,
)
from factgraph.application.protocol.schema_runtime import EntityRef
from tests._t3_error_contract_fixtures import address, build_fixture

_INDEX, _SPACE, _POLICY, _QUERY = build_fixture()
_ENTITY_REF = EntityRef("Person", {"employee_id": "e-1"})
_FIELD_ENDPOINT = field_endpoint("Person", "age")
_FUNCTION_ENDPOINT = FunctionValueEndpointV1(
    function_digest="sha256:" + "a" * 64,
    relation_predicate_id="fn:demo",
    port_name="amount",
    mode="input",
    scalar_domain="int",
    position=1,
)


def _binding(value):
    return EvaluationQueryBinding(address("age"), value)


def _assert_value_error_cause(caught, message: str) -> None:
    assert caught.value.code == "QUERY_BINDING_TYPE_MISMATCH"
    assert type(caught.value.__cause__) is ValueError
    assert str(caught.value.__cause__) == message


# --- CompiledEvaluationQueryV0.__post_init__ seal ---


@pytest.mark.parametrize("field_name", ["compiled_policy", "_lowering_plan"])
@pytest.mark.parametrize("value", ["not-a-policy", None, object()])
def test_compiled_query_rejects_untrusted_runtime_types_as_value_error(field_name, value):
    message = "compiled EvaluationQuery requires trusted Policy and lowering plan"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        dataclasses.replace(_QUERY, **{field_name: value})
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


@pytest.mark.parametrize("compiled_query", ["not-a-query", None, object(), _POLICY])
def test_assert_compiled_query_current_rejects_foreign_object_as_value_error(compiled_query):
    message = "compiled_query must be CompiledEvaluationQueryV0"
    with pytest.raises(ValueError, match=re.escape(message)) as caught:
        _assert_compiled_evaluation_query_current(compiled_query)
    assert type(caught.value) is ValueError
    assert str(caught.value) == message


def test_assert_compiled_query_current_accepts_the_compiled_query():
    assert _assert_compiled_evaluation_query_current(_QUERY) is None


# --- _normalize_binding endpoint rejections ---


def test_field_endpoint_binding_rejects_entity_ref_as_value_error():
    with pytest.raises(EvaluationQueryError) as caught:
        _normalize_binding(_binding(_ENTITY_REF), _FIELD_ENDPOINT, _INDEX)
    _assert_value_error_cause(caught, "field endpoint expects scalar value")


def test_function_scalar_endpoint_binding_rejects_entity_ref_as_value_error():
    with pytest.raises(EvaluationQueryError) as caught:
        _normalize_binding(_binding(_ENTITY_REF), _FUNCTION_ENDPOINT, _INDEX)
    _assert_value_error_cause(caught, "function scalar endpoint expects scalar value")


@pytest.mark.parametrize("endpoint", [None, "field", object()])
def test_unsupported_endpoint_binding_rejects_value_as_value_error(endpoint):
    with pytest.raises(EvaluationQueryError) as caught:
        _normalize_binding(_binding(41), endpoint, _INDEX)
    _assert_value_error_cause(caught, "unsupported semantic endpoint")


# --- valid-type positive controls ---


def test_field_endpoint_binding_accepts_scalar_value():
    value_type, normalized, digest = _normalize_binding(_binding(41), _FIELD_ENDPOINT, _INDEX)
    assert (value_type, normalized) == ("int", 41)
    assert isinstance(digest, str) and digest


def test_function_scalar_endpoint_binding_accepts_scalar_value():
    value_type, normalized, digest = _normalize_binding(_binding(41), _FUNCTION_ENDPOINT, _INDEX)
    assert (value_type, normalized) == ("int", 41)
    assert isinstance(digest, str) and digest
