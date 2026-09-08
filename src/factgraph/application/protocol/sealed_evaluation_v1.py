"""Exact request-side protocol for one detached neutral evaluation.

This module owns canonical component/request codecs and outer pin validation.
It deliberately owns no evaluator and does not decode the capability-specific
compiled-program body.  The runtime owner performs that semantic decode only
after :func:`decode_sealed_evaluation_request_v1` has accepted every outer pin.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from typing import Any

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.schema.schema_ir import (
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
)
from factgraph.core.schema.schema_ir import (
    schema_digest as compute_schema_digest,
)

from .common import ProtocolShapeError
from .evaluation_run_v1 import (
    EvaluationEnginePinV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayFactV1,
    EvaluationReplayProgramEnvelopeV1,
    EvaluationReplayRelationV1,
    EvaluationReplayWorldV1,
    evaluation_replay_program_envelope_v1_from_bytes,
)
from .goal_plan_v1 import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    ExactLocalAbsenceExpectationV1,
    ExistsExpectationV1,
    GoalPlanV1,
    GoalRowExpectationV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalValueV1,
    SetEqualsExpectationV1,
)
from .relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
)
from .scenario_v1 import ExactLocalClosureTargetV1, ScenarioSpecV1

SEALED_EVALUATION_RUNTIME_DIGEST_V1 = sha256_token(b"factgraph.sealed-evaluation-runtime.v1")

MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1 = 4 * 1024 * 1024
MAX_SEALED_EVALUATION_REQUEST_BYTES_V1 = 8 * 1024 * 1024
MAX_SEALED_EVALUATION_JSON_DEPTH_V1 = 64
MAX_GOAL_SELECTIONS_V1 = 128
MAX_GOAL_EXPECTATIONS_V1 = 128
MAX_GOAL_EXPECTATION_VALUES_V1 = 128
MAX_SET_EQUALS_ROWS_V1 = 1024
MAX_ASSET_DEPENDENCIES_V1 = 512
MAX_CAPTURE_ROWS_V1 = 4096

_SHA256_TOKEN_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ASSET_KINDS = frozenset({"rule", "policy", "function", "provider", "relation_provider"})
_EXPLAIN_CAPTURES = frozenset({"not_captured", "structured_display"})
_COMPARISON_CAPTURES = frozenset({"not_requested", "baseline_vs_effective", "published_candidate"})


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
    if _json_depth(value) > MAX_SEALED_EVALUATION_JSON_DEPTH_V1:
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


def _dump_component(value: object, *, label: str) -> bytes:
    raw = _canonical_json_bytes(value, label=label)
    if not raw or len(raw) > MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1:
        raise _fail(f"{label} exceeds the component byte limit")
    return raw


def _load_json_object(
    raw: object,
    *,
    label: str,
    max_bytes: int = MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1,
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


def _exact_object(
    value: object,
    keys: frozenset[str],
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or frozenset(value) != keys:
        raise _fail(f"{label} has unknown or missing fields")
    return value


def _array(value: object, *, label: str) -> list[object]:
    if type(value) is not list:
        raise _fail(f"{label} must be a JSON array")
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


def _exact_int(value: object, *, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _fail(f"{label} must be an exact integer in {minimum}..{maximum}")
    return value


def _domain_token(domain: str, payload: object) -> str:
    return "sha256:" + sha256_hex(
        _canonical_json_bytes(
            {"format": domain, "payload": payload},
            label=f"{domain} digest payload",
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
    if not raw or len(raw) > MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1 or _b64u(raw) != text:
        raise _fail(f"{label} must be bounded unpadded canonical base64url")
    return raw


def _construct(label: str, factory: Any) -> Any:
    try:
        return factory()
    except ProtocolShapeError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise _fail(f"{label} is malformed") from exc


def _goal_value_to_wire(value: GoalValueV1) -> dict[str, object]:
    if type(value) is not GoalValueV1:
        raise _fail("Goal value must be exact GoalValueV1")
    current = _construct("GoalValueV1", lambda: GoalValueV1(value.tag, value.value))
    if current.value_digest != value.value_digest:
        raise _fail("GoalValueV1 value_digest is stale")
    return {"tag": current.tag, "value": current.value, "value_digest": current.value_digest}


def _goal_value_from_wire(value: object) -> GoalValueV1:
    row = _exact_object(
        value,
        frozenset({"tag", "value", "value_digest"}),
        label="GoalValueV1",
    )
    result = _construct(
        "GoalValueV1",
        lambda: GoalValueV1(row["tag"], row["value"]),
    )
    if row["value_digest"] != result.value_digest:
        raise _fail("GoalValueV1 value_digest mismatch")
    return result


def _goal_target_to_wire(value: GoalTargetRefV1) -> dict[str, object]:
    if type(value) is not GoalTargetRefV1:
        raise _fail("Goal target must be exact GoalTargetRefV1")
    current = _construct(
        "GoalTargetRefV1",
        lambda: GoalTargetRefV1(
            value.kind,
            value.target_id,
            value.target_version,
            value.target_digest,
        ),
    )
    return {
        "kind": current.kind,
        "target_id": current.target_id,
        "target_version": current.target_version,
        "target_digest": current.target_digest,
    }


def _goal_target_from_wire(value: object) -> GoalTargetRefV1:
    row = _exact_object(
        value,
        frozenset({"kind", "target_id", "target_version", "target_digest"}),
        label="GoalTargetRefV1",
    )
    return _construct(
        "GoalTargetRefV1",
        lambda: GoalTargetRefV1(
            row["kind"],
            row["target_id"],
            row["target_version"],
            row["target_digest"],
        ),
    )


def _goal_row_to_wire(value: GoalRowExpectationV1) -> dict[str, object]:
    if type(value) is not GoalRowExpectationV1:
        raise _fail("Goal expectation row must be exact GoalRowExpectationV1")
    if type(value.values) is not tuple:
        raise _fail("GoalRowExpectationV1.values must be exact tuple")
    current = _construct(
        "GoalRowExpectationV1",
        lambda: GoalRowExpectationV1(
            tuple(
                (
                    _string(alias, label="GoalRowExpectationV1.alias"),
                    _construct(
                        "GoalValueV1",
                        lambda item=item: GoalValueV1(item.tag, item.value),
                    ),
                )
                for alias, item in value.values
                if type(item) is GoalValueV1
            )
        ),
    )
    if len(current.values) != len(value.values) or current.row_digest != value.row_digest:
        raise _fail("GoalRowExpectationV1 is stale or contains a wrong concrete value")
    if current.values != value.values:
        raise _fail("GoalRowExpectationV1 values are not canonical")
    if len(current.values) > MAX_GOAL_EXPECTATION_VALUES_V1:
        raise _fail("Goal expectation row exceeds the value limit")
    return {
        "values": [
            {"alias": alias, "value": _goal_value_to_wire(item)} for alias, item in current.values
        ],
        "row_digest": current.row_digest,
    }


def _goal_row_from_wire(value: object) -> GoalRowExpectationV1:
    row = _exact_object(
        value,
        frozenset({"values", "row_digest"}),
        label="GoalRowExpectationV1",
    )
    cells = _array(row["values"], label="GoalRowExpectationV1.values")
    if not cells or len(cells) > MAX_GOAL_EXPECTATION_VALUES_V1:
        raise _fail("GoalRowExpectationV1.values is empty or exceeds its limit")
    values: list[tuple[str, GoalValueV1]] = []
    for index, raw in enumerate(cells):
        cell = _exact_object(
            raw,
            frozenset({"alias", "value"}),
            label=f"GoalRowExpectationV1.values[{index}]",
        )
        values.append(
            (
                _string(cell["alias"], label=f"GoalRowExpectationV1.values[{index}].alias"),
                _goal_value_from_wire(cell["value"]),
            )
        )
    result = _construct(
        "GoalRowExpectationV1",
        lambda: GoalRowExpectationV1(tuple(values)),
    )
    if row["row_digest"] != result.row_digest:
        raise _fail("GoalRowExpectationV1 row_digest mismatch")
    return result


def _closure_target_to_wire(value: ExactLocalClosureTargetV1) -> dict[str, object]:
    from .sealed_evaluation_scenario_v1 import exact_local_closure_target_v1_to_wire

    return exact_local_closure_target_v1_to_wire(value)


def _closure_target_from_wire(value: object) -> ExactLocalClosureTargetV1:
    from .sealed_evaluation_scenario_v1 import exact_local_closure_target_v1_from_wire

    return exact_local_closure_target_v1_from_wire(value)


def _goal_expectation_to_wire(value: object) -> dict[str, object]:
    if type(value) is ContainsRowExpectationV1:
        current = _construct(
            "ContainsRowExpectationV1",
            lambda: ContainsRowExpectationV1(
                value.expectation_id,
                _goal_row_from_wire(_goal_row_to_wire(value.row)),
            ),
        )
        if current.expectation_digest != value.expectation_digest or value.kind != current.kind:
            raise _fail("ContainsRowExpectationV1 is stale")
        return {
            "kind": current.kind,
            "expectation_id": current.expectation_id,
            "row": _goal_row_to_wire(current.row),
            "expectation_digest": current.expectation_digest,
        }
    if type(value) is ExactLocalAbsenceExpectationV1:
        current = _construct(
            "ExactLocalAbsenceExpectationV1",
            lambda: ExactLocalAbsenceExpectationV1(
                value.expectation_id,
                _closure_target_from_wire(_closure_target_to_wire(value.closure_target)),
            ),
        )
        if current.expectation_digest != value.expectation_digest or value.kind != current.kind:
            raise _fail("ExactLocalAbsenceExpectationV1 is stale")
        return {
            "kind": current.kind,
            "expectation_id": current.expectation_id,
            "closure_target": _closure_target_to_wire(current.closure_target),
            "expectation_digest": current.expectation_digest,
        }
    if type(value) is ExistsExpectationV1:
        current = _construct(
            "ExistsExpectationV1",
            lambda: ExistsExpectationV1(value.expectation_id, value.expected),
        )
        if current.expectation_digest != value.expectation_digest or value.kind != current.kind:
            raise _fail("ExistsExpectationV1 is stale")
        return {
            "kind": current.kind,
            "expectation_id": current.expectation_id,
            "expected": current.expected,
            "expectation_digest": current.expectation_digest,
        }
    if type(value) is CountEqExpectationV1:
        current = _construct(
            "CountEqExpectationV1",
            lambda: CountEqExpectationV1(value.expectation_id, value.expected_count),
        )
        if current.expectation_digest != value.expectation_digest or value.kind != current.kind:
            raise _fail("CountEqExpectationV1 is stale")
        return {
            "kind": current.kind,
            "expectation_id": current.expectation_id,
            "expected_count": current.expected_count,
            "expectation_digest": current.expectation_digest,
        }
    if type(value) is SetEqualsExpectationV1:
        if type(value.rows) is not tuple:
            raise _fail("SetEqualsExpectationV1.rows must be exact tuple")
        current = _construct(
            "SetEqualsExpectationV1",
            lambda: SetEqualsExpectationV1(
                value.expectation_id,
                tuple(_goal_row_from_wire(_goal_row_to_wire(item)) for item in value.rows),
            ),
        )
        if (
            current.expectation_digest != value.expectation_digest
            or value.kind != current.kind
            or current.rows != value.rows
        ):
            raise _fail("SetEqualsExpectationV1 is stale or noncanonical")
        if len(current.rows) > MAX_SET_EQUALS_ROWS_V1:
            raise _fail("SetEqualsExpectationV1 exceeds the row limit")
        return {
            "kind": current.kind,
            "expectation_id": current.expectation_id,
            "rows": [_goal_row_to_wire(item) for item in current.rows],
            "expectation_digest": current.expectation_digest,
        }
    raise _fail("GoalPlanV1 contains an unsupported expectation concrete type")


def _goal_expectation_from_wire(value: object) -> object:
    if type(value) is not dict:
        raise _fail("Goal expectation must be an exact JSON object")
    kind = value.get("kind")
    if kind == "contains_row":
        row = _exact_object(
            value,
            frozenset({"kind", "expectation_id", "row", "expectation_digest"}),
            label="ContainsRowExpectationV1",
        )
        result = _construct(
            "ContainsRowExpectationV1",
            lambda: ContainsRowExpectationV1(
                row["expectation_id"],
                _goal_row_from_wire(row["row"]),
            ),
        )
    elif kind == "exact_local_absence":
        row = _exact_object(
            value,
            frozenset({"kind", "expectation_id", "closure_target", "expectation_digest"}),
            label="ExactLocalAbsenceExpectationV1",
        )
        result = _construct(
            "ExactLocalAbsenceExpectationV1",
            lambda: ExactLocalAbsenceExpectationV1(
                row["expectation_id"],
                _closure_target_from_wire(row["closure_target"]),
            ),
        )
    elif kind == "exists":
        row = _exact_object(
            value,
            frozenset({"kind", "expectation_id", "expected", "expectation_digest"}),
            label="ExistsExpectationV1",
        )
        result = _construct(
            "ExistsExpectationV1",
            lambda: ExistsExpectationV1(row["expectation_id"], row["expected"]),
        )
    elif kind == "count_eq":
        row = _exact_object(
            value,
            frozenset({"kind", "expectation_id", "expected_count", "expectation_digest"}),
            label="CountEqExpectationV1",
        )
        result = _construct(
            "CountEqExpectationV1",
            lambda: CountEqExpectationV1(
                row["expectation_id"],
                row["expected_count"],
            ),
        )
    elif kind == "set_equals":
        row = _exact_object(
            value,
            frozenset({"kind", "expectation_id", "rows", "expectation_digest"}),
            label="SetEqualsExpectationV1",
        )
        rows = _array(row["rows"], label="SetEqualsExpectationV1.rows")
        if len(rows) > MAX_SET_EQUALS_ROWS_V1:
            raise _fail("SetEqualsExpectationV1 exceeds the row limit")
        result = _construct(
            "SetEqualsExpectationV1",
            lambda: SetEqualsExpectationV1(
                row["expectation_id"],
                tuple(_goal_row_from_wire(item) for item in rows),
            ),
        )
    else:
        raise _fail("Goal expectation kind is unsupported")
    if row["expectation_digest"] != result.expectation_digest:
        raise _fail("Goal expectation digest mismatch")
    return result


def _assert_goal_plan_bounds(plan: GoalPlanV1) -> None:
    if not 1 <= len(plan.selections) <= MAX_GOAL_SELECTIONS_V1:
        raise _fail("GoalPlanV1 selections exceed the closed limit")
    if len(plan.expectations) > MAX_GOAL_EXPECTATIONS_V1:
        raise _fail("GoalPlanV1 expectations exceed the closed limit")
    for expectation in plan.expectations:
        if type(expectation) is ContainsRowExpectationV1:
            _goal_row_to_wire(expectation.row)
        elif type(expectation) is SetEqualsExpectationV1:
            if len(expectation.rows) > MAX_SET_EQUALS_ROWS_V1:
                raise _fail("SetEqualsExpectationV1 exceeds the row limit")
            for row in expectation.rows:
                _goal_row_to_wire(row)


def _current_goal_plan(plan: GoalPlanV1) -> GoalPlanV1:
    if type(plan) is not GoalPlanV1 or type(plan.selections) is not tuple:
        raise _fail("Goal plan must be exact GoalPlanV1")
    if type(plan.expectations) is not tuple:
        raise _fail("GoalPlanV1.expectations must be exact tuple")
    selections: list[GoalSelectionV1] = []
    for item in plan.selections:
        if type(item) is not GoalSelectionV1:
            raise _fail("GoalPlanV1 selection has wrong concrete type")
        selections.append(
            _construct(
                "GoalSelectionV1",
                lambda item=item: GoalSelectionV1(item.alias, item.value_tag),
            )
        )
    expectations = tuple(
        _goal_expectation_from_wire(_goal_expectation_to_wire(item)) for item in plan.expectations
    )
    current = _construct(
        "GoalPlanV1",
        lambda: GoalPlanV1(
            target=_goal_target_from_wire(_goal_target_to_wire(plan.target)),
            query_digest=plan.query_digest,
            result_mode=plan.result_mode,
            selections=tuple(selections),
            candidate_target=(
                None
                if plan.candidate_target is None
                else _goal_target_from_wire(_goal_target_to_wire(plan.candidate_target))
            ),
            candidate_query_digest=plan.candidate_query_digest,
            scenario_request_digest=plan.scenario_request_digest,
            evidence_scope_digest=plan.evidence_scope_digest,
            execution_profile_digest=plan.execution_profile_digest,
            expectations=expectations,
        ),
    )
    if current.plan_digest != plan.plan_digest:
        raise _fail("GoalPlanV1 plan_digest is stale")
    if current.selections != plan.selections or current.expectations != plan.expectations:
        raise _fail("GoalPlanV1 collection representation is not canonical")
    _assert_goal_plan_bounds(current)
    return current


def _goal_plan_to_wire(plan: GoalPlanV1) -> dict[str, object]:
    plan = _current_goal_plan(plan)
    return {
        "$type": "FactGraphGoalPlanV1",
        "target": _goal_target_to_wire(plan.target),
        "query_digest": plan.query_digest,
        "result_mode": plan.result_mode,
        "selections": [
            {"alias": item.alias, "value_tag": item.value_tag} for item in plan.selections
        ],
        "candidate_target": (
            None if plan.candidate_target is None else _goal_target_to_wire(plan.candidate_target)
        ),
        "candidate_query_digest": plan.candidate_query_digest,
        "scenario_request_digest": plan.scenario_request_digest,
        "evidence_scope_digest": plan.evidence_scope_digest,
        "execution_profile_digest": plan.execution_profile_digest,
        "expectations": [_goal_expectation_to_wire(item) for item in plan.expectations],
        "plan_digest": plan.plan_digest,
    }


def _goal_plan_from_wire(value: object) -> GoalPlanV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "target",
                "query_digest",
                "result_mode",
                "selections",
                "candidate_target",
                "candidate_query_digest",
                "scenario_request_digest",
                "evidence_scope_digest",
                "execution_profile_digest",
                "expectations",
                "plan_digest",
            }
        ),
        label="GoalPlanV1",
    )
    if row["$type"] != "FactGraphGoalPlanV1":
        raise _fail("GoalPlanV1 type is invalid")
    selection_rows = _array(row["selections"], label="GoalPlanV1.selections")
    expectation_rows = _array(row["expectations"], label="GoalPlanV1.expectations")
    if not 1 <= len(selection_rows) <= MAX_GOAL_SELECTIONS_V1:
        raise _fail("GoalPlanV1 selections exceed the closed limit")
    if len(expectation_rows) > MAX_GOAL_EXPECTATIONS_V1:
        raise _fail("GoalPlanV1 expectations exceed the closed limit")
    selections: list[GoalSelectionV1] = []
    for index, raw in enumerate(selection_rows):
        selection = _exact_object(
            raw,
            frozenset({"alias", "value_tag"}),
            label=f"GoalPlanV1.selections[{index}]",
        )
        selections.append(
            _construct(
                "GoalSelectionV1",
                lambda selection=selection: GoalSelectionV1(
                    selection["alias"],
                    selection["value_tag"],
                ),
            )
        )
    result = _construct(
        "GoalPlanV1",
        lambda: GoalPlanV1(
            target=_goal_target_from_wire(row["target"]),
            query_digest=row["query_digest"],
            result_mode=row["result_mode"],
            selections=tuple(selections),
            candidate_target=(
                None
                if row["candidate_target"] is None
                else _goal_target_from_wire(row["candidate_target"])
            ),
            candidate_query_digest=row["candidate_query_digest"],
            scenario_request_digest=row["scenario_request_digest"],
            evidence_scope_digest=row["evidence_scope_digest"],
            execution_profile_digest=row["execution_profile_digest"],
            expectations=tuple(_goal_expectation_from_wire(item) for item in expectation_rows),
        ),
    )
    _assert_goal_plan_bounds(result)
    if row["plan_digest"] != result.plan_digest:
        raise _fail("GoalPlanV1 plan_digest mismatch")
    return result


def goal_plan_v1_bytes(plan: GoalPlanV1) -> bytes:
    """Encode one exact current GoalPlan component."""

    return _dump_component(_goal_plan_to_wire(plan), label="GoalPlanV1")


def goal_plan_v1_from_bytes(raw: bytes) -> GoalPlanV1:
    """Decode one exact current GoalPlan component."""

    row = _load_json_object(raw, label="GoalPlanV1")
    result = _goal_plan_from_wire(row)
    if goal_plan_v1_bytes(result) != raw:
        raise _fail("GoalPlanV1 set/order representation is not canonical")
    return result


def _engine_pin_to_wire(pin: EvaluationEnginePinV1) -> dict[str, object]:
    if type(pin) is not EvaluationEnginePinV1:
        raise _fail("Engine pin must be exact EvaluationEnginePinV1")
    current = _construct(
        "EvaluationEnginePinV1",
        lambda: EvaluationEnginePinV1(
            pin.engine,
            pin.engine_version,
            pin.adapter_version,
        ),
    )
    if current.pin_digest != pin.pin_digest:
        raise _fail("EvaluationEnginePinV1 pin_digest is stale")
    return {
        "engine": current.engine,
        "engine_version": current.engine_version,
        "adapter_version": current.adapter_version,
        "pin_digest": current.pin_digest,
    }


def _engine_pin_from_wire(value: object) -> EvaluationEnginePinV1:
    row = _exact_object(
        value,
        frozenset({"engine", "engine_version", "adapter_version", "pin_digest"}),
        label="EvaluationEnginePinV1",
    )
    result = _construct(
        "EvaluationEnginePinV1",
        lambda: EvaluationEnginePinV1(
            row["engine"],
            row["engine_version"],
            row["adapter_version"],
        ),
    )
    if row["pin_digest"] != result.pin_digest:
        raise _fail("EvaluationEnginePinV1 pin_digest mismatch")
    return result


def _execution_profile_to_wire(
    profile: EvaluationExecutionProfileV1,
) -> dict[str, object]:
    if type(profile) is not EvaluationExecutionProfileV1 or type(profile.engines) is not tuple:
        raise _fail("Execution profile must be exact EvaluationExecutionProfileV1")
    current = _construct(
        "EvaluationExecutionProfileV1",
        lambda: EvaluationExecutionProfileV1(
            profile.kind,
            profile.compiler_digest,
            profile.config_digest,
            tuple(_engine_pin_from_wire(_engine_pin_to_wire(item)) for item in profile.engines),
        ),
    )
    if current.profile_digest != profile.profile_digest or current.engines != profile.engines:
        raise _fail("EvaluationExecutionProfileV1 is stale or noncanonical")
    return {
        "$type": "FactGraphEvaluationExecutionProfileV1",
        "kind": current.kind,
        "compiler_digest": current.compiler_digest,
        "config_digest": current.config_digest,
        "engines": [_engine_pin_to_wire(item) for item in current.engines],
        "profile_digest": current.profile_digest,
    }


def _execution_profile_from_wire(value: object) -> EvaluationExecutionProfileV1:
    row = _exact_object(
        value,
        frozenset(
            {"$type", "kind", "compiler_digest", "config_digest", "engines", "profile_digest"}
        ),
        label="EvaluationExecutionProfileV1",
    )
    if row["$type"] != "FactGraphEvaluationExecutionProfileV1":
        raise _fail("EvaluationExecutionProfileV1 type is invalid")
    engine_rows = _array(row["engines"], label="EvaluationExecutionProfileV1.engines")
    if not 1 <= len(engine_rows) <= 3:
        raise _fail("EvaluationExecutionProfileV1 engine inventory is outside its limit")
    result = _construct(
        "EvaluationExecutionProfileV1",
        lambda: EvaluationExecutionProfileV1(
            row["kind"],
            row["compiler_digest"],
            row["config_digest"],
            tuple(_engine_pin_from_wire(item) for item in engine_rows),
        ),
    )
    if row["profile_digest"] != result.profile_digest:
        raise _fail("EvaluationExecutionProfileV1 profile_digest mismatch")
    return result


def evaluation_execution_profile_v1_bytes(
    profile: EvaluationExecutionProfileV1,
) -> bytes:
    """Encode one exact current execution-profile component."""

    return _dump_component(
        _execution_profile_to_wire(profile),
        label="EvaluationExecutionProfileV1",
    )


def evaluation_execution_profile_v1_from_bytes(
    raw: bytes,
) -> EvaluationExecutionProfileV1:
    """Decode one exact current execution-profile component."""

    row = _load_json_object(raw, label="EvaluationExecutionProfileV1")
    result = _execution_profile_from_wire(row)
    if evaluation_execution_profile_v1_bytes(result) != raw:
        raise _fail("EvaluationExecutionProfileV1 representation is not canonical")
    return result


def _replay_fact_to_wire(fact: EvaluationReplayFactV1) -> dict[str, object]:
    if type(fact) is not EvaluationReplayFactV1 or type(fact.values) is not tuple:
        raise _fail("Replay fact must be exact EvaluationReplayFactV1")
    current = _construct(
        "EvaluationReplayFactV1",
        lambda: EvaluationReplayFactV1(
            fact.witness_ref,
            tuple(_goal_value_from_wire(_goal_value_to_wire(item)) for item in fact.values),
        ),
    )
    if current.fact_digest != fact.fact_digest or current.values != fact.values:
        raise _fail("EvaluationReplayFactV1 is stale or noncanonical")
    return {
        "witness_ref": current.witness_ref,
        "values": [_goal_value_to_wire(item) for item in current.values],
        "fact_digest": current.fact_digest,
    }


def _replay_fact_from_wire(value: object) -> EvaluationReplayFactV1:
    row = _exact_object(
        value,
        frozenset({"witness_ref", "values", "fact_digest"}),
        label="EvaluationReplayFactV1",
    )
    values = _array(row["values"], label="EvaluationReplayFactV1.values")
    result = _construct(
        "EvaluationReplayFactV1",
        lambda: EvaluationReplayFactV1(
            row["witness_ref"],
            tuple(_goal_value_from_wire(item) for item in values),
        ),
    )
    if row["fact_digest"] != result.fact_digest:
        raise _fail("EvaluationReplayFactV1 fact_digest mismatch")
    return result


def _replay_relation_to_wire(
    relation: EvaluationReplayRelationV1,
) -> dict[str, object]:
    if (
        type(relation) is not EvaluationReplayRelationV1
        or type(relation.value_tags) is not tuple
        or type(relation.facts) is not tuple
    ):
        raise _fail("Replay relation must be exact EvaluationReplayRelationV1")
    current = _construct(
        "EvaluationReplayRelationV1",
        lambda: EvaluationReplayRelationV1(
            relation.predicate_id,
            tuple(relation.value_tags),
            tuple(_replay_fact_from_wire(_replay_fact_to_wire(item)) for item in relation.facts),
        ),
    )
    if current.relation_digest != relation.relation_digest or current.facts != relation.facts:
        raise _fail("EvaluationReplayRelationV1 is stale or noncanonical")
    return {
        "predicate_id": current.predicate_id,
        "value_tags": list(current.value_tags),
        "facts": [_replay_fact_to_wire(item) for item in current.facts],
        "relation_digest": current.relation_digest,
    }


def _replay_relation_from_wire(value: object) -> EvaluationReplayRelationV1:
    row = _exact_object(
        value,
        frozenset({"predicate_id", "value_tags", "facts", "relation_digest"}),
        label="EvaluationReplayRelationV1",
    )
    tags = _array(row["value_tags"], label="EvaluationReplayRelationV1.value_tags")
    facts = _array(row["facts"], label="EvaluationReplayRelationV1.facts")
    result = _construct(
        "EvaluationReplayRelationV1",
        lambda: EvaluationReplayRelationV1(
            row["predicate_id"],
            tuple(tags),
            tuple(_replay_fact_from_wire(item) for item in facts),
        ),
    )
    if row["relation_digest"] != result.relation_digest:
        raise _fail("EvaluationReplayRelationV1 relation_digest mismatch")
    return result


def _replay_world_to_wire(world: EvaluationReplayWorldV1) -> dict[str, object]:
    if (
        type(world) is not EvaluationReplayWorldV1
        or type(world.closure_target_digests) is not tuple
        or type(world.relations) is not tuple
    ):
        raise _fail("Replay world must be exact EvaluationReplayWorldV1")
    current = _construct(
        "EvaluationReplayWorldV1",
        lambda: EvaluationReplayWorldV1(
            world.side,
            world.semantic_world_digest,
            world.resolution_evidence_digest,
            tuple(world.closure_target_digests),
            tuple(
                _replay_relation_from_wire(_replay_relation_to_wire(item))
                for item in world.relations
            ),
        ),
    )
    if (
        current.relation_snapshot_digest != world.relation_snapshot_digest
        or current.world_capture_digest != world.world_capture_digest
        or current.closure_target_digests != world.closure_target_digests
        or current.relations != world.relations
    ):
        raise _fail("EvaluationReplayWorldV1 is stale or noncanonical")
    return {
        "$type": "FactGraphEvaluationReplayWorldV1",
        "side": current.side,
        "semantic_world_digest": current.semantic_world_digest,
        "resolution_evidence_digest": current.resolution_evidence_digest,
        "closure_target_digests": list(current.closure_target_digests),
        "relations": [_replay_relation_to_wire(item) for item in current.relations],
        "relation_snapshot_digest": current.relation_snapshot_digest,
        "world_capture_digest": current.world_capture_digest,
    }


def _replay_world_from_wire(value: object) -> EvaluationReplayWorldV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "side",
                "semantic_world_digest",
                "resolution_evidence_digest",
                "closure_target_digests",
                "relations",
                "relation_snapshot_digest",
                "world_capture_digest",
            }
        ),
        label="EvaluationReplayWorldV1",
    )
    if row["$type"] != "FactGraphEvaluationReplayWorldV1":
        raise _fail("EvaluationReplayWorldV1 type is invalid")
    closures = _array(
        row["closure_target_digests"],
        label="EvaluationReplayWorldV1.closure_target_digests",
    )
    relations = _array(row["relations"], label="EvaluationReplayWorldV1.relations")
    result = _construct(
        "EvaluationReplayWorldV1",
        lambda: EvaluationReplayWorldV1(
            row["side"],
            row["semantic_world_digest"],
            row["resolution_evidence_digest"],
            tuple(closures),
            tuple(_replay_relation_from_wire(item) for item in relations),
        ),
    )
    if (
        row["relation_snapshot_digest"] != result.relation_snapshot_digest
        or row["world_capture_digest"] != result.world_capture_digest
    ):
        raise _fail("EvaluationReplayWorldV1 derived digest mismatch")
    return result


def evaluation_replay_world_v1_bytes(world: EvaluationReplayWorldV1) -> bytes:
    """Encode one exact baseline/effective replay-world component."""

    return _dump_component(_replay_world_to_wire(world), label="EvaluationReplayWorldV1")


def evaluation_replay_world_v1_from_bytes(raw: bytes) -> EvaluationReplayWorldV1:
    """Decode one exact baseline/effective replay-world component."""

    row = _load_json_object(raw, label="EvaluationReplayWorldV1")
    result = _replay_world_from_wire(row)
    if evaluation_replay_world_v1_bytes(result) != raw:
        raise _fail("EvaluationReplayWorldV1 set/order representation is not canonical")
    return result


@dataclass(frozen=True)
class EvaluationWorldInputPinsV1:
    """Immutable resolver inputs for the captured pre-provider baseline."""

    base_view_digest: str
    admissibility_digest: str
    pins_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _token(
            self.base_view_digest,
            label="EvaluationWorldInputPinsV1.base_view_digest",
        )
        _token(
            self.admissibility_digest,
            label="EvaluationWorldInputPinsV1.admissibility_digest",
        )
        object.__setattr__(
            self,
            "pins_digest",
            _domain_token(
                "sealed_evaluation_world_input_pins_v1",
                {
                    "base_view_digest": self.base_view_digest,
                    "admissibility_digest": self.admissibility_digest,
                },
            ),
        )


def _current_world_input_pins(
    pins: EvaluationWorldInputPinsV1,
) -> EvaluationWorldInputPinsV1:
    if type(pins) is not EvaluationWorldInputPinsV1:
        raise _fail("World input pins must be exact EvaluationWorldInputPinsV1")
    current = _construct(
        "EvaluationWorldInputPinsV1",
        lambda: EvaluationWorldInputPinsV1(
            pins.base_view_digest,
            pins.admissibility_digest,
        ),
    )
    if current.pins_digest != pins.pins_digest:
        raise _fail("EvaluationWorldInputPinsV1 pins_digest is stale")
    return current


def _world_input_pins_to_wire(
    pins: EvaluationWorldInputPinsV1,
) -> dict[str, object]:
    pins = _current_world_input_pins(pins)
    return {
        "base_view_digest": pins.base_view_digest,
        "admissibility_digest": pins.admissibility_digest,
        "pins_digest": pins.pins_digest,
    }


def _world_input_pins_from_wire(value: object) -> EvaluationWorldInputPinsV1:
    row = _exact_object(
        value,
        frozenset({"base_view_digest", "admissibility_digest", "pins_digest"}),
        label="EvaluationWorldInputPinsV1",
    )
    result = _construct(
        "EvaluationWorldInputPinsV1",
        lambda: EvaluationWorldInputPinsV1(
            row["base_view_digest"],
            row["admissibility_digest"],
        ),
    )
    if row["pins_digest"] != result.pins_digest:
        raise _fail("EvaluationWorldInputPinsV1 pins_digest mismatch")
    return result


@dataclass(frozen=True)
class EvaluationAssetPinV1:
    """One neutral immutable asset identity used by the sealed evaluation."""

    kind: str
    asset_id: str
    version: str
    artifact_digest: str
    pin_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind not in _ASSET_KINDS:
            raise _fail("EvaluationAssetPinV1.kind is outside the closed asset kinds")
        _string(self.asset_id, label="EvaluationAssetPinV1.asset_id")
        _string(self.version, label="EvaluationAssetPinV1.version")
        _token(self.artifact_digest, label="EvaluationAssetPinV1.artifact_digest")
        object.__setattr__(
            self,
            "pin_digest",
            _domain_token(
                "evaluation_asset_pin_v1",
                {
                    "kind": self.kind,
                    "asset_id": self.asset_id,
                    "version": self.version,
                    "artifact_digest": self.artifact_digest,
                },
            ),
        )


def _current_asset_pin(pin: EvaluationAssetPinV1) -> EvaluationAssetPinV1:
    if type(pin) is not EvaluationAssetPinV1:
        raise _fail("Asset pin must be exact EvaluationAssetPinV1")
    current = _construct(
        "EvaluationAssetPinV1",
        lambda: EvaluationAssetPinV1(
            pin.kind,
            pin.asset_id,
            pin.version,
            pin.artifact_digest,
        ),
    )
    if current.pin_digest != pin.pin_digest:
        raise _fail("EvaluationAssetPinV1 pin_digest is stale")
    return current


def _asset_pin_to_wire(pin: EvaluationAssetPinV1) -> dict[str, object]:
    pin = _current_asset_pin(pin)
    return {
        "kind": pin.kind,
        "asset_id": pin.asset_id,
        "version": pin.version,
        "artifact_digest": pin.artifact_digest,
        "pin_digest": pin.pin_digest,
    }


def _asset_pin_from_wire(value: object) -> EvaluationAssetPinV1:
    row = _exact_object(
        value,
        frozenset({"kind", "asset_id", "version", "artifact_digest", "pin_digest"}),
        label="EvaluationAssetPinV1",
    )
    result = _construct(
        "EvaluationAssetPinV1",
        lambda: EvaluationAssetPinV1(
            row["kind"],
            row["asset_id"],
            row["version"],
            row["artifact_digest"],
        ),
    )
    if row["pin_digest"] != result.pin_digest:
        raise _fail("EvaluationAssetPinV1 pin_digest mismatch")
    return result


@dataclass(frozen=True)
class EvaluationAssetBundleV1:
    """Closed integrity pins for one neutral evaluation request."""

    primary_target: EvaluationAssetPinV1
    candidate_target: EvaluationAssetPinV1 | None
    dependencies: tuple[EvaluationAssetPinV1, ...]
    query_digest: str
    schema_digest: str
    address_space_digest: str
    compiler_digest: str
    execution_profile_digest: str
    runtime_digest: str
    bundle_digest: str = field(init=False)

    def __post_init__(self) -> None:
        primary_target = _current_asset_pin(self.primary_target)
        candidate_target = (
            None if self.candidate_target is None else _current_asset_pin(self.candidate_target)
        )
        if candidate_target is not None:
            if candidate_target.kind not in {"rule", "policy"}:
                raise _fail("EvaluationAssetBundleV1 candidate must be Rule or Policy")
            if candidate_target.pin_digest == primary_target.pin_digest:
                raise _fail("EvaluationAssetBundleV1 candidate must be distinct")
        if (
            type(self.dependencies) is not tuple
            or len(self.dependencies) > MAX_ASSET_DEPENDENCIES_V1
            or any(type(item) is not EvaluationAssetPinV1 for item in self.dependencies)
        ):
            raise _fail("EvaluationAssetBundleV1.dependencies is malformed or over limit")
        dependencies = tuple(_current_asset_pin(item) for item in self.dependencies)
        canonical = tuple(sorted(dependencies, key=lambda item: item.pin_digest))
        if len({item.pin_digest for item in canonical}) != len(canonical):
            raise _fail("EvaluationAssetBundleV1 dependency pins must be unique")
        target_pins = {primary_target.pin_digest}
        if candidate_target is not None:
            target_pins.add(candidate_target.pin_digest)
        if any(item.pin_digest in target_pins for item in canonical):
            raise _fail("EvaluationAssetBundleV1 dependency cannot repeat a target pin")
        for name in (
            "query_digest",
            "schema_digest",
            "address_space_digest",
            "compiler_digest",
            "execution_profile_digest",
            "runtime_digest",
        ):
            _token(getattr(self, name), label=f"EvaluationAssetBundleV1.{name}")
        if self.runtime_digest != SEALED_EVALUATION_RUNTIME_DIGEST_V1:
            raise _fail("EvaluationAssetBundleV1 runtime capability pin is not current")
        object.__setattr__(self, "primary_target", primary_target)
        object.__setattr__(self, "candidate_target", candidate_target)
        object.__setattr__(self, "dependencies", canonical)
        object.__setattr__(
            self,
            "bundle_digest",
            _domain_token(
                "evaluation_asset_bundle_v1",
                {
                    "primary_target": primary_target.pin_digest,
                    "candidate_target": (
                        None if candidate_target is None else candidate_target.pin_digest
                    ),
                    "dependencies": [item.pin_digest for item in canonical],
                    "query_digest": self.query_digest,
                    "schema_digest": self.schema_digest,
                    "address_space_digest": self.address_space_digest,
                    "compiler_digest": self.compiler_digest,
                    "execution_profile_digest": self.execution_profile_digest,
                    "runtime_digest": self.runtime_digest,
                },
            ),
        )


def _current_asset_bundle(bundle: EvaluationAssetBundleV1) -> EvaluationAssetBundleV1:
    if type(bundle) is not EvaluationAssetBundleV1 or type(bundle.dependencies) is not tuple:
        raise _fail("Asset bundle must be exact EvaluationAssetBundleV1")
    current = _construct(
        "EvaluationAssetBundleV1",
        lambda: EvaluationAssetBundleV1(
            primary_target=_current_asset_pin(bundle.primary_target),
            candidate_target=(
                None
                if bundle.candidate_target is None
                else _current_asset_pin(bundle.candidate_target)
            ),
            dependencies=tuple(_current_asset_pin(item) for item in bundle.dependencies),
            query_digest=bundle.query_digest,
            schema_digest=bundle.schema_digest,
            address_space_digest=bundle.address_space_digest,
            compiler_digest=bundle.compiler_digest,
            execution_profile_digest=bundle.execution_profile_digest,
            runtime_digest=bundle.runtime_digest,
        ),
    )
    if current.bundle_digest != bundle.bundle_digest or current.dependencies != bundle.dependencies:
        raise _fail("EvaluationAssetBundleV1 is stale or noncanonical")
    return current


def _asset_bundle_to_wire(bundle: EvaluationAssetBundleV1) -> dict[str, object]:
    bundle = _current_asset_bundle(bundle)
    return {
        "$type": "FactGraphEvaluationAssetBundleV1",
        "primary_target": _asset_pin_to_wire(bundle.primary_target),
        "candidate_target": (
            None if bundle.candidate_target is None else _asset_pin_to_wire(bundle.candidate_target)
        ),
        "dependencies": [_asset_pin_to_wire(item) for item in bundle.dependencies],
        "query_digest": bundle.query_digest,
        "schema_digest": bundle.schema_digest,
        "address_space_digest": bundle.address_space_digest,
        "compiler_digest": bundle.compiler_digest,
        "execution_profile_digest": bundle.execution_profile_digest,
        "runtime_digest": bundle.runtime_digest,
        "bundle_digest": bundle.bundle_digest,
    }


def _asset_bundle_from_wire(value: object) -> EvaluationAssetBundleV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "primary_target",
                "candidate_target",
                "dependencies",
                "query_digest",
                "schema_digest",
                "address_space_digest",
                "compiler_digest",
                "execution_profile_digest",
                "runtime_digest",
                "bundle_digest",
            }
        ),
        label="EvaluationAssetBundleV1",
    )
    if row["$type"] != "FactGraphEvaluationAssetBundleV1":
        raise _fail("EvaluationAssetBundleV1 type is invalid")
    dependencies = _array(
        row["dependencies"],
        label="EvaluationAssetBundleV1.dependencies",
    )
    if len(dependencies) > MAX_ASSET_DEPENDENCIES_V1:
        raise _fail("EvaluationAssetBundleV1 dependency limit exceeded")
    result = _construct(
        "EvaluationAssetBundleV1",
        lambda: EvaluationAssetBundleV1(
            primary_target=_asset_pin_from_wire(row["primary_target"]),
            candidate_target=(
                None
                if row["candidate_target"] is None
                else _asset_pin_from_wire(row["candidate_target"])
            ),
            dependencies=tuple(_asset_pin_from_wire(item) for item in dependencies),
            query_digest=row["query_digest"],
            schema_digest=row["schema_digest"],
            address_space_digest=row["address_space_digest"],
            compiler_digest=row["compiler_digest"],
            execution_profile_digest=row["execution_profile_digest"],
            runtime_digest=row["runtime_digest"],
        ),
    )
    if row["bundle_digest"] != result.bundle_digest:
        raise _fail("EvaluationAssetBundleV1 bundle_digest mismatch")
    return result


@dataclass(frozen=True)
class EvaluationCaptureProfileV1:
    """Closed request-side capture selection, not authority."""

    row_limit: int
    explain: str
    comparison: str
    capture_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _exact_int(
            self.row_limit,
            label="EvaluationCaptureProfileV1.row_limit",
            minimum=1,
            maximum=MAX_CAPTURE_ROWS_V1,
        )
        if type(self.explain) is not str or self.explain not in _EXPLAIN_CAPTURES:
            raise _fail("EvaluationCaptureProfileV1.explain is outside the closed enum")
        if type(self.comparison) is not str or self.comparison not in _COMPARISON_CAPTURES:
            raise _fail("EvaluationCaptureProfileV1.comparison is outside the closed enum")
        object.__setattr__(
            self,
            "capture_digest",
            _domain_token(
                "evaluation_capture_profile_v1",
                {
                    "row_limit": self.row_limit,
                    "explain": self.explain,
                    "comparison": self.comparison,
                },
            ),
        )


def _current_capture_profile(
    profile: EvaluationCaptureProfileV1,
) -> EvaluationCaptureProfileV1:
    if type(profile) is not EvaluationCaptureProfileV1:
        raise _fail("Capture profile must be exact EvaluationCaptureProfileV1")
    current = _construct(
        "EvaluationCaptureProfileV1",
        lambda: EvaluationCaptureProfileV1(
            profile.row_limit,
            profile.explain,
            profile.comparison,
        ),
    )
    if current.capture_digest != profile.capture_digest:
        raise _fail("EvaluationCaptureProfileV1 capture_digest is stale")
    return current


def _capture_profile_to_wire(profile: EvaluationCaptureProfileV1) -> dict[str, object]:
    profile = _current_capture_profile(profile)
    return {
        "$type": "FactGraphEvaluationCaptureProfileV1",
        "row_limit": profile.row_limit,
        "explain": profile.explain,
        "comparison": profile.comparison,
        "capture_digest": profile.capture_digest,
    }


def _capture_profile_from_wire(value: object) -> EvaluationCaptureProfileV1:
    row = _exact_object(
        value,
        frozenset({"$type", "row_limit", "explain", "comparison", "capture_digest"}),
        label="EvaluationCaptureProfileV1",
    )
    if row["$type"] != "FactGraphEvaluationCaptureProfileV1":
        raise _fail("EvaluationCaptureProfileV1 type is invalid")
    result = _construct(
        "EvaluationCaptureProfileV1",
        lambda: EvaluationCaptureProfileV1(
            row["row_limit"],
            row["explain"],
            row["comparison"],
        ),
    )
    if row["capture_digest"] != result.capture_digest:
        raise _fail("EvaluationCaptureProfileV1 capture_digest mismatch")
    return result


@dataclass(frozen=True)
class EvaluationSchemaCaptureV1:
    """Canonical Schema IR bytes plus the Schema-owned identity digest."""

    schema_bytes: bytes
    schema_digest: str = field(init=False)

    def __post_init__(self) -> None:
        row = _load_json_object(self.schema_bytes, label="EvaluationSchemaCaptureV1.schema")
        try:
            schema = ensure_schema_ir(row)
            canonical = canonicalize_schema_ir_jcs(schema)
            digest = compute_schema_digest(schema)
        except Exception as exc:
            raise _fail("EvaluationSchemaCaptureV1 schema is invalid") from exc
        if canonical != self.schema_bytes:
            raise _fail("EvaluationSchemaCaptureV1 schema bytes are not canonical")
        object.__setattr__(self, "schema_bytes", canonical)
        object.__setattr__(self, "schema_digest", digest)

    @property
    def schema(self) -> dict[str, object]:
        """Return a detached, validated Schema IR object."""

        return _load_json_object(self.schema_bytes, label="EvaluationSchemaCaptureV1.schema")


def _current_schema_capture(
    capture: EvaluationSchemaCaptureV1,
) -> EvaluationSchemaCaptureV1:
    if type(capture) is not EvaluationSchemaCaptureV1:
        raise _fail("Schema capture must be exact EvaluationSchemaCaptureV1")
    current = _construct(
        "EvaluationSchemaCaptureV1",
        lambda: EvaluationSchemaCaptureV1(capture.schema_bytes),
    )
    if (
        current.schema_digest != capture.schema_digest
        or current.schema_bytes != capture.schema_bytes
    ):
        raise _fail("EvaluationSchemaCaptureV1 is stale or noncanonical")
    return current


def _schema_capture_to_wire(capture: EvaluationSchemaCaptureV1) -> dict[str, object]:
    capture = _current_schema_capture(capture)
    return {
        "$type": "FactGraphEvaluationSchemaCaptureV1",
        "schema": capture.schema,
        "schema_digest": capture.schema_digest,
    }


def _schema_capture_from_wire(value: object) -> EvaluationSchemaCaptureV1:
    row = _exact_object(
        value,
        frozenset({"$type", "schema", "schema_digest"}),
        label="EvaluationSchemaCaptureV1",
    )
    if row["$type"] != "FactGraphEvaluationSchemaCaptureV1":
        raise _fail("EvaluationSchemaCaptureV1 type is invalid")
    if type(row["schema"]) is not dict:
        raise _fail("EvaluationSchemaCaptureV1.schema must be an exact JSON object")
    result = _construct(
        "EvaluationSchemaCaptureV1",
        lambda: EvaluationSchemaCaptureV1(
            _canonical_json_bytes(row["schema"], label="EvaluationSchemaCaptureV1.schema")
        ),
    )
    if row["schema_digest"] != result.schema_digest:
        raise _fail("EvaluationSchemaCaptureV1 schema_digest mismatch")
    return result


def evaluation_schema_capture_v1_bytes(capture: EvaluationSchemaCaptureV1) -> bytes:
    """Encode one exact Schema capture component."""

    return _dump_component(
        _schema_capture_to_wire(capture),
        label="EvaluationSchemaCaptureV1",
    )


def evaluation_schema_capture_v1_from_bytes(raw: bytes) -> EvaluationSchemaCaptureV1:
    """Decode one exact Schema capture component."""

    row = _load_json_object(raw, label="EvaluationSchemaCaptureV1")
    result = _schema_capture_from_wire(row)
    if evaluation_schema_capture_v1_bytes(result) != raw:
        raise _fail("EvaluationSchemaCaptureV1 representation is not canonical")
    return result


def _provider_request_to_wire(request: ProviderRequestV1) -> dict[str, object]:
    request = _current_provider_request(request)
    return {
        "$type": "FactGraphProviderRequestV1",
        "provider_digest": request.provider_digest,
        "query_digest": request.query_digest,
        "schema_digest": request.schema_digest,
        "dependency_predicate_ids": list(request.dependency_predicate_ids),
        "supplied_predicate_ids": list(request.supplied_predicate_ids),
        "bindings": [
            {"slot": slot, "value": _goal_value_to_wire(value)} for slot, value in request.bindings
        ],
        "request_digest": request.request_digest,
    }


def _current_provider_request(request: ProviderRequestV1) -> ProviderRequestV1:
    if (
        type(request) is not ProviderRequestV1
        or type(request.dependency_predicate_ids) is not tuple
        or type(request.supplied_predicate_ids) is not tuple
        or type(request.bindings) is not tuple
    ):
        raise _fail("Provider request must be exact ProviderRequestV1")
    bindings: list[tuple[str, GoalValueV1]] = []
    for item in request.bindings:
        if type(item) is not tuple or len(item) != 2 or type(item[1]) is not GoalValueV1:
            raise _fail("ProviderRequestV1 binding has wrong concrete type")
        bindings.append(
            (
                _string(item[0], label="ProviderRequestV1.binding.slot"),
                _goal_value_from_wire(_goal_value_to_wire(item[1])),
            )
        )
    current = _construct(
        "ProviderRequestV1",
        lambda: ProviderRequestV1(
            provider_digest=request.provider_digest,
            query_digest=request.query_digest,
            schema_digest=request.schema_digest,
            dependency_predicate_ids=tuple(request.dependency_predicate_ids),
            supplied_predicate_ids=tuple(request.supplied_predicate_ids),
            bindings=tuple(bindings),
        ),
    )
    if current.request_digest != request.request_digest or current.bindings != request.bindings:
        raise _fail("ProviderRequestV1 is stale or noncanonical")
    return current


def _provider_request_from_wire(value: object) -> ProviderRequestV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "provider_digest",
                "query_digest",
                "schema_digest",
                "dependency_predicate_ids",
                "supplied_predicate_ids",
                "bindings",
                "request_digest",
            }
        ),
        label="ProviderRequestV1",
    )
    if row["$type"] != "FactGraphProviderRequestV1":
        raise _fail("ProviderRequestV1 type is invalid")
    dependencies = _array(
        row["dependency_predicate_ids"],
        label="ProviderRequestV1.dependency_predicate_ids",
    )
    supplied = _array(
        row["supplied_predicate_ids"],
        label="ProviderRequestV1.supplied_predicate_ids",
    )
    bindings = _array(row["bindings"], label="ProviderRequestV1.bindings")
    parsed_bindings: list[tuple[str, GoalValueV1]] = []
    for index, raw in enumerate(bindings):
        binding = _exact_object(
            raw,
            frozenset({"slot", "value"}),
            label=f"ProviderRequestV1.bindings[{index}]",
        )
        parsed_bindings.append(
            (
                _string(binding["slot"], label=f"ProviderRequestV1.bindings[{index}].slot"),
                _goal_value_from_wire(binding["value"]),
            )
        )
    result = _construct(
        "ProviderRequestV1",
        lambda: ProviderRequestV1(
            provider_digest=row["provider_digest"],
            query_digest=row["query_digest"],
            schema_digest=row["schema_digest"],
            dependency_predicate_ids=tuple(dependencies),
            supplied_predicate_ids=tuple(supplied),
            bindings=tuple(parsed_bindings),
        ),
    )
    if row["request_digest"] != result.request_digest:
        raise _fail("ProviderRequestV1 request_digest mismatch")
    return result


def _provider_row_to_wire(row: ProviderRelationRowV1) -> dict[str, object]:
    row = _current_provider_row(row)
    return {
        "predicate_id": row.predicate_id,
        "values": [_goal_value_to_wire(item) for item in row.values],
        "origin_ref": row.origin_ref,
        "tuple_digest": row.tuple_digest,
        "row_digest": row.row_digest,
    }


def _current_provider_row(row: ProviderRelationRowV1) -> ProviderRelationRowV1:
    if type(row) is not ProviderRelationRowV1 or type(row.values) is not tuple:
        raise _fail("Provider row must be exact ProviderRelationRowV1")
    current = _construct(
        "ProviderRelationRowV1",
        lambda: ProviderRelationRowV1(
            row.predicate_id,
            tuple(_goal_value_from_wire(_goal_value_to_wire(item)) for item in row.values),
            row.origin_ref,
        ),
    )
    if (
        current.tuple_digest != row.tuple_digest
        or current.row_digest != row.row_digest
        or current.values != row.values
    ):
        raise _fail("ProviderRelationRowV1 is stale or noncanonical")
    return current


def _provider_row_from_wire(value: object) -> ProviderRelationRowV1:
    row = _exact_object(
        value,
        frozenset({"predicate_id", "values", "origin_ref", "tuple_digest", "row_digest"}),
        label="ProviderRelationRowV1",
    )
    values = _array(row["values"], label="ProviderRelationRowV1.values")
    result = _construct(
        "ProviderRelationRowV1",
        lambda: ProviderRelationRowV1(
            row["predicate_id"],
            tuple(_goal_value_from_wire(item) for item in values),
            row["origin_ref"],
        ),
    )
    if row["tuple_digest"] != result.tuple_digest or row["row_digest"] != result.row_digest:
        raise _fail("ProviderRelationRowV1 derived digest mismatch")
    return result


def _provider_materialization_to_wire(
    materialization: ProviderMaterializationV1,
) -> dict[str, object]:
    materialization = _current_provider_materialization(materialization)
    return {
        "$type": "FactGraphProviderMaterializationV1",
        "provider_digest": materialization.provider_digest,
        "request_digest": materialization.request_digest,
        "receipt_ref": materialization.receipt_ref,
        "receipt_digest": materialization.receipt_digest,
        "predicate_ids": list(materialization.predicate_ids),
        "rows": [_provider_row_to_wire(item) for item in materialization.rows],
        "materialization_digest": materialization.materialization_digest,
    }


def _current_provider_materialization(
    materialization: ProviderMaterializationV1,
) -> ProviderMaterializationV1:
    if (
        type(materialization) is not ProviderMaterializationV1
        or type(materialization.predicate_ids) is not tuple
        or type(materialization.rows) is not tuple
    ):
        raise _fail("Provider materialization must be exact ProviderMaterializationV1")
    current = _construct(
        "ProviderMaterializationV1",
        lambda: ProviderMaterializationV1(
            provider_digest=materialization.provider_digest,
            request_digest=materialization.request_digest,
            receipt_ref=materialization.receipt_ref,
            receipt_digest=materialization.receipt_digest,
            predicate_ids=tuple(materialization.predicate_ids),
            rows=tuple(_current_provider_row(item) for item in materialization.rows),
        ),
    )
    if (
        current.materialization_digest != materialization.materialization_digest
        or current.rows != materialization.rows
    ):
        raise _fail("ProviderMaterializationV1 is stale or noncanonical")
    return current


def _provider_materialization_from_wire(value: object) -> ProviderMaterializationV1:
    row = _exact_object(
        value,
        frozenset(
            {
                "$type",
                "provider_digest",
                "request_digest",
                "receipt_ref",
                "receipt_digest",
                "predicate_ids",
                "rows",
                "materialization_digest",
            }
        ),
        label="ProviderMaterializationV1",
    )
    if row["$type"] != "FactGraphProviderMaterializationV1":
        raise _fail("ProviderMaterializationV1 type is invalid")
    predicate_ids = _array(
        row["predicate_ids"],
        label="ProviderMaterializationV1.predicate_ids",
    )
    rows = _array(row["rows"], label="ProviderMaterializationV1.rows")
    result = _construct(
        "ProviderMaterializationV1",
        lambda: ProviderMaterializationV1(
            provider_digest=row["provider_digest"],
            request_digest=row["request_digest"],
            receipt_ref=row["receipt_ref"],
            receipt_digest=row["receipt_digest"],
            predicate_ids=tuple(predicate_ids),
            rows=tuple(_provider_row_from_wire(item) for item in rows),
        ),
    )
    if row["materialization_digest"] != result.materialization_digest:
        raise _fail("ProviderMaterializationV1 materialization_digest mismatch")
    return result


@dataclass(frozen=True)
class EvaluationProviderCaptureV1:
    """The exact provider request and its already materialized finite output."""

    request: ProviderRequestV1
    materialization: ProviderMaterializationV1
    capture_digest: str = field(init=False)

    def __post_init__(self) -> None:
        request = _current_provider_request(self.request)
        materialization = _current_provider_materialization(self.materialization)
        if (
            materialization.provider_digest != request.provider_digest
            or materialization.request_digest != request.request_digest
            or materialization.predicate_ids != request.supplied_predicate_ids
        ):
            raise _fail(
                "EvaluationProviderCaptureV1 materialization does not match its reconstructed request"
            )
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "materialization", materialization)
        object.__setattr__(
            self,
            "capture_digest",
            _domain_token(
                "evaluation_provider_capture_v1",
                {
                    "request_digest": request.request_digest,
                    "materialization_digest": materialization.materialization_digest,
                },
            ),
        )


def _current_provider_capture(
    capture: EvaluationProviderCaptureV1,
) -> EvaluationProviderCaptureV1:
    if type(capture) is not EvaluationProviderCaptureV1:
        raise _fail("Provider capture must be exact EvaluationProviderCaptureV1")
    current = _construct(
        "EvaluationProviderCaptureV1",
        lambda: EvaluationProviderCaptureV1(
            _current_provider_request(capture.request),
            _current_provider_materialization(capture.materialization),
        ),
    )
    if current.capture_digest != capture.capture_digest:
        raise _fail("EvaluationProviderCaptureV1 capture_digest is stale")
    return current


def _provider_capture_to_wire(capture: EvaluationProviderCaptureV1) -> dict[str, object]:
    capture = _current_provider_capture(capture)
    return {
        "$type": "FactGraphEvaluationProviderCaptureV1",
        "request": _provider_request_to_wire(capture.request),
        "materialization": _provider_materialization_to_wire(capture.materialization),
        "capture_digest": capture.capture_digest,
    }


def _provider_capture_from_wire(value: object) -> EvaluationProviderCaptureV1:
    row = _exact_object(
        value,
        frozenset({"$type", "request", "materialization", "capture_digest"}),
        label="EvaluationProviderCaptureV1",
    )
    if row["$type"] != "FactGraphEvaluationProviderCaptureV1":
        raise _fail("EvaluationProviderCaptureV1 type is invalid")
    result = _construct(
        "EvaluationProviderCaptureV1",
        lambda: EvaluationProviderCaptureV1(
            _provider_request_from_wire(row["request"]),
            _provider_materialization_from_wire(row["materialization"]),
        ),
    )
    if row["capture_digest"] != result.capture_digest:
        raise _fail("EvaluationProviderCaptureV1 capture_digest mismatch")
    return result


def evaluation_provider_capture_v1_bytes(capture: EvaluationProviderCaptureV1) -> bytes:
    """Encode one exact provider request/materialization component."""

    return _dump_component(
        _provider_capture_to_wire(capture),
        label="EvaluationProviderCaptureV1",
    )


def evaluation_provider_capture_v1_from_bytes(raw: bytes) -> EvaluationProviderCaptureV1:
    """Decode one exact provider request/materialization component."""

    row = _load_json_object(raw, label="EvaluationProviderCaptureV1")
    result = _provider_capture_from_wire(row)
    if evaluation_provider_capture_v1_bytes(result) != raw:
        raise _fail("EvaluationProviderCaptureV1 set/order representation is not canonical")
    return result


def scenario_spec_v1_bytes(spec: ScenarioSpecV1) -> bytes:
    """Encode Scenario through the stricter C2 Scenario component owner."""

    from .sealed_evaluation_scenario_v1 import scenario_spec_v1_bytes as encode

    return encode(spec)


def scenario_spec_v1_from_bytes(raw: bytes) -> ScenarioSpecV1:
    """Decode Scenario through the stricter C2 Scenario component owner."""

    from .sealed_evaluation_scenario_v1 import scenario_spec_v1_from_bytes as decode

    return decode(raw)


def _candidate_plan(plan: GoalPlanV1) -> GoalPlanV1 | None:
    if plan.candidate_target is None:
        return None
    assert plan.candidate_query_digest is not None
    return GoalPlanV1(
        target=plan.candidate_target,
        query_digest=plan.candidate_query_digest,
        result_mode=plan.result_mode,
        selections=plan.selections,
        scenario_request_digest=plan.scenario_request_digest,
        evidence_scope_digest=plan.evidence_scope_digest,
        execution_profile_digest=plan.execution_profile_digest,
    )


@dataclass(frozen=True, repr=False)
class SealedEvaluationRequestV1:
    """Canonical component bytes for one neutral, detached evaluation."""

    asset_bundle: EvaluationAssetBundleV1
    goal_plan_bytes: bytes
    execution_profile_bytes: bytes
    schema_bytes: bytes
    program_envelope_bytes: bytes
    baseline_world_bytes: bytes
    world_input_pins: EvaluationWorldInputPinsV1
    scenario_bytes: bytes | None
    provider_capture_bytes: bytes | None
    capture: EvaluationCaptureProfileV1
    request_digest: str = field(init=False)

    def __post_init__(self) -> None:
        asset_bundle = _current_asset_bundle(self.asset_bundle)
        capture = _current_capture_profile(self.capture)
        world_input_pins = _current_world_input_pins(self.world_input_pins)
        object.__setattr__(self, "asset_bundle", asset_bundle)
        object.__setattr__(self, "capture", capture)
        object.__setattr__(self, "world_input_pins", world_input_pins)
        required_components = (
            ("goal_plan_bytes", self.goal_plan_bytes),
            ("execution_profile_bytes", self.execution_profile_bytes),
            ("schema_bytes", self.schema_bytes),
            ("program_envelope_bytes", self.program_envelope_bytes),
            ("baseline_world_bytes", self.baseline_world_bytes),
        )
        for name, raw in required_components:
            if (
                type(raw) is not bytes
                or not raw
                or len(raw) > MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1
            ):
                raise _fail(f"SealedEvaluationRequestV1.{name} is not bounded exact bytes")
        for name in ("scenario_bytes", "provider_capture_bytes"):
            raw = getattr(self, name)
            if raw is not None and (
                type(raw) is not bytes
                or not raw
                or len(raw) > MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1
            ):
                raise _fail(f"SealedEvaluationRequestV1.{name} is not null or bounded bytes")

        # Component syntax/version is validated before the request digest is
        # accepted.  This does not decode the compiled-program body.
        goal_plan_v1_from_bytes(self.goal_plan_bytes)
        evaluation_execution_profile_v1_from_bytes(self.execution_profile_bytes)
        evaluation_schema_capture_v1_from_bytes(self.schema_bytes)
        _load_json_object(
            self.program_envelope_bytes,
            label="EvaluationReplayProgramEnvelopeV1",
        )
        evaluation_replay_program_envelope_v1_from_bytes(self.program_envelope_bytes)
        evaluation_replay_world_v1_from_bytes(self.baseline_world_bytes)
        if self.scenario_bytes is not None:
            scenario_spec_v1_from_bytes(self.scenario_bytes)
        if self.provider_capture_bytes is not None:
            evaluation_provider_capture_v1_from_bytes(self.provider_capture_bytes)
        object.__setattr__(
            self,
            "request_digest",
            _domain_token("sealed_evaluation_request_v1", _request_digest_payload(self)),
        )

    def __repr__(self) -> str:
        return (
            "SealedEvaluationRequestV1("
            f"request_digest={self.request_digest!r}, components=<redacted>)"
        )


def _request_digest_payload(request: SealedEvaluationRequestV1) -> dict[str, object]:
    return {
        "asset_bundle": _asset_bundle_to_wire(request.asset_bundle),
        "goal_plan_bytes_b64u": _b64u(request.goal_plan_bytes),
        "execution_profile_bytes_b64u": _b64u(request.execution_profile_bytes),
        "schema_bytes_b64u": _b64u(request.schema_bytes),
        "program_envelope_bytes_b64u": _b64u(request.program_envelope_bytes),
        "baseline_world_bytes_b64u": _b64u(request.baseline_world_bytes),
        "world_input_pins": _world_input_pins_to_wire(request.world_input_pins),
        "scenario_bytes_b64u": (
            None if request.scenario_bytes is None else _b64u(request.scenario_bytes)
        ),
        "provider_capture_bytes_b64u": (
            None
            if request.provider_capture_bytes is None
            else _b64u(request.provider_capture_bytes)
        ),
        "capture": _capture_profile_to_wire(request.capture),
    }


def sealed_evaluation_request_v1_bytes(request: SealedEvaluationRequestV1) -> bytes:
    """Encode the exact outer request envelope with its 8 MiB ceiling."""

    if type(request) is not SealedEvaluationRequestV1:
        raise _fail("Request must be exact SealedEvaluationRequestV1")
    assert_sealed_evaluation_request_current_v1(request)
    raw = _canonical_json_bytes(
        {
            "$type": "FactGraphSealedEvaluationRequestV1",
            **_request_digest_payload(request),
            "request_digest": request.request_digest,
        },
        label="SealedEvaluationRequestV1",
    )
    if len(raw) > MAX_SEALED_EVALUATION_REQUEST_BYTES_V1:
        raise _fail("SealedEvaluationRequestV1 exceeds the request byte limit")
    return raw


def sealed_evaluation_request_v1_from_bytes(raw: bytes) -> SealedEvaluationRequestV1:
    """Decode the exact outer request envelope without executing anything."""

    row = _load_json_object(
        raw,
        label="SealedEvaluationRequestV1",
        max_bytes=MAX_SEALED_EVALUATION_REQUEST_BYTES_V1,
    )
    data = _exact_object(
        row,
        frozenset(
            {
                "$type",
                "asset_bundle",
                "goal_plan_bytes_b64u",
                "execution_profile_bytes_b64u",
                "schema_bytes_b64u",
                "program_envelope_bytes_b64u",
                "baseline_world_bytes_b64u",
                "world_input_pins",
                "scenario_bytes_b64u",
                "provider_capture_bytes_b64u",
                "capture",
                "request_digest",
            }
        ),
        label="SealedEvaluationRequestV1",
    )
    if data["$type"] != "FactGraphSealedEvaluationRequestV1":
        raise _fail("SealedEvaluationRequestV1 type is invalid")

    def optional_component(name: str) -> bytes | None:
        value = data[name]
        return None if value is None else _decode_b64u(value, label=name)

    result = _construct(
        "SealedEvaluationRequestV1",
        lambda: SealedEvaluationRequestV1(
            asset_bundle=_asset_bundle_from_wire(data["asset_bundle"]),
            goal_plan_bytes=_decode_b64u(
                data["goal_plan_bytes_b64u"],
                label="goal_plan_bytes_b64u",
            ),
            execution_profile_bytes=_decode_b64u(
                data["execution_profile_bytes_b64u"],
                label="execution_profile_bytes_b64u",
            ),
            schema_bytes=_decode_b64u(
                data["schema_bytes_b64u"],
                label="schema_bytes_b64u",
            ),
            program_envelope_bytes=_decode_b64u(
                data["program_envelope_bytes_b64u"],
                label="program_envelope_bytes_b64u",
            ),
            baseline_world_bytes=_decode_b64u(
                data["baseline_world_bytes_b64u"],
                label="baseline_world_bytes_b64u",
            ),
            world_input_pins=_world_input_pins_from_wire(data["world_input_pins"]),
            scenario_bytes=optional_component("scenario_bytes_b64u"),
            provider_capture_bytes=optional_component("provider_capture_bytes_b64u"),
            capture=_capture_profile_from_wire(data["capture"]),
        ),
    )
    if data["request_digest"] != result.request_digest:
        raise _fail("SealedEvaluationRequestV1 request_digest mismatch")
    if sealed_evaluation_request_v1_bytes(result) != raw:
        raise _fail("SealedEvaluationRequestV1 representation is not canonical")
    return result


def assert_sealed_evaluation_request_current_v1(
    request: SealedEvaluationRequestV1,
) -> None:
    """Revalidate an in-memory request as the exact current V1 contract."""

    if type(request) is not SealedEvaluationRequestV1:
        raise _fail("Request must be exact SealedEvaluationRequestV1")
    expected = SealedEvaluationRequestV1(
        asset_bundle=request.asset_bundle,
        goal_plan_bytes=request.goal_plan_bytes,
        execution_profile_bytes=request.execution_profile_bytes,
        schema_bytes=request.schema_bytes,
        program_envelope_bytes=request.program_envelope_bytes,
        baseline_world_bytes=request.baseline_world_bytes,
        world_input_pins=request.world_input_pins,
        scenario_bytes=request.scenario_bytes,
        provider_capture_bytes=request.provider_capture_bytes,
        capture=request.capture,
    )
    if request.request_digest != expected.request_digest:
        raise _fail("SealedEvaluationRequestV1 is not current")


@dataclass(frozen=True)
class DecodedSealedEvaluationRequestV1:
    """Closed typed components after outer syntax and pin validation."""

    asset_bundle: EvaluationAssetBundleV1
    goal_plan: GoalPlanV1
    candidate_plan: GoalPlanV1 | None
    execution_profile: EvaluationExecutionProfileV1
    schema: EvaluationSchemaCaptureV1
    program_envelope: EvaluationReplayProgramEnvelopeV1
    baseline_world: EvaluationReplayWorldV1
    world_input_pins: EvaluationWorldInputPinsV1
    scenario: ScenarioSpecV1 | None
    provider_capture: EvaluationProviderCaptureV1 | None
    capture: EvaluationCaptureProfileV1
    request_digest: str

    def __post_init__(self) -> None:
        exact_fields = (
            (self.asset_bundle, EvaluationAssetBundleV1, "asset_bundle"),
            (self.goal_plan, GoalPlanV1, "goal_plan"),
            (self.execution_profile, EvaluationExecutionProfileV1, "execution_profile"),
            (self.schema, EvaluationSchemaCaptureV1, "schema"),
            (
                self.program_envelope,
                EvaluationReplayProgramEnvelopeV1,
                "program_envelope",
            ),
            (self.baseline_world, EvaluationReplayWorldV1, "baseline_world"),
            (
                self.world_input_pins,
                EvaluationWorldInputPinsV1,
                "world_input_pins",
            ),
            (self.capture, EvaluationCaptureProfileV1, "capture"),
        )
        for value, expected, name in exact_fields:
            if type(value) is not expected:
                raise _fail(f"DecodedSealedEvaluationRequestV1.{name} has wrong type")
        if self.candidate_plan is not None and type(self.candidate_plan) is not GoalPlanV1:
            raise _fail("DecodedSealedEvaluationRequestV1.candidate_plan has wrong type")
        if self.scenario is not None and type(self.scenario) is not ScenarioSpecV1:
            raise _fail("DecodedSealedEvaluationRequestV1.scenario has wrong type")
        if (
            self.provider_capture is not None
            and type(self.provider_capture) is not EvaluationProviderCaptureV1
        ):
            raise _fail("DecodedSealedEvaluationRequestV1.provider_capture has wrong type")
        _token(self.request_digest, label="DecodedSealedEvaluationRequestV1.request_digest")


def _assert_world_schema(
    world: EvaluationReplayWorldV1,
    schema: EvaluationSchemaCaptureV1,
) -> None:
    if world.side != "baseline":
        raise _fail("Sealed request accepts only a baseline replay world")
    if not world.relations:
        raise _fail("Sealed request requires an explicit non-empty dependency inventory")
    if world.closure_target_digests:
        raise _fail("Sealed request baseline closure inventory must be empty")
    schema_row = schema.schema
    specs: dict[str, tuple[str, ...]] = {}
    for raw in schema_row["predicates"]:  # schema validator owns this shape
        assert type(raw) is dict
        predicate_id = raw["pred_id"]
        arg_specs = raw["arg_specs"]
        assert type(predicate_id) is str and type(arg_specs) is list
        specs[predicate_id] = tuple(item["type_domain"] for item in arg_specs)
    witness_refs: set[str] = set()
    fact_digests: set[str] = set()
    for relation in world.relations:
        if specs.get(relation.predicate_id) != relation.value_tags:
            raise _fail("Replay world relation does not match the captured Schema IR")
        for fact in relation.facts:
            if fact.witness_ref in witness_refs or fact.fact_digest in fact_digests:
                raise _fail("Replay world witness/fact identity must be globally unique")
            witness_refs.add(fact.witness_ref)
            fact_digests.add(fact.fact_digest)


def _assert_provider_schema(
    capture: EvaluationProviderCaptureV1,
    schema: EvaluationSchemaCaptureV1,
) -> None:
    schema_row = schema.schema
    specs: dict[str, tuple[str, ...]] = {}
    for raw in schema_row["predicates"]:
        assert type(raw) is dict
        specs[raw["pred_id"]] = tuple(item["type_domain"] for item in raw["arg_specs"])
    for row in capture.materialization.rows:
        expected = specs.get(row.predicate_id)
        actual = tuple(value.tag for value in row.values)
        if expected is None or expected != actual:
            raise _fail("Provider materialization row does not match captured Schema IR")


def _assert_request_cross_pins(
    *,
    request: SealedEvaluationRequestV1,
    plan: GoalPlanV1,
    candidate_plan: GoalPlanV1 | None,
    profile: EvaluationExecutionProfileV1,
    schema: EvaluationSchemaCaptureV1,
    envelope: EvaluationReplayProgramEnvelopeV1,
    world: EvaluationReplayWorldV1,
    scenario: ScenarioSpecV1 | None,
    provider: EvaluationProviderCaptureV1 | None,
) -> None:
    bundle = request.asset_bundle
    if plan.target.target_version is None:
        raise _fail("Sealed Goal target requires a non-null immutable version")
    if (
        bundle.primary_target.kind != plan.target.kind
        or bundle.primary_target.asset_id != plan.target.target_id
        or bundle.primary_target.version != plan.target.target_version
        or bundle.primary_target.artifact_digest != plan.target.target_digest
    ):
        raise _fail("Primary asset pin does not match GoalPlanV1 target")
    if plan.execution_profile_digest != profile.profile_digest:
        raise _fail("GoalPlanV1 execution profile pin is absent or mismatched")
    if plan.evidence_scope_digest is None:
        raise _fail("Sealed GoalPlanV1 requires an admitted evidence-scope pin")
    if (
        bundle.query_digest != plan.query_digest
        or bundle.schema_digest != schema.schema_digest
        or bundle.compiler_digest != profile.compiler_digest
        or bundle.execution_profile_digest != profile.profile_digest
        or envelope.plan_digest != plan.plan_digest
        or envelope.query_digest != plan.query_digest
        or envelope.target_digest != plan.target.target_digest
        or envelope.schema_digest != schema.schema_digest
        or envelope.address_space_digest != bundle.address_space_digest
        or envelope.compiler_digest != profile.compiler_digest
        or envelope.execution_profile_digest != profile.profile_digest
    ):
        raise _fail("Goal/schema/program/profile/asset outer pin mismatch")

    if (scenario is None) != (plan.scenario_request_digest is None):
        raise _fail("Scenario component presence does not match GoalPlanV1")
    if scenario is not None and scenario.spec_digest != plan.scenario_request_digest:
        raise _fail("Scenario component digest does not match GoalPlanV1")

    if candidate_plan is None:
        if bundle.candidate_target is not None or any(
            value is not None
            for value in (
                envelope.candidate_plan_digest,
                envelope.candidate_query_digest,
                envelope.candidate_target_digest,
            )
        ):
            raise _fail("Candidate presence is not all-or-none")
    else:
        assert plan.candidate_target is not None
        assert plan.candidate_query_digest is not None
        if plan.candidate_target.target_version is None:
            raise _fail("Sealed candidate target requires a non-null immutable version")
        pin = bundle.candidate_target
        if pin is None or (
            pin.kind != plan.candidate_target.kind
            or pin.asset_id != plan.candidate_target.target_id
            or pin.version != plan.candidate_target.target_version
            or pin.artifact_digest != plan.candidate_target.target_digest
            or envelope.candidate_plan_digest != candidate_plan.plan_digest
            or envelope.candidate_query_digest != candidate_plan.query_digest
            or envelope.candidate_target_digest != candidate_plan.target.target_digest
        ):
            raise _fail("Candidate asset/program/Goal pins do not match")

    provider_dependencies = tuple(item for item in bundle.dependencies if item.kind == "provider")
    if plan.target.kind == "relation_provider":
        if (
            bundle.primary_target.kind != "relation_provider"
            or candidate_plan is not None
            or provider is None
            or len(provider_dependencies) != 1
        ):
            raise _fail("Relation-provider target requires one capture/dependency and no candidate")
        dependency = provider_dependencies[0]
        if (
            dependency.artifact_digest != provider.request.provider_digest
            or provider.request.query_digest != plan.query_digest
            or provider.request.schema_digest != schema.schema_digest
            or tuple(item.predicate_id for item in world.relations)
            != provider.request.dependency_predicate_ids
        ):
            raise _fail("Provider request does not match asset/query/schema/baseline pins")
        _assert_provider_schema(provider, schema)
    elif provider is not None or provider_dependencies:
        raise _fail("Rule/Policy target cannot carry a provider capture/dependency")

    if request.capture.comparison == "baseline_vs_effective":
        if scenario is None or not scenario.operations or candidate_plan is not None:
            raise _fail("baseline_vs_effective capture requires Scenario and no candidate")
    elif request.capture.comparison == "published_candidate" and candidate_plan is None:
        raise _fail("published_candidate capture requires a candidate")

    _assert_world_schema(world, schema)


def decode_sealed_evaluation_request_v1(
    request: SealedEvaluationRequestV1,
) -> DecodedSealedEvaluationRequestV1:
    """Decode typed components and validate all non-program-body pins.

    The returned program envelope is syntax/digest checked but its compiled
    body remains deliberately opaque here.  The runtime owner must decode that
    body last and then reproduce dependency/binding/native-display semantics.
    """

    assert_sealed_evaluation_request_current_v1(request)
    plan = goal_plan_v1_from_bytes(request.goal_plan_bytes)
    profile = evaluation_execution_profile_v1_from_bytes(request.execution_profile_bytes)
    schema = evaluation_schema_capture_v1_from_bytes(request.schema_bytes)
    world = evaluation_replay_world_v1_from_bytes(request.baseline_world_bytes)
    scenario = (
        None
        if request.scenario_bytes is None
        else scenario_spec_v1_from_bytes(request.scenario_bytes)
    )
    provider = (
        None
        if request.provider_capture_bytes is None
        else evaluation_provider_capture_v1_from_bytes(request.provider_capture_bytes)
    )
    # The existing public envelope decoder validates syntax/current type and
    # freezes JSON.  It does not semantically decode the compiled body.
    envelope = evaluation_replay_program_envelope_v1_from_bytes(request.program_envelope_bytes)
    candidate = _candidate_plan(plan)
    _assert_request_cross_pins(
        request=request,
        plan=plan,
        candidate_plan=candidate,
        profile=profile,
        schema=schema,
        envelope=envelope,
        world=world,
        scenario=scenario,
        provider=provider,
    )
    return DecodedSealedEvaluationRequestV1(
        asset_bundle=request.asset_bundle,
        goal_plan=plan,
        candidate_plan=candidate,
        execution_profile=profile,
        schema=schema,
        program_envelope=envelope,
        baseline_world=world,
        world_input_pins=request.world_input_pins,
        scenario=scenario,
        provider_capture=provider,
        capture=request.capture,
        request_digest=request.request_digest,
    )


__all__ = [
    "MAX_SEALED_EVALUATION_COMPONENT_BYTES_V1",
    "MAX_SEALED_EVALUATION_JSON_DEPTH_V1",
    "MAX_SEALED_EVALUATION_REQUEST_BYTES_V1",
    "SEALED_EVALUATION_RUNTIME_DIGEST_V1",
    "DecodedSealedEvaluationRequestV1",
    "EvaluationAssetBundleV1",
    "EvaluationAssetPinV1",
    "EvaluationCaptureProfileV1",
    "EvaluationProviderCaptureV1",
    "EvaluationSchemaCaptureV1",
    "EvaluationWorldInputPinsV1",
    "SealedEvaluationRequestV1",
    "assert_sealed_evaluation_request_current_v1",
    "decode_sealed_evaluation_request_v1",
    "evaluation_execution_profile_v1_bytes",
    "evaluation_execution_profile_v1_from_bytes",
    "evaluation_provider_capture_v1_bytes",
    "evaluation_provider_capture_v1_from_bytes",
    "evaluation_replay_world_v1_bytes",
    "evaluation_replay_world_v1_from_bytes",
    "evaluation_schema_capture_v1_bytes",
    "evaluation_schema_capture_v1_from_bytes",
    "goal_plan_v1_bytes",
    "goal_plan_v1_from_bytes",
    "scenario_spec_v1_bytes",
    "scenario_spec_v1_from_bytes",
    "sealed_evaluation_request_v1_bytes",
    "sealed_evaluation_request_v1_from_bytes",
]
