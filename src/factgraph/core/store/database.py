from __future__ import annotations

import base64
import json
import math
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.schema.schema_ir import schema_digest as compute_schema_digest
from factgraph.core.store.ledger import Claim, ClaimArg, Ledger, META_KINDS, MetaRow


DBTX_V1_PREFIX = b"factpy\x00dbtx_v1\x00"
DBDATA_V1_PREFIX = b"factpy\x00dbdata_v1\x00"
ASSERTION_V1_PREFIX = b"factpy\x00assertion_v1\x00"
_JSON_BYTES_KEY = "__factpy_bytes_b64__"
_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1


class DatabaseError(Exception):
    """Base error for the Database identity substrate."""


class DuplicateAssertionError(DatabaseError):
    """Raised when a content-addressed assertion already exists."""


@dataclass(frozen=True)
class MetaEntry:
    key: str
    kind: str
    value: Any


@dataclass(frozen=True)
class AssertionInput:
    pred_id: str
    fact_tuple: tuple[tuple[str, Any], ...]
    meta: tuple[MetaEntry, ...] = ()


@dataclass(frozen=True)
class AssertionRecord:
    asrt_id: str
    pred_id: str
    fact_tuple: tuple[tuple[str, Any], ...]
    schema_digest: str
    assertion_digest: str
    tx_id: str
    meta: tuple[MetaEntry, ...]


@dataclass(frozen=True)
class DatabaseValue:
    db_id: str
    tx_id: str
    schema_digest: str
    data_digest: str


@dataclass(frozen=True)
class CommitResult:
    parent_tx_id: str
    value: DatabaseValue
    assertions: tuple[AssertionRecord, ...]


def canonical_bytes_dbdata_v1(asrt_ids: Iterable[str]) -> bytes:
    sorted_ids = sorted(_require_token(asrt_id, prefix="asrt:", field="asrt_id") for asrt_id in asrt_ids)
    out = bytearray(DBDATA_V1_PREFIX)
    out.extend(_u32be(len(sorted_ids)))
    for asrt_id in sorted_ids:
        out.extend(_str_field(asrt_id))
    return bytes(out)


def canonical_bytes_dbtx_v1(
    *,
    parent_tx_id: str | None,
    schema_digest: str,
    added_assertion_digests: Sequence[str],
    data_digest: str,
) -> bytes:
    if parent_tx_id is not None:
        _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id")
    _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    _require_token(data_digest, prefix="sha256:", field="data_digest")
    sorted_digests = sorted(
        _require_token(digest, prefix="sha256:", field="assertion_digest")
        for digest in added_assertion_digests
    )

    out = bytearray(DBTX_V1_PREFIX)
    out.extend(b"\x00" if parent_tx_id is None else b"\x01" + _str_field(parent_tx_id))
    out.extend(_str_field(schema_digest))
    out.extend(_u32be(len(sorted_digests)))
    for digest in sorted_digests:
        out.extend(_str_field(digest))
    out.extend(_str_field(data_digest))
    return bytes(out)


def canonical_bytes_assertion_v1(
    *,
    pred_id: str,
    fact_tuple: Sequence[tuple[str, Any]],
    schema_digest: str,
    meta: Sequence[MetaEntry | MetaRow | tuple[str, str, Any]] = (),
) -> bytes:
    if not isinstance(pred_id, str) or not pred_id:
        raise DatabaseError("pred_id must be non-empty string")
    _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    normalized_fact_tuple = _normalize_fact_tuple(fact_tuple)
    meta_entries = _normalize_meta_entries(meta)
    fact_bytes = canonical_bytes_tup_v1(list(normalized_fact_tuple))
    meta_bytes = _canonical_meta_entries_bytes(meta_entries)

    out = bytearray(ASSERTION_V1_PREFIX)
    out.extend(_str_field(pred_id))
    out.extend(_bytes_field(fact_bytes))
    out.extend(_str_field(schema_digest))
    out.extend(_bytes_field(meta_bytes))
    return bytes(out)


def assertion_digest_for(
    *,
    pred_id: str,
    fact_tuple: Sequence[tuple[str, Any]],
    schema_digest: str,
    meta: Sequence[MetaEntry | MetaRow | tuple[str, str, Any]] = (),
) -> str:
    return sha256_token(
        canonical_bytes_assertion_v1(
            pred_id=pred_id,
            fact_tuple=fact_tuple,
            schema_digest=schema_digest,
            meta=meta,
        )
    )


def asrt_id_for(
    *,
    pred_id: str,
    fact_tuple: Sequence[tuple[str, Any]],
    schema_digest: str,
    meta: Sequence[MetaEntry | MetaRow | tuple[str, str, Any]] = (),
) -> str:
    return "asrt:" + sha256_hex(
        canonical_bytes_assertion_v1(
            pred_id=pred_id,
            fact_tuple=fact_tuple,
            schema_digest=schema_digest,
            meta=meta,
        )
    )


class Database:
    """Database identity boundary above the append-only Ledger substrate."""

    def __init__(self, *, ledger: Ledger, db_id: str, schema_digest: str) -> None:
        self._ledger = ledger
        self._db_id = _require_db_id(db_id)
        self._schema_digest = _require_token(schema_digest, prefix="sha256:", field="schema_digest")

    @classmethod
    def create(cls, path: str | Path = ":memory:", *, schema_ir: dict[str, Any]) -> Database:
        ledger = Ledger(path=path)
        if ledger.get_ledger_meta("db_id") is not None:
            raise DatabaseError("Database already exists at path")
        if ledger.find_claims() or ledger.revokes:
            raise DatabaseError("Database.create requires an empty Ledger substrate")

        schema_token = compute_schema_digest(schema_ir)
        db_id = _new_db_id(path)
        data_digest = sha256_token(canonical_bytes_dbdata_v1(()))
        tx_id = "tx:" + sha256_hex(
            canonical_bytes_dbtx_v1(
                parent_tx_id=None,
                schema_digest=schema_token,
                added_assertion_digests=(),
                data_digest=data_digest,
            )
        )
        ledger.set_ledger_meta("db_id", db_id)
        ledger.set_ledger_meta("schema_digest", schema_token)
        ledger.set_ledger_meta("head_tx_id", tx_id)
        ledger.set_ledger_meta("head_data_digest", data_digest)
        return cls(ledger=ledger, db_id=db_id, schema_digest=schema_token)

    @classmethod
    def open(cls, path: str | Path, *, schema_ir: dict[str, Any]) -> Database:
        ledger = Ledger(path=path)
        db_id = ledger.get_ledger_meta("db_id")
        if db_id is None:
            raise DatabaseError("Database metadata not found; use Database.create first")
        schema_token = compute_schema_digest(schema_ir)
        stored_schema = ledger.get_ledger_meta("schema_digest")
        if stored_schema != schema_token:
            raise DatabaseError(
                f"schema_digest mismatch: stored={stored_schema!r}, expected={schema_token!r}"
            )
        if ledger.get_ledger_meta("head_tx_id") is None:
            raise DatabaseError("Database head_tx_id metadata missing")
        if ledger.get_ledger_meta("head_data_digest") is None:
            raise DatabaseError("Database head_data_digest metadata missing")
        return cls(ledger=ledger, db_id=db_id, schema_digest=schema_token)

    @property
    def db_id(self) -> str:
        return self._db_id

    @property
    def schema_digest(self) -> str:
        return self._schema_digest

    def head(self) -> DatabaseValue:
        tx_id = self._ledger.get_ledger_meta("head_tx_id")
        data_digest = self._ledger.get_ledger_meta("head_data_digest")
        if tx_id is None or data_digest is None:
            raise DatabaseError("Database head metadata missing")
        return DatabaseValue(
            db_id=self._db_id,
            tx_id=_require_token(tx_id, prefix="tx:", field="tx_id"),
            schema_digest=self._schema_digest,
            data_digest=_require_token(data_digest, prefix="sha256:", field="data_digest"),
        )

    def commit_assertions(self, assertions: Sequence[AssertionInput]) -> CommitResult:
        if not assertions:
            raise DatabaseError("commit_assertions requires at least one assertion")

        parent = self.head()
        prepared = [self._prepare_assertion(item) for item in assertions]
        added_ids = [record.asrt_id for record, _claim, _args, _meta in prepared]
        if len(set(added_ids)) != len(added_ids):
            raise DuplicateAssertionError("duplicate content-addressed assertion in commit")
        for asrt_id in added_ids:
            if self._ledger.get_claim(asrt_id) is not None:
                raise DuplicateAssertionError(f"assertion already exists: {asrt_id}")

        active_ids = self._active_assertion_ids()
        active_ids.update(added_ids)
        data_digest = sha256_token(canonical_bytes_dbdata_v1(active_ids))
        tx_id = "tx:" + sha256_hex(
            canonical_bytes_dbtx_v1(
                parent_tx_id=parent.tx_id,
                schema_digest=self._schema_digest,
                added_assertion_digests=[record.assertion_digest for record, *_ in prepared],
                data_digest=data_digest,
            )
        )

        records: list[AssertionRecord] = []
        for provisional, claim, args, input_meta_rows in prepared:
            record = AssertionRecord(
                asrt_id=provisional.asrt_id,
                pred_id=provisional.pred_id,
                fact_tuple=provisional.fact_tuple,
                schema_digest=provisional.schema_digest,
                assertion_digest=provisional.assertion_digest,
                tx_id=tx_id,
                meta=provisional.meta,
            )
            ledger_meta_rows = [
                *input_meta_rows,
                MetaRow(asrt_id=record.asrt_id, key="schema_digest", kind="str", value=record.schema_digest),
                MetaRow(
                    asrt_id=record.asrt_id,
                    key="assertion_digest",
                    kind="str",
                    value=record.assertion_digest,
                ),
                MetaRow(asrt_id=record.asrt_id, key="tx_id", kind="str", value=record.tx_id),
            ]
            self._ledger.append_assertion(
                claim=claim,
                claim_args=args,
                meta_rows=ledger_meta_rows,
                asrt_id=record.asrt_id,
            )
            records.append(record)

        self._ledger.replace_ledger_meta("head_tx_id", tx_id)
        self._ledger.replace_ledger_meta("head_data_digest", data_digest)
        return CommitResult(
            parent_tx_id=parent.tx_id,
            value=DatabaseValue(
                db_id=self._db_id,
                tx_id=tx_id,
                schema_digest=self._schema_digest,
                data_digest=data_digest,
            ),
            assertions=tuple(records),
        )

    def _prepare_assertion(
        self, item: AssertionInput
    ) -> tuple[AssertionRecord, Claim, list[ClaimArg], list[MetaRow]]:
        if not isinstance(item, AssertionInput):
            raise TypeError("assertions must contain AssertionInput")
        fact_tuple = _normalize_fact_tuple(item.fact_tuple)
        meta = _normalize_meta_entries(item.meta)
        assertion_digest = assertion_digest_for(
            pred_id=item.pred_id,
            fact_tuple=fact_tuple,
            schema_digest=self._schema_digest,
            meta=meta,
        )
        asrt_id = "asrt:" + assertion_digest.removeprefix("sha256:")
        e_ref = fact_tuple[0][1]
        rest_terms = list(fact_tuple[1:])
        claim = Claim(asrt_id=asrt_id, pred_id=item.pred_id, e_ref=e_ref, rest_terms=rest_terms)
        claim_arg_rows = claim_args_from_rest_terms(rest_terms)
        args = [
            ClaimArg(asrt_id=asrt_id, idx=idx, val_atom=val_atom, tag=tag)
            for idx, val_atom, tag in claim_arg_rows
        ]
        meta_rows = [MetaRow(asrt_id=asrt_id, key=row.key, kind=row.kind, value=row.value) for row in meta]
        provisional = AssertionRecord(
            asrt_id=asrt_id,
            pred_id=item.pred_id,
            fact_tuple=fact_tuple,
            schema_digest=self._schema_digest,
            assertion_digest=assertion_digest,
            tx_id="tx:" + "0" * 64,
            meta=meta,
        )
        return provisional, claim, args, meta_rows

    def _active_assertion_ids(self) -> set[str]:
        return {
            claim.asrt_id
            for claim in self._ledger.find_claims()
            if not self._ledger.has_active_revocation(claim.asrt_id)
        }


def _u32be(number: int) -> bytes:
    if number < 0:
        raise DatabaseError("negative length")
    return number.to_bytes(4, "big", signed=False)


def _str_field(value: str) -> bytes:
    if not isinstance(value, str):
        raise DatabaseError("expected string field")
    raw = value.encode("utf-8")
    return _u32be(len(raw)) + raw


def _bytes_field(value: bytes) -> bytes:
    return _u32be(len(value)) + value


def _require_token(value: str, *, prefix: str, field: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise DatabaseError(f"{field} must start with {prefix!r}")
    suffix = value[len(prefix) :]
    if len(suffix) != 64 or any(ch not in "0123456789abcdef" for ch in suffix):
        raise DatabaseError(f"{field} must use 64 lowercase hex chars")
    return value


def _require_db_id(value: str) -> str:
    if not isinstance(value, str) or not (value.startswith("db:") or value.startswith("mem:")):
        raise DatabaseError("db_id must start with 'db:' or 'mem:'")
    return value


def _new_db_id(path: str | Path) -> str:
    if str(path) == ":memory:":
        return f"mem:{uuid.uuid4()}"
    return f"db:{uuid.uuid4()}"


def _normalize_fact_tuple(fact_tuple: Sequence[tuple[str, Any]]) -> tuple[tuple[str, Any], ...]:
    if not isinstance(fact_tuple, tuple):
        raise DatabaseError("fact_tuple must be tuple of (tag, value) pairs")
    if not fact_tuple:
        raise DatabaseError("fact_tuple must include entity_ref in position 0")
    first = fact_tuple[0]
    if not isinstance(first, tuple) or len(first) != 2 or first[0] != "entity_ref":
        raise DatabaseError("fact_tuple[0] must be ('entity_ref', e_ref)")
    canonical_bytes_tup_v1(list(fact_tuple))
    return tuple(fact_tuple)


def _normalize_meta_entries(
    rows: Sequence[MetaEntry | MetaRow | tuple[str, str, Any]]
) -> tuple[MetaEntry, ...]:
    result: list[MetaEntry] = []
    for row in rows:
        if isinstance(row, MetaEntry):
            entry = row
        elif isinstance(row, MetaRow):
            entry = MetaEntry(row.key, row.kind, row.value)
        elif isinstance(row, tuple) and len(row) == 3:
            entry = MetaEntry(row[0], row[1], row[2])
        else:
            raise DatabaseError("meta entries must be MetaEntry, MetaRow, or (key, kind, value)")
        if not isinstance(entry.key, str) or not entry.key:
            raise DatabaseError("meta key must be non-empty string")
        if entry.kind not in META_KINDS:
            raise DatabaseError(f"unsupported meta kind: {entry.kind}")
        result.append(entry)
    return tuple(result)


def _canonical_meta_entries_bytes(rows: Sequence[MetaEntry]) -> bytes:
    encoded = [
        (row.key, row.kind, _meta_value_bytes(row.kind, row.value))
        for row in rows
    ]
    encoded.sort(key=lambda item: (item[0], item[1], item[2]))
    out = bytearray()
    out.extend(_u32be(len(encoded)))
    for key, kind, value_bytes in encoded:
        out.extend(_str_field(key))
        out.extend(_str_field(kind))
        out.extend(_bytes_field(value_bytes))
    return bytes(out)


def _meta_value_bytes(kind: str, value: Any) -> bytes:
    if kind == "str":
        if not isinstance(value, str):
            raise DatabaseError("meta str value must be str")
        return value.encode("utf-8")
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise DatabaseError("meta int value must be int and not bool")
        _require_int64(value, field="meta int")
        return str(value).encode("ascii")
    if kind == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DatabaseError("meta float value must be numeric and not bool")
        as_float = float(value)
        if not math.isfinite(as_float):
            raise DatabaseError("meta float value must be finite")
        if as_float == 0.0:
            as_float = 0.0
        return struct.pack(">d", as_float)
    if kind == "bool":
        if not isinstance(value, bool):
            raise DatabaseError("meta bool value must be bool")
        return b"\x01" if value else b"\x00"
    if kind == "time":
        if isinstance(value, bool) or not isinstance(value, int):
            raise DatabaseError("meta time value must be int epoch nanos")
        _require_int64(value, field="meta time")
        return struct.pack(">q", value)
    if kind == "json":
        return json.dumps(
            _to_jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    raise DatabaseError(f"unsupported meta kind: {kind}")


def _require_int64(value: int, *, field: str) -> None:
    if value < _INT64_MIN or value > _INT64_MAX:
        raise DatabaseError(f"{field} is out of int64 range")


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


__all__ = [
    "ASSERTION_V1_PREFIX",
    "DBDATA_V1_PREFIX",
    "DBTX_V1_PREFIX",
    "AssertionInput",
    "AssertionRecord",
    "CommitResult",
    "Database",
    "DatabaseError",
    "DatabaseValue",
    "DuplicateAssertionError",
    "MetaEntry",
    "asrt_id_for",
    "assertion_digest_for",
    "canonical_bytes_assertion_v1",
    "canonical_bytes_dbdata_v1",
    "canonical_bytes_dbtx_v1",
]
