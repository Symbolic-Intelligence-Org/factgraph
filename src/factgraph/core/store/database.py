"""Durable Database commit protocol and dual state/history commitments.

Known durability gaps: macOS ``F_FULLFSYNC`` is not requested after the
portable ``fsync`` calls, and a missing authoritative tx object cannot yet be
re-anchored even when the SQLite ledger is intact. The explicit repair flow
therefore requires a valid tx-object head anchor.
"""

from __future__ import annotations

import base64
import fcntl
import json
import math
import os
import sqlite3
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Iterable, Mapping, Sequence

from factgraph.core.protocol.annotation_v1 import SHARED_ANNOTATION_KEYS
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.lthash import (
    LTHASH_SCHEME,
    LtHashError,
    add as lthash_add,
    decode_state,
    empty_state,
    encode_state,
    from_elements as lthash_from_elements,
    remove as lthash_remove,
)
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.schema.schema_ir import (
    SchemaIRValidationError,
    canonicalize_schema_ir_identity_jcs,
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
    schema_digest as compute_schema_digest,
)
from factgraph.core.store.ledger import (
    AnnotationRow,
    Claim,
    ClaimArg,
    Ledger,
    LedgerAssertionWrite,
    LedgerHeadConflictError,
    LedgerRevocationWrite,
    META_KINDS,
    MetaRow,
    Revokes,
)


DBTX_V1_PREFIX = b"factpy\x00dbtx_v1\x00"
DBTX_V2_PREFIX = b"factgraph\x00dbtx_v2\x00"
DBSTATE_ELEMENT_V2_PREFIX = b"factgraph\x00dbstate_element_v2\x00"
DBDATA_V1_PREFIX = b"factpy\x00dbdata_v1\x00"
ASSERTION_V1_PREFIX = b"factpy\x00assertion_v1\x00"
VIEW_V1_PREFIX = b"factpy\x00subset_view_v1\x00"
_JSON_BYTES_KEY = "__factpy_bytes_b64__"
_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_WORKSPACE_MANIFEST_NAME = "factgraph_workspace.json"
_DATABASE_WORKSPACE_VERSION = "1"
_RESERVED_ASSERTION_META_KEYS = frozenset({"assertion_digest", "schema_digest", "tx_id"})


class DatabaseError(Exception):
    """Base error for the Database identity substrate."""


class DuplicateAssertionError(DatabaseError):
    """Raised when a server-generated assertion id unexpectedly collides."""


class DatabaseIntegrityError(DatabaseError):
    """Raised when persisted history, state and ledger data disagree."""


class DatabaseLockedError(DatabaseError):
    """Raised when another process owns the workspace writer lock."""


class HeadConflictError(DatabaseError):
    """Raised when a commit loses the ledger head compare-and-swap."""


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
class RevocationInput:
    revoked_asrt_id: str
    meta: tuple[MetaEntry, ...] = ()


@dataclass(frozen=True)
class MetaAppendInput:
    asrt_id: str
    key: str
    kind: str
    value: Any


@dataclass(frozen=True)
class SchemaTransitionInput:
    old_schema_digest: str
    new_schema_ir: dict[str, Any]


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
class RevocationRecord:
    revoker_asrt_id: str
    revoked_asrt_id: str
    tx_id: str
    meta: tuple[MetaEntry, ...]


@dataclass(frozen=True)
class DatabaseValue:
    db_id: str
    tx_id: str
    schema_digest: str
    state_digest: str
    digest_scheme: str
    tx_seq: int

    @property
    def data_digest(self) -> str:
        """Compatibility alias for the v0.2 DatabaseValue field name."""
        return self.state_digest


@dataclass(frozen=True)
class FrozenAssertionSet:
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
    revocations: tuple[RevocationRecord, ...] = ()


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
    lock: Path
    assertions: Path
    views: Path


def canonical_bytes_dbdata_v1(asrt_ids: Iterable[str]) -> bytes:
    sorted_ids = sorted(
        _require_token(asrt_id, prefix="asrt:", field="asrt_id") for asrt_id in asrt_ids
    )
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


def canonical_bytes_dbtx_v2(
    *,
    parent_tx_id: str | None,
    schema_digest: str,
    digest_scheme: str,
    tx_seq: int,
    operations: Sequence[Mapping[str, Any]],
) -> bytes:
    """Canonical history commitment over one ordered commit delta.

    ``dbtx_v2`` operation tags are additive: ``A`` assertion, ``R``
    revocation, ``M`` append-meta, ``S`` schema-change, and the existing repair
    tags. Readers must continue accepting tx objects written before later tags
    were introduced.
    """
    if parent_tx_id is not None:
        _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id")
    _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    if digest_scheme != LTHASH_SCHEME:
        raise DatabaseError(f"unsupported digest_scheme: {digest_scheme!r}")
    if isinstance(tx_seq, bool) or not isinstance(tx_seq, int) or tx_seq < 0:
        raise DatabaseError("tx_seq must be non-negative int")
    normalized = _normalize_tx_operations(operations)

    out = bytearray(DBTX_V2_PREFIX)
    out.extend(b"\x00" if parent_tx_id is None else b"\x01" + _str_field(parent_tx_id))
    out.extend(_str_field(schema_digest))
    out.extend(_str_field(digest_scheme))
    out.extend(_u64be(tx_seq))
    out.extend(_u32be(len(normalized)))
    for operation in normalized:
        kind = operation["kind"]
        if kind == "assertion":
            out.extend(b"A")
            out.extend(_str_field(operation["asrt_id"]))
            out.extend(_str_field(operation["assertion_digest"]))
        elif kind == "revocation":
            out.extend(b"R")
            out.extend(_str_field(operation["revoker_asrt_id"]))
            out.extend(_str_field(operation["revoked_asrt_id"]))
            out.extend(_bytes_field(_canonical_meta_entries_bytes(operation["meta"])))
        elif kind == "append_meta":
            out.extend(b"M")
            out.extend(_str_field(operation["asrt_id"]))
            out.extend(_bytes_field(_canonical_meta_entries_bytes((operation["meta"],))))
        elif kind == "schema_change":
            out.extend(b"S")
            out.extend(_str_field(operation["old_schema_digest"]))
            out.extend(_str_field(operation["new_schema_digest"]))
        elif kind == "repair_add":
            out.extend(b"+")
            out.extend(_str_field(operation["asrt_id"]))
        elif kind == "repair_remove":
            out.extend(b"-")
            out.extend(_str_field(operation["asrt_id"]))
        elif kind == "repair":
            out.extend(b"P")
            out.extend(_str_field(operation["previous_state_digest"]))
            out.extend(_str_field(operation["rebuilt_state_digest"]))
            out.extend(_str_field(operation["reason"]))
        else:  # pragma: no cover - normalization is exhaustive
            raise DatabaseError(f"unsupported tx operation: {kind!r}")
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
        schema_ir: dict[str, Any] | None = None,
        workspace_paths: DatabaseWorkspacePaths | None = None,
        lock_handle: IO[bytes] | None = None,
    ) -> None:
        if workspace_paths is None and not getattr(ledger, "_memory_mode", False):
            raise DatabaseError(
                "durable legacy Ledger injection is not writable; "
                "use the Phase 3 migrate-workspace flow"
            )
        self._ledger = ledger
        self._db_id = _require_db_id(db_id)
        self._schema_digest = _require_token(schema_digest, prefix="sha256:", field="schema_digest")
        if schema_ir is not None:
            schema_ir = ensure_schema_ir(schema_ir)
            if compute_schema_digest(schema_ir) != self._schema_digest:
                raise DatabaseError("schema_ir does not match schema_digest")
        self._schema_ir = schema_ir
        self._workspace_paths = workspace_paths
        self._lock_handle = lock_handle
        self._closed = False

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            return

    def close(self) -> None:
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            self._ledger.close()
        finally:
            if self._lock_handle is not None:
                _release_workspace_lock(self._lock_handle)
                self._lock_handle = None

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
        state_digest = encode_state(empty_state())
        tx_id = _tx_id_for_v2(
            parent_tx_id=None,
            schema_digest=schema_token,
            digest_scheme=LTHASH_SCHEME,
            tx_seq=0,
            operations=(),
        )
        ledger.commit_batch(
            assertions=(),
            revocations=(),
            expected_head_tx_id=None,
            head_tx_id=tx_id,
            metadata=_head_metadata(
                db_id=db_id,
                schema_digest=schema_token,
                state_digest=state_digest,
                tx_seq=0,
            ),
        )
        return cls(
            ledger=ledger,
            db_id=db_id,
            schema_digest=schema_token,
            schema_ir=schema_ir,
        )

    @classmethod
    def _create_workspace(cls, *, path: Path, schema_ir: dict[str, Any]) -> Database:
        paths = resolve_database_workspace_paths(path)
        _ensure_new_database_workspace(paths)
        lock_handle = _acquire_workspace_lock(paths)
        ledger: Ledger | None = None
        try:
            schema_bytes = canonicalize_schema_ir_jcs(schema_ir)
            schema_token = compute_schema_digest(schema_ir)
            db_id = _new_db_id(path)
            state_digest = encode_state(empty_state())
            tx_id = _tx_id_for_v2(
                parent_tx_id=None,
                schema_digest=schema_token,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=0,
                operations=(),
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
                digest_scheme=LTHASH_SCHEME,
                tx_seq=0,
                operations=(),
            )
            _write_database_meta(paths, db_id=db_id)
            _write_workspace_manifest(paths)
            ledger.commit_batch(
                assertions=(),
                revocations=(),
                expected_head_tx_id=None,
                head_tx_id=tx_id,
                metadata=_head_metadata(
                    db_id=db_id,
                    schema_digest=schema_token,
                    state_digest=state_digest,
                    tx_seq=0,
                ),
            )
            return cls(
                ledger=ledger,
                db_id=db_id,
                schema_digest=schema_token,
                schema_ir=schema_ir,
                workspace_paths=paths,
                lock_handle=lock_handle,
            )
        except Exception:
            if ledger is not None:
                ledger.close()
            _release_workspace_lock(lock_handle)
            raise

    @classmethod
    def open(cls, path: str | Path, *, schema_ir: dict[str, Any]) -> Database:
        if _is_memory_path(path):
            raise DatabaseError("Database.open does not support ':memory:'")
        paths = resolve_database_workspace_paths(path)
        if _is_new_database_workspace(paths):
            lock_handle = _acquire_workspace_lock(paths)
            try:
                return cls._open_workspace(
                    paths=paths,
                    schema_ir=schema_ir,
                    lock_handle=lock_handle,
                )
            except Exception:
                _release_workspace_lock(lock_handle)
                raise
        if paths.manifest.exists() or paths.db.exists():
            raise DatabaseError(
                "legacy or incomplete Database workspace is not writable in v0.3; "
                "use the Phase 3 migrate-workspace flow"
            )
        if paths.root.exists():
            raise DatabaseError(
                "incomplete Database workspace: factgraph_workspace.json and db/ are missing; "
                "recreate the workspace or use the Phase 3 migrate-workspace flow for a legacy source"
            )
        raise DatabaseError(
            "legacy ledger write mode is disabled; use the Phase 3 migrate-workspace flow"
        )

    @classmethod
    def _open_workspace(
        cls,
        *,
        paths: DatabaseWorkspacePaths,
        schema_ir: dict[str, Any],
        lock_handle: IO[bytes],
    ) -> Database:
        schema_token = compute_schema_digest(schema_ir)
        _validate_schema_object(paths, schema_digest=schema_token, expected_schema_ir=schema_ir)
        meta = _read_database_meta(paths)
        db_id = _require_db_id(meta["db_id"])
        ledger = Ledger(path=paths.assertions)
        try:
            stored_scheme = ledger.get_ledger_meta("digest_scheme")
            if stored_scheme != LTHASH_SCHEME:
                raise DatabaseError(
                    f"Database digest_scheme {stored_scheme!r} is not writable in v0.3; "
                    "use the Phase 3 migrate-workspace flow"
                )
            _validate_workspace_integrity(
                paths,
                ledger=ledger,
                expected_schema_digest=schema_token,
                db_id=db_id,
            )
        except Exception:
            ledger.close()
            raise
        return cls(
            ledger=ledger,
            db_id=db_id,
            schema_digest=schema_token,
            schema_ir=schema_ir,
            workspace_paths=paths,
            lock_handle=lock_handle,
        )

    @classmethod
    def repair(
        cls,
        path: str | Path,
        *,
        schema_ir: dict[str, Any],
        reason: str = "explicit-rebuild",
    ) -> Database:
        """Rebuild state from ledger data and append an explicit repair event."""
        if _is_memory_path(path):
            raise DatabaseError("Database.repair requires a durable workspace")
        if not isinstance(reason, str) or not reason.strip():
            raise DatabaseError("repair reason must be non-empty string")
        paths = resolve_database_workspace_paths(path)
        if not _is_new_database_workspace(paths):
            raise DatabaseError("Database.repair requires a v0.3 Database workspace")
        lock_handle = _acquire_workspace_lock(paths)
        ledger: Ledger | None = None
        try:
            schema_token = compute_schema_digest(schema_ir)
            _validate_schema_object(paths, schema_digest=schema_token, expected_schema_ir=schema_ir)
            db_id = _require_db_id(_read_database_meta(paths)["db_id"])
            ledger = Ledger(path=paths.assertions)
            stored_scheme = ledger.get_ledger_meta("digest_scheme")
            if stored_scheme != LTHASH_SCHEME:
                raise DatabaseError(
                    f"Database digest_scheme {stored_scheme!r} is not repairable in v0.3; "
                    "use the Phase 3 migrate-workspace flow"
                )
            stored_head = ledger.get_ledger_meta("head_tx_id")
            if stored_head is None:
                raise DatabaseIntegrityError("repair cannot recover a missing head_tx_id anchor")
            parent_payload = _read_tx_object(paths, stored_head)
            history_ids = _replay_history(
                paths,
                head_tx_id=stored_head,
                expected_schema_digest=schema_token,
            )
            ledger_assertions = _active_factual_assertions(ledger)
            ledger_ids = set(ledger_assertions)
            rebuilt_digest = _state_digest_for_assertions(ledger_assertions)
            previous_digest = ledger.get_ledger_meta("head_state_digest") or "<missing>"
            operations: list[dict[str, Any]] = [
                {"kind": "repair_remove", "asrt_id": asrt_id}
                for asrt_id in sorted(history_ids - ledger_ids)
            ]
            operations.extend(
                {"kind": "repair_add", "asrt_id": asrt_id}
                for asrt_id in sorted(ledger_ids - history_ids)
            )
            operations.append(
                {
                    "kind": "repair",
                    "previous_state_digest": previous_digest,
                    "rebuilt_state_digest": rebuilt_digest,
                    "reason": reason.strip(),
                }
            )
            tx_seq = int(parent_payload["tx_seq"]) + 1
            tx_id = _tx_id_for_v2(
                parent_tx_id=stored_head,
                schema_digest=schema_token,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=tx_seq,
                operations=operations,
            )
            _write_tx_object(
                paths,
                tx_id=tx_id,
                parent_tx_id=stored_head,
                schema_digest=schema_token,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=tx_seq,
                operations=operations,
            )
            ledger.commit_batch(
                assertions=(),
                revocations=(),
                expected_head_tx_id=stored_head,
                head_tx_id=tx_id,
                metadata={
                    **_head_metadata(
                        db_id=db_id,
                        schema_digest=schema_token,
                        state_digest=rebuilt_digest,
                        tx_seq=tx_seq,
                    ),
                    "last_repair": json.dumps(
                        {
                            "reason": reason.strip(),
                            "repaired_at_epoch_ns": time.time_ns(),
                            "tx_id": tx_id,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            )
            _validate_workspace_integrity(
                paths,
                ledger=ledger,
                expected_schema_digest=schema_token,
                db_id=db_id,
            )
            return cls(
                ledger=ledger,
                db_id=db_id,
                schema_digest=schema_token,
                schema_ir=schema_ir,
                workspace_paths=paths,
                lock_handle=lock_handle,
            )
        except Exception:
            if ledger is not None:
                ledger.close()
            _release_workspace_lock(lock_handle)
            raise

    @property
    def db_id(self) -> str:
        return self._db_id

    @property
    def schema_digest(self) -> str:
        return self._schema_digest

    def touch_saved_at(self) -> int:
        """Update non-transactional workspace lifecycle metadata.

        Factual data, state/history commitments, and the Database head are not
        changed. This is the v0.3 implementation of ``FactGraph.save_workspace``.
        """
        self._ensure_open()
        if self._workspace_paths is None:
            raise DatabaseError("save metadata requires a durable Database workspace")
        payload = _read_database_meta(self._workspace_paths)
        saved_at = time.time_ns()
        payload["last_saved_at_epoch_ns"] = saved_at
        if "created_at_epoch_ns" not in payload:
            payload["created_at_epoch_ns"] = saved_at
        _atomic_write_bytes(self._workspace_paths.db_meta, _json_bytes(payload))
        return saved_at

    @classmethod
    def migrate_legacy_ledger(
        cls,
        *,
        source_ledger_path: str | Path,
        target_workspace: str | Path,
        schema_ir: dict[str, Any],
    ) -> DatabaseValue:
        """Build and verify a v0.3 workspace from an offline v0.2 Ledger.

        The target must be a distinct empty staging directory. Legacy factual
        and revocation rows keep their assertion ids and insertion order. The
        pre-v0.3 history cannot be reconstructed, so migration creates an
        explicit genesis repair anchor over the imported active set.
        """
        source = Path(source_ledger_path)
        target = Path(target_workspace)
        if not source.is_file():
            raise DatabaseError(f"legacy ledger component missing: {source}")
        if source.resolve(strict=False) == (
            resolve_database_workspace_paths(target).assertions.resolve(strict=False)
        ):
            raise DatabaseError("legacy migration source and target ledger must differ")

        created = cls.create(target, schema_ir=schema_ir)
        created.close()
        paths = resolve_database_workspace_paths(target)
        try:
            source_uri = source.resolve().as_uri() + "?mode=ro"
            source_conn = sqlite3.connect(source_uri, uri=True)
            try:
                target_conn = sqlite3.connect(str(paths.assertions))
                try:
                    source_conn.backup(target_conn)
                finally:
                    target_conn.close()
            finally:
                source_conn.close()
        except sqlite3.Error as exc:
            raise DatabaseError(f"failed to copy legacy ledger: {exc}") from exc

        for orphan in paths.tx_objects.glob("*.json"):
            orphan.unlink()

        schema_token = compute_schema_digest(schema_ir)
        db_id = _require_db_id(_read_database_meta(paths)["db_id"])
        ledger = Ledger(path=paths.assertions)
        try:
            if ledger.get_ledger_meta("head_tx_id") is not None:
                raise DatabaseError("legacy migration source already has a transactional head")

            assertion_digests: dict[str, str] = {}
            meta_appends: list[MetaRow] = []
            for claim in ledger.find_claims():
                asrt_id = _require_asrt_id(claim.asrt_id, field="legacy asrt_id")
                rows = ledger.find_meta(asrt_id=asrt_id)
                if any(row.key in _RESERVED_ASSERTION_META_KEYS for row in rows):
                    raise DatabaseError(
                        f"legacy assertion already carries v0.3 reserved metadata: {asrt_id}"
                    )
                if _is_system_predicate(claim.pred_id):
                    continue
                user_meta = _normalize_meta_entries(
                    tuple(MetaEntry(row.key, row.kind, row.value) for row in rows)
                )
                digest = assertion_digest_for(
                    pred_id=claim.pred_id,
                    fact_tuple=(("entity_ref", claim.e_ref), *tuple(claim.rest_terms)),
                    schema_digest=schema_token,
                    meta=user_meta,
                )
                assertion_digests[asrt_id] = digest

            active_assertions = {
                asrt_id: digest
                for asrt_id, digest in assertion_digests.items()
                if not ledger.has_active_revocation(asrt_id)
            }
            state_digest = _state_digest_for_assertions(active_assertions)
            operations: list[dict[str, Any]] = [
                {"kind": "repair_add", "asrt_id": asrt_id}
                for asrt_id in sorted(active_assertions)
            ]
            operations.append(
                {
                    "kind": "repair",
                    "previous_state_digest": "<legacy-v0.2-unanchored>",
                    "rebuilt_state_digest": state_digest,
                    "reason": "migrate-workspace-v0.2-anchor",
                }
            )
            tx_id = _tx_id_for_v2(
                parent_tx_id=None,
                schema_digest=schema_token,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=0,
                operations=operations,
            )
            for asrt_id, digest in assertion_digests.items():
                meta_appends.extend(
                    (
                        MetaRow(asrt_id, "schema_digest", "str", schema_token),
                        MetaRow(asrt_id, "assertion_digest", "str", digest),
                        MetaRow(asrt_id, "tx_id", "str", tx_id),
                    )
                )
            for revocation in ledger.revokes:
                revoker_id = _require_asrt_id(
                    revocation.revoker_asrt_id,
                    field="legacy revoker_asrt_id",
                )
                rows = ledger.find_meta(asrt_id=revoker_id)
                if any(row.key in {"schema_digest", "tx_id"} for row in rows):
                    raise DatabaseError(
                        f"legacy revoker already carries v0.3 reserved metadata: {revoker_id}"
                    )
                meta_appends.extend(
                    (
                        MetaRow(revoker_id, "schema_digest", "str", schema_token),
                        MetaRow(revoker_id, "tx_id", "str", tx_id),
                    )
                )

            _write_tx_object(
                paths,
                tx_id=tx_id,
                parent_tx_id=None,
                schema_digest=schema_token,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=0,
                operations=operations,
            )
            ledger.commit_batch(
                assertions=(),
                revocations=(),
                meta_appends=meta_appends,
                expected_head_tx_id=None,
                head_tx_id=tx_id,
                metadata={
                    **_head_metadata(
                        db_id=db_id,
                        schema_digest=schema_token,
                        state_digest=state_digest,
                        tx_seq=0,
                    ),
                    "migration_source_version": "v0.2",
                },
            )
        finally:
            ledger.close()

        verified = cls.open(target, schema_ir=schema_ir)
        try:
            return verified.head()
        finally:
            verified.close()

    def _ledger_for_attach(self) -> Ledger:
        """Return the mutable Ledger substrate for FactGraph.attach internals."""
        return self._ledger

    def head(self) -> DatabaseValue:
        self._ensure_open()
        value = _read_ledger_head(
            self._ledger,
            expected_schema_digest=self._schema_digest,
            db_id=self._db_id,
        )
        if self._workspace_paths is not None:
            payload = _read_tx_object(self._workspace_paths, value.tx_id)
            if payload["tx_seq"] != value.tx_seq or payload["digest_scheme"] != value.digest_scheme:
                raise DatabaseIntegrityError("head metadata disagrees with the head tx object")
        return value

    def commit_assertions(self, assertions: Sequence[AssertionInput]) -> CommitResult:
        if not assertions:
            raise DatabaseError("commit_assertions requires at least one assertion")
        return self.commit_changes(assertions=assertions, revocations=())

    def commit_changes(
        self,
        assertions: Sequence[AssertionInput],
        revocations: Sequence[RevocationInput],
        meta_appends: Sequence[MetaAppendInput] = (),
        schema_transition: SchemaTransitionInput | None = None,
    ) -> CommitResult:
        self._ensure_open()
        if not assertions and not revocations and not meta_appends and schema_transition is None:
            raise DatabaseError("commit_changes requires at least one change")
        if schema_transition is not None and (assertions or revocations or meta_appends):
            raise DatabaseError("schema_transition must be committed as an isolated change")
        parent = self.head()
        prepared = [self._prepare_assertion(item) for item in assertions]
        added_ids = [record.asrt_id for record, _claim, _args, _meta, _annotations in prepared]
        if len(set(added_ids)) != len(added_ids):
            raise DuplicateAssertionError("duplicate server-generated assertion id in commit")
        for asrt_id in added_ids:
            if self._ledger.get_claim(asrt_id) is not None:
                raise DuplicateAssertionError(f"assertion already exists: {asrt_id}")

        added_assertions = {
            record.asrt_id: record
            for record, _claim, _args, _meta, _annotations in prepared
        }
        prepared_revocations = self._prepare_revocations(
            revocations,
            added_assertions=added_assertions,
        )
        prepared_meta_appends = self._prepare_meta_appends(meta_appends)
        prepared_schema_transition = self._prepare_schema_transition(schema_transition)
        state = decode_state(parent.state_digest)
        operations: list[dict[str, Any]] = []
        for provisional, _claim, _args, _meta, _annotations in prepared:
            state = lthash_add(
                state,
                _state_element(provisional.asrt_id, provisional.assertion_digest),
            )
            operations.append(
                {
                    "kind": "assertion",
                    "asrt_id": provisional.asrt_id,
                    "assertion_digest": provisional.assertion_digest,
                }
            )
        for revocation, _meta_rows, target_assertion_digest in prepared_revocations:
            state = lthash_remove(
                state,
                _state_element(revocation.revoked_asrt_id, target_assertion_digest),
            )
            operations.append(
                {
                    "kind": "revocation",
                    "revoker_asrt_id": revocation.revoker_asrt_id,
                    "revoked_asrt_id": revocation.revoked_asrt_id,
                    "meta": revocation.meta,
                }
            )
        for row in prepared_meta_appends:
            operations.append(
                {
                    "kind": "append_meta",
                    "asrt_id": row.asrt_id,
                    "meta": MetaEntry(row.key, row.kind, row.value),
                }
            )

        commit_schema_digest = self._schema_digest
        next_schema_ir = self._schema_ir
        if prepared_schema_transition is not None:
            old_schema_digest, commit_schema_digest, next_schema_ir = prepared_schema_transition
            operations.append(
                {
                    "kind": "schema_change",
                    "old_schema_digest": old_schema_digest,
                    "new_schema_digest": commit_schema_digest,
                }
            )
        state_digest = encode_state(state)
        tx_seq = parent.tx_seq + 1
        tx_id = _tx_id_for_v2(
            parent_tx_id=parent.tx_id,
            schema_digest=commit_schema_digest,
            digest_scheme=LTHASH_SCHEME,
            tx_seq=tx_seq,
            operations=operations,
        )

        records: list[AssertionRecord] = []
        assertion_writes: list[LedgerAssertionWrite] = []
        for provisional, claim, args, input_meta_rows, annotation_rows in prepared:
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
                MetaRow(
                    asrt_id=record.asrt_id,
                    key="schema_digest",
                    kind="str",
                    value=record.schema_digest,
                ),
                MetaRow(
                    asrt_id=record.asrt_id,
                    key="assertion_digest",
                    kind="str",
                    value=record.assertion_digest,
                ),
                MetaRow(asrt_id=record.asrt_id, key="tx_id", kind="str", value=record.tx_id),
            ]
            assertion_writes.append(
                LedgerAssertionWrite(
                    claim=claim,
                    claim_args=tuple(args),
                    meta_rows=tuple(ledger_meta_rows),
                    annotation_rows=tuple(annotation_rows),
                )
            )
            records.append(record)

        revocation_records: list[RevocationRecord] = []
        revocation_writes: list[LedgerRevocationWrite] = []
        for provisional, input_meta_rows, _target_assertion_digest in prepared_revocations:
            record = RevocationRecord(
                revoker_asrt_id=provisional.revoker_asrt_id,
                revoked_asrt_id=provisional.revoked_asrt_id,
                tx_id=tx_id,
                meta=provisional.meta,
            )
            revocation_writes.append(
                LedgerRevocationWrite(
                    revokes=Revokes(record.revoker_asrt_id, record.revoked_asrt_id),
                    meta_rows=tuple(
                        [
                            *input_meta_rows,
                            MetaRow(
                                record.revoker_asrt_id, "schema_digest", "str", self._schema_digest
                            ),
                            MetaRow(record.revoker_asrt_id, "tx_id", "str", tx_id),
                        ]
                    ),
                    annotation_rows=tuple(_annotation_rows(record.revoker_asrt_id, record.meta)),
                )
            )
            revocation_records.append(record)

        if self._workspace_paths is not None:
            if prepared_schema_transition is not None:
                assert next_schema_ir is not None
                _write_schema_object(
                    self._workspace_paths,
                    schema_digest=commit_schema_digest,
                    schema_bytes=canonicalize_schema_ir_jcs(next_schema_ir),
                )
            _write_tx_object(
                self._workspace_paths,
                tx_id=tx_id,
                parent_tx_id=parent.tx_id,
                schema_digest=commit_schema_digest,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=tx_seq,
                operations=operations,
            )
        try:
            self._ledger.commit_batch(
                assertions=assertion_writes,
                revocations=revocation_writes,
                meta_appends=prepared_meta_appends,
                expected_head_tx_id=parent.tx_id,
                head_tx_id=tx_id,
                metadata=_head_metadata(
                    db_id=self._db_id,
                    schema_digest=commit_schema_digest,
                    state_digest=state_digest,
                    tx_seq=tx_seq,
                ),
            )
        except LedgerHeadConflictError as exc:
            raise HeadConflictError(str(exc)) from exc

        if prepared_schema_transition is not None:
            self._schema_digest = commit_schema_digest
            self._schema_ir = next_schema_ir

        return CommitResult(
            parent_tx_id=parent.tx_id,
            value=DatabaseValue(
                db_id=self._db_id,
                tx_id=tx_id,
                schema_digest=commit_schema_digest,
                state_digest=state_digest,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=tx_seq,
            ),
            assertions=tuple(records),
            revocations=tuple(revocation_records),
        )

    def create_view(
        self,
        name: str,
        asrt_ids: Iterable[str],
        *,
        base: DatabaseValue | None = None,
    ) -> FrozenAssertionSet:
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
        view = FrozenAssertionSet(
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
    ) -> tuple[AssertionRecord, Claim, list[ClaimArg], list[MetaRow], list[AnnotationRow]]:
        if not isinstance(item, AssertionInput):
            raise TypeError("assertions must contain AssertionInput")
        if _is_system_predicate(item.pred_id):
            raise DatabaseError("user assertions cannot use the reserved '__system__.' namespace")
        fact_tuple = _normalize_fact_tuple(item.fact_tuple)
        meta = _normalize_meta_entries(item.meta)
        _reject_reserved_assertion_meta(meta)
        assertion_digest = assertion_digest_for(
            pred_id=item.pred_id,
            fact_tuple=fact_tuple,
            schema_digest=self._schema_digest,
            meta=meta,
        )
        asrt_id = _new_assertion_id()
        e_ref = fact_tuple[0][1]
        rest_terms = list(fact_tuple[1:])
        claim = Claim(asrt_id=asrt_id, pred_id=item.pred_id, e_ref=e_ref, rest_terms=rest_terms)
        claim_arg_rows = claim_args_from_rest_terms(rest_terms)
        args = [
            ClaimArg(asrt_id=asrt_id, idx=idx, val_atom=val_atom, tag=tag)
            for idx, val_atom, tag in claim_arg_rows
        ]
        meta_rows = [
            MetaRow(asrt_id=asrt_id, key=row.key, kind=row.kind, value=row.value) for row in meta
        ]
        provisional = AssertionRecord(
            asrt_id=asrt_id,
            pred_id=item.pred_id,
            fact_tuple=fact_tuple,
            schema_digest=self._schema_digest,
            assertion_digest=assertion_digest,
            tx_id="tx:" + "0" * 64,
            meta=meta,
        )
        return provisional, claim, args, meta_rows, _annotation_rows(asrt_id, meta)

    def _prepare_revocations(
        self,
        items: Sequence[RevocationInput],
        *,
        added_assertions: Mapping[str, AssertionRecord],
    ) -> list[tuple[RevocationRecord, list[MetaRow], str]]:
        prepared: list[tuple[RevocationRecord, list[MetaRow], str]] = []
        targets: set[str] = set()
        for item in items:
            if not isinstance(item, RevocationInput):
                raise TypeError("revocations must contain RevocationInput")
            target = _require_asrt_id(item.revoked_asrt_id, field="revoked_asrt_id")
            if target in targets:
                raise DatabaseError(f"duplicate revocation target in commit: {target}")
            targets.add(target)
            added = added_assertions.get(target)
            if added is not None:
                if _is_system_predicate(added.pred_id):
                    raise DatabaseError("system claims cannot be revoked")
                target_assertion_digest = added.assertion_digest
            else:
                claim = self._ledger.get_claim(target)
                if claim is None:
                    if any(row.revoker_asrt_id == target for row in self._ledger.revokes):
                        raise DatabaseError("revoke-of-revoke is forbidden")
                    raise DatabaseError(f"revocation target does not exist: {target}")
                if _is_system_predicate(claim.pred_id):
                    raise DatabaseError("system claims cannot be revoked")
                if self._ledger.has_active_revocation(target):
                    raise DatabaseError(f"assertion is already revoked: {target}")
                target_assertion_digest = _verified_assertion_digest(self._ledger, claim)
            meta = _normalize_meta_entries(item.meta)
            _reject_reserved_assertion_meta(meta)
            revoker_id = _new_assertion_id()
            provisional = RevocationRecord(
                revoker_asrt_id=revoker_id,
                revoked_asrt_id=target,
                tx_id="tx:" + "0" * 64,
                meta=meta,
            )
            meta_rows = [MetaRow(revoker_id, row.key, row.kind, row.value) for row in meta]
            prepared.append((provisional, meta_rows, target_assertion_digest))
        return prepared

    def _prepare_meta_appends(
        self,
        items: Sequence[MetaAppendInput],
    ) -> list[MetaRow]:
        prepared: list[MetaRow] = []
        for item in items:
            if not isinstance(item, MetaAppendInput):
                raise TypeError("meta_appends must contain MetaAppendInput")
            asrt_id = _require_asrt_id(item.asrt_id, field="meta append asrt_id")
            if not self._ledger._is_known_asrt_id(asrt_id):
                raise DatabaseError(f"meta append target does not exist: {asrt_id}")
            entry = _normalize_meta_entries((MetaEntry(item.key, item.kind, item.value),))[0]
            _meta_value_bytes(entry.kind, entry.value)
            prepared.append(MetaRow(asrt_id, entry.key, entry.kind, entry.value))
        return prepared

    def _prepare_schema_transition(
        self,
        item: SchemaTransitionInput | None,
    ) -> tuple[str, str, dict[str, Any]] | None:
        if item is None:
            return None
        if not isinstance(item, SchemaTransitionInput):
            raise TypeError("schema_transition must be SchemaTransitionInput")
        old_schema_digest = _require_token(
            item.old_schema_digest,
            prefix="sha256:",
            field="old_schema_digest",
        )
        if old_schema_digest != self._schema_digest:
            raise DatabaseError(
                "schema transition old_schema_digest does not match the current Database schema"
            )
        schema_bytes = canonicalize_schema_ir_jcs(item.new_schema_ir)
        new_schema_ir = _schema_ir_from_canonical_bytes(schema_bytes)
        new_schema_digest = compute_schema_digest(new_schema_ir)
        if new_schema_digest == old_schema_digest:
            raise DatabaseError("schema transition must change schema_digest")
        return old_schema_digest, new_schema_digest, new_schema_ir

    def _active_assertion_ids(self) -> set[str]:
        return _active_factual_assertion_ids(self._ledger)

    def _ensure_open(self) -> None:
        if self._closed:
            raise DatabaseError("Database is closed")


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
        lock=db / "writer.lock",
        assertions=db / "assertions.db",
        views=root / "views",
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
    schema_token = compute_schema_digest(schema_ir)
    _validate_schema_object(paths, schema_digest=schema_token, expected_schema_ir=schema_ir)
    return schema_token


def schema_object_exists_for_workspace(path: str | Path, schema_digest: str) -> bool:
    """Return whether a workspace contains the schema object for `schema_digest`."""
    paths = resolve_database_workspace_paths(path)
    return _schema_object_path(paths, schema_digest).exists()


def _is_memory_path(path: str | Path) -> bool:
    return str(path) == ":memory:"


def _is_new_database_workspace(paths: DatabaseWorkspacePaths) -> bool:
    return paths.db_meta.exists() and paths.assertions.exists()


def _ensure_new_database_workspace(paths: DatabaseWorkspacePaths) -> None:
    if paths.root.exists() and not paths.root.is_dir():
        raise DatabaseError("Database workspace path exists and is not a directory")
    if (
        paths.manifest.exists()
        or paths.db_meta.exists()
        or paths.head.exists()
        or paths.assertions.exists()
    ):
        raise DatabaseError("Database workspace already exists at path")
    for directory in (
        paths.root,
        paths.db,
        paths.objects,
        paths.tx_objects,
        paths.schema_objects,
        paths.refs,
    ):
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


def _tx_id_for_v2(
    *,
    parent_tx_id: str | None,
    schema_digest: str,
    digest_scheme: str,
    tx_seq: int,
    operations: Sequence[Mapping[str, Any]],
) -> str:
    return "tx:" + sha256_hex(
        canonical_bytes_dbtx_v2(
            parent_tx_id=parent_tx_id,
            schema_digest=schema_digest,
            digest_scheme=digest_scheme,
            tx_seq=tx_seq,
            operations=operations,
        )
    )


def _write_schema_object(
    paths: DatabaseWorkspacePaths,
    *,
    schema_digest: str,
    schema_bytes: bytes,
) -> None:
    schema_path = _schema_object_path(paths, schema_digest)
    schema_token = _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    schema_ir = _schema_ir_from_canonical_bytes(schema_bytes)
    if canonicalize_schema_ir_jcs(schema_ir) != schema_bytes:
        raise DatabaseError("schema object bytes differ from canonical schema bytes")
    expected_digest = compute_schema_digest(schema_ir)
    if expected_digest != schema_token:
        raise DatabaseError("schema object bytes do not match schema_digest")
    if schema_path.exists():
        stored_schema_ir = _schema_ir_from_canonical_bytes(schema_path.read_bytes())
        if compute_schema_digest(stored_schema_ir) != schema_token:
            raise DatabaseError("schema object filename/content digest mismatch")
        return
    _atomic_write_bytes(schema_path, schema_bytes)


def _write_view_object(paths: DatabaseWorkspacePaths, view: FrozenAssertionSet) -> None:
    expected_digest = view_digest_for(
        db_id=view.db_id,
        base_tx_id=view.base_tx_id,
        schema_digest=view.schema_digest,
        asrt_ids=view.asrt_ids,
    )
    if expected_digest != _require_token(view.view_digest, prefix="sha256:", field="view_digest"):
        raise DatabaseError("view object identity fields do not match view_digest")
    _write_once_bytes(
        _view_object_path(paths, view.view_digest), _json_bytes(_view_object_payload(view))
    )


def _view_object_payload(view: FrozenAssertionSet) -> dict[str, Any]:
    return {
        "asrt_ids": list(view.asrt_ids),
        "base_tx_id": _require_token(view.base_tx_id, prefix="tx:", field="base_tx_id"),
        "db_id": _require_db_id(view.db_id),
        "name": _normalize_view_name(view.name),
        "schema_digest": _require_token(
            view.schema_digest, prefix="sha256:", field="schema_digest"
        ),
        "view_digest": _require_token(view.view_digest, prefix="sha256:", field="view_digest"),
    }


def _validate_schema_object(
    paths: DatabaseWorkspacePaths,
    *,
    schema_digest: str,
    expected_schema_ir: dict[str, Any],
) -> None:
    schema_path = _schema_object_path(paths, schema_digest)
    if not schema_path.exists():
        raise DatabaseError(
            f"schema object missing for schema_digest={schema_digest!r}: {schema_path}"
        )
    actual = schema_path.read_bytes()
    stored_schema_ir = _schema_ir_from_canonical_bytes(actual)
    if canonicalize_schema_ir_jcs(stored_schema_ir) != actual:
        raise DatabaseError("schema object bytes differ from canonical schema bytes")
    expected_token = _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    if compute_schema_digest(stored_schema_ir) != expected_token:
        raise DatabaseError("schema object filename/content digest mismatch")
    expected_schema_ir = ensure_schema_ir(expected_schema_ir)
    if compute_schema_digest(expected_schema_ir) != expected_token:
        raise DatabaseError("expected schema_ir does not match schema_digest")
    if canonicalize_schema_ir_identity_jcs(stored_schema_ir) != canonicalize_schema_ir_identity_jcs(
        expected_schema_ir
    ):
        raise DatabaseError("schema object identity differs from expected schema identity")


def _validate_schema_object_digest(
    paths: DatabaseWorkspacePaths,
    schema_digest: str,
) -> None:
    schema_token = _require_token(
        schema_digest,
        prefix="sha256:",
        field="schema_digest",
    )
    schema_path = _schema_object_path(paths, schema_token)
    if not schema_path.exists():
        raise DatabaseIntegrityError(f"schema object missing: {schema_path}")
    actual = schema_path.read_bytes()
    stored_schema_ir = _schema_ir_from_canonical_bytes(actual)
    if canonicalize_schema_ir_jcs(stored_schema_ir) != actual:
        raise DatabaseIntegrityError("schema object bytes differ from canonical schema bytes")
    if compute_schema_digest(stored_schema_ir) != schema_token:
        raise DatabaseIntegrityError("schema object filename/content digest mismatch")


def _schema_ir_from_canonical_bytes(schema_bytes: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(schema_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatabaseError(f"invalid schema object bytes: {exc}") from exc
    if not isinstance(payload, dict):
        raise DatabaseError("invalid schema object bytes: root must be JSON object")
    try:
        return ensure_schema_ir(payload)
    except SchemaIRValidationError as exc:
        raise DatabaseError(f"invalid schema object bytes: {exc}") from exc


def _write_tx_object(
    paths: DatabaseWorkspacePaths,
    *,
    tx_id: str,
    parent_tx_id: str | None,
    schema_digest: str,
    digest_scheme: str,
    tx_seq: int,
    operations: Sequence[Mapping[str, Any]],
) -> None:
    tx_id = _require_token(tx_id, prefix="tx:", field="tx_id")
    normalized = _normalize_tx_operations(operations)
    expected_tx_id = _tx_id_for_v2(
        parent_tx_id=parent_tx_id,
        schema_digest=schema_digest,
        digest_scheme=digest_scheme,
        tx_seq=tx_seq,
        operations=normalized,
    )
    if expected_tx_id != tx_id:
        raise DatabaseError("tx object identity fields do not match tx_id")
    payload = {
        "digest_scheme": digest_scheme,
        "operations": [_tx_operation_payload(operation) for operation in normalized],
        "parent_tx_id": None
        if parent_tx_id is None
        else _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id"),
        "schema_digest": _require_token(schema_digest, prefix="sha256:", field="schema_digest"),
        "tx_seq": tx_seq,
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
    _require_exact_keys(
        payload,
        {
            "digest_scheme",
            "operations",
            "parent_tx_id",
            "schema_digest",
            "tx_id",
            "tx_seq",
        },
    )
    if payload.get("tx_id") != tx_id:
        raise DatabaseError("tx object filename/content tx_id mismatch")
    parent_tx_id = payload.get("parent_tx_id")
    if parent_tx_id is not None:
        parent_tx_id = _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id")
    schema_token = _require_token(
        payload.get("schema_digest"), prefix="sha256:", field="schema_digest"
    )
    digest_scheme = payload.get("digest_scheme")
    if digest_scheme != LTHASH_SCHEME:
        raise DatabaseError(f"unsupported tx digest_scheme: {digest_scheme!r}")
    tx_seq = payload.get("tx_seq")
    if isinstance(tx_seq, bool) or not isinstance(tx_seq, int) or tx_seq < 0:
        raise DatabaseError("tx object tx_seq must be non-negative int")
    raw_operations = payload.get("operations")
    if not isinstance(raw_operations, list):
        raise DatabaseError("tx object operations must be list")
    operations = _normalize_tx_operations(raw_operations)
    expected_tx_id = _tx_id_for_v2(
        parent_tx_id=parent_tx_id,
        schema_digest=schema_token,
        digest_scheme=digest_scheme,
        tx_seq=tx_seq,
        operations=operations,
    )
    if expected_tx_id != tx_id:
        raise DatabaseError("tx object identity fields do not recompute tx_id")
    payload["parent_tx_id"] = parent_tx_id
    payload["schema_digest"] = schema_token
    payload["digest_scheme"] = digest_scheme
    payload["tx_seq"] = tx_seq
    payload["operations"] = operations
    return payload


def _write_database_meta(paths: DatabaseWorkspacePaths, *, db_id: str) -> None:
    created_at = time.time_ns()
    payload = {
        "created_at_epoch_ns": created_at,
        "database_workspace_version": _DATABASE_WORKSPACE_VERSION,
        "db_id": _require_db_id(db_id),
        "last_saved_at_epoch_ns": created_at,
    }
    _write_once_bytes(paths.db_meta, _json_bytes(payload))


def _read_database_meta(paths: DatabaseWorkspacePaths) -> dict[str, Any]:
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
    for key in ("created_at_epoch_ns", "last_saved_at_epoch_ns"):
        value = payload.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise DatabaseError(f"Database meta.json {key} must be non-negative int")
    return dict(payload)


def _write_workspace_manifest(paths: DatabaseWorkspacePaths) -> None:
    components = {
        "db": "db/",
        "views": "views/",
    }
    payload = {
        "components": components,
        "factgraph_workspace_version": _DATABASE_WORKSPACE_VERSION,
    }
    _atomic_write_bytes(paths.manifest, _json_bytes(payload))


def _head_metadata(
    *,
    db_id: str,
    schema_digest: str,
    state_digest: str,
    tx_seq: int,
) -> dict[str, str]:
    decode_state(state_digest)
    if isinstance(tx_seq, bool) or not isinstance(tx_seq, int) or tx_seq < 0:
        raise DatabaseError("tx_seq must be non-negative int")
    return {
        "db_id": _require_db_id(db_id),
        "schema_digest": _require_token(schema_digest, prefix="sha256:", field="schema_digest"),
        "head_state_digest": state_digest,
        "digest_scheme": LTHASH_SCHEME,
        "head_tx_seq": str(tx_seq),
    }


def _read_ledger_head(
    ledger: Ledger,
    *,
    expected_schema_digest: str,
    db_id: str,
) -> DatabaseValue:
    keys = (
        "db_id",
        "schema_digest",
        "head_tx_id",
        "head_state_digest",
        "digest_scheme",
        "head_tx_seq",
    )
    meta = ledger.get_ledger_meta_snapshot(keys)
    missing = [key for key in keys if meta[key] is None]
    if missing:
        raise DatabaseIntegrityError(f"Database head metadata missing: {', '.join(missing)}")
    if meta["db_id"] != _require_db_id(db_id):
        raise DatabaseIntegrityError("ledger_meta db_id mismatch")
    schema_token = _require_token(
        str(meta["schema_digest"]),
        prefix="sha256:",
        field="schema_digest",
    )
    if schema_token != _require_token(
        expected_schema_digest,
        prefix="sha256:",
        field="expected_schema_digest",
    ):
        raise DatabaseIntegrityError("ledger_meta schema_digest mismatch")
    if meta["digest_scheme"] != LTHASH_SCHEME:
        raise DatabaseIntegrityError(f"unsupported digest_scheme: {meta['digest_scheme']!r}")
    state_digest = str(meta["head_state_digest"])
    try:
        decode_state(state_digest)
    except LtHashError as exc:
        raise DatabaseIntegrityError(f"invalid head_state_digest: {exc}") from exc
    raw_seq = str(meta["head_tx_seq"])
    try:
        tx_seq = int(raw_seq)
    except ValueError as exc:
        raise DatabaseIntegrityError("head_tx_seq must be a non-negative integer") from exc
    if tx_seq < 0 or str(tx_seq) != raw_seq:
        raise DatabaseIntegrityError("head_tx_seq must use canonical decimal encoding")
    return DatabaseValue(
        db_id=_require_db_id(db_id),
        tx_id=_require_token(str(meta["head_tx_id"]), prefix="tx:", field="head_tx_id"),
        schema_digest=schema_token,
        state_digest=state_digest,
        digest_scheme=LTHASH_SCHEME,
        tx_seq=tx_seq,
    )


def _validate_workspace_integrity(
    paths: DatabaseWorkspacePaths,
    *,
    ledger: Ledger,
    expected_schema_digest: str,
    db_id: str,
) -> DatabaseValue:
    head = _read_ledger_head(
        ledger,
        expected_schema_digest=expected_schema_digest,
        db_id=db_id,
    )
    payload = _read_tx_object(paths, head.tx_id)
    if payload["schema_digest"] != head.schema_digest:
        raise DatabaseIntegrityError("head tx object schema_digest mismatch")
    if payload["digest_scheme"] != head.digest_scheme or payload["tx_seq"] != head.tx_seq:
        raise DatabaseIntegrityError("head tx object disagrees with ledger_meta")
    history_ids = _replay_history(
        paths,
        head_tx_id=head.tx_id,
        expected_schema_digest=head.schema_digest,
    )
    ledger_assertions = _active_factual_assertions(ledger)
    ledger_ids = set(ledger_assertions)
    if history_ids != ledger_ids:
        raise DatabaseIntegrityError("tx history terminal set does not match ledger data")
    computed = _state_digest_for_assertions(ledger_assertions)
    if computed != head.state_digest:
        raise DatabaseIntegrityError("head_state_digest does not match active factual data")
    return head


def _replay_history(
    paths: DatabaseWorkspacePaths,
    *,
    head_tx_id: str,
    expected_schema_digest: str,
) -> set[str]:
    chain: list[dict[str, Any]] = []
    seen_tx_ids: set[str] = set()
    cursor: str | None = _require_token(head_tx_id, prefix="tx:", field="head_tx_id")
    while cursor is not None:
        if cursor in seen_tx_ids:
            raise DatabaseIntegrityError("tx history contains a cycle")
        seen_tx_ids.add(cursor)
        payload = _read_tx_object(paths, cursor)
        chain.append(payload)
        cursor = payload["parent_tx_id"]
    chain.reverse()
    active: set[str] = set()
    known_asrt_ids: set[str] = set()
    effective_schema_digest: str | None = None
    for expected_seq, payload in enumerate(chain):
        if payload["tx_seq"] != expected_seq:
            raise DatabaseIntegrityError("tx history sequence is not contiguous from genesis")
        if expected_seq == 0 and payload["parent_tx_id"] is not None:
            raise DatabaseIntegrityError("genesis tx must not have a parent")
        schema_operations = [
            operation
            for operation in payload["operations"]
            if operation["kind"] == "schema_change"
        ]
        if expected_seq == 0:
            if schema_operations:
                raise DatabaseIntegrityError("genesis tx cannot contain schema_change")
            effective_schema_digest = payload["schema_digest"]
            _validate_schema_object_digest(paths, effective_schema_digest)
        elif schema_operations:
            if len(schema_operations) != 1 or len(payload["operations"]) != 1:
                raise DatabaseIntegrityError("schema_change must be an isolated tx operation")
            operation = schema_operations[0]
            if operation["old_schema_digest"] != effective_schema_digest:
                raise DatabaseIntegrityError("schema_change old digest breaks transition continuity")
            if operation["new_schema_digest"] != payload["schema_digest"]:
                raise DatabaseIntegrityError("schema_change new digest disagrees with tx schema_digest")
            _validate_schema_object_digest(paths, operation["new_schema_digest"])
            effective_schema_digest = operation["new_schema_digest"]
        elif payload["schema_digest"] != effective_schema_digest:
            raise DatabaseIntegrityError("tx history schema_digest changed without schema_change")
        for operation in payload["operations"]:
            kind = operation["kind"]
            if kind == "assertion":
                asrt_id = operation["asrt_id"]
                if asrt_id in known_asrt_ids:
                    raise DatabaseIntegrityError(f"assertion id repeated in history: {asrt_id}")
                known_asrt_ids.add(asrt_id)
                active.add(asrt_id)
            elif kind == "revocation":
                target = operation["revoked_asrt_id"]
                if target not in active:
                    raise DatabaseIntegrityError(
                        f"revocation target is not active in history: {target}"
                    )
                active.remove(target)
                revoker_asrt_id = operation["revoker_asrt_id"]
                if revoker_asrt_id in known_asrt_ids:
                    raise DatabaseIntegrityError(
                        f"revoker assertion id repeated in history: {revoker_asrt_id}"
                    )
                known_asrt_ids.add(revoker_asrt_id)
            elif kind == "append_meta":
                if operation["asrt_id"] not in known_asrt_ids:
                    raise DatabaseIntegrityError(
                        f"append_meta target is not present in history: {operation['asrt_id']}"
                    )
            elif kind == "schema_change":
                continue
            elif kind == "repair_add":
                active.add(operation["asrt_id"])
                known_asrt_ids.add(operation["asrt_id"])
            elif kind == "repair_remove":
                active.discard(operation["asrt_id"])
            elif kind == "repair":
                continue
    if effective_schema_digest != _require_token(
        expected_schema_digest,
        prefix="sha256:",
        field="expected_schema_digest",
    ):
        raise DatabaseIntegrityError("tx history terminal schema_digest mismatch")
    return active


def _active_factual_assertion_ids(ledger: Ledger) -> set[str]:
    return set(_active_factual_assertions(ledger))


def _is_system_predicate(pred_id: str) -> bool:
    """Return the INV-13/INV-15 reserved-namespace predicate."""
    return isinstance(pred_id, str) and pred_id.startswith("__system__.")


def _verified_assertion_digest(ledger: Ledger, claim: Claim) -> str:
    """Read and verify the content digest persisted with one factual claim."""
    rows = ledger.find_meta(asrt_id=claim.asrt_id)
    digest_rows = [row for row in rows if row.key == "assertion_digest" and row.kind == "str"]
    schema_rows = [row for row in rows if row.key == "schema_digest" and row.kind == "str"]
    tx_rows = [row for row in rows if row.key == "tx_id" and row.kind == "str"]
    if len(digest_rows) != 1 or len(schema_rows) != 1 or len(tx_rows) != 1:
        raise DatabaseIntegrityError(
            f"assertion {claim.asrt_id} must have exactly one assertion_digest, "
            "schema_digest and tx_id metadata row"
        )
    try:
        stored_digest = _require_token(
            digest_rows[0].value,
            prefix="sha256:",
            field="assertion_digest",
        )
        schema_digest = _require_token(
            schema_rows[0].value,
            prefix="sha256:",
            field="schema_digest",
        )
        _require_token(tx_rows[0].value, prefix="tx:", field="tx_id")
        tx_row_index = rows.index(tx_rows[0])
        if rows.index(digest_rows[0]) >= tx_row_index or rows.index(schema_rows[0]) >= tx_row_index:
            raise DatabaseError("reserved assertion identity metadata is out of order")
        # Initial assertion meta is inserted before the reserved tx_id marker.
        # Later append_meta history is deliberately outside state_digest per
        # Q-SAE-7 and therefore must not alter the assertion content digest.
        user_meta = _normalize_meta_entries(
            tuple(
                row for row in rows[:tx_row_index] if row.key not in _RESERVED_ASSERTION_META_KEYS
            )
        )
        recomputed = assertion_digest_for(
            pred_id=claim.pred_id,
            fact_tuple=(("entity_ref", claim.e_ref), *tuple(claim.rest_terms)),
            schema_digest=schema_digest,
            meta=user_meta,
        )
    except DatabaseError as exc:
        raise DatabaseIntegrityError(
            f"assertion {claim.asrt_id} has malformed identity metadata"
        ) from exc
    if recomputed != stored_digest:
        raise DatabaseIntegrityError(
            f"assertion_digest does not match factual content for {claim.asrt_id}"
        )
    return stored_digest


def _active_factual_assertions(ledger: Ledger) -> dict[str, str]:
    active: dict[str, str] = {}
    for claim in ledger.find_claims():
        if _is_system_predicate(claim.pred_id) or ledger.has_active_revocation(claim.asrt_id):
            continue
        asrt_id = _require_asrt_id(claim.asrt_id, field="asrt_id")
        active[asrt_id] = _verified_assertion_digest(ledger, claim)
    return active


def _state_digest_for_assertions(assertions: Mapping[str, str]) -> str:
    normalized = sorted(
        (
            _require_asrt_id(asrt_id, field="asrt_id"),
            _require_token(digest, prefix="sha256:", field="assertion_digest"),
        )
        for asrt_id, digest in assertions.items()
    )
    return encode_state(
        lthash_from_elements(
            _state_element(asrt_id, assertion_digest) for asrt_id, assertion_digest in normalized
        )
    )


def _state_element(asrt_id: str, assertion_digest: str) -> bytes:
    normalized_id = _require_asrt_id(asrt_id, field="asrt_id")
    normalized_digest = _require_token(
        assertion_digest,
        prefix="sha256:",
        field="assertion_digest",
    )
    return DBSTATE_ELEMENT_V2_PREFIX + _str_field(normalized_id) + _str_field(normalized_digest)


def _acquire_workspace_lock(paths: DatabaseWorkspacePaths) -> IO[bytes]:
    paths.lock.parent.mkdir(parents=True, exist_ok=True)
    handle = paths.lock.open("a+b")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise DatabaseLockedError(
            f"Database workspace is already open for writing: {paths.root}"
        ) from exc
    return handle


def _release_workspace_lock(handle: IO[bytes]) -> None:
    with _suppress_os_error():
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    with _suppress_os_error():
        handle.close()


def _tx_object_path(paths: DatabaseWorkspacePaths, tx_id: str) -> Path:
    return paths.tx_objects / f"{_token_hex(tx_id, prefix='tx:', field='tx_id')}.json"


def _schema_object_path(paths: DatabaseWorkspacePaths, schema_digest: str) -> Path:
    return (
        paths.schema_objects
        / f"{_token_hex(schema_digest, prefix='sha256:', field='schema_digest')}.json"
    )


def _view_object_path(paths: DatabaseWorkspacePaths, view_digest: str) -> Path:
    return (
        paths.views
        / "objects"
        / f"{_token_hex(view_digest, prefix='sha256:', field='view_digest')}.json"
    )


def _token_hex(value: str, *, prefix: str, field: str) -> str:
    return _require_token(value, prefix=prefix, field=field).removeprefix(prefix)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


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
            try:
                os.fsync(fh.fileno())
            except OSError as exc:
                raise DatabaseError(f"fsync failed for object file: {tmp}") from exc
        os.replace(tmp, path)
        _fsync_parent(path)
    finally:
        if tmp.exists():
            with _suppress_os_error():
                tmp.unlink()


def _fsync_parent(path: Path) -> None:
    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError as exc:
        raise DatabaseError(f"cannot open object directory for fsync: {path.parent}") from exc
    try:
        try:
            os.fsync(fd)
        except OSError as exc:
            raise DatabaseError(f"directory fsync failed: {path.parent}") from exc
    finally:
        os.close(fd)


class _suppress_os_error:
    def __enter__(self) -> None:
        return None

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> bool:
        return exc_type is not None and issubclass(exc_type, OSError)


def _u32be(number: int) -> bytes:
    if number < 0:
        raise DatabaseError("negative length")
    return number.to_bytes(4, "big", signed=False)


def _u64be(number: int) -> bytes:
    if number < 0 or number >= 1 << 64:
        raise DatabaseError("integer is out of uint64 range")
    return number.to_bytes(8, "big", signed=False)


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


def _new_assertion_id() -> str:
    return f"asrt:{uuid.uuid4().hex}"


def _require_asrt_id(value: str, *, field: str) -> str:
    if not isinstance(value, str):
        raise DatabaseError(f"{field} must be string")
    suffix = value.removeprefix("asrt:") if value.startswith("asrt:") else value
    if len(suffix) not in {32, 64} or any(ch not in "0123456789abcdef" for ch in suffix):
        raise DatabaseError(
            f"{field} must be UUID hex or 'asrt:' plus 32 or 64 lowercase hex chars"
        )
    return value


def _normalize_tx_operations(
    operations: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for raw in operations:
        if not isinstance(raw, Mapping):
            raise DatabaseError("tx operations must be mappings")
        kind = raw.get("kind")
        if kind == "assertion":
            _require_exact_keys(raw, {"kind", "asrt_id", "assertion_digest"})
            normalized.append(
                {
                    "kind": kind,
                    "asrt_id": _require_asrt_id(raw.get("asrt_id"), field="asrt_id"),
                    "assertion_digest": _require_token(
                        raw.get("assertion_digest"),
                        prefix="sha256:",
                        field="assertion_digest",
                    ),
                }
            )
        elif kind == "revocation":
            _require_exact_keys(raw, {"kind", "revoker_asrt_id", "revoked_asrt_id", "meta"})
            raw_meta = raw.get("meta")
            if not isinstance(raw_meta, (list, tuple)):
                raise DatabaseError("revocation operation meta must be a sequence")
            meta_entries: list[MetaEntry] = []
            for entry in raw_meta:
                if isinstance(entry, MetaEntry):
                    meta_entries.append(entry)
                    continue
                if not isinstance(entry, Mapping):
                    raise DatabaseError("tx operation meta entries must be mappings")
                _require_exact_keys(entry, {"key", "kind", "value"})
                meta_entries.append(
                    MetaEntry(
                        entry.get("key"),
                        entry.get("kind"),
                        _from_jsonable(entry.get("value")),
                    )
                )
            normalized.append(
                {
                    "kind": kind,
                    "revoker_asrt_id": _require_asrt_id(
                        raw.get("revoker_asrt_id"),
                        field="revoker_asrt_id",
                    ),
                    "revoked_asrt_id": _require_asrt_id(
                        raw.get("revoked_asrt_id"),
                        field="revoked_asrt_id",
                    ),
                    "meta": _normalize_meta_entries(tuple(meta_entries)),
                }
            )
        elif kind == "append_meta":
            _require_exact_keys(raw, {"kind", "asrt_id", "meta"})
            raw_meta = raw.get("meta")
            if isinstance(raw_meta, MetaEntry):
                meta = raw_meta
            elif isinstance(raw_meta, Mapping):
                _require_exact_keys(raw_meta, {"key", "kind", "value"})
                meta = MetaEntry(
                    raw_meta.get("key"),
                    raw_meta.get("kind"),
                    _from_jsonable(raw_meta.get("value")),
                )
            else:
                raise DatabaseError("append_meta operation meta must be MetaEntry or mapping")
            normalized_meta = _normalize_meta_entries((meta,))[0]
            _meta_value_bytes(normalized_meta.kind, normalized_meta.value)
            normalized.append(
                {
                    "kind": kind,
                    "asrt_id": _require_asrt_id(raw.get("asrt_id"), field="append_meta asrt_id"),
                    "meta": normalized_meta,
                }
            )
        elif kind == "schema_change":
            _require_exact_keys(
                raw,
                {"kind", "old_schema_digest", "new_schema_digest"},
            )
            old_schema_digest = _require_token(
                raw.get("old_schema_digest"),
                prefix="sha256:",
                field="old_schema_digest",
            )
            new_schema_digest = _require_token(
                raw.get("new_schema_digest"),
                prefix="sha256:",
                field="new_schema_digest",
            )
            if old_schema_digest == new_schema_digest:
                raise DatabaseError("schema_change must change schema_digest")
            normalized.append(
                {
                    "kind": kind,
                    "old_schema_digest": old_schema_digest,
                    "new_schema_digest": new_schema_digest,
                }
            )
        elif kind in {"repair_add", "repair_remove"}:
            _require_exact_keys(raw, {"kind", "asrt_id"})
            normalized.append(
                {
                    "kind": kind,
                    "asrt_id": _require_asrt_id(raw.get("asrt_id"), field="repair asrt_id"),
                }
            )
        elif kind == "repair":
            _require_exact_keys(
                raw,
                {"kind", "previous_state_digest", "rebuilt_state_digest", "reason"},
            )
            previous = raw.get("previous_state_digest")
            rebuilt = raw.get("rebuilt_state_digest")
            reason = raw.get("reason")
            if not isinstance(previous, str) or not previous:
                raise DatabaseError("repair previous_state_digest must be non-empty string")
            if not isinstance(rebuilt, str):
                raise DatabaseError("repair rebuilt_state_digest must be string")
            decode_state(rebuilt)
            if not isinstance(reason, str) or not reason:
                raise DatabaseError("repair reason must be non-empty string")
            normalized.append(
                {
                    "kind": kind,
                    "previous_state_digest": previous,
                    "rebuilt_state_digest": rebuilt,
                    "reason": reason,
                }
            )
        else:
            raise DatabaseError(f"unsupported tx operation kind: {kind!r}")
    return tuple(normalized)


def _tx_operation_payload(operation: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _normalize_tx_operations((operation,))[0]
    if normalized["kind"] not in {"revocation", "append_meta"}:
        return dict(normalized)
    if normalized["kind"] == "append_meta":
        row = normalized["meta"]
        return {
            "kind": "append_meta",
            "asrt_id": normalized["asrt_id"],
            "meta": {"key": row.key, "kind": row.kind, "value": _to_jsonable(row.value)},
        }
    return {
        **normalized,
        "meta": [
            {"key": row.key, "kind": row.kind, "value": _to_jsonable(row.value)}
            for row in normalized["meta"]
        ],
    }


def _require_exact_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise DatabaseError(
            f"unexpected tx operation fields: expected {sorted(expected)}, got {sorted(value)}"
        )


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
    return tuple(sorted({_require_asrt_id(value, field="view asrt_id") for value in items}))


def _normalize_meta_entries(
    rows: Sequence[MetaEntry | MetaRow | tuple[str, str, Any]],
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


def _annotation_rows(asrt_id: str, meta: Sequence[MetaEntry]) -> list[AnnotationRow]:
    rows: list[AnnotationRow] = []
    for entry in meta:
        annotation = SHARED_ANNOTATION_KEYS.get(entry.key)
        if annotation is None:
            continue
        category, origin = annotation
        rows.append(
            AnnotationRow(
                asrt_id=asrt_id,
                namespace="shared",
                category=category,
                key=entry.key,
                kind=entry.kind,
                value=entry.value,
                origin=origin,
            )
        )
    return rows


def _reject_reserved_assertion_meta(rows: Sequence[MetaEntry]) -> None:
    reserved = sorted({row.key for row in rows} & _RESERVED_ASSERTION_META_KEYS)
    if reserved:
        raise DatabaseError(
            "assertion/revocation meta cannot use Database-reserved key(s): " + ", ".join(reserved)
        )


def _canonical_meta_entries_bytes(rows: Sequence[MetaEntry]) -> bytes:
    encoded = [(row.key, row.kind, _meta_value_bytes(row.kind, row.value)) for row in rows]
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


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {_JSON_BYTES_KEY} and isinstance(value[_JSON_BYTES_KEY], str):
            return base64.b64decode(value[_JSON_BYTES_KEY].encode("ascii"))
        return {str(key): _from_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_jsonable(item) for item in value]
    return value


__all__ = [
    "ASSERTION_V1_PREFIX",
    "DBDATA_V1_PREFIX",
    "DBTX_V1_PREFIX",
    "DBTX_V2_PREFIX",
    "VIEW_V1_PREFIX",
    "AssertionInput",
    "AssertionRecord",
    "CommitResult",
    "Database",
    "DatabaseError",
    "DatabaseIntegrityError",
    "DatabaseLockedError",
    "DatabaseValue",
    "DatabaseWorkspacePaths",
    "DuplicateAssertionError",
    "FrozenAssertionSet",
    "HeadConflictError",
    "MetaEntry",
    "MetaAppendInput",
    "RevocationInput",
    "RevocationRecord",
    "SchemaTransitionInput",
    "asrt_id_for",
    "assertion_digest_for",
    "canonical_bytes_assertion_v1",
    "canonical_bytes_dbdata_v1",
    "canonical_bytes_dbtx_v1",
    "canonical_bytes_dbtx_v2",
    "canonical_bytes_view_v1",
    "resolve_database_workspace_paths",
    "schema_object_exists_for_workspace",
    "validate_schema_object_for_workspace",
    "view_digest_for",
    "write_schema_object_for_workspace",
]
