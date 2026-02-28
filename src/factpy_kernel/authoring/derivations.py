from __future__ import annotations

"""
High-level authoring entrypoints for derivation parsing, compilation, and preview.
"""

from .preflight import (
    derivation_dry_run_preview,
    derivation_dry_run_preview_authoring,
    AuthoringPreflightError,
)
from .derivation_compile import AuthoringDerivationCompileError, compile_authoring_derivation_v1
from .derivation_dsl_parse import (
    AuthoringDerivationDSLParseError,
    parse_authoring_derivation_dsl_v1,
)

__all__ = [
    "AuthoringPreflightError",
    "AuthoringDerivationCompileError",
    "AuthoringDerivationDSLParseError",
    "compile_authoring_derivation_v1",
    "parse_authoring_derivation_dsl_v1",
    "derivation_dry_run_preview",
    "derivation_dry_run_preview_authoring",
]
