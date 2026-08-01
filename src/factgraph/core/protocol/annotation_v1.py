"""Shared metadata-to-annotation projection contract."""

from __future__ import annotations


SHARED_ANNOTATION_KEYS: dict[str, tuple[str, str]] = {
    "source": ("source", "observed"),
    "source_loc": ("source", "observed"),
    "trace_id": ("source", "observed"),
    "approved_by": ("source", "observed"),
    "note": ("source", "observed"),
    "raw_kind": ("semantic", "observed"),
    "bound": ("semantic", "observed"),
}


__all__ = ["SHARED_ANNOTATION_KEYS"]
