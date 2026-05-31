"""Top-level FactGraph CLI for v0.2.0+ workspace migration.

Slice 7C / Q6-A (d.4) — implements ``migrate-workspace`` for legacy
workspaces created before Slice 7A's schema-anchor migration. The legacy
shape stored the schema IR at ``<workspace>/registry/schema/schema_ir.json``
and declared ``components.registry`` in the workspace manifest. The
post-A20(E) layout writes the schema object to
``<workspace>/db/objects/schema/<digest>.json`` via Slice 7A helpers and
drops ``components.registry`` from the manifest.

Invocation:

    python -m factgraph migrate-workspace <path> [--dry-run] [--archive | --no-archive]

The migration is opt-in. ``FactGraph.load_workspace(...)`` rejects legacy workspaces
with an ``SDKStoreError`` instructing users to run this CLI; this CLI is
NOT auto-invoked from load. The migration writes no ``authoring_apply_events.jsonl``
entry (Slice 7C retired the apply-execute write path; Q6-A (a.2)).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factgraph.core.schema.schema_ir import schema_digest
from factgraph.core.store.database import (
    DatabaseError,
    write_schema_object_for_workspace,
)


_LEGACY_REGISTRY_DIR = "registry"
_LEGACY_REGISTRY_SCHEMA_REL = "schema/schema_ir.json"
_LEGACY_REGISTRY_MANIFEST = "registry_manifest.json"
_WORKSPACE_MANIFEST = "factgraph_workspace.json"


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
        help="Migrate a legacy registry/ workspace to the post-A20(E) db/objects/schema layout.",
    )
    migrate.add_argument(
        "path",
        help="Workspace directory carrying legacy registry/ markers.",
    )
    migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the migration plan as JSON without performing any writes.",
    )
    archive_group = migrate.add_mutually_exclusive_group()
    archive_group.add_argument(
        "--archive",
        dest="archive",
        action="store_true",
        default=True,
        help="(Default) Rename legacy registry/ to registry.legacy.<ISO8601-UTC-timestamp>/.",
    )
    archive_group.add_argument(
        "--no-archive",
        dest="archive",
        action="store_false",
        help="Leave legacy registry/ in place after migration.",
    )

    return parser


# ---------------------------------------------------------------------------
# migrate-workspace implementation
# ---------------------------------------------------------------------------


def _run_migrate_workspace(*, path: str, dry_run: bool, archive: bool) -> int:
    workspace = Path(path)
    abs_path = str(workspace.resolve(strict=False))

    if not workspace.exists() or not workspace.is_dir():
        _print_error_json(
            kind="workspace_not_found",
            message=f"workspace directory not found: {abs_path}",
            details={"workspace": abs_path},
        )
        return 1

    manifest_path = workspace / _WORKSPACE_MANIFEST
    if not manifest_path.exists():
        _print_error_json(
            kind="workspace_manifest_missing",
            message=f"workspace manifest missing: {_WORKSPACE_MANIFEST}",
            details={"workspace": abs_path, "manifest_path": str(manifest_path)},
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

    legacy_present = (
        manifest_registry is not None or legacy_registry_dir.exists()
    )

    # Idempotent noop: nothing to migrate.
    if not legacy_present:
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
    except Exception as exc:
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

    schema_object_rel = f"db/objects/schema/{digest}.json"
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
    except Exception as exc:
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


# ---------------------------------------------------------------------------
# JSON output helpers
# ---------------------------------------------------------------------------


def _print_success_json(
    *,
    status: str,
    workspace: str,
    schema_digest_value: str | None,
    actions: list[dict[str, Any]],
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "workspace": workspace,
        "actions": actions,
    }
    if schema_digest_value is not None:
        payload["schema_digest"] = schema_digest_value
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
