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
from factgraph.application.protocol import (
    AtomDescriptor,
    ExplicitBoolError,
    OccurrenceInspect,
    PortInspect,
    RuleExpr,
    RuleExprError,
    RuleExprInspect,
    RuleJoinConstraint,
)
from factgraph.application.protocol import Rule as ApplicationRule
from factgraph.application.schema_mutation_runtime import SchemaAddResult
from factgraph.core.semantics import SemanticsProfile
from factgraph.core.store import AssertionInput, CommitResult, Database, MetaEntry
from .dsl import (
    Branch,
    DSLToApplicationRuleError,
    Inference,
    Not,
    Pred,
    Query,
    Rule,
    RuleRef,
    SDKDSLError,
    build_application_rule,
    vars,
)
from .dsl import Rule as LegacyRule
from .ingest import IngestResult, ValidationReport

__all__ = [
    "SDKSchemaError",
    "SDKStoreError",
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
    "SchemaAddResult",
    "AssertionInput",
    "CommitResult",
    "Database",
    "MetaEntry",
    "Rule",
    "LegacyRule",
    "ApplicationRule",
    "RuleRef",
    "Inference",
    "Query",
    "Pred",
    "Not",
    "vars",
    "build_application_rule",
    "DSLToApplicationRuleError",
    "RuleExprInspect",
    "OccurrenceInspect",
    "AtomDescriptor",
    "PortInspect",
    "RuleExpr",
    "RuleExprError",
    "RuleJoinConstraint",
    "ExplicitBoolError",
    "FactGraph",
    "SDKStore",
    "build_authoring_schema_from_classes",
    "compile_schema_from_classes",
    "schema_preflight_from_classes",
]
