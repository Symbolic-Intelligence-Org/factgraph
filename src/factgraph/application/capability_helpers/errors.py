"""Capability helper error classes."""

from __future__ import annotations


class CapabilityHelperError(ValueError):
    """Raised when an ergonomic helper cannot build a valid capability input."""


class OriginPackageError(CapabilityHelperError):
    """Raised when SDK-package objects are passed to application helpers."""


__all__ = [
    "CapabilityHelperError",
    "OriginPackageError",
]
