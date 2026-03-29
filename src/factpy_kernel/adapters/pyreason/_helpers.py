"""Shared helpers for the pyreason adapter package."""
from __future__ import annotations


def _pred_short_name(pred_id: str) -> str:
    """Extract the short name after the first colon, or return as-is."""
    parts = pred_id.split(":", 1)
    return parts[1] if len(parts) > 1 else pred_id


def _parse_edge_component(component: str) -> tuple[str, str] | None:
    """Parse PyReason edge component names to ``(from_ref, to_ref)``."""
    if component.startswith("(") and component.endswith(")"):
        inner = component[1:-1]
        parts = [part.strip() for part in inner.split(",")]
        if len(parts) == 2:
            return (parts[0], parts[1])
    if "-" in component:
        parts = component.split("-", 1)
        if len(parts) == 2:
            return (parts[0], parts[1])
    return None
