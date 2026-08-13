"""Pure EvaluationQuery `contains_row` expectation compilation and matching."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .evaluation_query_runtime import (
    CompiledEvaluationQueryV0,
    ResolvedEvaluationQuerySelection,
    _canonical_value,
)
from .protocol.evaluation_expectation import (
    CompiledContainsRowExpectationV0,
    ContainsRowExpectationV0,
    ExpectationResultV0,
    ResolvedExpectationValueV0,
)
from .protocol.evaluate_result import EvaluateResult, EvaluateRow, _public_term_value
from .schema_runtime import (
    SchemaIndex,
    SchemaResolutionError,
    encode_entity_ref,
    field_predicate,
    materialize_identity,
)
from .semantic_address_runtime import SemanticAddressSpace
from .protocol.schema_runtime import EntityRef
from .protocol.semantic_port import EntityIdentityEndpoint, FieldEndpoint
from .value_validation import FieldValueValidationError, validate_field_value
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms


class EvaluationExpectationError(ValueError):
    """A Query expectation cannot be compiled or evaluated safely."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def compile_contains_row_expectations_v0(
    expectations: tuple[ContainsRowExpectationV0, ...],
    *,
    compiled_query: CompiledEvaluationQueryV0,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex,
) -> tuple[CompiledContainsRowExpectationV0, ...]:
    """Resolve selected aliases and values without changing the Query artifact."""

    if not isinstance(compiled_query, CompiledEvaluationQueryV0):
        raise EvaluationExpectationError("expectation requires CompiledEvaluationQueryV0", code="EXPECTATION_QUERY_REQUIRED")
    if not isinstance(address_space, SemanticAddressSpace) or not isinstance(schema_index, SchemaIndex):
        raise EvaluationExpectationError("expectation requires trusted address space and SchemaIndex", code="EXPECTATION_CONTEXT_REQUIRED")
    if not isinstance(expectations, tuple) or not all(isinstance(item, ContainsRowExpectationV0) for item in expectations):
        raise EvaluationExpectationError("expectations must be tuple[ContainsRowExpectationV0, ...]", code="EXPECTATION_PROTOCOL_SHAPE")
    ids = tuple(item.expectation_id for item in expectations)
    if len(set(ids)) != len(ids):
        raise EvaluationExpectationError("expectation ids must be unique", code="DUPLICATE_EXPECTATION_ID")
    selection_by_alias = {item.alias: item for item in compiled_query.selections}
    compiled: list[CompiledContainsRowExpectationV0] = []
    for expectation in expectations:
        values: list[ResolvedExpectationValueV0] = []
        for alias, raw_value in expectation.selected_values:
            selection = selection_by_alias.get(alias)
            if selection is None:
                raise EvaluationExpectationError(
                    f"expectation alias {alias!r} is not selected by this Query",
                    code="EXPECTATION_ALIAS_NOT_SELECTED",
                )
            value_type, normalized, value_digest = _normalize_expected_value(
                selection,
                raw_value,
                address_space=address_space,
                schema_index=schema_index,
            )
            values.append(
                ResolvedExpectationValueV0(alias, value_type, normalized, value_digest)
            )
        compiled.append(
            CompiledContainsRowExpectationV0(
                expectation.expectation_id,
                compiled_query.query_digest,
                tuple(sorted(values, key=lambda item: item.alias)),
            )
        )
    return tuple(compiled)


def evaluate_contains_row_expectations_v0(
    expectations: tuple[CompiledContainsRowExpectationV0, ...],
    *,
    result: EvaluateResult,
    targeted_query_wrapper_digest: str,
    completeness_basis: str,
) -> tuple[ExpectationResultV0, ...]:
    """Evaluate compiled observations over one already-completed result."""

    if not isinstance(result, EvaluateResult):
        raise EvaluationExpectationError("expectation result requires EvaluateResult", code="EXPECTATION_RESULT_REQUIRED")
    if not isinstance(targeted_query_wrapper_digest, str) or not targeted_query_wrapper_digest.startswith("sha256:"):
        raise EvaluationExpectationError("expectation requires targeted Query wrapper digest", code="EXPECTATION_WRAPPER_REQUIRED")
    if completeness_basis not in {"complete_native_enumeration_v0", "unknown", "unsupported"}:
        raise EvaluationExpectationError("expectation completeness basis is unsupported", code="EXPECTATION_COMPLETENESS_INVALID")
    query_digest = _query_digest_for_result(result)
    outcomes: list[ExpectationResultV0] = []
    for expectation in expectations:
        if expectation.query_digest != query_digest:
            raise EvaluationExpectationError("compiled expectation does not match result Query", code="EXPECTATION_QUERY_MISMATCH")
        matching = tuple(
            sorted(
                row.row_id
                for row in result.rows
                if _row_matches(row, expectation.values)
            )
        )
        if matching:
            status, diagnostic = "satisfied", "EXPECTATION_CONTAINS_ROW_SATISFIED"
        elif completeness_basis == "complete_native_enumeration_v0":
            status, diagnostic = "not_satisfied", "EXPECTATION_CONTAINS_ROW_NOT_SATISFIED"
        elif completeness_basis == "unknown":
            status, diagnostic = "underdetermined", "EXPECTATION_COMPLETENESS_UNKNOWN"
        else:
            status, diagnostic = "unsupported", "EXPECTATION_UNSUPPORTED"
        outcomes.append(
            ExpectationResultV0(
                expectation_id=expectation.expectation_id,
                kind="contains_row",
                expectation_digest=expectation.expectation_digest,
                query_digest=query_digest,
                targeted_query_wrapper_digest=targeted_query_wrapper_digest,
                result_id=result.result_id,
                result_digest=result.fingerprint.result_digest,
                run_anchor_digest=(None if result.run_anchor is None else result.run_anchor.anchor_digest),
                status=status,
                completeness_basis=completeness_basis,
                matched_row_ids=matching,
                diagnostic_code=diagnostic,
            )
        )
    return tuple(outcomes)


def assert_compiled_contains_row_expectation_current(
    value: CompiledContainsRowExpectationV0,
) -> None:
    """Recheck a compiled expectation before it crosses the execution seam."""

    if not isinstance(value, CompiledContainsRowExpectationV0):
        raise EvaluationExpectationError(
            "compiled expectation has invalid runtime type",
            code="EXPECTATION_PROTOCOL_SHAPE",
        )
    try:
        CompiledContainsRowExpectationV0.__post_init__(value)
        for item in value.values:
            canonical, digest = _canonical_value(item.value_type, item.normalized_value)
            if canonical != item.normalized_value or digest != item.value_digest:
                raise ValueError("canonical value or digest mismatch")
    except (TypeError, ValueError) as exc:
        raise EvaluationExpectationError(
            "compiled expectation failed its integrity check",
            code="EXPECTATION_INTEGRITY_MISMATCH",
        ) from exc


def _normalize_expected_value(
    selection: ResolvedEvaluationQuerySelection,
    raw_value: object,
    *,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex,
) -> tuple[str, object, str]:
    """Reuse F3's endpoint-aware normalization rather than compare Python reprs."""

    try:
        endpoint = address_space.resolve(selection.address).endpoint
        if isinstance(endpoint, EntityIdentityEndpoint):
            if not isinstance(raw_value, EntityRef) or raw_value.entity_type != endpoint.entity_type:
                raise ValueError(f"expected EntityRef[{endpoint.entity_type}]")
            identity = materialize_identity(endpoint.entity_type, raw_value.identity, index=schema_index)
            value_type = "entity_ref"
            normalized = encode_entity_ref(EntityRef(endpoint.entity_type, identity), index=schema_index)
        elif isinstance(endpoint, FieldEndpoint):
            if isinstance(raw_value, EntityRef):
                raise ValueError("field endpoint expects scalar value")
            pred = field_predicate(schema_index, endpoint.entity_type, endpoint.field_name)
            value_type = str(pred.value_type_domain)
            value = raw_value.lower() if value_type == "uuid" and isinstance(raw_value, str) else raw_value
            normalized = claim_args_from_rest_terms([(value_type, value)])[0][1]
            if isinstance(normalized, str) and normalized.startswith("$"):
                raise ValueError("native lowering cannot preserve a '$'-prefixed string constant")
            validate_field_value(normalized, pred_info=pred)
        else:
            raise ValueError("unsupported semantic endpoint")
        canonical, digest = _canonical_value(value_type, normalized)
        return value_type, canonical, digest
    except (
        FieldValueValidationError,
        SchemaResolutionError,
        TypeError,
        ValueError,
    ) as exc:
        raise EvaluationExpectationError(
            f"expectation value is incompatible with selected alias {selection.alias!r}: {exc}",
            code="EXPECTATION_VALUE_TYPE_MISMATCH",
        ) from exc


def _row_matches(row: EvaluateRow, values: Sequence[ResolvedExpectationValueV0]) -> bool:
    if not isinstance(row, EvaluateRow):
        raise EvaluationExpectationError("expectation result row is malformed", code="EXPECTATION_ROW_MALFORMED")
    for expected in values:
        term = row.bindings.get(expected.alias)
        if not isinstance(term, Mapping):
            raise EvaluationExpectationError("result row lacks selected expectation alias", code="EXPECTATION_RESULT_SHAPE")
        try:
            actual, digest = _canonical_value(expected.value_type, _public_term_value(term))
        except (TypeError, ValueError) as exc:
            raise EvaluationExpectationError("result row value contradicts selected domain", code="EXPECTATION_RESULT_SHAPE") from exc
        if actual != expected.normalized_value or digest != expected.value_digest:
            return False
    return True


def _query_digest_for_result(result: EvaluateResult) -> str:
    prefix = "sha256:"
    value = result.fingerprint.expr_digest
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) != len(prefix) + 64:
        raise EvaluationExpectationError("result does not carry an EvaluationQuery digest", code="EXPECTATION_RESULT_QUERY_REQUIRED")
    return value[len(prefix):]


__all__ = [
    "EvaluationExpectationError",
    "assert_compiled_contains_row_expectation_current",
    "compile_contains_row_expectations_v0",
    "evaluate_contains_row_expectations_v0",
]
