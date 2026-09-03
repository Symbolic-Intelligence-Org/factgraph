"""Strict V2 execution-semantics profiles and stable attachment pins.

The public SDK may create these values through a convenience builder, but the
protocol has no callback, arbitrary engine kwargs or lowered branch label.
Every attachment names an authored target side and a stable Rule/occurrence/
choice address.  A later authoring bridge supplies those strings and digests;
this module deliberately does not import product Rule/Policy wrappers.

Expected target bridge shape:

* a target pin contains ``side``, target kind/id/version and exact logical
  ``target_digest``;
* a Rule attachment additionally contains exact Rule id/version/content digest;
* an occurrence attachment additionally contains the exact Policy-local alias;
* a choice attachment additionally contains an authored structural node id.

All values are replayable only through this canonical codec.  The module owns
validation and sealing, not compiler lineage expansion or engine execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str
from .scenario_v2 import FactSemanticsV2

EvaluationEngineV2: TypeAlias = Literal["native", "souffle", "problog"]
EvaluationProfileKindV2: TypeAlias = Literal[
    "native_deterministic_v2",
    "portable_deterministic_v2",
    "problog_point_v2",
]
EvaluationTargetSideV2: TypeAlias = Literal["primary", "candidate"]
EvaluationAttachmentKindV2: TypeAlias = Literal["rule", "occurrence", "choice"]
EvaluationAttachmentSemanticsKindV2: TypeAlias = Literal[
    "problog_rule_point_v1",
    "problog_occurrence_point_v1",
    "problog_choice_activation_v1",
]
EvaluationCaptureModeV2: TypeAlias = Literal["sealed_replay_required"]

_ENGINES = frozenset({"native", "souffle", "problog"})
_PROFILE_KINDS = frozenset(
    {"native_deterministic_v2", "portable_deterministic_v2", "problog_point_v2"}
)
_TARGET_SIDES = frozenset({"primary", "candidate"})
_TARGET_KINDS = frozenset({"rule", "policy"})
_ATTACHMENT_KINDS = frozenset({"rule", "occurrence", "choice"})
_ATTACHMENT_SEMANTICS_KINDS = frozenset(
    {
        "problog_rule_point_v1",
        "problog_occurrence_point_v1",
        "problog_choice_activation_v1",
    }
)
_CAPTURE_MODES = frozenset({"sealed_replay_required"})
_PROFILE_ENGINE_ORDER: dict[str, tuple[str, ...]] = {
    "native_deterministic_v2": ("native",),
    "portable_deterministic_v2": ("native", "souffle", "problog"),
    # The latter two frames are explicitly represented as unsupported by a
    # V2 point-probability runner; their pins prevent a fake fallback.
    "problog_point_v2": ("problog", "native", "souffle"),
}

MAX_EXECUTION_PROFILE_V2_BYTES = 1024 * 1024
MAX_EXECUTION_PROFILE_V2_DEPTH = 32
MAX_EXECUTION_PROFILE_V2_ATTACHMENTS = 128
MAX_EXECUTION_PROFILE_V2_LOWERING_SLOTS = 256
MAX_EXECUTION_PROFILE_V2_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_EXECUTION_PROFILE_V2_ROWS = 100_000
MAX_EXECUTION_PROFILE_V2_TIMEOUT_MS = 600_000


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


def _require_token(value: object, *, field_name: str) -> str:
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


def _require_literal(value: object, *, field_name: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProtocolShapeError(f"{field_name} is outside this protocol")
    return value


def _require_bounded_str(value: object, *, field_name: str, max_length: int = 256) -> str:
    _require_non_empty_str(value, field_name=field_name)
    assert isinstance(value, str)
    if len(value) > max_length or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ProtocolShapeError(f"{field_name} must be bounded text without control characters")
    return value


def _require_positive_int(value: object, *, field_name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise ProtocolShapeError(f"{field_name} must be positive int within protocol cap")
    return value


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ProtocolShapeError("EvaluationExecutionProfileV2 JSON has duplicate object key")
        output[key] = value
    return output


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(
        f"EvaluationExecutionProfileV2 JSON has non-standard constant {value!r}"
    )


def _assert_exact_keys(value: object, expected: frozenset[str], *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProtocolShapeError(f"{label} has unsupported or missing fields")
    return value


@dataclass(frozen=True)
class EvaluationEnginePinV2:
    """One exact engine + adapter identity in a V2 semantic profile."""

    engine: EvaluationEngineV2
    engine_version: str
    adapter_version: str
    pin_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.engine, field_name="EvaluationEnginePinV2.engine", allowed=_ENGINES)
        _require_bounded_str(self.engine_version, field_name="EvaluationEnginePinV2.engine_version")
        _require_bounded_str(
            self.adapter_version, field_name="EvaluationEnginePinV2.adapter_version"
        )
        object.__setattr__(
            self,
            "pin_digest",
            _token(
                "evaluation_engine_pin_v2",
                (self.engine, self.engine_version, self.adapter_version),
            ),
        )

    def to_wire(self) -> dict[str, str]:
        """Return the canonical engine/adapter pin payload."""
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "adapter_version": self.adapter_version,
        }


@dataclass(frozen=True)
class EvaluationResourcePolicyV2:
    """Closed runtime resource budget; no callback or arbitrary runner option."""

    max_rows: int = 10_000
    timeout_ms: int | None = None
    policy_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_positive_int(
            self.max_rows,
            field_name="EvaluationResourcePolicyV2.max_rows",
            maximum=MAX_EXECUTION_PROFILE_V2_ROWS,
        )
        if self.timeout_ms is not None:
            _require_positive_int(
                self.timeout_ms,
                field_name="EvaluationResourcePolicyV2.timeout_ms",
                maximum=MAX_EXECUTION_PROFILE_V2_TIMEOUT_MS,
            )
        object.__setattr__(
            self,
            "policy_digest",
            _token(
                "evaluation_resource_policy_v2",
                {"max_rows": self.max_rows, "timeout_ms": self.timeout_ms},
            ),
        )

    def to_wire(self) -> dict[str, int | None]:
        """Return the canonical closed resource-policy payload."""
        return {"max_rows": self.max_rows, "timeout_ms": self.timeout_ms}


@dataclass(frozen=True)
class EvaluationCapturePolicyV2:
    """Closed capture commitment required for V2 replay/run construction."""

    mode: EvaluationCaptureModeV2 = "sealed_replay_required"
    max_capture_bytes: int = 4 * 1024 * 1024
    policy_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(
            self.mode, field_name="EvaluationCapturePolicyV2.mode", allowed=_CAPTURE_MODES
        )
        _require_positive_int(
            self.max_capture_bytes,
            field_name="EvaluationCapturePolicyV2.max_capture_bytes",
            maximum=MAX_EXECUTION_PROFILE_V2_CAPTURE_BYTES,
        )
        object.__setattr__(
            self,
            "policy_digest",
            _token(
                "evaluation_capture_policy_v2",
                {"mode": self.mode, "max_capture_bytes": self.max_capture_bytes},
            ),
        )

    def to_wire(self) -> dict[str, int | str]:
        """Return the canonical replay-capture policy payload."""
        return {"mode": self.mode, "max_capture_bytes": self.max_capture_bytes}


@dataclass(frozen=True)
class DeterministicSemanticsV2:
    """V2 deterministic model; it rejects any fact probability semantics."""

    model: Literal["deterministic_v1"] = "deterministic_v1"
    semantics_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.model != "deterministic_v1":
            raise ProtocolShapeError("DeterministicSemanticsV2.model is unsupported")
        object.__setattr__(
            self,
            "semantics_digest",
            _token("deterministic_semantics_v2", {"model": self.model}),
        )

    def to_wire(self) -> dict[str, str]:
        """Return the canonical deterministic-semantics payload."""
        return {"kind": "deterministic", "model": self.model}


@dataclass(frozen=True)
class ProbLogPointSemanticsV2:
    """Declared-point ProbLog model with an explicit numeric projection.

    ``FactSemanticsV2`` deliberately retains the caller's canonical decimal
    declaration.  The current ProbLog adapter, however, executes through its
    legacy binary-float boundary.  ``materialization`` names that boundary so
    a sealed run can show the submitted decimal separately from the number
    actually emitted to ProbLog; it is not an arbitrary engine config knob.
    """

    model: Literal["independent_bernoulli_v1"] = "independent_bernoulli_v1"
    identity_probability: Literal[True] = True
    materialization: Literal["problog_float64_v1"] = "problog_float64_v1"
    semantics_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            self.model != "independent_bernoulli_v1"
            or self.identity_probability is not True
            or self.materialization != "problog_float64_v1"
        ):
            raise ProtocolShapeError("ProbLogPointSemanticsV2 is unsupported")
        object.__setattr__(
            self,
            "semantics_digest",
            _token(
                "problog_point_semantics_v2",
                {
                    "model": self.model,
                    "identity_probability": self.identity_probability,
                    "materialization": self.materialization,
                },
            ),
        )

    def to_wire(self) -> dict[str, object]:
        """Return the canonical ProbLog point-semantics payload."""
        return {
            "kind": "problog_point",
            "model": self.model,
            "identity_probability": self.identity_probability,
            "materialization": self.materialization,
        }


EvaluationSemanticsV2: TypeAlias = DeterministicSemanticsV2 | ProbLogPointSemanticsV2


@dataclass(frozen=True)
class EvaluationTargetPinV2:
    """A side-specific authored Rule/Policy target pin, independent of SDK classes."""

    side: EvaluationTargetSideV2
    target_kind: Literal["rule", "policy"]
    target_id: str
    target_version: str | None
    target_digest: str
    pin_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.side, field_name="EvaluationTargetPinV2.side", allowed=_TARGET_SIDES)
        _require_literal(
            self.target_kind, field_name="EvaluationTargetPinV2.target_kind", allowed=_TARGET_KINDS
        )
        _require_bounded_str(self.target_id, field_name="EvaluationTargetPinV2.target_id")
        if self.target_version is not None:
            _require_bounded_str(
                self.target_version, field_name="EvaluationTargetPinV2.target_version"
            )
        _require_token(self.target_digest, field_name="EvaluationTargetPinV2.target_digest")
        object.__setattr__(
            self,
            "pin_digest",
            _token(
                "evaluation_target_pin_v2",
                {
                    "side": self.side,
                    "target_kind": self.target_kind,
                    "target_id": self.target_id,
                    "target_version": self.target_version,
                    "target_digest": self.target_digest,
                },
            ),
        )

    def to_wire(self) -> dict[str, object]:
        """Return the canonical side-specific target pin payload."""
        return {
            "side": self.side,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "target_version": self.target_version,
            "target_digest": self.target_digest,
        }


@dataclass(frozen=True)
class ExecutionAttachmentSemanticsV2:
    """Closed activation settings; never a generic engine configuration bag."""

    kind: EvaluationAttachmentSemanticsKindV2
    semantics_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(
            self.kind,
            field_name="ExecutionAttachmentSemanticsV2.kind",
            allowed=_ATTACHMENT_SEMANTICS_KINDS,
        )
        object.__setattr__(
            self,
            "semantics_digest",
            _token("execution_attachment_semantics_v2", {"kind": self.kind}),
        )

    def to_wire(self) -> dict[str, str]:
        """Return the canonical attachment-semantics marker."""
        return {"kind": self.kind}


@dataclass(frozen=True)
class ExecutionAttachmentV2:
    """One stable authored attachment request, before compiler lineage expansion."""

    kind: EvaluationAttachmentKindV2
    target: EvaluationTargetPinV2
    semantics: ExecutionAttachmentSemanticsV2
    rule_id: str | None = None
    rule_version: str | None = None
    rule_digest: str | None = None
    occurrence_alias: str | None = None
    structural_node_id: str | None = None
    binding_digest: str = field(init=False)
    attachment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(
            self.kind, field_name="ExecutionAttachmentV2.kind", allowed=_ATTACHMENT_KINDS
        )
        if not isinstance(self.target, EvaluationTargetPinV2):
            raise ProtocolShapeError("ExecutionAttachmentV2.target must be EvaluationTargetPinV2")
        if not isinstance(self.semantics, ExecutionAttachmentSemanticsV2):
            raise ProtocolShapeError(
                "ExecutionAttachmentV2.semantics must be ExecutionAttachmentSemanticsV2"
            )
        fresh_target = EvaluationTargetPinV2(
            side=self.target.side,
            target_kind=self.target.target_kind,
            target_id=self.target.target_id,
            target_version=self.target.target_version,
            target_digest=self.target.target_digest,
        )
        fresh_semantics = ExecutionAttachmentSemanticsV2(kind=self.semantics.kind)
        if (
            fresh_target.pin_digest != self.target.pin_digest
            or fresh_semantics.semantics_digest != self.semantics.semantics_digest
        ):
            raise ProtocolShapeError("ExecutionAttachmentV2 nested seal is stale")
        if self.kind == "rule":
            self._validate_rule_shape()
            expected_semantics = "problog_rule_point_v1"
        elif self.kind == "occurrence":
            self._validate_occurrence_shape()
            expected_semantics = "problog_occurrence_point_v1"
        else:
            self._validate_choice_shape()
            expected_semantics = "problog_choice_activation_v1"
        if self.semantics.kind != expected_semantics:
            raise ProtocolShapeError(
                "ExecutionAttachmentV2 semantics kind does not match attachment kind"
            )
        binding_payload = {
            "kind": self.kind,
            "target_pin": self.target.pin_digest,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_digest": self.rule_digest,
            "occurrence_alias": self.occurrence_alias,
            "structural_node_id": self.structural_node_id,
        }
        binding_digest = _token("execution_attachment_v2_binding", binding_payload)
        attachment_digest = _token(
            "execution_attachment_v2",
            {
                "binding_digest": binding_digest,
                "semantics_digest": self.semantics.semantics_digest,
            },
        )
        if hasattr(self, "binding_digest") or hasattr(self, "attachment_digest"):
            if (
                getattr(self, "binding_digest", None) != binding_digest
                or getattr(self, "attachment_digest", None) != attachment_digest
            ):
                raise ProtocolShapeError("ExecutionAttachmentV2 attachment seal is stale")
            return
        object.__setattr__(self, "binding_digest", binding_digest)
        object.__setattr__(self, "attachment_digest", attachment_digest)

    def _validate_rule_shape(self) -> None:
        for name in ("rule_id", "rule_digest"):
            _require_bounded_str(getattr(self, name), field_name=f"ExecutionAttachmentV2.{name}")
        _require_token(self.rule_digest, field_name="ExecutionAttachmentV2.rule_digest")
        if self.rule_version is not None:
            _require_bounded_str(self.rule_version, field_name="ExecutionAttachmentV2.rule_version")
        if self.occurrence_alias is not None or self.structural_node_id is not None:
            raise ProtocolShapeError("rule attachment cannot carry occurrence or choice node")
        if self.target.target_kind == "rule" and (
            self.target.target_id != self.rule_id or self.target.target_version != self.rule_version
        ):
            raise ProtocolShapeError("direct Rule attachment must match its target Rule identity")
        # ``target_digest`` is deliberately *not* the Rule content digest.
        # ProductRuleV1's target pin includes the resolved schema/semantic
        # contract (its logical identity), while ``rule_digest`` remains the
        # independently captured authored Rule content pin.  Equating these
        # two values would let the same text-shaped Rule cross a schema
        # boundary under one direct-rule profile.

    def _validate_occurrence_shape(self) -> None:
        if self.target.target_kind != "policy":
            raise ProtocolShapeError("occurrence attachment requires Policy target")
        for name in ("rule_id", "rule_digest", "occurrence_alias"):
            _require_bounded_str(getattr(self, name), field_name=f"ExecutionAttachmentV2.{name}")
        _require_token(self.rule_digest, field_name="ExecutionAttachmentV2.rule_digest")
        if self.rule_version is not None:
            _require_bounded_str(self.rule_version, field_name="ExecutionAttachmentV2.rule_version")
        if self.structural_node_id is not None:
            raise ProtocolShapeError("occurrence attachment cannot carry choice node")

    def _validate_choice_shape(self) -> None:
        if self.target.target_kind != "policy":
            raise ProtocolShapeError("choice attachment requires Policy target")
        _require_bounded_str(
            self.structural_node_id, field_name="ExecutionAttachmentV2.structural_node_id"
        )
        if (
            self.rule_id is not None
            or self.rule_version is not None
            or self.rule_digest is not None
            or self.occurrence_alias is not None
        ):
            raise ProtocolShapeError("choice attachment cannot carry Rule/occurrence fields")

    def to_wire(self) -> dict[str, object]:
        """Return the canonical authored execution-attachment payload."""
        return {
            "kind": self.kind,
            "target": self.target.to_wire(),
            "semantics": self.semantics.to_wire(),
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "rule_digest": self.rule_digest,
            "occurrence_alias": self.occurrence_alias,
            "structural_node_id": self.structural_node_id,
        }


def _assert_engine_pin_v2_current(value: EvaluationEnginePinV2) -> None:
    if not isinstance(value, EvaluationEnginePinV2):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 engine pin is malformed")
    fresh = EvaluationEnginePinV2(
        engine=value.engine,
        engine_version=value.engine_version,
        adapter_version=value.adapter_version,
    )
    if fresh.pin_digest != value.pin_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 engine pin seal is stale")


def _assert_resource_policy_v2_current(value: EvaluationResourcePolicyV2) -> None:
    if not isinstance(value, EvaluationResourcePolicyV2):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 resources are malformed")
    fresh = EvaluationResourcePolicyV2(max_rows=value.max_rows, timeout_ms=value.timeout_ms)
    if fresh.policy_digest != value.policy_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 resource policy seal is stale")


def _assert_capture_policy_v2_current(value: EvaluationCapturePolicyV2) -> None:
    if not isinstance(value, EvaluationCapturePolicyV2):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 capture policy is malformed")
    fresh = EvaluationCapturePolicyV2(mode=value.mode, max_capture_bytes=value.max_capture_bytes)
    if fresh.policy_digest != value.policy_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 capture policy seal is stale")


def _assert_semantics_v2_current(value: EvaluationSemanticsV2) -> None:
    if isinstance(value, DeterministicSemanticsV2):
        fresh: EvaluationSemanticsV2 = DeterministicSemanticsV2(model=value.model)
    elif isinstance(value, ProbLogPointSemanticsV2):
        fresh = ProbLogPointSemanticsV2(
            model=value.model,
            identity_probability=value.identity_probability,
            materialization=value.materialization,
        )
    else:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 semantics are malformed")
    if fresh.semantics_digest != value.semantics_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 semantics seal is stale")


def _assert_target_pin_v2_current(value: EvaluationTargetPinV2) -> None:
    if not isinstance(value, EvaluationTargetPinV2):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 target pin is malformed")
    fresh = EvaluationTargetPinV2(
        side=value.side,
        target_kind=value.target_kind,
        target_id=value.target_id,
        target_version=value.target_version,
        target_digest=value.target_digest,
    )
    if fresh.pin_digest != value.pin_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 target pin seal is stale")


def _assert_attachment_semantics_v2_current(value: ExecutionAttachmentSemanticsV2) -> None:
    if not isinstance(value, ExecutionAttachmentSemanticsV2):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 attachment semantics are malformed")
    fresh = ExecutionAttachmentSemanticsV2(kind=value.kind)
    if fresh.semantics_digest != value.semantics_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 attachment semantics seal is stale")


def _assert_attachment_v2_current(value: ExecutionAttachmentV2) -> None:
    if not isinstance(value, ExecutionAttachmentV2):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 attachment is malformed")
    _assert_target_pin_v2_current(value.target)
    _assert_attachment_semantics_v2_current(value.semantics)
    fresh = ExecutionAttachmentV2(
        kind=value.kind,
        target=value.target,
        semantics=value.semantics,
        rule_id=value.rule_id,
        rule_version=value.rule_version,
        rule_digest=value.rule_digest,
        occurrence_alias=value.occurrence_alias,
        structural_node_id=value.structural_node_id,
    )
    if (
        fresh.binding_digest != value.binding_digest
        or fresh.attachment_digest != value.attachment_digest
    ):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 attachment seal is stale")


@dataclass(frozen=True)
class ResolvedExecutionAttachmentV2:
    """Verified private lowering slots for one public attachment pin.

    Slots are digest tokens, not compiler branch labels.  A compiler/runtime
    creates this only after proving a total lineage expansion from the exact
    authored pin.  The public profile and SDK never expose the slots.
    """

    attachment_digest: str
    lowering_slot_digests: tuple[str, ...]
    resolution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(
            self.attachment_digest,
            field_name="ResolvedExecutionAttachmentV2.attachment_digest",
        )
        if (
            not isinstance(self.lowering_slot_digests, tuple)
            or not self.lowering_slot_digests
            or len(self.lowering_slot_digests) > MAX_EXECUTION_PROFILE_V2_LOWERING_SLOTS
        ):
            raise ProtocolShapeError(
                "ResolvedExecutionAttachmentV2.lowering_slot_digests must be bounded non-empty tuple"
            )
        slots = tuple(sorted(self.lowering_slot_digests))
        if len(set(slots)) != len(slots):
            raise ProtocolShapeError("ResolvedExecutionAttachmentV2 lowering slots must be unique")
        for index, digest in enumerate(slots):
            _require_token(
                digest,
                field_name=f"ResolvedExecutionAttachmentV2.lowering_slot_digests[{index}]",
            )
        expected_digest = _token(
            "resolved_execution_attachment_v2",
            {"attachment_digest": self.attachment_digest, "lowering_slots": slots},
        )
        if hasattr(self, "resolution_digest"):
            if self.lowering_slot_digests != slots or self.resolution_digest != expected_digest:
                raise ProtocolShapeError("ResolvedExecutionAttachmentV2 seal is stale")
            return
        object.__setattr__(self, "lowering_slot_digests", slots)
        object.__setattr__(self, "resolution_digest", expected_digest)


def _assert_resolved_attachment_v2_current(value: ResolvedExecutionAttachmentV2) -> None:
    if not isinstance(value, ResolvedExecutionAttachmentV2):
        raise ProtocolShapeError("ResolvedExecutionAttachmentsV2 attachment is malformed")
    fresh = ResolvedExecutionAttachmentV2(
        attachment_digest=value.attachment_digest,
        lowering_slot_digests=value.lowering_slot_digests,
    )
    if (
        fresh.resolution_digest != value.resolution_digest
        or fresh.lowering_slot_digests != value.lowering_slot_digests
    ):
        raise ProtocolShapeError("ResolvedExecutionAttachmentsV2 attachment seal is stale")


@dataclass(frozen=True)
class ResolvedExecutionAttachmentsV2:
    """A total compiler-proved attachment expansion for one profile snapshot."""

    profile_digest: str
    attachments: tuple[ResolvedExecutionAttachmentV2, ...]
    resolution_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(
            self.profile_digest, field_name="ResolvedExecutionAttachmentsV2.profile_digest"
        )
        if not isinstance(self.attachments, tuple) or not all(
            isinstance(item, ResolvedExecutionAttachmentV2) for item in self.attachments
        ):
            raise ProtocolShapeError(
                "ResolvedExecutionAttachmentsV2.attachments must be ResolvedExecutionAttachmentV2 tuple"
            )
        for item in self.attachments:
            _assert_resolved_attachment_v2_current(item)
        attachments = tuple(sorted(self.attachments, key=lambda item: item.attachment_digest))
        if len({item.attachment_digest for item in attachments}) != len(attachments):
            raise ProtocolShapeError("ResolvedExecutionAttachmentsV2 attachments must be unique")
        slot_owners: dict[str, str] = {}
        for attachment in attachments:
            for slot in attachment.lowering_slot_digests:
                previous = slot_owners.setdefault(slot, attachment.attachment_digest)
                if previous != attachment.attachment_digest:
                    raise ProtocolShapeError(
                        "ResolvedExecutionAttachmentsV2 detects rule/occurrence lowering overlap"
                    )
        expected_digest = _token(
            "resolved_execution_attachments_v2",
            {
                "profile_digest": self.profile_digest,
                "attachments": tuple(item.resolution_digest for item in attachments),
            },
        )
        if hasattr(self, "resolution_digest"):
            if self.attachments != attachments or self.resolution_digest != expected_digest:
                raise ProtocolShapeError("ResolvedExecutionAttachmentsV2 seal is stale")
            return
        object.__setattr__(self, "attachments", attachments)
        object.__setattr__(self, "resolution_digest", expected_digest)


def _assert_resolved_attachments_v2_current(value: ResolvedExecutionAttachmentsV2) -> None:
    if not isinstance(value, ResolvedExecutionAttachmentsV2):
        raise ProtocolShapeError("resolved attachment carrier is malformed")
    fresh = ResolvedExecutionAttachmentsV2(
        profile_digest=value.profile_digest,
        attachments=value.attachments,
    )
    if fresh.resolution_digest != value.resolution_digest or fresh.attachments != value.attachments:
        raise ProtocolShapeError("resolved attachment carrier seal is stale")


@dataclass(frozen=True)
class EvaluationExecutionProfileV2:
    """Canonical V2 profile with a closed semantics model and attachment set."""

    kind: EvaluationProfileKindV2
    name: str | None
    compiler_digest: str
    engines: tuple[EvaluationEnginePinV2, ...]
    semantics: EvaluationSemanticsV2
    resources: EvaluationResourcePolicyV2 = field(default_factory=EvaluationResourcePolicyV2)
    capture: EvaluationCapturePolicyV2 = field(default_factory=EvaluationCapturePolicyV2)
    # A V2 profile is target-scoped before it is executed.  Attachments already
    # carry a target pin, but a plain probabilistic-fact profile has no
    # attachment at all; without this inventory it could be spliced onto an
    # unrelated Rule/Policy at plan time.  ``()`` remains useful only for
    # protocol construction tests and is rejected by the public runner.
    target_pins: tuple[EvaluationTargetPinV2, ...] = ()
    attachments: tuple[ExecutionAttachmentV2, ...] = ()
    profile_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(
            self.kind, field_name="EvaluationExecutionProfileV2.kind", allowed=_PROFILE_KINDS
        )
        if self.name is not None:
            _require_bounded_str(self.name, field_name="EvaluationExecutionProfileV2.name")
        _require_token(
            self.compiler_digest, field_name="EvaluationExecutionProfileV2.compiler_digest"
        )
        if not isinstance(self.engines, tuple) or not all(
            isinstance(item, EvaluationEnginePinV2) for item in self.engines
        ):
            raise ProtocolShapeError("EvaluationExecutionProfileV2.engines must be pin tuple")
        for engine_pin in self.engines:
            _assert_engine_pin_v2_current(engine_pin)
        engine_names = tuple(engine_pin.engine for engine_pin in self.engines)
        if (
            len(set(engine_names)) != len(engine_names)
            or engine_names != _PROFILE_ENGINE_ORDER[self.kind]
        ):
            raise ProtocolShapeError(
                "EvaluationExecutionProfileV2 engines do not match profile kind"
            )
        if self.kind in {"native_deterministic_v2", "portable_deterministic_v2"}:
            if not isinstance(self.semantics, DeterministicSemanticsV2):
                raise ProtocolShapeError("native deterministic V2 profile has wrong semantic model")
        elif not isinstance(self.semantics, ProbLogPointSemanticsV2):
            raise ProtocolShapeError("ProbLog point V2 profile has wrong semantic model")
        _assert_semantics_v2_current(self.semantics)
        if not isinstance(self.resources, EvaluationResourcePolicyV2):
            raise ProtocolShapeError("EvaluationExecutionProfileV2.resources is malformed")
        _assert_resource_policy_v2_current(self.resources)
        if not isinstance(self.capture, EvaluationCapturePolicyV2):
            raise ProtocolShapeError("EvaluationExecutionProfileV2.capture is malformed")
        _assert_capture_policy_v2_current(self.capture)
        if (
            not isinstance(self.target_pins, tuple)
            or len(self.target_pins) > 2
            or not all(isinstance(item, EvaluationTargetPinV2) for item in self.target_pins)
        ):
            raise ProtocolShapeError("EvaluationExecutionProfileV2.target_pins are malformed")
        for target_pin in self.target_pins:
            _assert_target_pin_v2_current(target_pin)
        target_pins = tuple(sorted(self.target_pins, key=lambda item: item.pin_digest))
        if len({item.pin_digest for item in target_pins}) != len(target_pins):
            raise ProtocolShapeError("EvaluationExecutionProfileV2 target pins must be unique")
        if len({item.side for item in target_pins}) != len(target_pins):
            raise ProtocolShapeError(
                "EvaluationExecutionProfileV2 target pins must have unique sides"
            )
        if (
            not isinstance(self.attachments, tuple)
            or len(self.attachments) > MAX_EXECUTION_PROFILE_V2_ATTACHMENTS
            or not all(isinstance(item, ExecutionAttachmentV2) for item in self.attachments)
        ):
            raise ProtocolShapeError("EvaluationExecutionProfileV2.attachments are malformed")
        for attachment in self.attachments:
            _assert_attachment_v2_current(attachment)
        attachments = _canonical_attachments(self.attachments)
        known_pins = {item.pin_digest for item in target_pins}
        if any(item.target.pin_digest not in known_pins for item in attachments):
            raise ProtocolShapeError(
                "EvaluationExecutionProfileV2 attachment target must be declared by target_pins"
            )
        if self.kind in {"native_deterministic_v2", "portable_deterministic_v2"} and attachments:
            raise ProtocolShapeError(
                "deterministic V2 profile does not accept probability attachments"
            )
        expected_digest = _token(
            "evaluation_execution_profile_v2",
            {
                "kind": self.kind,
                "name": self.name,
                "compiler_digest": self.compiler_digest,
                "engines": tuple(item.pin_digest for item in self.engines),
                "semantics_digest": self.semantics.semantics_digest,
                "resources_digest": self.resources.policy_digest,
                "capture_digest": self.capture.policy_digest,
                "target_pins": tuple(item.pin_digest for item in target_pins),
                "attachments": tuple(item.attachment_digest for item in attachments),
            },
        )
        if hasattr(self, "profile_digest"):
            if self.profile_digest != expected_digest:
                raise ProtocolShapeError("EvaluationExecutionProfileV2.profile_digest is stale")
            if self.target_pins != target_pins or self.attachments != attachments:
                raise ProtocolShapeError("EvaluationExecutionProfileV2 canonical ordering is stale")
            return
        object.__setattr__(self, "target_pins", target_pins)
        object.__setattr__(self, "attachments", attachments)
        object.__setattr__(self, "profile_digest", expected_digest)

    def to_bytes(self) -> bytes:
        """Serialize this sealed profile to canonical V2 bytes.

        Returns:
            Canonical bytes that include all engine, target and attachment pins.
        """
        return evaluation_execution_profile_v2_bytes(self)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "EvaluationExecutionProfileV2":
        """Decode and validate a canonical V2 execution profile.

        Args:
            raw: Canonical bytes produced by ``to_bytes()``.

        Returns:
            A fully validated sealed execution profile.

        Raises:
            ProtocolShapeError: If the payload or any nested seal is invalid.
        """
        result = evaluation_execution_profile_v2_from_bytes(raw)
        if not isinstance(result, cls):  # pragma: no cover - defensive boundary
            raise ProtocolShapeError("EvaluationExecutionProfileV2 codec returned wrong type")
        return result


def _canonical_attachments(
    attachments: tuple[ExecutionAttachmentV2, ...],
) -> tuple[ExecutionAttachmentV2, ...]:
    by_binding: dict[str, ExecutionAttachmentV2] = {}
    for attachment in attachments:
        existing = by_binding.get(attachment.binding_digest)
        if existing is None:
            by_binding[attachment.binding_digest] = attachment
        elif existing.attachment_digest != attachment.attachment_digest:
            raise ProtocolShapeError("conflicting duplicate V2 execution attachment")
    return tuple(sorted(by_binding.values(), key=lambda item: item.attachment_digest))


def profile_accepts_fact_semantics_v2(
    profile: EvaluationExecutionProfileV2,
    fact_semantics: FactSemanticsV2 | None,
) -> bool:
    """Validate profile/Scenario fact-semantics compatibility before an engine call."""

    if not isinstance(profile, EvaluationExecutionProfileV2):
        raise ProtocolShapeError("profile must be EvaluationExecutionProfileV2")
    if fact_semantics is None:
        return True
    if not isinstance(fact_semantics, FactSemanticsV2):
        raise ProtocolShapeError("fact_semantics must be FactSemanticsV2 or None")
    if profile.kind != "problog_point_v2":
        raise ProtocolShapeError(
            "deterministic V2 profile rejects probabilistic Scenario fact semantics"
        )
    return True


def validate_resolved_execution_attachments_v2(
    profile: EvaluationExecutionProfileV2,
    resolved: ResolvedExecutionAttachmentsV2,
) -> None:
    """Ensure one compiler-expanded attachment carrier exactly covers a profile."""

    if not isinstance(profile, EvaluationExecutionProfileV2) or not isinstance(
        resolved, ResolvedExecutionAttachmentsV2
    ):
        raise ProtocolShapeError("profile/resolved attachments are malformed")
    assert_evaluation_execution_profile_v2_current(profile)
    _assert_resolved_attachments_v2_current(resolved)
    if resolved.profile_digest != profile.profile_digest:
        raise ProtocolShapeError("resolved attachment profile digest does not match profile")
    expected = {item.attachment_digest for item in profile.attachments}
    actual = {item.attachment_digest for item in resolved.attachments}
    if actual != expected:
        raise ProtocolShapeError(
            "resolved attachment carrier does not exactly cover profile attachments"
        )


def _semantics_to_wire(semantics: EvaluationSemanticsV2) -> dict[str, object]:
    return dict(semantics.to_wire())


def _semantics_from_wire(value: object) -> EvaluationSemanticsV2:
    row = _assert_exact_keys(
        value,
        frozenset({"kind", "model"})
        if isinstance(value, dict) and value.get("kind") == "deterministic"
        else frozenset({"kind", "model", "identity_probability", "materialization"}),
        label="EvaluationExecutionProfileV2 semantics",
    )
    if row["kind"] == "deterministic":
        return DeterministicSemanticsV2(model=row["model"])  # type: ignore[arg-type]
    if row["kind"] == "problog_point":
        return ProbLogPointSemanticsV2(
            model=row["model"],  # type: ignore[arg-type]
            identity_probability=row["identity_probability"],  # type: ignore[arg-type]
            materialization=row["materialization"],  # type: ignore[arg-type]
        )
    raise ProtocolShapeError("EvaluationExecutionProfileV2 semantics kind is invalid")


def _target_from_wire(value: object) -> EvaluationTargetPinV2:
    row = _assert_exact_keys(
        value,
        frozenset({"side", "target_kind", "target_id", "target_version", "target_digest"}),
        label="EvaluationExecutionProfileV2 attachment target",
    )
    return EvaluationTargetPinV2(
        side=row["side"],  # type: ignore[arg-type]
        target_kind=row["target_kind"],  # type: ignore[arg-type]
        target_id=row["target_id"],  # type: ignore[arg-type]
        target_version=row["target_version"],  # type: ignore[arg-type]
        target_digest=row["target_digest"],  # type: ignore[arg-type]
    )


def _attachment_from_wire(value: object) -> ExecutionAttachmentV2:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "kind",
                "target",
                "semantics",
                "rule_id",
                "rule_version",
                "rule_digest",
                "occurrence_alias",
                "structural_node_id",
            }
        ),
        label="EvaluationExecutionProfileV2 attachment",
    )
    semantics_row = _assert_exact_keys(
        row["semantics"],
        frozenset({"kind"}),
        label="EvaluationExecutionProfileV2 attachment semantics",
    )
    return ExecutionAttachmentV2(
        kind=row["kind"],  # type: ignore[arg-type]
        target=_target_from_wire(row["target"]),
        semantics=ExecutionAttachmentSemanticsV2(kind=semantics_row["kind"]),  # type: ignore[arg-type]
        rule_id=row["rule_id"],  # type: ignore[arg-type]
        rule_version=row["rule_version"],  # type: ignore[arg-type]
        rule_digest=row["rule_digest"],  # type: ignore[arg-type]
        occurrence_alias=row["occurrence_alias"],  # type: ignore[arg-type]
        structural_node_id=row["structural_node_id"],  # type: ignore[arg-type]
    )


def _profile_to_wire(profile: EvaluationExecutionProfileV2) -> dict[str, object]:
    return {
        "$type": "EvaluationExecutionProfileV2",
        "kind": profile.kind,
        "name": profile.name,
        "compiler_digest": profile.compiler_digest,
        "engines": [item.to_wire() for item in profile.engines],
        "semantics": _semantics_to_wire(profile.semantics),
        "resources": profile.resources.to_wire(),
        "capture": profile.capture.to_wire(),
        "target_pins": [item.to_wire() for item in profile.target_pins],
        "attachments": [item.to_wire() for item in profile.attachments],
    }


def assert_evaluation_execution_profile_v2_current(
    profile: EvaluationExecutionProfileV2,
) -> None:
    """Recursively verify a profile without mutating/resealing it.

    A frozen dataclass can still be changed with ``object.__setattr__``.  The
    public execution path must therefore not call ``__post_init__`` on a live
    profile: that would recompute an old digest over altered nested settings.
    Re-decoding its raw public wire creates a fresh independently validated
    snapshot, which we compare to the existing cached identity and canonical
    ordering without writing to the supplied object.
    """

    if not isinstance(profile, EvaluationExecutionProfileV2):
        raise ProtocolShapeError("profile must be EvaluationExecutionProfileV2")
    raw = _canonical_json_bytes(_profile_to_wire(profile), label="EvaluationExecutionProfileV2")
    fresh = evaluation_execution_profile_v2_from_bytes(raw)
    canonical = _canonical_json_bytes(_profile_to_wire(fresh), label="EvaluationExecutionProfileV2")
    if raw != canonical or fresh.profile_digest != profile.profile_digest:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 profile seal is stale")


def evaluation_execution_profile_v2_bytes(profile: EvaluationExecutionProfileV2) -> bytes:
    """Encode only the exact canonical V2 profile wire shape."""

    if not isinstance(profile, EvaluationExecutionProfileV2):
        raise ProtocolShapeError("profile must be EvaluationExecutionProfileV2")
    assert_evaluation_execution_profile_v2_current(profile)
    raw = _canonical_json_bytes(_profile_to_wire(profile), label="EvaluationExecutionProfileV2")
    if len(raw) > MAX_EXECUTION_PROFILE_V2_BYTES:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 exceeds codec size cap")
    return raw


def evaluation_execution_profile_v2_from_bytes(raw: bytes) -> EvaluationExecutionProfileV2:
    """Decode a strict duplicate-key-free canonical V2 profile byte sequence."""

    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_EXECUTION_PROFILE_V2_BYTES:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 bytes are empty or exceed cap")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError(
            "EvaluationExecutionProfileV2 bytes must be canonical JSON"
        ) from exc
    if _json_depth(value) > MAX_EXECUTION_PROFILE_V2_DEPTH:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 exceeds JSON depth cap")
    if _canonical_json_bytes(value, label="EvaluationExecutionProfileV2") != raw:
        raise ProtocolShapeError("EvaluationExecutionProfileV2 bytes must be canonical JSON")
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "$type",
                "kind",
                "name",
                "compiler_digest",
                "engines",
                "semantics",
                "resources",
                "capture",
                "target_pins",
                "attachments",
            }
        ),
        label="EvaluationExecutionProfileV2",
    )
    if row["$type"] != "EvaluationExecutionProfileV2":
        raise ProtocolShapeError("EvaluationExecutionProfileV2 type is invalid")
    engines_raw = row["engines"]
    if not isinstance(engines_raw, list):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 engines must be array")
    engines: list[EvaluationEnginePinV2] = []
    for index, item in enumerate(engines_raw):
        item_row = _assert_exact_keys(
            item,
            frozenset({"engine", "engine_version", "adapter_version"}),
            label=f"EvaluationExecutionProfileV2 engine[{index}]",
        )
        engines.append(
            EvaluationEnginePinV2(
                engine=item_row["engine"],  # type: ignore[arg-type]
                engine_version=item_row["engine_version"],  # type: ignore[arg-type]
                adapter_version=item_row["adapter_version"],  # type: ignore[arg-type]
            )
        )
    resources_row = _assert_exact_keys(
        row["resources"],
        frozenset({"max_rows", "timeout_ms"}),
        label="EvaluationExecutionProfileV2 resources",
    )
    capture_row = _assert_exact_keys(
        row["capture"],
        frozenset({"mode", "max_capture_bytes"}),
        label="EvaluationExecutionProfileV2 capture",
    )
    attachments_raw = row["attachments"]
    if not isinstance(attachments_raw, list):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 attachments must be array")
    target_pins_raw = row["target_pins"]
    if not isinstance(target_pins_raw, list):
        raise ProtocolShapeError("EvaluationExecutionProfileV2 target_pins must be array")
    return EvaluationExecutionProfileV2(
        kind=row["kind"],  # type: ignore[arg-type]
        name=row["name"],  # type: ignore[arg-type]
        compiler_digest=row["compiler_digest"],  # type: ignore[arg-type]
        engines=tuple(engines),
        semantics=_semantics_from_wire(row["semantics"]),
        resources=EvaluationResourcePolicyV2(
            max_rows=resources_row["max_rows"],  # type: ignore[arg-type]
            timeout_ms=resources_row["timeout_ms"],  # type: ignore[arg-type]
        ),
        capture=EvaluationCapturePolicyV2(
            mode=capture_row["mode"],  # type: ignore[arg-type]
            max_capture_bytes=capture_row["max_capture_bytes"],  # type: ignore[arg-type]
        ),
        target_pins=tuple(_target_from_wire(item) for item in target_pins_raw),
        attachments=tuple(_attachment_from_wire(item) for item in attachments_raw),
    )


__all__ = [
    "DeterministicSemanticsV2",
    "EvaluationAttachmentKindV2",
    "EvaluationAttachmentSemanticsKindV2",
    "EvaluationCaptureModeV2",
    "EvaluationCapturePolicyV2",
    "EvaluationEnginePinV2",
    "EvaluationEngineV2",
    "EvaluationExecutionProfileV2",
    "EvaluationProfileKindV2",
    "EvaluationResourcePolicyV2",
    "EvaluationSemanticsV2",
    "EvaluationTargetPinV2",
    "EvaluationTargetSideV2",
    "ExecutionAttachmentSemanticsV2",
    "ExecutionAttachmentV2",
    "MAX_EXECUTION_PROFILE_V2_ATTACHMENTS",
    "MAX_EXECUTION_PROFILE_V2_BYTES",
    "MAX_EXECUTION_PROFILE_V2_CAPTURE_BYTES",
    "MAX_EXECUTION_PROFILE_V2_DEPTH",
    "MAX_EXECUTION_PROFILE_V2_LOWERING_SLOTS",
    "MAX_EXECUTION_PROFILE_V2_ROWS",
    "MAX_EXECUTION_PROFILE_V2_TIMEOUT_MS",
    "ProbLogPointSemanticsV2",
    "ResolvedExecutionAttachmentV2",
    "ResolvedExecutionAttachmentsV2",
    "assert_evaluation_execution_profile_v2_current",
    "evaluation_execution_profile_v2_bytes",
    "evaluation_execution_profile_v2_from_bytes",
    "profile_accepts_fact_semantics_v2",
    "validate_resolved_execution_attachments_v2",
]
