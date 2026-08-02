"""Narrow audit/debug access to ordered claim-meta events.

This module deliberately does not add a general SDK history namespace.  It
exposes immutable event DTOs, deterministic export/import, and as-of effective
resolution for audit and explain tooling only.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from factgraph.core.store.ledger import Ledger, META_KINDS, _normalize_event_sequence

_JSON_BYTES_KEY = "__factgraph_meta_bytes_b64__"


class MetaHistoryError(ValueError):
    """Raised when an audit meta-history payload is malformed."""


@dataclass(frozen=True)
class MetaHistoryEvent:
    asrt_id: str
    key: str
    kind: str | None
    value: Any
    tx_seq: int
    op_ordinal: int

    def __post_init__(self) -> None:
        if not isinstance(self.asrt_id, str) or not self.asrt_id:
            raise MetaHistoryError("asrt_id must be non-empty string")
        if not isinstance(self.key, str) or not self.key:
            raise MetaHistoryError("key must be non-empty string")
        if self.kind is None:
            if self.value is not None:
                raise MetaHistoryError("UNSET event kind/value must both be null")
        elif self.kind not in META_KINDS:
            raise MetaHistoryError(f"unsupported meta kind: {self.kind!r}")
        _normalize_event_sequence((self.tx_seq, self.op_ordinal))

    @property
    def event_seq(self) -> tuple[int, int]:
        return (self.tx_seq, self.op_ordinal)

    @property
    def is_unset(self) -> bool:
        return self.kind is None


def read_meta_history(
    ledger: Ledger,
    *,
    asrt_id: str | None = None,
    key: str | None = None,
) -> tuple[MetaHistoryEvent, ...]:
    """Read ordered immutable events from one Ledger for audit/debug use."""
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    return tuple(
        MetaHistoryEvent(
            asrt_id=event.asrt_id,
            key=event.key,
            kind=event.kind,
            value=event.value,
            tx_seq=event.tx_seq,
            op_ordinal=event.op_ordinal,
        )
        for event in ledger._meta_history_events(asrt_id=asrt_id, key=key)
    )


def effective_meta_at(
    ledger: Ledger,
    *,
    asrt_id: str,
    as_of: tuple[int, int],
) -> dict[str, Any]:
    """Return effective key/value state at an inclusive event boundary."""
    boundary = _normalize_event_sequence(as_of)
    assert boundary is not None
    return {
        event.key: event.value
        for event in ledger._effective_meta_events(asrt_id=asrt_id, as_of=boundary)
    }


def export_meta_history(
    ledger: Ledger,
    *,
    asrt_id: str | None = None,
    key: str | None = None,
) -> bytes:
    """Export canonical bytes without changing event order."""
    return _history_bytes(read_meta_history(ledger, asrt_id=asrt_id, key=key))


def import_meta_history(data: bytes) -> tuple[MetaHistoryEvent, ...]:
    """Parse and validate canonical audit bytes without mutating a Ledger."""
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise MetaHistoryError("meta history must be valid UTF-8 JSON") from exc
    if not isinstance(payload, list):
        raise MetaHistoryError("meta history payload must be a list")
    events: list[MetaHistoryEvent] = []
    for index, raw in enumerate(payload):
        if not isinstance(raw, Mapping) or set(raw) != {
            "asrt_id",
            "key",
            "kind",
            "value",
            "tx_seq",
            "op_ordinal",
        }:
            raise MetaHistoryError(f"event[{index}] has invalid fields")
        events.append(
            MetaHistoryEvent(
                asrt_id=raw["asrt_id"],
                key=raw["key"],
                kind=raw["kind"],
                value=_from_jsonable(raw["value"]),
                tx_seq=raw["tx_seq"],
                op_ordinal=raw["op_ordinal"],
            )
        )
    ordered = tuple(sorted(events, key=_event_sort_key))
    if tuple(events) != ordered:
        raise MetaHistoryError("meta history events are not in canonical event order")
    if _history_bytes(ordered) != data:
        raise MetaHistoryError("meta history payload is not canonically encoded")
    return ordered


def _history_bytes(events: Sequence[MetaHistoryEvent]) -> bytes:
    return json.dumps(
        [
            {
                "asrt_id": event.asrt_id,
                "key": event.key,
                "kind": event.kind,
                "value": _to_jsonable(event.value),
                "tx_seq": event.tx_seq,
                "op_ordinal": event.op_ordinal,
            }
            for event in events
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _event_sort_key(event: MetaHistoryEvent) -> tuple[int, int, str, str]:
    return (event.tx_seq, event.op_ordinal, event.asrt_id, event.key)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {_JSON_BYTES_KEY: base64.urlsafe_b64encode(value).decode("ascii")}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_from_jsonable(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {_JSON_BYTES_KEY}:
            encoded = value[_JSON_BYTES_KEY]
            if not isinstance(encoded, str):
                raise MetaHistoryError("encoded bytes payload must be string")
            try:
                return base64.urlsafe_b64decode(encoded.encode("ascii"))
            except (UnicodeError, ValueError) as exc:
                raise MetaHistoryError("invalid encoded bytes payload") from exc
        return {str(key): _from_jsonable(item) for key, item in value.items()}
    return value


__all__ = [
    "MetaHistoryError",
    "MetaHistoryEvent",
    "effective_meta_at",
    "export_meta_history",
    "import_meta_history",
    "read_meta_history",
]
