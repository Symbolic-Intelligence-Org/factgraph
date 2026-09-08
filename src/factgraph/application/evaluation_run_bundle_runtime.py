from __future__ import annotations

import base64
import json
import math
import struct
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from typing import Any, cast

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.rules.where_ast import (
    WhereASTError,
    lower_ast_to_where_ir,
    parse_where_ir_to_ast,
)
from factgraph.core.rules.where_ast_validate import WhereASTValidationError, validate_where_ast
from factgraph.core.rules.where_eval import _where_ast_gate_enabled
from factgraph.core.schema.schema_ir import (
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
    schema_digest,
)
from factgraph.core.store._evaluate import _native_where_dependency_predicates
from factgraph.core.store._support import (
    ProjectedFact,
    ProofReceipt,
    binding_dict_from_items,
    compute_support_digest,
    normalize_binding_items,
    normalize_detail_items,
    support_artifact_bytes,
    support_artifact_from_dict,
)
from factgraph.core.store._support_capture import build_support_artifact_for_binding

from .evaluation_query_runtime import (
    CompiledEvaluationQueryV0,
    _assert_compiled_evaluation_query_current,
)
from .protocol.common import ProtocolShapeError
from .protocol.derivation import CompiledDerivationPlan
from .protocol.evaluate_result import (
    EvaluateResult,
    canonical_bytes_for_evaluate,
    claim_digest_for,
)
from .protocol.evaluation_query import EvaluationQueryFieldNavigationV0
from .protocol.evaluation_run import (
    EvaluationRunAnchorV0,
    EvaluationRunBindingV0,
    EvaluationRunExecutionProfileV0,
    EvaluationRunNavigationSelectionV0,
    EvaluationRunRowAnchorV0,
    EvaluationRunRulePinV0,
    EvaluationRunSelectionV0,
    EvaluationRunSummaryAnchorV0,
    EvaluationRunTargetV0,
)
from .protocol.evaluation_run_bundle import (
    EvaluationRunBundleV0,
    EvaluationRunExecutionContractV0,
    EvaluationRunNativePlanV0,
    EvaluationRunProjectionRowV0,
    EvaluationRunRelationV0,
    EvaluationRunValueV0,
    _token,
)
from .protocol.policy import (
    PolicyCompareStructureNodeV0,
    PolicyConditionLoweredRefV0,
    PolicyFieldNavigation,
    PolicyLineage,
    PolicyLiteral,
    PolicyLoweredRef,
    PolicyNodeLineage,
    PolicyStructureNodeV0,
    PolicyStructureV0,
)
from .protocol.rule_expr_lowering import _materialize_adapter_derivation_plan
from .protocol.schema_runtime import FieldPath
from .protocol.semantic_address import SemanticPortAddress

MAX_EVALUATION_RUN_BUNDLE_BYTES = 1024 * 1024
MAX_EVALUATION_RUN_BUNDLE_PREDICATES = 128
MAX_EVALUATION_RUN_BUNDLE_FACTS = 20_000
MAX_EVALUATION_RUN_BUNDLE_ROWS = 1_000
MAX_EVALUATION_RUN_BUNDLE_VALUES = 64
MAX_EVALUATION_RUN_BUNDLE_DEPTH = 64
_MAX_COMPONENT_BYTES = MAX_EVALUATION_RUN_BUNDLE_BYTES


def _build_evaluation_run_bundle_v0(
    compiled_query: CompiledEvaluationQueryV0,
    result: EvaluateResult,
    *,
    materialized_plan: CompiledDerivationPlan,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
    proof_receipts: Mapping[str, ProofReceipt],
) -> EvaluationRunBundleV0:
    """Capture a complete native Query run artifact; this does not replay it."""
    _assert_compiled_evaluation_query_current(compiled_query)
    if not isinstance(result, EvaluateResult) or result.run_anchor is None:
        raise ProtocolShapeError("EvaluationRun bundle requires an anchored EvaluateResult")
    if result.engine != "native" or result.fingerprint.config_digest is not None:
        raise ProtocolShapeError("EvaluationRun bundle v0 captures native/config-none runs only")
    expected_plan, _ = _materialize_adapter_derivation_plan(
        compiled_query._lowering_plan, engine="native"
    )
    if (
        not isinstance(materialized_plan, CompiledDerivationPlan)
        or materialized_plan != expected_plan
    ):
        raise ProtocolShapeError("materialized plan is not the exact native Query plan")
    schema_bytes = canonicalize_schema_ir_jcs(schema_ir)
    schema_token = schema_digest(schema_ir)
    if schema_token != compiled_query.schema_digest:
        raise ProtocolShapeError("captured schema does not match compiled Query")
    schema_bytes_digest = f"sha256:{sha256_hex(schema_bytes)}"
    schema_capture_digest = _token(
        "evaluation_run_schema_capture_v0", (schema_token, schema_bytes_digest)
    )
    native_plan = _capture_native_plan(materialized_plan)
    binding_values = tuple(
        EvaluationRunValueV0(
            cast(Any, item.value_type),
            cast(Any, item.normalized_value),
        )
        for item in compiled_query.bindings
    )
    dependencies = _native_where_dependency_predicates(materialized_plan.body_ir)
    relations = _capture_relations(schema_ir, effective_relations, dependencies)
    rows = _capture_rows(result, compiled_query.selections, proof_receipts)
    contract = EvaluationRunExecutionContractV0(
        "native",
        "none",
        "empty",
        "enabled" if _where_ast_gate_enabled() else "disabled",
        "materialized_native_where_ir_v0",
    )
    query_capture_digest = _token(
        "evaluation_run_query_capture_v0",
        (
            compiled_query.query_digest,
            result.run_anchor.bindings,
            binding_values,
            result.run_anchor.selections,
        ),
    )
    relations_digest = _token(
        "evaluation_run_relations_capture_v0",
        (
            "plan_dependency_complete",
            dependencies,
            relations,
        ),
    )
    rows_digest = _token(
        "evaluation_run_rows_capture_v0", tuple(row.row_capture_digest for row in rows)
    )
    bundle_digest = _token(
        "evaluation_run_bundle_v0",
        (
            result.run_anchor.anchor_digest,
            query_capture_digest,
            native_plan.plan_digest,
            schema_capture_digest,
            relations_digest,
            rows_digest,
            contract,
            "digest_sealed_not_authenticated",
            "unverified",
            "contains_captured_typed_values",
            "caller_managed",
            "captured_proof_receipts_available",
            "not_implemented",
        ),
    )
    bundle = EvaluationRunBundleV0(
        result.run_anchor,
        compiled_query.query_digest,
        binding_values,
        native_plan,
        schema_bytes,
        schema_bytes_digest,
        schema_capture_digest,
        relations,
        rows,
        "plan_dependency_complete",
        dependencies,
        contract,
        "digest_sealed_not_authenticated",
        "unverified",
        "contains_captured_typed_values",
        "caller_managed",
        "captured_proof_receipts_available",
        "not_implemented",
        query_capture_digest,
        relations_digest,
        rows_digest,
        bundle_digest,
    )
    # Encoding performs the complete validation once, including the size cap.
    evaluation_run_bundle_bytes(bundle)
    return bundle


def _canonical_json_bytes(value: Any, *, label: str) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError, RecursionError) as exc:
        raise ProtocolShapeError(f"{label} cannot be represented as canonical JSON") from exc


def evaluation_run_bundle_bytes(bundle: EvaluationRunBundleV0) -> bytes:
    _assert_evaluation_run_bundle_current(bundle)
    raw = _canonical_json_bytes(_wire(bundle), label="EvaluationRun bundle")
    if len(raw) > MAX_EVALUATION_RUN_BUNDLE_BYTES:
        raise ProtocolShapeError("EvaluationRun bundle exceeds maximum encoded size")
    return raw


def evaluation_run_bundle_from_bytes(raw: bytes) -> EvaluationRunBundleV0:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EVALUATION_RUN_BUNDLE_BYTES:
        raise ProtocolShapeError("EvaluationRun bundle bytes are empty or exceed maximum size")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("EvaluationRun bundle is not valid UTF-8 JSON") from exc
    if _json_depth(payload) > MAX_EVALUATION_RUN_BUNDLE_DEPTH:
        raise ProtocolShapeError("EvaluationRun bundle exceeds maximum JSON depth")
    if _canonical_json_bytes(payload, label="EvaluationRun bundle") != raw:
        raise ProtocolShapeError("EvaluationRun bundle JSON is not canonical")
    bundle = _unwire(payload)
    if not isinstance(bundle, EvaluationRunBundleV0):
        raise ProtocolShapeError("EvaluationRun bundle root type is invalid")
    _assert_evaluation_run_bundle_current(bundle)
    return bundle


def _capture_native_plan(plan: CompiledDerivationPlan) -> EvaluationRunNativePlanV0:
    if (
        len(plan.heads) != 1
        or plan.body_confidence is not None
        or plan.head_spec is not None
        or plan.engine_ext is not None
        or plan.engine_options
    ):
        raise ProtocolShapeError("native Query plan contains unsupported execution extensions")
    where_payload = _where_to_wire(plan.body_ir)
    where_bytes = _canonical_json_bytes(where_payload, label="native where IR")
    if len(where_bytes) > _MAX_COMPONENT_BYTES:
        raise ProtocolShapeError("native where IR exceeds maximum component size")
    decoded = _where_from_wire(where_payload)
    if decoded != plan.body_ir:
        raise ProtocolShapeError("native where IR tagged encoding is not exact")
    where_digest = f"sha256:{sha256_hex(where_bytes)}"
    head = plan.heads[0]
    plan_digest = _token(
        "evaluation_run_native_plan_v0",
        (
            plan.derivation_id,
            plan.version,
            head.target_pred_id,
            head.head_var_names,
            where_digest,
        ),
    )
    return EvaluationRunNativePlanV0(
        plan.derivation_id,
        plan.version,
        head.target_pred_id,
        head.head_var_names,
        where_bytes,
        where_digest,
        plan_digest,
    )


def _capture_relations(
    schema_ir: dict[str, Any],
    relations: Mapping[str, Sequence[ProjectedFact]],
    dependencies: tuple[str, ...],
) -> tuple[EvaluationRunRelationV0, ...]:
    schema = ensure_schema_ir(schema_ir)
    specs = {
        item["pred_id"]: tuple(arg["type_domain"] for arg in item["arg_specs"])
        for item in schema["predicates"]
    }
    if len(dependencies) > MAX_EVALUATION_RUN_BUNDLE_PREDICATES:
        raise ProtocolShapeError("EvaluationRun dependency predicate limit exceeded")
    if set(dependencies) - set(specs) or set(relations) != set(dependencies):
        raise ProtocolShapeError(
            "effective relation inventory must exactly cover plan dependencies, including empty ones"
        )
    captured: list[EvaluationRunRelationV0] = []
    fact_count = 0
    for pred_id in dependencies:
        value_types = specs[pred_id]
        facts: list[tuple[str, tuple[EvaluationRunValueV0, ...]]] = []
        rows = relations[pred_id]
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            raise ProtocolShapeError("effective relation rows must be a sequence")
        for row in rows:
            fact_count += 1
            if fact_count > MAX_EVALUATION_RUN_BUNDLE_FACTS:
                raise ProtocolShapeError("EvaluationRun effective fact limit exceeded")
            if not isinstance(row, ProjectedFact) or len(row.fact_tuple) != len(value_types):
                raise ProtocolShapeError("effective relation fact does not match schema arity")
            if len(value_types) > MAX_EVALUATION_RUN_BUNDLE_VALUES:
                raise ProtocolShapeError("EvaluationRun fact value limit exceeded")
            values = tuple(
                EvaluationRunValueV0(tag, value)  # type: ignore[arg-type]
                for tag, value in zip(value_types, row.fact_tuple, strict=True)
            )
            facts.append((row.asrt_id, values))
        captured.append(EvaluationRunRelationV0(pred_id, value_types, tuple(facts)))
    return tuple(captured)


def _capture_rows(
    result: EvaluateResult,
    selections: Sequence[Any],
    receipts: Mapping[str, ProofReceipt],
) -> tuple[EvaluationRunProjectionRowV0, ...]:
    if len(result.rows) > MAX_EVALUATION_RUN_BUNDLE_ROWS:
        raise ProtocolShapeError("EvaluationRun projection row limit exceeded")
    if len(selections) > MAX_EVALUATION_RUN_BUNDLE_VALUES:
        raise ProtocolShapeError("EvaluationRun projection value limit exceeded")
    if set(receipts) != {row.row_id for row in result.rows}:
        raise ProtocolShapeError("ProofReceipt inventory must exactly match projection rows")
    rows: list[EvaluationRunProjectionRowV0] = []
    assert result.run_anchor is not None
    for ordinal, (row, anchor) in enumerate(
        zip(result.rows, result.run_anchor.row_anchors, strict=True)
    ):
        values = tuple(
            (
                selection.alias,
                _projection_value(selection.value_type, row.bindings.get(selection.alias)),
            )
            for selection in selections
        )
        receipt = receipts[row.row_id]
        if not isinstance(receipt, ProofReceipt) or receipt.kind != "native_binding_v1":
            raise ProtocolShapeError("EvaluationRun bundle requires native ProofReceipts")
        receipt_bytes = support_artifact_bytes(receipt)
        _validate_proof_receipt_bytes(receipt_bytes)
        receipt_digest = compute_support_digest(receipt)
        certainty = _capture_certainty(row.certainty)
        row_digest = _token(
            "evaluation_run_projection_row_v0",
            (
                ordinal,
                row.row_id,
                anchor.claim_digest,
                anchor.head_scope_digest,
                certainty,
                anchor.certainty_digest,
                values,
                receipt_digest,
            ),
        )
        rows.append(
            EvaluationRunProjectionRowV0(
                ordinal,
                row.row_id,
                anchor.claim_digest,
                anchor.head_scope_digest,
                certainty,
                anchor.certainty_digest,
                values,
                receipt_bytes,
                receipt_digest,
                row_digest,
            )
        )
    return tuple(rows)


def _projection_value(value_type: str, displayed: object) -> EvaluationRunValueV0:
    if not isinstance(displayed, Mapping):
        raise ProtocolShapeError("captured projection value is not typed")
    if value_type == "entity_ref":
        if set(displayed) != {"kind", "value"} or displayed.get("kind") != "entity_ref":
            raise ProtocolShapeError("captured entity_ref projection is malformed")
    elif (
        set(displayed) != {"kind", "tag", "value"}
        or displayed.get("kind") != "literal"
        or displayed.get("tag") != value_type
    ):
        raise ProtocolShapeError("captured literal projection is malformed")
    return EvaluationRunValueV0(value_type, displayed["value"])  # type: ignore[arg-type]


def _capture_certainty(value: object) -> tuple[str, str, str] | None:
    if value is None:
        return None
    lo, hi, kind = (
        getattr(value, "lo", None),
        getattr(value, "hi", None),
        getattr(value, "kind", None),
    )
    if (
        not isinstance(lo, float)
        or not isinstance(hi, float)
        or kind not in {"boolean", "probabilistic", "possibilistic"}
    ):
        raise ProtocolShapeError("captured certainty bounds are malformed")
    return (
        f"0x{struct.unpack('>Q', struct.pack('>d', 0.0 if lo == 0.0 else lo))[0]:016x}",
        f"0x{struct.unpack('>Q', struct.pack('>d', 0.0 if hi == 0.0 else hi))[0]:016x}",
        kind,
    )


def _assert_evaluation_run_bundle_current(
    bundle: EvaluationRunBundleV0,
    *,
    rebuild_receipts: bool = True,
) -> None:
    """Validate bundle consistency, optionally deferring bounded receipt rebuilding."""
    if not isinstance(rebuild_receipts, bool):
        raise ProtocolShapeError("EvaluationRun receipt rebuild flag must be bool")
    if not isinstance(bundle, EvaluationRunBundleV0):
        raise ProtocolShapeError("bundle must be EvaluationRunBundleV0")
    EvaluationRunBundleV0.__post_init__(bundle)
    where = _validate_native_where_bytes(bundle.native_plan.where_bytes)
    try:
        schema = json.loads(
            bundle.schema_bytes.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("captured schema bytes are not JSON") from exc
    if _json_depth(schema) > MAX_EVALUATION_RUN_BUNDLE_DEPTH:
        raise ProtocolShapeError("captured schema JSON exceeds maximum depth")
    if (
        canonicalize_schema_ir_jcs(schema) != bundle.schema_bytes
        or schema_digest(schema) != bundle.run_anchor.target.schema_digest
    ):
        raise ProtocolShapeError("captured schema bytes or digest are not canonical")
    specs = {
        item["pred_id"]: tuple(arg["type_domain"] for arg in item["arg_specs"])
        for item in schema["predicates"]
    }
    captured_specs = {item.predicate_id: item.value_types for item in bundle.relations}
    if set(captured_specs) != set(bundle.dependency_predicate_ids) or any(
        specs.get(pred_id) != value_types for pred_id, value_types in captured_specs.items()
    ):
        raise ProtocolShapeError("captured relation inventory does not match captured schema")
    if _native_where_dependency_predicates(where) != bundle.dependency_predicate_ids:
        raise ProtocolShapeError(
            "captured dependency predicate inventory does not match native plan"
        )
    if (
        len(bundle.relations) > MAX_EVALUATION_RUN_BUNDLE_PREDICATES
        or sum(len(item.facts) for item in bundle.relations) > MAX_EVALUATION_RUN_BUNDLE_FACTS
    ):
        raise ProtocolShapeError("captured relation limits are exceeded")
    if (
        len(bundle.binding_values) > MAX_EVALUATION_RUN_BUNDLE_VALUES
        or len(bundle.run_anchor.selections) > MAX_EVALUATION_RUN_BUNDLE_VALUES
        or len(bundle.native_plan.head_var_names) > MAX_EVALUATION_RUN_BUNDLE_VALUES
        or len(bundle.run_anchor.selections) != len(bundle.native_plan.head_var_names)
        or any(
            len(relation.value_types) > MAX_EVALUATION_RUN_BUNDLE_VALUES
            or any(
                len(values) > MAX_EVALUATION_RUN_BUNDLE_VALUES
                for _asrt_id, values in relation.facts
            )
            for relation in bundle.relations
        )
    ):
        raise ProtocolShapeError("captured value width limit is exceeded")
    if len(bundle.rows) > MAX_EVALUATION_RUN_BUNDLE_ROWS:
        raise ProtocolShapeError("captured projection row limit is exceeded")
    captured_relation = {
        relation.predicate_id: [
            ProjectedFact(
                asrt_id=asrt_id,
                fact_tuple=tuple(value.value for value in values),
            )
            for asrt_id, values in relation.facts
        ]
        for relation in bundle.relations
    }
    assertion_ids = {fact.asrt_id for facts in captured_relation.values() for fact in facts}
    assertion_by_id: dict[str, tuple[str, tuple[tuple[str, object], ...]]] = {}
    assertion_ids_by_fact: dict[
        tuple[str, tuple[tuple[str, object], ...]], tuple[str, ...]
    ] = {}
    for relation in bundle.relations:
        grouped: dict[tuple[tuple[str, object], ...], list[str]] = {}
        for asrt_id, values in relation.facts:
            tagged_fact = tuple((value.tag, value.value) for value in values)
            assertion_by_id[asrt_id] = (relation.predicate_id, tagged_fact)
            grouped.setdefault(tagged_fact, []).append(asrt_id)
        for tagged_fact, assertion_ids_for_fact in grouped.items():
            assertion_ids_by_fact[(relation.predicate_id, tagged_fact)] = tuple(
                sorted(assertion_ids_for_fact)
            )
    for row, anchor in zip(bundle.rows, bundle.run_anchor.row_anchors, strict=True):
        if len(row.values) > MAX_EVALUATION_RUN_BUNDLE_VALUES:
            raise ProtocolShapeError("captured projection value limit is exceeded")
        displayed = {
            alias: (
                {"kind": "entity_ref", "value": value.value}
                if value.tag == "entity_ref"
                else {"kind": "literal", "tag": value.tag, "value": value.value}
            )
            for alias, value in row.values
        }
        if (
            sha256_token(canonical_bytes_for_evaluate("evaluation_run_bindings_v0", displayed))
            != anchor.bindings_digest
        ):
            raise ProtocolShapeError(
                "captured projection values do not match Run row binding digest"
            )
        if (
            claim_digest_for("projection", bundle.run_anchor.projection_head_id, displayed)
            != row.claim_digest
        ):
            raise ProtocolShapeError("captured projection values do not match Run row claim digest")
        receipt = _validate_proof_receipt_bytes(row.proof_receipt_bytes)
        receipt_binding = binding_dict_from_items(receipt.binding_items)
        if receipt.root_result_kind != "fact" or receipt.rule_refs or receipt.rule_ref_edges:
            raise ProtocolShapeError(
                "ProofReceipt execution kind or RuleRef inventory is outside capture v0"
            )
        try:
            bound_head = tuple(
                (value.tag, _canonical_storage_value(value.tag, receipt_binding[name]))
                for name, (_alias, value) in zip(
                    bundle.native_plan.head_var_names,
                    row.values,
                    strict=True,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolShapeError(
                "ProofReceipt does not bind the captured projection head"
            ) from exc
        if bound_head != tuple((value.tag, value.value) for _alias, value in row.values):
            raise ProtocolShapeError(
                "ProofReceipt head bindings do not match the captured projection row"
            )
        selected_case = _validate_receipt_static_consistency(
            receipt,
            where=where,
            value_types_by_predicate=specs,
            assertion_by_id=assertion_by_id,
            assertion_ids_by_fact=assertion_ids_by_fact,
        )
        if rebuild_receipts:
            try:
                rebuilt_receipt = build_support_artifact_for_binding(
                    where=where,
                    binding=receipt_binding,
                    witness_facts=captured_relation,
                    root_result_kind="fact",
                    selected_case_index=selected_case,
                )
            except (TypeError, ValueError) as exc:
                raise ProtocolShapeError(
                    "ProofReceipt cannot be rebuilt from the captured execution relation"
                ) from exc
            if support_artifact_bytes(rebuilt_receipt) != row.proof_receipt_bytes:
                raise ProtocolShapeError(
                    "ProofReceipt does not match the captured plan, bindings, and relation"
                )
        witness_ids = {
            asrt_id for witness in receipt.pred_witnesses for asrt_id in witness.asrt_ids
        }
        if witness_ids - assertion_ids:
            raise ProtocolShapeError(
                "ProofReceipt witness is absent from captured effective relations"
            )


def _canonical_storage_value(tag: str, value: object) -> object:
    if tag == "bytes" and isinstance(value, str):
        value = _decode_b64u(value)
    return claim_args_from_rest_terms([(tag, value)])[0][1]


def _receipt_case_index(receipt: ProofReceipt) -> int:
    keys = [
        *(item.pred_condition_key for item in receipt.pred_witnesses),
        *(item.step_key for item in receipt.non_fact_steps),
    ]
    cases: set[int] = set()
    for key in keys:
        prefix, dot, _rest = key.partition(".")
        if dot != "." or not prefix.startswith("c") or not prefix[1:].isdigit():
            raise ProtocolShapeError("ProofReceipt condition key is malformed")
        cases.add(int(prefix[1:]))
    if len(cases) != 1:
        raise ProtocolShapeError("ProofReceipt must describe exactly one native branch")
    return next(iter(cases))


def _validate_receipt_static_consistency(
    receipt: ProofReceipt,
    *,
    where: list[Any],
    value_types_by_predicate: Mapping[str, tuple[str, ...]],
    assertion_by_id: Mapping[str, tuple[str, tuple[tuple[str, object], ...]]],
    assertion_ids_by_fact: Mapping[
        tuple[str, tuple[tuple[str, object], ...]], tuple[str, ...]
    ],
) -> int:
    """Check receipt-to-plan consistency without repeated relation scans.

    This runs before any verifier early return.  It intentionally validates only
    the receipt's selected branch and its referenced witnesses; rebuilding the
    complete receipt remains separately bounded because it repeatedly traverses
    captured relations.
    """
    selected_case = _receipt_case_index(receipt)
    branches = _where_branches(where)
    if selected_case >= len(branches):
        raise ProtocolShapeError("ProofReceipt selected branch is absent from the native plan")
    branch = branches[selected_case]
    binding_keys = tuple(key for key, _value in receipt.binding_items)
    if len(binding_keys) != len(set(binding_keys)):
        raise ProtocolShapeError("ProofReceipt binding inventory contains duplicate keys")
    binding = binding_dict_from_items(receipt.binding_items)
    expected_predicates: dict[str, tuple[str, tuple[tuple[str, object], ...]]] = {}
    expected_steps: dict[str, tuple[str, str, tuple[tuple[str, Any], ...]]] = {}
    for condition_index, atom in enumerate(branch):
        kind = atom[0]
        if kind == "pred":
            if len(atom) != 3 or not isinstance(atom[1], str) or not isinstance(atom[2], list):
                raise ProtocolShapeError("captured native predicate atom is malformed")
            value_types = value_types_by_predicate.get(atom[1])
            if value_types is None:
                raise ProtocolShapeError("captured predicate is absent from the captured schema")
            grounded = _ground_receipt_terms(atom[2], binding, value_types)
            key = f"c{selected_case}.c{condition_index}:{atom[1]}"
            expected_predicates[key] = (atom[1], grounded)
        else:
            key = f"c{selected_case}.c{condition_index}:{kind}"
            expected_steps[key] = (
                str(kind),
                "no_match" if kind == "not" else "satisfied",
                normalize_detail_items(
                    {
                        "atom_repr": repr(atom),
                        "binding": [
                            [key, value]
                            for key, value in normalize_binding_items(binding)
                        ],
                    }
                ),
            )

    witness_keys = tuple(item.pred_condition_key for item in receipt.pred_witnesses)
    if len(witness_keys) != len(set(witness_keys)):
        raise ProtocolShapeError("ProofReceipt predicate condition keys are not unique")
    witnesses = {item.pred_condition_key: item for item in receipt.pred_witnesses}
    if set(witnesses) != set(expected_predicates):
        raise ProtocolShapeError("ProofReceipt predicate condition inventory does not match branch")
    for key, witness in witnesses.items():
        predicate_id, grounded = expected_predicates[key]
        if not witness.asrt_ids:
            raise ProtocolShapeError("ProofReceipt predicate witness has no captured assertion")
        try:
            expected_assertion_ids = assertion_ids_by_fact.get((predicate_id, grounded), ())
        except TypeError as exc:
            raise ProtocolShapeError(
                "ProofReceipt predicate witness terms cannot be indexed"
            ) from exc
        if witness.asrt_ids != expected_assertion_ids:
            raise ProtocolShapeError(
                "ProofReceipt predicate witness inventory does not match captured branch relation"
            )
        for assertion_id in witness.asrt_ids:
            actual = assertion_by_id.get(assertion_id)
            if actual != (predicate_id, grounded):
                raise ProtocolShapeError(
                    "ProofReceipt predicate witness does not match captured branch relation"
                )

    step_keys = tuple(item.step_key for item in receipt.non_fact_steps)
    if len(step_keys) != len(set(step_keys)):
        raise ProtocolShapeError("ProofReceipt non-fact condition keys are not unique")
    steps = {item.step_key: item for item in receipt.non_fact_steps}
    if set(steps) != set(expected_steps):
        raise ProtocolShapeError("ProofReceipt non-fact condition inventory does not match branch")
    for key, step in steps.items():
        expected_kind, expected_status, expected_details = expected_steps[key]
        if (
            step.kind != expected_kind
            or step.status != expected_status
            or not _type_exact_equal(step.details, expected_details)
        ):
            raise ProtocolShapeError("ProofReceipt non-fact step does not match captured branch")
    return selected_case


def _where_branches(where: list[Any]) -> tuple[list[tuple[Any, ...]], ...]:
    if all(isinstance(item, tuple) and item for item in where):
        return (where,)
    if all(
        isinstance(branch, list)
        and branch
        and all(isinstance(atom, tuple) and atom for atom in branch)
        for branch in where
    ):
        return tuple(where)
    raise ProtocolShapeError("captured native plan branch shape is invalid")


def _ground_receipt_terms(
    terms: list[Any],
    binding: Mapping[str, Any],
    value_types: tuple[str, ...],
) -> tuple[tuple[str, object], ...]:
    if len(terms) != len(value_types):
        raise ProtocolShapeError("captured predicate arity does not match captured schema")
    grounded: list[tuple[str, object]] = []
    for term, value_type in zip(terms, value_types, strict=True):
        if isinstance(term, str) and term.startswith("$"):
            if term not in binding:
                raise ProtocolShapeError("ProofReceipt does not bind captured predicate term")
            raw_value = binding[term]
        else:
            raw_value = term
        try:
            grounded.append((value_type, _canonical_storage_value(value_type, raw_value)))
        except (TypeError, ValueError) as exc:
            raise ProtocolShapeError(
                "ProofReceipt predicate term is incompatible with captured schema"
            ) from exc
    return tuple(grounded)


def _type_exact_equal(left: object, right: object) -> bool:
    """Compare receipt detail values without Python's bool/int coercion."""
    if type(left) is not type(right):
        return False
    if isinstance(left, tuple):
        return len(left) == len(right) and all(
            _type_exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _type_exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if isinstance(left, Mapping):
        return (
            len(left) == len(right)
            and all(
                key in right and _type_exact_equal(value, right[key])
                for key, value in left.items()
            )
        )
    return left == right


def _validate_native_where_bytes(raw: bytes) -> list[Any]:
    if not raw or len(raw) > _MAX_COMPONENT_BYTES:
        raise ProtocolShapeError("native where bytes are empty or exceed maximum size")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("native where bytes are not valid JSON") from exc
    if _json_depth(value) > MAX_EVALUATION_RUN_BUNDLE_DEPTH:
        raise ProtocolShapeError("native where JSON exceeds maximum depth")
    if _canonical_json_bytes(value, label="native where JSON") != raw:
        raise ProtocolShapeError("native where JSON is not canonical")
    return _where_from_wire(value)


def _validate_proof_receipt_bytes(raw: bytes) -> ProofReceipt:
    if not raw or len(raw) > _MAX_COMPONENT_BYTES:
        raise ProtocolShapeError("ProofReceipt bytes are empty or exceed maximum size")
    try:
        row = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("ProofReceipt bytes are not valid JSON") from exc
    if _json_depth(row) > MAX_EVALUATION_RUN_BUNDLE_DEPTH:
        raise ProtocolShapeError("ProofReceipt JSON exceeds maximum depth")
    _keys(
        row,
        {
            "kind",
            "root_result_kind",
            "binding",
            "pred_witnesses",
            "non_fact_steps",
            "rule_refs",
            "rule_ref_edges",
        },
    )
    for item in _list(row["pred_witnesses"]):
        _keys(item, {"pred_condition_key", "asrt_ids"})
    for item in _list(row["non_fact_steps"]):
        _keys(item, {"step_key", "kind", "status", "details"})
    for item in _list(row["rule_ref_edges"]):
        _keys(
            item,
            {
                "ruleref_condition_key",
                "rule_ref_id",
                "rule_ref_version",
                "child_support_digest",
                "unresolved_reason",
            },
        )
    try:
        artifact = support_artifact_from_dict(row)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolShapeError("ProofReceipt payload is malformed") from exc
    if artifact.kind != "native_binding_v1" or support_artifact_bytes(artifact) != raw:
        raise ProtocolShapeError("ProofReceipt is non-native or non-canonical")
    return artifact


# Exact list/tuple/scalar tags are decoded first, then the existing native AST
# parser and validator are the grammar oracle. No repr/pickle/arbitrary JSON path.
def _where_to_wire(raw: list[Any]) -> object:
    _validate_where_ir(raw)
    return _ir_to_wire(raw, 0)


def _where_from_wire(value: object) -> list[Any]:
    raw = _ir_from_wire(value, 0)
    if not isinstance(raw, list):
        raise ProtocolShapeError("native where root must decode to list")
    _validate_where_ir(raw)
    return raw


def _validate_where_ir(raw: list[Any]) -> None:
    try:
        ast = parse_where_ir_to_ast(raw)
        validate_where_ast(ast, mode="python", capabilities={"allow_ruleref": False})
        if lower_ast_to_where_ir(ast) != raw:
            raise ProtocolShapeError("native where IR is not canonical")
    except (WhereASTError, WhereASTValidationError, TypeError, ValueError) as exc:
        raise ProtocolShapeError("native where IR is outside the whitelisted grammar") from exc


def _ir_to_wire(value: object, depth: int) -> object:
    if depth > MAX_EVALUATION_RUN_BUNDLE_DEPTH:
        raise ProtocolShapeError("native where IR exceeds maximum depth")
    if isinstance(value, tuple):
        return {"$tuple": [_ir_to_wire(item, depth + 1) for item in value]}
    if isinstance(value, list):
        return {"$list": [_ir_to_wire(item, depth + 1) for item in value]}
    if isinstance(value, bytes):
        return {"$bytes_b64u": base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolShapeError("native where float constant must be finite")
        bits = struct.unpack(">Q", struct.pack(">d", 0.0 if value == 0.0 else value))[0]
        return {"$float64": f"0x{bits:016x}"}
    if (
        value is None
        or isinstance(value, (str, bool))
        or (isinstance(value, int) and not isinstance(value, bool))
    ):
        if isinstance(value, int) and not isinstance(value, bool):
            claim_args_from_rest_terms([("int", value)])
        return {"$scalar": value}
    raise ProtocolShapeError("native where constant type is outside the whitelisted grammar")


def _ir_from_wire(value: object, depth: int) -> object:
    if depth > MAX_EVALUATION_RUN_BUNDLE_DEPTH:
        raise ProtocolShapeError("native where IR exceeds maximum depth")
    row = _map(value)
    if set(row) == {"$tuple"}:
        return tuple(_ir_from_wire(item, depth + 1) for item in _list(row["$tuple"]))
    if set(row) == {"$list"}:
        return [_ir_from_wire(item, depth + 1) for item in _list(row["$list"])]
    if set(row) == {"$bytes_b64u"}:
        return _decode_b64u(_str(row["$bytes_b64u"]))
    if set(row) == {"$float64"}:
        token = _str(row["$float64"])
        if (
            len(token) == 18
            and token.startswith("0x")
            and token == token.lower()
            and token != "0x8000000000000000"
        ):
            try:
                hexadecimal_payload = token[2:]
                number = struct.unpack(">d", int(hexadecimal_payload, 16).to_bytes(8, "big"))[0]
            except (ValueError, OverflowError) as exc:
                raise ProtocolShapeError("native where float is malformed") from exc
            if math.isfinite(number):
                return 0.0 if number == 0.0 else number
    if set(row) == {"$scalar"}:
        scalar = row["$scalar"]
        if scalar is None or isinstance(scalar, (str, bool)):
            return scalar
        if isinstance(scalar, int) and not isinstance(scalar, bool):
            claim_args_from_rest_terms([("int", scalar)])
            return scalar
    raise ProtocolShapeError("native where tagged value is malformed")


_WIRE_TYPES = {
    cls.__name__: cls
    for cls in (
        SemanticPortAddress,
        FieldPath,
        PolicyFieldNavigation,
        PolicyLiteral,
        EvaluationQueryFieldNavigationV0,
        PolicyStructureNodeV0,
        PolicyCompareStructureNodeV0,
        PolicyStructureV0,
        PolicyLoweredRef,
        PolicyConditionLoweredRefV0,
        PolicyNodeLineage,
        PolicyLineage,
        EvaluationRunRulePinV0,
        EvaluationRunTargetV0,
        EvaluationRunBindingV0,
        EvaluationRunSelectionV0,
        EvaluationRunNavigationSelectionV0,
        EvaluationRunExecutionProfileV0,
        EvaluationRunRowAnchorV0,
        EvaluationRunSummaryAnchorV0,
        EvaluationRunAnchorV0,
        EvaluationRunValueV0,
        EvaluationRunNativePlanV0,
        EvaluationRunRelationV0,
        EvaluationRunProjectionRowV0,
        EvaluationRunExecutionContractV0,
        EvaluationRunBundleV0,
    )
}


def _wire(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        cls = type(value)
        if cls.__name__ not in _WIRE_TYPES or _WIRE_TYPES[cls.__name__] is not cls:
            raise ProtocolShapeError("EvaluationRun bundle contains unregistered DTO")
        return {
            "$type": cls.__name__,
            "fields": {
                item.name: _wire(getattr(value, item.name)) for item in fields(value) if item.init
            },
        }
    if isinstance(value, tuple):
        return {"$tuple": [_wire(item) for item in value]}
    if isinstance(value, bytes):
        return {"$bytes_b64u": base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")}
    if (
        value is None
        or isinstance(value, (str, bool))
        or (isinstance(value, int) and not isinstance(value, bool))
    ):
        return value
    raise ProtocolShapeError(
        f"EvaluationRun bundle wire type is unsupported: {type(value).__name__}"
    )


def _unwire(value: object) -> object:
    if (
        value is None
        or isinstance(value, (str, bool))
        or (isinstance(value, int) and not isinstance(value, bool))
    ):
        return value
    row = _map(value)
    if set(row) == {"$tuple"}:
        return tuple(_unwire(item) for item in _list(row["$tuple"]))
    if set(row) == {"$bytes_b64u"}:
        return _decode_b64u(_str(row["$bytes_b64u"]))
    _keys(row, {"$type", "fields"})
    name = _str(row["$type"])
    cls = _WIRE_TYPES.get(name)
    if cls is None:
        raise ProtocolShapeError("EvaluationRun bundle DTO type is not whitelisted")
    values = _map(row["fields"])
    expected = {item.name for item in fields(cls) if item.init}
    _keys(values, expected)
    try:
        constructor: Any = cls
        return constructor(**{key: _unwire(item) for key, item in values.items()})
    except (TypeError, ValueError) as exc:
        raise ProtocolShapeError(f"EvaluationRun bundle {name} is malformed") from exc


def _map(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ProtocolShapeError("EvaluationRun bundle expected JSON object")
    return value


def _list(value: object) -> list[Any]:
    if not isinstance(value, list):
        raise ProtocolShapeError("EvaluationRun bundle expected JSON array")
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise ProtocolShapeError("EvaluationRun bundle expected string")
    return value


def _keys(value: object, expected: set[str]) -> None:
    row = _map(value)
    if set(row) != expected:
        raise ProtocolShapeError("EvaluationRun bundle object has missing or unknown fields")


__all__ = [
    "MAX_EVALUATION_RUN_BUNDLE_BYTES",
    "MAX_EVALUATION_RUN_BUNDLE_DEPTH",
    "MAX_EVALUATION_RUN_BUNDLE_FACTS",
    "MAX_EVALUATION_RUN_BUNDLE_PREDICATES",
    "MAX_EVALUATION_RUN_BUNDLE_ROWS",
    "MAX_EVALUATION_RUN_BUNDLE_VALUES",
    "evaluation_run_bundle_bytes",
    "evaluation_run_bundle_from_bytes",
]


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    row: dict[str, object] = {}
    for key, value in pairs:
        if key in row:
            raise ProtocolShapeError("EvaluationRun bundle JSON contains duplicate object key")
        row[key] = value
    return row


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(f"EvaluationRun bundle JSON contains non-standard constant {value!r}")


def _decode_b64u(encoded: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode((encoded + "=" * (-len(encoded) % 4)).encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ProtocolShapeError("bundle base64url value is malformed") from exc
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != encoded:
        raise ProtocolShapeError("bundle base64url value is non-canonical")
    return raw
