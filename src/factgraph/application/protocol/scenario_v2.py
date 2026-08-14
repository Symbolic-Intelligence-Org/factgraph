"""Parallel Scenario V2 protocol values with typed metadata lanes.

Scenario V1 remains the frozen deterministic algebra.  V2 deliberately wraps
that ground operation grammar instead of widening V1's durable identity.  Its
``meta=`` convenience spelling is lowered immediately into three closed lanes:

* :class:`FactSemanticsV2` is evaluator-visible and belongs to the semantic
  world digest;
* :class:`~factgraph.application.protocol.provenance_v1.ProvenanceRefV1` and
  display annotation are Explain/audit material and belong to the resolution
  evidence digest; and
* resolver-created source classifications remain internal protocol values,
  not caller supplied metadata.

This module owns values and sealing only.  ``scenario_v2_runtime`` owns the
small normalization/materializer handoff.  Neither module executes an engine
or modifies a ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import json
import math
from typing import Literal, Mapping, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str
from .provenance_v1 import (
    ProvenanceLocatorV1,
    ProvenanceRefV1,
    canonical_provenance_refs_v1,
)
from .scenario_v1 import (
    ScenarioCreateEphemeralEntityV1,
    ScenarioEnsureMemberV1,
    ScenarioEnsureRelationV1,
    ScenarioOperationKindV1,
    ScenarioOperationV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioValueV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutEntityV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutRelationV1,
    ScenarioWithoutValueV1,
)
from .schema_runtime import EntityRef, FieldPath


ScenarioFactRawKindV2: TypeAlias = Literal["probabilistic"]
ScenarioFactOriginV2: TypeAlias = Literal["baseline_support", "scenario_synthetic"]

_RAW_KINDS = frozenset({"probabilistic"})
_FACT_ORIGINS = frozenset({"baseline_support", "scenario_synthetic"})
_META_KEYS = frozenset({"raw_kind", "bound", "source", "sources", "note", "labels"})
_FACT_PRODUCING_KINDS = frozenset({"set_effective_value", "ensure_member", "ensure_relation"})
_WITHOUT_KINDS = frozenset(
    {
        "without_field",
        "without_value",
        "without_relation",
        "without_entity",
        "without_assertion",
    }
)

MAX_DECIMAL_V2_CHARS = 64
MAX_DECIMAL_V2_SCALE = 24
MAX_SCENARIO_NOTE_V2_CHARS = 2048
MAX_SCENARIO_LABELS_V2 = 16
MAX_SCENARIO_LABEL_V2_CHARS = 128
MAX_SCENARIO_V2_OPERATIONS = 256


def _token(label: str, payload: object) -> str:
    try:
        raw = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:  # pragma: no cover - DTO guarded
        raise ProtocolShapeError(f"{label} payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(raw)}"


def _require_sha256_token(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    suffix = value[7:]
    if (
        len(suffix) != 64
        or suffix != suffix.lower()
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    return value


def _require_display_text(value: object, *, field_name: str, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise ProtocolShapeError(f"{field_name} must be bounded non-empty display text")
    return value


def canonical_decimal_v2(value: object, *, field_name: str = "decimal") -> str:
    """Normalize one finite exact decimal into V2's non-exponent wire form.

    The protocol stores a decimal *string*, never a binary float.  SDK ingress
    may pass finite ``float`` values for ergonomic ``[0.8, 0.8]`` input; it is
    converted through ``repr`` before this function validates canonical form.
    """

    if isinstance(value, bool):
        raise ProtocolShapeError(f"{field_name} must be finite decimal, not bool")
    if isinstance(value, Decimal):
        raw = format(value, "f")
    elif isinstance(value, int):
        raw = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolShapeError(f"{field_name} must be finite decimal")
        raw = repr(value)
    elif isinstance(value, str):
        raw = value
    else:
        raise ProtocolShapeError(f"{field_name} must be finite decimal")
    if not raw or len(raw) > MAX_DECIMAL_V2_CHARS or "e" in raw.lower() or raw.startswith("+"):
        raise ProtocolShapeError(f"{field_name} must be a bounded non-exponent decimal")
    try:
        parsed = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ProtocolShapeError(f"{field_name} must be finite decimal") from exc
    if not parsed.is_finite():
        raise ProtocolShapeError(f"{field_name} must be finite decimal")
    exponent = parsed.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -MAX_DECIMAL_V2_SCALE:
        raise ProtocolShapeError(f"{field_name} exceeds decimal scale cap")
    # Decimal.normalize() can write scientific notation, so spell the finite
    # normalized coefficient explicitly.  This also strips trailing zeros.
    if parsed == 0:
        canonical = "0"
    else:
        canonical = format(parsed.normalize(), "f")
        if canonical.startswith("-0") and Decimal(canonical) == 0:
            canonical = "0"
    if canonical.startswith("."):
        canonical = f"0{canonical}"
    if canonical.startswith("-."):
        canonical = f"-0{canonical[1:]}"
    if len(canonical) > MAX_DECIMAL_V2_CHARS:
        raise ProtocolShapeError(f"{field_name} exceeds decimal wire cap")
    return canonical


@dataclass(frozen=True)
class FactSemanticsV2:
    """The only initially supported evaluator-visible Scenario fact semantic."""

    raw_kind: ScenarioFactRawKindV2
    point_probability: str
    semantics_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.raw_kind not in _RAW_KINDS:
            raise ProtocolShapeError("FactSemanticsV2.raw_kind is unsupported")
        canonical = canonical_decimal_v2(
            self.point_probability, field_name="FactSemanticsV2.point_probability"
        )
        if canonical != self.point_probability:
            raise ProtocolShapeError("FactSemanticsV2.point_probability is not canonical")
        probability = Decimal(canonical)
        if probability < 0 or probability > 1:
            raise ProtocolShapeError("FactSemanticsV2.point_probability must be in [0, 1]")
        object.__setattr__(
            self,
            "semantics_digest",
            _token(
                "scenario_fact_semantics_v2",
                {"raw_kind": self.raw_kind, "point_probability": canonical},
            ),
        )

    @classmethod
    def probabilistic_point(cls, value: object) -> "FactSemanticsV2":
        return cls(raw_kind="probabilistic", point_probability=canonical_decimal_v2(value))

    def to_wire(self) -> dict[str, str]:
        return {"raw_kind": self.raw_kind, "point_probability": self.point_probability}


@dataclass(frozen=True)
class ScenarioDisplayV2:
    """Bounded presentation-only Scenario annotation."""

    note: str | None = None
    labels: tuple[str, ...] = ()
    display_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.note is not None:
            _require_display_text(
                self.note, field_name="ScenarioDisplayV2.note", limit=MAX_SCENARIO_NOTE_V2_CHARS
            )
        if not isinstance(self.labels, tuple) or len(self.labels) > MAX_SCENARIO_LABELS_V2:
            raise ProtocolShapeError("ScenarioDisplayV2.labels must be bounded tuple[str, ...]")
        normalized = tuple(
            sorted(
                {
                    _require_display_text(
                        label,
                        field_name=f"ScenarioDisplayV2.labels[{index}]",
                        limit=MAX_SCENARIO_LABEL_V2_CHARS,
                    )
                    for index, label in enumerate(self.labels)
                }
            )
        )
        object.__setattr__(self, "labels", normalized)
        object.__setattr__(
            self,
            "display_digest",
            _token("scenario_display_v2", {"note": self.note, "labels": normalized}),
        )

    @property
    def is_empty(self) -> bool:
        return self.note is None and not self.labels

    def to_wire(self) -> dict[str, object]:
        return {"note": self.note, "labels": list(self.labels)}


@dataclass(frozen=True)
class ScenarioMetaV2:
    """Fully lowered metadata for exactly one Scenario operation/fact lane."""

    fact_semantics: FactSemanticsV2 | None = None
    provenance: tuple[ProvenanceRefV1, ...] = ()
    display: ScenarioDisplayV2 = field(default_factory=ScenarioDisplayV2)
    semantics_digest: str = field(init=False)
    provenance_digest: str = field(init=False)
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.fact_semantics is not None and not isinstance(self.fact_semantics, FactSemanticsV2):
            raise ProtocolShapeError(
                "ScenarioMetaV2.fact_semantics must be FactSemanticsV2 or None"
            )
        provenance = canonical_provenance_refs_v1(
            self.provenance, field_name="ScenarioMetaV2.provenance"
        )
        if not isinstance(self.display, ScenarioDisplayV2):
            raise ProtocolShapeError("ScenarioMetaV2.display must be ScenarioDisplayV2")
        object.__setattr__(self, "provenance", provenance)
        semantics_digest = _token(
            "scenario_meta_v2_semantics",
            None if self.fact_semantics is None else self.fact_semantics.semantics_digest,
        )
        provenance_digest = _token(
            "scenario_meta_v2_provenance",
            tuple(item.reference_digest for item in provenance),
        )
        object.__setattr__(self, "semantics_digest", semantics_digest)
        object.__setattr__(self, "provenance_digest", provenance_digest)
        object.__setattr__(
            self,
            "evidence_digest",
            _token(
                "scenario_meta_v2_evidence",
                {
                    "provenance_digest": provenance_digest,
                    "display_digest": self.display.display_digest,
                },
            ),
        )

    @property
    def is_empty(self) -> bool:
        return self.fact_semantics is None and not self.provenance and self.display.is_empty

    def to_wire(self) -> dict[str, object]:
        return {
            "fact_semantics": None
            if self.fact_semantics is None
            else self.fact_semantics.to_wire(),
            "provenance": [item.to_wire() for item in self.provenance],
            "display": self.display.to_wire(),
        }


def _coerce_provenance_ref(value: object, *, field_name: str) -> ProvenanceRefV1:
    if isinstance(value, ProvenanceRefV1):
        return value
    if not isinstance(value, Mapping):
        raise ProtocolShapeError(f"{field_name} must be ProvenanceRefV1 or closed source object")
    allowed = {"ref", "locator", "content_digest", "origin_role", "admission_ref"}
    if not {"ref", "locator", "origin_role"}.issubset(value) or set(value) - allowed:
        raise ProtocolShapeError(f"{field_name} has unsupported or missing source fields")
    return ProvenanceRefV1.from_wire(
        {
            "ref": value["ref"],
            "locator": value["locator"],
            "content_digest": value.get("content_digest"),
            "origin_role": value["origin_role"],
            "admission_ref": value.get("admission_ref"),
        }
    )


def lower_scenario_meta_v2(meta: object) -> ScenarioMetaV2:
    """Fail-closed lower the ergonomic SDK ``meta=`` spelling.

    This is intentionally the only accepted free-form boundary.  It accepts a
    small mapping, turns it into typed values and rejects all leftovers before
    a Scenario resolver or engine can see it.
    """

    if meta is None:
        return ScenarioMetaV2()
    if isinstance(meta, ScenarioMetaV2):
        return meta
    if not isinstance(meta, Mapping):
        raise ProtocolShapeError("Scenario meta must be mapping, ScenarioMetaV2, or None")
    keys = set(meta)
    if not all(isinstance(key, str) for key in keys) or keys - _META_KEYS:
        raise ProtocolShapeError("Scenario meta has unsupported keys")
    if "source" in keys and "sources" in keys:
        raise ProtocolShapeError("Scenario meta cannot supply both source and sources")
    has_raw_kind = "raw_kind" in keys
    has_bound = "bound" in keys
    if has_raw_kind != has_bound:
        raise ProtocolShapeError("Scenario meta raw_kind and bound must appear together")
    fact_semantics: FactSemanticsV2 | None = None
    if has_raw_kind:
        if meta["raw_kind"] != "probabilistic":
            raise ProtocolShapeError("Scenario meta raw_kind is unsupported")
        bound = meta["bound"]
        if not isinstance(bound, (tuple, list)) or len(bound) != 2:
            raise ProtocolShapeError("Scenario meta probabilistic bound must be [p, p]")
        left = canonical_decimal_v2(bound[0], field_name="Scenario meta bound[0]")
        right = canonical_decimal_v2(bound[1], field_name="Scenario meta bound[1]")
        if left != right:
            raise ProtocolShapeError("Scenario meta initially supports exact point bounds only")
        fact_semantics = FactSemanticsV2(raw_kind="probabilistic", point_probability=left)
    provenance: tuple[ProvenanceRefV1, ...] = ()
    if "source" in keys:
        provenance = (_coerce_provenance_ref(meta["source"], field_name="Scenario meta source"),)
    elif "sources" in keys:
        sources = meta["sources"]
        if not isinstance(sources, (tuple, list)):
            raise ProtocolShapeError("Scenario meta sources must be list or tuple")
        provenance = tuple(
            _coerce_provenance_ref(item, field_name=f"Scenario meta sources[{index}]")
            for index, item in enumerate(sources)
        )
    note = meta.get("note")
    labels_raw = meta.get("labels", ())
    if not isinstance(labels_raw, (tuple, list)):
        raise ProtocolShapeError("Scenario meta labels must be list or tuple")
    display = ScenarioDisplayV2(
        note=note,  # type: ignore[arg-type]
        labels=tuple(labels_raw),  # type: ignore[arg-type]
    )
    return ScenarioMetaV2(
        fact_semantics=fact_semantics,
        provenance=provenance,
        display=display,
    )


def scenario_operation_kind_v2(operation: ScenarioOperationV1) -> ScenarioOperationKindV1:
    """Return the stable V1 kind while retaining the V1 grammar untouched."""

    if isinstance(operation, ScenarioSetEffectiveValueV1):
        return "set_effective_value"
    if isinstance(operation, ScenarioEnsureMemberV1):
        return "ensure_member"
    if isinstance(operation, ScenarioSetExactMembersV1):
        return "set_exact_members"
    if isinstance(operation, ScenarioWithoutFieldV1):
        return "without_field"
    if isinstance(operation, ScenarioWithoutValueV1):
        return "without_value"
    if isinstance(operation, ScenarioCreateEphemeralEntityV1):
        return "create_ephemeral_entity"
    if isinstance(operation, ScenarioEnsureRelationV1):
        return "ensure_relation"
    if isinstance(operation, ScenarioWithoutRelationV1):
        return "without_relation"
    if isinstance(operation, ScenarioWithoutEntityV1):
        return "without_entity"
    if isinstance(operation, ScenarioWithoutAssertionV1):
        return "without_assertion"
    raise ProtocolShapeError("ScenarioOperationV2.operation must be ScenarioOperationV1")


@dataclass(frozen=True)
class ScenarioOperationV2:
    """One V1 ground operation plus V2 typed metadata.

    Multi-member exact-set operations use ``member_meta`` in value order.  An
    operation-level semantic request there is rejected because it would not
    say which synthetic member receives the probability.  ``without_*`` can
    describe its provenance/display but cannot manufacture fact semantics.
    """

    operation: ScenarioOperationV1
    meta: ScenarioMetaV2 = field(default_factory=ScenarioMetaV2)
    member_meta: tuple[ScenarioMetaV2, ...] = ()
    operation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        kind = scenario_operation_kind_v2(self.operation)
        if not isinstance(self.meta, ScenarioMetaV2):
            raise ProtocolShapeError("ScenarioOperationV2.meta must be ScenarioMetaV2")
        if not isinstance(self.member_meta, tuple) or not all(
            isinstance(item, ScenarioMetaV2) for item in self.member_meta
        ):
            raise ProtocolShapeError("ScenarioOperationV2.member_meta must be ScenarioMetaV2 tuple")
        if kind in _WITHOUT_KINDS:
            if self.meta.fact_semantics is not None or self.member_meta:
                raise ProtocolShapeError("Scenario without operation cannot carry fact semantics")
        elif kind == "set_exact_members":
            if self.meta.fact_semantics is not None:
                raise ProtocolShapeError(
                    "Scenario exact-member semantics must be supplied per member"
                )
            assert isinstance(self.operation, ScenarioSetExactMembersV1)
            if self.member_meta and len(self.member_meta) != len(self.operation.values):
                raise ProtocolShapeError("Scenario exact-member metadata must cover every member")
        else:
            if self.member_meta:
                raise ProtocolShapeError(
                    "Scenario member metadata is only valid for exact-member operation"
                )
            if kind not in _FACT_PRODUCING_KINDS and self.meta.fact_semantics is not None:
                raise ProtocolShapeError("Scenario operation does not produce a semantic fact")
        object.__setattr__(
            self,
            "operation_digest",
            _token(
                "scenario_operation_v2",
                {
                    "v1_statement_digest": self.operation.statement_digest,
                    "kind": kind,
                    "meta_semantics_digest": self.meta.semantics_digest,
                    "meta_evidence_digest": self.meta.evidence_digest,
                    "member_meta_semantics_digests": tuple(
                        item.semantics_digest for item in self.member_meta
                    ),
                    "member_meta_evidence_digests": tuple(
                        item.evidence_digest for item in self.member_meta
                    ),
                },
            ),
        )

    @property
    def kind(self) -> ScenarioOperationKindV1:
        return scenario_operation_kind_v2(self.operation)

    @property
    def premise_id(self) -> str:
        return self.operation.premise_id


def _current_scenario_value_v1(value: ScenarioValueV1) -> ScenarioValueV1:
    """Rebuild a V1 value without trusting a frozen object's stale fields."""

    if not isinstance(value, ScenarioValueV1):
        raise ProtocolShapeError("Scenario V2 nested value must be ScenarioValueV1")
    return ScenarioValueV1(value.tag, value.value)


def _current_entity_ref_v1(value: EntityRef) -> EntityRef:
    if not isinstance(value, EntityRef):
        raise ProtocolShapeError("Scenario V2 nested entity must be EntityRef")
    return EntityRef(value.entity_type, dict(value.identity), value.encoded_ref)


def _current_field_path_v1(value: FieldPath) -> FieldPath:
    if not isinstance(value, FieldPath):
        raise ProtocolShapeError("Scenario V2 nested field must be FieldPath")
    return FieldPath(value.entity_type, value.field_name)


def _current_provenance_ref_v1(value: ProvenanceRefV1) -> ProvenanceRefV1:
    """Recursively verify all provenance fields and their cached digests."""

    if not isinstance(value, ProvenanceRefV1) or not isinstance(value.locator, ProvenanceLocatorV1):
        raise ProtocolShapeError("Scenario V2 provenance reference is malformed")
    locator = ProvenanceLocatorV1(
        kind=value.locator.kind,
        opaque_ref=value.locator.opaque_ref,
        line_start=value.locator.line_start,
        line_end=value.locator.line_end,
        pointer=tuple(value.locator.pointer),
    )
    if locator.locator_digest != value.locator.locator_digest:
        raise ProtocolShapeError("Scenario V2 provenance locator digest is stale")
    fresh = ProvenanceRefV1(
        source_ref=value.source_ref,
        locator=locator,
        origin_role=value.origin_role,
        content_digest=value.content_digest,
        admission_ref=value.admission_ref,
    )
    if fresh.reference_digest != value.reference_digest:
        raise ProtocolShapeError("Scenario V2 provenance reference digest is stale")
    return fresh


def _current_fact_semantics_v2(value: FactSemanticsV2 | None) -> FactSemanticsV2 | None:
    if value is None:
        return None
    if not isinstance(value, FactSemanticsV2):
        raise ProtocolShapeError("Scenario V2 fact semantics is malformed")
    fresh = FactSemanticsV2(value.raw_kind, value.point_probability)
    if fresh.semantics_digest != value.semantics_digest:
        raise ProtocolShapeError("Scenario V2 fact semantics digest is stale")
    return fresh


def _current_display_v2(value: ScenarioDisplayV2) -> ScenarioDisplayV2:
    if not isinstance(value, ScenarioDisplayV2):
        raise ProtocolShapeError("Scenario V2 display metadata is malformed")
    fresh = ScenarioDisplayV2(note=value.note, labels=tuple(value.labels))
    if fresh.display_digest != value.display_digest:
        raise ProtocolShapeError("Scenario V2 display metadata digest is stale")
    return fresh


def _current_meta_v2(value: ScenarioMetaV2) -> ScenarioMetaV2:
    if not isinstance(value, ScenarioMetaV2):
        raise ProtocolShapeError("Scenario V2 metadata is malformed")
    fresh = ScenarioMetaV2(
        fact_semantics=_current_fact_semantics_v2(value.fact_semantics),
        provenance=tuple(_current_provenance_ref_v1(item) for item in value.provenance),
        display=_current_display_v2(value.display),
    )
    if (
        fresh.semantics_digest != value.semantics_digest
        or fresh.provenance_digest != value.provenance_digest
        or fresh.evidence_digest != value.evidence_digest
    ):
        raise ProtocolShapeError("Scenario V2 metadata digest is stale")
    return fresh


def _current_operation_v1(value: ScenarioOperationV1) -> ScenarioOperationV1:
    """Reconstruct the V1 statement beneath a V2 operation before sealing.

    V1 values have cached statement digests, and ``frozen=True`` does not
    prevent hostile ``object.__setattr__`` mutation.  Rebuilding keeps a V2
    Scenario from accepting a fresh-looking meta digest over a stale V1
    statement.  The original object is never reinitialised or repaired here.
    """

    if isinstance(value, ScenarioSetEffectiveValueV1):
        fresh: ScenarioOperationV1 = ScenarioSetEffectiveValueV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            field=_current_field_path_v1(value.field),
            value=_current_scenario_value_v1(value.value),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioEnsureMemberV1):
        fresh = ScenarioEnsureMemberV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            field=_current_field_path_v1(value.field),
            value=_current_scenario_value_v1(value.value),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioSetExactMembersV1):
        fresh = ScenarioSetExactMembersV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            field=_current_field_path_v1(value.field),
            values=tuple(_current_scenario_value_v1(item) for item in value.values),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioWithoutFieldV1):
        fresh = ScenarioWithoutFieldV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            field=_current_field_path_v1(value.field),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioWithoutValueV1):
        fresh = ScenarioWithoutValueV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            field=_current_field_path_v1(value.field),
            value=_current_scenario_value_v1(value.value),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioCreateEphemeralEntityV1):
        fresh = ScenarioCreateEphemeralEntityV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioEnsureRelationV1):
        fresh = ScenarioEnsureRelationV1(
            premise_id=value.premise_id,
            predicate_id=value.predicate_id,
            values=tuple(_current_scenario_value_v1(item) for item in value.values),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioWithoutRelationV1):
        fresh = ScenarioWithoutRelationV1(
            premise_id=value.premise_id,
            predicate_id=value.predicate_id,
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioWithoutEntityV1):
        fresh = ScenarioWithoutEntityV1(
            premise_id=value.premise_id,
            entity=_current_entity_ref_v1(value.entity),
            origin_refs=tuple(value.origin_refs),
        )
    elif isinstance(value, ScenarioWithoutAssertionV1):
        fresh = ScenarioWithoutAssertionV1(
            premise_id=value.premise_id,
            assertion_id=value.assertion_id,
            origin_refs=tuple(value.origin_refs),
        )
    else:
        raise ProtocolShapeError("Scenario V2 operation must wrap ScenarioOperationV1")
    if fresh.statement_digest != value.statement_digest:
        raise ProtocolShapeError("Scenario V2 wrapped V1 statement digest is stale")
    return fresh


def _assert_scenario_operation_v2_current(value: ScenarioOperationV2) -> None:
    """Fail closed when any nested V1/V2 digest cache no longer matches data."""

    if not isinstance(value, ScenarioOperationV2):
        raise ProtocolShapeError("Scenario V2 operation is malformed")
    fresh = ScenarioOperationV2(
        operation=_current_operation_v1(value.operation),
        meta=_current_meta_v2(value.meta),
        member_meta=tuple(_current_meta_v2(item) for item in value.member_meta),
    )
    if fresh.operation_digest != value.operation_digest:
        raise ProtocolShapeError("Scenario V2 operation digest is stale")


@dataclass(frozen=True)
class ScenarioSpecV2:
    """An immutable unordered Scenario operation batch with V2 metadata lanes."""

    operations: tuple[ScenarioOperationV2, ...]
    spec_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operations, tuple)
            or not self.operations
            or len(self.operations) > MAX_SCENARIO_V2_OPERATIONS
            or not all(isinstance(item, ScenarioOperationV2) for item in self.operations)
        ):
            raise ProtocolShapeError(
                "ScenarioSpecV2.operations must be bounded ScenarioOperationV2 tuple"
            )
        for item in self.operations:
            _assert_scenario_operation_v2_current(item)
        premise_ids = tuple(item.premise_id for item in self.operations)
        if len(set(premise_ids)) != len(premise_ids):
            raise ProtocolShapeError("ScenarioSpecV2 premise ids must be unique")
        canonical = tuple(sorted(self.operations, key=lambda item: item.operation_digest))
        expected_digest = _token(
            "scenario_spec_v2",
            {"operation_digests": tuple(item.operation_digest for item in canonical)},
        )
        if hasattr(self, "spec_digest"):
            if self.spec_digest != expected_digest:
                raise ProtocolShapeError("Scenario V2 spec digest is stale")
            # A revalidation call must not rewrite a sealed spec's cached
            # identity or canonical operation ordering.
            if self.operations != canonical:
                raise ProtocolShapeError("Scenario V2 spec operation ordering is noncanonical")
            return
        object.__setattr__(self, "operations", canonical)
        object.__setattr__(self, "spec_digest", expected_digest)


@dataclass(frozen=True)
class ScenarioOperationMetaBindingV2:
    """One source metadata lane linked to a resolved Scenario operation.

    ``member_value_digest`` is present only for a V1 exact-member source.  It
    prevents a semantic point assigned to one member from being accidentally
    credited to another member after V1 canonicalizes an operation group.
    """

    premise_id: str
    source_operation_digest: str
    meta: ScenarioMetaV2
    member_value_digest: str | None = None
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.premise_id, field_name="ScenarioOperationMetaBindingV2.premise_id"
        )
        _require_sha256_token(
            self.source_operation_digest,
            field_name="ScenarioOperationMetaBindingV2.source_operation_digest",
        )
        if not isinstance(self.meta, ScenarioMetaV2):
            raise ProtocolShapeError("ScenarioOperationMetaBindingV2.meta must be ScenarioMetaV2")
        if self.member_value_digest is not None:
            _require_sha256_token(
                self.member_value_digest,
                field_name="ScenarioOperationMetaBindingV2.member_value_digest",
            )
        object.__setattr__(
            self,
            "binding_digest",
            _token(
                "scenario_operation_meta_binding_v2",
                {
                    "premise_id": self.premise_id,
                    "source_operation_digest": self.source_operation_digest,
                    "meta_semantics_digest": self.meta.semantics_digest,
                    "meta_evidence_digest": self.meta.evidence_digest,
                    "member_value_digest": self.member_value_digest,
                },
            ),
        )


@dataclass(frozen=True)
class ResolvedScenarioOperationEvidenceV2:
    """Normalized Scenario operation trace retained independently of facts.

    It captures no-op/masked operation provenance and display metadata rather
    than silently dropping it when a V1 effective relation contains no new
    synthetic tuple.  It remains evidence-only: its digest never participates
    in ``semantic_world_digest``.
    """

    kind: ScenarioOperationKindV1
    resolved_operation_digest: str
    metadata_bindings: tuple[ScenarioOperationMetaBindingV2, ...]
    masked_witness_ids: tuple[str, ...] = ()
    synthetic_witness_ids: tuple[str, ...] = ()
    operation_evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in {
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
        }:
            raise ProtocolShapeError("ResolvedScenarioOperationEvidenceV2.kind is unsupported")
        _require_sha256_token(
            self.resolved_operation_digest,
            field_name="ResolvedScenarioOperationEvidenceV2.resolved_operation_digest",
        )
        if (
            not isinstance(self.metadata_bindings, tuple)
            or not self.metadata_bindings
            or not all(
                isinstance(item, ScenarioOperationMetaBindingV2) for item in self.metadata_bindings
            )
        ):
            raise ProtocolShapeError(
                "ResolvedScenarioOperationEvidenceV2.metadata_bindings must be non-empty binding tuple"
            )
        bindings = tuple(sorted(self.metadata_bindings, key=lambda item: item.binding_digest))
        if len({item.binding_digest for item in bindings}) != len(bindings):
            raise ProtocolShapeError(
                "ResolvedScenarioOperationEvidenceV2 metadata bindings must be unique"
            )
        normalized_ids: dict[str, tuple[str, ...]] = {}
        for name in ("masked_witness_ids", "synthetic_witness_ids"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise ProtocolShapeError(
                    f"ResolvedScenarioOperationEvidenceV2.{name} must be tuple"
                )
            canonical = tuple(sorted(set(value)))
            for index, witness_id in enumerate(canonical):
                _require_non_empty_str(
                    witness_id, field_name=f"ResolvedScenarioOperationEvidenceV2.{name}[{index}]"
                )
            normalized_ids[name] = canonical
        object.__setattr__(self, "metadata_bindings", bindings)
        object.__setattr__(self, "masked_witness_ids", normalized_ids["masked_witness_ids"])
        object.__setattr__(self, "synthetic_witness_ids", normalized_ids["synthetic_witness_ids"])
        object.__setattr__(
            self,
            "operation_evidence_digest",
            _token(
                "resolved_scenario_operation_evidence_v2",
                {
                    "kind": self.kind,
                    "resolved_operation_digest": self.resolved_operation_digest,
                    "metadata_bindings": tuple(item.binding_digest for item in bindings),
                    "masked_witness_ids": normalized_ids["masked_witness_ids"],
                    "synthetic_witness_ids": normalized_ids["synthetic_witness_ids"],
                },
            ),
        )


@dataclass(frozen=True)
class EffectiveWorldFactV2:
    """One captured effective-world witness with separated semantic/evidence pins."""

    predicate_id: str
    witness_id: str
    values: tuple[ScenarioValueV1, ...]
    origin: ScenarioFactOriginV2
    fact_semantics: FactSemanticsV2 | None = None
    provenance: tuple[ProvenanceRefV1, ...] = ()
    display: ScenarioDisplayV2 = field(default_factory=ScenarioDisplayV2)
    premise_ids: tuple[str, ...] = ()
    scenario_operation_digests: tuple[str, ...] = ()
    semantic_fact_digest: str = field(init=False)
    evidence_fact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.predicate_id, field_name="EffectiveWorldFactV2.predicate_id")
        _require_non_empty_str(self.witness_id, field_name="EffectiveWorldFactV2.witness_id")
        if (
            not isinstance(self.values, tuple)
            or not self.values
            or not all(isinstance(value, ScenarioValueV1) for value in self.values)
        ):
            raise ProtocolShapeError("EffectiveWorldFactV2.values must be ScenarioValueV1 tuple")
        if self.origin not in _FACT_ORIGINS:
            raise ProtocolShapeError("EffectiveWorldFactV2.origin is unsupported")
        if self.fact_semantics is not None and not isinstance(self.fact_semantics, FactSemanticsV2):
            raise ProtocolShapeError("EffectiveWorldFactV2.fact_semantics is malformed")
        provenance = canonical_provenance_refs_v1(
            self.provenance, field_name="EffectiveWorldFactV2.provenance"
        )
        if not isinstance(self.display, ScenarioDisplayV2):
            raise ProtocolShapeError("EffectiveWorldFactV2.display must be ScenarioDisplayV2")
        if not isinstance(self.premise_ids, tuple):
            raise ProtocolShapeError("EffectiveWorldFactV2.premise_ids must be tuple[str, ...]")
        premise_ids = tuple(sorted(set(self.premise_ids)))
        for index, premise_id in enumerate(premise_ids):
            _require_non_empty_str(
                premise_id, field_name=f"EffectiveWorldFactV2.premise_ids[{index}]"
            )
        if not isinstance(self.scenario_operation_digests, tuple):
            raise ProtocolShapeError(
                "EffectiveWorldFactV2.scenario_operation_digests must be tuple[str, ...]"
            )
        operation_digests = tuple(sorted(set(self.scenario_operation_digests)))
        for index, digest in enumerate(operation_digests):
            _require_sha256_token(
                digest,
                field_name=f"EffectiveWorldFactV2.scenario_operation_digests[{index}]",
            )
        if self.origin == "scenario_synthetic":
            if not premise_ids or not operation_digests:
                raise ProtocolShapeError(
                    "scenario synthetic fact requires premise ids and operation digests"
                )
        elif premise_ids or operation_digests:
            raise ProtocolShapeError(
                "baseline support fact cannot carry Scenario operation linkage"
            )
        semantic_fact_digest = _token(
            "effective_world_fact_v2_semantics",
            {
                "predicate_id": self.predicate_id,
                "values": tuple((value.tag, value.value) for value in self.values),
                "fact_semantics": None
                if self.fact_semantics is None
                else self.fact_semantics.semantics_digest,
            },
        )
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "premise_ids", premise_ids)
        object.__setattr__(self, "scenario_operation_digests", operation_digests)
        object.__setattr__(self, "semantic_fact_digest", semantic_fact_digest)
        object.__setattr__(
            self,
            "evidence_fact_digest",
            _token(
                "effective_world_fact_v2_evidence",
                {
                    "semantic_fact_digest": semantic_fact_digest,
                    "witness_id": self.witness_id,
                    "origin": self.origin,
                    "provenance": tuple(item.reference_digest for item in provenance),
                    "display_digest": self.display.display_digest,
                    "premise_ids": premise_ids,
                    "scenario_operation_digests": operation_digests,
                },
            ),
        )

    @property
    def tuple_identity(self) -> tuple[str, tuple[tuple[str, object], ...]]:
        return (
            self.predicate_id,
            tuple((value.tag, value.value) for value in self.values),
        )


@dataclass(frozen=True)
class EffectiveWorldV2:
    """A sealed V2 world whose logic and traceability identities are distinct."""

    schema_digest: str
    base_view_digest: str
    admissibility_digest: str
    dependency_predicate_ids: tuple[str, ...]
    facts: tuple[EffectiveWorldFactV2, ...]
    closure_target_digests: tuple[str, ...] = ()
    operation_evidence: tuple[ResolvedScenarioOperationEvidenceV2, ...] = ()
    semantic_relation_digest: str = field(init=False)
    resolution_relation_digest: str = field(init=False)
    semantic_world_digest: str = field(init=False)
    resolution_evidence_digest: str = field(init=False)
    world_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("schema_digest", "base_view_digest", "admissibility_digest"):
            _require_sha256_token(getattr(self, name), field_name=f"EffectiveWorldV2.{name}")
        if (
            not isinstance(self.dependency_predicate_ids, tuple)
            or not self.dependency_predicate_ids
        ):
            raise ProtocolShapeError(
                "EffectiveWorldV2.dependency_predicate_ids must be non-empty tuple"
            )
        predicates = tuple(sorted(set(self.dependency_predicate_ids)))
        for index, predicate_id in enumerate(predicates):
            _require_non_empty_str(
                predicate_id, field_name=f"EffectiveWorldV2.dependency_predicate_ids[{index}]"
            )
        if not isinstance(self.facts, tuple) or not all(
            isinstance(item, EffectiveWorldFactV2) for item in self.facts
        ):
            raise ProtocolShapeError("EffectiveWorldV2.facts must be EffectiveWorldFactV2 tuple")
        if {item.predicate_id for item in self.facts} - set(predicates):
            raise ProtocolShapeError(
                "EffectiveWorldV2 facts are outside dependency predicate inventory"
            )
        facts = tuple(sorted(self.facts, key=lambda item: item.evidence_fact_digest))
        if len({item.witness_id for item in facts}) != len(facts):
            raise ProtocolShapeError("EffectiveWorldV2 witness ids must be unique")
        by_tuple: dict[tuple[str, tuple[tuple[str, object], ...]], set[str | None]] = {}
        synthetic_counts: dict[tuple[str, tuple[tuple[str, object], ...]], int] = {}
        for item in facts:
            key = item.tuple_identity
            by_tuple.setdefault(key, set()).add(
                None if item.fact_semantics is None else item.fact_semantics.semantics_digest
            )
            if item.origin == "scenario_synthetic":
                synthetic_counts[key] = synthetic_counts.get(key, 0) + 1
        if any(len(semantics) > 1 for semantics in by_tuple.values()):
            raise ProtocolShapeError("same effective tuple has conflicting fact semantics")
        if any(count > 1 for count in synthetic_counts.values()):
            raise ProtocolShapeError(
                "duplicate synthetic effective tuple must be merged before world construction"
            )
        if not isinstance(self.closure_target_digests, tuple):
            raise ProtocolShapeError("EffectiveWorldV2.closure_target_digests must be tuple")
        closures = tuple(sorted(self.closure_target_digests))
        if len(set(closures)) != len(closures):
            raise ProtocolShapeError("EffectiveWorldV2 closure target digests must be unique")
        for index, digest in enumerate(closures):
            _require_sha256_token(
                digest, field_name=f"EffectiveWorldV2.closure_target_digests[{index}]"
            )
        if not isinstance(self.operation_evidence, tuple) or not all(
            isinstance(item, ResolvedScenarioOperationEvidenceV2)
            for item in self.operation_evidence
        ):
            raise ProtocolShapeError("EffectiveWorldV2.operation_evidence is malformed")
        operation_evidence = tuple(
            sorted(self.operation_evidence, key=lambda item: item.operation_evidence_digest)
        )
        if len({item.operation_evidence_digest for item in operation_evidence}) != len(
            operation_evidence
        ):
            raise ProtocolShapeError("EffectiveWorldV2 operation evidence must be unique")
        semantic_relation_digest = _token(
            "effective_world_v2_semantic_relation",
            tuple(sorted({item.semantic_fact_digest for item in facts})),
        )
        resolution_relation_digest = _token(
            "effective_world_v2_resolution_relation",
            tuple(item.evidence_fact_digest for item in facts),
        )
        semantic_world_digest = _token(
            "effective_world_v2_semantic_world",
            {
                "schema_digest": self.schema_digest,
                "dependency_predicate_ids": predicates,
                "semantic_relation_digest": semantic_relation_digest,
            },
        )
        resolution_evidence_digest = _token(
            "effective_world_v2_resolution_evidence",
            {
                "semantic_world_digest": semantic_world_digest,
                "base_view_digest": self.base_view_digest,
                "admissibility_digest": self.admissibility_digest,
                "resolution_relation_digest": resolution_relation_digest,
                "closure_target_digests": closures,
                "operation_evidence": tuple(
                    item.operation_evidence_digest for item in operation_evidence
                ),
            },
        )
        object.__setattr__(self, "dependency_predicate_ids", predicates)
        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "closure_target_digests", closures)
        object.__setattr__(self, "operation_evidence", operation_evidence)
        object.__setattr__(self, "semantic_relation_digest", semantic_relation_digest)
        object.__setattr__(self, "resolution_relation_digest", resolution_relation_digest)
        object.__setattr__(self, "semantic_world_digest", semantic_world_digest)
        object.__setattr__(self, "resolution_evidence_digest", resolution_evidence_digest)
        object.__setattr__(
            self,
            "world_digest",
            _token(
                "effective_world_v2",
                {
                    "semantic_world_digest": semantic_world_digest,
                    "resolution_evidence_digest": resolution_evidence_digest,
                },
            ),
        )


__all__ = [
    "EffectiveWorldFactV2",
    "EffectiveWorldV2",
    "FactSemanticsV2",
    "MAX_DECIMAL_V2_CHARS",
    "MAX_DECIMAL_V2_SCALE",
    "MAX_SCENARIO_LABELS_V2",
    "MAX_SCENARIO_LABEL_V2_CHARS",
    "MAX_SCENARIO_NOTE_V2_CHARS",
    "MAX_SCENARIO_V2_OPERATIONS",
    "ScenarioDisplayV2",
    "ScenarioFactOriginV2",
    "ScenarioFactRawKindV2",
    "ScenarioMetaV2",
    "ScenarioOperationMetaBindingV2",
    "ScenarioOperationV2",
    "ScenarioSpecV2",
    "ResolvedScenarioOperationEvidenceV2",
    "canonical_decimal_v2",
    "lower_scenario_meta_v2",
    "scenario_operation_kind_v2",
]
