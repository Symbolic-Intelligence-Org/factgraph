from __future__ import annotations

import base64
import json
import math
import struct
from dataclasses import dataclass
from typing import Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import (
    CANONICAL_TAGS,
    canonical_bytes_tup_v1,
    claim_args_from_rest_terms,
)
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs, schema_digest

from .common import ProtocolShapeError
from .evaluation_run import (
    EvaluationRunAnchorV0,
    _plain,
    _sha_hex,
    _sha_token,
    _text,
)
from .evaluation_run import (
    _seal as _seal_token,
)
from .evaluation_run import (
    _token as _anchor_token,
)

RunBundleScalar: TypeAlias = str | int | bool
_MAX_EVALUATION_RUN_VALUES = 64


def _token(label: str, payload: object) -> str:
    """Digest nested protocol DTOs through the F4A canonical plain form."""
    return _anchor_token(label, _plain(payload))


@dataclass(frozen=True, repr=False)
class EvaluationRunValueV0:
    """One canonical tup_v1 value in JSON-safe storage form."""

    tag: Literal["entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid"]
    value: RunBundleScalar

    def __post_init__(self) -> None:
        if self.tag not in CANONICAL_TAGS:
            raise ProtocolShapeError("EvaluationRun bundle value tag is unsupported")
        try:
            normalized = claim_args_from_rest_terms(
                [(self.tag, _storage_to_raw(self.tag, self.value))]
            )[0][1]
        except (TypeError, ValueError) as exc:
            raise ProtocolShapeError("EvaluationRun bundle value is not canonical tup_v1") from exc
        if type(normalized) is not type(self.value) or normalized != self.value:
            raise ProtocolShapeError("EvaluationRun bundle value is not in canonical storage form")

    @property
    def digest(self) -> str:
        return sha256_hex(
            canonical_bytes_tup_v1([(self.tag, _storage_to_raw(self.tag, self.value))])
        )

    def __repr__(self) -> str:
        return f"EvaluationRunValueV0(tag={self.tag!r}, value=<redacted>)"


@dataclass(frozen=True, repr=False)
class EvaluationRunNativePlanV0:
    derivation_id: str
    version: str
    target_pred_id: str
    head_var_names: tuple[str, ...]
    where_bytes: bytes
    where_digest: str
    plan_digest: str

    def __post_init__(self) -> None:
        for name in ("derivation_id", "version", "target_pred_id"):
            _text(getattr(self, name), name)
        if (
            not isinstance(self.head_var_names, tuple)
            or not self.head_var_names
            or len(self.head_var_names) > _MAX_EVALUATION_RUN_VALUES
            or not all(isinstance(item, str) and item for item in self.head_var_names)
        ):
            raise ProtocolShapeError("EvaluationRun native plan head_var_names are malformed")
        if not isinstance(self.where_bytes, bytes) or not self.where_bytes:
            raise ProtocolShapeError(
                "EvaluationRun native plan where_bytes must be non-empty bytes"
            )
        _seal_token(self.where_digest, f"sha256:{sha256_hex(self.where_bytes)}", "where_digest")
        expected = _token(
            "evaluation_run_native_plan_v0",
            (
                self.derivation_id,
                self.version,
                self.target_pred_id,
                self.head_var_names,
                self.where_digest,
            ),
        )
        _seal_token(self.plan_digest, expected, "plan_digest")

    def __repr__(self) -> str:
        return (
            f"EvaluationRunNativePlanV0(plan_digest={self.plan_digest!r}, where_bytes=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class EvaluationRunRelationV0:
    predicate_id: str
    value_types: tuple[str, ...]
    facts: tuple[tuple[str, tuple[EvaluationRunValueV0, ...]], ...]

    def __post_init__(self) -> None:
        _text(self.predicate_id, "relation predicate_id")
        if (
            not isinstance(self.value_types, tuple)
            or not self.value_types
            or len(self.value_types) > _MAX_EVALUATION_RUN_VALUES
            or any(value_type not in CANONICAL_TAGS for value_type in self.value_types)
        ):
            raise ProtocolShapeError("EvaluationRun relation value_types are malformed")
        if not isinstance(self.facts, tuple) or any(
            not isinstance(fact, tuple)
            or len(fact) != 2
            or not isinstance(fact[0], str)
            or not fact[0]
            or not isinstance(fact[1], tuple)
            or len(fact[1]) > _MAX_EVALUATION_RUN_VALUES
            or not all(isinstance(value, EvaluationRunValueV0) for value in fact[1])
            or tuple(value.tag for value in fact[1]) != self.value_types
            for fact in self.facts
        ):
            raise ProtocolShapeError("EvaluationRun relation facts are malformed")
        if len({fact[0] for fact in self.facts}) != len(self.facts):
            raise ProtocolShapeError("EvaluationRun relation assertion ids must be unique")

    def __repr__(self) -> str:
        return f"EvaluationRunRelationV0(predicate_id={self.predicate_id!r}, facts=<redacted>)"


@dataclass(frozen=True, repr=False)
class EvaluationRunProjectionRowV0:
    ordinal: int
    row_id: str
    claim_digest: str
    head_scope_digest: str
    certainty: tuple[str, str, str] | None
    certainty_digest: str
    values: tuple[tuple[str, EvaluationRunValueV0], ...]
    proof_receipt_bytes: bytes
    proof_receipt_digest: str
    row_capture_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool) or self.ordinal < 0:
            raise ProtocolShapeError("EvaluationRun projection ordinal must be non-negative int")
        _text(self.row_id, "projection row_id")
        for name in ("claim_digest", "head_scope_digest", "certainty_digest"):
            _sha_token(getattr(self, name), name)
        if _certainty_digest(self.certainty) != self.certainty_digest:
            raise ProtocolShapeError("EvaluationRun projection certainty does not match its digest")
        if (
            not isinstance(self.values, tuple)
            or not self.values
            or len(self.values) > _MAX_EVALUATION_RUN_VALUES
            or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not item[0]
                or not isinstance(item[1], EvaluationRunValueV0)
                for item in self.values
            )
            or len({item[0] for item in self.values}) != len(self.values)
        ):
            raise ProtocolShapeError("EvaluationRun projection values are malformed")
        if not isinstance(self.proof_receipt_bytes, bytes) or not self.proof_receipt_bytes:
            raise ProtocolShapeError("EvaluationRun projection row requires ProofReceipt bytes")
        _seal_token(
            self.proof_receipt_digest,
            f"sha256:{sha256_hex(self.proof_receipt_bytes)}",
            "proof_receipt_digest",
        )
        expected = _token(
            "evaluation_run_projection_row_v0",
            (
                self.ordinal,
                self.row_id,
                self.claim_digest,
                self.head_scope_digest,
                self.certainty,
                self.certainty_digest,
                self.values,
                self.proof_receipt_digest,
            ),
        )
        _seal_token(self.row_capture_digest, expected, "row_capture_digest")

    def __repr__(self) -> str:
        return f"EvaluationRunProjectionRowV0(ordinal={self.ordinal}, values=<redacted>, proof_receipt=<redacted>)"


@dataclass(frozen=True)
class EvaluationRunExecutionContractV0:
    engine: Literal["native"]
    config: Literal["none"]
    premise_policy: Literal["empty"]
    where_ast_gate: Literal["enabled", "disabled"]
    plan_form: Literal["materialized_native_where_ir_v0"]

    def __post_init__(self) -> None:
        if (self.engine, self.config, self.premise_policy, self.plan_form) != (
            "native",
            "none",
            "empty",
            "materialized_native_where_ir_v0",
        ) or self.where_ast_gate not in {"enabled", "disabled"}:
            raise ProtocolShapeError("EvaluationRun execution contract is outside capture v0")


@dataclass(frozen=True, repr=False)
class EvaluationRunBundleV0:
    run_anchor: EvaluationRunAnchorV0
    query_digest: str
    binding_values: tuple[EvaluationRunValueV0, ...]
    native_plan: EvaluationRunNativePlanV0
    schema_bytes: bytes
    schema_bytes_digest: str
    schema_capture_digest: str
    relations: tuple[EvaluationRunRelationV0, ...]
    rows: tuple[EvaluationRunProjectionRowV0, ...]
    relation_capture_scope: Literal["plan_dependency_complete"]
    dependency_predicate_ids: tuple[str, ...]
    execution_contract: EvaluationRunExecutionContractV0
    integrity: Literal["digest_sealed_not_authenticated"]
    authenticity: Literal["unverified"]
    privacy: Literal["contains_captured_typed_values"]
    custody: Literal["caller_managed"]
    playback: Literal["captured_proof_receipts_available"]
    replay_availability: Literal["not_implemented"]
    query_capture_digest: str
    relations_capture_digest: str
    rows_capture_digest: str
    bundle_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_anchor, EvaluationRunAnchorV0):
            raise ProtocolShapeError("EvaluationRun bundle requires an F4A Run anchor")
        _sha_hex(self.query_digest, "query_digest")
        if self.query_digest != self.run_anchor.query_digest:
            raise ProtocolShapeError("EvaluationRun bundle query does not match Run anchor")
        _tuple_of(self.binding_values, EvaluationRunValueV0, "binding_values")
        if not all(
            isinstance(item, expected)
            for item, expected in (
                (self.native_plan, EvaluationRunNativePlanV0),
                (self.execution_contract, EvaluationRunExecutionContractV0),
            )
        ):
            raise ProtocolShapeError("EvaluationRun bundle component type is invalid")
        if (
            len(self.binding_values) > _MAX_EVALUATION_RUN_VALUES
            or len(self.run_anchor.selections) > _MAX_EVALUATION_RUN_VALUES
            or len(self.run_anchor.selections) != len(self.native_plan.head_var_names)
        ):
            raise ProtocolShapeError("EvaluationRun bundle value width limit is exceeded")
        _tuple_of(self.relations, EvaluationRunRelationV0, "relations", non_empty=True)
        _tuple_of(self.rows, EvaluationRunProjectionRowV0, "rows")
        if self.relation_capture_scope != "plan_dependency_complete":
            raise ProtocolShapeError("EvaluationRun relation capture scope is outside v0")
        if (
            not isinstance(self.dependency_predicate_ids, tuple)
            or tuple(sorted(set(self.dependency_predicate_ids))) != self.dependency_predicate_ids
        ):
            raise ProtocolShapeError(
                "EvaluationRun dependency predicate inventory must be sorted unique"
            )
        if tuple(
            sorted(self.relations, key=lambda item: item.predicate_id)
        ) != self.relations or len({item.predicate_id for item in self.relations}) != len(
            self.relations
        ):
            raise ProtocolShapeError(
                "EvaluationRun relations must be unique and canonically ordered"
            )
        if tuple(item.ordinal for item in self.rows) != tuple(range(len(self.rows))):
            raise ProtocolShapeError("EvaluationRun projection row ordinals are not contiguous")
        if not isinstance(self.schema_bytes, bytes) or not self.schema_bytes:
            raise ProtocolShapeError("EvaluationRun bundle schema bytes are malformed")
        _seal_token(
            self.schema_bytes_digest,
            f"sha256:{sha256_hex(self.schema_bytes)}",
            "schema_bytes_digest",
        )
        _seal_token(
            self.schema_capture_digest,
            _token(
                "evaluation_run_schema_capture_v0",
                (self.run_anchor.target.schema_digest, self.schema_bytes_digest),
            ),
            "schema_capture_digest",
        )
        try:
            decoded_schema = json.loads(
                self.schema_bytes.decode("utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProtocolShapeError("EvaluationRun bundle schema is not JSON") from exc
        if (
            canonicalize_schema_ir_jcs(decoded_schema) != self.schema_bytes
            or schema_digest(decoded_schema) != self.run_anchor.target.schema_digest
        ):
            raise ProtocolShapeError("EvaluationRun bundle schema does not match Run anchor")
        if self.native_plan.target_pred_id != self.run_anchor.projection_head_id:
            raise ProtocolShapeError("EvaluationRun bundle plan head does not match Run anchor")
        if set(self.dependency_predicate_ids) - {item.predicate_id for item in self.relations}:
            raise ProtocolShapeError(
                "EvaluationRun dependencies are absent from captured relations"
            )
        all_asrt_ids = [fact[0] for relation in self.relations for fact in relation.facts]
        if len(all_asrt_ids) != len(set(all_asrt_ids)):
            raise ProtocolShapeError("EvaluationRun assertion ids must be globally unique")
        if tuple((value.tag, value.digest) for value in self.binding_values) != tuple(
            (item.value_type, item.value_digest) for item in self.run_anchor.bindings
        ):
            raise ProtocolShapeError("EvaluationRun bundle query capture does not match Run anchor")
        if tuple(
            (row.row_id, row.claim_digest, row.head_scope_digest, row.certainty_digest)
            for row in self.rows
        ) != tuple(
            (row.row_id, row.claim_digest, row.head_scope_digest, row.certainty_digest)
            for row in self.run_anchor.row_anchors
        ):
            raise ProtocolShapeError("EvaluationRun bundle rows do not match Run anchor")
        aliases = tuple(item.alias for item in self.run_anchor.selections)
        if any(tuple(value[0] for value in row.values) != aliases for row in self.rows):
            raise ProtocolShapeError(
                "EvaluationRun bundle row projection does not match selections"
            )
        expected_query = _token(
            "evaluation_run_query_capture_v0",
            (
                self.query_digest,
                self.run_anchor.bindings,
                self.binding_values,
                self.run_anchor.selections,
            ),
        )
        expected_relations = _token(
            "evaluation_run_relations_capture_v0",
            (
                self.relation_capture_scope,
                self.dependency_predicate_ids,
                self.relations,
            ),
        )
        expected_rows = _token(
            "evaluation_run_rows_capture_v0", tuple(row.row_capture_digest for row in self.rows)
        )
        _seal_token(self.query_capture_digest, expected_query, "query_capture_digest")
        _seal_token(self.relations_capture_digest, expected_relations, "relations_capture_digest")
        _seal_token(self.rows_capture_digest, expected_rows, "rows_capture_digest")
        expected_bundle = _token(
            "evaluation_run_bundle_v0",
            (
                self.run_anchor.anchor_digest,
                self.query_capture_digest,
                self.native_plan.plan_digest,
                self.schema_capture_digest,
                self.relations_capture_digest,
                self.rows_capture_digest,
                self.execution_contract,
                self.integrity,
                self.authenticity,
                self.privacy,
                self.custody,
                self.playback,
                self.replay_availability,
            ),
        )
        if (
            self.integrity,
            self.authenticity,
            self.privacy,
            self.custody,
            self.playback,
            self.replay_availability,
        ) != (
            "digest_sealed_not_authenticated",
            "unverified",
            "contains_captured_typed_values",
            "caller_managed",
            "captured_proof_receipts_available",
            "not_implemented",
        ):
            raise ProtocolShapeError("EvaluationRun bundle custody semantics are outside v0")
        _seal_token(self.bundle_digest, expected_bundle, "bundle_digest")

    def __repr__(self) -> str:
        return f"EvaluationRunBundleV0(bundle_digest={self.bundle_digest!r}, captured_values=<redacted>)"


def _tuple_of(
    value: object, item_type: type[object], name: str, *, non_empty: bool = False
) -> None:
    if (
        not isinstance(value, tuple)
        or (non_empty and not value)
        or not all(isinstance(item, item_type) for item in value)
    ):
        raise ProtocolShapeError(f"EvaluationRun bundle {name} is malformed")


def _storage_to_raw(tag: str, value: RunBundleScalar) -> object:
    if tag != "bytes":
        return value
    if not isinstance(value, str):
        raise ProtocolShapeError("EvaluationRun bytes storage value must be base64url string")
    try:
        raw = base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
    except (UnicodeEncodeError, ValueError) as exc:
        raise ProtocolShapeError("EvaluationRun bytes storage value is malformed") from exc
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value:
        raise ProtocolShapeError("EvaluationRun bytes storage value is non-canonical")
    return raw


def _finite_hex_float(value: object) -> float:
    if (
        not isinstance(value, str)
        or len(value) != 18
        or not value.startswith("0x")
        or value != value.lower()
        or value == "0x8000000000000000"
    ):
        raise ProtocolShapeError("EvaluationRun certainty bound must be float64 hex")
    try:
        hexadecimal_payload = value[2:]
        number = struct.unpack(">d", int(hexadecimal_payload, 16).to_bytes(8, "big"))[0]
    except (ValueError, OverflowError) as exc:
        raise ProtocolShapeError("EvaluationRun certainty bound is malformed") from exc
    if not math.isfinite(number):
        raise ProtocolShapeError("EvaluationRun certainty bound must be finite")
    return 0.0 if number == 0.0 else number


def _certainty_digest(value: tuple[str, str, str] | None) -> str:
    # Kept local to avoid a protocol import cycle: EvaluateResult owns the
    # canonical Evaluate envelope while this bundle is an optional field on it.
    from .evaluate_result import canonical_bytes_for_evaluate

    if value is None:
        payload: object = None
    elif (
        not isinstance(value, tuple)
        or len(value) != 3
        or value[2] not in {"boolean", "probabilistic", "possibilistic"}
    ):
        raise ProtocolShapeError("EvaluationRun projection certainty is malformed")
    else:
        lo, hi = _finite_hex_float(value[0]), _finite_hex_float(value[1])
        if not 0.0 <= lo <= hi <= 1.0:
            raise ProtocolShapeError("EvaluationRun projection certainty bounds are invalid")
        payload = {"lo": lo, "hi": hi, "kind": value[2]}
    return sha256_token(canonical_bytes_for_evaluate("evaluation_run_certainty_v0", payload))


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(f"EvaluationRun bundle JSON contains non-standard constant {value!r}")


__all__ = [
    "EvaluationRunBundleV0",
    "EvaluationRunExecutionContractV0",
    "EvaluationRunNativePlanV0",
    "EvaluationRunProjectionRowV0",
    "EvaluationRunRelationV0",
    "EvaluationRunValueV0",
]
