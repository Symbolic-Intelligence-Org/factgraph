"""Pure, sealed V1 contracts for a portable evaluation goal.

This module deliberately owns *declarations and observed technical outcomes*,
not evaluation.  It is the common contract at the boundary between a Query
compiler and an executor: a later native/Souffle/ProbLog adapter may consume a
``GoalPlanV1`` and materialize a ``GoalResultV1`` without changing the meaning
of target identity, projection, expectations, row identity, or assessment.

The protocol does not make an authorization, source-authority, truthfulness,
or product-disposition claim.  Those belong to the caller (for example
Meander).  Likewise, digest sealing is deterministic integrity checking, not
authentication across a trust boundary.

``rows`` and ``set`` intentionally use *set* semantics.  A result may not
contain two semantically identical projection rows, and no bag/count-of-proof
semantics is exposed by this contract.  ``count`` therefore counts unique
semantic projection rows only.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import CANONICAL_TAGS, claim_args_from_rest_terms

from .common import ProtocolShapeError, _require_non_empty_str
from .scenario_v1 import ExactLocalClosureTargetV1

GoalTargetKindV1: TypeAlias = Literal["rule", "policy", "relation_provider"]
GoalResultModeV1: TypeAlias = Literal["rows", "exists", "count", "set"]
GoalCompletenessV1: TypeAlias = Literal[
    "complete", "incomplete", "resource_limited", "unsupported", "unknown"
]
GoalExistsValueV1: TypeAlias = Literal["true", "false", "undetermined"]
GoalExpectationKindV1: TypeAlias = Literal[
    "contains_row", "exact_local_absence", "exists", "count_eq", "set_equals"
]
GoalExpectationStatusV1: TypeAlias = Literal[
    "satisfied", "not_satisfied", "underdetermined", "unsupported"
]
ScenarioResolutionStateV1: TypeAlias = Literal[
    "not_requested", "resolved", "conflict", "unsupported", "unresolved"
]
ExecutionStateV1: TypeAlias = Literal["not_run", "succeeded", "failed", "unsupported", "unresolved"]
ParityStateV1: TypeAlias = Literal[
    "not_requested", "equivalent", "different", "unsupported", "unresolved"
]
ExplainStateV1: TypeAlias = Literal[
    "not_requested", "available", "unavailable", "unsupported", "unresolved"
]
ReplayStateV1: TypeAlias = Literal[
    "not_requested", "available", "unavailable", "unsupported", "unresolved"
]
ContractValidityStateV1: TypeAlias = Literal["valid", "invalid", "unsupported", "unresolved"]
ExactLocalClosureStateV1: TypeAlias = Literal[
    "not_requested", "resolved", "required", "unsupported", "unresolved"
]
CapabilityStateV1: TypeAlias = Literal["not_requested", "supported", "rejected", "unresolved"]
GoalValueTagV1: TypeAlias = Literal[
    "entity_ref", "string", "int", "float64", "bool", "bytes", "time", "uuid"
]
GoalValueStorageV1: TypeAlias = str | int | bool

_TARGET_KINDS = frozenset({"rule", "policy", "relation_provider"})
_RESULT_MODES = frozenset({"rows", "exists", "count", "set"})
_COMPLETENESS = frozenset({"complete", "incomplete", "resource_limited", "unsupported", "unknown"})
_EXISTS_VALUES = frozenset({"true", "false", "undetermined"})
_EXPECTATION_KINDS = frozenset(
    {"contains_row", "exact_local_absence", "exists", "count_eq", "set_equals"}
)
_EXPECTATION_STATUSES = frozenset({"satisfied", "not_satisfied", "underdetermined", "unsupported"})
_SCENARIO_RESOLUTION_STATES = frozenset(
    {"not_requested", "resolved", "conflict", "unsupported", "unresolved"}
)
_EXECUTION_STATES = frozenset({"not_run", "succeeded", "failed", "unsupported", "unresolved"})
_PARITY_STATES = frozenset(
    {"not_requested", "equivalent", "different", "unsupported", "unresolved"}
)
_EXPLAIN_STATES = frozenset(
    {"not_requested", "available", "unavailable", "unsupported", "unresolved"}
)
_REPLAY_STATES = frozenset(
    {"not_requested", "available", "unavailable", "unsupported", "unresolved"}
)
_CONTRACT_VALIDITY_STATES = frozenset({"valid", "invalid", "unsupported", "unresolved"})
_EXACT_LOCAL_CLOSURE_STATES = frozenset(
    {"not_requested", "resolved", "required", "unsupported", "unresolved"}
)
_CAPABILITY_STATES = frozenset({"not_requested", "supported", "rejected", "unresolved"})


def _token(label: str, payload: object) -> str:
    raw = json.dumps(
        {"format": label, "payload": _plain(payload)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{sha256_hex(raw)}"


def _plain(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value


def _require_token(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ProtocolShapeError(f"{field_name} must be sha256 token")
    _require_hex(value[7:], field_name)
    return value


def _require_hex(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ProtocolShapeError(f"{field_name} must be lowercase sha256 hex")
    return value


def _require_count(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProtocolShapeError(f"{field_name} must be non-negative int")
    return value


def _require_literal(value: object, field_name: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProtocolShapeError(f"{field_name} is outside this protocol")
    return value


def _canonical_value_storage(tag: GoalValueTagV1, value: GoalValueStorageV1) -> GoalValueStorageV1:
    """Validate and return canonical JSON-safe ``tup_v1`` storage.

    This deliberately mirrors the stable capture representation without
    importing its v0 DTO.  V1 can therefore be decoded and checked independently
    of a particular capture/replay implementation.
    """

    if tag not in CANONICAL_TAGS:
        raise ProtocolShapeError("GoalValueV1.tag is unsupported")
    if tag in {"int", "time"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ProtocolShapeError(f"GoalValueV1.value for {tag} must be int")
        raw: object = value
    elif tag == "bool":
        if not isinstance(value, bool):
            raise ProtocolShapeError("GoalValueV1.value for bool must be bool")
        raw = value
    else:
        if not isinstance(value, str):
            raise ProtocolShapeError(f"GoalValueV1.value for {tag} must be str")
        raw = value
        if tag == "bytes":
            try:
                padding = "=" * (-len(value) % 4)
                raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
            except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                raise ProtocolShapeError("GoalValueV1 bytes value is not base64url") from exc
    try:
        normalized = claim_args_from_rest_terms([(tag, raw)])[0][1]
    except (TypeError, ValueError) as exc:
        raise ProtocolShapeError(f"GoalValueV1.value is not canonical {tag} storage") from exc
    if normalized != value:
        raise ProtocolShapeError(f"GoalValueV1.value is not canonical {tag} storage")
    return value


@dataclass(frozen=True, repr=False)
class GoalValueV1:
    """One canonical, typed, JSON-safe projection value."""

    tag: GoalValueTagV1
    value: GoalValueStorageV1
    value_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _canonical_value_storage(self.tag, self.value)
        object.__setattr__(self, "value_digest", _token("goal_value_v1", (self.tag, self.value)))

    def __repr__(self) -> str:
        return f"GoalValueV1(tag={self.tag!r}, value=<redacted>)"


@dataclass(frozen=True)
class GoalTargetRefV1:
    """An immutable reference to the target compiled by a future executor."""

    kind: GoalTargetKindV1
    target_id: str
    target_version: str | None
    target_digest: str

    def __post_init__(self) -> None:
        _require_literal(self.kind, "GoalTargetRefV1.kind", _TARGET_KINDS)
        _require_non_empty_str(self.target_id, field_name="GoalTargetRefV1.target_id")
        if self.target_version is not None:
            _require_non_empty_str(self.target_version, field_name="GoalTargetRefV1.target_version")
        _require_token(self.target_digest, "GoalTargetRefV1.target_digest")


@dataclass(frozen=True)
class GoalSelectionV1:
    """One ordered projection column and its compiled value domain."""

    alias: str
    value_tag: GoalValueTagV1

    def __post_init__(self) -> None:
        _require_non_empty_str(self.alias, field_name="GoalSelectionV1.alias")
        if self.value_tag not in CANONICAL_TAGS:
            raise ProtocolShapeError("GoalSelectionV1.value_tag is unsupported")


@dataclass(frozen=True)
class GoalRowExpectationV1:
    """A typed projected row, either subset-shaped or exact by expectation kind."""

    values: tuple[tuple[str, GoalValueV1], ...]
    row_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple) or not self.values:
            raise ProtocolShapeError("GoalRowExpectationV1.values must be non-empty tuple")
        normalized: list[tuple[str, GoalValueV1]] = []
        aliases: list[str] = []
        for index, item in enumerate(self.values):
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not isinstance(item[1], GoalValueV1)
            ):
                raise ProtocolShapeError(
                    f"GoalRowExpectationV1.values[{index}] must be (str, GoalValueV1)"
                )
            _require_non_empty_str(
                item[0], field_name=f"GoalRowExpectationV1.values[{index}].alias"
            )
            aliases.append(item[0])
            normalized.append(item)
        if len(set(aliases)) != len(aliases):
            raise ProtocolShapeError("GoalRowExpectationV1 aliases must be unique")
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "values", tuple(normalized))
        object.__setattr__(
            self,
            "row_digest",
            _token(
                "goal_row_expectation_v1",
                tuple((alias, value.tag, value.value_digest) for alias, value in normalized),
            ),
        )


@dataclass(frozen=True)
class ContainsRowExpectationV1:
    """Require a V1 selected-row result to contain one expected row."""

    expectation_id: str
    row: GoalRowExpectationV1
    expectation_digest: str = field(init=False)
    kind: GoalExpectationKindV1 = "contains_row"

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.expectation_id, field_name="ContainsRowExpectationV1.expectation_id"
        )
        if self.kind != "contains_row" or not isinstance(self.row, GoalRowExpectationV1):
            raise ProtocolShapeError("ContainsRowExpectationV1 is malformed")
        object.__setattr__(
            self,
            "expectation_digest",
            _token("goal_contains_row_expectation_v1", (self.expectation_id, self.row.row_digest)),
        )


@dataclass(frozen=True)
class ExactLocalAbsenceExpectationV1:
    """Assert resolver-owned exact local absence, never query-row absence.

    This expectation deliberately names the exact Scenario closure target,
    rather than treating a zero Query row as a negative fact.  A query can
    project a derived result which bears no one-to-one relation to the field,
    relation, or entity that Scenario made empty; accepting a caller-provided
    row here would therefore permit an unsound wider absence claim.

    The executor may mark this satisfied only when the resolved Scenario has
    exactly this closure target and its sealed effective relation is complete
    for that target.  It never lowers a generic ``NotAtom`` and it never says
    anything about a source or the global ledger.
    """

    expectation_id: str
    closure_target: ExactLocalClosureTargetV1
    expectation_digest: str = field(init=False)
    kind: GoalExpectationKindV1 = "exact_local_absence"

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.expectation_id,
            field_name="ExactLocalAbsenceExpectationV1.expectation_id",
        )
        if self.kind != "exact_local_absence" or not isinstance(
            self.closure_target, ExactLocalClosureTargetV1
        ):
            raise ProtocolShapeError("ExactLocalAbsenceExpectationV1 is malformed")
        object.__setattr__(
            self,
            "expectation_digest",
            _token(
                "goal_exact_local_absence_expectation_v1",
                (
                    self.expectation_id,
                    self.closure_target.target_digest,
                ),
            ),
        )

    @property
    def closure_target_digest(self) -> str:
        """Stable shorthand used by run capture and assessment code."""

        return self.closure_target.target_digest


@dataclass(frozen=True)
class ExistsExpectationV1:
    """Require the V1 result's existence observation to match a boolean."""

    expectation_id: str
    expected: bool
    expectation_digest: str = field(init=False)
    kind: GoalExpectationKindV1 = "exists"

    def __post_init__(self) -> None:
        _require_non_empty_str(self.expectation_id, field_name="ExistsExpectationV1.expectation_id")
        if self.kind != "exists" or not isinstance(self.expected, bool):
            raise ProtocolShapeError("ExistsExpectationV1 is malformed")
        object.__setattr__(
            self,
            "expectation_digest",
            _token("goal_exists_expectation_v1", (self.expectation_id, self.expected)),
        )


@dataclass(frozen=True)
class CountEqExpectationV1:
    """Require the V1 selected-row count to equal an exact integer."""

    expectation_id: str
    expected_count: int
    expectation_digest: str = field(init=False)
    kind: GoalExpectationKindV1 = "count_eq"

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.expectation_id, field_name="CountEqExpectationV1.expectation_id"
        )
        if self.kind != "count_eq":
            raise ProtocolShapeError("CountEqExpectationV1.kind must be count_eq")
        _require_count(self.expected_count, "CountEqExpectationV1.expected_count")
        object.__setattr__(
            self,
            "expectation_digest",
            _token("goal_count_eq_expectation_v1", (self.expectation_id, self.expected_count)),
        )


@dataclass(frozen=True)
class SetEqualsExpectationV1:
    """Require the V1 selected-row set to equal an exact expected set."""

    expectation_id: str
    rows: tuple[GoalRowExpectationV1, ...]
    expectation_digest: str = field(init=False)
    kind: GoalExpectationKindV1 = "set_equals"

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.expectation_id, field_name="SetEqualsExpectationV1.expectation_id"
        )
        if self.kind != "set_equals" or not isinstance(self.rows, tuple):
            raise ProtocolShapeError("SetEqualsExpectationV1 is malformed")
        if not all(isinstance(row, GoalRowExpectationV1) for row in self.rows):
            raise ProtocolShapeError(
                "SetEqualsExpectationV1.rows must be GoalRowExpectationV1 tuple"
            )
        rows = tuple(sorted(self.rows, key=lambda item: item.row_digest))
        if len({item.row_digest for item in rows}) != len(rows):
            raise ProtocolShapeError(
                "SetEqualsExpectationV1 has duplicate semantic rows; bags are unsupported"
            )
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "expectation_digest",
            _token(
                "goal_set_equals_expectation_v1",
                (self.expectation_id, tuple(item.row_digest for item in rows)),
            ),
        )


GoalExpectationV1: TypeAlias = (
    ContainsRowExpectationV1
    | ExactLocalAbsenceExpectationV1
    | ExistsExpectationV1
    | CountEqExpectationV1
    | SetEqualsExpectationV1
)


@dataclass(frozen=True)
class GoalPlanV1:
    """A sealed, executor-independent query goal.

    ``query_digest`` identifies the compiler-owned Query shape.  The plan only
    refers to an optional Scenario/effective-world request by digest; it does
    not resolve or privilege a premise.  Resolution is recorded by an eventual
    technical assessment and a materialized result anchor.
    """

    target: GoalTargetRefV1
    query_digest: str
    result_mode: GoalResultModeV1
    selections: tuple[GoalSelectionV1, ...]
    candidate_target: GoalTargetRefV1 | None = None
    candidate_query_digest: str | None = None
    scenario_request_digest: str | None = None
    evidence_scope_digest: str | None = None
    execution_profile_digest: str | None = None
    expectations: tuple[GoalExpectationV1, ...] = ()
    plan_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.target, GoalTargetRefV1):
            raise ProtocolShapeError("GoalPlanV1.target must be GoalTargetRefV1")
        if self.candidate_target is not None and not isinstance(
            self.candidate_target, GoalTargetRefV1
        ):
            raise ProtocolShapeError("GoalPlanV1.candidate_target must be GoalTargetRefV1 or None")
        if self.candidate_target is not None and self.candidate_target == self.target:
            raise ProtocolShapeError("GoalPlanV1.candidate_target must differ from target")
        if (self.candidate_target is None) != (self.candidate_query_digest is None):
            raise ProtocolShapeError(
                "GoalPlanV1 candidate target and candidate query digest must be supplied together"
            )
        if self.candidate_target is not None and (
            self.target.kind == "relation_provider"
            or self.candidate_target.kind == "relation_provider"
        ):
            raise ProtocolShapeError(
                "GoalPlanV1 immutable comparison is limited to Rule/Policy targets"
            )
        _require_token(self.query_digest, "GoalPlanV1.query_digest")
        _require_literal(self.result_mode, "GoalPlanV1.result_mode", _RESULT_MODES)
        if (
            not isinstance(self.selections, tuple)
            or not self.selections
            or not all(isinstance(item, GoalSelectionV1) for item in self.selections)
        ):
            raise ProtocolShapeError(
                "GoalPlanV1.selections must be non-empty GoalSelectionV1 tuple"
            )
        aliases = tuple(item.alias for item in self.selections)
        if len(set(aliases)) != len(aliases):
            raise ProtocolShapeError("GoalPlanV1 selection aliases must be unique")
        for name in (
            "scenario_request_digest",
            "evidence_scope_digest",
            "execution_profile_digest",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_token(value, f"GoalPlanV1.{name}")
        if self.candidate_query_digest is not None:
            _require_token(self.candidate_query_digest, "GoalPlanV1.candidate_query_digest")
        if not isinstance(self.expectations, tuple) or not all(
            isinstance(
                item,
                (
                    ContainsRowExpectationV1,
                    ExactLocalAbsenceExpectationV1,
                    ExistsExpectationV1,
                    CountEqExpectationV1,
                    SetEqualsExpectationV1,
                ),
            )
            for item in self.expectations
        ):
            raise ProtocolShapeError("GoalPlanV1.expectations has an unsupported expectation")
        expectation_ids = tuple(item.expectation_id for item in self.expectations)
        if len(set(expectation_ids)) != len(expectation_ids):
            raise ProtocolShapeError("GoalPlanV1 expectation ids must be unique")
        for expectation in self.expectations:
            _validate_expectation_against_plan(expectation, self.selections)
        if (
            any(isinstance(item, ExactLocalAbsenceExpectationV1) for item in self.expectations)
            and self.scenario_request_digest is None
        ):
            raise ProtocolShapeError(
                "exact-local absence expectation requires a Scenario request digest"
            )
        object.__setattr__(
            self,
            "plan_digest",
            _token(
                "goal_plan_v1",
                {
                    "target": self.target,
                    "candidate_target": self.candidate_target,
                    "candidate_query_digest": self.candidate_query_digest,
                    "query_digest": self.query_digest,
                    "result_mode": self.result_mode,
                    "selections": self.selections,
                    "scenario_request_digest": self.scenario_request_digest,
                    "evidence_scope_digest": self.evidence_scope_digest,
                    "execution_profile_digest": self.execution_profile_digest,
                    "expectations": tuple(
                        (item.expectation_id, item.kind, item.expectation_digest)
                        for item in self.expectations
                    ),
                },
            ),
        )


def _validate_expectation_against_plan(
    expectation: GoalExpectationV1,
    selections: tuple[GoalSelectionV1, ...],
) -> None:
    selection_by_alias = {selection.alias: selection for selection in selections}
    if isinstance(expectation, ContainsRowExpectationV1):
        _validate_expected_row(expectation.row, selection_by_alias, exact=False)
    elif isinstance(expectation, ExactLocalAbsenceExpectationV1):
        # This is a world-target assertion, intentionally independent of the
        # selected derived Query rows.  The runtime checks it against the
        # sealed Scenario closure rather than trying to infer absence from
        # projection shape.
        return
    elif isinstance(expectation, SetEqualsExpectationV1):
        for row in expectation.rows:
            _validate_expected_row(row, selection_by_alias, exact=True)


def _validate_expected_row(
    row: GoalRowExpectationV1,
    selection_by_alias: dict[str, GoalSelectionV1],
    *,
    exact: bool,
) -> None:
    aliases = tuple(alias for alias, _ in row.values)
    if exact and set(aliases) != set(selection_by_alias):
        raise ProtocolShapeError("exact expected row must provide every selected alias")
    for alias, value in row.values:
        selection = selection_by_alias.get(alias)
        if selection is None:
            raise ProtocolShapeError("expectation references an unknown selected alias")
        if selection.value_tag != value.tag:
            raise ProtocolShapeError("expectation value tag does not match selected value tag")


@dataclass(frozen=True)
class GoalRowAnchorV1:
    """Deterministic semantic identity of one unique projected result row."""

    plan_digest: str
    semantic_row_digest: str
    anchor_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.plan_digest, "GoalRowAnchorV1.plan_digest")
        _require_token(self.semantic_row_digest, "GoalRowAnchorV1.semantic_row_digest")
        object.__setattr__(
            self,
            "anchor_digest",
            _token("goal_row_anchor_v1", (self.plan_digest, self.semantic_row_digest)),
        )


@dataclass(frozen=True)
class GoalResultRowV1:
    """One canonical projection row with a plan-bound semantic anchor."""

    values: tuple[tuple[str, GoalValueV1], ...]
    semantic_row_digest: str = field(init=False)
    anchor: GoalRowAnchorV1 | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.values, tuple) or not self.values:
            raise ProtocolShapeError("GoalResultRowV1.values must be non-empty tuple")
        aliases: list[str] = []
        normalized: list[tuple[str, GoalValueV1]] = []
        for index, item in enumerate(self.values):
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not isinstance(item[0], str)
                or not isinstance(item[1], GoalValueV1)
            ):
                raise ProtocolShapeError(
                    f"GoalResultRowV1.values[{index}] must be (str, GoalValueV1)"
                )
            _require_non_empty_str(item[0], field_name=f"GoalResultRowV1.values[{index}].alias")
            aliases.append(item[0])
            normalized.append(item)
        if len(set(aliases)) != len(aliases):
            raise ProtocolShapeError("GoalResultRowV1 aliases must be unique")
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "values", tuple(normalized))
        semantic = _token(
            "goal_semantic_result_row_v1",
            tuple((alias, value.tag, value.value_digest) for alias, value in normalized),
        )
        object.__setattr__(self, "semantic_row_digest", semantic)
        if self.anchor is not None:
            if not isinstance(self.anchor, GoalRowAnchorV1):
                raise ProtocolShapeError("GoalResultRowV1.anchor must be GoalRowAnchorV1 or None")
            if self.anchor.semantic_row_digest != semantic:
                raise ProtocolShapeError("GoalResultRowV1 anchor does not match values")

    def anchored(self, plan_digest: str) -> GoalResultRowV1:
        """Return this immutable row with its deterministic plan-bound anchor."""

        return GoalResultRowV1(
            self.values,
            anchor=GoalRowAnchorV1(plan_digest, self.semantic_row_digest),
        )


@dataclass(frozen=True)
class GoalSummaryAnchorV1:
    """A complete anchor for the semantic set observed for one goal result."""

    plan_digest: str
    result_mode: GoalResultModeV1
    completeness: GoalCompletenessV1
    semantic_row_digests: tuple[str, ...]
    summary_anchor_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.plan_digest, "GoalSummaryAnchorV1.plan_digest")
        _require_literal(self.result_mode, "GoalSummaryAnchorV1.result_mode", _RESULT_MODES)
        _require_literal(self.completeness, "GoalSummaryAnchorV1.completeness", _COMPLETENESS)
        if not isinstance(self.semantic_row_digests, tuple):
            raise ProtocolShapeError("GoalSummaryAnchorV1.semantic_row_digests must be tuple")
        for digest in self.semantic_row_digests:
            _require_token(digest, "GoalSummaryAnchorV1 semantic row digest")
        if tuple(sorted(self.semantic_row_digests)) != self.semantic_row_digests:
            raise ProtocolShapeError("GoalSummaryAnchorV1 rows must be canonical sorted")
        if len(set(self.semantic_row_digests)) != len(self.semantic_row_digests):
            raise ProtocolShapeError("GoalSummaryAnchorV1 does not permit bag semantics")
        object.__setattr__(
            self,
            "summary_anchor_digest",
            _token(
                "goal_summary_anchor_v1",
                (
                    self.plan_digest,
                    self.result_mode,
                    self.completeness,
                    self.semantic_row_digests,
                ),
            ),
        )


@dataclass(frozen=True)
class GoalExpectationOutcomeV1:
    """Result-local technical outcome for exactly one declared expectation."""

    expectation_id: str
    expectation_digest: str
    kind: GoalExpectationKindV1
    status: GoalExpectationStatusV1
    matched_semantic_row_digests: tuple[str, ...] = ()
    diagnostic_code: str = "GOAL_EXPECTATION_OUTCOME"
    outcome_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(
            self.expectation_id, field_name="GoalExpectationOutcomeV1.expectation_id"
        )
        _require_token(self.expectation_digest, "GoalExpectationOutcomeV1.expectation_digest")
        _require_literal(self.kind, "GoalExpectationOutcomeV1.kind", _EXPECTATION_KINDS)
        _require_literal(self.status, "GoalExpectationOutcomeV1.status", _EXPECTATION_STATUSES)
        _require_non_empty_str(
            self.diagnostic_code, field_name="GoalExpectationOutcomeV1.diagnostic_code"
        )
        if not isinstance(self.matched_semantic_row_digests, tuple):
            raise ProtocolShapeError(
                "GoalExpectationOutcomeV1.matched_semantic_row_digests must be tuple"
            )
        for digest in self.matched_semantic_row_digests:
            _require_token(digest, "GoalExpectationOutcomeV1 matched semantic row digest")
        if tuple(sorted(self.matched_semantic_row_digests)) != self.matched_semantic_row_digests:
            raise ProtocolShapeError("GoalExpectationOutcomeV1 matches must be canonical sorted")
        if len(set(self.matched_semantic_row_digests)) != len(self.matched_semantic_row_digests):
            raise ProtocolShapeError("GoalExpectationOutcomeV1 does not permit bag semantics")
        # ``exists(expected=True)`` needs a witness at runtime, whereas
        # ``exists(expected=False)`` is correctly satisfied by a complete
        # empty enumeration.  The expected boolean lives in the immutable
        # plan inventory, so this standalone result DTO can require a witness
        # only for the intrinsically row-shaped contains-row form.  The runner
        # performs the plan/result cross-check before constructing this DTO.
        if (
            self.status == "satisfied"
            and self.kind == "contains_row"
            and not self.matched_semantic_row_digests
        ):
            raise ProtocolShapeError("satisfied contains-row expectation requires a witness row")
        if self.kind == "exact_local_absence":
            # Exact-local absence is a Scenario-world/closure statement, not a
            # statement about the selected derived rows.  A row reference here
            # would invite an executor to confuse a zero or nonmatching query
            # result with an absence proof for an unrelated field/relation.
            # Its target is already sealed in the expectation inventory; the
            # later assessment records the closure basis and diagnostic.
            if self.matched_semantic_row_digests:
                raise ProtocolShapeError(
                    "exact-local absence expectation must not carry query-row witnesses"
                )
        elif self.status != "satisfied" and self.matched_semantic_row_digests:
            raise ProtocolShapeError("only satisfied expectation may carry matched rows")
        object.__setattr__(
            self,
            "outcome_digest",
            _token(
                "goal_expectation_outcome_v1",
                (
                    self.expectation_id,
                    self.expectation_digest,
                    self.kind,
                    self.status,
                    self.matched_semantic_row_digests,
                    self.diagnostic_code,
                ),
            ),
        )


@dataclass(frozen=True)
class GoalResultV1:
    """One materialized result with no bag semantics and explicit completeness."""

    plan_digest: str
    result_mode: GoalResultModeV1
    completeness: GoalCompletenessV1
    rows: tuple[GoalResultRowV1, ...]
    exists_value: GoalExistsValueV1 | None = None
    count_value: int | None = None
    expectation_outcomes: tuple[GoalExpectationOutcomeV1, ...] = ()
    summary_anchor: GoalSummaryAnchorV1 | None = None
    result_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.plan_digest, "GoalResultV1.plan_digest")
        _require_literal(self.result_mode, "GoalResultV1.result_mode", _RESULT_MODES)
        _require_literal(self.completeness, "GoalResultV1.completeness", _COMPLETENESS)
        if not isinstance(self.rows, tuple) or not all(
            isinstance(item, GoalResultRowV1) for item in self.rows
        ):
            raise ProtocolShapeError("GoalResultV1.rows must be GoalResultRowV1 tuple")
        anchored_rows: list[GoalResultRowV1] = []
        for row in self.rows:
            anchored = row.anchored(self.plan_digest) if row.anchor is None else row
            assert anchored.anchor is not None
            if anchored.anchor.plan_digest != self.plan_digest:
                raise ProtocolShapeError("GoalResultV1 row anchor belongs to another plan")
            anchored_rows.append(anchored)
        anchored_rows.sort(key=lambda item: item.semantic_row_digest)
        semantic_digests = tuple(item.semantic_row_digest for item in anchored_rows)
        if len(set(semantic_digests)) != len(semantic_digests):
            raise ProtocolShapeError(
                "GoalResultV1 does not permit duplicate semantic rows or bag semantics"
            )
        object.__setattr__(self, "rows", tuple(anchored_rows))
        self._validate_mode_values(semantic_digests)
        if not isinstance(self.expectation_outcomes, tuple) or not all(
            isinstance(item, GoalExpectationOutcomeV1) for item in self.expectation_outcomes
        ):
            raise ProtocolShapeError("GoalResultV1.expectation_outcomes is malformed")
        outcome_ids = tuple(item.expectation_id for item in self.expectation_outcomes)
        if len(set(outcome_ids)) != len(outcome_ids):
            raise ProtocolShapeError("GoalResultV1 expectation outcome ids must be unique")
        row_digest_set = frozenset(semantic_digests)
        if any(
            not set(item.matched_semantic_row_digests).issubset(row_digest_set)
            for item in self.expectation_outcomes
        ):
            raise ProtocolShapeError("GoalResultV1 expectation outcome references a missing row")
        for outcome in self.expectation_outcomes:
            # A capability/closure limitation can leave one expectation
            # unsupported or underdetermined even when this Query's selected
            # row enumeration itself is complete.  Conversely, exact-local
            # absence is evaluated against Scenario's sealed closure, not the
            # result-row enumeration.  Only row-derived negative outcomes
            # require a complete enumeration of those rows.
            if (
                outcome.kind != "exact_local_absence"
                and outcome.status == "not_satisfied"
                and self.completeness != "complete"
            ):
                raise ProtocolShapeError("not_satisfied expectation requires complete enumeration")
        expected_summary = GoalSummaryAnchorV1(
            self.plan_digest, self.result_mode, self.completeness, semantic_digests
        )
        if self.summary_anchor is None:
            object.__setattr__(self, "summary_anchor", expected_summary)
        elif self.summary_anchor != expected_summary:
            raise ProtocolShapeError("GoalResultV1 summary anchor does not match result rows")
        object.__setattr__(
            self,
            "result_digest",
            _token(
                "goal_result_v1",
                {
                    "plan_digest": self.plan_digest,
                    "result_mode": self.result_mode,
                    "completeness": self.completeness,
                    "semantic_rows": semantic_digests,
                    "exists_value": self.exists_value,
                    "count_value": self.count_value,
                    "expectations": tuple(
                        (item.expectation_id, item.outcome_digest)
                        for item in self.expectation_outcomes
                    ),
                    "summary_anchor_digest": expected_summary.summary_anchor_digest,
                },
            ),
        )

    def _validate_mode_values(self, semantic_digests: tuple[str, ...]) -> None:
        if self.result_mode in {"rows", "set"}:
            if self.exists_value is not None or self.count_value is not None:
                raise ProtocolShapeError(
                    "rows/set result must not carry exists/count scalar result"
                )
            return
        if self.result_mode == "exists":
            if self.count_value is not None:
                raise ProtocolShapeError("exists result must not carry count")
            _require_literal(self.exists_value, "GoalResultV1.exists_value", _EXISTS_VALUES)
            if self.exists_value == "true":
                if len(semantic_digests) != 1:
                    raise ProtocolShapeError("true exists result requires exactly one witness row")
            elif self.exists_value == "false":
                if semantic_digests or self.completeness != "complete":
                    raise ProtocolShapeError(
                        "false exists result requires zero rows and complete enumeration"
                    )
            elif semantic_digests:
                raise ProtocolShapeError("undetermined exists result must not carry a witness row")
            return
        if self.result_mode == "count":
            if self.exists_value is not None:
                raise ProtocolShapeError("count result must not carry exists value")
            if self.count_value is None:
                if self.completeness == "complete":
                    raise ProtocolShapeError("complete count result requires count_value")
            else:
                _require_count(self.count_value, "GoalResultV1.count_value")
                if self.completeness != "complete" or self.count_value != len(semantic_digests):
                    raise ProtocolShapeError(
                        "count value requires complete unique-row enumeration and must match it"
                    )
            return
        raise AssertionError("validated GoalResult mode is unreachable")


@dataclass(frozen=True)
class GoalTechnicalAssessmentV1:
    """Technical status axes, explicitly separate from any product verdict.

    It says whether the protocol contract was valid, FactGraph resolved a
    Scenario and exact-local closure, ran an engine, observed cross-engine
    parity, had complete enumeration, evaluated declared expectations, can
    explain/replay the run, and rejected a requested capability.  These are
    deliberately independent axes: for example a complete selected-row
    result can still have an underdetermined exact-local absence expectation
    because the requested closure was unavailable.  It intentionally cannot
    represent source authority, factual truth, policy approval, or an action
    authorization decision.
    """

    plan_digest: str
    result_digest: str | None
    scenario_resolution: ScenarioResolutionStateV1
    execution: ExecutionStateV1
    parity: ParityStateV1
    completeness: GoalCompletenessV1
    expectation: GoalExpectationStatusV1 | Literal["not_requested"]
    explain: ExplainStateV1
    replay: ReplayStateV1
    contract_validity: ContractValidityStateV1 = "valid"
    exact_local_closure: ExactLocalClosureStateV1 = "not_requested"
    capability: CapabilityStateV1 = "not_requested"
    assessment_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_token(self.plan_digest, "GoalTechnicalAssessmentV1.plan_digest")
        if self.result_digest is not None:
            _require_token(self.result_digest, "GoalTechnicalAssessmentV1.result_digest")
        _require_literal(
            self.scenario_resolution,
            "GoalTechnicalAssessmentV1.scenario_resolution",
            _SCENARIO_RESOLUTION_STATES,
        )
        _require_literal(self.execution, "GoalTechnicalAssessmentV1.execution", _EXECUTION_STATES)
        _require_literal(self.parity, "GoalTechnicalAssessmentV1.parity", _PARITY_STATES)
        _require_literal(self.completeness, "GoalTechnicalAssessmentV1.completeness", _COMPLETENESS)
        _require_literal(
            self.expectation,
            "GoalTechnicalAssessmentV1.expectation",
            _EXPECTATION_STATUSES | {"not_requested"},
        )
        _require_literal(self.explain, "GoalTechnicalAssessmentV1.explain", _EXPLAIN_STATES)
        _require_literal(self.replay, "GoalTechnicalAssessmentV1.replay", _REPLAY_STATES)
        _require_literal(
            self.contract_validity,
            "GoalTechnicalAssessmentV1.contract_validity",
            _CONTRACT_VALIDITY_STATES,
        )
        _require_literal(
            self.exact_local_closure,
            "GoalTechnicalAssessmentV1.exact_local_closure",
            _EXACT_LOCAL_CLOSURE_STATES,
        )
        _require_literal(
            self.capability,
            "GoalTechnicalAssessmentV1.capability",
            _CAPABILITY_STATES,
        )
        if self.execution == "succeeded" and self.result_digest is None:
            raise ProtocolShapeError("successful technical assessment requires result_digest")
        if self.execution != "succeeded" and self.result_digest is not None:
            raise ProtocolShapeError("only successful technical assessment may carry result_digest")
        if self.execution != "succeeded" and self.completeness == "complete":
            raise ProtocolShapeError("non-successful execution cannot claim complete enumeration")
        if self.contract_validity != "valid" and self.execution == "succeeded":
            raise ProtocolShapeError(
                "invalid/unsupported contract cannot claim successful execution"
            )
        if self.capability == "rejected" and self.execution == "succeeded":
            raise ProtocolShapeError("rejected capability cannot claim successful execution")
        if self.exact_local_closure == "resolved" and self.scenario_resolution != "resolved":
            raise ProtocolShapeError("resolved exact-local closure requires resolved Scenario")
        object.__setattr__(
            self,
            "assessment_digest",
            _token(
                "goal_technical_assessment_v1",
                (
                    self.plan_digest,
                    self.result_digest,
                    self.scenario_resolution,
                    self.execution,
                    self.parity,
                    self.completeness,
                    self.expectation,
                    self.explain,
                    self.replay,
                    self.contract_validity,
                    self.exact_local_closure,
                    self.capability,
                ),
            ),
        )


__all__ = [
    "ContainsRowExpectationV1",
    "CapabilityStateV1",
    "ContractValidityStateV1",
    "CountEqExpectationV1",
    "ExecutionStateV1",
    "ExactLocalAbsenceExpectationV1",
    "ExactLocalClosureStateV1",
    "ExistsExpectationV1",
    "ExplainStateV1",
    "GoalCompletenessV1",
    "GoalExpectationKindV1",
    "GoalExpectationOutcomeV1",
    "GoalExpectationStatusV1",
    "GoalExpectationV1",
    "GoalExistsValueV1",
    "GoalPlanV1",
    "GoalResultModeV1",
    "GoalResultRowV1",
    "GoalResultV1",
    "GoalRowAnchorV1",
    "GoalRowExpectationV1",
    "GoalSelectionV1",
    "GoalSummaryAnchorV1",
    "GoalTargetKindV1",
    "GoalTargetRefV1",
    "GoalTechnicalAssessmentV1",
    "GoalValueStorageV1",
    "GoalValueTagV1",
    "GoalValueV1",
    "ParityStateV1",
    "ReplayStateV1",
    "ScenarioResolutionStateV1",
    "SetEqualsExpectationV1",
]
