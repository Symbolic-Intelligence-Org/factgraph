from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def load_authoring_apply_events(registry_root: str | Path) -> list[AuthoringApplyEvent]:
    root = Path(registry_root)
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
    legacy = root / "authoring_apply_events.jsonl"
    workspace = root.parent
    if (
        root.name == "registry"
        and (workspace / "factgraph_workspace.json").exists()
        and (workspace / "db").exists()
    ):
        return [legacy, workspace / "db" / "audit" / "authoring_apply_events.jsonl"]
    return [legacy]


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
