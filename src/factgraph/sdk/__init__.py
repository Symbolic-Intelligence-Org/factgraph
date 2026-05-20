from __future__ import annotations

from .compile import (
    build_authoring_schema_from_classes,
    compile_schema_from_classes,
    schema_preflight_from_classes,
)
from .errors import (
    CardinalityError,
    EditorClosedError,
    EntityNotFoundError,
    FrozenSnapshotError,
    SDKRegistryError,
    SDKSchemaError,
    SDKStoreError,
)
from .error_codes import (
    INVALID_ROW_FORMAT,
    QUERY_ALIAS_CONFLICT,
    QUERY_INVALID_ROW_FORMAT,
    QUERY_MISSING_REF,
    QUERY_NOT_IMPLEMENTED,
    QUERY_TYPE_MISMATCH,
    QUERY_UNBOUND_VAR,
)
from .schema import Entity, Field, Identity, Relationship
from .semantics import ProbLogSemantics, PyReasonSemantics
from .store import FactGraph, SDKStore
from factgraph.application.authoring_runtime import SavedInferenceRef, SavedRuleRef
from factgraph.application.schema_mutation_runtime import SchemaAddResult
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store import AssertionInput, CommitResult, Database, MetaEntry
from .dsl import Branch, Inference, Not, Pred, Query, Rule, RuleRef, SDKDSLError, vars
from .ingest import IngestResult, ValidationReport

__all__ = [
    "SDKSchemaError",
    "SDKStoreError",
    "SDKRegistryError",
    "EntityNotFoundError",
    "FrozenSnapshotError",
    "CardinalityError",
    "EditorClosedError",
    "INVALID_ROW_FORMAT",
    "QUERY_MISSING_REF",
    "QUERY_TYPE_MISMATCH",
    "QUERY_ALIAS_CONFLICT",
    "QUERY_UNBOUND_VAR",
    "QUERY_INVALID_ROW_FORMAT",
    "QUERY_NOT_IMPLEMENTED",
    "IngestResult",
    "ValidationReport",
    "SDKDSLError",
    "Branch",
    "Entity",
    "Field",
    "Identity",
    "Relationship",
    "SemanticsProfile",
    "ProbLogSemantics",
    "PyReasonSemantics",
    "SavedRuleRef",
    "SavedInferenceRef",
    "SchemaAddResult",
    "AssertionInput",
    "CommitResult",
    "Database",
    "MetaEntry",
    "Rule",
    "RuleRef",
    "Inference",
    "Query",
    "Pred",
    "Not",
    "vars",
    "FactGraph",
    "SDKStore",
    "build_authoring_schema_from_classes",
    "compile_schema_from_classes",
    "schema_preflight_from_classes",
]
