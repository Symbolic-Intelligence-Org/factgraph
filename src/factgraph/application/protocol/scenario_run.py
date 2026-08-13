"""Detached, replacement-only ScenarioRun protocol values.

``ScenarioRunV0`` is deliberately separate from ``EvaluateResult.scenario``.
The older compatibility path reports a hypothetical result but has no captured
evidence contract.  This protocol owns two captured *relations* (baseline and
effective) and explicitly records that an effective synthetic witness is a
caller-declared hypothesis rather than a ledger assertion.

The opaque capture bytes are an implementation payload.  They are sealed into
the outer record but are not exposed as an ``EvaluationRunBundleV0`` API.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
import json
from typing import Any, Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError, _require_bool, _require_non_empty_str
from .evaluation_run_bundle import EvaluationRunValueV0
from .evaluation_run_verification import EvaluationRunVerificationV0
from .evaluation_scenario import ScenarioResultDiffV0, ScenarioScalarValueV0
from .policy_explanation import PolicyExplanationViewV0
from .schema_runtime import FieldPath


ScenarioRunSide: TypeAlias = Literal["baseline", "effective"]
ScenarioOriginKind: TypeAlias = Literal[
    "scenario_hypothesis_v0",
    "scenario_hypothesis_set_v0",
]


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


def _canonical_token(label: str, payload: object) -> str:
    try:
        raw = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:  # pragma: no cover - constructor guards
        raise ProtocolShapeError("ScenarioRun protocol payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(raw)}"


@dataclass(frozen=True)
class ScenarioPremiseBindingV0:
    """One resolver-produced mapping from a premise to its synthetic witness.

    This is a capture-time identity map, not a claim of premise truth.  It is
    deliberately produced by the trusted Scenario resolver rather than inferred
    later from an assertion-id prefix.
    """

    premise_id: str
    operation_digest: str
    origin_kind: ScenarioOriginKind
    entity_ref: str
    field: FieldPath
    predicate_id: str
    baseline_assertion_id: str
    synthetic_witness_id: str
    baseline_value: ScenarioScalarValueV0
    effective_value: ScenarioScalarValueV0
    semantic_value_changed: bool
    binding_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "premise_id",
            "entity_ref",
            "predicate_id",
            "baseline_assertion_id",
            "synthetic_witness_id",
        ):
            _require_non_empty_str(getattr(self, name), field_name=f"Scenario premise {name}")
        _sha256_token(self.operation_digest, "Scenario premise operation_digest")
        if self.origin_kind not in {
            "scenario_hypothesis_v0",
            "scenario_hypothesis_set_v0",
        }:
            raise ProtocolShapeError("Scenario premise origin_kind is invalid")
        if not isinstance(self.field, FieldPath):
            raise ProtocolShapeError("Scenario premise field must be FieldPath")
        if not isinstance(self.baseline_value, ScenarioScalarValueV0) or not isinstance(
            self.effective_value, ScenarioScalarValueV0
        ):
            raise ProtocolShapeError("Scenario premise values must be ScenarioScalarValueV0")
        if self.baseline_value.tag != self.effective_value.tag:
            raise ProtocolShapeError("Scenario premise values must have the same scalar tag")
        _require_bool(
            self.semantic_value_changed,
            field_name="Scenario premise semantic_value_changed",
        )
        if self.semantic_value_changed != (self.baseline_value != self.effective_value):
            raise ProtocolShapeError(
                "Scenario premise semantic_value_changed must match canonical values"
            )
        object.__setattr__(
            self,
            "binding_digest",
            _canonical_token(
                "scenario_premise_binding_v0",
                {
                    "premise_id": self.premise_id,
                    "operation_digest": self.operation_digest,
                    "origin_kind": self.origin_kind,
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


@dataclass(frozen=True)
class ScenarioRunPlanV0:
    """Pinned execution contract for one bounded replacement-only ScenarioRun."""

    query_digest: str
    target_digest: str
    policy_digest: str
    address_space_digest: str
    schema_digest: str
    base_view_digest: str
    baseline_relation_digest: str
    effective_relation_digest: str
    scenario_kind: Literal["single_field_replacement", "atomic_field_replacement_set"]
    premise_bindings: tuple[ScenarioPremiseBindingV0, ...]
    engine: Literal["native"] = "native"
    config: Literal["none"] = "none"
    ledger_premise_policy: Literal["empty"] = "empty"
    overlay_kind: Literal["replacement_only_v0"] = "replacement_only_v0"
    plan_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        for name in ("query_digest", "policy_digest", "address_space_digest"):
            _sha256_hex(getattr(self, name), f"ScenarioRun plan {name}")
        for name in (
            "target_digest",
            "schema_digest",
            "base_view_digest",
            "baseline_relation_digest",
            "effective_relation_digest",
        ):
            _sha256_token(getattr(self, name), f"ScenarioRun plan {name}")
        if self.scenario_kind not in {
            "single_field_replacement",
            "atomic_field_replacement_set",
        }:
            raise ProtocolShapeError("ScenarioRun plan scenario_kind is invalid")
        if not isinstance(self.premise_bindings, tuple) or not self.premise_bindings or not all(
            isinstance(item, ScenarioPremiseBindingV0) for item in self.premise_bindings
        ):
            raise ProtocolShapeError("ScenarioRun plan requires premise bindings")
        premise_ids = tuple(item.premise_id for item in self.premise_bindings)
        targets = tuple(
            (item.entity_ref, item.predicate_id, item.baseline_assertion_id)
            for item in self.premise_bindings
        )
        canonical = tuple(
            sorted(
                self.premise_bindings,
                key=lambda item: (
                    item.entity_ref,
                    item.field.entity_type,
                    item.field.field_name,
                ),
            )
        )
        if self.premise_bindings != canonical:
            raise ProtocolShapeError("ScenarioRun premise bindings must use canonical target order")
        if len(set(premise_ids)) != len(premise_ids) or len(set(targets)) != len(targets):
            raise ProtocolShapeError("ScenarioRun premise bindings must be unique")
        origins = {item.origin_kind for item in self.premise_bindings}
        expected = (
            ("single_field_replacement", 1, {"scenario_hypothesis_v0"})
            if self.scenario_kind == "single_field_replacement"
            else ("atomic_field_replacement_set", None, {"scenario_hypothesis_set_v0"})
        )
        _kind, required_count, required_origins = expected
        if (
            (required_count is not None and len(self.premise_bindings) != required_count)
            or origins != required_origins
        ):
            raise ProtocolShapeError("ScenarioRun plan kind does not match premise inventory")
        if (
            self.engine,
            self.config,
            self.ledger_premise_policy,
            self.overlay_kind,
        ) != ("native", "none", "empty", "replacement_only_v0"):
            raise ProtocolShapeError("ScenarioRun execution contract is outside v0")
        object.__setattr__(
            self,
            "plan_digest",
            _canonical_token(
                "scenario_run_plan_v0",
                {
                    "query_digest": self.query_digest,
                    "target_digest": self.target_digest,
                    "policy_digest": self.policy_digest,
                    "address_space_digest": self.address_space_digest,
                    "schema_digest": self.schema_digest,
                    "base_view_digest": self.base_view_digest,
                    "baseline_relation_digest": self.baseline_relation_digest,
                    "effective_relation_digest": self.effective_relation_digest,
                    "scenario_kind": self.scenario_kind,
                    "premise_binding_digests": tuple(
                        item.binding_digest for item in self.premise_bindings
                    ),
                    "engine": self.engine,
                    "config": self.config,
                    "ledger_premise_policy": self.ledger_premise_policy,
                    "overlay_kind": self.overlay_kind,
                },
            ),
        )


@dataclass(frozen=True, repr=False)
class ScenarioRunRowV0:
    """A typed public projection row without its private proof receipt bytes."""

    ordinal: int
    row_capture_digest: str
    semantic_row_anchor_digest: str
    claim_digest: str
    head_scope_digest: str
    values: tuple[tuple[str, EvaluationRunValueV0], ...]
    row_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int) or self.ordinal < 0:
            raise ProtocolShapeError("ScenarioRun row ordinal must be non-negative int")
        for name in (
            "row_capture_digest",
            "semantic_row_anchor_digest",
            "claim_digest",
            "head_scope_digest",
        ):
            _sha256_token(getattr(self, name), f"ScenarioRun row {name}")
        if (
            not isinstance(self.values, tuple)
            or not self.values
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
            raise ProtocolShapeError("ScenarioRun row values are malformed")
        object.__setattr__(
            self,
            "row_digest",
            _canonical_token(
                "scenario_run_row_v0",
                (
                    self.ordinal,
                    self.row_capture_digest,
                    self.semantic_row_anchor_digest,
                    self.claim_digest,
                    self.head_scope_digest,
                    tuple((alias, value.tag, value.value) for alias, value in self.values),
                ),
            ),
        )

    def __repr__(self) -> str:
        return (
            "ScenarioRunRowV0("
            f"ordinal={self.ordinal}, row_capture_digest={self.row_capture_digest!r}, values=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class ScenarioRunSideV0:
    """One named captured relation/result side of a ScenarioRun."""

    side: Literal["baseline", "effective"]
    run_anchor_digest: str
    result_digest: str
    relation_digest: str
    capture_bytes_digest: str
    rows: tuple[ScenarioRunRowV0, ...]
    side_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        if self.side not in {"baseline", "effective"}:
            raise ProtocolShapeError("ScenarioRun side is invalid")
        for name in (
            "run_anchor_digest",
            "result_digest",
            "relation_digest",
            "capture_bytes_digest",
        ):
            _sha256_token(getattr(self, name), f"ScenarioRun side {name}")
        if not isinstance(self.rows, tuple) or not all(
            isinstance(item, ScenarioRunRowV0) for item in self.rows
        ):
            raise ProtocolShapeError("ScenarioRun side rows are malformed")
        if tuple(item.ordinal for item in self.rows) != tuple(range(len(self.rows))):
            raise ProtocolShapeError("ScenarioRun side row ordinals are not contiguous")
        row_ids = tuple(item.row_capture_digest for item in self.rows)
        if len(set(row_ids)) != len(row_ids):
            raise ProtocolShapeError("ScenarioRun side rows have duplicate capture digests")
        object.__setattr__(
            self,
            "side_digest",
            _canonical_token(
                "scenario_run_side_v0",
                (
                    self.side,
                    self.run_anchor_digest,
                    self.result_digest,
                    self.relation_digest,
                    self.capture_bytes_digest,
                    tuple(item.row_digest for item in self.rows),
                ),
            ),
        )

    def __repr__(self) -> str:
        return f"ScenarioRunSideV0(side={self.side!r}, rows=<redacted>)"


@dataclass(frozen=True, repr=False)
class ScenarioRunV0:
    """A sealed, detached baseline/effective Scenario capture.

    The leading-underscore byte fields are intentionally opaque implementation
    data.  They are never returned as an F4 ``EvaluationRunBundleV0`` surface.
    Integrity sealing detects accidental splice/tamper; it is not authentication
    across an untrusted process boundary.
    """

    plan: ScenarioRunPlanV0
    baseline: ScenarioRunSideV0
    effective: ScenarioRunSideV0
    result_diff: ScenarioResultDiffV0
    _baseline_capture_bytes: bytes = dataclass_field(repr=False, compare=False)
    _effective_capture_bytes: bytes = dataclass_field(repr=False, compare=False)
    integrity: Literal["digest_sealed_not_authenticated"] = "digest_sealed_not_authenticated"
    authenticity: Literal["unverified"] = "unverified"
    premise_provenance: Literal["caller_declared_unverified"] = "caller_declared_unverified"
    ledger_truth: Literal["not_verified_by_scenario_capture"] = "not_verified_by_scenario_capture"
    explain_availability: Literal["detached_scenario_receipt_playback_available"] = (
        "detached_scenario_receipt_playback_available"
    )
    verification_availability: Literal["isolated_native_semantic_and_support_available"] = (
        "isolated_native_semantic_and_support_available"
    )
    scenario_run_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ScenarioRunPlanV0) or not isinstance(
            self.result_diff, ScenarioResultDiffV0
        ):
            raise ProtocolShapeError("ScenarioRun plan or diff is invalid")
        if not isinstance(self.baseline, ScenarioRunSideV0) or not isinstance(
            self.effective, ScenarioRunSideV0
        ):
            raise ProtocolShapeError("ScenarioRun sides are invalid")
        if (self.baseline.side, self.effective.side) != ("baseline", "effective"):
            raise ProtocolShapeError("ScenarioRun requires baseline then effective side")
        if not isinstance(self._baseline_capture_bytes, bytes) or not self._baseline_capture_bytes:
            raise ProtocolShapeError("ScenarioRun baseline capture bytes are malformed")
        if not isinstance(self._effective_capture_bytes, bytes) or not self._effective_capture_bytes:
            raise ProtocolShapeError("ScenarioRun effective capture bytes are malformed")
        expected_capture_tokens = (
            f"sha256:{sha256_hex(self._baseline_capture_bytes)}",
            f"sha256:{sha256_hex(self._effective_capture_bytes)}",
        )
        if (
            self.baseline.capture_bytes_digest,
            self.effective.capture_bytes_digest,
        ) != expected_capture_tokens:
            raise ProtocolShapeError("ScenarioRun side capture bytes do not match their digests")
        if (
            self.integrity,
            self.authenticity,
            self.premise_provenance,
            self.ledger_truth,
            self.explain_availability,
            self.verification_availability,
        ) != (
            "digest_sealed_not_authenticated",
            "unverified",
            "caller_declared_unverified",
            "not_verified_by_scenario_capture",
            "detached_scenario_receipt_playback_available",
            "isolated_native_semantic_and_support_available",
        ):
            raise ProtocolShapeError("ScenarioRun availability or provenance semantics are outside v0")
        object.__setattr__(
            self,
            "scenario_run_digest",
            _canonical_token(
                "scenario_run_v0",
                (
                    self.plan.plan_digest,
                    self.baseline.side_digest,
                    self.effective.side_digest,
                    self.result_diff.diff_digest,
                    self.integrity,
                    self.authenticity,
                    self.premise_provenance,
                    self.ledger_truth,
                    self.explain_availability,
                    self.verification_availability,
                ),
            ),
        )

    def diff(self) -> ScenarioResultDiffV0:
        """Return the captured result-multiset summary without reading a Store."""

        from factgraph.application.scenario_run_runtime import _assert_scenario_run_current

        _assert_scenario_run_current(self)
        return self.result_diff

    def explain(
        self,
        *,
        side: Literal["baseline", "effective"],
        row_capture_digest: str,
    ) -> "ScenarioRunExplanationV0":
        from factgraph.application.scenario_run_runtime import explain_scenario_run_v0

        return explain_scenario_run_v0(self, side=side, row_capture_digest=row_capture_digest)

    def verify(self) -> "ScenarioRunVerificationV0":
        from factgraph.application.scenario_run_runtime import verify_scenario_run_v0

        return verify_scenario_run_v0(self)

    def to_bytes(self) -> bytes:
        from factgraph.application.scenario_run_runtime import scenario_run_bytes

        return scenario_run_bytes(self)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "ScenarioRunV0":
        """Decode a detached ScenarioRun without consulting a live Store."""

        from factgraph.application.scenario_run_runtime import scenario_run_from_bytes

        value = scenario_run_from_bytes(raw)
        if not isinstance(value, cls):  # pragma: no cover - defensive import boundary
            raise ProtocolShapeError("ScenarioRun codec returned an unexpected value")
        return value

    def __repr__(self) -> str:
        return (
            "ScenarioRunV0("
            f"scenario_run_digest={self.scenario_run_digest!r}, captures=<redacted>)"
        )


@dataclass(frozen=True)
class ScenarioRunExplanationV0:
    """Detached evidence plus authored-Policy projection for one captured row."""

    scenario_run_digest: str
    side: Literal["baseline", "effective"]
    row_capture_digest: str
    evidence: Any
    policy_projection: PolicyExplanationViewV0
    explanation_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        _sha256_token(self.scenario_run_digest, "ScenarioRun explanation scenario_run_digest")
        _sha256_token(self.row_capture_digest, "ScenarioRun explanation row_capture_digest")
        if self.side not in {"baseline", "effective"}:
            raise ProtocolShapeError("ScenarioRun explanation side is invalid")
        if not isinstance(self.policy_projection, PolicyExplanationViewV0):
            raise ProtocolShapeError("ScenarioRun explanation policy projection is invalid")
        object.__setattr__(
            self,
            "explanation_digest",
            _canonical_token(
                "scenario_run_explanation_v0",
                (
                    self.scenario_run_digest,
                    self.side,
                    self.row_capture_digest,
                    self.policy_projection.projection_digest,
                ),
            ),
        )


@dataclass(frozen=True)
class ScenarioRunVerificationV0:
    """Pair of isolated F4 verification records with Scenario truth boundaries."""

    scenario_run_digest: str
    baseline: EvaluationRunVerificationV0
    effective: EvaluationRunVerificationV0
    verification_scope: Literal["isolated_captured_scenario_relations_v0"] = (
        "isolated_captured_scenario_relations_v0"
    )
    premise_truth_verified: Literal[False] = False
    ledger_truth_verified: Literal[False] = False
    verification_digest: str = dataclass_field(init=False)

    def __post_init__(self) -> None:
        _sha256_token(self.scenario_run_digest, "ScenarioRun verification scenario_run_digest")
        if not isinstance(self.baseline, EvaluationRunVerificationV0) or not isinstance(
            self.effective, EvaluationRunVerificationV0
        ):
            raise ProtocolShapeError("ScenarioRun verification side records are invalid")
        if (
            self.verification_scope,
            self.premise_truth_verified,
            self.ledger_truth_verified,
        ) != ("isolated_captured_scenario_relations_v0", False, False):
            raise ProtocolShapeError("ScenarioRun verification semantics are outside v0")
        object.__setattr__(
            self,
            "verification_digest",
            _canonical_token(
                "scenario_run_verification_v0",
                (
                    self.scenario_run_digest,
                    self.baseline.verification_digest,
                    self.effective.verification_digest,
                    self.verification_scope,
                    self.premise_truth_verified,
                    self.ledger_truth_verified,
                ),
            ),
        )

    @property
    def matched(self) -> bool:
        return self.baseline.verdict in {
            "matched_declared_runtime",
            "matched_unpinned_runtime",
        } and self.effective.verdict in {
            "matched_declared_runtime",
            "matched_unpinned_runtime",
        }


__all__ = [
    "ScenarioOriginKind",
    "ScenarioPremiseBindingV0",
    "ScenarioRunExplanationV0",
    "ScenarioRunPlanV0",
    "ScenarioRunRowV0",
    "ScenarioRunSide",
    "ScenarioRunSideV0",
    "ScenarioRunV0",
    "ScenarioRunVerificationV0",
]
