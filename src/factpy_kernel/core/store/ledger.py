from __future__ import annotations

import base64
import json
import sqlite3
import uuid
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal


META_KINDS = {"str", "num", "bool", "time", "json"}
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
        self._reset_indexes()
        self._conn = sqlite3.connect(
            path_str,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        if path_str == ":memory:":
            self._conn.execute("PRAGMA journal_mode = MEMORY")
        else:
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.executescript(_DDL)
        self._load_from_db()

    def __deepcopy__(self, memo: dict[int, Any]) -> Ledger:
        clone = Ledger()
        self._conn.backup(clone._conn)
        clone._reset_indexes()
        clone._load_from_db()
        memo[id(self)] = clone
        return clone

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def append_assertion(
        self,
        *,
        claim: Claim,
        claim_args: list[ClaimArg],
        meta_rows: list[MetaRow],
        idempotency: Idempotency | None = None,
        asrt_id: str | None = None,
    ) -> AppendResult:
        _validate_claim_input(claim, require_asrt_id=False)
        _validate_claim_args_rows(claim_args)
        _validate_meta_rows(meta_rows)
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

        with self._transaction():
            self._insert_claim(actual_claim, effective_asrt_id)
            self._insert_claim_args(actual_claim_args, effective_asrt_id)
            self._insert_meta_rows(actual_meta_rows, effective_asrt_id)
            if idempotency is not None:
                self._conn.execute(
                    "INSERT OR REPLACE INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, 'assertion')",
                    (idempotency.ingest_key, effective_asrt_id),
                )

        self._idx_add_claim(actual_claim)
        self._idx_add_claim_args(actual_claim_args)
        self._idx_add_meta(actual_meta_rows)
        if idempotency is not None:
            self._ingest_keys[idempotency.ingest_key] = (effective_asrt_id, "assertion")
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

        with self._transaction():
            self._conn.execute(
                "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                (effective_revoker_id, revokes.revoked_asrt_id),
            )
            self._insert_meta_rows(actual_meta_rows, effective_revoker_id)
            if idempotency is not None:
                self._conn.execute(
                    "INSERT OR REPLACE INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, 'revocation')",
                    (idempotency.ingest_key, effective_revoker_id),
                )

        self._idx_add_revoke(actual_revokes)
        self._idx_add_meta(actual_meta_rows)
        if idempotency is not None:
            self._ingest_keys[idempotency.ingest_key] = (effective_revoker_id, "revocation")
        return AppendResult(asrt_id=effective_revoker_id, written=True)

    def append_claim(self, claim: Claim) -> None:
        """
        .. deprecated::
            请使用 append_assertion(...)。此方法在兼容期保留，
            后续清理阶段将降级为私有或删除。
        """
        _validate_claim_input(claim, require_asrt_id=True)
        normalized_terms = [_normalize_term(term) for term in claim.rest_terms]
        actual_claim = Claim(
            asrt_id=claim.asrt_id,
            pred_id=claim.pred_id,
            e_ref=claim.e_ref,
            rest_terms=normalized_terms,
        )
        with self._transaction():
            self._insert_claim(actual_claim, claim.asrt_id)
        self._idx_add_claim(actual_claim)

    def append_claim_args(self, rows: list[ClaimArg]) -> None:
        """
        .. deprecated::
            请使用 append_assertion(...)。此方法在兼容期保留，
            后续清理阶段将降级为私有或删除。
        """
        _validate_claim_args_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for claim_arg: {row.asrt_id}")
        actual_rows = [
            ClaimArg(asrt_id=row.asrt_id, idx=row.idx, val_atom=row.val_atom, tag=row.tag)
            for row in rows
        ]
        with self._transaction():
            self._conn.executemany(
                "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) VALUES (?, ?, ?, ?)",
                [(row.asrt_id, row.idx, _enc(row.val_atom), row.tag) for row in actual_rows],
            )
        self._idx_add_claim_args(actual_rows)

    def append_meta(self, rows: list[MetaRow]) -> None:
        """
        .. deprecated::
            请使用 append_assertion(...) 或 append_revocation(...)。
            此方法在兼容期保留，后续清理阶段将降级为私有或删除。
        """
        _validate_meta_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for meta: {row.asrt_id}")
        actual_rows = [
            MetaRow(asrt_id=row.asrt_id, key=row.key, kind=row.kind, value=row.value)
            for row in rows
        ]
        with self._transaction():
            self._conn.executemany(
                "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                [(row.asrt_id, row.key, row.kind, _enc(row.value)) for row in actual_rows],
            )
        self._idx_add_meta(actual_rows)

    def append_revokes(self, row: Revokes) -> None:
        """
        .. deprecated::
            请使用 append_revocation(...)。此方法在兼容期保留，
            后续清理阶段将降级为私有或删除。
        """
        _validate_revokes_row(row)
        actual_row = Revokes(
            revoker_asrt_id=row.revoker_asrt_id,
            revoked_asrt_id=row.revoked_asrt_id,
        )
        with self._transaction():
            self._conn.execute(
                "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                (row.revoker_asrt_id, row.revoked_asrt_id),
            )
        self._idx_add_revoke(actual_row)

    def get_claim(self, asrt_id: str) -> Claim | None:
        return self._claim_by_asrt_id.get(asrt_id)

    def find_claims(self, pred_id: str | None = None, e_ref: str | None = None) -> list[Claim]:
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

    def has_active_revocation(self, revoked_asrt_id: str) -> bool:
        return revoked_asrt_id in self._revoked_asrt_ids

    def find_revoker(self, revoked_asrt_id: str) -> str | None:
        return self._first_revoker_by_revoked_asrt_id.get(revoked_asrt_id)

    @property
    def claims(self) -> list[Claim]:
        return list(self._claims)

    @property
    def claim_args(self) -> list[ClaimArg]:
        return list(self._claim_args)

    @property
    def meta_rows(self) -> list[MetaRow]:
        return list(self._meta_rows_data)

    @property
    def _meta_rows(self) -> _MetaRowsProxy:
        return _MetaRowsProxy(self)

    @_meta_rows.setter
    def _meta_rows(self, rows: list[MetaRow]) -> None:
        self._force_replace_meta_rows(rows)

    @property
    def revokes(self) -> list[Revokes]:
        return list(self._revokes_data)

    def rebuild_indexes(self) -> None:
        """No-op for API compatibility; write-through cache updates eagerly."""

    def close(self) -> None:
        with suppress(Exception):
            self._conn.close()

    def get_ledger_meta(self, key: str) -> str | None:
        """Return the stored ledger_meta value for key, or None when absent."""
        row = self._conn.execute(
            "SELECT value FROM ledger_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return str(row["value"]) if row is not None else None

    def set_ledger_meta(self, key: str, value: str) -> None:
        """Insert a ledger_meta value when key is absent; existing values are preserved."""
        self._conn.execute(
            "INSERT OR IGNORE INTO ledger_meta (key, value) VALUES (?, ?)",
            (key, value),
        )

    def _force_replace_meta_rows(self, rows: list[MetaRow]) -> None:
        _validate_meta_rows(rows)
        actual_rows = [
            MetaRow(asrt_id=row.asrt_id, key=row.key, kind=row.kind, value=row.value)
            for row in rows
        ]
        with self._transaction():
            self._conn.execute("DELETE FROM meta_rows")
            if actual_rows:
                self._conn.executemany(
                    "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                    [(row.asrt_id, row.key, row.kind, _enc(row.value)) for row in actual_rows],
                )
        self._clear_meta_indexes()
        self._idx_add_meta(actual_rows)

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

    def _idx_add_revoke(self, row: Revokes) -> None:
        self._revokes_data.append(row)
        self._revoker_asrt_ids.add(row.revoker_asrt_id)
        self._revoked_asrt_ids.add(row.revoked_asrt_id)
        self._first_revoker_by_revoked_asrt_id.setdefault(row.revoked_asrt_id, row.revoker_asrt_id)

    def _load_from_db(self) -> None:
        self._reset_indexes()

        for row in self._conn.execute(
            "SELECT asrt_id, pred_id, e_ref, rest_terms FROM claims ORDER BY seq"
        ).fetchall():
            self._idx_add_claim(_row_to_claim(row))

        for row in self._conn.execute(
            "SELECT asrt_id, idx, val_atom, tag FROM claim_args ORDER BY id"
        ).fetchall():
            self._idx_add_claim_args(
                [ClaimArg(row["asrt_id"], row["idx"], _dec(row["val_atom"]), row["tag"])]
            )

        for row in self._conn.execute(
            "SELECT asrt_id, key, kind, value FROM meta_rows ORDER BY id"
        ).fetchall():
            self._idx_add_meta([MetaRow(row["asrt_id"], row["key"], row["kind"], _dec(row["value"]))])

        for row in self._conn.execute(
            "SELECT revoker_asrt_id, revoked_asrt_id FROM revokes ORDER BY id"
        ).fetchall():
            self._idx_add_revoke(Revokes(row["revoker_asrt_id"], row["revoked_asrt_id"]))

        for row in self._conn.execute(
            "SELECT ingest_key, asrt_id, kind FROM ingest_keys ORDER BY ingest_key"
        ).fetchall():
            self._ingest_keys[str(row["ingest_key"])] = (str(row["asrt_id"]), str(row["kind"]))

    def _is_known_asrt_id(self, asrt_id: str) -> bool:
        return asrt_id in self._claim_by_asrt_id or asrt_id in self._revoker_asrt_ids

    def _find_ingest_key(self, ingest_key: str) -> str | None:
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
            self._conn.execute(
                "INSERT OR REPLACE INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, ?)",
                (ingest_key, asrt_id, kind),
            )
        except Exception:
            return
        self._ingest_keys[ingest_key] = (asrt_id, kind)

    def _insert_claim(self, claim: Claim, asrt_id: str) -> None:
        _validate_claim_identity(asrt_id=asrt_id, pred_id=claim.pred_id, e_ref=claim.e_ref)
        normalized = [_normalize_term(term) for term in claim.rest_terms]
        try:
            self._conn.execute(
                "INSERT INTO claims (asrt_id, pred_id, e_ref, rest_terms) VALUES (?, ?, ?, ?)",
                (asrt_id, claim.pred_id, claim.e_ref, _enc_rest_terms(normalized)),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"duplicate asrt_id: {asrt_id}") from exc

    def _insert_claim_args(self, rows: list[ClaimArg], asrt_id: str) -> None:
        self._conn.executemany(
            "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) VALUES (?, ?, ?, ?)",
            [(asrt_id, row.idx, _enc(row.val_atom), row.tag) for row in rows],
        )

    def _insert_meta_rows(self, rows: list[MetaRow], asrt_id: str) -> None:
        self._conn.executemany(
            "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
            [(asrt_id, row.key, row.kind, _enc(row.value)) for row in rows],
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
