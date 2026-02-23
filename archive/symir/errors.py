"""Custom exceptions for the lightweight IR system."""

from __future__ import annotations


class IRBaseError(Exception):
    """Base exception for IR-related failures."""


class SchemaError(IRBaseError):
    """Raised when a schema definition is invalid."""


class FactStoreError(IRBaseError):
    """Raised when loading or mapping fact data fails."""


class MappingError(IRBaseError):
    """Raised when mapping IR to a target language fails."""


class ValidationError(IRBaseError):
    """Raised when rule validation fails."""


class ProviderError(IRBaseError):
    """Raised when data provider operations fail."""


class RenderError(IRBaseError):
    """Raised when rendering fails."""
