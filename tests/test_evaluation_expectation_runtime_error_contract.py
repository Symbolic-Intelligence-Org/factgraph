"""Expectation-value normalization keeps its ValueError-to-code contract.

``_normalize_expected_value`` is wrapped by an enclosing
``except (FieldValueValidationError, SchemaResolutionError, TypeError, ValueError)``
that re-raises ``EvaluationExpectationError(code="EXPECTATION_VALUE_TYPE_MISMATCH")``.
Every case below reaches one ``raise ValueError`` site with a wrong-type input
(the input a ``TypeError`` rewrite would re-classify) and pins the exact
message on ``__cause__``, so the exception class stays part of the tested
contract rather than a lint accident.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from factgraph.application.evaluation_expectation_runtime import (
    EvaluationExpectationError,
    _normalize_expected_value,
)
from factgraph.application.evaluation_query_runtime import (
    ResolvedEvaluationQueryNavigationSelectionV0,
)
from factgraph.application.protocol.schema_runtime import EntityRef
from tests._t3_error_contract_fixtures import build_fixture

_INDEX, _SPACE, _POLICY, _QUERY = build_fixture()
_FIELD_SELECTION = _QUERY.selections[0]
_NAV_SELECTION = ResolvedEvaluationQueryNavigationSelectionV0(
    alias="age",
    navigation=SimpleNamespace(),
    value_type="int",
    field_predicate_id="person:age",
    sources=(),
)


def _normalize(selection, raw_value, *, address_space=_SPACE):
    return _normalize_expected_value(
        selection,
        raw_value,
        address_space=address_space,
        schema_index=_INDEX,
    )


def _assert_value_error_cause(caught, message: str) -> None:
    assert caught.value.code == "EXPECTATION_VALUE_TYPE_MISMATCH"
    assert type(caught.value.__cause__) is ValueError
    assert str(caught.value.__cause__) == message


# --- "field navigation expects scalar value" ---


def test_navigation_selection_rejects_entity_ref_as_value_error():
    with pytest.raises(EvaluationExpectationError) as caught:
        _normalize(_NAV_SELECTION, EntityRef("Person", {"employee_id": "e-1"}))
    _assert_value_error_cause(caught, "field navigation expects scalar value")


# --- "field endpoint expects scalar value" ---


def test_field_endpoint_rejects_entity_ref_as_value_error():
    with pytest.raises(EvaluationExpectationError) as caught:
        _normalize(_FIELD_SELECTION, EntityRef("Person", {"employee_id": "e-1"}))
    _assert_value_error_cause(caught, "field endpoint expects scalar value")


# --- "unsupported semantic endpoint" ---


def test_unsupported_endpoint_rejects_value_as_value_error():
    space = SimpleNamespace(resolve=lambda address: SimpleNamespace(endpoint=object()))
    with pytest.raises(EvaluationExpectationError) as caught:
        _normalize(_FIELD_SELECTION, 41, address_space=space)
    _assert_value_error_cause(caught, "unsupported semantic endpoint")


# --- valid-type positive control ---


def test_field_endpoint_accepts_scalar_value():
    value_type, canonical, digest = _normalize(_FIELD_SELECTION, 41)
    assert value_type == "int"
    assert canonical == 41
    assert isinstance(digest, str) and digest
