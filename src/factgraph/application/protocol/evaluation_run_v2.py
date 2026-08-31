"""Sealed V2 replay/run carriers built on Scenario V2 and V2 profiles.

This is a protocol layer, not an executor.  It holds the material a later
runner must produce/consume: exact V2 profile bytes, captured worlds with both
digest lanes, authored target/asset pins, and typed engine observations.  It
does not call an engine, resolve a policy registry, or turn a probabilistic
observation into a boolean truth claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_non_empty_str
from .execution_profile_v2 import (
    EvaluationEngineV2,
    EvaluationExecutionProfileV2,
    EvaluationTargetPinV2,
    ProbLogPointSemanticsV2,
    assert_evaluation_execution_profile_v2_current,
    evaluation_execution_profile_v2_from_bytes,
)
from .goal_plan_v1 import GoalValueV1
from .provenance_v1 import ProvenanceRefV1
from .scenario_v1 import ScenarioValueV1
from .scenario_v2 import (
    EffectiveWorldFactV2,
    EffectiveWorldV2,
    FactSemanticsV2,
    ResolvedScenarioOperationEvidenceV2,
    ScenarioDisplayV2,
    ScenarioMetaV2,
    ScenarioOperationMetaBindingV2,
    canonical_decimal_v2,
)


EvaluationRunWorldSideV2: TypeAlias = Literal["baseline", "effective", "candidate_effective"]
EvaluationRunFrameStatusV2: TypeAlias = Literal["succeeded", "failed", "unsupported"]
EvaluationExpectationSupportV2: TypeAlias = Literal["not_requested", "unsupported"]
EvaluationProbabilityMaterializationActionV2: TypeAlias = Literal["emitted", "omitted_zero"]

_WORLD_SIDES = frozenset({"baseline", "effective", "candidate_effective"})
_FRAME_STATUSES = frozenset({"succeeded", "failed", "unsupported"})
_EXPECTATION_SUPPORT = frozenset({"not_requested", "unsupported"})
_PROBABILITY_MATERIALIZATION_ACTIONS = frozenset({"emitted", "omitted_zero"})

MAX_EVALUATION_REPLAY_V2_BYTES = 8 * 1024 * 1024
MAX_EVALUATION_REPLAY_V2_DEPTH = 64
MAX_EVALUATION_REPLAY_V2_ROWS = 100_000
MAX_EVALUATION_REPLAY_V2_DESCRIPTOR_BYTES = 64 * 1024


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
    suffix = value[7:]
    if (
        len(suffix) != 64
        or suffix != suffix.lower()
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    return value


def _require_literal(value: object, *, field_name: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProtocolShapeError(f"{field_name} is outside this protocol")
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
            raise ProtocolShapeError("EvaluationRunV2 JSON has duplicate object key")
        output[key] = value
    return output


def _reject_json_constant(value: str) -> object:
    raise ProtocolShapeError(f"EvaluationRunV2 JSON has non-standard constant {value!r}")


def _assert_exact_keys(value: object, expected: frozenset[str], *, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ProtocolShapeError(f"{label} has unsupported or missing fields")
    return value


def _assert_canonical_json_payload(raw: bytes, *, label: str, cap: int) -> object:
    if not isinstance(raw, bytes) or not raw or len(raw) > cap:
        raise ProtocolShapeError(f"{label} bytes are empty or exceed cap")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolShapeError(f"{label} must be canonical UTF-8 JSON") from exc
    if _json_depth(value) > MAX_EVALUATION_REPLAY_V2_DEPTH:
        raise ProtocolShapeError(f"{label} exceeds JSON depth cap")
    if _canonical_json_bytes(value, label=label) != raw:
        raise ProtocolShapeError(f"{label} must be canonical JSON")
    return value


def _value_to_wire(value: ScenarioValueV1) -> dict[str, object]:
    return {"tag": value.tag, "value": value.value}


def _value_from_wire(value: object) -> ScenarioValueV1:
    row = _assert_exact_keys(value, frozenset({"tag", "value"}), label="V2 scenario value")
    return ScenarioValueV1(tag=row["tag"], value=row["value"])  # type: ignore[arg-type]


def _meta_to_wire(
    *,
    semantics: FactSemanticsV2 | None,
    provenance: tuple[ProvenanceRefV1, ...],
    display: ScenarioDisplayV2,
) -> dict[str, object]:
    return {
        "fact_semantics": None if semantics is None else semantics.to_wire(),
        "provenance": [item.to_wire() for item in provenance],
        "display": display.to_wire(),
    }


def _meta_from_wire(
    value: object,
) -> tuple[FactSemanticsV2 | None, tuple[ProvenanceRefV1, ...], ScenarioDisplayV2]:
    row = _assert_exact_keys(
        value,
        frozenset({"fact_semantics", "provenance", "display"}),
        label="V2 world fact metadata",
    )
    raw_semantics = row["fact_semantics"]
    if raw_semantics is None:
        semantics = None
    else:
        semantics_row = _assert_exact_keys(
            raw_semantics,
            frozenset({"raw_kind", "point_probability"}),
            label="V2 world fact semantics",
        )
        semantics = FactSemanticsV2(
            raw_kind=semantics_row["raw_kind"],  # type: ignore[arg-type]
            point_probability=semantics_row["point_probability"],  # type: ignore[arg-type]
        )
    provenance_raw = row["provenance"]
    if not isinstance(provenance_raw, list):
        raise ProtocolShapeError("V2 world fact provenance must be array")
    display_raw = _assert_exact_keys(
        row["display"], frozenset({"note", "labels"}), label="V2 world fact display"
    )
    labels = display_raw["labels"]
    if not isinstance(labels, list):
        raise ProtocolShapeError("V2 world fact display labels must be array")
    return (
        semantics,
        tuple(ProvenanceRefV1.from_wire(item) for item in provenance_raw),
        ScenarioDisplayV2(note=display_raw["note"], labels=tuple(labels)),  # type: ignore[arg-type]
    )


def _fact_to_wire(fact: EffectiveWorldFactV2) -> dict[str, object]:
    return {
        "predicate_id": fact.predicate_id,
        "witness_id": fact.witness_id,
        "values": [_value_to_wire(value) for value in fact.values],
        "origin": fact.origin,
        "meta": _meta_to_wire(
            semantics=fact.fact_semantics,
            provenance=fact.provenance,
            display=fact.display,
        ),
        "premise_ids": list(fact.premise_ids),
        "scenario_operation_digests": list(fact.scenario_operation_digests),
    }


def _fact_from_wire(value: object) -> EffectiveWorldFactV2:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "predicate_id",
                "witness_id",
                "values",
                "origin",
                "meta",
                "premise_ids",
                "scenario_operation_digests",
            }
        ),
        label="V2 world fact",
    )
    values = row["values"]
    premise_ids = row["premise_ids"]
    operation_digests = row["scenario_operation_digests"]
    if (
        not isinstance(values, list)
        or not isinstance(premise_ids, list)
        or not isinstance(operation_digests, list)
    ):
        raise ProtocolShapeError("V2 world fact sequence is malformed")
    semantics, provenance, display = _meta_from_wire(row["meta"])
    return EffectiveWorldFactV2(
        predicate_id=row["predicate_id"],  # type: ignore[arg-type]
        witness_id=row["witness_id"],  # type: ignore[arg-type]
        values=tuple(_value_from_wire(item) for item in values),
        origin=row["origin"],  # type: ignore[arg-type]
        fact_semantics=semantics,
        provenance=provenance,
        display=display,
        premise_ids=tuple(premise_ids),  # type: ignore[arg-type]
        scenario_operation_digests=tuple(operation_digests),  # type: ignore[arg-type]
    )


def _operation_evidence_to_wire(
    evidence: ResolvedScenarioOperationEvidenceV2,
) -> dict[str, object]:
    return {
        "kind": evidence.kind,
        "resolved_operation_digest": evidence.resolved_operation_digest,
        "metadata_bindings": [
            {
                "premise_id": binding.premise_id,
                "source_operation_digest": binding.source_operation_digest,
                "member_value_digest": binding.member_value_digest,
                "meta": _meta_to_wire(
                    semantics=binding.meta.fact_semantics,
                    provenance=binding.meta.provenance,
                    display=binding.meta.display,
                ),
            }
            for binding in evidence.metadata_bindings
        ],
        "masked_witness_ids": list(evidence.masked_witness_ids),
        "synthetic_witness_ids": list(evidence.synthetic_witness_ids),
    }


def _operation_evidence_from_wire(value: object) -> ResolvedScenarioOperationEvidenceV2:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "kind",
                "resolved_operation_digest",
                "metadata_bindings",
                "masked_witness_ids",
                "synthetic_witness_ids",
            }
        ),
        label="V2 resolved Scenario operation evidence",
    )
    bindings_raw = row["metadata_bindings"]
    masked = row["masked_witness_ids"]
    synthetic = row["synthetic_witness_ids"]
    if (
        not isinstance(bindings_raw, list)
        or not isinstance(masked, list)
        or not isinstance(synthetic, list)
    ):
        raise ProtocolShapeError("V2 resolved Scenario operation evidence sequences are malformed")
    bindings: list[ScenarioOperationMetaBindingV2] = []
    for index, item in enumerate(bindings_raw):
        item_row = _assert_exact_keys(
            item,
            frozenset({"premise_id", "source_operation_digest", "member_value_digest", "meta"}),
            label=f"V2 Scenario metadata binding[{index}]",
        )
        semantics, provenance, display = _meta_from_wire(item_row["meta"])
        bindings.append(
            ScenarioOperationMetaBindingV2(
                premise_id=item_row["premise_id"],  # type: ignore[arg-type]
                source_operation_digest=item_row["source_operation_digest"],  # type: ignore[arg-type]
                member_value_digest=item_row["member_value_digest"],  # type: ignore[arg-type]
                meta=ScenarioMetaV2(
                    fact_semantics=semantics,
                    provenance=provenance,
                    display=display,
                ),
            )
        )
    return ResolvedScenarioOperationEvidenceV2(
        kind=row["kind"],  # type: ignore[arg-type]
        resolved_operation_digest=row["resolved_operation_digest"],  # type: ignore[arg-type]
        metadata_bindings=tuple(bindings),
        masked_witness_ids=tuple(masked),  # type: ignore[arg-type]
        synthetic_witness_ids=tuple(synthetic),  # type: ignore[arg-type]
    )


def _world_to_wire(world: EffectiveWorldV2) -> dict[str, object]:
    return {
        "schema_digest": world.schema_digest,
        "base_view_digest": world.base_view_digest,
        "admissibility_digest": world.admissibility_digest,
        "dependency_predicate_ids": list(world.dependency_predicate_ids),
        "facts": [_fact_to_wire(item) for item in world.facts],
        "closure_target_digests": list(world.closure_target_digests),
        "operation_evidence": [
            _operation_evidence_to_wire(item) for item in world.operation_evidence
        ],
    }


def _world_from_wire(value: object) -> EffectiveWorldV2:
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "schema_digest",
                "base_view_digest",
                "admissibility_digest",
                "dependency_predicate_ids",
                "facts",
                "closure_target_digests",
                "operation_evidence",
            }
        ),
        label="V2 replay world",
    )
    predicates = row["dependency_predicate_ids"]
    facts = row["facts"]
    closures = row["closure_target_digests"]
    operation_evidence = row["operation_evidence"]
    if (
        not isinstance(predicates, list)
        or not isinstance(facts, list)
        or not isinstance(closures, list)
        or not isinstance(operation_evidence, list)
    ):
        raise ProtocolShapeError("V2 replay world sequences are malformed")
    return EffectiveWorldV2(
        schema_digest=row["schema_digest"],  # type: ignore[arg-type]
        base_view_digest=row["base_view_digest"],  # type: ignore[arg-type]
        admissibility_digest=row["admissibility_digest"],  # type: ignore[arg-type]
        dependency_predicate_ids=tuple(predicates),  # type: ignore[arg-type]
        facts=tuple(_fact_from_wire(item) for item in facts),
        closure_target_digests=tuple(closures),  # type: ignore[arg-type]
        operation_evidence=tuple(
            _operation_evidence_from_wire(item) for item in operation_evidence
        ),
    )


def _assert_effective_world_v2_current(world: EffectiveWorldV2) -> None:
    """Rebuild a captured world and compare every cached V2 digest lane.

    ``EffectiveWorldV2`` is a frozen public DTO, not a tamper-proof object.
    This helper deliberately decodes a new world from its raw wire instead of
    invoking ``__post_init__`` on the caller object, which would otherwise
    overwrite stale derived identities.
    """

    if not isinstance(world, EffectiveWorldV2):
        raise ProtocolShapeError("EvaluationReplayWorldV2.world must be EffectiveWorldV2")
    fresh_world = _world_from_wire(_world_to_wire(world))
    for name in (
        "semantic_relation_digest",
        "resolution_relation_digest",
        "semantic_world_digest",
        "resolution_evidence_digest",
        "world_digest",
    ):
        if getattr(fresh_world, name) != getattr(world, name):
            raise ProtocolShapeError("EvaluationReplayWorldV2 world seal is stale")


@dataclass(frozen=True)
class EvaluationReplayWorldV2:
    """One named V2 world capture; it seals both semantic/evidence lanes."""

    side: EvaluationRunWorldSideV2
    world: EffectiveWorldV2
    world_capture_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.side, field_name="EvaluationReplayWorldV2.side", allowed=_WORLD_SIDES)
        _assert_effective_world_v2_current(self.world)
        expected_digest = _token(
            "evaluation_replay_world_v2",
            {
                "side": self.side,
                "semantic_world_digest": self.world.semantic_world_digest,
                "resolution_evidence_digest": self.world.resolution_evidence_digest,
                "world_digest": self.world.world_digest,
            },
        )
        if hasattr(self, "world_capture_digest"):
            if self.world_capture_digest != expected_digest:
                raise ProtocolShapeError("EvaluationReplayWorldV2.world_capture_digest is stale")
            return
        object.__setattr__(self, "world_capture_digest", expected_digest)

    def to_wire(self) -> dict[str, object]:
        return {"side": self.side, "world": _world_to_wire(self.world)}


def _assert_replay_world_v2_current(value: EvaluationReplayWorldV2) -> None:
    if not isinstance(value, EvaluationReplayWorldV2):
        raise ProtocolShapeError("EvaluationReplayPayloadV2 world is malformed")
    _assert_effective_world_v2_current(value.world)
    fresh = EvaluationReplayWorldV2(side=value.side, world=value.world)
    if fresh.world_capture_digest != value.world_capture_digest:
        raise ProtocolShapeError("EvaluationReplayPayloadV2 world capture seal is stale")


@dataclass(frozen=True)
class EvaluationRunPlanV2:
    """A V2 query target + asset + address-space capture.

    Candidate programs may legitimately compile against a different Policy
    address space than the primary target.  The per-plan pin keeps replay from
    accidentally treating the primary address space as a global invariant.
    """

    target: EvaluationTargetPinV2
    query_digest: str
    asset_descriptor_bytes: bytes | None
    asset_descriptor_digest: str | None
    asset_binding_digest: str
    address_space_digest: str
    plan_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.target, EvaluationTargetPinV2):
            raise ProtocolShapeError("EvaluationRunPlanV2.target must be EvaluationTargetPinV2")
        fresh_target = EvaluationTargetPinV2(
            side=self.target.side,
            target_kind=self.target.target_kind,
            target_id=self.target.target_id,
            target_version=self.target.target_version,
            target_digest=self.target.target_digest,
        )
        if fresh_target.pin_digest != self.target.pin_digest:
            raise ProtocolShapeError("EvaluationRunPlanV2 target pin seal is stale")
        _require_token(self.query_digest, field_name="EvaluationRunPlanV2.query_digest")
        _require_token(
            self.asset_binding_digest, field_name="EvaluationRunPlanV2.asset_binding_digest"
        )
        _require_token(
            self.address_space_digest, field_name="EvaluationRunPlanV2.address_space_digest"
        )
        if (self.asset_descriptor_bytes is None) != (self.asset_descriptor_digest is None):
            raise ProtocolShapeError(
                "EvaluationRunPlanV2 asset descriptor fields must appear together"
            )
        if self.asset_descriptor_bytes is not None:
            descriptor = _assert_canonical_json_payload(
                self.asset_descriptor_bytes,
                label="EvaluationRunPlanV2 asset descriptor",
                cap=MAX_EVALUATION_REPLAY_V2_DESCRIPTOR_BYTES,
            )
            _require_token(
                self.asset_descriptor_digest,
                field_name="EvaluationRunPlanV2.asset_descriptor_digest",
            )
            _validate_asset_descriptor_v1(
                descriptor,
                expected_digest=self.asset_descriptor_digest,
            )
            descriptor_capture_digest = f"sha256:{sha256_hex(self.asset_descriptor_bytes)}"
        else:
            descriptor_capture_digest = None
        expected_digest = _token(
            "evaluation_run_plan_v2",
            {
                "target_pin": self.target.pin_digest,
                "query_digest": self.query_digest,
                "asset_descriptor_digest": self.asset_descriptor_digest,
                "asset_descriptor_capture_digest": descriptor_capture_digest,
                "asset_binding_digest": self.asset_binding_digest,
                "address_space_digest": self.address_space_digest,
            },
        )
        if hasattr(self, "plan_digest"):
            if self.plan_digest != expected_digest:
                raise ProtocolShapeError("EvaluationRunPlanV2.plan_digest is stale")
            return
        object.__setattr__(self, "plan_digest", expected_digest)


def _assert_run_plan_v2_current(value: EvaluationRunPlanV2) -> None:
    if not isinstance(value, EvaluationRunPlanV2):
        raise ProtocolShapeError("EvaluationRunV2 plan is malformed")
    fresh = EvaluationRunPlanV2(
        target=value.target,
        query_digest=value.query_digest,
        asset_descriptor_bytes=value.asset_descriptor_bytes,
        asset_descriptor_digest=value.asset_descriptor_digest,
        asset_binding_digest=value.asset_binding_digest,
        address_space_digest=value.address_space_digest,
    )
    if fresh.plan_digest != value.plan_digest:
        raise ProtocolShapeError("EvaluationRunV2 plan seal is stale")


def _validate_asset_descriptor_v1(value: object, *, expected_digest: str | None) -> None:
    """Validate the one public AssetMeta descriptor wire retained by V2 runs.

    A run plan is registry-free, but a descriptor is not an arbitrary JSON
    attachment.  The product runner separately proves the descriptor/binding
    association against a live Product asset; this protocol guard prevents a
    malformed or unrelated object from becoming durable replay material.
    """

    row = _assert_exact_keys(
        value,
        frozenset({"format", "name", "description", "tags"}),
        label="EvaluationRunPlanV2 asset descriptor",
    )
    if row["format"] != "asset_meta_v1":
        raise ProtocolShapeError("EvaluationRunPlanV2 asset descriptor format is unsupported")
    if not isinstance(row["name"], str) or not row["name"]:
        raise ProtocolShapeError("EvaluationRunPlanV2 asset descriptor name is malformed")
    if row["description"] is not None and not isinstance(row["description"], str):
        raise ProtocolShapeError("EvaluationRunPlanV2 asset descriptor description is malformed")
    tags = row["tags"]
    if not isinstance(tags, list) or not all(isinstance(item, str) and item for item in tags):
        raise ProtocolShapeError("EvaluationRunPlanV2 asset descriptor tags are malformed")
    if tags != sorted(set(tags)):
        raise ProtocolShapeError("EvaluationRunPlanV2 asset descriptor tags are not canonical")
    if expected_digest != _token("asset_meta_v1", value):
        raise ProtocolShapeError(
            "EvaluationRunPlanV2 asset descriptor digest does not match descriptor bytes"
        )


@dataclass(frozen=True)
class EvaluationSelectedRowV2:
    """Value-only selected identity plus a separately sealed point observation."""

    values: tuple[tuple[str, GoalValueV1], ...]
    point_probability: str | None = None
    row_identity_digest: str = field(init=False)
    observation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple) or not self.values:
            raise ProtocolShapeError("EvaluationSelectedRowV2.values must be non-empty tuple")
        normalized: list[tuple[str, GoalValueV1]] = []
        for index, item in enumerate(self.values):
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not isinstance(item[1], GoalValueV1)
            ):
                raise ProtocolShapeError(
                    f"EvaluationSelectedRowV2.values[{index}] must be (str, GoalValueV1)"
                )
            _require_non_empty_str(
                item[0], field_name=f"EvaluationSelectedRowV2.values[{index}].alias"
            )
            fresh_value = GoalValueV1(item[1].tag, item[1].value)
            if fresh_value.value_digest != item[1].value_digest:
                raise ProtocolShapeError("EvaluationSelectedRowV2 selected value seal is stale")
            normalized.append(item)
        canonical = tuple(sorted(normalized, key=lambda item: item[0]))
        if len({alias for alias, _ in canonical}) != len(canonical):
            raise ProtocolShapeError("EvaluationSelectedRowV2 aliases must be unique")
        if self.point_probability is not None:
            probability = canonical_decimal_v2(
                self.point_probability, field_name="EvaluationSelectedRowV2.point_probability"
            )
            if probability != self.point_probability:
                raise ProtocolShapeError(
                    "EvaluationSelectedRowV2.point_probability is not canonical"
                )
            if Decimal(probability) < 0 or Decimal(probability) > 1:
                raise ProtocolShapeError(
                    "EvaluationSelectedRowV2.point_probability must be in [0, 1]"
                )
        identity = _token(
            "evaluation_selected_row_v2_identity",
            tuple((alias, value.value_digest) for alias, value in canonical),
        )
        observation_digest = _token(
            "evaluation_selected_row_v2_observation",
            {"row_identity_digest": identity, "point_probability": self.point_probability},
        )
        if hasattr(self, "row_identity_digest") or hasattr(self, "observation_digest"):
            if (
                self.values != canonical
                or getattr(self, "row_identity_digest", None) != identity
                or getattr(self, "observation_digest", None) != observation_digest
            ):
                raise ProtocolShapeError("EvaluationSelectedRowV2 row seal is stale")
            return
        object.__setattr__(self, "values", canonical)
        object.__setattr__(self, "row_identity_digest", identity)
        object.__setattr__(self, "observation_digest", observation_digest)


@dataclass(frozen=True)
class BranchWitnessV2:
    """Provider-neutral proof-path witness captured before row de-duplication.

    ``compiled_branch_id`` belongs to the sealed FactGraph target.  It is not
    a Meander Policy/Branch identity and carries no matched/unknown business
    classification.
    """

    compiled_branch_id: str
    evaluation_side: EvaluationRunWorldSideV2
    row_identity_digest: str
    proof_identity_digest: str
    evidence_references: tuple[str, ...]
    witness_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.compiled_branch_id, field_name="BranchWitnessV2.compiled_branch_id"
        )
        _require_literal(
            self.evaluation_side,
            field_name="BranchWitnessV2.evaluation_side",
            allowed=_WORLD_SIDES,
        )
        _require_token(
            self.row_identity_digest, field_name="BranchWitnessV2.row_identity_digest"
        )
        _require_token(
            self.proof_identity_digest, field_name="BranchWitnessV2.proof_identity_digest"
        )
        if not isinstance(self.evidence_references, tuple) or not self.evidence_references:
            raise ProtocolShapeError(
                "BranchWitnessV2.evidence_references must be canonical sha256 tokens"
            )
        for item in self.evidence_references:
            _require_token(item, field_name="BranchWitnessV2.evidence_reference")
        if tuple(sorted(set(self.evidence_references))) != self.evidence_references:
            raise ProtocolShapeError(
                "BranchWitnessV2.evidence_references must be canonical sha256 tokens"
            )
        expected = _token(
            "branch_witness_v2",
            {
                "compiled_branch_id": self.compiled_branch_id,
                "evaluation_side": self.evaluation_side,
                "row_identity_digest": self.row_identity_digest,
                "proof_identity_digest": self.proof_identity_digest,
                "evidence_references": self.evidence_references,
            },
        )
        if hasattr(self, "witness_digest"):
            if self.witness_digest != expected:
                raise ProtocolShapeError("BranchWitnessV2.witness_digest is stale")
            return
        object.__setattr__(self, "witness_digest", expected)


@dataclass(frozen=True)
class EvaluationFunctionCallV2:
    """One sealed pure Function call materialized before engine execution."""

    occurrence_alias: str
    function_digest: str
    implementation_digest: str
    relation_predicate_id: str
    call_key: str
    inputs: tuple[tuple[str, GoalValueV1], ...]
    output: tuple[str, GoalValueV1]
    call_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("occurrence_alias", "relation_predicate_id", "call_key"):
            _require_non_empty_str(
                getattr(self, name), field_name=f"EvaluationFunctionCallV2.{name}"
            )
        for name in ("function_digest", "implementation_digest"):
            _require_token(getattr(self, name), field_name=f"EvaluationFunctionCallV2.{name}")
        if not isinstance(self.inputs, tuple) or not self.inputs:
            raise ProtocolShapeError("EvaluationFunctionCallV2.inputs must be non-empty tuple")
        normalized: list[tuple[str, GoalValueV1]] = []
        for name, value in self.inputs:
            _require_non_empty_str(name, field_name="EvaluationFunctionCallV2.inputs.name")
            fresh = GoalValueV1(value.tag, value.value)
            if fresh.value_digest != value.value_digest:
                raise ProtocolShapeError("EvaluationFunctionCallV2 input value seal is stale")
            normalized.append((name, value))
        inputs = tuple(sorted(normalized, key=lambda item: item[0]))
        if len({name for name, _value in inputs}) != len(inputs):
            raise ProtocolShapeError("EvaluationFunctionCallV2 input names must be unique")
        if (
            not isinstance(self.output, tuple)
            or len(self.output) != 2
            or not isinstance(self.output[0], str)
            or not isinstance(self.output[1], GoalValueV1)
        ):
            raise ProtocolShapeError("EvaluationFunctionCallV2.output is malformed")
        _require_non_empty_str(self.output[0], field_name="EvaluationFunctionCallV2.output.name")
        fresh_output = GoalValueV1(self.output[1].tag, self.output[1].value)
        if fresh_output.value_digest != self.output[1].value_digest:
            raise ProtocolShapeError("EvaluationFunctionCallV2 output value seal is stale")
        expected = _token(
            "evaluation_function_call_v2",
            {
                "occurrence_alias": self.occurrence_alias,
                "function_digest": self.function_digest,
                "implementation_digest": self.implementation_digest,
                "relation_predicate_id": self.relation_predicate_id,
                "call_key": self.call_key,
                "inputs": tuple((name, value.value_digest) for name, value in inputs),
                "output": (self.output[0], self.output[1].value_digest),
            },
        )
        if hasattr(self, "call_digest"):
            if self.inputs != inputs or self.call_digest != expected:
                raise ProtocolShapeError("EvaluationFunctionCallV2 seal is stale")
            return
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "call_digest", expected)


@dataclass(frozen=True)
class EvaluationFunctionMaterializationV2:
    """All calls for one Function occurrence in one captured world side."""

    occurrence_alias: str
    function_digest: str
    signature_digest: str
    implementation_digest: str
    relation_predicate_id: str
    ports: tuple[tuple[str, str, Literal["input", "output"]], ...]
    calls: tuple[EvaluationFunctionCallV2, ...]
    materialization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.occurrence_alias,
            field_name="EvaluationFunctionMaterializationV2.occurrence_alias",
        )
        _require_non_empty_str(
            self.relation_predicate_id,
            field_name="EvaluationFunctionMaterializationV2.relation_predicate_id",
        )
        for name in ("function_digest", "signature_digest", "implementation_digest"):
            _require_token(
                getattr(self, name),
                field_name=f"EvaluationFunctionMaterializationV2.{name}",
            )
        if not isinstance(self.ports, tuple) or len(self.ports) < 2:
            raise ProtocolShapeError("EvaluationFunctionMaterializationV2.ports are malformed")
        ports: list[tuple[str, str, Literal["input", "output"]]] = []
        for item in self.ports:
            if (
                not isinstance(item, tuple)
                or len(item) != 3
                or not isinstance(item[0], str)
                or item[1] not in {"string", "int", "float64", "bool", "time", "uuid"}
                or item[2] not in {"input", "output"}
            ):
                raise ProtocolShapeError("EvaluationFunctionMaterializationV2 port is malformed")
            _require_non_empty_str(
                item[0], field_name="EvaluationFunctionMaterializationV2.ports.name"
            )
            ports.append(item)  # type: ignore[arg-type]
        if (
            len({name for name, _tag, _mode in ports}) != len(ports)
            or sum(mode == "output" for _name, _tag, mode in ports) != 1
            or ports[-1][2] != "output"
            or any(mode != "input" for _name, _tag, mode in ports[:-1])
        ):
            raise ProtocolShapeError(
                "EvaluationFunctionMaterializationV2 ports must be ordered inputs plus one output"
            )
        canonical_ports = tuple(ports)
        if not isinstance(self.calls, tuple) or not all(
            isinstance(item, EvaluationFunctionCallV2) for item in self.calls
        ):
            raise ProtocolShapeError("EvaluationFunctionMaterializationV2.calls are malformed")
        calls = tuple(sorted(self.calls, key=lambda item: item.call_digest))
        if len({item.call_digest for item in calls}) != len(calls):
            raise ProtocolShapeError("EvaluationFunctionMaterializationV2 calls must be unique")
        if any(
            item.occurrence_alias != self.occurrence_alias
            or item.function_digest != self.function_digest
            or item.implementation_digest != self.implementation_digest
            or item.relation_predicate_id != self.relation_predicate_id
            or tuple((name, value.tag, "input") for name, value in item.inputs)
            != canonical_ports[:-1]
            or (item.output[0], item.output[1].tag, "output") != canonical_ports[-1]
            for item in calls
        ):
            raise ProtocolShapeError("EvaluationFunctionMaterializationV2 call pins mismatch")
        expected = _token(
            "evaluation_function_materialization_v2",
            {
                "occurrence_alias": self.occurrence_alias,
                "function_digest": self.function_digest,
                "signature_digest": self.signature_digest,
                "implementation_digest": self.implementation_digest,
                "relation_predicate_id": self.relation_predicate_id,
                "ports": canonical_ports,
                "calls": tuple(item.call_digest for item in calls),
            },
        )
        if hasattr(self, "materialization_digest"):
            if (
                self.ports != canonical_ports
                or self.calls != calls
                or self.materialization_digest != expected
            ):
                raise ProtocolShapeError("EvaluationFunctionMaterializationV2 seal is stale")
            return
        object.__setattr__(self, "calls", calls)
        object.__setattr__(self, "ports", canonical_ports)
        object.__setattr__(self, "materialization_digest", expected)


def _assert_selected_row_v2_current(value: EvaluationSelectedRowV2) -> None:
    if not isinstance(value, EvaluationSelectedRowV2):
        raise ProtocolShapeError("EvaluationEngineFrameV2 observation is malformed")
    fresh = EvaluationSelectedRowV2(values=value.values, point_probability=value.point_probability)
    if (
        fresh.row_identity_digest != value.row_identity_digest
        or fresh.observation_digest != value.observation_digest
        or fresh.values != value.values
    ):
        raise ProtocolShapeError("EvaluationEngineFrameV2 observation seal is stale")


@dataclass(frozen=True)
class EvaluationProbabilityMaterializationEntryV2:
    """One declared Scenario point as materialized for the current ProbLog adapter.

    The V2 world keeps ``declared_point_probability`` as a canonical Decimal
    string.  ProbLog currently consumes binary floats, so the result carrier
    makes that loss of decimal precision explicit rather than implying that
    the engine observed the original declaration.  ``float64_hex`` is the
    exact binary projection; ``float64_text``/``problog_text`` are its stable
    shortest decimal spellings used for presentation and source generation.
    """

    fact_evidence_digest: str
    declared_point_probability: str
    float64_hex: str
    float64_text: str
    problog_text: str | None
    action: EvaluationProbabilityMaterializationActionV2
    entry_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(
            self.fact_evidence_digest,
            field_name="EvaluationProbabilityMaterializationEntryV2.fact_evidence_digest",
        )
        declared = canonical_decimal_v2(
            self.declared_point_probability,
            field_name="EvaluationProbabilityMaterializationEntryV2.declared_point_probability",
        )
        if declared != self.declared_point_probability or not (
            Decimal("0") <= Decimal(declared) <= Decimal("1")
        ):
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2 declared probability is invalid"
            )
        if not isinstance(self.float64_hex, str) or not self.float64_hex:
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2.float64_hex is malformed"
            )
        if not isinstance(self.float64_text, str) or not self.float64_text:
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2.float64_text is malformed"
            )
        if self.action not in _PROBABILITY_MATERIALIZATION_ACTIONS:
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2.action is unsupported"
            )
        try:
            projected = float(Decimal(declared))
            from_hex = float.fromhex(self.float64_hex)
        except (ValueError, OverflowError) as exc:
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2 float64 carrier is invalid"
            ) from exc
        if (
            projected != from_hex
            or projected.hex() != self.float64_hex
            or repr(projected) != self.float64_text
            or not 0.0 <= projected <= 1.0
        ):
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2 does not match its declared decimal"
            )
        if self.action == "emitted":
            if Decimal(declared) <= 0 or self.problog_text != self.float64_text:
                raise ProtocolShapeError(
                    "EvaluationProbabilityMaterializationEntryV2 emitted projection is invalid"
                )
        elif Decimal(declared) != 0 or self.problog_text is not None:
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationEntryV2 zero omission is invalid"
            )
        expected_digest = _token(
            "evaluation_probability_materialization_entry_v2",
            {
                "fact_evidence_digest": self.fact_evidence_digest,
                "declared_point_probability": declared,
                "float64_hex": self.float64_hex,
                "float64_text": self.float64_text,
                "problog_text": self.problog_text,
                "action": self.action,
            },
        )
        if hasattr(self, "entry_digest"):
            if self.entry_digest != expected_digest:
                raise ProtocolShapeError(
                    "EvaluationProbabilityMaterializationEntryV2.entry_digest is stale"
                )
            return
        object.__setattr__(self, "entry_digest", expected_digest)


def _assert_probability_materialization_entry_v2_current(
    value: EvaluationProbabilityMaterializationEntryV2,
) -> None:
    if not isinstance(value, EvaluationProbabilityMaterializationEntryV2):
        raise ProtocolShapeError("EvaluationProbabilityMaterializationV2 entry is malformed")
    fresh = EvaluationProbabilityMaterializationEntryV2(
        fact_evidence_digest=value.fact_evidence_digest,
        declared_point_probability=value.declared_point_probability,
        float64_hex=value.float64_hex,
        float64_text=value.float64_text,
        problog_text=value.problog_text,
        action=value.action,
    )
    if fresh.entry_digest != value.entry_digest:
        raise ProtocolShapeError("EvaluationProbabilityMaterializationV2 entry seal is stale")


@dataclass(frozen=True)
class EvaluationProbabilityMaterializationV2:
    """Sealed per-world input projection for ``problog_point_v2``.

    Empty entries are meaningful: they state that the profile used the
    float64 materializer but the captured world had no declared probabilistic
    facts.  WeightedChoice lowering has its own captured topology/program
    carrier and is deliberately not relabelled as a Scenario fact projection.
    """

    model: Literal["problog_float64_v1"]
    entries: tuple[EvaluationProbabilityMaterializationEntryV2, ...] = ()
    materialization_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.model != "problog_float64_v1":
            raise ProtocolShapeError("EvaluationProbabilityMaterializationV2.model is unsupported")
        if not isinstance(self.entries, tuple) or not all(
            isinstance(item, EvaluationProbabilityMaterializationEntryV2) for item in self.entries
        ):
            raise ProtocolShapeError("EvaluationProbabilityMaterializationV2.entries are malformed")
        for item in self.entries:
            _assert_probability_materialization_entry_v2_current(item)
        entries = tuple(sorted(self.entries, key=lambda item: item.fact_evidence_digest))
        if len({item.fact_evidence_digest for item in entries}) != len(entries):
            raise ProtocolShapeError(
                "EvaluationProbabilityMaterializationV2 entries must have unique fact witnesses"
            )
        expected_digest = _token(
            "evaluation_probability_materialization_v2",
            {
                "model": self.model,
                "entries": tuple(item.entry_digest for item in entries),
            },
        )
        if hasattr(self, "materialization_digest"):
            if self.entries != entries or self.materialization_digest != expected_digest:
                raise ProtocolShapeError("EvaluationProbabilityMaterializationV2 seal is stale")
            return
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "materialization_digest", expected_digest)


def _assert_probability_materialization_v2_current(
    value: EvaluationProbabilityMaterializationV2,
) -> None:
    if not isinstance(value, EvaluationProbabilityMaterializationV2):
        raise ProtocolShapeError("EvaluationEngineFrameV2 probability materialization is malformed")
    fresh = EvaluationProbabilityMaterializationV2(model=value.model, entries=value.entries)
    if (
        fresh.materialization_digest != value.materialization_digest
        or fresh.entries != value.entries
    ):
        raise ProtocolShapeError(
            "EvaluationEngineFrameV2 probability materialization seal is stale"
        )


def problog_probability_materialization_v2_from_world(
    world: EffectiveWorldV2,
) -> EvaluationProbabilityMaterializationV2:
    """Project declared V2 fact decimals through the current ProbLog boundary.

    This is intentionally a pure protocol function.  Both the isolated runner
    and :class:`EvaluationRunV2` call it, which prevents a sealed frame from
    claiming a convenient decimal that the actual float64 materialization did
    not use.  A declared ``0`` is retained in the world but omitted from the
    generated ProbLog EDB because that adapter cannot encode ``0::fact``.
    """

    if not isinstance(world, EffectiveWorldV2):
        raise ProtocolShapeError("world must be EffectiveWorldV2")
    entries: list[EvaluationProbabilityMaterializationEntryV2] = []
    for fact in world.facts:
        semantics = fact.fact_semantics
        if semantics is None:
            continue
        declared = semantics.point_probability
        try:
            projected = float(Decimal(declared))
        except (
            ValueError,
            OverflowError,
        ) as exc:  # pragma: no cover - FactSemanticsV2 guards range.
            raise ProtocolShapeError("V2 declared point cannot materialize to float64") from exc
        if not 0.0 <= projected <= 1.0:
            raise ProtocolShapeError("V2 declared point cannot materialize to float64")
        action: EvaluationProbabilityMaterializationActionV2 = (
            "omitted_zero" if Decimal(declared) == 0 else "emitted"
        )
        entries.append(
            EvaluationProbabilityMaterializationEntryV2(
                fact_evidence_digest=fact.evidence_fact_digest,
                declared_point_probability=declared,
                float64_hex=projected.hex(),
                float64_text=repr(projected),
                problog_text=None if action == "omitted_zero" else repr(projected),
                action=action,
            )
        )
    return EvaluationProbabilityMaterializationV2(
        model="problog_float64_v1", entries=tuple(entries)
    )


@dataclass(frozen=True)
class EvaluationEngineFrameV2:
    """One typed engine outcome; unsupported frames never fabricate rows."""

    engine: EvaluationEngineV2
    status: EvaluationRunFrameStatusV2
    observations: tuple[EvaluationSelectedRowV2, ...] = ()
    diagnostic_code: str = "EVALUATION_ENGINE_SUCCEEDED"
    probability_materialization: EvaluationProbabilityMaterializationV2 | None = None
    branch_witnesses: tuple[BranchWitnessV2, ...] = ()
    frame_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(
            self.engine,
            field_name="EvaluationEngineFrameV2.engine",
            allowed=frozenset({"native", "souffle", "problog"}),
        )
        _require_literal(
            self.status, field_name="EvaluationEngineFrameV2.status", allowed=_FRAME_STATUSES
        )
        _require_non_empty_str(
            self.diagnostic_code, field_name="EvaluationEngineFrameV2.diagnostic_code"
        )
        if (
            not isinstance(self.observations, tuple)
            or len(self.observations) > MAX_EVALUATION_REPLAY_V2_ROWS
            or not all(isinstance(item, EvaluationSelectedRowV2) for item in self.observations)
        ):
            raise ProtocolShapeError("EvaluationEngineFrameV2 observations are malformed")
        for item in self.observations:
            _assert_selected_row_v2_current(item)
        observations = tuple(sorted(self.observations, key=lambda item: item.observation_digest))
        if len({item.observation_digest for item in observations}) != len(observations):
            raise ProtocolShapeError("EvaluationEngineFrameV2 observations must be unique")
        if not isinstance(self.branch_witnesses, tuple) or not all(
            isinstance(item, BranchWitnessV2) for item in self.branch_witnesses
        ):
            raise ProtocolShapeError("EvaluationEngineFrameV2 branch witnesses are malformed")
        witnesses = tuple(
            sorted(self.branch_witnesses, key=lambda item: item.witness_digest)
        )
        if len({item.witness_digest for item in witnesses}) != len(witnesses):
            raise ProtocolShapeError("EvaluationEngineFrameV2 branch witnesses must be unique")
        observation_ids = {item.row_identity_digest for item in observations}
        if any(item.row_identity_digest not in observation_ids for item in witnesses):
            raise ProtocolShapeError("branch witness row is absent from the engine frame")
        if self.status == "succeeded":
            if self.diagnostic_code != "EVALUATION_ENGINE_SUCCEEDED":
                raise ProtocolShapeError(
                    "successful EvaluationEngineFrameV2 has failure diagnostic"
                )
        elif observations or witnesses or self.diagnostic_code == "EVALUATION_ENGINE_SUCCEEDED":
            raise ProtocolShapeError("failed/unsupported EvaluationEngineFrameV2 cannot carry rows")
        if self.probability_materialization is not None:
            if (
                self.engine != "problog"
                or self.status != "succeeded"
                or not isinstance(
                    self.probability_materialization,
                    EvaluationProbabilityMaterializationV2,
                )
            ):
                raise ProtocolShapeError(
                    "probability materialization is only valid for a successful ProbLog frame"
                )
            _assert_probability_materialization_v2_current(self.probability_materialization)
        digest_payload: dict[str, object] = {
            "engine": self.engine,
            "status": self.status,
            "observations": tuple(item.observation_digest for item in observations),
            "diagnostic_code": self.diagnostic_code,
            "probability_materialization": None
            if self.probability_materialization is None
            else self.probability_materialization.materialization_digest,
        }
        # Preserve every pre-witness V2 frame digest.  The extension is sealed
        # only when a branch-aware target actually captures witnesses.
        if witnesses:
            digest_payload["branch_witnesses"] = tuple(
                item.witness_digest for item in witnesses
            )
        expected_digest = _token("evaluation_engine_frame_v2", digest_payload)
        if hasattr(self, "frame_digest"):
            if (
                self.observations != observations
                or self.branch_witnesses != witnesses
                or self.frame_digest != expected_digest
            ):
                raise ProtocolShapeError("EvaluationEngineFrameV2.frame_digest is stale")
            return
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "branch_witnesses", witnesses)
        object.__setattr__(self, "frame_digest", expected_digest)


def _assert_engine_frame_v2_current(value: EvaluationEngineFrameV2) -> None:
    if not isinstance(value, EvaluationEngineFrameV2):
        raise ProtocolShapeError("EvaluationRunSideV2 engine frame is malformed")
    fresh = EvaluationEngineFrameV2(
        engine=value.engine,
        status=value.status,
        observations=value.observations,
        diagnostic_code=value.diagnostic_code,
        probability_materialization=value.probability_materialization,
        branch_witnesses=value.branch_witnesses,
    )
    if fresh.frame_digest != value.frame_digest or fresh.observations != value.observations:
        raise ProtocolShapeError("EvaluationRunSideV2 engine frame seal is stale")


@dataclass(frozen=True)
class EvaluationRunSideV2:
    """One baseline/effective/candidate result side with exact world/plan pins."""

    name: EvaluationRunWorldSideV2
    plan_digest: str
    world_capture_digest: str
    engine_frames: tuple[EvaluationEngineFrameV2, ...]
    expectation_support: EvaluationExpectationSupportV2 = "not_requested"
    function_materializations: tuple[EvaluationFunctionMaterializationV2, ...] = ()
    side_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_literal(self.name, field_name="EvaluationRunSideV2.name", allowed=_WORLD_SIDES)
        _require_token(self.plan_digest, field_name="EvaluationRunSideV2.plan_digest")
        _require_token(
            self.world_capture_digest, field_name="EvaluationRunSideV2.world_capture_digest"
        )
        if not isinstance(self.engine_frames, tuple) or not all(
            isinstance(item, EvaluationEngineFrameV2) for item in self.engine_frames
        ):
            raise ProtocolShapeError("EvaluationRunSideV2.engine_frames are malformed")
        for item in self.engine_frames:
            _assert_engine_frame_v2_current(item)
        if len({item.engine for item in self.engine_frames}) != len(self.engine_frames):
            raise ProtocolShapeError("EvaluationRunSideV2 engine frames must be unique")
        if not isinstance(self.function_materializations, tuple) or not all(
            isinstance(item, EvaluationFunctionMaterializationV2)
            for item in self.function_materializations
        ):
            raise ProtocolShapeError("EvaluationRunSideV2 function materializations are malformed")
        function_materializations = tuple(
            sorted(self.function_materializations, key=lambda item: item.occurrence_alias)
        )
        if len({item.occurrence_alias for item in function_materializations}) != len(
            function_materializations
        ):
            raise ProtocolShapeError("EvaluationRunSideV2 Function occurrences must be unique")
        _require_literal(
            self.expectation_support,
            field_name="EvaluationRunSideV2.expectation_support",
            allowed=_EXPECTATION_SUPPORT,
        )
        expected_digest = _token(
            "evaluation_run_side_v2",
            {
                "name": self.name,
                "plan_digest": self.plan_digest,
                "world_capture_digest": self.world_capture_digest,
                "frames": tuple(item.frame_digest for item in self.engine_frames),
                "expectation_support": self.expectation_support,
                "function_materializations": tuple(
                    item.materialization_digest for item in function_materializations
                ),
            },
        )
        if hasattr(self, "side_digest"):
            if (
                self.function_materializations != function_materializations
                or self.side_digest != expected_digest
            ):
                raise ProtocolShapeError("EvaluationRunSideV2.side_digest is stale")
            return
        object.__setattr__(self, "function_materializations", function_materializations)
        object.__setattr__(self, "side_digest", expected_digest)


def _assert_run_side_v2_current(value: EvaluationRunSideV2) -> None:
    if not isinstance(value, EvaluationRunSideV2):
        raise ProtocolShapeError("EvaluationRunV2 side is malformed")
    fresh = EvaluationRunSideV2(
        name=value.name,
        plan_digest=value.plan_digest,
        world_capture_digest=value.world_capture_digest,
        engine_frames=value.engine_frames,
        expectation_support=value.expectation_support,
        function_materializations=value.function_materializations,
    )
    if fresh.side_digest != value.side_digest:
        raise ProtocolShapeError("EvaluationRunV2 side seal is stale")


@dataclass(frozen=True)
class EvaluationReplayPayloadV2:
    """Detached V2 replay material with full profile bytes and captured worlds."""

    schema_digest: str
    address_space_digest: str
    profile_bytes: bytes
    compiled_program_bytes: bytes
    worlds: tuple[EvaluationReplayWorldV2, ...]
    profile_digest: str = field(init=False)
    payload_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.schema_digest, field_name="EvaluationReplayPayloadV2.schema_digest")
        _require_token(
            self.address_space_digest, field_name="EvaluationReplayPayloadV2.address_space_digest"
        )
        profile = evaluation_execution_profile_v2_from_bytes(self.profile_bytes)
        _assert_canonical_json_payload(
            self.compiled_program_bytes,
            label="EvaluationReplayPayloadV2 compiled program",
            cap=MAX_EVALUATION_REPLAY_V2_BYTES,
        )
        if (
            not isinstance(self.worlds, tuple)
            or len(self.worlds) not in {2, 3}
            or not all(isinstance(item, EvaluationReplayWorldV2) for item in self.worlds)
        ):
            raise ProtocolShapeError("EvaluationReplayPayloadV2 worlds are malformed")
        for item in self.worlds:
            _assert_replay_world_v2_current(item)
        worlds = tuple(sorted(self.worlds, key=lambda item: item.side))
        sides = tuple(item.side for item in worlds)
        if sides not in {
            ("baseline", "effective"),
            ("baseline", "candidate_effective", "effective"),
        }:
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV2 worlds must include baseline/effective"
            )
        if any(item.world.schema_digest != self.schema_digest for item in worlds):
            raise ProtocolShapeError("EvaluationReplayPayloadV2 world schema digest mismatch")
        # A V2 replay is one captured view plus an optional Scenario overlay.
        # Baseline/effective may intentionally differ in their facts, fact
        # semantics, premise lanes, and operation evidence, but they must
        # never be assembled from different captured views or different
        # admission/dependency inventories.  A candidate changes only the
        # compiled product program, so it must execute against the *identical*
        # sealed effective world rather than a look-alike world.
        baseline = next(item.world for item in worlds if item.side == "baseline")
        effective = next(item.world for item in worlds if item.side == "effective")
        if (
            baseline.schema_digest != effective.schema_digest
            or baseline.base_view_digest != effective.base_view_digest
            or baseline.admissibility_digest != effective.admissibility_digest
            or baseline.dependency_predicate_ids != effective.dependency_predicate_ids
        ):
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV2 baseline/effective worlds do not share one capture basis"
            )
        candidate = next(
            (item.world for item in worlds if item.side == "candidate_effective"), None
        )
        if candidate is not None and candidate.world_digest != effective.world_digest:
            raise ProtocolShapeError(
                "EvaluationReplayPayloadV2 candidate effective world must exactly equal effective world"
            )
        expected_profile_digest = profile.profile_digest
        expected_payload_digest = _token(
            "evaluation_replay_payload_v2",
            {
                "schema_digest": self.schema_digest,
                "address_space_digest": self.address_space_digest,
                "profile_digest": expected_profile_digest,
                "profile_bytes_digest": f"sha256:{sha256_hex(self.profile_bytes)}",
                "compiled_program_bytes_digest": f"sha256:{sha256_hex(self.compiled_program_bytes)}",
                "worlds": tuple(item.world_capture_digest for item in worlds),
            },
        )
        # Do not turn an explicit direct __post_init__ call into a reseal
        # primitive.  Public validators rebuild fresh objects instead.  This
        # guard also makes direct protocol use safe after hostile frozen-data
        # mutation: cached identities must describe the current raw payload.
        if hasattr(self, "profile_digest") or hasattr(self, "payload_digest"):
            if (
                self.worlds != worlds
                or getattr(self, "profile_digest", None) != expected_profile_digest
                or getattr(self, "payload_digest", None) != expected_payload_digest
            ):
                raise ProtocolShapeError("EvaluationReplayPayloadV2 payload seal is stale")
            return
        object.__setattr__(self, "worlds", worlds)
        object.__setattr__(self, "profile_digest", expected_profile_digest)
        object.__setattr__(self, "payload_digest", expected_payload_digest)

    def world(self, side: EvaluationRunWorldSideV2) -> EvaluationReplayWorldV2:
        for item in self.worlds:
            if item.side == side:
                return item
        raise ProtocolShapeError(f"EvaluationReplayPayloadV2 lacks world side {side!r}")


@dataclass(frozen=True)
class EvaluationRunV2:
    """Completed V2 run carrier; construction verifies only sealed protocol links."""

    primary_plan: EvaluationRunPlanV2
    profile: EvaluationExecutionProfileV2
    replay_payload: EvaluationReplayPayloadV2
    baseline: EvaluationRunSideV2
    effective: EvaluationRunSideV2
    candidate_plan: EvaluationRunPlanV2 | None = None
    candidate_effective: EvaluationRunSideV2 | None = None
    run_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.primary_plan, EvaluationRunPlanV2):
            raise ProtocolShapeError("EvaluationRunV2.primary_plan is malformed")
        if not isinstance(self.profile, EvaluationExecutionProfileV2):
            raise ProtocolShapeError("EvaluationRunV2.profile is malformed")
        if not isinstance(self.replay_payload, EvaluationReplayPayloadV2):
            raise ProtocolShapeError("EvaluationRunV2.replay_payload is malformed")
        _assert_run_plan_v2_current(self.primary_plan)
        assert_evaluation_execution_profile_v2_current(self.profile)
        # This name is intentionally resolved at call time.  It is defined
        # below with the public payload serializer and rebuilds nested worlds
        # rather than invoking __post_init__ on the supplied payload.
        assert_evaluation_replay_payload_v2_current(self.replay_payload)
        _assert_run_side_v2_current(self.baseline)
        _assert_run_side_v2_current(self.effective)
        if self.profile.profile_digest != self.replay_payload.profile_digest:
            raise ProtocolShapeError(
                "EvaluationRunV2 replay profile bytes do not match run profile"
            )
        if self.primary_plan.target.side != "primary":
            raise ProtocolShapeError(
                "EvaluationRunV2 primary target must explicitly use primary side"
            )
        if self.primary_plan.address_space_digest != self.replay_payload.address_space_digest:
            raise ProtocolShapeError(
                "EvaluationRunV2 replay payload must pin the primary plan address space"
            )
        profile_pins = {item.pin_digest for item in self.profile.target_pins}
        if self.primary_plan.target.pin_digest not in profile_pins:
            raise ProtocolShapeError(
                "EvaluationRunV2 primary target is not declared by profile target pins"
            )
        self._validate_side(self.baseline, "baseline", self.primary_plan)
        self._validate_side(self.effective, "effective", self.primary_plan)
        if (self.candidate_plan is None) != (self.candidate_effective is None):
            raise ProtocolShapeError("EvaluationRunV2 candidate plan/side must appear together")
        if self.candidate_plan is not None:
            assert self.candidate_effective is not None
            _assert_run_plan_v2_current(self.candidate_plan)
            _assert_run_side_v2_current(self.candidate_effective)
            if self.candidate_plan.target.side != "candidate":
                raise ProtocolShapeError(
                    "EvaluationRunV2 candidate target must explicitly use candidate side"
                )
            if self.candidate_plan.target.pin_digest not in profile_pins:
                raise ProtocolShapeError(
                    "EvaluationRunV2 candidate target is not declared by profile target pins"
                )
            self._validate_side(
                self.candidate_effective, "candidate_effective", self.candidate_plan
            )
        self._validate_frames()
        expected_digest = _token(
            "evaluation_run_v2",
            {
                "primary_plan": self.primary_plan.plan_digest,
                "profile": self.profile.profile_digest,
                "payload": self.replay_payload.payload_digest,
                "baseline": self.baseline.side_digest,
                "effective": self.effective.side_digest,
                "candidate_plan": None
                if self.candidate_plan is None
                else self.candidate_plan.plan_digest,
                "candidate_effective": None
                if self.candidate_effective is None
                else self.candidate_effective.side_digest,
            },
        )
        if hasattr(self, "run_digest"):
            if self.run_digest != expected_digest:
                raise ProtocolShapeError("EvaluationRunV2.run_digest is stale")
            return
        object.__setattr__(self, "run_digest", expected_digest)

    def _validate_side(
        self,
        side: EvaluationRunSideV2,
        expected_name: EvaluationRunWorldSideV2,
        plan: EvaluationRunPlanV2,
    ) -> None:
        if not isinstance(side, EvaluationRunSideV2):
            raise ProtocolShapeError("EvaluationRunV2 side is malformed")
        world = self.replay_payload.world(expected_name)
        if (
            side.name != expected_name
            or side.plan_digest != plan.plan_digest
            or side.world_capture_digest != world.world_capture_digest
        ):
            raise ProtocolShapeError("EvaluationRunV2 side does not match plan/world capture")

    def _validate_frames(self) -> None:
        expected_engines = tuple(item.engine for item in self.profile.engines)
        for side in (self.baseline, self.effective, self.candidate_effective):
            if side is None:
                continue
            frames = {item.engine: item for item in side.engine_frames}
            if tuple(item.engine for item in side.engine_frames) != expected_engines:
                raise ProtocolShapeError("EvaluationRunV2 frame engines do not match profile")
            if self.profile.kind == "native_deterministic_v2":
                if frames["native"].status != "succeeded":
                    raise ProtocolShapeError("native deterministic V2 run requires native success")
            elif self.profile.kind == "portable_deterministic_v2":
                if any(frames[engine].status != "succeeded" for engine in expected_engines):
                    raise ProtocolShapeError(
                        "portable deterministic V2 run requires all three engine successes"
                    )
                if any(
                    observation.point_probability is not None
                    for frame in frames.values()
                    for observation in frame.observations
                ) or any(
                    frame.probability_materialization is not None for frame in frames.values()
                ):
                    raise ProtocolShapeError(
                        "portable deterministic V2 frames cannot carry probability semantics"
                    )
            else:
                if not isinstance(self.profile.semantics, ProbLogPointSemanticsV2):
                    raise ProtocolShapeError("ProbLog point V2 run has malformed profile semantics")
                if (
                    frames["problog"].status != "succeeded"
                    or frames["native"].status != "unsupported"
                    or frames["souffle"].status != "unsupported"
                ):
                    raise ProtocolShapeError(
                        "ProbLog point V2 run requires ProbLog result and explicit unsupported frames"
                    )
                if any(item.point_probability is None for item in frames["problog"].observations):
                    raise ProtocolShapeError(
                        "ProbLog point V2 rows require explicit point certainty"
                    )
                materialization = frames["problog"].probability_materialization
                if not isinstance(materialization, EvaluationProbabilityMaterializationV2):
                    raise ProtocolShapeError(
                        "ProbLog point V2 run requires its float64 materialization capture"
                    )
                if materialization.model != self.profile.semantics.materialization:
                    raise ProtocolShapeError(
                        "ProbLog point V2 materialization does not match profile semantics"
                    )
                expected_materialization = problog_probability_materialization_v2_from_world(
                    self.replay_payload.world(side.name).world
                )
                if materialization != expected_materialization:
                    raise ProtocolShapeError(
                        "ProbLog point V2 materialization does not match its captured world"
                    )
                if (
                    frames["native"].probability_materialization is not None
                    or frames["souffle"].probability_materialization is not None
                ):
                    raise ProtocolShapeError(
                        "unsupported V2 engine frames cannot carry probability materialization"
                    )
                if side.expectation_support != "unsupported":
                    raise ProtocolShapeError(
                        "ProbLog point V2 expectations are currently unsupported"
                    )


def _rebuild_run_plan_v2(value: EvaluationRunPlanV2) -> EvaluationRunPlanV2:
    if not isinstance(value, EvaluationRunPlanV2):
        raise ProtocolShapeError("EvaluationRunV2 plan is malformed")
    fresh = EvaluationRunPlanV2(
        target=EvaluationTargetPinV2(
            side=value.target.side,
            target_kind=value.target.target_kind,
            target_id=value.target.target_id,
            target_version=value.target.target_version,
            target_digest=value.target.target_digest,
        ),
        query_digest=value.query_digest,
        asset_descriptor_bytes=value.asset_descriptor_bytes,
        asset_descriptor_digest=value.asset_descriptor_digest,
        asset_binding_digest=value.asset_binding_digest,
        address_space_digest=value.address_space_digest,
    )
    if fresh.plan_digest != value.plan_digest:
        raise ProtocolShapeError("EvaluationRunPlanV2 plan seal is stale")
    return fresh


def _rebuild_probability_materialization_v2(
    value: EvaluationProbabilityMaterializationV2 | None,
) -> EvaluationProbabilityMaterializationV2 | None:
    if value is None:
        return None
    if not isinstance(value, EvaluationProbabilityMaterializationV2):
        raise ProtocolShapeError("EvaluationRunV2 probability materialization is malformed")
    entries = tuple(
        EvaluationProbabilityMaterializationEntryV2(
            fact_evidence_digest=item.fact_evidence_digest,
            declared_point_probability=item.declared_point_probability,
            float64_hex=item.float64_hex,
            float64_text=item.float64_text,
            problog_text=item.problog_text,
            action=item.action,
        )
        for item in value.entries
    )
    fresh = EvaluationProbabilityMaterializationV2(model=value.model, entries=entries)
    if fresh.materialization_digest != value.materialization_digest:
        raise ProtocolShapeError("EvaluationRunV2 probability materialization seal is stale")
    return fresh


def _rebuild_selected_row_v2(value: EvaluationSelectedRowV2) -> EvaluationSelectedRowV2:
    if not isinstance(value, EvaluationSelectedRowV2):
        raise ProtocolShapeError("EvaluationRunV2 selected row is malformed")
    values: list[tuple[str, GoalValueV1]] = []
    for item in value.values:
        if not isinstance(item, tuple) or len(item) != 2 or not isinstance(item[1], GoalValueV1):
            raise ProtocolShapeError("EvaluationRunV2 selected row values are malformed")
        alias, goal_value = item
        fresh_value = GoalValueV1(goal_value.tag, goal_value.value)
        if fresh_value.value_digest != goal_value.value_digest:
            raise ProtocolShapeError("EvaluationRunV2 selected value seal is stale")
        values.append((alias, fresh_value))
    fresh = EvaluationSelectedRowV2(tuple(values), point_probability=value.point_probability)
    if (
        fresh.row_identity_digest != value.row_identity_digest
        or fresh.observation_digest != value.observation_digest
    ):
        raise ProtocolShapeError("EvaluationRunV2 selected row seal is stale")
    return fresh


def _rebuild_engine_frame_v2(value: EvaluationEngineFrameV2) -> EvaluationEngineFrameV2:
    if not isinstance(value, EvaluationEngineFrameV2):
        raise ProtocolShapeError("EvaluationRunV2 engine frame is malformed")
    fresh = EvaluationEngineFrameV2(
        engine=value.engine,
        status=value.status,
        observations=tuple(_rebuild_selected_row_v2(item) for item in value.observations),
        diagnostic_code=value.diagnostic_code,
        probability_materialization=_rebuild_probability_materialization_v2(
            value.probability_materialization
        ),
        branch_witnesses=tuple(
            BranchWitnessV2(
                compiled_branch_id=item.compiled_branch_id,
                evaluation_side=item.evaluation_side,
                row_identity_digest=item.row_identity_digest,
                proof_identity_digest=item.proof_identity_digest,
                evidence_references=item.evidence_references,
            )
            for item in value.branch_witnesses
        ),
    )
    if fresh.frame_digest != value.frame_digest:
        raise ProtocolShapeError("EvaluationRunV2 engine frame seal is stale")
    return fresh


def _rebuild_function_materialization_v2(
    value: EvaluationFunctionMaterializationV2,
) -> EvaluationFunctionMaterializationV2:
    if not isinstance(value, EvaluationFunctionMaterializationV2):
        raise ProtocolShapeError("EvaluationRunV2 Function materialization is malformed")
    calls = tuple(
        EvaluationFunctionCallV2(
            occurrence_alias=item.occurrence_alias,
            function_digest=item.function_digest,
            implementation_digest=item.implementation_digest,
            relation_predicate_id=item.relation_predicate_id,
            call_key=item.call_key,
            inputs=tuple(
                (name, GoalValueV1(port_value.tag, port_value.value))
                for name, port_value in item.inputs
            ),
            output=(
                item.output[0],
                GoalValueV1(item.output[1].tag, item.output[1].value),
            ),
        )
        for item in value.calls
    )
    fresh = EvaluationFunctionMaterializationV2(
        occurrence_alias=value.occurrence_alias,
        function_digest=value.function_digest,
        signature_digest=value.signature_digest,
        implementation_digest=value.implementation_digest,
        relation_predicate_id=value.relation_predicate_id,
        ports=value.ports,
        calls=calls,
    )
    if fresh.materialization_digest != value.materialization_digest:
        raise ProtocolShapeError("EvaluationRunV2 Function materialization seal is stale")
    return fresh


def _rebuild_run_side_v2(value: EvaluationRunSideV2) -> EvaluationRunSideV2:
    if not isinstance(value, EvaluationRunSideV2):
        raise ProtocolShapeError("EvaluationRunV2 side is malformed")
    fresh = EvaluationRunSideV2(
        name=value.name,
        plan_digest=value.plan_digest,
        world_capture_digest=value.world_capture_digest,
        engine_frames=tuple(_rebuild_engine_frame_v2(item) for item in value.engine_frames),
        expectation_support=value.expectation_support,
        function_materializations=tuple(
            _rebuild_function_materialization_v2(item) for item in value.function_materializations
        ),
    )
    if fresh.side_digest != value.side_digest:
        raise ProtocolShapeError("EvaluationRunV2 side seal is stale")
    return fresh


def _rebuild_replay_world_v2(value: EvaluationReplayWorldV2) -> EvaluationReplayWorldV2:
    if not isinstance(value, EvaluationReplayWorldV2):
        raise ProtocolShapeError("EvaluationRunV2 replay world is malformed")
    # The strict world codec rebuilds every V2 fact/meta/provenance lane from
    # raw public values; it never invokes __post_init__ on the caller object.
    fresh_world = _world_from_wire(_world_to_wire(value.world))
    for name in (
        "semantic_relation_digest",
        "resolution_relation_digest",
        "semantic_world_digest",
        "resolution_evidence_digest",
        "world_digest",
    ):
        if getattr(fresh_world, name) != getattr(value.world, name):
            raise ProtocolShapeError("EvaluationRunV2 replay world seal is stale")
    fresh = EvaluationReplayWorldV2(side=value.side, world=fresh_world)
    if fresh.world_capture_digest != value.world_capture_digest:
        raise ProtocolShapeError("EvaluationRunV2 replay world capture seal is stale")
    return fresh


def _rebuild_replay_payload_v2(value: EvaluationReplayPayloadV2) -> EvaluationReplayPayloadV2:
    if not isinstance(value, EvaluationReplayPayloadV2):
        raise ProtocolShapeError("EvaluationRunV2 replay payload is malformed")
    fresh = EvaluationReplayPayloadV2(
        schema_digest=value.schema_digest,
        address_space_digest=value.address_space_digest,
        profile_bytes=value.profile_bytes,
        compiled_program_bytes=value.compiled_program_bytes,
        worlds=tuple(_rebuild_replay_world_v2(item) for item in value.worlds),
    )
    if (
        fresh.profile_digest != value.profile_digest
        or fresh.payload_digest != value.payload_digest
        or fresh.worlds != value.worlds
    ):
        raise ProtocolShapeError("EvaluationRunV2 replay payload seal is stale")
    return fresh


def assert_evaluation_replay_payload_v2_current(payload: EvaluationReplayPayloadV2) -> None:
    """Verify a sealed replay payload without mutating or resealing it.

    This is deliberately narrower than :func:`assert_evaluation_run_v2_current`:
    it is useful to callers that persist or transport a detached payload before
    constructing a result carrier.  In particular, it rebuilds every captured
    world and its nested Scenario metadata from raw wire, then compares all
    cached digest lanes.  Never call ``__post_init__`` on the caller object
    here: doing so could bless an altered payload with fresh cached identities.
    """

    _rebuild_replay_payload_v2(payload)


def assert_evaluation_run_v2_current(run: EvaluationRunV2) -> None:
    """Recursively verify a sealed V2 run without resealing caller objects.

    This is the one public integrity gate for detached replay and product
    presentation.  It rebuilds every derived-digest carrier from raw fields,
    compares cached identities, and then validates the fresh run's cross-links.
    Calling any live ``__post_init__`` would be unsafe here because it could
    overwrite a stale digest after hostile mutation.
    """

    if not isinstance(run, EvaluationRunV2):
        raise ProtocolShapeError("run must be EvaluationRunV2")
    assert_evaluation_execution_profile_v2_current(run.profile)
    if run.replay_payload.profile_bytes != run.profile.to_bytes():
        raise ProtocolShapeError("EvaluationRunV2 profile bytes are stale or spliced")
    fresh_payload = _rebuild_replay_payload_v2(run.replay_payload)
    primary_plan = _rebuild_run_plan_v2(run.primary_plan)
    candidate_plan = (
        None if run.candidate_plan is None else _rebuild_run_plan_v2(run.candidate_plan)
    )
    fresh = EvaluationRunV2(
        primary_plan=primary_plan,
        profile=run.profile,
        replay_payload=fresh_payload,
        baseline=_rebuild_run_side_v2(run.baseline),
        effective=_rebuild_run_side_v2(run.effective),
        candidate_plan=candidate_plan,
        candidate_effective=(
            None
            if run.candidate_effective is None
            else _rebuild_run_side_v2(run.candidate_effective)
        ),
    )
    if fresh.run_digest != run.run_digest:
        raise ProtocolShapeError("EvaluationRunV2 run seal is stale")


def _payload_to_wire(payload: EvaluationReplayPayloadV2) -> dict[str, object]:
    return {
        "$type": "EvaluationReplayPayloadV2",
        "schema_digest": payload.schema_digest,
        "address_space_digest": payload.address_space_digest,
        "profile_bytes": payload.profile_bytes.decode("utf-8"),
        "compiled_program_bytes": payload.compiled_program_bytes.decode("utf-8"),
        "worlds": [item.to_wire() for item in payload.worlds],
    }


def evaluation_replay_payload_v2_bytes(payload: EvaluationReplayPayloadV2) -> bytes:
    if not isinstance(payload, EvaluationReplayPayloadV2):
        raise ProtocolShapeError("payload must be EvaluationReplayPayloadV2")
    assert_evaluation_replay_payload_v2_current(payload)
    raw = _canonical_json_bytes(_payload_to_wire(payload), label="EvaluationReplayPayloadV2")
    if len(raw) > MAX_EVALUATION_REPLAY_V2_BYTES:
        raise ProtocolShapeError("EvaluationReplayPayloadV2 exceeds wire size cap")
    return raw


def evaluation_replay_payload_v2_from_bytes(raw: bytes) -> EvaluationReplayPayloadV2:
    value = _assert_canonical_json_payload(
        raw, label="EvaluationReplayPayloadV2", cap=MAX_EVALUATION_REPLAY_V2_BYTES
    )
    row = _assert_exact_keys(
        value,
        frozenset(
            {
                "$type",
                "schema_digest",
                "address_space_digest",
                "profile_bytes",
                "compiled_program_bytes",
                "worlds",
            }
        ),
        label="EvaluationReplayPayloadV2",
    )
    if row["$type"] != "EvaluationReplayPayloadV2":
        raise ProtocolShapeError("EvaluationReplayPayloadV2 type is invalid")
    if not isinstance(row["profile_bytes"], str) or not isinstance(
        row["compiled_program_bytes"], str
    ):
        raise ProtocolShapeError("EvaluationReplayPayloadV2 embedded bytes must be strings")
    worlds_raw = row["worlds"]
    if not isinstance(worlds_raw, list):
        raise ProtocolShapeError("EvaluationReplayPayloadV2 worlds must be array")
    worlds: list[EvaluationReplayWorldV2] = []
    for index, item in enumerate(worlds_raw):
        item_row = _assert_exact_keys(
            item, frozenset({"side", "world"}), label=f"EvaluationReplayPayloadV2 world[{index}]"
        )
        worlds.append(
            EvaluationReplayWorldV2(
                side=item_row["side"],  # type: ignore[arg-type]
                world=_world_from_wire(item_row["world"]),
            )
        )
    return EvaluationReplayPayloadV2(
        schema_digest=row["schema_digest"],  # type: ignore[arg-type]
        address_space_digest=row["address_space_digest"],  # type: ignore[arg-type]
        profile_bytes=row["profile_bytes"].encode("utf-8"),
        compiled_program_bytes=row["compiled_program_bytes"].encode("utf-8"),
        worlds=tuple(worlds),
    )


__all__ = [
    "BranchWitnessV2",
    "EvaluationEngineFrameV2",
    "EvaluationExpectationSupportV2",
    "EvaluationProbabilityMaterializationActionV2",
    "EvaluationProbabilityMaterializationEntryV2",
    "EvaluationProbabilityMaterializationV2",
    "EvaluationFunctionCallV2",
    "EvaluationFunctionMaterializationV2",
    "EvaluationReplayPayloadV2",
    "EvaluationReplayWorldV2",
    "EvaluationRunFrameStatusV2",
    "EvaluationRunPlanV2",
    "EvaluationRunSideV2",
    "EvaluationRunV2",
    "EvaluationRunWorldSideV2",
    "EvaluationSelectedRowV2",
    "MAX_EVALUATION_REPLAY_V2_BYTES",
    "MAX_EVALUATION_REPLAY_V2_DEPTH",
    "MAX_EVALUATION_REPLAY_V2_DESCRIPTOR_BYTES",
    "MAX_EVALUATION_REPLAY_V2_ROWS",
    "evaluation_replay_payload_v2_bytes",
    "evaluation_replay_payload_v2_from_bytes",
    "problog_probability_materialization_v2_from_world",
    "assert_evaluation_replay_payload_v2_current",
    "assert_evaluation_run_v2_current",
]
