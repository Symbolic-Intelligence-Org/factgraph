from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.store.runtime import Store
from factgraph.core.view.projector import project_view_facts

from .protocol.relation_query import (
    PublishedEntityFieldV1,
    PublishedRelationGraphV1,
    PublishedRelationPathV1,
    PublishedRelationQueryV1,
    PublishedStoredRelationV1,
    RelationQueryBindingV1,
    RelationQuerySourceV1,
)
from .protocol.schema_runtime import EntityRef
from .schema_runtime import SchemaIndex
from .value_validation import FieldValueValidationError, validate_field_value

RelationQueryStage = Literal["graph_admission", "query_compile", "query_execute"]


class RelationQueryError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: RelationQueryStage,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.path = tuple(path)
        self.details = dict(details or {})


@dataclass(frozen=True)
class ResolvedRelationQuerySelectionV1:
    alias: str
    value_type: str
    entity_type: str | None = None


@dataclass(frozen=True)
class SealedRelationQueryInvocationV1:
    query_digest: str
    graph_digest: str
    schema_digest: str
    publication_id: str
    row_limit: int
    dependency_predicate_ids: tuple[str, ...]
    domain_guard_predicate_ids: tuple[str, ...]
    selections: tuple[ResolvedRelationQuerySelectionV1, ...]
    _where_ir: tuple[Any, ...] = field(repr=False, compare=False)
    _selection_vars: tuple[str, ...] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        for name in ("query_digest", "graph_digest", "schema_digest", "publication_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.row_limit, int) or self.row_limit < 1:
            raise ValueError("row_limit must be a positive integer")
        if len(self.selections) != len(self._selection_vars) or not self.selections:
            raise ValueError("sealed relation query selections are malformed")
        expected = _invocation_digest(
            graph_digest=self.graph_digest,
            schema_digest=self.schema_digest,
            publication_id=self.publication_id,
            row_limit=self.row_limit,
            dependencies=self.dependency_predicate_ids,
            guards=self.domain_guard_predicate_ids,
            selections=self.selections,
            selection_vars=self._selection_vars,
            where_ir=self._where_ir,
        )
        if expected != self.query_digest:
            raise ValueError("sealed relation query digest does not match compiler output")


@dataclass(frozen=True)
class RelationQueryResultV1:
    query_digest: str
    rows: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.query_digest, str) or not self.query_digest:
            raise ValueError("query_digest must be a non-empty string")
        if not isinstance(self.rows, tuple) or not all(isinstance(row, dict) for row in self.rows):
            raise ValueError("rows must be a tuple of mappings")


@dataclass(frozen=True)
class _ResolvedSource:
    variable: str
    value_type: str
    entity_type: str | None
    predicate_id: str | None


@dataclass(frozen=True)
class _PathContext:
    path: PublishedRelationPathV1
    node_types: tuple[str, ...]
    node_vars: tuple[str, ...]
    relation_value_vars: tuple[str, ...]
    path_index: int


def compile_published_relation_query(
    query: PublishedRelationQueryV1,
    *,
    schema_index: SchemaIndex,
) -> SealedRelationQueryInvocationV1:
    """Compile only server-resolved published graph intent into a sealed invocation."""
    if not isinstance(query, PublishedRelationQueryV1):
        raise _error("query must be PublishedRelationQueryV1", "INVALID_RELATION_QUERY")
    if not isinstance(schema_index, SchemaIndex):
        raise _error("schema_index must be SchemaIndex", "INVALID_QUERY_SCHEMA")

    graph = query.graph
    field_by_key, relation_by_key, path_by_key = _validate_graph(graph, schema_index)
    all_sources = tuple(item.source for item in query.bindings) + tuple(
        item.source for item in query.selections
    )
    used_path_keys = sorted({source.path_key for source in all_sources})
    contexts: dict[str, _PathContext] = {}
    where: list[Any] = []
    dependencies: set[str] = set()
    guards: set[str] = set()

    for path_index, path_key in enumerate(used_path_keys):
        path = path_by_key.get(path_key)
        if path is None:
            raise _error(
                f"query references unpublished path {path_key!r}",
                "UNPUBLISHED_RELATION_PATH",
                path=("source", "path_key"),
            )
        node_types = _validate_path(path, relation_by_key, schema_index)
        context = _PathContext(
            path=path,
            node_types=node_types,
            node_vars=tuple(f"$rq_p{path_index}_n{idx}" for idx in range(len(node_types))),
            relation_value_vars=tuple(
                f"$rq_p{path_index}_r{idx}" for idx in range(len(path.steps))
            ),
            path_index=path_index,
        )
        contexts[path_key] = context
        for node_type, node_var in zip(context.node_types, context.node_vars, strict=True):
            guard = schema_index.entities[node_type].exists_predicate_id
            guards.add(guard)
            dependencies.add(guard)
            where.append(("pred", guard, [node_var]))
        for step_index, step in enumerate(path.steps):
            relation = relation_by_key[step.relation_key]
            left = context.node_vars[step_index]
            right = context.node_vars[step_index + 1]
            if step.direction == "reverse":
                left, right = right, left
            where.append(
                (
                    "pred",
                    relation.predicate_id,
                    [left, right, context.relation_value_vars[step_index]],
                )
            )
            dependencies.add(relation.predicate_id)

    field_vars: dict[RelationQuerySourceV1, str] = {}
    for source in sorted(
        {
            source
            for source in all_sources
            if source.kind == "field"
        },
        key=_source_key,
    ):
        context = contexts[source.path_key]
        resolved = _resolve_source(
            source,
            context=context,
            field_by_key=field_by_key,
            relation_by_key=relation_by_key,
            field_vars=field_vars,
        )
        assert resolved.predicate_id is not None
        field_vars[source] = resolved.variable
        where.append(
            (
                "pred",
                resolved.predicate_id,
                [context.node_vars[source.position], resolved.variable],
            )
        )
        dependencies.add(resolved.predicate_id)

    for binding in query.bindings:
        resolved = _resolve_source(
            binding.source,
            context=contexts[binding.source.path_key],
            field_by_key=field_by_key,
            relation_by_key=relation_by_key,
            field_vars=field_vars,
        )
        normalized = _normalize_binding(binding, resolved, schema_index)
        where.append((binding.operator, resolved.variable, normalized))

    resolved_selections: list[ResolvedRelationQuerySelectionV1] = []
    selection_vars: list[str] = []
    for selection in query.selections:
        resolved = _resolve_source(
            selection.source,
            context=contexts[selection.source.path_key],
            field_by_key=field_by_key,
            relation_by_key=relation_by_key,
            field_vars=field_vars,
        )
        resolved_selections.append(
            ResolvedRelationQuerySelectionV1(
                alias=selection.alias,
                value_type=resolved.value_type,
                entity_type=resolved.entity_type,
            )
        )
        selection_vars.append(resolved.variable)

    graph_digest = _graph_digest(graph)
    dependency_ids = tuple(sorted(dependencies))
    guard_ids = tuple(sorted(guards))
    selections = tuple(resolved_selections)
    selection_var_tuple = tuple(selection_vars)
    where_tuple = tuple(where)
    query_digest = _invocation_digest(
        graph_digest=graph_digest,
        schema_digest=schema_index.schema_digest,
        publication_id=graph.publication_id,
        row_limit=query.row_limit,
        dependencies=dependency_ids,
        guards=guard_ids,
        selections=selections,
        selection_vars=selection_var_tuple,
        where_ir=where_tuple,
    )
    return SealedRelationQueryInvocationV1(
        query_digest=query_digest,
        graph_digest=graph_digest,
        schema_digest=schema_index.schema_digest,
        publication_id=graph.publication_id,
        row_limit=query.row_limit,
        dependency_predicate_ids=dependency_ids,
        domain_guard_predicate_ids=guard_ids,
        selections=selections,
        _where_ir=where_tuple,
        _selection_vars=selection_var_tuple,
    )


def execute_published_relation_query(
    invocation: SealedRelationQueryInvocationV1,
    *,
    store: Store,
    schema_index: SchemaIndex,
) -> RelationQueryResultV1:
    """Execute a sealed compiler product; callers never supply raw query IR."""
    if not isinstance(invocation, SealedRelationQueryInvocationV1):
        raise _error(
            "invocation must be SealedRelationQueryInvocationV1",
            "INVALID_SEALED_RELATION_QUERY",
            stage="query_execute",
        )
    SealedRelationQueryInvocationV1.__post_init__(invocation)
    if not isinstance(store, Store) or not isinstance(schema_index, SchemaIndex):
        raise _error(
            "store and schema_index must be trusted runtime values",
            "INVALID_RELATION_QUERY_RUNTIME",
            stage="query_execute",
        )
    if schema_index.schema_digest != invocation.schema_digest:
        raise _error(
            "sealed relation query schema pin does not match runtime schema",
            "RELATION_QUERY_SCHEMA_DRIFT",
            stage="query_execute",
        )
    bindings = evaluate_native_where(
        project_view_facts(store.ledger, store.schema_ir),
        list(invocation._where_ir),
    ).bindings
    if len(bindings) > invocation.row_limit:
        raise _error(
            "relation query result exceeds its published row limit",
            "RELATION_QUERY_ROW_LIMIT_EXCEEDED",
            stage="query_execute",
            details={"row_count": len(bindings), "row_limit": invocation.row_limit},
        )
    rows = tuple(
        {
            selection.alias: binding.get(variable)
            for selection, variable in zip(
                invocation.selections,
                invocation._selection_vars,
                strict=True,
            )
        }
        for binding in bindings
    )
    return RelationQueryResultV1(query_digest=invocation.query_digest, rows=rows)


def _validate_graph(
    graph: PublishedRelationGraphV1,
    index: SchemaIndex,
) -> tuple[
    dict[str, PublishedEntityFieldV1],
    dict[str, PublishedStoredRelationV1],
    dict[str, PublishedRelationPathV1],
]:
    raw_predicates = {
        item.get("pred_id"): item
        for item in index.schema_ir.get("predicates", [])
        if isinstance(item, dict) and isinstance(item.get("pred_id"), str)
    }
    fields = {item.key: item for item in graph.fields}
    relations = {item.key: item for item in graph.relations}
    paths = {item.key: item for item in graph.paths}

    for field_spec in graph.fields:
        if field_spec.node_kind != "stored_field":
            raise _forbidden_node(field_spec.key, field_spec.node_kind)
        predicate = index.predicates_by_id.get(field_spec.predicate_id)
        raw = raw_predicates.get(field_spec.predicate_id)
        if predicate is None or raw is None or raw.get("relationship_type") is not None:
            raise _graph_error(field_spec.key, "field predicate is not a stored entity field")
        if (
            predicate.owner_type != field_spec.entity_type
            or predicate.value_type_domain != field_spec.value_type
            or predicate.cardinality != field_spec.cardinality
        ):
            raise _graph_error(
                field_spec.key,
                "field endpoint/type/cardinality does not match schema",
            )

    for relation_spec in graph.relations:
        if relation_spec.node_kind != "stored_relation":
            raise _forbidden_node(relation_spec.key, relation_spec.node_kind)
        predicate = index.predicates_by_id.get(relation_spec.predicate_id)
        raw = raw_predicates.get(relation_spec.predicate_id)
        arg_specs = raw.get("arg_specs") if isinstance(raw, dict) else None
        if (
            predicate is None
            or not isinstance(raw, dict)
            or not isinstance(raw.get("relationship_type"), str)
            or not isinstance(arg_specs, list)
            or len(arg_specs) != 3
        ):
            raise _graph_error(
                relation_spec.key,
                "relation predicate is not a stored ternary relation",
            )
        if (
            raw.get("from_entity_type") != relation_spec.from_entity_type
            or raw.get("to_entity_type") != relation_spec.to_entity_type
            or not isinstance(arg_specs[2], dict)
            or arg_specs[2].get("type_domain") != relation_spec.value_type
            or predicate.cardinality != relation_spec.cardinality
        ):
            raise _graph_error(
                relation_spec.key,
                "relation endpoint/type/cardinality does not match schema",
            )
        if (
            relation_spec.from_entity_type not in index.entities
            or relation_spec.to_entity_type not in index.entities
        ):
            raise _graph_error(
                relation_spec.key,
                "relation endpoint entity type is not in schema",
            )

    for path in graph.paths:
        _validate_path(path, relations, index)
    return fields, relations, paths


def _validate_path(
    path: PublishedRelationPathV1,
    relations: dict[str, PublishedStoredRelationV1],
    index: SchemaIndex,
) -> tuple[str, ...]:
    if path.root_entity_type not in index.entities:
        raise _graph_error(path.key, "path root entity type is not in schema")
    nodes = [path.root_entity_type]
    current = path.root_entity_type
    for step_index, step in enumerate(path.steps):
        relation = relations.get(step.relation_key)
        if relation is None:
            raise _graph_error(path.key, f"step {step_index} references unpublished relation")
        expected = (
            relation.from_entity_type
            if step.direction == "forward"
            else relation.to_entity_type
        )
        next_type = (
            relation.to_entity_type
            if step.direction == "forward"
            else relation.from_entity_type
        )
        if current != expected:
            raise _error(
                f"published path {path.key!r} is not endpoint-continuous at step {step_index}",
                "RELATION_PATH_DISCONTINUITY",
                path=("graph", "paths", path.key, "steps", str(step_index)),
                details={"expected_entity_type": expected, "actual_entity_type": current},
            )
        nodes.append(next_type)
        current = next_type
    return tuple(nodes)


def _resolve_source(
    source: RelationQuerySourceV1,
    *,
    context: _PathContext,
    field_by_key: dict[str, PublishedEntityFieldV1],
    relation_by_key: dict[str, PublishedStoredRelationV1],
    field_vars: dict[RelationQuerySourceV1, str],
) -> _ResolvedSource:
    if source.kind == "entity":
        if source.position >= len(context.node_vars):
            raise _source_error(source, "entity position is outside the published path")
        entity_type = context.node_types[source.position]
        return _ResolvedSource(
            variable=context.node_vars[source.position],
            value_type="entity_ref",
            entity_type=entity_type,
            predicate_id=None,
        )
    if source.kind == "field":
        if source.position >= len(context.node_vars):
            raise _source_error(source, "field position is outside the published path")
        field_spec = field_by_key.get(source.member_key or "")
        if field_spec is None:
            raise _source_error(source, "field source references an unpublished field")
        if field_spec.entity_type != context.node_types[source.position]:
            raise _source_error(source, "field source entity type does not match its path node")
        variable = field_vars.get(
            source,
            f"$rq_p{context.path_index}_f{_stable_member_index(field_by_key, field_spec.key)}_n{source.position}",
        )
        return _ResolvedSource(
            variable=variable,
            value_type=field_spec.value_type,
            entity_type=None,
            predicate_id=field_spec.predicate_id,
        )
    if source.position >= len(context.path.steps):
        raise _source_error(source, "relation position is outside the published path")
    step = context.path.steps[source.position]
    if source.member_key != step.relation_key:
        raise _source_error(source, "relation source does not name the relation at its path position")
    relation = relation_by_key.get(source.member_key or "")
    if relation is None:
        raise _source_error(source, "relation source references an unpublished relation")
    return _ResolvedSource(
        variable=context.relation_value_vars[source.position],
        value_type=relation.value_type,
        entity_type=None,
        predicate_id=relation.predicate_id,
    )


def _normalize_binding(
    binding: RelationQueryBindingV1,
    resolved: _ResolvedSource,
    index: SchemaIndex,
) -> Any:
    value = binding.value
    if resolved.value_type == "entity_ref":
        if binding.operator not in {"eq", "ne"}:
            raise _source_error(
                binding.source,
                "entity bindings only support equality comparisons",
            )
        if not isinstance(value, EntityRef) or value.encoded_ref is None:
            raise _source_error(binding.source, "entity binding requires a resolved EntityRef")
        if value.entity_type != resolved.entity_type or value.entity_type not in index.entities:
            raise _source_error(binding.source, "entity binding type does not match its path node")
        return value.encoded_ref
    if isinstance(value, EntityRef):
        raise _source_error(binding.source, "scalar binding cannot contain EntityRef")
    if binding.operator in {"gt", "ge", "lt", "le"} and resolved.value_type not in {
        "int",
        "float64",
        "time",
    }:
        raise _source_error(
            binding.source,
            "ordering comparison requires int, float64, or time",
        )
    assert resolved.predicate_id is not None
    predicate = replace(
        index.predicates_by_id[resolved.predicate_id],
        value_type_domain=resolved.value_type,
    )
    try:
        validate_field_value(value, pred_info=predicate)
    except FieldValueValidationError as exc:
        raise _error(
            "relation query binding does not match its published type",
            "RELATION_QUERY_BINDING_TYPE_MISMATCH",
            path=("bindings", binding.source.path_key),
            details={"cause_code": exc.code},
        ) from exc
    return value


def _graph_digest(graph: PublishedRelationGraphV1) -> str:
    return sha256_hex(_canonical_bytes(graph))


def _invocation_digest(
    *,
    graph_digest: str,
    schema_digest: str,
    publication_id: str,
    row_limit: int,
    dependencies: tuple[str, ...],
    guards: tuple[str, ...],
    selections: tuple[ResolvedRelationQuerySelectionV1, ...],
    selection_vars: tuple[str, ...],
    where_ir: tuple[Any, ...],
) -> str:
    return sha256_hex(
        _canonical_bytes(
            {
                "kind": "sealed_relation_query_v1",
                "graph_digest": graph_digest,
                "schema_digest": schema_digest,
                "publication_id": publication_id,
                "row_limit": row_limit,
                "dependencies": dependencies,
                "guards": guards,
                "selections": selections,
                "selection_vars": selection_vars,
                "where": where_ir,
            }
        )
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_value(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _canonical_value(getattr(value, name))
            for name in value.__dataclass_fields__
            if not name.startswith("_")
        }
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, bytes):
        return {"bytes_b64": base64.b64encode(value).decode("ascii")}
    return value


def _source_key(source: RelationQuerySourceV1) -> tuple[str, int, str, str]:
    return (source.path_key, source.position, source.kind, source.member_key or "")


def _stable_member_index(fields: dict[str, PublishedEntityFieldV1], key: str) -> int:
    return sorted(fields).index(key)


def _error(
    message: str,
    code: str,
    *,
    stage: RelationQueryStage = "query_compile",
    path: tuple[str, ...] = (),
    details: dict[str, Any] | None = None,
) -> RelationQueryError:
    return RelationQueryError(
        message,
        code=code,
        stage=stage,
        path=path,
        details=details,
    )


def _graph_error(key: str, message: str) -> RelationQueryError:
    return _error(
        f"published graph member {key!r}: {message}",
        "PUBLISHED_RELATION_GRAPH_MISMATCH",
        stage="graph_admission",
        path=("graph", key),
    )


def _forbidden_node(key: str, node_kind: str) -> RelationQueryError:
    return _error(
        f"query graph node {key!r} has forbidden kind {node_kind!r}",
        "QUERY_NODE_KIND_FORBIDDEN",
        stage="graph_admission",
        path=("graph", key, "node_kind"),
        details={"node_kind": node_kind},
    )


def _source_error(source: RelationQuerySourceV1, message: str) -> RelationQueryError:
    return _error(
        message,
        "INVALID_RELATION_QUERY_SOURCE",
        path=("source", source.path_key, str(source.position), source.kind),
    )


__all__ = [
    "RelationQueryError",
    "RelationQueryResultV1",
    "ResolvedRelationQuerySelectionV1",
    "SealedRelationQueryInvocationV1",
    "compile_published_relation_query",
    "execute_published_relation_query",
]
