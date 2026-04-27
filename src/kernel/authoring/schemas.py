from __future__ import annotations

"""
High-level authoring entrypoints for schema parsing, compilation, and preflight.

This module groups the schema-facing public surface so callers do not need to
remember the individual leaf module names.
"""

from .preflight import schema_preflight, schema_preflight_authoring, AuthoringPreflightError
from .schema_compile import AuthoringSchemaCompileError, compile_authoring_schema_v1
from .schema_dsl_parse import AuthoringSchemaDSLParseError, parse_authoring_schema_dsl_v1

__all__ = [
    "AuthoringPreflightError",
    "AuthoringSchemaCompileError",
    "AuthoringSchemaDSLParseError",
    "compile_authoring_schema_v1",
    "parse_authoring_schema_dsl_v1",
    "schema_preflight",
    "schema_preflight_authoring",
]
