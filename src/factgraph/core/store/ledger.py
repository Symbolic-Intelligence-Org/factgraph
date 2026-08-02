from __future__ import annotations

import base64
import binascii
import json
import math
import sqlite3
import struct
import threading
import uuid
import warnings
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Mapping, Sequence

from factgraph.core.protocol.annotation_v1 import initial_meta_annotation_v1
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms


META_KINDS = {"str", "int", "float", "bool", "time", "json"}
ANNOTATION_ORIGINS = {"observed", "derived"}
ANNOTATION_CATEGORIES = {"source", "semantic", "derived", "operational"}
_JSON_BYTES_KEY = "__factpy_bytes_b64__"


@dataclass(frozen=True)
class Claim:
    asrt_id: str
    pred_id: str
    e_ref: str
    rest_terms: list[tuple[str, Any]]


@dataclass(frozen=True)
class ClaimArg:
    asrt_id: str
    idx: int
    val_atom: Any
    tag: str


@dataclass(frozen=True)
class MetaRow:
    asrt_id: str
    key: str
    kind: str
    value: Any


@dataclass(frozen=True)
class AnnotationRow:
    """Assertion-level annotation per decision blueprint §4.1."""

    asrt_id: str
    namespace: str
    category: str
    key: str
    kind: str
    value: Any
    origin: str
    derivation: str | None = None


@dataclass(frozen=True)
class Revokes:
    revoker_asrt_id: str
    revoked_asrt_id: str


@dataclass(frozen=True)
class Idempotency:
    ingest_key: str
    on_conflict: Literal["skip", "error"] = "skip"


@dataclass(frozen=True)
class AppendResult:
    asrt_id: str
    written: bool


class DuplicateIngestKeyError(Exception):
    """Raised when an ingest key already exists and on_conflict='error'."""


class LedgerHeadConflictError(Exception):
    """Raised when a commit's expected head no longer matches ledger_meta."""


class LedgerFormatError(Exception):
    """Raised when a persisted ledger uses an unsupported physical schema."""


@dataclass(frozen=True)
class LedgerAssertionWrite:
    claim: Claim
    claim_args: tuple[ClaimArg, ...]
    meta_rows: tuple[MetaRow, ...]
    annotation_rows: tuple[AnnotationRow, ...] = ()


@dataclass(frozen=True)
class LedgerRevocationWrite:
    revokes: Revokes
    meta_rows: tuple[MetaRow, ...] = ()
    annotation_rows: tuple[AnnotationRow, ...] = ()


@dataclass(frozen=True)
class _ClaimMetaEvent:
    asrt_id: str
    key: str
    kind: str | None
    value: Any
    tx_seq: int
    op_ordinal: int

    @property
    def event_seq(self) -> tuple[int, int]:
        return (self.tx_seq, self.op_ordinal)

    @property
    def is_unset(self) -> bool:
        return self.kind is None


@dataclass(frozen=True)
class _MetaTombstone:
    """Private carrier for an explicit UNSET event.

    Public/generic meta surfaces accept only ``MetaRow`` and therefore cannot
    forge the dual-NULL storage representation.  Database policy code emits
    this carrier only for an explicit UNSET operation.
    """

    asrt_id: str
    key: str


_DDL = """
CREATE TABLE IF NOT EXISTS claims (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id    TEXT NOT NULL UNIQUE,
    pred_id    TEXT NOT NULL,
    e_ref      TEXT NOT NULL,
    rest_terms TEXT,
    value      TEXT,
    value_tag  TEXT,
    tx_ref     INTEGER NOT NULL,
    CHECK ((value IS NULL) = (value_tag IS NULL))
);

CREATE TABLE IF NOT EXISTS ledger_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_asrt_id ON claims(asrt_id);
CREATE INDEX IF NOT EXISTS idx_claims_pred_id ON claims(pred_id);
CREATE INDEX IF NOT EXISTS idx_claims_e_ref ON claims(e_ref);
CREATE INDEX IF NOT EXISTS idx_claims_pred_eref ON claims(pred_id, e_ref);
CREATE INDEX IF NOT EXISTS idx_claims_pred_value ON claims(pred_id, value);
CREATE INDEX IF NOT EXISTS idx_claims_revokes ON claims(value)
    WHERE pred_id = '__system__.revokes';

CREATE TABLE IF NOT EXISTS claim_meta (
    asrt_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    kind        TEXT,
    value       TEXT,
    tx_seq      INTEGER NOT NULL,
    op_ordinal  INTEGER NOT NULL,
    PRIMARY KEY (asrt_id, key, tx_seq, op_ordinal),
    CHECK ((kind IS NULL) = (value IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_claim_meta_key_value ON claim_meta(key, value);
CREATE INDEX IF NOT EXISTS idx_claim_meta_asrt ON claim_meta(asrt_id);
CREATE INDEX IF NOT EXISTS idx_claim_meta_kind ON claim_meta(kind);
"""

_LEGACY_TABLES = frozenset(
    {"claim_args", "meta_rows", "revokes", "ingest_keys", "annotation_rows"}
)
_SYSTEM_PREFIX = "__system__."
_REVOCATION_PREDICATE = "__system__.revokes"
_ANNOTATION_COMPAT_PREFIX = "__factgraph_annotation_v1__:"


@dataclass(frozen=True)
class _AnnotationStorageMetaRow(MetaRow):
    """Private carrier for annotation compatibility events emitted internally."""


def _is_reserved_annotation_meta_key(key: str) -> bool:
    return key.startswith(_ANNOTATION_COMPAT_PREFIX)


class _MetaRowsProxy(list[MetaRow]):
    def __init__(self, ledger: "Ledger") -> None:
        self._ledger = ledger
        super().__init__(ledger.meta_rows)

    def _flush(self) -> None:
        self._ledger._force_replace_meta_rows(list(self))

    def __setitem__(self, index, value) -> None:
        super().__setitem__(index, value)
        self._flush()

    def __delitem__(self, index) -> None:
        super().__delitem__(index)
        self._flush()

    def append(self, value: MetaRow) -> None:
        super().append(value)
        self._flush()

    def extend(self, values) -> None:
        super().extend(values)
        self._flush()

    def insert(self, index: int, value: MetaRow) -> None:
        super().insert(index, value)
        self._flush()

    def pop(self, index: int = -1):
        value = super().pop(index)
        self._flush()
        return value

    def remove(self, value: MetaRow) -> None:
        super().remove(value)
        self._flush()

    def clear(self) -> None:
        super().clear()
        self._flush()


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {_JSON_BYTES_KEY: base64.b64encode(value).decode("ascii")}
    if isinstance(value, bytearray):
        return {_JSON_BYTES_KEY: base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, memoryview):
        return {_JSON_BYTES_KEY: base64.b64encode(value.tobytes()).decode("ascii")}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value.keys()) == {_JSON_BYTES_KEY} and isinstance(value[_JSON_BYTES_KEY], str):
            return base64.b64decode(value[_JSON_BYTES_KEY].encode("ascii"))
        return {key: _from_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_jsonable(item) for item in value]
    return value


def _enc(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, separators=(",", ":"))


def _dec(raw: str) -> Any:
    return _from_jsonable(json.loads(raw))


def _enc_rest_terms(rest_terms: list[tuple[str, Any]]) -> str:
    payload = [[tag, _to_jsonable(value)] for tag, value in rest_terms]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _dec_rest_terms(raw: str) -> list[tuple[str, Any]]:
    return [(str(tag), _from_jsonable(value)) for tag, value in json.loads(raw)]


def _encode_claim_value(rest_terms: list[tuple[str, Any]]) -> tuple[str | None, str | None]:
    if not rest_terms:
        return None, None
    if len(rest_terms) != 1:
        raise ValueError("claims must contain zero or one value term")
    _idx, value, tag = claim_args_from_rest_terms(rest_terms)[0]
    if tag in {"entity_ref", "string", "uuid", "bytes"}:
        return str(value), tag
    if tag in {"int", "time"}:
        return str(value), tag
    if tag == "bool":
        return "true" if value else "false", tag
    if tag == "float64":
        bits = int(str(value)[2:], 16)
        number = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        return repr(0.0 if number == 0.0 else number), tag
    raise ValueError(f"unsupported claim value tag: {tag}")


def _decode_claim_value(value: str | None, tag: str | None) -> list[tuple[str, Any]]:
    if value is None and tag is None:
        return []
    if value is None or tag is None:
        raise LedgerFormatError("claims value/value_tag nullability mismatch")
    if tag in {"entity_ref", "string", "uuid"}:
        decoded: Any = value
    elif tag in {"int", "time"}:
        decoded = int(value)
    elif tag == "bool":
        if value not in {"true", "false"}:
            raise LedgerFormatError("invalid canonical bool in claims.value")
        decoded = value == "true"
    elif tag == "float64":
        decoded = float(value)
        if not math.isfinite(decoded):
            raise LedgerFormatError("invalid canonical float64 in claims.value")
        if decoded == 0.0:
            decoded = 0.0
    elif tag == "bytes":
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    else:
        raise LedgerFormatError(f"unsupported claims.value_tag: {tag!r}")
    # Re-run protocol normalization so corrupt/non-canonical SQL text fails closed.
    claim_args_from_rest_terms([(tag, decoded)])
    return [(tag, decoded)]


def _decode_claim_terms(
    rest_terms: str | None,
    value: str | None,
    value_tag: str | None,
) -> list[tuple[str, Any]]:
    legacy_terms = [] if rest_terms is None else _dec_rest_terms(rest_terms)
    normalized_legacy = [_normalize_term(term) for term in legacy_terms]
    if normalized_legacy and (value is not None or value_tag is not None):
        raise LedgerFormatError(
            "claims row uses both legacy rest_terms and value/value_tag carriers"
        )
    if normalized_legacy:
        claim_args_from_rest_terms(normalized_legacy)
        return normalized_legacy
    return _decode_claim_value(value, value_tag)


def _encode_meta_value(kind: str, value: Any) -> str:
    if kind == "str":
        if not isinstance(value, str):
            raise ValueError("meta str value must be str")
        return value
    if kind in {"int", "time"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"meta {kind} value must be int")
        return str(value)
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("meta float value must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("meta float value must be finite")
        return repr(0.0 if number == 0.0 else number)
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError("meta bool value must be bool")
        return "true" if value else "false"
    if kind == "json":
        return json.dumps(
            _to_jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    raise ValueError(f"unsupported meta kind: {kind}")


def _decode_meta_value(kind: str | None, value: str | None) -> Any:
    if kind is None and value is None:
        return None
    if kind is None or value is None:
        raise LedgerFormatError("claim_meta kind/value nullability mismatch")
    try:
        if kind == "str":
            return value
        if kind in {"int", "time"}:
            return int(value)
        if kind == "float":
            decoded = float(value)
            if not math.isfinite(decoded):
                raise LedgerFormatError("invalid canonical float claim_meta value")
            return 0.0 if decoded == 0.0 else decoded
        if kind == "bool":
            if value not in {"true", "false"}:
                raise LedgerFormatError("invalid canonical bool claim_meta value")
            return value == "true"
        if kind == "json":
            return _from_jsonable(json.loads(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LedgerFormatError(f"invalid claim_meta {kind!r} value encoding") from exc
    raise LedgerFormatError(f"unsupported claim_meta kind: {kind!r}")


def _annotation_storage_key(row: AnnotationRow) -> str:
    identity = json.dumps(
        {
            "category": row.category,
            "derivation": row.derivation,
            "key": row.key,
            "namespace": row.namespace,
            "origin": row.origin,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    token = base64.urlsafe_b64encode(identity).decode("ascii").rstrip("=")
    return _ANNOTATION_COMPAT_PREFIX + token


def _annotation_compatibility_meta_rows(
    rows: Sequence[AnnotationRow],
    skip_meta_rows: Sequence[MetaRow],
) -> list[MetaRow]:
    reproducible = {
        _annotation_identity(annotation)
        for row in skip_meta_rows
        if (annotation := _initial_meta_annotation_row(row)) is not None
    }
    return [
        _AnnotationStorageMetaRow(
            row.asrt_id,
            _annotation_storage_key(row),
            row.kind,
            row.value,
        )
        for row in rows
        if _annotation_identity(row) not in reproducible
    ]


def _initial_meta_annotation_row(row: MetaRow) -> AnnotationRow | None:
    projection = initial_meta_annotation_v1(row.key)
    if projection is None:
        return None
    return AnnotationRow(
        asrt_id=row.asrt_id,
        namespace=projection.namespace,
        category=projection.category,
        key=row.key,
        kind=row.kind,
        value=row.value,
        origin=projection.origin,
        derivation=projection.derivation,
    )


def _initial_meta_annotation_rows(rows: Sequence[MetaRow]) -> list[AnnotationRow]:
    return [
        annotation
        for row in rows
        if (annotation := _initial_meta_annotation_row(row)) is not None
    ]


def _annotation_identity(row: AnnotationRow) -> tuple[object, ...]:
    return (
        row.asrt_id,
        row.namespace,
        row.category,
        row.key,
        row.kind,
        _encode_meta_value(row.kind, row.value),
        row.origin,
        row.derivation,
    )


def _merge_annotation_rows(
    contract_rows: Sequence[AnnotationRow],
    explicit_rows: Sequence[AnnotationRow],
) -> list[AnnotationRow]:
    merged: dict[tuple[str, str, str, str], AnnotationRow] = {}
    for row in (*contract_rows, *explicit_rows):
        merged[(row.asrt_id, row.namespace, row.category, row.key)] = row
    return list(merged.values())


def _annotation_from_storage_key(
    asrt_id: str,
    storage_key: str,
    kind: str,
    value: Any,
) -> AnnotationRow:
    try:
        if not _is_reserved_annotation_meta_key(storage_key):
            raise ValueError("missing annotation compatibility prefix")
        token = storage_key.removeprefix(_ANNOTATION_COMPAT_PREFIX)
        if not token:
            raise ValueError("empty annotation compatibility payload")
        padding = "=" * (-len(token) % 4)
        raw = base64.b64decode(
            (token + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("annotation compatibility payload must be an object")
        row = AnnotationRow(
            asrt_id=asrt_id,
            namespace=payload["namespace"],
            category=payload["category"],
            key=payload["key"],
            kind=kind,
            value=value,
            origin=payload["origin"],
            derivation=payload["derivation"],
        )
        _validate_annotation_rows([row])
        return row
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, UnicodeError, ValueError) as exc:
        raise LedgerFormatError(
            f"malformed annotation compatibility storage key for asrt_id {asrt_id!r}"
        ) from exc


class Ledger:
    """
    Append-only ledger backed by SQLite with write-through in-memory indexes.

    Ledger() -> in-memory sqlite database
    Ledger(path="./data/ledger.db") -> file-backed sqlite database
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        if isinstance(path, Path):
            path_str = str(path)
        elif isinstance(path, str):
            path_str = path
        else:
            raise TypeError("path must be str | Path")

        if path_str != ":memory:":
            Path(path_str).parent.mkdir(parents=True, exist_ok=True)

        self._path = path_str
        self._memory_mode = path_str == ":memory:"
        self._closed = False
        self._owner_thread_id = threading.get_ident()
        self._memory_warning_emitted = False
        self._managed_annotation_writer: Callable[[Sequence[AnnotationRow]], Any] | None = None
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self._connections_lock = threading.Lock()
        self._all_connections: list[sqlite3.Connection] = []
        self._memory_conn: sqlite3.Connection | None = None
        self._reset_indexes()
        main_conn = self._get_connection()
        self._init_schema(main_conn)
        self._load_from_db_via(main_conn)

    def __deepcopy__(self, memo: dict[int, Any]) -> Ledger:
        clone = Ledger()
        with self._write_lock:
            source_conn = self._get_connection()
            target_conn = clone._get_connection()
            source_conn.backup(target_conn)
        clone._reset_indexes()
        clone._load_from_db_via(clone._get_connection())
        memo[id(self)] = clone
        return clone

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()

    @contextmanager
    def _write_session(self) -> Iterator[tuple[sqlite3.Connection, list[Callable[[], None]]]]:
        with self._write_lock:
            conn = self._get_connection()
            post_commit: list[Callable[[], None]] = []
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn, post_commit
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    with suppress(Exception):
                        conn.execute("ROLLBACK")
                raise
            for hook in post_commit:
                hook()

    def commit_batch(
        self,
        *,
        assertions: Sequence[LedgerAssertionWrite],
        revocations: Sequence[LedgerRevocationWrite],
        expected_head_tx_id: str | None,
        head_tx_id: str,
        metadata: Mapping[str, str],
        meta_appends: Sequence[MetaRow | _MetaTombstone] = (),
    ) -> None:
        """Atomically append a Database commit and advance its CAS-protected head.

        Database owns transaction identity and digest computation.  Ledger owns
        the single SQLite boundary: all factual rows, revocation rows, appended
        meta events and lifecycle metadata become visible together, with
        in-memory indexes updated only after COMMIT succeeds.
        """
        if not isinstance(head_tx_id, str) or not head_tx_id:
            raise ValueError("head_tx_id must be non-empty string")
        if expected_head_tx_id is not None and (
            not isinstance(expected_head_tx_id, str) or not expected_head_tx_id
        ):
            raise ValueError("expected_head_tx_id must be non-empty string when provided")
        normalized_metadata = dict(metadata)
        if "head_tx_id" in normalized_metadata:
            raise ValueError("metadata must not contain head_tx_id; use the dedicated argument")
        for key, value in normalized_metadata.items():
            if not isinstance(key, str) or not key:
                raise ValueError("ledger metadata keys must be non-empty strings")
            if not isinstance(value, str):
                raise ValueError("ledger metadata values must be strings")

        raw_assertion_writes = tuple(assertions)
        raw_revocation_writes = tuple(revocations)
        if any(not isinstance(item, LedgerAssertionWrite) for item in raw_assertion_writes):
            raise TypeError("assertions must contain LedgerAssertionWrite")
        if any(not isinstance(item, LedgerRevocationWrite) for item in raw_revocation_writes):
            raise TypeError("revocations must contain LedgerRevocationWrite")
        assertion_writes = tuple(
            LedgerAssertionWrite(
                claim=item.claim,
                claim_args=item.claim_args,
                meta_rows=item.meta_rows,
                annotation_rows=tuple(
                    _merge_annotation_rows(
                        _initial_meta_annotation_rows(item.meta_rows),
                        item.annotation_rows,
                    )
                ),
            )
            for item in raw_assertion_writes
        )
        revocation_writes = tuple(
            LedgerRevocationWrite(
                revokes=item.revokes,
                meta_rows=item.meta_rows,
                annotation_rows=tuple(
                    _merge_annotation_rows(
                        _initial_meta_annotation_rows(item.meta_rows),
                        item.annotation_rows,
                    )
                ),
            )
            for item in raw_revocation_writes
        )
        appended_meta_rows = tuple(meta_appends)
        _validate_meta_events(appended_meta_rows)
        raw_tx_seq = normalized_metadata.get("head_tx_seq")
        if raw_tx_seq is None or not raw_tx_seq.isdecimal():
            raise ValueError("metadata head_tx_seq must be a canonical non-negative integer")
        tx_seq = int(raw_tx_seq)
        new_claim_ids: set[str] = set()
        new_revoker_ids: set[str] = set()
        for item in assertion_writes:
            _validate_claim_input(item.claim, require_asrt_id=True)
            _validate_claim_args_rows(list(item.claim_args))
            _validate_meta_rows(list(item.meta_rows))
            _reject_duplicate_meta_keys(item.meta_rows, context="assertion initial meta")
            _validate_annotation_rows(list(item.annotation_rows))
            asrt_id = item.claim.asrt_id
            if asrt_id in new_claim_ids:
                raise ValueError(f"duplicate asrt_id in batch: {asrt_id}")
            if any(row.asrt_id != asrt_id for row in item.claim_args):
                raise ValueError("claim_args asrt_id must match the batch claim")
            if any(row.asrt_id != asrt_id for row in item.meta_rows):
                raise ValueError("meta_rows asrt_id must match the batch claim")
            if any(row.asrt_id != asrt_id for row in item.annotation_rows):
                raise ValueError("annotation_rows asrt_id must match the batch claim")
            new_claim_ids.add(asrt_id)

        for item in revocation_writes:
            _validate_revokes_row(item.revokes)
            _validate_meta_rows(list(item.meta_rows))
            _reject_duplicate_meta_keys(item.meta_rows, context="revocation initial meta")
            _validate_annotation_rows(list(item.annotation_rows))
            revoker_id = item.revokes.revoker_asrt_id
            if revoker_id in new_revoker_ids or revoker_id in new_claim_ids:
                raise ValueError(f"duplicate revoker_asrt_id in batch: {revoker_id}")
            if any(row.asrt_id != revoker_id for row in item.meta_rows):
                raise ValueError("revocation meta_rows asrt_id must match revoker_asrt_id")
            if any(row.asrt_id != revoker_id for row in item.annotation_rows):
                raise ValueError("revocation annotation_rows asrt_id must match revoker_asrt_id")
            new_revoker_ids.add(revoker_id)

        known_after_commit = new_claim_ids | new_revoker_ids
        for row in appended_meta_rows:
            if row.asrt_id not in known_after_commit and not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for meta: {row.asrt_id}")

        with self._write_session() as (conn, post_commit):
            existing_ids = new_claim_ids | new_revoker_ids
            for asrt_id in existing_ids:
                if self._is_known_asrt_id(asrt_id):
                    raise ValueError(f"duplicate asrt_id: {asrt_id}")

            if expected_head_tx_id is None:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO ledger_meta (key, value) VALUES ('head_tx_id', ?)",
                    (head_tx_id,),
                )
            else:
                cursor = conn.execute(
                    "UPDATE ledger_meta SET value = ? WHERE key = 'head_tx_id' AND value = ?",
                    (head_tx_id, expected_head_tx_id),
                )
            if cursor.rowcount != 1:
                raise LedgerHeadConflictError(f"head CAS failed: expected {expected_head_tx_id!r}")

            for op_ordinal, item in enumerate(assertion_writes):
                self._insert_claim(
                    conn,
                    item.claim,
                    item.claim.asrt_id,
                    tx_ref=tx_seq,
                )
                self._insert_meta_rows(
                    conn,
                    list(item.meta_rows),
                    item.claim.asrt_id,
                    tx_seq=tx_seq,
                    op_ordinal=op_ordinal,
                )
                if item.annotation_rows:
                    self._insert_annotation_rows(
                        conn,
                        list(item.annotation_rows),
                        tx_seq=tx_seq,
                        op_ordinal=op_ordinal,
                        skip_meta_rows=item.meta_rows,
                    )

            revocation_offset = len(assertion_writes)
            for relative_ordinal, item in enumerate(revocation_writes):
                op_ordinal = revocation_offset + relative_ordinal
                target = self._claim_by_asrt_id.get(item.revokes.revoked_asrt_id)
                if target is None:
                    target = next(
                        (
                            candidate.claim
                            for candidate in assertion_writes
                            if candidate.claim.asrt_id == item.revokes.revoked_asrt_id
                        ),
                        None,
                    )
                if target is None:
                    raise ValueError(
                        f"revocation target does not exist: {item.revokes.revoked_asrt_id}"
                    )
                revoke_claim = Claim(
                    asrt_id=item.revokes.revoker_asrt_id,
                    pred_id=_REVOCATION_PREDICATE,
                    e_ref=target.e_ref,
                    rest_terms=[("string", item.revokes.revoked_asrt_id)],
                )
                self._insert_claim(
                    conn,
                    revoke_claim,
                    item.revokes.revoker_asrt_id,
                    tx_ref=tx_seq,
                )
                self._insert_meta_rows(
                    conn,
                    list(item.meta_rows),
                    item.revokes.revoker_asrt_id,
                    tx_seq=tx_seq,
                    op_ordinal=op_ordinal,
                )
                if item.annotation_rows:
                    self._insert_annotation_rows(
                        conn,
                        list(item.annotation_rows),
                        tx_seq=tx_seq,
                        op_ordinal=op_ordinal,
                        skip_meta_rows=item.meta_rows,
                    )

            meta_offset = revocation_offset + len(revocation_writes)
            for relative_ordinal, row in enumerate(appended_meta_rows):
                self._insert_meta_rows(
                    conn,
                    [row],
                    row.asrt_id,
                    tx_seq=tx_seq,
                    op_ordinal=meta_offset + relative_ordinal,
                )

            conn.executemany(
                """
                INSERT INTO ledger_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                sorted(normalized_metadata.items()),
            )

            def _apply_batch_indexes() -> None:
                for op_ordinal, item in enumerate(assertion_writes):
                    self._claim_tx_refs[item.claim.asrt_id] = tx_seq
                    self._claim_op_ordinals[item.claim.asrt_id] = op_ordinal
                    self._idx_add_claim(item.claim)
                    self._idx_add_claim_meta_events(
                        item.meta_rows,
                        tx_seq=tx_seq,
                        op_ordinal=op_ordinal,
                        project_meta=True,
                    )
                    if item.annotation_rows:
                        self._idx_add_claim_meta_events(
                            _annotation_compatibility_meta_rows(
                                item.annotation_rows,
                                item.meta_rows,
                            ),
                            tx_seq=tx_seq,
                            op_ordinal=op_ordinal,
                            project_meta=False,
                        )
                        self._idx_add_annotation(list(item.annotation_rows))
                for relative_ordinal, item in enumerate(revocation_writes):
                    op_ordinal = revocation_offset + relative_ordinal
                    target = self._claim_by_asrt_id.get(item.revokes.revoked_asrt_id)
                    if target is None:
                        target = next(
                            candidate.claim
                            for candidate in assertion_writes
                            if candidate.claim.asrt_id == item.revokes.revoked_asrt_id
                        )
                    self._idx_add_system_revocation_claim(
                        Claim(
                            item.revokes.revoker_asrt_id,
                            _REVOCATION_PREDICATE,
                            target.e_ref,
                            [("string", item.revokes.revoked_asrt_id)],
                        ),
                        tx_ref=tx_seq,
                    )
                    self._claim_op_ordinals[item.revokes.revoker_asrt_id] = op_ordinal
                    self._idx_add_revoke(item.revokes)
                    self._idx_add_claim_meta_events(
                        item.meta_rows,
                        tx_seq=tx_seq,
                        op_ordinal=op_ordinal,
                        project_meta=True,
                    )
                    if item.annotation_rows:
                        self._idx_add_claim_meta_events(
                            _annotation_compatibility_meta_rows(
                                item.annotation_rows,
                                item.meta_rows,
                            ),
                            tx_seq=tx_seq,
                            op_ordinal=op_ordinal,
                            project_meta=False,
                        )
                        self._idx_add_annotation(list(item.annotation_rows))
                for relative_ordinal, row in enumerate(appended_meta_rows):
                    self._idx_add_claim_meta_events(
                        (row,),
                        tx_seq=tx_seq,
                        op_ordinal=meta_offset + relative_ordinal,
                        project_meta=isinstance(row, MetaRow)
                        and not isinstance(row, _AnnotationStorageMetaRow),
                    )
                    if isinstance(row, _AnnotationStorageMetaRow):
                        self._idx_add_annotation(
                            [_annotation_from_storage_key(row.asrt_id, row.key, row.kind, row.value)]
                        )

            post_commit.append(_apply_batch_indexes)

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._path,
            check_same_thread=True,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        if self._memory_mode:
            conn.execute("PRAGMA journal_mode = MEMORY")
        else:
            conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _register_connection(self, conn: sqlite3.Connection) -> sqlite3.Connection:
        with self._connections_lock:
            if self._closed:
                with suppress(Exception):
                    conn.close()
                raise RuntimeError("Ledger was closed during connection acquisition")
            self._all_connections.append(conn)
        return conn

    def _get_connection(self) -> sqlite3.Connection:
        self._ensure_open()
        if self._memory_mode:
            if threading.get_ident() != self._owner_thread_id and not self._memory_warning_emitted:
                warnings.warn(
                    "memory ledger is single-threaded; do not use from multiple threads",
                    RuntimeWarning,
                    stacklevel=2,
                )
                self._memory_warning_emitted = True
            if self._memory_conn is None:
                self._memory_conn = self._register_connection(self._open_connection())
            return self._memory_conn

        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._register_connection(self._open_connection())
            self._local.conn = conn
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        existing_tables = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        legacy_tables = sorted(existing_tables & _LEGACY_TABLES)
        if legacy_tables:
            raise LedgerFormatError(
                "unsupported seven-table v0.3 ledger format "
                f"({', '.join(legacy_tables)} present); rebuild this development workspace "
                "or re-run `python -m factgraph migrate-workspace <v0.2-workspace>` "
                "from the original v0.2 source"
            )
        conn.executescript(_DDL)
        conn.execute(
            "INSERT OR IGNORE INTO ledger_meta (key, value) VALUES "
            "('ledger_format_version', 'slice3b-v1')"
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Ledger is closed")

    def append_assertion(
        self,
        *,
        claim: Claim,
        claim_args: list[ClaimArg],
        meta_rows: list[MetaRow],
        annotation_rows: list[AnnotationRow] | None = None,
        idempotency: Idempotency | None = None,
        asrt_id: str | None = None,
    ) -> AppendResult:
        _validate_claim_input(claim, require_asrt_id=False)
        _validate_claim_args_rows(claim_args)
        _validate_meta_rows_for_append_assertion(meta_rows)
        _reject_duplicate_meta_keys(meta_rows, context="assertion initial meta")
        effective_asrt_id = asrt_id or (
            claim.asrt_id if isinstance(claim.asrt_id, str) and claim.asrt_id else _new_asrt_id()
        )
        actual_meta_rows = [
            MetaRow(
                asrt_id=effective_asrt_id,
                key=row.key,
                kind=row.kind,
                value=row.value,
            )
            for row in meta_rows
        ]
        actual_meta_rows = _materialize_idempotency_meta(
            actual_meta_rows,
            idempotency=idempotency,
            asrt_id=effective_asrt_id,
        )

        if idempotency is not None:
            existing = self._find_ingest_key(idempotency.ingest_key)
            if existing is not None:
                if idempotency.on_conflict == "error":
                    raise DuplicateIngestKeyError(
                        f"ingest_key already exists: {idempotency.ingest_key}"
                    )
                return AppendResult(asrt_id=existing, written=False)

        normalized_terms = [_normalize_term(term) for term in claim.rest_terms]
        actual_claim = Claim(
            asrt_id=effective_asrt_id,
            pred_id=claim.pred_id,
            e_ref=claim.e_ref,
            rest_terms=normalized_terms,
        )
        actual_claim_args = [
            ClaimArg(
                asrt_id=effective_asrt_id,
                idx=row.idx,
                val_atom=row.val_atom,
                tag=row.tag,
            )
            for row in claim_args
        ]
        expected_claim_args = [
            ClaimArg(
                asrt_id=effective_asrt_id,
                idx=idx,
                val_atom=val_atom,
                tag=tag,
            )
            for idx, val_atom, tag in claim_args_from_rest_terms(normalized_terms)
        ]
        if actual_claim_args != expected_claim_args:
            raise ValueError("claim_args must exactly match claim.rest_terms")
        explicit_annotation_rows = [
            AnnotationRow(
                asrt_id=effective_asrt_id,
                namespace=row.namespace,
                category=row.category,
                key=row.key,
                kind=row.kind,
                value=row.value,
                origin=row.origin,
                derivation=row.derivation,
            )
            for row in (annotation_rows or [])
        ]
        actual_annotation_rows = _merge_annotation_rows(
            _initial_meta_annotation_rows(actual_meta_rows),
            explicit_annotation_rows,
        )
        if actual_annotation_rows:
            _validate_annotation_rows(actual_annotation_rows)

        with self._write_session() as (conn, post_commit):
            tx_seq = self._next_direct_tx_seq(conn)
            self._insert_claim(conn, actual_claim, effective_asrt_id, tx_ref=tx_seq)
            self._insert_meta_rows(
                conn,
                actual_meta_rows,
                effective_asrt_id,
                tx_seq=tx_seq,
                op_ordinal=0,
            )
            if actual_annotation_rows:
                self._insert_annotation_rows(
                    conn,
                    actual_annotation_rows,
                    tx_seq=tx_seq,
                    op_ordinal=0,
                    skip_meta_rows=actual_meta_rows,
                )

            def _apply_assertion_indexes() -> None:
                self._claim_tx_refs[actual_claim.asrt_id] = tx_seq
                self._claim_op_ordinals[actual_claim.asrt_id] = 0
                self._idx_add_claim(actual_claim)
                self._idx_add_claim_meta_events(
                    actual_meta_rows,
                    tx_seq=tx_seq,
                    op_ordinal=0,
                    project_meta=True,
                )
                if actual_annotation_rows:
                    self._idx_add_claim_meta_events(
                        _annotation_compatibility_meta_rows(
                            actual_annotation_rows,
                            actual_meta_rows,
                        ),
                        tx_seq=tx_seq,
                        op_ordinal=0,
                        project_meta=False,
                    )
                    self._idx_add_annotation(actual_annotation_rows)

            post_commit.append(_apply_assertion_indexes)
        return AppendResult(asrt_id=effective_asrt_id, written=True)

    def append_revocation(
        self,
        *,
        revokes: Revokes,
        meta_rows: list[MetaRow],
        idempotency: Idempotency | None = None,
        revoker_asrt_id: str | None = None,
    ) -> AppendResult:
        _validate_revokes_row(revokes)
        _validate_meta_rows(meta_rows)
        _reject_duplicate_meta_keys(meta_rows, context="revocation initial meta")
        effective_revoker_id = revoker_asrt_id or (
            revokes.revoker_asrt_id
            if isinstance(revokes.revoker_asrt_id, str) and revokes.revoker_asrt_id
            else _new_asrt_id()
        )
        actual_meta_rows = [
            MetaRow(
                asrt_id=effective_revoker_id,
                key=row.key,
                kind=row.kind,
                value=row.value,
            )
            for row in meta_rows
        ]
        actual_meta_rows = _materialize_idempotency_meta(
            actual_meta_rows,
            idempotency=idempotency,
            asrt_id=effective_revoker_id,
        )

        if idempotency is not None:
            existing = self._find_ingest_key(idempotency.ingest_key)
            if existing is not None:
                if idempotency.on_conflict == "error":
                    raise DuplicateIngestKeyError(
                        f"ingest_key already exists: {idempotency.ingest_key}"
                    )
                return AppendResult(asrt_id=existing, written=False)

        actual_revokes = Revokes(
            revoker_asrt_id=effective_revoker_id,
            revoked_asrt_id=revokes.revoked_asrt_id,
        )
        actual_annotation_rows = _initial_meta_annotation_rows(actual_meta_rows)
        _validate_annotation_rows(actual_annotation_rows)

        with self._write_session() as (conn, post_commit):
            target = self._claim_by_asrt_id.get(revokes.revoked_asrt_id)
            if target is None:
                raise ValueError(f"revocation target does not exist: {revokes.revoked_asrt_id}")
            tx_seq = self._next_direct_tx_seq(conn)
            revoke_claim = Claim(
                effective_revoker_id,
                _REVOCATION_PREDICATE,
                target.e_ref,
                [("string", revokes.revoked_asrt_id)],
            )
            self._insert_claim(conn, revoke_claim, effective_revoker_id, tx_ref=tx_seq)
            self._insert_meta_rows(
                conn,
                actual_meta_rows,
                effective_revoker_id,
                tx_seq=tx_seq,
                op_ordinal=0,
            )
            if actual_annotation_rows:
                self._insert_annotation_rows(
                    conn,
                    actual_annotation_rows,
                    tx_seq=tx_seq,
                    op_ordinal=0,
                    skip_meta_rows=actual_meta_rows,
                )

            def _apply_revocation_indexes() -> None:
                self._idx_add_system_revocation_claim(revoke_claim, tx_ref=tx_seq)
                self._claim_op_ordinals[revoke_claim.asrt_id] = 0
                self._idx_add_revoke(actual_revokes)
                self._idx_add_claim_meta_events(
                    actual_meta_rows,
                    tx_seq=tx_seq,
                    op_ordinal=0,
                    project_meta=True,
                )
                if actual_annotation_rows:
                    self._idx_add_annotation(actual_annotation_rows)

            post_commit.append(_apply_revocation_indexes)
        return AppendResult(asrt_id=effective_revoker_id, written=True)

    def append_claim(self, claim: Claim) -> None:
        """
        .. deprecated::
            Use append_assertion(...) instead. This method is kept
            during the compatibility window and will be downgraded
            to private or removed in a later cleanup phase.
        """
        _validate_claim_input(claim, require_asrt_id=True)
        normalized_terms = [_normalize_term(term) for term in claim.rest_terms]
        actual_claim = Claim(
            asrt_id=claim.asrt_id,
            pred_id=claim.pred_id,
            e_ref=claim.e_ref,
            rest_terms=normalized_terms,
        )
        with self._write_session() as (conn, post_commit):
            tx_seq = self._next_direct_tx_seq(conn)
            self._insert_claim(conn, actual_claim, claim.asrt_id, tx_ref=tx_seq)
            def _apply_claim_index() -> None:
                self._claim_tx_refs[actual_claim.asrt_id] = tx_seq
                self._claim_op_ordinals[actual_claim.asrt_id] = 0
                self._idx_add_claim(actual_claim)

            post_commit.append(_apply_claim_index)

    def append_claim_args(self, rows: list[ClaimArg]) -> None:
        """
        .. deprecated::
            Use append_assertion(...) instead. This method is kept
            during the compatibility window and will be downgraded
            to private or removed in a later cleanup phase.
        """
        _validate_claim_args_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for claim_arg: {row.asrt_id}")
        for row in rows:
            claim = self._claim_by_asrt_id.get(row.asrt_id)
            expected = claim_args_from_rest_terms(claim.rest_terms if claim is not None else [])
            if (row.idx, row.val_atom, row.tag) not in expected:
                raise ValueError("claim_args must match the value already stored on claims")

    def append_meta(self, rows: list[MetaRow]) -> None:
        """
        .. deprecated::
            Use append_assertion(...) or append_revocation(...)
            instead. This method is kept during the compatibility
            window and will be downgraded to private or removed in
            a later cleanup phase.
        """
        _validate_meta_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for meta: {row.asrt_id}")
        actual_rows = [
            MetaRow(asrt_id=row.asrt_id, key=row.key, kind=row.kind, value=row.value)
            for row in rows
        ]
        with self._write_session() as (conn, post_commit):
            tx_seq = self._next_direct_tx_seq(conn)
            for op_ordinal, row in enumerate(actual_rows):
                self._insert_meta_rows(
                    conn,
                    [row],
                    row.asrt_id,
                    tx_seq=tx_seq,
                    op_ordinal=op_ordinal,
                )
            def _apply_meta_indexes() -> None:
                for op_ordinal, row in enumerate(actual_rows):
                    self._idx_add_claim_meta_events(
                        (row,),
                        tx_seq=tx_seq,
                        op_ordinal=op_ordinal,
                        project_meta=True,
                    )

            post_commit.append(_apply_meta_indexes)

    def append_annotations(self, rows: list[AnnotationRow]) -> None:
        if self._managed_annotation_writer is not None:
            self._managed_annotation_writer(tuple(rows))
            return
        _validate_annotation_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for annotation: {row.asrt_id}")
        actual_rows = [
            AnnotationRow(
                asrt_id=row.asrt_id,
                namespace=row.namespace,
                category=row.category,
                key=row.key,
                kind=row.kind,
                value=row.value,
                origin=row.origin,
                derivation=row.derivation,
            )
            for row in rows
        ]
        with self._write_session() as (conn, post_commit):
            tx_seq = self._next_direct_tx_seq(conn)
            for op_ordinal, row in enumerate(actual_rows):
                self._insert_annotation_rows(
                    conn,
                    [row],
                    tx_seq=tx_seq,
                    op_ordinal=op_ordinal,
                    skip_meta_rows=(),
                )
            def _apply_annotation_indexes() -> None:
                for op_ordinal, row in enumerate(actual_rows):
                    self._idx_add_claim_meta_events(
                        _annotation_compatibility_meta_rows((row,), ()),
                        tx_seq=tx_seq,
                        op_ordinal=op_ordinal,
                        project_meta=False,
                    )
                self._idx_add_annotation(actual_rows)

            post_commit.append(_apply_annotation_indexes)

    def append_revokes(self, row: Revokes) -> None:
        """
        .. deprecated::
            Use append_revocation(...) instead. This method is
            kept during the compatibility window and will be
            downgraded to private or removed in a later cleanup
            phase.
        """
        _validate_revokes_row(row)
        actual_row = Revokes(
            revoker_asrt_id=row.revoker_asrt_id,
            revoked_asrt_id=row.revoked_asrt_id,
        )
        with self._write_session() as (conn, post_commit):
            target = self._claim_by_asrt_id.get(row.revoked_asrt_id)
            if target is None:
                raise ValueError(f"revocation target does not exist: {row.revoked_asrt_id}")
            tx_seq = self._next_direct_tx_seq(conn)
            revoke_claim = Claim(
                row.revoker_asrt_id,
                _REVOCATION_PREDICATE,
                target.e_ref,
                [("string", row.revoked_asrt_id)],
            )
            self._insert_claim(conn, revoke_claim, row.revoker_asrt_id, tx_ref=tx_seq)
            post_commit.append(
                lambda: (
                    self._idx_add_system_revocation_claim(revoke_claim, tx_ref=tx_seq),
                    self._claim_op_ordinals.__setitem__(revoke_claim.asrt_id, 0),
                    self._idx_add_revoke(actual_row),
                )
            )

    def get_claim(self, asrt_id: str) -> Claim | None:
        with self._write_lock:
            self._ensure_open()
            return self._claim_by_asrt_id.get(asrt_id)

    def _get_claim_including_system(self, asrt_id: str) -> Claim | None:
        """Return an exact id for audit/replay, bypassing INV-15 filtering."""
        with self._write_lock:
            self._ensure_open()
            return self._claim_by_asrt_id.get(asrt_id) or self._system_claim_by_asrt_id.get(
                asrt_id
            )

    def find_claims(self, pred_id: str | None = None, e_ref: str | None = None) -> list[Claim]:
        with self._write_lock:
            self._ensure_open()
            if pred_id is not None and e_ref is not None:
                return list(self._claims_by_pred_e_ref.get((pred_id, e_ref), []))
            if pred_id is not None:
                return list(self._claims_by_pred_id.get(pred_id, []))
            if e_ref is not None:
                return list(self._claims_by_e_ref.get(e_ref, []))
            return list(self._claims)

    def find_claim_args(
        self,
        asrt_id: str | None = None,
        idx: int | None = None,
        tag: str | None = None,
    ) -> list[ClaimArg]:
        with self._write_lock:
            self._ensure_open()
            rows = (
                self._claim_args_by_asrt_id.get(asrt_id, [])
                if asrt_id is not None
                else self._claim_args
            )
            if idx is not None:
                rows = [row for row in rows if row.idx == idx]
            if tag is not None:
                rows = [row for row in rows if row.tag == tag]
            return list(rows)

    def find_meta(
        self,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
    ) -> list[MetaRow]:
        with self._write_lock:
            self._ensure_open()
            if asrt_id is not None:
                if key is not None and kind is not None:
                    return list(self._meta_by_asrt_id_key_kind.get((asrt_id, key, kind), []))
                if key is not None:
                    return list(self._meta_by_asrt_id_key.get((asrt_id, key), []))
                rows = self._meta_by_asrt_id.get(asrt_id, [])
                if kind is not None:
                    rows = [row for row in rows if row.kind == kind]
                return list(rows)
            if key is not None:
                rows = self._meta_by_key.get(key, [])
                if kind is not None:
                    rows = [row for row in rows if row.kind == kind]
                return list(rows)
            if kind is not None:
                return list(self._meta_by_kind.get(kind, []))
            return list(self._meta_rows_data)

    def _meta_history_events(
        self,
        *,
        asrt_id: str | None = None,
        key: str | None = None,
    ) -> tuple[_ClaimMetaEvent, ...]:
        """Return immutable event history for the narrow audit/debug surface."""
        with self._write_lock:
            self._ensure_open()
            if asrt_id is not None and key is not None:
                rows = self._claim_meta_events_by_asrt_id_key.get((asrt_id, key), ())
            elif asrt_id is not None:
                rows = self._claim_meta_events_by_asrt_id.get(asrt_id, ())
            elif key is not None:
                rows = (row for row in self._claim_meta_events if row.key == key)
            else:
                rows = self._claim_meta_events
            return tuple(sorted(rows, key=_claim_meta_event_sort_key))

    def _effective_meta_events(
        self,
        *,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
        as_of: tuple[int, int] | None = None,
    ) -> tuple[_ClaimMetaEvent, ...]:
        """Resolve last-wins meta using the Q-SAE-8 global event order."""
        boundary = _normalize_event_sequence(as_of)
        history = self._meta_history_events(asrt_id=asrt_id, key=key)
        latest: dict[tuple[str, str], _ClaimMetaEvent] = {}
        for event in history:
            if boundary is not None and event.event_seq > boundary:
                continue
            latest[(event.asrt_id, event.key)] = event
        rows = [
            event
            for event in latest.values()
            if not event.is_unset and (kind is None or event.kind == kind)
        ]
        return tuple(sorted(rows, key=_claim_meta_event_sort_key))

    def _effective_meta_rows(
        self,
        *,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
        as_of: tuple[int, int] | None = None,
    ) -> tuple[MetaRow, ...]:
        return tuple(
            MetaRow(event.asrt_id, event.key, str(event.kind), event.value)
            for event in self._effective_meta_events(
                asrt_id=asrt_id,
                key=key,
                kind=kind,
                as_of=as_of,
            )
        )

    def _latest_meta_event_sequence(self) -> tuple[int, int] | None:
        with self._write_lock:
            self._ensure_open()
            if not self._claim_meta_events:
                return None
            return max(event.event_seq for event in self._claim_meta_events)

    def find_annotations(
        self,
        asrt_id: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        key: str | None = None,
    ) -> list[AnnotationRow]:
        with self._write_lock:
            self._ensure_open()
            if asrt_id is not None:
                rows = self._anno_by_asrt_id.get(asrt_id, [])
            elif namespace is not None and category is not None:
                rows = self._anno_by_ns_cat.get((namespace, category), [])
            elif key is not None:
                rows = self._anno_by_key.get(key, [])
            else:
                rows = self._annotation_rows_data

            result = rows
            if asrt_id is not None:
                result = [row for row in result if row.asrt_id == asrt_id]
            if namespace is not None:
                result = [row for row in result if row.namespace == namespace]
            if category is not None:
                result = [row for row in result if row.category == category]
            if key is not None:
                result = [row for row in result if row.key == key]
            return list(result)

    def has_active_revocation(self, revoked_asrt_id: str) -> bool:
        with self._write_lock:
            self._ensure_open()
            return revoked_asrt_id in self._revoked_asrt_ids

    def find_revoker(self, revoked_asrt_id: str) -> str | None:
        with self._write_lock:
            self._ensure_open()
            return self._first_revoker_by_revoked_asrt_id.get(revoked_asrt_id)

    def _find_active_assertion_by_ingest_key(self, ingest_key: str) -> str | None:
        """Internal O(1)-indexed lookup used by the application commit adapter."""
        if not isinstance(ingest_key, str) or not ingest_key:
            raise ValueError("ingest_key must be non-empty string")
        with self._write_lock:
            self._ensure_open()
            for asrt_id in self._meta_ingest_key_asrt_ids.get(ingest_key, ()):
                if asrt_id not in self._claim_by_asrt_id:
                    continue
                if asrt_id in self._revoked_asrt_ids:
                    continue
                return asrt_id
            return None

    @property
    def claims(self) -> list[Claim]:
        with self._write_lock:
            self._ensure_open()
            return list(self._claims)

    @property
    def claim_args(self) -> list[ClaimArg]:
        with self._write_lock:
            self._ensure_open()
            return list(self._claim_args)

    @property
    def meta_rows(self) -> list[MetaRow]:
        with self._write_lock:
            self._ensure_open()
            return list(self._meta_rows_data)

    @property
    def annotation_rows(self) -> list[AnnotationRow]:
        with self._write_lock:
            self._ensure_open()
            return list(self._annotation_rows_data)

    @property
    def _meta_rows(self) -> _MetaRowsProxy:
        return _MetaRowsProxy(self)

    @_meta_rows.setter
    def _meta_rows(self, rows: list[MetaRow]) -> None:
        self._force_replace_meta_rows(rows)

    @property
    def revokes(self) -> list[Revokes]:
        with self._write_lock:
            self._ensure_open()
            return list(self._revokes_data)

    def rebuild_indexes(self) -> None:
        """No-op for API compatibility; write-through cache updates eagerly."""

    def close(self) -> None:
        with self._write_lock:
            with self._connections_lock:
                if self._closed:
                    return
                self._closed = True
                self._all_connections.clear()

        current_conn = getattr(self._local, "conn", None)
        if current_conn is not None:
            with suppress(Exception):
                current_conn.close()
            with suppress(Exception):
                delattr(self._local, "conn")
        self._memory_conn = None

    def get_ledger_meta(self, key: str) -> str | None:
        """Return the stored ledger_meta value for key, or None when absent."""
        with self._write_lock:
            row = (
                self._get_connection()
                .execute(
                    "SELECT value FROM ledger_meta WHERE key = ?",
                    (key,),
                )
                .fetchone()
            )
            return str(row["value"]) if row is not None else None

    def get_ledger_meta_snapshot(self, keys: Sequence[str]) -> dict[str, str | None]:
        """Read lifecycle metadata under one Ledger lock acquisition."""
        normalized = tuple(keys)
        if any(not isinstance(key, str) or not key for key in normalized):
            raise ValueError("ledger metadata keys must be non-empty strings")
        if not normalized:
            return {}
        placeholders = ",".join("?" for _ in normalized)
        with self._write_lock:
            rows = (
                self._get_connection()
                .execute(
                    f"SELECT key, value FROM ledger_meta WHERE key IN ({placeholders})",
                    normalized,
                )
                .fetchall()
            )
            found = {str(row["key"]): str(row["value"]) for row in rows}
            return {key: found.get(key) for key in normalized}

    def set_ledger_meta(self, key: str, value: str) -> None:
        """Insert a ledger_meta value when key is absent; existing values are preserved."""
        with self._write_session() as (conn, _post_commit):
            conn.execute(
                "INSERT OR IGNORE INTO ledger_meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def replace_ledger_meta(self, key: str, value: str) -> None:
        """Insert or replace a ledger_meta value for lifecycle-managed metadata."""
        with self._write_session() as (conn, _post_commit):
            conn.execute(
                """
                INSERT INTO ledger_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def _force_replace_meta_rows(self, rows: list[MetaRow]) -> None:
        _validate_meta_rows(rows)
        actual_rows = [
            MetaRow(asrt_id=row.asrt_id, key=row.key, kind=row.kind, value=row.value)
            for row in rows
        ]
        with self._write_session() as (conn, post_commit):
            tx_seq = self._next_direct_tx_seq(conn)
            conn.execute(
                "DELETE FROM claim_meta WHERE key NOT LIKE ?",
                (_ANNOTATION_COMPAT_PREFIX + "%",),
            )
            for op_ordinal, row in enumerate(actual_rows):
                self._insert_meta_rows(
                    conn,
                    [row],
                    row.asrt_id,
                    tx_seq=tx_seq,
                    op_ordinal=op_ordinal,
                )

            def _apply_meta_replace() -> None:
                self._load_from_db()

            post_commit.append(_apply_meta_replace)

    def _reset_indexes(self) -> None:
        # Physical three-table indexes. Public legacy row families below are
        # eager compatibility projections rebuilt from these sources at open.
        self._claims: list[Claim] = []
        self._claim_by_asrt_id: dict[str, Claim] = {}
        self._claims_by_pred_id: dict[str, list[Claim]] = {}
        self._claims_by_e_ref: dict[str, list[Claim]] = {}
        self._claims_by_pred_e_ref: dict[tuple[str, str], list[Claim]] = {}
        self._system_claim_by_asrt_id: dict[str, Claim] = {}
        self._claim_tx_refs: dict[str, int] = {}
        self._claim_op_ordinals: dict[str, int] = {}

        self._claim_meta_events: list[_ClaimMetaEvent] = []
        self._claim_meta_events_by_asrt_id: dict[str, list[_ClaimMetaEvent]] = {}
        self._claim_meta_events_by_asrt_id_key: dict[
            tuple[str, str], list[_ClaimMetaEvent]
        ] = {}

        self._claim_args: list[ClaimArg] = []
        self._claim_args_by_asrt_id: dict[str, list[ClaimArg]] = {}

        self._meta_rows_data: list[MetaRow] = []
        self._meta_by_asrt_id: dict[str, list[MetaRow]] = {}
        self._meta_by_kind: dict[str, list[MetaRow]] = {}
        self._meta_by_key: dict[str, list[MetaRow]] = {}
        self._meta_by_asrt_id_key: dict[tuple[str, str], list[MetaRow]] = {}
        self._meta_by_asrt_id_key_kind: dict[tuple[str, str, str], list[MetaRow]] = {}
        self._meta_ingest_key_asrt_ids: dict[str, list[str]] = {}

        self._annotation_rows_data: list[AnnotationRow] = []
        self._anno_by_asrt_id: dict[str, list[AnnotationRow]] = {}
        self._anno_by_ns_cat: dict[tuple[str, str], list[AnnotationRow]] = {}
        self._anno_by_key: dict[str, list[AnnotationRow]] = {}
        self._anno_by_identity: dict[tuple[str, str, str, str], AnnotationRow] = {}

        self._revokes_data: list[Revokes] = []
        self._revoker_asrt_ids: set[str] = set()
        self._revoked_asrt_ids: set[str] = set()
        self._first_revoker_by_revoked_asrt_id: dict[str, str] = {}

    def _clear_meta_indexes(self) -> None:
        self._claim_meta_events = []
        self._claim_meta_events_by_asrt_id.clear()
        self._claim_meta_events_by_asrt_id_key.clear()
        self._meta_rows_data = []
        self._meta_by_asrt_id.clear()
        self._meta_by_kind.clear()
        self._meta_by_key.clear()
        self._meta_by_asrt_id_key.clear()
        self._meta_by_asrt_id_key_kind.clear()
        self._meta_ingest_key_asrt_ids.clear()

    def _clear_annotation_indexes(self) -> None:
        self._annotation_rows_data = []
        self._anno_by_asrt_id.clear()
        self._anno_by_ns_cat.clear()
        self._anno_by_key.clear()
        self._anno_by_identity.clear()

    def _idx_add_claim(self, claim: Claim, *, tx_ref: int | None = None) -> None:
        if claim.pred_id.startswith(_SYSTEM_PREFIX):
            self._idx_add_system_revocation_claim(claim, tx_ref=tx_ref)
            return
        self._claims.append(claim)
        self._claim_by_asrt_id[claim.asrt_id] = claim
        if tx_ref is not None:
            self._claim_tx_refs[claim.asrt_id] = tx_ref
        self._claims_by_pred_id.setdefault(claim.pred_id, []).append(claim)
        self._claims_by_e_ref.setdefault(claim.e_ref, []).append(claim)
        self._claims_by_pred_e_ref.setdefault((claim.pred_id, claim.e_ref), []).append(claim)
        rows = [
            ClaimArg(claim.asrt_id, idx, value, tag)
            for idx, value, tag in claim_args_from_rest_terms(claim.rest_terms)
        ]
        self._idx_add_claim_args(rows)

    def _idx_add_system_revocation_claim(
        self,
        claim: Claim,
        *,
        tx_ref: int | None = None,
    ) -> None:
        if claim.pred_id != _REVOCATION_PREDICATE:
            raise LedgerFormatError(f"unsupported system claim predicate: {claim.pred_id}")
        if len(claim.rest_terms) != 1 or claim.rest_terms[0][0] != "string":
            raise LedgerFormatError("__system__.revokes claim has invalid value shape")
        self._system_claim_by_asrt_id[claim.asrt_id] = claim
        if tx_ref is not None:
            self._claim_tx_refs[claim.asrt_id] = tx_ref

    def _idx_add_claim_args(self, rows: list[ClaimArg]) -> None:
        for row in rows:
            self._claim_args.append(row)
            self._claim_args_by_asrt_id.setdefault(row.asrt_id, []).append(row)

    def _idx_add_meta(self, rows: list[MetaRow]) -> None:
        for row in rows:
            self._meta_rows_data.append(row)
            self._meta_by_asrt_id.setdefault(row.asrt_id, []).append(row)
            self._meta_by_kind.setdefault(row.kind, []).append(row)
            self._meta_by_key.setdefault(row.key, []).append(row)
            self._meta_by_asrt_id_key.setdefault((row.asrt_id, row.key), []).append(row)
            self._meta_by_asrt_id_key_kind.setdefault((row.asrt_id, row.key, row.kind), []).append(
                row
            )
            if row.key == "ingest_key" and row.kind == "str" and isinstance(row.value, str):
                self._meta_ingest_key_asrt_ids.setdefault(row.value, []).append(row.asrt_id)

    def _idx_add_claim_meta_events(
        self,
        rows: Sequence[MetaRow | _MetaTombstone],
        *,
        tx_seq: int,
        op_ordinal: int,
        project_meta: bool,
    ) -> None:
        events = [
            _ClaimMetaEvent(
                asrt_id=row.asrt_id,
                key=row.key,
                kind=row.kind if isinstance(row, MetaRow) else None,
                value=row.value if isinstance(row, MetaRow) else None,
                tx_seq=tx_seq,
                op_ordinal=op_ordinal,
            )
            for row in rows
        ]
        for event in events:
            self._idx_add_claim_meta_event(event)
        if project_meta:
            self._idx_add_meta([row for row in rows if isinstance(row, MetaRow)])

    def _idx_add_claim_meta_event(self, event: _ClaimMetaEvent) -> None:
        self._claim_meta_events.append(event)
        self._claim_meta_events_by_asrt_id.setdefault(event.asrt_id, []).append(event)
        self._claim_meta_events_by_asrt_id_key.setdefault(
            (event.asrt_id, event.key), []
        ).append(event)

    def _idx_add_annotation(self, rows: list[AnnotationRow]) -> None:
        for row in rows:
            identity = (row.asrt_id, row.namespace, row.category, row.key)
            existing = self._anno_by_identity.get(identity)
            if existing is not None:
                self._idx_remove_annotation(existing)
            self._annotation_rows_data.append(row)
            self._anno_by_asrt_id.setdefault(row.asrt_id, []).append(row)
            self._anno_by_ns_cat.setdefault((row.namespace, row.category), []).append(row)
            self._anno_by_key.setdefault(row.key, []).append(row)
            self._anno_by_identity[identity] = row

    def _idx_remove_annotation(self, row: AnnotationRow) -> None:
        with suppress(ValueError):
            self._annotation_rows_data.remove(row)

        rows = self._anno_by_asrt_id.get(row.asrt_id)
        if rows is not None:
            with suppress(ValueError):
                rows.remove(row)
            if not rows:
                self._anno_by_asrt_id.pop(row.asrt_id, None)

        rows = self._anno_by_ns_cat.get((row.namespace, row.category))
        if rows is not None:
            with suppress(ValueError):
                rows.remove(row)
            if not rows:
                self._anno_by_ns_cat.pop((row.namespace, row.category), None)

        rows = self._anno_by_key.get(row.key)
        if rows is not None:
            with suppress(ValueError):
                rows.remove(row)
            if not rows:
                self._anno_by_key.pop(row.key, None)

        self._anno_by_identity.pop((row.asrt_id, row.namespace, row.category, row.key), None)

    def _idx_add_revoke(self, row: Revokes) -> None:
        self._revokes_data.append(row)
        self._revoker_asrt_ids.add(row.revoker_asrt_id)
        self._revoked_asrt_ids.add(row.revoked_asrt_id)
        self._first_revoker_by_revoked_asrt_id.setdefault(row.revoked_asrt_id, row.revoker_asrt_id)

    def _load_from_db_via(self, conn: sqlite3.Connection) -> None:
        self._reset_indexes()

        next_op_ordinal_by_tx: dict[int, int] = {}
        for row in conn.execute(
            "SELECT asrt_id, pred_id, e_ref, rest_terms, value, value_tag, tx_ref "
            "FROM claims ORDER BY seq"
        ).fetchall():
            claim = _row_to_claim(row)
            tx_ref = int(row["tx_ref"])
            op_ordinal = next_op_ordinal_by_tx.get(tx_ref, 0)
            next_op_ordinal_by_tx[tx_ref] = op_ordinal + 1
            self._claim_op_ordinals[claim.asrt_id] = op_ordinal
            if claim.pred_id.startswith(_SYSTEM_PREFIX):
                self._idx_add_system_revocation_claim(claim, tx_ref=tx_ref)
                self._idx_add_revoke(Revokes(claim.asrt_id, str(claim.rest_terms[0][1])))
            else:
                self._claim_tx_refs[claim.asrt_id] = tx_ref
                self._idx_add_claim(claim)

        persisted_meta_rows = conn.execute(
            "SELECT rowid, asrt_id, key, kind, value, tx_seq, op_ordinal "
            "FROM claim_meta ORDER BY tx_seq, op_ordinal, rowid"
        ).fetchall()
        identity_marked_asrt_ids = {
            str(row["asrt_id"])
            for row in persisted_meta_rows
            if row["key"] == "tx_id" and row["kind"] == "str"
        }
        identity_closed: set[str] = set()
        for row in persisted_meta_rows:
            kind = row["kind"]
            value = _decode_meta_value(kind, row["value"])
            key = str(row["key"])
            asrt_id = str(row["asrt_id"])
            self._idx_add_claim_meta_event(
                _ClaimMetaEvent(
                    asrt_id=asrt_id,
                    key=key,
                    kind=None if kind is None else str(kind),
                    value=value,
                    tx_seq=int(row["tx_seq"]),
                    op_ordinal=int(row["op_ordinal"]),
                )
            )
            if kind is None:
                continue
            if key.startswith(_ANNOTATION_COMPAT_PREFIX):
                self._idx_add_annotation(
                    [_annotation_from_storage_key(asrt_id, key, str(kind), value)]
                )
                continue
            meta = MetaRow(asrt_id, key, str(kind), value)
            self._idx_add_meta([meta])
            if asrt_id in identity_marked_asrt_ids:
                is_initial_meta = asrt_id not in identity_closed
            else:
                is_initial_meta = (
                    int(row["tx_seq"]) == self._claim_tx_refs.get(asrt_id)
                    and int(row["op_ordinal"]) == self._claim_op_ordinals.get(asrt_id)
                )
            if is_initial_meta:
                annotation = _initial_meta_annotation_row(meta)
                if annotation is not None:
                    self._idx_add_annotation([annotation])
            if key == "tx_id" and kind == "str":
                identity_closed.add(asrt_id)

    def _load_from_db(self) -> None:
        self._load_from_db_via(self._get_connection())

    def _is_known_asrt_id(self, asrt_id: str) -> bool:
        with self._write_lock:
            return asrt_id in self._claim_by_asrt_id or asrt_id in self._system_claim_by_asrt_id

    def _find_ingest_key(self, ingest_key: str) -> str | None:
        with self._write_lock:
            for asrt_id in self._meta_ingest_key_asrt_ids.get(ingest_key, []):
                if asrt_id in self._claim_by_asrt_id:
                    if self.has_active_revocation(asrt_id):
                        continue
                    return asrt_id
                if asrt_id in self._revoker_asrt_ids:
                    return asrt_id
        return None

    def _backfill_ingest_key(self, ingest_key: str, asrt_id: str, kind: str) -> None:
        return

    def _insert_claim(
        self,
        conn: sqlite3.Connection,
        claim: Claim,
        asrt_id: str,
        *,
        tx_ref: int,
    ) -> None:
        _validate_claim_identity(asrt_id=asrt_id, pred_id=claim.pred_id, e_ref=claim.e_ref)
        normalized = [_normalize_term(term) for term in claim.rest_terms]
        if len(normalized) <= 1:
            value, value_tag = _encode_claim_value(normalized)
            stored_rest_terms = _enc_rest_terms([])
        else:
            # Q-SYS-B Q15.1: retain the legacy n-ary carrier through Slice 5.
            value, value_tag = None, None
            stored_rest_terms = _enc_rest_terms(normalized)
        try:
            conn.execute(
                "INSERT INTO claims "
                "(asrt_id, pred_id, e_ref, rest_terms, value, value_tag, tx_ref) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    asrt_id,
                    claim.pred_id,
                    claim.e_ref,
                    stored_rest_terms,
                    value,
                    value_tag,
                    tx_ref,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"duplicate asrt_id: {asrt_id}") from exc

    def _insert_meta_rows(
        self,
        conn: sqlite3.Connection,
        rows: Sequence[MetaRow | _MetaTombstone],
        asrt_id: str,
        *,
        tx_seq: int,
        op_ordinal: int,
    ) -> None:
        conn.executemany(
            "INSERT INTO claim_meta "
            "(asrt_id, key, kind, value, tx_seq, op_ordinal) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    asrt_id,
                    row.key,
                    row.kind if isinstance(row, MetaRow) else None,
                    _encode_meta_value(row.kind, row.value)
                    if isinstance(row, MetaRow)
                    else None,
                    tx_seq,
                    op_ordinal,
                )
                for row in rows
            ],
        )

    def _insert_annotation_rows(
        self,
        conn: sqlite3.Connection,
        rows: list[AnnotationRow],
        *,
        tx_seq: int,
        op_ordinal: int,
        skip_meta_rows: Sequence[MetaRow],
    ) -> None:
        compatibility_rows = _annotation_compatibility_meta_rows(rows, skip_meta_rows)
        if compatibility_rows:
            for row in compatibility_rows:
                self._insert_meta_rows(
                    conn,
                    [row],
                    row.asrt_id,
                    tx_seq=tx_seq,
                    op_ordinal=op_ordinal,
                )

    @staticmethod
    def _next_direct_tx_seq(conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT MAX(seq_value) AS max_seq FROM ("
            "SELECT MAX(tx_ref) AS seq_value FROM claims "
            "UNION ALL SELECT MAX(tx_seq) AS seq_value FROM claim_meta"
            ")"
        ).fetchone()
        return 0 if row is None or row["max_seq"] is None else int(row["max_seq"]) + 1


def _new_asrt_id() -> str:
    return uuid.uuid4().hex


def _row_to_claim(row: sqlite3.Row) -> Claim:
    return Claim(
        row["asrt_id"],
        row["pred_id"],
        row["e_ref"],
        _decode_claim_terms(row["rest_terms"], row["value"], row["value_tag"]),
    )


def _validate_claim_input(claim: Claim, *, require_asrt_id: bool) -> None:
    if not isinstance(claim, Claim):
        raise TypeError("claim must be Claim")
    _validate_claim_identity(
        asrt_id=claim.asrt_id if require_asrt_id else None,
        pred_id=claim.pred_id,
        e_ref=claim.e_ref,
    )
    if claim.pred_id.startswith(_SYSTEM_PREFIX):
        raise ValueError(
            "general claim writes cannot use the reserved '__system__.' namespace; "
            "use the dedicated revocation path"
        )


def _validate_claim_identity(*, asrt_id: str | None, pred_id: str, e_ref: str) -> None:
    if asrt_id is not None and (not isinstance(asrt_id, str) or not asrt_id):
        raise ValueError("asrt_id must be non-empty")
    if not isinstance(pred_id, str) or not pred_id:
        raise ValueError("pred_id must be non-empty")
    if not isinstance(e_ref, str) or not e_ref:
        raise ValueError("e_ref must be non-empty")


def _validate_claim_args_rows(rows: list[ClaimArg]) -> None:
    for row in rows:
        if not isinstance(row, ClaimArg):
            raise TypeError("rows must contain ClaimArg")
        if isinstance(row.idx, bool) or not isinstance(row.idx, int) or row.idx < 0:
            raise ValueError("claim_arg idx must be non-negative int")
        if not isinstance(row.tag, str) or not row.tag:
            raise ValueError("claim_arg tag must be non-empty str")


def _validate_meta_rows(rows: list[MetaRow]) -> None:
    for row in rows:
        if not isinstance(row, MetaRow):
            raise TypeError("rows must contain MetaRow")
        if row.kind not in META_KINDS:
            raise ValueError(f"unsupported meta kind: {row.kind}")
        if not isinstance(row.key, str) or not row.key:
            raise ValueError("meta key must be non-empty str")
        if _is_reserved_annotation_meta_key(row.key) and not isinstance(
            row, _AnnotationStorageMetaRow
        ):
            raise ValueError(
                "meta key uses the reserved annotation storage namespace: "
                f"{_ANNOTATION_COMPAT_PREFIX}"
            )
        if not isinstance(row.asrt_id, str) or not row.asrt_id:
            raise ValueError("meta asrt_id must be non-empty str")


def _validate_meta_events(rows: Sequence[MetaRow | _MetaTombstone]) -> None:
    normal_rows = [row for row in rows if isinstance(row, MetaRow)]
    _validate_meta_rows(normal_rows)
    for row in rows:
        if isinstance(row, MetaRow):
            continue
        if not isinstance(row, _MetaTombstone):
            raise TypeError("meta_appends must contain MetaRow or private UNSET events")
        if not isinstance(row.asrt_id, str) or not row.asrt_id:
            raise ValueError("UNSET asrt_id must be non-empty str")
        if not isinstance(row.key, str) or not row.key:
            raise ValueError("UNSET key must be non-empty str")
        if _is_reserved_annotation_meta_key(row.key):
            raise ValueError("UNSET cannot target the reserved annotation storage namespace")


def _normalize_event_sequence(value: tuple[int, int] | None) -> tuple[int, int] | None:
    if value is None:
        return None
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(isinstance(part, bool) or not isinstance(part, int) or part < 0 for part in value)
    ):
        raise ValueError("as_of must be a (tx_seq, op_ordinal) pair of non-negative ints")
    return value


def _claim_meta_event_sort_key(event: _ClaimMetaEvent) -> tuple[int, int, str, str]:
    return (event.tx_seq, event.op_ordinal, event.asrt_id, event.key)


def _validate_meta_rows_for_append_assertion(rows: list[MetaRow]) -> None:
    for row in rows:
        if not isinstance(row, MetaRow):
            raise TypeError("rows must contain MetaRow")
        if row.kind not in META_KINDS:
            raise ValueError(f"unsupported meta kind: {row.kind}")
        if not isinstance(row.key, str) or not row.key:
            raise ValueError("meta key must be non-empty str")
        if _is_reserved_annotation_meta_key(row.key):
            raise ValueError(
                "meta key uses the reserved annotation storage namespace: "
                f"{_ANNOTATION_COMPAT_PREFIX}"
            )
        if not isinstance(row.asrt_id, str):
            raise ValueError("meta asrt_id must be str when provided")


def _reject_duplicate_meta_keys(rows: Sequence[MetaRow], *, context: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        if row.key in seen:
            duplicates.add(row.key)
        seen.add(row.key)
    if duplicates:
        raise ValueError(
            f"{context} keys must be unique; repeated key(s): " + ", ".join(sorted(duplicates))
        )


def _materialize_idempotency_meta(
    rows: list[MetaRow],
    *,
    idempotency: Idempotency | None,
    asrt_id: str,
) -> list[MetaRow]:
    if idempotency is None:
        return rows
    if not isinstance(idempotency.ingest_key, str) or not idempotency.ingest_key:
        raise ValueError("ingest_key must be non-empty string")
    if idempotency.on_conflict not in {"skip", "error"}:
        raise ValueError("idempotency on_conflict must be 'skip' or 'error'")

    ingest_rows = [row for row in rows if row.key == "ingest_key"]
    if ingest_rows:
        row = ingest_rows[0]
        if row.kind != "str" or row.value != idempotency.ingest_key:
            raise ValueError("ingest_key meta must match the Idempotency ingest_key")
        return rows
    return [*rows, MetaRow(asrt_id, "ingest_key", "str", idempotency.ingest_key)]


def _validate_annotation_rows(rows: list[AnnotationRow]) -> None:
    for row in rows:
        if not isinstance(row, AnnotationRow):
            raise TypeError("rows must contain AnnotationRow")
        if not isinstance(row.asrt_id, str) or not row.asrt_id:
            raise ValueError("annotation asrt_id must be non-empty str")
        if not isinstance(row.namespace, str) or not row.namespace:
            raise ValueError("annotation namespace must be non-empty str")
        if row.category not in ANNOTATION_CATEGORIES:
            raise ValueError(f"unsupported annotation category: {row.category}")
        if not isinstance(row.key, str) or not row.key:
            raise ValueError("annotation key must be non-empty str")
        if row.kind not in META_KINDS:
            raise ValueError(f"unsupported annotation kind: {row.kind}")
        if row.origin not in ANNOTATION_ORIGINS:
            raise ValueError(f"unsupported annotation origin: {row.origin}")
        if row.origin == "derived" and (not isinstance(row.derivation, str) or not row.derivation):
            raise ValueError("derivation must be non-empty when origin='derived'")
        if row.derivation is not None and not isinstance(row.derivation, str):
            raise ValueError("annotation derivation must be str when provided")


def _validate_revokes_row(row: Revokes) -> None:
    if not isinstance(row, Revokes):
        raise TypeError("row must be Revokes")
    if not isinstance(row.revoker_asrt_id, str) or not row.revoker_asrt_id:
        raise ValueError("revoker_asrt_id and revoked_asrt_id must be non-empty")
    if not isinstance(row.revoked_asrt_id, str) or not row.revoked_asrt_id:
        raise ValueError("revoker_asrt_id and revoked_asrt_id must be non-empty")


def _normalize_term(term: tuple[str, Any]) -> tuple[str, Any]:
    if not isinstance(term, tuple) or len(term) != 2:
        raise ValueError("rest_terms entries must be tuple(tag, value)")
    tag, value = term
    if not isinstance(tag, str) or not tag:
        raise ValueError("rest_terms tag must be non-empty str")
    return tag, value
