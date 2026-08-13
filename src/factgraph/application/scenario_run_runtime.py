"""Detached runtime for the bounded ScenarioRun v0 lifecycle.

The generic F4 bundle remains an internal adapter here.  ScenarioRun's public
contract names its two captured relation sides and rewrites every evidence
source so a synthetic effective witness cannot look like a ledger assertion.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import Any, Literal

from factgraph.application.evaluation_run_bundle_runtime import (
    MAX_EVALUATION_RUN_BUNDLE_BYTES,
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
)
from factgraph.application.evaluation_run_evidence_runtime import (
    _evaluation_run_bundle_evidence,
)
from factgraph.application.evaluation_run_verification_runtime import (
    verify_evaluation_run_bundle,
)
from factgraph.application.protocol.evaluate_result import canonical_bytes_for_evaluate
from factgraph.application.policy_explanation_runtime import project_policy_explanation_v0
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_bundle import EvaluationRunBundleV0
from factgraph.application.protocol.evaluation_scenario import (
    ScenarioResultDiffV0,
    ScenarioScalarValueV0,
)
from factgraph.application.protocol.scenario_run import (
    ScenarioPremiseBindingV0,
    ScenarioRunExplanationV0,
    ScenarioRunPlanV0,
    ScenarioRunRowV0,
    ScenarioRunSideV0,
    ScenarioRunV0,
    ScenarioRunVerificationV0,
)
from factgraph.application.protocol.schema_runtime import FieldPath
from factgraph.core.protocol.digests import sha256_hex, sha256_token


# A ScenarioRun carries two opaque, URL-safe-base64 encoded capture frames.
# Account for the 4/3 binary-to-text expansion of two maximum-size F4 payloads
# plus bounded outer plan/summary metadata, rather than accidentally making a
# valid pair of inner captures impossible to serialize.
MAX_SCENARIO_RUN_BYTES = 2 * (4 * ((MAX_EVALUATION_RUN_BUNDLE_BYTES + 2) // 3)) + 256 * 1024
_SCENARIO_WIRE_TYPE = "scenario_run_v0"
_SCENARIO_CAPTURE_MAGIC = b"scenario_run_capture_v0\0"


def build_scenario_run_v0(
    *,
    compiled_query: Any,
    target: Any,
    base_view_digest: str,
    baseline_relation_digest: str,
    effective_relation_digest: str,
    premise_bindings: tuple[ScenarioPremiseBindingV0, ...],
    result_diff: ScenarioResultDiffV0,
    baseline_bundle: EvaluationRunBundleV0,
    effective_bundle: EvaluationRunBundleV0,
) -> ScenarioRunV0:
    """Seal two private F4 bundles into one explicit Scenario contract."""

    if not isinstance(premise_bindings, tuple) or not premise_bindings:
        raise ProtocolShapeError("ScenarioRun requires resolver-produced premise bindings")
    scenario_kind: Literal["single_field_replacement", "atomic_field_replacement_set"]
    if len(premise_bindings) == 1:
        scenario_kind = "single_field_replacement"
    else:
        scenario_kind = "atomic_field_replacement_set"
    plan = ScenarioRunPlanV0(
        query_digest=compiled_query.query_digest,
        target_digest=target.target_digest,
        policy_digest=compiled_query.policy_digest,
        address_space_digest=compiled_query.address_space_digest,
        schema_digest=compiled_query.schema_digest,
        base_view_digest=base_view_digest,
        baseline_relation_digest=baseline_relation_digest,
        effective_relation_digest=effective_relation_digest,
        scenario_kind=scenario_kind,
        premise_bindings=premise_bindings,
    )
    baseline_bytes = _scenario_capture_bytes("baseline", baseline_bundle)
    effective_bytes = _scenario_capture_bytes("effective", effective_bundle)
    run = ScenarioRunV0(
        plan=plan,
        baseline=_side_from_bundle(
            "baseline",
            baseline_bundle,
            relation_digest=baseline_relation_digest,
            capture_bytes=baseline_bytes,
        ),
        effective=_side_from_bundle(
            "effective",
            effective_bundle,
            relation_digest=effective_relation_digest,
            capture_bytes=effective_bytes,
        ),
        result_diff=result_diff,
        _baseline_capture_bytes=baseline_bytes,
        _effective_capture_bytes=effective_bytes,
    )
    _assert_scenario_run_current(run)
    return run


def scenario_run_bytes(run: ScenarioRunV0) -> bytes:
    """Canonical outer codec.  Inner F4 bytes remain opaque payload fields."""

    _assert_scenario_run_current(run)
    payload = {
        "$type": _SCENARIO_WIRE_TYPE,
        "fields": {
            "plan": _plan_to_wire(run.plan),
            "baseline": _side_to_wire(run.baseline),
            "effective": _side_to_wire(run.effective),
            "result_diff": _diff_to_wire(run.result_diff),
            "baseline_capture": _b64(run._baseline_capture_bytes),
            "effective_capture": _b64(run._effective_capture_bytes),
            "integrity": run.integrity,
            "authenticity": run.authenticity,
            "premise_provenance": run.premise_provenance,
            "ledger_truth": run.ledger_truth,
            "explain_availability": run.explain_availability,
            "verification_availability": run.verification_availability,
            "scenario_run_digest": run.scenario_run_digest,
        },
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > MAX_SCENARIO_RUN_BYTES:
        raise ProtocolShapeError("ScenarioRun exceeds maximum encoded size")
    return raw


def scenario_run_from_bytes(raw: bytes) -> ScenarioRunV0:
    """Decode one strict canonical ScenarioRun outer payload."""

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SCENARIO_RUN_BYTES:
        raise ProtocolShapeError("ScenarioRun bytes are empty or exceed maximum size")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("ScenarioRun bytes are not valid UTF-8 JSON") from exc
    if _json_depth(payload) > 64 or _canonical_json_bytes(payload) != raw:
        raise ProtocolShapeError("ScenarioRun JSON is non-canonical or too deep")
    if not isinstance(payload, dict) or set(payload) != {"$type", "fields"}:
        raise ProtocolShapeError("ScenarioRun root shape is invalid")
    if payload["$type"] != _SCENARIO_WIRE_TYPE or not isinstance(payload["fields"], dict):
        raise ProtocolShapeError("ScenarioRun root type is invalid")
    fields = payload["fields"]
    required = {
        "plan",
        "baseline",
        "effective",
        "result_diff",
        "baseline_capture",
        "effective_capture",
        "integrity",
        "authenticity",
        "premise_provenance",
        "ledger_truth",
        "explain_availability",
        "verification_availability",
        "scenario_run_digest",
    }
    if set(fields) != required:
        raise ProtocolShapeError("ScenarioRun fields are not exact")
    run = ScenarioRunV0(
        plan=_plan_from_wire(fields["plan"]),
        baseline=_side_from_wire(fields["baseline"]),
        effective=_side_from_wire(fields["effective"]),
        result_diff=_diff_from_wire(fields["result_diff"]),
        _baseline_capture_bytes=_unb64(fields["baseline_capture"]),
        _effective_capture_bytes=_unb64(fields["effective_capture"]),
        integrity=fields["integrity"],
        authenticity=fields["authenticity"],
        premise_provenance=fields["premise_provenance"],
        ledger_truth=fields["ledger_truth"],
        explain_availability=fields["explain_availability"],
        verification_availability=fields["verification_availability"],
    )
    if fields["scenario_run_digest"] != run.scenario_run_digest:
        raise ProtocolShapeError("ScenarioRun digest does not match content")
    _assert_scenario_run_current(run)
    return run


def explain_scenario_run_v0(
    run: ScenarioRunV0,
    *,
    side: Literal["baseline", "effective"],
    row_capture_digest: str,
) -> ScenarioRunExplanationV0:
    """Play one detached row and project it onto the authored Policy tree."""

    bundles = _assert_scenario_run_current(run)
    if side not in {"baseline", "effective"}:
        raise ProtocolShapeError("ScenarioRun explain side must be baseline or effective")
    bundle = bundles[side]
    matching = tuple(row for row in bundle.rows if row.row_capture_digest == row_capture_digest)
    if len(matching) != 1:
        raise ProtocolShapeError("ScenarioRun row_capture_digest is absent or ambiguous on the chosen side")
    source_map = _source_metadata_for_side(run, bundle, side=side)
    evidence = _evaluation_run_bundle_evidence(
        bundle,
        row_capture_digest=row_capture_digest,
        source_meta_by_assertion=source_map,
        metadata_extra={
            "scenario_run_digest": run.scenario_run_digest,
            "scenario_plan_digest": run.plan.plan_digest,
            "scenario_side": side,
            "scenario_relation_digest": (
                run.plan.baseline_relation_digest
                if side == "baseline"
                else run.plan.effective_relation_digest
            ),
            "historical_ledger_replay": False,
            "premise_truth_verified": False,
        },
    )
    anchor = bundle.run_anchor.row_anchors[matching[0].ordinal]
    projection = project_policy_explanation_v0(
        bundle.run_anchor,
        evidence,
        semantic_row_anchor_digest=anchor.semantic_anchor_digest,
    )
    return ScenarioRunExplanationV0(
        scenario_run_digest=run.scenario_run_digest,
        side=side,
        row_capture_digest=row_capture_digest,
        evidence=evidence,
        policy_projection=projection,
    )


def verify_scenario_run_v0(run: ScenarioRunV0) -> ScenarioRunVerificationV0:
    """Verify both captured relations without a Store or live ledger fallback."""

    bundles = _assert_scenario_run_current(run)
    return ScenarioRunVerificationV0(
        scenario_run_digest=run.scenario_run_digest,
        baseline=verify_evaluation_run_bundle(bundles["baseline"]),
        effective=verify_evaluation_run_bundle(bundles["effective"]),
    )


def _assert_scenario_run_current(run: ScenarioRunV0) -> dict[str, EvaluationRunBundleV0]:
    """Cross-check outer plan, private F4 payloads and source inventory."""

    if not isinstance(run, ScenarioRunV0):
        raise ProtocolShapeError("ScenarioRun must be ScenarioRunV0")
    ScenarioRunV0.__post_init__(run)
    baseline = _scenario_capture_from_bytes(run._baseline_capture_bytes, expected_side="baseline")
    effective = _scenario_capture_from_bytes(run._effective_capture_bytes, expected_side="effective")
    pairs = {
        "baseline": (baseline, run.baseline, run.plan.baseline_relation_digest),
        "effective": (effective, run.effective, run.plan.effective_relation_digest),
    }
    for side, (bundle, summary, relation_digest) in pairs.items():
        _assert_side_matches_bundle(
            side,
            summary,
            bundle,
            relation_digest=relation_digest,
            capture_bytes=(
                run._baseline_capture_bytes
                if side == "baseline"
                else run._effective_capture_bytes
            ),
        )
        if (
            bundle.query_digest != run.plan.query_digest
            or bundle.run_anchor.target.target_digest != run.plan.target_digest
            or bundle.run_anchor.target.policy_digest != run.plan.policy_digest
            or bundle.run_anchor.target.address_space_digest != run.plan.address_space_digest
            or bundle.run_anchor.target.schema_digest != run.plan.schema_digest
        ):
            raise ProtocolShapeError("ScenarioRun side bundle does not match its outer pins")
    if (
        baseline.run_anchor.bindings != effective.run_anchor.bindings
        or baseline.run_anchor.selections != effective.run_anchor.selections
        or baseline.native_plan != effective.native_plan
        or baseline.schema_bytes != effective.schema_bytes
        or baseline.execution_contract != effective.execution_contract
        or baseline.query_digest != effective.query_digest
    ):
        raise ProtocolShapeError("ScenarioRun sides do not share one exact Query execution contract")
    if baseline.run_anchor.view_snapshot_digest != run.plan.base_view_digest:
        raise ProtocolShapeError("ScenarioRun baseline side does not match the captured base view")
    if effective.run_anchor.view_snapshot_digest != run.plan.effective_relation_digest:
        raise ProtocolShapeError("ScenarioRun effective side does not match effective relation identity")
    _assert_relation_identity(baseline, run.plan.baseline_relation_digest)
    _assert_relation_identity(effective, run.plan.effective_relation_digest)
    _assert_premise_inventory(run.plan.premise_bindings, baseline, effective)
    expected_diff = _diff_from_bundles(baseline, effective)
    if run.result_diff != expected_diff:
        raise ProtocolShapeError("ScenarioRun result diff does not match captured side rows")
    return {"baseline": baseline, "effective": effective}


def _side_from_bundle(
    side: Literal["baseline", "effective"],
    bundle: EvaluationRunBundleV0,
    *,
    relation_digest: str,
    capture_bytes: bytes,
) -> ScenarioRunSideV0:
    return ScenarioRunSideV0(
        side=side,
        run_anchor_digest=bundle.run_anchor.anchor_digest,
        result_digest=bundle.run_anchor.result_digest,
        relation_digest=relation_digest,
        capture_bytes_digest=f"sha256:{sha256_hex(capture_bytes)}",
        rows=tuple(
            ScenarioRunRowV0(
                ordinal=row.ordinal,
                row_capture_digest=row.row_capture_digest,
                semantic_row_anchor_digest=bundle.run_anchor.row_anchors[row.ordinal].semantic_anchor_digest,
                claim_digest=row.claim_digest,
                head_scope_digest=row.head_scope_digest,
                values=row.values,
            )
            for row in bundle.rows
        ),
    )


def _scenario_capture_bytes(
    side: Literal["baseline", "effective"],
    bundle: EvaluationRunBundleV0,
) -> bytes:
    """Frame an F4 payload so it cannot be decoded as a public F4 bundle.

    ScenarioRun deliberately uses F4 capture and verification internals, but
    the effective relation may contain caller-declared synthetic witnesses.
    A short, exact Scenario-only frame makes the byte payload consumable only
    by this runtime's source-aware path; it is an API/protocol boundary, not
    cryptographic confidentiality against an in-process attacker.
    """

    if side not in {"baseline", "effective"}:
        raise ProtocolShapeError("ScenarioRun capture side is invalid")
    return _SCENARIO_CAPTURE_MAGIC + side.encode("ascii") + b"\0" + evaluation_run_bundle_bytes(bundle)


def _scenario_capture_from_bytes(
    raw: bytes,
    *,
    expected_side: Literal["baseline", "effective"],
) -> EvaluationRunBundleV0:
    """Decode one exact private Scenario capture frame."""

    if not isinstance(raw, bytes) or not raw.startswith(_SCENARIO_CAPTURE_MAGIC):
        raise ProtocolShapeError("ScenarioRun capture framing is invalid")
    remainder = raw[len(_SCENARIO_CAPTURE_MAGIC) :]
    marker = expected_side.encode("ascii") + b"\0"
    if not remainder.startswith(marker):
        raise ProtocolShapeError("ScenarioRun capture side framing is invalid")
    return evaluation_run_bundle_from_bytes(remainder[len(marker) :])


def _assert_side_matches_bundle(
    side: str,
    summary: ScenarioRunSideV0,
    bundle: EvaluationRunBundleV0,
    *,
    relation_digest: str,
    capture_bytes: bytes,
) -> None:
    expected = _side_from_bundle(
        side,  # type: ignore[arg-type]
        bundle,
        relation_digest=relation_digest,
        capture_bytes=capture_bytes,
    )
    if summary != expected:
        raise ProtocolShapeError("ScenarioRun public side summary does not match private capture")


def _assert_relation_identity(bundle: EvaluationRunBundleV0, expected: str) -> None:
    relation = {
        item.predicate_id: tuple(
            (fact_id, tuple(value.value for value in values))
            for fact_id, values in item.facts
        )
        for item in bundle.relations
    }
    raw = json.dumps(
        {
            "format": "scenario_effective_relation_v0",
            "payload": tuple((pred_id, rows) for pred_id, rows in sorted(relation.items())),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if expected != f"sha256:{sha256_hex(raw)}":
        raise ProtocolShapeError("ScenarioRun captured relation does not match relation digest")


def _assert_premise_inventory(
    bindings: tuple[ScenarioPremiseBindingV0, ...],
    baseline: EvaluationRunBundleV0,
    effective: EvaluationRunBundleV0,
) -> None:
    baseline_index = _facts_by_id(baseline)
    effective_index = _facts_by_id(effective)
    synthetic_ids = {binding.synthetic_witness_id for binding in bindings}
    replaced_ids = {binding.baseline_assertion_id for binding in bindings}
    if len(synthetic_ids) != len(bindings):
        raise ProtocolShapeError("ScenarioRun premise synthetic witnesses are not unique")
    for binding in bindings:
        base = baseline_index.get(binding.baseline_assertion_id)
        synthetic = effective_index.get(binding.synthetic_witness_id)
        if base is None or synthetic is None:
            raise ProtocolShapeError("ScenarioRun premise binding is absent from captured relation")
        if (
            base[0] != binding.predicate_id
            or synthetic[0] != binding.predicate_id
            or tuple(value.value for value in base[1])
            != (binding.entity_ref, binding.baseline_value.value)
            or tuple(value.value for value in synthetic[1])
            != (binding.entity_ref, binding.effective_value.value)
        ):
            raise ProtocolShapeError("ScenarioRun premise binding contradicts captured relation values")
    # Do not rediscover synthetic witnesses from an assertion-id convention.
    # The resolver's sealed binding inventory is the authority.  It describes
    # the *entire* baseline/effective delta: exactly the resolved baseline
    # witnesses disappear, exactly the resolved synthetic witnesses appear,
    # and every untouched witness is byte-for-byte identical.
    baseline_ids = set(baseline_index)
    effective_ids = set(effective_index)
    if effective_ids - baseline_ids != synthetic_ids:
        raise ProtocolShapeError("ScenarioRun synthetic witness inventory is not exact")
    if baseline_ids - effective_ids != replaced_ids:
        raise ProtocolShapeError("ScenarioRun replacement witness inventory is not exact")
    if replaced_ids & effective_ids:
        raise ProtocolShapeError("ScenarioRun effective relation retains a replaced baseline witness")
    if synthetic_ids & baseline_ids:
        raise ProtocolShapeError("ScenarioRun baseline relation contains a synthetic witness")
    for fact_id in baseline_ids & effective_ids:
        if baseline_index[fact_id] != effective_index[fact_id]:
            raise ProtocolShapeError("ScenarioRun changed an undeclared captured witness")


def _facts_by_id(
    bundle: EvaluationRunBundleV0,
) -> dict[str, tuple[str, tuple[Any, ...]]]:
    return {
        fact_id: (relation.predicate_id, values)
        for relation in bundle.relations
        for fact_id, values in relation.facts
    }


def _source_metadata_for_side(
    run: ScenarioRunV0,
    bundle: EvaluationRunBundleV0,
    *,
    side: Literal["baseline", "effective"],
) -> dict[str, dict[str, object]]:
    synthetic = {item.synthetic_witness_id: item for item in run.plan.premise_bindings}
    metadata: dict[str, dict[str, object]] = {}
    for fact_id, (pred_id, _values) in _facts_by_id(bundle).items():
        binding = synthetic.get(fact_id)
        if side == "baseline":
            if binding is not None:
                raise ProtocolShapeError("ScenarioRun baseline side contains hypothesis source")
            metadata[fact_id] = {
                "role": "captured_baseline_relation_witness",
                "origin": "scenario_run_v0",
                "scenario_side": "baseline",
                "ledger_backed_at_capture": True,
                "predicate_id": pred_id,
                "assertion_id": fact_id,
            }
        elif binding is None:
            metadata[fact_id] = {
                "role": "captured_effective_relation_witness",
                "origin": "scenario_run_v0",
                "scenario_side": "effective",
                "ledger_backed_at_capture": True,
                "predicate_id": pred_id,
                "assertion_id": fact_id,
            }
        else:
            metadata[fact_id] = {
                "role": "scenario_hypothesis",
                "origin": "scenario_run_v0",
                "scenario_side": "effective",
                "ledger_backed_at_capture": False,
                "premise_id": binding.premise_id,
                "operation_digest": binding.operation_digest,
                "baseline_assertion_id": binding.baseline_assertion_id,
                "synthetic_witness_id": binding.synthetic_witness_id,
                "predicate_id": pred_id,
                "assertion_id": fact_id,
            }
    return metadata


def _diff_from_bundles(
    baseline: EvaluationRunBundleV0,
    effective: EvaluationRunBundleV0,
) -> ScenarioResultDiffV0:
    return ScenarioResultDiffV0(
        baseline_row_count=len(baseline.rows),
        effective_row_count=len(effective.rows),
        baseline_semantic_rows_digest=_semantic_rows_digest(baseline),
        effective_semantic_rows_digest=_semantic_rows_digest(effective),
        result_changed=_semantic_rows_digest(baseline) != _semantic_rows_digest(effective),
    )


def _semantic_rows_digest(bundle: EvaluationRunBundleV0) -> str:
    tokens = []
    for row, anchor in zip(bundle.rows, bundle.run_anchor.row_anchors, strict=True):
        tokens.append(
            sha256_token(
                canonical_bytes_for_evaluate(
                    "scenario_query_row_semantic_v0",
                    {
                        "kind": anchor.claim_kind,
                        "claim_digest": row.claim_digest,
                        "bindings": _displayed_values(row.values),
                        "closed_head_digest": row.head_scope_digest,
                        "certainty": _certainty_payload(row.certainty),
                    },
                )
            )
        )
    return sha256_token(
        canonical_bytes_for_evaluate("scenario_query_row_multiset_v0", tuple(sorted(tokens)))
    )


def _displayed_values(values: Sequence[tuple[str, Any]]) -> dict[str, object]:
    return {
        alias: (
            {"kind": "entity_ref", "value": value.value}
            if value.tag == "entity_ref"
            else {"kind": "literal", "tag": value.tag, "value": value.value}
        )
        for alias, value in values
    }


def _certainty_payload(value: tuple[str, str, str] | None) -> dict[str, object] | None:
    if value is None:
        return None
    import struct

    return {
        "lo": struct.unpack(">d", int(value[0], 16).to_bytes(8, "big"))[0],
        "hi": struct.unpack(">d", int(value[1], 16).to_bytes(8, "big"))[0],
        "kind": value[2],
    }


def _plan_to_wire(value: ScenarioRunPlanV0) -> dict[str, object]:
    return {
        "query_digest": value.query_digest,
        "target_digest": value.target_digest,
        "policy_digest": value.policy_digest,
        "address_space_digest": value.address_space_digest,
        "schema_digest": value.schema_digest,
        "base_view_digest": value.base_view_digest,
        "baseline_relation_digest": value.baseline_relation_digest,
        "effective_relation_digest": value.effective_relation_digest,
        "scenario_kind": value.scenario_kind,
        "premise_bindings": [_binding_to_wire(item) for item in value.premise_bindings],
        "engine": value.engine,
        "config": value.config,
        "ledger_premise_policy": value.ledger_premise_policy,
        "overlay_kind": value.overlay_kind,
        "plan_digest": value.plan_digest,
    }


def _plan_from_wire(value: object) -> ScenarioRunPlanV0:
    if not isinstance(value, dict):
        raise ProtocolShapeError("ScenarioRun plan wire shape is invalid")
    required = {
        "query_digest", "target_digest", "policy_digest", "address_space_digest",
        "schema_digest", "base_view_digest", "baseline_relation_digest",
        "effective_relation_digest", "scenario_kind", "premise_bindings", "engine",
        "config", "ledger_premise_policy", "overlay_kind", "plan_digest",
    }
    if set(value) != required or not isinstance(value["premise_bindings"], list):
        raise ProtocolShapeError("ScenarioRun plan wire fields are invalid")
    plan = ScenarioRunPlanV0(
        query_digest=value["query_digest"], target_digest=value["target_digest"],
        policy_digest=value["policy_digest"], address_space_digest=value["address_space_digest"],
        schema_digest=value["schema_digest"], base_view_digest=value["base_view_digest"],
        baseline_relation_digest=value["baseline_relation_digest"],
        effective_relation_digest=value["effective_relation_digest"],
        scenario_kind=value["scenario_kind"],
        premise_bindings=tuple(_binding_from_wire(item) for item in value["premise_bindings"]),
        engine=value["engine"], config=value["config"],
        ledger_premise_policy=value["ledger_premise_policy"], overlay_kind=value["overlay_kind"],
    )
    if plan.plan_digest != value["plan_digest"]:
        raise ProtocolShapeError("ScenarioRun plan digest does not match content")
    return plan


def _binding_to_wire(value: ScenarioPremiseBindingV0) -> dict[str, object]:
    return {
        "premise_id": value.premise_id,
        "operation_digest": value.operation_digest,
        "origin_kind": value.origin_kind,
        "entity_ref": value.entity_ref,
        "field": [value.field.entity_type, value.field.field_name],
        "predicate_id": value.predicate_id,
        "baseline_assertion_id": value.baseline_assertion_id,
        "synthetic_witness_id": value.synthetic_witness_id,
        "baseline_value": [value.baseline_value.tag, value.baseline_value.value],
        "effective_value": [value.effective_value.tag, value.effective_value.value],
        "semantic_value_changed": value.semantic_value_changed,
        "binding_digest": value.binding_digest,
    }


def _binding_from_wire(value: object) -> ScenarioPremiseBindingV0:
    if not isinstance(value, dict):
        raise ProtocolShapeError("ScenarioRun premise binding wire shape is invalid")
    required = {
        "premise_id", "operation_digest", "origin_kind", "entity_ref", "field",
        "predicate_id", "baseline_assertion_id", "synthetic_witness_id", "baseline_value",
        "effective_value", "semantic_value_changed", "binding_digest",
    }
    if set(value) != required or not all(
        isinstance(value[name], list) and len(value[name]) == 2
        for name in ("field", "baseline_value", "effective_value")
    ):
        raise ProtocolShapeError("ScenarioRun premise binding fields are invalid")
    binding = ScenarioPremiseBindingV0(
        premise_id=value["premise_id"], operation_digest=value["operation_digest"],
        origin_kind=value["origin_kind"], entity_ref=value["entity_ref"],
        field=FieldPath(*value["field"]), predicate_id=value["predicate_id"],
        baseline_assertion_id=value["baseline_assertion_id"],
        synthetic_witness_id=value["synthetic_witness_id"],
        baseline_value=ScenarioScalarValueV0(*value["baseline_value"]),
        effective_value=ScenarioScalarValueV0(*value["effective_value"]),
        semantic_value_changed=value["semantic_value_changed"],
    )
    if binding.binding_digest != value["binding_digest"]:
        raise ProtocolShapeError("ScenarioRun premise binding digest does not match content")
    return binding


def _side_to_wire(value: ScenarioRunSideV0) -> dict[str, object]:
    return {
        "side": value.side,
        "run_anchor_digest": value.run_anchor_digest,
        "result_digest": value.result_digest,
        "relation_digest": value.relation_digest,
        "capture_bytes_digest": value.capture_bytes_digest,
        "rows": [_row_to_wire(item) for item in value.rows],
        "side_digest": value.side_digest,
    }


def _side_from_wire(value: object) -> ScenarioRunSideV0:
    if not isinstance(value, dict):
        raise ProtocolShapeError("ScenarioRun side wire shape is invalid")
    required = {
        "side", "run_anchor_digest", "result_digest", "relation_digest",
        "capture_bytes_digest", "rows", "side_digest",
    }
    if set(value) != required or not isinstance(value["rows"], list):
        raise ProtocolShapeError("ScenarioRun side wire fields are invalid")
    side = ScenarioRunSideV0(
        side=value["side"], run_anchor_digest=value["run_anchor_digest"],
        result_digest=value["result_digest"], relation_digest=value["relation_digest"],
        capture_bytes_digest=value["capture_bytes_digest"],
        rows=tuple(_row_from_wire(item) for item in value["rows"]),
    )
    if side.side_digest != value["side_digest"]:
        raise ProtocolShapeError("ScenarioRun side digest does not match content")
    return side


def _row_to_wire(value: ScenarioRunRowV0) -> dict[str, object]:
    return {
        "ordinal": value.ordinal,
        "row_capture_digest": value.row_capture_digest,
        "semantic_row_anchor_digest": value.semantic_row_anchor_digest,
        "claim_digest": value.claim_digest,
        "head_scope_digest": value.head_scope_digest,
        "values": [[alias, item.tag, item.value] for alias, item in value.values],
        "row_digest": value.row_digest,
    }


def _row_from_wire(value: object) -> ScenarioRunRowV0:
    if not isinstance(value, dict):
        raise ProtocolShapeError("ScenarioRun row wire shape is invalid")
    required = {
        "ordinal", "row_capture_digest", "semantic_row_anchor_digest", "claim_digest",
        "head_scope_digest", "values", "row_digest",
    }
    if set(value) != required or not isinstance(value["values"], list) or not all(
        isinstance(item, list) and len(item) == 3 for item in value["values"]
    ):
        raise ProtocolShapeError("ScenarioRun row wire fields are invalid")
    row = ScenarioRunRowV0(
        ordinal=value["ordinal"], row_capture_digest=value["row_capture_digest"],
        semantic_row_anchor_digest=value["semantic_row_anchor_digest"],
        claim_digest=value["claim_digest"], head_scope_digest=value["head_scope_digest"],
        values=tuple((item[0], _value_from_wire(item[1:])) for item in value["values"]),
    )
    if row.row_digest != value["row_digest"]:
        raise ProtocolShapeError("ScenarioRun row digest does not match content")
    return row


def _value_from_wire(value: object) -> Any:
    from factgraph.application.protocol.evaluation_run_bundle import EvaluationRunValueV0

    if not isinstance(value, list) or len(value) != 2:
        raise ProtocolShapeError("ScenarioRun row value wire shape is invalid")
    return EvaluationRunValueV0(value[0], value[1])


def _diff_to_wire(value: ScenarioResultDiffV0) -> dict[str, object]:
    return {
        "baseline_row_count": value.baseline_row_count,
        "effective_row_count": value.effective_row_count,
        "baseline_semantic_rows_digest": value.baseline_semantic_rows_digest,
        "effective_semantic_rows_digest": value.effective_semantic_rows_digest,
        "result_changed": value.result_changed,
        "diff_digest": value.diff_digest,
    }


def _diff_from_wire(value: object) -> ScenarioResultDiffV0:
    if not isinstance(value, dict) or set(value) != {
        "baseline_row_count", "effective_row_count", "baseline_semantic_rows_digest",
        "effective_semantic_rows_digest", "result_changed", "diff_digest",
    }:
        raise ProtocolShapeError("ScenarioRun diff wire shape is invalid")
    diff = ScenarioResultDiffV0(
        value["baseline_row_count"], value["effective_row_count"],
        value["baseline_semantic_rows_digest"], value["effective_semantic_rows_digest"],
        value["result_changed"],
    )
    if diff.diff_digest != value["diff_digest"]:
        raise ProtocolShapeError("ScenarioRun diff digest does not match content")
    return diff


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError("ScenarioRun binary field is invalid")
    try:
        raw = base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ProtocolShapeError("ScenarioRun binary field is malformed") from exc
    if _b64(raw) != value:
        raise ProtocolShapeError("ScenarioRun binary field is non-canonical")
    return raw


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError, RecursionError) as exc:
        raise ProtocolShapeError("ScenarioRun payload cannot be canonical JSON") from exc


def _unique_json_object(items: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in items:
        if key in output:
            raise ProtocolShapeError(f"ScenarioRun JSON has duplicate key {key!r}")
        output[key] = value
    return output


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(f"ScenarioRun JSON contains non-standard constant {value!r}")


def _json_depth(value: object, depth: int = 0) -> int:
    if isinstance(value, dict):
        return max([depth, *(_json_depth(item, depth + 1) for item in value.values())])
    if isinstance(value, list):
        return max([depth, *(_json_depth(item, depth + 1) for item in value)])
    return depth


__all__ = [
    "MAX_SCENARIO_RUN_BYTES",
    "_assert_scenario_run_current",
    "build_scenario_run_v0",
    "explain_scenario_run_v0",
    "scenario_run_bytes",
    "scenario_run_from_bytes",
    "verify_scenario_run_v0",
]
