"""Sealed V1 execution-run and detached-replay protocol values.

This module is deliberately a *protocol* rather than an evaluator.  It joins
the V1 query/result contract to the material which a later executor needs to
replay one exact run without consulting a current ``Store``.  In particular it
does not turn a replay into a historical-ledger claim, a source-authority
claim, or an authorization decision.

The three important boundaries are kept explicit:

* ``EvaluationReplayPayloadV1`` owns the captured schema/program/world inputs
  and has a strict canonical JSON codec.  It contains no Python callbacks,
  Store objects, or provider callables.
* ``EvaluationRunV1`` owns the relationship between an immutable
  ``GoalPlanV1``, baseline/effective worlds, engine-normalized results, and
  technical assessment.  It is integrity-sealed but not authenticated.
* ``ExplainTargetV1`` names either an exact semantic row anchor or the exact
  result summary; it never means “the first row”.

The protocol intentionally requires a completed canonical result in an
``EvaluationRunV1``.  A per-engine frame may nevertheless be typed
``failed`` or ``unsupported``: it then contains no result and therefore cannot
be mistaken for replayable/Explain-able evidence.  A failure before even one
canonical result exists is represented by ``GoalTechnicalAssessmentV1`` on its
own.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str
from .goal_plan_v1 import (
    GoalPlanV1,
    GoalResultV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
)

EvaluationWorldSideV1: TypeAlias = Literal["baseline", "effective"]
EvaluationRunSideNameV1: TypeAlias = Literal["baseline", "effective", "candidate_effective"]
EvaluationEngineV1: TypeAlias = Literal["native", "souffle", "problog"]
EvaluationEngineFrameStatusV1: TypeAlias = Literal["succeeded", "failed", "unsupported"]
EvaluationProfileKindV1: TypeAlias = Literal["native_deterministic_v1", "portable_deterministic_v1"]
ExplainTargetKindV1: TypeAlias = Literal["row", "summary"]

_WORLD_SIDES = frozenset({"baseline", "effective"})
_RUN_SIDE_NAMES = frozenset({"baseline", "effective", "candidate_effective"})
_ENGINES = frozenset({"native", "souffle", "problog"})
_ENGINE_FRAME_STATUSES = frozenset({"succeeded", "failed", "unsupported"})
_PROFILE_KINDS = frozenset({"native_deterministic_v1", "portable_deterministic_v1"})
_EXPLAIN_TARGET_KINDS = frozenset({"row", "summary"})
_PORTABLE_ENGINE_ORDER: tuple[str, ...] = ("native", "souffle", "problog")

MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES = 4 * 1024 * 1024
MAX_EVALUATION_REPLAY_PAYLOAD_V1_DEPTH = 64
MAX_EVALUATION_REPLAY_RELATIONS_V1 = 256
MAX_EVALUATION_REPLAY_FACTS_V1 = 50_000
MAX_EVALUATION_REPLAY_VALUES_V1 = 64


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
        raise ProtocolShapeError(f"{label} cannot be represented as canonical JSON") from exc


def _token(label: str, payload: object) -> str:
    return f"sha256:{sha256_hex(_canonical_json_bytes({'format': label, 'payload': payload}, label=label))}"


def _require_token(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    raw = value[7:]
    if (
        len(raw) != 64
        or raw != raw.lower()
        or any(character not in "0123456789abcdef" for character in raw)
    ):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    return value


def _require_literal(value: object, field_name: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProtocolShapeError(f"{field_name} is outside this protocol")
    return value


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_b64u(value: object, field_name: str) -> bytes:
    if not isinstance(value, str):
        raise ProtocolShapeError(f"{field_name} must be canonical base64url")
    try:
        raw = base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise ProtocolShapeError(f"{field_name} must be canonical base64url") from exc
    if _b64u(raw) != value:
        raise ProtocolShapeError(f"{field_name} must be canonical base64url")
    return raw


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ProtocolShapeError("Evaluation replay payload JSON contains duplicate object key")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(
        f"Evaluation replay payload JSON contains non-standard constant {value!r}"
    )


def _assert_exact_keys(value: object, expected: frozenset[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProtocolShapeError(f"{label} has unsupported or missing fields")
    return value


def _assert_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ProtocolShapeError(f"{label} must be JSON array")
    return value


def _freeze_json(value: object) -> object:
    """Make a canonical JSON value recursively immutable in memory."""

    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _plain_json(value: object) -> object:
    """Return a detached JSON value from the recursively frozen form."""

    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain_json(item) for item in value]
    return value


def _semantic_row_set_digest(result: GoalResultV1) -> str:
    """The only cross-engine equality claim made by the V1 protocol."""

    return _token(
        "evaluation_run_v1_semantic_row_set",
        {
            "plan_digest": result.plan_digest,
            "result_mode": result.result_mode,
            "rows": tuple(row.semantic_row_digest for row in result.rows),
            "exists_value": result.exists_value,
            "count_value": result.count_value,
            "completeness": result.completeness,
        },
    )


@dataclass(frozen=True, repr=False)
class EvaluationReplayFactV1:
    """One captured, typed finite relation tuple.

    ``witness_ref`` is an opaque capture-local label, never an assertion that a
    current ledger still has this id.  It lets a later evidence adapter retain
    the relation's locally captured witness boundary without serializing a
    live assertion or Store object.
    """

    witness_ref: str
    values: tuple[GoalValueV1, ...]
    fact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.witness_ref, field_name="EvaluationReplayFactV1.witness_ref")
        if (
            not isinstance(self.values, tuple)
            or not self.values
            or len(self.values) > MAX_EVALUATION_REPLAY_VALUES_V1
            or not all(isinstance(value, GoalValueV1) for value in self.values)
        ):
            raise ProtocolShapeError(
                "EvaluationReplayFactV1.values must be non-empty GoalValueV1 tuple"
            )
        object.__setattr__(
            self,
            "fact_digest",
            _token(
                "evaluation_replay_fact_v1",
                {
                    "witness_ref": self.witness_ref,
                    "values": tuple((value.tag, value.value_digest) for value in self.values),
                },
            ),
        )

    def __repr__(self) -> str:
        return f"EvaluationReplayFactV1(witness_ref={self.witness_ref!r}, values=<redacted>)"


@dataclass(frozen=True, repr=False)
class EvaluationReplayRelationV1:
    """One schema-typed finite captured relation in a replay world."""

    predicate_id: str
    value_tags: tuple[str, ...]
    facts: tuple[EvaluationReplayFactV1, ...]
    relation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.predicate_id, field_name="EvaluationReplayRelationV1.predicate_id"
        )
        if (
            not isinstance(self.value_tags, tuple)
            or not self.value_tags
            or len(self.value_tags) > MAX_EVALUATION_REPLAY_VALUES_V1
            or any(
                tag
                not in {
                    "entity_ref",
                    "string",
                    "int",
                    "float64",
                    "bool",
                    "bytes",
                    "time",
                    "uuid",
                }
                for tag in self.value_tags
            )
        ):
            raise ProtocolShapeError("EvaluationReplayRelationV1.value_tags are malformed")
        if not isinstance(self.facts, tuple) or not all(
            isinstance(fact, EvaluationReplayFactV1) for fact in self.facts
        ):
            raise ProtocolShapeError(
                "EvaluationReplayRelationV1.facts must be EvaluationReplayFactV1 tuple"
            )
        if any(tuple(value.tag for value in fact.values) != self.value_tags for fact in self.facts):
            raise ProtocolShapeError(
                "EvaluationReplayRelationV1 fact value tags do not match relation"
            )
        facts = tuple(sorted(self.facts, key=lambda item: item.fact_digest))
        if len({fact.witness_ref for fact in facts}) != len(facts):
            raise ProtocolShapeError("EvaluationReplayRelationV1 witness refs must be unique")
        if len({fact.fact_digest for fact in facts}) != len(facts):
            raise ProtocolShapeError("EvaluationReplayRelationV1 duplicate captured fact")
        object.__setattr__(self, "facts", facts)
        object.__setattr__(
            self,
            "relation_digest",
            _token(
                "evaluation_replay_relation_v1",
                {
                    "predicate_id": self.predicate_id,
                    "value_tags": self.value_tags,
                    "facts": tuple(fact.fact_digest for fact in facts),
                },
            ),
        )

    def __repr__(self) -> str:
        return f"EvaluationReplayRelationV1(predicate_id={self.predicate_id!r}, facts=<redacted>)"


@dataclass(frozen=True)
class EvaluationReplayWorldV1:
    """One baseline/effective world captured for detached execution.

    ``semantic_world_digest`` and ``resolution_evidence_digest`` are distinct
    pins supplied by the Scenario resolver.  The first identifies the resolved
    semantics; the second identifies its operation/conflict/closure evidence.
    The captured relation digest is computed locally from the exact finite
    material required to replay, rather than trusted from a caller.
    """

    side: EvaluationWorldSideV1
    semantic_world_digest: str
    resolution_evidence_digest: str
    closure_target_digests: tuple[str, ...]
    relations: tuple[EvaluationReplayRelationV1, ...]
    relation_snapshot_digest: str = field(init=False)
    world_capture_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.side, "EvaluationReplayWorldV1.side", _WORLD_SIDES)
        _require_token(
            self.semantic_world_digest,
            "EvaluationReplayWorldV1.semantic_world_digest",
        )
        _require_token(
            self.resolution_evidence_digest,
            "EvaluationReplayWorldV1.resolution_evidence_digest",
        )
        if not isinstance(self.closure_target_digests, tuple):
            raise ProtocolShapeError("EvaluationReplayWorldV1.closure_target_digests must be tuple")
        for digest in self.closure_target_digests:
            _require_token(digest, "EvaluationReplayWorldV1 closure target digest")
        closures = tuple(sorted(self.closure_target_digests))
        if len(set(closures)) != len(closures):
            raise ProtocolShapeError(
                "EvaluationReplayWorldV1 closure target digests must be unique"
            )
        if (
            not isinstance(self.relations, tuple)
            or len(self.relations) > MAX_EVALUATION_REPLAY_RELATIONS_V1
            or not all(
                isinstance(relation, EvaluationReplayRelationV1) for relation in self.relations
            )
        ):
            raise ProtocolShapeError(
                "EvaluationReplayWorldV1.relations must be EvaluationReplayRelationV1 tuple"
            )
        relations = tuple(sorted(self.relations, key=lambda item: item.predicate_id))
        if len({relation.predicate_id for relation in relations}) != len(relations):
            raise ProtocolShapeError("EvaluationReplayWorldV1 predicate ids must be unique")
        fact_count = sum(len(relation.facts) for relation in relations)
        if fact_count > MAX_EVALUATION_REPLAY_FACTS_V1:
            raise ProtocolShapeError("EvaluationReplayWorldV1 fact limit exceeded")
        object.__setattr__(self, "closure_target_digests", closures)
        object.__setattr__(self, "relations", relations)
        relation_snapshot_digest = _token(
            "evaluation_replay_relation_snapshot_v1",
            tuple(relation.relation_digest for relation in relations),
        )
        object.__setattr__(self, "relation_snapshot_digest", relation_snapshot_digest)
        object.__setattr__(
            self,
            "world_capture_digest",
            _token(
                "evaluation_replay_world_v1",
                {
                    "side": self.side,
                    "semantic_world_digest": self.semantic_world_digest,
                    "resolution_evidence_digest": self.resolution_evidence_digest,
                    "closure_target_digests": closures,
                    "relation_snapshot_digest": relation_snapshot_digest,
                },
            ),
        )


@dataclass(frozen=True, repr=False)
class ProviderReceiptRefV1:
    """A sealed reference to one pre-engine provider materialization.

    The receipt stays opaque to FactGraph's proof system.  It records the
    identity of the provider/request/materialization so replay can *use the
    captured relation* without calling the provider again.  It is not a proof
    of provider internals or a permission to make a fresh external request.
    """

    provider_digest: str
    request_digest: str
    materialization_digest: str
    receipt_ref: str
    receipt_digest: str
    reference_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "provider_digest",
            "request_digest",
            "materialization_digest",
            "receipt_digest",
        ):
            _require_token(getattr(self, name), f"ProviderReceiptRefV1.{name}")
        _require_non_empty_str(self.receipt_ref, field_name="ProviderReceiptRefV1.receipt_ref")
        object.__setattr__(
            self,
            "reference_digest",
            _token(
                "provider_receipt_ref_v1",
                (
                    self.provider_digest,
                    self.request_digest,
                    self.materialization_digest,
                    self.receipt_ref,
                    self.receipt_digest,
                ),
            ),
        )

    def __repr__(self) -> str:
        return (
            "ProviderReceiptRefV1("
            f"provider_digest={self.provider_digest!r}, receipt_ref=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class EvaluationReplayProgramEnvelopeV1:
    """Strict replay header linking an opaque compiled program to one run.

    The protocol deliberately does *not* lower or execute ``compiled_program``.
    A runtime owns that capability-specific body schema.  This DTO does make
    the otherwise opaque canonical JSON body inseparable from the exact
    schema, address space, plan/target, and execution-profile pins which a
    detached replay must verify before it attempts execution.
    """

    schema_digest: str
    address_space_digest: str
    plan_digest: str
    query_digest: str
    target_digest: str
    execution_profile_digest: str
    compiler_digest: str
    compiled_program: Mapping[str, object]
    candidate_plan_digest: str | None = None
    candidate_query_digest: str | None = None
    candidate_target_digest: str | None = None
    envelope_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "schema_digest",
            "address_space_digest",
            "plan_digest",
            "query_digest",
            "target_digest",
            "execution_profile_digest",
            "compiler_digest",
        ):
            _require_token(getattr(self, name), f"EvaluationReplayProgramEnvelopeV1.{name}")
        candidate_values = (
            self.candidate_plan_digest,
            self.candidate_query_digest,
            self.candidate_target_digest,
        )
        if any(value is None for value in candidate_values) and any(
            value is not None for value in candidate_values
        ):
            raise ProtocolShapeError(
                "EvaluationReplayProgramEnvelopeV1 candidate pins must be all present or all absent"
            )
        for index, value in enumerate(candidate_values):
            if value is not None:
                _require_token(
                    value,
                    f"EvaluationReplayProgramEnvelopeV1.candidate_pin[{index}]",
                )
        if not isinstance(self.compiled_program, Mapping) or not self.compiled_program:
            raise ProtocolShapeError(
                "EvaluationReplayProgramEnvelopeV1.compiled_program must be a non-empty JSON object"
            )
        # Normalize into a fresh JSON object to eliminate mutable caller-owned
        # maps and to reject non-finite/non-JSON values before sealing.
        normalized = _assert_canonical_json_bytes(
            _canonical_json_bytes(
                _plain_json(self.compiled_program),
                label="EvaluationReplayProgramEnvelopeV1.compiled_program",
            ),
            "EvaluationReplayProgramEnvelopeV1.compiled_program",
        )
        if not isinstance(normalized, dict) or not normalized:
            raise ProtocolShapeError(
                "EvaluationReplayProgramEnvelopeV1.compiled_program must be a JSON object"
            )
        object.__setattr__(self, "compiled_program", _freeze_json(normalized))
        object.__setattr__(
            self,
            "envelope_digest",
            _token(
                "evaluation_replay_program_envelope_v1",
                {
                    "schema_digest": self.schema_digest,
                    "address_space_digest": self.address_space_digest,
                    "plan_digest": self.plan_digest,
                    "query_digest": self.query_digest,
                    "target_digest": self.target_digest,
                    "execution_profile_digest": self.execution_profile_digest,
                    "compiler_digest": self.compiler_digest,
                    "compiled_program": normalized,
                    "candidate_plan_digest": self.candidate_plan_digest,
                    "candidate_query_digest": self.candidate_query_digest,
                    "candidate_target_digest": self.candidate_target_digest,
                },
            ),
        )

    def to_bytes(self) -> bytes:
        return evaluation_replay_program_envelope_v1_bytes(self)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EvaluationReplayProgramEnvelopeV1":
        value = evaluation_replay_program_envelope_v1_from_bytes(raw)
        if not isinstance(value, cls):  # pragma: no cover - defensive boundary
            raise ProtocolShapeError("Evaluation replay program envelope codec returned wrong type")
        return value

    def __repr__(self) -> str:
        return (
            "EvaluationReplayProgramEnvelopeV1("
            f"envelope_digest={self.envelope_digest!r}, compiled_program=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class EvaluationReplayPayloadV1:
    """The detached material for a future V1 replay.

    ``schema_bytes`` and ``compiled_program_bytes`` are deliberately captured
    canonical JSON values, not live compiler/schema objects.  A later replay
    runtime must decode and validate those values under its explicit V1
    capability profile.  This protocol only guarantees their sealed byte
    identity and the exact finite worlds they are paired with.
    """

    schema_digest: str
    address_space_digest: str
    schema_bytes: bytes
    compiled_program_bytes: bytes
    worlds: tuple[EvaluationReplayWorldV1, ...]
    provider_receipts: tuple[ProviderReceiptRefV1, ...] = ()
    schema_bytes_digest: str = field(init=False)
    compiled_program_digest: str = field(init=False)
    program_envelope_digest: str = field(init=False)
    payload_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.schema_digest, "EvaluationReplayPayloadV1.schema_digest")
        _require_token(
            self.address_space_digest,
            "EvaluationReplayPayloadV1.address_space_digest",
        )
        for name in ("schema_bytes", "compiled_program_bytes"):
            value = getattr(self, name)
            if not isinstance(value, bytes) or not value:
                raise ProtocolShapeError(
                    f"EvaluationReplayPayloadV1.{name} must be non-empty bytes"
                )
            if len(value) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES:
                raise ProtocolShapeError(f"EvaluationReplayPayloadV1.{name} exceeds size limit")
            _assert_canonical_json_bytes(value, f"EvaluationReplayPayloadV1.{name}")
        program_envelope = evaluation_replay_program_envelope_v1_from_bytes(
            self.compiled_program_bytes
        )
        if (
            program_envelope.schema_digest != self.schema_digest
            or program_envelope.address_space_digest != self.address_space_digest
        ):
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV1 replay program envelope does not match schema/address-space pins"
            )
        if (
            not isinstance(self.worlds, tuple)
            or len(self.worlds) != 2
            or not all(isinstance(world, EvaluationReplayWorldV1) for world in self.worlds)
        ):
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV1 requires baseline and effective worlds"
            )
        worlds = tuple(sorted(self.worlds, key=lambda item: item.side))
        if tuple(world.side for world in worlds) != ("baseline", "effective"):
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV1 worlds must be one baseline and one effective"
            )
        if not isinstance(self.provider_receipts, tuple) or not all(
            isinstance(item, ProviderReceiptRefV1) for item in self.provider_receipts
        ):
            raise ProtocolShapeError("EvaluationReplayPayloadV1 provider receipts are malformed")
        receipts = tuple(sorted(self.provider_receipts, key=lambda item: item.reference_digest))
        if len({item.reference_digest for item in receipts}) != len(receipts):
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV1 provider receipt references must be unique"
            )
        object.__setattr__(self, "worlds", worlds)
        object.__setattr__(self, "provider_receipts", receipts)
        schema_bytes_digest = f"sha256:{sha256_hex(self.schema_bytes)}"
        program_digest = f"sha256:{sha256_hex(self.compiled_program_bytes)}"
        object.__setattr__(self, "schema_bytes_digest", schema_bytes_digest)
        object.__setattr__(self, "compiled_program_digest", program_digest)
        object.__setattr__(self, "program_envelope_digest", program_envelope.envelope_digest)
        object.__setattr__(
            self,
            "payload_digest",
            _token(
                "evaluation_replay_payload_v1",
                {
                    "schema_digest": self.schema_digest,
                    "address_space_digest": self.address_space_digest,
                    "schema_bytes_digest": schema_bytes_digest,
                    "compiled_program_digest": program_digest,
                    "program_envelope_digest": program_envelope.envelope_digest,
                    "worlds": tuple(world.world_capture_digest for world in worlds),
                    "provider_receipts": tuple(item.reference_digest for item in receipts),
                },
            ),
        )

    def world(self, side: EvaluationWorldSideV1) -> EvaluationReplayWorldV1:
        """Return a captured side by explicit name; there is no implicit default."""

        _require_literal(side, "EvaluationReplayPayloadV1.world side", _WORLD_SIDES)
        return next(item for item in self.worlds if item.side == side)

    @property
    def program_envelope(self) -> EvaluationReplayProgramEnvelopeV1:
        """Decode the sealed replay header; never infer it from live state."""

        return evaluation_replay_program_envelope_v1_from_bytes(self.compiled_program_bytes)

    def to_bytes(self) -> bytes:
        return evaluation_replay_payload_v1_bytes(self)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EvaluationReplayPayloadV1":
        value = evaluation_replay_payload_v1_from_bytes(raw)
        if not isinstance(value, cls):  # pragma: no cover - defensive import boundary
            raise ProtocolShapeError("Evaluation replay payload codec returned wrong type")
        return value

    def __repr__(self) -> str:
        return (
            "EvaluationReplayPayloadV1("
            f"payload_digest={self.payload_digest!r}, captured_values=<redacted>)"
        )


@dataclass(frozen=True)
class EvaluationEnginePinV1:
    """One exact engine/adapter identity used by a replayable run."""

    engine: EvaluationEngineV1
    engine_version: str
    adapter_version: str
    pin_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.engine, "EvaluationEnginePinV1.engine", _ENGINES)
        _require_non_empty_str(
            self.engine_version, field_name="EvaluationEnginePinV1.engine_version"
        )
        _require_non_empty_str(
            self.adapter_version, field_name="EvaluationEnginePinV1.adapter_version"
        )
        object.__setattr__(
            self,
            "pin_digest",
            _token(
                "evaluation_engine_pin_v1",
                (self.engine, self.engine_version, self.adapter_version),
            ),
        )


@dataclass(frozen=True)
class EvaluationExecutionProfileV1:
    """The exact engine contract, independent from a product policy."""

    kind: EvaluationProfileKindV1
    compiler_digest: str
    config_digest: str | None
    engines: tuple[EvaluationEnginePinV1, ...]
    profile_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.kind, "EvaluationExecutionProfileV1.kind", _PROFILE_KINDS)
        _require_token(self.compiler_digest, "EvaluationExecutionProfileV1.compiler_digest")
        # V1 intentionally has no canonical configuration codec yet.  Merely
        # sealing an opaque digest would make detached replay look pinned while
        # leaving it unable to reconstruct the actual engine configuration.
        # Reject every configuration now; a later, separately versioned codec
        # may widen this field only together with replay validation.
        if self.config_digest is not None:
            raise ProtocolShapeError(
                "EvaluationExecutionProfileV1 does not permit engine configuration before a configuration codec exists"
            )
        if (
            not isinstance(self.engines, tuple)
            or not self.engines
            or not all(isinstance(item, EvaluationEnginePinV1) for item in self.engines)
        ):
            raise ProtocolShapeError("EvaluationExecutionProfileV1.engines must be pin tuple")
        engine_names = tuple(item.engine for item in self.engines)
        if len(set(engine_names)) != len(engine_names):
            raise ProtocolShapeError("EvaluationExecutionProfileV1 engines must be unique")
        required = ("native",) if self.kind == "native_deterministic_v1" else _PORTABLE_ENGINE_ORDER
        if engine_names != required:
            raise ProtocolShapeError("EvaluationExecutionProfileV1 engines do not match profile")
        object.__setattr__(
            self,
            "profile_digest",
            _token(
                "evaluation_execution_profile_v1",
                {
                    "kind": self.kind,
                    "compiler_digest": self.compiler_digest,
                    "config_digest": self.config_digest,
                    "engine_pins": tuple(item.pin_digest for item in self.engines),
                },
            ),
        )


@dataclass(frozen=True)
class EvaluationEngineResultV1:
    """One engine's typed outcome for one completed run side.

    A portable run must retain a concrete frame even when one adapter rejects
    the selected capability or fails.  That preserves the distinction between
    ``no parity claim because Soufflé was unsupported`` and ``Soufflé produced
    a different normalized row set``.  Only successful frames carry a
    ``GoalResultV1``.  Engine proof receipts remain outside this common result
    surface because matching rows do not establish common proof equality.
    """

    engine: EvaluationEngineV1
    result: GoalResultV1 | None
    status: EvaluationEngineFrameStatusV1 = "succeeded"
    diagnostic_code: str = "EVALUATION_ENGINE_SUCCEEDED"
    diagnostic_detail_digest: str | None = None
    semantic_row_set_digest: str | None = field(init=False)
    frame_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.engine, "EvaluationEngineResultV1.engine", _ENGINES)
        _require_literal(
            self.status,
            "EvaluationEngineResultV1.status",
            _ENGINE_FRAME_STATUSES,
        )
        _require_non_empty_str(
            self.diagnostic_code,
            field_name="EvaluationEngineResultV1.diagnostic_code",
        )
        if self.diagnostic_detail_digest is not None:
            _require_token(
                self.diagnostic_detail_digest,
                "EvaluationEngineResultV1.diagnostic_detail_digest",
            )
        if self.status == "succeeded":
            if not isinstance(self.result, GoalResultV1):
                raise ProtocolShapeError(
                    "successful EvaluationEngineResultV1 requires GoalResultV1"
                )
            semantic_row_set_digest: str | None = _semantic_row_set_digest(self.result)
        else:
            if self.result is not None:
                raise ProtocolShapeError(
                    "failed/unsupported EvaluationEngineResultV1 must not carry a result"
                )
            if self.diagnostic_code == "EVALUATION_ENGINE_SUCCEEDED":
                raise ProtocolShapeError(
                    "failed/unsupported EvaluationEngineResultV1 requires a failure diagnostic"
                )
            semantic_row_set_digest = None
        object.__setattr__(self, "semantic_row_set_digest", semantic_row_set_digest)
        object.__setattr__(
            self,
            "frame_digest",
            _token(
                "evaluation_engine_result_v1",
                {
                    "engine": self.engine,
                    "status": self.status,
                    "result_digest": None if self.result is None else self.result.result_digest,
                    "semantic_row_set_digest": semantic_row_set_digest,
                    "diagnostic_code": self.diagnostic_code,
                    "diagnostic_detail_digest": self.diagnostic_detail_digest,
                },
            ),
        )


@dataclass(frozen=True)
class EvaluationRunSideV1:
    """One complete result against one explicitly captured world side."""

    name: EvaluationRunSideNameV1
    plan_digest: str
    world_side: EvaluationWorldSideV1
    world_capture_digest: str
    canonical_result: GoalResultV1
    engine_results: tuple[EvaluationEngineResultV1, ...]
    assessment: GoalTechnicalAssessmentV1
    side_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.name, "EvaluationRunSideV1.name", _RUN_SIDE_NAMES)
        _require_token(self.plan_digest, "EvaluationRunSideV1.plan_digest")
        _require_literal(self.world_side, "EvaluationRunSideV1.world_side", _WORLD_SIDES)
        _require_token(self.world_capture_digest, "EvaluationRunSideV1.world_capture_digest")
        if not isinstance(self.canonical_result, GoalResultV1):
            raise ProtocolShapeError("EvaluationRunSideV1.canonical_result must be GoalResultV1")
        if self.canonical_result.plan_digest != self.plan_digest:
            raise ProtocolShapeError("EvaluationRunSideV1 result belongs to another plan")
        if (
            not isinstance(self.engine_results, tuple)
            or not self.engine_results
            or not all(isinstance(item, EvaluationEngineResultV1) for item in self.engine_results)
        ):
            raise ProtocolShapeError("EvaluationRunSideV1.engine_results must be non-empty tuple")
        names = tuple(item.engine for item in self.engine_results)
        if len(set(names)) != len(names):
            raise ProtocolShapeError("EvaluationRunSideV1 engine result inventory must be unique")
        successful_frames = tuple(
            item for item in self.engine_results if item.status == "succeeded"
        )
        if not successful_frames:
            raise ProtocolShapeError(
                "EvaluationRunSideV1 requires at least one successful canonical engine frame"
            )
        if any(
            item.result is None or item.result.plan_digest != self.plan_digest
            for item in successful_frames
        ):
            raise ProtocolShapeError(
                "EvaluationRunSideV1 successful engine result does not match canonical plan"
            )
        if not isinstance(self.assessment, GoalTechnicalAssessmentV1):
            raise ProtocolShapeError(
                "EvaluationRunSideV1.assessment must be GoalTechnicalAssessmentV1"
            )
        if (
            self.assessment.plan_digest != self.plan_digest
            or self.assessment.result_digest != self.canonical_result.result_digest
            or self.assessment.execution != "succeeded"
            or self.assessment.completeness != self.canonical_result.completeness
        ):
            raise ProtocolShapeError(
                "EvaluationRunSideV1 assessment does not match completed result"
            )
        object.__setattr__(
            self,
            "side_digest",
            _token(
                "evaluation_run_side_v1",
                {
                    "name": self.name,
                    "plan_digest": self.plan_digest,
                    "world_side": self.world_side,
                    "world_capture_digest": self.world_capture_digest,
                    "canonical_result_digest": self.canonical_result.result_digest,
                    "semantic_row_set_digest": _semantic_row_set_digest(self.canonical_result),
                    "engine_frames": tuple(item.frame_digest for item in self.engine_results),
                    "assessment_digest": self.assessment.assessment_digest,
                },
            ),
        )


@dataclass(frozen=True)
class ExplainTargetV1:
    """An exact named result target for detached Explain.

    This is deliberately only a reference.  ``EvaluationRunV1`` verifies the
    reference against its sealed materialized result before it is accepted.
    """

    side: EvaluationRunSideNameV1
    kind: ExplainTargetKindV1
    anchor_digest: str
    target_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.side, "ExplainTargetV1.side", _RUN_SIDE_NAMES)
        _require_literal(self.kind, "ExplainTargetV1.kind", _EXPLAIN_TARGET_KINDS)
        _require_token(self.anchor_digest, "ExplainTargetV1.anchor_digest")
        object.__setattr__(
            self,
            "target_digest",
            _token("evaluation_explain_target_v1", (self.side, self.kind, self.anchor_digest)),
        )


@dataclass(frozen=True)
class EvaluationRunV1:
    """A completed, sealed v1 run over captured baseline/effective worlds.

    The optional candidate plan represents an immutable Rule/Policy comparison
    target.  It receives the same captured effective world as the primary
    target; it is never a mutable patch and never becomes a published policy.
    """

    plan: GoalPlanV1
    execution_profile: EvaluationExecutionProfileV1
    replay_payload: EvaluationReplayPayloadV1
    baseline: EvaluationRunSideV1
    effective: EvaluationRunSideV1
    candidate_plan: GoalPlanV1 | None = None
    candidate_effective: EvaluationRunSideV1 | None = None
    explain_target: ExplainTargetV1 | None = None
    run_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, GoalPlanV1):
            raise ProtocolShapeError("EvaluationRunV1.plan must be GoalPlanV1")
        if not isinstance(self.execution_profile, EvaluationExecutionProfileV1):
            raise ProtocolShapeError(
                "EvaluationRunV1.execution_profile must be EvaluationExecutionProfileV1"
            )
        if not isinstance(self.replay_payload, EvaluationReplayPayloadV1):
            raise ProtocolShapeError(
                "EvaluationRunV1.replay_payload must be EvaluationReplayPayloadV1"
            )
        if self.plan.execution_profile_digest not in {
            None,
            self.execution_profile.profile_digest,
        }:
            raise ProtocolShapeError(
                "EvaluationRunV1 plan execution profile pin does not match run"
            )
        self._validate_replay_program_envelope()
        self._validate_primary_side(self.baseline, "baseline", "baseline")
        self._validate_primary_side(self.effective, "effective", "effective")
        if (self.candidate_plan is None) != (self.candidate_effective is None):
            raise ProtocolShapeError(
                "EvaluationRunV1 candidate plan and side must be present together"
            )
        if self.candidate_plan is not None:
            assert self.candidate_effective is not None
            if not isinstance(self.candidate_plan, GoalPlanV1):
                raise ProtocolShapeError("EvaluationRunV1 candidate_plan must be GoalPlanV1")
            if self.candidate_plan.execution_profile_digest not in {
                None,
                self.execution_profile.profile_digest,
            }:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan execution profile pin does not match run"
                )
            if self.plan.candidate_target is None:
                raise ProtocolShapeError(
                    "EvaluationRunV1 primary plan does not declare a candidate target"
                )
            if self.candidate_plan.target != self.plan.candidate_target:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan does not match the primary candidate pin"
                )
            if self.candidate_plan.query_digest != self.plan.candidate_query_digest:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan does not match the primary candidate Query pin"
                )
            envelope = self.replay_payload.program_envelope
            if (
                envelope.candidate_plan_digest != self.candidate_plan.plan_digest
                or envelope.candidate_query_digest != self.candidate_plan.query_digest
                or envelope.candidate_target_digest != self.candidate_plan.target.target_digest
            ):
                raise ProtocolShapeError(
                    "EvaluationRunV1 replay program envelope candidate pins do not match candidate plan"
                )
            if self.candidate_plan.candidate_target is not None:
                raise ProtocolShapeError("EvaluationRunV1 candidate plan cannot nest a candidate")
            if self.candidate_plan.scenario_request_digest != self.plan.scenario_request_digest:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan must share the primary Scenario request"
                )
            if self.candidate_plan.evidence_scope_digest != self.plan.evidence_scope_digest:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan must share the primary evidence-admission scope"
                )
            if self.candidate_plan.expectations:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan cannot carry primary-target expectations"
                )
            if self.candidate_plan.target.target_digest == self.plan.target.target_digest:
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate target must be independently pinned"
                )
            if self.candidate_plan.result_mode != self.plan.result_mode or tuple(
                (item.alias, item.value_tag) for item in self.candidate_plan.selections
            ) != tuple((item.alias, item.value_tag) for item in self.plan.selections):
                raise ProtocolShapeError(
                    "EvaluationRunV1 candidate plan must expose the same comparison projection"
                )
            self._validate_side(
                self.candidate_effective,
                expected_name="candidate_effective",
                expected_plan_digest=self.candidate_plan.plan_digest,
                expected_world_side="effective",
                plan=self.candidate_plan,
            )
        elif self.plan.candidate_target is not None:
            raise ProtocolShapeError(
                "EvaluationRunV1 primary plan declares a candidate target without candidate execution"
            )
        self._validate_profile_engines()
        self._validate_explain_target()
        object.__setattr__(
            self,
            "run_digest",
            _token(
                "evaluation_run_v1",
                {
                    "plan_digest": self.plan.plan_digest,
                    "execution_profile_digest": self.execution_profile.profile_digest,
                    "replay_payload_digest": self.replay_payload.payload_digest,
                    "baseline": self.baseline.side_digest,
                    "effective": self.effective.side_digest,
                    "candidate_plan_digest": None
                    if self.candidate_plan is None
                    else self.candidate_plan.plan_digest,
                    "candidate_effective": None
                    if self.candidate_effective is None
                    else self.candidate_effective.side_digest,
                    "explain_target": None
                    if self.explain_target is None
                    else self.explain_target.target_digest,
                },
            ),
        )

    def _validate_replay_program_envelope(self) -> None:
        """Cross-check the detached program header against sealed run pins.

        This is a binding check, not a claim that the opaque compiled-program
        body is executable.  A runtime must separately validate that body under
        its explicit compiler capability profile before replay.
        """

        envelope = self.replay_payload.program_envelope
        if (
            envelope.schema_digest != self.replay_payload.schema_digest
            or envelope.address_space_digest != self.replay_payload.address_space_digest
            or envelope.plan_digest != self.plan.plan_digest
            or envelope.query_digest != self.plan.query_digest
            or envelope.target_digest != self.plan.target.target_digest
            or envelope.execution_profile_digest != self.execution_profile.profile_digest
            or envelope.compiler_digest != self.execution_profile.compiler_digest
        ):
            raise ProtocolShapeError(
                "EvaluationRunV1 replay program envelope does not match run pins"
            )
        candidate_values = (
            envelope.candidate_plan_digest,
            envelope.candidate_query_digest,
            envelope.candidate_target_digest,
        )
        if self.plan.candidate_target is None:
            if any(value is not None for value in candidate_values):
                raise ProtocolShapeError(
                    "EvaluationRunV1 replay program envelope has undeclared candidate pins"
                )
        elif envelope.candidate_target_digest != self.plan.candidate_target.target_digest:
            raise ProtocolShapeError(
                "EvaluationRunV1 replay program envelope candidate target does not match plan"
            )

    def _validate_primary_side(
        self,
        side: EvaluationRunSideV1,
        name: EvaluationRunSideNameV1,
        world_side: EvaluationWorldSideV1,
    ) -> None:
        self._validate_side(
            side,
            expected_name=name,
            expected_plan_digest=self.plan.plan_digest,
            expected_world_side=world_side,
            plan=self.plan,
        )

    def _validate_side(
        self,
        side: EvaluationRunSideV1,
        *,
        expected_name: EvaluationRunSideNameV1,
        expected_plan_digest: str,
        expected_world_side: EvaluationWorldSideV1,
        plan: GoalPlanV1,
    ) -> None:
        if not isinstance(side, EvaluationRunSideV1):
            raise ProtocolShapeError("EvaluationRunV1 side is malformed")
        if (
            side.name != expected_name
            or side.plan_digest != expected_plan_digest
            or side.world_side != expected_world_side
            or side.world_capture_digest
            != self.replay_payload.world(expected_world_side).world_capture_digest
        ):
            raise ProtocolShapeError("EvaluationRunV1 side does not match its pinned plan/world")
        expected_selection_shape = {item.alias: item.value_tag for item in plan.selections}
        for row in side.canonical_result.rows:
            # Rows normalize aliases for stable semantic identity, while the
            # Query plan retains caller select order for display/projection.
            # Compare the typed mapping, never accidentally make alphabetical
            # row normalization reject a valid nonalphabetical select order.
            actual_selection_shape = {alias: value.tag for alias, value in row.values}
            if actual_selection_shape != expected_selection_shape:
                raise ProtocolShapeError(
                    "EvaluationRunV1 result row does not match the pinned selection shape"
                )
        expected_expectations = {
            item.expectation_id: (item.kind, item.expectation_digest) for item in plan.expectations
        }
        actual_expectations = {
            item.expectation_id: (item.kind, item.expectation_digest)
            for item in side.canonical_result.expectation_outcomes
        }
        if actual_expectations != expected_expectations:
            raise ProtocolShapeError(
                "EvaluationRunV1 expectation outcomes do not exactly cover the pinned plan"
            )

    def _validate_profile_engines(self) -> None:
        expected = tuple(pin.engine for pin in self.execution_profile.engines)
        for side in (self.baseline, self.effective, self.candidate_effective):
            if side is None:
                continue
            actual = tuple(item.engine for item in side.engine_results)
            if actual != expected:
                raise ProtocolShapeError(
                    "EvaluationRunV1 side engines do not match execution profile"
                )
            if self.execution_profile.kind == "portable_deterministic_v1":
                frame_statuses = tuple(item.status for item in side.engine_results)
                native_frame = side.engine_results[0]
                canonical_digest = _semantic_row_set_digest(side.canonical_result)
                if (
                    native_frame.engine != "native"
                    or native_frame.status != "succeeded"
                    or native_frame.result is None
                    or native_frame.semantic_row_set_digest != canonical_digest
                ):
                    raise ProtocolShapeError(
                        "portable EvaluationRunV1 requires Native as its successful canonical frame"
                    )
                if any(status == "failed" for status in frame_statuses):
                    if side.assessment.parity != "unresolved":
                        raise ProtocolShapeError(
                            "portable EvaluationRunV1 with failed engine requires unresolved parity"
                        )
                elif any(status == "unsupported" for status in frame_statuses):
                    if side.assessment.parity != "unsupported":
                        raise ProtocolShapeError(
                            "portable EvaluationRunV1 with unsupported engine requires unsupported parity"
                        )
                elif all(status == "succeeded" for status in frame_statuses):
                    successful_digests = {
                        item.semantic_row_set_digest for item in side.engine_results
                    }
                    expected_parity = "equivalent" if len(successful_digests) == 1 else "different"
                    if side.assessment.parity != expected_parity:
                        raise ProtocolShapeError(
                            "portable EvaluationRunV1 parity does not match successful engine row sets"
                        )
            elif side.assessment.parity != "not_requested":
                raise ProtocolShapeError("native EvaluationRunV1 cannot claim portable parity")

    def _validate_explain_target(self) -> None:
        if self.explain_target is None:
            return
        if not isinstance(self.explain_target, ExplainTargetV1):
            raise ProtocolShapeError("EvaluationRunV1.explain_target must be ExplainTargetV1")
        side = {
            "baseline": self.baseline,
            "effective": self.effective,
            "candidate_effective": self.candidate_effective,
        }[self.explain_target.side]
        if side is None:
            raise ProtocolShapeError(
                "EvaluationRunV1 Explain target references absent candidate side"
            )
        if self.explain_target.kind == "row":
            anchors = {
                row.anchor.anchor_digest
                for row in side.canonical_result.rows
                if row.anchor is not None
            }
        else:
            assert side.canonical_result.summary_anchor is not None
            anchors = {side.canonical_result.summary_anchor.summary_anchor_digest}
        if self.explain_target.anchor_digest not in anchors:
            raise ProtocolShapeError(
                "EvaluationRunV1 Explain target does not belong to sealed result"
            )


def _assert_canonical_json_bytes(raw: bytes, label: str) -> object:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError(f"{label} must be canonical UTF-8 JSON") from exc
    if _json_depth(value) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_DEPTH:
        raise ProtocolShapeError(f"{label} exceeds JSON depth limit")
    if _canonical_json_bytes(value, label=label) != raw:
        raise ProtocolShapeError(f"{label} must be canonical JSON")
    return value


def evaluation_replay_program_envelope_v1_bytes(
    envelope: EvaluationReplayProgramEnvelopeV1,
) -> bytes:
    """Encode a replay-program header with a strict, canonical wire shape."""

    if not isinstance(envelope, EvaluationReplayProgramEnvelopeV1):
        raise ProtocolShapeError("envelope must be EvaluationReplayProgramEnvelopeV1")
    EvaluationReplayProgramEnvelopeV1.__post_init__(envelope)
    raw = _canonical_json_bytes(
        {
            "$type": "EvaluationReplayProgramEnvelopeV1",
            "schema_digest": envelope.schema_digest,
            "address_space_digest": envelope.address_space_digest,
            "plan_digest": envelope.plan_digest,
            "query_digest": envelope.query_digest,
            "target_digest": envelope.target_digest,
            "execution_profile_digest": envelope.execution_profile_digest,
            "compiler_digest": envelope.compiler_digest,
            "compiled_program": _plain_json(envelope.compiled_program),
            "candidate_plan_digest": envelope.candidate_plan_digest,
            "candidate_query_digest": envelope.candidate_query_digest,
            "candidate_target_digest": envelope.candidate_target_digest,
        },
        label="Evaluation replay program envelope",
    )
    if len(raw) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES:
        raise ProtocolShapeError("Evaluation replay program envelope exceeds size limit")
    return raw


def evaluation_replay_program_envelope_v1_from_bytes(
    raw: bytes,
) -> EvaluationReplayProgramEnvelopeV1:
    """Decode only the exact canonical program-envelope wire shape."""

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES:
        raise ProtocolShapeError(
            "Evaluation replay program envelope bytes are empty or exceed size limit"
        )
    value = _assert_canonical_json_bytes(raw, "Evaluation replay program envelope")
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "$type",
                "schema_digest",
                "address_space_digest",
                "plan_digest",
                "query_digest",
                "target_digest",
                "execution_profile_digest",
                "compiler_digest",
                "compiled_program",
                "candidate_plan_digest",
                "candidate_query_digest",
                "candidate_target_digest",
            }
        ),
        "Evaluation replay program envelope",
    )
    if row["$type"] != "EvaluationReplayProgramEnvelopeV1":
        raise ProtocolShapeError("Evaluation replay program envelope type is invalid")
    required_strings = (
        "schema_digest",
        "address_space_digest",
        "plan_digest",
        "query_digest",
        "target_digest",
        "execution_profile_digest",
        "compiler_digest",
    )
    if not all(isinstance(row[name], str) for name in required_strings):
        raise ProtocolShapeError("Evaluation replay program envelope digest field is malformed")
    candidate_values = tuple(
        row[name]
        for name in (
            "candidate_plan_digest",
            "candidate_query_digest",
            "candidate_target_digest",
        )
    )
    if not all(value is None or isinstance(value, str) for value in candidate_values):
        raise ProtocolShapeError("Evaluation replay program envelope candidate pin is malformed")
    if not isinstance(row["compiled_program"], dict):
        raise ProtocolShapeError("Evaluation replay program envelope compiled_program is malformed")
    return EvaluationReplayProgramEnvelopeV1(
        schema_digest=row["schema_digest"],  # type: ignore[arg-type]
        address_space_digest=row["address_space_digest"],  # type: ignore[arg-type]
        plan_digest=row["plan_digest"],  # type: ignore[arg-type]
        query_digest=row["query_digest"],  # type: ignore[arg-type]
        target_digest=row["target_digest"],  # type: ignore[arg-type]
        execution_profile_digest=row["execution_profile_digest"],  # type: ignore[arg-type]
        compiler_digest=row["compiler_digest"],  # type: ignore[arg-type]
        compiled_program=row["compiled_program"],
        candidate_plan_digest=row["candidate_plan_digest"],  # type: ignore[arg-type]
        candidate_query_digest=row["candidate_query_digest"],  # type: ignore[arg-type]
        candidate_target_digest=row["candidate_target_digest"],  # type: ignore[arg-type]
    )


def evaluation_replay_payload_v1_bytes(payload: EvaluationReplayPayloadV1) -> bytes:
    """Encode the detached replay material with no pickle/ambient resolver path."""

    if not isinstance(payload, EvaluationReplayPayloadV1):
        raise ProtocolShapeError("payload must be EvaluationReplayPayloadV1")
    EvaluationReplayPayloadV1.__post_init__(payload)
    raw = _canonical_json_bytes(_payload_to_wire(payload), label="Evaluation replay payload")
    if len(raw) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES:
        raise ProtocolShapeError("Evaluation replay payload exceeds size limit")
    return raw


def evaluation_replay_payload_v1_from_bytes(raw: bytes) -> EvaluationReplayPayloadV1:
    """Decode only the exact canonical V1 replay wire shape, fail-closed."""

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES:
        raise ProtocolShapeError("Evaluation replay payload bytes are empty or exceed size limit")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError("Evaluation replay payload is not valid UTF-8 JSON") from exc
    if _json_depth(value) > MAX_EVALUATION_REPLAY_PAYLOAD_V1_DEPTH:
        raise ProtocolShapeError("Evaluation replay payload exceeds JSON depth limit")
    if _canonical_json_bytes(value, label="Evaluation replay payload") != raw:
        raise ProtocolShapeError("Evaluation replay payload JSON is not canonical")
    payload = _payload_from_wire(value)
    EvaluationReplayPayloadV1.__post_init__(payload)
    return payload


def _payload_to_wire(payload: EvaluationReplayPayloadV1) -> dict[str, object]:
    return {
        "$type": "EvaluationReplayPayloadV1",
        "schema_digest": payload.schema_digest,
        "address_space_digest": payload.address_space_digest,
        "schema_bytes_b64u": _b64u(payload.schema_bytes),
        "compiled_program_bytes_b64u": _b64u(payload.compiled_program_bytes),
        "worlds": [_world_to_wire(world) for world in payload.worlds],
        "provider_receipts": [_receipt_to_wire(item) for item in payload.provider_receipts],
    }


def _world_to_wire(world: EvaluationReplayWorldV1) -> dict[str, object]:
    return {
        "side": world.side,
        "semantic_world_digest": world.semantic_world_digest,
        "resolution_evidence_digest": world.resolution_evidence_digest,
        "closure_target_digests": list(world.closure_target_digests),
        "relations": [_relation_to_wire(relation) for relation in world.relations],
    }


def _relation_to_wire(relation: EvaluationReplayRelationV1) -> dict[str, object]:
    return {
        "predicate_id": relation.predicate_id,
        "value_tags": list(relation.value_tags),
        "facts": [
            {
                "witness_ref": fact.witness_ref,
                "values": [_value_to_wire(value) for value in fact.values],
            }
            for fact in relation.facts
        ],
    }


def _value_to_wire(value: GoalValueV1) -> dict[str, object]:
    return {"tag": value.tag, "value": value.value}


def _receipt_to_wire(receipt: ProviderReceiptRefV1) -> dict[str, object]:
    return {
        "provider_digest": receipt.provider_digest,
        "request_digest": receipt.request_digest,
        "materialization_digest": receipt.materialization_digest,
        "receipt_ref": receipt.receipt_ref,
        "receipt_digest": receipt.receipt_digest,
    }


def _payload_from_wire(value: object) -> EvaluationReplayPayloadV1:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "$type",
                "schema_digest",
                "address_space_digest",
                "schema_bytes_b64u",
                "compiled_program_bytes_b64u",
                "worlds",
                "provider_receipts",
            }
        ),
        "Evaluation replay payload",
    )
    if row["$type"] != "EvaluationReplayPayloadV1":
        raise ProtocolShapeError("Evaluation replay payload type is invalid")
    schema_digest = row["schema_digest"]
    address_space_digest = row["address_space_digest"]
    if not isinstance(schema_digest, str) or not isinstance(address_space_digest, str):
        raise ProtocolShapeError("Evaluation replay payload digest field is malformed")
    worlds = tuple(_world_from_wire(item) for item in _assert_list(row["worlds"], "worlds"))
    receipts = tuple(
        _receipt_from_wire(item)
        for item in _assert_list(row["provider_receipts"], "provider_receipts")
    )
    return EvaluationReplayPayloadV1(
        schema_digest=schema_digest,
        address_space_digest=address_space_digest,
        schema_bytes=_decode_b64u(row["schema_bytes_b64u"], "schema_bytes_b64u"),
        compiled_program_bytes=_decode_b64u(
            row["compiled_program_bytes_b64u"], "compiled_program_bytes_b64u"
        ),
        worlds=worlds,
        provider_receipts=receipts,
    )


def _world_from_wire(value: object) -> EvaluationReplayWorldV1:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "side",
                "semantic_world_digest",
                "resolution_evidence_digest",
                "closure_target_digests",
                "relations",
            }
        ),
        "Evaluation replay world",
    )
    if not all(
        isinstance(row[name], str)
        for name in ("side", "semantic_world_digest", "resolution_evidence_digest")
    ):
        raise ProtocolShapeError("Evaluation replay world scalar field is malformed")
    closure_values = _assert_list(row["closure_target_digests"], "closure_target_digests")
    if not all(isinstance(item, str) for item in closure_values):
        raise ProtocolShapeError("Evaluation replay closure target digest is malformed")
    return EvaluationReplayWorldV1(
        side=row["side"],  # type: ignore[arg-type]
        semantic_world_digest=row["semantic_world_digest"],  # type: ignore[arg-type]
        resolution_evidence_digest=row["resolution_evidence_digest"],  # type: ignore[arg-type]
        closure_target_digests=tuple(item for item in closure_values if isinstance(item, str)),
        relations=tuple(
            _relation_from_wire(item) for item in _assert_list(row["relations"], "relations")
        ),
    )


def _relation_from_wire(value: object) -> EvaluationReplayRelationV1:
    row = _assert_exact_keys(
        value,
        frozenset({"predicate_id", "value_tags", "facts"}),
        "Evaluation replay relation",
    )
    if not isinstance(row["predicate_id"], str):
        raise ProtocolShapeError("Evaluation replay relation predicate_id is malformed")
    tags = _assert_list(row["value_tags"], "value_tags")
    if not all(isinstance(item, str) for item in tags):
        raise ProtocolShapeError("Evaluation replay relation value tag is malformed")
    facts: list[EvaluationReplayFactV1] = []
    for item in _assert_list(row["facts"], "facts"):
        fact = _assert_exact_keys(
            item,
            frozenset({"witness_ref", "values"}),
            "Evaluation replay fact",
        )
        if not isinstance(fact["witness_ref"], str):
            raise ProtocolShapeError("Evaluation replay fact witness_ref is malformed")
        facts.append(
            EvaluationReplayFactV1(
                fact["witness_ref"],
                tuple(
                    _value_from_wire(value) for value in _assert_list(fact["values"], "fact values")
                ),
            )
        )
    return EvaluationReplayRelationV1(
        row["predicate_id"],
        tuple(item for item in tags if isinstance(item, str)),
        tuple(facts),
    )


def _value_from_wire(value: object) -> GoalValueV1:
    row = _assert_exact_keys(value, frozenset({"tag", "value"}), "Goal replay value")
    if not isinstance(row["tag"], str):
        raise ProtocolShapeError("Goal replay value tag is malformed")
    stored = row["value"]
    if not isinstance(stored, (str, int, bool)) or isinstance(stored, float):
        raise ProtocolShapeError("Goal replay value storage is malformed")
    return GoalValueV1(row["tag"], stored)  # type: ignore[arg-type]


def _receipt_from_wire(value: object) -> ProviderReceiptRefV1:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "provider_digest",
                "request_digest",
                "materialization_digest",
                "receipt_ref",
                "receipt_digest",
            }
        ),
        "Provider receipt reference",
    )
    if not all(isinstance(item, str) for item in row.values()):
        raise ProtocolShapeError("Provider receipt reference field is malformed")
    return ProviderReceiptRefV1(
        provider_digest=row["provider_digest"],  # type: ignore[arg-type]
        request_digest=row["request_digest"],  # type: ignore[arg-type]
        materialization_digest=row["materialization_digest"],  # type: ignore[arg-type]
        receipt_ref=row["receipt_ref"],  # type: ignore[arg-type]
        receipt_digest=row["receipt_digest"],  # type: ignore[arg-type]
    )


__all__ = [
    "EvaluationEnginePinV1",
    "EvaluationEngineResultV1",
    "EvaluationEngineFrameStatusV1",
    "EvaluationEngineV1",
    "EvaluationExecutionProfileV1",
    "EvaluationProfileKindV1",
    "EvaluationReplayFactV1",
    "EvaluationReplayPayloadV1",
    "EvaluationReplayProgramEnvelopeV1",
    "EvaluationReplayRelationV1",
    "EvaluationReplayWorldV1",
    "EvaluationRunSideNameV1",
    "EvaluationRunSideV1",
    "EvaluationRunV1",
    "EvaluationWorldSideV1",
    "ExplainTargetKindV1",
    "ExplainTargetV1",
    "MAX_EVALUATION_REPLAY_FACTS_V1",
    "MAX_EVALUATION_REPLAY_PAYLOAD_V1_BYTES",
    "MAX_EVALUATION_REPLAY_PAYLOAD_V1_DEPTH",
    "MAX_EVALUATION_REPLAY_RELATIONS_V1",
    "MAX_EVALUATION_REPLAY_VALUES_V1",
    "ProviderReceiptRefV1",
    "evaluation_replay_payload_v1_bytes",
    "evaluation_replay_payload_v1_from_bytes",
    "evaluation_replay_program_envelope_v1_bytes",
    "evaluation_replay_program_envelope_v1_from_bytes",
]
