"""Exact result-side protocol for one detached neutral evaluation.

The full :class:`EvaluationRunV1` is encoded here rather than treating the
existing replay payload as a complete run. Every nested DTO is reconstructed
through a named, closed arm before its derived digest is accepted. Runtime
comparison and Scenario-diff records are projected losslessly without
importing their private runtime owners or claiming causal/evidence authority.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from typing import Any

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError
from .evaluation_run_v1 import (
    EvaluationEngineResultV1,
    EvaluationReplayFactV1,
    EvaluationReplayPayloadV1,
    EvaluationReplayRelationV1,
    EvaluationReplayWorldV1,
    EvaluationRunSideV1,
    EvaluationRunV1,
    ExplainTargetV1,
    ProviderReceiptRefV1,
    evaluation_replay_payload_v1_bytes,
    evaluation_replay_payload_v1_from_bytes,
)
from .goal_plan_v1 import (
    GoalExpectationOutcomeV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalRowAnchorV1,
    GoalSummaryAnchorV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
)
from .scenario_v1 import ResolvedScenarioOperationV1, ScenarioValueV1
from .schema_runtime import FieldPath
from .sealed_evaluation_v1 import (
    MAX_GOAL_EXPECTATION_VALUES_V1,
    MAX_GOAL_EXPECTATIONS_V1,
    MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,
    EvaluationProviderCaptureV1,
    SealedEvaluationRequestV1,
    assert_sealed_evaluation_request_current_v1,
    decode_sealed_evaluation_request_v1,
    evaluation_execution_profile_v1_bytes,
    evaluation_execution_profile_v1_from_bytes,
    goal_plan_v1_bytes,
    goal_plan_v1_from_bytes,
)

MAX_SEALED_EVALUATION_RESULT_BYTES_V1 = 16 * 1024 * 1024
MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1 = 4096
MAX_EVALUATION_SCENARIO_OPERATIONS_V1 = 256

_RUN_TYPE = "FactGraphEvaluationRunV1"
_COMPARISON_TYPE = "FactGraphEvaluationComparisonV1"
_SCENARIO_DIFF_TYPE = "FactGraphEvaluationScenarioDiffV1"
_RESULT_TYPE = "FactGraphSealedEvaluationResultV1"
_SHA256_TOKEN_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_BARE_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _fail(message: str) -> ProtocolShapeError:
    return ProtocolShapeError(message)


def _reject_constant(value: str) -> object:
    raise _fail(f"non-standard JSON constant {value!r} is forbidden")


def _reject_float(value: str) -> object:
    raise _fail(f"raw JSON float {value!r} is forbidden")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _fail(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _json_depth(value: object) -> int:
    if type(value) is dict:
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if type(value) is list:
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _assert_plain_json(value: object, *, label: str) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        raise _fail(f"{label} contains a raw binary float")
    if type(value) is list:
        for index, item in enumerate(value):
            _assert_plain_json(item, label=f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise _fail(f"{label} contains a non-string object key")
            _assert_plain_json(item, label=f"{label}[{key!r}]")
        return
    raise _fail(f"{label} contains a non-JSON concrete type")


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    _assert_plain_json(value, label=label)
    if _json_depth(value) > 64:
        raise _fail(f"{label} exceeds the JSON depth limit")
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise _fail(f"{label} is not canonical UTF-8 JSON") from exc


def _load_json_object(
    raw: object,
    *,
    label: str,
    max_bytes: int = MAX_SEALED_EVALUATION_RESULT_BYTES_V1,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw or len(raw) > max_bytes:
        raise _fail(f"{label} must be non-empty exact bytes within its limit")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except ProtocolShapeError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise _fail(f"{label} must be canonical UTF-8 JSON") from exc
    if type(value) is not dict:
        raise _fail(f"{label} must be a JSON object")
    if _canonical_json_bytes(value, label=label) != raw:
        raise _fail(f"{label} must use the canonical JSON representation")
    return value


def _exact_object(value: object, keys: frozenset[str], *, label: str) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != keys:
        raise _fail(f"{label} has unknown or missing fields")
    return value


def _array(value: object, *, label: str, maximum: int | None = None) -> list[object]:
    if type(value) is not list:
        raise _fail(f"{label} must be a JSON array")
    if maximum is not None and len(value) > maximum:
        raise _fail(f"{label} exceeds its item limit")
    return value


def _string(value: object, *, label: str, non_empty: bool = True) -> str:
    if type(value) is not str or (non_empty and not value):
        raise _fail(f"{label} must be an exact{' non-empty' if non_empty else ''} string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _fail(f"{label} must contain Unicode scalar values") from exc
    return value


def _token(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _SHA256_TOKEN_RE.fullmatch(text) is None:
        raise _fail(f"{label} must be lowercase sha256:<64 hex>")
    return text


def _bare_digest(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _BARE_SHA256_RE.fullmatch(text) is None:
        raise _fail(f"{label} must be lowercase bare sha256 hex")
    return text


def _construct(label: str, factory: Any) -> Any:
    try:
        return factory()
    except ProtocolShapeError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise _fail(f"{label} is malformed") from exc


def _digest_plain(value: object, *, label: str) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        raise _fail(f"{label} contains a raw binary float")
    if type(value) in {tuple, list}:
        return [_digest_plain(item, label=f"{label}[]") for item in value]
    if type(value) is dict:
        result: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise _fail(f"{label} contains a non-string digest key")
            result[key] = _digest_plain(item, label=f"{label}[{key!r}]")
        return result
    raise _fail(f"{label} contains an unsupported digest value")


def _domain_token(domain: str, payload: object) -> str:
    return "sha256:" + sha256_hex(
        _canonical_json_bytes(
            {
                "format": domain,
                "payload": _digest_plain(payload, label=f"{domain} digest payload"),
            },
            label=f"{domain} digest envelope",
        )
    )


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_b64u(value: object, *, label: str) -> bytes:
    text = _string(value, label=label)
    if "=" in text:
        raise _fail(f"{label} must be unpadded canonical base64url")
    try:
        raw = base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise _fail(f"{label} must be canonical base64url") from exc
    if not raw or len(raw) > MAX_SEALED_EVALUATION_RESULT_BYTES_V1 or _b64u(raw) != text:
        raise _fail(f"{label} must be bounded non-empty canonical base64url")
    return raw


def _component_object(raw: bytes, *, label: str) -> dict[str, object]:
    return _load_json_object(raw, label=label)


def _goal_value_current(value: GoalValueV1) -> GoalValueV1:
    if type(value) is not GoalValueV1:
        raise _fail("Goal value must be exact GoalValueV1")
    current = _construct("GoalValueV1", lambda: GoalValueV1(value.tag, value.value))
    if current != value:
        raise _fail("GoalValueV1 is stale or noncanonical")
    return current


def _goal_value_to_wire(value: GoalValueV1) -> dict[str, object]:
    value = _goal_value_current(value)
    return {"tag": value.tag, "value": value.value, "value_digest": value.value_digest}


def _goal_value_from_wire(value: object) -> GoalValueV1:
    row = _exact_object(
        value,
        frozenset({"tag", "value", "value_digest"}),
        label="GoalValueV1",
    )
    result = _construct("GoalValueV1", lambda: GoalValueV1(row["tag"], row["value"]))
    if row["value_digest"] != result.value_digest:
        raise _fail("GoalValueV1 value_digest mismatch")
    return result


def _goal_anchor_current(anchor: GoalRowAnchorV1) -> GoalRowAnchorV1:
    if type(anchor) is not GoalRowAnchorV1:
        raise _fail("Goal row anchor must be exact GoalRowAnchorV1")
    current = _construct(
        "GoalRowAnchorV1",
        lambda: GoalRowAnchorV1(anchor.plan_digest, anchor.semantic_row_digest),
    )
    if current != anchor:
        raise _fail("GoalRowAnchorV1 is stale")
    return current


def _goal_anchor_to_wire(anchor: GoalRowAnchorV1) -> dict[str, object]:
    anchor = _goal_anchor_current(anchor)
    return {
        "plan_digest": anchor.plan_digest,
        "semantic_row_digest": anchor.semantic_row_digest,
        "anchor_digest": anchor.anchor_digest,
    }


def _goal_anchor_from_wire(value: object) -> GoalRowAnchorV1:
    row = _exact_object(
        value,
        frozenset({"plan_digest", "semantic_row_digest", "anchor_digest"}),
        label="GoalRowAnchorV1",
    )
    result = _construct(
        "GoalRowAnchorV1",
        lambda: GoalRowAnchorV1(row["plan_digest"], row["semantic_row_digest"]),
    )
    if row["anchor_digest"] != result.anchor_digest:
        raise _fail("GoalRowAnchorV1 anchor_digest mismatch")
    return result


def _goal_row_current(row: GoalResultRowV1) -> GoalResultRowV1:
    if type(row) is not GoalResultRowV1 or type(row.values) is not tuple or row.anchor is None:
        raise _fail("Run row must be an exact anchored GoalResultRowV1")
    if len(row.values) > MAX_GOAL_EXPECTATION_VALUES_V1:
        raise _fail("GoalResultRowV1 exceeds the selected-value limit")
    values: list[tuple[str, GoalValueV1]] = []
    for index, item in enumerate(row.values):
        if type(item) is not tuple or len(item) != 2:
            raise _fail(f"GoalResultRowV1.values[{index}] is malformed")
        values.append(
            (
                _string(item[0], label=f"GoalResultRowV1.values[{index}].alias"),
                _goal_value_current(item[1]),
            )
        )
    current = _construct(
        "GoalResultRowV1",
        lambda: GoalResultRowV1(tuple(values), anchor=_goal_anchor_current(row.anchor)),
    )
    if current != row:
        raise _fail("GoalResultRowV1 is stale or noncanonical")
    return current


def _goal_row_to_wire(row: GoalResultRowV1) -> dict[str, object]:
    row = _goal_row_current(row)
    assert row.anchor is not None
    return {
        "values": [
            {"alias": alias, "value": _goal_value_to_wire(value)} for alias, value in row.values
        ],
        "semantic_row_digest": row.semantic_row_digest,
        "anchor": _goal_anchor_to_wire(row.anchor),
    }


def _goal_row_from_wire(value: object) -> GoalResultRowV1:
    row = _exact_object(
        value,
        frozenset({"values", "semantic_row_digest", "anchor"}),
        label="GoalResultRowV1",
    )
    cells = _array(
        row["values"],
        label="GoalResultRowV1.values",
        maximum=MAX_GOAL_EXPECTATION_VALUES_V1,
    )
    if not cells:
        raise _fail("GoalResultRowV1.values must be non-empty")
    values: list[tuple[str, GoalValueV1]] = []
    for index, item in enumerate(cells):
        cell = _exact_object(
            item,
            frozenset({"alias", "value"}),
            label=f"GoalResultRowV1.values[{index}]",
        )
        values.append(
            (
                _string(cell["alias"], label=f"GoalResultRowV1.values[{index}].alias"),
                _goal_value_from_wire(cell["value"]),
            )
        )
    result = _construct(
        "GoalResultRowV1",
        lambda: GoalResultRowV1(tuple(values), anchor=_goal_anchor_from_wire(row["anchor"])),
    )
    if row["semantic_row_digest"] != result.semantic_row_digest:
        raise _fail("GoalResultRowV1 semantic_row_digest mismatch")
    return result


def _expectation_outcome_current(
    outcome: GoalExpectationOutcomeV1,
) -> GoalExpectationOutcomeV1:
    if type(outcome) is not GoalExpectationOutcomeV1:
        raise _fail("Expectation outcome must be exact GoalExpectationOutcomeV1")
    if type(outcome.matched_semantic_row_digests) is not tuple:
        raise _fail("Expectation outcome matches must be an exact tuple")
    current = _construct(
        "GoalExpectationOutcomeV1",
        lambda: GoalExpectationOutcomeV1(
            outcome.expectation_id,
            outcome.expectation_digest,
            outcome.kind,
            outcome.status,
            tuple(outcome.matched_semantic_row_digests),
            outcome.diagnostic_code,
        ),
    )
    if current != outcome:
        raise _fail("GoalExpectationOutcomeV1 is stale or noncanonical")
    return current


def _expectation_outcome_to_wire(
    outcome: GoalExpectationOutcomeV1,
) -> dict[str, object]:
    outcome = _expectation_outcome_current(outcome)
    return {
        "expectation_id": outcome.expectation_id,
        "expectation_digest": outcome.expectation_digest,
        "kind": outcome.kind,
        "status": outcome.status,
        "matched_semantic_row_digests": list(outcome.matched_semantic_row_digests),
        "diagnostic_code": outcome.diagnostic_code,
        "outcome_digest": outcome.outcome_digest,
    }


def _expectation_outcome_from_wire(value: object) -> GoalExpectationOutcomeV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "expectation_id",
                "expectation_digest",
                "kind",
                "status",
                "matched_semantic_row_digests",
                "diagnostic_code",
                "outcome_digest",
            }
        ),
        label="GoalExpectationOutcomeV1",
    )
    matched = _array(
        row["matched_semantic_row_digests"],
        label="GoalExpectationOutcomeV1.matched_semantic_row_digests",
        maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
    )
    result = _construct(
        "GoalExpectationOutcomeV1",
        lambda: GoalExpectationOutcomeV1(
            row["expectation_id"],
            row["expectation_digest"],
            row["kind"],
            row["status"],
            tuple(matched),
            row["diagnostic_code"],
        ),
    )
    if row["outcome_digest"] != result.outcome_digest:
        raise _fail("GoalExpectationOutcomeV1 outcome_digest mismatch")
    return result


def _summary_current(summary: GoalSummaryAnchorV1) -> GoalSummaryAnchorV1:
    if type(summary) is not GoalSummaryAnchorV1 or type(summary.semantic_row_digests) is not tuple:
        raise _fail("Summary anchor must be exact GoalSummaryAnchorV1")
    if len(summary.semantic_row_digests) > MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1:
        raise _fail("GoalSummaryAnchorV1 exceeds the row limit")
    current = _construct(
        "GoalSummaryAnchorV1",
        lambda: GoalSummaryAnchorV1(
            summary.plan_digest,
            summary.result_mode,
            summary.completeness,
            tuple(summary.semantic_row_digests),
        ),
    )
    if current != summary:
        raise _fail("GoalSummaryAnchorV1 is stale or noncanonical")
    return current


def _summary_to_wire(summary: GoalSummaryAnchorV1) -> dict[str, object]:
    summary = _summary_current(summary)
    return {
        "plan_digest": summary.plan_digest,
        "result_mode": summary.result_mode,
        "completeness": summary.completeness,
        "semantic_row_digests": list(summary.semantic_row_digests),
        "summary_anchor_digest": summary.summary_anchor_digest,
    }


def _summary_from_wire(value: object) -> GoalSummaryAnchorV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "plan_digest",
                "result_mode",
                "completeness",
                "semantic_row_digests",
                "summary_anchor_digest",
            }
        ),
        label="GoalSummaryAnchorV1",
    )
    digests = _array(
        row["semantic_row_digests"],
        label="GoalSummaryAnchorV1.semantic_row_digests",
        maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
    )
    result = _construct(
        "GoalSummaryAnchorV1",
        lambda: GoalSummaryAnchorV1(
            row["plan_digest"],
            row["result_mode"],
            row["completeness"],
            tuple(digests),
        ),
    )
    if row["summary_anchor_digest"] != result.summary_anchor_digest:
        raise _fail("GoalSummaryAnchorV1 summary_anchor_digest mismatch")
    return result


def _goal_result_current(result: GoalResultV1) -> GoalResultV1:
    if (
        type(result) is not GoalResultV1
        or type(result.rows) is not tuple
        or type(result.expectation_outcomes) is not tuple
        or result.summary_anchor is None
    ):
        raise _fail("Result must be an exact completed GoalResultV1")
    if len(result.rows) > MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1:
        raise _fail("GoalResultV1 exceeds the row limit")
    if len(result.expectation_outcomes) > MAX_GOAL_EXPECTATIONS_V1:
        raise _fail("GoalResultV1 exceeds the expectation-outcome limit")
    current = _construct(
        "GoalResultV1",
        lambda: GoalResultV1(
            result.plan_digest,
            result.result_mode,
            result.completeness,
            tuple(_goal_row_current(item) for item in result.rows),
            result.exists_value,
            result.count_value,
            tuple(_expectation_outcome_current(item) for item in result.expectation_outcomes),
            _summary_current(result.summary_anchor),
        ),
    )
    if current != result:
        raise _fail("GoalResultV1 is stale or noncanonical")
    return current


def _goal_result_to_wire(result: GoalResultV1) -> dict[str, object]:
    result = _goal_result_current(result)
    assert result.summary_anchor is not None
    return {
        "plan_digest": result.plan_digest,
        "result_mode": result.result_mode,
        "completeness": result.completeness,
        "rows": [_goal_row_to_wire(item) for item in result.rows],
        "exists_value": result.exists_value,
        "count_value": result.count_value,
        "expectation_outcomes": [
            _expectation_outcome_to_wire(item) for item in result.expectation_outcomes
        ],
        "summary_anchor": _summary_to_wire(result.summary_anchor),
        "result_digest": result.result_digest,
    }


def _goal_result_from_wire(value: object) -> GoalResultV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "plan_digest",
                "result_mode",
                "completeness",
                "rows",
                "exists_value",
                "count_value",
                "expectation_outcomes",
                "summary_anchor",
                "result_digest",
            }
        ),
        label="GoalResultV1",
    )
    rows = _array(
        row["rows"],
        label="GoalResultV1.rows",
        maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
    )
    outcomes = _array(
        row["expectation_outcomes"],
        label="GoalResultV1.expectation_outcomes",
        maximum=MAX_GOAL_EXPECTATIONS_V1,
    )
    result = _construct(
        "GoalResultV1",
        lambda: GoalResultV1(
            row["plan_digest"],
            row["result_mode"],
            row["completeness"],
            tuple(_goal_row_from_wire(item) for item in rows),
            row["exists_value"],
            row["count_value"],
            tuple(_expectation_outcome_from_wire(item) for item in outcomes),
            _summary_from_wire(row["summary_anchor"]),
        ),
    )
    if row["result_digest"] != result.result_digest:
        raise _fail("GoalResultV1 result_digest mismatch")
    return result


def _assessment_current(value: GoalTechnicalAssessmentV1) -> GoalTechnicalAssessmentV1:
    if type(value) is not GoalTechnicalAssessmentV1:
        raise _fail("Assessment must be exact GoalTechnicalAssessmentV1")
    current = _construct(
        "GoalTechnicalAssessmentV1",
        lambda: GoalTechnicalAssessmentV1(
            value.plan_digest,
            value.result_digest,
            value.scenario_resolution,
            value.execution,
            value.parity,
            value.completeness,
            value.expectation,
            value.explain,
            value.replay,
            value.contract_validity,
            value.exact_local_closure,
            value.capability,
        ),
    )
    if current != value:
        raise _fail("GoalTechnicalAssessmentV1 is stale")
    return current


def _assessment_to_wire(value: GoalTechnicalAssessmentV1) -> dict[str, object]:
    value = _assessment_current(value)
    return {
        "plan_digest": value.plan_digest,
        "result_digest": value.result_digest,
        "scenario_resolution": value.scenario_resolution,
        "execution": value.execution,
        "parity": value.parity,
        "completeness": value.completeness,
        "expectation": value.expectation,
        "explain": value.explain,
        "replay": value.replay,
        "contract_validity": value.contract_validity,
        "exact_local_closure": value.exact_local_closure,
        "capability": value.capability,
        "assessment_digest": value.assessment_digest,
    }


def _assessment_from_wire(value: object) -> GoalTechnicalAssessmentV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "plan_digest",
                "result_digest",
                "scenario_resolution",
                "execution",
                "parity",
                "completeness",
                "expectation",
                "explain",
                "replay",
                "contract_validity",
                "exact_local_closure",
                "capability",
                "assessment_digest",
            }
        ),
        label="GoalTechnicalAssessmentV1",
    )
    result = _construct(
        "GoalTechnicalAssessmentV1",
        lambda: GoalTechnicalAssessmentV1(
            row["plan_digest"],
            row["result_digest"],
            row["scenario_resolution"],
            row["execution"],
            row["parity"],
            row["completeness"],
            row["expectation"],
            row["explain"],
            row["replay"],
            row["contract_validity"],
            row["exact_local_closure"],
            row["capability"],
        ),
    )
    if row["assessment_digest"] != result.assessment_digest:
        raise _fail("GoalTechnicalAssessmentV1 assessment_digest mismatch")
    return result


def _engine_frame_current(value: EvaluationEngineResultV1) -> EvaluationEngineResultV1:
    if type(value) is not EvaluationEngineResultV1:
        raise _fail("Engine frame must be exact EvaluationEngineResultV1")
    current = _construct(
        "EvaluationEngineResultV1",
        lambda: EvaluationEngineResultV1(
            value.engine,
            None if value.result is None else _goal_result_current(value.result),
            value.status,
            value.diagnostic_code,
            value.diagnostic_detail_digest,
        ),
    )
    if current != value:
        raise _fail("EvaluationEngineResultV1 is stale")
    return current


def _engine_frame_to_wire(value: EvaluationEngineResultV1) -> dict[str, object]:
    value = _engine_frame_current(value)
    return {
        "engine": value.engine,
        "result": None if value.result is None else _goal_result_to_wire(value.result),
        "status": value.status,
        "diagnostic_code": value.diagnostic_code,
        "diagnostic_detail_digest": value.diagnostic_detail_digest,
        "semantic_row_set_digest": value.semantic_row_set_digest,
        "frame_digest": value.frame_digest,
    }


def _engine_frame_from_wire(value: object) -> EvaluationEngineResultV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "engine",
                "result",
                "status",
                "diagnostic_code",
                "diagnostic_detail_digest",
                "semantic_row_set_digest",
                "frame_digest",
            }
        ),
        label="EvaluationEngineResultV1",
    )
    result = _construct(
        "EvaluationEngineResultV1",
        lambda: EvaluationEngineResultV1(
            row["engine"],
            None if row["result"] is None else _goal_result_from_wire(row["result"]),
            row["status"],
            row["diagnostic_code"],
            row["diagnostic_detail_digest"],
        ),
    )
    if (
        row["semantic_row_set_digest"] != result.semantic_row_set_digest
        or row["frame_digest"] != result.frame_digest
    ):
        raise _fail("EvaluationEngineResultV1 derived digest mismatch")
    return result


def _run_side_current(value: EvaluationRunSideV1) -> EvaluationRunSideV1:
    if type(value) is not EvaluationRunSideV1 or type(value.engine_results) is not tuple:
        raise _fail("Run side must be exact EvaluationRunSideV1")
    if not 1 <= len(value.engine_results) <= 3:
        raise _fail("EvaluationRunSideV1 engine inventory is outside its limit")
    current = _construct(
        "EvaluationRunSideV1",
        lambda: EvaluationRunSideV1(
            value.name,
            value.plan_digest,
            value.world_side,
            value.world_capture_digest,
            _goal_result_current(value.canonical_result),
            tuple(_engine_frame_current(item) for item in value.engine_results),
            _assessment_current(value.assessment),
        ),
    )
    if current != value:
        raise _fail("EvaluationRunSideV1 is stale or noncanonical")
    return current


def _run_side_to_wire(value: EvaluationRunSideV1) -> dict[str, object]:
    value = _run_side_current(value)
    return {
        "name": value.name,
        "plan_digest": value.plan_digest,
        "world_side": value.world_side,
        "world_capture_digest": value.world_capture_digest,
        "canonical_result": _goal_result_to_wire(value.canonical_result),
        "engine_results": [_engine_frame_to_wire(item) for item in value.engine_results],
        "assessment": _assessment_to_wire(value.assessment),
        "side_digest": value.side_digest,
    }


def _run_side_from_wire(value: object) -> EvaluationRunSideV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "name",
                "plan_digest",
                "world_side",
                "world_capture_digest",
                "canonical_result",
                "engine_results",
                "assessment",
                "side_digest",
            }
        ),
        label="EvaluationRunSideV1",
    )
    frames = _array(
        row["engine_results"],
        label="EvaluationRunSideV1.engine_results",
        maximum=3,
    )
    if not frames:
        raise _fail("EvaluationRunSideV1.engine_results must be non-empty")
    result = _construct(
        "EvaluationRunSideV1",
        lambda: EvaluationRunSideV1(
            row["name"],
            row["plan_digest"],
            row["world_side"],
            row["world_capture_digest"],
            _goal_result_from_wire(row["canonical_result"]),
            tuple(_engine_frame_from_wire(item) for item in frames),
            _assessment_from_wire(row["assessment"]),
        ),
    )
    if row["side_digest"] != result.side_digest:
        raise _fail("EvaluationRunSideV1 side_digest mismatch")
    return result


def _replay_fact_current(value: EvaluationReplayFactV1) -> EvaluationReplayFactV1:
    if type(value) is not EvaluationReplayFactV1 or type(value.values) is not tuple:
        raise _fail("Replay fact must be exact EvaluationReplayFactV1")
    current = _construct(
        "EvaluationReplayFactV1",
        lambda: EvaluationReplayFactV1(
            value.witness_ref,
            tuple(_goal_value_current(item) for item in value.values),
        ),
    )
    if current != value:
        raise _fail("EvaluationReplayFactV1 is stale or noncanonical")
    return current


def _replay_relation_current(
    value: EvaluationReplayRelationV1,
) -> EvaluationReplayRelationV1:
    if (
        type(value) is not EvaluationReplayRelationV1
        or type(value.value_tags) is not tuple
        or type(value.facts) is not tuple
    ):
        raise _fail("Replay relation must be exact EvaluationReplayRelationV1")
    current = _construct(
        "EvaluationReplayRelationV1",
        lambda: EvaluationReplayRelationV1(
            value.predicate_id,
            tuple(value.value_tags),
            tuple(_replay_fact_current(item) for item in value.facts),
        ),
    )
    if current != value:
        raise _fail("EvaluationReplayRelationV1 is stale or noncanonical")
    return current


def _replay_world_current(value: EvaluationReplayWorldV1) -> EvaluationReplayWorldV1:
    if (
        type(value) is not EvaluationReplayWorldV1
        or type(value.closure_target_digests) is not tuple
        or type(value.relations) is not tuple
    ):
        raise _fail("Replay world must be exact EvaluationReplayWorldV1")
    current = _construct(
        "EvaluationReplayWorldV1",
        lambda: EvaluationReplayWorldV1(
            value.side,
            value.semantic_world_digest,
            value.resolution_evidence_digest,
            tuple(value.closure_target_digests),
            tuple(_replay_relation_current(item) for item in value.relations),
        ),
    )
    if current != value:
        raise _fail("EvaluationReplayWorldV1 is stale or noncanonical")
    return current


def _provider_receipt_current(value: ProviderReceiptRefV1) -> ProviderReceiptRefV1:
    if type(value) is not ProviderReceiptRefV1:
        raise _fail("Provider receipt must be exact ProviderReceiptRefV1")
    current = _construct(
        "ProviderReceiptRefV1",
        lambda: ProviderReceiptRefV1(
            value.provider_digest,
            value.request_digest,
            value.materialization_digest,
            value.receipt_ref,
            value.receipt_digest,
        ),
    )
    if current != value:
        raise _fail("ProviderReceiptRefV1 is stale")
    return current


def _replay_payload_current(value: EvaluationReplayPayloadV1) -> EvaluationReplayPayloadV1:
    if (
        type(value) is not EvaluationReplayPayloadV1
        or type(value.schema_bytes) is not bytes
        or type(value.compiled_program_bytes) is not bytes
        or type(value.worlds) is not tuple
        or type(value.provider_receipts) is not tuple
    ):
        raise _fail("Replay payload must be exact EvaluationReplayPayloadV1")
    current = _construct(
        "EvaluationReplayPayloadV1",
        lambda: EvaluationReplayPayloadV1(
            value.schema_digest,
            value.address_space_digest,
            value.schema_bytes,
            value.compiled_program_bytes,
            tuple(_replay_world_current(item) for item in value.worlds),
            tuple(_provider_receipt_current(item) for item in value.provider_receipts),
        ),
    )
    if current != value:
        raise _fail("EvaluationReplayPayloadV1 is stale or noncanonical")
    return current


def _explain_target_current(value: ExplainTargetV1) -> ExplainTargetV1:
    if type(value) is not ExplainTargetV1:
        raise _fail("Explain target must be exact ExplainTargetV1")
    current = _construct(
        "ExplainTargetV1",
        lambda: ExplainTargetV1(value.side, value.kind, value.anchor_digest),
    )
    if current != value:
        raise _fail("ExplainTargetV1 is stale")
    return current


def _explain_target_to_wire(value: ExplainTargetV1) -> dict[str, object]:
    value = _explain_target_current(value)
    return {
        "side": value.side,
        "kind": value.kind,
        "anchor_digest": value.anchor_digest,
        "target_digest": value.target_digest,
    }


def _explain_target_from_wire(value: object) -> ExplainTargetV1:
    row = _exact_object(
        value,
        frozenset({"side", "kind", "anchor_digest", "target_digest"}),
        label="ExplainTargetV1",
    )
    result = _construct(
        "ExplainTargetV1",
        lambda: ExplainTargetV1(row["side"], row["kind"], row["anchor_digest"]),
    )
    if row["target_digest"] != result.target_digest:
        raise _fail("ExplainTargetV1 target_digest mismatch")
    return result


def _run_current(run: EvaluationRunV1) -> EvaluationRunV1:
    if type(run) is not EvaluationRunV1:
        raise _fail("Run must be exact EvaluationRunV1")
    plan = goal_plan_v1_from_bytes(goal_plan_v1_bytes(run.plan))
    profile = evaluation_execution_profile_v1_from_bytes(
        evaluation_execution_profile_v1_bytes(run.execution_profile)
    )
    candidate = (
        None
        if run.candidate_plan is None
        else goal_plan_v1_from_bytes(goal_plan_v1_bytes(run.candidate_plan))
    )
    current = _construct(
        "EvaluationRunV1",
        lambda: EvaluationRunV1(
            plan,
            profile,
            _replay_payload_current(run.replay_payload),
            _run_side_current(run.baseline),
            _run_side_current(run.effective),
            candidate,
            None if run.candidate_effective is None else _run_side_current(run.candidate_effective),
            None if run.explain_target is None else _explain_target_current(run.explain_target),
        ),
    )
    if current != run:
        raise _fail("EvaluationRunV1 is stale or noncanonical")
    return current


def _run_to_wire(run: EvaluationRunV1) -> dict[str, object]:
    run = _run_current(run)
    replay_payload = evaluation_replay_payload_v1_bytes(run.replay_payload)
    return {
        "$type": _RUN_TYPE,
        "plan": _component_object(goal_plan_v1_bytes(run.plan), label="GoalPlanV1"),
        "execution_profile": _component_object(
            evaluation_execution_profile_v1_bytes(run.execution_profile),
            label="EvaluationExecutionProfileV1",
        ),
        "replay_payload": _component_object(
            replay_payload,
            label="EvaluationReplayPayloadV1",
        ),
        "baseline": _run_side_to_wire(run.baseline),
        "effective": _run_side_to_wire(run.effective),
        "candidate_plan": (
            None
            if run.candidate_plan is None
            else _component_object(
                goal_plan_v1_bytes(run.candidate_plan),
                label="CandidateGoalPlanV1",
            )
        ),
        "candidate_effective": (
            None if run.candidate_effective is None else _run_side_to_wire(run.candidate_effective)
        ),
        "explain_target": (
            None if run.explain_target is None else _explain_target_to_wire(run.explain_target)
        ),
        "run_digest": run.run_digest,
    }


def evaluation_run_v1_bytes(run: EvaluationRunV1) -> bytes:
    """Encode the complete neutral Run with its exact nested component graph."""

    raw = _canonical_json_bytes(_run_to_wire(run), label="EvaluationRunV1")
    if len(raw) > MAX_SEALED_EVALUATION_RESULT_BYTES_V1:
        raise _fail("EvaluationRunV1 exceeds the 16 MiB result limit")
    return raw


def evaluation_run_v1_from_bytes(raw: bytes) -> EvaluationRunV1:
    """Decode a complete neutral Run without executing or reading live state."""

    row = _load_json_object(raw, label="EvaluationRunV1")
    data = _exact_object(
        row,
        frozenset(
            {
                "$type",
                "plan",
                "execution_profile",
                "replay_payload",
                "baseline",
                "effective",
                "candidate_plan",
                "candidate_effective",
                "explain_target",
                "run_digest",
            }
        ),
        label="EvaluationRunV1",
    )
    if data["$type"] != _RUN_TYPE:
        raise _fail("EvaluationRunV1 type is invalid")
    plan = goal_plan_v1_from_bytes(
        _canonical_json_bytes(data["plan"], label="EvaluationRunV1.plan")
    )
    profile = evaluation_execution_profile_v1_from_bytes(
        _canonical_json_bytes(
            data["execution_profile"],
            label="EvaluationRunV1.execution_profile",
        )
    )
    replay_payload = evaluation_replay_payload_v1_from_bytes(
        _canonical_json_bytes(
            data["replay_payload"],
            label="EvaluationRunV1.replay_payload",
        )
    )
    candidate_plan = (
        None
        if data["candidate_plan"] is None
        else goal_plan_v1_from_bytes(
            _canonical_json_bytes(
                data["candidate_plan"],
                label="EvaluationRunV1.candidate_plan",
            )
        )
    )
    result = _construct(
        "EvaluationRunV1",
        lambda: EvaluationRunV1(
            plan,
            profile,
            replay_payload,
            _run_side_from_wire(data["baseline"]),
            _run_side_from_wire(data["effective"]),
            candidate_plan,
            None
            if data["candidate_effective"] is None
            else _run_side_from_wire(data["candidate_effective"]),
            None
            if data["explain_target"] is None
            else _explain_target_from_wire(data["explain_target"]),
        ),
    )
    if data["run_digest"] != result.run_digest:
        raise _fail("EvaluationRunV1 run_digest mismatch")
    if evaluation_run_v1_bytes(result) != raw:
        raise _fail("EvaluationRunV1 representation is not canonical")
    return result


def _canonical_token_tuple(
    values: object,
    *,
    label: str,
    maximum: int,
) -> tuple[str, ...]:
    if type(values) is not tuple or len(values) > maximum:
        raise _fail(f"{label} must be an exact bounded tuple")
    result = tuple(_token(item, label=f"{label}[]") for item in values)
    if tuple(sorted(result)) != result or len(set(result)) != len(result):
        raise _fail(f"{label} must be a canonical sorted set")
    return result


@dataclass(frozen=True)
class EvaluationComparisonV1:
    """Lossless non-causal projection of a runtime policy comparison."""

    primary_plan_digest: str
    candidate_plan_digest: str
    effective_world_capture_digest: str
    primary_target_digest: str
    candidate_target_digest: str
    primary_compiled_plan_digest: str
    candidate_compiled_plan_digest: str
    compiled_body_equal: bool
    compiled_head_equal: bool
    primary_policy_structure_digest: str | None
    candidate_policy_structure_digest: str | None
    authored_structure_relation: str
    shared_semantic_row_digests: tuple[str, ...]
    primary_only_semantic_row_digests: tuple[str, ...]
    candidate_only_semantic_row_digests: tuple[str, ...]
    result_relation: str
    structural_basis: str = "captured_compiled_derivation_body_and_head"
    causal_attribution: str = "not_claimed"
    comparison_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "primary_plan_digest",
            "candidate_plan_digest",
            "effective_world_capture_digest",
            "primary_target_digest",
            "candidate_target_digest",
            "primary_compiled_plan_digest",
            "candidate_compiled_plan_digest",
        ):
            _token(getattr(self, name), label=f"EvaluationComparisonV1.{name}")
        if type(self.compiled_body_equal) is not bool or type(self.compiled_head_equal) is not bool:
            raise _fail("EvaluationComparisonV1 equality flags must be exact bool")
        for name in (
            "primary_policy_structure_digest",
            "candidate_policy_structure_digest",
        ):
            value = getattr(self, name)
            if value is not None:
                _bare_digest(value, label=f"EvaluationComparisonV1.{name}")
        if self.primary_target_digest == self.candidate_target_digest:
            raise _fail("EvaluationComparisonV1 requires distinct immutable targets")
        primary_structure = self.primary_policy_structure_digest
        candidate_structure = self.candidate_policy_structure_digest
        if primary_structure is None and candidate_structure is None:
            expected_structure_relation = "not_captured"
        elif primary_structure is None or candidate_structure is None:
            expected_structure_relation = "captured"
        elif primary_structure == candidate_structure:
            expected_structure_relation = "equivalent"
        else:
            expected_structure_relation = "different"
        if self.authored_structure_relation != expected_structure_relation:
            raise _fail("EvaluationComparisonV1 authored structure relation is derived")
        if self.structural_basis != "captured_compiled_derivation_body_and_head":
            raise _fail("EvaluationComparisonV1 structural_basis is fixed")
        if self.causal_attribution != "not_claimed":
            raise _fail("EvaluationComparisonV1 cannot claim causal attribution")
        shared = _canonical_token_tuple(
            self.shared_semantic_row_digests,
            label="EvaluationComparisonV1.shared_semantic_row_digests",
            maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
        )
        primary_only = _canonical_token_tuple(
            self.primary_only_semantic_row_digests,
            label="EvaluationComparisonV1.primary_only_semantic_row_digests",
            maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
        )
        candidate_only = _canonical_token_tuple(
            self.candidate_only_semantic_row_digests,
            label="EvaluationComparisonV1.candidate_only_semantic_row_digests",
            maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
        )
        if (
            set(shared) & set(primary_only)
            or set(shared) & set(candidate_only)
            or set(primary_only) & set(candidate_only)
        ):
            raise _fail("EvaluationComparisonV1 semantic row sets must be disjoint")
        expected_result_relation = "different" if primary_only or candidate_only else "equivalent"
        if self.result_relation != expected_result_relation:
            raise _fail("EvaluationComparisonV1 result relation is derived")
        object.__setattr__(
            self,
            "comparison_digest",
            _domain_token(
                "policy_variant_comparison_v1",
                (
                    self.primary_plan_digest,
                    self.candidate_plan_digest,
                    self.effective_world_capture_digest,
                    self.primary_target_digest,
                    self.candidate_target_digest,
                    self.primary_compiled_plan_digest,
                    self.candidate_compiled_plan_digest,
                    self.compiled_body_equal,
                    self.compiled_head_equal,
                    self.primary_policy_structure_digest,
                    self.candidate_policy_structure_digest,
                    self.authored_structure_relation,
                    shared,
                    primary_only,
                    candidate_only,
                    self.result_relation,
                    self.structural_basis,
                    self.causal_attribution,
                ),
            ),
        )


def _comparison_current(value: EvaluationComparisonV1) -> EvaluationComparisonV1:
    if type(value) is not EvaluationComparisonV1:
        raise _fail("Comparison must be exact EvaluationComparisonV1")
    current = EvaluationComparisonV1(
        value.primary_plan_digest,
        value.candidate_plan_digest,
        value.effective_world_capture_digest,
        value.primary_target_digest,
        value.candidate_target_digest,
        value.primary_compiled_plan_digest,
        value.candidate_compiled_plan_digest,
        value.compiled_body_equal,
        value.compiled_head_equal,
        value.primary_policy_structure_digest,
        value.candidate_policy_structure_digest,
        value.authored_structure_relation,
        value.shared_semantic_row_digests,
        value.primary_only_semantic_row_digests,
        value.candidate_only_semantic_row_digests,
        value.result_relation,
        value.structural_basis,
        value.causal_attribution,
    )
    if current != value:
        raise _fail("EvaluationComparisonV1 is stale or noncanonical")
    return current


def _comparison_to_wire(value: EvaluationComparisonV1) -> dict[str, object]:
    value = _comparison_current(value)
    return {
        "$type": _COMPARISON_TYPE,
        "primary_plan_digest": value.primary_plan_digest,
        "candidate_plan_digest": value.candidate_plan_digest,
        "effective_world_capture_digest": value.effective_world_capture_digest,
        "primary_target_digest": value.primary_target_digest,
        "candidate_target_digest": value.candidate_target_digest,
        "primary_compiled_plan_digest": value.primary_compiled_plan_digest,
        "candidate_compiled_plan_digest": value.candidate_compiled_plan_digest,
        "compiled_body_equal": value.compiled_body_equal,
        "compiled_head_equal": value.compiled_head_equal,
        "primary_policy_structure_digest": value.primary_policy_structure_digest,
        "candidate_policy_structure_digest": value.candidate_policy_structure_digest,
        "authored_structure_relation": value.authored_structure_relation,
        "shared_semantic_row_digests": list(value.shared_semantic_row_digests),
        "primary_only_semantic_row_digests": list(value.primary_only_semantic_row_digests),
        "candidate_only_semantic_row_digests": list(value.candidate_only_semantic_row_digests),
        "result_relation": value.result_relation,
        "structural_basis": value.structural_basis,
        "causal_attribution": value.causal_attribution,
        "comparison_digest": value.comparison_digest,
    }


def _comparison_from_wire(value: object) -> EvaluationComparisonV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "primary_plan_digest",
                "candidate_plan_digest",
                "effective_world_capture_digest",
                "primary_target_digest",
                "candidate_target_digest",
                "primary_compiled_plan_digest",
                "candidate_compiled_plan_digest",
                "compiled_body_equal",
                "compiled_head_equal",
                "primary_policy_structure_digest",
                "candidate_policy_structure_digest",
                "authored_structure_relation",
                "shared_semantic_row_digests",
                "primary_only_semantic_row_digests",
                "candidate_only_semantic_row_digests",
                "result_relation",
                "structural_basis",
                "causal_attribution",
                "comparison_digest",
            }
        ),
        label="EvaluationComparisonV1",
    )
    if row["$type"] != _COMPARISON_TYPE:
        raise _fail("EvaluationComparisonV1 type is invalid")
    shared = _array(
        row["shared_semantic_row_digests"],
        label="EvaluationComparisonV1.shared_semantic_row_digests",
        maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
    )
    primary_only = _array(
        row["primary_only_semantic_row_digests"],
        label="EvaluationComparisonV1.primary_only_semantic_row_digests",
        maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
    )
    candidate_only = _array(
        row["candidate_only_semantic_row_digests"],
        label="EvaluationComparisonV1.candidate_only_semantic_row_digests",
        maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
    )
    result = _construct(
        "EvaluationComparisonV1",
        lambda: EvaluationComparisonV1(
            row["primary_plan_digest"],
            row["candidate_plan_digest"],
            row["effective_world_capture_digest"],
            row["primary_target_digest"],
            row["candidate_target_digest"],
            row["primary_compiled_plan_digest"],
            row["candidate_compiled_plan_digest"],
            row["compiled_body_equal"],
            row["compiled_head_equal"],
            row["primary_policy_structure_digest"],
            row["candidate_policy_structure_digest"],
            row["authored_structure_relation"],
            tuple(shared),
            tuple(primary_only),
            tuple(candidate_only),
            row["result_relation"],
            row["structural_basis"],
            row["causal_attribution"],
        ),
    )
    if row["comparison_digest"] != result.comparison_digest:
        raise _fail("EvaluationComparisonV1 comparison_digest mismatch")
    return result


def evaluation_comparison_v1_bytes(value: EvaluationComparisonV1) -> bytes:
    """Encode a typed non-causal candidate comparison projection."""

    raw = _canonical_json_bytes(
        _comparison_to_wire(value),
        label="EvaluationComparisonV1",
    )
    if len(raw) > MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1:
        raise _fail("EvaluationComparisonV1 exceeds the 4 MiB component limit")
    return raw


def evaluation_comparison_v1_from_bytes(raw: bytes) -> EvaluationComparisonV1:
    """Decode a typed comparison projection without evaluating either side."""

    row = _load_json_object(
        raw,
        label="EvaluationComparisonV1",
        max_bytes=MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,
    )
    result = _comparison_from_wire(row)
    if evaluation_comparison_v1_bytes(result) != raw:
        raise _fail("EvaluationComparisonV1 representation is not canonical")
    return result


def _scenario_value_current(value: ScenarioValueV1) -> ScenarioValueV1:
    if type(value) is not ScenarioValueV1:
        raise _fail("Scenario value must be exact ScenarioValueV1")
    current = _construct(
        "ScenarioValueV1",
        lambda: ScenarioValueV1(value.tag, value.value),
    )
    if current != value or current.value_digest != value.value_digest:
        raise _fail("ScenarioValueV1 is stale or noncanonical")
    return current


def _scenario_value_to_wire(value: ScenarioValueV1) -> dict[str, object]:
    value = _scenario_value_current(value)
    return {"tag": value.tag, "value": value.value, "value_digest": value.value_digest}


def _scenario_value_from_wire(value: object) -> ScenarioValueV1:
    row = _exact_object(
        value,
        frozenset({"tag", "value", "value_digest"}),
        label="ScenarioValueV1",
    )
    result = _construct(
        "ScenarioValueV1",
        lambda: ScenarioValueV1(row["tag"], row["value"]),
    )
    if row["value_digest"] != result.value_digest:
        raise _fail("ScenarioValueV1 value_digest mismatch")
    return result


def _field_path_current(value: FieldPath) -> FieldPath:
    if type(value) is not FieldPath:
        raise _fail("Field path must be exact FieldPath")
    current = _construct(
        "FieldPath",
        lambda: FieldPath(
            _string(value.entity_type, label="FieldPath.entity_type"),
            _string(value.field_name, label="FieldPath.field_name"),
        ),
    )
    if current != value:
        raise _fail("FieldPath is noncanonical")
    return current


def _field_path_to_wire(value: FieldPath) -> dict[str, object]:
    value = _field_path_current(value)
    return {"entity_type": value.entity_type, "field_name": value.field_name}


def _field_path_from_wire(value: object) -> FieldPath:
    row = _exact_object(
        value,
        frozenset({"entity_type", "field_name"}),
        label="FieldPath",
    )
    return _construct(
        "FieldPath",
        lambda: FieldPath(
            _string(row["entity_type"], label="FieldPath.entity_type"),
            _string(row["field_name"], label="FieldPath.field_name"),
        ),
    )


def _exact_string_tuple(value: object, *, label: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise _fail(f"{label} must be an exact tuple")
    result = tuple(_string(item, label=f"{label}[]") for item in value)
    if tuple(sorted(set(result))) != result:
        raise _fail(f"{label} must be sorted and unique")
    return result


def _resolved_operation_current(
    value: ResolvedScenarioOperationV1,
) -> ResolvedScenarioOperationV1:
    if type(value) is not ResolvedScenarioOperationV1 or type(value.values) is not tuple:
        raise _fail("Scenario operation must be exact ResolvedScenarioOperationV1")
    current = _construct(
        "ResolvedScenarioOperationV1",
        lambda: ResolvedScenarioOperationV1(
            kind=value.kind,
            entity_ref=value.entity_ref,
            entity_type=value.entity_type,
            predicate_id=value.predicate_id,
            field=None if value.field is None else _field_path_current(value.field),
            assertion_id=value.assertion_id,
            values=tuple(_scenario_value_current(item) for item in value.values),
            premise_ids=_exact_string_tuple(
                value.premise_ids,
                label="ResolvedScenarioOperationV1.premise_ids",
            ),
            origin_refs=_exact_string_tuple(
                value.origin_refs,
                label="ResolvedScenarioOperationV1.origin_refs",
            ),
            masked_witness_ids=_exact_string_tuple(
                value.masked_witness_ids,
                label="ResolvedScenarioOperationV1.masked_witness_ids",
            ),
            synthetic_witness_ids=_exact_string_tuple(
                value.synthetic_witness_ids,
                label="ResolvedScenarioOperationV1.synthetic_witness_ids",
            ),
        ),
    )
    if current != value:
        raise _fail("ResolvedScenarioOperationV1 is stale or noncanonical")
    return current


def _resolved_operation_to_wire(
    value: ResolvedScenarioOperationV1,
) -> dict[str, object]:
    value = _resolved_operation_current(value)
    return {
        "kind": value.kind,
        "entity_ref": value.entity_ref,
        "entity_type": value.entity_type,
        "predicate_id": value.predicate_id,
        "field": None if value.field is None else _field_path_to_wire(value.field),
        "assertion_id": value.assertion_id,
        "values": [_scenario_value_to_wire(item) for item in value.values],
        "premise_ids": list(value.premise_ids),
        "origin_refs": list(value.origin_refs),
        "masked_witness_ids": list(value.masked_witness_ids),
        "synthetic_witness_ids": list(value.synthetic_witness_ids),
        "operation_digest": value.operation_digest,
    }


def _wire_string_tuple(value: object, *, label: str) -> tuple[str, ...]:
    values = _array(value, label=label)
    result = tuple(_string(item, label=f"{label}[]") for item in values)
    if tuple(sorted(set(result))) != result:
        raise _fail(f"{label} must be sorted and unique")
    return result


def _resolved_operation_from_wire(value: object) -> ResolvedScenarioOperationV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "kind",
                "entity_ref",
                "entity_type",
                "predicate_id",
                "field",
                "assertion_id",
                "values",
                "premise_ids",
                "origin_refs",
                "masked_witness_ids",
                "synthetic_witness_ids",
                "operation_digest",
            }
        ),
        label="ResolvedScenarioOperationV1",
    )
    values = _array(row["values"], label="ResolvedScenarioOperationV1.values")
    result = _construct(
        "ResolvedScenarioOperationV1",
        lambda: ResolvedScenarioOperationV1(
            kind=row["kind"],
            entity_ref=row["entity_ref"],
            entity_type=row["entity_type"],
            predicate_id=row["predicate_id"],
            field=None if row["field"] is None else _field_path_from_wire(row["field"]),
            assertion_id=row["assertion_id"],
            values=tuple(_scenario_value_from_wire(item) for item in values),
            premise_ids=_wire_string_tuple(
                row["premise_ids"],
                label="ResolvedScenarioOperationV1.premise_ids",
            ),
            origin_refs=_wire_string_tuple(
                row["origin_refs"],
                label="ResolvedScenarioOperationV1.origin_refs",
            ),
            masked_witness_ids=_wire_string_tuple(
                row["masked_witness_ids"],
                label="ResolvedScenarioOperationV1.masked_witness_ids",
            ),
            synthetic_witness_ids=_wire_string_tuple(
                row["synthetic_witness_ids"],
                label="ResolvedScenarioOperationV1.synthetic_witness_ids",
            ),
        ),
    )
    if row["operation_digest"] != result.operation_digest:
        raise _fail("ResolvedScenarioOperationV1 operation_digest mismatch")
    return result


def _scenario_patch_digest(
    operations: tuple[ResolvedScenarioOperationV1, ...],
) -> str:
    return _domain_token(
        "evaluation_run_v1_scenario_patch",
        tuple(item.operation_digest for item in operations),
    )


@dataclass(frozen=True)
class EvaluationScenarioDiffV1:
    """Lossless descriptive baseline/effective Scenario observation."""

    run_digest: str
    plan_digest: str
    scenario_request_digest: str
    baseline_world_capture_digest: str
    effective_world_capture_digest: str
    baseline_semantic_world_digest: str
    effective_semantic_world_digest: str
    baseline_relation_snapshot_digest: str
    effective_relation_snapshot_digest: str
    baseline_resolution_evidence_digest: str
    effective_resolution_evidence_digest: str
    baseline_closure_target_digests: tuple[str, ...]
    effective_closure_target_digests: tuple[str, ...]
    input_difference_axes: tuple[str, ...]
    scenario_operations: tuple[ResolvedScenarioOperationV1, ...] | None = field(
        default=None,
        repr=False,
    )
    scenario_patch_capture: str = "not_captured"
    scenario_patch_application: str = "not_captured"
    scenario_patch_digest: str | None = None
    scenario_operation_digests: tuple[str, ...] = ()
    shared_semantic_row_digests: tuple[str, ...] = ()
    baseline_only_semantic_row_digests: tuple[str, ...] = ()
    effective_only_semantic_row_digests: tuple[str, ...] = ()
    result_relation: str = "equivalent"
    evidence_relation: str = "not_claimed"
    causal_attribution: str = "not_claimed"
    diff_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "run_digest",
            "plan_digest",
            "scenario_request_digest",
            "baseline_world_capture_digest",
            "effective_world_capture_digest",
            "baseline_semantic_world_digest",
            "effective_semantic_world_digest",
            "baseline_relation_snapshot_digest",
            "effective_relation_snapshot_digest",
            "baseline_resolution_evidence_digest",
            "effective_resolution_evidence_digest",
        ):
            _token(getattr(self, name), label=f"EvaluationScenarioDiffV1.{name}")
        baseline_closure = _canonical_token_tuple(
            self.baseline_closure_target_digests,
            label="EvaluationScenarioDiffV1.baseline_closure_target_digests",
            maximum=MAX_EVALUATION_SCENARIO_OPERATIONS_V1,
        )
        effective_closure = _canonical_token_tuple(
            self.effective_closure_target_digests,
            label="EvaluationScenarioDiffV1.effective_closure_target_digests",
            maximum=MAX_EVALUATION_SCENARIO_OPERATIONS_V1,
        )
        axis_order = (
            "semantic_world",
            "relation_snapshot",
            "resolution_evidence",
            "closure_targets",
        )
        if type(self.input_difference_axes) is not tuple:
            raise _fail("EvaluationScenarioDiffV1.input_difference_axes must be tuple")
        expected_axes = tuple(
            axis
            for axis, changed in zip(
                axis_order,
                (
                    self.baseline_semantic_world_digest != self.effective_semantic_world_digest,
                    self.baseline_relation_snapshot_digest
                    != self.effective_relation_snapshot_digest,
                    self.baseline_resolution_evidence_digest
                    != self.effective_resolution_evidence_digest,
                    baseline_closure != effective_closure,
                ),
                strict=True,
            )
            if changed
        )
        if self.input_difference_axes != expected_axes:
            raise _fail("EvaluationScenarioDiffV1 input axes are derived from world pins")
        if self.scenario_patch_capture not in {"captured", "not_captured"}:
            raise _fail("EvaluationScenarioDiffV1 patch capture state is invalid")
        if self.scenario_patch_capture == "captured":
            if (
                type(self.scenario_operations) is not tuple
                or len(self.scenario_operations) > MAX_EVALUATION_SCENARIO_OPERATIONS_V1
            ):
                raise _fail("Captured Scenario diff requires a bounded operation tuple")
            operations = tuple(
                _resolved_operation_current(item) for item in self.scenario_operations
            )
            expected_patch_digest = _scenario_patch_digest(operations)
            expected_operation_digests = tuple(item.operation_digest for item in operations)
            expected_application = "applied" if operations else "no_effective_operation"
            if self.scenario_patch_digest != expected_patch_digest:
                raise _fail("EvaluationScenarioDiffV1 patch digest mismatch")
        else:
            if self.scenario_operations is not None or self.scenario_patch_digest is not None:
                raise _fail("Uncaptured Scenario diff cannot carry operations or patch digest")
            operations = None
            expected_operation_digests = ()
            expected_application = "not_captured"
        if self.scenario_patch_application != expected_application:
            raise _fail("EvaluationScenarioDiffV1 patch application state is derived")
        if (
            type(self.scenario_operation_digests) is not tuple
            or self.scenario_operation_digests != expected_operation_digests
        ):
            raise _fail("EvaluationScenarioDiffV1 operation digests must match the patch")
        shared = _canonical_token_tuple(
            self.shared_semantic_row_digests,
            label="EvaluationScenarioDiffV1.shared_semantic_row_digests",
            maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
        )
        baseline_only = _canonical_token_tuple(
            self.baseline_only_semantic_row_digests,
            label="EvaluationScenarioDiffV1.baseline_only_semantic_row_digests",
            maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
        )
        effective_only = _canonical_token_tuple(
            self.effective_only_semantic_row_digests,
            label="EvaluationScenarioDiffV1.effective_only_semantic_row_digests",
            maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
        )
        if (
            set(shared) & set(baseline_only)
            or set(shared) & set(effective_only)
            or set(baseline_only) & set(effective_only)
        ):
            raise _fail("EvaluationScenarioDiffV1 semantic row sets must be disjoint")
        expected_relation = "different" if baseline_only or effective_only else "equivalent"
        if self.result_relation != expected_relation:
            raise _fail("EvaluationScenarioDiffV1 result relation is derived")
        if self.evidence_relation != "not_claimed" or self.causal_attribution != "not_claimed":
            raise _fail("EvaluationScenarioDiffV1 cannot claim evidence or causality")
        object.__setattr__(self, "scenario_operations", operations)
        object.__setattr__(
            self,
            "diff_digest",
            _domain_token(
                "scenario_diff_v1",
                {
                    "run_digest": self.run_digest,
                    "plan_digest": self.plan_digest,
                    "scenario_request_digest": self.scenario_request_digest,
                    "baseline_world_capture_digest": self.baseline_world_capture_digest,
                    "effective_world_capture_digest": self.effective_world_capture_digest,
                    "baseline_semantic_world_digest": self.baseline_semantic_world_digest,
                    "effective_semantic_world_digest": self.effective_semantic_world_digest,
                    "baseline_relation_snapshot_digest": self.baseline_relation_snapshot_digest,
                    "effective_relation_snapshot_digest": self.effective_relation_snapshot_digest,
                    "baseline_resolution_evidence_digest": (
                        self.baseline_resolution_evidence_digest
                    ),
                    "effective_resolution_evidence_digest": (
                        self.effective_resolution_evidence_digest
                    ),
                    "baseline_closure_target_digests": baseline_closure,
                    "effective_closure_target_digests": effective_closure,
                    "input_difference_axes": self.input_difference_axes,
                    "scenario_patch_capture": self.scenario_patch_capture,
                    "scenario_patch_application": self.scenario_patch_application,
                    "scenario_patch_digest": self.scenario_patch_digest,
                    "scenario_operation_digests": expected_operation_digests,
                    "shared_semantic_row_digests": shared,
                    "baseline_only_semantic_row_digests": baseline_only,
                    "effective_only_semantic_row_digests": effective_only,
                    "result_relation": self.result_relation,
                    "evidence_relation": self.evidence_relation,
                    "causal_attribution": self.causal_attribution,
                },
            ),
        )


def _scenario_diff_current(value: EvaluationScenarioDiffV1) -> EvaluationScenarioDiffV1:
    if type(value) is not EvaluationScenarioDiffV1:
        raise _fail("Scenario diff must be exact EvaluationScenarioDiffV1")
    current = EvaluationScenarioDiffV1(
        run_digest=value.run_digest,
        plan_digest=value.plan_digest,
        scenario_request_digest=value.scenario_request_digest,
        baseline_world_capture_digest=value.baseline_world_capture_digest,
        effective_world_capture_digest=value.effective_world_capture_digest,
        baseline_semantic_world_digest=value.baseline_semantic_world_digest,
        effective_semantic_world_digest=value.effective_semantic_world_digest,
        baseline_relation_snapshot_digest=value.baseline_relation_snapshot_digest,
        effective_relation_snapshot_digest=value.effective_relation_snapshot_digest,
        baseline_resolution_evidence_digest=value.baseline_resolution_evidence_digest,
        effective_resolution_evidence_digest=value.effective_resolution_evidence_digest,
        baseline_closure_target_digests=value.baseline_closure_target_digests,
        effective_closure_target_digests=value.effective_closure_target_digests,
        input_difference_axes=value.input_difference_axes,
        scenario_operations=value.scenario_operations,
        scenario_patch_capture=value.scenario_patch_capture,
        scenario_patch_application=value.scenario_patch_application,
        scenario_patch_digest=value.scenario_patch_digest,
        scenario_operation_digests=value.scenario_operation_digests,
        shared_semantic_row_digests=value.shared_semantic_row_digests,
        baseline_only_semantic_row_digests=value.baseline_only_semantic_row_digests,
        effective_only_semantic_row_digests=value.effective_only_semantic_row_digests,
        result_relation=value.result_relation,
        evidence_relation=value.evidence_relation,
        causal_attribution=value.causal_attribution,
    )
    if current != value:
        raise _fail("EvaluationScenarioDiffV1 is stale or noncanonical")
    return current


def _scenario_diff_to_wire(value: EvaluationScenarioDiffV1) -> dict[str, object]:
    value = _scenario_diff_current(value)
    return {
        "$type": _SCENARIO_DIFF_TYPE,
        "run_digest": value.run_digest,
        "plan_digest": value.plan_digest,
        "scenario_request_digest": value.scenario_request_digest,
        "baseline_world_capture_digest": value.baseline_world_capture_digest,
        "effective_world_capture_digest": value.effective_world_capture_digest,
        "baseline_semantic_world_digest": value.baseline_semantic_world_digest,
        "effective_semantic_world_digest": value.effective_semantic_world_digest,
        "baseline_relation_snapshot_digest": value.baseline_relation_snapshot_digest,
        "effective_relation_snapshot_digest": value.effective_relation_snapshot_digest,
        "baseline_resolution_evidence_digest": value.baseline_resolution_evidence_digest,
        "effective_resolution_evidence_digest": value.effective_resolution_evidence_digest,
        "baseline_closure_target_digests": list(value.baseline_closure_target_digests),
        "effective_closure_target_digests": list(value.effective_closure_target_digests),
        "input_difference_axes": list(value.input_difference_axes),
        "scenario_operations": (
            None
            if value.scenario_operations is None
            else [_resolved_operation_to_wire(item) for item in value.scenario_operations]
        ),
        "scenario_patch_capture": value.scenario_patch_capture,
        "scenario_patch_application": value.scenario_patch_application,
        "scenario_patch_digest": value.scenario_patch_digest,
        "scenario_operation_digests": list(value.scenario_operation_digests),
        "shared_semantic_row_digests": list(value.shared_semantic_row_digests),
        "baseline_only_semantic_row_digests": list(value.baseline_only_semantic_row_digests),
        "effective_only_semantic_row_digests": list(value.effective_only_semantic_row_digests),
        "result_relation": value.result_relation,
        "evidence_relation": value.evidence_relation,
        "causal_attribution": value.causal_attribution,
        "diff_digest": value.diff_digest,
    }


def _scenario_diff_from_wire(value: object) -> EvaluationScenarioDiffV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "run_digest",
                "plan_digest",
                "scenario_request_digest",
                "baseline_world_capture_digest",
                "effective_world_capture_digest",
                "baseline_semantic_world_digest",
                "effective_semantic_world_digest",
                "baseline_relation_snapshot_digest",
                "effective_relation_snapshot_digest",
                "baseline_resolution_evidence_digest",
                "effective_resolution_evidence_digest",
                "baseline_closure_target_digests",
                "effective_closure_target_digests",
                "input_difference_axes",
                "scenario_operations",
                "scenario_patch_capture",
                "scenario_patch_application",
                "scenario_patch_digest",
                "scenario_operation_digests",
                "shared_semantic_row_digests",
                "baseline_only_semantic_row_digests",
                "effective_only_semantic_row_digests",
                "result_relation",
                "evidence_relation",
                "causal_attribution",
                "diff_digest",
            }
        ),
        label="EvaluationScenarioDiffV1",
    )
    if row["$type"] != _SCENARIO_DIFF_TYPE:
        raise _fail("EvaluationScenarioDiffV1 type is invalid")
    raw_operations = row["scenario_operations"]
    operations = (
        None
        if raw_operations is None
        else tuple(
            _resolved_operation_from_wire(item)
            for item in _array(
                raw_operations,
                label="EvaluationScenarioDiffV1.scenario_operations",
                maximum=MAX_EVALUATION_SCENARIO_OPERATIONS_V1,
            )
        )
    )
    result = _construct(
        "EvaluationScenarioDiffV1",
        lambda: EvaluationScenarioDiffV1(
            run_digest=row["run_digest"],
            plan_digest=row["plan_digest"],
            scenario_request_digest=row["scenario_request_digest"],
            baseline_world_capture_digest=row["baseline_world_capture_digest"],
            effective_world_capture_digest=row["effective_world_capture_digest"],
            baseline_semantic_world_digest=row["baseline_semantic_world_digest"],
            effective_semantic_world_digest=row["effective_semantic_world_digest"],
            baseline_relation_snapshot_digest=row["baseline_relation_snapshot_digest"],
            effective_relation_snapshot_digest=row["effective_relation_snapshot_digest"],
            baseline_resolution_evidence_digest=row["baseline_resolution_evidence_digest"],
            effective_resolution_evidence_digest=row["effective_resolution_evidence_digest"],
            baseline_closure_target_digests=tuple(
                _array(
                    row["baseline_closure_target_digests"],
                    label="EvaluationScenarioDiffV1.baseline_closure_target_digests",
                    maximum=MAX_EVALUATION_SCENARIO_OPERATIONS_V1,
                )
            ),
            effective_closure_target_digests=tuple(
                _array(
                    row["effective_closure_target_digests"],
                    label="EvaluationScenarioDiffV1.effective_closure_target_digests",
                    maximum=MAX_EVALUATION_SCENARIO_OPERATIONS_V1,
                )
            ),
            input_difference_axes=tuple(
                _array(
                    row["input_difference_axes"],
                    label="EvaluationScenarioDiffV1.input_difference_axes",
                    maximum=4,
                )
            ),
            scenario_operations=operations,
            scenario_patch_capture=row["scenario_patch_capture"],
            scenario_patch_application=row["scenario_patch_application"],
            scenario_patch_digest=row["scenario_patch_digest"],
            scenario_operation_digests=tuple(
                _array(
                    row["scenario_operation_digests"],
                    label="EvaluationScenarioDiffV1.scenario_operation_digests",
                    maximum=MAX_EVALUATION_SCENARIO_OPERATIONS_V1,
                )
            ),
            shared_semantic_row_digests=tuple(
                _array(
                    row["shared_semantic_row_digests"],
                    label="EvaluationScenarioDiffV1.shared_semantic_row_digests",
                    maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
                )
            ),
            baseline_only_semantic_row_digests=tuple(
                _array(
                    row["baseline_only_semantic_row_digests"],
                    label="EvaluationScenarioDiffV1.baseline_only_semantic_row_digests",
                    maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
                )
            ),
            effective_only_semantic_row_digests=tuple(
                _array(
                    row["effective_only_semantic_row_digests"],
                    label="EvaluationScenarioDiffV1.effective_only_semantic_row_digests",
                    maximum=MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1,
                )
            ),
            result_relation=row["result_relation"],
            evidence_relation=row["evidence_relation"],
            causal_attribution=row["causal_attribution"],
        ),
    )
    if row["diff_digest"] != result.diff_digest:
        raise _fail("EvaluationScenarioDiffV1 diff_digest mismatch")
    return result


def evaluation_scenario_diff_v1_bytes(value: EvaluationScenarioDiffV1) -> bytes:
    """Encode a typed descriptive Scenario diff."""

    raw = _canonical_json_bytes(
        _scenario_diff_to_wire(value),
        label="EvaluationScenarioDiffV1",
    )
    if len(raw) > MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1:
        raise _fail("EvaluationScenarioDiffV1 exceeds the 4 MiB component limit")
    return raw


def evaluation_scenario_diff_v1_from_bytes(raw: bytes) -> EvaluationScenarioDiffV1:
    """Decode a Scenario diff without replaying the run."""

    row = _load_json_object(
        raw,
        label="EvaluationScenarioDiffV1",
        max_bytes=MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,
    )
    result = _scenario_diff_from_wire(row)
    if evaluation_scenario_diff_v1_bytes(result) != raw:
        raise _fail("EvaluationScenarioDiffV1 representation is not canonical")
    return result


def _semantic_row_set(side: EvaluationRunSideV1) -> set[str]:
    return {item.semantic_row_digest for item in side.canonical_result.rows}


def _assert_comparison_matches_run(
    comparison: EvaluationComparisonV1,
    run: EvaluationRunV1,
) -> None:
    if run.candidate_plan is None or run.candidate_effective is None:
        raise _fail("EvaluationComparisonV1 requires a candidate Run side")
    if (
        comparison.primary_plan_digest != run.plan.plan_digest
        or comparison.candidate_plan_digest != run.candidate_plan.plan_digest
        or comparison.primary_target_digest != run.plan.target.target_digest
        or comparison.candidate_target_digest != run.candidate_plan.target.target_digest
        or comparison.effective_world_capture_digest
        != run.replay_payload.world("effective").world_capture_digest
    ):
        raise _fail("EvaluationComparisonV1 does not match Run pins")
    primary_rows = _semantic_row_set(run.effective)
    candidate_rows = _semantic_row_set(run.candidate_effective)
    if (
        comparison.shared_semantic_row_digests != tuple(sorted(primary_rows & candidate_rows))
        or comparison.primary_only_semantic_row_digests
        != tuple(sorted(primary_rows - candidate_rows))
        or comparison.candidate_only_semantic_row_digests
        != tuple(sorted(candidate_rows - primary_rows))
    ):
        raise _fail("EvaluationComparisonV1 does not match sealed result rows")


def _assert_scenario_diff_matches_run(
    diff: EvaluationScenarioDiffV1,
    run: EvaluationRunV1,
) -> None:
    if run.plan.scenario_request_digest is None:
        raise _fail("EvaluationScenarioDiffV1 requires a Scenario-pinned Run")
    baseline_world = run.replay_payload.world("baseline")
    effective_world = run.replay_payload.world("effective")
    if (
        diff.run_digest != run.run_digest
        or diff.plan_digest != run.plan.plan_digest
        or diff.scenario_request_digest != run.plan.scenario_request_digest
        or diff.baseline_world_capture_digest != baseline_world.world_capture_digest
        or diff.effective_world_capture_digest != effective_world.world_capture_digest
        or diff.baseline_semantic_world_digest != baseline_world.semantic_world_digest
        or diff.effective_semantic_world_digest != effective_world.semantic_world_digest
        or diff.baseline_relation_snapshot_digest != baseline_world.relation_snapshot_digest
        or diff.effective_relation_snapshot_digest != effective_world.relation_snapshot_digest
        or diff.baseline_resolution_evidence_digest != baseline_world.resolution_evidence_digest
        or diff.effective_resolution_evidence_digest != effective_world.resolution_evidence_digest
        or diff.baseline_closure_target_digests != baseline_world.closure_target_digests
        or diff.effective_closure_target_digests != effective_world.closure_target_digests
    ):
        raise _fail("EvaluationScenarioDiffV1 does not match sealed Run/world pins")
    baseline_rows = _semantic_row_set(run.baseline)
    effective_rows = _semantic_row_set(run.effective)
    if (
        diff.shared_semantic_row_digests != tuple(sorted(baseline_rows & effective_rows))
        or diff.baseline_only_semantic_row_digests != tuple(sorted(baseline_rows - effective_rows))
        or diff.effective_only_semantic_row_digests != tuple(sorted(effective_rows - baseline_rows))
    ):
        raise _fail("EvaluationScenarioDiffV1 does not match sealed result rows")


def _sealed_result_payload(
    *,
    request_digest: str,
    asset_bundle_digest: str,
    run: EvaluationRunV1,
    comparison: EvaluationComparisonV1 | None,
    scenario_diff: EvaluationScenarioDiffV1 | None,
) -> dict[str, object]:
    return {
        "$type": _RESULT_TYPE,
        "request_digest": request_digest,
        "asset_bundle_digest": asset_bundle_digest,
        "run_bytes_b64u": _b64u(evaluation_run_v1_bytes(run)),
        "comparison": (
            None
            if comparison is None
            else _component_object(
                evaluation_comparison_v1_bytes(comparison),
                label="EvaluationComparisonV1",
            )
        ),
        "scenario_diff": (
            None
            if scenario_diff is None
            else _component_object(
                evaluation_scenario_diff_v1_bytes(scenario_diff),
                label="EvaluationScenarioDiffV1",
            )
        ),
    }


@dataclass(frozen=True)
class SealedEvaluationResultV1:
    """One complete neutral result artifact, not a retention/replay claim."""

    request_digest: str
    asset_bundle_digest: str
    run: EvaluationRunV1
    comparison: EvaluationComparisonV1 | None = None
    scenario_diff: EvaluationScenarioDiffV1 | None = None
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _token(self.request_digest, label="SealedEvaluationResultV1.request_digest")
        _token(
            self.asset_bundle_digest,
            label="SealedEvaluationResultV1.asset_bundle_digest",
        )
        run = _run_current(self.run)
        if self.comparison is not None and type(self.comparison) is not EvaluationComparisonV1:
            raise _fail("SealedEvaluationResultV1.comparison has wrong concrete type")
        if (
            self.scenario_diff is not None
            and type(self.scenario_diff) is not EvaluationScenarioDiffV1
        ):
            raise _fail("SealedEvaluationResultV1.scenario_diff has wrong concrete type")
        comparison = None if self.comparison is None else _comparison_current(self.comparison)
        scenario_diff = (
            None if self.scenario_diff is None else _scenario_diff_current(self.scenario_diff)
        )
        if comparison is not None and scenario_diff is not None:
            raise _fail("SealedEvaluationResultV1 capture projections are mutually exclusive")
        if comparison is not None:
            _assert_comparison_matches_run(comparison, run)
        if scenario_diff is not None:
            if run.candidate_plan is not None:
                raise _fail("Scenario diff projection cannot accompany a candidate Run")
            _assert_scenario_diff_matches_run(scenario_diff, run)
        object.__setattr__(self, "run", run)
        object.__setattr__(self, "comparison", comparison)
        object.__setattr__(self, "scenario_diff", scenario_diff)
        object.__setattr__(
            self,
            "artifact_digest",
            _domain_token(
                "sealed_evaluation_result_v1",
                _sealed_result_payload(
                    request_digest=self.request_digest,
                    asset_bundle_digest=self.asset_bundle_digest,
                    run=run,
                    comparison=comparison,
                    scenario_diff=scenario_diff,
                ),
            ),
        )


def _result_current(value: SealedEvaluationResultV1) -> SealedEvaluationResultV1:
    if type(value) is not SealedEvaluationResultV1:
        raise _fail("Result must be exact SealedEvaluationResultV1")
    current = SealedEvaluationResultV1(
        value.request_digest,
        value.asset_bundle_digest,
        value.run,
        value.comparison,
        value.scenario_diff,
    )
    if current != value:
        raise _fail("SealedEvaluationResultV1 is stale or noncanonical")
    return current


def sealed_evaluation_result_v1_bytes(value: SealedEvaluationResultV1) -> bytes:
    """Encode the exact terminal FactGraph artifact within 16 MiB."""

    value = _result_current(value)
    raw = _canonical_json_bytes(
        {
            **_sealed_result_payload(
                request_digest=value.request_digest,
                asset_bundle_digest=value.asset_bundle_digest,
                run=value.run,
                comparison=value.comparison,
                scenario_diff=value.scenario_diff,
            ),
            "artifact_digest": value.artifact_digest,
        },
        label="SealedEvaluationResultV1",
    )
    if len(raw) > MAX_SEALED_EVALUATION_RESULT_BYTES_V1:
        raise _fail("SealedEvaluationResultV1 exceeds the 16 MiB result limit")
    return raw


def sealed_evaluation_result_v1_from_bytes(raw: bytes) -> SealedEvaluationResultV1:
    """Decode one complete terminal artifact without reevaluating it."""

    row = _load_json_object(raw, label="SealedEvaluationResultV1")
    data = _exact_object(
        row,
        frozenset(
            {
                "$type",
                "request_digest",
                "asset_bundle_digest",
                "run_bytes_b64u",
                "comparison",
                "scenario_diff",
                "artifact_digest",
            }
        ),
        label="SealedEvaluationResultV1",
    )
    if data["$type"] != _RESULT_TYPE:
        raise _fail("SealedEvaluationResultV1 type is invalid")
    result = _construct(
        "SealedEvaluationResultV1",
        lambda: SealedEvaluationResultV1(
            data["request_digest"],
            data["asset_bundle_digest"],
            evaluation_run_v1_from_bytes(
                _decode_b64u(data["run_bytes_b64u"], label="run_bytes_b64u")
            ),
            None if data["comparison"] is None else _comparison_from_wire(data["comparison"]),
            None
            if data["scenario_diff"] is None
            else _scenario_diff_from_wire(data["scenario_diff"]),
        ),
    )
    if data["artifact_digest"] != result.artifact_digest:
        raise _fail("SealedEvaluationResultV1 artifact_digest mismatch")
    if sealed_evaluation_result_v1_bytes(result) != raw:
        raise _fail("SealedEvaluationResultV1 representation is not canonical")
    return result


def _relation_values(
    relation: EvaluationReplayRelationV1,
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        sorted(tuple(item.value_digest for item in fact.values) for fact in relation.facts)
    )


def _assert_provider_result_binding(
    *,
    request_world: EvaluationReplayWorldV1,
    run_world: EvaluationReplayWorldV1,
    provider: EvaluationProviderCaptureV1,
    receipts: tuple[ProviderReceiptRefV1, ...],
) -> None:
    expected_receipt = ProviderReceiptRefV1(
        provider.request.provider_digest,
        provider.request.request_digest,
        provider.materialization.materialization_digest,
        provider.materialization.receipt_ref,
        provider.materialization.receipt_digest,
    )
    if receipts != (expected_receipt,):
        raise _fail("Run replay receipt does not match the captured Provider result")
    request_relations = {item.predicate_id: item for item in request_world.relations}
    run_relations = {item.predicate_id: item for item in run_world.relations}
    if set(request_relations) != set(run_relations):
        raise _fail("Provider replacement changed the dependency predicate inventory")
    supplied = set(provider.request.supplied_predicate_ids)
    for predicate_id, relation in request_relations.items():
        if predicate_id not in supplied and run_relations[predicate_id] != relation:
            raise _fail("Provider replacement changed an undeclared dependency relation")
    expected_values: dict[str, list[tuple[str, ...]]] = {
        predicate_id: [] for predicate_id in supplied
    }
    for row in provider.materialization.rows:
        expected_values[row.predicate_id].append(tuple(item.value_digest for item in row.values))
    for predicate_id in supplied:
        if _relation_values(run_relations[predicate_id]) != tuple(
            sorted(expected_values[predicate_id])
        ):
            raise _fail("Run baseline does not contain the captured Provider materialization")


def _assert_program_result_binding(
    *,
    request_program_bytes: bytes,
    run_program_bytes: bytes,
    scenario_present: bool,
) -> None:
    request_row = _load_json_object(
        request_program_bytes,
        label="request EvaluationReplayProgramEnvelopeV1",
    )
    run_row = _load_json_object(
        run_program_bytes,
        label="run EvaluationReplayProgramEnvelopeV1",
    )
    request_program = request_row.get("compiled_program")
    run_program = run_row.get("compiled_program")
    if (
        type(request_program) is not dict
        or type(run_program) is not dict
        or "scenario_patch" not in request_program
        or "scenario_patch" not in run_program
    ):
        raise _fail("Evaluation program must expose an exact scenario_patch field")
    if request_program["scenario_patch"] is not None:
        raise _fail("Sealed request program cannot carry a resolved Scenario patch")
    if scenario_present:
        if run_program["scenario_patch"] is None:
            raise _fail("Scenario-pinned Run must retain its resolved Scenario patch")
    elif run_program["scenario_patch"] is not None:
        raise _fail("Run without Scenario cannot carry a resolved Scenario patch")

    normalized_program = dict(run_program)
    normalized_program["scenario_patch"] = None
    normalized_run = dict(run_row)
    normalized_run["compiled_program"] = normalized_program
    if normalized_run != request_row:
        raise _fail(
            "EvaluationRunV1 program differs from request beyond the resolved Scenario patch"
        )


def assert_sealed_evaluation_result_matches_request_v1(
    result: SealedEvaluationResultV1,
    request: SealedEvaluationRequestV1,
) -> None:
    """Validate a terminal artifact against its already-sealed request.

    This function performs only immutable byte/pin/result checks. It never
    calls a provider, evaluator, catalog, Store, ledger, or other live state.
    """

    if type(request) is not SealedEvaluationRequestV1:
        raise _fail("Request must be exact SealedEvaluationRequestV1")
    assert_sealed_evaluation_request_current_v1(request)
    result = _result_current(result)
    decoded = decode_sealed_evaluation_request_v1(request)
    if (
        result.request_digest != request.request_digest
        or result.asset_bundle_digest != request.asset_bundle.bundle_digest
    ):
        raise _fail("Sealed result does not match request/bundle digests")
    run = result.run
    if (
        run.plan != decoded.goal_plan
        or run.execution_profile != decoded.execution_profile
        or run.candidate_plan != decoded.candidate_plan
        or run.replay_payload.schema_digest != decoded.schema.schema_digest
        or run.replay_payload.schema_bytes != decoded.schema.schema_bytes
        or run.replay_payload.address_space_digest != decoded.asset_bundle.address_space_digest
    ):
        raise _fail("EvaluationRunV1 does not match decoded request components")
    _assert_program_result_binding(
        request_program_bytes=request.program_envelope_bytes,
        run_program_bytes=run.replay_payload.compiled_program_bytes,
        scenario_present=decoded.scenario is not None,
    )
    run_baseline = run.replay_payload.world("baseline")
    if decoded.provider_capture is None:
        if run.replay_payload.provider_receipts:
            raise _fail("Non-Provider result cannot carry Provider receipt references")
        if run_baseline != decoded.baseline_world:
            raise _fail("Run baseline does not match the sealed request baseline")
    else:
        _assert_provider_result_binding(
            request_world=decoded.baseline_world,
            run_world=run_baseline,
            provider=decoded.provider_capture,
            receipts=run.replay_payload.provider_receipts,
        )
    sides = (run.baseline, run.effective, run.candidate_effective)
    if any(
        side is not None and len(side.canonical_result.rows) > decoded.capture.row_limit
        for side in sides
    ):
        raise _fail("Run rows exceed the request capture row limit")
    if decoded.capture.explain == "not_captured":
        if run.explain_target is not None:
            raise _fail("Run emitted Explain target when capture was not requested")
    elif run.explain_target is None:
        raise _fail("Structured Explain capture requires an explicit Run target")
    if decoded.capture.comparison == "not_requested":
        if result.comparison is not None or result.scenario_diff is not None:
            raise _fail("Result emitted an unrequested comparison projection")
    elif decoded.capture.comparison == "baseline_vs_effective":
        if result.comparison is not None or result.scenario_diff is None:
            raise _fail("baseline_vs_effective requires exactly one Scenario diff")
        if result.scenario_diff.scenario_patch_capture != "captured":
            raise _fail("Scenario diff must retain the resolved Scenario patch")
    elif decoded.capture.comparison == "published_candidate":
        if result.comparison is None or result.scenario_diff is not None:
            raise _fail("published_candidate requires exactly one typed comparison")
    else:  # pragma: no cover - request DTO closes this value
        raise AssertionError("closed comparison capture is unreachable")


__all__ = [
    "MAX_EVALUATION_RESULT_ROWS_PER_SIDE_V1",
    "MAX_EVALUATION_SCENARIO_OPERATIONS_V1",
    "MAX_SEALED_EVALUATION_RESULT_BYTES_V1",
    "EvaluationComparisonV1",
    "EvaluationScenarioDiffV1",
    "SealedEvaluationResultV1",
    "assert_sealed_evaluation_result_matches_request_v1",
    "evaluation_comparison_v1_bytes",
    "evaluation_comparison_v1_from_bytes",
    "evaluation_run_v1_bytes",
    "evaluation_run_v1_from_bytes",
    "evaluation_scenario_diff_v1_bytes",
    "evaluation_scenario_diff_v1_from_bytes",
    "sealed_evaluation_result_v1_bytes",
    "sealed_evaluation_result_v1_from_bytes",
]
