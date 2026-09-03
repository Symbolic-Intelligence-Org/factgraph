from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, TypeAlias

from factgraph.core.protocol.digests import sha256_token
from factgraph.core.store._support import BindingItems, ProofReceipt, compute_support_digest

if TYPE_CHECKING:
    from factgraph.application.protocol.common import WarningDTO
else:
    WarningDTO = Any

JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]


ROUND_EVENT_SCHEMA_VERSION = "1.0"
ROUND_EVENTS_AUDIT_FILE_KEY = "round_events"
ROUND_EVENTS_REL_PATH = "audit/round_events.jsonl"

ROUND_EVENT_KINDS = frozenset(
    {
        "round_started",
        "check_result",
        "diagnose_result",
        "fact_overlay_result",
        "why_not_result",
        "proof_frame_result",
        "round_finalized",
    }
)
_LIFECYCLE_KINDS = frozenset({"round_started", "round_finalized"})


class RoundEventError(ValueError):
    """Raised when round-event construction or recording violates the scoped contract."""


@dataclass(frozen=True)
class RoundEvent:
    round_id: str
    sequence: int
    event_ts: int
    kind: str
    schema_version: str
    payload: Mapping[str, JSONValue]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.round_id, field_name="round_id")
        _validate_non_negative_int(self.sequence, field_name="sequence")
        _validate_non_negative_int(self.event_ts, field_name="event_ts")
        _require_non_empty_str(self.kind, field_name="kind")
        _require_non_empty_str(self.schema_version, field_name="schema_version")
        object.__setattr__(
            self,
            "payload",
            _validate_json_mapping(self.payload, field_name="payload"),
        )

    @property
    def event_id(self) -> str:
        return f"{self.round_id}:{self.sequence}"


@dataclass(frozen=True)
class RoundSummary:
    round_id: str
    event_count: int
    kind_counts: dict[str, int]
    started_at: int | None
    finalized_at: int | None
    is_finalized: bool
    sequence_gaps: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_non_empty_str(self.round_id, field_name="round_id")
        _validate_non_negative_int(self.event_count, field_name="event_count")
        if self.started_at is not None:
            _validate_non_negative_int(self.started_at, field_name="started_at")
        if self.finalized_at is not None:
            _validate_non_negative_int(self.finalized_at, field_name="finalized_at")
        if not isinstance(self.is_finalized, bool):
            raise RoundEventError("is_finalized must be bool")
        if not isinstance(self.kind_counts, dict):
            raise RoundEventError("kind_counts must be dict[str, int]")
        normalized_counts: dict[str, int] = {}
        for kind, count in self.kind_counts.items():
            _require_non_empty_str(kind, field_name="kind_counts.<key>")
            normalized_counts[kind] = _validate_non_negative_int(
                count, field_name=f"kind_counts[{kind!r}]"
            )
        object.__setattr__(self, "kind_counts", normalized_counts)
        if not isinstance(self.sequence_gaps, tuple):
            raise RoundEventError("sequence_gaps must be tuple[int, ...]")
        for idx, gap in enumerate(self.sequence_gaps):
            _validate_non_negative_int(gap, field_name=f"sequence_gaps[{idx}]")


@dataclass
class RoundRecorder:
    round_id: str
    _events: list[RoundEvent] = field(default_factory=list)
    _started: bool = False
    _finalized: bool = False

    def start(self, *, event_ts: int | None = None) -> RoundEvent:
        if self._started:
            raise RoundEventError("round already started")
        event = make_round_started_event(self.round_id, event_ts=_coerce_event_ts(event_ts))
        self._events.append(event)
        self._started = True
        return event

    def record(
        self,
        *,
        kind: str,
        payload: Mapping[str, JSONValue],
        event_ts: int | None = None,
    ) -> RoundEvent:
        if not self._started:
            raise RoundEventError("round must be started before recording events")
        if self._finalized:
            raise RoundEventError("round already finalized")
        if kind in _LIFECYCLE_KINDS:
            raise RoundEventError("lifecycle events are managed by start/finalize")
        if kind not in ROUND_EVENT_KINDS:
            raise RoundEventError(f"unknown first-slice round event kind: {kind}")
        event = RoundEvent(
            round_id=self.round_id,
            sequence=len(self._events),
            event_ts=_coerce_event_ts(event_ts),
            kind=kind,
            schema_version=ROUND_EVENT_SCHEMA_VERSION,
            payload=payload,
        )
        self._events.append(event)
        return event

    def finalize(self, package_dir: str | Path, *, event_ts: int | None = None) -> Path:
        if not self._started:
            raise RoundEventError("round must be started before finalize")
        if self._finalized:
            raise RoundEventError("round already finalized")
        finalized = make_round_finalized_event(
            self.round_id,
            sequence=len(self._events),
            events=tuple(self._events),
            event_ts=_coerce_event_ts(event_ts),
        )
        candidate_events = tuple(self._events) + (finalized,)
        path = write_round_events_atomic(package_dir, candidate_events)
        self._events.append(finalized)
        self._finalized = True
        return path

    @property
    def events(self) -> tuple[RoundEvent, ...]:
        return tuple(self._events)


def start_round(round_id: str, *, event_ts: int | None = None) -> RoundRecorder:
    _require_non_empty_str(round_id, field_name="round_id")
    recorder = RoundRecorder(round_id=round_id)
    recorder.start(event_ts=event_ts)
    return recorder


def record_round_event(
    recorder: RoundRecorder,
    *,
    kind: str,
    payload: Mapping[str, JSONValue],
    event_ts: int | None = None,
) -> RoundEvent:
    if not isinstance(recorder, RoundRecorder):
        raise RoundEventError("recorder must be RoundRecorder")
    return recorder.record(kind=kind, payload=payload, event_ts=event_ts)


def finalize_round(
    recorder: RoundRecorder,
    package_dir: str | Path,
    *,
    event_ts: int | None = None,
) -> Path:
    if not isinstance(recorder, RoundRecorder):
        raise RoundEventError("recorder must be RoundRecorder")
    return recorder.finalize(package_dir, event_ts=event_ts)


def make_round_started_event(round_id: str, *, event_ts: int | None = None) -> RoundEvent:
    timestamp = _coerce_event_ts(event_ts)
    return RoundEvent(
        round_id=round_id,
        sequence=0,
        event_ts=timestamp,
        kind="round_started",
        schema_version=ROUND_EVENT_SCHEMA_VERSION,
        payload={"started_at": timestamp},
    )


def make_round_finalized_event(
    round_id: str,
    *,
    sequence: int,
    events: tuple[RoundEvent, ...],
    event_ts: int | None = None,
) -> RoundEvent:
    timestamp = _coerce_event_ts(event_ts)
    capability_events = [event for event in events if event.kind not in _LIFECYCLE_KINDS]
    kind_counts: dict[str, int] = {}
    for event in capability_events:
        kind_counts[event.kind] = kind_counts.get(event.kind, 0) + 1
    return RoundEvent(
        round_id=round_id,
        sequence=sequence,
        event_ts=timestamp,
        kind="round_finalized",
        schema_version=ROUND_EVENT_SCHEMA_VERSION,
        payload={
            "finalized_at": timestamp,
            "event_count": len(capability_events),
            "kind_counts": kind_counts,
        },
    )


def round_event_to_row(event: RoundEvent) -> dict[str, JSONValue]:
    if not isinstance(event, RoundEvent):
        raise RoundEventError("event must be RoundEvent")
    return {
        "round_id": event.round_id,
        "sequence": event.sequence,
        "event_ts": event.event_ts,
        "kind": event.kind,
        "schema_version": event.schema_version,
        "payload": dict(event.payload),
    }


def round_event_from_row(row: Mapping[str, Any]) -> RoundEvent:
    if not isinstance(row, Mapping):
        raise RoundEventError("round event row must be object")
    schema_version = row.get("schema_version")
    kind = row.get("kind")
    if isinstance(kind, str) and kind and isinstance(schema_version, str):
        major_part = schema_version.split(".", 1)[0]
        if major_part.isdigit() and int(major_part) >= 2:
            kind = f"future:{kind}"
    return RoundEvent(
        round_id=row.get("round_id"),
        sequence=row.get("sequence"),
        event_ts=row.get("event_ts"),
        kind=kind,
        schema_version=schema_version,
        payload=row.get("payload"),
    )


def write_round_events_atomic(package_dir: str | Path, events: tuple[RoundEvent, ...]) -> Path:
    root = Path(package_dir)
    audit_dir = root / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    target = root / ROUND_EVENTS_REL_PATH
    new_round_ids = {event.round_id for event in events}
    preserved_rows: list[dict[str, JSONValue]] = []
    if target.exists():
        with target.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if row.get("round_id") in new_round_ids:
                    continue
                preserved_rows.append(row)
    new_rows = [round_event_to_row(event) for event in events]
    _replace_jsonl(target, preserved_rows + new_rows)
    _record_round_events_manifest_entry(root)
    return target


def project_check_event_payload(request: Any, result: Any) -> dict[str, JSONValue]:
    evidence = getattr(result, "evidence_envelope", None)
    evidence_payload: dict[str, JSONValue] | None = None
    if evidence is not None:
        support_digest = getattr(evidence, "support_digest", None)
        as_of_event_seq = getattr(evidence, "as_of_event_seq", None)
        if (
            not isinstance(as_of_event_seq, tuple)
            or len(as_of_event_seq) != 2
            or any(
                isinstance(part, bool) or not isinstance(part, int) or part < 0
                for part in as_of_event_seq
            )
        ):
            raise RoundEventError(
                "evidence_envelope.as_of_event_seq must be a "
                "(tx_seq, op_ordinal) pair of non-negative ints"
            )
        evidence_payload = {
            "engine_payload_kind": str(getattr(evidence, "support_kind", "")),
            "payload_digest": str(support_digest) if isinstance(support_digest, str) else _opaque_digest(evidence),
            "as_of_event_seq": list(as_of_event_seq),
        }
    return {
        "request": {
            "plan_digest": _plan_digest(getattr(request, "plan", None)),
            "binding": project_binding_items(getattr(request, "binding", ())),
            "engine": str(getattr(request, "engine", "")),
        },
        "result": {
            "status": str(getattr(result, "status", "")),
            "requested_binding": project_binding_items(getattr(result, "requested_binding", ())),
            "matched_count": _optional_int(getattr(result, "matched_count", None)),
            "matched_binding": project_optional_binding_items(getattr(result, "matched_binding", None)),
            "evidence_envelope": evidence_payload,
        },
        "errors": project_messages(getattr(result, "errors", ())),
        "warnings": project_messages(getattr(result, "warnings", ())),
    }


def project_diagnose_event_payload(request: Any, result: Any) -> dict[str, JSONValue]:
    locator = getattr(result, "diagnostic_payload", None)
    diagnostic_payload: dict[str, JSONValue] | None = None
    if locator is not None:
        diagnostic_payload = {
            "case_index": int(getattr(locator, "case_index", 0)),
            "failed_atom_index": int(getattr(locator, "failed_atom_index", 0)),
            "attempted_binding": project_binding_items(getattr(locator, "attempted_binding", ())),
        }
    return {
        "request": {
            "plan_digest": _plan_digest(getattr(request, "plan", None)),
            "binding": project_binding_items(getattr(request, "binding", ())),
            "engine": str(getattr(request, "engine", "")),
        },
        "result": {
            "status": str(getattr(result, "status", "")),
            "requested_binding": project_binding_items(getattr(result, "requested_binding", ())),
            "matched_count": _optional_int(getattr(result, "matched_count", None)),
            "matched_binding": project_optional_binding_items(getattr(result, "matched_binding", None)),
            "failure_kind": _optional_str(getattr(result, "failure_kind", None)),
            "diagnostic_payload": diagnostic_payload,
        },
        "errors": project_messages(getattr(result, "errors", ())),
        "warnings": project_messages(getattr(result, "warnings", ())),
    }


def project_fact_overlay_event_payload(request: Any, result: Any) -> dict[str, JSONValue]:
    return {
        "request": {
            "plan_digest": _plan_digest(getattr(request, "plan", None)),
            "binding": project_binding_items(getattr(request, "binding", ())),
            "overlay_digest": _opaque_digest(getattr(request, "overlay", None)),
            "engine": str(getattr(request, "engine", "")),
        },
        "result": {
            "status": str(getattr(result, "status", "")),
            "requested_binding": project_binding_items(getattr(result, "requested_binding", ())),
            "before": _project_overlay_phase(getattr(result, "before", None)),
            "after": _project_overlay_phase(getattr(result, "after", None)),
            "diff": _project_overlay_diff(getattr(result, "diff", None)),
        },
        "errors": project_messages(getattr(result, "errors", ())),
        "warnings": project_messages(getattr(result, "warnings", ())),
    }


def project_why_not_event_payload(request: Any, result: Any) -> dict[str, JSONValue]:
    return {
        "request": {
            "plan_digest": _plan_digest(getattr(request, "plan", None)),
            "candidate_universe": project_binding_items_tuple(
                getattr(request, "candidate_universe", ())
            ),
            "engine": str(getattr(request, "engine", "")),
        },
        "result": {
            "status": str(getattr(result, "status", "")),
            "requested_universe": project_binding_items_tuple(
                getattr(result, "requested_universe", ())
            ),
            "passed": project_binding_items_tuple(getattr(result, "passed", ())),
            "failed": [
                {
                    "binding": project_binding_items(getattr(row, "binding", ())),
                    "diagnostic": _project_why_not_diagnostic(
                        getattr(row, "diagnostic", None)
                    ),
                }
                for row in getattr(result, "failed", ())
            ],
        },
        "errors": project_messages(getattr(result, "errors", ())),
        "warnings": project_messages(getattr(result, "warnings", ())),
    }


def project_proof_frame_event_payload(request: Any, result: Any) -> dict[str, JSONValue]:
    support = getattr(request, "support_artifact", None)
    support_digest = compute_support_digest(support) if isinstance(support, ProofReceipt) else _opaque_digest(support)
    return {
        "request": {
            "support_digest": support_digest,
            "overlay_digest": _opaque_digest(getattr(request, "overlay", None)),
        },
        "result": {
            "status": str(getattr(result, "status", "")),
            "binding_items": project_binding_items(getattr(result, "binding_items", ())),
            "atom_verdicts": [
                {
                    "condition_key": str(getattr(verdict, "condition_key", "")),
                    "verdict": str(getattr(verdict, "verdict", "")),
                    "affected_action_indices": [
                        int(index)
                        for index in getattr(verdict, "affected_action_indices", ())
                    ],
                }
                for verdict in getattr(result, "atom_verdicts", ())
            ],
        },
    }


def project_binding_items(binding_items: BindingItems | Any) -> list[list[JSONValue]]:
    if not isinstance(binding_items, tuple):
        raise RoundEventError("binding_items must be BindingItems tuple")
    rows: list[list[JSONValue]] = []
    for idx, item in enumerate(binding_items):
        if not isinstance(item, tuple) or len(item) != 2:
            raise RoundEventError(f"binding_items[{idx}] must be tuple[str, Any]")
        name, value = item
        if not isinstance(name, str) or not name:
            raise RoundEventError(f"binding_items[{idx}][0] must be non-empty string")
        rows.append([name, project_json_value(value)])
    return rows


def project_optional_binding_items(binding_items: BindingItems | None) -> list[list[JSONValue]] | None:
    if binding_items is None:
        return None
    return project_binding_items(binding_items)


def project_binding_items_tuple(bindings: Any) -> list[list[list[JSONValue]]]:
    if not isinstance(bindings, tuple):
        raise RoundEventError("bindings must be tuple[BindingItems, ...]")
    return [project_binding_items(binding) for binding in bindings]


def project_messages(messages: Any) -> list[dict[str, JSONValue]]:
    if not isinstance(messages, tuple):
        raise RoundEventError("messages must be tuple")
    return [
        {
            "code": str(getattr(message, "code", "")),
            "message": str(getattr(message, "message", "")),
            "path": [str(segment) for segment in getattr(message, "path", ())],
            "details": project_json_value(dict(getattr(message, "details", {}))),
        }
        for message in messages
    ]


def project_json_value(value: Any) -> JSONValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return [project_json_value(item) for item in value]
    if isinstance(value, list):
        return [project_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): project_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    return {"opaque_digest": _opaque_digest(value), "opaque_type": _qualified_type_name(value)}


def summarize_round_events(round_id: str, events: tuple[RoundEvent, ...]) -> RoundSummary:
    if not events:
        return RoundSummary(
            round_id=round_id,
            event_count=0,
            kind_counts={},
            started_at=None,
            finalized_at=None,
            is_finalized=False,
            sequence_gaps=(),
        )
    kind_counts: dict[str, int] = {}
    started_at: int | None = None
    finalized_at: int | None = None
    for event in events:
        kind_counts[event.kind] = kind_counts.get(event.kind, 0) + 1
        if event.kind == "round_started" and started_at is None:
            value = event.payload.get("started_at")
            started_at = value if isinstance(value, int) and not isinstance(value, bool) else event.event_ts
        if event.kind == "round_finalized":
            value = event.payload.get("finalized_at")
            finalized_at = value if isinstance(value, int) and not isinstance(value, bool) else event.event_ts
    sequences = sorted(event.sequence for event in events)
    gaps = tuple(value for value in range(sequences[0], sequences[-1] + 1) if value not in set(sequences))
    return RoundSummary(
        round_id=round_id,
        event_count=sum(count for kind, count in kind_counts.items() if kind not in _LIFECYCLE_KINDS),
        kind_counts=kind_counts,
        started_at=started_at,
        finalized_at=finalized_at,
        is_finalized=finalized_at is not None,
        sequence_gaps=gaps,
    )


def warning_to_row(warning: WarningDTO) -> dict[str, JSONValue]:
    return {
        "code": warning.code,
        "message": warning.message,
        "path": list(warning.path),
        "details": dict(warning.details),
    }


def make_warning(
    *,
    code: str,
    message: str,
    path: tuple[str, ...] = (),
    details: Mapping[str, JSONValue] | None = None,
) -> WarningDTO:
    from factgraph.application.protocol.common import WarningDTO as _WarningDTO

    return _WarningDTO(code=code, message=message, path=path, details=dict(details or {}))


def _project_overlay_phase(phase: Any) -> dict[str, JSONValue] | None:
    if phase is None:
        return None
    return {
        "status": str(getattr(phase, "status", "")),
        "matched_binding": project_optional_binding_items(getattr(phase, "matched_binding", None)),
    }


def _project_overlay_diff(diff: Any) -> dict[str, JSONValue] | None:
    if diff is None:
        return None
    return {
        "status_changed": bool(getattr(diff, "status_changed", False)),
        "matched_count_delta": int(getattr(diff, "matched_count_delta", 0)),
        "bindings_added": project_binding_items_tuple(getattr(diff, "bindings_added", ())),
        "bindings_removed": project_binding_items_tuple(getattr(diff, "bindings_removed", ())),
    }


def _project_why_not_diagnostic(diagnostic: Any) -> dict[str, JSONValue]:
    locator = getattr(diagnostic, "atom_locator", None)
    return {
        "status": str(getattr(diagnostic, "status", "")),
        "failure_kind": _optional_str(getattr(diagnostic, "failure_kind", None)),
        "diagnostic_granularity": str(getattr(diagnostic, "diagnostic_granularity", "")),
        "atom_locator": _project_why_not_atom_locator(locator),
        "errors": project_messages(getattr(diagnostic, "errors", ())),
        "warnings": project_messages(getattr(diagnostic, "warnings", ())),
    }


def _project_why_not_atom_locator(locator: Any) -> dict[str, JSONValue] | None:
    if locator is None:
        return None
    return {
        "case_index": int(getattr(locator, "case_index", 0)),
        "failed_atom_index": int(getattr(locator, "failed_atom_index", 0)),
        "attempted_binding": project_binding_items(getattr(locator, "attempted_binding", ())),
    }


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise RoundEventError("expected int or None")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _plan_digest(plan: Any) -> str:
    if plan is None:
        return _opaque_digest(None)
    payload = {
        "derivation_id": getattr(plan, "derivation_id", None),
        "version": getattr(plan, "version", None),
        "body_ir": project_json_value(getattr(plan, "body_ir", None)),
        "heads": project_json_value(
            tuple(
                {
                    "target_pred_id": getattr(head, "target_pred_id", None),
                    "head_var_names": list(getattr(head, "head_var_names", ())),
                }
                for head in getattr(plan, "heads", ())
            )
        ),
    }
    return _digest_json(payload)


def _opaque_digest(value: Any) -> str:
    return _digest_json(_stable_digest_projection(value))


def _stable_digest_projection(value: Any) -> JSONValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return [_stable_digest_projection(item) for item in value]
    if isinstance(value, list):
        return [_stable_digest_projection(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _stable_digest_projection(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if is_dataclass(value):
        return {
            "__type__": _qualified_type_name(value),
            "fields": {
                field.name: _stable_digest_projection(getattr(value, field.name))
                for field in fields(value)
            },
        }
    return {"__type__": _qualified_type_name(value)}


def _digest_json(payload: JSONValue) -> str:
    return sha256_token(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    )


def _qualified_type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def _replace_jsonl(path: Path, rows: list[dict[str, JSONValue]]) -> None:
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
                handle.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def _record_round_events_manifest_entry(root: Path) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise RoundEventError(f"missing manifest.json: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RoundEventError("manifest.json must be object")
    if payload.get("package_kind") != "audit":
        raise RoundEventError("round events can only be written to audit packages")
    paths = payload.get("paths")
    if not isinstance(paths, dict):
        raise RoundEventError("manifest.paths must be object")
    audit_files = paths.get("audit_files")
    if not isinstance(audit_files, dict):
        raise RoundEventError("manifest.paths.audit_files must be object")
    audit_files[ROUND_EVENTS_AUDIT_FILE_KEY] = ROUND_EVENTS_REL_PATH
    _replace_json(manifest_path, payload)


def _replace_json(path: Path, payload: dict[str, Any]) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def _coerce_event_ts(value: int | None) -> int:
    if value is None:
        return time.time_ns()
    return _validate_non_negative_int(value, field_name="event_ts")


def _validate_non_negative_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RoundEventError(f"{field_name} must be non-negative int")
    return value


def _require_non_empty_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RoundEventError(f"{field_name} must be non-empty string")
    return value


def _validate_json_mapping(value: Any, *, field_name: str) -> dict[str, JSONValue]:
    if not isinstance(value, Mapping):
        raise RoundEventError(f"{field_name} must be Mapping[str, JSONValue]")
    return {
        str(key): _validate_json_value(item, field_name=f"{field_name}[{key!r}]")
        for key, item in value.items()
    }


def _validate_json_value(value: Any, *, field_name: str) -> JSONValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_validate_json_value(item, field_name=f"{field_name}[]") for item in value]
    if isinstance(value, dict):
        return {
            str(key): _validate_json_value(item, field_name=f"{field_name}[{key!r}]")
            for key, item in value.items()
        }
    raise RoundEventError(f"{field_name} must be JSONValue")


__all__ = [
    "ROUND_EVENTS_AUDIT_FILE_KEY",
    "ROUND_EVENTS_REL_PATH",
    "ROUND_EVENT_KINDS",
    "ROUND_EVENT_SCHEMA_VERSION",
    "RoundEvent",
    "RoundEventError",
    "RoundRecorder",
    "RoundSummary",
    "finalize_round",
    "make_round_finalized_event",
    "make_round_started_event",
    "project_binding_items",
    "project_check_event_payload",
    "project_diagnose_event_payload",
    "project_fact_overlay_event_payload",
    "project_json_value",
    "project_messages",
    "project_proof_frame_event_payload",
    "project_why_not_event_payload",
    "record_round_event",
    "round_event_from_row",
    "round_event_to_row",
    "start_round",
    "summarize_round_events",
    "warning_to_row",
    "write_round_events_atomic",
]
