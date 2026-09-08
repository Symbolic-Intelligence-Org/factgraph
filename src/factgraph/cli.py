"""Top-level FactGraph CLI for opt-in workspace migration.

``migrate-workspace`` accepts both the pre-A20(E) registry marker and the
v0.2 layout whose authoritative Ledger lived at ``<workspace>/ledger.db``.
The v0.3 layout owns ``db/assertions.db`` transactionally, keeps canonical
schema objects under ``db/objects/schema/``, and records one explicit repair
anchor because the pre-v0.3 transaction history cannot be reconstructed.

Invocation:

    python -m factgraph migrate-workspace <path> [--dry-run] [--archive | --no-archive]

The migration is opt-in and must run while the source workspace is closed.
``FactGraph.load_workspace(...)`` never auto-invokes it. The migration writes
no ``authoring_apply_events.jsonl`` entry (Slice 7C retired that write path).
Interrupted replacement leaves a visible ``<workspace>.legacy-<timestamp>``
sibling; reruns detect it and return explicit manual recovery guidance.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.store.database import (
    Database,
    DatabaseError,
    write_schema_object_for_workspace,
)

_LEGACY_REGISTRY_DIR = "registry"
_LEGACY_REGISTRY_SCHEMA_REL = "schema/schema_ir.json"
_LEGACY_REGISTRY_MANIFEST = "registry_manifest.json"
_WORKSPACE_MANIFEST = "factgraph_workspace.json"


def _migration_backup_siblings(workspace: Path) -> list[Path]:
    """Return interrupted-replacement backups beside ``workspace``.

    The non-hidden form is canonical. The hidden pattern is also recognized so
    a workspace stranded by an earlier prerelease build remains discoverable.
    """
    parent = workspace.parent
    if not parent.is_dir():
        return []
    prefixes = (f"{workspace.name}.legacy-", f".{workspace.name}.legacy-")
    return sorted(
        candidate
        for candidate in parent.iterdir()
        if candidate.is_dir() and candidate.name.startswith(prefixes)
    )


def _print_recovery_required(
    *,
    workspace: Path,
    candidates: list[Path],
    replacement_present: bool,
) -> None:
    abs_path = str(workspace.resolve(strict=False))
    candidate_paths = [str(candidate.resolve(strict=False)) for candidate in candidates]
    if replacement_present:
        guidance = (
            "a migrated replacement and an unarchived legacy sibling both exist; "
            "verify the replacement, then archive or remove the sibling explicitly"
        )
    else:
        guidance = (
            "the requested workspace is missing; verify the legacy sibling, rename it "
            "back to the requested path, then rerun migrate-workspace"
        )
    _print_error_json(
        kind="workspace_recovery_required",
        message=f"interrupted workspace replacement detected: {guidance}",
        details={
            "workspace": abs_path,
            "recovery_candidates": candidate_paths,
            "replacement_present": replacement_present,
            "guidance": guidance,
        },
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "migrate-workspace":
        return _run_migrate_workspace(
            path=args.path,
            dry_run=bool(args.dry_run),
            archive=bool(args.archive),
        )
    # argparse should reject this branch before reaching here
    _print_error_json(
        kind="unknown_command",
        message=f"unknown command: {args.command}",
        details={"command": args.command},
    )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m factgraph")
    sub = parser.add_subparsers(dest="command", required=True)

    migrate = sub.add_parser(
        "migrate-workspace",
        help="Migrate a v0.2 workspace to the transactional v0.3 Database layout.",
    )
    migrate.add_argument(
        "path",
        help="Closed v0.2 workspace directory to migrate.",
    )
    migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the source and print the plan without writing.",
    )
    archive_group = migrate.add_mutually_exclusive_group()
    archive_group.add_argument(
        "--archive",
        dest="archive",
        action="store_true",
        default=True,
        help="(Default) Retain the complete v0.2 workspace plus any legacy registry marker.",
    )
    archive_group.add_argument(
        "--no-archive",
        dest="archive",
        action="store_false",
        help="Discard the v0.2 backup after the verified replacement succeeds.",
    )

    return parser


# ---------------------------------------------------------------------------
# migrate-workspace implementation
# ---------------------------------------------------------------------------


def _run_migrate_workspace(*, path: str, dry_run: bool, archive: bool) -> int:
    workspace = Path(path)
    abs_path = str(workspace.resolve(strict=False))

    if not workspace.exists() or not workspace.is_dir():
        recovery_candidates = _migration_backup_siblings(workspace)
        if recovery_candidates:
            _print_recovery_required(
                workspace=workspace,
                candidates=recovery_candidates,
                replacement_present=False,
            )
            return 1
        _print_error_json(
            kind="workspace_not_found",
            message=f"workspace directory not found: {abs_path}",
            details={"workspace": abs_path},
        )
        return 1

    manifest_path = workspace / _WORKSPACE_MANIFEST
    if not manifest_path.exists():
        _print_error_json(
            kind="workspace_incomplete",
            message=(
                f"workspace manifest missing: {_WORKSPACE_MANIFEST}; "
                "recreate this incomplete workspace"
            ),
            details={
                "workspace": abs_path,
                "manifest_path": str(manifest_path),
                "guidance": "recreate; migrate-workspace requires a complete v0.2 workspace",
            },
        )
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _print_error_json(
            kind="workspace_manifest_unreadable",
            message=f"failed to read workspace manifest: {exc}",
            details={"workspace": abs_path, "manifest_path": str(manifest_path)},
        )
        return 1
    if not isinstance(manifest, dict):
        _print_error_json(
            kind="workspace_manifest_invalid",
            message="workspace manifest must be a JSON object",
            details={"workspace": abs_path},
        )
        return 1

    components = manifest.get("components")
    manifest_registry = (
        components.get("registry") if isinstance(components, dict) else None
    )
    legacy_registry_dir = workspace / _LEGACY_REGISTRY_DIR

    db_meta = workspace / "db" / "meta.json"
    db_assertions = workspace / "db" / "assertions.db"
    new_layout = db_meta.is_file() and db_assertions.is_file()
    legacy_ledger_name = (
        components.get("ledger")
        if isinstance(components, dict) and isinstance(components.get("ledger"), str)
        else "ledger.db"
    )
    legacy_ledger_path = workspace / legacy_ledger_name

    if not new_layout and legacy_ledger_path.is_file():
        return _run_v02_layout_migration(
            workspace=workspace,
            manifest=manifest,
            legacy_ledger_path=legacy_ledger_path,
            legacy_registry_dir=legacy_registry_dir,
            dry_run=dry_run,
            archive=archive,
        )

    if not new_layout:
        _print_error_json(
            kind="workspace_incomplete",
            message=(
                "workspace has neither a complete v0.3 db/ layout nor a complete "
                "v0.2 ledger.db source; recreate it"
            ),
            details={
                "workspace": abs_path,
                "expected_v03": ["db/meta.json", "db/assertions.db"],
                "expected_v02": legacy_ledger_name,
                "guidance": "recreate; registry-only and torn-create sources are not migratable",
            },
        )
        return 1

    legacy_present = (
        manifest_registry is not None or legacy_registry_dir.exists()
    )

    # Idempotent noop: nothing to migrate.
    if not legacy_present:
        recovery_candidates = _migration_backup_siblings(workspace)
        if recovery_candidates:
            _print_recovery_required(
                workspace=workspace,
                candidates=recovery_candidates,
                replacement_present=True,
            )
            return 1
        _print_success_json(
            status="noop",
            workspace=abs_path,
            schema_digest_value=_safe_str(manifest.get("schema_digest")),
            actions=[],
        )
        return 0

    legacy_schema_path = (
        legacy_registry_dir / _LEGACY_REGISTRY_SCHEMA_REL
    )
    if not legacy_schema_path.exists():
        _print_error_json(
            kind="legacy_schema_missing",
            message="legacy registry/ marker present but no schema_ir.json found",
            details={
                "workspace": abs_path,
                "schema_path": str(legacy_schema_path),
            },
        )
        return 1

    try:
        legacy_schema_ir = json.loads(
            legacy_schema_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        _print_error_json(
            kind="legacy_schema_unreadable",
            message=f"failed to read legacy schema_ir: {exc}",
            details={
                "workspace": abs_path,
                "schema_path": str(legacy_schema_path),
            },
        )
        return 1
    if not isinstance(legacy_schema_ir, dict):
        _print_error_json(
            kind="legacy_schema_invalid",
            message="legacy schema_ir must be a JSON object",
            details={
                "workspace": abs_path,
                "schema_path": str(legacy_schema_path),
            },
        )
        return 1

    try:
        digest = schema_digest(legacy_schema_ir)
    except Exception as exc:  # noqa: BLE001 - schema_digest boundary over untrusted legacy JSON; reported as the schema_digest_failed error JSON with exit code 1.
        _print_error_json(
            kind="schema_digest_failed",
            message=f"failed to compute schema_digest: {exc}",
            details={
                "workspace": abs_path,
                "schema_path": str(legacy_schema_path),
            },
        )
        return 1

    manifest_digest = manifest.get("schema_digest")
    if isinstance(manifest_digest, str) and manifest_digest and manifest_digest != digest:
        _print_error_json(
            kind="schema_digest_mismatch",
            message=(
                f"legacy schema_ir digest does not match workspace manifest: "
                f"legacy={digest!r}, manifest={manifest_digest!r}"
            ),
            details={
                "workspace": abs_path,
                "legacy_digest": digest,
                "manifest_digest": manifest_digest,
            },
        )
        return 1

    timestamp = (
        datetime.now(timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )
    archive_target_name = f"{_LEGACY_REGISTRY_DIR}.legacy.{timestamp}"
    archive_target = workspace / archive_target_name

    schema_object_rel = f"db/objects/schema/{digest.removeprefix('sha256:')}.json"
    actions: list[dict[str, Any]] = [
        {"kind": "write", "path": schema_object_rel},
    ]
    if archive and legacy_registry_dir.exists():
        actions.append(
            {
                "kind": "rename",
                "from": _LEGACY_REGISTRY_DIR,
                "to": archive_target_name,
            }
        )
    if manifest_registry is not None:
        actions.append(
            {
                "kind": "manifest_update",
                "removed_components": ["registry"],
            }
        )

    if dry_run:
        _print_success_json(
            status="dry_run",
            workspace=abs_path,
            schema_digest_value=digest,
            actions=actions,
        )
        return 0

    # Perform the migration.
    try:
        write_schema_object_for_workspace(workspace, legacy_schema_ir)
    except DatabaseError as exc:
        _print_error_json(
            kind="db_schema_object_write_failed",
            message=f"failed to write workspace schema object: {exc}",
            details={"workspace": abs_path, "schema_digest": digest},
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - workspace schema object write crosses the Database adapter; reported as the db_schema_object_write_failed error JSON with exit code 1.
        _print_error_json(
            kind="db_schema_object_write_failed",
            message=f"unexpected error writing workspace schema object: {exc}",
            details={"workspace": abs_path, "schema_digest": digest},
        )
        return 1

    if archive and legacy_registry_dir.exists():
        try:
            legacy_registry_dir.rename(archive_target)
        except OSError as exc:
            _print_error_json(
                kind="legacy_archive_failed",
                message=f"failed to archive legacy registry/: {exc}",
                details={
                    "workspace": abs_path,
                    "from": _LEGACY_REGISTRY_DIR,
                    "to": archive_target_name,
                },
            )
            return 1

    if manifest_registry is not None and isinstance(components, dict):
        new_components = {k: v for k, v in components.items() if k != "registry"}
        manifest["components"] = new_components
        try:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            _print_error_json(
                kind="manifest_update_failed",
                message=f"failed to update workspace manifest: {exc}",
                details={"workspace": abs_path, "manifest_path": str(manifest_path)},
            )
            return 1

    _print_success_json(
        status="migrated",
        workspace=abs_path,
        schema_digest_value=digest,
        actions=actions,
    )
    return 0


def _run_v02_layout_migration(
    *,
    workspace: Path,
    manifest: dict[str, Any],
    legacy_ledger_path: Path,
    legacy_registry_dir: Path,
    dry_run: bool,
    archive: bool,
) -> int:
    abs_path = str(workspace.resolve(strict=False))
    loaded = _load_v02_schema_ir(
        workspace=workspace,
        manifest=manifest,
        legacy_registry_dir=legacy_registry_dir,
    )
    if loaded is None:
        return 1
    schema_ir, digest = loaded
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"workspace.legacy.{timestamp}"
    actions: list[dict[str, Any]] = [
        {
            "kind": "copy_legacy_ledger",
            "from": legacy_ledger_path.name,
            "to": "db/assertions.db",
        },
        {"kind": "write_migration_anchor", "tx_seq": 0},
        {"kind": "replace_workspace_layout", "components": ["db/", "views/"]},
    ]
    if archive:
        actions.append({"kind": "archive_workspace", "to": backup_name})

    if dry_run:
        _print_success_json(
            status="dry_run",
            workspace=abs_path,
            schema_digest_value=digest,
            actions=actions,
        )
        return 0

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{workspace.name}.migrate-",
            dir=str(workspace.parent),
        )
    )
    backup_sibling = workspace.with_name(f"{workspace.name}.legacy-{timestamp}")
    try:
        head = Database.migrate_legacy_ledger(
            source_ledger_path=legacy_ledger_path,
            target_workspace=staging,
            schema_ir=schema_ir,
        )
        legacy_views = workspace / "views"
        if legacy_views.is_dir():
            shutil.copytree(legacy_views, staging / "views", dirs_exist_ok=True)

        if backup_sibling.exists():
            raise DatabaseError(f"migration backup target already exists: {backup_sibling}")
        os.replace(workspace, backup_sibling)
        try:
            os.replace(staging, workspace)
        except Exception:
            os.replace(backup_sibling, workspace)
            raise

        if archive:
            archive_target = workspace / backup_name
            os.replace(backup_sibling, archive_target)
        else:
            shutil.rmtree(backup_sibling)
    except Exception as exc:  # noqa: BLE001 - v0.2 workspace filesystem migration boundary (copy/replace/rmtree); reported as workspace_layout_migration_failed with exit code 1 after rollback.
        _print_error_json(
            kind="workspace_layout_migration_failed",
            message=f"failed to migrate v0.2 workspace: {exc}",
            details={"workspace": abs_path, "legacy_ledger": str(legacy_ledger_path)},
        )
        return 1
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    _print_success_json(
        status="migrated",
        workspace=abs_path,
        schema_digest_value=digest,
        actions=actions,
        head_tx_id=head.tx_id,
    )
    return 0


def _load_v02_schema_ir(
    *,
    workspace: Path,
    manifest: dict[str, Any],
    legacy_registry_dir: Path,
) -> tuple[dict[str, Any], str] | None:
    manifest_digest = manifest.get("schema_digest")
    candidates: list[Path] = []
    if isinstance(manifest_digest, str) and manifest_digest.startswith("sha256:"):
        candidates.append(
            workspace
            / "db"
            / "objects"
            / "schema"
            / f"{manifest_digest.removeprefix('sha256:')}.json"
        )
    candidates.append(legacy_registry_dir / _LEGACY_REGISTRY_SCHEMA_REL)
    schema_object_dir = workspace / "db" / "objects" / "schema"
    if schema_object_dir.is_dir():
        for candidate in sorted(schema_object_dir.glob("*.json")):
            if candidate not in candidates:
                candidates.append(candidate)
    schema_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if schema_path is None:
        _print_error_json(
            kind="legacy_schema_missing",
            message="v0.2 workspace has no content-addressed or registry schema object",
            details={"workspace": str(workspace.resolve(strict=False))},
        )
        return None
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("schema root must be object")  # noqa: TRY004 - Joins json.loads' family at the legacy_schema_unreadable boundary.
        digest = schema_digest(payload)
    except Exception as exc:  # noqa: BLE001 - legacy schema object read/digest boundary over untrusted JSON; reported as the legacy_schema_unreadable error JSON and returns None.
        _print_error_json(
            kind="legacy_schema_unreadable",
            message=f"failed to read v0.2 schema object: {exc}",
            details={"schema_path": str(schema_path)},
        )
        return None
    if isinstance(manifest_digest, str) and manifest_digest and manifest_digest != digest:
        _print_error_json(
            kind="schema_digest_mismatch",
            message=(
                "v0.2 schema object content digest disagrees with the workspace "
                "manifest schema_digest"
            ),
            details={
                "manifest_schema_digest": manifest_digest,
                "object_schema_digest": digest,
                "schema_path": str(schema_path),
            },
        )
        return None
    return payload, digest


# ---------------------------------------------------------------------------
# JSON output helpers
# ---------------------------------------------------------------------------


def _print_success_json(
    *,
    status: str,
    workspace: str,
    schema_digest_value: str | None,
    actions: list[dict[str, Any]],
    head_tx_id: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "workspace": workspace,
        "actions": actions,
    }
    if schema_digest_value is not None:
        payload["schema_digest"] = schema_digest_value
    if head_tx_id is not None:
        payload["head_tx_id"] = head_tx_id
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _print_error_json(
    *,
    kind: str,
    message: str,
    details: dict[str, Any],
) -> None:
    payload: dict[str, Any] = {
        "status": "error",
        "kind": kind,
        "message": message,
        "details": details,
    }
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        file=sys.stderr,
    )


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
