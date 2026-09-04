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
import shlex
import sqlite3
import struct
import time
import uuid
import weakref
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from factgraph.core.evidence.write_protocol import _SYSTEM_MANAGED_META_KEYS
from factgraph.core.protocol.annotation_v1 import initial_meta_annotation_v1
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.lthash import (
    LTHASH_SCHEME,
    LtHashError,
    decode_state,
    empty_state,
    encode_state,
)
from factgraph.core.protocol.lthash import (
    add as lthash_add,
)
from factgraph.core.protocol.lthash import (
    from_elements as lthash_from_elements,
)
from factgraph.core.protocol.lthash import (
    remove as lthash_remove,
)
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.schema.meta_policy import (
    MetaKeyPolicyError,
    lazy_meta_keys,
    require_tx_liftable_meta_key,
)
from factgraph.core.schema.schema_ir import (
    SchemaIRValidationError,
    canonicalize_schema_ir_identity_jcs,
    canonicalize_schema_ir_jcs,
    ensure_schema_ir,
)
from factgraph.core.schema.schema_ir import (
    schema_digest as compute_schema_digest,
)
from factgraph.core.store.ledger import (
    _ANNOTATION_COMPAT_PREFIX,
    META_KINDS,
    AnnotationRow,
    Claim,
    ClaimArg,
    Ledger,
    LedgerAssertionWrite,
    LedgerHeadConflictError,
    LedgerRevocationWrite,
    MetaRow,
    Revokes,
    TxMetaDefault,
    _annotation_compatibility_meta_rows,
    _annotation_from_storage_key,
    _AnnotationStorageMetaRow,
    _dec,
    _dec_rest_terms,
    _decode_claim_terms,
    _decode_meta_value,
    _is_reserved_annotation_meta_key,
    _MetaTombstone,
)

DBTX_V1_PREFIX = b"factpy\x00dbtx_v1\x00"
DBTX_V2_PREFIX = b"factgraph\x00dbtx_v2\x00"
DBTX_V2_META_DEFAULTS_SUFFIX = b"\x00factgraph\x00tx_meta_defaults_v1\x00"
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
    """One typed metadata key/value included in a canonical write."""

    key: str
    kind: str
    value: Any


@dataclass(frozen=True)
class AssertionInput:
    """Canonical assertion payload accepted by ``Database.commit_*``."""

    pred_id: str
    fact_tuple: tuple[tuple[str, Any], ...]
    meta: tuple[MetaEntry, ...] = ()


@dataclass(frozen=True)
class RevocationInput:
    """Canonical request to revoke one existing assertion."""

    revoked_asrt_id: str
    meta: tuple[MetaEntry, ...] = ()


@dataclass(frozen=True)
class MetaAppendInput:
    """Canonical metadata append request for one assertion."""

    asrt_id: str
    key: str
    kind: str
    value: Any


@dataclass(frozen=True)
class _MetaUnsetInput:
    """Private explicit-UNSET command; generic meta inputs remain non-null."""

    asrt_id: str
    key: str


@dataclass(frozen=True)
class _AnnotationMetaAppendInput(MetaAppendInput):
    """Private input allowed to carry the reserved annotation storage key."""


@dataclass(frozen=True)
class _UnsetMetaEntry:
    key: str
    kind: None = None
    value: None = None


@dataclass(frozen=True)
class _LegacyLedgerRows:
    claims: tuple[Claim, ...]
    meta_rows: tuple[MetaRow, ...]
    annotation_rows: tuple[AnnotationRow, ...]
    revocations: tuple[Revokes, ...]


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
    """Committed transaction result with the new head and written records."""

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
    meta_defaults: Sequence[MetaEntry | Mapping[str, Any]] = (),
) -> bytes:
    """Canonical history commitment over one ordered commit delta.

    ``dbtx_v2`` operation tags are additive: ``A`` assertion, ``R``
    revocation, ``M`` append-meta, ``S`` schema-change, and the existing repair
    tags. Orthogonal tx defaults use a separate domain-delimited suffix, absent
    when empty, so they never consume claim-event op ordinals. Readers must
    continue accepting tx objects written before later tags were introduced.
    """
    if parent_tx_id is not None:
        _require_token(parent_tx_id, prefix="tx:", field="parent_tx_id")
    _require_token(schema_digest, prefix="sha256:", field="schema_digest")
    if digest_scheme != LTHASH_SCHEME:
        raise DatabaseError(f"unsupported digest_scheme: {digest_scheme!r}")
    if isinstance(tx_seq, bool) or not isinstance(tx_seq, int) or tx_seq < 0:
        raise DatabaseError("tx_seq must be non-negative int")
    normalized = _normalize_tx_operations(operations)
    normalized_defaults = _normalize_tx_meta_defaults(meta_defaults)

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
    if normalized_defaults:
        out.extend(DBTX_V2_META_DEFAULTS_SUFFIX)
        out.extend(_canonical_meta_entries_bytes(normalized_defaults))
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
                "migrate its closed v0.2 workspace with "
                "`python -m factgraph migrate-workspace <workspace>`"
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
        if schema_ir is not None:
            self._ledger.configure_meta_load_policy(lazy_meta_keys(schema_ir))
        if workspace_paths is not None:
            head_tx_id = self._ledger.get_ledger_meta("head_tx_id")
            if head_tx_id is None:
                raise DatabaseIntegrityError(
                    "cannot build tx meta-default index without head_tx_id"
                )
            self._ledger.replace_tx_meta_defaults(
                _tx_meta_defaults_from_history(workspace_paths, head_tx_id=head_tx_id)
            )
        owner_ref = weakref.ref(self)

        def _managed_meta_writer(rows: Sequence[MetaRow]) -> CommitResult | None:
            owner = owner_ref()
            if owner is None or owner._closed:
                raise DatabaseError("managed meta writer belongs to a closed Database")
            return owner._commit_meta_rows(rows)

        def _managed_annotation_writer(
            rows: Sequence[AnnotationRow],
        ) -> CommitResult | None:
            owner = owner_ref()
            if owner is None or owner._closed:
                raise DatabaseError("managed annotation writer belongs to a closed Database")
            return owner._commit_annotations(rows)

        # Weak-owner callbacks keep Ledger writes routed through Database
        # without forming Database -> Ledger -> bound-method -> Database cycles.
        # Such a cycle can defer writer.lock cleanup until an unrelated GC.
        self._managed_meta_writer_callback = _managed_meta_writer
        self._managed_annotation_writer_callback = _managed_annotation_writer
        self._ledger._managed_meta_writer = _managed_meta_writer
        self._ledger._managed_annotation_writer = _managed_annotation_writer

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:  # noqa: BLE001 - __del__ finalizer must not raise during interpreter teardown; close() faults stay visible to explicit close()/context-manager use.
            return

    def close(self) -> None:
        """Close the Database and release its durable workspace lock.

        Notes:
            Closing is idempotent. A ``FactGraph`` created with
            ``FactGraph.attach(db, ...)`` does not own this Database; the
            caller must close it or use ``Database`` as a context manager.
        """
        if getattr(self, "_closed", True):
            return
        self._closed = True
        if self._ledger._managed_meta_writer is self._managed_meta_writer_callback:
            self._ledger._managed_meta_writer = None
        if self._ledger._managed_annotation_writer is self._managed_annotation_writer_callback:
            self._ledger._managed_annotation_writer = None
        try:
            self._ledger.close()
        finally:
            if self._lock_handle is not None:
                _release_workspace_lock(self._lock_handle)
                self._lock_handle = None

    @classmethod
    def create(cls, path: str | Path = ":memory:", *, schema_ir: dict[str, Any]) -> Database:
        """Create a new in-memory or durable Database.

        Args:
            path: ``":memory:"`` or a new workspace directory.
            schema_ir: Canonical schema IR for the Database.

        Returns:
            An open Database owning its Ledger and workspace lock.

        Raises:
            DatabaseError: If the schema or destination is invalid.
        """
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
        """Open an existing durable Database workspace.

        Args:
            path: Existing v0.3 Database workspace directory.
            schema_ir: Canonical schema IR expected by the workspace.

        Returns:
            An open Database holding the exclusive writer lock.

        Raises:
            DatabaseError: If the workspace, schema, or format is invalid.
        """
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
        if not paths.root.exists():
            raise DatabaseError(
                f"Database workspace not found: {paths.root}; "
                "create it with Database.create(...)"
            )
        if not paths.root.is_dir():
            raise DatabaseError(
                f"Database workspace path is not a directory: {paths.root}; "
                "migrate a closed v0.2 workspace directory with "
                "`python -m factgraph migrate-workspace <workspace>`"
            )
        if (paths.root / "ledger.db").is_file():
            raise DatabaseError(
                "legacy v0.2 workspace is not writable; run "
                f"`{_migrate_workspace_command(paths.root)}`"
            )
        raise DatabaseError(
            "incomplete Database workspace; recreate it with Database.create(...). "
            "The migration command is only for a complete v0.2 workspace: "
            f"`{_migrate_workspace_command(paths.root)}`"
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
                    f"Database digest_scheme {stored_scheme!r} is unsupported; "
                    "this db/ workspace needs an explicit format migration"
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
        """Rebuild state from ledger data and append an explicit repair event.

        Args:
            path: Durable Database workspace to repair.
            schema_ir: Canonical schema expected by the workspace.
            reason: Non-empty operator reason recorded in the repair event.

        Returns:
            The repaired open Database.

        Raises:
            DatabaseError: If the workspace, schema, reason, or integrity state
                cannot be repaired safely.
        """
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
                    f"Database digest_scheme {stored_scheme!r} is unsupported; "
                    "this db/ workspace needs an explicit format migration"
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
        """Return the stable Database identity token."""
        return self._db_id

    @property
    def schema_digest(self) -> str:
        """Return the schema digest pinned by this Database."""
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
        explicit genesis import transaction made of standard assertion,
        revocation, and append-meta operations.
        """
        source = Path(source_ledger_path)
        target = Path(target_workspace)
        if not source.is_file():
            raise DatabaseError(f"legacy ledger component missing: {source}")
        if source.resolve(strict=False) == (
            resolve_database_workspace_paths(target).assertions.resolve(strict=False)
        ):
            raise DatabaseError("legacy migration source and target ledger must differ")

        legacy_rows = _read_legacy_ledger_rows(source)
        schema_token = compute_schema_digest(schema_ir)
        created = cls.create(target, schema_ir=schema_ir)
        created.close()
        paths = resolve_database_workspace_paths(target)
        try:
            target_conn = sqlite3.connect(str(paths.assertions))
            try:
                target_conn.execute("BEGIN IMMEDIATE")
                try:
                    target_conn.execute("DELETE FROM claims")
                    target_conn.execute("DELETE FROM claim_meta")
                    target_conn.execute(
                        "DELETE FROM ledger_meta WHERE key <> 'ledger_format_version'"
                    )
                    target_conn.execute("COMMIT")
                except BaseException:
                    if target_conn.in_transaction:
                        target_conn.execute("ROLLBACK")
                    raise
            finally:
                target_conn.close()
        except sqlite3.Error as exc:
            raise DatabaseError(f"failed to initialize migration target: {exc}") from exc

        for orphan in paths.tx_objects.glob("*.json"):
            orphan.unlink()

        db_id = _require_db_id(_read_database_meta(paths)["db_id"])
        ledger = Ledger(path=paths.assertions)
        try:
            assertion_digests: dict[str, str] = {}
            meta_rows_by_asrt_id: dict[str, list[MetaRow]] = {}
            for row in legacy_rows.meta_rows:
                meta_rows_by_asrt_id.setdefault(row.asrt_id, []).append(row)
            for claim in legacy_rows.claims:
                asrt_id = _require_asrt_id(claim.asrt_id, field="legacy asrt_id")
                rows = meta_rows_by_asrt_id.get(asrt_id, [])
                if any(row.key in _RESERVED_ASSERTION_META_KEYS for row in rows):
                    raise DatabaseError(
                        f"legacy assertion already carries v0.3 reserved metadata: {asrt_id}"
                    )
                digest = assertion_digest_for(
                    pred_id=claim.pred_id,
                    fact_tuple=(("entity_ref", claim.e_ref), *tuple(claim.rest_terms)),
                    schema_digest=schema_token,
                    # v0.2 had no creation-vs-append event boundary.  Import
                    # every legacy meta row as an explicit M event below so
                    # repeated keys remain ordered and chain-reconstructible.
                    meta=(),
                )
                assertion_digests[asrt_id] = digest

            revoked_assertion_ids = {
                row.revoked_asrt_id for row in legacy_rows.revocations
            }
            active_assertions = {
                asrt_id: digest
                for asrt_id, digest in assertion_digests.items()
                if asrt_id not in revoked_assertion_ids
            }
            state_digest = _state_digest_for_assertions(active_assertions)
            annotation_meta_rows = _annotation_compatibility_meta_rows(
                legacy_rows.annotation_rows,
                (),
            )
            operations: list[dict[str, Any]] = [
                {
                    "kind": "assertion",
                    "asrt_id": claim.asrt_id,
                    "assertion_digest": assertion_digests[claim.asrt_id],
                }
                for claim in legacy_rows.claims
            ]
            operations.extend(
                {
                    "kind": "revocation",
                    "revoker_asrt_id": row.revoker_asrt_id,
                    "revoked_asrt_id": row.revoked_asrt_id,
                    "meta": (),
                }
                for row in legacy_rows.revocations
            )
            operations.extend(
                {
                    "kind": "append_meta",
                    "asrt_id": row.asrt_id,
                    "meta": MetaEntry(row.key, row.kind, row.value),
                }
                for row in (*legacy_rows.meta_rows, *annotation_meta_rows)
            )
            tx_id = _tx_id_for_v2(
                parent_tx_id=None,
                schema_digest=schema_token,
                digest_scheme=LTHASH_SCHEME,
                tx_seq=0,
                operations=operations,
            )
            assertion_writes = tuple(
                LedgerAssertionWrite(
                    claim=claim,
                    claim_args=tuple(
                        ClaimArg(claim.asrt_id, idx, val_atom, tag)
                        for idx, val_atom, tag in claim_args_from_rest_terms(claim.rest_terms)
                    ),
                    meta_rows=(
                        MetaRow(claim.asrt_id, "schema_digest", "str", schema_token),
                        MetaRow(
                            claim.asrt_id,
                            "assertion_digest",
                            "str",
                            assertion_digests[claim.asrt_id],
                        ),
                        MetaRow(claim.asrt_id, "tx_id", "str", tx_id),
                    ),
                )
                for claim in legacy_rows.claims
            )
            revocation_writes = tuple(
                LedgerRevocationWrite(
                    revokes=row,
                    meta_rows=(
                        MetaRow(row.revoker_asrt_id, "schema_digest", "str", schema_token),
                        MetaRow(row.revoker_asrt_id, "tx_id", "str", tx_id),
                    ),
                )
                for row in legacy_rows.revocations
            )
            for revocation in legacy_rows.revocations:
                revoker_id = _require_asrt_id(
                    revocation.revoker_asrt_id,
                    field="legacy revoker_asrt_id",
                )
                rows = meta_rows_by_asrt_id.get(revoker_id, [])
                if any(row.key in _RESERVED_ASSERTION_META_KEYS for row in rows):
                    raise DatabaseError(
                        f"legacy revoker already carries v0.3 reserved metadata: {revoker_id}"
                    )
            meta_appends: list[MetaRow] = [*legacy_rows.meta_rows, *annotation_meta_rows]

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
                assertions=assertion_writes,
                revocations=revocation_writes,
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
        """Return the current transaction/state head after integrity checks.

        Returns:
            The authoritative current ``DatabaseValue`` including transaction
            id, sequence, schema digest, and state digest.

        Raises:
            DatabaseIntegrityError: If persisted head metadata or transaction
                linkage fails verification.
        """
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
        """Commit one non-empty assertion batch atomically.

        Args:
            assertions: Canonical assertion inputs.

        Returns:
            The resulting transaction and Database head.

        Raises:
            DatabaseError: If the batch is empty or invalid.
        """
        if not assertions:
            raise DatabaseError("commit_assertions requires at least one assertion")
        return self.commit_changes(assertions=assertions, revocations=())

    def commit_changes(
        self,
        assertions: Sequence[AssertionInput],
        revocations: Sequence[RevocationInput],
        meta_appends: Sequence[MetaAppendInput | _MetaUnsetInput] = (),
        schema_transition: SchemaTransitionInput | None = None,
        *,
        meta_defaults: Sequence[MetaEntry] = (),
    ) -> CommitResult:
        """Commit one canonical change set atomically.

        Args:
            assertions: Assertions to append.
            revocations: Assertion revocations to append.
            meta_appends: Metadata append/unset operations.
            schema_transition: Optional isolated additive schema transition.
            meta_defaults: Transaction-level defaults for declared liftable keys.

        Returns:
            The resulting transaction and Database head.

        Raises:
            DatabaseError: If the change set is empty, conflicting, or invalid.
        """
        self._ensure_open()
        if (
            not assertions
            and not revocations
            and not meta_appends
            and schema_transition is None
            and not meta_defaults
        ):
            raise DatabaseError("commit_changes requires at least one change")
        if meta_defaults and not (assertions or revocations):
            raise DatabaseError(
                "meta_defaults require at least one assertion or revocation consumer"
            )
        if schema_transition is not None and (
            assertions or revocations or meta_appends or meta_defaults
        ):
            raise DatabaseError("schema_transition must be committed as an isolated change")
        prepared_meta_defaults = _normalize_tx_meta_defaults(meta_defaults)
        if prepared_meta_defaults and self._schema_ir is None:
            raise DatabaseError(
                "tx meta defaults require a schema with declared tx_liftable keys"
            )
        for entry in prepared_meta_defaults:
            try:
                require_tx_liftable_meta_key(
                    self._schema_ir,
                    entry.key,
                    context="tx meta defaults",
                )
            except MetaKeyPolicyError as exc:
                raise DatabaseError(str(exc)) from exc
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
                    "meta": MetaEntry(row.key, row.kind, row.value)
                    if isinstance(row, MetaRow)
                    else _UnsetMetaEntry(row.key),
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
            meta_defaults=prepared_meta_defaults,
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
                    meta_rows=(
                        *input_meta_rows,
                        MetaRow(
                            record.revoker_asrt_id, "schema_digest", "str", self._schema_digest
                        ),
                        MetaRow(record.revoker_asrt_id, "tx_id", "str", tx_id),
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
                meta_defaults=prepared_meta_defaults,
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

        if prepared_meta_defaults:
            self._ledger.record_tx_meta_defaults(
                tuple(
                    TxMetaDefault(tx_seq, row.key, row.kind, row.value)
                    for row in prepared_meta_defaults
                )
            )

        if prepared_schema_transition is not None:
            self._schema_digest = commit_schema_digest
            self._schema_ir = next_schema_ir
            self._ledger.configure_meta_load_policy(lazy_meta_keys(next_schema_ir))

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

    def _commit_meta_unsets(self, items: Sequence[_MetaUnsetInput]) -> CommitResult:
        """Internal policy hook for explicit UNSET events."""
        if not items:
            raise DatabaseError("_commit_meta_unsets requires at least one event")
        return self.commit_changes(assertions=(), revocations=(), meta_appends=items)

    def _commit_meta_rows(self, rows: Sequence[MetaRow]) -> CommitResult | None:
        """Commit managed ``Ledger.append_meta`` calls through dbtx_v2."""
        if not rows:
            return None
        return self.commit_changes(
            assertions=(),
            revocations=(),
            meta_appends=tuple(
                MetaAppendInput(row.asrt_id, row.key, row.kind, row.value) for row in rows
            ),
        )

    def _commit_annotations(self, rows: Sequence[AnnotationRow]) -> CommitResult | None:
        """Commit adapter annotation events through dbtx_v2 append-meta ops."""
        storage_rows = _annotation_compatibility_meta_rows(tuple(rows), ())
        if not storage_rows:
            return None
        inputs: list[_AnnotationMetaAppendInput] = []
        for row in storage_rows:
            # Decode once before any write so malformed AnnotationRow fields fail
            # at the prepare boundary, not after the tx object is durable.
            _annotation_from_storage_key(row.asrt_id, row.key, row.kind, row.value)
            inputs.append(
                _AnnotationMetaAppendInput(row.asrt_id, row.key, row.kind, row.value)
            )
        return self.commit_changes(assertions=(), revocations=(), meta_appends=inputs)

    def create_view(
        self,
        name: str,
        asrt_ids: Iterable[str],
        *,
        base: DatabaseValue | None = None,
    ) -> FrozenAssertionSet:
        """Persist a named frozen assertion set at the current head.

        Args:
            name: Stable view name.
            asrt_ids: Existing assertion ids to include.
            base: Optional current-head guard.

        Returns:
            The persisted frozen assertion-set descriptor.

        Raises:
            DatabaseError: If the Database is in-memory, the base is stale, or
                an assertion id does not exist.
        """
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
        _reject_duplicate_initial_meta_keys(meta, context="assertion initial meta")
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
            _reject_duplicate_initial_meta_keys(meta, context="revocation initial meta")
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
        items: Sequence[MetaAppendInput | _MetaUnsetInput],
    ) -> list[MetaRow | _MetaTombstone]:
        prepared: list[MetaRow | _MetaTombstone] = []
        for item in items:
            if isinstance(item, _MetaUnsetInput):
                asrt_id = _require_asrt_id(item.asrt_id, field="meta UNSET asrt_id")
                if not self._ledger._is_known_asrt_id(asrt_id):
                    raise DatabaseError(f"meta UNSET target does not exist: {asrt_id}")
                if not isinstance(item.key, str) or not item.key:
                    raise DatabaseError("meta UNSET key must be non-empty string")
                _reject_reserved_meta_keys((item.key,), context="meta UNSET")
                _reject_system_managed_meta_keys((item.key,), context="meta UNSET")
                prepared.append(_MetaTombstone(asrt_id, item.key))
                continue
            if not isinstance(item, MetaAppendInput):
                raise TypeError("meta_appends must contain MetaAppendInput")
            asrt_id = _require_asrt_id(item.asrt_id, field="meta append asrt_id")
            if not self._ledger._is_known_asrt_id(asrt_id):
                raise DatabaseError(f"meta append target does not exist: {asrt_id}")
            entry = _normalize_meta_entries((MetaEntry(item.key, item.kind, item.value),))[0]
            if isinstance(item, _AnnotationMetaAppendInput):
                if not _is_reserved_annotation_meta_key(entry.key):
                    raise DatabaseError("internal annotation input must use its reserved namespace")
                row_type = _AnnotationStorageMetaRow
            else:
                _reject_reserved_assertion_meta((entry,))
                _reject_system_managed_meta_keys((entry.key,), context="meta append")
                row_type = MetaRow
            _meta_value_bytes(entry.kind, entry.value)
            prepared.append(row_type(asrt_id, entry.key, entry.kind, entry.value))
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


def _migrate_workspace_command(path: str | Path) -> str:
    return f"python -m factgraph migrate-workspace {shlex.quote(str(path))}"


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
    meta_defaults: Sequence[MetaEntry | Mapping[str, Any]] = (),
) -> str:
    return "tx:" + sha256_hex(
        canonical_bytes_dbtx_v2(
            parent_tx_id=parent_tx_id,
            schema_digest=schema_digest,
            digest_scheme=digest_scheme,
            tx_seq=tx_seq,
            operations=operations,
            meta_defaults=meta_defaults,
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


def _read_legacy_ledger_rows(source: Path) -> _LegacyLedgerRows:
    """Read a v0.2 logical snapshot without mutating its SQLite file.

    Released v0.2 workspaces use the seven-table layout. A headless
    three-table snapshot is also accepted for the v0.2 compatibility surface
    on this release line. A transactional Database is never a migration source.
    """
    seven_tables = {
        "claims",
        "claim_args",
        "meta_rows",
        "revokes",
        "ingest_keys",
        "ledger_meta",
        "annotation_rows",
    }
    three_tables = {"claims", "claim_meta", "ledger_meta"}
    source_uri = source.resolve().as_uri() + "?mode=ro"
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(source_uri, uri=True)
        conn.row_factory = sqlite3.Row
        checks = [str(row[0]) for row in conn.execute("PRAGMA quick_check").fetchall()]
        if checks != ["ok"]:
            raise DatabaseError(f"legacy ledger quick_check failed: {checks!r}")
        tables = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        head = (
            conn.execute("SELECT value FROM ledger_meta WHERE key = 'head_tx_id'").fetchone()
            if "ledger_meta" in tables
            else None
        )
        if head is not None:
            raise DatabaseError("legacy migration source already has a transactional head")

        if seven_tables <= tables:
            rows = _read_seven_table_legacy_rows(conn)
        elif three_tables <= tables and not (tables & (seven_tables - {"claims", "ledger_meta"})):
            rows = _read_three_table_legacy_rows(conn)
        else:
            raise DatabaseError(
                "unsupported v0.2 ledger schema; expected the seven-table release layout"
            )
        _validate_legacy_ledger_rows(rows)
        return rows
    except DatabaseError:
        raise
    except (json.JSONDecodeError, sqlite3.Error, TypeError, ValueError) as exc:
        raise DatabaseError(f"failed to read legacy ledger: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()


def _contract_annotation_for_meta(row: MetaRow) -> AnnotationRow | None:
    projection = initial_meta_annotation_v1(row.key)
    if projection is None:
        return None
    return AnnotationRow(
        row.asrt_id,
        projection.namespace,
        projection.category,
        row.key,
        row.kind,
        row.value,
        projection.origin,
        projection.derivation,
    )


def _migration_annotation_identity(row: AnnotationRow) -> tuple[object, ...]:
    return (
        row.asrt_id,
        row.key,
        row.namespace,
        row.category,
        row.kind,
        json.dumps(
            _to_jsonable(row.value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        row.origin,
        row.derivation,
    )


def _read_seven_table_legacy_rows(conn: sqlite3.Connection) -> _LegacyLedgerRows:
    claims = tuple(
        Claim(
            str(row["asrt_id"]),
            str(row["pred_id"]),
            str(row["e_ref"]),
            _dec_rest_terms(str(row["rest_terms"])),
        )
        for row in conn.execute(
            "SELECT asrt_id, pred_id, e_ref, rest_terms FROM claims ORDER BY seq"
        ).fetchall()
    )
    actual_args = tuple(
        ClaimArg(
            str(row["asrt_id"]),
            int(row["idx"]),
            _dec(str(row["val_atom"])),
            str(row["tag"]),
        )
        for row in conn.execute(
            "SELECT asrt_id, idx, val_atom, tag FROM claim_args ORDER BY id"
        ).fetchall()
    )
    expected_args = tuple(
        ClaimArg(claim.asrt_id, idx, val_atom, tag)
        for claim in claims
        for idx, val_atom, tag in claim_args_from_rest_terms(claim.rest_terms)
    )
    if actual_args != expected_args:
        raise DatabaseError("legacy claim_args disagree with claims.rest_terms")
    meta_rows = tuple(
        MetaRow(
            str(row["asrt_id"]),
            str(row["key"]),
            str(row["kind"]),
            _dec(str(row["value"])),
        )
        for row in conn.execute(
            "SELECT asrt_id, key, kind, value FROM meta_rows ORDER BY id"
        ).fetchall()
    )
    annotation_rows = tuple(
        AnnotationRow(
            str(row["asrt_id"]),
            str(row["namespace"]),
            str(row["category"]),
            str(row["key"]),
            str(row["kind"]),
            _dec(str(row["value"])),
            str(row["origin"]),
            None if row["derivation"] is None else str(row["derivation"]),
        )
        for row in conn.execute(
            "SELECT asrt_id, namespace, category, key, kind, value, origin, derivation "
            "FROM annotation_rows ORDER BY id"
        ).fetchall()
    )
    revocations = tuple(
        Revokes(str(row["revoker_asrt_id"]), str(row["revoked_asrt_id"]))
        for row in conn.execute(
            "SELECT revoker_asrt_id, revoked_asrt_id FROM revokes ORDER BY id"
        ).fetchall()
    )
    return _LegacyLedgerRows(claims, meta_rows, annotation_rows, revocations)


def _read_three_table_legacy_rows(conn: sqlite3.Connection) -> _LegacyLedgerRows:
    factual_claims: list[Claim] = []
    revocations: list[Revokes] = []
    claim_tx_refs: dict[str, int] = {}
    claim_op_ordinals: dict[str, int] = {}
    next_op_ordinal_by_tx: dict[int, int] = {}
    for row in conn.execute(
        "SELECT asrt_id, pred_id, e_ref, rest_terms, value, value_tag, tx_ref "
        "FROM claims ORDER BY seq"
    ).fetchall():
        asrt_id = str(row["asrt_id"])
        pred_id = str(row["pred_id"])
        terms = _decode_claim_terms(row["rest_terms"], row["value"], row["value_tag"])
        tx_ref = int(row["tx_ref"])
        claim_tx_refs[asrt_id] = tx_ref
        claim_op_ordinals[asrt_id] = next_op_ordinal_by_tx.get(tx_ref, 0)
        next_op_ordinal_by_tx[tx_ref] = claim_op_ordinals[asrt_id] + 1
        if pred_id.startswith("__system__."):
            if pred_id != "__system__.revokes" or len(terms) != 1 or terms[0][0] != "string":
                raise DatabaseError(f"invalid legacy system claim: {asrt_id}")
            revocations.append(Revokes(asrt_id, str(terms[0][1])))
        else:
            factual_claims.append(Claim(asrt_id, pred_id, str(row["e_ref"]), terms))

    meta_rows: list[MetaRow] = []
    annotation_rows: list[AnnotationRow] = []
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
        asrt_id = str(row["asrt_id"])
        key = str(row["key"])
        kind = row["kind"]
        value = _decode_meta_value(kind, row["value"])
        if kind is None:
            raise DatabaseError("v0.2 migration source cannot contain claim_meta tombstones")
        kind = str(kind)
        if key.startswith(_ANNOTATION_COMPAT_PREFIX):
            annotation_rows.append(_annotation_from_storage_key(asrt_id, key, kind, value))
            continue
        meta = MetaRow(asrt_id, key, kind, value)
        meta_rows.append(meta)
        if asrt_id in identity_marked_asrt_ids:
            is_initial_meta = asrt_id not in identity_closed
        else:
            is_initial_meta = (
                int(row["tx_seq"]) == claim_tx_refs.get(asrt_id)
                and int(row["op_ordinal"]) == claim_op_ordinals.get(asrt_id)
            )
        if is_initial_meta:
            projection = initial_meta_annotation_v1(key)
            if projection is not None:
                annotation_rows.append(
                    AnnotationRow(
                        asrt_id,
                        projection.namespace,
                        projection.category,
                        key,
                        kind,
                        value,
                        projection.origin,
                        projection.derivation,
                    )
                )
        if key == "tx_id" and kind == "str":
            identity_closed.add(asrt_id)
    return _LegacyLedgerRows(
        tuple(factual_claims),
        tuple(meta_rows),
        tuple(annotation_rows),
        tuple(revocations),
    )


def _validate_legacy_ledger_rows(rows: _LegacyLedgerRows) -> None:
    factual_ids: set[str] = set()
    for claim in rows.claims:
        asrt_id = _require_asrt_id(claim.asrt_id, field="legacy asrt_id")
        if asrt_id in factual_ids:
            raise DatabaseError(f"duplicate legacy asrt_id: {asrt_id}")
        if _is_system_predicate(claim.pred_id):
            raise DatabaseError(f"legacy factual claim uses reserved predicate: {claim.pred_id}")
        factual_ids.add(asrt_id)

    revoker_ids: set[str] = set()
    for row in rows.revocations:
        revoker_id = _require_asrt_id(row.revoker_asrt_id, field="legacy revoker_asrt_id")
        target_id = _require_asrt_id(row.revoked_asrt_id, field="legacy revoked_asrt_id")
        if revoker_id in factual_ids or revoker_id in revoker_ids:
            raise DatabaseError(f"duplicate legacy revoker_asrt_id: {revoker_id}")
        if target_id not in factual_ids:
            raise DatabaseError(f"legacy revocation target does not exist: {target_id}")
        revoker_ids.add(revoker_id)

    known_ids = factual_ids | revoker_ids
    for row in (*rows.meta_rows, *rows.annotation_rows):
        if row.asrt_id not in known_ids:
            raise DatabaseError(f"legacy metadata references unknown asrt_id: {row.asrt_id}")


def _write_tx_object(
    paths: DatabaseWorkspacePaths,
    *,
    tx_id: str,
    parent_tx_id: str | None,
    schema_digest: str,
    digest_scheme: str,
    tx_seq: int,
    operations: Sequence[Mapping[str, Any]],
    meta_defaults: Sequence[MetaEntry | Mapping[str, Any]] = (),
) -> None:
    tx_id = _require_token(tx_id, prefix="tx:", field="tx_id")
    normalized = _normalize_tx_operations(operations)
    normalized_defaults = _normalize_tx_meta_defaults(meta_defaults)
    expected_tx_id = _tx_id_for_v2(
        parent_tx_id=parent_tx_id,
        schema_digest=schema_digest,
        digest_scheme=digest_scheme,
        tx_seq=tx_seq,
        operations=normalized,
        meta_defaults=normalized_defaults,
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
    if normalized_defaults:
        payload["meta_defaults"] = _tx_meta_defaults_payload(normalized_defaults)
    _write_once_bytes(_tx_object_path(paths, tx_id), _json_bytes(payload))


def _read_tx_object(paths: DatabaseWorkspacePaths, tx_id: str) -> dict[str, Any]:
    tx_id = _require_token(tx_id, prefix="tx:", field="tx_id")
    tx_path = _tx_object_path(paths, tx_id)
    if not tx_path.exists():
        raise DatabaseError(f"tx object missing: {tx_path}")
    payload = json.loads(tx_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DatabaseError("tx object must be JSON object")
    required_keys = {
        "digest_scheme",
        "operations",
        "parent_tx_id",
        "schema_digest",
        "tx_id",
        "tx_seq",
    }
    if set(payload) not in (required_keys, required_keys | {"meta_defaults"}):
        raise DatabaseError(
            "unexpected tx object fields: expected the six identity fields plus "
            f"optional meta_defaults, got {sorted(payload)}"
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
    meta_defaults = (
        _read_tx_meta_defaults(payload["meta_defaults"])
        if "meta_defaults" in payload
        else ()
    )
    if "meta_defaults" in payload and not meta_defaults:
        raise DatabaseError("tx object must omit meta_defaults when empty")
    expected_tx_id = _tx_id_for_v2(
        parent_tx_id=parent_tx_id,
        schema_digest=schema_token,
        digest_scheme=digest_scheme,
        tx_seq=tx_seq,
        operations=operations,
        meta_defaults=meta_defaults,
    )
    if expected_tx_id != tx_id:
        raise DatabaseError("tx object identity fields do not recompute tx_id")
    payload["parent_tx_id"] = parent_tx_id
    payload["schema_digest"] = schema_token
    payload["digest_scheme"] = digest_scheme
    payload["tx_seq"] = tx_seq
    payload["operations"] = operations
    if meta_defaults:
        payload["meta_defaults"] = meta_defaults
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
    _validate_claim_meta_parity(paths, ledger=ledger, head_tx_id=head.tx_id)
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


def _tx_meta_defaults_from_history(
    paths: DatabaseWorkspacePaths, *, head_tx_id: str
) -> tuple[TxMetaDefault, ...]:
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor: str | None = _require_token(
        head_tx_id, prefix="tx:", field="head_tx_id"
    )
    while cursor is not None:
        if cursor in seen:
            raise DatabaseIntegrityError("tx history contains a cycle")
        seen.add(cursor)
        payload = _read_tx_object(paths, cursor)
        chain.append(payload)
        cursor = payload["parent_tx_id"]
    chain.reverse()
    return tuple(
        TxMetaDefault(payload["tx_seq"], row.key, row.kind, row.value)
        for payload in chain
        for row in payload.get("meta_defaults", ())
    )


def _validate_claim_meta_parity(
    paths: DatabaseWorkspacePaths,
    *,
    ledger: Ledger,
    head_tx_id: str,
) -> None:
    """Verify every physical claim_meta event against its dbtx_v2 operation.

    Assertion initial meta is committed by ``assertion_digest`` plus the
    operation's tx/schema identity rows. Revocation initial meta and every M
    event are carried directly by the tx object. Any unconsumed physical event
    is therefore an unchained write and fails closed.
    """
    chain: list[dict[str, Any]] = []
    cursor: str | None = head_tx_id
    seen: set[str] = set()
    while cursor is not None:
        if cursor in seen:
            raise DatabaseIntegrityError("tx history contains a cycle")
        seen.add(cursor)
        payload = _read_tx_object(paths, cursor)
        chain.append(payload)
        cursor = payload["parent_tx_id"]
    chain.reverse()

    actual_by_position: dict[tuple[int, int], list[Any]] = {}
    for event in ledger._claim_meta_events:
        actual_by_position.setdefault(event.event_seq, []).append(event)

    consumed: set[tuple[int, int]] = set()
    known_tx_ids = {str(payload["tx_id"]) for payload in chain}

    # A repair_add sanctions a factual claim that arrived outside the tx
    # chain. Its physical tx_ref/op_ordinal therefore describes the drifted
    # write, not the later repair operation's position. Validate and consume
    # that original event group by assertion identity before walking normal
    # position-bound operations; the two positions can legitimately collide
    # with a repair_remove/repair operation in the repair transaction.
    for payload in chain:
        for operation in payload["operations"]:
            if operation["kind"] != "repair_add":
                continue
            asrt_id = operation["asrt_id"]
            physical_position = (
                ledger._claim_tx_refs.get(asrt_id),
                ledger._claim_op_ordinals.get(asrt_id),
            )
            if not all(isinstance(part, int) for part in physical_position):
                raise DatabaseIntegrityError(
                    f"repair_add has no physical claim position: {asrt_id}"
                )
            typed_position = (int(physical_position[0]), int(physical_position[1]))
            events = actual_by_position.get(typed_position, [])
            _validate_repair_add_meta_operation(
                ledger,
                payload=payload,
                operation=operation,
                events=events,
                known_tx_ids=known_tx_ids,
            )
            consumed.add(typed_position)

    for payload in chain:
        tx_seq = int(payload["tx_seq"])
        for op_ordinal, operation in enumerate(payload["operations"]):
            position = (tx_seq, op_ordinal)
            events = actual_by_position.get(position, [])
            kind = operation["kind"]
            if kind == "assertion":
                _validate_assertion_meta_operation(
                    ledger,
                    payload=payload,
                    operation=operation,
                    op_ordinal=op_ordinal,
                    events=events,
                )
            elif kind == "revocation":
                _validate_revocation_meta_operation(
                    ledger,
                    payload=payload,
                    operation=operation,
                    op_ordinal=op_ordinal,
                    events=events,
                )
            elif kind == "append_meta":
                _validate_append_meta_operation(operation=operation, events=events, position=position)
            elif events and position not in consumed:
                raise DatabaseIntegrityError(
                    f"claim_meta event has no meta-bearing tx operation at {position}"
                )
            consumed.add(position)

    leftovers = sorted(set(actual_by_position) - consumed)
    if leftovers:
        first = leftovers[0]
        event = actual_by_position[first][0]
        raise DatabaseIntegrityError(
            "claim_meta event is not represented by tx history: "
            f"asrt_id={event.asrt_id!r}, key={event.key!r}, event_seq={first}"
        )


def _validate_assertion_meta_operation(
    ledger: Ledger,
    *,
    payload: Mapping[str, Any],
    operation: Mapping[str, Any],
    op_ordinal: int,
    events: Sequence[Any],
) -> None:
    asrt_id = operation["asrt_id"]
    claim = ledger.get_claim(asrt_id)
    if claim is None:
        raise DatabaseIntegrityError(f"assertion tx operation has no factual claim: {asrt_id}")
    if ledger._claim_tx_refs.get(asrt_id) != payload["tx_seq"]:
        raise DatabaseIntegrityError(f"claims.tx_ref disagrees with assertion tx for {asrt_id}")
    if ledger._claim_op_ordinals.get(asrt_id) != op_ordinal:
        raise DatabaseIntegrityError(f"claim operation ordinal disagrees for {asrt_id}")
    rows = _unique_meta_events(events, asrt_id=asrt_id, context="assertion")
    expected_reserved = {
        "schema_digest": ("str", payload["schema_digest"]),
        "assertion_digest": ("str", operation["assertion_digest"]),
        "tx_id": ("str", payload["tx_id"]),
    }
    for key, expected in expected_reserved.items():
        _require_meta_event_value(rows, asrt_id=asrt_id, key=key, expected=expected)
    user_meta = tuple(
        MetaEntry(key, str(event.kind), event.value)
        for key, event in rows.items()
        if key not in _RESERVED_ASSERTION_META_KEYS
    )
    recomputed = assertion_digest_for(
        pred_id=claim.pred_id,
        fact_tuple=(("entity_ref", claim.e_ref), *tuple(claim.rest_terms)),
        schema_digest=payload["schema_digest"],
        meta=user_meta,
    )
    if recomputed != operation["assertion_digest"]:
        raise DatabaseIntegrityError(
            f"claim_meta initial content disagrees with assertion_digest for {asrt_id}"
        )


def _validate_revocation_meta_operation(
    ledger: Ledger,
    *,
    payload: Mapping[str, Any],
    operation: Mapping[str, Any],
    op_ordinal: int,
    events: Sequence[Any],
) -> None:
    asrt_id = operation["revoker_asrt_id"]
    if asrt_id not in ledger._system_claim_by_asrt_id:
        raise DatabaseIntegrityError(f"revocation tx operation has no system claim: {asrt_id}")
    if ledger._claim_tx_refs.get(asrt_id) != payload["tx_seq"]:
        raise DatabaseIntegrityError(f"claims.tx_ref disagrees with revocation tx for {asrt_id}")
    if ledger._claim_op_ordinals.get(asrt_id) != op_ordinal:
        raise DatabaseIntegrityError(f"revocation operation ordinal disagrees for {asrt_id}")
    rows = _unique_meta_events(events, asrt_id=asrt_id, context="revocation")
    expected = {
        entry.key: (entry.kind, entry.value)
        for entry in operation["meta"]
    }
    expected.update(
        {
            "schema_digest": ("str", payload["schema_digest"]),
            "tx_id": ("str", payload["tx_id"]),
        }
    )
    if set(rows) != set(expected):
        raise DatabaseIntegrityError(
            f"claim_meta keys disagree with revocation tx for {asrt_id}: "
            f"ledger={sorted(rows)}, tx={sorted(expected)}"
        )
    for key, value in expected.items():
        _require_meta_event_value(rows, asrt_id=asrt_id, key=key, expected=value)


def _validate_append_meta_operation(
    *,
    operation: Mapping[str, Any],
    events: Sequence[Any],
    position: tuple[int, int],
) -> None:
    if len(events) != 1:
        raise DatabaseIntegrityError(
            f"append_meta tx operation must map to exactly one claim_meta event at {position}"
        )
    event = events[0]
    entry = operation["meta"]
    expected_kind = None if isinstance(entry, _UnsetMetaEntry) else entry.kind
    expected_value = None if isinstance(entry, _UnsetMetaEntry) else entry.value
    expected = (operation["asrt_id"], entry.key, expected_kind, expected_value)
    actual = (event.asrt_id, event.key, event.kind, event.value)
    if actual != expected:
        raise DatabaseIntegrityError(
            "append_meta chain/ledger mismatch at "
            f"{position}: ledger={actual!r}, tx={expected!r}"
        )


def _validate_repair_add_meta_operation(
    ledger: Ledger,
    *,
    payload: Mapping[str, Any],
    operation: Mapping[str, Any],
    events: Sequence[Any],
    known_tx_ids: set[str],
) -> None:
    """Validate initial rows recovered by a sanctioned repair_add anchor."""
    asrt_id = operation["asrt_id"]
    claim = ledger.get_claim(asrt_id)
    if claim is None:
        raise DatabaseIntegrityError(f"repair_add has no factual claim: {asrt_id}")
    rows = _unique_meta_events(events, asrt_id=asrt_id, context="repair_add")
    _require_meta_event_value(
        rows,
        asrt_id=asrt_id,
        key="schema_digest",
        expected=("str", payload["schema_digest"]),
    )
    user_meta = tuple(
        MetaEntry(key, str(event.kind), event.value)
        for key, event in rows.items()
        if key not in _RESERVED_ASSERTION_META_KEYS
    )
    digest = assertion_digest_for(
        pred_id=claim.pred_id,
        fact_tuple=(("entity_ref", claim.e_ref), *tuple(claim.rest_terms)),
        schema_digest=payload["schema_digest"],
        meta=user_meta,
    )
    _require_meta_event_value(
        rows,
        asrt_id=asrt_id,
        key="assertion_digest",
        expected=("str", digest),
    )
    tx_event = rows.get("tx_id")
    if tx_event is None or tx_event.kind != "str" or tx_event.value not in known_tx_ids:
        raise DatabaseIntegrityError(
            f"claim_meta 'tx_id' for repaired assertion {asrt_id} is not anchored in history"
        )
def _unique_meta_events(
    events: Sequence[Any],
    *,
    asrt_id: str,
    context: str,
) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for event in events:
        if event.asrt_id != asrt_id:
            raise DatabaseIntegrityError(
                f"claim_meta {context} event targets the wrong assertion: {event.asrt_id}"
            )
        if event.kind is None:
            raise DatabaseIntegrityError(f"claim_meta {context} initial event cannot be UNSET")
        if event.key in rows:
            raise DatabaseIntegrityError(
                f"claim_meta {context} initial key is duplicated for {asrt_id}: {event.key}"
            )
        rows[event.key] = event
    return rows


def _require_meta_event_value(
    rows: Mapping[str, Any],
    *,
    asrt_id: str,
    key: str,
    expected: tuple[str, Any],
) -> None:
    event = rows.get(key)
    if event is None:
        raise DatabaseIntegrityError(f"claim_meta is missing {key!r} for {asrt_id}")
    actual = (event.kind, event.value)
    if actual != expected:
        raise DatabaseIntegrityError(
            f"claim_meta {key!r} disagrees for {asrt_id}: ledger={actual!r}, tx={expected!r}"
        )


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
    if not isinstance(value, str) or not value.startswith(("db:", "mem:")):
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
            if isinstance(raw_meta, (MetaEntry, _UnsetMetaEntry)):
                meta = raw_meta
            elif isinstance(raw_meta, Mapping):
                _require_exact_keys(raw_meta, {"key", "kind", "value"})
                raw_key = raw_meta.get("key")
                raw_kind = raw_meta.get("kind")
                raw_value = _from_jsonable(raw_meta.get("value"))
                if raw_kind is None:
                    if raw_value is not None:
                        raise DatabaseError("append_meta kind/value must both be null for UNSET")
                    if not isinstance(raw_key, str) or not raw_key:
                        raise DatabaseError("UNSET meta key must be non-empty string")
                    meta = _UnsetMetaEntry(raw_key)
                else:
                    meta = MetaEntry(raw_key, raw_kind, raw_value)
            else:
                raise DatabaseError("append_meta operation meta must be MetaEntry or mapping")
            if isinstance(meta, _UnsetMetaEntry):
                normalized_meta: MetaEntry | _UnsetMetaEntry = meta
            else:
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
            "meta": {
                "key": row.key,
                "kind": row.kind,
                "value": None if isinstance(row, _UnsetMetaEntry) else _to_jsonable(row.value),
            },
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


def _normalize_tx_meta_defaults(
    rows: Sequence[MetaEntry | Mapping[str, Any]],
) -> tuple[MetaEntry, ...]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise DatabaseError("meta_defaults must be a sequence")
    entries: list[MetaEntry] = []
    for raw in rows:
        if isinstance(raw, MetaEntry):
            entry = raw
        elif isinstance(raw, Mapping):
            _require_exact_keys(raw, {"key", "kind", "value"})
            entry = MetaEntry(
                raw.get("key"),
                raw.get("kind"),
                _from_jsonable(raw.get("value")),
            )
        else:
            raise DatabaseError("meta_defaults entries must be MetaEntry or mapping")
        entries.extend(_normalize_meta_entries((entry,)))

    keys = [entry.key for entry in entries]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise DatabaseError(
            "meta_defaults keys must be unique; repeated key(s): "
            + ", ".join(duplicates)
        )
    _reject_reserved_meta_keys(keys, context="tx meta defaults")
    _reject_system_managed_meta_keys(keys, context="tx meta defaults")
    system_keys = sorted(key for key in keys if key.startswith("__system__."))
    if system_keys:
        raise DatabaseError(
            "tx meta defaults cannot use the reserved '__system__.' namespace: "
            + ", ".join(system_keys)
        )
    return tuple(sorted(entries, key=lambda entry: entry.key))


def _read_tx_meta_defaults(value: Any) -> tuple[MetaEntry, ...]:
    if not isinstance(value, list):
        raise DatabaseError("tx object meta_defaults must be a list")
    raw_keys: list[str] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise DatabaseError("tx object meta_defaults entries must be objects")
        _require_exact_keys(raw, {"key", "kind", "value"})
        key = raw.get("key")
        if not isinstance(key, str) or not key:
            raise DatabaseError("tx object meta_defaults keys must be non-empty strings")
        raw_keys.append(key)
    if raw_keys != sorted(raw_keys):
        raise DatabaseError("tx object meta_defaults must be sorted by key")
    if len(raw_keys) != len(set(raw_keys)):
        raise DatabaseError("tx object meta_defaults keys must be unique")
    normalized = _normalize_tx_meta_defaults(value)
    if [entry.key for entry in normalized] != raw_keys:
        raise DatabaseError("tx object meta_defaults are not canonical")
    return normalized


def _tx_meta_defaults_payload(rows: Sequence[MetaEntry]) -> list[dict[str, Any]]:
    normalized = _normalize_tx_meta_defaults(rows)
    return [
        {"key": row.key, "kind": row.kind, "value": _to_jsonable(row.value)}
        for row in normalized
    ]


def _annotation_rows(asrt_id: str, meta: Sequence[MetaEntry]) -> list[AnnotationRow]:
    rows: list[AnnotationRow] = []
    for entry in meta:
        projection = initial_meta_annotation_v1(entry.key)
        if projection is None:
            continue
        rows.append(
            AnnotationRow(
                asrt_id=asrt_id,
                namespace=projection.namespace,
                category=projection.category,
                key=entry.key,
                kind=entry.kind,
                value=entry.value,
                origin=projection.origin,
                derivation=projection.derivation,
            )
        )
    return rows


def _reject_reserved_assertion_meta(rows: Sequence[MetaEntry]) -> None:
    _reject_reserved_meta_keys(tuple(row.key for row in rows), context="assertion/revocation meta")


def _reject_reserved_meta_keys(keys: Sequence[str], *, context: str) -> None:
    annotation_storage_keys = sorted(key for key in keys if _is_reserved_annotation_meta_key(key))
    if annotation_storage_keys:
        raise DatabaseError(
            f"{context} cannot use the reserved annotation storage "
            f"namespace: {_ANNOTATION_COMPAT_PREFIX}"
        )
    reserved = sorted(set(keys) & _RESERVED_ASSERTION_META_KEYS)
    if reserved:
        raise DatabaseError(
            f"{context} cannot use Database-reserved key(s): " + ", ".join(reserved)
        )


def _reject_system_managed_meta_keys(keys: Sequence[str], *, context: str) -> None:
    managed = sorted(set(keys) & _SYSTEM_MANAGED_META_KEYS)
    if managed:
        raise DatabaseError(
            f"{context} cannot override system-managed key(s): " + ", ".join(managed)
        )


def _reject_duplicate_initial_meta_keys(
    rows: Sequence[MetaEntry],
    *,
    context: str,
) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        if row.key in seen:
            duplicates.add(row.key)
        seen.add(row.key)
    if duplicates:
        raise DatabaseError(
            f"{context} keys must be unique; repeated key(s): "
            + ", ".join(sorted(duplicates))
        )


def _canonical_meta_entries_bytes(rows: Sequence[MetaEntry | _UnsetMetaEntry]) -> bytes:
    # The empty kind + empty value pair is reserved for explicit UNSET.  Normal
    # MetaEntry validation rejects an empty kind, so the encoding is unambiguous
    # and leaves every pre-existing dbtx_v2 byte sequence unchanged.
    encoded = [
        (row.key, "", b"")
        if isinstance(row, _UnsetMetaEntry)
        else (row.key, row.kind, _meta_value_bytes(row.kind, row.value))
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
    "DBTX_V2_META_DEFAULTS_SUFFIX",
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
    "MetaAppendInput",
    "MetaEntry",
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
