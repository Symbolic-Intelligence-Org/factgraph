"""Pre-evaluation identity for one bounded Query effective relation.

This parallel v1 value deliberately does not replace the Q7/Q11 Scenario
resolution DTOs.  Those compatibility DTOs seal an observed result diff, while
this value seals only the relation that is admissible *before* evaluation.
Neither name implies a global ledger or historical snapshot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_bool, _require_non_empty_str
from .evaluation_scenario import ScenarioScalarValueV0
from .schema_runtime import FieldPath

QueryEffectiveSnapshotScopeV1 = Literal["query_dependency_relation_v1"]
QueryEffectiveSnapshotNormalizationProfileV1 = Literal[
    "single_field_replacement_v0",
    "atomic_field_replacement_set_v0",
]

_NORMALIZATION_PROFILES = frozenset(
    {
        "single_field_replacement_v0",
        "atomic_field_replacement_set_v0",
    }
)


@dataclass(frozen=True)
class ResolvedExistingVisibleScalarReplacementV1:
    """One schema-resolved replacement in an effective Query relation.

    The values and assertion ids identify a concrete relation transition.  They
    do not assert that the effective value is a ledger fact or that its caller
    premise is true.
    """

    premise_id: str
    entity_ref: str
    field: FieldPath
    predicate_id: str
    baseline_assertion_id: str
    synthetic_witness_id: str
    baseline_value: ScenarioScalarValueV0
    effective_value: ScenarioScalarValueV0
    semantic_value_changed: bool
    operation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "premise_id",
            "entity_ref",
            "predicate_id",
            "baseline_assertion_id",
            "synthetic_witness_id",
        ):
            _require_non_empty_str(
                getattr(self, name),
                field_name=f"ResolvedExistingVisibleScalarReplacementV1.{name}",
            )
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError(
                "ResolvedExistingVisibleScalarReplacementV1.field must be FieldPath"
            )
        if not isinstance(self.baseline_value, ScenarioScalarValueV0) or not isinstance(
            self.effective_value, ScenarioScalarValueV0
        ):
            raise ProtocolShapeError(
                "ResolvedExistingVisibleScalarReplacementV1 values must be ScenarioScalarValueV0"
            )
        if self.baseline_value.tag != self.effective_value.tag:
            raise ProtocolShapeError(
                "ResolvedExistingVisibleScalarReplacementV1 values must share one scalar tag"
            )
        _require_bool(
            self.semantic_value_changed,
            field_name="ResolvedExistingVisibleScalarReplacementV1.semantic_value_changed",
        )
        if self.semantic_value_changed != (self.baseline_value != self.effective_value):
            raise ProtocolShapeError(
                "ResolvedExistingVisibleScalarReplacementV1 semantic delta does not match values"
            )
        object.__setattr__(
            self,
            "operation_digest",
            _token(
                "resolved_existing_visible_scalar_replacement_v1",
                {
                    "premise_id": self.premise_id,
                    "entity_ref": self.entity_ref,
                    "field": (self.field.entity_type, self.field.field_name),
                    "predicate_id": self.predicate_id,
                    "baseline_assertion_id": self.baseline_assertion_id,
                    "synthetic_witness_id": self.synthetic_witness_id,
                    "baseline_value": (self.baseline_value.tag, self.baseline_value.value),
                    "effective_value": (self.effective_value.tag, self.effective_value.value),
                    "semantic_value_changed": self.semantic_value_changed,
                },
            ),
        )

    @property
    def canonical_target_key(self) -> tuple[str, str, str]:
        """Stable sort key; the baseline assertion stays a separate pin."""

        return (self.entity_ref, self.field.entity_type, self.field.field_name)


@dataclass(frozen=True)
class QueryEffectiveSnapshotV1:
    """Identity-only description of one Query dependency relation transition.

    The associated immutable relations are intentionally runtime-private.  This
    public DTO is not a portable replay codec and has no current/live claim on
    its own; callers must retain the separately captured base-view guard.
    """

    query_digest: str
    policy_digest: str
    address_space_digest: str
    schema_digest: str
    base_view_digest: str
    dependency_predicate_ids: tuple[str, ...]
    baseline_relation_digest: str
    effective_relation_digest: str
    operations: tuple[ResolvedExistingVisibleScalarReplacementV1, ...]
    normalization_profile: QueryEffectiveSnapshotNormalizationProfileV1
    scope: QueryEffectiveSnapshotScopeV1 = "query_dependency_relation_v1"
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("query_digest", "policy_digest", "address_space_digest"):
            _sha256_hex(getattr(self, name), f"QueryEffectiveSnapshotV1.{name}")
        for name in (
            "schema_digest",
            "base_view_digest",
            "baseline_relation_digest",
            "effective_relation_digest",
        ):
            _sha256_token(getattr(self, name), f"QueryEffectiveSnapshotV1.{name}")
        if self.scope != "query_dependency_relation_v1":
            raise ProtocolShapeError("QueryEffectiveSnapshotV1.scope is invalid")
        if (
            not isinstance(self.dependency_predicate_ids, tuple)
            or not self.dependency_predicate_ids
            or any(not isinstance(item, str) or not item for item in self.dependency_predicate_ids)
            or self.dependency_predicate_ids != tuple(sorted(self.dependency_predicate_ids))
            or len(set(self.dependency_predicate_ids)) != len(self.dependency_predicate_ids)
        ):
            raise ProtocolShapeError(
                "QueryEffectiveSnapshotV1 dependency predicates must be canonical and non-empty"
            )
        if (
            not isinstance(self.operations, tuple)
            or not self.operations
            or not all(
                isinstance(item, ResolvedExistingVisibleScalarReplacementV1)
                for item in self.operations
            )
        ):
            raise ProtocolShapeError(
                "QueryEffectiveSnapshotV1.operations must be resolved scalar replacements"
            )
        operation_keys = tuple(item.canonical_target_key for item in self.operations)
        if operation_keys != tuple(sorted(operation_keys)) or len(set(operation_keys)) != len(operation_keys):
            raise ProtocolShapeError(
                "QueryEffectiveSnapshotV1.operations must have canonical unique targets"
            )
        premise_ids = tuple(item.premise_id for item in self.operations)
        if len(set(premise_ids)) != len(premise_ids):
            raise ProtocolShapeError("QueryEffectiveSnapshotV1 operations must have unique premise ids")
        if self.normalization_profile not in _NORMALIZATION_PROFILES:
            raise ProtocolShapeError("QueryEffectiveSnapshotV1 normalization profile is invalid")
        required_count = 1 if self.normalization_profile == "single_field_replacement_v0" else 2
        if len(self.operations) < required_count or (
            self.normalization_profile == "single_field_replacement_v0" and len(self.operations) != 1
        ):
            raise ProtocolShapeError(
                "QueryEffectiveSnapshotV1 normalization profile does not match operation inventory"
            )
        if any(item.predicate_id not in self.dependency_predicate_ids for item in self.operations):
            raise ProtocolShapeError(
                "QueryEffectiveSnapshotV1 operation is outside dependency predicates"
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            _token(
                "query_effective_snapshot_v1",
                {
                    "scope": self.scope,
                    "query_digest": self.query_digest,
                    "policy_digest": self.policy_digest,
                    "address_space_digest": self.address_space_digest,
                    "schema_digest": self.schema_digest,
                    "base_view_digest": self.base_view_digest,
                    "dependency_predicate_ids": self.dependency_predicate_ids,
                    "baseline_relation_digest": self.baseline_relation_digest,
                    "effective_relation_digest": self.effective_relation_digest,
                    "operation_digests": tuple(item.operation_digest for item in self.operations),
                    "normalization_profile": self.normalization_profile,
                },
            ),
        )


def _sha256_hex(value: object, field_name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
    ):
        raise ProtocolShapeError(f"{field_name} must be lowercase sha256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be lowercase sha256 hex") from exc


def _sha256_token(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    _sha256_hex(value[7:], field_name)


def _token(label: str, payload: object) -> str:
    try:
        raw = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # pragma: no cover - guarded constructor inputs
        raise ProtocolShapeError("QueryEffectiveSnapshotV1 payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(raw)}"


__all__ = [
    "QueryEffectiveSnapshotNormalizationProfileV1",
    "QueryEffectiveSnapshotScopeV1",
    "QueryEffectiveSnapshotV1",
    "ResolvedExistingVisibleScalarReplacementV1",
]
