"""Portable, query-local Scenario v1 protocol values.

This is deliberately *not* a second assertion ledger or a generic negation
language.  A :class:`ScenarioSpecV1` is resolved against one already selected
projected relation.  ``without_*`` operations can only create an exact,
query-local closure target in the resulting ``EffectiveWorldV1``.  They never
create a persistent negative fact, change Rule/Policy semantics, or imply
global negation-as-failure.

Evidence admissibility is intentionally represented by ``EvidenceScopeV1``
as a separate input concern.  Ignoring a witness means ``EXCLUDED``; it does
not manufacture the ``EMPTY_BY_SCENARIO`` closure carried by ``without_*``.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms

from .common import ProtocolShapeError, _require_non_empty_str
from .schema_runtime import EntityRef, FieldPath

ScenarioValueTagV1: TypeAlias = Literal[
    "string",
    "int",
    "float64",
    "bool",
    "bytes",
    "time",
    "uuid",
    "entity_ref",
]
ScenarioValueStorageV1: TypeAlias = str | int | bool
ScenarioOperationKindV1: TypeAlias = Literal[
    "set_effective_value",
    "ensure_member",
    "set_exact_members",
    "without_field",
    "without_value",
    "create_ephemeral_entity",
    "ensure_relation",
    "without_relation",
    "without_entity",
    "without_assertion",
]
ClosureTargetKindV1: TypeAlias = Literal[
    "field", "member", "exact_set", "relation", "entity", "assertion"
]

_VALUE_TAGS = frozenset({"string", "int", "float64", "bool", "bytes", "time", "uuid", "entity_ref"})
_OPERATION_KINDS = frozenset(
    {
        "set_effective_value",
        "ensure_member",
        "set_exact_members",
        "without_field",
        "without_value",
        "create_ephemeral_entity",
        "ensure_relation",
        "without_relation",
        "without_entity",
        "without_assertion",
    }
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
    except (TypeError, ValueError) as exc:  # pragma: no cover - guarded by DTOs
        raise ProtocolShapeError("Scenario v1 payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(encoded)}"


def _entity_payload(entity: EntityRef) -> dict[str, object]:
    return {"entity_type": entity.entity_type, "identity": dict(entity.identity)}


def _canonical_strings(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[str, ...]")
    for idx, value in enumerate(values):
        _require_non_empty_str(value, field_name=f"{field_name}[{idx}]")
    return tuple(sorted(set(values)))


def _raw_value(tag: ScenarioValueTagV1, value: ScenarioValueStorageV1) -> Any:
    if tag == "bytes":
        if not isinstance(value, str):
            raise ProtocolShapeError("ScenarioValueV1 bytes storage must be string")
        try:
            padding = "=" * (-len(value) % 4)
            return base64.urlsafe_b64decode((value + padding).encode("ascii"))
        except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
            raise ProtocolShapeError("ScenarioValueV1 bytes storage is invalid base64url") from exc
    return value


@dataclass(frozen=True, repr=False)
class ScenarioValueV1:
    """A canonical tup_v1 value stored without caller-object identity.

    ``entity_ref`` uses the same canonical string storage as a projected
    relation.  The resolver verifies that its tag agrees with the active
    schema before it permits an operation to use it.
    """

    tag: ScenarioValueTagV1
    value: ScenarioValueStorageV1

    def __post_init__(self) -> None:
        if self.tag not in _VALUE_TAGS:
            raise ProtocolShapeError("ScenarioValueV1.tag must be a supported tup_v1 tag")
        if self.tag in {"int", "time"}:
            if isinstance(self.value, bool) or not isinstance(self.value, int):
                raise ProtocolShapeError(f"ScenarioValueV1.value for {self.tag} must be int")
        elif self.tag == "bool":
            if not isinstance(self.value, bool):
                raise ProtocolShapeError("ScenarioValueV1.value for bool must be bool")
        elif not isinstance(self.value, str):
            raise ProtocolShapeError(f"ScenarioValueV1.value for {self.tag} must be str")
        try:
            normalized = claim_args_from_rest_terms([(self.tag, _raw_value(self.tag, self.value))])[
                0
            ][1]
        except (ValueError, TypeError, UnicodeEncodeError, binascii.Error) as exc:
            raise ProtocolShapeError("ScenarioValueV1 storage is not canonical") from exc
        if normalized != self.value:
            raise ProtocolShapeError("ScenarioValueV1 storage is not canonical")

    @classmethod
    def from_raw(cls, tag: ScenarioValueTagV1, value: Any) -> "ScenarioValueV1":
        """Normalize one Python value into canonical Scenario storage.

        Args:
            tag: Canonical scalar/entity value tag.
            value: Python value to normalize.

        Returns:
            A detached canonical Scenario value.
        """
        if tag not in _VALUE_TAGS:
            raise ProtocolShapeError("ScenarioValueV1.tag must be a supported tup_v1 tag")
        try:
            normalized = claim_args_from_rest_terms([(tag, value)])[0][1]
        except (ValueError, TypeError, UnicodeEncodeError, binascii.Error) as exc:
            raise ProtocolShapeError("ScenarioValueV1 raw value is invalid") from exc
        return cls(tag=tag, value=normalized)

    def to_raw(self) -> Any:
        """Return the canonical Python representation of this stored value."""
        return _raw_value(self.tag, self.value)

    @property
    def value_digest(self) -> str:
        """Return the digest of the canonical tag/value pair."""
        return _token("scenario_value_v1", {"tag": self.tag, "value": self.value})


@dataclass(frozen=True)
class _ScenarioFieldOperationBaseV1:
    premise_id: str
    entity: EntityRef
    field: FieldPath
    origin_refs: tuple[str, ...] = dc_field(default=(), kw_only=True)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.premise_id, field_name=f"{type(self).__name__}.premise_id")
        if not isinstance(self.entity, EntityRef):
            raise ProtocolShapeError(f"{type(self).__name__}.entity must be EntityRef")
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError(f"{type(self).__name__}.field must be FieldPath")
        if self.entity.entity_type != self.field.entity_type:
            raise ProtocolShapeError(
                f"{type(self).__name__}.entity and field must share entity_type"
            )
        object.__setattr__(
            self,
            "origin_refs",
            _canonical_strings(self.origin_refs, field_name=f"{type(self).__name__}.origin_refs"),
        )

    def _base_payload(self) -> dict[str, object]:
        return {
            "premise_id": self.premise_id,
            "entity": _entity_payload(self.entity),
            "field": {"entity_type": self.field.entity_type, "field_name": self.field.field_name},
            "origin_refs": self.origin_refs,
        }


@dataclass(frozen=True)
class ScenarioSetEffectiveValueV1(_ScenarioFieldOperationBaseV1):
    """Replace one single-valued field in the run-local effective world."""

    value: ScenarioValueV1 = dc_field(default_factory=lambda: ScenarioValueV1("string", ""))
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.value, ScenarioValueV1):
            raise ProtocolShapeError("ScenarioSetEffectiveValueV1.value must be ScenarioValueV1")
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_set_effective_value_v1",
                {**self._base_payload(), "value": (self.value.tag, self.value.value)},
            ),
        )


@dataclass(frozen=True)
class ScenarioEnsureMemberV1(_ScenarioFieldOperationBaseV1):
    """Ensure one value exists in a run-local multi-valued field."""

    value: ScenarioValueV1 = dc_field(default_factory=lambda: ScenarioValueV1("string", ""))
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.value, ScenarioValueV1):
            raise ProtocolShapeError("ScenarioEnsureMemberV1.value must be ScenarioValueV1")
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_ensure_member_v1",
                {**self._base_payload(), "value": (self.value.tag, self.value.value)},
            ),
        )


@dataclass(frozen=True)
class ScenarioSetExactMembersV1(_ScenarioFieldOperationBaseV1):
    """Replace a run-local multi-valued field with an exact member set."""

    values: tuple[ScenarioValueV1, ...] = ()
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.values, tuple) or not all(
            isinstance(value, ScenarioValueV1) for value in self.values
        ):
            raise ProtocolShapeError(
                "ScenarioSetExactMembersV1.values must be tuple[ScenarioValueV1, ...]"
            )
        canonical = tuple(sorted(self.values, key=lambda value: (value.tag, str(value.value))))
        if len(set(canonical)) != len(canonical):
            raise ProtocolShapeError("ScenarioSetExactMembersV1.values must be unique")
        object.__setattr__(self, "values", canonical)
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_set_exact_members_v1",
                {
                    **self._base_payload(),
                    "values": tuple((value.tag, value.value) for value in canonical),
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioWithoutFieldV1(_ScenarioFieldOperationBaseV1):
    """Remove every effective value for one entity field."""

    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self, "statement_digest", _token("scenario_without_field_v1", self._base_payload())
        )


@dataclass(frozen=True)
class ScenarioWithoutValueV1(_ScenarioFieldOperationBaseV1):
    """Remove one effective value from a multi-valued field."""

    value: ScenarioValueV1 = dc_field(default_factory=lambda: ScenarioValueV1("string", ""))
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.value, ScenarioValueV1):
            raise ProtocolShapeError("ScenarioWithoutValueV1.value must be ScenarioValueV1")
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_without_value_v1",
                {**self._base_payload(), "value": (self.value.tag, self.value.value)},
            ),
        )


@dataclass(frozen=True)
class ScenarioEnsureRelationV1:
    """Ensure one ground tuple in a schema-declared extensional relation.

    This is intentionally not an arbitrary external function call.  The
    resolver accepts only a supplied, schema-declared non-derived predicate.
    """

    premise_id: str
    predicate_id: str
    values: tuple[ScenarioValueV1, ...]
    origin_refs: tuple[str, ...] = ()
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.premise_id, field_name="ScenarioEnsureRelationV1.premise_id")
        _require_non_empty_str(
            self.predicate_id, field_name="ScenarioEnsureRelationV1.predicate_id"
        )
        if (
            not isinstance(self.values, tuple)
            or not self.values
            or not all(isinstance(value, ScenarioValueV1) for value in self.values)
        ):
            raise ProtocolShapeError(
                "ScenarioEnsureRelationV1.values must be non-empty ScenarioValueV1 tuple"
            )
        object.__setattr__(
            self,
            "origin_refs",
            _canonical_strings(self.origin_refs, field_name="ScenarioEnsureRelationV1.origin_refs"),
        )
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_ensure_relation_v1",
                {
                    "premise_id": self.premise_id,
                    "predicate_id": self.predicate_id,
                    "values": tuple((value.tag, value.value) for value in self.values),
                    "origin_refs": self.origin_refs,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioWithoutRelationV1:
    """Remove effective facts for one relation predicate."""

    premise_id: str
    predicate_id: str
    origin_refs: tuple[str, ...] = ()
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.premise_id, field_name="ScenarioWithoutRelationV1.premise_id")
        _require_non_empty_str(
            self.predicate_id, field_name="ScenarioWithoutRelationV1.predicate_id"
        )
        object.__setattr__(
            self,
            "origin_refs",
            _canonical_strings(
                self.origin_refs, field_name="ScenarioWithoutRelationV1.origin_refs"
            ),
        )
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_without_relation_v1",
                {
                    "premise_id": self.premise_id,
                    "predicate_id": self.predicate_id,
                    "origin_refs": self.origin_refs,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioWithoutEntityV1:
    """Remove one entity and its effective dependent facts."""

    premise_id: str
    entity: EntityRef
    origin_refs: tuple[str, ...] = ()
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.premise_id, field_name="ScenarioWithoutEntityV1.premise_id")
        if not isinstance(self.entity, EntityRef):
            raise ProtocolShapeError("ScenarioWithoutEntityV1.entity must be EntityRef")
        object.__setattr__(
            self,
            "origin_refs",
            _canonical_strings(self.origin_refs, field_name="ScenarioWithoutEntityV1.origin_refs"),
        )
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_without_entity_v1",
                {
                    "premise_id": self.premise_id,
                    "entity": _entity_payload(self.entity),
                    "origin_refs": self.origin_refs,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioWithoutAssertionV1:
    """SDK/debug-only removal of one exact admitted witness.

    This is deliberately distinct from ``EvidenceScopeV1.ignore``: its effect
    is an explicit Scenario-local effective-world operation with a closure for
    exactly that captured assertion tuple.  It is not intended as an Agent
    public primitive, because a caller must already hold the opaque witness id.
    """

    premise_id: str
    assertion_id: str
    origin_refs: tuple[str, ...] = ()
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.premise_id, field_name="ScenarioWithoutAssertionV1.premise_id")
        _require_non_empty_str(
            self.assertion_id,
            field_name="ScenarioWithoutAssertionV1.assertion_id",
        )
        object.__setattr__(
            self,
            "origin_refs",
            _canonical_strings(
                self.origin_refs,
                field_name="ScenarioWithoutAssertionV1.origin_refs",
            ),
        )
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_without_assertion_v1",
                {
                    "premise_id": self.premise_id,
                    "assertion_id": self.assertion_id,
                    "origin_refs": self.origin_refs,
                },
            ),
        )


@dataclass(frozen=True)
class ScenarioCreateEphemeralEntityV1:
    """Create one run-local entity that is never written to the ledger."""

    premise_id: str
    entity: EntityRef
    origin_refs: tuple[str, ...] = ()
    statement_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.premise_id, field_name="ScenarioCreateEphemeralEntityV1.premise_id"
        )
        if not isinstance(self.entity, EntityRef):
            raise ProtocolShapeError("ScenarioCreateEphemeralEntityV1.entity must be EntityRef")
        object.__setattr__(
            self,
            "origin_refs",
            _canonical_strings(
                self.origin_refs, field_name="ScenarioCreateEphemeralEntityV1.origin_refs"
            ),
        )
        object.__setattr__(
            self,
            "statement_digest",
            _token(
                "scenario_create_ephemeral_entity_v1",
                {
                    "premise_id": self.premise_id,
                    "entity": _entity_payload(self.entity),
                    "origin_refs": self.origin_refs,
                },
            ),
        )


ScenarioOperationV1: TypeAlias = (
    ScenarioSetEffectiveValueV1
    | ScenarioEnsureMemberV1
    | ScenarioSetExactMembersV1
    | ScenarioWithoutFieldV1
    | ScenarioWithoutValueV1
    | ScenarioCreateEphemeralEntityV1
    | ScenarioEnsureRelationV1
    | ScenarioWithoutRelationV1
    | ScenarioWithoutEntityV1
    | ScenarioWithoutAssertionV1
)


@dataclass(frozen=True)
class ScenarioSpecV1:
    """An unordered, immutable batch of ground scenario statements.

    The constructor canonicalizes statement order.  It intentionally does not
    resolve a target predicate or attach a baseline relation; that work belongs
    to the trusted runtime so an agent cannot turn an unresolved input into a
    false supported result.
    """

    operations: tuple[ScenarioOperationV1, ...]
    spec_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.operations, tuple) or not all(
            isinstance(
                item,
                (
                    ScenarioSetEffectiveValueV1,
                    ScenarioEnsureMemberV1,
                    ScenarioSetExactMembersV1,
                    ScenarioWithoutFieldV1,
                    ScenarioWithoutValueV1,
                    ScenarioCreateEphemeralEntityV1,
                    ScenarioEnsureRelationV1,
                    ScenarioWithoutRelationV1,
                    ScenarioWithoutEntityV1,
                    ScenarioWithoutAssertionV1,
                ),
            )
            for item in self.operations
        ):
            raise ProtocolShapeError("ScenarioSpecV1.operations must be ScenarioOperationV1 tuple")
        premise_ids = tuple(item.premise_id for item in self.operations)
        if len(set(premise_ids)) != len(premise_ids):
            raise ProtocolShapeError("ScenarioSpecV1 premise_id values must be unique")
        canonical = tuple(sorted(self.operations, key=lambda item: item.statement_digest))
        object.__setattr__(self, "operations", canonical)
        object.__setattr__(
            self,
            "spec_digest",
            _token(
                "scenario_spec_v1",
                {"operation_digests": tuple(item.statement_digest for item in canonical)},
            ),
        )


@dataclass(frozen=True)
class EvidenceScopeV1:
    """A narrow admission filter, never a closure or absence declaration."""

    ignored_assertion_ids: tuple[str, ...] = ()
    scope_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        canonical = _canonical_strings(
            self.ignored_assertion_ids,
            field_name="EvidenceScopeV1.ignored_assertion_ids",
        )
        object.__setattr__(self, "ignored_assertion_ids", canonical)
        object.__setattr__(
            self,
            "scope_digest",
            _token("evidence_scope_v1", {"ignored_assertion_ids": canonical}),
        )


@dataclass(frozen=True)
class ExactLocalClosureTargetV1:
    """One exact Scenario-local absence target, not a global negative fact."""

    kind: ClosureTargetKindV1
    entity_ref: str | None
    predicate_id: str | None
    value: ScenarioValueV1 | None = None
    assertion_id: str | None = None
    members: tuple[ScenarioValueV1, ...] = ()
    target_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in {"field", "member", "exact_set", "relation", "entity", "assertion"}:
            raise ProtocolShapeError("ExactLocalClosureTargetV1.kind is unsupported")
        if self.kind in {"field", "member", "exact_set", "entity"}:
            _require_non_empty_str(
                self.entity_ref, field_name="ExactLocalClosureTargetV1.entity_ref"
            )
        elif self.entity_ref is not None:
            raise ProtocolShapeError("relation/assertion closure target must not carry entity_ref")
        if self.kind in {"field", "member", "exact_set", "relation", "assertion"}:
            _require_non_empty_str(
                self.predicate_id, field_name="ExactLocalClosureTargetV1.predicate_id"
            )
        elif self.predicate_id is not None:
            raise ProtocolShapeError("entity closure target must not carry predicate_id")
        if (
            self.kind in {"field", "exact_set", "relation", "entity", "assertion"}
            and self.value is not None
        ):
            raise ProtocolShapeError("non-member closure target must not carry value")
        if self.kind == "member" and not isinstance(self.value, ScenarioValueV1):
            raise ProtocolShapeError("member closure target must carry ScenarioValueV1")
        if not isinstance(self.members, tuple) or not all(
            isinstance(member, ScenarioValueV1) for member in self.members
        ):
            raise ProtocolShapeError("closure target members must be ScenarioValueV1 tuple")
        canonical_members = tuple(sorted(self.members, key=lambda member: member.value_digest))
        if len({member.value_digest for member in canonical_members}) != len(canonical_members):
            raise ProtocolShapeError("closure target members must be unique")
        if self.kind == "exact_set":
            # An empty tuple is a meaningful exact empty set.  It is distinct
            # from WITHOUT_FIELD because it records the SET_EXACT operation.
            object.__setattr__(self, "members", canonical_members)
        elif canonical_members:
            raise ProtocolShapeError("only exact_set closure target may carry members")
        if self.kind == "assertion":
            _require_non_empty_str(
                self.assertion_id,
                field_name="ExactLocalClosureTargetV1.assertion_id",
            )
        elif self.assertion_id is not None:
            raise ProtocolShapeError("only assertion closure target may carry assertion_id")
        object.__setattr__(
            self,
            "target_digest",
            _token(
                "scenario_exact_local_closure_target_v1",
                {
                    "kind": self.kind,
                    "entity_ref": self.entity_ref,
                    "predicate_id": self.predicate_id,
                    "value": None if self.value is None else (self.value.tag, self.value.value),
                    "assertion_id": self.assertion_id,
                    "members": tuple((member.tag, member.value) for member in canonical_members),
                },
            ),
        )


@dataclass(frozen=True)
class ClosureScopeV1:
    """Exact local absence targets produced by scenario resolution.

    Empty ``targets`` is open-world.  Non-empty targets say only that the
    sealed effective relation is complete for those specific field/member
    targets.  They do not authorize generic NotAtom, policy-level NAF, or an
    inference about any other relation row.
    """

    targets: tuple[ExactLocalClosureTargetV1, ...] = ()
    mode: Literal["open", "exact_local"] = dc_field(init=False)
    closure_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.targets, tuple) or not all(
            isinstance(target, ExactLocalClosureTargetV1) for target in self.targets
        ):
            raise ProtocolShapeError(
                "ClosureScopeV1.targets must be ExactLocalClosureTargetV1 tuple"
            )
        canonical = tuple(sorted(self.targets, key=lambda target: target.target_digest))
        if len({target.target_digest for target in canonical}) != len(canonical):
            raise ProtocolShapeError("ClosureScopeV1.targets must be unique")
        object.__setattr__(self, "targets", canonical)
        object.__setattr__(self, "mode", "exact_local" if canonical else "open")
        object.__setattr__(
            self,
            "closure_digest",
            _token(
                "scenario_closure_scope_v1",
                {"targets": tuple(target.target_digest for target in canonical)},
            ),
        )


@dataclass(frozen=True)
class EffectiveWorldFactV1:
    predicate_id: str
    witness_id: str
    values: tuple[ScenarioValueV1, ...]
    source_kind: Literal["baseline", "scenario"]
    fact_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.predicate_id, field_name="EffectiveWorldFactV1.predicate_id")
        _require_non_empty_str(self.witness_id, field_name="EffectiveWorldFactV1.witness_id")
        if (
            not isinstance(self.values, tuple)
            or not self.values
            or not all(isinstance(value, ScenarioValueV1) for value in self.values)
        ):
            raise ProtocolShapeError(
                "EffectiveWorldFactV1.values must be non-empty ScenarioValueV1 tuple"
            )
        if self.source_kind not in {"baseline", "scenario"}:
            raise ProtocolShapeError(
                "EffectiveWorldFactV1.source_kind must be baseline or scenario"
            )
        object.__setattr__(
            self,
            "fact_digest",
            _token(
                "effective_world_fact_v1",
                {
                    "predicate_id": self.predicate_id,
                    "witness_id": self.witness_id,
                    "values": tuple((value.tag, value.value) for value in self.values),
                    "source_kind": self.source_kind,
                },
            ),
        )


@dataclass(frozen=True)
class ResolvedScenarioOperationV1:
    """Canonical operation after schema, conflict, and baseline resolution."""

    kind: ScenarioOperationKindV1
    entity_ref: str | None
    entity_type: str | None
    predicate_id: str | None
    field: FieldPath | None
    assertion_id: str | None = None
    values: tuple[ScenarioValueV1, ...] = ()
    premise_ids: tuple[str, ...] = ()
    origin_refs: tuple[str, ...] = ()
    masked_witness_ids: tuple[str, ...] = ()
    synthetic_witness_ids: tuple[str, ...] = ()
    operation_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in _OPERATION_KINDS:
            raise ProtocolShapeError("ResolvedScenarioOperationV1.kind is unsupported")
        is_create = self.kind == "create_ephemeral_entity"
        is_entity_remove = self.kind == "without_entity"
        is_assertion_remove = self.kind == "without_assertion"
        is_relation = self.kind in {"ensure_relation", "without_relation"}
        if is_relation or is_assertion_remove:
            if self.entity_ref is not None or self.entity_type is not None:
                raise ProtocolShapeError(
                    "relation/assertion operation must not carry entity target"
                )
        else:
            _require_non_empty_str(
                self.entity_ref, field_name="ResolvedScenarioOperationV1.entity_ref"
            )
            _require_non_empty_str(
                self.entity_type, field_name="ResolvedScenarioOperationV1.entity_type"
            )
        if is_create or is_entity_remove:
            if self.predicate_id is not None or self.field is not None or self.values:
                raise ProtocolShapeError(
                    "entity-level operation must not carry field/predicate/value"
                )
            if self.assertion_id is not None:
                raise ProtocolShapeError("entity-level operation must not carry assertion id")
        elif is_assertion_remove:
            _require_non_empty_str(
                self.predicate_id, field_name="ResolvedScenarioOperationV1.predicate_id"
            )
            _require_non_empty_str(
                self.assertion_id, field_name="ResolvedScenarioOperationV1.assertion_id"
            )
            if self.field is not None or not self.values:
                raise ProtocolShapeError("assertion removal must carry its resolved tuple only")
        elif is_relation:
            _require_non_empty_str(
                self.predicate_id, field_name="ResolvedScenarioOperationV1.predicate_id"
            )
            if self.field is not None:
                raise ProtocolShapeError("relation operation must not carry FieldPath")
            if self.assertion_id is not None:
                raise ProtocolShapeError("relation operation must not carry assertion id")
            if self.kind == "ensure_relation" and not self.values:
                raise ProtocolShapeError("ensure_relation must carry values")
            if self.kind == "without_relation" and self.values:
                raise ProtocolShapeError("without_relation must not carry values")
        else:
            _require_non_empty_str(
                self.predicate_id, field_name="ResolvedScenarioOperationV1.predicate_id"
            )
            if not isinstance(self.field, FieldPath):
                raise ProtocolShapeError("field operation must carry FieldPath")
            if self.field.entity_type != self.entity_type:
                raise ProtocolShapeError("field operation entity_type must match FieldPath")
            if self.assertion_id is not None:
                raise ProtocolShapeError("field operation must not carry assertion id")
        if not isinstance(self.values, tuple) or not all(
            isinstance(value, ScenarioValueV1) for value in self.values
        ):
            raise ProtocolShapeError(
                "ResolvedScenarioOperationV1.values must be ScenarioValueV1 tuple"
            )
        for name in ("premise_ids", "origin_refs", "masked_witness_ids", "synthetic_witness_ids"):
            canonical = _canonical_strings(
                getattr(self, name), field_name=f"ResolvedScenarioOperationV1.{name}"
            )
            if name == "premise_ids" and not canonical:
                raise ProtocolShapeError(
                    "ResolvedScenarioOperationV1.premise_ids must be non-empty"
                )
            object.__setattr__(self, name, canonical)
        if is_assertion_remove:
            if self.masked_witness_ids != (self.assertion_id,):
                raise ProtocolShapeError(
                    "assertion removal must mask exactly its resolved assertion id"
                )
            if self.synthetic_witness_ids:
                raise ProtocolShapeError("assertion removal must not create synthetic witnesses")
        object.__setattr__(
            self,
            "operation_digest",
            _token(
                "resolved_scenario_operation_v1",
                {
                    "kind": self.kind,
                    "entity_ref": self.entity_ref,
                    "entity_type": self.entity_type,
                    "predicate_id": self.predicate_id,
                    "field": None
                    if self.field is None
                    else (self.field.entity_type, self.field.field_name),
                    "assertion_id": self.assertion_id,
                    "values": tuple((value.tag, value.value) for value in self.values),
                    "premise_ids": self.premise_ids,
                    "origin_refs": self.origin_refs,
                    "masked_witness_ids": self.masked_witness_ids,
                    "synthetic_witness_ids": self.synthetic_witness_ids,
                },
            ),
        )


@dataclass(frozen=True)
class EffectiveWorldV1:
    """An immutable, serializable relation usable by a future engine adapter."""

    schema_digest: str
    base_view_digest: str
    admissibility_digest: str
    dependency_predicate_ids: tuple[str, ...]
    facts: tuple[EffectiveWorldFactV1, ...]
    operations: tuple[ResolvedScenarioOperationV1, ...] = ()
    closure: ClosureScopeV1 = dc_field(default_factory=ClosureScopeV1)
    relation_digest: str = dc_field(init=False)
    world_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        for name in ("schema_digest", "base_view_digest", "admissibility_digest"):
            _sha256_token(getattr(self, name), f"EffectiveWorldV1.{name}")
        predicates = _canonical_strings(
            self.dependency_predicate_ids,
            field_name="EffectiveWorldV1.dependency_predicate_ids",
        )
        if not predicates:
            raise ProtocolShapeError("EffectiveWorldV1.dependency_predicate_ids must be non-empty")
        if not isinstance(self.facts, tuple) or not all(
            isinstance(fact, EffectiveWorldFactV1) for fact in self.facts
        ):
            raise ProtocolShapeError("EffectiveWorldV1.facts must be EffectiveWorldFactV1 tuple")
        if {fact.predicate_id for fact in self.facts} - set(predicates):
            raise ProtocolShapeError("EffectiveWorldV1.facts must belong to dependency predicates")
        witness_ids = tuple(fact.witness_id for fact in self.facts)
        if len(set(witness_ids)) != len(witness_ids):
            raise ProtocolShapeError("EffectiveWorldV1.fact witness ids must be unique")
        if not isinstance(self.operations, tuple) or not all(
            isinstance(operation, ResolvedScenarioOperationV1) for operation in self.operations
        ):
            raise ProtocolShapeError(
                "EffectiveWorldV1.operations must be ResolvedScenarioOperationV1 tuple"
            )
        if not isinstance(self.closure, ClosureScopeV1):
            raise ProtocolShapeError("EffectiveWorldV1.closure must be ClosureScopeV1")
        facts = tuple(sorted(self.facts, key=lambda fact: fact.fact_digest))
        operations = tuple(
            sorted(self.operations, key=lambda operation: operation.operation_digest)
        )
        object.__setattr__(self, "dependency_predicate_ids", predicates)
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "operations", operations)
        relation_digest = _token(
            "effective_world_relation_v1",
            {"facts": tuple(fact.fact_digest for fact in facts)},
        )
        object.__setattr__(self, "relation_digest", relation_digest)
        object.__setattr__(
            self,
            "world_digest",
            _token(
                "effective_world_v1",
                {
                    "schema_digest": self.schema_digest,
                    "base_view_digest": self.base_view_digest,
                    "admissibility_digest": self.admissibility_digest,
                    "dependency_predicate_ids": predicates,
                    "relation_digest": relation_digest,
                    "operation_digests": tuple(
                        operation.operation_digest for operation in operations
                    ),
                    "closure_digest": self.closure.closure_digest,
                },
            ),
        )


@dataclass(frozen=True)
class ResolvedScenarioV1:
    """Trusted resolver output linking the baseline and the sealed effective world."""

    spec: ScenarioSpecV1
    baseline_world: EffectiveWorldV1
    effective_world: EffectiveWorldV1
    resolution_evidence_digest: str = dc_field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.spec, ScenarioSpecV1):
            raise ProtocolShapeError("ResolvedScenarioV1.spec must be ScenarioSpecV1")
        if not isinstance(self.baseline_world, EffectiveWorldV1):
            raise ProtocolShapeError("ResolvedScenarioV1.baseline_world must be EffectiveWorldV1")
        if not isinstance(self.effective_world, EffectiveWorldV1):
            raise ProtocolShapeError("ResolvedScenarioV1.effective_world must be EffectiveWorldV1")
        if self.baseline_world.schema_digest != self.effective_world.schema_digest:
            raise ProtocolShapeError("ResolvedScenarioV1 worlds must have the same schema digest")
        if self.baseline_world.base_view_digest != self.effective_world.base_view_digest:
            raise ProtocolShapeError(
                "ResolvedScenarioV1 worlds must have the same base view digest"
            )
        if self.baseline_world.admissibility_digest != self.effective_world.admissibility_digest:
            raise ProtocolShapeError(
                "ResolvedScenarioV1 worlds must have the same admissibility digest"
            )
        object.__setattr__(
            self,
            "resolution_evidence_digest",
            _token(
                "resolved_scenario_v1",
                {
                    "spec_digest": self.spec.spec_digest,
                    "baseline_world_digest": self.baseline_world.world_digest,
                    "effective_world_digest": self.effective_world.world_digest,
                },
            ),
        )


__all__ = [
    "ClosureScopeV1",
    "ClosureTargetKindV1",
    "EffectiveWorldFactV1",
    "EffectiveWorldV1",
    "EvidenceScopeV1",
    "ExactLocalClosureTargetV1",
    "ResolvedScenarioOperationV1",
    "ResolvedScenarioV1",
    "ScenarioCreateEphemeralEntityV1",
    "ScenarioEnsureMemberV1",
    "ScenarioEnsureRelationV1",
    "ScenarioOperationKindV1",
    "ScenarioOperationV1",
    "ScenarioSetEffectiveValueV1",
    "ScenarioSetExactMembersV1",
    "ScenarioSpecV1",
    "ScenarioValueStorageV1",
    "ScenarioValueTagV1",
    "ScenarioValueV1",
    "ScenarioWithoutFieldV1",
    "ScenarioWithoutEntityV1",
    "ScenarioWithoutAssertionV1",
    "ScenarioWithoutRelationV1",
    "ScenarioWithoutValueV1",
]
