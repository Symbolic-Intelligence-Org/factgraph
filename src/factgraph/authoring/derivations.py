"""
High-level authoring entrypoints for derivation parsing, compilation, and preview.
"""

from __future__ import annotations

from .derivation_compile import AuthoringDerivationCompileError, compile_authoring_derivation_v1
from .derivation_dsl_parse import (
    AuthoringDerivationDSLParseError,
    parse_authoring_derivation_dsl_v1,
)
from .preflight import (
    AuthoringPreflightError,
    derivation_dry_run_preview,
    derivation_dry_run_preview_authoring,
)

__all__ = [
    "AuthoringDerivationCompileError",
    "AuthoringDerivationDSLParseError",
    "AuthoringPreflightError",
    "compile_authoring_derivation_v1",
    "derivation_dry_run_preview",
    "derivation_dry_run_preview_authoring",
    "parse_authoring_derivation_dsl_v1",
]
