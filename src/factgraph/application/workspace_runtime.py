from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factgraph.core.store.ledger import Ledger


WORKSPACE_MANIFEST_NAME = "factgraph_workspace.json"
WORKSPACE_VERSION = "1"
WORKSPACE_SAVE_SCOPE = "level_4"
WORKSPACE_LEDGER = "ledger.db"


class WorkspaceRuntimeError(Exception):
    pass


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    manifest: Path
    ledger: Path


def resolve_workspace_paths(path: str | Path) -> WorkspacePaths:
    if not isinstance(path, (str, Path)):
        raise WorkspaceRuntimeError("workspace path must be str | Path")
    root = Path(path)
    return WorkspacePaths(
        root=root,
        manifest=root / WORKSPACE_MANIFEST_NAME,
        ledger=root / WORKSPACE_LEDGER,
    )


def workspace_manifest_payload(
    *,
    schema_digest: str,
    created_at: str | None = None,
    last_saved_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(schema_digest, str) or not schema_digest:
        raise WorkspaceRuntimeError("schema_digest must be non-empty string")
    now = _now_iso()
    return {
        "factgraph_workspace_version": WORKSPACE_VERSION,
        "save_scope": WORKSPACE_SAVE_SCOPE,
        "schema_digest": schema_digest,
        "components": {
            "ledger": WORKSPACE_LEDGER,
            "db": "db/",
            "views": "views/",
        },
        "created_at": created_at or now,
        "last_saved_at": last_saved_at or now,
    }


def save_workspace_manifest(path: str | Path, *, schema_digest: str) -> dict[str, Any]:
    paths = resolve_workspace_paths(path)
    existing = _load_manifest(paths.manifest)
    created_at = existing.get("created_at") if existing is not None else None
    if created_at is not None and not isinstance(created_at, str):
        created_at = None
    payload = workspace_manifest_payload(
        schema_digest=schema_digest,
        created_at=created_at,
        last_saved_at=_now_iso(),
    )
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def validate_workspace_manifest(
    path: str | Path,
    *,
    schema_digest: str | None = None,
) -> dict[str, Any]:
    paths = resolve_workspace_paths(path)
    if not paths.manifest.exists():
        raise WorkspaceRuntimeError(f"workspace manifest missing: {WORKSPACE_MANIFEST_NAME}")
    payload = _load_manifest(paths.manifest)
    if payload is None:
        raise WorkspaceRuntimeError(f"workspace manifest missing: {WORKSPACE_MANIFEST_NAME}")
    if payload.get("factgraph_workspace_version") != WORKSPACE_VERSION:
        raise WorkspaceRuntimeError("unsupported factgraph_workspace_version")
    if payload.get("save_scope") != WORKSPACE_SAVE_SCOPE:
        raise WorkspaceRuntimeError("unsupported workspace save_scope")
    components = payload.get("components")
    if not isinstance(components, dict):
        raise WorkspaceRuntimeError("workspace manifest components must be object")
    if components.get("ledger") != WORKSPACE_LEDGER:
        raise WorkspaceRuntimeError("workspace manifest ledger component mismatch")
    manifest_digest = payload.get("schema_digest")
    if not isinstance(manifest_digest, str) or not manifest_digest:
        raise WorkspaceRuntimeError("workspace manifest schema_digest must be non-empty string")
    if schema_digest is not None and manifest_digest != schema_digest:
        raise WorkspaceRuntimeError(
            f"workspace schema_digest mismatch: manifest={manifest_digest!r}, expected={schema_digest!r}"
        )
    return payload


def copy_ledger_to_workspace(*, ledger: Ledger, target_path: str | Path) -> None:
    if not isinstance(ledger, Ledger):
        raise WorkspaceRuntimeError("ledger must be Ledger")
    target = Path(target_path)
    source_path = Path(getattr(ledger, "_path", ":memory:"))
    if str(source_path) != ":memory:" and source_path == target:
        _checkpoint_ledger(ledger)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = ledger._get_connection()  # noqa: SLF001 - application runtime owns workspace persistence.
    try:
        target_conn = sqlite3.connect(str(target))
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    except sqlite3.Error as exc:
        raise WorkspaceRuntimeError(f"failed to copy ledger into workspace: {exc}") from exc


def save_workspace(
    path: str | Path,
    *,
    schema_digest: str,
    ledger: Ledger,
) -> WorkspacePaths:
    paths = resolve_workspace_paths(path)
    paths.root.mkdir(parents=True, exist_ok=True)
    copy_ledger_to_workspace(ledger=ledger, target_path=paths.ledger)
    save_workspace_manifest(paths.root, schema_digest=schema_digest)
    return paths


def load_workspace(path: str | Path, *, schema_digest: str) -> WorkspacePaths:
    paths = resolve_workspace_paths(path)
    validate_workspace_manifest(paths.root, schema_digest=schema_digest)
    if not paths.ledger.exists():
        raise WorkspaceRuntimeError("workspace ledger component missing")
    return paths


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkspaceRuntimeError(f"invalid workspace manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkspaceRuntimeError("workspace manifest must be object")
    return payload


def _checkpoint_ledger(ledger: Ledger) -> None:
    conn = ledger._get_connection()  # noqa: SLF001 - application runtime owns workspace persistence.
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
    except sqlite3.Error:
        # In-memory ledgers and some sqlite modes may not support checkpointing;
        # a same-path save should still be idempotent.
        return


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "WORKSPACE_LEDGER",
    "WORKSPACE_MANIFEST_NAME",
    "WORKSPACE_SAVE_SCOPE",
    "WORKSPACE_VERSION",
    "WorkspacePaths",
    "WorkspaceRuntimeError",
    "copy_ledger_to_workspace",
    "load_workspace",
    "resolve_workspace_paths",
    "save_workspace",
    "save_workspace_manifest",
    "validate_workspace_manifest",
    "workspace_manifest_payload",
]
