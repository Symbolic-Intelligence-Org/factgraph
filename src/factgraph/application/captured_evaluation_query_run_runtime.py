"""Runtime and strict codec for detached captured targeted-Query observations."""

from __future__ import annotations

import base64
import json

from factgraph.application.evaluation_expectation_runtime import (
    EvaluationExpectationError,
    assert_compiled_contains_row_expectation_current,
    evaluate_captured_contains_row_expectations_v0,
)
from factgraph.application.evaluation_query_target_runtime import (
    targeted_evaluation_query_wrapper_digest_v0,
)
from factgraph.application.evaluation_run_bundle_runtime import (
    MAX_EVALUATION_RUN_BUNDLE_BYTES,
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
)
from factgraph.application.evaluation_run_evidence_runtime import (
    evaluation_run_bundle_evidence,
)
from factgraph.application.evaluation_run_verification_runtime import (
    verify_evaluation_run_bundle,
)
from factgraph.application.policy_explanation_runtime import (
    project_policy_explanation_v0,
)
from factgraph.application.protocol.captured_evaluation_query_run import (
    CapturedEvaluationQueryRunExplanationV0,
    CapturedEvaluationQueryRunV0,
    CapturedEvaluationQueryRunVerificationV0,
    MAX_CAPTURED_EVALUATION_QUERY_EXPECTATIONS_V0,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_expectation import (
    CompiledContainsRowExpectationV0,
    ExpectationResultV0,
    ResolvedExpectationValueV0,
)
from factgraph.application.protocol.evaluation_run_bundle import EvaluationRunBundleV0


MAX_CAPTURED_EVALUATION_QUERY_RUN_BYTES = (
    4 * ((MAX_EVALUATION_RUN_BUNDLE_BYTES + 2) // 3) + 128 * 1024
)
_WIRE_TYPE = "captured_evaluation_query_run_v0"
_MAX_DEPTH = 64


def build_captured_evaluation_query_run_v0(
    *,
    bundle: EvaluationRunBundleV0,
    targeted_query_wrapper_digest: str,
    expectations: tuple[CompiledContainsRowExpectationV0, ...],
) -> CapturedEvaluationQueryRunV0:
    """Seal one exact F4 capture and its precompiled Query observations."""

    _assert_bundle_current(bundle)
    _assert_expectation_inventory(expectations, bundle=bundle)
    expected_wrapper = targeted_evaluation_query_wrapper_digest_v0(
        bundle.query_digest,
        bundle.run_anchor.target.target_digest,
        expectations,
    )
    if targeted_query_wrapper_digest != expected_wrapper:
        raise ProtocolShapeError("Captured Query run wrapper seal does not match bundle and inventory")
    try:
        outcomes = evaluate_captured_contains_row_expectations_v0(
            expectations,
            bundle=bundle,
            targeted_query_wrapper_digest=targeted_query_wrapper_digest,
        )
    except EvaluationExpectationError as exc:
        raise ProtocolShapeError(f"Captured Query run expectation evaluation failed: {exc.code}") from exc
    run = CapturedEvaluationQueryRunV0(
        bundle=bundle,
        targeted_query_wrapper_digest=targeted_query_wrapper_digest,
        expectations=expectations,
        expectation_results=outcomes,
    )
    _assert_captured_evaluation_query_run_current(run)
    # Match F4's capture contract: an accepted in-memory artifact must already
    # fit its own strict durable codec rather than fail only when a caller later
    # tries to persist or hand it off.
    captured_evaluation_query_run_bytes(run)
    return run


def captured_evaluation_query_run_bytes(run: CapturedEvaluationQueryRunV0) -> bytes:
    """Encode a canonical strict outer envelope around one F4 bundle."""

    _assert_captured_evaluation_query_run_current(run)
    payload = {
        "$type": _WIRE_TYPE,
        "fields": {
            "bundle": _b64(evaluation_run_bundle_bytes(run.bundle)),
            "targeted_query_wrapper_digest": run.targeted_query_wrapper_digest,
            "expectations": [_expectation_to_wire(item) for item in run.expectations],
            "expectation_results": [_outcome_to_wire(item) for item in run.expectation_results],
            "integrity": run.integrity,
            "authenticity": run.authenticity,
            "privacy": run.privacy,
            "custody": run.custody,
            "explain_availability": run.explain_availability,
            "verification_availability": run.verification_availability,
            "captured_query_run_digest": run.captured_query_run_digest,
        },
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > MAX_CAPTURED_EVALUATION_QUERY_RUN_BYTES:
        raise ProtocolShapeError("Captured Query run exceeds maximum encoded size")
    return raw


def captured_evaluation_query_run_from_bytes(raw: bytes) -> CapturedEvaluationQueryRunV0:
    """Decode one canonical captured Query observation without a live Store."""

    if (
        not isinstance(raw, bytes)
        or not raw
        or len(raw) > MAX_CAPTURED_EVALUATION_QUERY_RUN_BYTES
    ):
        raise ProtocolShapeError("Captured Query run bytes are empty or exceed maximum size")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("Captured Query run bytes are not valid UTF-8 JSON") from exc
    if _json_depth(payload) > _MAX_DEPTH or _canonical_json_bytes(payload) != raw:
        raise ProtocolShapeError("Captured Query run JSON is non-canonical or too deep")
    if not isinstance(payload, dict) or set(payload) != {"$type", "fields"}:
        raise ProtocolShapeError("Captured Query run root shape is invalid")
    if payload["$type"] != _WIRE_TYPE or not isinstance(payload["fields"], dict):
        raise ProtocolShapeError("Captured Query run root type is invalid")
    fields = payload["fields"]
    required = {
        "bundle",
        "targeted_query_wrapper_digest",
        "expectations",
        "expectation_results",
        "integrity",
        "authenticity",
        "privacy",
        "custody",
        "explain_availability",
        "verification_availability",
        "captured_query_run_digest",
    }
    if (
        set(fields) != required
        or not isinstance(fields["expectations"], list)
        or not isinstance(fields["expectation_results"], list)
    ):
        raise ProtocolShapeError("Captured Query run fields are not exact")
    run = CapturedEvaluationQueryRunV0(
        bundle=evaluation_run_bundle_from_bytes(_unb64(fields["bundle"])),
        targeted_query_wrapper_digest=fields["targeted_query_wrapper_digest"],
        expectations=tuple(_expectation_from_wire(item) for item in fields["expectations"]),
        expectation_results=tuple(_outcome_from_wire(item) for item in fields["expectation_results"]),
        integrity=fields["integrity"],
        authenticity=fields["authenticity"],
        privacy=fields["privacy"],
        custody=fields["custody"],
        explain_availability=fields["explain_availability"],
        verification_availability=fields["verification_availability"],
    )
    if fields["captured_query_run_digest"] != run.captured_query_run_digest:
        raise ProtocolShapeError("Captured Query run digest does not match content")
    _assert_captured_evaluation_query_run_current(run)
    return run


def explain_captured_evaluation_query_run_v0(
    run: CapturedEvaluationQueryRunV0,
    *,
    row_capture_digest: str,
) -> CapturedEvaluationQueryRunExplanationV0:
    """Play back one positive captured row and project it to the Policy tree."""

    bundle = _assert_captured_evaluation_query_run_current(run)
    if not isinstance(row_capture_digest, str) or not row_capture_digest:
        raise ProtocolShapeError("Captured Query explain requires non-empty row_capture_digest")
    matching = tuple(row for row in bundle.rows if row.row_capture_digest == row_capture_digest)
    if len(matching) != 1:
        raise ProtocolShapeError("Captured Query row_capture_digest is absent or ambiguous")
    row = matching[0]
    evidence = evaluation_run_bundle_evidence(bundle, row_capture_digest=row_capture_digest)
    anchor = bundle.run_anchor.row_anchors[row.ordinal]
    projection = project_policy_explanation_v0(
        bundle.run_anchor,
        evidence,
        semantic_row_anchor_digest=anchor.semantic_anchor_digest,
    )
    return CapturedEvaluationQueryRunExplanationV0(
        captured_query_run_digest=run.captured_query_run_digest,
        row_capture_digest=row_capture_digest,
        evidence=evidence,
        policy_projection=projection,
    )


def verify_captured_evaluation_query_run_v0(
    run: CapturedEvaluationQueryRunV0,
) -> CapturedEvaluationQueryRunVerificationV0:
    """Verify only the captured native bundle; observations stay observations."""

    bundle = _assert_captured_evaluation_query_run_current(run)
    return CapturedEvaluationQueryRunVerificationV0(
        captured_query_run_digest=run.captured_query_run_digest,
        bundle_verification=verify_evaluation_run_bundle(bundle),
    )


def _assert_captured_evaluation_query_run_current(
    run: CapturedEvaluationQueryRunV0,
) -> EvaluationRunBundleV0:
    if not isinstance(run, CapturedEvaluationQueryRunV0):
        raise ProtocolShapeError("Captured Query run must be CapturedEvaluationQueryRunV0")
    CapturedEvaluationQueryRunV0.__post_init__(run)
    bundle = _assert_bundle_current(run.bundle)
    _assert_expectation_inventory(run.expectations, bundle=bundle)
    expected_wrapper = targeted_evaluation_query_wrapper_digest_v0(
        bundle.query_digest,
        bundle.run_anchor.target.target_digest,
        run.expectations,
    )
    if run.targeted_query_wrapper_digest != expected_wrapper:
        raise ProtocolShapeError("Captured Query run wrapper seal does not match contents")
    try:
        expected_outcomes = evaluate_captured_contains_row_expectations_v0(
            run.expectations,
            bundle=bundle,
            targeted_query_wrapper_digest=run.targeted_query_wrapper_digest,
        )
    except EvaluationExpectationError as exc:
        raise ProtocolShapeError(f"Captured Query run outcome recomputation failed: {exc.code}") from exc
    if run.expectation_results != expected_outcomes:
        raise ProtocolShapeError("Captured Query run outcomes do not match captured rows")
    return bundle


def _assert_bundle_current(bundle: EvaluationRunBundleV0) -> EvaluationRunBundleV0:
    if not isinstance(bundle, EvaluationRunBundleV0):
        raise ProtocolShapeError("Captured Query run bundle is invalid")
    # F4's canonical encode/decode is the authoritative structural validator;
    # use the decoded object so every detached call has no incidental Store read.
    decoded = evaluation_run_bundle_from_bytes(evaluation_run_bundle_bytes(bundle))
    if decoded != bundle:
        raise ProtocolShapeError("Captured Query run bundle changed during canonical validation")
    return decoded


def _assert_expectation_inventory(
    expectations: tuple[CompiledContainsRowExpectationV0, ...],
    *,
    bundle: EvaluationRunBundleV0,
) -> None:
    if not isinstance(expectations, tuple):
        raise ProtocolShapeError("Captured Query run expectations must be a tuple")
    if len(expectations) > MAX_CAPTURED_EVALUATION_QUERY_EXPECTATIONS_V0:
        raise ProtocolShapeError("Captured Query run expectation inventory exceeds the v0 limit")
    selection_types = {
        item.alias: item.value_type
        for item in bundle.run_anchor.selections
    }
    ids: list[str] = []
    for item in expectations:
        try:
            assert_compiled_contains_row_expectation_current(item)
        except EvaluationExpectationError as exc:
            raise ProtocolShapeError(f"Captured Query expectation is stale: {exc.code}") from exc
        if item.query_digest != bundle.query_digest:
            raise ProtocolShapeError("Captured Query expectation does not match bundle Query")
        for value in item.values:
            selected_type = selection_types.get(value.alias)
            if selected_type is None:
                raise ProtocolShapeError(
                    "Captured Query expectation aliases must be present in bundle selections"
                )
            if selected_type != value.value_type:
                raise ProtocolShapeError(
                    "Captured Query expectation value type does not match bundle selection"
                )
        ids.append(item.expectation_id)
    if len(ids) != len(set(ids)):
        raise ProtocolShapeError("Captured Query expectation ids are duplicated")


def _expectation_to_wire(value: CompiledContainsRowExpectationV0) -> dict[str, object]:
    return {
        "expectation_id": value.expectation_id,
        "query_digest": value.query_digest,
        "values": [
            [item.alias, item.value_type, item.normalized_value, item.value_digest]
            for item in value.values
        ],
        "kind": value.kind,
        "expectation_digest": value.expectation_digest,
    }


def _expectation_from_wire(value: object) -> CompiledContainsRowExpectationV0:
    if not isinstance(value, dict):
        raise ProtocolShapeError("Captured Query expectation wire shape is invalid")
    required = {"expectation_id", "query_digest", "values", "kind", "expectation_digest"}
    if (
        set(value) != required
        or not isinstance(value["values"], list)
        or not all(isinstance(item, list) and len(item) == 4 for item in value["values"])
    ):
        raise ProtocolShapeError("Captured Query expectation wire fields are invalid")
    if value["kind"] != "contains_row":
        raise ProtocolShapeError("Captured Query expectation kind is invalid")
    expectation = CompiledContainsRowExpectationV0(
        expectation_id=value["expectation_id"],
        query_digest=value["query_digest"],
        values=tuple(
            ResolvedExpectationValueV0(
                alias=item[0],
                value_type=item[1],
                normalized_value=item[2],
                value_digest=item[3],
            )
            for item in value["values"]
        ),
    )
    if expectation.expectation_digest != value["expectation_digest"]:
        raise ProtocolShapeError("Captured Query expectation digest does not match content")
    return expectation


def _outcome_to_wire(value: ExpectationResultV0) -> dict[str, object]:
    return {
        "expectation_id": value.expectation_id,
        "kind": value.kind,
        "expectation_digest": value.expectation_digest,
        "query_digest": value.query_digest,
        "targeted_query_wrapper_digest": value.targeted_query_wrapper_digest,
        "result_id": value.result_id,
        "result_digest": value.result_digest,
        "run_anchor_digest": value.run_anchor_digest,
        "status": value.status,
        "completeness_basis": value.completeness_basis,
        "matched_row_ids": list(value.matched_row_ids),
        "diagnostic_code": value.diagnostic_code,
        "outcome_digest": value.outcome_digest,
    }


def _outcome_from_wire(value: object) -> ExpectationResultV0:
    if not isinstance(value, dict):
        raise ProtocolShapeError("Captured Query outcome wire shape is invalid")
    required = {
        "expectation_id", "kind", "expectation_digest", "query_digest",
        "targeted_query_wrapper_digest", "result_id", "result_digest", "run_anchor_digest",
        "status", "completeness_basis", "matched_row_ids", "diagnostic_code", "outcome_digest",
    }
    if set(value) != required or not isinstance(value["matched_row_ids"], list):
        raise ProtocolShapeError("Captured Query outcome wire fields are invalid")
    outcome = ExpectationResultV0(
        expectation_id=value["expectation_id"],
        kind=value["kind"],
        expectation_digest=value["expectation_digest"],
        query_digest=value["query_digest"],
        targeted_query_wrapper_digest=value["targeted_query_wrapper_digest"],
        result_id=value["result_id"],
        result_digest=value["result_digest"],
        run_anchor_digest=value["run_anchor_digest"],
        status=value["status"],
        completeness_basis=value["completeness_basis"],
        matched_row_ids=tuple(value["matched_row_ids"]),
        diagnostic_code=value["diagnostic_code"],
    )
    if outcome.outcome_digest != value["outcome_digest"]:
        raise ProtocolShapeError("Captured Query outcome digest does not match content")
    return outcome


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError("Captured Query binary field is invalid")
    try:
        raw = base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ProtocolShapeError("Captured Query binary field is malformed") from exc
    if _b64(raw) != value:
        raise ProtocolShapeError("Captured Query binary field is non-canonical")
    return raw


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError, RecursionError) as exc:
        raise ProtocolShapeError("Captured Query run payload cannot be canonical JSON") from exc


def _unique_json_object(items: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in items:
        if key in output:
            raise ProtocolShapeError(f"Captured Query run JSON has duplicate key {key!r}")
        output[key] = value
    return output


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(f"Captured Query run JSON contains non-standard constant {value!r}")


def _json_depth(value: object, depth: int = 0) -> int:
    if isinstance(value, dict):
        return max([depth, *(_json_depth(item, depth + 1) for item in value.values())])
    if isinstance(value, list):
        return max([depth, *(_json_depth(item, depth + 1) for item in value)])
    return depth


__all__ = [
    "MAX_CAPTURED_EVALUATION_QUERY_RUN_BYTES",
    "_assert_captured_evaluation_query_run_current",
    "build_captured_evaluation_query_run_v0",
    "captured_evaluation_query_run_bytes",
    "captured_evaluation_query_run_from_bytes",
    "explain_captured_evaluation_query_run_v0",
    "verify_captured_evaluation_query_run_v0",
]
