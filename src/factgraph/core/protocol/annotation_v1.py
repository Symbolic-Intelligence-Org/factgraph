"""Shared metadata-to-annotation projection contract."""

from __future__ import annotations

from dataclasses import dataclass

SHARED_ANNOTATION_KEYS: dict[str, tuple[str, str]] = {
    "source": ("source", "observed"),
    "source_loc": ("source", "observed"),
    "trace_id": ("source", "observed"),
    "approved_by": ("source", "observed"),
    "note": ("source", "observed"),
    "raw_kind": ("semantic", "observed"),
    "bound": ("semantic", "observed"),
}


@dataclass(frozen=True)
class InitialMetaAnnotationV1:
    """Annotation identity reproducible from one initial-meta event."""

    namespace: str
    category: str
    origin: str
    derivation: str | None = None


def initial_meta_annotation_v1(key: str) -> InitialMetaAnnotationV1 | None:
    """Return the deterministic annotation projection for an initial meta key."""
    shared = SHARED_ANNOTATION_KEYS.get(key)
    if shared is None:
        return None
    category, origin = shared
    return InitialMetaAnnotationV1(
        namespace="shared",
        category=category,
        origin=origin,
    )


__all__ = [
    "SHARED_ANNOTATION_KEYS",
    "InitialMetaAnnotationV1",
    "initial_meta_annotation_v1",
]
