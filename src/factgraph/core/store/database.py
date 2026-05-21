from __future__ import annotations

import base64
import json
import math
import os
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.schema.schema_ir import (
    canonicalize_schema_ir_jcs,
    schema_digest as compute_schema_digest,
)
from factgraph.core.store.ledger import Claim, ClaimArg, Ledger, META_KINDS, MetaRow


DBTX_V1_PREFIX = b"factpy\x00dbtx_v1\x00"
DBDATA_V1_PREFIX = b"factpy\x00dbdata_v1\x00"
ASSERTION_V1_PREFIX = b"factpy\x00assertion_v1\x00"
VIEW_V1_PREFIX = b"factpy\x00subset_view_v1\x00"
_JSON_BYTES_KEY = "__factpy_bytes_b64__"
_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_WORKSPACE_MANIFEST_NAME = "factgraph_workspace.json"
_DATABASE_WORKSPACE_VERSION = "1"


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
class FrozenAssertionView:
    name: str
    db_id: str
    base_tx_id: str
    schema_digest: str
    asrt_ids: tuple[str, ...]
    view_digest: str


@dataclass(frozen=True)
class CommitResult:
    parent_tx_id: str
    value: DatabaseValue
    assertions: tuple[AssertionRecord, ...]


@dataclass(frozen=True)
class DatabaseWorkspacePaths:
    root: Path
    manifest: Path
    db: Path
    db_meta: Path
    objects: Path
    tx_objects: Path
    schema_objects: Path
    refs: Path
    head: Path
    assertions: Path
    views: Path
    registry: Path


def canonical_bytes_dbdata_v1(asrt_ids: Iterable[str]) -> bytes:
    sorted_ids = sorted(_require_token(asrt_id, prefix="asrt:", field="asrt_id") for asrt_id in asrt_ids)
    out = bytearray(DBDATA_V1_PREFIX)
    out.extend(_u32be(len(sorted_ids)))
    for asrt_id in sorted_ids:
        out.extend(_str_field(asrt_id))
    return bytes(out)


def canonical_bytes_view_v1(
    *,
    db_id: str,
    base_tx_id: str,
    schema_digest: str,
    asrt_ids: Iterable[str],
) -> bytes:
    _require_db_id(db_id)
    _require_token(base_tx_id, prefix="tx:", field="base_tx_id")
    _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    sorted_ids = _normalize_view_asrt_ids(asrt_ids)

    out = bytearray(VIEW_V1_PREFIX)
    out.extend(_str_field(db_id))
    out.extend(_str_field(base_tx_id))
    out.extend(_str_field(schema_digest))
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


def view_digest_for(
    *,
    db_id: str,
    base_tx_id: str,
    schema_digest: str,
    asrt_ids: Iterable[str],
) -> str:
    return sha256_token(
        canonical_bytes_view_v1(
            db_id=db_id,
            base_tx_id=base_tx_id,
            schema_digest=schema_digest,
            asrt_ids=asrt_ids,
        )
    )


class Database:
    """Database identity boundary above the append-only Ledger substrate."""

    def __init__(
        self,
        *,
        ledger: Ledger,
        db_id: str,
        schema_digest: str,
        workspace_paths: DatabaseWorkspacePaths | None = None,
    ) -> None:
        self._ledger = ledger
        self._db_id = _require_db_id(db_id)
        self._schema_digest = _require_token(schema_digest, prefix="sha256:", field="schema_digest")
        self._workspace_paths = workspace_paths

    @classmethod
    def create(cls, path: str | Path = ":memory:", *, schema_ir: dict[str, Any]) -> Database:
        if _is_memory_path(path):
            return cls._create_memory(schema_ir=schema_ir)
        return cls._create_workspace(path=Path(path), schema_ir=schema_ir)

    @classmethod
    def _create_memory(cls, *, schema_ir: dict[str, Any]) -> Database:
        path = ":memory:"
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
    def _create_workspace(cls, *, path: Path, schema_ir: dict[str, Any]) -> Database:
        paths = resolve_database_workspace_paths(path)
        _ensure_new_database_workspace(paths)

        schema_bytes = canonicalize_schema_ir_jcs(schema_ir)
        schema_token = compute_schema_digest(schema_ir)
        db_id = _new_db_id(path)
        data_digest = sha256_token(canonical_bytes_dbdata_v1(()))
        tx_id = _tx_id_for(
            parent_tx_id=None,
            schema_digest=schema_token,
            added_assertion_digests=(),
            data_digest=data_digest,
        )
        ledger = Ledger(path=paths.assertions)
        if ledger.get_ledger_meta("db_id") is not None:
            raise DatabaseError("Database already exists in db/assertions.db")
        if ledger.find_claims() or ledger.revokes:
            raise DatabaseError("Database.create requires an empty db/assertions.db substrate")

        _write_schema_object(paths, schema_digest=schema_token, schema_bytes=schema_bytes)
        _write_tx_object(
            paths,
            tx_id=tx_id,
            parent_tx_id=None,
            schema_digest=schema_token,
            data_digest=data_digest,
            added_assertion_digests=(),
            added_asrt_ids=(),
        )
        _write_database_meta(paths, db_id=db_id)
        _write_workspace_manifest(paths)
        _write_head_ref(paths, tx_id)
        _update_ledger_meta_cache(ledger, db_id=db_id, schema_digest=schema_token, tx_id=tx_id, data_digest=data_digest)
        return cls(ledger=ledger, db_id=db_id, schema_digest=schema_token, workspace_paths=paths)

    @classmethod
    def open(cls, path: str | Path, *, schema_ir: dict[str, Any]) -> Database:
        if _is_memory_path(path):
            raise DatabaseError("Database.open does not support ':memory:'")
        paths = resolve_database_workspace_paths(path)
        if _is_new_database_workspace(paths):
            return cls._open_workspace(paths=paths, schema_ir=schema_ir)
        if paths.manifest.exists() or paths.db.exists():
            raise DatabaseError("new-layout Database workspace metadata not found")
        return cls._open_legacy_ledger(path=path, schema_ir=schema_ir)

    @classmethod
    def _open_legacy_ledger(cls, *, path: str | Path, schema_ir: dict[str, Any]) -> Database:
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

    @classmethod
    def _open_workspace(cls, *, paths: DatabaseWorkspacePaths, schema_ir: dict[str, Any]) -> Database:
        schema_bytes = canonicalize_schema_ir_jcs(schema_ir)
        schema_token = compute_schema_digest(schema_ir)
        _validate_schema_object(paths, schema_digest=schema_token, expected_bytes=schema_bytes)
        meta = _read_database_meta(paths)
        db_id = _require_db_id(meta["db_id"])
        ledger = Ledger(path=paths.assertions)
        _read_head_value(paths, expected_schema_digest=schema_token, db_id=db_id)
        return cls(ledger=ledger, db_id=db_id, schema_digest=schema_token, workspace_paths=paths)

    @property
    def db_id(self) -> str:
        return self._db_id

    @property
    def schema_digest(self) -> str:
        return self._schema_digest

    def _ledger_for_attach(self) -> Ledger:
        """Return the mutable Ledger substrate for FactGraph.attach internals."""
        return self._ledger

    def head(self) -> DatabaseValue:
        if self._workspace_paths is not None:
            return _read_head_value(
                self._workspace_paths,
                expected_schema_digest=self._schema_digest,
                db_id=self._db_id,
            )
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
        added_assertion_digests = [record.assertion_digest for record, *_ in prepared]
        tx_id = _tx_id_for(
            parent_tx_id=parent.tx_id,
            schema_digest=self._schema_digest,
            added_assertion_digests=added_assertion_digests,
            data_digest=data_digest,
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

        if self._workspace_paths is not None:
            _write_tx_object(
                self._workspace_paths,
                tx_id=tx_id,
                parent_tx_id=parent.tx_id,
                schema_digest=self._schema_digest,
                data_digest=data_digest,
                added_assertion_digests=added_assertion_digests,
                added_asrt_ids=added_ids,
            )
            _write_head_ref(self._workspace_paths, tx_id)
            _update_ledger_meta_cache(
                self._ledger,
                db_id=self._db_id,
                schema_digest=self._schema_digest,
                tx_id=tx_id,
                data_digest=data_digest,
            )
        else:
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

    def create_view(
        self,
        name: str,
        asrt_ids: Iterable[str],
        *,
        base: DatabaseValue | None = None,
    ) -> FrozenAssertionView:
        if self._workspace_paths is None:
            raise DatabaseError("durable view persistence requires a new-layout Database workspace")

        normalized_name = _normalize_view_name(name)
        head = self.head()
        if base is not None and base != head:
            raise DatabaseError("view base must be the current Database head")
        normalized_ids = _normalize_view_asrt_ids(asrt_ids)
        for asrt_id in normalized_ids:
            if self._ledger.get_claim(asrt_id) is None:
                raise DatabaseError(f"view assertion does not exist: {asrt_id}")

        view_digest = view_digest_for(
            db_id=head.db_id,
            base_tx_id=head.tx_id,
            schema_digest=head.schema_digest,
            asrt_ids=normalized_ids,
        )
        view = FrozenAssertionView(
            name=normalized_name,
            db_id=head.db_id,
            base_tx_id=head.tx_id,
            schema_digest=head.schema_digest,
            asrt_ids=normalized_ids,
            view_digest=view_digest,
        )
        _write_view_object(self._workspace_paths, view)
        return view

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


def resolve_database_workspace_paths(path: str | Path) -> DatabaseWorkspacePaths:
    root = Path(path)
    db = root / "db"
    objects = db / "objects"
    refs = db / "refs"
    return DatabaseWorkspacePaths(
        root=root,
        manifest=root / _WORKSPACE_MANIFEST_NAME,
        db=db,
        db_meta=db / "meta.json",
        objects=objects,
        tx_objects=objects / "tx",
        schema_objects=objects / "schema",
        refs=refs,
        head=refs / "head.txt",
        assertions=db / "assertions.db",
        views=root / "views",
        registry=root / "registry",
    )


def write_schema_object_for_workspace(path: str | Path, schema_ir: dict[str, Any]) -> str:
    """Write the canonical schema object for a workspace and return its digest."""
    paths = resolve_database_workspace_paths(path)
    schema_bytes = canonicalize_schema_ir_jcs(schema_ir)
    schema_token = compute_schema_digest(schema_ir)
    _write_schema_object(paths, schema_digest=schema_token, schema_bytes=schema_bytes)
    return schema_token


def validate_schema_object_for_workspace(path: str | Path, schema_ir: dict[str, Any]) -> str:
    """Validate the canonical schema object for a workspace and return its digest."""
    paths = resolve_database_workspace_paths(path)
    schema_bytes = canonicalize_schema_ir_jcs(schema_ir)
    schema_token = compute_schema_digest(schema_ir)
    _validate_schema_object(paths, schema_digest=schema_token, expected_bytes=schema_bytes)
    return schema_token


def schema_object_exists_for_workspace(path: str | Path, schema_digest: str) -> bool:
    """Return whether a workspace contains the schema object for `schema_digest`."""
    paths = resolve_database_workspace_paths(path)
    return _schema_object_path(paths, schema_digest).exists()


def _is_memory_path(path: str | Path) -> bool:
    return str(path) == ":memory:"


def _is_new_database_workspace(paths: DatabaseWorkspacePaths) -> bool:
    return paths.db_meta.exists() and paths.head.exists() and paths.assertions.exists()


def _ensure_new_database_workspace(paths: DatabaseWorkspacePaths) -> None:
    if paths.root.exists() and not paths.root.is_dir():
        raise DatabaseError("Database workspace path exists and is not a directory")
    if paths.manifest.exists() or paths.db_meta.exists() or paths.head.exists() or paths.assertions.exists():
        raise DatabaseError("Database workspace already exists at path")
    for directory in (paths.root, paths.db, paths.objects, paths.tx_objects, paths.schema_objects, paths.refs):
        directory.mkdir(parents=True, exist_ok=True)


def _tx_id_for(
    *,
    parent_tx_id: str | None,
    schema_digest: str,
    added_assertion_digests: Sequence[str],
    data_digest: str,
) -> str:
    return "tx:" + sha256_hex(
        canonical_bytes_dbtx_v1(
            parent_tx_id=parent_tx_id,
            schema_digest=schema_digest,
            added_assertion_digests=added_assertion_digests,
            data_digest=data_digest,
        )
    )


def _write_schema_object(
    paths: DatabaseWorkspacePaths,
    *,
    schema_digest: str,
    schema_bytes: bytes,
) -> None:
    schema_path = _schema_object_path(paths, schema_digest)
    expected_digest = sha256_token(schema_bytes)
    if expected_digest != _require_token(schema_digest, prefix="sha256:", field="schema_digest"):
        raise DatabaseError("schema object bytes do not match schema_digest")
    _write_once_bytes(schema_path, schema_bytes)


def _write_view_object(paths: DatabaseWorkspacePaths, view: FrozenAssertionView) -> None:
    expected_digest = view_digest_for(
        db_id=view.db_id,
        base_tx_id=view.base_tx_id,
        schema_digest=view.schema_digest,
        asrt_ids=view.asrt_ids,
    )
    if expected_digest != _require_token(view.view_digest, prefix="sha256:", field="view_digest"):
        raise DatabaseError("view object identity fields do not match view_digest")
    _write_once_bytes(_view_object_path(paths, view.view_digest), _json_bytes(_view_object_payload(view)))


def _view_object_payload(view: FrozenAssertionView) -> dict[str, Any]:
    return {
        "asrt_ids": list(view.asrt_ids),
        "base_tx_id": _require_token(view.base_tx_id, prefix="tx:", field="base_tx_id"),
        "db_id": _require_db_id(view.db_id),
        "name": _normalize_view_name(view.name),
        "schema_digest": _require_token(view.schema_digest, prefix="sha256:", field="schema_digest"),
        "view_digest": _require_token(view.view_digest, prefix="sha256:", field="view_digest"),
    }


def _validate_schema_object(
    paths: DatabaseWorkspacePaths,
    *,
    schema_digest: str,
    expected_bytes: bytes,
) -> None:
    schema_path = _schema_object_path(paths, schema_digest)
    if not schema_path.exists():
        raise DatabaseError(f"schema object missing: {schema_path}")
    actual = schema_path.read_bytes()
    if actual != expected_bytes:
        raise DatabaseError("schema object bytes differ from canonical schema bytes")
    expected_digest = sha256_token(actual)
    if expected_digest != _require_token(schema_digest, prefix="sha256:", field="schema_digest"):
        raise DatabaseError("schema object filename/content digest mismatch")


def _write_tx_object(
    paths: DatabaseWorkspacePaths,
    *,
    tx_id: str,
    parent_tx_id: str | None,
    schema_digest: str,
    data_digest: str,
    added_assertion_digests: Sequence[str],
    added_asrt_ids: Sequence[str],
) -> None:
    tx_id = _require_token(tx_id, prefix="tx:", field="tx_id")
    sorted_digests = sorted(
        _require_token(digest, prefix="sha256:", field="assertion_digest")
        for digest in added_assertion_digests
    )
    sorted_asrt_ids = sorted(_require_token(asrt_id, prefix="asrt:", field="asrt_id") for asrt_id in added_asrt_ids)
    expected_tx_id = _tx_id_for(
        parent_tx_id=parent_tx_id,
        schema_digest=schema_digest,
        added_assertion_digests=sorted_digests,
        data_digest=data_digest,
    )
    if expected_tx_id != tx_id:
        raise DatabaseError("tx object identity fields do not match tx_id")
    payload = {
        "added_assertion_digests": sorted_digests,
        "added_asrt_ids": sorted_asrt_ids,
        "data_digest": _require_token(data_digest, prefix="sha256:", field="data_digest"),
        "parent_tx_id": None
        if parent_tx_id is None
        else _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id"),
        "schema_digest": _require_token(schema_digest, prefix="sha256:", field="schema_digest"),
        "tx_id": tx_id,
    }
    _write_once_bytes(_tx_object_path(paths, tx_id), _json_bytes(payload))


def _read_tx_object(paths: DatabaseWorkspacePaths, tx_id: str) -> dict[str, Any]:
    tx_id = _require_token(tx_id, prefix="tx:", field="tx_id")
    tx_path = _tx_object_path(paths, tx_id)
    if not tx_path.exists():
        raise DatabaseError(f"tx object missing: {tx_path}")
    payload = json.loads(tx_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DatabaseError("tx object must be JSON object")
    if payload.get("tx_id") != tx_id:
        raise DatabaseError("tx object filename/content tx_id mismatch")
    parent_tx_id = payload.get("parent_tx_id")
    if parent_tx_id is not None:
        parent_tx_id = _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id")
    schema_token = _require_token(payload.get("schema_digest"), prefix="sha256:", field="schema_digest")
    data_digest = _require_token(payload.get("data_digest"), prefix="sha256:", field="data_digest")
    digests = payload.get("added_assertion_digests")
    if not isinstance(digests, list):
        raise DatabaseError("tx object added_assertion_digests must be list")
    assertion_digests = [
        _require_token(digest, prefix="sha256:", field="assertion_digest")
        for digest in digests
    ]
    added_asrt_ids = payload.get("added_asrt_ids")
    if not isinstance(added_asrt_ids, list):
        raise DatabaseError("tx object added_asrt_ids must be list")
    payload["added_asrt_ids"] = [
        _require_token(asrt_id, prefix="asrt:", field="asrt_id")
        for asrt_id in added_asrt_ids
    ]
    expected_tx_id = _tx_id_for(
        parent_tx_id=parent_tx_id,
        schema_digest=schema_token,
        added_assertion_digests=assertion_digests,
        data_digest=data_digest,
    )
    if expected_tx_id != tx_id:
        raise DatabaseError("tx object identity fields do not recompute tx_id")
    payload["parent_tx_id"] = parent_tx_id
    payload["schema_digest"] = schema_token
    payload["data_digest"] = data_digest
    payload["added_assertion_digests"] = assertion_digests
    return payload


def _write_database_meta(paths: DatabaseWorkspacePaths, *, db_id: str) -> None:
    payload = {
        "database_workspace_version": _DATABASE_WORKSPACE_VERSION,
        "db_id": _require_db_id(db_id),
    }
    _write_once_bytes(paths.db_meta, _json_bytes(payload))


def _read_database_meta(paths: DatabaseWorkspacePaths) -> dict[str, str]:
    if not paths.db_meta.exists():
        raise DatabaseError("Database meta.json missing")
    payload = json.loads(paths.db_meta.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DatabaseError("Database meta.json must be JSON object")
    version = payload.get("database_workspace_version")
    if version != _DATABASE_WORKSPACE_VERSION:
        raise DatabaseError(f"unsupported database_workspace_version: {version!r}")
    db_id = payload.get("db_id")
    if not isinstance(db_id, str):
        raise DatabaseError("Database meta.json db_id missing")
    return {"db_id": db_id}


def _write_workspace_manifest(paths: DatabaseWorkspacePaths) -> None:
    components = {
        "db": "db/",
        "views": "views/",
    }
    if paths.registry.exists():
        components["registry"] = "registry/"
    payload = {
        "components": components,
        "factgraph_workspace_version": _DATABASE_WORKSPACE_VERSION,
    }
    _atomic_write_bytes(paths.manifest, _json_bytes(payload))


def _write_head_ref(paths: DatabaseWorkspacePaths, tx_id: str) -> None:
    tx_id = _require_token(tx_id, prefix="tx:", field="tx_id")
    _read_tx_object(paths, tx_id)
    _atomic_write_bytes(paths.head, (tx_id + "\n").encode("ascii"))


def _read_head_value(
    paths: DatabaseWorkspacePaths,
    *,
    expected_schema_digest: str,
    db_id: str,
) -> DatabaseValue:
    if not paths.head.exists():
        raise DatabaseError("head.txt missing")
    tx_id = _require_token(paths.head.read_text(encoding="ascii").strip(), prefix="tx:", field="tx_id")
    tx_payload = _read_tx_object(paths, tx_id)
    schema_token = tx_payload["schema_digest"]
    if schema_token != _require_token(expected_schema_digest, prefix="sha256:", field="schema_digest"):
        raise DatabaseError("head tx object schema_digest mismatch")
    return DatabaseValue(
        db_id=_require_db_id(db_id),
        tx_id=tx_id,
        schema_digest=schema_token,
        data_digest=tx_payload["data_digest"],
    )


def _update_ledger_meta_cache(
    ledger: Ledger,
    *,
    db_id: str,
    schema_digest: str,
    tx_id: str,
    data_digest: str,
) -> None:
    ledger.replace_ledger_meta("db_id", _require_db_id(db_id))
    ledger.replace_ledger_meta("schema_digest", _require_token(schema_digest, prefix="sha256:", field="schema_digest"))
    ledger.replace_ledger_meta("head_tx_id", _require_token(tx_id, prefix="tx:", field="tx_id"))
    ledger.replace_ledger_meta("head_data_digest", _require_token(data_digest, prefix="sha256:", field="data_digest"))


def _tx_object_path(paths: DatabaseWorkspacePaths, tx_id: str) -> Path:
    return paths.tx_objects / f"{_token_hex(tx_id, prefix='tx:', field='tx_id')}.json"


def _schema_object_path(paths: DatabaseWorkspacePaths, schema_digest: str) -> Path:
    return paths.schema_objects / f"{_token_hex(schema_digest, prefix='sha256:', field='schema_digest')}.json"


def _view_object_path(paths: DatabaseWorkspacePaths, view_digest: str) -> Path:
    return paths.views / "objects" / f"{_token_hex(view_digest, prefix='sha256:', field='view_digest')}.json"


def _token_hex(value: str, *, prefix: str, field: str) -> str:
    return _require_token(value, prefix=prefix, field=field).removeprefix(prefix)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write_once_bytes(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise DatabaseError(f"object already exists with different bytes: {path}")
        return
    _atomic_write_bytes(path, data)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        with tmp.open("wb") as fh:
            fh.write(data)
            fh.flush()
            with _suppress_os_error():
                os.fsync(fh.fileno())
        os.replace(tmp, path)
        _fsync_parent(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _fsync_parent(path: Path) -> None:
    with _suppress_os_error():
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class _suppress_os_error:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> bool:
        return exc_type is not None and issubclass(exc_type, OSError)


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


def _normalize_view_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise DatabaseError("view name must be non-empty string")
    return name.strip()


def _normalize_view_asrt_ids(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise DatabaseError("view asrt_ids must be iterable[str], not string")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise DatabaseError("view asrt_ids must be iterable[str]") from exc
    return tuple(
        sorted(
            {
                _require_token(value, prefix="asrt:", field="view asrt_id")
                for value in items
            }
        )
    )


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
    "VIEW_V1_PREFIX",
    "AssertionInput",
    "AssertionRecord",
    "CommitResult",
    "Database",
    "DatabaseError",
    "DatabaseValue",
    "DatabaseWorkspacePaths",
    "DuplicateAssertionError",
    "FrozenAssertionView",
    "MetaEntry",
    "asrt_id_for",
    "assertion_digest_for",
    "canonical_bytes_assertion_v1",
    "canonical_bytes_dbdata_v1",
    "canonical_bytes_dbtx_v1",
    "canonical_bytes_view_v1",
    "resolve_database_workspace_paths",
    "schema_object_exists_for_workspace",
    "validate_schema_object_for_workspace",
    "view_digest_for",
    "write_schema_object_for_workspace",
]
