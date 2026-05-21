from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Slice 7C / Q6-A (a.2) note:
#   The apply-execute write path was retired alongside `FileAuthoringRegistry`.
#   This module retains the read path for legacy audit-package consumption
#   (`audit/reader.py`, `service/static_ui.py`). New workspaces produce zero
#   apply events; pre-7C workspaces and audit packages may still carry the
#   `authoring_apply_events.jsonl` file at either the workspace `db/audit/`
#   path (Slice 7B layout) or the legacy `registry/` layout (pre-7B). The
#   `_legacy_workspace_apply_log_path()` helper here is the relocated and
#   renamed `_workspace_apply_log_path_for_registry()` from the deleted
#   `authoring/registry_fs.py`; it is intentionally read-only.


class AuthoringAuditReadError(Exception):
    pass


@dataclass(frozen=True)
class AuthoringApplyEvent:
    action_id: str | None
    section: str | None
    action: str | None
    status: str | None
    backend_result: dict[str, Any] | None
    raw: dict[str, Any]


def load_authoring_apply_events(workspace_path: str | Path) -> list[AuthoringApplyEvent]:
    """Load authoring apply events from the supplied path.

    Accepts a workspace root directory or an audit-package directory. Reads
    from the canonical workspace location
    (``<path>/db/audit/authoring_apply_events.jsonl``) plus, when the input
    is a legacy ``registry/`` directory, the legacy fallback at
    ``<path>/authoring_apply_events.jsonl``. Missing files are silently
    skipped so callers see an empty list for new (post-7C) workspaces.
    """
    root = Path(workspace_path)
    events: list[AuthoringApplyEvent] = []
    for path in _apply_log_read_paths(root):
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuthoringAuditReadError(
                    f"invalid authoring apply event JSON at {path}:{line_no}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise AuthoringAuditReadError(f"authoring apply event must be object at {path}:{line_no}")
            events.append(
                AuthoringApplyEvent(
                    action_id=payload.get("action_id") if isinstance(payload.get("action_id"), str) else None,
                    section=payload.get("section") if isinstance(payload.get("section"), str) else None,
                    action=payload.get("action") if isinstance(payload.get("action"), str) else None,
                    status=payload.get("status") if isinstance(payload.get("status"), str) else None,
                    backend_result=payload.get("backend_result")
                    if isinstance(payload.get("backend_result"), dict)
                    else None,
                    raw=payload,
                )
            )
    return events


def _apply_log_read_paths(root: Path) -> list[Path]:
    """Return the candidate read paths in priority order.

    Three legacy + canonical read paths are supported (Step 4.7 P1-3 fix):

    1. **Canonical workspace layout** (Slice 7B+):
       ``<root>/db/audit/authoring_apply_events.jsonl``.
    2. **Audit-package fallback**: ``<root>/authoring_apply_events.jsonl``.
       Audit packages emitted by older versions of the runtime placed the
       apply-log directly at the package root. Static UI / audit-package
       consumers MUST continue to read this location when present.
    3. **Legacy workspace ``registry/`` fallback**: when ``root`` itself is
       a legacy ``registry/`` directory inside a workspace, the legacy
       per-registry file ``<root>/authoring_apply_events.jsonl`` is
       resolved via :func:`_legacy_workspace_apply_log_path`. (This path
       happens to coincide with the audit-package fallback above when the
       caller passes a registry directory, which is fine — file existence
       is checked per-path before reading.)

    Missing files are silently skipped by :func:`load_authoring_apply_events`.
    """
    paths: list[Path] = [
        root / "db" / "audit" / "authoring_apply_events.jsonl",
        root / "authoring_apply_events.jsonl",
    ]
    legacy = _legacy_workspace_apply_log_path(root)
    if legacy is not None and legacy not in paths:
        paths.append(legacy)
    return paths


def _legacy_workspace_apply_log_path(root: Path) -> Path | None:
    """Return the legacy ``registry/authoring_apply_events.jsonl`` path when ``root``
    is a legacy ``registry/`` directory inside a workspace, else ``None``.

    Read-only helper relocated from the deleted ``authoring/registry_fs.py``
    module. The three-condition workspace marker mirrors the Slice 7B
    implementation: a path named ``registry`` whose parent contains both
    ``factgraph_workspace.json`` and a ``db/`` directory.
    """
    workspace = root.parent
    if (
        root.name == "registry"
        and (workspace / "factgraph_workspace.json").exists()
        and (workspace / "db").exists()
    ):
        return root / "authoring_apply_events.jsonl"
    return None


def summarize_authoring_apply_events(events: list[AuthoringApplyEvent]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    section_counts: dict[str, int] = {}
    for event in events:
        if isinstance(event.status, str):
            status_counts[event.status] = status_counts.get(event.status, 0) + 1
        if isinstance(event.section, str):
            section_counts[event.section] = section_counts.get(event.section, 0) + 1
    return {
        "event_count": len(events),
        "status_counts": {key: status_counts[key] for key in sorted(status_counts)},
        "section_counts": {key: section_counts[key] for key in sorted(section_counts)},
    }
