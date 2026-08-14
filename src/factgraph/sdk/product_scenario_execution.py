"""Strict ergonomic SDK construction for Scenario V2 and V2 profiles.

This module is deliberately a *construction* layer.  It turns the ordinary
SDK ``Field`` + managed entity-reference spelling into the parallel V2
Scenario protocol, and it turns typed product Rule/Policy handles into sealed
V2 execution-profile attachments.  It never resolves a Scenario against a
Store, invokes an engine, or keeps a registry of targets.

The separate application protocol owns canonical values and validation.  The
SDK layer adds only three conveniences:

* ``fg.scenario()`` accepts a ``Field`` descriptor, a managed entity reference
  and a Python value;
* ``fg.execution`` supplies closed deterministic/ProbLog profile builders;
  and
* ``fg.problog`` constructs the three closed attachment semantic markers.

In particular, a Scenario ``meta=`` mapping is passed immediately through
``lower_scenario_meta_v2``.  A legacy ``source=`` string, arbitrary metadata
mapping, or ``confidence`` field therefore cannot be smuggled into a V2
Scenario or later confused with ledger metadata.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.execution_profile_v2 import (
    DeterministicSemanticsV2,
    EvaluationCapturePolicyV2,
    EvaluationEnginePinV2,
    EvaluationExecutionProfileV2,
    EvaluationResourcePolicyV2,
    EvaluationTargetPinV2,
    ExecutionAttachmentSemanticsV2,
    ExecutionAttachmentV2,
    ProbLogPointSemanticsV2,
)
from factgraph.application.protocol.provenance_v1 import (
    ProvenanceLocatorV1,
    ProvenanceRefV1,
)
from factgraph.application.protocol.scenario_v1 import ScenarioValueV1
from factgraph.application.protocol.scenario_v2 import (
    ScenarioMetaV2,
    ScenarioSpecV2,
    lower_scenario_meta_v2,
)
from factgraph.application.protocol.schema_runtime import EntityRef, FieldPath
from factgraph.application.scenario_v2_runtime import (
    ScenarioBuilderV2 as _ApplicationScenarioBuilderV2,
)
from factgraph.application.schema_runtime import entity_type_from_ref

from .errors import FrozenSnapshotError, SDKStoreError
from .policy_authoring import PolicyOccurrenceHandle
from .product_authoring import (
    ProductPolicyV1,
    ProductRuleV1,
    WeightedChoiceHandle,
    WeightedChoiceTopologyV1,
    assert_asset_binding_current_v1,
)
from .schema import Field

if TYPE_CHECKING:
    from .store import SDKStore


DEFAULT_NATIVE_ENGINE_VERSION_V2 = "factgraph-native-v2"
DEFAULT_NATIVE_ADAPTER_VERSION_V2 = "factgraph-native-adapter-v2"
DEFAULT_PROBLOG_ENGINE_VERSION_V2 = "problog-v2"
DEFAULT_PROBLOG_ADAPTER_VERSION_V2 = "factgraph-problog-adapter-v2"
DEFAULT_SOUFFLE_ENGINE_VERSION_V2 = "souffle-v2"
DEFAULT_SOUFFLE_ADAPTER_VERSION_V2 = "factgraph-souffle-adapter-v2"

_UNSET = object()
_Target = ProductRuleV1 | ProductPolicyV1
_TargetSide = Literal["primary", "candidate"]


class ProductScenarioExecutionError(SDKStoreError):
    """Typed rejection on the product Scenario/profile construction surface."""


def _goal_plan_v2_compiler_digest() -> str:
    """Load the authoritative runner pin only after the SDK package is ready."""

    # ``goal_plan_v2_runtime`` imports product authoring wrappers.  Delaying
    # this one-way lookup avoids a package-init cycle while still making the
    # runner module the single source of truth for every constructed profile.
    from factgraph.application.goal_plan_v2_runtime import GOAL_PLAN_V2_COMPILER_DIGEST

    return GOAL_PLAN_V2_COMPILER_DIGEST


def _as_sdk_error(exc: Exception, *, action: str, code: str) -> ProductScenarioExecutionError:
    """Keep application protocol failures out of the public SDK exception mix."""

    return ProductScenarioExecutionError(f"{action} rejected: {exc}", code=code)


def _require_target(value: object, *, field_name: str) -> _Target:
    if not isinstance(value, (ProductRuleV1, ProductPolicyV1)):
        raise ProductScenarioExecutionError(
            f"{field_name} must be ProductRuleV1 or ProductPolicyV1; "
            "build the Rule/Policy through fg.build_rule(...) or fg.policy_builder(...)",
            code="V2_PROFILE_PRODUCT_TARGET_REQUIRED",
        )
    try:
        assert_asset_binding_current_v1(value)
    except SDKStoreError:
        raise
    return value


def _require_target_side(value: object, *, field_name: str) -> _TargetSide:
    if value not in {"primary", "candidate"}:
        raise ProductScenarioExecutionError(
            f"{field_name} must be 'primary' or 'candidate'",
            code="V2_PROFILE_TARGET_SIDE_INVALID",
        )
    return value  # type: ignore[return-value]


def _target_pin(target: _Target, *, side: _TargetSide) -> EvaluationTargetPinV2:
    """Build an exact authored target pin without giving metadata semantic force."""

    if isinstance(target, ProductRuleV1):
        return EvaluationTargetPinV2(
            side=side,
            target_kind="rule",
            target_id=target.rule.id,
            target_version=target.rule.version,
            # A target pin names the authored *Rule asset* (including its
            # schema/semantic contract).  An attachment carries the separate
            # Rule content digest.  Do not collapse the two identities: two
            # Rule assets can share source content while remaining different
            # product targets by id/version or contract.
            target_digest=target.logical_identity_digest,
        )
    return EvaluationTargetPinV2(
        side=side,
        target_kind="policy",
        target_id=target.policy.id,
        target_version=target.policy.version,
        target_digest=target.logical_identity_digest,
    )


def _rule_digest_token(value: object) -> str:
    """Lift the established bare Rule content hash into the V2 token grammar."""

    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProductScenarioExecutionError(
            "Product Rule content digest is not a canonical SHA-256 hash",
            code="V2_PROFILE_RULE_DIGEST_INVALID",
        )
    return f"sha256:{value}"


def _rule_is_occurrence_of_policy(rule: ProductRuleV1, target: ProductPolicyV1) -> bool:
    return any(
        managed.occurrence.rule.id == rule.rule.id
        and managed.occurrence.rule.version == rule.rule.version
        and managed.occurrence.rule.content_digest == rule.rule.content_digest
        for managed in target.address_space.occurrences
    )


def _field_context(
    graph: "SDKStore", field: object, *, action: str
) -> tuple[dict[str, Any], FieldPath]:
    if not isinstance(field, Field):
        raise ProductScenarioExecutionError(
            f"scenario.{action}(...) requires an SDK Field descriptor",
            code="SCENARIO_V2_FIELD_REQUIRED",
        )
    try:
        predicate = graph._schema_pred_for_field(field)
    except SDKStoreError:
        raise
    entity_type = predicate.get("owner_type")
    field_name = predicate.get("py_field_name")
    if (
        not isinstance(entity_type, str)
        or not entity_type
        or not isinstance(field_name, str)
        or not field_name
    ):
        raise ProductScenarioExecutionError(
            "SDK field binding has no canonical schema path",
            code="SCENARIO_V2_FIELD_SCHEMA_INVALID",
        )
    return predicate, FieldPath(entity_type=entity_type, field_name=field_name)


def _entity_ref_for_field(
    graph: "SDKStore",
    entity: object,
    *,
    field: FieldPath,
    action: str,
) -> EntityRef:
    """Normalize one managed SDK entity spelling to V1's exact EntityRef."""

    candidate = getattr(entity, "ref", entity)
    if isinstance(candidate, EntityRef):
        normalized = candidate
    elif isinstance(candidate, str):
        entity_type = entity_type_from_ref(candidate)
        identity = graph._identity_values_by_e_ref.get(candidate)
        if (
            not isinstance(entity_type, str)
            or not entity_type
            or not isinstance(identity, dict)
            or not identity
        ):
            raise ProductScenarioExecutionError(
                "scenario entity reference must be managed by this graph; use "
                "fg.entities.ref(...) or fg.entities.create(...) first",
                code="SCENARIO_V2_UNRESOLVABLE_ENTITY",
            )
        normalized = EntityRef(
            entity_type=entity_type,
            identity=dict(identity),
            encoded_ref=candidate,
        )
    else:
        raise ProductScenarioExecutionError(
            f"scenario.{action}(...) entity must be a managed e_ref, EntityRef, or snapshot with .ref",
            code="SCENARIO_V2_ENTITY_REQUIRED",
        )
    if normalized.entity_type != field.entity_type:
        raise ProductScenarioExecutionError(
            f"scenario.{action}(...) entity type {normalized.entity_type!r} does not match "
            f"field {field.entity_type}.{field.field_name}",
            code="SCENARIO_V2_ENTITY_FIELD_MISMATCH",
        )
    return normalized


def _value_tag(predicate: dict[str, Any]) -> str:
    specs = predicate.get("arg_specs")
    if not isinstance(specs, list) or len(specs) != 2 or not isinstance(specs[1], dict):
        raise ProductScenarioExecutionError(
            "SDK field binding has malformed value type information",
            code="SCENARIO_V2_FIELD_SCHEMA_INVALID",
        )
    tag = specs[1].get("type_domain")
    if not isinstance(tag, str) or not tag:
        raise ProductScenarioExecutionError(
            "SDK field binding has no supported Scenario value type",
            code="SCENARIO_V2_VALUE_TYPE_INVALID",
        )
    return tag


def _scenario_value(predicate: dict[str, Any], value: object) -> ScenarioValueV1:
    """Use the same scalar normalization envelope as SDK field writes."""

    tag = _value_tag(predicate)
    raw = getattr(value, "ref", value)
    if tag == "entity_ref" and isinstance(raw, EntityRef):
        raw = raw.encoded_ref
    if tag == "entity_ref" and (not isinstance(raw, str) or not raw.startswith("idref_v1:")):
        raise ProductScenarioExecutionError(
            "entity-reference Scenario value must be a canonical managed e_ref or EntityRef",
            code="SCENARIO_V2_VALUE_INVALID",
        )
    if tag == "time" and isinstance(raw, datetime):
        if raw.tzinfo is None or raw.tzinfo.utcoffset(raw) is None:
            raise ProductScenarioExecutionError(
                "time Scenario value must be epoch nanos or timezone-aware datetime",
                code="SCENARIO_V2_VALUE_INVALID",
            )
        raw = int(raw.astimezone(timezone.utc).timestamp() * 1_000_000_000)
    if tag == "uuid" and isinstance(raw, UUID):
        raw = str(raw).lower()
    try:
        return ScenarioValueV1.from_raw(tag, raw)  # type: ignore[arg-type]
    except (TypeError, ValueError, ProtocolShapeError) as exc:
        raise _as_sdk_error(exc, action="scenario value", code="SCENARIO_V2_VALUE_INVALID") from exc


def _require_cardinality(predicate: dict[str, Any], *, expected: str, action: str) -> None:
    actual = predicate.get("cardinality")
    if actual != expected:
        noun = "single-value" if expected == "single" else "multi-value"
        raise ProductScenarioExecutionError(
            f"scenario.{action}(...) requires a {noun} Field",
            code="SCENARIO_V2_CARDINALITY_MISMATCH",
        )


class ScenarioBuilderV2:
    """Ergonomic, mutable-while-building SDK facade for immutable ScenarioSpecV2.

    Every method returns this builder and every ``meta=`` is lowered at the
    call boundary.  ``set_exact`` intentionally uses per-member metadata:
    supplying operation-level metadata there would make it ambiguous which
    resulting synthetic fact owns the semantic/provenance annotation.
    """

    __slots__ = ("_graph", "_builder", "_next_premise", "_premise_ids")

    def __init__(self, graph: "SDKStore") -> None:
        self._graph = graph
        self._builder = _ApplicationScenarioBuilderV2()
        self._next_premise = 1
        self._premise_ids: set[str] = set()

    @property
    def operations(self) -> tuple[object, ...]:
        """Read-only staged V2 operations, chiefly for diagnostics/tests."""

        return self._builder.operations

    def _premise(self, value: str | None) -> str:
        if value is None:
            result = f"sdk-scenario:{self._next_premise}"
        elif isinstance(value, str) and value:
            result = value
        else:
            raise ProductScenarioExecutionError(
                "premise_id must be a non-empty string when supplied",
                code="SCENARIO_V2_PREMISE_ID_INVALID",
            )
        if result in self._premise_ids:
            raise ProductScenarioExecutionError(
                f"duplicate Scenario premise_id {result!r}",
                code="SCENARIO_V2_PREMISE_ID_DUPLICATE",
            )
        return result

    def _append(
        self,
        operation: object,
        *,
        premise_id: str,
        meta: ScenarioMetaV2,
        member_meta: tuple[ScenarioMetaV2, ...] = (),
    ) -> "ScenarioBuilderV2":
        try:
            self._builder.add_operation(operation, meta=meta, member_meta=member_meta)
        except (TypeError, ValueError, ProtocolShapeError) as exc:
            raise _as_sdk_error(
                exc, action="Scenario operation", code="SCENARIO_V2_OPERATION_INVALID"
            ) from exc
        self._premise_ids.add(premise_id)
        self._next_premise += 1
        return self

    @staticmethod
    def _meta(value: object) -> ScenarioMetaV2:
        try:
            return lower_scenario_meta_v2(value)
        except (TypeError, ValueError, ProtocolShapeError) as exc:
            raise _as_sdk_error(
                exc, action="Scenario meta", code="SCENARIO_V2_META_INVALID"
            ) from exc

    def set(
        self,
        field: Field,
        entity: object,
        value: object,
        *,
        meta: object = None,
        premise_id: str | None = None,
    ) -> "ScenarioBuilderV2":
        """Replace one single-value field in the run-local effective world."""

        from factgraph.application.protocol.scenario_v1 import ScenarioSetEffectiveValueV1

        predicate, path = _field_context(self._graph, field, action="set")
        _require_cardinality(predicate, expected="single", action="set")
        normalized_premise = self._premise(premise_id)
        return self._append(
            ScenarioSetEffectiveValueV1(
                normalized_premise,
                _entity_ref_for_field(self._graph, entity, field=path, action="set"),
                path,
                _scenario_value(predicate, value),
            ),
            premise_id=normalized_premise,
            meta=self._meta(meta),
        )

    def add(
        self,
        field: Field,
        entity: object,
        value: object,
        *,
        meta: object = None,
        premise_id: str | None = None,
    ) -> "ScenarioBuilderV2":
        """Ensure one member of a multi-value field in the effective world."""

        from factgraph.application.protocol.scenario_v1 import ScenarioEnsureMemberV1

        predicate, path = _field_context(self._graph, field, action="add")
        _require_cardinality(predicate, expected="multi", action="add")
        normalized_premise = self._premise(premise_id)
        return self._append(
            ScenarioEnsureMemberV1(
                normalized_premise,
                _entity_ref_for_field(self._graph, entity, field=path, action="add"),
                path,
                _scenario_value(predicate, value),
            ),
            premise_id=normalized_premise,
            meta=self._meta(meta),
        )

    def set_exact(
        self,
        field: Field,
        entity: object,
        values: Sequence[object],
        *,
        member_meta: Sequence[object] | None = None,
        premise_id: str | None = None,
    ) -> "ScenarioBuilderV2":
        """Set the complete member set of one multi-value field.

        If values carry provenance/display/semantic metadata, pass exactly one
        closed ``member_meta`` entry per input value.  This keeps a point
        probability attached to a precise synthetic fact rather than an
        ambiguous whole-set operation.
        """

        from factgraph.application.protocol.scenario_v1 import ScenarioSetExactMembersV1

        predicate, path = _field_context(self._graph, field, action="set_exact")
        _require_cardinality(predicate, expected="multi", action="set_exact")
        if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
            raise ProductScenarioExecutionError(
                "scenario.set_exact(...) values must be a sequence of field values",
                code="SCENARIO_V2_VALUES_REQUIRED",
            )
        normalized_values = tuple(_scenario_value(predicate, value) for value in values)
        if member_meta is None:
            normalized_member_meta: tuple[ScenarioMetaV2, ...] = ()
        else:
            if isinstance(member_meta, (str, bytes, bytearray)) or not isinstance(
                member_meta, Sequence
            ):
                raise ProductScenarioExecutionError(
                    "scenario.set_exact(...) member_meta must be a sequence when supplied",
                    code="SCENARIO_V2_MEMBER_META_INVALID",
                )
            if len(member_meta) != len(normalized_values):
                raise ProductScenarioExecutionError(
                    "scenario.set_exact(...) member_meta must cover every declared value",
                    code="SCENARIO_V2_MEMBER_META_INVALID",
                )
            normalized_member_meta = tuple(self._meta(item) for item in member_meta)
            # ``ScenarioSetExactMembersV1`` canonically sorts its values.
            # Keep the accompanying per-member semantic/provenance lane paired
            # with its input value before handing the operation to that lower
            # layer.  Sorting the values alone would let a probability or
            # source annotation migrate to another member.
            paired_members = tuple(
                sorted(
                    zip(normalized_values, normalized_member_meta, strict=True),
                    key=lambda item: (item[0].tag, str(item[0].value)),
                )
            )
            normalized_values = tuple(item[0] for item in paired_members)
            normalized_member_meta = tuple(item[1] for item in paired_members)
        normalized_premise = self._premise(premise_id)
        return self._append(
            ScenarioSetExactMembersV1(
                normalized_premise,
                _entity_ref_for_field(self._graph, entity, field=path, action="set_exact"),
                path,
                normalized_values,
            ),
            premise_id=normalized_premise,
            # Operation-level metadata is intentionally empty: the application
            # V2 materializer consumes per-member metadata for exact sets.
            meta=ScenarioMetaV2(),
            member_meta=normalized_member_meta,
        )

    def without(
        self,
        field: Field,
        entity: object,
        value: object = _UNSET,
        *,
        meta: object = None,
        premise_id: str | None = None,
    ) -> "ScenarioBuilderV2":
        """Mask a whole field, or one member when ``value=`` is supplied."""

        from factgraph.application.protocol.scenario_v1 import (
            ScenarioWithoutFieldV1,
            ScenarioWithoutValueV1,
        )

        predicate, path = _field_context(self._graph, field, action="without")
        normalized_premise = self._premise(premise_id)
        normalized_entity = _entity_ref_for_field(self._graph, entity, field=path, action="without")
        operation: ScenarioWithoutFieldV1 | ScenarioWithoutValueV1
        if value is _UNSET:
            operation = ScenarioWithoutFieldV1(normalized_premise, normalized_entity, path)
        else:
            _require_cardinality(predicate, expected="multi", action="without(value=...)")
            operation = ScenarioWithoutValueV1(
                normalized_premise,
                normalized_entity,
                path,
                _scenario_value(predicate, value),
            )
        return self._append(
            operation,
            premise_id=normalized_premise,
            meta=self._meta(meta),
        )

    def build(self) -> ScenarioSpecV2:
        """Return the immutable V2 request; this never resolves or executes it."""

        try:
            return self._builder.build()
        except (TypeError, ValueError, ProtocolShapeError) as exc:
            raise _as_sdk_error(
                exc, action="Scenario build", code="SCENARIO_V2_BUILD_INVALID"
            ) from exc


class ExecutionProfileBuilderV2:
    """Fluent, strict construction of one detached V2 execution profile.

    ``target=`` is deliberately explicit.  An occurrence or choice handle
    alone only proves local authoring ownership; it cannot identify the final
    Policy's digest.  Providing the product Rule/Policy context lets each
    attachment seal its exact target before a later V2 plan can execute it.
    """

    __slots__ = (
        "_default_target",
        "_default_side",
        "_kind",
        "_name",
        "_engines",
        "_resources",
        "_capture",
        "_semantics",
        "_target_pins",
        "_attachments",
    )

    def __init__(
        self,
        *,
        target: _Target,
        side: _TargetSide,
        kind: Literal["native", "problog"],
        name: str | None,
        engines: tuple[EvaluationEnginePinV2, ...],
        resources: EvaluationResourcePolicyV2,
        capture: EvaluationCapturePolicyV2,
    ) -> None:
        self._default_target = _require_target(target, field_name="target")
        self._default_side = _require_target_side(side, field_name="side")
        self._kind = kind
        self._name = name
        self._engines = engines
        self._resources = resources
        self._capture = capture
        self._semantics: DeterministicSemanticsV2 | ProbLogPointSemanticsV2 | None = (
            DeterministicSemanticsV2() if kind == "native" else None
        )
        default_pin = _target_pin(self._default_target, side=self._default_side)
        self._target_pins: dict[_TargetSide, EvaluationTargetPinV2] = {
            self._default_side: default_pin
        }
        self._attachments: list[ExecutionAttachmentV2] = []

    @property
    def target(self) -> _Target:
        """The explicit default target context; it is never registered."""

        return self._default_target

    def fact_semantics(self, *, identity_probability: bool = True) -> "ExecutionProfileBuilderV2":
        """Select the only shipped ProbLog V2 fact-semantic model."""

        if self._kind != "problog":
            raise ProductScenarioExecutionError(
                "fact_semantics(...) is only valid for fg.execution.problog(...)",
                code="V2_PROFILE_SEMANTICS_UNSUPPORTED",
            )
        if identity_probability is not True:
            raise ProductScenarioExecutionError(
                "V2 ProbLog currently requires identity_probability=True",
                code="V2_PROFILE_SEMANTICS_UNSUPPORTED",
            )
        self._semantics = ProbLogPointSemanticsV2(identity_probability=True)
        return self

    def with_target(
        self,
        target: _Target,
        *,
        side: _TargetSide,
    ) -> "ExecutionProfileBuilderV2":
        """Declare an additional primary/candidate target pin without semantics.

        Deterministic V2 profiles have no attachments, but a candidate Query
        still needs an exact target pin before it can be captured and replayed.
        This is deliberately a target inventory declaration, not a generic
        configuration override or an implicit candidate compiler.
        """

        self._attachment_target(target, side)
        return self

    def for_target(
        self,
        target: _Target,
        *,
        side: _TargetSide,
    ) -> "ExecutionProfileBuilderV2":
        """Alias for :meth:`with_target` for fluent profile declarations."""

        return self.with_target(target, side=side)

    def _attachment_target(
        self,
        target: _Target | None,
        side: _TargetSide | None,
    ) -> tuple[_Target, EvaluationTargetPinV2]:
        selected = (
            self._default_target if target is None else _require_target(target, field_name="target")
        )
        selected_side = (
            self._default_side if side is None else _require_target_side(side, field_name="side")
        )
        pin = _target_pin(selected, side=selected_side)
        previous = self._target_pins.get(selected_side)
        if previous is None:
            self._target_pins[selected_side] = pin
        elif previous != pin:
            raise ProductScenarioExecutionError(
                f"profile already pins a different {selected_side!r} target",
                code="V2_PROFILE_TARGET_SIDE_CONFLICT",
            )
        return selected, pin

    def _assert_no_rule_occurrence_overlap(
        self,
        *,
        kind: Literal["rule", "occurrence"],
        target: EvaluationTargetPinV2,
        rule_id: str,
        rule_version: str | None,
        rule_digest: str,
    ) -> None:
        """Reject two semantic owners for one Rule in one Policy target side.

        A Policy-level Rule attachment and a per-occurrence attachment for
        that same Rule would both configure one lowering slot.  The target
        pin includes the comparison side, so primary/candidate profiles remain
        independently configurable.
        """

        if target.target_kind != "policy":
            return
        conflicting_kind = "occurrence" if kind == "rule" else "rule"
        for existing in self._attachments:
            if (
                existing.kind == conflicting_kind
                and existing.target.pin_digest == target.pin_digest
                and existing.rule_id == rule_id
                and existing.rule_version == rule_version
                and existing.rule_digest == rule_digest
            ):
                raise ProductScenarioExecutionError(
                    "a Policy Rule cannot have both Rule-level and occurrence-level "
                    "ProbLog semantics in the same target side",
                    code="V2_PROFILE_ATTACHMENT_OVERLAP",
                )

    @staticmethod
    def _semantics_marker(
        value: object,
        *,
        expected: str,
    ) -> ExecutionAttachmentSemanticsV2:
        if not isinstance(value, ExecutionAttachmentSemanticsV2) or value.kind != expected:
            raise ProductScenarioExecutionError(
                f"attachment requires fg.problog.{expected.removeprefix('problog_').removesuffix('_v1')}()",
                code="V2_PROFILE_ATTACHMENT_SEMANTICS_INVALID",
            )
        return value

    def for_rule(
        self,
        rule: ProductRuleV1,
        semantics: ExecutionAttachmentSemanticsV2,
        *,
        target: _Target | None = None,
        side: _TargetSide | None = None,
    ) -> "ExecutionProfileBuilderV2":
        """Attach closed ProbLog rule semantics to a direct Rule or Policy member."""

        if self._kind != "problog":
            raise ProductScenarioExecutionError(
                "for_rule(...) is only valid for fg.execution.problog(...)",
                code="V2_PROFILE_ATTACHMENT_UNSUPPORTED",
            )
        if not isinstance(rule, ProductRuleV1):
            raise ProductScenarioExecutionError(
                "for_rule(...) requires a ProductRuleV1",
                code="V2_PROFILE_RULE_REQUIRED",
            )
        selected, target_pin = self._attachment_target(target, side)
        if isinstance(selected, ProductRuleV1):
            if selected.logical_identity_digest != rule.logical_identity_digest:
                raise ProductScenarioExecutionError(
                    "direct Rule attachment must name the profile's exact Rule target",
                    code="V2_PROFILE_RULE_TARGET_MISMATCH",
                )
        elif not _rule_is_occurrence_of_policy(rule, selected):
            raise ProductScenarioExecutionError(
                "Rule attachment is not an occurrence of the selected Policy target",
                code="V2_PROFILE_RULE_TARGET_MISMATCH",
            )
        rule_digest = _rule_digest_token(rule.rule.content_digest)
        self._assert_no_rule_occurrence_overlap(
            kind="rule",
            target=target_pin,
            rule_id=rule.rule.id,
            rule_version=rule.rule.version,
            rule_digest=rule_digest,
        )
        try:
            attachment = ExecutionAttachmentV2(
                kind="rule",
                target=target_pin,
                semantics=self._semantics_marker(semantics, expected="problog_rule_point_v1"),
                rule_id=rule.rule.id,
                rule_version=rule.rule.version,
                rule_digest=rule_digest,
            )
        except ProtocolShapeError as exc:
            raise _as_sdk_error(
                exc, action="Rule attachment", code="V2_PROFILE_ATTACHMENT_INVALID"
            ) from exc
        self._attachments.append(attachment)
        return self

    def for_occurrence(
        self,
        occurrence: PolicyOccurrenceHandle,
        semantics: ExecutionAttachmentSemanticsV2,
        *,
        target: ProductPolicyV1 | None = None,
        side: _TargetSide | None = None,
    ) -> "ExecutionProfileBuilderV2":
        """Attach semantics to one exact, owner-bound Policy occurrence."""

        if self._kind != "problog":
            raise ProductScenarioExecutionError(
                "for_occurrence(...) is only valid for fg.execution.problog(...)",
                code="V2_PROFILE_ATTACHMENT_UNSUPPORTED",
            )
        if not isinstance(occurrence, PolicyOccurrenceHandle):
            raise ProductScenarioExecutionError(
                "for_occurrence(...) requires the handle returned by policy.use(...)",
                code="V2_PROFILE_OCCURRENCE_REQUIRED",
            )
        selected, target_pin = self._attachment_target(target, side)
        if not isinstance(selected, ProductPolicyV1):
            raise ProductScenarioExecutionError(
                "occurrence attachments require a ProductPolicyV1 target context",
                code="V2_PROFILE_POLICY_TARGET_REQUIRED",
            )
        if occurrence._owner is not selected._authoring_owner:
            raise ProductScenarioExecutionError(
                "occurrence handle belongs to a different Policy target",
                code="V2_PROFILE_OCCURRENCE_TARGET_MISMATCH",
            )
        managed = next(
            (
                candidate
                for candidate in selected.address_space.occurrences
                if candidate.occurrence.alias == occurrence.alias
            ),
            None,
        )
        if managed is None or managed.occurrence.rule != occurrence._managed.occurrence.rule:
            raise ProductScenarioExecutionError(
                "occurrence alias/rule does not resolve in the selected Policy target",
                code="V2_PROFILE_OCCURRENCE_TARGET_MISMATCH",
            )
        rule = managed.occurrence.rule
        rule_digest = _rule_digest_token(rule.content_digest)
        self._assert_no_rule_occurrence_overlap(
            kind="occurrence",
            target=target_pin,
            rule_id=rule.id,
            rule_version=rule.version,
            rule_digest=rule_digest,
        )
        try:
            attachment = ExecutionAttachmentV2(
                kind="occurrence",
                target=target_pin,
                semantics=self._semantics_marker(semantics, expected="problog_occurrence_point_v1"),
                rule_id=rule.id,
                rule_version=rule.version,
                rule_digest=rule_digest,
                occurrence_alias=occurrence.alias,
            )
        except ProtocolShapeError as exc:
            raise _as_sdk_error(
                exc, action="occurrence attachment", code="V2_PROFILE_ATTACHMENT_INVALID"
            ) from exc
        self._attachments.append(attachment)
        return self

    def for_choice(
        self,
        choice: WeightedChoiceHandle | WeightedChoiceTopologyV1,
        semantics: ExecutionAttachmentSemanticsV2,
        *,
        target: ProductPolicyV1 | None = None,
        side: _TargetSide | None = None,
    ) -> "ExecutionProfileBuilderV2":
        """Activate one already-authored WeightedChoice without changing weights."""

        if self._kind != "problog":
            raise ProductScenarioExecutionError(
                "for_choice(...) is only valid for fg.execution.problog(...)",
                code="V2_PROFILE_ATTACHMENT_UNSUPPORTED",
            )
        selected, target_pin = self._attachment_target(target, side)
        if not isinstance(selected, ProductPolicyV1):
            raise ProductScenarioExecutionError(
                "choice attachments require a ProductPolicyV1 target context",
                code="V2_PROFILE_POLICY_TARGET_REQUIRED",
            )
        topology = choice.topology if isinstance(choice, WeightedChoiceHandle) else choice
        if not isinstance(topology, WeightedChoiceTopologyV1):
            raise ProductScenarioExecutionError(
                "for_choice(...) requires a WeightedChoice handle/topology",
                code="V2_PROFILE_CHOICE_REQUIRED",
            )
        if topology not in selected.weighted_choices:
            raise ProductScenarioExecutionError(
                "WeightedChoice does not belong to the selected Policy target",
                code="V2_PROFILE_CHOICE_TARGET_MISMATCH",
            )
        try:
            attachment = ExecutionAttachmentV2(
                kind="choice",
                target=target_pin,
                semantics=self._semantics_marker(
                    semantics, expected="problog_choice_activation_v1"
                ),
                structural_node_id=topology.node_id,
            )
        except ProtocolShapeError as exc:
            raise _as_sdk_error(
                exc, action="choice attachment", code="V2_PROFILE_ATTACHMENT_INVALID"
            ) from exc
        self._attachments.append(attachment)
        return self

    def build(self) -> EvaluationExecutionProfileV2:
        """Seal the detached profile; no execution occurs at this call."""

        kind: Literal["native_deterministic_v2", "problog_point_v2"]
        if self._kind == "problog":
            if not isinstance(self._semantics, ProbLogPointSemanticsV2):
                raise ProductScenarioExecutionError(
                    "fg.execution.problog(...).fact_semantics(identity_probability=True) "
                    "must be selected explicitly before build()",
                    code="V2_PROFILE_SEMANTICS_REQUIRED",
                )
            kind = "problog_point_v2"
        else:
            assert isinstance(self._semantics, DeterministicSemanticsV2)
            kind = "native_deterministic_v2"
        try:
            return EvaluationExecutionProfileV2(
                kind=kind,
                name=self._name,
                compiler_digest=_goal_plan_v2_compiler_digest(),
                engines=self._engines,
                semantics=self._semantics,
                resources=self._resources,
                capture=self._capture,
                target_pins=tuple(self._target_pins.values()),
                attachments=tuple(self._attachments),
            )
        except ProtocolShapeError as exc:
            raise _as_sdk_error(
                exc, action="V2 execution profile", code="V2_PROFILE_INVALID"
            ) from exc


class _SDKExecutionManagerV2:
    """Read-only ``fg.execution`` namespace for V2 profile construction."""

    __slots__ = ("_graph",)

    def __init__(self, graph: "SDKStore") -> None:
        object.__setattr__(self, "_graph", graph)

    def __setattr__(self, name: str, value: object) -> None:
        raise FrozenSnapshotError("FactGraph.execution namespace is read-only")

    def native_deterministic(
        self,
        *,
        target: _Target,
        name: str | None = None,
        side: _TargetSide = "primary",
        max_rows: int = 10_000,
        timeout_ms: int | None = None,
        max_capture_bytes: int = 4 * 1024 * 1024,
        native_engine_version: str = DEFAULT_NATIVE_ENGINE_VERSION_V2,
        native_adapter_version: str = DEFAULT_NATIVE_ADAPTER_VERSION_V2,
    ) -> ExecutionProfileBuilderV2:
        """Start the closed native deterministic V2 profile builder."""

        try:
            resources = EvaluationResourcePolicyV2(max_rows=max_rows, timeout_ms=timeout_ms)
            capture = EvaluationCapturePolicyV2(max_capture_bytes=max_capture_bytes)
            engines = (
                EvaluationEnginePinV2("native", native_engine_version, native_adapter_version),
            )
        except ProtocolShapeError as exc:
            raise _as_sdk_error(
                exc, action="native deterministic profile", code="V2_PROFILE_INVALID"
            ) from exc
        return ExecutionProfileBuilderV2(
            target=target,
            side=side,
            kind="native",
            name=name,
            engines=engines,
            resources=resources,
            capture=capture,
        )

    def problog(
        self,
        *,
        target: _Target,
        name: str | None = None,
        side: _TargetSide = "primary",
        max_rows: int = 10_000,
        timeout_ms: int | None = None,
        max_capture_bytes: int = 4 * 1024 * 1024,
        problog_engine_version: str = DEFAULT_PROBLOG_ENGINE_VERSION_V2,
        problog_adapter_version: str = DEFAULT_PROBLOG_ADAPTER_VERSION_V2,
        native_engine_version: str = DEFAULT_NATIVE_ENGINE_VERSION_V2,
        native_adapter_version: str = DEFAULT_NATIVE_ADAPTER_VERSION_V2,
        souffle_engine_version: str = DEFAULT_SOUFFLE_ENGINE_VERSION_V2,
        souffle_adapter_version: str = DEFAULT_SOUFFLE_ADAPTER_VERSION_V2,
    ) -> ExecutionProfileBuilderV2:
        """Start a point-probability ProbLog V2 profile builder.

        The profile pins all three declared engine environments.  It does not
        claim native/Soufflé probability execution; their V2 frames remain
        typed unsupported until a future engine implementation says otherwise.
        """

        try:
            resources = EvaluationResourcePolicyV2(max_rows=max_rows, timeout_ms=timeout_ms)
            capture = EvaluationCapturePolicyV2(max_capture_bytes=max_capture_bytes)
            engines = (
                EvaluationEnginePinV2("problog", problog_engine_version, problog_adapter_version),
                EvaluationEnginePinV2("native", native_engine_version, native_adapter_version),
                EvaluationEnginePinV2("souffle", souffle_engine_version, souffle_adapter_version),
            )
        except ProtocolShapeError as exc:
            raise _as_sdk_error(exc, action="ProbLog profile", code="V2_PROFILE_INVALID") from exc
        return ExecutionProfileBuilderV2(
            target=target,
            side=side,
            kind="problog",
            name=name,
            engines=engines,
            resources=resources,
            capture=capture,
        )


class _SDKProbLogManagerV2:
    """Read-only marker factory for the closed ProbLog V2 attachment union."""

    __slots__ = ("_graph",)

    def __init__(self, graph: "SDKStore") -> None:
        object.__setattr__(self, "_graph", graph)

    def __setattr__(self, name: str, value: object) -> None:
        raise FrozenSnapshotError("FactGraph.problog namespace is read-only")

    def rule_semantics(self) -> ExecutionAttachmentSemanticsV2:
        """Return the sole current direct-Rule ProbLog attachment marker."""

        return ExecutionAttachmentSemanticsV2("problog_rule_point_v1")

    def occurrence_semantics(self) -> ExecutionAttachmentSemanticsV2:
        """Return the sole current Policy-occurrence ProbLog marker."""

        return ExecutionAttachmentSemanticsV2("problog_occurrence_point_v1")

    def choice_semantics(self) -> ExecutionAttachmentSemanticsV2:
        """Return the sole current WeightedChoice activation marker.

        Arm probabilities belong to the authored ``WeightedChoice`` topology;
        this method accepts no probability override by design.
        """

        return ExecutionAttachmentSemanticsV2("problog_choice_activation_v1")


def scenario_builder_v2(graph: "SDKStore") -> ScenarioBuilderV2:
    """Return the public SDK Scenario V2 builder for one graph."""

    return ScenarioBuilderV2(graph)


__all__ = [
    "DEFAULT_NATIVE_ADAPTER_VERSION_V2",
    "DEFAULT_NATIVE_ENGINE_VERSION_V2",
    "DEFAULT_PROBLOG_ADAPTER_VERSION_V2",
    "DEFAULT_PROBLOG_ENGINE_VERSION_V2",
    "DEFAULT_SOUFFLE_ADAPTER_VERSION_V2",
    "DEFAULT_SOUFFLE_ENGINE_VERSION_V2",
    "ExecutionProfileBuilderV2",
    "ProductScenarioExecutionError",
    "ProvenanceLocatorV1",
    "ProvenanceRefV1",
    "ScenarioBuilderV2",
    "_SDKExecutionManagerV2",
    "_SDKProbLogManagerV2",
    "scenario_builder_v2",
]
