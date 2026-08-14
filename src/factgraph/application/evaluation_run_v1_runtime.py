"""Detached V1 EvaluationRun capture, replay, Explain, and comparison helpers.

This module is deliberately a narrow *runtime* companion to
``protocol.evaluation_run_v1``.  It has four non-negotiable boundaries:

* capture serializes a fully typed ``CompiledDerivationPlan`` into a strict,
  canonical program body that is bound to the GoalPlan, target, schema,
  address-space and execution-profile pins;
* replay takes one already-captured :class:`EvaluationRunV1` only.  It never
  accepts or opens a live ``Store`` and never invokes a RelationProvider;
* Explain requires an explicit row or summary anchor.  A captured empty result
  is reported as an observation, never as a proof of a negative fact;
* Policy-variant comparison reports program and selected-row-set differences.
  It never attributes a difference to one rule, source, premise, or policy
  node.

The portable evaluator is intentionally the same positive finite common
denominator used by V1 Query execution.  Thus even ``native_deterministic_v1``
replay reconstructs a fresh isolated materialized relation rather than falling
back to a current ledger.  Portable replay verifies selected row sets across
Native, Souffle and ProbLog, but explicitly does **not** claim proof/evidence
parity between those engines.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import math
from typing import Any, Literal

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.rules.where_ast import (
    WhereASTError,
    lower_ast_to_where_ir,
    parse_where_ir_to_ast,
)
from factgraph.core.schema.schema_ir import (
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
    schema_digest,
)
from factgraph.core.store._support import ProjectedFact

from .portable_evaluation_runtime import (
    PortableEngineEvaluationV1,
    PortableEngineObservationFrameV1,
    PortableEvaluationError,
    execute_native_deterministic_v1,
    observe_portable_deterministic_v1,
    portable_dependency_predicate_ids_v1,
)
from .protocol.common import ProtocolShapeError
from .protocol.derivation import CompiledDerivationPlan, CompiledHeadCall
from .protocol.evaluation_run_v1 import (
    EvaluationEngineResultV1,
    EvaluationExecutionProfileV1,
    EvaluationReplayFactV1,
    EvaluationReplayPayloadV1,
    EvaluationReplayProgramEnvelopeV1,
    EvaluationReplayRelationV1,
    EvaluationReplayWorldV1,
    EvaluationRunSideV1,
    EvaluationRunV1,
    ExplainTargetV1,
    ProviderReceiptRefV1,
)
from .protocol.goal_plan_v1 import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    ExactLocalAbsenceExpectationV1,
    ExistsExpectationV1,
    GoalExpectationOutcomeV1,
    GoalPlanV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalRowExpectationV1,
    GoalValueV1,
    SetEqualsExpectationV1,
)
from .protocol.policy import (
    PolicyCompareStructureNodeV0,
    PolicyFieldNavigation,
    PolicyStructureNodeV0,
    PolicyStructureV0,
)
from .protocol.scenario_v1 import (
    ExactLocalClosureTargetV1,
    ResolvedScenarioOperationV1,
    ScenarioValueV1,
)
from .protocol.schema_runtime import FieldPath
from .protocol.semantic_address import SemanticPortAddress


_PROGRAM_TYPE = "FactGraphEvaluationProgramV1"
_PROGRAM_RECORD_TYPE = "FactGraphCompiledDerivationPlanV1"
_STRUCTURAL_VALUE_TYPE = "FactGraphStructuralValueV1"
_AUTHORED_POLICY_STRUCTURE_TYPE = "FactGraphAuthoredPolicyStructureV1"
_SCENARIO_PATCH_TYPE = "FactGraphScenarioPatchV1"
_MAX_STRUCTURAL_DEPTH = 64
_MAX_STRUCTURAL_NODES = 100_000


class EvaluationRunRuntimeErrorV1(ValueError):
    """Fail-closed capture/replay rejection with a stable diagnostic code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _canonical_json_bytes(value: object, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is not canonical JSON", code="EVALUATION_RUN_V1_CANONICAL_JSON_INVALID"
        ) from exc


def _thaw_json(value: object) -> object:
    """Convert protocol-owned frozen JSON containers back to JSON values."""

    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_thaw_json(item) for item in value]
    return value


def _token(label: str, payload: object) -> str:
    return f"sha256:{sha256_hex(_canonical_json_bytes({'format': label, 'payload': payload}, label=label))}"


def _require_token(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise EvaluationRunRuntimeErrorV1(
            f"{name} must be sha256 token", code="EVALUATION_RUN_V1_PIN_INVALID"
        )
    raw = value[7:]
    if len(raw) != 64 or raw != raw.lower() or any(char not in "0123456789abcdef" for char in raw):
        raise EvaluationRunRuntimeErrorV1(
            f"{name} must be sha256 token", code="EVALUATION_RUN_V1_PIN_INVALID"
        )
    return value


def _exact_keys(value: object, keys: frozenset[str], *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} has unsupported or missing fields",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return value


def _plain_json(value: object, *, label: str) -> object:
    """Parse a canonical JSON scalar/object without duplicate-key ambiguity."""

    if not isinstance(value, bytes):
        raise EvaluationRunRuntimeErrorV1(
            f"{label} must be bytes", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
        )

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in items:
            if key in result:
                raise EvaluationRunRuntimeErrorV1(
                    f"{label} has duplicate object key",
                    code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
                )
            result[key] = item
        return result

    def reject_constant(text: str) -> object:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} has non-standard JSON constant {text!r}",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )

    try:
        decoded = json.loads(
            value.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is not valid UTF-8 JSON",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        ) from exc
    if _canonical_json_bytes(decoded, label=label) != value:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is not canonical JSON",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return decoded


def _encode_structural(value: object, *, depth: int = 0) -> dict[str, object]:
    """Encode tuple/list/map distinctions which ordinary JSON would erase."""

    if depth > _MAX_STRUCTURAL_DEPTH:
        raise EvaluationRunRuntimeErrorV1(
            "compiled program exceeds structural depth limit",
            code="EVALUATION_RUN_V1_PROGRAM_LIMIT_EXCEEDED",
        )
    if value is None or isinstance(value, (str, bool)):
        return {"$type": _STRUCTURAL_VALUE_TYPE, "kind": "scalar", "value": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"$type": _STRUCTURAL_VALUE_TYPE, "kind": "scalar", "value": value}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvaluationRunRuntimeErrorV1(
                "compiled program contains non-finite float",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
        return {"$type": _STRUCTURAL_VALUE_TYPE, "kind": "float64", "value": value.hex()}
    if isinstance(value, bytes):
        encoded = base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
        return {"$type": _STRUCTURAL_VALUE_TYPE, "kind": "bytes", "value": encoded}
    if isinstance(value, tuple):
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "tuple",
            "items": [_encode_structural(item, depth=depth + 1) for item in value],
        }
    if isinstance(value, list):
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "list",
            "items": [_encode_structural(item, depth=depth + 1) for item in value],
        }
    if isinstance(value, dict):
        if not all(isinstance(key, str) and key for key in value):
            raise EvaluationRunRuntimeErrorV1(
                "compiled program map keys must be non-empty strings",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
        return {
            "$type": _STRUCTURAL_VALUE_TYPE,
            "kind": "map",
            "items": [
                [key, _encode_structural(item, depth=depth + 1)]
                for key, item in sorted(value.items())
            ],
        }
    raise EvaluationRunRuntimeErrorV1(
        f"compiled program contains unsupported value {type(value).__name__}",
        code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
    )


def _decode_structural(value: object, *, depth: int = 0, budget: list[int] | None = None) -> object:
    if depth > _MAX_STRUCTURAL_DEPTH:
        raise EvaluationRunRuntimeErrorV1(
            "compiled program exceeds structural depth limit",
            code="EVALUATION_RUN_V1_PROGRAM_LIMIT_EXCEEDED",
        )
    if budget is None:
        budget = [_MAX_STRUCTURAL_NODES]
    budget[0] -= 1
    if budget[0] < 0:
        raise EvaluationRunRuntimeErrorV1(
            "compiled program exceeds structural node limit",
            code="EVALUATION_RUN_V1_PROGRAM_LIMIT_EXCEEDED",
        )
    # ``_exact_keys`` cannot express the two disjoint forms cleanly.  Do the
    # exact checks here rather than accepting a hybrid value/items node.
    if not isinstance(value, Mapping) or value.get("$type") != _STRUCTURAL_VALUE_TYPE:
        raise EvaluationRunRuntimeErrorV1(
            "compiled structural value is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    row = value
    kind = row.get("kind")
    if kind == "scalar":
        exact = _exact_keys(row, frozenset({"$type", "kind", "value"}), label="scalar")
        scalar = exact["value"]
        if scalar is not None and not isinstance(scalar, (str, bool, int)):
            raise EvaluationRunRuntimeErrorV1(
                "compiled scalar is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        if isinstance(scalar, float):
            raise EvaluationRunRuntimeErrorV1(
                "compiled scalar float must use float64 form",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
        return scalar
    if kind == "float64":
        exact = _exact_keys(row, frozenset({"$type", "kind", "value"}), label="float64")
        raw = exact["value"]
        if not isinstance(raw, str):
            raise EvaluationRunRuntimeErrorV1(
                "compiled float64 is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        try:
            result = float.fromhex(raw)
        except ValueError as exc:
            raise EvaluationRunRuntimeErrorV1(
                "compiled float64 is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            ) from exc
        if not math.isfinite(result) or result.hex() != raw:
            raise EvaluationRunRuntimeErrorV1(
                "compiled float64 is not canonical", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        return result
    if kind == "bytes":
        exact = _exact_keys(row, frozenset({"$type", "kind", "value"}), label="bytes")
        raw = exact["value"]
        if not isinstance(raw, str):
            raise EvaluationRunRuntimeErrorV1(
                "compiled bytes are malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        try:
            decoded_bytes = base64.urlsafe_b64decode((raw + "=" * (-len(raw) % 4)).encode("ascii"))
        except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
            raise EvaluationRunRuntimeErrorV1(
                "compiled bytes are malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            ) from exc
        if base64.urlsafe_b64encode(decoded_bytes).decode("ascii").rstrip("=") != raw:
            raise EvaluationRunRuntimeErrorV1(
                "compiled bytes are not canonical", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        return decoded_bytes
    if kind in {"tuple", "list"}:
        exact = _exact_keys(row, frozenset({"$type", "kind", "items"}), label=kind)
        items = exact["items"]
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            raise EvaluationRunRuntimeErrorV1(
                "compiled structural items must be a list",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
        decoded_items = [_decode_structural(item, depth=depth + 1, budget=budget) for item in items]
        return tuple(decoded_items) if kind == "tuple" else decoded_items
    if kind == "map":
        exact = _exact_keys(row, frozenset({"$type", "kind", "items"}), label="map")
        items = exact["items"]
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            raise EvaluationRunRuntimeErrorV1(
                "compiled map items must be a list", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        decoded_map: dict[str, object] = {}
        previous: str | None = None
        for item in items:
            if (
                not isinstance(item, Sequence)
                or isinstance(item, (str, bytes, bytearray))
                or len(item) != 2
                or not isinstance(item[0], str)
                or not item[0]
            ):
                raise EvaluationRunRuntimeErrorV1(
                    "compiled map item is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
                )
            key = item[0]
            if previous is not None and key <= previous:
                raise EvaluationRunRuntimeErrorV1(
                    "compiled map keys must be canonical",
                    code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
                )
            previous = key
            decoded_map[key] = _decode_structural(item[1], depth=depth + 1, budget=budget)
        return decoded_map
    raise EvaluationRunRuntimeErrorV1(
        "compiled structural value kind is unsupported",
        code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
    )


def _validate_capture_plan(plan: CompiledDerivationPlan) -> None:
    if not isinstance(plan, CompiledDerivationPlan):
        raise EvaluationRunRuntimeErrorV1(
            "compiled program must be CompiledDerivationPlan",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    if (
        plan.body_confidence is not None
        or plan.head_spec is not None
        or plan.engine_ext is not None
        or plan.engine_options
    ):
        raise EvaluationRunRuntimeErrorV1(
            "V1 replay program permits only unconfigured positive compiled plans",
            code="EVALUATION_RUN_V1_PROGRAM_CAPABILITY_REJECTED",
        )
    if len(plan.heads) != 1:
        raise EvaluationRunRuntimeErrorV1(
            "V1 replay program requires exactly one head",
            code="EVALUATION_RUN_V1_PROGRAM_CAPABILITY_REJECTED",
        )
    try:
        ast = parse_where_ir_to_ast(plan.body_ir)
        if lower_ast_to_where_ir(ast) != plan.body_ir:
            raise EvaluationRunRuntimeErrorV1(
                "compiled plan body is not canonical where IR",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
    except WhereASTError as exc:
        raise EvaluationRunRuntimeErrorV1(
            "compiled plan body is invalid where IR",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        ) from exc


def _compiled_plan_wire(plan: CompiledDerivationPlan) -> dict[str, object]:
    _validate_capture_plan(plan)
    return {
        "$type": _PROGRAM_RECORD_TYPE,
        "derivation_id": plan.derivation_id,
        "version": plan.version,
        "body_ir": _encode_structural(plan.body_ir),
        "heads": [
            {"target_pred_id": head.target_pred_id, "head_var_names": list(head.head_var_names)}
            for head in plan.heads
        ],
    }


def _compiled_plan_from_wire(value: object) -> CompiledDerivationPlan:
    row = _exact_keys(
        value,
        frozenset({"$type", "derivation_id", "version", "body_ir", "heads"}),
        label="compiled derivation plan",
    )
    if row["$type"] != _PROGRAM_RECORD_TYPE:
        raise EvaluationRunRuntimeErrorV1(
            "compiled derivation plan type is invalid",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    if not isinstance(row["derivation_id"], str) or not isinstance(row["version"], str):
        raise EvaluationRunRuntimeErrorV1(
            "compiled derivation plan identity is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    body = _decode_structural(row["body_ir"])
    if not isinstance(body, list):
        raise EvaluationRunRuntimeErrorV1(
            "compiled derivation body must be a list",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    raw_heads = row["heads"]
    if (
        not isinstance(raw_heads, Sequence)
        or isinstance(raw_heads, (str, bytes, bytearray))
        or not raw_heads
    ):
        raise EvaluationRunRuntimeErrorV1(
            "compiled derivation heads are malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    heads: list[CompiledHeadCall] = []
    for raw_head in raw_heads:
        head = _exact_keys(
            raw_head,
            frozenset({"target_pred_id", "head_var_names"}),
            label="compiled derivation head",
        )
        names = head["head_var_names"]
        if (
            not isinstance(head["target_pred_id"], str)
            or not isinstance(names, Sequence)
            or isinstance(names, (str, bytes, bytearray))
            or not all(isinstance(name, str) for name in names)
        ):
            raise EvaluationRunRuntimeErrorV1(
                "compiled derivation head is malformed",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
        heads.append(CompiledHeadCall(head["target_pred_id"], tuple(names)))
    try:
        plan = CompiledDerivationPlan(
            derivation_id=row["derivation_id"],
            version=row["version"],
            body_ir=body,
            heads=tuple(heads),
        )
    except ProtocolShapeError as exc:
        raise EvaluationRunRuntimeErrorV1(
            "compiled derivation plan is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
        ) from exc
    _validate_capture_plan(plan)
    # Require an exact round trip, otherwise an alternate spelling of the
    # same AST could turn an envelope into a non-canonical execution program.
    if _canonical_json_bytes(
        _compiled_plan_wire(plan), label="compiled derivation plan"
    ) != _canonical_json_bytes(_thaw_json(value), label="compiled derivation plan"):
        raise EvaluationRunRuntimeErrorV1(
            "compiled derivation plan is not canonical",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return plan


def _compiled_plan_digest(plan: CompiledDerivationPlan) -> str:
    return _token("evaluation_run_v1_compiled_plan", _compiled_plan_wire(plan))


def _require_plain_sha256(value: object, *, name: str) -> str:
    """Validate the legacy bare-hex digest used by ``PolicyStructureV0``."""

    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise EvaluationRunRuntimeErrorV1(
            f"{name} must be lowercase sha256 hex",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return value


def _semantic_address_to_wire(address: SemanticPortAddress) -> dict[str, object]:
    if not isinstance(address, SemanticPortAddress):
        raise EvaluationRunRuntimeErrorV1(
            "policy structure address is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return {
        "occurrence_alias": address.occurrence_alias,
        "port_name": address.port_name,
    }


def _semantic_address_from_wire(value: object, *, label: str) -> SemanticPortAddress:
    row = _exact_keys(value, frozenset({"occurrence_alias", "port_name"}), label=label)
    try:
        return SemanticPortAddress(row["occurrence_alias"], row["port_name"])
    except (TypeError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        ) from exc


def _field_path_to_wire(field_path: FieldPath) -> dict[str, object]:
    if not isinstance(field_path, FieldPath):
        raise EvaluationRunRuntimeErrorV1(
            "policy structure field path is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return {"entity_type": field_path.entity_type, "field_name": field_path.field_name}


def _field_path_from_wire(value: object, *, label: str) -> FieldPath:
    row = _exact_keys(value, frozenset({"entity_type", "field_name"}), label=label)
    try:
        return FieldPath(row["entity_type"], row["field_name"])
    except (TypeError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        ) from exc


def _policy_operand_to_wire(
    value: SemanticPortAddress | PolicyFieldNavigation,
) -> dict[str, object]:
    if isinstance(value, SemanticPortAddress):
        return {"kind": "address", "address": _semantic_address_to_wire(value)}
    if isinstance(value, PolicyFieldNavigation):
        return {
            "kind": "field_navigation",
            "base": _semantic_address_to_wire(value.base),
            "field": _field_path_to_wire(value.field),
        }
    raise EvaluationRunRuntimeErrorV1(
        "policy structure comparison operand is malformed",
        code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
    )


def _policy_operand_from_wire(
    value: object, *, label: str
) -> SemanticPortAddress | PolicyFieldNavigation:
    if not isinstance(value, Mapping) or not isinstance(value.get("kind"), str):
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    if value["kind"] == "address":
        row = _exact_keys(value, frozenset({"kind", "address"}), label=label)
        return _semantic_address_from_wire(row["address"], label=f"{label}.address")
    if value["kind"] == "field_navigation":
        row = _exact_keys(value, frozenset({"kind", "base", "field"}), label=label)
        try:
            return PolicyFieldNavigation(
                _semantic_address_from_wire(row["base"], label=f"{label}.base"),
                _field_path_from_wire(row["field"], label=f"{label}.field"),
            )
        except (TypeError, ValueError) as exc:
            raise EvaluationRunRuntimeErrorV1(
                f"{label} is malformed",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            ) from exc
    raise EvaluationRunRuntimeErrorV1(
        f"{label} has unsupported operand kind",
        code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
    )


def _authored_policy_structure_to_wire(structure: PolicyStructureV0) -> dict[str, object]:
    """Make a strict replay-only snapshot of the authored Policy topology.

    The lowering plan is deliberately not used as a proxy for author intent:
    ``Any`` branch expansion and compiler-generated aliases make it lossy.
    This snapshot is only structural context for Explain; it does not assert
    per-node proof status or replace the existing EvidenceGraph path.
    """

    if not isinstance(structure, PolicyStructureV0):
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure is malformed",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    try:
        current = PolicyStructureV0(structure.root_node_id, structure.nodes)
    except (TypeError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure is malformed",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        ) from exc
    if current.structure_digest != structure.structure_digest:
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure digest is stale",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    nodes: list[dict[str, object]] = []
    for node in structure.nodes:
        if isinstance(node, PolicyStructureNodeV0):
            nodes.append(
                {
                    "node_id": node.node_id,
                    "kind": node.kind,
                    "child_node_ids": list(node.child_node_ids),
                    "occurrence_alias": node.occurrence_alias,
                    "left": None if node.left is None else _semantic_address_to_wire(node.left),
                    "right": None if node.right is None else _semantic_address_to_wire(node.right),
                }
            )
        elif isinstance(node, PolicyCompareStructureNodeV0):
            nodes.append(
                {
                    "node_id": node.node_id,
                    "kind": "compare",
                    "op": node.op,
                    "left": _policy_operand_to_wire(node.left),
                    "right": _policy_operand_to_wire(node.right),
                }
            )
        else:  # pragma: no cover - PolicyStructureV0 validates this already.
            raise EvaluationRunRuntimeErrorV1(
                "authored policy structure node is malformed",
                code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
            )
    return {
        "$type": _AUTHORED_POLICY_STRUCTURE_TYPE,
        "root_node_id": structure.root_node_id,
        "structure_digest": structure.structure_digest,
        "nodes": nodes,
    }


def _authored_policy_structure_from_wire(value: object) -> PolicyStructureV0:
    row = _exact_keys(
        value,
        frozenset({"$type", "root_node_id", "structure_digest", "nodes"}),
        label="authored policy structure",
    )
    if row["$type"] != _AUTHORED_POLICY_STRUCTURE_TYPE or not isinstance(row["root_node_id"], str):
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    declared_digest = _require_plain_sha256(row["structure_digest"], name="structure_digest")
    raw_nodes = row["nodes"]
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, (str, bytes, bytearray)):
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure nodes are malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    nodes: list[PolicyStructureNodeV0 | PolicyCompareStructureNodeV0] = []
    for index, raw_node in enumerate(raw_nodes):
        label = f"authored policy structure.nodes[{index}]"
        if not isinstance(raw_node, Mapping) or not isinstance(raw_node.get("kind"), str):
            raise EvaluationRunRuntimeErrorV1(
                f"{label} is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            )
        kind = raw_node["kind"]
        try:
            if kind == "compare":
                node = _exact_keys(
                    raw_node,
                    frozenset({"node_id", "kind", "op", "left", "right"}),
                    label=label,
                )
                nodes.append(
                    PolicyCompareStructureNodeV0(
                        node["node_id"],
                        node["op"],  # type: ignore[arg-type]
                        _policy_operand_from_wire(node["left"], label=f"{label}.left"),
                        _policy_operand_from_wire(node["right"], label=f"{label}.right"),
                    )
                )
                continue
            node = _exact_keys(
                raw_node,
                frozenset(
                    {
                        "node_id",
                        "kind",
                        "child_node_ids",
                        "occurrence_alias",
                        "left",
                        "right",
                    }
                ),
                label=label,
            )
            child_ids = node["child_node_ids"]
            if (
                not isinstance(child_ids, Sequence)
                or isinstance(child_ids, (str, bytes, bytearray))
                or not all(isinstance(child_id, str) for child_id in child_ids)
            ):
                raise EvaluationRunRuntimeErrorV1(
                    f"{label}.child_node_ids is malformed",
                    code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
                )
            left = (
                None
                if node["left"] is None
                else _semantic_address_from_wire(node["left"], label=f"{label}.left")
            )
            right = (
                None
                if node["right"] is None
                else _semantic_address_from_wire(node["right"], label=f"{label}.right")
            )
            nodes.append(
                PolicyStructureNodeV0(
                    node["node_id"],  # type: ignore[arg-type]
                    kind,  # type: ignore[arg-type]
                    tuple(child_ids),
                    node["occurrence_alias"],  # type: ignore[arg-type]
                    left,
                    right,
                )
            )
        except (TypeError, ValueError) as exc:
            raise EvaluationRunRuntimeErrorV1(
                f"{label} is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            ) from exc
    try:
        structure = PolicyStructureV0(row["root_node_id"], tuple(nodes))
    except (TypeError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure is malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        ) from exc
    if structure.structure_digest != declared_digest:
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure digest is mismatched",
            code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
        )
    if _canonical_json_bytes(
        _authored_policy_structure_to_wire(structure), label="authored policy structure"
    ) != _canonical_json_bytes(_thaw_json(value), label="authored policy structure"):
        raise EvaluationRunRuntimeErrorV1(
            "authored policy structure is not canonical",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    return structure


def _scenario_value_to_wire(value: ScenarioValueV1) -> dict[str, object]:
    if not isinstance(value, ScenarioValueV1):
        raise EvaluationRunRuntimeErrorV1(
            "scenario patch value is malformed", code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID"
        )
    return {"tag": value.tag, "value": value.value}


def _scenario_value_from_wire(value: object, *, label: str) -> ScenarioValueV1:
    row = _exact_keys(value, frozenset({"tag", "value"}), label=label)
    try:
        return ScenarioValueV1(row["tag"], row["value"])  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            f"{label} is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
        ) from exc


def _scenario_patch_to_wire(
    operations: tuple[ResolvedScenarioOperationV1, ...],
) -> dict[str, object]:
    """Capture resolved, not merely requested, Scenario patch operations.

    ``masked_witness_ids`` and ``synthetic_witness_ids`` deliberately stay in
    this snapshot.  They are provenance references for UI/debugging, not a
    proof that a Scenario operation caused a particular result row.
    """

    if not isinstance(operations, tuple) or not all(
        isinstance(operation, ResolvedScenarioOperationV1) for operation in operations
    ):
        raise EvaluationRunRuntimeErrorV1(
            "scenario operations must be a ResolvedScenarioOperationV1 tuple",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    rows = [
        {
            "kind": operation.kind,
            "entity_ref": operation.entity_ref,
            "entity_type": operation.entity_type,
            "predicate_id": operation.predicate_id,
            "field": None if operation.field is None else _field_path_to_wire(operation.field),
            "assertion_id": operation.assertion_id,
            "values": [_scenario_value_to_wire(value) for value in operation.values],
            "premise_ids": list(operation.premise_ids),
            "origin_refs": list(operation.origin_refs),
            "masked_witness_ids": list(operation.masked_witness_ids),
            "synthetic_witness_ids": list(operation.synthetic_witness_ids),
            "operation_digest": operation.operation_digest,
        }
        for operation in operations
    ]
    return {
        "$type": _SCENARIO_PATCH_TYPE,
        "operations": rows,
        "patch_digest": _token(
            "evaluation_run_v1_scenario_patch",
            tuple(operation.operation_digest for operation in operations),
        ),
    }


def _scenario_patch_from_wire(
    value: object,
) -> tuple[ResolvedScenarioOperationV1, ...]:
    row = _exact_keys(
        value,
        frozenset({"$type", "operations", "patch_digest"}),
        label="scenario patch",
    )
    if row["$type"] != _SCENARIO_PATCH_TYPE:
        raise EvaluationRunRuntimeErrorV1(
            "scenario patch type is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
        )
    _require_token(row["patch_digest"], name="scenario_patch_digest")
    raw_operations = row["operations"]
    if not isinstance(raw_operations, Sequence) or isinstance(
        raw_operations, (str, bytes, bytearray)
    ):
        raise EvaluationRunRuntimeErrorV1(
            "scenario patch operations are malformed",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    operations: list[ResolvedScenarioOperationV1] = []
    for index, raw_operation in enumerate(raw_operations):
        label = f"scenario patch.operations[{index}]"
        operation = _exact_keys(
            raw_operation,
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
            label=label,
        )
        values = operation["values"]
        string_sequences = {
            name: operation[name]
            for name in (
                "premise_ids",
                "origin_refs",
                "masked_witness_ids",
                "synthetic_witness_ids",
            )
        }
        if (
            not isinstance(values, Sequence)
            or isinstance(values, (str, bytes, bytearray))
            or any(
                not isinstance(items, Sequence)
                or isinstance(items, (str, bytes, bytearray))
                or not all(isinstance(item, str) for item in items)
                for items in string_sequences.values()
            )
        ):
            raise EvaluationRunRuntimeErrorV1(
                f"{label} has malformed list field",
                code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
            )
        try:
            parsed = ResolvedScenarioOperationV1(
                operation["kind"],  # type: ignore[arg-type]
                operation["entity_ref"],  # type: ignore[arg-type]
                operation["entity_type"],  # type: ignore[arg-type]
                operation["predicate_id"],  # type: ignore[arg-type]
                None
                if operation["field"] is None
                else _field_path_from_wire(operation["field"], label=f"{label}.field"),
                assertion_id=operation["assertion_id"],  # type: ignore[arg-type]
                values=tuple(
                    _scenario_value_from_wire(item, label=f"{label}.values") for item in values
                ),
                premise_ids=tuple(string_sequences["premise_ids"]),  # type: ignore[arg-type]
                origin_refs=tuple(string_sequences["origin_refs"]),  # type: ignore[arg-type]
                masked_witness_ids=tuple(string_sequences["masked_witness_ids"]),  # type: ignore[arg-type]
                synthetic_witness_ids=tuple(string_sequences["synthetic_witness_ids"]),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as exc:
            raise EvaluationRunRuntimeErrorV1(
                f"{label} is malformed", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
            ) from exc
        if parsed.operation_digest != operation["operation_digest"]:
            raise EvaluationRunRuntimeErrorV1(
                f"{label} digest is mismatched", code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH"
            )
        operations.append(parsed)
    parsed_tuple = tuple(operations)
    if row["patch_digest"] != _scenario_patch_to_wire(parsed_tuple)["patch_digest"]:
        raise EvaluationRunRuntimeErrorV1(
            "scenario patch digest is mismatched", code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH"
        )
    if _canonical_json_bytes(
        _scenario_patch_to_wire(parsed_tuple), label="scenario patch"
    ) != _canonical_json_bytes(_thaw_json(value), label="scenario patch"):
        raise EvaluationRunRuntimeErrorV1(
            "scenario patch is not canonical", code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID"
        )
    return parsed_tuple


def _validate_plan_profile(plan: GoalPlanV1, profile: EvaluationExecutionProfileV1) -> None:
    if plan.execution_profile_digest not in {None, profile.profile_digest}:
        raise EvaluationRunRuntimeErrorV1(
            "GoalPlan profile pin does not match execution profile",
            code="EVALUATION_RUN_V1_PROFILE_PIN_MISMATCH",
        )


def _program_record(plan: GoalPlanV1, compiled_plan: CompiledDerivationPlan) -> dict[str, object]:
    return {
        "$type": "FactGraphEvaluationProgramRecordV1",
        "plan_digest": plan.plan_digest,
        "query_digest": plan.query_digest,
        "target_digest": plan.target.target_digest,
        "compiled_plan_digest": _compiled_plan_digest(compiled_plan),
        "compiled_plan": _compiled_plan_wire(compiled_plan),
    }


def _decode_program_record(
    value: object,
    *,
    plan_digest: str,
    query_digest: str,
    target_digest: str,
) -> CompiledDerivationPlan:
    row = _exact_keys(
        value,
        frozenset(
            {
                "$type",
                "plan_digest",
                "query_digest",
                "target_digest",
                "compiled_plan_digest",
                "compiled_plan",
            }
        ),
        label="evaluation program record",
    )
    if row["$type"] != "FactGraphEvaluationProgramRecordV1":
        raise EvaluationRunRuntimeErrorV1(
            "evaluation program record type is invalid",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    for name, expected in (
        ("plan_digest", plan_digest),
        ("query_digest", query_digest),
        ("target_digest", target_digest),
    ):
        if row[name] != expected:
            raise EvaluationRunRuntimeErrorV1(
                f"evaluation program record {name} does not match sealed run",
                code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
            )
    compiled = _compiled_plan_from_wire(row["compiled_plan"])
    if row["compiled_plan_digest"] != _compiled_plan_digest(compiled):
        raise EvaluationRunRuntimeErrorV1(
            "evaluation program compiled-plan digest does not match body/head",
            code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
        )
    return compiled


@dataclass(frozen=True)
class DecodedEvaluationReplayProgramV1:
    """Runtime-only, reconstituted compiled bodies from a sealed envelope."""

    primary: CompiledDerivationPlan = field(repr=False, compare=False)
    candidate: CompiledDerivationPlan | None = field(default=None, repr=False, compare=False)
    primary_policy_structure: PolicyStructureV0 | None = field(
        default=None, repr=False, compare=False
    )
    candidate_policy_structure: PolicyStructureV0 | None = field(
        default=None, repr=False, compare=False
    )
    scenario_operations: tuple[ResolvedScenarioOperationV1, ...] | None = field(
        default=None, repr=False, compare=False
    )
    primary_compiled_plan_digest: str = ""
    candidate_compiled_plan_digest: str | None = None


def build_evaluation_replay_program_envelope_v1(
    *,
    schema_ir: Mapping[str, Any],
    address_space_digest: str,
    plan: GoalPlanV1,
    execution_profile: EvaluationExecutionProfileV1,
    primary_compiled_plan: CompiledDerivationPlan,
    candidate_plan: GoalPlanV1 | None = None,
    candidate_compiled_plan: CompiledDerivationPlan | None = None,
    primary_policy_structure: PolicyStructureV0 | None = None,
    candidate_policy_structure: PolicyStructureV0 | None = None,
    scenario_operations: tuple[ResolvedScenarioOperationV1, ...] | None = None,
) -> EvaluationReplayProgramEnvelopeV1:
    """Capture the exact replay program, with no live evaluator/store input.

    The compiler/body provenance is an in-process admission responsibility of
    the caller.  This function then freezes exactly the admitted body/head and
    binds it to the immutable plan/profile/schema pins; replay never silently
    recompiles a different current Policy.  Callers with an admitted compiled
    Policy may additionally pass its authored structure and the resolved
    Scenario operations.  They are sealed Explain context, never substitutes
    for engine proof/evidence.
    """

    if not isinstance(plan, GoalPlanV1) or not isinstance(
        execution_profile, EvaluationExecutionProfileV1
    ):
        raise EvaluationRunRuntimeErrorV1(
            "plan and execution profile are required",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    _validate_plan_profile(plan, execution_profile)
    _require_token(address_space_digest, name="address_space_digest")
    try:
        validated_schema = ensure_schema_ir(dict(schema_ir))
    except Exception as exc:
        raise EvaluationRunRuntimeErrorV1(
            "schema is invalid", code="EVALUATION_RUN_V1_SCHEMA_INVALID"
        ) from exc
    schema_pin = schema_digest(validated_schema)
    _validate_capture_plan(primary_compiled_plan)
    if (candidate_plan is None) != (candidate_compiled_plan is None):
        raise EvaluationRunRuntimeErrorV1(
            "candidate plan and compiled program must be supplied together",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    if candidate_plan is not None:
        assert candidate_compiled_plan is not None
        _validate_plan_profile(candidate_plan, execution_profile)
        if plan.candidate_target is None or candidate_plan.target != plan.candidate_target:
            raise EvaluationRunRuntimeErrorV1(
                "candidate plan does not match the primary immutable candidate pin",
                code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
            )
        if candidate_plan.query_digest != plan.candidate_query_digest:
            raise EvaluationRunRuntimeErrorV1(
                "candidate plan does not match the primary immutable candidate Query pin",
                code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
            )
        if candidate_plan.candidate_target is not None:
            raise EvaluationRunRuntimeErrorV1(
                "candidate plan cannot nest a candidate",
                code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
            )
        _validate_capture_plan(candidate_compiled_plan)
    if candidate_plan is None:
        if candidate_policy_structure is not None:
            raise EvaluationRunRuntimeErrorV1(
                "candidate policy structure requires a candidate plan",
                code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
            )
        if plan.candidate_target is not None:
            raise EvaluationRunRuntimeErrorV1(
                "primary plan declares a candidate without its compiled program",
                code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
            )
    candidate_record: dict[str, object] | None = None
    if candidate_plan is not None:
        assert candidate_compiled_plan is not None
        candidate_record = _program_record(candidate_plan, candidate_compiled_plan)
    compiled_program: dict[str, object] = {
        "$type": _PROGRAM_TYPE,
        "primary": _program_record(plan, primary_compiled_plan),
        "candidate": candidate_record,
        "primary_policy_structure": (
            None
            if primary_policy_structure is None
            else _authored_policy_structure_to_wire(primary_policy_structure)
        ),
        "candidate_policy_structure": (
            None
            if candidate_policy_structure is None
            else _authored_policy_structure_to_wire(candidate_policy_structure)
        ),
        "scenario_patch": (
            None if scenario_operations is None else _scenario_patch_to_wire(scenario_operations)
        ),
    }
    return EvaluationReplayProgramEnvelopeV1(
        schema_digest=schema_pin,
        address_space_digest=address_space_digest,
        plan_digest=plan.plan_digest,
        query_digest=plan.query_digest,
        target_digest=plan.target.target_digest,
        execution_profile_digest=execution_profile.profile_digest,
        compiler_digest=execution_profile.compiler_digest,
        compiled_program=compiled_program,
        candidate_plan_digest=None if candidate_plan is None else candidate_plan.plan_digest,
        candidate_query_digest=None if candidate_plan is None else candidate_plan.query_digest,
        candidate_target_digest=None
        if candidate_plan is None
        else candidate_plan.target.target_digest,
    )


def capture_evaluation_replay_world_v1(
    *,
    side: Literal["baseline", "effective"],
    schema_ir: Mapping[str, Any],
    semantic_world_digest: str,
    resolution_evidence_digest: str,
    closure_target_digests: tuple[str, ...],
    relations: Mapping[str, Sequence[ProjectedFact]],
) -> EvaluationReplayWorldV1:
    """Convert a finite typed relation into a Store-free replay world.

    This does not decide which predicates belong in the Query.  The later
    portable evaluator requires the captured inventory to equal the compiled
    plan's dependencies, making an omitted relation distinct from an empty one.
    """

    try:
        schema = ensure_schema_ir(dict(schema_ir))
    except Exception as exc:
        raise EvaluationRunRuntimeErrorV1(
            "schema is invalid", code="EVALUATION_RUN_V1_SCHEMA_INVALID"
        ) from exc
    if not isinstance(relations, Mapping):
        raise EvaluationRunRuntimeErrorV1(
            "relations must be a mapping", code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID"
        )
    tags_by_predicate = _predicate_tags(schema)
    captured: list[EvaluationReplayRelationV1] = []
    seen_witnesses: set[str] = set()
    for predicate_id, facts in sorted(relations.items()):
        tags = tags_by_predicate.get(predicate_id)
        if tags is None:
            raise EvaluationRunRuntimeErrorV1(
                f"unknown replay predicate {predicate_id!r}",
                code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH",
            )
        if not isinstance(facts, Sequence) or isinstance(facts, (str, bytes, bytearray)):
            raise EvaluationRunRuntimeErrorV1(
                "relation facts must be a sequence", code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID"
            )
        captured_facts: list[EvaluationReplayFactV1] = []
        for fact in facts:
            if not isinstance(fact, ProjectedFact) or len(fact.fact_tuple) != len(tags):
                raise EvaluationRunRuntimeErrorV1(
                    "replay fact does not match schema arity",
                    code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH",
                )
            if fact.asrt_id in seen_witnesses:
                raise EvaluationRunRuntimeErrorV1(
                    "replay relation repeats witness id across predicates",
                    code="EVALUATION_RUN_V1_RELATION_WITNESS_DUPLICATE",
                )
            seen_witnesses.add(fact.asrt_id)
            captured_facts.append(
                EvaluationReplayFactV1(
                    fact.asrt_id,
                    tuple(
                        _goal_value_from_raw(tag, raw)
                        for tag, raw in zip(tags, fact.fact_tuple, strict=True)
                    ),
                )
            )
        captured.append(EvaluationReplayRelationV1(predicate_id, tags, tuple(captured_facts)))
    return EvaluationReplayWorldV1(
        side=side,
        semantic_world_digest=semantic_world_digest,
        resolution_evidence_digest=resolution_evidence_digest,
        closure_target_digests=closure_target_digests,
        relations=tuple(captured),
    )


def capture_evaluation_replay_payload_v1(
    *,
    schema_ir: Mapping[str, Any],
    address_space_digest: str,
    plan: GoalPlanV1,
    execution_profile: EvaluationExecutionProfileV1,
    primary_compiled_plan: CompiledDerivationPlan,
    baseline_world: EvaluationReplayWorldV1,
    effective_world: EvaluationReplayWorldV1,
    candidate_plan: GoalPlanV1 | None = None,
    candidate_compiled_plan: CompiledDerivationPlan | None = None,
    primary_policy_structure: PolicyStructureV0 | None = None,
    candidate_policy_structure: PolicyStructureV0 | None = None,
    scenario_operations: tuple[ResolvedScenarioOperationV1, ...] | None = None,
    provider_receipts: tuple[ProviderReceiptRefV1, ...] = (),
) -> EvaluationReplayPayloadV1:
    """Capture all detached replay material without retaining a live Store.

    ``primary_policy_structure`` / ``candidate_policy_structure`` and
    ``scenario_operations`` are opt-in because only the trusted in-process
    compiler/resolver can supply them.  Omitting them remains an explicit
    ``not_captured`` Explain state rather than a reconstructed guess.
    """

    if not isinstance(baseline_world, EvaluationReplayWorldV1) or baseline_world.side != "baseline":
        raise EvaluationRunRuntimeErrorV1(
            "baseline_world must be baseline replay world",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    if (
        not isinstance(effective_world, EvaluationReplayWorldV1)
        or effective_world.side != "effective"
    ):
        raise EvaluationRunRuntimeErrorV1(
            "effective_world must be effective replay world",
            code="EVALUATION_RUN_V1_CAPTURE_INPUT_INVALID",
        )
    envelope = build_evaluation_replay_program_envelope_v1(
        schema_ir=schema_ir,
        address_space_digest=address_space_digest,
        plan=plan,
        execution_profile=execution_profile,
        primary_compiled_plan=primary_compiled_plan,
        candidate_plan=candidate_plan,
        candidate_compiled_plan=candidate_compiled_plan,
        primary_policy_structure=primary_policy_structure,
        candidate_policy_structure=candidate_policy_structure,
        scenario_operations=scenario_operations,
    )
    try:
        validated_schema = ensure_schema_ir(dict(schema_ir))
        schema_bytes = canonicalize_schema_ir_jcs(validated_schema)
    except Exception as exc:
        raise EvaluationRunRuntimeErrorV1(
            "schema cannot be captured canonically", code="EVALUATION_RUN_V1_SCHEMA_INVALID"
        ) from exc
    # Do not defer a mismatched captured-world/schema pair until a later
    # detached replay.  This remains Store-free: it validates only the finite
    # relation already supplied by the caller.
    _world_relation(baseline_world, validated_schema)
    _world_relation(effective_world, validated_schema)
    return EvaluationReplayPayloadV1(
        schema_digest=envelope.schema_digest,
        address_space_digest=address_space_digest,
        schema_bytes=schema_bytes,
        compiled_program_bytes=envelope.to_bytes(),
        worlds=(baseline_world, effective_world),
        provider_receipts=provider_receipts,
    )


def decode_evaluation_replay_program_v1(
    run: EvaluationRunV1,
) -> DecodedEvaluationReplayProgramV1:
    """Validate one run's sealed envelope and reconstruct only its program.

    This helper accepts the completed run rather than a free payload so callers
    cannot accidentally decode a program under another GoalPlan/profile.
    """

    _assert_run_current(run)
    payload = run.replay_payload
    _decode_schema_from_payload(payload)
    envelope = payload.program_envelope
    compiled_program = envelope.compiled_program
    root = _exact_keys(
        compiled_program,
        frozenset(
            {
                "$type",
                "primary",
                "candidate",
                "primary_policy_structure",
                "candidate_policy_structure",
                "scenario_patch",
            }
        ),
        label="evaluation replay program",
    )
    if root["$type"] != _PROGRAM_TYPE:
        raise EvaluationRunRuntimeErrorV1(
            "evaluation replay program type is invalid",
            code="EVALUATION_RUN_V1_PROGRAM_SHAPE_INVALID",
        )
    primary = _decode_program_record(
        root["primary"],
        plan_digest=run.plan.plan_digest,
        query_digest=run.plan.query_digest,
        target_digest=run.plan.target.target_digest,
    )
    candidate: CompiledDerivationPlan | None = None
    if run.candidate_plan is None:
        if root["candidate"] is not None:
            raise EvaluationRunRuntimeErrorV1(
                "replay program has undeclared candidate",
                code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
            )
    else:
        if root["candidate"] is None:
            raise EvaluationRunRuntimeErrorV1(
                "replay program omits declared candidate",
                code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
            )
        candidate = _decode_program_record(
            root["candidate"],
            plan_digest=run.candidate_plan.plan_digest,
            query_digest=run.candidate_plan.query_digest,
            target_digest=run.candidate_plan.target.target_digest,
        )
    if root["primary_policy_structure"] is None:
        primary_policy_structure = None
    else:
        primary_policy_structure = _authored_policy_structure_from_wire(
            root["primary_policy_structure"]
        )
    if root["candidate_policy_structure"] is None:
        candidate_policy_structure = None
    else:
        if candidate is None:
            raise EvaluationRunRuntimeErrorV1(
                "replay program has undeclared candidate policy structure",
                code="EVALUATION_RUN_V1_PROGRAM_PIN_MISMATCH",
            )
        candidate_policy_structure = _authored_policy_structure_from_wire(
            root["candidate_policy_structure"]
        )
    if root["scenario_patch"] is None:
        scenario_operations = None
    else:
        scenario_operations = _scenario_patch_from_wire(root["scenario_patch"])
    return DecodedEvaluationReplayProgramV1(
        primary=primary,
        candidate=candidate,
        primary_policy_structure=primary_policy_structure,
        candidate_policy_structure=candidate_policy_structure,
        scenario_operations=scenario_operations,
        primary_compiled_plan_digest=_compiled_plan_digest(primary),
        candidate_compiled_plan_digest=(
            None if candidate is None else _compiled_plan_digest(candidate)
        ),
    )


@dataclass(frozen=True)
class EvaluationRunReplaySideV1:
    """One detached replay observation; mismatch is diagnostic, not a proof."""

    side: Literal["baseline", "effective", "candidate_effective"]
    declared_result_digest: str
    observed_result_digest: str
    result_match: bool
    declared_engine_frame_digests: tuple[str, ...]
    observed_engine_frame_digests: tuple[str, ...]
    engine_frame_match: bool
    side_replay_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.declared_result_digest, name="declared_result_digest")
        _require_token(self.observed_result_digest, name="observed_result_digest")
        if self.side not in {"baseline", "effective", "candidate_effective"}:
            raise EvaluationRunRuntimeErrorV1(
                "replay side is unsupported", code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID"
            )
        if not isinstance(self.result_match, bool) or not isinstance(self.engine_frame_match, bool):
            raise EvaluationRunRuntimeErrorV1(
                "replay comparison flags must be bool",
                code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID",
            )
        for digest in (*self.declared_engine_frame_digests, *self.observed_engine_frame_digests):
            _require_token(digest, name="engine_frame_digest")
        object.__setattr__(
            self,
            "side_replay_digest",
            _token(
                "evaluation_run_replay_side_v1",
                (
                    self.side,
                    self.declared_result_digest,
                    self.observed_result_digest,
                    self.result_match,
                    self.declared_engine_frame_digests,
                    self.observed_engine_frame_digests,
                    self.engine_frame_match,
                ),
            ),
        )


@dataclass(frozen=True)
class EvaluationRunReplayV1:
    """A replay report produced solely from an ``EvaluationRunV1`` capture."""

    run_digest: str
    replay_payload_digest: str
    program_envelope_digest: str
    status: Literal["matched", "mismatch"]
    baseline: EvaluationRunReplaySideV1
    effective: EvaluationRunReplaySideV1
    candidate_effective: EvaluationRunReplaySideV1 | None = None
    engine_pin_attestation: Literal["sealed_declared_pins_not_runtime_attested"] = (
        "sealed_declared_pins_not_runtime_attested"
    )
    proof_parity: Literal["not_claimed"] = "not_claimed"
    replay_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("run_digest", "replay_payload_digest", "program_envelope_digest"):
            _require_token(getattr(self, name), name=name)
        if self.status not in {"matched", "mismatch"}:
            raise EvaluationRunRuntimeErrorV1(
                "replay status is invalid", code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID"
            )
        if self.engine_pin_attestation != "sealed_declared_pins_not_runtime_attested":
            raise EvaluationRunRuntimeErrorV1(
                "replay engine-pin attestation is invalid",
                code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID",
            )
        if self.proof_parity != "not_claimed":
            raise EvaluationRunRuntimeErrorV1(
                "replay proof-parity claim is invalid",
                code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID",
            )
        if (
            not isinstance(self.baseline, EvaluationRunReplaySideV1)
            or self.baseline.side != "baseline"
        ):
            raise EvaluationRunRuntimeErrorV1(
                "baseline replay side is invalid", code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID"
            )
        if (
            not isinstance(self.effective, EvaluationRunReplaySideV1)
            or self.effective.side != "effective"
        ):
            raise EvaluationRunRuntimeErrorV1(
                "effective replay side is invalid", code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID"
            )
        if self.candidate_effective is not None and (
            not isinstance(self.candidate_effective, EvaluationRunReplaySideV1)
            or self.candidate_effective.side != "candidate_effective"
        ):
            raise EvaluationRunRuntimeErrorV1(
                "candidate replay side is invalid", code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID"
            )
        all_match = (
            self.baseline.result_match
            and self.baseline.engine_frame_match
            and self.effective.result_match
            and self.effective.engine_frame_match
        )
        if self.candidate_effective is not None:
            all_match = (
                all_match
                and self.candidate_effective.result_match
                and self.candidate_effective.engine_frame_match
            )
        if (self.status == "matched") != all_match:
            raise EvaluationRunRuntimeErrorV1(
                "replay status does not match side observations",
                code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID",
            )
        object.__setattr__(
            self,
            "replay_digest",
            _token(
                "evaluation_run_replay_v1",
                (
                    self.run_digest,
                    self.replay_payload_digest,
                    self.program_envelope_digest,
                    self.status,
                    self.baseline.side_replay_digest,
                    self.effective.side_replay_digest,
                    None
                    if self.candidate_effective is None
                    else self.candidate_effective.side_replay_digest,
                    self.engine_pin_attestation,
                    self.proof_parity,
                ),
            ),
        )


def replay_evaluation_run_v1(run: EvaluationRunV1) -> EvaluationRunReplayV1:
    """Re-execute exactly one captured run without a Store or provider callback.

    Invalid schemas/program envelopes and engine failures are fail-closed
    exceptions.  A valid re-execution that differs from the captured result is
    returned as ``status='mismatch'`` so a caller can preserve the diagnostic
    rather than mistaking it for a successful replay.
    """

    decoded = decode_evaluation_replay_program_v1(run)
    schema = _decode_schema_from_payload(run.replay_payload)
    baseline_relation = _world_relation(run.replay_payload.world("baseline"), schema)
    effective_relation = _world_relation(run.replay_payload.world("effective"), schema)
    baseline = _replay_side(
        declared=run.baseline,
        plan=run.plan,
        profile=run.execution_profile,
        compiled_plan=decoded.primary,
        schema_ir=schema,
        relation=baseline_relation,
        closure_target_digests=run.replay_payload.world("baseline").closure_target_digests,
    )
    effective = _replay_side(
        declared=run.effective,
        plan=run.plan,
        profile=run.execution_profile,
        compiled_plan=decoded.primary,
        schema_ir=schema,
        relation=effective_relation,
        closure_target_digests=run.replay_payload.world("effective").closure_target_digests,
    )
    candidate: EvaluationRunReplaySideV1 | None = None
    if run.candidate_plan is not None:
        assert run.candidate_effective is not None and decoded.candidate is not None
        candidate = _replay_side(
            declared=run.candidate_effective,
            plan=run.candidate_plan,
            profile=run.execution_profile,
            compiled_plan=decoded.candidate,
            schema_ir=schema,
            relation=effective_relation,
            closure_target_digests=run.replay_payload.world("effective").closure_target_digests,
        )
    matched = (
        baseline.result_match
        and baseline.engine_frame_match
        and effective.result_match
        and effective.engine_frame_match
    )
    if candidate is not None:
        matched = matched and candidate.result_match and candidate.engine_frame_match
    return EvaluationRunReplayV1(
        run_digest=run.run_digest,
        replay_payload_digest=run.replay_payload.payload_digest,
        program_envelope_digest=run.replay_payload.program_envelope_digest,
        status="matched" if matched else "mismatch",
        baseline=baseline,
        effective=effective,
        candidate_effective=candidate,
    )


def _replay_side(
    *,
    declared: EvaluationRunSideV1,
    plan: GoalPlanV1,
    profile: EvaluationExecutionProfileV1,
    compiled_plan: CompiledDerivationPlan,
    schema_ir: dict[str, Any],
    relation: Mapping[str, Sequence[ProjectedFact]],
    closure_target_digests: tuple[str, ...],
) -> EvaluationRunReplaySideV1:
    # A comparison run captures the union of its primary and candidate
    # dependencies as one shared effective world.  Each sealed compiled plan
    # must still receive *exactly* its own finite dependency inventory: broad
    # captured input is not an excuse for an engine to read an undeclared
    # predicate or for a missing predicate to look like an empty relation.
    try:
        dependency_ids = portable_dependency_predicate_ids_v1(
            compiled_plan,
            schema_ir=schema_ir,
        )
    except PortableEvaluationError as exc:
        raise EvaluationRunRuntimeErrorV1(
            "captured replay program is outside the deterministic profile",
            code="EVALUATION_RUN_V1_REPLAY_PROGRAM_UNSUPPORTED",
        ) from exc
    if set(dependency_ids) - set(relation):
        raise EvaluationRunRuntimeErrorV1(
            "captured replay world omits a sealed program dependency",
            code="EVALUATION_RUN_V1_REPLAY_RELATION_INCOMPLETE",
        )
    program_relation = {predicate_id: relation[predicate_id] for predicate_id in dependency_ids}
    try:
        observations = _observe_profile(
            profile=profile,
            compiled_plan=compiled_plan,
            schema_ir=schema_ir,
            relation=program_relation,
        )
    except EvaluationRunRuntimeErrorV1:
        raise
    except (PortableEvaluationError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            "detached replay engine execution failed",
            code="EVALUATION_RUN_V1_REPLAY_EXECUTION_FAILED",
        ) from exc
    observed_frames: list[EvaluationEngineResultV1] = []
    for observed in observations:
        if observed.status == "succeeded":
            assert observed.evaluation is not None
            observed_result = _goal_result_from_engine_output(
                plan=plan,
                output=observed.evaluation,
                closure_target_digests=closure_target_digests,
                # Exact-local closure belongs to the resolved *world*, which may
                # be the primary/candidate dependency union.  The engine sees only
                # its own strict subset, but absence must be checked against the
                # full captured world so an unrelated candidate-only relation
                # cannot look empty merely because it was not queried here.
                relation=relation,
                schema_ir=schema_ir,
            )
            observed_frames.append(EvaluationEngineResultV1(observed.engine, observed_result))
        else:
            assert observed.diagnostic is not None
            observed_frames.append(
                EvaluationEngineResultV1(
                    engine=observed.engine,
                    result=None,
                    status=observed.status,
                    diagnostic_code=observed.diagnostic.code,
                    diagnostic_detail_digest=observed.diagnostic.detail_digest,
                )
            )
    # Profile inventory is already protocol-sealed; still compare exact order so
    # a runtime cannot quietly drop an adapter frame during replay.
    if tuple(frame.engine for frame in observed_frames) != tuple(
        pin.engine for pin in profile.engines
    ):
        raise EvaluationRunRuntimeErrorV1(
            "detached replay engine inventory differs from profile",
            code="EVALUATION_RUN_V1_REPLAY_ENGINE_INVENTORY_MISMATCH",
        )
    canonical = observed_frames[0].result
    if canonical is None:
        raise EvaluationRunRuntimeErrorV1(
            "detached replay Native canonical engine did not produce a result",
            code="EVALUATION_RUN_V1_REPLAY_CANONICAL_ENGINE_UNAVAILABLE",
        )
    return EvaluationRunReplaySideV1(
        side=declared.name,
        declared_result_digest=declared.canonical_result.result_digest,
        observed_result_digest=canonical.result_digest,
        result_match=canonical.result_digest == declared.canonical_result.result_digest,
        declared_engine_frame_digests=tuple(item.frame_digest for item in declared.engine_results),
        observed_engine_frame_digests=tuple(item.frame_digest for item in observed_frames),
        engine_frame_match=tuple(item.frame_digest for item in observed_frames)
        == tuple(item.frame_digest for item in declared.engine_results),
    )


def _observe_profile(
    *,
    profile: EvaluationExecutionProfileV1,
    compiled_plan: CompiledDerivationPlan,
    schema_ir: dict[str, Any],
    relation: Mapping[str, Sequence[ProjectedFact]],
) -> tuple[PortableEngineObservationFrameV1, ...]:
    if profile.kind == "native_deterministic_v1":
        return (
            PortableEngineObservationFrameV1(
                engine="native",
                status="succeeded",
                evaluation=execute_native_deterministic_v1(
                    compiled_plan, schema_ir=schema_ir, effective_relations=relation
                ),
            ),
        )
    portable = observe_portable_deterministic_v1(
        compiled_plan, schema_ir=schema_ir, effective_relations=relation
    )
    return portable.frames


def _goal_result_from_engine_output(
    *,
    plan: GoalPlanV1,
    output: PortableEngineEvaluationV1,
    closure_target_digests: tuple[str, ...],
    relation: Mapping[str, Sequence[ProjectedFact]],
    schema_ir: Mapping[str, Any],
) -> GoalResultV1:
    all_rows: tuple[GoalResultRowV1, ...] = tuple(
        _goal_row_from_terms(plan, item.terms) for item in output.rows
    )
    # The engine output itself has unique selected rows, but make the check
    # explicit before a result-mode transform conceals an adapter regression.
    if len({row.semantic_row_digest for row in all_rows}) != len(all_rows):
        raise EvaluationRunRuntimeErrorV1(
            "engine returned duplicate semantic result rows",
            code="EVALUATION_RUN_V1_REPLAY_RESULT_SHAPE_INVALID",
        )
    rows: tuple[GoalResultRowV1, ...]
    exists_value: Literal["true", "false"] | None = None
    count_value: int | None = None
    if plan.result_mode in {"rows", "set"}:
        rows = all_rows
    elif plan.result_mode == "exists":
        exists_value = "true" if all_rows else "false"
        rows = all_rows[:1] if all_rows else ()
    elif plan.result_mode == "count":
        rows = all_rows
        count_value = len(all_rows)
    else:  # Protocol construction protects this; retain a defensive fail-close.
        raise EvaluationRunRuntimeErrorV1(
            "GoalPlan result mode is unsupported",
            code="EVALUATION_RUN_V1_REPLAY_RESULT_SHAPE_INVALID",
        )
    outcomes = _expectation_outcomes(
        plan=plan,
        all_rows=all_rows,
        closure_target_digests=closure_target_digests,
        relation=relation,
        schema_ir=schema_ir,
    )
    return GoalResultV1(
        plan_digest=plan.plan_digest,
        result_mode=plan.result_mode,
        completeness="complete",
        rows=rows,
        exists_value=exists_value,
        count_value=count_value,
        expectation_outcomes=outcomes,
    )


def _goal_row_from_terms(
    plan: GoalPlanV1, terms: tuple[tuple[str, object], ...]
) -> GoalResultRowV1:
    if len(terms) != len(plan.selections):
        raise EvaluationRunRuntimeErrorV1(
            "engine projection arity differs from sealed GoalPlan",
            code="EVALUATION_RUN_V1_REPLAY_RESULT_SHAPE_INVALID",
        )
    values: list[tuple[str, GoalValueV1]] = []
    for selection, term in zip(plan.selections, terms, strict=True):
        if not isinstance(term, tuple) or len(term) != 2 or term[0] != selection.value_tag:
            raise EvaluationRunRuntimeErrorV1(
                "engine projection tag differs from sealed GoalPlan",
                code="EVALUATION_RUN_V1_REPLAY_RESULT_SHAPE_INVALID",
            )
        values.append((selection.alias, _goal_value_from_raw(selection.value_tag, term[1])))
    return GoalResultRowV1(tuple(values))


def _expectation_outcomes(
    *,
    plan: GoalPlanV1,
    all_rows: tuple[GoalResultRowV1, ...],
    closure_target_digests: tuple[str, ...],
    relation: Mapping[str, Sequence[ProjectedFact]],
    schema_ir: Mapping[str, Any],
) -> tuple[GoalExpectationOutcomeV1, ...]:
    row_set = {_row_value_shape(row) for row in all_rows}
    outcomes: list[GoalExpectationOutcomeV1] = []
    for expectation in plan.expectations:
        status: Literal["satisfied", "not_satisfied", "underdetermined"]
        matched: tuple[str, ...] = ()
        diagnostic: str
        if isinstance(expectation, ContainsRowExpectationV1):
            matched = tuple(
                sorted(
                    row.semantic_row_digest
                    for row in all_rows
                    if _row_matches_expectation(row, expectation.row)
                )
            )
            status = "satisfied" if matched else "not_satisfied"
            diagnostic = (
                "GOAL_CONTAINS_ROW_SATISFIED" if matched else "GOAL_CONTAINS_ROW_NOT_SATISFIED"
            )
        elif isinstance(expectation, ExactLocalAbsenceExpectationV1):
            if expectation.closure_target_digest in closure_target_digests:
                if not _closure_target_holds_in_relation(
                    expectation.closure_target,
                    relation=relation,
                    schema_ir=schema_ir,
                ):
                    raise EvaluationRunRuntimeErrorV1(
                        "captured exact-local closure contradicts its captured relation",
                        code="EVALUATION_RUN_V1_CLOSURE_RELATION_MISMATCH",
                    )
                status = "satisfied"
                diagnostic = "GOAL_EXACT_LOCAL_ABSENCE_SATISFIED"
            else:
                status = "underdetermined"
                diagnostic = "GOAL_EXACT_LOCAL_CLOSURE_NOT_EFFECTIVE"
        elif isinstance(expectation, ExistsExpectationV1):
            actual = bool(all_rows)
            status = "satisfied" if actual == expectation.expected else "not_satisfied"
            diagnostic = (
                "GOAL_EXISTS_SATISFIED" if status == "satisfied" else "GOAL_EXISTS_NOT_SATISFIED"
            )
        elif isinstance(expectation, CountEqExpectationV1):
            status = "satisfied" if len(all_rows) == expectation.expected_count else "not_satisfied"
            diagnostic = (
                "GOAL_COUNT_SATISFIED" if status == "satisfied" else "GOAL_COUNT_NOT_SATISFIED"
            )
        elif isinstance(expectation, SetEqualsExpectationV1):
            # ``GoalRowExpectationV1.row_digest`` and
            # ``GoalResultRowV1.semantic_row_digest`` intentionally use
            # different domain-separation labels.  Equality here is equality
            # of the complete typed projection, not equality of unrelated
            # digest namespaces.
            expected = {
                tuple((alias, value.tag, value.value_digest) for alias, value in item.values)
                for item in expectation.rows
            }
            status = "satisfied" if row_set == expected else "not_satisfied"
            diagnostic = (
                "GOAL_SET_EQUALS_SATISFIED"
                if status == "satisfied"
                else "GOAL_SET_EQUALS_NOT_SATISFIED"
            )
        else:  # pragma: no cover - GoalPlanV1 already seals the union.
            raise EvaluationRunRuntimeErrorV1(
                "GoalPlan expectation is unsupported",
                code="EVALUATION_RUN_V1_REPLAY_RESULT_SHAPE_INVALID",
            )
        outcomes.append(
            GoalExpectationOutcomeV1(
                expectation_id=expectation.expectation_id,
                expectation_digest=expectation.expectation_digest,
                kind=expectation.kind,
                status=status,
                matched_semantic_row_digests=matched,
                diagnostic_code=diagnostic,
            )
        )
    return tuple(outcomes)


def _closure_target_holds_in_relation(
    target: ExactLocalClosureTargetV1,
    *,
    relation: Mapping[str, Sequence[ProjectedFact]],
    schema_ir: Mapping[str, Any],
) -> bool:
    """Verify resolver-owned closure against the sealed replay relation.

    A closure digest alone is deliberately insufficient: replay must not let a
    self-consistent forged payload restore the very tuple that Scenario removed
    and still report an exact absence as satisfied.  This is a structural
    check of the already captured effective world, not general NAF.
    """

    rows = tuple(relation.get(target.predicate_id or "", ()))
    if target.kind == "field":
        return not any(row.fact_tuple and row.fact_tuple[0] == target.entity_ref for row in rows)
    if target.kind == "member":
        assert target.value is not None
        return not any(
            len(row.fact_tuple) >= 2
            and row.fact_tuple[0] == target.entity_ref
            and row.fact_tuple[1] == target.value.to_raw()
            for row in rows
        )
    if target.kind == "exact_set":
        actual = {
            row.fact_tuple[1]
            for row in rows
            if len(row.fact_tuple) >= 2 and row.fact_tuple[0] == target.entity_ref
        }
        expected = {member.to_raw() for member in target.members}
        return actual == expected
    if target.kind == "relation":
        return not rows
    if target.kind == "assertion":
        return not any(row.asrt_id == target.assertion_id for row in rows)
    if target.kind == "entity":
        tags_by_predicate = _predicate_tags(dict(schema_ir))
        for predicate_id, predicate_rows in relation.items():
            tags = tags_by_predicate.get(predicate_id)
            if tags is None:
                raise EvaluationRunRuntimeErrorV1(
                    "captured replay relation has no schema domains",
                    code="EVALUATION_RUN_V1_CLOSURE_RELATION_MISMATCH",
                )
            for row in predicate_rows:
                if any(
                    tag == "entity_ref" and value == target.entity_ref
                    for tag, value in zip(tags, row.fact_tuple, strict=True)
                ):
                    return False
        return True
    raise AssertionError("validated exact-local closure kind is unreachable")


def _row_matches_expectation(row: GoalResultRowV1, expected: GoalRowExpectationV1) -> bool:
    actual = dict(row.values)
    return all(actual.get(alias) == value for alias, value in expected.values)


def _row_value_shape(row: GoalResultRowV1) -> tuple[tuple[str, str, str], ...]:
    return tuple((alias, value.tag, value.value_digest) for alias, value in row.values)


def _decode_schema_from_payload(payload: EvaluationReplayPayloadV1) -> dict[str, Any]:
    raw = _plain_json(payload.schema_bytes, label="captured replay schema")
    if not isinstance(raw, dict):
        raise EvaluationRunRuntimeErrorV1(
            "captured replay schema is not an object", code="EVALUATION_RUN_V1_SCHEMA_INVALID"
        )
    try:
        schema = ensure_schema_ir(raw)
    except Exception as exc:
        raise EvaluationRunRuntimeErrorV1(
            "captured replay schema is invalid", code="EVALUATION_RUN_V1_SCHEMA_INVALID"
        ) from exc
    if schema_digest(schema) != payload.schema_digest:
        raise EvaluationRunRuntimeErrorV1(
            "captured replay schema digest does not match payload",
            code="EVALUATION_RUN_V1_SCHEMA_PIN_MISMATCH",
        )
    return schema


def _predicate_tags(schema: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    tags: dict[str, tuple[str, ...]] = {}
    for raw in schema.get("predicates", []):
        if not isinstance(raw, dict):
            continue
        predicate_id = raw.get("pred_id")
        specs = raw.get("arg_specs")
        if not isinstance(predicate_id, str) or not isinstance(specs, list) or not specs:
            continue
        domains = tuple(
            item.get("type_domain") if isinstance(item, dict) else None for item in specs
        )
        if any(not isinstance(domain, str) for domain in domains):
            continue
        tags[predicate_id] = domains  # type: ignore[assignment]
    return tags


def _world_relation(
    world: EvaluationReplayWorldV1,
    schema: Mapping[str, Any],
) -> Mapping[str, tuple[ProjectedFact, ...]]:
    tags_by_predicate = _predicate_tags(schema)
    relation: dict[str, tuple[ProjectedFact, ...]] = {}
    seen_witnesses: set[str] = set()
    for captured in world.relations:
        expected_tags = tags_by_predicate.get(captured.predicate_id)
        if expected_tags is None or captured.value_tags != expected_tags:
            raise EvaluationRunRuntimeErrorV1(
                "captured replay relation does not match schema",
                code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH",
            )
        rows: list[ProjectedFact] = []
        for fact in captured.facts:
            if fact.witness_ref in seen_witnesses:
                raise EvaluationRunRuntimeErrorV1(
                    "captured replay relation repeats witness id",
                    code="EVALUATION_RUN_V1_RELATION_WITNESS_DUPLICATE",
                )
            seen_witnesses.add(fact.witness_ref)
            if tuple(value.tag for value in fact.values) != expected_tags:
                raise EvaluationRunRuntimeErrorV1(
                    "captured replay fact tags do not match schema",
                    code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH",
                )
            rows.append(
                ProjectedFact(
                    fact.witness_ref, tuple(_goal_value_to_raw(value) for value in fact.values)
                )
            )
        relation[captured.predicate_id] = tuple(rows)
    return relation


def _goal_value_from_raw(tag: str, raw: object) -> GoalValueV1:
    try:
        rows = claim_args_from_rest_terms([(tag, raw)])
    except (TypeError, ValueError) as exc:
        raise EvaluationRunRuntimeErrorV1(
            "captured value is not canonical for its declared type",
            code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH",
        ) from exc
    if len(rows) != 1 or rows[0][2] != tag:
        raise EvaluationRunRuntimeErrorV1(
            "captured value does not preserve declared type",
            code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH",
        )
    return GoalValueV1(tag, rows[0][1])  # type: ignore[arg-type]


def _goal_value_to_raw(value: GoalValueV1) -> object:
    if value.tag == "bytes":
        assert isinstance(value.value, str)
        try:
            raw = base64.urlsafe_b64decode(
                (value.value + "=" * (-len(value.value) % 4)).encode("ascii")
            )
        except (ValueError, UnicodeEncodeError, binascii.Error) as exc:  # protocol already guards
            raise EvaluationRunRuntimeErrorV1(
                "captured bytes value is invalid", code="EVALUATION_RUN_V1_RELATION_SCHEMA_MISMATCH"
            ) from exc
        return raw
    return value.value


def _assert_run_current(run: EvaluationRunV1) -> None:
    if not isinstance(run, EvaluationRunV1):
        raise EvaluationRunRuntimeErrorV1(
            "run must be EvaluationRunV1", code="EVALUATION_RUN_V1_REPLAY_INPUT_INVALID"
        )
    try:
        EvaluationRunV1.__post_init__(run)
    except ProtocolShapeError as exc:
        raise EvaluationRunRuntimeErrorV1(
            "run failed integrity validation", code="EVALUATION_RUN_V1_REPLAY_RUN_INVALID"
        ) from exc


@dataclass(frozen=True)
class EvaluationRunExplanationV1:
    """A structural Explain envelope with intentionally limited proof claims."""

    run_digest: str
    target: ExplainTargetV1
    result_digest: str
    world_capture_digest: str
    semantic_world_digest: str
    observation: Literal["positive_row_observed", "result_summary_observed"]
    logical_conclusion: Literal["holds", "not_claimed"]
    policy_structure: PolicyStructureV0 | None = field(default=None, repr=False, compare=False)
    policy_structure_capture: Literal["captured", "not_captured"] = "not_captured"
    scenario_operations: tuple[ResolvedScenarioOperationV1, ...] | None = field(
        default=None, repr=False, compare=False
    )
    scenario_patch_capture: Literal["captured", "not_captured"] = "not_captured"
    scenario_patch_application: Literal["applied", "not_applied", "not_captured"] = "not_captured"
    engine_evidence: Literal["not_captured"] = "not_captured"
    negative_proof: Literal["not_claimed"] = "not_claimed"
    proof_parity: Literal["not_claimed"] = "not_claimed"
    provider_receipt_count: int = 0
    explanation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "run_digest",
            "result_digest",
            "world_capture_digest",
            "semantic_world_digest",
        ):
            _require_token(getattr(self, name), name=name)
        if not isinstance(self.target, ExplainTargetV1):
            raise EvaluationRunRuntimeErrorV1(
                "Explain target is invalid", code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID"
            )
        if self.observation not in {"positive_row_observed", "result_summary_observed"}:
            raise EvaluationRunRuntimeErrorV1(
                "Explain observation is invalid", code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID"
            )
        if self.logical_conclusion not in {"holds", "not_claimed"}:
            raise EvaluationRunRuntimeErrorV1(
                "Explain conclusion is invalid", code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID"
            )
        if self.observation == "positive_row_observed" and self.logical_conclusion != "holds":
            raise EvaluationRunRuntimeErrorV1(
                "positive row Explain must identify only the observed held row",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if (
            self.observation == "result_summary_observed"
            and self.logical_conclusion != "not_claimed"
        ):
            raise EvaluationRunRuntimeErrorV1(
                "summary Explain must not claim a logical conclusion",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if self.policy_structure_capture not in {"captured", "not_captured"}:
            raise EvaluationRunRuntimeErrorV1(
                "Explain policy structure capture state is invalid",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if (self.policy_structure_capture == "captured") != isinstance(
            self.policy_structure, PolicyStructureV0
        ):
            raise EvaluationRunRuntimeErrorV1(
                "Explain policy structure capture does not match structure payload",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if self.scenario_patch_capture not in {"captured", "not_captured"}:
            raise EvaluationRunRuntimeErrorV1(
                "Explain Scenario patch capture state is invalid",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if (self.scenario_patch_capture == "captured") != isinstance(
            self.scenario_operations, tuple
        ):
            raise EvaluationRunRuntimeErrorV1(
                "Explain Scenario patch capture does not match operation payload",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if self.scenario_operations is not None and not all(
            isinstance(operation, ResolvedScenarioOperationV1)
            for operation in self.scenario_operations
        ):
            raise EvaluationRunRuntimeErrorV1(
                "Explain Scenario patch operations are malformed",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        allowed_patch_application = (
            {"not_captured"}
            if self.scenario_patch_capture == "not_captured"
            else {"applied", "not_applied"}
        )
        if self.scenario_patch_application not in allowed_patch_application:
            raise EvaluationRunRuntimeErrorV1(
                "Explain Scenario patch application state is invalid",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        if (
            isinstance(self.provider_receipt_count, bool)
            or not isinstance(self.provider_receipt_count, int)
            or self.provider_receipt_count < 0
        ):
            raise EvaluationRunRuntimeErrorV1(
                "provider receipt count is invalid", code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID"
            )
        object.__setattr__(
            self,
            "explanation_digest",
            _token(
                "evaluation_run_explanation_v1",
                (
                    self.run_digest,
                    self.target.target_digest,
                    self.result_digest,
                    self.world_capture_digest,
                    self.semantic_world_digest,
                    self.observation,
                    self.logical_conclusion,
                    None
                    if self.policy_structure is None
                    else self.policy_structure.structure_digest,
                    self.policy_structure_capture,
                    None
                    if self.scenario_operations is None
                    else _scenario_patch_to_wire(self.scenario_operations)["patch_digest"],
                    self.scenario_patch_capture,
                    self.scenario_patch_application,
                    self.engine_evidence,
                    self.negative_proof,
                    self.proof_parity,
                    self.provider_receipt_count,
                ),
            ),
        )


def explain_evaluation_run_v1(
    run: EvaluationRunV1,
    target: ExplainTargetV1,
) -> EvaluationRunExplanationV1:
    """Return an explicit row/summary structural Explain envelope.

    No default target exists.  In particular, an empty result summary never
    becomes ``false`` or a negative proof merely because it has no row anchor.
    """

    _assert_run_current(run)
    if not isinstance(target, ExplainTargetV1):
        raise EvaluationRunRuntimeErrorV1(
            "Explain requires explicit ExplainTargetV1",
            code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
        )
    try:
        ExplainTargetV1.__post_init__(target)
    except ProtocolShapeError as exc:
        raise EvaluationRunRuntimeErrorV1(
            "Explain target is malformed", code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID"
        ) from exc
    side = _run_side(run, target.side)
    if target.kind == "row":
        anchors = {
            row.anchor.anchor_digest for row in side.canonical_result.rows if row.anchor is not None
        }
        if target.anchor_digest not in anchors:
            raise EvaluationRunRuntimeErrorV1(
                "Explain row target does not belong to this sealed run",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        observation: Literal["positive_row_observed", "result_summary_observed"] = (
            "positive_row_observed"
        )
        conclusion: Literal["holds", "not_claimed"] = "holds"
    else:
        assert side.canonical_result.summary_anchor is not None
        if target.anchor_digest != side.canonical_result.summary_anchor.summary_anchor_digest:
            raise EvaluationRunRuntimeErrorV1(
                "Explain summary target does not belong to this sealed run",
                code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
            )
        observation = "result_summary_observed"
        conclusion = "not_claimed"
    world = run.replay_payload.world(side.world_side)
    decoded = decode_evaluation_replay_program_v1(run)
    policy_structure = (
        decoded.candidate_policy_structure
        if target.side == "candidate_effective"
        else decoded.primary_policy_structure
    )
    scenario_operations = decoded.scenario_operations
    return EvaluationRunExplanationV1(
        run_digest=run.run_digest,
        target=target,
        result_digest=side.canonical_result.result_digest,
        world_capture_digest=world.world_capture_digest,
        semantic_world_digest=world.semantic_world_digest,
        observation=observation,
        logical_conclusion=conclusion,
        policy_structure=policy_structure,
        policy_structure_capture=("captured" if policy_structure is not None else "not_captured"),
        scenario_operations=scenario_operations,
        scenario_patch_capture=("captured" if scenario_operations is not None else "not_captured"),
        scenario_patch_application=(
            "not_captured"
            if scenario_operations is None
            else (
                "applied"
                if target.side in {"effective", "candidate_effective"} and bool(scenario_operations)
                else "not_applied"
            )
        ),
        provider_receipt_count=len(run.replay_payload.provider_receipts),
    )


def _run_side(run: EvaluationRunV1, side_name: str) -> EvaluationRunSideV1:
    if side_name == "baseline":
        return run.baseline
    if side_name == "effective":
        return run.effective
    if side_name == "candidate_effective" and run.candidate_effective is not None:
        return run.candidate_effective
    raise EvaluationRunRuntimeErrorV1(
        "Explain target refers to an absent run side",
        code="EVALUATION_RUN_V1_EXPLAIN_TARGET_INVALID",
    )


@dataclass(frozen=True)
class PolicyVariantComparisonV1:
    """A non-causal comparison of two immutable compiled Query targets.

    ``compiled_*_equal`` describes the lowered executable program only.  When
    both sides supplied a sealed :class:`PolicyStructureV0`, the separate
    ``authored_structure_relation`` describes that authored topology.  A
    structure difference is deliberately *not* a node-level explanation or
    causal attribution for a result difference.
    """

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
    authored_structure_relation: Literal["captured", "equivalent", "different", "not_captured"]
    shared_semantic_row_digests: tuple[str, ...]
    primary_only_semantic_row_digests: tuple[str, ...]
    candidate_only_semantic_row_digests: tuple[str, ...]
    result_relation: Literal["equivalent", "different"]
    structural_basis: Literal["captured_compiled_derivation_body_and_head"] = (
        "captured_compiled_derivation_body_and_head"
    )
    causal_attribution: Literal["not_claimed"] = "not_claimed"
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
            _require_token(getattr(self, name), name=name)
        for name in ("primary_policy_structure_digest", "candidate_policy_structure_digest"):
            value = getattr(self, name)
            if value is not None:
                # ``PolicyStructureV0`` predates V1's ``sha256:`` token
                # convention and deliberately exposes a bare canonical hex
                # digest.  Preserve that existing protocol at the boundary.
                _require_plain_sha256(value, name=name)
        if self.primary_target_digest == self.candidate_target_digest:
            raise EvaluationRunRuntimeErrorV1(
                "policy comparison requires distinct immutable target pins",
                code="EVALUATION_RUN_V1_COMPARISON_INVALID",
            )
        if self.result_relation not in {"equivalent", "different"}:
            raise EvaluationRunRuntimeErrorV1(
                "comparison result relation is invalid", code="EVALUATION_RUN_V1_COMPARISON_INVALID"
            )
        if self.structural_basis != "captured_compiled_derivation_body_and_head":
            raise EvaluationRunRuntimeErrorV1(
                "comparison structural basis is invalid",
                code="EVALUATION_RUN_V1_COMPARISON_INVALID",
            )
        primary_structure = self.primary_policy_structure_digest
        candidate_structure = self.candidate_policy_structure_digest
        if primary_structure is None and candidate_structure is None:
            expected_structure_relation = "not_captured"
        elif primary_structure is None or candidate_structure is None:
            # One captured topology is useful context, but it cannot support
            # an equivalence/difference claim about a missing other side.
            expected_structure_relation = "captured"
        elif primary_structure == candidate_structure:
            expected_structure_relation = "equivalent"
        else:
            expected_structure_relation = "different"
        if self.authored_structure_relation != expected_structure_relation:
            raise EvaluationRunRuntimeErrorV1(
                "comparison authored structure relation does not match captured structure pins",
                code="EVALUATION_RUN_V1_COMPARISON_INVALID",
            )
        if self.causal_attribution != "not_claimed":
            raise EvaluationRunRuntimeErrorV1(
                "comparison causal attribution must remain not claimed",
                code="EVALUATION_RUN_V1_COMPARISON_INVALID",
            )
        for values in (
            self.shared_semantic_row_digests,
            self.primary_only_semantic_row_digests,
            self.candidate_only_semantic_row_digests,
        ):
            if tuple(sorted(values)) != values or len(set(values)) != len(values):
                raise EvaluationRunRuntimeErrorV1(
                    "comparison row digests must be canonical sets",
                    code="EVALUATION_RUN_V1_COMPARISON_INVALID",
                )
            for value in values:
                _require_token(value, name="semantic_row_digest")
        if set(self.shared_semantic_row_digests) & set(self.primary_only_semantic_row_digests):
            raise EvaluationRunRuntimeErrorV1(
                "comparison primary rows overlap", code="EVALUATION_RUN_V1_COMPARISON_INVALID"
            )
        if set(self.shared_semantic_row_digests) & set(self.candidate_only_semantic_row_digests):
            raise EvaluationRunRuntimeErrorV1(
                "comparison candidate rows overlap", code="EVALUATION_RUN_V1_COMPARISON_INVALID"
            )
        different = bool(
            self.primary_only_semantic_row_digests or self.candidate_only_semantic_row_digests
        )
        if (self.result_relation == "different") != different:
            raise EvaluationRunRuntimeErrorV1(
                "comparison result relation does not match row-set diff",
                code="EVALUATION_RUN_V1_COMPARISON_INVALID",
            )
        object.__setattr__(
            self,
            "comparison_digest",
            _token(
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
                    self.shared_semantic_row_digests,
                    self.primary_only_semantic_row_digests,
                    self.candidate_only_semantic_row_digests,
                    self.result_relation,
                    self.structural_basis,
                    self.causal_attribution,
                ),
            ),
        )


def compare_policy_variants_v1(run: EvaluationRunV1) -> PolicyVariantComparisonV1:
    """Compare captured candidate/primary programs and effective result sets.

    The comparison is intentionally descriptive.  Identical/different bodies
    and selected row sets do not prove which authored Rule, fact, provider, or
    Scenario operation caused any observed difference.
    """

    _assert_run_current(run)
    if run.candidate_plan is None or run.candidate_effective is None:
        raise EvaluationRunRuntimeErrorV1(
            "run has no immutable candidate comparison",
            code="EVALUATION_RUN_V1_COMPARISON_UNAVAILABLE",
        )
    decoded = decode_evaluation_replay_program_v1(run)
    assert decoded.candidate is not None and decoded.candidate_compiled_plan_digest is not None
    primary_rows = {row.semantic_row_digest for row in run.effective.canonical_result.rows}
    candidate_rows = {
        row.semantic_row_digest for row in run.candidate_effective.canonical_result.rows
    }
    return PolicyVariantComparisonV1(
        primary_plan_digest=run.plan.plan_digest,
        candidate_plan_digest=run.candidate_plan.plan_digest,
        effective_world_capture_digest=run.replay_payload.world("effective").world_capture_digest,
        primary_target_digest=run.plan.target.target_digest,
        candidate_target_digest=run.candidate_plan.target.target_digest,
        primary_compiled_plan_digest=decoded.primary_compiled_plan_digest,
        candidate_compiled_plan_digest=decoded.candidate_compiled_plan_digest,
        compiled_body_equal=decoded.primary.body_ir == decoded.candidate.body_ir,
        compiled_head_equal=decoded.primary.heads == decoded.candidate.heads,
        primary_policy_structure_digest=(
            None
            if decoded.primary_policy_structure is None
            else decoded.primary_policy_structure.structure_digest
        ),
        candidate_policy_structure_digest=(
            None
            if decoded.candidate_policy_structure is None
            else decoded.candidate_policy_structure.structure_digest
        ),
        authored_structure_relation=(
            "not_captured"
            if decoded.primary_policy_structure is None
            and decoded.candidate_policy_structure is None
            else (
                "captured"
                if decoded.primary_policy_structure is None
                or decoded.candidate_policy_structure is None
                else (
                    "equivalent"
                    if decoded.primary_policy_structure.structure_digest
                    == decoded.candidate_policy_structure.structure_digest
                    else "different"
                )
            )
        ),
        shared_semantic_row_digests=tuple(sorted(primary_rows & candidate_rows)),
        primary_only_semantic_row_digests=tuple(sorted(primary_rows - candidate_rows)),
        candidate_only_semantic_row_digests=tuple(sorted(candidate_rows - primary_rows)),
        result_relation="equivalent" if primary_rows == candidate_rows else "different",
    )


@dataclass(frozen=True)
class ScenarioDiffV1:
    """A sealed, descriptive baseline/effective diff for one Scenario run.

    This is deliberately a *comparison artifact*, not another evaluator.  It
    is derived only from the two worlds and normalized results already sealed
    into an :class:`EvaluationRunV1`; it never accepts a ``Store`` or executes
    a fresh program.  In particular, a relation or selected-row difference is
    not evidence that one Scenario operation caused it, and it is not a claim
    about engine proof/evidence parity.

    ``baseline_world_capture_digest`` and ``effective_world_capture_digest``
    preserve exact capture identity.  The explicit semantic/relation/
    resolution/closure pins make the input-difference axes inspectable rather
    than treating the inevitable ``baseline``/``effective`` capture labels as
    a semantic change by themselves.
    """

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
    input_difference_axes: tuple[
        Literal[
            "semantic_world",
            "relation_snapshot",
            "resolution_evidence",
            "closure_targets",
        ],
        ...,
    ]
    scenario_operations: tuple[ResolvedScenarioOperationV1, ...] | None = field(
        default=None, repr=False, compare=False
    )
    scenario_patch_capture: Literal["captured", "not_captured"] = "not_captured"
    scenario_patch_application: Literal["applied", "no_effective_operation", "not_captured"] = (
        "not_captured"
    )
    scenario_patch_digest: str | None = None
    scenario_operation_digests: tuple[str, ...] = ()
    shared_semantic_row_digests: tuple[str, ...] = ()
    baseline_only_semantic_row_digests: tuple[str, ...] = ()
    effective_only_semantic_row_digests: tuple[str, ...] = ()
    result_relation: Literal["equivalent", "different"] = "equivalent"
    evidence_relation: Literal["not_claimed"] = "not_claimed"
    causal_attribution: Literal["not_claimed"] = "not_claimed"
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
            _require_token(getattr(self, name), name=name)

        for values in (
            self.baseline_closure_target_digests,
            self.effective_closure_target_digests,
        ):
            if tuple(sorted(values)) != values or len(set(values)) != len(values):
                raise EvaluationRunRuntimeErrorV1(
                    "Scenario diff closure target digests must be canonical sets",
                    code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
                )
            for value in values:
                _require_token(value, name="closure_target_digest")

        axis_order: tuple[
            Literal[
                "semantic_world",
                "relation_snapshot",
                "resolution_evidence",
                "closure_targets",
            ],
            ...,
        ] = (
            "semantic_world",
            "relation_snapshot",
            "resolution_evidence",
            "closure_targets",
        )
        allowed_axes = set(axis_order)
        if (
            not isinstance(self.input_difference_axes, tuple)
            or any(axis not in allowed_axes for axis in self.input_difference_axes)
            or len(set(self.input_difference_axes)) != len(self.input_difference_axes)
        ):
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff input difference axes are malformed",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )
        changed_by_axis: tuple[bool, ...] = (
            self.baseline_semantic_world_digest != self.effective_semantic_world_digest,
            self.baseline_relation_snapshot_digest != self.effective_relation_snapshot_digest,
            self.baseline_resolution_evidence_digest != self.effective_resolution_evidence_digest,
            self.baseline_closure_target_digests != self.effective_closure_target_digests,
        )
        expected_axes: tuple[
            Literal[
                "semantic_world",
                "relation_snapshot",
                "resolution_evidence",
                "closure_targets",
            ],
            ...,
        ] = tuple(
            axis for axis, changed in zip(axis_order, changed_by_axis, strict=True) if changed
        )
        if self.input_difference_axes != expected_axes:
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff input difference axes do not match captured worlds",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )

        if self.scenario_patch_capture not in {"captured", "not_captured"}:
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff patch capture state is invalid",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )
        if self.scenario_patch_capture == "captured":
            if (
                not isinstance(self.scenario_operations, tuple)
                or not all(
                    isinstance(operation, ResolvedScenarioOperationV1)
                    for operation in self.scenario_operations
                )
                or self.scenario_patch_digest is None
            ):
                raise EvaluationRunRuntimeErrorV1(
                    "captured Scenario diff requires resolved operations and patch digest",
                    code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
                )
            expected_patch_digest = _scenario_patch_to_wire(self.scenario_operations)[
                "patch_digest"
            ]
            if self.scenario_patch_digest != expected_patch_digest:
                raise EvaluationRunRuntimeErrorV1(
                    "Scenario diff patch digest does not match resolved operations",
                    code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
                )
            expected_operation_digests = tuple(
                operation.operation_digest for operation in self.scenario_operations
            )
            expected_patch_application = (
                "applied" if self.scenario_operations else "no_effective_operation"
            )
        else:
            if self.scenario_operations is not None or self.scenario_patch_digest is not None:
                raise EvaluationRunRuntimeErrorV1(
                    "uncaptured Scenario diff cannot carry a patch payload",
                    code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
                )
            expected_operation_digests = ()
            expected_patch_application = "not_captured"
        if self.scenario_patch_application != expected_patch_application:
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff patch application state does not match capture",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )
        if self.scenario_operation_digests != expected_operation_digests:
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff operation digests do not match patch capture",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )
        if self.scenario_patch_digest is not None:
            _require_token(self.scenario_patch_digest, name="scenario_patch_digest")
        for digest in self.scenario_operation_digests:
            _require_token(digest, name="scenario_operation_digest")

        for values in (
            self.shared_semantic_row_digests,
            self.baseline_only_semantic_row_digests,
            self.effective_only_semantic_row_digests,
        ):
            if tuple(sorted(values)) != values or len(set(values)) != len(values):
                raise EvaluationRunRuntimeErrorV1(
                    "Scenario diff row digests must be canonical sets",
                    code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
                )
            for value in values:
                _require_token(value, name="semantic_row_digest")
        shared = set(self.shared_semantic_row_digests)
        baseline_only = set(self.baseline_only_semantic_row_digests)
        effective_only = set(self.effective_only_semantic_row_digests)
        if shared & baseline_only or shared & effective_only or baseline_only & effective_only:
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff row sets overlap", code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID"
            )
        different = bool(baseline_only or effective_only)
        if (
            self.result_relation not in {"equivalent", "different"}
            or (self.result_relation == "different") != different
        ):
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff result relation does not match row-set diff",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )
        if self.evidence_relation != "not_claimed" or self.causal_attribution != "not_claimed":
            raise EvaluationRunRuntimeErrorV1(
                "Scenario diff cannot claim evidence or causal attribution",
                code="EVALUATION_RUN_V1_SCENARIO_DIFF_INVALID",
            )
        object.__setattr__(
            self,
            "diff_digest",
            _token(
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
                    "baseline_resolution_evidence_digest": self.baseline_resolution_evidence_digest,
                    "effective_resolution_evidence_digest": self.effective_resolution_evidence_digest,
                    "baseline_closure_target_digests": self.baseline_closure_target_digests,
                    "effective_closure_target_digests": self.effective_closure_target_digests,
                    "input_difference_axes": self.input_difference_axes,
                    "scenario_patch_capture": self.scenario_patch_capture,
                    "scenario_patch_application": self.scenario_patch_application,
                    "scenario_patch_digest": self.scenario_patch_digest,
                    "scenario_operation_digests": self.scenario_operation_digests,
                    "shared_semantic_row_digests": self.shared_semantic_row_digests,
                    "baseline_only_semantic_row_digests": self.baseline_only_semantic_row_digests,
                    "effective_only_semantic_row_digests": self.effective_only_semantic_row_digests,
                    "result_relation": self.result_relation,
                    "evidence_relation": self.evidence_relation,
                    "causal_attribution": self.causal_attribution,
                },
            ),
        )


def diff_scenario_run_v1(run: EvaluationRunV1) -> ScenarioDiffV1:
    """Describe one sealed Scenario baseline/effective pair without replaying it.

    A normal Query intentionally has baseline/effective worlds too, because
    that keeps the execution protocol uniform.  It must not therefore obtain a
    what-if diff by accident: callers need an explicit Scenario request pin.
    """

    _assert_run_current(run)
    if run.plan.scenario_request_digest is None:
        raise EvaluationRunRuntimeErrorV1(
            "run has no explicit Scenario request",
            code="EVALUATION_RUN_V1_SCENARIO_DIFF_UNAVAILABLE",
        )
    baseline_world = run.replay_payload.world("baseline")
    effective_world = run.replay_payload.world("effective")
    decoded = decode_evaluation_replay_program_v1(run)
    operations = decoded.scenario_operations
    patch_digest = (
        None if operations is None else _scenario_patch_to_wire(operations)["patch_digest"]
    )
    baseline_rows = {row.semantic_row_digest for row in run.baseline.canonical_result.rows}
    effective_rows = {row.semantic_row_digest for row in run.effective.canonical_result.rows}
    axes = tuple(
        axis
        for axis, changed in (
            (
                "semantic_world",
                baseline_world.semantic_world_digest != effective_world.semantic_world_digest,
            ),
            (
                "relation_snapshot",
                baseline_world.relation_snapshot_digest != effective_world.relation_snapshot_digest,
            ),
            (
                "resolution_evidence",
                baseline_world.resolution_evidence_digest
                != effective_world.resolution_evidence_digest,
            ),
            (
                "closure_targets",
                baseline_world.closure_target_digests != effective_world.closure_target_digests,
            ),
        )
        if changed
    )
    return ScenarioDiffV1(
        run_digest=run.run_digest,
        plan_digest=run.plan.plan_digest,
        scenario_request_digest=run.plan.scenario_request_digest,
        baseline_world_capture_digest=baseline_world.world_capture_digest,
        effective_world_capture_digest=effective_world.world_capture_digest,
        baseline_semantic_world_digest=baseline_world.semantic_world_digest,
        effective_semantic_world_digest=effective_world.semantic_world_digest,
        baseline_relation_snapshot_digest=baseline_world.relation_snapshot_digest,
        effective_relation_snapshot_digest=effective_world.relation_snapshot_digest,
        baseline_resolution_evidence_digest=baseline_world.resolution_evidence_digest,
        effective_resolution_evidence_digest=effective_world.resolution_evidence_digest,
        baseline_closure_target_digests=baseline_world.closure_target_digests,
        effective_closure_target_digests=effective_world.closure_target_digests,
        input_difference_axes=axes,  # type: ignore[arg-type]
        scenario_operations=operations,
        scenario_patch_capture="captured" if operations is not None else "not_captured",
        scenario_patch_application=(
            "not_captured"
            if operations is None
            else ("applied" if operations else "no_effective_operation")
        ),
        scenario_patch_digest=patch_digest,  # type: ignore[arg-type]
        scenario_operation_digests=(
            ()
            if operations is None
            else tuple(operation.operation_digest for operation in operations)
        ),
        shared_semantic_row_digests=tuple(sorted(baseline_rows & effective_rows)),
        baseline_only_semantic_row_digests=tuple(sorted(baseline_rows - effective_rows)),
        effective_only_semantic_row_digests=tuple(sorted(effective_rows - baseline_rows)),
        result_relation="equivalent" if baseline_rows == effective_rows else "different",
    )


__all__ = [
    "DecodedEvaluationReplayProgramV1",
    "EvaluationRunExplanationV1",
    "EvaluationRunReplaySideV1",
    "EvaluationRunReplayV1",
    "EvaluationRunRuntimeErrorV1",
    "PolicyVariantComparisonV1",
    "ScenarioDiffV1",
    "build_evaluation_replay_program_envelope_v1",
    "capture_evaluation_replay_payload_v1",
    "capture_evaluation_replay_world_v1",
    "compare_policy_variants_v1",
    "decode_evaluation_replay_program_v1",
    "diff_scenario_run_v1",
    "explain_evaluation_run_v1",
    "replay_evaluation_run_v1",
]
