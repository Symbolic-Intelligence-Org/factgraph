from __future__ import annotations

import base64
import json
import sqlite3
import threading
import uuid
import warnings
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Literal


META_KINDS = {"str", "int", "float", "bool", "time", "json"}
ANNOTATION_ORIGINS = {"observed", "derived"}
ANNOTATION_CATEGORIES = {"source", "semantic", "derived", "operational"}
_JSON_BYTES_KEY = "__factgraph_bytes_b64__"


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


_DDL = """
CREATE TABLE IF NOT EXISTS claims (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id    TEXT NOT NULL UNIQUE,
    pred_id    TEXT NOT NULL,
    e_ref      TEXT NOT NULL,
    rest_terms TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_args (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id  TEXT NOT NULL,
    idx      INTEGER NOT NULL,
    val_atom TEXT NOT NULL,
    tag      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta_rows (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id TEXT NOT NULL,
    key     TEXT NOT NULL,
    kind    TEXT NOT NULL,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revokes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    revoker_asrt_id  TEXT NOT NULL,
    revoked_asrt_id  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_keys (
    ingest_key TEXT PRIMARY KEY,
    asrt_id    TEXT NOT NULL,
    kind       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_asrt_id ON claims(asrt_id);
CREATE INDEX IF NOT EXISTS idx_claims_pred_id ON claims(pred_id);
CREATE INDEX IF NOT EXISTS idx_claims_e_ref ON claims(e_ref);
CREATE INDEX IF NOT EXISTS idx_claims_pred_eref ON claims(pred_id, e_ref);

CREATE INDEX IF NOT EXISTS idx_args_asrt ON claim_args(asrt_id);
CREATE INDEX IF NOT EXISTS idx_args_tag ON claim_args(tag);
CREATE INDEX IF NOT EXISTS idx_args_idx ON claim_args(idx);

CREATE INDEX IF NOT EXISTS idx_meta_asrt ON meta_rows(asrt_id);
CREATE INDEX IF NOT EXISTS idx_meta_key ON meta_rows(key);
CREATE INDEX IF NOT EXISTS idx_meta_kind ON meta_rows(kind);
CREATE INDEX IF NOT EXISTS idx_meta_asrt_key ON meta_rows(asrt_id, key);
CREATE INDEX IF NOT EXISTS idx_meta_asrt_key_kind ON meta_rows(asrt_id, key, kind);

CREATE INDEX IF NOT EXISTS idx_revokes_revoked ON revokes(revoked_asrt_id);
CREATE INDEX IF NOT EXISTS idx_revokes_revoker ON revokes(revoker_asrt_id);

CREATE TABLE IF NOT EXISTS annotation_rows (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id    TEXT NOT NULL,
    namespace  TEXT NOT NULL,
    category   TEXT NOT NULL,
    key        TEXT NOT NULL,
    kind       TEXT NOT NULL,
    value      TEXT NOT NULL,
    origin     TEXT NOT NULL,
    derivation TEXT,
    UNIQUE(asrt_id, namespace, category, key)
);

CREATE INDEX IF NOT EXISTS idx_anno_asrt ON annotation_rows(asrt_id);
CREATE INDEX IF NOT EXISTS idx_anno_ns_cat ON annotation_rows(namespace, category);
CREATE INDEX IF NOT EXISTS idx_anno_key ON annotation_rows(key);
CREATE INDEX IF NOT EXISTS idx_anno_asrt_ns_cat_key
    ON annotation_rows(asrt_id, namespace, category, key);
"""


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
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")
                for hook in post_commit:
                    hook()

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
        conn.executescript(_DDL)

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
        effective_asrt_id = asrt_id or (
            claim.asrt_id if isinstance(claim.asrt_id, str) and claim.asrt_id else _new_asrt_id()
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
        actual_meta_rows = [
            MetaRow(
                asrt_id=effective_asrt_id,
                key=row.key,
                kind=row.kind,
                value=row.value,
            )
            for row in meta_rows
        ]
        actual_annotation_rows = [
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
        if actual_annotation_rows:
            _validate_annotation_rows(actual_annotation_rows)

        with self._write_session() as (conn, post_commit):
            self._insert_claim(conn, actual_claim, effective_asrt_id)
            self._insert_claim_args(conn, actual_claim_args, effective_asrt_id)
            self._insert_meta_rows(conn, actual_meta_rows, effective_asrt_id)
            if actual_annotation_rows:
                self._insert_annotation_rows(conn, actual_annotation_rows)
            if idempotency is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, 'assertion')",
                    (idempotency.ingest_key, effective_asrt_id),
                )
            def _apply_assertion_indexes() -> None:
                self._idx_add_claim(actual_claim)
                self._idx_add_claim_args(actual_claim_args)
                self._idx_add_meta(actual_meta_rows)
                if actual_annotation_rows:
                    self._idx_add_annotation(actual_annotation_rows)
                if idempotency is not None:
                    self._ingest_keys[idempotency.ingest_key] = (effective_asrt_id, "assertion")

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
        effective_revoker_id = revoker_asrt_id or (
            revokes.revoker_asrt_id
            if isinstance(revokes.revoker_asrt_id, str) and revokes.revoker_asrt_id
            else _new_asrt_id()
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
        actual_meta_rows = [
            MetaRow(
                asrt_id=effective_revoker_id,
                key=row.key,
                kind=row.kind,
                value=row.value,
            )
            for row in meta_rows
        ]

        with self._write_session() as (conn, post_commit):
            conn.execute(
                "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                (effective_revoker_id, revokes.revoked_asrt_id),
            )
            self._insert_meta_rows(conn, actual_meta_rows, effective_revoker_id)
            if idempotency is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, 'revocation')",
                    (idempotency.ingest_key, effective_revoker_id),
                )
            def _apply_revocation_indexes() -> None:
                self._idx_add_revoke(actual_revokes)
                self._idx_add_meta(actual_meta_rows)
                if idempotency is not None:
                    self._ingest_keys[idempotency.ingest_key] = (effective_revoker_id, "revocation")

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
            self._insert_claim(conn, actual_claim, claim.asrt_id)
            post_commit.append(lambda: self._idx_add_claim(actual_claim))

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
        actual_rows = [
            ClaimArg(asrt_id=row.asrt_id, idx=row.idx, val_atom=row.val_atom, tag=row.tag)
            for row in rows
        ]
        with self._write_session() as (conn, post_commit):
            conn.executemany(
                "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) VALUES (?, ?, ?, ?)",
                [(row.asrt_id, row.idx, _enc(row.val_atom), row.tag) for row in actual_rows],
            )
            post_commit.append(lambda: self._idx_add_claim_args(actual_rows))

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
            conn.executemany(
                "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                [(row.asrt_id, row.key, row.kind, _enc(row.value)) for row in actual_rows],
            )
            post_commit.append(lambda: self._idx_add_meta(actual_rows))

    def append_annotations(self, rows: list[AnnotationRow]) -> None:
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
            self._insert_annotation_rows(conn, actual_rows)
            post_commit.append(lambda: self._idx_add_annotation(actual_rows))

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
            conn.execute(
                "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                (row.revoker_asrt_id, row.revoked_asrt_id),
            )
            post_commit.append(lambda: self._idx_add_revoke(actual_row))

    def get_claim(self, asrt_id: str) -> Claim | None:
        with self._write_lock:
            self._ensure_open()
            return self._claim_by_asrt_id.get(asrt_id)

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
            rows = self._claim_args_by_asrt_id.get(asrt_id, []) if asrt_id is not None else self._claim_args
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
            row = self._get_connection().execute(
                "SELECT value FROM ledger_meta WHERE key = ?",
                (key,),
            ).fetchone()
            return str(row["value"]) if row is not None else None

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
            conn.execute("DELETE FROM meta_rows")
            if actual_rows:
                conn.executemany(
                    "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                    [(row.asrt_id, row.key, row.kind, _enc(row.value)) for row in actual_rows],
                )
            def _apply_meta_replace() -> None:
                self._clear_meta_indexes()
                self._idx_add_meta(actual_rows)

            post_commit.append(_apply_meta_replace)

    def _reset_indexes(self) -> None:
        self._claims: list[Claim] = []
        self._claim_by_asrt_id: dict[str, Claim] = {}
        self._claims_by_pred_id: dict[str, list[Claim]] = {}
        self._claims_by_e_ref: dict[str, list[Claim]] = {}
        self._claims_by_pred_e_ref: dict[tuple[str, str], list[Claim]] = {}

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

        self._ingest_keys: dict[str, tuple[str, str]] = {}

    def _clear_meta_indexes(self) -> None:
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

    def _idx_add_claim(self, claim: Claim) -> None:
        self._claims.append(claim)
        self._claim_by_asrt_id[claim.asrt_id] = claim
        self._claims_by_pred_id.setdefault(claim.pred_id, []).append(claim)
        self._claims_by_e_ref.setdefault(claim.e_ref, []).append(claim)
        self._claims_by_pred_e_ref.setdefault((claim.pred_id, claim.e_ref), []).append(claim)

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
            self._meta_by_asrt_id_key_kind.setdefault((row.asrt_id, row.key, row.kind), []).append(row)
            if row.key == "ingest_key" and row.kind == "str" and isinstance(row.value, str):
                self._meta_ingest_key_asrt_ids.setdefault(row.value, []).append(row.asrt_id)

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

        for row in conn.execute(
            "SELECT asrt_id, pred_id, e_ref, rest_terms FROM claims ORDER BY seq"
        ).fetchall():
            self._idx_add_claim(_row_to_claim(row))

        for row in conn.execute(
            "SELECT asrt_id, idx, val_atom, tag FROM claim_args ORDER BY id"
        ).fetchall():
            self._idx_add_claim_args(
                [ClaimArg(row["asrt_id"], row["idx"], _dec(row["val_atom"]), row["tag"])]
            )

        for row in conn.execute(
            "SELECT asrt_id, key, kind, value FROM meta_rows ORDER BY id"
        ).fetchall():
            self._idx_add_meta([MetaRow(row["asrt_id"], row["key"], row["kind"], _dec(row["value"]))])

        for row in conn.execute(
            "SELECT asrt_id, namespace, category, key, kind, value, origin, derivation"
            " FROM annotation_rows ORDER BY id"
        ).fetchall():
            self._idx_add_annotation(
                [
                    AnnotationRow(
                        row["asrt_id"],
                        row["namespace"],
                        row["category"],
                        row["key"],
                        row["kind"],
                        _dec(row["value"]),
                        row["origin"],
                        row["derivation"],
                    )
                ]
            )

        for row in conn.execute(
            "SELECT revoker_asrt_id, revoked_asrt_id FROM revokes ORDER BY id"
        ).fetchall():
            self._idx_add_revoke(Revokes(row["revoker_asrt_id"], row["revoked_asrt_id"]))

        for row in conn.execute(
            "SELECT ingest_key, asrt_id, kind FROM ingest_keys ORDER BY ingest_key"
        ).fetchall():
            self._ingest_keys[str(row["ingest_key"])] = (str(row["asrt_id"]), str(row["kind"]))

    def _load_from_db(self) -> None:
        self._load_from_db_via(self._get_connection())

    def _is_known_asrt_id(self, asrt_id: str) -> bool:
        with self._write_lock:
            return asrt_id in self._claim_by_asrt_id or asrt_id in self._revoker_asrt_ids

    def _find_ingest_key(self, ingest_key: str) -> str | None:
        with self._write_lock:
            entry = self._ingest_keys.get(ingest_key)
            if entry is not None:
                asrt_id, kind = entry
                if kind == "assertion":
                    if asrt_id in self._claim_by_asrt_id and not self.has_active_revocation(asrt_id):
                        return asrt_id
                elif kind == "revocation" and asrt_id in self._revoker_asrt_ids:
                    return asrt_id

            for asrt_id in self._meta_ingest_key_asrt_ids.get(ingest_key, []):
                if asrt_id in self._claim_by_asrt_id:
                    if self.has_active_revocation(asrt_id):
                        continue
                    self._backfill_ingest_key(ingest_key, asrt_id, "assertion")
                    return asrt_id
                if asrt_id in self._revoker_asrt_ids:
                    self._backfill_ingest_key(ingest_key, asrt_id, "revocation")
                    return asrt_id
        return None

    def _backfill_ingest_key(self, ingest_key: str, asrt_id: str, kind: str) -> None:
        try:
            with self._write_session() as (conn, post_commit):
                conn.execute(
                    "INSERT OR REPLACE INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, ?)",
                    (ingest_key, asrt_id, kind),
                )
                post_commit.append(lambda: self._ingest_keys.__setitem__(ingest_key, (asrt_id, kind)))
        except Exception:
            return

    def _insert_claim(self, conn: sqlite3.Connection, claim: Claim, asrt_id: str) -> None:
        _validate_claim_identity(asrt_id=asrt_id, pred_id=claim.pred_id, e_ref=claim.e_ref)
        normalized = [_normalize_term(term) for term in claim.rest_terms]
        try:
            conn.execute(
                "INSERT INTO claims (asrt_id, pred_id, e_ref, rest_terms) VALUES (?, ?, ?, ?)",
                (asrt_id, claim.pred_id, claim.e_ref, _enc_rest_terms(normalized)),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"duplicate asrt_id: {asrt_id}") from exc

    def _insert_claim_args(self, conn: sqlite3.Connection, rows: list[ClaimArg], asrt_id: str) -> None:
        conn.executemany(
            "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) VALUES (?, ?, ?, ?)",
            [(asrt_id, row.idx, _enc(row.val_atom), row.tag) for row in rows],
        )

    def _insert_meta_rows(self, conn: sqlite3.Connection, rows: list[MetaRow], asrt_id: str) -> None:
        conn.executemany(
            "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
            [(asrt_id, row.key, row.kind, _enc(row.value)) for row in rows],
        )

    def _insert_annotation_rows(self, conn: sqlite3.Connection, rows: list[AnnotationRow]) -> None:
        conn.executemany(
            "INSERT OR REPLACE INTO annotation_rows"
            " (asrt_id, namespace, category, key, kind, value, origin, derivation)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.asrt_id,
                    row.namespace,
                    row.category,
                    row.key,
                    row.kind,
                    _enc(row.value),
                    row.origin,
                    row.derivation,
                )
                for row in rows
            ],
        )


def _new_asrt_id() -> str:
    return uuid.uuid4().hex


def _row_to_claim(row: sqlite3.Row) -> Claim:
    return Claim(row["asrt_id"], row["pred_id"], row["e_ref"], _dec_rest_terms(row["rest_terms"]))


def _validate_claim_input(claim: Claim, *, require_asrt_id: bool) -> None:
    if not isinstance(claim, Claim):
        raise TypeError("claim must be Claim")
    _validate_claim_identity(
        asrt_id=claim.asrt_id if require_asrt_id else None,
        pred_id=claim.pred_id,
        e_ref=claim.e_ref,
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
        if not isinstance(row.asrt_id, str) or not row.asrt_id:
            raise ValueError("meta asrt_id must be non-empty str")


def _validate_meta_rows_for_append_assertion(rows: list[MetaRow]) -> None:
    for row in rows:
        if not isinstance(row, MetaRow):
            raise TypeError("rows must contain MetaRow")
        if row.kind not in META_KINDS:
            raise ValueError(f"unsupported meta kind: {row.kind}")
        if not isinstance(row.key, str) or not row.key:
            raise ValueError("meta key must be non-empty str")
        if not isinstance(row.asrt_id, str):
            raise ValueError("meta asrt_id must be str when provided")


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
