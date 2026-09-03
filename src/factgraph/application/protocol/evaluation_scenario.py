"""Narrow, replacement-only Scenario protocol values.

This module deliberately does not define a general premise algebra.  The v0
contract represents one already-visible scalar field substitution which is
resolved by the trusted SDK runtime before the ordinary native Query evaluator
runs.  It is not an asserted fact and has no EvidenceGraph/replay contract.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms

from .common import ProtocolShapeError, _require_bool, _require_non_empty_str
from .schema_runtime import EntityRef, FieldPath

ScenarioInputValue: TypeAlias = str | int | float | bool | bytes
ScenarioScalarTag: TypeAlias = Literal[
    "string",
    "int",
    "float64",
    "bool",
    "bytes",
    "time",
    "uuid",
]
ScenarioScalarStorage: TypeAlias = str | int | bool

_SCALAR_TAGS = frozenset(
    {"string", "int", "float64", "bool", "bytes", "time", "uuid"}
)


@dataclass(frozen=True)
class ScenarioFieldSubstitutionV0:
    """One direct, run-local replacement of a visible scalar field value.

    ``EntityRef.encoded_ref`` is intentionally non-authoritative input.  The
    runtime re-materializes identity through the active trusted schema before
    it resolves the target fact.
    """

    entity: EntityRef
    field: FieldPath
    value: ScenarioInputValue
    premise_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.entity, EntityRef):
            raise ProtocolShapeError("ScenarioFieldSubstitutionV0.entity must be EntityRef")
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("ScenarioFieldSubstitutionV0.field must be FieldPath")
        if self.entity.entity_type != self.field.entity_type:
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionV0.entity and field must have the same entity_type"
            )
        if not isinstance(self.value, (str, int, float, bool, bytes)):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionV0.value must be one scalar protocol value"
            )
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ProtocolShapeError("ScenarioFieldSubstitutionV0.value float must be finite")
        _require_non_empty_str(self.premise_id, field_name="ScenarioFieldSubstitutionV0.premise_id")


@dataclass(frozen=True)
class ScenarioFieldSubstitutionSetV0:
    """One atomic, run-local set of direct scalar field replacements.

    This is intentionally a collection of the already narrow v0 member type,
    not a general premise language.  Runtime resolution canonicalizes trusted
    schema targets and rejects duplicate targets before either evaluator call.
    """

    substitutions: tuple[ScenarioFieldSubstitutionV0, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.substitutions, tuple) or len(self.substitutions) < 2:
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetV0.substitutions must be a tuple of at least two members"
            )
        if not all(isinstance(item, ScenarioFieldSubstitutionV0) for item in self.substitutions):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetV0.substitutions must contain ScenarioFieldSubstitutionV0"
            )
        premise_ids = tuple(item.premise_id for item in self.substitutions)
        if len(set(premise_ids)) != len(premise_ids):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetV0 premise_id values must be unique"
            )


@dataclass(frozen=True, repr=False)
class ScenarioScalarValueV0:
    """Canonical storage value used by an evaluated Scenario resolution."""

    tag: ScenarioScalarTag
    value: ScenarioScalarStorage

    def __post_init__(self) -> None:
        if self.tag not in _SCALAR_TAGS:
            raise ProtocolShapeError("ScenarioScalarValueV0.tag must be a scalar tup_v1 tag")
        if self.tag in {"int", "time"}:
            if isinstance(self.value, bool) or not isinstance(self.value, int):
                raise ProtocolShapeError(f"ScenarioScalarValueV0.value for {self.tag} must be int")
        elif self.tag == "bool":
            if not isinstance(self.value, bool):
                raise ProtocolShapeError("ScenarioScalarValueV0.value for bool must be bool")
        elif not isinstance(self.value, str):
            raise ProtocolShapeError(f"ScenarioScalarValueV0.value for {self.tag} must be str")
        try:
            raw_value: Any = self.value
            if self.tag == "bytes":
                assert isinstance(self.value, str)
                padding = "=" * (-len(self.value) % 4)
                raw_value = base64.urlsafe_b64decode((self.value + padding).encode("ascii"))
            normalized = claim_args_from_rest_terms([(self.tag, raw_value)])[0][1]
        except (ValueError, TypeError, UnicodeEncodeError, binascii.Error) as exc:
            raise ProtocolShapeError(
                f"ScenarioScalarValueV0.value is not canonical {self.tag} storage"
            ) from exc
        if normalized != self.value:
            raise ProtocolShapeError(
                f"ScenarioScalarValueV0.value is not canonical {self.tag} storage"
            )


@dataclass(frozen=True)
class ScenarioResultDiffV0:
    """Stable multiset summary of baseline versus effective Query rows."""

    baseline_row_count: int
    effective_row_count: int
    baseline_semantic_rows_digest: str
    effective_semantic_rows_digest: str
    result_changed: bool
    diff_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("baseline_row_count", "effective_row_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ProtocolShapeError(f"ScenarioResultDiffV0.{name} must be non-negative int")
        _sha256_token(self.baseline_semantic_rows_digest, "ScenarioResultDiffV0.baseline_semantic_rows_digest")
        _sha256_token(self.effective_semantic_rows_digest, "ScenarioResultDiffV0.effective_semantic_rows_digest")
        _require_bool(self.result_changed, field_name="ScenarioResultDiffV0.result_changed")
        if self.result_changed != (
            self.baseline_semantic_rows_digest != self.effective_semantic_rows_digest
        ):
            raise ProtocolShapeError(
                "ScenarioResultDiffV0.result_changed must match semantic-row digest equality"
            )
        object.__setattr__(
            self,
            "diff_digest",
            _token(
                "scenario_result_diff_v0",
                {
                    "baseline_row_count": self.baseline_row_count,
                    "effective_row_count": self.effective_row_count,
                    "baseline_semantic_rows_digest": self.baseline_semantic_rows_digest,
                    "effective_semantic_rows_digest": self.effective_semantic_rows_digest,
                    "result_changed": self.result_changed,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioResolutionV0:
    """Typed result metadata for one resolved Scenario field substitution.

    The relation digests identify run-local projected relations, not durable
    ledger snapshots.  ``effective_source_changed`` is always true because a
    synthetic hypothesis witness replaced the selected visible source even
    when the value itself is equal.
    """

    premise_id: str
    entity_ref: str
    field: FieldPath
    baseline_value: ScenarioScalarValueV0
    effective_value: ScenarioScalarValueV0
    base_view_digest: str
    baseline_relation_digest: str
    effective_relation_digest: str
    operation_digest: str = field(init=False)
    scenario_digest: str = field(init=False)
    semantic_value_changed: bool
    effective_source_changed: Literal[True]
    result_diff: ScenarioResultDiffV0 | None = None
    origin_kind: Literal["scenario_hypothesis_v0"] = "scenario_hypothesis_v0"

    def __post_init__(self) -> None:
        _require_non_empty_str(self.premise_id, field_name="ScenarioResolutionV0.premise_id")
        _require_non_empty_str(self.entity_ref, field_name="ScenarioResolutionV0.entity_ref")
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("ScenarioResolutionV0.field must be FieldPath")
        if not isinstance(self.baseline_value, ScenarioScalarValueV0):
            raise ProtocolShapeError("ScenarioResolutionV0.baseline_value must be ScenarioScalarValueV0")
        if not isinstance(self.effective_value, ScenarioScalarValueV0):
            raise ProtocolShapeError("ScenarioResolutionV0.effective_value must be ScenarioScalarValueV0")
        if self.baseline_value.tag != self.effective_value.tag:
            raise ProtocolShapeError("ScenarioResolutionV0 values must have the same scalar tag")
        for name in (
            "base_view_digest",
            "baseline_relation_digest",
            "effective_relation_digest",
        ):
            _sha256_token(getattr(self, name), f"ScenarioResolutionV0.{name}")
        _require_bool(self.semantic_value_changed, field_name="ScenarioResolutionV0.semantic_value_changed")
        if self.semantic_value_changed != (self.baseline_value != self.effective_value):
            raise ProtocolShapeError(
                "ScenarioResolutionV0.semantic_value_changed must match value equality"
            )
        if self.effective_source_changed is not True:
            raise ProtocolShapeError("ScenarioResolutionV0.effective_source_changed must be True")
        if self.result_diff is not None and not isinstance(self.result_diff, ScenarioResultDiffV0):
            raise ProtocolShapeError("ScenarioResolutionV0.result_diff must be ScenarioResultDiffV0 or None")
        if self.origin_kind != "scenario_hypothesis_v0":
            raise ProtocolShapeError("ScenarioResolutionV0.origin_kind must be scenario_hypothesis_v0")
        operation_digest = _token(
            "scenario_field_substitution_operation_v0",
            {
                "premise_id": self.premise_id,
                "entity_ref": self.entity_ref,
                "field": (self.field.entity_type, self.field.field_name),
                "baseline_value": (self.baseline_value.tag, self.baseline_value.value),
                "effective_value": (self.effective_value.tag, self.effective_value.value),
                "base_view_digest": self.base_view_digest,
                "baseline_relation_digest": self.baseline_relation_digest,
                "effective_relation_digest": self.effective_relation_digest,
                "semantic_value_changed": self.semantic_value_changed,
                "effective_source_changed": self.effective_source_changed,
                "origin_kind": self.origin_kind,
            },
        )
        object.__setattr__(self, "operation_digest", operation_digest)
        object.__setattr__(
            self,
            "scenario_digest",
            _token(
                "scenario_field_substitution_v0",
                {
                    "operation_digest": operation_digest,
                    "result_diff_digest": None if self.result_diff is None else self.result_diff.diff_digest,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioFieldSubstitutionOperationV0:
    """One trusted-schema-resolved member of a Scenario substitution set.

    ``operation_digest`` commits only this member's canonical target and value
    transition.  It deliberately does not include the final relation digest,
    avoiding a cyclic set-resolution identity.
    """

    premise_id: str
    entity_ref: str
    field: FieldPath
    baseline_value: ScenarioScalarValueV0
    effective_value: ScenarioScalarValueV0
    semantic_value_changed: bool
    effective_source_changed: Literal[True]
    operation_digest: str = field(init=False)
    origin_kind: Literal["scenario_hypothesis_set_v0"] = "scenario_hypothesis_set_v0"

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.premise_id, field_name="ScenarioFieldSubstitutionOperationV0.premise_id"
        )
        _require_non_empty_str(
            self.entity_ref, field_name="ScenarioFieldSubstitutionOperationV0.entity_ref"
        )
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("ScenarioFieldSubstitutionOperationV0.field must be FieldPath")
        if not isinstance(self.baseline_value, ScenarioScalarValueV0):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionOperationV0.baseline_value must be ScenarioScalarValueV0"
            )
        if not isinstance(self.effective_value, ScenarioScalarValueV0):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionOperationV0.effective_value must be ScenarioScalarValueV0"
            )
        if self.baseline_value.tag != self.effective_value.tag:
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionOperationV0 values must have the same scalar tag"
            )
        _require_bool(
            self.semantic_value_changed,
            field_name="ScenarioFieldSubstitutionOperationV0.semantic_value_changed",
        )
        if self.semantic_value_changed != (self.baseline_value != self.effective_value):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionOperationV0.semantic_value_changed must match value equality"
            )
        if self.effective_source_changed is not True:
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionOperationV0.effective_source_changed must be True"
            )
        if self.origin_kind != "scenario_hypothesis_set_v0":
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionOperationV0.origin_kind must be scenario_hypothesis_set_v0"
            )
        object.__setattr__(
            self,
            "operation_digest",
            _token(
                "scenario_field_substitution_set_operation_v0",
                {
                    "premise_id": self.premise_id,
                    "entity_ref": self.entity_ref,
                    "field": (self.field.entity_type, self.field.field_name),
                    "baseline_value": (self.baseline_value.tag, self.baseline_value.value),
                    "effective_value": (self.effective_value.tag, self.effective_value.value),
                    "semantic_value_changed": self.semantic_value_changed,
                    "effective_source_changed": self.effective_source_changed,
                    "origin_kind": self.origin_kind,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioFieldSubstitutionSetResolutionV0:
    """Typed result metadata for one atomic direct-field substitution set.

    This metadata is integrity-sealed, not authenticated.  Its relation digests
    identify run-local evaluator inputs, never durable snapshots or evidence.
    """

    operations: tuple[ScenarioFieldSubstitutionOperationV0, ...]
    base_view_digest: str
    baseline_relation_digest: str
    effective_relation_digest: str
    result_diff: ScenarioResultDiffV0 | None = None
    scenario_digest: str = field(init=False)
    origin_kind: Literal["scenario_hypothesis_set_v0"] = "scenario_hypothesis_set_v0"

    def __post_init__(self) -> None:
        if not isinstance(self.operations, tuple) or len(self.operations) < 2:
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0.operations must be a tuple of at least two members"
            )
        if not all(isinstance(item, ScenarioFieldSubstitutionOperationV0) for item in self.operations):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0.operations must contain ScenarioFieldSubstitutionOperationV0"
            )
        premise_ids = tuple(item.premise_id for item in self.operations)
        if len(set(premise_ids)) != len(premise_ids):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0 operations must have unique premise ids"
            )
        canonical_keys = tuple((item.entity_ref, item.field.entity_type, item.field.field_name) for item in self.operations)
        if canonical_keys != tuple(sorted(canonical_keys)):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0.operations must use canonical target order"
            )
        if len(set(canonical_keys)) != len(canonical_keys):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0 operations must have unique canonical targets"
            )
        for name in (
            "base_view_digest",
            "baseline_relation_digest",
            "effective_relation_digest",
        ):
            _sha256_token(
                getattr(self, name), f"ScenarioFieldSubstitutionSetResolutionV0.{name}"
            )
        if self.result_diff is not None and not isinstance(self.result_diff, ScenarioResultDiffV0):
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0.result_diff must be ScenarioResultDiffV0 or None"
            )
        if self.origin_kind != "scenario_hypothesis_set_v0":
            raise ProtocolShapeError(
                "ScenarioFieldSubstitutionSetResolutionV0.origin_kind must be scenario_hypothesis_set_v0"
            )
        object.__setattr__(
            self,
            "scenario_digest",
            _token(
                "scenario_field_substitution_set_v0",
                {
                    "operation_digests": tuple(item.operation_digest for item in self.operations),
                    "base_view_digest": self.base_view_digest,
                    "baseline_relation_digest": self.baseline_relation_digest,
                    "effective_relation_digest": self.effective_relation_digest,
                    "result_diff_digest": None if self.result_diff is None else self.result_diff.diff_digest,
                    "origin_kind": self.origin_kind,
                },
            ),
        )


def _sha256_token(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be a sha256 token")
    suffix = value[len("sha256:") :]
    if len(suffix) != 64 or any(char not in "0123456789abcdef" for char in suffix):
        raise ProtocolShapeError(f"{field_name} must be a sha256 token")


def _token(label: str, payload: object) -> str:
    try:
        encoded = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # pragma: no cover - all construction inputs are checked above
        raise ProtocolShapeError("Scenario protocol payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(encoded)}"


__all__ = [
    "ScenarioFieldSubstitutionV0",
    "ScenarioFieldSubstitutionSetV0",
    "ScenarioFieldSubstitutionOperationV0",
    "ScenarioFieldSubstitutionSetResolutionV0",
    "ScenarioInputValue",
    "ScenarioResolutionV0",
    "ScenarioResultDiffV0",
    "ScenarioScalarStorage",
    "ScenarioScalarTag",
    "ScenarioScalarValueV0",
]
