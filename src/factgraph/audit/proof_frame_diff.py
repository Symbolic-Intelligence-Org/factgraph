from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, TypeAlias

from factgraph.application.protocol.common import JSONValue, WarningDTO
from factgraph.application.protocol.proofframe import ProofFrameStatus

from .round_events import RoundEvent

AtomDeltaKind: TypeAlias = Literal["atom_added", "atom_removed", "atom_verdict_changed"]
FrameMarker: TypeAlias = Literal["rule_refs_unsupported"]

_ATOM_DELTA_KINDS = ("atom_added", "atom_removed", "atom_verdict_changed")
_FRAME_MARKERS = ("rule_refs_unsupported",)
_PROOF_FRAME_STATUSES = ("still_valid", "invalidated", "unknown")

BindingJSON: TypeAlias = tuple[tuple[str, JSONValue], ...]


class ProofFrameDiffError(ValueError):
    """Raised when persisted ProofFrame round-event payloads cannot be diffed."""


@dataclass(frozen=True)
class EventReference:
    round_id: str
    sequence: int

    def __post_init__(self) -> None:
        _require_non_empty_str(self.round_id, field_name="round_id")
        _require_non_negative_int(self.sequence, field_name="sequence")


@dataclass(frozen=True)
class FrameIdentity:
    support_digest: str
    binding_items: BindingJSON

    def __post_init__(self) -> None:
        _require_non_empty_str(self.support_digest, field_name="support_digest")
        object.__setattr__(
            self,
            "binding_items",
            _validate_binding_json(self.binding_items, field_name="binding_items"),
        )


@dataclass(frozen=True)
class FrameStatusChange:
    before: ProofFrameStatus | None
    after: ProofFrameStatus | None

    def __post_init__(self) -> None:
        if self.before is not None:
            _validate_proof_frame_status(self.before, field_name="before")
        if self.after is not None:
            _validate_proof_frame_status(self.after, field_name="after")


@dataclass(frozen=True)
class AtomDelta:
    condition_key: str
    kind: AtomDeltaKind
    before_verdict: ProofFrameStatus | None
    after_verdict: ProofFrameStatus | None

    def __post_init__(self) -> None:
        _require_non_empty_str(self.condition_key, field_name="condition_key")
        _validate_literal(self.kind, field_name="kind", allowed=_ATOM_DELTA_KINDS)
        if self.before_verdict is not None:
            _validate_proof_frame_status(self.before_verdict, field_name="before_verdict")
        if self.after_verdict is not None:
            _validate_proof_frame_status(self.after_verdict, field_name="after_verdict")
        if self.kind == "atom_added":
            if self.before_verdict is not None or self.after_verdict is None:
                raise ProofFrameDiffError("atom_added requires before_verdict=None and after_verdict")
        elif self.kind == "atom_removed":
            if self.before_verdict is None or self.after_verdict is not None:
                raise ProofFrameDiffError("atom_removed requires before_verdict and after_verdict=None")
        elif self.kind == "atom_verdict_changed":
            if self.before_verdict is None or self.after_verdict is None:
                raise ProofFrameDiffError("atom_verdict_changed requires both verdicts")
            if self.before_verdict == self.after_verdict:
                raise ProofFrameDiffError("atom_verdict_changed requires different verdicts")


@dataclass(frozen=True)
class FrameDelta:
    frame_identity: FrameIdentity
    source_a: EventReference | None
    source_b: EventReference | None
    frame_status_change: FrameStatusChange | None
    atom_deltas: tuple[AtomDelta, ...] = ()
    markers: tuple[FrameMarker, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.frame_identity, FrameIdentity):
            raise ProofFrameDiffError("frame_identity must be FrameIdentity")
        if self.source_a is not None and not isinstance(self.source_a, EventReference):
            raise ProofFrameDiffError("source_a must be EventReference or None")
        if self.source_b is not None and not isinstance(self.source_b, EventReference):
            raise ProofFrameDiffError("source_b must be EventReference or None")
        if self.source_a is None and self.source_b is None:
            raise ProofFrameDiffError("FrameDelta requires at least one source")
        if self.frame_status_change is not None and not isinstance(
            self.frame_status_change, FrameStatusChange
        ):
            raise ProofFrameDiffError("frame_status_change must be FrameStatusChange or None")
        object.__setattr__(
            self,
            "atom_deltas",
            _validate_tuple_items(self.atom_deltas, field_name="atom_deltas", item_type=AtomDelta),
        )
        markers = _validate_markers(self.markers)
        object.__setattr__(self, "markers", markers)
        if markers and self.atom_deltas:
            raise ProofFrameDiffError("marked frames must not carry atom_deltas")


@dataclass(frozen=True)
class ProofFrameDiff:
    round_a_id: str
    round_b_id: str
    frame_deltas: tuple[FrameDelta, ...]
    warnings: tuple[WarningDTO, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.round_a_id, field_name="round_a_id")
        _require_non_empty_str(self.round_b_id, field_name="round_b_id")
        object.__setattr__(
            self,
            "frame_deltas",
            _validate_tuple_items(
                self.frame_deltas,
                field_name="frame_deltas",
                item_type=FrameDelta,
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            _validate_tuple_items(self.warnings, field_name="warnings", item_type=WarningDTO),
        )


@dataclass(frozen=True)
class _ProofFrameRecord:
    identity: FrameIdentity
    source: EventReference
    status: ProofFrameStatus
    atoms: dict[str, ProofFrameStatus]

    @property
    def rule_refs_unsupported(self) -> bool:
        return not self.atoms


def build_proof_frame_diff(
    *,
    round_a_id: str,
    round_b_id: str,
    round_a_events: tuple[RoundEvent, ...],
    round_b_events: tuple[RoundEvent, ...],
    warnings: tuple[WarningDTO, ...] = (),
    include_unchanged: bool = False,
) -> ProofFrameDiff:
    """Build a deterministic L4 ProofFrame diff from two rounds' events."""

    _require_non_empty_str(round_a_id, field_name="round_a_id")
    _require_non_empty_str(round_b_id, field_name="round_b_id")
    records_a = _proof_frame_records(round_a_events)
    records_b = _proof_frame_records(round_b_events)
    keys = sorted(set(records_a) | set(records_b))
    deltas: list[FrameDelta] = []
    for key in keys:
        delta = _diff_frame_records(
            records_a.get(key),
            records_b.get(key),
            include_unchanged=include_unchanged,
        )
        if delta is not None:
            deltas.append(delta)
    return ProofFrameDiff(
        round_a_id=round_a_id,
        round_b_id=round_b_id,
        frame_deltas=tuple(deltas),
        warnings=warnings,
    )


def _proof_frame_records(events: tuple[RoundEvent, ...]) -> dict[tuple[str, str], _ProofFrameRecord]:
    records: dict[tuple[str, str], _ProofFrameRecord] = {}
    for event in sorted(events, key=lambda item: item.sequence):
        if event.kind != "proof_frame_result":
            continue
        record = _proof_frame_record_from_event(event)
        key = _frame_identity_sort_key(record.identity)
        if key in records:
            raise ProofFrameDiffError(
                f"duplicate proof_frame_result frame identity in round {event.round_id} "
                f"at sequence {event.sequence}"
            )
        records[key] = record
    return records


def _proof_frame_record_from_event(event: RoundEvent) -> _ProofFrameRecord:
    payload = event.payload
    request = _require_mapping(payload.get("request"), field_name="payload.request")
    result = _require_mapping(payload.get("result"), field_name="payload.result")
    support_digest = _require_non_empty_str(
        request.get("support_digest"),
        field_name="payload.request.support_digest",
    )
    binding_items = _validate_binding_json(
        result.get("binding_items"),
        field_name="payload.result.binding_items",
    )
    status = _validate_proof_frame_status(
        result.get("status"),
        field_name="payload.result.status",
    )
    atom_verdicts = result.get("atom_verdicts")
    if not isinstance(atom_verdicts, list):
        raise ProofFrameDiffError("payload.result.atom_verdicts must be list")
    atoms: dict[str, ProofFrameStatus] = {}
    for idx, item in enumerate(atom_verdicts):
        row = _require_mapping(item, field_name=f"payload.result.atom_verdicts[{idx}]")
        condition_key = _require_non_empty_str(
            row.get("condition_key"),
            field_name=f"payload.result.atom_verdicts[{idx}].condition_key",
        )
        if condition_key in atoms:
            raise ProofFrameDiffError("payload.result.atom_verdicts must not duplicate condition_key")
        atoms[condition_key] = _validate_proof_frame_status(
            row.get("verdict"),
            field_name=f"payload.result.atom_verdicts[{idx}].verdict",
        )
    return _ProofFrameRecord(
        identity=FrameIdentity(support_digest=support_digest, binding_items=binding_items),
        source=EventReference(round_id=event.round_id, sequence=event.sequence),
        status=status,
        atoms=atoms,
    )


def _diff_frame_records(
    record_a: _ProofFrameRecord | None,
    record_b: _ProofFrameRecord | None,
    *,
    include_unchanged: bool,
) -> FrameDelta | None:
    if record_a is None and record_b is None:
        return None
    record = record_a or record_b
    assert record is not None
    if record_a is None:
        return FrameDelta(
            frame_identity=record.identity,
            source_a=None,
            source_b=record_b.source if record_b is not None else None,
            frame_status_change=None,
        )
    if record_b is None:
        return FrameDelta(
            frame_identity=record.identity,
            source_a=record_a.source,
            source_b=None,
            frame_status_change=None,
        )

    status_change = (
        FrameStatusChange(before=record_a.status, after=record_b.status)
        if record_a.status != record_b.status
        else None
    )
    markers = (
        ("rule_refs_unsupported",)
        if record_a.rule_refs_unsupported or record_b.rule_refs_unsupported
        else ()
    )
    atom_deltas = () if markers else _diff_atoms(record_a.atoms, record_b.atoms)
    if (
        status_change is None
        and not atom_deltas
        and not markers
        and not include_unchanged
    ):
        return None
    return FrameDelta(
        frame_identity=record.identity,
        source_a=record_a.source,
        source_b=record_b.source,
        frame_status_change=status_change,
        atom_deltas=atom_deltas,
        markers=markers,
    )


def _diff_atoms(
    atoms_a: dict[str, ProofFrameStatus],
    atoms_b: dict[str, ProofFrameStatus],
) -> tuple[AtomDelta, ...]:
    deltas: list[AtomDelta] = []
    for condition_key in sorted(set(atoms_a) | set(atoms_b)):
        before = atoms_a.get(condition_key)
        after = atoms_b.get(condition_key)
        if before is None:
            deltas.append(
                AtomDelta(
                    condition_key=condition_key,
                    kind="atom_added",
                    before_verdict=None,
                    after_verdict=after,
                )
            )
        elif after is None:
            deltas.append(
                AtomDelta(
                    condition_key=condition_key,
                    kind="atom_removed",
                    before_verdict=before,
                    after_verdict=None,
                )
            )
        elif before != after:
            deltas.append(
                AtomDelta(
                    condition_key=condition_key,
                    kind="atom_verdict_changed",
                    before_verdict=before,
                    after_verdict=after,
                )
            )
    return tuple(deltas)


def _frame_identity_sort_key(identity: FrameIdentity) -> tuple[str, str]:
    return (
        identity.support_digest,
        json.dumps(identity.binding_items, sort_keys=True, separators=(",", ":")),
    )


def _validate_binding_json(value: Any, *, field_name: str) -> BindingJSON:
    if not isinstance(value, (list, tuple)):
        raise ProofFrameDiffError(f"{field_name} must be binding JSON list")
    rows: list[tuple[str, JSONValue]] = []
    seen: set[str] = set()
    for idx, item in enumerate(value):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ProofFrameDiffError(f"{field_name}[{idx}] must be [str, JSONValue]")
        key = _require_non_empty_str(item[0], field_name=f"{field_name}[{idx}][0]")
        if key in seen:
            raise ProofFrameDiffError(f"{field_name} must not duplicate binding names")
        seen.add(key)
        rows.append((key, _validate_json_value(item[1], field_name=f"{field_name}[{idx}][1]")))
    return tuple(sorted(rows, key=lambda row: row[0]))


def _validate_json_value(value: Any, *, field_name: str) -> JSONValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_validate_json_value(item, field_name=f"{field_name}[]") for item in value]
    if isinstance(value, tuple):
        return [_validate_json_value(item, field_name=f"{field_name}[]") for item in value]
    if isinstance(value, dict):
        return {
            _require_non_empty_str(key, field_name=f"{field_name}.<key>"): _validate_json_value(
                item,
                field_name=f"{field_name}[{key!r}]",
            )
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    raise ProofFrameDiffError(f"{field_name} must be JSONValue")


def _validate_proof_frame_status(value: Any, *, field_name: str) -> ProofFrameStatus:
    return _validate_literal(value, field_name=field_name, allowed=_PROOF_FRAME_STATUSES)


def _validate_literal(value: Any, *, field_name: str, allowed: tuple[str, ...]) -> Any:
    text = _require_non_empty_str(value, field_name=field_name)
    if text not in allowed:
        raise ProofFrameDiffError(f"{field_name} must be one of {allowed}")
    return text


def _validate_markers(value: Any) -> tuple[FrameMarker, ...]:
    if not isinstance(value, tuple):
        raise ProofFrameDiffError("markers must be tuple[FrameMarker, ...]")
    normalized: list[FrameMarker] = []
    seen: set[str] = set()
    for idx, item in enumerate(value):
        marker = _validate_literal(item, field_name=f"markers[{idx}]", allowed=_FRAME_MARKERS)
        if marker in seen:
            raise ProofFrameDiffError("markers must not contain duplicates")
        seen.add(marker)
        normalized.append(marker)
    return tuple(normalized)


def _validate_tuple_items(value: Any, *, field_name: str, item_type: type[Any]) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise ProofFrameDiffError(f"{field_name} must be tuple[{item_type.__name__}, ...]")
    for idx, item in enumerate(value):
        if not isinstance(item, item_type):
            raise ProofFrameDiffError(f"{field_name}[{idx}] must be {item_type.__name__}")
    return value


def _require_mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProofFrameDiffError(f"{field_name} must be object")
    return value


def _require_non_empty_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProofFrameDiffError(f"{field_name} must be non-empty string")
    return value


def _require_non_negative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProofFrameDiffError(f"{field_name} must be non-negative int")
    return value


__all__ = [
    "AtomDelta",
    "AtomDeltaKind",
    "EventReference",
    "FrameDelta",
    "FrameIdentity",
    "FrameMarker",
    "FrameStatusChange",
    "ProofFrameDiff",
    "ProofFrameDiffError",
    "build_proof_frame_diff",
]
