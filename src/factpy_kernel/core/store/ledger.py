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
    Append-only ledger backed by SQLite.

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
        self._conn = sqlite3.connect(path_str, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if path_str == ":memory:":
            self._conn.execute("PRAGMA journal_mode = MEMORY")
        else:
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.executescript(_DDL)
        self._conn.commit()

    def __deepcopy__(self, memo: dict[int, Any]) -> Ledger:
        clone = Ledger()
        self._conn.backup(clone._conn)
        memo[id(self)] = clone
        return clone

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

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
        effective_asrt_id = asrt_id or (claim.asrt_id if isinstance(claim.asrt_id, str) and claim.asrt_id else _new_asrt_id())

        if idempotency is not None:
            existing = self._find_ingest_key(idempotency.ingest_key)
            if existing is not None:
                if idempotency.on_conflict == "error":
                    raise DuplicateIngestKeyError(f"ingest_key already exists: {idempotency.ingest_key}")
                return AppendResult(asrt_id=existing, written=False)

        with self._transaction():
            self._insert_claim(claim, effective_asrt_id)
            self._insert_claim_args(claim_args, effective_asrt_id)
            self._insert_meta_rows(meta_rows, effective_asrt_id)
            if idempotency is not None:
                self._conn.execute(
                    "INSERT INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, 'assertion')",
                    (idempotency.ingest_key, effective_asrt_id),
                )
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
            revokes.revoker_asrt_id if isinstance(revokes.revoker_asrt_id, str) and revokes.revoker_asrt_id else _new_asrt_id()
        )

        if idempotency is not None:
            existing = self._find_ingest_key(idempotency.ingest_key)
            if existing is not None:
                if idempotency.on_conflict == "error":
                    raise DuplicateIngestKeyError(f"ingest_key already exists: {idempotency.ingest_key}")
                return AppendResult(asrt_id=existing, written=False)

        with self._transaction():
            self._conn.execute(
                "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                (effective_revoker_id, revokes.revoked_asrt_id),
            )
            self._insert_meta_rows(meta_rows, effective_revoker_id)
            if idempotency is not None:
                self._conn.execute(
                    "INSERT INTO ingest_keys (ingest_key, asrt_id, kind) VALUES (?, ?, 'revocation')",
                    (idempotency.ingest_key, effective_revoker_id),
                )
        return AppendResult(asrt_id=effective_revoker_id, written=True)

    def append_claim(self, claim: Claim) -> None:
        _validate_claim_input(claim, require_asrt_id=True)
        with self._transaction():
            self._insert_claim(claim, claim.asrt_id)

    def append_claim_args(self, rows: list[ClaimArg]) -> None:
        _validate_claim_args_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for claim_arg: {row.asrt_id}")
        with self._transaction():
            self._conn.executemany(
                "INSERT INTO claim_args (asrt_id, idx, val_atom, tag) VALUES (?, ?, ?, ?)",
                [(row.asrt_id, row.idx, _enc(row.val_atom), row.tag) for row in rows],
            )

    def append_meta(self, rows: list[MetaRow]) -> None:
        _validate_meta_rows(rows)
        for row in rows:
            if not self._is_known_asrt_id(row.asrt_id):
                raise ValueError(f"unknown asrt_id for meta: {row.asrt_id}")
        with self._transaction():
            self._conn.executemany(
                "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                [(row.asrt_id, row.key, row.kind, _enc(row.value)) for row in rows],
            )

    def append_revokes(self, row: Revokes) -> None:
        _validate_revokes_row(row)
        with self._transaction():
            self._conn.execute(
                "INSERT INTO revokes (revoker_asrt_id, revoked_asrt_id) VALUES (?, ?)",
                (row.revoker_asrt_id, row.revoked_asrt_id),
            )

    def get_claim(self, asrt_id: str) -> Claim | None:
        row = self._conn.execute(
            "SELECT asrt_id, pred_id, e_ref, rest_terms FROM claims WHERE asrt_id = ?",
            (asrt_id,),
        ).fetchone()
        return _row_to_claim(row) if row is not None else None

    def find_claims(self, pred_id: str | None = None, e_ref: str | None = None) -> list[Claim]:
        conds: list[str] = []
        params: list[Any] = []
        if pred_id is not None:
            conds.append("pred_id = ?")
            params.append(pred_id)
        if e_ref is not None:
            conds.append("e_ref = ?")
            params.append(e_ref)
        where = f" WHERE {' AND '.join(conds)}" if conds else ""
        rows = self._conn.execute(
            f"SELECT asrt_id, pred_id, e_ref, rest_terms FROM claims{where} ORDER BY seq",
            params,
        ).fetchall()
        return [_row_to_claim(row) for row in rows]

    def find_claim_args(
        self,
        asrt_id: str | None = None,
        idx: int | None = None,
        tag: str | None = None,
    ) -> list[ClaimArg]:
        conds: list[str] = []
        params: list[Any] = []
        if asrt_id is not None:
            conds.append("asrt_id = ?")
            params.append(asrt_id)
        if idx is not None:
            conds.append("idx = ?")
            params.append(idx)
        if tag is not None:
            conds.append("tag = ?")
            params.append(tag)
        where = f" WHERE {' AND '.join(conds)}" if conds else ""
        rows = self._conn.execute(
            f"SELECT asrt_id, idx, val_atom, tag FROM claim_args{where} ORDER BY id",
            params,
        ).fetchall()
        return [ClaimArg(row["asrt_id"], row["idx"], _dec(row["val_atom"]), row["tag"]) for row in rows]

    def find_meta(
        self,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
    ) -> list[MetaRow]:
        conds: list[str] = []
        params: list[Any] = []
        if asrt_id is not None:
            conds.append("asrt_id = ?")
            params.append(asrt_id)
        if key is not None:
            conds.append("key = ?")
            params.append(key)
        if kind is not None:
            conds.append("kind = ?")
            params.append(kind)
        where = f" WHERE {' AND '.join(conds)}" if conds else ""
        rows = self._conn.execute(
            f"SELECT asrt_id, key, kind, value FROM meta_rows{where} ORDER BY id",
            params,
        ).fetchall()
        return [MetaRow(row["asrt_id"], row["key"], row["kind"], _dec(row["value"])) for row in rows]

    def has_active_revocation(self, revoked_asrt_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM revokes WHERE revoked_asrt_id = ? LIMIT 1",
            (revoked_asrt_id,),
        ).fetchone()
        return row is not None

    def find_revoker(self, revoked_asrt_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT revoker_asrt_id FROM revokes WHERE revoked_asrt_id = ? ORDER BY id LIMIT 1",
            (revoked_asrt_id,),
        ).fetchone()
        return str(row["revoker_asrt_id"]) if row is not None else None

    @property
    def claims(self) -> list[Claim]:
        rows = self._conn.execute(
            "SELECT asrt_id, pred_id, e_ref, rest_terms FROM claims ORDER BY seq"
        ).fetchall()
        return [_row_to_claim(row) for row in rows]

    @property
    def claim_args(self) -> list[ClaimArg]:
        rows = self._conn.execute(
            "SELECT asrt_id, idx, val_atom, tag FROM claim_args ORDER BY id"
        ).fetchall()
        return [ClaimArg(row["asrt_id"], row["idx"], _dec(row["val_atom"]), row["tag"]) for row in rows]

    @property
    def meta_rows(self) -> list[MetaRow]:
        rows = self._conn.execute(
            "SELECT asrt_id, key, kind, value FROM meta_rows ORDER BY id"
        ).fetchall()
        return [MetaRow(row["asrt_id"], row["key"], row["kind"], _dec(row["value"])) for row in rows]

    @property
    def _meta_rows(self) -> _MetaRowsProxy:
        return _MetaRowsProxy(self)

    @_meta_rows.setter
    def _meta_rows(self, rows: list[MetaRow]) -> None:
        self._force_replace_meta_rows(rows)

    @property
    def revokes(self) -> list[Revokes]:
        rows = self._conn.execute(
            "SELECT revoker_asrt_id, revoked_asrt_id FROM revokes ORDER BY id"
        ).fetchall()
        return [Revokes(row["revoker_asrt_id"], row["revoked_asrt_id"]) for row in rows]

    def rebuild_indexes(self) -> None:
        """No-op for API compatibility; SQLite maintains indexes itself."""

    def close(self) -> None:
        self._conn.close()

    def _force_replace_meta_rows(self, rows: list[MetaRow]) -> None:
        """
        Testing-only helper. Replaces the entire meta_rows table.

        This intentionally breaks append-only semantics and must not be used in production paths.
        """
        _validate_meta_rows(rows)
        with self._transaction():
            self._conn.execute("DELETE FROM meta_rows")
            if rows:
                self._conn.executemany(
                    "INSERT INTO meta_rows (asrt_id, key, kind, value) VALUES (?, ?, ?, ?)",
                    [(row.asrt_id, row.key, row.kind, _enc(row.value)) for row in rows],
                )

    def _is_known_asrt_id(self, asrt_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM claims WHERE asrt_id = ? LIMIT 1",
            (asrt_id,),
        ).fetchone()
        if row is not None:
            return True
        row = self._conn.execute(
            "SELECT 1 FROM revokes WHERE revoker_asrt_id = ? LIMIT 1",
            (asrt_id,),
        ).fetchone()
        return row is not None

    def _find_ingest_key(self, ingest_key: str) -> str | None:
        row = self._conn.execute(
            "SELECT asrt_id FROM ingest_keys WHERE ingest_key = ?",
            (ingest_key,),
        ).fetchone()
        return str(row["asrt_id"]) if row is not None else None

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
